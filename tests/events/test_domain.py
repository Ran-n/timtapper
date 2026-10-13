#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 01:19:23.887866
Revised: 2026/10/13 01:19:23.887866

What a round's games hold: whether a game has anything noted, and whether cutting a round to its first games
would lose any of it.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from events.domain import TOP_CUT, Game, Round


@pytest.mark.parametrize(
    ("game", "noted"),
    [
        (Game(1), False),
        (Game(1, result="W"), True),
        (Game(1, went_first=False), True),  # False is something noted, not nothing
        (Game(2, chose_turn=False), True),
    ],
)
def test_a_game_is_noted_when_anything_about_it_is(game, noted):
    assert game.noted is noted


def bo3(*games: Game) -> Round:
    return Round(1, 1, 7, 3, TOP_CUT, "", games)


def test_noted_beyond_looks_only_past_the_cut():
    r = bo3(Game(1, "W"), Game(2), Game(3, went_first=True))
    assert [r.noted_beyond(n) for n in (0, 1, 2, 3)] == [True, True, True, False]


def test_an_empty_round_loses_nothing_at_any_cut():
    assert not any(bo3(Game(1), Game(2), Game(3)).noted_beyond(n) for n in (0, 1, 2, 3))


tristate = st.none() | st.booleans()
games = st.builds(Game, st.sampled_from((1, 2, 3)), st.sampled_from((None, "W", "L")), tristate, tristate)


@pytest.mark.property
@given(st.lists(games, max_size=3, unique_by=lambda g: g.game_no), st.integers(0, 3))
def test_noted_beyond_is_whether_any_dropped_game_is_noted(gs, keep):
    r = bo3(*sorted(gs, key=lambda g: g.game_no))
    assert r.noted_beyond(keep) == any(g.noted for g in gs if g.game_no > keep)
    assert not r.noted_beyond(3)  # keeping every game loses none
