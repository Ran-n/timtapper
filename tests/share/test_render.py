#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.477606
Revised: 2026/10/11 16:27:24.931485
"""

import datetime as dt

import pytest
from PIL import Image

from catalog.repository import Leader
from events.repository import Event, Round
from share import render
from stats.compute import games, matchups, summarize

LEADERS = {
    1: Leader(1, "OP01-001", "Roronoa Zoro", "OP01", ("Red",)),
    2: Leader(2, "OP01-003", "Monkey.D.Luffy", "OP01", ("Red", "Green")),
    3: Leader(3, "EB01-040", "Kyros", "EB01", ("Black", "Yellow")),
    4: Leader(4, "OP99-001", "A leader with an absurdly long name that cannot possibly fit", "OP99", ()),
}
identity = lambda s: s  # noqa: E731


def event(rounds, name="Sunday locals", leader=1):
    return Event(1, name, "locals", dt.date(2026, 10, 5), leader, "", tuple(rounds))


def rounds(n, result="W"):
    return [Round(i, i, (i % 4) + 1, result, i % 2 == 0, None, i > n - 2) for i in range(1, n + 1)]


def assert_card(path):
    assert path.exists() and path.suffix == ".png"
    with Image.open(path) as img:
        assert img.size == (render.W, render.H)
        # not a blank canvas: plenty of distinct colors were drawn
        assert len(img.convert("RGB").getcolors(maxcolors=1 << 16) or []) > 20


@pytest.mark.parametrize("n", [0, 1, 7, 30])
def test_event_card_any_round_count(n):
    assert_card(render.event_card(event(rounds(n)), LEADERS, identity, "Locals"))


def test_event_card_pending_round_unknown_leaders_and_long_name():
    ev = event([Round(1, 1, 99, None), Round(2, 2, 4, "D")], name="X" * 200, leader=None)
    assert_card(render.event_card(ev, LEADERS, identity, "Locals"))


def test_event_card_huge_record_shrinks():
    assert render.Card.fit("120-80-10", "ExtraBold", 120, 400) < 120
    assert render.Card.fit("3-1", "ExtraBold", 120, 400) == 120
    assert_card(render.event_card(event(rounds(150, "W")), LEADERS, identity, "Locals"))


def test_matchups_card():
    evs = [event(rounds(12)), event(rounds(5, "L"))]
    s, ms = summarize(evs), matchups(games(evs))
    assert_card(render.matchups_card("All leaders", s, ms, LEADERS, identity))


def test_matchups_card_empty_and_overflow():
    assert_card(render.matchups_card("All leaders", summarize([]), [], LEADERS, identity))
    many = [Round(i, i, 1000 + i, "W") for i in range(1, 40)]
    evs = [event(many)]
    assert_card(render.matchups_card("x", summarize(evs), matchups(games(evs)), LEADERS, identity))


def test_summary_card():
    evs = [event(rounds(12)), event([Round(9, 1, 3, "L"), Round(10, 2, 3, "L"), Round(11, 3, 3, "L")])]
    assert_card(render.summary_card("Playing Zoro", summarize(evs), LEADERS, identity))


def test_summary_card_empty():
    assert_card(render.summary_card("All leaders", summarize([]), LEADERS, identity))


def test_cards_use_translations():
    seen = []

    def spy(s):
        seen.append(s)
        return s

    render.summary_card("x", summarize([event(rounds(3))]), LEADERS, spy)
    assert {"Overall record", "Recent form", "Tracked with timtapper · One Piece TCG"} <= set(seen)


def test_cards_render_into_temp_dir(tmp_path):
    path = render.event_card(event(rounds(2)), LEADERS, identity, "Locals")
    assert path.parent == tmp_path / "temp"
