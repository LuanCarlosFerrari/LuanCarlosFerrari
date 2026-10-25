"""Regras invioláveis: nada de automação de entrada nem leitura de memória do jogo."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PACKAGES = {
    "pyautogui",
    "pynput",
    "pydirectinput",
    "keyboard",
    "mouse",
    "pymem",
    "pywinauto",
    "ahk",
    "frida",
    "pyinjector",
    "readwritememory",
}
FORBIDDEN_CALLS = [
    "SendInput",
    "keybd_event",
    "mouse_event",
    "PostMessage",
    "SendMessage",
    "ReadProcessMemory",
    "WriteProcessMemory",
    "OpenProcess",
    "VirtualAllocEx",
    "CreateRemoteThread",
    "SetWindowsHookEx",
]


def test_no_forbidden_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {re.split(r"[<>=\[ ;]", dep, maxsplit=1)[0].lower() for dep in project["dependencies"]}
    assert not names & FORBIDDEN_PACKAGES


def test_no_forbidden_calls_in_source() -> None:
    pattern = re.compile(r"\b(" + "|".join(FORBIDDEN_CALLS) + r")[AW]?\b")
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert offenders == []
