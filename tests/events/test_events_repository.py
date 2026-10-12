#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.326929
Revised: 2026/10/12 16:55:00.313313
"""

import datetime as dt

import pytest

from events.repository import EventError


def test_create_and_get(events, leader_ids):
    ev = events.create("  Regionals  ", "regional", dt.date(2026, 9, 1), leader_ids[0])
    assert ev.name == "Regionals"
    assert ev.event_type == "regional"
    assert ev.leader_id == leader_ids[0]
    assert ev.rounds == ()
    assert events.get(ev.id) == ev


def test_create_without_leader(events):
    assert events.create("Test", "testing", dt.date(2026, 9, 1)).leader_id is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"name": "   "}, "name is required"),
        ({"event_type": "worlds"}, "unknown event type"),
        ({"leader_id": 999_999}, "unknown leader"),
        ({"date": "2026-01-01"}, "date must be a date"),
    ],
)
def test_create_rejects_bad_input(events, kwargs, message):
    args = {"name": "x", "event_type": "locals", "date": dt.date(2026, 1, 1)} | kwargs
    with pytest.raises(EventError, match=message):
        events.create(**args)


def test_list_is_newest_first(events):
    old = events.create("old", "locals", dt.date(2026, 1, 1))
    new = events.create("new", "locals", dt.date(2026, 6, 1))
    same_day_later = events.create("later", "locals", dt.date(2026, 6, 1))
    assert [e.id for e in events.list()] == [same_day_later.id, new.id, old.id]


def test_update_fields(events, sample_event, leader_ids):
    ev = events.update(
        sample_event.id, name="Renamed", event_type="national", date=dt.date(2026, 2, 2), leader_id=leader_ids[2]
    )
    assert (ev.name, ev.event_type, ev.date, ev.leader_id) == (
        "Renamed",
        "national",
        dt.date(2026, 2, 2),
        leader_ids[2],
    )
    assert events.update(ev.id, notes="good run").notes == "good run"
    assert events.update(ev.id, leader_id=None).leader_id is None


def test_update_rejects_unknown_field_and_missing_event(events, sample_event):
    with pytest.raises(EventError, match="unknown event fields"):
        events.update(sample_event.id, colour="red")
    with pytest.raises(EventError, match="not found"):
        events.update(999_999, name="x")
    with pytest.raises(EventError, match="not found"):
        events.get(999_999)


def test_delete_cascades_rounds(events, sample_event, seeded_db):
    from sqlalchemy import func, select

    from db.models import Match

    events.delete(sample_event.id)
    with pytest.raises(EventError):
        events.get(sample_event.id)
    with seeded_db.session() as s:
        assert s.scalar(select(func.count()).select_from(Match)) == 0
    with pytest.raises(EventError):
        events.delete(sample_event.id)


def test_rounds_are_numbered_and_editable(events, sample_event, leader_ids):
    assert [r.round_no for r in sample_event.rounds] == [1, 2, 3, 4]
    pending = sample_event.rounds[3]
    assert pending.result is None
    updated = events.update_round(pending.id, result="L", top_cut=True, notes="time", opponent_leader_id=leader_ids[4])
    assert (updated.result, updated.top_cut, updated.notes, updated.opponent_leader_id) == (
        "L",
        True,
        "time",
        leader_ids[4],
    )
    assert events.update_round(pending.id, result=None).result is None


def test_add_round_inherits_requested_top_cut(events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[0], top_cut=True)
    assert r.round_no == 5
    assert r.top_cut is True


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"result": "X"}, "result must be"),
        ({"opponent_leader_id": 999_999}, "unknown leader"),
        ({"round_no": 7}, "unknown round fields"),
    ],
)
def test_update_round_rejects_bad_input(events, sample_event, fields, message):
    with pytest.raises(EventError, match=message):
        events.update_round(sample_event.rounds[0].id, **fields)


def test_round_errors_for_missing_ids(events, leader_ids):
    with pytest.raises(EventError):
        events.add_round(999_999, leader_ids[0])
    with pytest.raises(EventError):
        events.update_round(999_999, result="W")
    with pytest.raises(EventError):
        events.delete_round(999_999)


def test_delete_round_renumbers(events, sample_event):
    events.delete_round(sample_event.rounds[1].id)
    ev = events.get(sample_event.id)
    assert [r.round_no for r in ev.rounds] == [1, 2, 3]
    assert [r.id for r in ev.rounds] == [sample_event.rounds[i].id for i in (0, 2, 3)]
    events.delete_round(ev.rounds[0].id)
    assert [r.round_no for r in events.get(ev.id).rounds] == [1, 2]


def test_last_used_leader(events, leader_ids):
    assert events.last_used_leader_id() is None
    events.create("a", "locals", dt.date(2026, 1, 1), leader_ids[1])
    events.create("b", "locals", dt.date(2026, 3, 1), leader_ids[2])
    events.create("c", "locals", dt.date(2026, 4, 1))
    assert events.last_used_leader_id() == leader_ids[2]


# ---- placement and players -------------------------------------------------------------
def test_placement_and_players_are_optional_and_editable(events, sample_event):
    assert (sample_event.placement, sample_event.players) == (None, None)
    ev = events.update(sample_event.id, placement=3, players=32)
    assert (ev.placement, ev.players) == (3, 32)
    assert events.update(sample_event.id, placement=None).placement is None  # cleared again
    assert events.get(sample_event.id).players == 32


@pytest.mark.parametrize("bad", [0, -1, 2.5, "3", True])
@pytest.mark.parametrize("field", ["placement", "players"])
def test_placement_and_players_must_be_whole_numbers_of_one_or_more(events, sample_event, field, bad):
    with pytest.raises(EventError, match="whole number"):
        events.update(sample_event.id, **{field: bad})


def test_placement_cannot_be_past_the_player_count(events, sample_event):
    events.update(sample_event.id, players=8)
    with pytest.raises(EventError, match="past the 8 players"):
        events.update(sample_event.id, placement=9)
    events.update(sample_event.id, placement=8)
    with pytest.raises(EventError, match="past the 7 players"):
        events.update(sample_event.id, players=7)  # shrinking the field under a known placement
    assert (events.get(sample_event.id).placement, events.get(sample_event.id).players) == (8, 8)
