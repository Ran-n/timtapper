#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.562044
Revised: 2026/10/14 07:43:51.710205
"""

import dataclasses
import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from events.repository import Event, Game, Round
from stats.compute import (
    RECENT_FORM,
    Filters,
    Record,
    best_and_worst,
    filter_events,
    games,
    games_record_of,
    matchups,
    own_leaders,
    percent,
    record_of,
    summarize,
)


def rnd(no, opp, result, first=None, die=None, top_cut=False):
    return Round.single_game(no * 10, no, opp, result, first, die, top_cut)


def ev(eid, rounds, leader=1, etype="locals", date=dt.date(2026, 1, 1)):
    return Event(eid, f"e{eid}", etype, date, leader, "", tuple(rounds))


def test_record_basics():
    rec = Record().add("W").add("W").add("L")
    assert (rec.wins, rec.losses, rec.games) == (2, 1, 3)
    assert rec.win_rate == pytest.approx(2 / 3)
    assert rec.label() == "2-1"
    assert Record(3, 1).label() == "3-1"
    assert Record().win_rate is None


@pytest.mark.parametrize(
    ("rate", "text"),
    [
        (None, "—"),
        (0.0, "0%"),
        (0.666, "67%"),
        (1.0, "100%"),
        (5 / 8, "63%"),  # half-to-even rounding showed 62%
        (1 / 8, "13%"),
        (3 / 8, "38%"),
        (0.285, "29%"),  # 0.285 * 100 is 28.499999…
    ],
)
def test_percent(rate, text):
    assert percent(rate) == text


def test_record_of_skips_pending_rounds():
    assert record_of(ev(1, [rnd(1, 2, "W"), rnd(2, 3, None), rnd(3, 2, "L")])) == Record(1, 1)


def test_games_filters_and_orders_chronologically():
    events = [
        ev(2, [rnd(1, 5, "L")], leader=1, date=dt.date(2026, 2, 1)),
        ev(1, [rnd(2, 6, "W"), rnd(1, 5, "W")], leader=2, etype="treasure_cup", date=dt.date(2026, 1, 1)),
    ]
    assert [g.result for g in games(events)] == ["W", "W", "L"]
    assert [g.opponent_leader_id for g in games(events)] == [5, 6, 5]
    assert [g.result for g in games(events, Filters(own_leader_id=1))] == ["L"]
    assert [g.result for g in games(events, Filters(event_type="treasure_cup"))] == ["W", "W"]
    assert games(events, Filters(own_leader_id=2, event_type="locals")) == []


def test_summarize_splits():
    events = [
        ev(1, [rnd(1, 5, "W", True, True), rnd(2, 6, "L", False, False), rnd(3, 5, "W", False, True), rnd(4, 7, None)]),
        ev(2, [rnd(1, 5, "L", True, None)], date=dt.date(2026, 2, 1)),
    ]
    s = summarize(events)
    assert s.record == Record(2, 2)
    assert s.first == Record(1, 1)
    assert s.second == Record(1, 1)
    assert s.die_won == Record(2)
    assert s.die_lost == Record(0, 1)
    assert s.recent == ("W", "L", "W", "L")
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
    ms = matchups(events)
    assert [m.opponent_leader_id for m in ms] == [5, 6, 7]
    assert ms[0].record == Record(2, 1)
    assert ms[0].first == Record(1)
    assert ms[0].second == Record(0, 1)


def test_best_and_worst_need_min_games():
    events = [ev(1, [rnd(i, 5, r) for i, r in enumerate("WWWL", 1)] + [rnd(i, 6, r) for i, r in enumerate("LLW", 5)])]
    ms = matchups(events)
    best, worst = best_and_worst(ms)
    assert best.opponent_leader_id == 5
    assert worst.opponent_leader_id == 6
    assert best_and_worst(ms, min_games=4) == (ms[0], None)  # only one eligible: no separate "worst"
    assert best_and_worst(ms, min_games=10) == (None, None)


def test_own_leaders_most_used_first():
    events = [ev(1, [], leader=3), ev(2, [], leader=4), ev(3, [], leader=4), ev(4, [], leader=None)]
    assert own_leaders(events) == [4, 3]


results_st = st.lists(st.sampled_from(["W", "L", None]), max_size=40)


@pytest.mark.property
@given(results_st, st.lists(st.sampled_from([True, False, None]), min_size=40, max_size=40))
def test_property_splits_partition_the_record(results, firsts):
    rounds = [rnd(i + 1, (i % 4) + 1, r, firsts[i]) for i, r in enumerate(results)]
    s = summarize([ev(1, rounds)])
    decided = [r for r in results if r]
    assert s.record.games == len(decided)
    assert s.first.games + s.second.games <= s.record.games
    assert sum(m.record.games for m in matchups([ev(1, rounds)])) == s.record.games
    if s.record.games:
        assert 0 <= s.record.win_rate <= 1
    assert len(s.recent) == min(RECENT_FORM, len(decided))


@pytest.mark.property
@given(st.lists(st.sampled_from(["W", "L"]), max_size=30))
def test_property_record_label_roundtrip(results):
    rec = Record()
    for r in results:
        rec = rec.add(r)
    assert [int(p) for p in rec.label().split("-")] == [rec.wins, rec.losses]
    assert rec.games == len(results)


# ---- event filters ------------------------------------------------------------------
def test_filters_match_leader_type_and_name():
    a = ev(1, [], date=dt.date(2026, 1, 1))
    named = dataclasses.replace(a, name="Sunday Locals", event_type="locals")
    assert Filters().matches(named) and not Filters().active
    assert Filters(query="  sunday ").matches(named)  # trimmed, case-insensitive
    assert not Filters(query="regional").matches(named)
    assert Filters(event_type="locals").matches(named) and not Filters(event_type="treasure_cup").matches(named)
    assert Filters(own_leader_id=named.leader_id).matches(named) and not Filters(own_leader_id=999).matches(named)
    assert Filters(query="x").active and Filters(event_type="treasure_cup").active and Filters(own_leader_id=1).active
    assert not Filters(query="   ").active


def test_filter_events_keeps_order():
    evs = [dataclasses.replace(ev(i, []), name=n) for i, n in enumerate(["Locals A", "Online", "Locals B"], start=1)]
    assert [e.name for e in filter_events(evs, Filters(query="locals"))] == ["Locals A", "Locals B"]


@pytest.mark.property
@given(st.lists(st.text(max_size=12), max_size=12), st.text(max_size=4))
def test_property_filter_events_is_a_subsequence_that_all_match(names, query):
    evs = [dataclasses.replace(ev(i, []), name=n) for i, n in enumerate(names, start=1)]
    f = Filters(query=query)
    out = filter_events(evs, f)
    assert all(f.matches(e) for e in out)
    assert [e for e in evs if e in out] == out  # original order, nothing invented
    assert len(out) == sum(f.matches(e) for e in evs)
    assert filter_events(evs, Filters()) == evs


@pytest.mark.regression
def test_matchups_at_the_same_rate_are_not_a_best_and_a_worst():
    """Two 2-1 matchups showed one as the best and the other as the worst."""
    events = [ev(1, [rnd(i, 5, r) for i, r in enumerate("WWL", 1)] + [rnd(i, 6, r) for i, r in enumerate("WLW", 4)])]
    best, worst = best_and_worst(matchups(events))
    assert best is not None and worst is None


@pytest.mark.property
@given(st.integers(0, 60), st.integers(1, 60))
def test_property_percent_rounds_halves_up(wins, extra):
    games_played = wins + extra
    exact = wins * 100 / games_played
    shown = int(percent(wins / games_played).removesuffix("%"))
    assert shown - 0.5 <= exact < shown + 0.5


# ---- best of 3 ----------------------------------------------------------------------
def bo3(no, opp, *games, top_cut=True):
    kind = "top_cut" if top_cut else "swiss"
    return Round(no * 10, no, opp, 3, kind, "", tuple(Game(n, *g) for n, g in enumerate(games, start=1)))


def test_a_best_of_3_counts_once_in_the_record_and_per_game_below():
    # won 2-1: game 1 lost going 1st (you chose: higher seed), game 2 won going 2nd (you chose: lost game 1),
    # game 3 won going 1st (they chose: you won game 2)
    rounds = [bo3(1, 5, ("L", True, True), ("W", False), ("W", True)), rnd(2, 6, "L", True, False)]
    s = summarize([ev(1, rounds)])
    assert s.record == Record(1, 1)  # matches
    assert s.games == Record(2, 2)
    assert (s.first, s.second) == (Record(1, 2), Record(1, 0))
    assert (s.chose, s.opp_chose) == (Record(1, 1), Record(1, 1))
    assert (s.die_won, s.die_lost) == (Record(), Record(0, 1))  # only the Swiss game was decided by a die
    assert s.recent == ("W", "L")
    (m5, m6) = sorted(matchups([ev(1, rounds)]), key=lambda m: m.opponent_leader_id)
    assert (m5.record, m5.first, m5.second) == (Record(1, 0), Record(1, 1), Record(1, 0))


def test_an_unfinished_best_of_3_counts_its_games_but_no_match():
    s = summarize([ev(1, [bo3(1, 5, ("W", True, True))])])
    assert (s.record, s.games, s.events) == (Record(), Record(1, 0), 0)


def test_game_one_of_a_swiss_best_of_3_is_decided_by_the_die():
    s = summarize([ev(1, [bo3(1, 5, ("W", True, True), ("W", True), top_cut=False)])])
    assert s.die_won == Record(1, 0)  # game 1 only: game 2's chooser comes from game 1's result


def test_games_record_of_an_event():
    assert games_record_of(ev(1, [bo3(1, 5, ("W",), ("L",), ("W",)), rnd(2, 6, "L")])) == Record(2, 2)


@pytest.mark.property
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["W", "L", None]),
            st.sampled_from([True, False, None]),
            st.sampled_from([True, False, None]),
        ),
        min_size=3,
        max_size=3,
    ),
    st.booleans(),
)
def test_property_a_best_of_3_never_counts_more_than_one_match(games_, top_cut):
    r = bo3(1, 5, *games_, top_cut=top_cut)
    s = summarize([ev(1, [r])])
    assert s.record.games == (1 if r.result else 0)
    assert s.games.games == sum(1 for g in games_ if g[0])
    assert s.first.games + s.second.games <= s.games.games
    assert s.chose.games + s.opp_chose.games <= s.games.games
    assert s.die_won.games + s.die_lost.games <= (0 if top_cut else 1)


# ---- byes and sets ------------------------------------------------------------------
def bye(no):
    return Round(no * 10, no, None, 1, "bye")


def test_a_bye_wins_the_events_standing_but_stays_out_of_the_stats():
    e = ev(1, [rnd(1, 5, "W"), bye(2), rnd(3, 6, "L")])
    assert record_of(e) == Record(2, 1)  # the standing: a bye is a win
    s = summarize([e])
    assert (s.record, s.byes, s.games) == (Record(1, 1), 1, Record(1, 1))  # nothing was played in it
    assert [m.opponent_leader_id for m in matchups([e])] == [5, 6]


def test_filters_by_set():
    a, b = dataclasses.replace(ev(1, []), set_code="OP16"), dataclasses.replace(ev(2, []), set_code="OP15")
    assert filter_events([a, b], Filters(set_code="OP16")) == [a]
    assert Filters(set_code="OP16").active


@pytest.mark.property
@given(
    st.lists(
        st.tuples(
            st.integers(1, 3), st.sampled_from(["locals", "regional"]), st.lists(st.sampled_from("WL"), max_size=5)
        ),
        max_size=8,
    ),
    st.sampled_from([None, 1, 2]),
    st.sampled_from([None, "locals", "regional"]),
)
def test_property_summarizing_with_filters_is_summarizing_the_filtered_events(specs, leader, etype):
    events = [
        ev(i, [rnd(no, 4 + no % 3, r) for no, r in enumerate(results, 1)], leader=own, etype=kind)
        for i, (own, kind, results) in enumerate(specs, start=1)
    ]
    f = Filters(own_leader_id=leader, event_type=etype)
    assert summarize(events, f) == summarize(filter_events(events, f))
