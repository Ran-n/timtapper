#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:40.999702
Revised: 2026/10/11 16:27:21.377210

Backup: all events and rounds as one JSON file. Leaders are referenced by
card code (not local DB id), so a backup restores on any install. Restoring
replaces every event in a single transaction, and only after the whole file
has been validated — a bad file never leaves the DB half-imported.
"""

import datetime as dt
import json

from sqlalchemy import delete, select

from catalog.repository import Leader, LeaderRepository
from core.logging import get_logger
from db import Database
from db.models import EVENT_TYPES, RESULTS, EventType
from db.models import Event as EventRow
from db.models import Match as MatchRow
from events.repository import Event

_log = get_logger("backup")

FORMAT = "timtapper-backup"
VERSION = 1


class BackupError(ValueError):
    """The file is not a valid timtapper backup."""


def export_backup(events: list[Event], leaders: dict[int, Leader]) -> bytes:
    def code(leader_id: int | None) -> str | None:
        return leaders[leader_id].code if leader_id is not None else None

    payload = {
        "format": FORMAT,
        "version": VERSION,
        "exported": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "events": [
            {
                "name": ev.name,
                "event_type": ev.event_type,
                "date": ev.date.isoformat(),
                "leader": code(ev.leader_id),
                "notes": ev.notes,
                "rounds": [
                    {
                        "opponent": code(r.opponent_leader_id),
                        "result": r.result,
                        "went_first": r.went_first,
                        "won_die_roll": r.won_die_roll,
                        "top_cut": r.top_cut,
                        "notes": r.notes,
                    }
                    for r in ev.rounds
                ],
            }
            for ev in events
        ],
    }
    _log.info("exported %d events", len(events))
    return json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")


def _opt_bool(value, where: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise BackupError(f"{where}: expected true/false/null, got {value!r}")


def _str(value, where: str, *, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise BackupError(f"{where}: expected text, got {value!r}")
    return value


def parse_backup(data: bytes) -> list[dict]:
    """Validate a backup file and return its events. Raises BackupError."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError(f"not a JSON file: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise BackupError("not a timtapper backup")
    if payload.get("version") != VERSION:
        raise BackupError(f"unsupported backup version {payload.get('version')!r}")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise BackupError("events: expected a list")
    events = []
    for i, ev in enumerate(raw_events, start=1):
        where = f"event {i}"
        if not isinstance(ev, dict):
            raise BackupError(f"{where}: expected an object")
        if ev.get("event_type") not in EVENT_TYPES:
            raise BackupError(f"{where}: unknown event type {ev.get('event_type')!r}")
        try:
            date = dt.date.fromisoformat(ev.get("date") or "")
        except (TypeError, ValueError) as exc:
            raise BackupError(f"{where}: invalid date {ev.get('date')!r}") from exc
        rounds = ev.get("rounds") or []
        if not isinstance(rounds, list):
            raise BackupError(f"{where}: rounds must be a list")
        parsed_rounds = []
        for j, r in enumerate(rounds, start=1):
            rwhere = f"{where} round {j}"
            if not isinstance(r, dict):
                raise BackupError(f"{rwhere}: expected an object")
            if r.get("result") not in (*RESULTS, None):
                raise BackupError(f"{rwhere}: invalid result {r.get('result')!r}")
            parsed_rounds.append({
                "opponent": _str(r.get("opponent"), f"{rwhere} opponent", required=True),
                "result": r.get("result"),
                "went_first": _opt_bool(r.get("went_first"), rwhere),
                "won_die_roll": _opt_bool(r.get("won_die_roll"), rwhere),
                "top_cut": bool(_opt_bool(r.get("top_cut"), rwhere)),
                "notes": _str(r.get("notes"), f"{rwhere} notes"),
            })
        leader = ev.get("leader")
        events.append({
            "name": _str(ev.get("name"), f"{where} name", required=True).strip(),
            "event_type": ev["event_type"],
            "date": date,
            "leader": _str(leader, f"{where} leader") or None,
            "notes": _str(ev.get("notes"), f"{where} notes"),
            "rounds": parsed_rounds,
        })
    return events


def import_backup(db: Database, data: bytes) -> int:
    """Replace all events with the backup's. Returns the number of events restored."""
    events = parse_backup(data)
    leaders = LeaderRepository(db)
    with db.session() as s:
        type_ids = {t.key: t.id for t in s.scalars(select(EventType))}
        s.execute(delete(MatchRow))
        s.execute(delete(EventRow))
        for ev in events:
            row = EventRow(
                name=ev["name"],
                event_type_id=type_ids[ev["event_type"]],
                date=ev["date"],
                leader_id=leaders.ensure(s, ev["leader"]).id if ev["leader"] else None,
                notes=ev["notes"],
            )
            s.add(row)
            s.flush()
            for no, r in enumerate(ev["rounds"], start=1):
                s.add(
                    MatchRow(
                        event_id=row.id,
                        round_no=no,
                        opponent_leader_id=leaders.ensure(s, r["opponent"]).id,
                        result=r["result"],
                        went_first=r["went_first"],
                        won_die_roll=r["won_die_roll"],
                        top_cut=r["top_cut"],
                        notes=r["notes"],
                    )
                )
    _log.info("restored %d events from backup", len(events))
    return len(events)
