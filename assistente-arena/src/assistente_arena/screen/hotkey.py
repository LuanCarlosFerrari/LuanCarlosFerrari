"""Atalho global via RegisterHotKey: só recebe o atalho, não intercepta nem envia teclas."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

_MODIFIERS = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT}


def parse_hotkey(text: str) -> tuple[int, int]:
    """'ctrl+shift+a' → (modificadores, código virtual da tecla)."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        raise ValueError("atalho vazio")
    *mods, key = parts
    flags = MOD_NOREPEAT
    for mod in mods:
        if mod not in _MODIFIERS:
            raise ValueError(f"modificador desconhecido: {mod}")
        flags |= _MODIFIERS[mod]
    if len(key) == 1 and key.isalnum():
        return flags, ord(key.upper())
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        return flags, 0x70 + int(key[1:]) - 1
    raise ValueError(f"tecla não suportada: {key}")


def run_hotkey_loop(
    hotkey: str, on_press: Callable[[], None], on_idle: Callable[[], None], idle_s: float = 0.25
) -> None:
    """Fica escutando o atalho até Ctrl+C. `on_idle` roda a cada `idle_s` segundos."""
    if sys.platform != "win32":
        raise RuntimeError("O atalho global só funciona no Windows.")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    mods, vk = parse_hotkey(hotkey)
    if not user32.RegisterHotKey(None, 1, mods, vk):
        raise RuntimeError(f"Não consegui registrar {hotkey}: outro programa já usa esse atalho?")
    msg = wintypes.MSG()
    last_idle = 0.0
    try:
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    on_press()
            now = time.monotonic()
            if now - last_idle >= idle_s:
                on_idle()
                last_idle = now
            time.sleep(0.05)
    finally:
        user32.UnregisterHotKey(None, 1)
