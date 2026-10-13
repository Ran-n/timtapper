#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.688508
Revised: 2026/10/13 00:30:07.896829

Whole-screen snapshots of the real app against checked-in baselines (baselines/*.png).

Any visual change fails here until the new look is approved: rerun with
TIMTAPPER_UPDATE_BASELINES=1, look at every rewritten baseline, commit them.
A failure saves `<name>-actual.png` and `<name>-diff.png` next to pytest's tmp dir.
"""

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from pixels import find
from ui.theme import THEMES

pytestmark = [pytest.mark.desktop, pytest.mark.snapshot]

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


def baselines_for(scale: float) -> Path:
    """One set of baselines per display scaling: text rasterises differently at each, even shrunk to dp."""
    return BASELINES if scale == 1 else BASELINES / f"scale-{round(scale * 100)}"


def check(name: str, actual: Image.Image, tmp_path: Path, scale: float) -> None:
    folder = baselines_for(scale)
    baseline = folder / f"{name}.png"
    if UPDATE:
        folder.mkdir(parents=True, exist_ok=True)
        actual.save(baseline, optimize=True)
        pytest.skip(f"baseline {name}.png rewritten: look at it before committing")
    assert baseline.is_file(), f"no baseline {baseline.name}; create it with TIMTAPPER_UPDATE_BASELINES=1"
    expected = Image.open(baseline).convert("RGB")
    assert actual.size == expected.size, f"{name}: window is {actual.size}, baseline {expected.size}"
    changed, diff = changed_pixels(actual, expected)
    if changed > MAX_CHANGED:
        actual.save(tmp_path / f"{name}-actual.png")
        diff.save(tmp_path / f"{name}-diff.png")
        pytest.fail(f"{name}: {changed} pixels changed (box {diff.getbbox()}); see {tmp_path}")


@pytest.mark.parametrize("name", list(STATES))
def test_screen_matches_baseline(app, name, tmp_path):
    route, mode, width, *lang = STATES[name]
    check(name, app.show(route.format(newest=app.newest), mode, width, *lang), tmp_path, app.scale)


def test_open_event_filters_match_baseline(app, tmp_path):
    app.send("show", route="/events", mode="dark", width=360, filters_open=True)
    try:
        check("events-filters-dark-narrow", app.capture(), tmp_path, app.scale)
    finally:
        app.send("show", route="/events")


def test_picker_matches_baseline(app, tmp_path):
    app.send("show", route=f"/event/{app.newest}", mode="dark", width=360)
    app.send("picker")
    try:
        check("picker-dark-narrow", app.capture(), tmp_path, app.scale)
    finally:
        app.send("close")


def event_id(app, name: str) -> int:
    return next(e["id"] for e in app.send("events") if e["name"] == name)


def scrolled_to_end(app):
    img = app.capture()
    for _ in range(4):
        img = app.scroll(img.width / 2, img.height / 2, 10)
    return img


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
    check(name, scrolled_to_end(app), tmp_path, app.scale)


def test_an_open_round_matches_baseline(app, tmp_path):
    img = app.show(f"/event/{app.newest}", "dark", 360)
    faces = [b for b in find(img, THEMES["gruvbox"].dark.success, tol=6, min_area=150) if 16 <= b.w <= 26]
    first = min(faces, key=lambda b: b.y0)  # round 1's die (won)
    try:
        app.click(150, first.cy)
        check("event-round-open-dark-narrow", app.scroll(180, 400, 3), tmp_path, app.scale)
    finally:
        app.send("show", route="/events")


def test_the_delete_dialog_matches_baseline(app, tmp_path):
    img = app.show(f"/event/{app.newest}", "dark", 360)
    try:
        app.click(img.width - 20, 28)  # the ⋮ menu
        check("event-delete-dialog-dark-narrow", app.click(img.width - 100, 40), tmp_path, app.scale)
    finally:
        app.send("close")


@pytest.mark.parametrize(("name", "route"), [("events-empty-dark", "/events"), ("stats-empty-dark", "/stats")])
def test_empty_screens_match_baselines(app, tmp_path, name, route):
    app.send("clear_events")
    try:
        check(name, app.show(route, "dark"), tmp_path, app.scale)
    finally:
        app.reset()
