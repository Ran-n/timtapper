#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:20:11.971755
Revised: 2026/10/13 07:39:25.170476

Keeps the leader catalogue current. The Settings button calls run(); at
startup run_if_due() checks in the background, at most once a day, whether
optcgapi.com lists a set this install hasn't synced yet, and only then
downloads the multi-MB card lists. Background failures are logged, never
shown: the user didn't ask for this update, and the next start retries.
"""

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

import flet as ft

from catalog.optcgapi import CatalogError, fetch_sources
from catalog.repository import load_bundled_sources
from catalog.sync import SyncResult, is_due, new_sources, sync_leaders
from core.logging import get_logger

if TYPE_CHECKING:
    from ui.context import AppContext

_log = get_logger("ui.leader_updates")

PREF_CHECKED = "timtapper.leaders_checked"  # ISO UTC time of the last successful check or sync
PREF_SOURCES = "timtapper.leader_sources"  # comma-joined set ids covered by the last sync


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class LeaderUpdater:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def run(self) -> SyncResult:
        """Full update (leaders, portraits, set ids). Raises CatalogError when offline."""
        async with self._lock:
            result = await asyncio.to_thread(sync_leaders, self.ctx.leader_repo)
            self.ctx.invalidate_leaders()
            await self._remember(result.sources)
            return result

    async def run_if_due(self) -> None:
        """Background check; updates only when a new set is out. Never raises, never shows errors."""
        checked, stored = await self._recall()
        if not is_due(checked, _now()) or self.busy:
            return
        try:
            remote = await asyncio.to_thread(fetch_sources)
        except CatalogError as exc:
            _log.warning("background leader check skipped: %s", exc)
            return
        fresh = new_sources({*stored, *load_bundled_sources()}, remote)
        if not fresh:
            _log.info("leader catalogue is current (%d sets)", len(remote))
            await self._remember(None)
            return
        _log.info("new sets out (%s) — updating leaders", ", ".join(fresh))
        try:
            result = await self.run()
        except CatalogError as exc:
            _log.warning("background leader update failed: %s", exc)
            return
        except Exception:  # a background task has no caller to raise to: log it, the next start retries
            _log.exception("background leader update failed")
            return
        if result.failed_portraits:
            _log.warning("background leader update: %d portraits missing", result.failed_portraits)
        if result.added:
            self.ctx.notify(self.ctx._("{n} new leaders added").format(n=result.added))

    # ---- persisted state ----------------------------------------------
    async def _recall(self) -> tuple[dt.datetime | None, tuple[str, ...]]:
        try:
            prefs = ft.SharedPreferences()
            raw_checked = await prefs.get(PREF_CHECKED)
            raw_sources = await prefs.get(PREF_SOURCES)
        except Exception:
            _log.warning("could not read the leader update state — checking now", exc_info=True)
            return None, ()
        checked = None
        if raw_checked:
            try:
                checked = dt.datetime.fromisoformat(raw_checked)
            except ValueError:
                _log.warning("ignoring malformed %s=%r", PREF_CHECKED, raw_checked)
            else:
                if checked.tzinfo is None:  # stored without a zone: it was UTC, and comparing it to now would raise
                    checked = checked.replace(tzinfo=dt.UTC)
        return checked, tuple(s for s in (raw_sources or "").split(",") if s)

    async def _remember(self, sources: tuple[str, ...] | None) -> None:
        try:
            prefs = ft.SharedPreferences()
            await prefs.set(PREF_CHECKED, _now().isoformat())
            if sources is not None:
                await prefs.set(PREF_SOURCES, ",".join(sources))
        except Exception:
            _log.warning("could not save the leader update state — the next start checks again", exc_info=True)
