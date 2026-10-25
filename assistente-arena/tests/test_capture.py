from __future__ import annotations

from pathlib import Path

from PIL import Image

from assistente_arena.screen.capture import MAX_LONG_SIDE, load_file, prepare


def test_large_image_is_downscaled_keeping_aspect() -> None:
    prepared = prepare(Image.new("RGB", (2560, 1440), "black"))
    assert (prepared.width, prepared.height) == (MAX_LONG_SIDE, 882)
    assert prepared.png.startswith(b"\x89PNG")
    assert prepared.estimated_tokens == (1568 * 882 + 749) // 750


def test_small_image_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "tela.png"
    Image.new("RGBA", (800, 600)).save(path)
    prepared = load_file(path)
    assert (prepared.width, prepared.height) == (800, 600)
