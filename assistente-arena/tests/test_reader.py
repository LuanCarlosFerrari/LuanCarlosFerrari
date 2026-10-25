from __future__ import annotations

from pathlib import Path

from conftest import FIXTURES

from assistente_arena.arena_log.events import MatchEnded, MatchStarted
from assistente_arena.arena_log.monitor import read_state
from assistente_arena.arena_log.reader import LogReader


def _lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def test_full_match_is_detected() -> None:
    reader = LogReader()
    events = reader.feed_lines(_lines("sintetico_partida.log")) + reader.flush()
    assert MatchStarted(match_id="9F3A", event_id="Historic_Ladder") in events
    assert MatchEnded(match_id="9F3A") in events
    assert reader.state.in_match is False
    assert reader.state.detailed_logs is True
    assert reader.state.matches_seen == 1


def test_match_in_progress_when_log_stops_mid_match() -> None:
    lines = _lines("sintetico_partida.log")
    cut = next(i for i, line in enumerate(lines) if "MatchCompleted" in line) - 1
    reader = LogReader()
    reader.feed_lines(lines[:cut])
    reader.flush()
    assert reader.state.in_match is True


def test_detailed_logs_disabled_is_detected_before_first_header() -> None:
    reader = LogReader()
    reader.feed_lines(_lines("sintetico_registro_desligado.log"))
    assert reader.state.detailed_logs is False


def test_reset_clears_match() -> None:
    lines = _lines("sintetico_partida.log")
    cut = next(i for i, line in enumerate(lines) if "MatchCompleted" in line) - 1
    reader = LogReader()
    reader.feed_lines(lines[:cut])
    reader.flush()
    reader.reset()
    assert reader.state.in_match is False


def test_broken_handler_payload_is_counted_not_raised() -> None:
    reader = LogReader()
    reader.feed_lines(
        ["[UnityCrossThreadLogger]x", '{"matchGameRoomStateChangedEvent": {"semGameRoomInfo": 1}}']
    )
    reader.flush()
    assert reader.stats.failures["matchGameRoomStateChangedEvent"] == 1


def test_read_state_missing_file(tmp_path: Path) -> None:
    assert read_state(tmp_path / "nao_existe.log") is None


def test_read_state_handles_last_line_without_newline(tmp_path: Path) -> None:
    log = tmp_path / "Player.log"
    log.write_text(
        "[UnityCrossThreadLogger]x\n"
        '{"matchGameRoomStateChangedEvent":{"gameRoomInfo":{"gameRoomConfig":{"matchId":"M"},'
        '"stateType":"MatchGameRoomStateType_Playing"}}}',
        encoding="utf-8",
    )
    state = read_state(log)
    assert state is not None and state.in_match is True
