#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.516994
Revised: 2026/10/14 07:43:51.310608

Derived statistics. Pure functions over Event values — nothing here touches
the DB or Flet, so the stats screen and the share cards compute the exact
same numbers. Two levels: matches (rounds; a best of 3 won 2-1 is one win)
and games. Records, win rates, matchups and recent form count matches; turn
order and who chose it count games. Anything still being played never counts.
A bye is a win in its event's standing (record_of) but no match in the stats:
it has no opponent and nothing was played, so it stays out of win rates and
matchups, counted on its own instead.
"""

import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass

from events.domain import Event

RECENT_FORM = 10
MIN_MATCHUP_GAMES = 3  # matches against one leader before it can be a best or worst matchup


@dataclass(frozen=True, slots=True)
class Record:
    wins: int = 0
    losses: int = 0

    @property
    def games(self) -> int:
        """How many results the record holds (matches or games, whichever it counts)."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> float | None:
        return self.wins / self.games if self.games else None

    def add(self, result: str) -> Record:
        return Record(self.wins + (result == "W"), self.losses + (result == "L"))

    def label(self) -> str:
        """`5-2`: wins-losses (the OPTCG has no draws)."""
        return f"{self.wins}-{self.losses}"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """A decided round."""

    own_leader_id: int | None
    opponent_leader_id: int
    result: str
    event_id: int
    order: tuple[dt.date, int, int]  # (event date, event id, round) — chronological sort key


@dataclass(frozen=True, slots=True)
class GamePlayed:
    """A decided game of a round."""

    opponent_leader_id: int
    result: str
    went_first: bool | None
    chose_turn: bool | None  # you chose the turn order (noted, or by the rules in later games)
    die_decided: bool  # the die decided who chose (game 1 of a Swiss round)
    order: tuple[dt.date, int, int, int]  # (event date, event id, round, game)


@dataclass(frozen=True, slots=True)
class Filters:
    own_leader_id: int | None = None
    event_type: str | None = None
    query: str = ""  # case-insensitive text in the event's name (the events list's search field)
    set_code: str | None = None  # the set the event was played in

    @property
    def active(self) -> bool:
        return (
            self.own_leader_id is not None
            or self.event_type is not None
            or self.set_code is not None
            or bool(self.query.strip())
        )

    def matches(self, event: Event) -> bool:
        return (
            (self.own_leader_id is None or event.leader_id == self.own_leader_id)
            and (self.event_type is None or event.event_type == self.event_type)
            and (self.set_code is None or event.set_code == self.set_code)
            and self.query.strip().casefold() in event.name.casefold()
        )


@dataclass(frozen=True, slots=True)
class Matchup:
    opponent_leader_id: int
    record: Record  # matches
    first: Record  # games you went first in
    second: Record  # games you went second in


@dataclass(frozen=True, slots=True)
class Summary:
    record: Record  # matches
    games: Record  # every decided game
    first: Record
    second: Record
    die_won: Record  # games whose turn order the die decided, by whether you won it
    die_lost: Record
    chose: Record  # games where you chose the turn order
    opp_chose: Record  # games where your opponent did
    recent: tuple[str, ...]  # match results, oldest -> newest
    events: int
    byes: int
    best: Matchup | None
    worst: Matchup | None


def _record(results) -> Record:
    rec = Record()
    for result in results:
        rec = rec.add(result)
    return rec


def record_of(event: Event) -> Record:
    """The event's match record as its standing counts it: a bye is a win."""
    return _record(r.result for r in event.rounds if r.result)


def games_record_of(event: Event) -> Record:
    """The event's game record (every decided game of every round)."""
    return _record(g.result for r in event.rounds for g in r.played)


def filter_events(events: list[Event], filters: Filters) -> list[Event]:
    """The events `filters` lets through, in their original order."""
    return [ev for ev in events if filters.matches(ev)]


def matches(events: list[Event], filters: Filters | None = None) -> list[MatchResult]:
    """Every decided round played against someone (no byes) matching `filters`, in chronological order."""
    out = [
        MatchResult(ev.leader_id, r.opponent_leader_id, r.result, ev.id, (ev.date, ev.id, r.round_no))
        for ev in filter_events(events, filters or Filters())
        for r in ev.rounds
        if r.result and not r.bye
    ]
    return sorted(out, key=lambda m: m.order)


def games(events: list[Event], filters: Filters | None = None) -> list[GamePlayed]:
    """Every decided game matching `filters`, in chronological order."""
    out = [
        GamePlayed(
            r.opponent_leader_id,
            g.result,
            g.went_first,
            r.chose_turn(g.game_no),
            r.die_decided(g.game_no),
            (ev.date, ev.id, r.round_no, g.game_no),
        )
        for ev in filter_events(events, filters or Filters())
        for r in ev.rounds
        for g in r.played
    ]
    return sorted(out, key=lambda g: g.order)


def _tally(gs: list[GamePlayed], side) -> tuple[Record, Record]:
    """Results split by `side(game)`: True into the first record, False into the second, None into neither."""
    return _record(g.result for g in gs if side(g) is True), _record(g.result for g in gs if side(g) is False)


def _turn_order(gs: list[GamePlayed]) -> tuple[Record, Record]:
    return _tally(gs, lambda g: g.went_first)


def matchups(events: list[Event], filters: Filters | None = None) -> list[Matchup]:
    """Per opposing leader, most-played first (ties: better win rate first)."""
    by_opp: dict[int, list[str]] = defaultdict(list)
    for m in matches(events, filters):
        by_opp[m.opponent_leader_id].append(m.result)
    games_by_opp: dict[int, list[GamePlayed]] = defaultdict(list)
    for g in games(events, filters):
        games_by_opp[g.opponent_leader_id].append(g)
    out = [Matchup(opp, _record(results), *_turn_order(games_by_opp[opp])) for opp, results in by_opp.items()]
    return sorted(out, key=lambda m: (-m.record.games, -(m.record.win_rate or 0), m.opponent_leader_id))


def best_and_worst(ms: list[Matchup], min_games: int = MIN_MATCHUP_GAMES) -> tuple[Matchup | None, Matchup | None]:
    """Highest/lowest win-rate matchups with enough matches to mean something. No "worst" when it would win
    as often as the best: two matchups at the same rate aren't a best and a worst."""
    eligible = [m for m in ms if m.record.games >= min_games]
    if not eligible:
        return None, None
    best = max(eligible, key=lambda m: (m.record.win_rate, m.record.games))
    worst = min(eligible, key=lambda m: (m.record.win_rate, -m.record.games))
    return best, (worst if worst.record.win_rate < best.record.win_rate else None)


def summarize(events: list[Event], filters: Filters | None = None) -> Summary:
    shown = filter_events(events, filters or Filters())  # filtered once: every part below counts the same events
    ms, gs = matches(shown), games(shown)
    first, second = _turn_order(gs)
    die_won, die_lost = _tally([g for g in gs if g.die_decided], lambda g: g.chose_turn)
    chose, opp_chose = _tally(gs, lambda g: g.chose_turn)
    best, worst = best_and_worst(matchups(shown))
    return Summary(
        _record(m.result for m in ms),
        _record(g.result for g in gs),
        first,
        second,
        die_won,
        die_lost,
        chose,
        opp_chose,
        tuple(m.result for m in ms[-RECENT_FORM:]),
        len({m.event_id for m in ms}),
        sum(r.bye for ev in shown for r in ev.rounds),
        best,
        worst,
    )


def own_leaders(events: list[Event]) -> list[int]:
    """Own leaders that have events, most-used first."""
    counts: dict[int, int] = defaultdict(int)
    for ev in events:
        if ev.leader_id is not None:
            counts[ev.leader_id] += 1
    return sorted(counts, key=lambda lid: (-counts[lid], lid))


def percent(rate: float | None) -> str:
    """Whole percent, halves rounded up (5-3 is 63%, as people round), not to even as round() does."""
    if rate is None:
        return "—"
    return f"{math.floor(rate * 100 + 0.5 + 1e-9)}%"  # 1e-9: 0.285 * 100 lands just under 28.5
