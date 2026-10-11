#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:20:12.217340
Revised: 2026/10/11 17:20:12.217340
"""

import asyncio
import datetime as dt
import time

import pytest

from catalog import sync as sync_mod
from catalog.optcgapi import CatalogError, LeaderRecord
from catalog.repository import load_bundled_sources
from ui import leader_updates as updates_mod
from ui.leader_updates import PREF_CHECKED, PREF_SOURCES

NEW = LeaderRecord("OP99-001", "Newbie", "OP99", "Future", ("Red",))


@pytest.fixture
def api(monkeypatch):
    """Fake optcgapi: `api["sources"]` is what the set list returns (or raises); calls are counted."""
    state = {"sources": load_bundled_sources(), "set_checks": 0, "leader_downloads": 0}

    def sources():
        state["set_checks"] += 1
        if isinstance(state["sources"], Exception):
            raise state["sources"]
        return state["sources"]

    def leaders():
        state["leader_downloads"] += 1
        return [NEW]

    monkeypatch.setattr(updates_mod, "fetch_sources", sources)
    monkeypatch.setattr(sync_mod, "fetch_sources", sources)
    monkeypatch.setattr(sync_mod, "fetch_leaders", leaders)
    monkeypatch.setattr(sync_mod.portraits, "download_missing", lambda codes: (len(codes), 0))
    return state


def with_new_set(api, set_id="OP-99"):
    api["sources"] = (*load_bundled_sources(), set_id)


async def test_current_catalogue_only_records_the_check(ctx, api, prefs, page):
    await ctx.leader_updates.run_if_due()
    assert api["set_checks"] == 1 and api["leader_downloads"] == 0
    assert PREF_CHECKED in prefs and PREF_SOURCES not in prefs
    assert page.dialogs == []


async def test_new_set_triggers_update_and_notifies(ctx, api, prefs, page):
    with_new_set(api)
    await ctx.leader_updates.run_if_due()
    assert api["leader_downloads"] == 1
    assert any(ld.code == "OP99-001" for ld in ctx.leaders)
    assert "OP-99" in prefs[PREF_SOURCES].split(",")
    assert page.dialogs[-1].content.value == "1 new leaders added"
    assert page.dialogs[-1].data == "info"


async def test_new_set_without_new_leaders_stays_quiet(ctx, api, prefs, page, monkeypatch):
    with_new_set(api, "PRB-09")
    monkeypatch.setattr(sync_mod.LeaderRepository, "upsert", lambda self, records: (0, 0))
    await ctx.leader_updates.run_if_due()
    assert "PRB-09" in prefs[PREF_SOURCES].split(",")
    assert page.dialogs == []


async def test_synced_sets_are_not_synced_again(ctx, api, prefs):
    with_new_set(api)
    await ctx.leader_updates.run_if_due()
    prefs[PREF_CHECKED] = "2000-01-01T00:00:00+00:00"  # make the next start due again
    await ctx.leader_updates.run_if_due()
    assert api["set_checks"] == 3  # first check, the sync's own set list, second check
    assert api["leader_downloads"] == 1


async def test_stored_sources_count_as_known(ctx, api, prefs):
    with_new_set(api)
    prefs[PREF_SOURCES] = "OP-99"
    await ctx.leader_updates.run_if_due()
    assert api["leader_downloads"] == 0


async def test_checked_recently_does_nothing(ctx, api, prefs):
    prefs[PREF_CHECKED] = dt.datetime.now(dt.UTC).isoformat()
    await ctx.leader_updates.run_if_due()
    assert api["set_checks"] == 0


async def test_offline_check_is_logged_not_shown(ctx, api, prefs, page, caplog):
    api["sources"] = CatalogError("offline")
    await ctx.leader_updates.run_if_due()
    assert "background leader check skipped: offline" in caplog.text
    assert prefs == {} and page.dialogs == []


async def test_failed_background_update_is_logged_not_shown(ctx, api, prefs, page, monkeypatch, caplog):
    with_new_set(api)

    def offline():
        raise CatalogError("timeout")

    monkeypatch.setattr(sync_mod, "fetch_leaders", offline)
    await ctx.leader_updates.run_if_due()
    assert "background leader update failed: timeout" in caplog.text
    assert prefs == {} and page.dialogs == []


async def test_missing_portraits_are_logged(ctx, api, prefs, monkeypatch, caplog):
    with_new_set(api)
    monkeypatch.setattr(sync_mod.portraits, "download_missing", lambda codes: (0, len(codes)))
    await ctx.leader_updates.run_if_due()
    assert "1 portraits missing" in caplog.text


async def test_malformed_check_time_is_ignored(ctx, api, prefs, caplog):
    prefs[PREF_CHECKED] = "yesterday"
    await ctx.leader_updates.run_if_due()
    assert api["set_checks"] == 1
    assert "ignoring malformed" in caplog.text


async def test_unusable_prefs_still_check_and_log(ctx, api, monkeypatch, caplog):
    class Broken:
        async def get(self, key):
            raise RuntimeError("no storage")

        async def set(self, key, value):
            raise RuntimeError("read-only")

    monkeypatch.setattr(updates_mod.ft, "SharedPreferences", Broken)
    await ctx.leader_updates.run_if_due()
    assert api["set_checks"] == 1
    assert "could not read the leader update state" in caplog.text
    assert "could not save the leader update state" in caplog.text


async def test_skips_while_an_update_runs(ctx, api, prefs):
    updater = ctx.leader_updates
    async with updater._lock:
        assert updater.busy
        await updater.run_if_due()
    assert api["set_checks"] == 0


async def test_updates_never_overlap(ctx, prefs, monkeypatch):
    running, peaks = [0], []

    def slow_sync(repo):
        running[0] += 1
        peaks.append(running[0])
        time.sleep(0.05)
        running[0] -= 1
        return sync_mod.SyncResult(0, 0, 0, ("OP-01",))

    monkeypatch.setattr(updates_mod, "sync_leaders", slow_sync)
    await asyncio.gather(ctx.leader_updates.run(), ctx.leader_updates.run())
    assert peaks == [1, 1]
    assert prefs[PREF_SOURCES] == "OP-01"
