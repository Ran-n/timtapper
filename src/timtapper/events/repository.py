#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.014644
Revised: 2026/10/11 16:27:22.566460

Events and their rounds: CRUD over the local DB, exposed as plain values.
"""

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from core.logging import get_logger
from db import Database
from db.models import EVENT_TYPES, RESULTS, EventType
from db.models import Event as EventRow
from db.models import Leader as LeaderRow
from db.models import Match as MatchRow

_log = get_logger("events")

_EVENT_FIELDS = {"name", "event_type", "date", "leader_id", "notes"}
_MATCH_FIELDS = {"opponent_leader_id", "result", "went_first", "won_die_roll", "top_cut", "notes"}


class EventError(ValueError):
    """Rejected input or a missing event/round."""


@dataclass(frozen=True, slots=True)
class Round:
    id: int
    round_no: int
    opponent_leader_id: int
    result: str | None = None
    went_first: bool | None = None
    won_die_roll: bool | None = None
    top_cut: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    name: str
    event_type: str
    date: dt.date
    leader_id: int | None
    notes: str = ""
    rounds: tuple[Round, ...] = field(default_factory=tuple)


def _to_round(row: MatchRow) -> Round:
    return Round(
        row.id,
        row.round_no,
        row.opponent_leader_id,
        row.result,
        row.went_first,
        row.won_die_roll,
        row.top_cut,
        row.notes,
    )


def _to_event(row: EventRow) -> Event:
    return Event(
        row.id,
        row.name,
        row.event_type.key,
        row.date,
        row.leader_id,
        row.notes,
        tuple(_to_round(m) for m in row.matches),
    )


def _validate_event_fields(s: Session, fields: dict) -> dict:
    unknown = set(fields) - _EVENT_FIELDS
    if unknown:
        raise EventError(f"unknown event fields: {sorted(unknown)}")
    out = dict(fields)
    if "name" in out:
        out["name"] = (out["name"] or "").strip()
        if not out["name"]:
            raise EventError("event name is required")
    if "event_type" in out:
        key = out.pop("event_type")
        if key not in EVENT_TYPES:
            raise EventError(f"unknown event type {key!r}")
        out["event_type_id"] = s.scalar(select(EventType.id).where(EventType.key == key))
    if "date" in out and not isinstance(out["date"], dt.date):
        raise EventError("date must be a date")
    if out.get("leader_id") is not None and s.get(LeaderRow, out["leader_id"]) is None:
        raise EventError(f"unknown leader id {out['leader_id']}")
    return out


def _validate_match_fields(s: Session, fields: dict) -> dict:
    unknown = set(fields) - _MATCH_FIELDS
    if unknown:
        raise EventError(f"unknown round fields: {sorted(unknown)}")
    if "result" in fields and fields["result"] not in (*RESULTS, None):
        raise EventError(f"result must be one of {RESULTS} or None")
    if "opponent_leader_id" in fields and s.get(LeaderRow, fields["opponent_leader_id"]) is None:
        raise EventError(f"unknown leader id {fields['opponent_leader_id']}")
    return fields


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _load(s: Session, event_id: int) -> EventRow:
        row = s.get(EventRow, event_id, options=[selectinload(EventRow.matches), selectinload(EventRow.event_type)])
        if row is None:
            raise EventError(f"event {event_id} not found")
        return row

    def list(self) -> list[Event]:
        """All events, newest first."""
        with self.db.session() as s:
            rows = s.scalars(
                select(EventRow)
                .options(selectinload(EventRow.matches), selectinload(EventRow.event_type))
                .order_by(EventRow.date.desc(), EventRow.id.desc())
            )
            return [_to_event(r) for r in rows]

    def get(self, event_id: int) -> Event:
        with self.db.session() as s:
            return _to_event(self._load(s, event_id))

    def create(self, name: str, event_type: str, date: dt.date, leader_id: int | None = None) -> Event:
        with self.db.session() as s:
            fields = _validate_event_fields(
                s, {"name": name, "event_type": event_type, "date": date, "leader_id": leader_id}
            )
            row = EventRow(**fields)
            s.add(row)
            s.flush()
            event_id = row.id
        _log.info("event %d created (%s, %s)", event_id, event_type, date)
        return self.get(event_id)

    def update(self, event_id: int, **fields) -> Event:
        with self.db.session() as s:
            row = self._load(s, event_id)
            for key, value in _validate_event_fields(s, fields).items():
                setattr(row, key, value)
        _log.info("event %d updated: %s", event_id, sorted(fields))
        return self.get(event_id)

    def delete(self, event_id: int) -> None:
        with self.db.session() as s:
            s.delete(self._load(s, event_id))
        _log.info("event %d deleted", event_id)

    def add_round(self, event_id: int, opponent_leader_id: int, top_cut: bool = False) -> Round:
        with self.db.session() as s:
            self._load(s, event_id)
            _validate_match_fields(s, {"opponent_leader_id": opponent_leader_id})
            last = s.scalar(select(func.max(MatchRow.round_no)).where(MatchRow.event_id == event_id)) or 0
            row = MatchRow(event_id=event_id, round_no=last + 1, opponent_leader_id=opponent_leader_id, top_cut=top_cut)
            s.add(row)
            s.flush()
            result = _to_round(row)
        _log.info("event %d: round %d added", event_id, result.round_no)
        return result

    def update_round(self, round_id: int, **fields) -> Round:
        with self.db.session() as s:
            row = s.get(MatchRow, round_id)
            if row is None:
                raise EventError(f"round {round_id} not found")
            for key, value in _validate_match_fields(s, fields).items():
                setattr(row, key, value)
            s.flush()
            result = _to_round(row)
        _log.info("round %d updated: %s", round_id, sorted(fields))
        return result

    def delete_round(self, round_id: int) -> None:
        """Delete a round and renumber the later ones so rounds stay 1..n."""
        with self.db.session() as s:
            row = s.get(MatchRow, round_id)
            if row is None:
                raise EventError(f"round {round_id} not found")
            event_id, removed_no = row.event_id, row.round_no
            s.delete(row)
            s.flush()
            later = s.scalars(
                select(MatchRow)
                .where(MatchRow.event_id == event_id, MatchRow.round_no > removed_no)
                .order_by(MatchRow.round_no)
            )
            for m in later:
                m.round_no -= 1
                s.flush()
        _log.info("round %d deleted from event %d", round_id, event_id)

    def last_used_leader_id(self) -> int | None:
        """Own leader of the most recent event — the default for a new one."""
        with self.db.session() as s:
            return s.scalar(
                select(EventRow.leader_id)
                .where(EventRow.leader_id.is_not(None))
                .order_by(EventRow.date.desc(), EventRow.id.desc())
                .limit(1)
            )
