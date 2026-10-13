#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.870382
Revised: 2026/10/12 21:24:32.826618

Draw the app logo:

- src/timtapper/assets/icon.png (1024x1024): the bare mark on its frame, no
  name, shrunk into Android's adaptive-icon safe circle; flet build picks it
  up for the launcher icon and splash.
- src/timtapper/assets/icon.ico: the bare mark at full size, for the Windows
  window/taskbar (no launcher mask there).
- src/timtapper/assets/logo_mark.png (512x512): the bare mark on transparency,
  for in-app use (events app bar, empty events screen, Settings -> About).
- docs/logo.png (480 tall): icon + "timtapper" wordmark with the "app" highlighted, for the README.

The mark is a blue card caught mid-tap (rotating clockwise to rest, the OPTCG
action the name comes from) with an orange motion arc, carrying a rising bar chart
for the stats. Re-run after changing the design:

    uv run python scripts/make_icon.py
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from core.logging import get_logger, setup_logging  # noqa: E402

ASSETS = APP_DIR / "assets"
ICON_PATH = ASSETS / "icon.png"
ICO_PATH = ASSETS / "icon.ico"
MARK_PATH = ASSETS / "logo_mark.png"
LOGO_PATH = ROOT / "docs" / "logo.png"
FONT_HEAVY = ASSETS / "fonts" / "Poppins-ExtraBold.ttf"

SIZE = 1024
SS = 4  # supersampling factor; drawn at SIZE*SS then downscaled for clean edges

# Gruvbox dark (the default theme) for the frame, OPTCG blue for the card and gruvbox orange (the app's primary)
# for the accent. Blue + orange reads on light and dark READMEs and isn't a national flag (red + gold was Spain's).
BG = (29, 32, 33)  # gruvbox bg0_h
SHADOW = (0, 0, 0, 120)  # translucent so the transparent mark sits on light themes too
CARD = (41, 128, 205)  # theme.CARD_COLORS["Blue"]
CARD_EDGE = (28, 96, 160)
ACCENT = (254, 128, 25)  # gruvbox bright orange
ACCENT_DEEP = (214, 93, 14)  # gruvbox neutral orange: wordmark, legible on light and dark

CREAM = (251, 241, 199)  # gruvbox fg0 (light bg)

# "timtapper" split so the "app" inside it can be picked out: (text, highlighted)
NAME_PARTS = (("timt", False), ("app", True), ("er", False))
APP_NAME = "".join(text for text, _ in NAME_PARTS)
# (plain, highlight) colors of the README banner's name: blue/deep orange read on any background
BANNER_NAME_COLORS = (CARD, ACCENT_DEEP)
# Android shows an adaptive icon's 108 dp layer through a mask that only promises the central 66 dp circle
SAFE_RADIUS = SIZE * 66 / 108 / 2

CARD_W, CARD_H, CARD_R = 380, 530, 52
CARD_CENTER = (500, 540)
TILT = -20  # degrees; negative = clockwise in PIL, i.e. tapping
ARC_CENTER = (500, 600)
ARC_RADIUS = 430
ARC_START, ARC_END = 228, 296  # PIL angles: clockwise from 3 o'clock


def _s(v: float) -> int:
    return round(v * SS)


def _card_layer() -> Image.Image:
    """The card, upright, on its own transparent layer — rotated afterwards."""
    layer = Image.new("RGBA", (_s(SIZE), _s(SIZE)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = CARD_CENTER
    x0, y0, x1, y1 = cx - CARD_W / 2, cy - CARD_H / 2, cx + CARD_W / 2, cy + CARD_H / 2
    d.rounded_rectangle([_s(v) for v in (x0 + 18, y0 + 26, x1 + 18, y1 + 26)], radius=_s(CARD_R), fill=SHADOW)
    d.rounded_rectangle([_s(v) for v in (x0, y0, x1, y1)], radius=_s(CARD_R), fill=CARD_EDGE)
    d.rounded_rectangle([_s(v) for v in (x0, y0, x1, y1 - 14)], radius=_s(CARD_R), fill=CARD)
    # inner frame line, like a card border
    inset = 30
    d.rounded_rectangle(
        [_s(v) for v in (x0 + inset, y0 + inset, x1 - inset, y1 - inset - 14)],
        radius=_s(CARD_R - inset / 2),
        outline=(*CREAM, 70),
        width=_s(6),
    )
    # rising bars: the stats
    bar_w, gap, base = 64, 30, y1 - 100
    heights = (120, 205, 300)
    left = cx - (3 * bar_w + 2 * gap) / 2
    for i, h in enumerate(heights):
        bx = left + i * (bar_w + gap)
        fill = ACCENT if i == len(heights) - 1 else CREAM
        d.rounded_rectangle([_s(v) for v in (bx, base - h, bx + bar_w, base)], radius=_s(18), fill=fill)
    return layer.rotate(TILT, resample=Image.Resampling.BICUBIC, center=(_s(cx), _s(cy)))


def _motion_arc(d: ImageDraw.ImageDraw) -> None:
    """Gold arc over the card's top edge, ending in an arrowhead: the tap."""
    cx, cy = ARC_CENTER
    r, width = ARC_RADIUS, 40
    mid = r - width / 2  # PIL draws the arc stroke inward from the bounding circle
    box = [_s(v) for v in (cx - r, cy - r, cx + r, cy + r)]
    d.arc(box, start=ARC_START, end=ARC_END, fill=ACCENT, width=_s(width))

    def on_mid(deg: float) -> tuple[float, float]:
        a = math.radians(deg)
        return cx + mid * math.cos(a), cy + mid * math.sin(a)

    tx, ty = on_mid(ARC_START)  # round cap at the tail
    d.ellipse([_s(v) for v in (tx - width / 2, ty - width / 2, tx + width / 2, ty + width / 2)], fill=ACCENT)
    # arrowhead: base across the stroke at the arc's end, tip along the clockwise tangent
    a = math.radians(ARC_END)
    bx, by = on_mid(ARC_END)
    tangent = (-math.sin(a), math.cos(a))
    normal = (math.cos(a), math.sin(a))
    length, spread = 78, 54
    tip = (bx + tangent[0] * length, by + tangent[1] * length)
    outer = (bx + normal[0] * spread, by + normal[1] * spread)
    inner = (bx - normal[0] * spread, by - normal[1] * spread)
    d.polygon([(_s(x), _s(y)) for x, y in (tip, outer, inner)], fill=ACCENT)


def _draw_name(d: ImageDraw.ImageDraw, x: float, y: float, font: ImageFont.FreeTypeFont, colors: tuple) -> None:
    """Write "timtapper" left-middle anchored at (x, y), the "app" in the highlight color."""
    plain, highlight = colors
    for text, highlighted in NAME_PARTS:
        d.text((x, y), text, font=font, fill=highlight if highlighted else plain, anchor="lm")
        x += d.textlength(text, font=font)


def _mark() -> Image.Image:
    """Card + motion arc on a transparent, supersampled canvas."""
    mark = Image.new("RGBA", (_s(SIZE), _s(SIZE)), (0, 0, 0, 0))
    mark.alpha_composite(_card_layer())
    _motion_arc(ImageDraw.Draw(mark))
    return mark


def _safe_zone_scale(mark: Image.Image) -> float:
    """How far to shrink `mark`, centred on its bounds, so its farthest drawn pixel is inside SAFE_RADIUS."""
    x0, y0, x1, y1 = mark.getbbox()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    alpha = mark.getchannel("A").point(lambda a: 255 if a > 32 else 0).resize((SIZE // 4, SIZE // 4))
    step = mark.width / alpha.width
    far = max(
        math.hypot((x + 0.5) * step - cx, (y + 0.5) * step - cy)
        for y in range(alpha.height)
        for x in range(alpha.width)
        if alpha.getpixel((x, y))
    )
    return min(1.0, _s(SAFE_RADIUS) / far)


def draw_icon(adaptive: bool = True) -> Image.Image:
    """The square icon: the bare mark on the dark frame, no name. `adaptive`: shrunk into the launcher's
    safe circle, centred; otherwise as drawn, full size."""
    img = Image.new("RGBA", (_s(SIZE), _s(SIZE)), (*BG, 255))
    mark = _mark()
    if not adaptive:
        img.alpha_composite(mark)
        return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    scale = _safe_zone_scale(mark)
    x0, y0, x1, y1 = mark.getbbox()
    small = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.Resampling.LANCZOS)
    ox = _s(SIZE) / 2 - (x0 + x1) / 2 * scale
    oy = _s(SIZE) / 2 - (y0 + y1) / 2 * scale
    img.alpha_composite(small, (round(ox), round(oy)))
    return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def draw_mark(size: int = 512, margin: int = 8) -> Image.Image:
    """The bare mark trimmed to its bounds and centred on a transparent square."""
    mark = _mark()
    mark = mark.crop(mark.getbbox())
    side = max(mark.size) + 2 * _s(margin)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
    return square.resize((size, size), Image.Resampling.LANCZOS)


def draw_logo(icon: Image.Image) -> Image.Image:
    """Wordmark banner: rounded icon tile on the left, "tim·t·app·er" on the right, the "app" highlighted."""
    h, pad, gutter = 480, 40, 60
    tile = h - 2 * pad
    font = ImageFont.truetype(str(FONT_HEAVY), 210)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = pad + tile + gutter + round(probe.textlength(APP_NAME, font=font)) + pad
    logo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (tile * SS, tile * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tile * SS, tile * SS), radius=int(tile * 0.22 * SS), fill=255)
    mask = mask.resize((tile, tile), Image.Resampling.LANCZOS)
    logo.paste(icon.resize((tile, tile), Image.Resampling.LANCZOS), (pad, pad), mask)
    _draw_name(ImageDraw.Draw(logo), pad + tile + gutter, h / 2 + 10, font, BANNER_NAME_COLORS)
    return logo


def main() -> None:
    setup_logging()
    log = get_logger("scripts.make_icon")
    draw_icon().save(ICON_PATH)
    log.info("wrote %s", ICON_PATH)
    full = draw_icon(adaptive=False)
    full.save(ICO_PATH, sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    log.info("wrote %s", ICO_PATH)
    draw_mark().save(MARK_PATH)
    log.info("wrote %s", MARK_PATH)
    LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
    draw_logo(full).save(LOGO_PATH)
    log.info("wrote %s", LOGO_PATH)


if __name__ == "__main__":
    main()
