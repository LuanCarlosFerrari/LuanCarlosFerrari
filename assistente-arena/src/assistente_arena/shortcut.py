"""Cria o atalho "Assistente Arena" na área de trabalho e no Menu Iniciar (Windows).

O atalho chama `iniciar.cmd` pelo cmd.exe (assim dá para fixar na barra de tarefas)
e usa o ícone de assets/icone.ico. O PowerShell só é usado para gravar o .lnk;
os caminhos vão por variáveis de ambiente para não haver problema com aspas.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_DIR / "iniciar.cmd"
ICON = Path(__file__).resolve().parent / "assets" / "icone.ico"
NAME = "Assistente Arena"
DESCRIPTION = "Assistente Arena: Ctrl+Shift+A analisa o construtor de decks"

_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
foreach ($folder in $env:AA_FOLDERS.Split(';')) {
    $dir = [Environment]::GetFolderPath($folder)
    $path = Join-Path $dir ($env:AA_NAME + '.lnk')
    if ($env:AA_REMOVE -eq '1') {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
        Write-Output "removido: $path"
        continue
    }
    $lnk = $ws.CreateShortcut($path)
    $lnk.TargetPath = $env:ComSpec
    $lnk.Arguments = '/c "' + $env:AA_LAUNCHER + '"'
    $lnk.WorkingDirectory = $env:AA_DIR
    $lnk.IconLocation = $env:AA_ICON + ',0'
    $lnk.Description = $env:AA_DESCRIPTION
    $lnk.Save()
    Write-Output "criado: $path"
}
"""


def shortcut_env(*, start_menu: bool, remove: bool) -> dict[str, str]:
    folders = ["Desktop"] + (["Programs"] if start_menu else [])
    return {
        "AA_FOLDERS": ";".join(folders),
        "AA_NAME": NAME,
        "AA_LAUNCHER": str(LAUNCHER),
        "AA_DIR": str(PROJECT_DIR),
        "AA_ICON": str(ICON),
        "AA_DESCRIPTION": DESCRIPTION,
        "AA_REMOVE": "1" if remove else "0",
    }


def manage_shortcut(
    *,
    start_menu: bool = True,
    remove: bool = False,
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> list[str]:
    """Cria (ou remove) os atalhos. Devolve as linhas "criado/removido: caminho"."""
    if sys.platform != "win32" and run is subprocess.run:
        raise RuntimeError("O atalho só pode ser criado no Windows.")
    if not remove and not (LAUNCHER.exists() and ICON.exists()):
        raise RuntimeError(f"Arquivos do projeto não encontrados em {PROJECT_DIR}.")
    result = run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL],
        env={**os.environ, **shortcut_env(start_menu=start_menu, remove=remove)},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"O PowerShell não conseguiu gravar o atalho: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]
