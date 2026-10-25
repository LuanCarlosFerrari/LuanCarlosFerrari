"""Dublês para testar sem rede e sem gastar: Claude e Scryfall falsos."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import httpx

SAMPLE_ANALYSIS: dict[str, Any] = {
    "tipo_tela": "construtor_de_deck",
    "formato_visivel": "Histórico",
    "nome_do_deck": "Lobos",
    "cartas": [
        {
            "nome_na_tela": "Tovolar, Soberano Medonho",
            "nome_ingles": "Tovolar, Dire Overlord",
            "quantidade": 4,
            "confianca": "alta",
        },
        {
            "nome_na_tela": "Floresta",
            "nome_ingles": "Forrest",
            "quantidade": 10,
            "confianca": "media",
        },
        {
            "nome_na_tela": "???",
            "nome_ingles": "Carta Inexistente",
            "quantidade": 2,
            "confianca": "baixa",
        },
    ],
    "guia": {
        "resumo": "Agressivo tribal.",
        "plano_de_jogo": "Curvar lobos.",
        "mulligan": "Mantenha 2-4 terrenos.",
        "dicas": ["Transforme Tovolar no seu turno."],
        "trocas": [{"sai": "A", "entra": "B", "motivo": "C"}],
    },
}


class FakeClaude:
    def __init__(self, text: str | None = None, stop_reason: str = "end_turn") -> None:
        self.text = json.dumps(SAMPLE_ANALYSIS) if text is None else text
        self.stop_reason = stop_reason
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **request: Any) -> Iterator[SimpleNamespace]:
        self.requests.append(request)
        message = SimpleNamespace(
            model=request["model"],
            stop_reason=self.stop_reason,
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=self.text),
            ],
            usage=SimpleNamespace(
                input_tokens=3000,
                output_tokens=1000,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=None,
            ),
        )
        yield SimpleNamespace(get_final_message=lambda: message)


SCRYFALL_CARDS: dict[str, dict[str, Any]] = {
    "tovolar, dire overlord": {
        "name": "Tovolar, Dire Overlord // Tovolar, the Midnight Scourge",
        "oracle_id": "oid-tovolar",
        "arena_id": 78613,
        "rarity": "rare",
        "type_line": "Legendary Creature — Human Wolf // Legendary Creature — Werewolf",
        "card_faces": [{"mana_cost": "{1}{R}{G}"}, {"mana_cost": ""}],
        "set": "mid",
        "collector_number": "246",
    },
    "forest": {
        "name": "Forest",
        "oracle_id": "oid-forest",
        "arena_id": 1,
        "rarity": "common",
        "type_line": "Basic Land — Forest",
        "mana_cost": "",
        "set": "fdn",
        "collector_number": "1",
    },
}
PT_NAMES = {
    "oid-tovolar": {
        "card_faces": [
            {"printed_name": "Tovolar, Soberano Medonho"},
            {"printed_name": "Tovolar, Flagelo da Meia-noite"},
        ]
    },
    "oid-forest": {"printed_name": "Floresta"},
}


def scryfall_transport(calls: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        params = request.url.params
        if request.url.path == "/cards/named":
            if "exact" in params:
                card = SCRYFALL_CARDS.get(params["exact"].lower())
            else:
                fuzzy = params["fuzzy"].lower()
                card = SCRYFALL_CARDS.get("forest") if fuzzy == "forrest" else None
            return httpx.Response(200, json=card) if card else httpx.Response(404, json={})
        if request.url.path == "/cards/search":
            oid = params["q"].split()[0].removeprefix("oracleid:")
            pt = PT_NAMES.get(oid)
            return httpx.Response(200, json={"data": [pt]}) if pt else httpx.Response(404, json={})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)


def scryfall_client(calls: list[str]) -> httpx.Client:
    return httpx.Client(base_url="https://api.scryfall.com", transport=scryfall_transport(calls))
