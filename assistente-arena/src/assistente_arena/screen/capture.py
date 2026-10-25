"""Captura só a área da janela do Arena e prepara a imagem para o Claude.

A janela é encontrada pela classe/título (`UnityWndClass` / "MTGA"), sem abrir
o processo do jogo. A captura copia pixels da tela, como um gravador faz.
"""

from __future__ import annotations

import contextlib
import io
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

MAX_LONG_SIDE = 1568


class CaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class PreparedImage:
    png: bytes
    width: int
    height: int

    @property
    def estimated_tokens(self) -> int:
        return (self.width * self.height + 749) // 750


def prepare(image: Image.Image) -> PreparedImage:
    """Reduz para no máximo 1568 px no lado maior e codifica em PNG."""
    img = image.convert("RGB")
    long_side = max(img.size)
    if long_side > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / long_side
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
            Image.Resampling.LANCZOS,
        )
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return PreparedImage(buf.getvalue(), img.width, img.height)


def load_file(path: Path) -> PreparedImage:
    with Image.open(path) as img:
        return prepare(img)


def find_arena_window() -> tuple[int, Rect, bool]:
    """Devolve (hwnd, área cliente em pixels físicos, está em primeiro plano?)."""
    if sys.platform != "win32":
        raise CaptureError("A captura ao vivo só funciona no Windows. Use --imagem para testar.")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    # Coordenadas em pixels reais mesmo com escala de tela (125%, 150%...).
    with contextlib.suppress(AttributeError, OSError):
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    hwnd = user32.FindWindowW("UnityWndClass", "MTGA") or user32.FindWindowW(None, "MTGA")
    if not hwnd:
        raise CaptureError("Janela do MTG Arena não encontrada. O jogo está aberto?")
    if user32.IsIconic(hwnd):
        raise CaptureError("O Arena está minimizado.")

    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise CaptureError("Não consegui ler o tamanho da janela do Arena.")
    foreground = user32.GetForegroundWindow() == hwnd
    return int(hwnd), Rect(origin.x, origin.y, width, height), foreground


def capture_arena() -> tuple[PreparedImage, str]:
    """Captura a janela do Arena. Devolve a imagem e um aviso (ou "")."""
    import mss

    _, rect, foreground = find_arena_window()
    with mss.mss() as sct:
        shot = sct.grab(
            {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
        )
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    warning = ""
    if not foreground:
        warning = "O Arena não está em primeiro plano; outra janela pode ter saído na imagem."
    return prepare(img), warning
