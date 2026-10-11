#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:22:24.719836
Revised: 2026/10/11 17:22:24.719836

The app's logo widget and the assets scripts/make_icon.py draws for it.
"""

import flet as ft
import pytest
from PIL import Image

from core.paths import ASSETS_DIR
from ui.widgets import LOGO_MARK, empty_state, logo
from uitools import by_data, texts


def test_logo_is_a_square_contained_image():
    img = logo(40)
    assert (img.src, img.width, img.height, img.fit) == (LOGO_MARK, 40, 40, ft.BoxFit.CONTAIN)


def test_empty_state_shows_a_control_as_is():
    state = empty_state(logo(120), "Title", "Body")
    assert by_data(state, "logo").width == 120
    assert {"Title", "Body"} <= set(texts(state))


def test_empty_state_puts_an_icon_on_a_disc():
    state = empty_state(ft.Icons.STYLE_OUTLINED, "Title", "Body")
    disc = state.content.controls[0]
    assert disc.bgcolor == ft.Colors.PRIMARY_CONTAINER
    assert disc.content.icon == ft.Icons.STYLE_OUTLINED


def test_logo_mark_is_square_and_transparent():
    with Image.open(ASSETS_DIR / LOGO_MARK) as img:
        assert img.mode == "RGBA" and img.width == img.height
        assert img.getpixel((0, 0))[3] == 0


@pytest.mark.parametrize(("name", "fmt"), [("icon.png", "PNG"), ("icon.ico", "ICO")])
def test_app_icons_are_bundled(name, fmt):
    with Image.open(ASSETS_DIR / name) as img:
        assert img.format == fmt
