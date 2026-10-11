#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 01:04:16.610782
Revised: 2026/10/12 01:04:21.227796

Take the README screenshots (docs/screenshots/*.png) from the real app.

Opens timtapper in a phone-shaped desktop window on a throwaway database
seeded with a fixed set of demo events, walks the screens and grabs each one
from the window (Windows only: Flet 1.0's page.take_screenshot returns
nothing on desktop, so Pillow captures the window's client area instead).
Also renders an event share card. Your own data is never touched. Re-run after
a visible change, and don't cover the window while it runs:

    uv run python scripts/make_screenshots.py
"""

import asyncio
import ctypes
import datetime as dt
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "src" / "timtapper"
OUT_DIR = ROOT / "docs" / "screenshots"
sys.path.insert(0, str(APP_DIR))

# before any app import: every file the app writes goes to a scratch dir
_SCRATCH = Path(tempfile.mkdtemp(prefix="timtapper-shots-"))
os.environ["FLET_APP_STORAGE_DATA"] = str(_SCRATCH / "data")
os.environ["FLET_APP_STORAGE_TEMP"] = str(_SCRATCH / "temp")

import flet as ft  # noqa: E402
from PIL import ImageGrab  # noqa: E402

import main as app_main  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402
from i18n import event_type_label, set_lang  # noqa: E402
from share import render  # noqa: E402
from ui.app import install_routing  # noqa: E402
from ui.context import AppContext  # noqa: E402
from ui.leader_picker import open_picker  # noqa: E402
from ui.theme import apply_theme, get_theme  # noqa: E402

_log = get_logger("scripts.screenshots")

WINDOW_TITLE = "timtapper screenshots"  # unique, so a running copy of the app is never captured instead
SETTLE = 1.5  # seconds for portraits and fonts to paint before a capture

OWN_LEADER = "OP09-061"  # Monkey.D.Luffy
OPPONENTS = ["OP09-001", "OP01-060", "OP05-002", "OP07-038", "ST22-001", "OP11-062", "OP03-022", "OP12-061"]
# (name, type, days ago, rounds); a round is (opponent index, result, went first, won die roll)
EVENTS = [
    (
        "Store championship",
        "regional",
        2,
        [
            (0, "W", True, True),
            (1, "W", False, False),
            (2, "L", True, False),
            (3, "W", True, True),
            (0, None, None, None),
        ],
    ),
    (
        "Thursday locals",
        "locals",
        6,
        [(4, "W", True, True), (5, "L", False, False), (1, "W", True, False), (6, "W", False, True)],
    ),
    (
        "Testing with Dani",
        "testing",
        9,
        [(0, "L", False, False), (0, "W", True, True), (0, "W", True, False), (2, "L", False, True)],
    ),
    ("Online league week 3", "online", 13, [(7, "W", True, True), (3, "W", False, False), (5, "D", True, True)]),
    (
        "Sunday locals",
        "locals",
        20,
        [(1, "L", False, False), (2, "W", True, True), (4, "W", True, False), (0, "L", False, True)],
    ),
]


def seed(ctx: AppContext) -> int:
    """Create the demo events; returns the id of the newest (the one with a round in progress)."""
    by_code = {leader.code: leader.id for leader in ctx.leaders}
    missing = [c for c in (OWN_LEADER, *OPPONENTS) if c not in by_code]
    if missing:
        raise SystemExit(f"demo leaders missing from the catalogue: {missing}")
    today = dt.date.today()
    newest = 0
    for name, event_type, days_ago, rounds in reversed(EVENTS):
        ev = ctx.events.create(name, event_type, today - dt.timedelta(days=days_ago), by_code[OWN_LEADER])
        for opponent, result, went_first, won_die in rounds:
            r = ctx.events.add_round(ev.id, by_code[OPPONENTS[opponent]])
            ctx.events.update_round(r.id, result=result, went_first=went_first, won_die_roll=won_die)
        newest = ev.id
    ctx.invalidate_leaders()
    return newest


async def capture(page: ft.Page, name: str) -> None:
    await asyncio.sleep(SETTLE)
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, WINDOW_TITLE)
    if not hwnd:
        raise RuntimeError(f"window {WINDOW_TITLE!r} not found")
    user32.SetForegroundWindow(hwnd)  # a covered window captures whatever covers it
    await asyncio.sleep(0.3)
    ImageGrab.grab(window=hwnd).save(OUT_DIR / f"{name}.png", optimize=True)
    _log.info("saved %s.png", name)


async def run(page: ft.Page) -> None:
    page.title = WINDOW_TITLE
    app_main.shape_window(page)
    db = app_main.open_database()
    try:
        ctx = AppContext(page, db)
        set_lang(page, "en")
        ctx.theme = get_theme("gruvbox")
        route_change = install_routing(ctx)
        newest = seed(ctx)
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        async def show(route: str, name: str, mode: str = "dark") -> None:
            ctx.theme_mode = mode
            apply_theme(page, ctx.theme, mode)
            page.route = route
            route_change()
            await capture(page, name)

        await show("/events", "events")
        await show(f"/event/{newest}", "event")
        open_picker(ctx, "Opponent's leader", lambda _leader: None)
        await capture(page, "picker")
        page.pop_dialog()
        await show("/stats", "stats")
        await show("/settings", "settings", mode="light")
        await show("/events", "events-light", mode="light")

        _ = ctx._
        ev = ctx.events.get(newest)
        card = render.event_card(ev, ctx.leaders_by_id, _, event_type_label(_, ev.event_type))
        shutil.copyfile(card, OUT_DIR / "share-card.png")
        _log.info("saved share-card.png")
    except Exception:
        _log.exception("screenshot run failed")
        raise
    finally:
        db.dispose()
        await page.window.destroy()


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("make_screenshots.py captures windows with Pillow's Windows-only ImageGrab(window=...)")
    setup_logging()
    try:
        ft.run(run, assets_dir=str(APP_DIR / "assets"))
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)
