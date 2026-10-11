#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.562044
Revised: 2026/10/11 16:27:25.006973
"""

import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from events.repository import Event, Round
from stats.compute import (
    RECENT_FORM,
    Filters,
    Record,
    best_and_worst,
    games,
    matchups,
    own_leaders,
    percent,
    record_of,
    summarize,
)


def rnd(no, opp, result, first=None, die=None, top_cut=False):
    return Round(no * 10, no, opp, result, first, die, top_cut)


def ev(eid, rounds, leader=1, etype="locals", date=dt.date(2026, 1, 1)):
    return Event(eid, f"e{eid}", etype, date, leader, "", tuple(rounds))


def test_record_basics():
    rec = Record().add("W").add("W").add("L").add("D")
    assert (rec.wins, rec.losses, rec.draws, rec.games) == (2, 1, 1, 4)
    assert rec.win_rate == 0.5
    assert rec.label() == "2-1-1"
    assert Record(3, 1).label() == "3-1"
    assert Record().win_rate is None


@pytest.mark.parametrize(("rate", "text"), [(None, "—"), (0.0, "0%"), (0.666, "67%"), (1.0, "100%")])
def test_percent(rate, text):
    assert percent(rate) == text


def test_record_of_skips_pending_rounds():
    assert record_of(ev(1, [rnd(1, 2, "W"), rnd(2, 3, None), rnd(3, 2, "L")])) == Record(1, 1)


def test_games_filters_and_orders_chronologically():
    events = [
        ev(2, [rnd(1, 5, "L")], leader=1, date=dt.date(2026, 2, 1)),
        ev(1, [rnd(2, 6, "W"), rnd(1, 5, "W")], leader=2, etype="online", date=dt.date(2026, 1, 1)),
    ]
    assert [g.result for g in games(events)] == ["W", "W", "L"]
    assert [g.opponent_leader_id for g in games(events)] == [5, 6, 5]
    assert [g.result for g in games(events, Filters(own_leader_id=1))] == ["L"]
    assert [g.result for g in games(events, Filters(event_type="online"))] == ["W", "W"]
    assert games(events, Filters(own_leader_id=2, event_type="locals")) == []


def test_summarize_splits():
    events = [
        ev(1, [rnd(1, 5, "W", True, True), rnd(2, 6, "L", False, False), rnd(3, 5, "W", False, True), rnd(4, 7, None)]),
        ev(2, [rnd(1, 5, "D", True, None)], date=dt.date(2026, 2, 1)),
    ]
    s = summarize(events)
    assert s.record == Record(2, 1, 1)
    assert s.first == Record(1, 0, 1)
    assert s.second == Record(1, 1)
    assert s.die_won == Record(2)
    assert s.die_lost == Record(0, 1)
    assert s.recent == ("W", "L", "W", "D")
    assert s.events == 2


def test_summarize_empty():
    s = summarize([])
    assert s.record.games == 0
    assert s.recent == ()
    assert (s.best, s.worst, s.events) == (None, None, 0)


def test_recent_form_keeps_last_ten():
    results = ["L"] * 5 + ["W"] * RECENT_FORM
    s = summarize([ev(1, [rnd(i + 1, 5, r) for i, r in enumerate(results)])])
    assert s.recent == ("W",) * RECENT_FORM


def test_matchups_sorted_by_games_then_win_rate():
    events = [
        ev(1, [rnd(1, 5, "W", True), rnd(2, 5, "L", False), rnd(3, 6, "W"), rnd(4, 7, "L"), rnd(5, 5, "W")]),
    ]
    ms = matchups(games(events))
    assert [m.opponent_leader_id for m in ms] == [5, 6, 7]
    assert ms[0].record == Record(2, 1)
    assert ms[0].first == Record(1)
    assert ms[0].second == Record(0, 1)


def test_best_and_worst_need_min_games():
    events = [ev(1, [rnd(i, 5, r) for i, r in enumerate("WWWL", 1)] + [rnd(i, 6, r) for i, r in enumerate("LLW", 5)])]
    ms = matchups(games(events))
    best, worst = best_and_worst(ms)
    assert best.opponent_leader_id == 5
    assert worst.opponent_leader_id == 6
    assert best_and_worst(ms, min_games=4) == (ms[0], None)  # only one eligible: no separate "worst"
    assert best_and_worst(ms, min_games=10) == (None, None)


def test_own_leaders_most_used_first():
    events = [ev(1, [], leader=3), ev(2, [], leader=4), ev(3, [], leader=4), ev(4, [], leader=None)]
    assert own_leaders(events) == [4, 3]


results_st = st.lists(st.sampled_from(["W", "L", "D", None]), max_size=40)


@pytest.mark.property
@given(results_st, st.lists(st.sampled_from([True, False, None]), min_size=40, max_size=40))
def test_property_splits_partition_the_record(results, firsts):
    rounds = [rnd(i + 1, (i % 4) + 1, r, firsts[i]) for i, r in enumerate(results)]
    s = summarize([ev(1, rounds)])
    decided = [r for r in results if r]
    assert s.record.games == len(decided)
    assert s.first.games + s.second.games <= s.record.games
    assert sum(m.record.games for m in matchups(games([ev(1, rounds)]))) == s.record.games
    if s.record.games:
        assert 0 <= s.record.win_rate <= 1
    assert len(s.recent) == min(RECENT_FORM, len(decided))


@pytest.mark.property
@given(st.lists(st.sampled_from(["W", "L", "D"]), max_size=30))
def test_property_record_label_roundtrip(results):
    rec = Record()
    for r in results:
        rec = rec.add(r)
    parts = [int(p) for p in rec.label().split("-")]
    assert parts[:2] == [rec.wins, rec.losses]
    assert (parts[2] if len(parts) == 3 else 0) == rec.draws
