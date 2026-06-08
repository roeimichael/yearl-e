"""Generate the social share card (og.png, 1200x630) and favicon.png for yearl-e.

Antique-atlas aesthetic: parchment ground, ink lines, a faint engraved globe,
terracotta accent. Pure-PIL, no network. Re-run any time the branding changes.

    python scripts/make_og_image.py
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFont

OUT_OG = "frontend/og.png"
OUT_ICON = "frontend/favicon.png"

# palette
PARCH = (240, 231, 207)      # parchment
PARCH_D = (228, 216, 186)    # darker parchment (vignette)
INK = (58, 47, 37)           # dark sepia ink
INK_SOFT = (120, 104, 84)    # faded ink
TERRA = (176, 83, 47)        # terracotta accent
OLIVE = (107, 107, 58)       # olive

SERIF = "C:/Windows/Fonts/georgia.ttf"
SERIF_B = "C:/Windows/Fonts/georgiab.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def draw_globe(d: ImageDraw.ImageDraw, cx, cy, r, col, width=2):
    """A faint engraved globe: outline + meridians + parallels."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=width)
    # parallels (horizontal ellipses, foreshortened)
    for frac in (-0.66, -0.33, 0.0, 0.33, 0.66):
        yy = cy + frac * r
        rx = r * math.sqrt(max(0.0, 1 - frac * frac))
        ry = max(2, r * 0.10 * (1 - abs(frac) * 0.4))
        d.ellipse([cx - rx, yy - ry, cx + rx, yy + ry], outline=col, width=1)
    # meridians (vertical ellipses of varying width)
    for frac in (-0.66, -0.33, 0.0, 0.33, 0.66):
        rx = r * abs(frac) if frac != 0 else max(2, r * 0.02)
        d.ellipse([cx - rx, cy - r, cx + rx, cy + r], outline=col, width=1)


def make_og():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), PARCH)
    d = ImageDraw.Draw(img)

    # subtle vignette border (engraved frame)
    for i, col in ((0, PARCH_D),):
        pass
    d.rectangle([28, 28, W - 28, H - 28], outline=INK_SOFT, width=2)
    d.rectangle([38, 38, W - 38, H - 38], outline=PARCH_D, width=1)

    # faint globe on the right
    draw_globe(d, cx=940, cy=H // 2, r=210, col=INK_SOFT, width=2)
    # a terracotta "you are here" pin dot on the globe
    px, py = 902, 250
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=TERRA)
    d.ellipse([px - 17, py - 17, px + 17, py + 17], outline=TERRA, width=2)

    # title
    f_title = font(SERIF_B, 132)
    d.text((90, 150), "yearl-e", font=f_title, fill=INK)
    # accent rule under title
    d.line([96, 300, 96 + 360, 300], fill=TERRA, width=4)

    # subtitle
    f_sub = font(SERIF, 40)
    d.text((96, 330), "where on Earth would you", font=f_sub, fill=INK)
    d.text((96, 380), "want to live that year?", font=f_sub, fill=INK)

    # bottom tagline
    f_tag = font(SERIF, 28)
    d.text((96, 500), "a daily history game · 1500–2026 · real data, cited",
           font=f_tag, fill=OLIVE)

    img.save(OUT_OG, "PNG")
    print("wrote", OUT_OG, img.size)


def make_icon():
    # render large then downscale for crisp edges
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # parchment disc
    d.ellipse([8, 8, S - 8, S - 8], fill=PARCH, outline=INK, width=8)
    draw_globe(d, cx=S // 2, cy=S // 2, r=(S // 2) - 28, col=INK_SOFT, width=4)
    # terracotta pin
    d.ellipse([S // 2 - 22, 70 - 22, S // 2 + 22, 70 + 22], fill=TERRA)
    for px in (64, 128):
        pass
    img = img.resize((64, 64), Image.LANCZOS)
    img.save(OUT_ICON, "PNG")
    print("wrote", OUT_ICON, img.size)


if __name__ == "__main__":
    make_og()
    make_icon()
