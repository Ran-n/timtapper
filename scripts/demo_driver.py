#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:10:19.506999
Revised: 2026/10/14 03:41:53.675108

The real app on a fixed set of demo events, and every command a test driver sends it: the part of driving the app
that is the same on every target. Two transports carry the commands, one JSON object per command, one reply each:

    scripts/app_driver.py    desktop: the app runs in the driver's own process, commands on stdin
    scripts/driven_main.py   web and Android: the built app polls the test harness over HTTP

Commands (every reply has "ok"; a failed command replies {"ok": false, "error": "..."}):

    {"cmd": "show", "route": "/events", "mode": "dark", "theme": "gruvbox", "lang": "en", "width": 412,
     "filters_open": false}           every show starts with the events list unfiltered
    {"cmd": "picker"}                 open the opponent leader picker
    {"cmd": "picker_shown"}           codes and colors of the leaders the open picker lists
    {"cmd": "close"}                  close every open sheet, dialog and snackbar
    {"cmd": "round", "round_no": 1}   a round of the newest demo event
    {"cmd": "state"}                  the theme and brightness mode the app has now
    {"cmd": "event_filters"}          the events list's search, filters and whether its dropdowns are open
    {"cmd": "leaders"}                the catalogue's size, whether an update runs, every message the app showed
    {"cmd": "reset"}                  every event deleted and the demo data seeded again; replies the newest id
    {"cmd": "clear_events"}           every event deleted (the empty screens)
    {"cmd": "event", "event_id": 1}   an event as stored (default: the newest demo event), rounds included
    {"cmd": "events"}                 every event's id and name, newest first
    {"cmd": "notices"}                every snackbar message the app showed, oldest first
    {"cmd": "dialogs"}                the open dialogs, sheets and snackbars, by type
    {"cmd": "view"}                   the top view's route and how many views are stacked
    {"cmd": "field", "data": "name"}  the value (and disabled flag) of the control tagged `data` on screen
    {"cmd": "draft"}                  the id of the untouched new event, or null
    {"cmd": "shared"}                 every file the app shared, with its size (the share sheet is stubbed: it records
                                      instead; read the file through the app: on the web it lives in the browser)
    {"cmd": "real_share", "on": true} hand shares to the platform's real share sheet or download again
    {"cmd": "next_import", "path": p} the file the next "Import backup" picks (the file picker is stubbed)
    {"cmd": "offline", "on": true}    make every leader download fail as if there were no connection
    {"cmd": "quit"}

Taps are not commands: the caller taps the screen itself, as a person does (tests/rendered/targets.py).
"""

import datetime as dt
import inspect
from collections.abc import Callable
from pathlib import Path

import flet as ft
from PIL import Image

import main as app_main
from catalog import sync as sync_mod
from catalog.optcgapi import CatalogError
from core.logging import get_logger
from i18n import set_lang
from share.deliver import Delivery
from stats.compute import Filters
from ui import context as context_mod
from ui import leader_updates as updates_mod
from ui.app import install_routing
from ui.context import AppContext
from ui.leader_picker import build_picker
from ui.theme import apply_theme, get_theme

_log = get_logger("scripts.demo_driver")

TODAY = dt.date(2026, 10, 12)  # a fixed date, so dates on screen never change between runs
DEFAULT_WIDTH = app_main.PHONE_WINDOW["width"]

OWN_LEADER = "OP09-061"  # Monkey.D.Luffy
# index 8 has no spaces in its name (Eustass"Captain"Kid): it wraps only at the break points after its quotes
OPPONENTS = ["OP09-001", "OP01-060", "OP05-002", "OP07-038", "ST22-001", "OP11-062", "OP03-022", "OP12-061", "OP10-099"]
# (placement, players) per event; testing sessions have none, one event knows only its field size
STANDINGS = {
    "Store championship": (3, 32),
    "Thursday locals": (1, 12),
    "Treasure Cup Madrid": (5, 40),
    "Sunday locals": (None, 10),
}
# (name, type, days ago, rounds); a round is (opponent index, result, went first, won die roll), or
# (TOP_CUT_BO3, opponent index, [(result, went first, you chose) per game]) for a top-cut best of 3
TOP_CUT_BO3 = "top-cut-bo3"
BYE_ROUND = ("bye",)  # a bye: no opponent, won
DEMO_SET = "OP16"  # the set every demo event was played in
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
            (8, None, None, None),
        ],
    ),
    (
        "Thursday locals",
        "locals",
        6,
        [
            (4, "W", True, True),
            (5, "L", False, False),
            (1, "W", True, False),
            (6, "W", False, True),
            # top cut, best of 3, won 2-1: you had the higher seed and chose for game 1; the loser chose after
            (TOP_CUT_BO3, 3, [("L", True, True), ("W", False, None), ("W", True, None)]),
        ],
    ),
    (
        "Testing with Dani",
        "testing",
        9,
        [(0, "L", False, False), (0, "W", True, True), (0, "W", True, False), (2, "L", False, True)],
    ),
    (
        "Treasure Cup Madrid",
        "treasure_cup",
        13,
        [BYE_ROUND, (7, "W", True, True), (3, "W", False, False), (5, "L", True, True)],
    ),
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
        ctx.events.update(ev.id, set_code=DEMO_SET)
        if name in STANDINGS:
            placement, players = STANDINGS[name]
            ctx.events.update(ev.id, placement=placement, players=players)
        for spec in rounds:
            if spec[0] == TOP_CUT_BO3:
                _kind, opponent, games = spec
                r = ctx.events.add_round(ev.id, by_code[OPPONENTS[opponent]], "top_cut")
                for n, (result, went_first, chose) in enumerate(games, start=1):
                    ctx.events.update_game(r.id, n, result=result, went_first=went_first, chose_turn=chose)
                continue
            if spec == BYE_ROUND:
                ctx.events.add_round(ev.id, None, "bye")
                continue
            opponent, result, went_first, won_die = spec
            r = ctx.events.add_round(ev.id, by_code[OPPONENTS[opponent]])
            ctx.events.update_game(r.id, 1, result=result, went_first=went_first, chose_turn=won_die)
        newest = ev.id
    ctx.invalidate_leaders()
    return newest


class Demo:
    """The app on screen with the demo data, and the moves a driver makes on it."""

    def __init__(self, page: ft.Page, today: dt.date, title: str) -> None:
        page.title = title
        app_main.shape_window(page)
        self.page = page
        self.db = app_main.open_database()
        self.ctx = AppContext(page, self.db)
        set_lang(page, "en")
        self.ctx.theme = get_theme("gruvbox")
        self.route_change = install_routing(self.ctx)
        self.newest = seed(self.ctx, today)
        self.sheet: ft.BottomSheet | None = None
        # every snackbar the app shows, so a test can read what an action reported without matching its pixels
        self.notices: list[dict] = []
        show_notice = self.ctx.notify

        def notify(msg: str, error: bool = False) -> None:
            self.notices.append({"text": msg, "error": error})
            show_notice(msg, error)

        self.ctx.notify = notify
        self.today = today
        # sharing opens a native sheet or save dialog no test can answer: record the file instead (`real_share`
        # puts the platform's own back, for the tests that check the sheet itself opens)
        self.shared_files: list[dict] = []
        self._deliver = context_mod.deliver

        async def deliver(path: Path, *, title: str, mime_type: str) -> Delivery:
            shared = {"path": str(path), "title": title, "mime_type": mime_type, "bytes": path.stat().st_size}
            if mime_type.startswith("image/"):
                with Image.open(path) as image:
                    shared["pixels"] = list(image.size)
            self.shared_files.append(shared)
            return Delivery.SHARED

        self._recording_deliver = deliver
        context_mod.deliver = deliver
        # the native file picker likewise: "Import backup" picks whatever next_import queued (nothing: cancelled)
        self.import_path: Path | None = None
        demo = self

        class Picker:
            async def pick_files(self, **_kwargs) -> list[ft.FilePickerFile] | None:
                path, demo.import_path = demo.import_path, None
                return [ft.FilePickerFile(1, path.name, path.stat().st_size, path=str(path))] if path else None

        ft.FilePicker = Picker
        self._online = (sync_mod.fetch_leaders, sync_mod.fetch_sources, updates_mod.fetch_sources)

    def show(
        self,
        route: str,
        mode: str = "dark",
        theme: str = "gruvbox",
        lang: str = "en",
        width: int = 0,
        filters_open: bool = False,
    ) -> None:
        self.close()
        # a fresh screen every time: Flutter keeps a page's state (its scroll offset too) while its route stays the
        # same, so showing a screen again would start where the last test left it
        self.page.views.clear()
        self.page.update()
        self.ctx.event_filters = Filters()
        self.ctx.event_filters_open = filters_open
        set_lang(self.page, lang)
        self.ctx.theme = get_theme(theme)
        self.ctx.theme_mode = mode
        apply_theme(self.page, self.ctx.theme, mode)
        self.page.window.width = width or DEFAULT_WIDTH  # the desktop window; a browser or phone sizes itself
        if route.startswith("/event/"):  # reached from the list, as a person does: back leads to the list
            self.page.route = "/events"
            self.route_change()
        self.page.route = route
        self.route_change()

    def open_picker(self) -> None:
        self.sheet = build_picker(self.ctx, self.ctx._("Opponent's leader"), lambda _leader: None)
        self.page.show_dialog(self.sheet)

    def close(self) -> None:
        """Close every open sheet, dialog and snackbar: a message left by the last test must not show in the next."""
        while self.page.pop_dialog() is not None:
            pass
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
        """Round `round_no` of the newest demo event: its game 1 (the whole round in a best of 1)."""
        r = next(r for r in self.ctx.events.get(self.newest).rounds if r.round_no == round_no)
        game = r.game(1)
        return {"result": r.result, "went_first": game.went_first, "won_die_roll": game.chose_turn}

    def state(self) -> dict:
        return {"theme": self.ctx.theme.key, "mode": self.ctx.theme_mode}

    def event_filters(self) -> dict:
        f = self.ctx.event_filters
        return {
            "open": self.ctx.event_filters_open,
            "query": f.query,
            "event_type": f.event_type,
            "own_leader_id": f.own_leader_id,
        }

    def leaders(self) -> dict:
        return {
            "count": self.ctx.leader_repo.count(),
            "busy": self.ctx.leader_updates.busy,
            "notices": list(self.notices),
        }

    # ---- data ------------------------------------------------------------------
    def clear_events(self) -> None:
        self.close()
        self.ctx.draft = None
        for ev in self.ctx.events.list():
            self.ctx.events.delete(ev.id)
        self.ctx.invalidate_leaders()

    def reset(self) -> int:
        self.clear_events()
        self.newest = seed(self.ctx, self.today)
        self.notices.clear()
        self.shared_files.clear()
        self.import_path = None
        self.offline(False)
        self.real_share(False)
        return self.newest

    def offline(self, on: bool = True) -> None:
        def down(*_args, **_kwargs):
            raise CatalogError("no connection (driver)")

        sync_mod.fetch_leaders, sync_mod.fetch_sources, updates_mod.fetch_sources = (
            (down, down, down) if on else self._online
        )

    def real_share(self, on: bool = True) -> None:
        """Hand shared files to the platform's own share sheet or download (on), or record them (off, the default)."""
        context_mod.deliver = self._deliver if on else self._recording_deliver

    def next_import(self, path: str) -> None:
        self.import_path = Path(path)

    # ---- read-only state --------------------------------------------------------
    def event(self, event_id: int | None = None) -> dict:
        ev = self.ctx.events.get(event_id or self.newest)
        codes = {leader.id: leader.code for leader in self.ctx.leaders}
        return {
            "id": ev.id,
            "name": ev.name,
            "event_type": ev.event_type,
            "date": ev.date.isoformat(),
            "leader": codes.get(ev.leader_id),
            "notes": ev.notes,
            "placement": ev.placement,
            "players": ev.players,
            "rounds": [
                {
                    "round_no": r.round_no,
                    "opponent": codes.get(r.opponent_leader_id),
                    "best_of": r.best_of,
                    "result": r.result,
                    "top_cut": r.top_cut,
                    "notes": r.notes,
                    "games": [
                        {"result": g.result, "went_first": g.went_first, "chose_turn": r.chose_turn(g.game_no)}
                        for g in r.games
                    ],
                }
                for r in ev.rounds
            ],
        }

    def events(self) -> list[dict]:
        return [{"id": ev.id, "name": ev.name} for ev in self.ctx.events.list()]

    def notices_shown(self) -> list[dict]:
        return list(self.notices)

    def open_dialogs(self) -> list[str]:
        return [type(d).__name__ for d in self.page._dialogs.controls if d.open]

    def view(self) -> dict:
        return {"route": self.page.views[-1].route, "depth": len(self.page.views)}

    def field(self, data: str) -> dict:
        roots = [self.page.views[-1], *(d for d in self.page._dialogs.controls if d.open)]
        for root in roots:
            for control in _walk_all(root):
                if getattr(control, "data", None) == data:
                    value = getattr(control, "value", None)
                    if value is None and hasattr(control, "selected"):
                        value = list(control.selected or [])
                    return {"value": value, "disabled": bool(getattr(control, "disabled", False))}
        raise LookupError(f"no control tagged {data!r} on screen")

    def draft(self) -> int | None:
        return self.ctx.draft.id if self.ctx.draft else None

    def shared(self) -> list[dict]:
        return list(self.shared_files)

    def commands(self) -> dict[str, Callable[..., object]]:
        """Every command a driver answers, by name ("quit" is the transport's own)."""
        return {
            "show": self.show,
            "picker": self.open_picker,
            "picker_shown": self.picker_shown,
            "close": self.close,
            "round": self.round,
            "state": self.state,
            "event_filters": self.event_filters,
            "leaders": self.leaders,
            "reset": self.reset,
            "clear_events": self.clear_events,
            "event": self.event,
            "events": self.events,
            "notices": self.notices_shown,
            "dialogs": self.open_dialogs,
            "view": self.view,
            "field": self.field,
            "draft": self.draft,
            "shared": self.shared,
            "next_import": self.next_import,
            "offline": self.offline,
            "real_share": self.real_share,
        }


async def answer(commands: dict[str, Callable[..., object]], request: dict) -> dict:
    """Run one command and build its reply: {"ok": true, "result": ...}, or {"ok": false, "error": ...} when it
    fails (reported to the caller and logged, never swallowed)."""
    args = dict(request)
    cmd = args.pop("cmd", None)
    try:
        result = commands[cmd](**args)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        _log.exception("driver command failed: %s", request)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "result": result}


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


def _walk_all(control):
    """`_walk`, plus the parts of a control that aren't its content: app bars, actions, titles, tile controls."""
    yield control
    for name in ("content", "controls", "appbar", "actions", "title", "floating_action_button", "navigation_bar"):
        value = getattr(control, name, None)
        children = value if isinstance(value, list) else [value]
        for child in children:
            if isinstance(child, ft.BaseControl):
                yield from _walk_all(child)
