#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.770833
Revised: 2026/10/13 08:59:20.909037

Per-session app context handed to every screen: repositories, the cached
leader catalogue, translation, notifications, preferences and navigation.
"""

import asyncio
import datetime as dt
from collections.abc import Callable
from pathlib import Path

import flet as ft

from catalog.repository import Leader, LeaderRepository, set_codes, set_on
from core.logging import get_logger
from db import Database
from events.naming import suggest_name
from events.repository import Event, EventError, EventRepository
from i18n import DEFAULT_LANG, Translate, event_name_template, get_lang, set_lang, tr
from share.deliver import Delivery, deliver
from stats.compute import Filters
from ui.leader_updates import LeaderUpdater
from ui.theme import DEFAULT_MODE, AppTheme, Scheme, apply_theme, get_theme, is_dark
from ui.widgets import make_notifier

_log = get_logger("ui")

PREF_LANG = "timtapper.lang"
PREF_THEME = "timtapper.theme"  # mode: system/light/dark (key predates named themes)
PREF_PALETTE = "timtapper.palette"


async def saved_language() -> str:
    """The language chosen in Settings; the default when none was, or when it can't be read. Kept apart from the other
    preferences so the database failure screen, shown before there is any app, still speaks it."""
    try:
        return await ft.SharedPreferences().get(PREF_LANG) or DEFAULT_LANG
    except Exception:
        _log.warning("could not read the saved language — using the default", exc_info=True)
        return DEFAULT_LANG


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
        self._leaders_by_id: dict[int, Leader] | None = None
        self._release_dates: dict[str, dt.date] | None = None
        self.on_appearance_change: Callable[[], None] | None = None
        # the events list's search and filters, kept while you open an event and come back
        self.event_filters = Filters()
        self.event_filters_open = False
        # the event "New event" just made, as it was made: dropped if you leave it without adding anything
        self.draft: Event | None = None

    # ---- translation / preferences ------------------------------------
    @property
    def _(self) -> Translate:
        return tr(self.page)

    @property
    def lang(self) -> str:
        return get_lang(self.page)

    async def load_prefs(self) -> None:
        set_lang(self.page, await saved_language())
        try:
            prefs = ft.SharedPreferences()
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
        if self._leaders_by_id is None:
            self._leaders_by_id = {leader.id: leader for leader in self.leaders}
        return self._leaders_by_id

    @property
    def release_dates(self) -> dict[str, dt.date]:
        """Set code -> release date, for the sets that have one."""
        if self._release_dates is None:
            self._release_dates = self.leader_repo.release_dates()
        return self._release_dates

    def invalidate_leaders(self) -> None:
        """Drop the cache (catalogue refreshed, or play counts changed the picker order)."""
        self._leaders = self._leaders_by_id = self._release_dates = None

    def set_on(self, day: dt.date) -> str | None:
        """The set an event on `day` was played in, as far as the catalogue knows."""
        return set_on(day, set_codes(self.leaders), self.release_dates)

    # ---- events -------------------------------------------------------
    def suggested_name(self, event_type: str, exclude_id: int | None = None) -> str:
        """What a new event of `event_type` is called: "Local #4" after three locals."""
        return suggest_name(event_name_template(self._, event_type), self.events.names_of_type(event_type, exclude_id))

    def redate(self, event: Event, day: dt.date) -> dict:
        """The fields to save to move `event` to `day`: its set follows the date while it is still the one its old
        date gave it; a set you picked yourself (or "Not noted") stays."""
        fields: dict = {"date": day}
        if day != event.date and event.set_code == self.set_on(event.date):
            fields["set_code"] = self.set_on(day)
        return fields

    def new_event(self, event_type: str, date: dt.date, leader_id: int | None) -> Event:
        """Create an event under its suggested name; it stays a draft until something is added to it."""
        event = self.events.create(self.suggested_name(event_type), event_type, date, leader_id)
        played_in = self.set_on(date)
        if played_in:  # played in the set out on its date unless you say otherwise
            event = self.events.update(event.id, set_code=played_in)
        self.draft = event
        return self.draft

    def drop_untouched_draft(self) -> None:
        """Leaving the new event's screen: if nothing was changed or added, it was never wanted — delete it."""
        draft, self.draft = self.draft, None
        if draft is None:
            return
        try:
            current = self.events.get(draft.id)
        except EventError:
            _log.info("draft event %d is already gone", draft.id)
            return
        if current == draft:
            self.events.delete(draft.id)
            _log.info("draft event %d left untouched — dropped", draft.id)

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
            # "file": a share card or a backup
            self.notify(_("Could not create the file ({error})").format(error=type(exc).__name__), error=True)
            return
        try:
            outcome = await deliver(path, title=title, mime_type=mime_type)
        except Exception as exc:
            _log.exception("could not share or save %s", path.name)
            self.notify(_("Could not share or save the file ({error})").format(error=type(exc).__name__), error=True)
            return
        if outcome == Delivery.SAVED:
            self.notify(_("Saved"))
