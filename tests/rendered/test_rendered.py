#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.377682
Revised: 2026/10/12 13:16:03.377682

The real app, rendered: what the pixels on screen show, and what real clicks do.

Each test drives the app started by the session `app` fixture (conftest.py) on
the demo data from scripts/app_driver.py, then finds controls in the capture by
their exact theme colours (pixels.py). Taps are real mouse clicks.
"""

import pytest

from pixels import Blob, count, find, holes
from ui.theme import CARD_COLORS

pytestmark = pytest.mark.desktop

NARROW = 360  # PHONE_WINDOW min_width in main.py: everything must still fit
COLOR_ORDER = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")


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
def test_event_type_pill_heads_every_tile(app, scheme, mode, width):
    img = app.show("/events", mode, width)
    s = scheme(mode)
    types = pills(img, s.tint(s.primary, 0.22))
    rates = pills(img, s.tint(s.success, 0.22)) + pills(img, s.tint(s.error, 0.22))
    assert len(types) == 5  # one per demo event
    assert len({t.x0 for t in types}) == 1  # left-aligned in the text column, not stretched
    assert all(t.w < img.width / 2 for t in types)
    for rate in rates:
        above = [t for t in types if t.y1 < rate.y0]
        assert above and rate.y0 - max(t.y1 for t in above) >= 20  # the name line sits between
    # the pill's text and icon are drawn in the primary colour
    assert all(count(img, s.primary, t.box) > 20 for t in types)


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_portraits_are_framed_in_the_leader_colours(app, mode):
    img = app.show("/events", mode)
    # every demo event is played with Luffy (OP09-061), a Purple/Black leader: purple top band, black bottom
    tops = [b for b in find(img, CARD_COLORS["Purple"], tol=6, min_area=100) if b.w >= 50]
    bottoms = [b for b in find(img, CARD_COLORS["Black"], tol=6, min_area=100) if b.w >= 50]
    assert len(tops) == 5 and len(bottoms) == 5
    for top, bottom in zip(tops, bottoms, strict=True):
        assert top.x0 == bottom.x0 and top.w == bottom.w == 56  # the frame keeps the 56 px portrait size
        assert abs(bottom.y0 - top.y1) <= 2  # the bands meet: a hard split at the middle
        assert abs(top.h - bottom.h) <= 2


# ---- event screen: die badges ----------------------------------------------------
def test_die_faces_show_six_for_won_and_one_for_lost(app, scheme):
    img = app.show(f"/event/{app.newest}")
    s = scheme()
    won, lost = die_faces(img, s.success), die_faces(img, s.error)
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
        round_ones = [b for b in find(img, CARD_COLORS[name], tol=6, min_area=150) if abs(b.w - b.h) <= 2]
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
