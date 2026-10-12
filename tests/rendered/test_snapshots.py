#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.688508
Revised: 2026/10/12 16:55:00.735618

Whole-screen snapshots of the real app against checked-in baselines (baselines/*.png).

Any visual change fails here until the new look is approved: rerun with
TIMTAPPER_UPDATE_BASELINES=1, look at every rewritten baseline, commit them.
A failure saves `<name>-actual.png` and `<name>-diff.png` next to pytest's tmp dir.
"""

import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops

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
    # the longest labels (Spanish "Sistema") at the narrowest width
    "settings-dark-narrow-es": ("/settings", "dark", 360, "es"),
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
