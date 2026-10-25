"""Transforma linhas do Player.log em eventos e mantém o estado mínimo do jogo."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from assistente_arena.arena_log.events import (
    DetailedLogsStatus,
    Event,
    LogReset,
    MatchEnded,
    MatchStarted,
)
from assistente_arena.arena_log.framing import Entry, EntrySplitter
from assistente_arena.arena_log.handlers import ParseStats, dispatch


@dataclass
class ArenaState:
    in_match: bool = False
    match_id: str = ""
    event_id: str = ""
    detailed_logs: bool | None = None  # None = ainda não sabemos
    saw_game_json: bool = False
    matches_seen: int = 0

    def apply(self, event: Event) -> None:
        if isinstance(event, LogReset):
            self.in_match = False
            self.match_id = ""
            self.event_id = ""
            self.detailed_logs = None
            self.saw_game_json = False
        elif isinstance(event, DetailedLogsStatus):
            self.detailed_logs = event.enabled
        elif isinstance(event, MatchStarted):
            self.in_match = True
            self.match_id = event.match_id
            self.event_id = event.event_id
            self.matches_seen += 1
        elif isinstance(event, MatchEnded):
            self.in_match = False


@dataclass
class LogReader:
    state: ArenaState = field(default_factory=ArenaState)
    stats: ParseStats = field(default_factory=ParseStats)
    _splitter: EntrySplitter = field(default_factory=EntrySplitter)

    def feed_lines(self, lines: Iterable[str]) -> list[Event]:
        events: list[Event] = []
        for line in lines:
            events.extend(self._line_events(line))
            for entry in self._splitter.feed([line]):
                events.extend(self._entry_events(entry))
        self._apply(events)
        return events

    def flush(self) -> list[Event]:
        """Fecha a entrada pendente (fim do arquivo ou arquivo parado)."""
        events: list[Event] = []
        for entry in self._splitter.flush():
            events.extend(self._entry_events(entry))
        self._apply(events)
        return events

    def reset(self) -> list[Event]:
        self._splitter = EntrySplitter()
        events: list[Event] = [LogReset()]
        self._apply(events)
        return events

    def _line_events(self, line: str) -> list[Event]:
        if "DETAILED LOGS: ENABLED" in line:
            return [DetailedLogsStatus(enabled=True)]
        if "DETAILED LOGS: DISABLED" in line:
            return [DetailedLogsStatus(enabled=False)]
        return []

    def _entry_events(self, entry: Entry) -> list[Event]:
        if entry.objects:
            self.state.saw_game_json = True
        return list(dispatch(entry, self.stats))

    def _apply(self, events: list[Event]) -> None:
        for event in events:
            self.state.apply(event)
