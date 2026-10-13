#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 23:54:25.232214
Revised: 2026/10/13 01:17:14.555023

Events, their rounds and the rounds' games as plain values, and what follows from the OPTCG's rules: a round is
Swiss, top cut or a bye (no opponent, won without playing); a played round is a best of 1 or 3, won by whoever
first wins most of its games; in game 1 the die winner (Swiss) or the higher seed (top cut) chooses the turn order,
and in every later game the loser of the game before chooses.
"""

import datetime as dt
from dataclasses import dataclass, field

BEST_OF = (1, 3)
SWISS, TOP_CUT, BYE = "swiss", "top_cut", "bye"
KINDS = (SWISS, TOP_CUT, BYE)


def default_best_of(kind: str) -> int:
    """Top-cut rounds are played as best of 3, Swiss rounds as best of 1 (either can be switched); a bye isn't."""
    return 3 if kind == TOP_CUT else 1


@dataclass(frozen=True, slots=True)
class Game:
    game_no: int
    result: str | None = None  # "W"/"L"; None: not played (yet)
    went_first: bool | None = None
    # you chose the turn order. Game 1: always as noted. Later games: None follows the rules (the previous game's
    # loser chose); a value is an override for events that do it differently
    chose_turn: bool | None = None

    @property
    def noted(self) -> bool:
        """Something was noted about this game: its result, turn order or who chose it."""
        return any(v is not None for v in (self.result, self.went_first, self.chose_turn))


@dataclass(frozen=True, slots=True)
class Round:
    id: int
    round_no: int
    opponent_leader_id: int | None  # None for a bye
    best_of: int = 1
    kind: str = SWISS
    notes: str = ""
    games: tuple[Game, ...] = field(default_factory=tuple)

    @classmethod
    def single_game(
        cls,
        id: int,  # noqa: A002 — the field's name
        round_no: int,
        opponent_leader_id: int,
        result: str | None = None,
        went_first: bool | None = None,
        chose_turn: bool | None = None,
        top_cut: bool = False,
        notes: str = "",
    ) -> Round:
        """A best of 1, given its one game's result, turn order and who chose it."""
        kind = TOP_CUT if top_cut else SWISS
        return cls(id, round_no, opponent_leader_id, 1, kind, notes, (Game(1, result, went_first, chose_turn),))

    @property
    def top_cut(self) -> bool:
        return self.kind == TOP_CUT

    @property
    def bye(self) -> bool:
        return self.kind == BYE

    @property
    def to_win(self) -> int:
        return self.best_of // 2 + 1

    @property
    def wins(self) -> int:
        return sum(g.result == "W" for g in self.games)

    @property
    def losses(self) -> int:
        return sum(g.result == "L" for g in self.games)

    @property
    def result(self) -> str | None:
        """W/L once someone has won enough games (a bye: W); None while the round is still being played."""
        if self.bye:
            return "W"
        if self.wins >= self.to_win:
            return "W"
        if self.losses >= self.to_win:
            return "L"
        return None

    def game(self, game_no: int) -> Game:
        """Game `game_no`, or an empty one when it isn't stored (not played)."""
        return next((g for g in self.games if g.game_no == game_no), Game(game_no))

    def chose_turn(self, game_no: int) -> bool | None:
        """Whether you chose the turn order in `game_no`: as noted, else by the rules (the previous loser chose)."""
        noted = self.game(game_no).chose_turn
        if noted is not None or game_no == 1:
            return noted
        previous = self.game(game_no - 1).result
        return None if previous is None else previous == "L"

    def chose_by_rule(self, game_no: int) -> bool:
        """True when `game_no`'s chooser comes from the rules, not a note (a later game, not overridden)."""
        return game_no > 1 and self.game(game_no).chose_turn is None

    def die_decided(self, game_no: int) -> bool:
        """The die decided who chose: game 1 of a Swiss round (top cut goes by seed, later games by the result)."""
        return game_no == 1 and self.kind == SWISS

    def noted_beyond(self, game_no: int) -> bool:
        """A game after `game_no` holds something noted: what cutting the round to `game_no` games would lose."""
        return any(g.noted for g in self.games if g.game_no > game_no)

    @property
    def played(self) -> tuple[Game, ...]:
        """The games that have a result, in order."""
        return tuple(g for g in self.games if g.result)


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    name: str
    event_type: str
    date: dt.date
    leader_id: int | None
    notes: str = ""
    rounds: tuple[Round, ...] = field(default_factory=tuple)
    placement: int | None = None  # where you finished (1 = won); None: unknown
    players: int | None = None  # how many entered; None: unknown
    dropped: bool = False  # you left before it ended
    set_code: str | None = None  # the set it was played in (its newest legal set, e.g. "OP16"); None: not noted
