"""Eventos tipados que o leitor do log entrega ao resto do programa."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogReset:
    """O Player.log foi recriado (o Arena abriu de novo)."""


@dataclass(frozen=True)
class DetailedLogsStatus:
    enabled: bool


@dataclass(frozen=True)
class MatchStarted:
    match_id: str
    event_id: str


@dataclass(frozen=True)
class MatchEnded:
    match_id: str


Event = LogReset | DetailedLogsStatus | MatchStarted | MatchEnded
