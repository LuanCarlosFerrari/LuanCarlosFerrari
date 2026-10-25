from __future__ import annotations

import subprocess
from typing import Any

import pytest
from PIL import Image

from assistente_arena.shortcut import ICON, LAUNCHER, manage_shortcut, shortcut_env


def test_launcher_and_icon_are_shipped() -> None:
    assert LAUNCHER.exists()
    assert b"\r\n" in LAUNCHER.read_bytes()  # .cmd precisa de CRLF
    with Image.open(ICON) as ico:
        assert (256, 256) in ico.info["sizes"] and (16, 16) in ico.info["sizes"]


def test_env_paths() -> None:
    env = shortcut_env(start_menu=True, remove=False)
    assert env["AA_FOLDERS"] == "Desktop;Programs"
    assert env["AA_LAUNCHER"].endswith("iniciar.cmd")
    assert env["AA_ICON"].endswith("icone.ico")
    assert shortcut_env(start_menu=False, remove=True)["AA_FOLDERS"] == "Desktop"


def test_runs_powershell_with_env() -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["cmd"], seen["env"] = cmd, kwargs["env"]
        return subprocess.CompletedProcess(cmd, 0, "criado: C:\\Users\\x\\Desktop\\A.lnk\n", "")

    assert manage_shortcut(run=fake_run) == ["criado: C:\\Users\\x\\Desktop\\A.lnk"]
    assert seen["cmd"][0] == "powershell"
    assert seen["env"]["AA_REMOVE"] == "0"


def test_powershell_failure_is_reported() -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "acesso negado")

    with pytest.raises(RuntimeError, match="acesso negado"):
        manage_shortcut(run=fake_run)
