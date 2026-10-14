#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 16:30:39.263738
Revised: 2026/10/14 16:30:39.263738

The web version's instant shell. Starting the app in a browser takes seconds (Pyodide, then the app's packages), so
the page paints a read-only copy of the app's screens first and hands over once the app is ready (scripts/shell/).
That copy is written here: every screen the app can open at startup — the three tabs and each event — built by the
app's own view code and saved as a tree of the controls on it, with the theme's colors resolved, so the shell draws
exactly what the app would and never needs its own copy of a screen's layout.

The tree is plain JSON: {"t": control type, ...each property set away from its default}. Callbacks are left out,
but a control with one is marked "tap"; one the shell can follow on its own carries "nav", the route it opens.
Icons are their names ("add_outlined"); the shell looks up the codepoints. Image bytes (portraits downloaded after
install) go once into "images" and are referenced by key.
"""

import asyncio
import base64
import dataclasses
import enum
import hashlib
import json
import math
from collections.abc import Callable, Iterable
from types import SimpleNamespace
from typing import Any, Protocol

import flet as ft

from catalog import portraits
from core.logging import get_logger
from db import Database
from i18n import set_lang
from ui.app import NEW_ROUTE, TABS, build_view
from ui.context import AppContext
from ui.theme import AppTheme, Scheme

_log = get_logger("ui.shell")

VERSION = 1
# what a screen tree leaves out: help that needs a hover, and what only matters while editing
SKIPPED = frozenset({"tooltip", "semantics_label", "input_filter", "keyboard_type", "maintain_state", "data"})
# properties whose strings are colors: a theme token ("onsurfacevariant", "primary,0.5") is resolved to hex
COLOR_KEYS = frozenset({"color", "bgcolor", "collapsed_bgcolor", "icon_color", "indicator_color", "colors"})
REFRESH_DELAY = 1.5  # seconds after the last change: a burst of edits writes the shell once


class ShellPage(SimpleNamespace):
    """Just enough of ft.Page to build screens away from the one on display: its language and brightness, and
    no-ops for what a screen only does when tapped."""

    def __init__(self, lang: str, brightness: ft.Brightness | None) -> None:
        super().__init__(route="/", views=[], platform_brightness=brightness)
        set_lang(self, lang)

    def navigate(self, route: str) -> None:
        pass

    def run_task(self, handler, *args) -> None:
        pass

    def show_dialog(self, dialog) -> None:
        pass

    def update(self, *controls) -> None:
        pass


def theme_colors(scheme: Scheme) -> dict[str, str]:
    """Every color token a control can name ("surfacecontainer"), as this palette's hex."""
    colors = ft.ColorScheme  # the dataclass: its fields are the tokens, snake_case
    built = scheme.color_scheme()
    return {
        f.name.replace("_", ""): getattr(built, f.name) for f in dataclasses.fields(colors) if getattr(built, f.name)
    }


class Serializer:
    """Turns a control tree into the shell's JSON. `nav(control)` names the route a tappable control opens, if the
    shell may open it itself."""

    def __init__(self, colors: dict[str, str], images: dict[bytes, str], nav: Callable[[Any], str | None]) -> None:
        self.colors = colors
        self.images = images
        self.nav = nav

    def color(self, value: Any) -> Any:
        if isinstance(value, enum.Enum):
            value = value.value
        if isinstance(value, list | tuple):
            return [self.color(v) for v in value]
        if not isinstance(value, str) or value.startswith("#"):
            return value
        token, _, opacity = value.partition(",")
        hex_ = self.colors.get(token.lower().replace("_", ""), token)
        return f"{hex_},{opacity}" if opacity else hex_

    def image(self, data: bytes) -> dict:
        key = self.images.setdefault(data, f"i{len(self.images)}")
        return {"img": key}

    def value(self, value: Any, key: str = "") -> Any:
        if isinstance(value, float) and math.isinf(value):
            return "inf"  # "as wide as the parent" (width=float("inf")), which JSON can't hold
        if value is None or isinstance(value, bool | int | float) and not isinstance(value, enum.Enum):
            return value
        if isinstance(value, ft.IconData):
            return {"icon": value.name.lower()}
        if key in COLOR_KEYS:
            return self.color(value)
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return self.image(value)
        if isinstance(value, list | tuple):
            return [self.value(v, key) for v in value]
        if isinstance(value, dict):
            return {str(k): self.value(v, key) for k, v in value.items()}
        if dataclasses.is_dataclass(value):
            return self.node(value)
        return None  # a callback, or something the shell can't draw

    def node(self, obj: Any) -> dict:
        out: dict[str, Any] = {"t": type(obj).__name__}
        for f in dataclasses.fields(obj):
            name = f.name
            if name.startswith("_") or name in SKIPPED or _hidden(obj, name):
                continue
            value = getattr(obj, name, None)
            if name == "options" and isinstance(obj, ft.Dropdown):
                value = [o for o in value or () if o.key == obj.value]  # a closed dropdown shows its choice alone
            if name.startswith("on_"):
                if name in ("on_click", "on_change", "on_select", "on_tap") and value is not None:
                    out["tap"] = True
                continue
            if value is None or callable(value) and not isinstance(value, ft.BaseControl):
                continue
            if _is_default(f, value):
                continue
            encoded = self.value(value, name)
            if encoded is not None:
                out[name] = encoded
        route = self.nav(obj)
        if route:
            out["nav"] = route
        return out


def _hidden(obj: Any, name: str) -> bool:
    """What isn't on screen until tapped open: a closed expansion tile's contents (a round's editors) and a menu's
    items. The shell leaves it out."""
    if name == "controls":
        return isinstance(obj, ft.ExpansionTile) and not obj.expanded
    return name == "items" and isinstance(obj, ft.PopupMenuButton)


def _is_default(f: dataclasses.Field, value: Any) -> bool:
    try:
        if f.default is not dataclasses.MISSING:
            return value == f.default
        if f.default_factory is not dataclasses.MISSING:
            return value == f.default_factory()
    except Exception:  # a value that won't compare (a control against a list): it's set, keep it
        return False
    return False


def _nav(event_ids: Iterable[int]) -> Callable[[Any], str | None]:
    """Event tiles carry their event's id as `data`; the events tab's button starts a new one."""
    ids = set(event_ids)

    def nav(control: Any) -> str | None:
        if isinstance(control, ft.Container) and control.on_click is not None and control.data in ids:
            return f"/event/{control.data}"
        if isinstance(control, ft.FloatingActionButton):
            return NEW_ROUTE
        return None

    return nav


class ShellStorage(Protocol):
    """Where the shell's JSON is kept (core.web.ShellStore in a browser)."""

    async def save(self, text: str) -> None: ...

    async def load(self) -> str | None: ...


class ShellWriter:
    """Builds the shell from the database and keeps it in `storage`; `live` is the app's own context, whose language,
    theme and device brightness the shell takes. Each event's screen is kept, under a digest of the event and the
    look, until either changes, so a refresh after an edit rebuilds one screen, not all of them; the digests are saved
    with the shell, so a new visit picks up where the last one left off."""

    def __init__(self, live: AppContext, db: Database, storage: ShellStorage) -> None:
        self.live = live
        # its own connection to the app's database, without the app's commit hook: building the shell reads, every
        # read commits, and through the hook each refresh scheduled the next, cancelling itself before it saved
        self.db = Database(db.path)
        self.storage = storage
        self._events: dict[int, tuple[str, dict]] | None = None  # None: not yet loaded from the saved shell
        self._images: dict[bytes, str] = {}  # kept across refreshes, so a kept screen's image keys still hold
        self._pending: asyncio.Task | None = None
        self._loop = asyncio.get_running_loop()  # made by the app's main(), on its loop

    def close(self) -> None:
        if self._pending is not None:
            self._pending.cancel()
        self.db.dispose()

    def schedule(self) -> None:
        """Refresh soon, once the burst of changes this one belongs to is over. Callable from anywhere: flet
        runs some handlers (a route change) outside the event loop, so the restart goes to the writer's loop."""
        self._loop.call_soon_threadsafe(self._restart)

    def _restart(self) -> None:
        if self._pending is not None and not self._pending.done():
            self._pending.cancel()
        self._pending = self._loop.create_task(self._later())

    async def _later(self) -> None:
        await asyncio.sleep(REFRESH_DELAY)
        await self.refresh()

    async def refresh(self) -> None:
        try:
            if self._events is None:
                await self._resume()
            await self.storage.save(await self.build())
        except asyncio.CancelledError:
            raise
        except Exception:
            # the app works without it: the next visit's shell just shows the screens as they were
            _log.exception("could not write the web shell")

    async def _resume(self) -> None:
        """Take the screens and digests the last visit saved, so its unchanged screens aren't built again."""
        self._events = {}
        try:
            saved = json.loads(await self.storage.load() or "{}")
        except ValueError:
            _log.warning("the saved web shell is not JSON; building every screen again")
            return
        if saved.get("v") != VERSION:
            return
        for key, data in saved.get("images", {}).items():
            self._images[base64.b64decode(data)] = key
        views = saved.get("views", {})
        for event_id, key in saved.get("digests", {}).items():
            tree = views.get(f"/event/{event_id}")
            if tree is not None:
                self._events[int(event_id)] = (key, tree)

    def context(self) -> AppContext:
        live = self.live
        page = ShellPage(live.lang, getattr(live.page, "platform_brightness", None))
        ctx = AppContext(page, self.db)  # fresh: its own leader list and default filters, as a new start has
        ctx.theme, ctx.theme_mode = live.theme, live.theme_mode
        return ctx

    async def build(self) -> str:
        ctx = self.context()
        scheme = ctx.scheme
        hidden = {self.live.draft.id} if self.live.draft is not None else set()
        events = [e for e in ctx.events.list() if e.id not in hidden]
        serializer = Serializer(theme_colors(scheme), self._images, _nav(e.id for e in events))
        look = digest(VERSION, ctx.lang, ctx.theme.key, scheme.dark, ctx.leaders, _portrait_files())
        views = {route: serializer.node(build_view(ctx, route)) for route in TABS}
        cache = self._events or {}
        kept: dict[int, tuple[str, dict]] = {}
        for event in events:
            key = digest(event, look)
            cached = cache.get(event.id)
            if cached is None or cached[0] != key:
                cached = (key, serializer.node(build_view(ctx, f"/event/{event.id}")))
                await asyncio.sleep(0)  # one screen at a time: the app stays responsive while a long list builds
            kept[event.id] = cached
            views[f"/event/{event.id}"] = cached[1]
        self._events = kept
        doc = shell_document(ctx, scheme, views, self._images, {str(i): k for i, (k, _tree) in kept.items()})
        _log.info("web shell: %d screens, %d KB", len(views), len(doc) // 1024)
        return doc


def digest(*parts: Any) -> str:
    """A short fingerprint of `parts` (their repr), stable from one visit to the next."""
    return hashlib.blake2b(repr(parts).encode(), digest_size=12).hexdigest()


def _portrait_files() -> int:
    """How many portraits have been downloaded: a new one changes the screens that show it."""
    try:
        return sum(1 for _ in portraits.cache_dir().iterdir())
    except OSError:
        return 0


def shell_document(
    ctx: AppContext,
    scheme: Scheme,
    views: dict[str, dict],
    images: dict[bytes, str],
    digests: dict[str, str] | None = None,
) -> str:
    """The shell's JSON: the screens and what the shell draws around them."""
    _ = ctx._
    doc = {
        "v": VERSION,
        "lang": ctx.lang,
        "dark": scheme.dark,
        "colors": theme_colors(scheme),
        "scheme": {
            "bg": scheme.bg,
            "fg": scheme.fg,
            "muted": scheme.fg_muted,
            "nav": scheme.surface,
            "indicator": scheme.tint(scheme.primary, 0.35),
        },
        "tabs": TABS,
        "strings": {"opening": _("Opening…")},
        "views": views,
        "images": {key: base64.b64encode(data).decode() for data, key in images.items()},
        "digests": digests or {},
    }
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def default_documents(db: Database, theme: AppTheme, lang: str) -> dict[str, str]:
    """The shell a first visit shows, before the app has ever written one: the screens of an empty app in `lang`,
    in the light and the dark palette (the device picks). Built when the site is, from an empty database."""
    docs = {}
    for name, brightness in (("light", ft.Brightness.LIGHT), ("dark", ft.Brightness.DARK)):
        ctx = AppContext(ShellPage(lang, brightness), db)
        ctx.theme = theme
        scheme = ctx.scheme
        serializer = Serializer(theme_colors(scheme), {}, _nav(()))
        views = {route: serializer.node(build_view(ctx, route)) for route in TABS}
        docs[name] = shell_document(ctx, scheme, views, {})
    return docs
