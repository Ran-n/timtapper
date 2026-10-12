#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:02.103164
Revised: 2026/10/12 13:16:02.103164

Run the real timtapper desktop app on a throwaway demo database (Windows only).

The inside half of driving the real app, shared by scripts/make_screenshots.py
and the rendered UI tests (tests/rendered/). Importing this module points every
file the app writes at a scratch dir, so your own data is never touched.

    uv run python scripts/app_driver.py serve

opens the app in a phone-shaped window and answers one JSON command per stdin
line with one `@@{...}` line on stdout (logs go to stderr). Commands:

    {"cmd": "show", "route": "/events", "mode": "dark", "theme": "gruvbox", "lang": "en", "width": 412}
    {"cmd": "picker"}                 open the opponent leader picker
    {"cmd": "picker_shown"}           codes and colors of the leaders the open picker lists
    {"cmd": "close"}                  close the open dialog or sheet
    {"cmd": "round", "round_no": 1}   a round of the newest demo event
    {"cmd": "quit"}

Every reply has "ok"; a failed command replies {"ok": false, "error": "..."}.
Taps are not commands: the caller clicks the window itself (scripts/app_window.py).
"""

import asyncio
import datetime as dt
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

import main as app_main  # noqa: E402
from app_window import WINDOW_TITLE  # noqa: E402
from core.logging import get_logger, setup_logging  # noqa: E402
from i18n import set_lang  # noqa: E402
from ui.app import install_routing  # noqa: E402
from ui.context import AppContext  # noqa: E402
from ui.leader_picker import build_picker  # noqa: E402
from ui.theme import apply_theme, get_theme  # noqa: E402

_log = get_logger("scripts.app_driver")

REPLY = "@@"
DEFAULT_WIDTH = app_main.PHONE_WINDOW["width"]

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


def seed(ctx: AppContext, today: dt.date) -> int:
    """Create the demo events, dated back from `today`; returns the id of the newest (a round still in progress)."""
    by_code = {leader.code: leader.id for leader in ctx.leaders}
    missing = [c for c in (OWN_LEADER, *OPPONENTS) if c not in by_code]
    if missing:
        raise SystemExit(f"demo leaders missing from the catalogue: {missing}")
    newest = 0
    for name, event_type, days_ago, rounds in reversed(EVENTS):
        ev = ctx.events.create(name, event_type, today - dt.timedelta(days=days_ago), by_code[OWN_LEADER])
        for opponent, result, went_first, won_die in rounds:
            r = ctx.events.add_round(ev.id, by_code[OPPONENTS[opponent]])
            ctx.events.update_round(r.id, result=result, went_first=went_first, won_die_roll=won_die)
        newest = ev.id
    ctx.invalidate_leaders()
    return newest


class Demo:
    """The app on screen with the demo data, and the moves a driver makes on it."""

    def __init__(self, page: ft.Page, today: dt.date) -> None:
        page.title = WINDOW_TITLE
        app_main.shape_window(page)
        self.page = page
        self.db = app_main.open_database()
        self.ctx = AppContext(page, self.db)
        set_lang(page, "en")
        self.ctx.theme = get_theme("gruvbox")
        self.route_change = install_routing(self.ctx)
        self.newest = seed(self.ctx, today)
        self.sheet: ft.BottomSheet | None = None

    def show(self, route: str, mode: str = "dark", theme: str = "gruvbox", lang: str = "en", width: int = 0) -> None:
        self.close()
        set_lang(self.page, lang)
        self.ctx.theme = get_theme(theme)
        self.ctx.theme_mode = mode
        apply_theme(self.page, self.ctx.theme, mode)
        self.page.window.width = width or DEFAULT_WIDTH
        self.page.route = route
        self.route_change()

    def open_picker(self) -> None:
        self.sheet = build_picker(self.ctx, self.ctx._("Opponent's leader"), lambda _leader: None)
        self.page.show_dialog(self.sheet)

    def close(self) -> None:
        if self.sheet is not None:
            self.page.pop_dialog()
            self.sheet = None

    def picker_shown(self) -> list[dict]:
        if self.sheet is None:
            raise RuntimeError("no picker open")
        results = next(c for c in _walk(self.sheet) if getattr(c, "data", None) == "leader-results")
        by_id = self.ctx.leaders_by_id
        return [
            {"code": by_id[c.data].code, "colors": list(by_id[c.data].colors)}
            for c in results.controls
            if isinstance(c.data, int)
        ]

    def round(self, round_no: int) -> dict:
        r = next(r for r in self.ctx.events.get(self.newest).rounds if r.round_no == round_no)
        return {"result": r.result, "went_first": r.went_first, "won_die_roll": r.won_die_roll}

    async def close_app(self) -> None:
        self.db.dispose()
        await self.page.window.destroy()


def _walk(control):
    yield control
    for name in ("content", "controls"):
        value = getattr(control, name, None)
        if isinstance(value, ft.BaseControl):
            yield from _walk(value)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, ft.BaseControl):
                    yield from _walk(child)


def _reply(**payload) -> None:
    print(REPLY + json.dumps(payload), flush=True)


async def serve(page: ft.Page) -> None:
    """Answer commands from stdin until "quit" or end of input."""
    demo = Demo(page, dt.date(2026, 10, 12))  # a fixed date, so dates on screen never change between runs
    handlers: dict[str, Callable[..., object]] = {
        "show": demo.show,
        "picker": demo.open_picker,
        "picker_shown": demo.picker_shown,
        "close": demo.close,
        "round": demo.round,
    }
    demo.show("/events")
    _reply(ok=True, ready=True, newest=demo.newest)
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line or not line.strip():
                if not line:
                    break
                continue
            try:
                request = json.loads(line)
                cmd = request.pop("cmd")
                if cmd == "quit":
                    _reply(ok=True)
                    break
                result = handlers[cmd](**request)
                _reply(ok=True, result=result)
            except Exception as exc:  # a driver error is reported to the caller, never swallowed
                _log.exception("driver command failed: %s", line.strip())
                _reply(ok=False, error=f"{type(exc).__name__}: {exc}")
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
