#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.770833
Revised: 2026/10/11 16:27:23.411314

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
from ui.theme import apply_theme
from ui.widgets import make_notifier

_log = get_logger("ui")

PREF_LANG = "timtapper.lang"
PREF_THEME = "timtapper.theme"


class AppContext:
    def __init__(self, page: ft.Page, db: Database) -> None:
        self.page = page
        self.db = db
        self.leader_repo = LeaderRepository(db)
        self.events = EventRepository(db)
        self.theme_mode = "system"
        self.notify = make_notifier(page)
        self._leaders: list[Leader] | None = None
        self.on_language_change: Callable[[], None] | None = None

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
            self.theme_mode = await prefs.get(PREF_THEME) or "system"
        except Exception:
            _log.warning("could not read saved preferences — using defaults", exc_info=True)
        apply_theme(self.page, self.theme_mode)

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
        if self.on_language_change:
            self.on_language_change()

    async def change_theme(self, mode: str) -> None:
        self.theme_mode = mode
        apply_theme(self.page, mode)
        self.page.update()
        _log.info("theme set to %s", mode)
        await self._save_pref(PREF_THEME, mode)

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
