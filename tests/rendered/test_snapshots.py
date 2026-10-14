#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.688508
Revised: 2026/10/14 04:13:35.685902

Whole-screen snapshots of the real app against checked-in baselines, one set per target
(baselines/<target>/*.png: desktop, web, android), since each platform rasterises text its own way.

Any visual change fails here until the new look is approved: rerun with
TIMTAPPER_UPDATE_BASELINES=1, look at every rewritten baseline, commit them.
A failure saves `<name>-actual.png` and `<name>-diff.png` next to pytest's tmp dir.
"""

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from locate import scroll_to_end
from pixels import find
from ui.theme import THEMES

pytestmark = pytest.mark.snapshot

BASELINES = Path(__file__).resolve().parent / "baselines"
UPDATE = os.environ.get("TIMTAPPER_UPDATE_BASELINES") == "1"
# a pixel counts as changed past this channel difference; anti-aliasing jitter stays well below it
PIXEL_TOLERANCE = 48
MAX_CHANGED = 12  # pixels allowed to change: rendering is deterministic, and a redrawn icon changes far more

STATES = {
    "events-dark": ("/events", "dark", 0),
    "events-light": ("/events", "light", 0),
    "events-dark-narrow": ("/events", "dark", 360),
    "event-dark": ("/event/{newest}", "dark", 0),
    "event-light-narrow": ("/event/{newest}", "light", 360),
    "stats-dark": ("/stats", "dark", 0),
    "stats-light-narrow": ("/stats", "light", 360),
    "settings-dark": ("/settings", "dark", 0),
    "settings-light-narrow": ("/settings", "light", 360),
    # the longest labels (Spanish "Sistema", Galician too) at the narrowest width, on every screen
    "settings-dark-narrow-es": ("/settings", "dark", 360, "es"),
    "settings-dark-narrow-gl": ("/settings", "dark", 360, "gl"),
    "events-dark-narrow-es": ("/events", "dark", 360, "es"),
    "events-light-narrow-gl": ("/events", "light", 360, "gl"),
    "event-dark-narrow-es": ("/event/{newest}", "dark", 360, "es"),
    "event-light-narrow-gl": ("/event/{newest}", "light", 360, "gl"),
    "stats-dark-narrow-es": ("/stats", "dark", 360, "es"),
    "stats-light-narrow-gl": ("/stats", "light", 360, "gl"),
}


def changed_pixels(actual: Image.Image, expected: Image.Image) -> tuple[int, Image.Image]:
    diff = ImageChops.difference(actual, expected)
    r, g, b = diff.split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > PIXEL_TOLERANCE else 0)
    return worst.histogram()[255], worst


def baselines_for(app) -> Path:
    """One set of baselines per target, and on desktop per display scaling: text rasterises differently at each,
    even shrunk to dp (the phone has one fixed density, the browser runs at 1)."""
    folder = BASELINES / app.name
    return folder if app.name != "desktop" or app.scale == 1 else folder / f"scale-{round(app.scale * 100)}"


def check(name: str, actual: Image.Image, tmp_path: Path, app, ignore: tuple = ()) -> None:
    """`actual` against the baseline `name`; the boxes in `ignore` (dp) may differ (a blinking text caret)."""
    folder = baselines_for(app)
    baseline = folder / f"{name}.png"
    if UPDATE:
        folder.mkdir(parents=True, exist_ok=True)
        actual.save(baseline, optimize=True)
        pytest.skip(f"baseline {name}.png rewritten: look at it before committing")
    assert baseline.is_file(), f"no baseline {baseline.name}; create it with TIMTAPPER_UPDATE_BASELINES=1"
    expected = Image.open(baseline).convert("RGB")
    assert actual.size == expected.size, f"{name}: window is {actual.size}, baseline {expected.size}"
    compared = actual.copy()
    for box in ignore:
        compared.paste(expected.crop(box), box[:2])
    changed, diff = changed_pixels(compared, expected)
    if changed > MAX_CHANGED:
        actual.save(tmp_path / f"{name}-actual.png")
        diff.save(tmp_path / f"{name}-diff.png")
        pytest.fail(f"{name}: {changed} pixels changed (box {diff.getbbox()}); see {tmp_path}")


@pytest.mark.parametrize("name", list(STATES))
def test_screen_matches_baseline(app, name, tmp_path):
    route, mode, width, *lang = STATES[name]
    check(name, app.show(route.format(newest=app.newest), mode, width, *lang), tmp_path, app)


def test_open_event_filters_match_baseline(app, tmp_path):
    app.send("show", route="/events", mode="dark", width=360, filters_open=True)
    try:
        check("events-filters-dark-narrow", app.capture(), tmp_path, app)
    finally:
        app.send("show", route="/events")


@pytest.mark.parametrize("lang", ["en", "es"])  # Spanish: the longest search hint
def test_picker_matches_baseline(app, tmp_path, lang):
    app.send("show", route=f"/event/{app.newest}", mode="dark", width=360, lang=lang)
    app.send("picker")
    try:
        # the search field has the focus as the sheet opens: its caret blinks, so a capture may or may not show it
        s = THEMES["gruvbox"].dark
        found = app.wait_until(lambda: app.rings(s.primary, min_w=200, min_h=36, max_h=64), what="the search field")
        search = found[0]
        caret = (search.x0 + 36, search.y0 + 4, search.x0 + 56, search.y1 - 4)
        ignore = [caret]
        img = app.capture()
        if app.name == "android":  # with a field focused the navigation bar slides in a keyboard button at the bottom
            ignore.append((0, img.height - 8, img.width, img.height))
        name = "picker-dark-narrow" if lang == "en" else f"picker-dark-narrow-{lang}"
        check(name, img, tmp_path, app, ignore=tuple(ignore))
    finally:
        app.send("close")


def event_id(app, name: str) -> int:
    return next(e["id"] for e in app.send("events") if e["name"] == name)


@pytest.mark.parametrize(
    ("name", "event", "mode", "width"),
    [
        # a top-cut best of 3 (its number kept, a line per game under it) at the narrowest width
        ("event-bo3-dark-narrow", "Thursday locals", "dark", 360),
        ("event-bo3-light", "Thursday locals", "light", 0),
        # a bye: the jester framed in gold, "Automatic win"
        ("event-bye-dark", "Treasure Cup Madrid", "dark", 0),
        ("event-bye-light-narrow-es", "Treasure Cup Madrid", "light", 360),
    ],
)
def test_round_kinds_match_baselines(app, tmp_path, name, event, mode, width):
    app.show(f"/event/{event_id(app, event)}", mode, width, "es" if name.endswith("-es") else "en")
    check(name, scroll_to_end(app), tmp_path, app)


def test_an_open_round_matches_baseline(app, tmp_path):
    img = app.show(f"/event/{app.newest}", "dark", 360)
    faces = [b for b in find(img, THEMES["gruvbox"].dark.success, tol=6, min_area=150) if 16 <= b.w <= 26]
    first = min(faces, key=lambda b: b.y0)  # round 1's die (won)
    try:
        app.click(150, first.cy)
        check("event-round-open-dark-narrow", app.scroll(180, 400, 3), tmp_path, app)
    finally:
        app.send("show", route="/events")


def test_the_delete_dialog_matches_baseline(app, tmp_path):
    img = app.show(f"/event/{app.newest}", "dark", 360)
    try:
        app.click(img.width - 20, 28)  # the ⋮ menu
        check("event-delete-dialog-dark-narrow", app.click(img.width - 100, 40), tmp_path, app)
    finally:
        app.send("close")


@pytest.mark.parametrize(("name", "route"), [("events-empty-dark", "/events"), ("stats-empty-dark", "/stats")])
def test_empty_screens_match_baselines(app, tmp_path, name, route):
    app.send("clear_events")
    try:
        check(name, app.show(route, "dark"), tmp_path, app)
    finally:
        app.reset()
