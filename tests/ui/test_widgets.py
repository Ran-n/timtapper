#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:22:24.719836
Revised: 2026/10/13 07:39:26.491811

The app's logo widget and the assets scripts/make_icon.py draws for it.
"""

import flet as ft
import pytest
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from catalog.repository import Leader
from core.card_colors import CARD_COLORS, UNKNOWN_COLOR
from core.paths import ASSETS_DIR
from db.models import EVENT_TYPES
from i18n import translator
from stats.compute import Record
from ui.theme import THEMES
from ui.widgets import (
    DIE_PIPS,
    EVENT_TYPE_ICONS,
    EVENT_TYPE_TIERS,
    LOGO_MARK,
    chooser_badge,
    color_bar,
    die_badge,
    die_face,
    empty_state,
    event_type_pill,
    leader_portrait,
    leader_row,
    logo,
    pill,
    portrait_border,
    record_badges,
    result_badge,
    score_badge,
    tier_color,
    turn_badge,
)
from uitools import by_data, texts, walk


def test_logo_is_a_square_contained_image():
    img = logo(40)
    assert (img.src, img.width, img.height, img.fit) == (LOGO_MARK, 40, 40, ft.BoxFit.CONTAIN)


def test_launcher_icon_is_the_bare_mark_inside_the_adaptive_safe_circle():
    """The launcher icon carries no name, and nothing drawn reaches past the 66/108 circle Android
    promises to show — the mark's arrow used to poke out where launchers clip."""
    import math

    with Image.open(ASSETS_DIR / "icon.png") as icon:
        img = icon.convert("RGB")
    size = img.width
    bg = img.getpixel((2, 2))
    radius = size * 66 / 108 / 2
    small = img.resize((size // 8, size // 8), Image.Resampling.NEAREST)
    drawn = [
        (x, y)
        for y in range(small.height)
        for x in range(small.width)
        if sum(abs(a - b) for a, b in zip(small.getpixel((x, y)), bg, strict=True)) > 60
    ]
    assert drawn
    c = small.width / 2
    assert max(math.hypot(x + 0.5 - c, y + 0.5 - c) for x, y in drawn) * 8 <= radius
    assert max(y for _x, y in drawn) * 8 < size * 0.8  # no name line under the mark


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
    first, second = turn_badge(True, scheme, "1st", "2nd"), turn_badge(False, scheme, "1st", "2nd")
    assert icons(first) == [(ft.Icons.LOOKS_ONE, scheme.fg)] and icons(second) == [(ft.Icons.LOOKS_TWO, scheme.fg)]
    assert (first.content.semantics_label, second.content.semantics_label) == ("1st", "2nd")  # what's read aloud
    assert texts(first) == [] and first.bgcolor == scheme.surface_high
    unknown = turn_badge(None, scheme, "1st", "2nd")
    assert texts(unknown) == ["—"] and unknown.content.color == ft.Colors.ON_SURFACE_VARIANT


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


@pytest.mark.regression
def test_record_badges_never_show_draws(scheme):
    """The OPTCG has no draws: records read wins-losses only."""
    assert texts(record_badges(Record(2, 1), scheme))[0] == "2-1"


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
    p = event_type_pill(translator("en"), "locals", scheme)  # a store event: the secondary accent
    assert p.data == "event-type" and texts(p) == ["Locals"]
    assert icons(p) == [(ft.Icons.STOREFRONT_OUTLINED, scheme.secondary)]
    assert p.bgcolor == scheme.tint(scheme.secondary, 0.22)
    assert by_data(p, "event-type").content.controls[1].color == scheme.secondary


def test_event_type_pill_unknown_key(scheme):
    p = event_type_pill(translator("en"), "moon_cup", scheme)
    assert texts(p) == ["Other"] and icons(p) == [(ft.Icons.EVENT_OUTLINED, scheme.fg_muted)]  # casual, as Other


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


# ---- die faces, more cases -----------------------------------------------------
@pytest.mark.parametrize("n", range(1, 7))
def test_die_pip_layouts_are_standard(n):
    centres = DIE_PIPS[n]
    assert len(centres) == n and len(set(centres)) == n  # n distinct pips
    assert all(0 < x < 1 and 0 < y < 1 for x, y in centres)
    xs, ys = [x for x, _ in centres], [y for _, y in centres]
    assert abs(sum(xs) / n - 0.5) < 1e-9 and abs(sum(ys) / n - 0.5) < 1e-9  # every face is centred


@pytest.mark.parametrize("n", range(1, 7))
def test_die_pips_never_touch(n):
    face = die_face(n, "#000000", "#ffffff", 21.6)  # the size die_badge uses: 36 * 0.6
    dots = pips(face)
    for i, a in enumerate(dots):
        for b in dots[i + 1 :]:
            gap = ((a.left - b.left) ** 2 + (a.top - b.top) ** 2) ** 0.5
            assert gap > a.width, (n, a.left, a.top, b.left, b.top)


def test_die_face_shape():
    face = die_face(6, "#112233", "#ffffff", 20)
    assert (face.width, face.height, face.bgcolor, face.data) == (20, 20, "#112233", "die-face-6")
    assert face.border_radius == pytest.approx(20 * 0.22)
    assert all(p.width == p.height == pytest.approx(4) and p.border_radius == pytest.approx(2) for p in pips(face))


@pytest.mark.parametrize("size", [24, 36, 48])
def test_die_badge_scales_with_size(scheme, size):
    for won in (True, False, None):
        badge = die_badge(won, scheme, size)
        assert (badge.width, badge.height) == (size + 8, size)
    (face,) = faces(die_badge(True, scheme, size))
    assert face.width == pytest.approx(size * 0.6)


# ---- record badges, more cases ------------------------------------------------
def test_record_badges_even_rate_is_green(scheme):
    assert by_data(record_badges(Record(1, 1), scheme), "rate-badge").content.color == scheme.success


def test_record_badges_only_losses(scheme):
    badges = record_badges(Record(0, 2), scheme)
    assert texts(badges) == ["0-2", "0%"]
    assert by_data(badges, "rate-badge").content.color == scheme.error


def test_record_badges_pills_are_tinted(scheme):
    badges = record_badges(Record(3, 1), scheme)
    assert by_data(badges, "record-badge").bgcolor == scheme.tint(scheme.fg_muted, 0.22)
    assert by_data(badges, "rate-badge").bgcolor == scheme.tint(scheme.success, 0.22)


@pytest.mark.parametrize(("theme", "dark"), ALL_SCHEMES)
def test_record_badges_every_theme(theme, dark):
    s = THEMES[theme].scheme(dark=dark)
    assert by_data(record_badges(Record(2, 1), s), "rate-badge").content.color == s.success
    assert by_data(record_badges(Record(1, 2), s), "rate-badge").content.color == s.error


# ---- event type pill, more cases ----------------------------------------------
@pytest.mark.parametrize("lang", ["en", "es", "gl"])
@pytest.mark.parametrize("key", EVENT_TYPES)
def test_event_type_pill_every_type_and_language(scheme, lang, key):
    from i18n import event_type_label

    _ = translator(lang)
    p = event_type_pill(_, key, scheme)
    assert texts(p) == [event_type_label(_, key)] and texts(p)[0]
    assert icons(p) == [(EVENT_TYPE_ICONS[key], tier_color(key, scheme))]


@pytest.mark.parametrize(
    ("key", "accent"),
    [
        ("worlds", "primary"),
        ("treasure_cup", "tertiary"),
        ("store_championship", "secondary"),
        ("pirates_party", "fg_muted"),
    ],
)
def test_each_tier_has_its_accent(scheme, key, accent):
    assert tier_color(key, scheme) == getattr(scheme, accent)


def test_every_event_type_has_a_tier():
    assert set(EVENT_TYPE_TIERS) == set(EVENT_TYPES)


def test_event_type_icons_are_distinct():
    assert len(set(EVENT_TYPE_ICONS.values())) == len(EVENT_TYPE_ICONS)


def test_pill_with_icon_puts_icon_first(scheme):
    p = pill("Label", scheme.primary, scheme, icon=ft.Icons.FLAG_OUTLINED, data="x")
    icon, label = p.content.controls
    assert isinstance(icon, ft.Icon) and icon.icon == ft.Icons.FLAG_OUTLINED and label.value == "Label"
    assert p.data == "x"


# ---- portrait frame, more cases -----------------------------------------------
def test_portrait_frame_three_colors():
    frame = leader_portrait(leader(("Red", "Green", "Blue")), 56)
    assert frame.gradient.colors == [CARD_COLORS[c] for c in ("Red", "Red", "Green", "Green", "Blue", "Blue")]
    assert frame.gradient.stops == pytest.approx([0, 1 / 3, 1 / 3, 2 / 3, 2 / 3, 1])


@pytest.mark.parametrize("size", [12, 16, 24, 30, 32, 40, 48, 56, 64, 80])
def test_portrait_frame_keeps_outer_size(size):
    frame = leader_portrait(leader(("Red",)), size)
    border = portrait_border(size)
    assert (frame.width, frame.height, frame.padding) == (size, size, border)
    assert frame.content.width == frame.content.height == size - 2 * border
    assert frame.content.border_radius >= 0  # never a negative inner radius


def test_portrait_frame_without_a_picture_is_a_framed_silhouette():
    frame = leader_portrait(Leader(0, "OP99-999", "Nobody", None, ("Blue",)), 40)
    assert frame.data == "portrait-frame" and frame.bgcolor == CARD_COLORS["Blue"]
    assert isinstance(frame.content.content, ft.Icon)


def test_leader_row_frames_its_portrait():
    row = leader_row(leader(("Purple",)), "", size=16)
    frame = by_data(row, "portrait-frame")
    assert frame.width == 32 and frame.bgcolor == CARD_COLORS["Purple"]
    assert [c.data for c in walk(leader_row(None, "Pick", size=16))].count("portrait-frame") == 0


@pytest.mark.property
@given(st.lists(st.sampled_from(sorted(CARD_COLORS)), min_size=2, max_size=6))
def test_color_frame_bands_are_equal_and_ordered(colors):
    frame = leader_portrait(leader(tuple(colors)), 56)
    g = frame.gradient
    assert g.colors == [CARD_COLORS[c] for c in colors for _ in range(2)]
    assert g.stops[0] == 0 and g.stops[-1] == pytest.approx(1)
    assert g.stops == sorted(g.stops)  # hard edges only, never backwards
    widths = [g.stops[i + 1] - g.stops[i] for i in range(0, len(g.stops), 2)]
    assert widths == pytest.approx([1 / len(colors)] * len(colors))


# ---- dialogs and live updates --------------------------------------------------------
@pytest.mark.parametrize("is_async", [False, True])
async def test_confirm_runs_sync_and_async_actions_once(page, is_async):
    from ui.widgets import confirm
    from uitools import fire

    ran = []

    async def async_yes():
        ran.append("async")

    confirm(
        page, "Delete?", "Gone for good.", "Delete", "Cancel", async_yes if is_async else lambda: ran.append("sync")
    )
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert ran == ["async" if is_async else "sync"] and page.dialogs == []


def test_update_if_mounted_pushes_only_attached_controls():
    from types import SimpleNamespace

    from ui.widgets import update_if_mounted

    detached = ft.Text("x")
    update_if_mounted(detached)  # no page yet: must not raise

    pushed = []
    attached = SimpleNamespace(page=object(), update=lambda: pushed.append(True))
    update_if_mounted(attached)
    assert pushed == [True]


@pytest.mark.regression
@pytest.mark.parametrize("size", [14, 15, 16])
def test_leader_names_wrap_instead_of_being_cut(size):
    """Names used to end in "…" ("Sh…", "Donquixote Doflami…") wherever the row was tight."""
    long = Leader(1, "OP01-060", "Donquixote Doflamingo", "OP01", ("Blue",))
    name = next(c for c in walk(leader_row(long, "", size=size)) if isinstance(c, ft.Text) and c.value == long.name)
    assert name.max_lines is None and name.overflow != ft.TextOverflow.ELLIPSIS


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Monkey.D.Dragon", "Monkey.​D.​Dragon"),
        ('Eustass"Captain"Kid', 'Eustass"​Captain"​Kid'),
        ("Tony Tony.Chopper", "Tony Tony.​Chopper"),
        ("Roronoa Zoro & Sanji", "Roronoa Zoro & Sanji"),  # already breaks at its spaces
        ("Shanks", "Shanks"),
        ("Dr.", "Dr."),  # nothing to break before at the end
    ],
)
def test_breakable_adds_invisible_break_points_between_name_parts(name, expected):
    from ui.widgets import breakable

    assert breakable(name) == expected
    assert breakable(name).replace("​", "") == name  # only invisible additions


@pytest.mark.regression
def test_long_names_in_tight_rows_break_between_parts_not_mid_word():
    """At 360 dp a round row's name got ~78 dp, and "Donquixot/e" or "Monkey.D.Drag/on" split mid-word."""
    long = Leader(1, "OP07-001", "Monkey.D.Dragon", "OP07", ("Black",))
    row = leader_row(long, "", size=12, show_code=False, portrait_size=30, break_words=True)
    name = next(c for c in walk(row) if isinstance(c, ft.Text))
    assert name.value == "Monkey.​D.​Dragon" and name.size == 12
    assert by_data(row, "portrait-frame").width == 30
    plain = next(c for c in walk(leader_row(long, "")) if isinstance(c, ft.Text))
    assert plain.value == "Monkey.D.Dragon"  # other rows keep the name untouched


@pytest.mark.property
@given(st.text(max_size=30))
def test_property_breakable_only_adds_zero_width_spaces(name):
    from ui.widgets import breakable

    out = breakable(name)
    assert out.replace("​", "") == name.replace("​", "") or "​" in name
    assert not out.endswith("​") or name.endswith("​")


def test_leader_row_short_name_only_when_asked():
    dofla = Leader(1, "OP01-060", "Donquixote Doflamingo", "OP01", ("Blue",))

    def name_of(row):
        return next(c for c in walk(row) if isinstance(c, ft.Text)).value

    assert name_of(leader_row(dofla, "", short=True)) == "Doflamingo"
    assert name_of(leader_row(dofla, "")) == "Donquixote Doflamingo"  # the list, stats and picker have room


# ---- best of 3 badges ---------------------------------------------------------------
@pytest.mark.parametrize(("chose", "label"), [(True, "You"), (False, "Opp")])
def test_chooser_badge_says_who_chose(scheme, chose, label):
    badge = chooser_badge(chose, scheme, "You", "Opp")
    assert texts(badge) == [label]
    assert badge.bgcolor == (scheme.tint(scheme.primary, 0.22) if chose else scheme.surface_high)


def test_chooser_badge_unknown_is_a_muted_hand(scheme):
    badge = chooser_badge(None, scheme, "You", "Opp")
    (icon,) = [c for c in walk(badge) if isinstance(c, ft.Icon)]
    assert icon.icon == ft.Icons.FRONT_HAND_OUTLINED and texts(badge) == []


@pytest.mark.parametrize(("wins", "losses", "result"), [(2, 1, "W"), (0, 2, "L"), (1, 0, None)])
def test_score_badge_fills_in_the_result_colour_once_decided(scheme, wins, losses, result):
    badge = score_badge(wins, losses, result, scheme)
    assert texts(badge) == [f"{wins}-{losses}"]
    assert badge.bgcolor == (scheme.results[result] if result else ft.Colors.SURFACE_CONTAINER_HIGHEST)


def test_bye_portrait_is_the_jester_framed_like_a_leader(scheme):
    from ui.widgets import BYE_JOKER, bye_portrait

    p = bye_portrait(scheme, 30)
    assert (p.width, p.height, p.bgcolor) == (30, 30, scheme.tertiary)
    (img,) = [c for c in walk(p) if isinstance(c, ft.Image)]
    assert img.src == BYE_JOKER and (ASSETS_DIR / BYE_JOKER).is_file()


def test_the_jester_asset_is_a_square_transparent_png():
    from ui.widgets import BYE_JOKER

    with Image.open(ASSETS_DIR / BYE_JOKER) as im:
        assert im.size == (512, 512) and im.mode == "RGBA"
        assert im.getpixel((0, 0))[3] == 0  # a transparent corner: the frame's colour shows through


def test_the_jesters_licence_ships_with_it():
    assert "MIT License" in (ASSETS_DIR / "LICENSE-fluent-emoji.txt").read_text(encoding="utf-8")
