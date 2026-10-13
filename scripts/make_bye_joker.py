#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 00:01:20.053128
Revised: 2026/10/13 00:01:20.053128

Render the bye's portrait: scripts/bye_jester.svg (a jester adapted from Microsoft's Fluent Emoji, MIT) to
src/timtapper/assets/bye_joker.png (512x512, transparent). A bye stands in for an opponent you never played, so it
gets a jester where a leader's face would be; the app frames it like a portrait and the share cards paste the same
image. Re-run after changing the SVG:

    uv run python scripts/make_bye_joker.py
"""

import sys
from pathlib import Path

import resvg_py

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))

from core.logging import get_logger, setup_logging  # noqa: E402

SOURCE = ROOT / "scripts" / "bye_jester.svg"
OUT = APP_DIR / "assets" / "bye_joker.png"
SIZE = 512


def render(source: Path = SOURCE, size: int = SIZE) -> bytes:
    """The SVG as PNG bytes, `size` pixels square."""
    return bytes(resvg_py.svg_to_bytes(svg_path=str(source), width=size, height=size))


def main() -> None:
    setup_logging()
    OUT.write_bytes(render())
    get_logger("scripts.make_bye_joker").info("wrote %s", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
