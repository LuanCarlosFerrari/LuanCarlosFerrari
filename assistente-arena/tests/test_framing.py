from __future__ import annotations

from conftest import FIXTURES

from assistente_arena.arena_log.framing import extract_json_objects, split_entries


def test_braces_inside_strings_do_not_break_json() -> None:
    text = 'prefixo {"a": "}{ não é chave", "b": {"c": 1}} sufixo {"d": 2}'
    assert list(extract_json_objects(text)) == [{"a": "}{ não é chave", "b": {"c": 1}}, {"d": 2}]


def test_escaped_request_is_parsed_twice() -> None:
    text = '{"id": "x", "request": "{\\"PlatformKey\\": \\"Windows\\"}"}'
    (obj,) = extract_json_objects(text)
    assert obj["request"] == {"PlatformKey": "Windows"}


def test_invalid_json_is_skipped() -> None:
    assert list(extract_json_objects('{"a": } {"b": 1}')) == [{"b": 1}]


def test_lines_before_first_header_are_ignored_and_multiline_json_is_joined() -> None:
    lines = (FIXTURES / "sintetico_partida.log").read_text(encoding="utf-8").splitlines()
    entries = split_entries(lines)
    assert not any("Mono path" in e.header for e in entries)
    playing = [e for e in entries if "matchGameRoomStateChangedEvent" in str(e.objects)]
    assert len(playing) == 2
    room = playing[0].objects[0]["matchGameRoomStateChangedEvent"]["gameRoomInfo"]
    assert room["gameRoomConfig"]["matchId"] == "9F3A"


def test_response_line_starts_a_new_entry() -> None:
    lines = (FIXTURES / "sintetico_partida.log").read_text(encoding="utf-8").splitlines()
    entries = split_entries(lines)
    start_hook = next(e for e in entries if e.header.startswith("<== StartHook"))
    assert start_hook.objects[0]["InventoryInfo"]["Gold"] == 4550
