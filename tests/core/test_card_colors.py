#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 07:32:56.308983
Revised: 2026/10/13 07:39:27.829927
"""

import pytest

from core.card_colors import CARD_COLORS, UNKNOWN_COLOR, leader_hues, rgb
from db.models import COLORS
from share import render


def test_every_card_color_has_a_hue():
    assert set(CARD_COLORS) == set(COLORS)


@pytest.mark.parametrize(("hex_color", "expected"), [("#d63031", (214, 48, 49)), ("5a6270", (90, 98, 112))])
def test_rgb(hex_color, expected):
    assert rgb(hex_color) == expected


def test_leader_hues_keep_order_and_fall_back_for_unknown_or_missing_colors():
    assert leader_hues(("Purple", "Black")) == [CARD_COLORS["Purple"], CARD_COLORS["Black"]]
    assert leader_hues(("Pink",)) == [UNKNOWN_COLOR]
    assert leader_hues(()) == [UNKNOWN_COLOR]


def test_share_cards_draw_the_apps_hues():
    """One source for both: the share cards used to keep their own copy of these values."""
    expected = {name: rgb(hue) for name, hue in CARD_COLORS.items()}
    assert expected == render.CARD_COLORS
