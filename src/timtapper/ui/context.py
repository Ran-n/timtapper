#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.770833
Revised: 2026/10/11 17:20:12.664993

Per-session app context handed to every screen: repositories, the cached
leader catalogue, translation, notifications, preferences and navigation.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

import flet as ft

from catalog.repository import Leader, LeaderRepository
from core.logging import get_logger
from db import Database
from events.repository import EventRepository
from i18n import Translate, get_lang, set_lang, tr
from share.deliver import Delivery, deliver
from ui.leader_updates import LeaderUpdater
from ui.theme import DEFAULT_MODE, AppTheme, Scheme, apply_theme, get_theme, is_dark
from ui.widgets import make_notifier

_log = get_logger("ui")

PREF_LANG = "timtapper.lang"
PREF_THEME = "timtapper.theme"  # mode: system/light/dark (key predates named themes)
PREF_PALETTE = "timtapper.palette"


class AppContext:
    def __init__(self, page: ft.Page, db: Database) -> None:
        self.page = page
        self.db = db
        self.leader_repo = LeaderRepository(db)
        self.leader_updates = LeaderUpdater(self)
        self.events = EventRepository(db)
        self.theme_mode = DEFAULT_MODE
        self.theme: AppTheme = get_theme(None)
        self.notify = make_notifier(page, lambda: self.scheme)
        self._leaders: list[Leader] | None = None
        self.on_appearance_change: Callable[[], None] | None = None

    # ---- translation / preferences ------------------------------------
    @property
    def _(self) -> Translate:
        return tr(self.page)

    @property
    def lang(self) -> str:
        return get_lang(self.page)

    async def load_prefs(self) -> None:
        try:
            prefs = ft.SharedPreferences()
            set_lang(self.page, await prefs.get(PREF_LANG) or "en")
            self.theme_mode = await prefs.get(PREF_THEME) or DEFAULT_MODE
            self.theme = get_theme(await prefs.get(PREF_PALETTE))
        except Exception:
            _log.warning("could not read saved preferences — using defaults", exc_info=True)
        apply_theme(self.page, self.theme, self.theme_mode)

    async def _save_pref(self, key: str, value: str) -> None:
        try:
            await ft.SharedPreferences().set(key, value)
        except Exception:
            _log.warning("could not save preference %s", key, exc_info=True)
            self.notify(self._("Could not save this setting — it applies until the app restarts"), error=True)

    async def change_language(self, code: str) -> None:
        set_lang(self.page, code)
        _log.info("language set to %s", self.lang)
        await self._save_pref(PREF_LANG, self.lang)
        self.appearance_changed()

    async def change_mode(self, mode: str) -> None:
        self.theme_mode = mode
        self._restyle()
        _log.info("theme mode set to %s", mode)
        await self._save_pref(PREF_THEME, mode)

    async def change_theme(self, key: str) -> None:
        self.theme = get_theme(key)
        self._restyle()
        _log.info("theme set to %s", self.theme.key)
        await self._save_pref(PREF_PALETTE, self.theme.key)

    def _restyle(self) -> None:
        apply_theme(self.page, self.theme, self.theme_mode)
        self.appearance_changed()
        self.page.update()

    # ---- appearance ---------------------------------------------------
    @property
    def scheme(self) -> Scheme:
        """The palette on screen right now (for literal colors: result fills, snackbars)."""
        return self.theme.scheme(is_dark(self.page, self.theme_mode))

    def appearance_changed(self) -> None:
        """Language, theme or device brightness changed: rebuild what's on screen."""
        if self.on_appearance_change:
            self.on_appearance_change()

    # ---- leaders ------------------------------------------------------
    @property
    def leaders(self) -> list[Leader]:
        if self._leaders is None:
            self._leaders = self.leader_repo.all()
        return self._leaders

    @property
    def leaders_by_id(self) -> dict[int, Leader]:
        return {leader.id: leader for leader in self.leaders}

    def invalidate_leaders(self) -> None:
        """Drop the cache (catalogue refreshed, or play counts changed the picker order)."""
        self._leaders = None

    # ---- navigation ---------------------------------------------------
    def navigate(self, route: str) -> None:
        self.page.navigate(route)

    # ---- sharing ------------------------------------------------------
    async def share_file(self, render: Callable[[], Path], *, title: str, mime_type: str = "image/png") -> None:
        """Render off the UI thread, then share (or save). Every failure is reported to the user."""
        _ = self._
        try:
            path = await asyncio.to_thread(render)
        except Exception as exc:
            _log.exception("could not render %s", title)
            self.notify(_("Could not create the image ({error})").format(error=type(exc).__name__), error=True)
            return
        try:
            outcome = await deliver(path, title=title, mime_type=mime_type)
        except Exception as exc:
            _log.exception("could not share or save %s", path.name)
            self.notify(_("Could not share or save the file ({error})").format(error=type(exc).__name__), error=True)
            return
        if outcome == Delivery.SAVED:
            self.notify(_("Saved"))
