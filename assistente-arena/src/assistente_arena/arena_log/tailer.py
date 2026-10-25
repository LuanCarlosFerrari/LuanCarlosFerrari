"""Acompanha o Player.log em tempo real sem atrapalhar o Arena.

No Windows o arquivo é aberto com FILE_SHARE_READ | WRITE | DELETE. Sem o
DELETE, o Arena não conseguiria renomear o log para Player-prev.log ao abrir.
A recriação do arquivo é detectada pela troca do ID do arquivo ou por o
tamanho ficar menor que a posição já lida.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import IO


def default_log_path() -> Path:
    override = os.environ.get("ASSISTENTE_ARENA_LOG")
    if override:
        return Path(override)
    profile = os.environ.get("USERPROFILE", str(Path.home()))
    return Path(profile) / "AppData" / "LocalLow" / "Wizards Of The Coast" / "MTGA" / "Player.log"


def open_shared(path: Path) -> IO[bytes]:
    if sys.platform != "win32":
        return open(path, "rb")  # noqa: SIM115 — o Tailer controla o ciclo de vida
    import ctypes
    import msvcrt
    from ctypes import wintypes

    generic_read = 0x80000000
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    file_attribute_normal = 0x80
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path), generic_read, share_all, None, open_existing, file_attribute_normal, None
    )
    if handle == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), f"não foi possível abrir {path}")
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    return os.fdopen(fd, "rb")


class Tailer:
    """Lê só o que foi acrescentado. `poll()` devolve (recriado?, linhas novas)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: IO[bytes] | None = None
        self._file_id: tuple[int, int] | None = None
        self._pos = 0
        self._partial = b""

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None

    def poll(self) -> tuple[bool, list[str]]:
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            self.close()
            return False, []
        file_id = (st.st_dev, st.st_ino)
        reset = False
        if self._file is None or file_id != self._file_id or st.st_size < self._pos:
            reset = self._file is not None
            self.close()
            try:
                self._file = open_shared(self.path)
            except OSError:
                return False, []
            self._file_id = file_id
            self._pos = 0
            self._partial = b""
        assert self._file is not None
        self._file.seek(self._pos)
        data = self._file.read()
        self._pos += len(data)
        return reset, self._split(data)

    def _split(self, data: bytes) -> list[str]:
        if not data:
            return []
        data = self._partial + data
        *complete, self._partial = data.split(b"\n")
        return [line.rstrip(b"\r").decode("utf-8", errors="replace") for line in complete]

    def pending_lines(self) -> Iterator[str]:
        """Última linha sem quebra (fim de arquivo numa leitura única)."""
        if self._partial:
            yield self._partial.rstrip(b"\r").decode("utf-8", errors="replace")
            self._partial = b""
