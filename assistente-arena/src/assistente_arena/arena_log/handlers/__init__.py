"""Handlers: cada um transforma um tipo de mensagem do log em eventos.

Quando o Arena mudar o formato, a correção fica restrita ao handler afetado.
Falhas de leitura são contadas por handler (ver `ParseStats`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

from assistente_arena.arena_log.events import Event
from assistente_arena.arena_log.framing import Entry
from assistente_arena.arena_log.handlers import match_room

Handler = Callable[[Entry, dict[str, Any]], Iterator[Event]]

HANDLERS: dict[str, Handler] = {
    "matchGameRoomStateChangedEvent": match_room.handle,
}


class ParseStats:
    def __init__(self) -> None:
        self.failures: Counter[str] = Counter()


def dispatch(entry: Entry, stats: ParseStats | None = None) -> Iterator[Event]:
    for obj in entry.objects:
        for key, handler in HANDLERS.items():
            if key not in obj:
                continue
            try:
                yield from handler(entry, obj)
            except (KeyError, TypeError, ValueError):
                if stats is not None:
                    stats.failures[key] += 1
