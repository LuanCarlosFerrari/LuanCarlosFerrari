"""`matchGameRoomStateChangedEvent`: início e fim de partida."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from assistente_arena.arena_log.events import Event, MatchEnded, MatchStarted
from assistente_arena.arena_log.framing import Entry

PLAYING = "MatchGameRoomStateType_Playing"
COMPLETED = "MatchGameRoomStateType_MatchCompleted"


def handle(entry: Entry, obj: dict[str, Any]) -> Iterator[Event]:
    room_info = obj["matchGameRoomStateChangedEvent"]["gameRoomInfo"]
    state = room_info.get("stateType")
    config = room_info.get("gameRoomConfig") or {}
    match_id = str(
        config.get("matchId") or room_info.get("finalMatchResult", {}).get("matchId", "")
    )
    if state == PLAYING:
        yield MatchStarted(match_id=match_id, event_id=str(config.get("eventId", "")))
    elif state == COMPLETED:
        yield MatchEnded(match_id=match_id)
