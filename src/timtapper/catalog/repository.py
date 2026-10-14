#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.221073
Revised: 2026/10/14 07:43:51.157735

Leader catalogue persistence: upsert from LeaderRecords, read as plain Leader values; the sets' release dates,
and from them the set an event on a given day was played in.
"""

import datetime as dt
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from catalog.optcgapi import LeaderRecord
from core.logging import get_logger
from core.paths import ASSETS_DIR
from db import Database
from db.models import CardSet, Color, Match
from db.models import Leader as LeaderRow

_log = get_logger("catalog")
BUNDLED_LEADERS = ASSETS_DIR / "data" / "leaders.json"


# the names players actually call these leaders (the full ones crowd a round row)
SHORT_NAMES = {"Donquixote Doflamingo": "Doflamingo", 'Eustass"Captain"Kid': "Kid"}


@dataclass(frozen=True, slots=True)
class Leader:
    id: int
    code: str
    name: str
    set_code: str | None
    colors: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.name} · {self.code}"

    @property
    def short_name(self) -> str:
        """What players call the leader, for tight rows; the full name everywhere there's room."""
        return SHORT_NAMES.get(self.name, self.name)


def to_leader(row: LeaderRow) -> Leader:
    return Leader(
        row.id, row.code, row.name, row.card_set.code if row.card_set else None, tuple(c.name for c in row.colors)
    )


def _read_bundled(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _leaders_of(raw: dict) -> list[LeaderRecord]:
    return [LeaderRecord.from_json(item) for item in raw["leaders"]]


def _releases_of(raw: dict) -> dict[str, dt.date]:
    return {code: dt.date.fromisoformat(day) for code, day in raw.get("releases", {}).items()}


def load_bundled(path: Path = BUNDLED_LEADERS) -> list[LeaderRecord]:
    return _leaders_of(_read_bundled(path))


def load_bundled_sources(path: Path = BUNDLED_LEADERS) -> tuple[str, ...]:
    """Set/deck ids the bundled list was built from (empty for a list built before they were recorded)."""
    return tuple(_read_bundled(path).get("sources", ()))


def load_bundled_releases(path: Path = BUNDLED_LEADERS) -> dict[str, dt.date]:
    """Set code -> English release date, as bundled (empty for a list built before they were recorded)."""
    return _releases_of(_read_bundled(path))


class LeaderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, records: list[LeaderRecord]) -> tuple[int, int]:
        """Insert new leaders, update changed ones. Returns (added, updated)."""
        added = updated = 0
        with self.db.session() as s:
            colors = {c.name: c for c in s.scalars(select(Color))}
            sets = {cs.code: cs for cs in s.scalars(select(CardSet))}
            existing = {row.code: row for row in s.scalars(select(LeaderRow).options(selectinload(LeaderRow.colors)))}
            for rec in records:
                card_set = sets.get(rec.set_code)
                if card_set is None:
                    card_set = sets[rec.set_code] = CardSet(code=rec.set_code, name=rec.set_name)
                    s.add(card_set)
                elif rec.set_name and card_set.name != rec.set_name:
                    card_set.name = rec.set_name
                wanted_colors = [colors[c] for c in rec.colors if c in colors]
                row = existing.get(rec.code)
                if row is None:
                    s.add(LeaderRow(code=rec.code, name=rec.name, card_set=card_set, colors=wanted_colors))
                    added += 1
                elif (row.name, row.card_set, {c.id for c in row.colors}) != (
                    rec.name,
                    card_set,
                    {c.id for c in wanted_colors},
                ):
                    row.name, row.card_set, row.colors = rec.name, card_set, wanted_colors
                    updated += 1
        _log.info("leader catalogue synced: %d added, %d updated", added, updated)
        return added, updated

    def set_releases(self, releases: Mapping[str, dt.date]) -> int:
        """Store each set's release date, adding sets not seen yet; a set left out keeps the date it has.
        Returns how many dates changed."""
        changed = 0
        with self.db.session() as s:
            sets = {cs.code: cs for cs in s.scalars(select(CardSet))}
            for code, day in releases.items():
                card_set = sets.get(code)
                if card_set is None:
                    s.add(CardSet(code=code, release_date=day))
                elif card_set.release_date != day:
                    card_set.release_date = day
                else:
                    continue
                changed += 1
        if changed:
            _log.info("%d set release dates stored", changed)
        return changed

    def release_dates(self) -> dict[str, dt.date]:
        """Set code -> release date, for the sets that have one."""
        with self.db.session() as s:
            rows = s.execute(select(CardSet.code, CardSet.release_date).where(CardSet.release_date.is_not(None)))
            return {code: day for code, day in rows}

    def ensure(self, s: Session, code: str) -> LeaderRow:
        """Leader row for `code`, creating a bare placeholder when unknown (e.g. a backup from a newer catalogue)."""
        row = s.scalar(select(LeaderRow).where(LeaderRow.code == code))
        if row is None:
            _log.warning("unknown leader %s — adding a placeholder", code)
            row = LeaderRow(code=code, name=code)
            s.add(row)
            s.flush()
        return row

    def all(self) -> list[Leader]:
        """Every leader; most-played opponents first so the picker opens on the likely choice."""
        with self.db.session() as s:
            plays = (
                select(Match.opponent_leader_id, func.count().label("n")).group_by(Match.opponent_leader_id).subquery()
            )
            rows = s.scalars(
                select(LeaderRow)
                .outerjoin(plays, plays.c.opponent_leader_id == LeaderRow.id)
                .options(selectinload(LeaderRow.colors), selectinload(LeaderRow.card_set))
                .order_by(func.coalesce(plays.c.n, 0).desc(), LeaderRow.name, LeaderRow.code)
            )
            return [to_leader(r) for r in rows]

    def count(self) -> int:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(LeaderRow)) or 0


def install_bundled(repo: LeaderRepository, path: Path = BUNDLED_LEADERS) -> None:
    """Bring the catalogue up to the list shipped with the app: its leaders and its sets' release dates (the file
    read once: this runs on every start)."""
    raw = _read_bundled(path)
    repo.upsert(_leaders_of(raw))
    repo.set_releases(_releases_of(raw))


def search(leaders: list[Leader], query: str) -> list[Leader]:
    """Case-insensitive match on name, code or color; every word must match."""
    words = query.lower().split()
    if not words:
        return leaders
    return [
        leader
        for leader in leaders
        if all(w in f"{leader.name} {leader.code} {' '.join(leader.colors)}".lower() for w in words)
    ]


def filter_leaders(
    leaders: list[Leader], query: str, colors: frozenset[str] = frozenset(), set_code: str | None = None
) -> list[Leader]:
    """`search`, then keep leaders having every selected color (AND narrows) and, if given, that set."""
    return [
        leader
        for leader in search(leaders, query)
        if colors <= set(leader.colors) and (not set_code or leader.set_code == set_code)
    ]


# Main sets first, then extra boosters, starters, promo packs; any other prefix after those.
_SET_PREFIX_ORDER = ("OP", "EB", "ST", "PRB")


def _set_sort_key(code: str) -> tuple:
    match = re.fullmatch(r"([A-Z]+)(\d+)", code)
    if not match:
        return (2, 0, code, 0)
    prefix, number = match[1], int(match[2])
    rank = _SET_PREFIX_ORDER.index(prefix) if prefix in _SET_PREFIX_ORDER else len(_SET_PREFIX_ORDER)
    return (0 if rank < len(_SET_PREFIX_ORDER) else 1, rank, prefix, -number)


def sort_set_codes(codes: Iterable[str]) -> list[str]:
    """Distinct set codes, newest first within OP, EB, ST, PRB, other prefixes, then unparsable codes."""
    return sorted(set(codes), key=_set_sort_key)


def set_codes(leaders: Iterable[Leader]) -> list[str]:
    """The sets the leaders come from, in sort_set_codes' order."""
    return sort_set_codes(leader.set_code for leader in leaders if leader.set_code)


def is_main_set(code: str) -> bool:
    """A main booster (OP01, OP16...): the sets formats are named after."""
    return _set_sort_key(code)[:2] == (0, 0)


def set_on(day: dt.date, codes: Iterable[str], releases: Mapping[str, dt.date]) -> str | None:
    """The set an event on `day` is played in: the newest main set out by then (extra boosters, starters and promo
    packs join the format of the main set before them). With no release date known for any main set, the newest of
    `codes`; with dates known but nothing out yet, None."""
    ordered = sort_set_codes(codes)
    main = [code for code in ordered if is_main_set(code) and code in releases]
    if not main:
        return ordered[0] if ordered else None
    out = [code for code in main if releases[code] <= day]
    return max(out, key=lambda code: releases[code]) if out else None
