#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.944166
Revised: 2026/10/12 16:54:59.727898
"""

import contextlib
import dataclasses
import datetime as dt
import json
from dataclasses import astuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backup.json_backup import FORMAT, VERSION, BackupError, export_backup, import_backup, parse_backup
from catalog.repository import Leader
from db.models import EVENT_TYPES
from events.repository import Event, Round


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


# ---- properties ------------------------------------------------------------------
codes = st.from_regex(r"[A-Z]{1,4}\d{0,2}-\d{3}", fullmatch=True)
texts_ = st.text(max_size=40)
rounds_st = st.builds(
    Round,
    st.just(0),
    st.just(0),
    st.integers(1, 5),
    st.sampled_from([None, "W", "L"]),
    st.sampled_from([None, True, False]),
    st.sampled_from([None, True, False]),
    st.booleans(),
    texts_,
)
events_st = st.builds(
    Event,
    st.just(0),
    st.text(min_size=1, max_size=40).filter(lambda s: s.strip() == s and s),
    st.sampled_from(sorted(EVENT_TYPES)),
    st.dates(dt.date(2000, 1, 1), dt.date(2100, 12, 31)),
    st.one_of(st.none(), st.integers(1, 5)),
    texts_,
    st.lists(rounds_st, max_size=6).map(tuple),
)
# placement within the field when both are known
standings = st.one_of(st.none(), st.integers(1, 512)).flatmap(
    lambda players: st.tuples(
        st.one_of(st.none(), st.integers(1, players or 512)),
        st.just(players),
    )
)
events_st = st.tuples(events_st, standings).map(
    lambda pair: dataclasses.replace(pair[0], placement=pair[1][0], players=pair[1][1])
)


@pytest.mark.property
@given(st.lists(events_st, max_size=5), st.lists(codes, min_size=5, max_size=5, unique=True))
def test_property_export_then_parse_returns_what_was_exported(evs, leader_codes):
    leaders = {i + 1: Leader(i + 1, code, code, None, ()) for i, code in enumerate(leader_codes)}
    parsed = parse_backup(export_backup(evs, leaders))
    assert len(parsed) == len(evs)
    for ev, back in zip(evs, parsed, strict=True):
        assert (back["name"], back["event_type"], back["date"], back["notes"]) == (
            ev.name,
            ev.event_type,
            ev.date,
            ev.notes,
        )
        assert (back["placement"], back["players"]) == (ev.placement, ev.players)
        assert back["leader"] == (leaders[ev.leader_id].code if ev.leader_id else None)
        assert back["rounds"] == [
            {
                "opponent": leaders[r.opponent_leader_id].code,
                "result": r.result,
                "went_first": r.went_first,
                "won_die_roll": r.won_die_roll,
                "top_cut": r.top_cut,
                "notes": r.notes,
            }
            for r in ev.rounds
        ]


@pytest.mark.property
@given(st.binary(max_size=200))
def test_property_parse_never_crashes_on_garbage(data):
    """Any file the user picks either parses or raises BackupError: never anything else."""
    with contextlib.suppress(BackupError):  # the only failure allowed
        parse_backup(data)


@pytest.mark.property
@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.text(max_size=5),
        lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=8), c, max_size=3),
        max_leaves=12,
    )
)
def test_property_parse_rejects_wrong_shapes_cleanly(events_value):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [events_value]}).encode()
    with contextlib.suppress(BackupError):  # the only failure allowed
        parse_backup(data)


@pytest.mark.regression
def test_old_backups_with_draws_restore_them_as_losses():
    """v1 backups written before draws were dropped may hold "D": a draw is a loss for both players."""
    event = valid_event(rounds=[{"opponent": "OP01-001", "result": "D"}, {"opponent": "OP01-001", "result": "W"}])
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [event]}).encode()
    assert [r["result"] for r in parse_backup(data)[0]["rounds"]] == ["L", "W"]


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"placement": 0}, "placement: expected a whole number"),
        ({"players": "32"}, "players: expected a whole number"),
        ({"placement": True}, "placement: expected a whole number"),
        ({"placement": 9, "players": 8}, "past the 8 players"),
    ],
)
def test_parse_rejects_impossible_placements(over, message):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(**over)]}).encode()
    with pytest.raises(BackupError, match=message):
        parse_backup(data)


def test_v1_files_are_still_read():
    data = json.dumps({"format": FORMAT, "version": 1, "events": [valid_event()]}).encode()
    assert parse_backup(data)[0]["placement"] is None
