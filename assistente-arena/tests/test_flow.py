from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fakes import FakeClaude, scryfall_client
from PIL import Image

import assistente_arena.flow as flow
from assistente_arena.arena_log.reader import ArenaState
from assistente_arena.cards.scryfall import Scryfall
from assistente_arena.claude.costs import ExchangeRate, Ledger
from assistente_arena.config import Settings, data_dir
from assistente_arena.report import arena_export, render
from assistente_arena.screen.capture import prepare


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(ExchangeRate, "get", lambda self, client=None: (5.0, "PTAX teste"))
    original = Scryfall.__init__

    def fake_init(self: Scryfall, cache_path: Path, client: httpx.Client | None = None) -> None:
        original(self, cache_path, scryfall_client(calls))

    monkeypatch.setattr(Scryfall, "__init__", fake_init)
    return calls


def _run(
    state: ArenaState | None,
    client: FakeClaude,
    settings: Settings | None = None,
    live: bool = True,
) -> flow.Report:
    return flow.run_analysis(
        prepare(Image.new("RGB", (100, 50))),
        live=live,
        settings=settings or Settings(),
        log_path=Path("nao-usado.log"),
        format_hint="Histórico",
        state=state,
        client=client,  # type: ignore[arg-type]
    )


def test_full_flow_outside_match(offline: list[str]) -> None:
    client = FakeClaude()
    report = _run(ArenaState(detailed_logs=True), client)
    assert report.blocked == ""
    statuses = [c.status for c in report.cards]
    assert statuses == ["ok", "corrigida", "nao_encontrada"]
    # 3000 entrada × US$4/M + 1000 saída × US$20/M = US$0,032 → R$0,16 a R$5,00
    assert abs(report.cost_brl - 0.16) < 1e-9
    text = render(report)
    assert "Tovolar, Soberano Medonho" in text and "R$ 0,16" in text
    assert "Como jogar este deck" in text
    assert arena_export(report.cards).splitlines()[1] == "4 Tovolar, Dire Overlord"


def test_in_match_never_calls_claude(offline: list[str]) -> None:
    client = FakeClaude()
    report = _run(ArenaState(in_match=True, detailed_logs=True), client)
    assert "Partida em andamento" in report.blocked
    assert client.requests == []


def test_budget_blocks_before_calling(offline: list[str]) -> None:
    ledger = Ledger(data_dir() / "gastos.db")
    from assistente_arena.claude.costs import Usage

    ledger.record("x", "claude-opus-5-5", Usage(0, 1_000_000), rate=1.0)  # R$ 20
    ledger.close()
    client = FakeClaude()
    report = _run(ArenaState(detailed_logs=True), client)
    assert "Orçamento" in report.blocked and client.requests == []


def test_refusal_is_still_billed(offline: list[str]) -> None:
    report = _run(ArenaState(detailed_logs=True), FakeClaude(stop_reason="refusal"))
    assert "recusou" in report.blocked and report.cost_brl > 0


def test_missing_api_key_blocks(offline: list[str]) -> None:
    report = flow.run_analysis(
        prepare(Image.new("RGB", (10, 10))),
        live=True,
        settings=Settings(),
        log_path=Path("x.log"),
        format_hint="H",
        state=ArenaState(detailed_logs=True),
    )
    assert "Chave da API" in report.blocked
