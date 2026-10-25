"""Gera o ícone do Assistente Arena (assets/icone.ico e uma prévia em PNG).

Uso: uv run python tools/gerar_icone.py
Desenhado só com formas geométricas, sem fontes, para sair igual em qualquer máquina.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CARVAO = (28, 29, 26, 255)
SUPERFICIE = (38, 39, 34, 255)
OLIVA = (154, 163, 106, 255)
OLIVA_ESCURO = (122, 132, 80, 255)
TERROSO = (169, 119, 63, 255)
TEXTO = (228, 223, 211, 255)

SIZE = 1024  # desenha grande e reduz, para bordas suaves
OUT = Path(__file__).resolve().parents[1] / "src" / "assistente_arena" / "assets"


def draw() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Fundo: quadrado arredondado carvão com borda oliva escura.
    d.rounded_rectangle((32, 32, SIZE - 32, SIZE - 32), radius=150, fill=CARVAO)
    d.rounded_rectangle((32, 32, SIZE - 32, SIZE - 32), radius=150, outline=OLIVA_ESCURO, width=18)

    # Duas cartas em leque: a de trás terrosa, a da frente oliva.
    back = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle(
        (332, 222, 732, 782), radius=48, fill=SUPERFICIE, outline=TERROSO, width=28
    )
    img.alpha_composite(back.rotate(-11, resample=Image.Resampling.BICUBIC, center=(532, 502)))
    front = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    fd = ImageDraw.Draw(front)
    fd.rounded_rectangle((292, 242, 692, 802), radius=48, fill=SUPERFICIE, outline=OLIVA, width=32)

    # "A" geométrico dentro da carta da frente.
    cx, top, bottom = 492, 350, 700
    half, stroke = 150, 64
    fd.polygon(
        [
            (cx - 36, top),
            (cx + 36, top),
            (cx + half, bottom),
            (cx + half - stroke - 6, bottom),
            (cx, top + 122),
            (cx - half + stroke + 6, bottom),
            (cx - half, bottom),
        ],
        fill=TEXTO,
    )
    fd.rectangle((cx - 80, 570, cx + 80, 620), fill=TEXTO)
    img.alpha_composite(front.rotate(6, resample=Image.Resampling.BICUBIC, center=(492, 522)))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img = draw()
    sizes = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    img.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / "icone.ico", sizes=sizes)
    img.resize((512, 512), Image.Resampling.LANCZOS).save(OUT / "icone.png")
    print(f"Ícone salvo em {OUT}")


if __name__ == "__main__":
    main()
