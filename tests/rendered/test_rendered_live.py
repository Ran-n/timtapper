#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 22:20:02.105367
Revised: 2026/10/13 09:33:41.285939

The real app against the real optcgapi.com: a real click on Settings → Update leaders, then what the app
stored, said and showed. Needs both the screen (desktop) and the network (live): `uv run pytest -m "desktop or
live"` runs it, `-m "live and not desktop"` leaves it out.
"""

import time

import pytest

from pixels import count, find

pytestmark = [pytest.mark.desktop, pytest.mark.live]

UPDATE_TIMEOUT = 180  # seconds: every card list, then the portraits of leaders newer than the bundled list


def update_button(img, s):
    """The "Update leaders" button: the first filled tonal button down the settings screen. The theme mode's selected
    segment is filled in the same tint and is about as tall (29 dp at 125% scaling, 30 at 100%), so width tells them
    apart: a segment is a third of the row (at most ~120 dp on a phone), the button ~175 dp."""
    tonal = s.tint(s.secondary, 0.28)
    found = [b for b in find(img, tonal, tol=6, min_area=1500) if b.w >= 140 and 28 <= b.h <= 60]
    assert found, "no filled tonal button on the settings screen"
    return min(found, key=lambda b: b.y0)


def test_live_update_leaders_click_downloads_and_reports(app, scheme):
    s = scheme()
    img = app.show("/settings", "dark")
    button = update_button(img, s)
    before = app.send("leaders")
    # a bare click, not app.click(): the busy spinner keeps the screen moving, so it never settles for a capture
    app.window.click(button.cx * app.scale, button.cy * app.scale)
    deadline = time.monotonic() + UPDATE_TIMEOUT
    while True:
        state = app.send("leaders")
        new = state["notices"][len(before["notices"]) :]
        if new and not state["busy"]:
            break
        assert time.monotonic() < deadline, f"no result within {UPDATE_TIMEOUT}s: {state}"
        time.sleep(1)
    (notice,) = new
    assert notice["error"] is False, notice["text"]
    assert notice["text"].startswith("Leaders updated:")
    assert state["count"] >= before["count"]
    shot = app.capture()
    # the info snackbar (filled in the theme's text colour) is on screen, and the button is back to normal
    lower = (0, shot.height // 2, shot.width, shot.height)
    assert count(shot, s.fg, lower, tol=4) > 4000
    assert update_button(shot, s).y0 == button.y0
