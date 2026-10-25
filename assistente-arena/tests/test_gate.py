from __future__ import annotations

from assistente_arena.arena_log.reader import ArenaState
from assistente_arena.screen.gate import evaluate


def test_blocked_during_match_even_for_image_files() -> None:
    state = ArenaState(in_match=True, detailed_logs=True)
    assert not evaluate(state, live=True).allowed
    assert not evaluate(state, live=False).allowed


def test_live_requires_log() -> None:
    assert not evaluate(None, live=True).allowed


def test_live_blocked_when_detailed_logs_disabled() -> None:
    assert not evaluate(ArenaState(detailed_logs=False), live=True).allowed


def test_live_blocked_when_log_state_unknown() -> None:
    assert not evaluate(ArenaState(detailed_logs=None, saw_game_json=False), live=True).allowed


def test_live_allowed_outside_match() -> None:
    assert evaluate(ArenaState(detailed_logs=True), live=True).allowed
    assert evaluate(ArenaState(detailed_logs=None, saw_game_json=True), live=True).allowed


def test_image_file_without_log_is_allowed_with_warning() -> None:
    decision = evaluate(None, live=False)
    assert decision.allowed and decision.warning
