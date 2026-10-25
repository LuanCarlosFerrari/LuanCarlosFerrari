from __future__ import annotations

import json
from pathlib import Path

import httpx

from assistente_arena.claude.costs import (
    ExchangeRate,
    Ledger,
    Usage,
    check_budget,
    cost_usd,
    format_brl,
)


def test_cost_opus() -> None:
    usage = Usage(input_tokens=6000, output_tokens=800)
    assert abs(cost_usd("claude-opus-5-5", usage) - 0.040) < 1e-9


def test_cost_includes_cache() -> None:
    usage = Usage(0, 0, cache_read_tokens=1_000_000, cache_write_tokens=1_000_000)
    assert abs(cost_usd("claude-opus-5-5", usage) - (0.20 + 5.0)) < 1e-9


def test_format_brl() -> None:
    assert format_brl(0.2) == "R$ 0,20"
    assert format_brl(1234.5) == "R$ 1.234,50"


def test_budget() -> None:
    assert check_budget(1.0, 0.2, 20.0).allowed
    assert check_budget(1.0, 0.2, 20.0).message == ""
    warn = check_budget(16.0, 0.2, 20.0)
    assert warn.allowed and "Atenção" in warn.message
    assert not check_budget(19.9, 0.2, 20.0).allowed


def test_ledger_month_total(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "g.db")
    brl = ledger.record("teste", "claude-opus-5-5", Usage(6000, 800), rate=5.0)
    assert abs(brl - 0.20) < 1e-9
    assert abs(ledger.month_total_brl() - 0.20) < 1e-9
    assert ledger.month_count() == 1
    ledger.close()


def test_exchange_rate_fetch_and_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={"value": [{"cotacaoVenda": 5.0383, "dataHoraCotacao": "2026-10-22 13:12:09.3"}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rates = ExchangeRate(tmp_path / "c.json", manual_rate=5.5)
    assert rates.get(client) == (5.0383, "PTAX 22/10/2026")
    assert rates.get(client) == (5.0383, "PTAX 22/10/2026")
    assert len(calls) == 1


def test_exchange_rate_falls_back_to_manual(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rate, source = ExchangeRate(tmp_path / "c.json", manual_rate=5.5).get(client)
    assert rate == 5.5 and "manual" in source


def test_exchange_rate_uses_stale_cache_offline(tmp_path: Path) -> None:
    cache = tmp_path / "c.json"
    cache.write_text(
        json.dumps({"dia": "2000-01-01", "cotacao": 5.1, "fonte": "x", "fonte_data": "20/10/2026"})
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rate, source = ExchangeRate(cache, manual_rate=5.5).get(client)
    assert rate == 5.1 and "20/10/2026" in source
