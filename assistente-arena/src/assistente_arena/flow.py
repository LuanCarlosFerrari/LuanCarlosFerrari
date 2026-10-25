"""Fluxo da análise de tela: bloqueio → orçamento → Claude → conferência no Scryfall."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import anthropic

from assistente_arena.arena_log.monitor import read_state
from assistente_arena.arena_log.reader import ArenaState
from assistente_arena.cards.scryfall import CardInfo, Scryfall
from assistente_arena.claude.analyzer import (
    AnaliseTela,
    AnalysisError,
    CartaLida,
    analyze,
    estimate_usage,
)
from assistente_arena.claude.costs import ExchangeRate, Ledger, check_budget, cost_usd
from assistente_arena.config import Settings, data_dir, get_api_key
from assistente_arena.screen.capture import PreparedImage
from assistente_arena.screen.gate import evaluate

Status = Literal["ok", "corrigida", "conferir", "nao_encontrada"]


@dataclass(frozen=True)
class CheckedCard:
    read: CartaLida
    card: CardInfo | None
    status: Status


@dataclass
class Report:
    analysis: AnaliseTela | None = None
    cards: list[CheckedCard] = field(default_factory=list)
    model: str = ""
    cost_brl: float = 0.0
    month_brl: float = 0.0
    budget_brl: float = 0.0
    rate_source: str = ""
    warnings: list[str] = field(default_factory=list)
    blocked: str = ""


def check_cards(analysis: AnaliseTela, scryfall: Scryfall) -> list[CheckedCard]:
    checked: list[CheckedCard] = []
    for read in analysis.cartas:
        card, corrected = scryfall.find(read.nome_ingles)
        status: Status
        if card is None:
            status = "nao_encontrada"
        elif corrected:
            status = "corrigida"
        elif read.confianca == "baixa":
            status = "conferir"
        else:
            status = "ok"
        checked.append(CheckedCard(read, card, status))
    return checked


def run_analysis(
    image: PreparedImage,
    *,
    live: bool,
    settings: Settings,
    log_path: Path,
    format_hint: str,
    state: ArenaState | None = None,
    client: anthropic.Anthropic | None = None,
) -> Report:
    report = Report(budget_brl=settings.orcamento_mensal_brl)

    # 1. Nunca durante uma partida.
    if state is None:
        state = read_state(log_path)
    decision = evaluate(state, live=live)
    if not decision.allowed:
        report.blocked = decision.reason
        return report
    if decision.warning:
        report.warnings.append(decision.warning)

    # 2. Orçamento.
    folder = data_dir()
    rate, report.rate_source = ExchangeRate(
        folder / "cotacao.json", settings.cotacao_dolar_manual
    ).get()
    ledger = Ledger(folder / "gastos.db")
    try:
        estimate = cost_usd(settings.modelo, estimate_usage(image)) * rate
        report.month_brl = ledger.month_total_brl()
        budget = check_budget(report.month_brl, estimate, settings.orcamento_mensal_brl)
        if not budget.allowed:
            report.blocked = budget.message
            return report
        if budget.message:
            report.warnings.append(budget.message)

        # 3. Claude.
        if client is None:
            key = get_api_key()
            if not key:
                report.blocked = (
                    "Chave da API não configurada. Rode: assistente-arena chave "
                    "(ou defina a variável ANTHROPIC_API_KEY)."
                )
                return report
            client = anthropic.Anthropic(api_key=key)
        try:
            result = analyze(
                client,
                image,
                model=settings.modelo,
                effort=settings.esforco,
                format_hint=format_hint,
            )
        except AnalysisError as e:
            if e.usage is not None:
                report.cost_brl = ledger.record(
                    "analise_tela", e.model or settings.modelo, e.usage, rate
                )
                report.month_brl += report.cost_brl
            report.blocked = str(e)
            return report

        report.cost_brl = ledger.record("analise_tela", result.model, result.usage, rate)
        report.month_brl += report.cost_brl
        report.model = result.model
        report.analysis = result.analysis
    finally:
        ledger.close()

    # 4. Conferência dos nomes.
    scryfall = Scryfall(folder / "cartas.db")
    try:
        report.cards = check_cards(result.analysis, scryfall)
    except Exception as e:  # sem internet: mostra a leitura crua mesmo assim
        report.warnings.append(f"Não consegui conferir os nomes no Scryfall ({e}).")
        report.cards = [CheckedCard(c, None, "conferir") for c in result.analysis.cartas]
    finally:
        scryfall.close()
    return report
