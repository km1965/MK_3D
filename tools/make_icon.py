"""Génère l'icône de l'application : un MNT 3D sur une tuile aux couleurs de l'app."""

from __future__ import annotations

import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ICO_PATH = ASSETS_DIR / "mk_mnt_3d.ico"
PNG_PATH = ASSETS_DIR / "mk_mnt_3d.png"

SIZE = 512
TOP_COLOR = (10, 20, 34)
BOTTOM_COLOR = (31, 78, 121)
GLOW_COLOR = (53, 168, 224)
ICO_SIZES = [256, 128, 96, 64, 48, 32, 24, 16]


def _terrain(n: int = 150):
    x = np.linspace(-3.0, 3.0, n)
    y = np.linspace(-3.0, 3.0, n)
    xg, yg = np.meshgrid(x, y)
    z = (
        3.0 * np.exp(-(((xg + 1.1) ** 2 + (yg + 0.9) ** 2) / 1.6))
        + 2.6 * np.exp(-(((xg - 1.2) ** 2 + (yg - 0.7) ** 2) / 1.3))
        - 1.6 * np.exp(-(((xg - 0.2) ** 2 + (yg + 1.4) ** 2) / 1.0))
        + 0.35 * np.sin(2.2 * xg) * np.cos(2.0 * yg)
    )
    return xg, yg, z


def _render_terrain() -> Image.Image:
    xg, yg, z = _terrain()
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        xg,
        yg,
        z,
        cmap="turbo",
        rstride=2,
        cstride=2,
        linewidth=0.25,
        edgecolor=(1, 1, 1, 0.18),
        antialiased=True,
        shade=True,
    )
    ax.set_axis_off()
    ax.view_init(elev=34, azim=-60)
    ax.set_box_aspect((1.15, 1.0, 0.5))
    fig.patch.set_alpha(0.0)
    fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", transparent=True, dpi=240, pad_inches=0.0)
    plt.close(fig)
    buffer.seek(0)
    image = Image.open(buffer).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    return image


def _rounded_gradient() -> Image.Image:
    gradient = np.zeros((SIZE, SIZE, 3), dtype=np.uint8)
    for row in range(SIZE):
        t = row / (SIZE - 1)
        gradient[row, :] = [
            int(TOP_COLOR[c] + (BOTTOM_COLOR[c] - TOP_COLOR[c]) * t) for c in range(3)
        ]
    base = Image.fromarray(gradient, "RGB").convert("RGBA")

    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(SIZE * 0.22)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=radius, fill=255)
    base.putalpha(mask)

    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        (SIZE * 0.12, SIZE * 0.30, SIZE * 0.88, SIZE * 0.98),
        fill=GLOW_COLOR + (70,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(SIZE * 0.10))
    base = Image.alpha_composite(base, glow)

    base.putalpha(mask)
    return base


def _add_border(image: Image.Image) -> Image.Image:
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(SIZE * 0.22)
    draw.rounded_rectangle(
        (2, 2, SIZE - 3, SIZE - 3), radius=radius, outline=255, width=max(3, SIZE // 128)
    )
    border = Image.new("RGBA", (SIZE, SIZE), (90, 180, 235, 190))
    border.putalpha(mask)
    return Image.alpha_composite(image, border)


def build() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    tile = _rounded_gradient()

    terrain = _render_terrain()
    target = int(SIZE * 0.82)
    ratio = target / max(terrain.width, terrain.height)
    terrain = terrain.resize(
        (max(1, int(terrain.width * ratio)), max(1, int(terrain.height * ratio))),
        Image.LANCZOS,
    )

    shadow = Image.new("RGBA", terrain.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (0, 0), terrain.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))

    pos = ((SIZE - terrain.width) // 2, int((SIZE - terrain.height) // 2) + int(SIZE * 0.03))
    tile.alpha_composite(shadow, (pos[0] + 5, pos[1] + 9))
    tile.alpha_composite(terrain, pos)

    tile = _add_border(tile)

    tile.save(PNG_PATH)
    tile.save(ICO_PATH, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"[OK] Icône PNG : {PNG_PATH}")
    print(f"[OK] Icône ICO : {ICO_PATH} ({', '.join(str(s) for s in ICO_SIZES)} px)")
    return ICO_PATH


if __name__ == "__main__":
    build()
