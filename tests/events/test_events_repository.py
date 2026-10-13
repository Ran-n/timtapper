#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.326929
Revised: 2026/10/13 07:39:26.896473
"""

import datetime as dt

import pytest

from db.models import COUNT_MAX
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
        ({"event_type": "moon_cup"}, "unknown event type"),
        ({"leader_id": 999_999}, "unknown leader"),
        ({"date": "2026-01-01"}, "date must be a date"),
        ({"name": "x" * 121}, "longer than 120"),
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
    updated = events.update_round(pending.id, notes="time", opponent_leader_id=leader_ids[4])
    assert (updated.notes, updated.opponent_leader_id) == ("time", leader_ids[4])
    assert events.update_game(pending.id, 1, result="L").result == "L"
    assert events.update_game(pending.id, 1, result=None).result is None


def test_add_round_inherits_requested_top_cut(events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[0], "top_cut")
    assert r.round_no == 5
    assert r.top_cut is True


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"opponent_leader_id": 999_999}, "unknown leader"),
        ({"round_no": 7}, "unknown round fields"),
        ({"result": "W"}, "unknown round fields"),  # results belong to games
        ({"best_of": 2}, "best_of must be 1 or 3"),
        ({"best_of": True}, "best_of must be 1 or 3"),
        ({"kind": "final"}, "kind must be one of"),
        ({"notes": None}, "notes must be text"),
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


@pytest.mark.parametrize("bad", [0, -1, 2.5, "3", True, COUNT_MAX + 1, 10**20])
@pytest.mark.parametrize("field", ["placement", "players"])
def test_placement_and_players_must_be_whole_numbers_in_range(events, sample_event, field, bad):
    """10**20 is past SQLite's 64-bit integers: it used to crash the write with OverflowError, uncaught."""
    with pytest.raises(EventError, match=f"whole number from 1 to {COUNT_MAX}"):
        events.update(sample_event.id, **{field: bad})


def test_the_largest_count_is_accepted(events, sample_event):
    ev = events.update(sample_event.id, placement=COUNT_MAX, players=COUNT_MAX)
    assert (ev.placement, ev.players) == (COUNT_MAX, COUNT_MAX)


def test_placement_cannot_be_past_the_player_count(events, sample_event):
    events.update(sample_event.id, players=8)
    with pytest.raises(EventError, match="past the 8 players"):
        events.update(sample_event.id, placement=9)
    events.update(sample_event.id, placement=8)
    with pytest.raises(EventError, match="past the 7 players"):
        events.update(sample_event.id, players=7)  # shrinking the field under a known placement
    assert (events.get(sample_event.id).placement, events.get(sample_event.id).players) == (8, 8)


# ---- names by type ---------------------------------------------------------------------
def test_names_of_type(events, sample_event):
    other = events.create("Local #2", "locals", dt.date(2026, 1, 1))
    events.create("Testing #1", "testing", dt.date(2026, 1, 1))
    assert sorted(events.names_of_type("locals")) == ["Local #2", "Sunday locals"]
    assert events.names_of_type("locals", exclude_id=other.id) == ["Sunday locals"]
    assert events.names_of_type("regional") == []


def test_a_name_of_exactly_the_limit_is_kept(events, sample_event):
    assert events.update(sample_event.id, name="x" * 120).name == "x" * 120


@pytest.mark.regression
def test_event_notes_must_be_text(events, sample_event):
    """notes=None used to reach the NOT NULL column and fail as an IntegrityError, not a rejected edit."""
    with pytest.raises(EventError, match="notes must be text"):
        events.update(sample_event.id, notes=None)


def test_add_round_rejects_an_unknown_kind(events, sample_event, leader_ids):
    with pytest.raises(EventError, match="kind must be one of"):
        events.add_round(sample_event.id, leader_ids[1], "yes")


def test_event_error_keeps_its_template_and_params(events, sample_event):
    with pytest.raises(EventError) as caught:
        events.update(sample_event.id, players=8, placement=9)
    assert str(caught.value) == "placement 9 is past the 8 players"
    assert caught.value.template == "placement {placement} is past the {players} players"
    assert caught.value.params == {"placement": 9, "players": 8}


# ---- best of 3 ----------------------------------------------------------------------
def test_swiss_rounds_are_best_of_1_and_top_cut_rounds_best_of_3(events, sample_event, leader_ids):
    swiss = events.add_round(sample_event.id, leader_ids[1])
    top = events.add_round(sample_event.id, leader_ids[1], "top_cut")
    assert (swiss.best_of, [g.game_no for g in swiss.games]) == (1, [1])
    assert (top.best_of, [g.game_no for g in top.games]) == (3, [1, 2, 3])
    assert events.add_round(sample_event.id, leader_ids[1], "top_cut", best_of=1).best_of == 1


def test_a_bye_has_no_opponent_and_no_games_and_is_won(events, sample_event):
    bye = events.add_round(sample_event.id, None, "bye")
    assert (bye.kind, bye.opponent_leader_id, bye.games, bye.result) == ("bye", None, (), "W")
    with pytest.raises(EventError, match="a bye has no games"):
        events.update_game(bye.id, 1, result="L")


def test_a_bye_takes_no_opponent_and_a_played_round_needs_one(events, sample_event, leader_ids):
    with pytest.raises(EventError, match="a bye has no opponent"):
        events.add_round(sample_event.id, leader_ids[1], "bye")
    with pytest.raises(EventError, match="needs an opponent"):
        events.add_round(sample_event.id, None)
    bye = events.add_round(sample_event.id, None, "bye")
    with pytest.raises(EventError, match="needs an opponent"):
        events.update_round(bye.id, kind="swiss")
    with pytest.raises(EventError, match="a bye has no opponent"):
        events.update_round(bye.id, opponent_leader_id=leader_ids[1])


def test_a_round_turned_into_a_bye_drops_its_opponent_and_games_and_back(events, sample_event, leader_ids):
    r = sample_event.rounds[0]
    bye = events.update_round(r.id, kind="bye")
    assert (bye.opponent_leader_id, bye.games, bye.result) == (None, (), "W")
    back = events.update_round(r.id, kind="top_cut", opponent_leader_id=leader_ids[2])
    assert (back.opponent_leader_id, back.best_of, [g.result for g in back.games]) == (leader_ids[2], 3, [None] * 3)


def test_event_set_and_dropped(events, sample_event):
    ev = events.update(sample_event.id, set_code="OP16", dropped=True)
    assert (ev.set_code, ev.dropped) == ("OP16", True)
    assert events.update(sample_event.id, set_code=None).set_code is None
    with pytest.raises(EventError, match="unknown set 'OP99'"):
        events.update(sample_event.id, set_code="OP99")
    with pytest.raises(EventError, match="dropped must be true or false"):
        events.update(sample_event.id, dropped="yes")


def bo3(events, sample_event, leader_ids):
    return events.add_round(sample_event.id, leader_ids[1], "top_cut")


@pytest.mark.parametrize(
    ("results", "match"),
    [((), None), (("W",), None), (("W", "W"), "W"), (("L", "W"), None), (("L", "W", "L"), "L"), (("W", "L", "W"), "W")],
)
def test_a_best_of_3_is_won_by_whoever_wins_two(events, sample_event, leader_ids, results, match):
    r = bo3(events, sample_event, leader_ids)
    for n, result in enumerate(results, start=1):
        r = events.update_game(r.id, n, result=result)
    assert r.result == match
    assert events.get(sample_event.id).rounds[-1].result == match


def test_later_games_follow_the_rule_unless_overridden(events, sample_event, leader_ids):
    r = bo3(events, sample_event, leader_ids)
    assert r.chose_turn(2) is None  # game 1 not played yet
    r = events.update_game(r.id, 1, result="L")
    assert r.chose_turn(2) is True and r.chose_by_rule(2)  # you lost game 1, so you chose
    r = events.update_game(r.id, 2, result="W", chose_turn=False)
    assert r.chose_turn(2) is False and not r.chose_by_rule(2)  # an override wins over the rule
    assert r.chose_turn(3) is False  # you won game 2: they chose


def test_switching_best_of_adds_or_removes_games(events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[1])
    r = events.update_game(r.id, 1, result="W")
    r = events.update_round(r.id, best_of=3)
    assert [(g.game_no, g.result) for g in r.games] == [(1, "W"), (2, None), (3, None)]
    r = events.update_round(r.id, best_of=1)
    assert [(g.game_no, g.result) for g in r.games] == [(1, "W")]


def test_top_cut_brings_its_usual_best_of_unless_that_drops_games(events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[1])
    r = events.update_round(r.id, kind="top_cut")
    assert r.best_of == 3
    r = events.update_round(r.id, kind="swiss")
    assert r.best_of == 1  # games 2 and 3 were empty
    r = events.update_round(r.id, kind="top_cut")
    r = events.update_game(r.id, 2, result="L")
    r = events.update_round(r.id, kind="swiss")
    assert r.best_of == 3 and r.game(2).result == "L"  # game 2 is kept
    assert events.update_round(r.id, kind="top_cut", best_of=1).best_of == 1  # an explicit best-of wins


@pytest.mark.parametrize(
    ("game_no", "fields", "message"),
    [
        (2, {"result": "W"}, "game 2 is not part of a best of 1"),
        (0, {"result": "W"}, "game 0 is not part of a best of 1"),
        (True, {"result": "W"}, "is not part of a best of 1"),
        (1, {"result": "X"}, "result must be"),
        (1, {"went_first": "yes"}, "went_first must be"),
        (1, {"chose_turn": 1}, "chose_turn must be"),
        (1, {"won_die_roll": True}, "unknown game fields"),
    ],
)
def test_update_game_rejects_bad_input(events, sample_event, game_no, fields, message):
    with pytest.raises(EventError, match=message):
        events.update_game(sample_event.rounds[0].id, game_no, **fields)


def test_update_game_on_a_missing_round(events):
    with pytest.raises(EventError, match="round 999 not found"):
        events.update_game(999, 1, result="W")


@pytest.mark.regression
def test_a_round_without_stored_games_gets_one_on_its_first_edit(events, sample_event, seeded_db):
    """Rounds can predate their game rows (written outside the repository): the first edit must not fail."""
    from sqlalchemy import delete

    from db.models import Game as GameRow

    rid = sample_event.rounds[3].id
    with seeded_db.session() as s:
        s.execute(delete(GameRow).where(GameRow.match_id == rid))
    assert events.get(sample_event.id).rounds[3].games == ()
    assert events.update_game(rid, 1, result="W").result == "W"
