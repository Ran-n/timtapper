#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:02.103164
Revised: 2026/10/14 01:08:28.613497

Run the real timtapper desktop app on a throwaway demo database (Windows only).

The desktop transport of the app driver (scripts/demo_driver.py has the demo data
and the commands), shared by scripts/make_screenshots.py and the rendered UI tests
(tests/rendered/). Importing this module points every file the app writes at a
scratch dir, so your own data is never touched.

    uv run python scripts/app_driver.py serve

opens the app in a phone-shaped window and answers one JSON command per stdin
line with one `@@{...}` line on stdout (logs go to stderr).
Taps are not commands: the caller clicks the window itself (scripts/app_window.py).
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "src" / "timtapper"
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# before any app import: every file the app writes goes to a scratch dir
SCRATCH = Path(tempfile.mkdtemp(prefix="timtapper-driven-"))
os.environ["FLET_APP_STORAGE_DATA"] = str(SCRATCH / "data")
os.environ["FLET_APP_STORAGE_TEMP"] = str(SCRATCH / "temp")

import flet as ft  # noqa: E402
from demo_driver import TODAY, Demo, answer  # noqa: E402

from app_window import WINDOW_TITLE  # noqa: E402
from core.logging import setup_logging  # noqa: E402

REPLY = "@@"


class DesktopDemo(Demo):
    """The demo in the driver's own desktop window, which it closes on the way out."""

    def __init__(self, page: ft.Page, today=TODAY) -> None:
        super().__init__(page, today, WINDOW_TITLE)

    async def close_app(self) -> None:
        self.db.dispose()
        await self.page.window.destroy()


def _reply(**payload) -> None:
    print(REPLY + json.dumps(payload), flush=True)


async def serve(page: ft.Page) -> None:
    """Answer commands from stdin until "quit" or end of input."""
    demo = DesktopDemo(page)
    commands = demo.commands()
    demo.show("/events")
    _reply(ok=True, ready=True, newest=demo.newest)
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            if not line.strip():
                continue
            try:
                request = json.loads(line)
            except ValueError as exc:  # a malformed line is reported to the caller, never swallowed
                _reply(ok=False, error=f"{type(exc).__name__}: {exc}")
                continue
            if request.get("cmd") == "quit":
                _reply(ok=True)
                break
            _reply(**await answer(commands, request))
    finally:
        await demo.close_app()


def run(target: Callable) -> None:
    if sys.platform != "win32":
        raise SystemExit("the app driver is Windows only (window capture uses user32 and Pillow's ImageGrab)")
    setup_logging()
    try:
        ft.run(target, assets_dir=str(APP_DIR / "assets"))
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["serve"]:
        raise SystemExit("usage: app_driver.py serve")
    run(serve)
