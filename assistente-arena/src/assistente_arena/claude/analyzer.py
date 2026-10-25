"""Análise de uma captura do construtor de decks ou da coleção com o Claude."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, ValidationError

from assistente_arena.claude.costs import Usage
from assistente_arena.screen.capture import PreparedImage

# Modelos que aceitam o fallback automático do servidor quando recusam um pedido.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16000
# Prompt + esquema (~1.500) e resposta típica com raciocínio (~2.500), para a estimativa.
ESTIMATED_TEXT_INPUT_TOKENS = 1500
ESTIMATED_OUTPUT_TOKENS = 2500

SYSTEM_PROMPT = """\
Você é um treinador de Magic: The Gathering Arena e analisa capturas de tela do jogo \
para um jogador brasileiro. Ele joga principalmente Histórico, com decks tribais.

Você recebe a imagem da janela do Arena fora de partida: o construtor de decks ou a \
coleção. Faça o seguinte:
1. Diga que tela é essa.
2. Liste as cartas visíveis. No construtor de decks, use a lista do deck (coluna à \
direita), com as quantidades. Na coleção, use as cartas exibidas e a quantidade que \
o jogador possui (os marcadores de cópias). Para cada carta, informe o nome como \
aparece na tela e o nome oficial em inglês. Se não tiver certeza da leitura, use \
confiança "baixa" em vez de inventar.
3. No construtor de decks, escreva um guia curto e prático de como jogar o deck: \
plano de jogo, mulligan, cartas para segurar, combinações e ameaças comuns do formato. \
Sugira até 4 trocas, explicando o motivo. Na coleção ou em outra tela, deixe os \
campos do guia vazios.

Escreva tudo em português do Brasil. No texto do guia, cite cartas como \
"Nome em português (Nome em inglês)". Seja direto, sem enfeites.\
"""

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tipo_tela": {"type": "string", "enum": ["construtor_de_deck", "colecao", "outra"]},
        "formato_visivel": {"type": "string"},
        "nome_do_deck": {"type": "string"},
        "cartas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nome_na_tela": {"type": "string"},
                    "nome_ingles": {"type": "string"},
                    "quantidade": {"type": "integer"},
                    "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                },
                "required": ["nome_na_tela", "nome_ingles", "quantidade", "confianca"],
                "additionalProperties": False,
            },
        },
        "guia": {
            "type": "object",
            "properties": {
                "resumo": {"type": "string"},
                "plano_de_jogo": {"type": "string"},
                "mulligan": {"type": "string"},
                "dicas": {"type": "array", "items": {"type": "string"}},
                "trocas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sai": {"type": "string"},
                            "entra": {"type": "string"},
                            "motivo": {"type": "string"},
                        },
                        "required": ["sai", "entra", "motivo"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["resumo", "plano_de_jogo", "mulligan", "dicas", "trocas"],
            "additionalProperties": False,
        },
    },
    "required": ["tipo_tela", "formato_visivel", "nome_do_deck", "cartas", "guia"],
    "additionalProperties": False,
}


class CartaLida(BaseModel):
    nome_na_tela: str
    nome_ingles: str
    quantidade: int
    confianca: Literal["alta", "media", "baixa"]


class Troca(BaseModel):
    sai: str
    entra: str
    motivo: str


class Guia(BaseModel):
    resumo: str
    plano_de_jogo: str
    mulligan: str
    dicas: list[str]
    trocas: list[Troca]


class AnaliseTela(BaseModel):
    tipo_tela: Literal["construtor_de_deck", "colecao", "outra"]
    formato_visivel: str
    nome_do_deck: str
    cartas: list[CartaLida]
    guia: Guia


class AnalysisError(RuntimeError):
    """Falha na análise. `usage` vem preenchido quando a chamada foi cobrada."""

    def __init__(self, message: str, usage: Usage | None = None, model: str = "") -> None:
        super().__init__(message)
        self.usage = usage
        self.model = model


@dataclass(frozen=True)
class AnalysisResult:
    analysis: AnaliseTela
    model: str
    usage: Usage


def estimate_usage(image: PreparedImage) -> Usage:
    return Usage(
        input_tokens=image.estimated_tokens + ESTIMATED_TEXT_INPUT_TOKENS,
        output_tokens=ESTIMATED_OUTPUT_TOKENS,
    )


def build_request(
    image: PreparedImage, model: str, effort: str, format_hint: str
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.standard_b64encode(image.png).decode("ascii"),
                        },
                    },
                    {
                        "type": "text",
                        "text": f"Formato que pretendo jogar: {format_hint}. Analise esta tela.",
                    },
                ],
            }
        ],
    }
    if model in FALLBACK_MODELS:
        request["betas"] = [FALLBACK_BETA]
        request["fallbacks"] = "default"
    return request


def analyze(
    client: anthropic.Anthropic,
    image: PreparedImage,
    *,
    model: str,
    effort: str,
    format_hint: str,
) -> AnalysisResult:
    request = build_request(image, model, effort, format_hint)
    try:
        with client.beta.messages.stream(**request) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise AnalysisError("Chave da API inválida. Rode: assistente-arena chave") from e
    except anthropic.PermissionDeniedError as e:
        raise AnalysisError("A chave da API não tem permissão para este modelo.") from e
    except anthropic.RateLimitError as e:
        raise AnalysisError("Limite de uso da API atingido. Tente de novo em instantes.") from e
    except anthropic.APIConnectionError as e:
        raise AnalysisError("Sem conexão com a API da Anthropic.") from e
    except anthropic.APIStatusError as e:
        raise AnalysisError(f"Erro da API ({e.status_code}): {e.message}") from e

    raw_usage = response.usage
    usage = Usage(
        input_tokens=raw_usage.input_tokens,
        output_tokens=raw_usage.output_tokens,
        cache_read_tokens=raw_usage.cache_read_input_tokens or 0,
        cache_write_tokens=raw_usage.cache_creation_input_tokens or 0,
    )
    if response.stop_reason == "refusal":
        raise AnalysisError("O Claude recusou analisar esta imagem.", usage, response.model)
    if response.stop_reason == "max_tokens":
        raise AnalysisError(
            "A resposta ficou longa demais e foi cortada. Tente de novo.", usage, response.model
        )
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        analysis = parse_analysis(text)
    except AnalysisError as e:
        raise AnalysisError(str(e), usage, response.model) from e
    return AnalysisResult(analysis, response.model, usage)


def parse_analysis(text: str) -> AnaliseTela:
    try:
        return AnaliseTela.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as e:
        raise AnalysisError("A resposta do Claude não veio no formato esperado.") from e
