#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.870382
Revised: 2026/10/11 16:27:24.355979

Draw the app icon (src/timtapper/assets/icon.png, 1024x1024) — flet build
picks it up for the launcher icon and splash. Re-run after changing the design:

    uv run python scripts/make_icon.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

APP_DIR = Path(__file__).resolve().parent.parent / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from core.logging import get_logger, setup_logging  # noqa: E402

ASSETS = APP_DIR / "assets"
SIZE = 1024
NAVY = (13, 22, 38)
RED = (214, 48, 49)
GOLD = (245, 190, 60)
WHITE = (236, 240, 245)


def main() -> None:
    setup_logging()
    img = Image.new("RGBA", (SIZE, SIZE), NAVY)
    d = ImageDraw.Draw(img)
    # a leader card, slightly tilted feel via offset shadow card behind it
    d.rounded_rectangle((300, 210, 760, 840), radius=56, fill=GOLD)
    d.rounded_rectangle((250, 170, 710, 800), radius=56, fill=RED)
    font = ImageFont.truetype(str(ASSETS / "fonts" / "Poppins-ExtraBold.ttf"), 330)
    d.text((480, 490), "tt", font=font, fill=WHITE, anchor="mm")
    img.save(ASSETS / "icon.png")
    get_logger("scripts.make_icon").info("wrote %s", ASSETS / "icon.png")


if __name__ == "__main__":
    main()
