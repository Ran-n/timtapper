#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 17:20:11.865939
Revised: 2026/10/11 17:21:28.933130

Bring the local leader catalogue up to date with optcgapi.com: leaders,
their portraits, and the set ids the catalogue now covers. The set ids let
the app notice a new release with a few-KB request instead of re-downloading
every card (see ui/leader_updates.py).
"""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from catalog import portraits
from catalog.optcgapi import CatalogError, fetch_leaders, fetch_sources
from catalog.repository import LeaderRepository
from core.logging import get_logger

_log = get_logger("catalog.sync")

CHECK_INTERVAL = dt.timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SyncResult:
    added: int
    updated: int
    failed_portraits: int
    sources: tuple[str, ...] | None  # None: the set list could not be fetched this time


def sync_leaders(repo: LeaderRepository) -> SyncResult:
    """Download leaders + missing portraits and store them. Raises CatalogError when the leaders can't be fetched."""
    records = fetch_leaders()
    added, updated = repo.upsert(records)
    _saved, failed = portraits.download_missing([r.code for r in records])
    try:
        sources = fetch_sources()
    except CatalogError as exc:
        _log.warning("leaders synced but the set list could not be fetched: %s", exc)
        sources = None
    return SyncResult(added, updated, failed, sources)


def new_sources(known: Iterable[str], remote: Iterable[str]) -> list[str]:
    """Set ids released since the catalogue was last synced."""
    return sorted(set(remote) - set(known))


def is_due(last_checked: dt.datetime | None, now: dt.datetime, interval: dt.timedelta = CHECK_INTERVAL) -> bool:
    return last_checked is None or now - last_checked >= interval
