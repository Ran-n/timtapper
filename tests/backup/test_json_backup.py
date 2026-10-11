#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.944166
Revised: 2026/10/11 16:27:24.426791
"""

import datetime as dt
import json
from dataclasses import astuple

import pytest

from backup.json_backup import FORMAT, VERSION, BackupError, export_backup, import_backup, parse_backup


def comparable(evs):
    """Everything but database ids, which differ after a restore."""
    return [(e.name, e.event_type, e.date, e.leader_id, e.notes, [astuple(r)[1:] for r in e.rounds]) for e in evs]


def dump(events, leaders):
    return export_backup(events.list(), {ld.id: ld for ld in leaders.all()})


def test_roundtrip_restores_everything(events, leaders, sample_event):
    events.update(sample_event.id, notes="note ✓")
    events.update_round(sample_event.rounds[0].id, top_cut=True, notes="r1")
    before = events.list()
    data = dump(events, leaders)
    events.create("to be replaced", "online", dt.date(2026, 1, 1))

    assert import_backup(events.db, data) == 1
    after = events.list()
    assert comparable(after) == comparable(before)


def test_export_uses_codes_not_ids(events, leaders, sample_event):
    payload = json.loads(dump(events, leaders))
    assert payload["format"] == FORMAT and payload["version"] == VERSION
    first = payload["events"][0]
    by_id = {ld.id: ld for ld in leaders.all()}
    assert first["leader"] == by_id[sample_event.leader_id].code
    assert first["rounds"][0]["opponent"] == by_id[sample_event.rounds[0].opponent_leader_id].code


def test_import_creates_placeholders_for_unknown_leaders(events, leaders):
    data = json.dumps({
        "format": FORMAT,
        "version": VERSION,
        "events": [
            {
                "name": "Future",
                "event_type": "locals",
                "date": "2027-01-01",
                "leader": "OP99-001",
                "rounds": [{"opponent": "OP99-002", "result": "W"}],
            }
        ],
    }).encode()
    assert import_backup(events.db, data) == 1
    codes = {ld.code for ld in leaders.all()}
    assert {"OP99-001", "OP99-002"} <= codes


def valid_event(**over):
    return {"name": "x", "event_type": "locals", "date": "2026-01-01", "rounds": []} | over


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"\xff\xfe", "not a JSON file"),
        (b"{nope", "not a JSON file"),
        (json.dumps([1, 2]).encode(), "not a timtapper backup"),
        (json.dumps({"format": "other"}).encode(), "not a timtapper backup"),
        (json.dumps({"format": FORMAT, "version": 99}).encode(), "unsupported backup version"),
        (json.dumps({"format": FORMAT, "version": VERSION, "events": {}}).encode(), "expected a list"),
    ],
)
def test_parse_rejects_bad_files(payload, message):
    with pytest.raises(BackupError, match=message):
        parse_backup(payload)


@pytest.mark.parametrize(
    ("event", "message"),
    [
        ("nope", "expected an object"),
        (valid_event(event_type="worlds"), "unknown event type"),
        (valid_event(date="yesterday"), "invalid date"),
        (valid_event(date=None), "invalid date"),
        (valid_event(name=""), "name"),
        (valid_event(rounds="x"), "rounds must be a list"),
        (valid_event(rounds=["x"]), "expected an object"),
        (valid_event(rounds=[{"opponent": "OP01-001", "result": "X"}]), "invalid result"),
        (valid_event(rounds=[{"result": "W"}]), "opponent"),
        (valid_event(rounds=[{"opponent": "OP01-001", "went_first": "yes"}]), "true/false/null"),
        (valid_event(notes=3), "notes"),
    ],
)
def test_parse_rejects_bad_events(event, message):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [event]}).encode()
    with pytest.raises(BackupError, match=message):
        parse_backup(data)


def test_invalid_backup_leaves_data_untouched(events, sample_event):
    bad = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(), "broken"]}).encode()
    with pytest.raises(BackupError):
        import_backup(events.db, bad)
    assert [e.id for e in events.list()] == [sample_event.id]


def test_empty_backup_clears_events(events, sample_event):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": []}).encode()
    assert import_backup(events.db, data) == 0
    assert events.list() == []
