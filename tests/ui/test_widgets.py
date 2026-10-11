#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:22:24.719836
Revised: 2026/10/11 23:25:32.858754

The app's logo widget and the assets scripts/make_icon.py draws for it.
"""

import flet as ft
import pytest
from PIL import Image

from core.paths import ASSETS_DIR
from ui.widgets import LOGO_MARK, die_badge, empty_state, logo, result_badge, turn_badge
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


# ---- round row indicators ----------------------------------------------------------
@pytest.fixture
def scheme():
    from ui.theme import DEFAULT_THEME, THEMES

    return THEMES[DEFAULT_THEME].scheme(dark=True)


def icons(control) -> list:
    from uitools import walk

    return [(c.icon, c.color) for c in walk(control) if isinstance(c, ft.Icon)]


def test_turn_badge_states(scheme):
    assert texts(turn_badge(True, scheme, "1st", "2nd")) == ["1st"]
    assert texts(turn_badge(False, scheme, "1st", "2nd")) == ["2nd"]
    unknown = turn_badge(None, scheme, "1st", "2nd")
    assert texts(unknown) == ["—"] and unknown.content.color == ft.Colors.ON_SURFACE_VARIANT
    assert turn_badge(True, scheme, "1st", "2nd").content.color == scheme.fg


def test_die_badge_states(scheme):
    assert icons(die_badge(True, scheme)) == [(ft.Icons.CASINO, scheme.fg), (ft.Icons.CHECK, scheme.success)]
    assert icons(die_badge(False, scheme)) == [(ft.Icons.CASINO, scheme.fg), (ft.Icons.CLOSE, scheme.error)]
    assert icons(die_badge(None, scheme)) == [(ft.Icons.CASINO, ft.Colors.ON_SURFACE_VARIANT)]


def test_badges_line_up_with_result_badge(scheme):
    heights = {
        b.height for b in (result_badge("W", scheme), turn_badge(None, scheme, "a", "b"), die_badge(None, scheme))
    }
    assert heights == {36}
