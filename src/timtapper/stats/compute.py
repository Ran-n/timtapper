#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.516994
Revised: 2026/10/12 16:54:58.547389

Derived statistics. Pure functions over Event values — nothing here touches
the DB or Flet, so the stats screen and the share cards compute the exact
same numbers. Rounds without a result (still being played) never count.
"""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from events.repository import Event

RECENT_FORM = 10
MIN_MATCHUP_GAMES = 3


@dataclass(frozen=True, slots=True)
class Record:
    wins: int = 0
    losses: int = 0

    @property
    def games(self) -> int:
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
class Game:
    own_leader_id: int | None
    opponent_leader_id: int
    result: str
    went_first: bool | None
    won_die_roll: bool | None
    top_cut: bool
    event_type: str
    date: dt.date
    order: tuple[dt.date, int, int]  # (event date, event id, round) — chronological sort key


@dataclass(frozen=True, slots=True)
class Filters:
    own_leader_id: int | None = None
    event_type: str | None = None
    query: str = ""  # case-insensitive text in the event's name (the events list's search field)

    @property
    def active(self) -> bool:
        return self.own_leader_id is not None or self.event_type is not None or bool(self.query.strip())

    def matches(self, event: Event) -> bool:
        return (
            (self.own_leader_id is None or event.leader_id == self.own_leader_id)
            and (self.event_type is None or event.event_type == self.event_type)
            and self.query.strip().casefold() in event.name.casefold()
        )


@dataclass(frozen=True, slots=True)
class Matchup:
    opponent_leader_id: int
    record: Record
    first: Record
    second: Record


@dataclass(frozen=True, slots=True)
class Summary:
    record: Record
    first: Record
    second: Record
    die_won: Record
    die_lost: Record
    recent: tuple[str, ...]  # oldest -> newest
    events: int
    best: Matchup | None
    worst: Matchup | None


def record_of(event: Event) -> Record:
    rec = Record()
    for r in event.rounds:
        if r.result:
            rec = rec.add(r.result)
    return rec


def filter_events(events: list[Event], filters: Filters) -> list[Event]:
    """The events `filters` lets through, in their original order."""
    return [ev for ev in events if filters.matches(ev)]


def games(events: list[Event], filters: Filters | None = None) -> list[Game]:
    """Every decided round matching `filters`, in chronological order."""
    filters = filters or Filters()
    out = [
        Game(
            ev.leader_id,
            r.opponent_leader_id,
            r.result,
            r.went_first,
            r.won_die_roll,
            r.top_cut,
            ev.event_type,
            ev.date,
            (ev.date, ev.id, r.round_no),
        )
        for ev in filter_events(events, filters)
        for r in ev.rounds
        if r.result
    ]
    return sorted(out, key=lambda g: g.order)


def _split(gs: list[Game]) -> tuple[Record, Record, Record, Record, Record]:
    total = first = second = die_won = die_lost = Record()
    for g in gs:
        total = total.add(g.result)
        if g.went_first is True:
            first = first.add(g.result)
        elif g.went_first is False:
            second = second.add(g.result)
        if g.won_die_roll is True:
            die_won = die_won.add(g.result)
        elif g.won_die_roll is False:
            die_lost = die_lost.add(g.result)
    return total, first, second, die_won, die_lost


def matchups(gs: list[Game]) -> list[Matchup]:
    """Per opposing leader, most-played first (ties: better win rate first)."""
    by_opp: dict[int, list[Game]] = defaultdict(list)
    for g in gs:
        by_opp[g.opponent_leader_id].append(g)
    out = []
    for opp, opp_games in by_opp.items():
        total, first, second, _won, _lost = _split(opp_games)
        out.append(Matchup(opp, total, first, second))
    return sorted(out, key=lambda m: (-m.record.games, -(m.record.win_rate or 0), m.opponent_leader_id))


def best_and_worst(ms: list[Matchup], min_games: int = MIN_MATCHUP_GAMES) -> tuple[Matchup | None, Matchup | None]:
    """Highest/lowest win-rate matchups with enough games to mean something."""
    eligible = [m for m in ms if m.record.games >= min_games]
    if not eligible:
        return None, None
    best = max(eligible, key=lambda m: (m.record.win_rate, m.record.games))
    worst = min(eligible, key=lambda m: (m.record.win_rate, -m.record.games))
    return best, (worst if worst is not best else None)


def summarize(events: list[Event], filters: Filters | None = None) -> Summary:
    filters = filters or Filters()
    gs = games(events, filters)
    total, first, second, die_won, die_lost = _split(gs)
    best, worst = best_and_worst(matchups(gs))
    played_events = {g.order[1] for g in gs}
    return Summary(
        total,
        first,
        second,
        die_won,
        die_lost,
        tuple(g.result for g in gs[-RECENT_FORM:]),
        len(played_events),
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
    return "—" if rate is None else f"{round(rate * 100)}%"
