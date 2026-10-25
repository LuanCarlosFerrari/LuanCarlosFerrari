"""Custos da API em reais: tabela de preços, cotação PTAX e orçamento mensal."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

# Dólares por milhão de tokens (preço público da API, out/2026).
PRICES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01},
}
CACHE_WRITE_MULTIPLIER = 1.25
PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def price_for(model: str) -> dict[str, float]:
    return PRICES_USD_PER_MTOK.get(model, PRICES_USD_PER_MTOK["claude-opus-5-5"])


def cost_usd(model: str, usage: Usage) -> float:
    p = price_for(model)
    return (
        usage.input_tokens * p["input"]
        + usage.output_tokens * p["output"]
        + usage.cache_read_tokens * p["cache_read"]
        + usage.cache_write_tokens * p["input"] * CACHE_WRITE_MULTIPLIER
    ) / 1_000_000


def format_brl(value: float) -> str:
    """R$ 1.234,56 (formato brasileiro)."""
    text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


class ExchangeRate:
    """Cotação de venda PTAX do Banco Central, guardada por dia."""

    def __init__(self, cache_file: Path, manual_rate: float) -> None:
        self._cache_file = cache_file
        self._manual = manual_rate

    def get(self, client: httpx.Client | None = None) -> tuple[float, str]:
        today = date.today().isoformat()
        cached = self._read_cache()
        if cached and cached.get("dia") == today:
            return float(cached["cotacao"]), str(cached["fonte"])
        try:
            rate, when = self._fetch(client)
        except (httpx.HTTPError, KeyError, ValueError, IndexError):
            if cached:
                return float(cached["cotacao"]), f"PTAX de {cached['fonte_data']} (sem internet)"
            return self._manual, "cotação manual das configurações"
        source = f"PTAX {when}"
        self._cache_file.write_text(
            json.dumps({"dia": today, "cotacao": rate, "fonte": source, "fonte_data": when}),
            encoding="utf-8",
        )
        return rate, source

    def _read_cache(self) -> dict[str, Any] | None:
        try:
            data: dict[str, Any] = json.loads(self._cache_file.read_text(encoding="utf-8"))
            return data
        except (OSError, ValueError):
            return None

    @staticmethod
    def _fetch(client: httpx.Client | None) -> tuple[float, str]:
        end = date.today()
        start = end - timedelta(days=10)  # cobre fins de semana e feriados
        params = {
            "@dataInicial": f"'{start:%m-%d-%Y}'",
            "@dataFinalCotacao": f"'{end:%m-%d-%Y}'",
            "$format": "json",
            "$select": "cotacaoVenda,dataHoraCotacao",
        }
        http = client or httpx.Client(timeout=10)
        try:
            response = http.get(PTAX_URL, params=params)
            response.raise_for_status()
            last = response.json()["value"][-1]
        finally:
            if client is None:
                http.close()
        when = datetime.fromisoformat(last["dataHoraCotacao"][:19]).strftime("%d/%m/%Y")
        return float(last["cotacaoVenda"]), when


class Ledger:
    """Registro local de cada chamada, para o painel de gastos e o orçamento."""

    def __init__(self, db_path: Path) -> None:
        self._db = sqlite3.connect(db_path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS gastos ("
            " ts REAL, tipo TEXT, modelo TEXT, entrada INTEGER, saida INTEGER,"
            " cache_leitura INTEGER, cache_escrita INTEGER, usd REAL, brl REAL)"
        )

    def close(self) -> None:
        self._db.close()

    def record(self, kind: str, model: str, usage: Usage, rate: float) -> float:
        usd = cost_usd(model, usage)
        brl = usd * rate
        self._db.execute(
            "INSERT INTO gastos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                time.time(),
                kind,
                model,
                usage.input_tokens,
                usage.output_tokens,
                usage.cache_read_tokens,
                usage.cache_write_tokens,
                usd,
                brl,
            ),
        )
        self._db.commit()
        return brl

    def month_total_brl(self, today: date | None = None) -> float:
        today = today or date.today()
        start = datetime(today.year, today.month, 1).timestamp()
        row = self._db.execute("SELECT COALESCE(SUM(brl), 0) FROM gastos WHERE ts >= ?", (start,))
        return float(row.fetchone()[0])

    def month_count(self, today: date | None = None) -> int:
        today = today or date.today()
        start = datetime(today.year, today.month, 1).timestamp()
        row = self._db.execute("SELECT COUNT(*) FROM gastos WHERE ts >= ?", (start,))
        return int(row.fetchone()[0])


@dataclass(frozen=True)
class BudgetCheck:
    allowed: bool
    message: str


def check_budget(spent_brl: float, estimate_brl: float, budget_brl: float) -> BudgetCheck:
    if budget_brl <= 0:
        return BudgetCheck(True, "")
    if spent_brl + estimate_brl > budget_brl:
        return BudgetCheck(
            False,
            f"Orçamento do mês atingido: {format_brl(spent_brl)} de {format_brl(budget_brl)}. "
            "Para liberar, aumente 'orcamento_mensal_brl' no config.json.",
        )
    if spent_brl + estimate_brl >= 0.8 * budget_brl:
        return BudgetCheck(
            True,
            f"Atenção: você já usou {format_brl(spent_brl)} de {format_brl(budget_brl)} este mês.",
        )
    return BudgetCheck(True, "")
