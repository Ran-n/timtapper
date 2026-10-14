#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.377682
Revised: 2026/10/14 03:57:14.519956

The real app, rendered: what the pixels on screen show, and what real clicks do.

Each test drives the app started by the session `app` fixture (conftest.py) on
the demo data from scripts/demo_driver.py, once per target (desktop, web, Android),
then finds controls in the capture by their exact theme colours (pixels.py).
Taps are real input: mouse clicks on desktop, touches in the browser and on the phone.
"""

import pytest

from core.card_colors import CARD_COLORS
from locate import scroll_until
from pixels import Blob, count, find, holes
from ui.theme import THEMES

NARROW = 360  # PHONE_WINDOW min_width in main.py: everything must still fit
COLOR_ORDER = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")


def above_fab(img) -> int:
    """The y above which nothing is covered by the "New event" button (it floats over the list's bottom)."""
    return img.height - 170


def pills(img, color: str) -> list[Blob]:
    """Rounded pill fills of `color`: tall enough to be a pill (hairline outlines share some tints)."""
    return [b for b in find(img, color, tol=6, min_area=150) if 18 <= b.h <= 30]


def die_faces(img, color: str) -> list[Blob]:
    return [b for b in find(img, color, tol=6, min_area=150) if 16 <= b.w <= 26 and 16 <= b.h <= 26]


# ---- events list --------------------------------------------------------------
@pytest.mark.parametrize(("mode", "width"), [("dark", 0), ("light", 0), ("dark", NARROW)])
def test_record_and_rate_are_two_pills_side_by_side(app, scheme, mode, width):
    img = app.show("/events", mode, width)
    s = scheme(mode)
    records = pills(img, s.tint(s.fg_muted, 0.22))
    rates = pills(img, s.tint(s.success, 0.22)) + pills(img, s.tint(s.error, 0.22))
    pairs = []
    for rate in rates:
        left = [r for r in records if abs(r.y0 - rate.y0) <= 1 and r.x1 <= rate.x0]
        assert left, f"rate pill at {rate.box} has no record pill beside it"
        record = max(left, key=lambda r: r.x1)
        pairs.append((record, rate))
        assert 2 <= rate.x0 - record.x1 <= 8, (record.box, rate.box)  # a small gap: two pills, not one
        assert rate.x1 <= img.width - 30, rate.box  # clear of the chevron, nothing pushed off the card
    assert len(pairs) >= 4  # every tile above the "New event" button


@pytest.mark.parametrize(("mode", "width"), [("dark", 0), ("light", 0), ("dark", NARROW)])
def test_type_and_record_share_a_full_width_top_line(app, mode, width):
    """The type pill starts over the portrait and the record ends at the card's edge, on one line even at 360 dp;
    each type is drawn in its tier's accent (Regional: primary, Locals: secondary, Treasure Cup: tertiary…)."""
    from ui.widgets import tier_color

    img = app.show("/events", mode, width)
    s = THEMES["gruvbox"].scheme(dark=mode == "dark")
    shown = [e["id"] for e in app.send("events")]
    kinds = [app.send("event", event_id=i)["event_type"] for i in shown]
    tints = {k: s.tint(tier_color(k, s), 0.22) for k in kinds}
    # the left half only: a casual type's tint is the record pill's too, and records sit at the right
    types = sorted(
        (t for c in set(tints.values()) for t in pills(img, c) if t.x0 < img.width / 2 and t.y1 < above_fab(img)),
        key=lambda t: t.y0,
    )
    rates = pills(img, s.tint(s.success, 0.22)) + pills(img, s.tint(s.error, 0.22))
    assert len(types) >= 4  # every tile above the "New event" button
    assert len({t.x0 for t in types}) == 1  # one left edge, not stretched
    assert all(t.w < img.width / 2 for t in types)
    portraits = [b for b in find(img, CARD_COLORS["Purple"], tol=6, min_area=100) if b.w >= 50]
    assert portraits and all(abs(t.x0 - portraits[0].x0) <= 2 for t in types)  # over the portrait
    for t, kind in zip(types, kinds, strict=False):  # tiles are in the list's order
        beside = [r for r in rates if abs(r.cy - t.cy) <= 2]
        assert beside, f"no record on the type pill's line at {t.box}"  # never wrapped under it
        assert all(r.x1 >= img.width - 40 for r in beside)  # pushed to the card's right edge
        assert count(img, tier_color(kind, s), t.box) > 20, kind  # the pill's text and icon in its tier's accent


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_portraits_are_framed_in_the_leader_colours(app, mode):
    img = app.show("/events", mode)
    # every demo event is played with Luffy (OP09-061), a Purple/Black leader: purple top band, black bottom
    tops = [b for b in find(img, CARD_COLORS["Purple"], tol=6, min_area=100) if b.w >= 50 and b.y1 < above_fab(img)]
    bottoms = [b for b in find(img, CARD_COLORS["Black"], tol=6, min_area=100) if b.w >= 50]
    bottoms = bottoms[: len(tops)]  # the ones under the visible tops, in the same top-down order
    assert len(tops) == len(bottoms) >= 4  # every tile above the "New event" button
    for top, bottom in zip(tops, bottoms, strict=True):
        # the frame keeps the 56 dp portrait size (±1: shrinking a scaled capture to dp rounds edges)
        assert abs(top.x0 - bottom.x0) <= 1 and abs(top.w - 56) <= 1 and abs(bottom.w - 56) <= 1
        assert abs(bottom.y0 - top.y1) <= 2  # the bands meet: a hard split at the middle
        assert abs(top.h - bottom.h) <= 2


# ---- event screen: die badges ----------------------------------------------------
def test_die_faces_show_six_for_won_and_one_for_lost(app, scheme):
    app.show(f"/event/{app.newest}")
    s = scheme()

    def four_rounds(shot):  # round 4 can start below the fold
        won, lost = die_faces(shot, s.success), die_faces(shot, s.error)
        return (won, lost) if len(won) + len(lost) == 4 else None

    img, (won, lost) = scroll_until(app, four_rounds)
    assert len(won) == 2 and len(lost) == 2  # demo: rounds 1 and 4 won the roll, 2 and 3 lost it
    assert all(len(holes(img, f, s.on_accent)) == 6 for f in won)
    assert all(len(holes(img, f, s.on_accent)) == 1 for f in lost)
    for face in won + lost:  # each face sits on its tinted badge
        tint = s.tint(s.success if face in won else s.error, 0.22)
        assert count(img, tint, (face.x0 - 8, face.y0 - 6, face.x1 + 8, face.y1 + 6), tol=6) > 100


def test_tapping_the_die_cycles_it_on_screen_and_in_the_database(app, scheme):
    s = scheme()
    img = app.show(f"/event/{app.newest}")
    first = min(die_faces(img, s.success), key=lambda f: f.y0)  # round 1: won the roll
    x, y = first.cx, first.cy
    near = (first.x0 - 4, first.y0 - 4, first.x1 + 4, first.y1 + 4)

    def face_at(shot) -> str | None:
        for color, name in ((s.success, "won"), (s.error, "lost")):
            for f in die_faces(shot, color):
                if f.x0 >= near[0] and f.x1 <= near[2] and f.y0 >= near[1] and f.y1 <= near[3]:
                    return name
        return None

    seen = []
    for _ in range(3):
        shot = app.click(x, y)
        seen.append((face_at(shot), app.send("round", round_no=1)["won_die_roll"]))
    assert seen == [("lost", False), (None, None), ("won", True)]  # back where it started


# ---- leader picker ----------------------------------------------------------------
def dots(img) -> dict[str, Blob]:
    found = {}
    for name in COLOR_ORDER:
        # filled and round: a leader's portrait frame in the list below is as square, but hollow
        round_ones = [
            b
            for b in find(img, CARD_COLORS[name], tol=6, min_area=150)
            if abs(b.w - b.h) <= 2 and b.area >= 0.6 * b.w * b.h
        ]
        assert len(round_ones) == 1, (name, [b.box for b in round_ones])
        found[name] = round_ones[0]
    return found


@pytest.fixture
def picker(app):
    app.send("show", route=f"/event/{app.newest}", mode="dark", width=NARROW)
    app.send("picker")
    yield app
    app.send("close")


def test_colour_dots_fit_one_row_at_the_narrowest_width(picker):
    img = picker.capture()
    found = dots(img)
    rows = {round(b.cy) for b in found.values()}
    assert max(rows) - min(rows) <= 1  # one line, no wrap
    xs = [found[name].cx for name in COLOR_ORDER]
    assert xs == sorted(xs)  # in COLORS order
    assert found["Yellow"].x1 <= img.width - 16  # inside the sheet's padding
    assert all(24 <= b.w <= 30 for b in found.values())  # 28 dp dots


def test_tapping_dots_selects_and_filters(picker, scheme):
    s = scheme()
    before = picker.capture()
    start = dots(before)
    everyone = picker.send("picker_shown")

    def inside(name):  # the dot without its edge, where only the check can change colour
        b = start[name]
        return (b.x0 + 5, b.y0 + 5, b.x1 - 5, b.y1 - 5)

    def around(name):  # the dot plus a margin, where the selection ring is drawn
        b = start[name]
        return (b.x0 - 3, b.y0 - 3, b.x1 + 3, b.y1 + 3)

    def selected(shot, name, check):
        return count(shot, check, inside(name), tol=60) > 6 and count(shot, s.fg, around(name), tol=24) > 40

    assert count(before, "#ffffff", inside("Red"), tol=60) == 0 and not selected(before, "Red", "#ffffff")

    shot = picker.click(start["Red"].cx, start["Red"].cy)
    assert selected(shot, "Red", "#ffffff")  # ring + white check
    listed = picker.send("picker_shown")
    assert listed and all("Red" in ld["colors"] for ld in listed)

    shot = picker.click(start["Yellow"].cx, start["Yellow"].cy)
    assert selected(shot, "Yellow", "#000000")  # black on yellow: white would be unreadable
    assert selected(shot, "Red", "#ffffff")  # still on
    listed = picker.send("picker_shown")
    assert listed and all({"Red", "Yellow"} <= set(ld["colors"]) for ld in listed)

    picker.click(start["Red"].cx, start["Red"].cy)
    shot = picker.click(start["Yellow"].cx, start["Yellow"].cy)
    assert not selected(shot, "Red", "#ffffff") and not selected(shot, "Yellow", "#000000")
    assert picker.send("picker_shown") == everyone  # unfiltered again


# ---- settings: theme swatches -----------------------------------------------------
DOT_STEP = 18  # 14 dp dot + 4 dp spacing


def swatch_dots(img, theme_key: str, mode: str) -> list[Blob]:
    """The five preview dots a theme's swatch draws in its own colours, left to right."""
    s = THEMES[theme_key].scheme(dark=mode == "dark")
    colors = (s.primary, s.secondary, s.tertiary, s.success, s.error)
    round_dots = {
        c: [b for b in find(img, c, tol=4, min_area=80) if 12 <= b.w <= 16 and abs(b.w - b.h) <= 2] for c in colors
    }
    chains = []
    for first in round_dots[colors[0]]:
        chain = [first]
        for c in colors[1:]:
            nxt = [b for b in round_dots[c] if abs(b.cy - first.cy) <= 1 and abs(b.cx - chain[-1].cx - DOT_STEP) <= 2]
            if not nxt:
                break
            chain.append(nxt[0])
        if len(chain) == len(colors):
            chains.append(chain)
    assert len(chains) == 1, (theme_key, mode, [[b.box for b in ch] for ch in chains])
    return chains[0]


@pytest.mark.parametrize(("mode", "width"), [("dark", 0), ("light", 0), ("dark", NARROW), ("light", NARROW)])
def test_every_theme_swatch_previews_its_own_colours_in_a_two_column_grid(app, mode, width):
    img = app.show("/settings", mode, width)
    firsts = {key: swatch_dots(img, key, mode)[0] for key in THEMES}
    # the selected swatch's thicker border nudges its content in by a pixel or two
    columns, rows = lines([b.x0 for b in firsts.values()]), lines([b.y0 for b in firsts.values()])
    assert len(columns) == 2 and len(rows) == len(THEMES) // 2  # two per row, nothing wraps or overflows
    keys = list(THEMES)
    for i, key in enumerate(keys):  # laid out in THEMES order, row by row
        assert abs(firsts[key].x0 - columns[i % 2]) <= 3 and abs(firsts[key].y0 - rows[i // 2]) <= 3, key
    assert all(swatch_dots(img, k, mode)[-1].x1 <= img.width - 16 for k in keys)  # inside the page padding


def lines(values: list[float], tol: int = 3) -> list[float]:
    """Positions within `tol` of each other merged into one grid line (the smallest), in order."""
    out: list[float] = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def test_tapping_a_swatch_switches_the_whole_app_to_that_theme(app):
    target = next(k for k in THEMES if k != "gruvbox")
    img = app.show("/settings", "dark")
    new, old = THEMES[target].scheme(dark=True), THEMES["gruvbox"].scheme(dark=True)
    assert new.bg != old.bg
    dot = swatch_dots(img, target, "dark")[2]
    try:
        shot = app.click(dot.cx, dot.cy)
        assert app.send("state") == {"theme": target, "mode": "dark"}
        whole = (0, 0, shot.width, shot.height)
        assert count(shot, new.bg, whole, tol=2) > count(shot, old.bg, whole, tol=2)  # the page itself repainted
    finally:
        app.send("show", route="/settings", mode="dark", theme="gruvbox")


# ---- events list: filters ------------------------------------------------------------
def test_tapping_the_filter_button_opens_the_dropdowns_in_place(app, scheme):
    s = scheme()
    img = app.show("/events", "dark", NARROW)
    icon = [b for b in find(img, s.fg_muted, tol=24, min_area=8) if b.x0 > img.width - 70 and b.y1 < 140]
    assert icon, "no filter button at the right end of the search row"
    first_pill = min(pills(img, s.tint(s.primary, 0.22)), key=lambda b: b.y0)
    try:
        app.click(min(b.x0 for b in icon) + 10, sum(b.cy for b in icon) / len(icon))
        assert app.send("event_filters")["open"] is True

        def list_moved():  # the dropdowns open above the list, inline; on a busy machine that can lag the tap
            first = min(pills(app.capture(), s.tint(s.primary, 0.22)), key=lambda b: b.y0)
            return first if first.y0 - first_pill.y0 >= 90 else None

        moved = app.wait_until(list_moved, what="the list moving down under the dropdowns")
        assert moved.x0 == first_pill.x0
    finally:
        app.send("show", route="/events")
