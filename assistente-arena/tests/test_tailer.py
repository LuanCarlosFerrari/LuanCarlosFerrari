from __future__ import annotations

import os
from pathlib import Path

from assistente_arena.arena_log.events import LogReset, MatchStarted
from assistente_arena.arena_log.monitor import LogMonitor
from assistente_arena.arena_log.tailer import Tailer

PLAYING = (
    '{"matchGameRoomStateChangedEvent":{"gameRoomInfo":{"gameRoomConfig":{"matchId":"M1"},'
    '"stateType":"MatchGameRoomStateType_Playing"}}}'
)


def test_reads_only_appended_lines_and_keeps_partial(tmp_path: Path) -> None:
    log = tmp_path / "Player.log"
    log.write_bytes(b"a\nb\nmeia-li")
    tailer = Tailer(log)
    assert tailer.poll() == (False, ["a", "b"])
    with open(log, "ab") as f:
        f.write(b"nha\r\nc\n")
    assert tailer.poll() == (False, ["meia-linha", "c"])
    assert tailer.poll() == (False, [])
    tailer.close()


def test_detects_recreated_file(tmp_path: Path) -> None:
    log = tmp_path / "Player.log"
    log.write_text("linha antiga 1\nlinha antiga 2\n", encoding="utf-8")
    tailer = Tailer(log)
    tailer.poll()
    # O Arena renomeia o log antigo e cria um novo ao abrir.
    os.replace(log, tmp_path / "Player-prev.log")
    log.write_text("nova\n", encoding="utf-8")
    assert tailer.poll() == (True, ["nova"])
    tailer.close()


def test_detects_truncated_file(tmp_path: Path) -> None:
    log = tmp_path / "Player.log"
    log.write_text("x" * 100 + "\n", encoding="utf-8")
    tailer = Tailer(log)
    tailer.poll()
    with open(log, "w", encoding="utf-8") as f:
        f.write("y\n")
    reset, lines = tailer.poll()
    assert reset is True and lines == ["y"]
    tailer.close()


def test_missing_file_is_not_an_error(tmp_path: Path) -> None:
    tailer = Tailer(tmp_path / "Player.log")
    assert tailer.poll() == (False, [])


def test_monitor_emits_reset_and_new_match(tmp_path: Path) -> None:
    log = tmp_path / "Player.log"
    log.write_text(f"[UnityCrossThreadLogger]x\n{PLAYING}\n", encoding="utf-8")
    monitor = LogMonitor(log)
    monitor.poll()
    monitor.poll()  # arquivo parado: fecha a entrada pendente
    assert monitor.state.in_match is True
    os.replace(log, tmp_path / "Player-prev.log")
    log.write_text("[UnityCrossThreadLogger]y\n", encoding="utf-8")
    events = monitor.poll()
    assert LogReset() in events
    assert monitor.state.in_match is False
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"[UnityCrossThreadLogger]z\n{PLAYING}\n")
    events = monitor.poll() + monitor.poll()
    assert any(isinstance(e, MatchStarted) for e in events)
    monitor.close()
