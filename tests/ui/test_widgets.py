#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:22:24.719836
Revised: 2026/10/12 01:37:36.007371

The app's logo widget and the assets scripts/make_icon.py draws for it.
"""

import flet as ft
import pytest
from PIL import Image

from catalog.repository import Leader
from core.paths import ASSETS_DIR
from db.models import EVENT_TYPES
from i18n import translator
from stats.compute import Record
from ui.theme import CARD_COLORS, THEMES, UNKNOWN_COLOR
from ui.widgets import (
    EVENT_TYPE_ICONS,
    LOGO_MARK,
    color_bar,
    die_badge,
    die_face,
    empty_state,
    event_type_pill,
    leader_portrait,
    logo,
    pill,
    portrait_border,
    record_badges,
    result_badge,
    turn_badge,
)
from uitools import by_data, texts, walk


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
    return [(c.icon, c.color) for c in walk(control) if isinstance(c, ft.Icon)]


def test_turn_badge_states(scheme):
    assert texts(turn_badge(True, scheme, "1st", "2nd")) == ["1st"]
    assert texts(turn_badge(False, scheme, "1st", "2nd")) == ["2nd"]
    unknown = turn_badge(None, scheme, "1st", "2nd")
    assert texts(unknown) == ["—"] and unknown.content.color == ft.Colors.ON_SURFACE_VARIANT
    assert turn_badge(True, scheme, "1st", "2nd").content.color == scheme.fg


ALL_SCHEMES = [(key, dark) for key in THEMES for dark in (False, True)]


def faces(control) -> list:
    return [c for c in walk(control) if str(getattr(c, "data", "")).startswith("die-face-")]


def pips(control) -> list:
    return [c for c in walk(control) if getattr(c, "data", None) == "pip"]


@pytest.mark.parametrize(("theme", "dark"), ALL_SCHEMES)
def test_die_badge_states(theme, dark):
    scheme = THEMES[theme].scheme(dark=dark)
    won = die_badge(True, scheme)
    (face,) = faces(won)
    assert face.data == "die-face-6" and face.bgcolor == scheme.success
    assert won.bgcolor == scheme.tint(scheme.success, 0.22)
    assert len(pips(won)) == 6 and {p.bgcolor for p in pips(won)} == {scheme.on_accent}
    lost = die_badge(False, scheme)
    (face,) = faces(lost)
    assert face.data == "die-face-1" and face.bgcolor == scheme.error
    assert lost.bgcolor == scheme.tint(scheme.error, 0.22)
    assert len(pips(lost)) == 1 and pips(lost)[0].bgcolor == scheme.on_accent
    assert not icons(won) and not icons(lost)  # no check or cross any more
    unknown = die_badge(None, scheme)
    assert icons(unknown) == [(ft.Icons.CASINO, ft.Colors.ON_SURFACE_VARIANT)] and not faces(unknown)


@pytest.mark.parametrize("n", range(1, 7))
def test_die_face_pip_counts(n):
    face = die_face(n, "#000000", "#ffffff", 20)
    dots = pips(face)
    assert len(dots) == n
    for dot in dots:
        assert dot.left >= 0 and dot.left + dot.width <= 20
        assert dot.top >= 0 and dot.top + dot.height <= 20


@pytest.mark.parametrize("n", [0, 7])
def test_die_face_rejects_bad_pip_counts(n):
    with pytest.raises(ValueError, match="1-6 pips"):
        die_face(n, "#000000", "#ffffff", 20)


def test_badges_line_up_with_result_badge(scheme):
    badges = (
        result_badge("W", scheme),
        turn_badge(None, scheme, "a", "b"),
        die_badge(None, scheme),
        die_badge(True, scheme),
        die_badge(False, scheme),
    )
    assert {b.height for b in badges} == {36}


# ---- record badges ------------------------------------------------------------
def test_record_badges_split(scheme):
    badges = record_badges(Record(2, 1), scheme)
    assert texts(badges) == ["2-1", "67%"]
    assert texts(by_data(badges, "record-badge")) == ["2-1"]
    assert by_data(badges, "record-badge").content.color == scheme.fg_muted
    assert by_data(badges, "rate-badge").content.color == scheme.success
    assert badges.wrap is False


def test_record_badges_losing_rate_is_red(scheme):
    assert by_data(record_badges(Record(1, 2), scheme), "rate-badge").content.color == scheme.error


def test_record_badges_draws(scheme):
    assert texts(record_badges(Record(2, 1, 1), scheme))[0] == "2-1-1"


def test_record_badges_no_games(scheme):
    badges = record_badges(Record(), scheme)
    assert texts(badges) == ["—"]
    assert not [c for c in walk(badges) if getattr(c, "data", None) == "rate-badge"]


def test_record_badges_size(scheme):
    assert {t.size for t in walk(record_badges(Record(3, 1), scheme, size=15)) if isinstance(t, ft.Text)} == {15}


# ---- event type pill ----------------------------------------------------------
def test_every_event_type_has_an_icon():
    assert set(EVENT_TYPE_ICONS) == set(EVENT_TYPES)


def test_event_type_pill(scheme):
    p = event_type_pill(translator("en"), "locals", scheme)
    assert p.data == "event-type" and texts(p) == ["Locals"]
    assert icons(p) == [(ft.Icons.STOREFRONT_OUTLINED, scheme.primary)]
    assert p.bgcolor == scheme.tint(scheme.primary, 0.22)
    assert by_data(p, "event-type").content.controls[1].color == scheme.primary


def test_event_type_pill_unknown_key(scheme):
    p = event_type_pill(translator("en"), "worlds", scheme)
    assert texts(p) == ["Other"] and icons(p) == [(ft.Icons.EVENT_OUTLINED, scheme.primary)]


def test_event_type_pill_translated(scheme):
    assert texts(event_type_pill(translator("gl"), "locals", scheme)) == ["Locais"]


def test_pill_without_icon_unchanged(scheme):
    p = pill("hi", scheme.error, scheme)
    assert isinstance(p.content, ft.Text) and p.content.value == "hi" and p.content.color == scheme.error
    assert p.bgcolor == scheme.tint(scheme.error, 0.22) and not icons(p)


# ---- portrait frame -----------------------------------------------------------
def leader(colors: tuple[str, ...]) -> Leader:
    return Leader(1, "OP01-001", "Someone", None, colors)


def test_portrait_frame_single_color():
    frame = leader_portrait(leader(("Red",)), 56)
    assert frame.data == "portrait-frame" and frame.bgcolor == CARD_COLORS["Red"] and frame.gradient is None
    assert (frame.width, frame.height, frame.padding) == (56, 56, 3)
    assert frame.content.width == 50 and frame.content.border_radius == 56 // 4 - 3


def test_portrait_frame_multicolor():
    frame = leader_portrait(leader(("Red", "Green")), 56)
    red, green = CARD_COLORS["Red"], CARD_COLORS["Green"]
    assert frame.gradient.colors == [red, red, green, green]
    assert frame.gradient.stops == [0, 0.5, 0.5, 1]
    assert frame.gradient.begin == ft.Alignment.TOP_CENTER and frame.gradient.end == ft.Alignment.BOTTOM_CENTER


def test_portrait_frame_unknown_colors():
    assert leader_portrait(leader(()), 40).bgcolor == UNKNOWN_COLOR
    assert leader_portrait(leader(("Pink",)), 40).bgcolor == UNKNOWN_COLOR


def test_portrait_without_leader_has_no_frame():
    placeholder = leader_portrait(None, 56)
    assert placeholder.data != "portrait-frame" and placeholder.width == 56
    assert isinstance(placeholder.content, ft.Icon)


@pytest.mark.parametrize(("size", "border"), [(16, 2), (32, 2), (56, 3)])
def test_portrait_border_width_scales(size, border):
    assert portrait_border(size) == border


def test_color_bar_unchanged():
    bar = color_bar(("Red", "Green", "Pink"))
    assert [s.bgcolor for s in bar.content.controls] == [CARD_COLORS["Red"], CARD_COLORS["Green"], UNKNOWN_COLOR]
    assert [s.bgcolor for s in color_bar(()).content.controls] == [UNKNOWN_COLOR]
