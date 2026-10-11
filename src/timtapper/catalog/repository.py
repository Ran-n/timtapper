#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.221073
Revised: 2026/10/11 16:27:21.631004

Leader catalogue persistence: upsert from LeaderRecords, read as plain Leader values.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from catalog.optcgapi import IMAGE_URL, LeaderRecord
from core.logging import get_logger
from core.paths import ASSETS_DIR
from db import Database
from db.models import CardSet, Color, Match
from db.models import Leader as LeaderRow

_log = get_logger("catalog")
BUNDLED_LEADERS = ASSETS_DIR / "data" / "leaders.json"


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
    def image_url(self) -> str:
        return IMAGE_URL.format(code=self.code)


def to_leader(row: LeaderRow) -> Leader:
    return Leader(
        row.id, row.code, row.name, row.card_set.code if row.card_set else None, tuple(c.name for c in row.colors)
    )


def load_bundled(path: Path = BUNDLED_LEADERS) -> list[LeaderRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [LeaderRecord.from_json(item) for item in raw["leaders"]]


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

    def by_id(self) -> dict[int, Leader]:
        return {leader.id: leader for leader in self.all()}

    def count(self) -> int:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(LeaderRow)) or 0


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
