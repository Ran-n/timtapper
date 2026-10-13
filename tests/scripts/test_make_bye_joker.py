#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 00:01:20.133084
Revised: 2026/10/13 00:01:20.133084
"""

import importlib.util
import io
from pathlib import Path

from PIL import Image

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "make_bye_joker.py"
_spec = importlib.util.spec_from_file_location("make_bye_joker", _PATH)
joker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(joker)


def test_render_draws_the_svg_at_the_asked_size():
    with Image.open(io.BytesIO(joker.render(size=64))) as im:
        assert im.size == (64, 64) and im.mode == "RGBA"


def test_main_writes_the_asset(tmp_path, monkeypatch):
    out = tmp_path / "bye.png"
    monkeypatch.setattr(joker, "OUT", out)
    monkeypatch.setattr(joker, "ROOT", tmp_path)
    joker.main()
    with Image.open(out) as im:
        assert im.size == (joker.SIZE, joker.SIZE)


def test_the_svg_credits_fluent_emoji():
    assert "Fluent Emoji" in joker.SOURCE.read_text(encoding="utf-8")
