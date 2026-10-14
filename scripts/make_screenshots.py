#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 01:04:16.610782
Revised: 2026/10/14 01:08:28.931444

Take the README screenshots (docs/screenshots/*.png) from the real app.

Opens timtapper in a phone-shaped desktop window on a throwaway database
seeded with a fixed set of demo events (scripts/demo_driver.py), walks the
screens and grabs each one from the window (Windows only: Flet 1.0's
page.take_screenshot returns nothing on desktop, so Pillow captures the
window's client area instead; scripts/app_window.py). Also renders an event
share card. Your own data is never touched. Re-run after a visible change, and
don't cover the window while it runs:

    uv run python scripts/make_screenshots.py
"""

import asyncio
import datetime as dt
import shutil

import flet as ft

from app_driver import ROOT, DesktopDemo, run
from app_window import AppWindow
from core.logging import get_logger
from i18n import event_type_label
from share import render

OUT_DIR = ROOT / "docs" / "screenshots"

_log = get_logger("scripts.screenshots")


async def capture(window: AppWindow, name: str) -> None:
    # off the event loop: the app keeps answering its client while we wait for the screen to settle
    shot = await asyncio.to_thread(window.capture)
    shot.save(OUT_DIR / f"{name}.png", optimize=True)
    _log.info("saved %s.png", name)


async def shoot(page: ft.Page) -> None:
    demo = DesktopDemo(page, dt.date.today())
    window = AppWindow()
    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(window.wait_open)

        async def show(route: str, name: str, mode: str = "dark") -> None:
            demo.show(route, mode)
            await capture(window, name)

        await show("/events", "events")
        await show(f"/event/{demo.newest}", "event")
        demo.open_picker()
        await capture(window, "picker")
        demo.close()
        await show("/stats", "stats")
        await show("/settings", "settings", mode="light")
        await show("/events", "events-light", mode="light")

        _ = demo.ctx._
        ev = demo.ctx.events.get(demo.newest)
        card = render.event_card(ev, demo.ctx.leaders_by_id, _, event_type_label(_, ev.event_type))
        shutil.copyfile(card, OUT_DIR / "share-card.png")
        _log.info("saved share-card.png")
    except Exception:
        _log.exception("screenshot run failed")
        raise
    finally:
        await demo.close_app()


if __name__ == "__main__":
    run(shoot)
