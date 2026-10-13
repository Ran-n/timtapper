#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:20:12.113794
Revised: 2026/10/12 22:20:11.922861
"""

import datetime as dt

import pytest

from catalog import sync as sync_mod
from catalog.optcgapi import CatalogError, LeaderRecord
from catalog.sync import CHECK_INTERVAL, SyncResult, is_due, new_sources, sync_leaders

NEW = LeaderRecord("OP99-001", "Newbie", "OP99", "Future", ("Red",))


@pytest.fixture
def online(monkeypatch):
    asked = []
    monkeypatch.setattr(sync_mod, "fetch_leaders", lambda: [NEW])
    monkeypatch.setattr(sync_mod, "fetch_sources", lambda: ("OP-99",))
    monkeypatch.setattr(sync_mod.portraits, "download_missing", lambda codes: asked.append(codes) or (0, 1))
    return asked


def test_sync_stores_leaders_portraits_and_sources(leaders, online):
    result = sync_leaders(leaders)
    assert result == SyncResult(added=1, updated=0, failed_portraits=1, sources=("OP-99",))
    assert any(ld.code == "OP99-001" for ld in leaders.all())
    assert online == [["OP99-001"]]


def test_sync_survives_set_list_failure(leaders, online, monkeypatch, caplog):
    def broken():
        raise CatalogError("allSets down")

    monkeypatch.setattr(sync_mod, "fetch_sources", broken)
    result = sync_leaders(leaders)
    assert result.added == 1 and result.sources is None
    assert "set list could not be fetched" in caplog.text


def test_sync_leader_failure_propagates_and_stores_nothing(leaders, monkeypatch):
    def offline():
        raise CatalogError("offline")

    monkeypatch.setattr(sync_mod, "fetch_leaders", offline)
    n = leaders.count()
    with pytest.raises(CatalogError):
        sync_leaders(leaders)
    assert leaders.count() == n


@pytest.mark.parametrize(
    ("known", "remote", "fresh"),
    [
        ((), ("OP-01",), ["OP-01"]),
        (("OP-01",), ("OP-01",), []),
        (("OP-01", "OP-02"), ("OP-01",), []),  # a set the API dropped is not a new release
        (("OP-01",), ("OP-03", "OP-01", "EB-04"), ["EB-04", "OP-03"]),
    ],
)
def test_new_sources(known, remote, fresh):
    assert new_sources(known, remote) == fresh


NOW = dt.datetime(2026, 10, 11, 12, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("last", "due"),
    [
        (None, True),
        (NOW, False),
        (NOW - CHECK_INTERVAL + dt.timedelta(minutes=1), False),
        (NOW - CHECK_INTERVAL, True),
    ],
)
def test_is_due(last, due):
    assert is_due(last, NOW) is due


@pytest.mark.live
def test_live_full_sync_into_a_real_database(leaders):
    """What "Update leaders" does, end to end: every leader stored, every new one's picture downloaded."""
    result = sync_leaders(leaders)
    assert result.sources is not None and "OP-01" in result.sources
    assert result.failed_portraits == 0
    assert leaders.count() >= 100
