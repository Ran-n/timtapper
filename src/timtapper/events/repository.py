#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.014644
Revised: 2026/10/13 07:40:24.352297

Events and their rounds: CRUD over the local DB, exposed as plain values.
"""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from core.errors import TranslatableError
from core.logging import get_logger
from db import Database
from db.models import COUNT_MAX, EVENT_NAME_MAX, EVENT_TYPES, RESULTS, CardSet, EventType
from db.models import Event as EventRow
from db.models import Game as GameRow
from db.models import Leader as LeaderRow
from db.models import Match as MatchRow
from events.domain import BEST_OF, BYE, KINDS, SWISS, Event, Game, Round, default_best_of

__all__ = ["Event", "EventError", "EventRepository", "Game", "Round", "is_count"]

_log = get_logger("events")

_EVENT_FIELDS = {"name", "event_type", "date", "leader_id", "notes", "placement", "players", "dropped", "set_code"}
_ROUND_FIELDS = {"opponent_leader_id", "best_of", "kind", "notes"}
_GAME_FIELDS = {"result", "went_first", "chose_turn"}


class EventError(TranslatableError):
    """Rejected input or a missing event/round."""


# per-field messages, whole sentences so each one translates on its own
_WHOLE_NUMBER_ERRORS = {
    "placement": "placement must be a whole number from 1 to {max}",
    "players": "players must be a whole number from 1 to {max}",
}
_TRISTATE_ERRORS = {
    "went_first": "went_first must be true, false or None",
    "chose_turn": "chose_turn must be true, false or None",
}


def _to_game(row: GameRow) -> Game:
    return Game(row.game_no, row.result, row.went_first, row.chose_turn)


def _to_round(row: MatchRow) -> Round:
    return Round(
        row.id,
        row.round_no,
        row.opponent_leader_id,
        row.best_of,
        row.kind,
        row.notes,
        tuple(_to_game(g) for g in row.games),
    )


def _to_event(row: EventRow) -> Event:
    return Event(
        row.id,
        row.name,
        row.event_type.key,
        row.date,
        row.leader_id,
        row.notes,
        tuple(_to_round(m) for m in row.matches),
        row.placement,
        row.players,
        row.dropped,
        row.card_set.code if row.card_set else None,
    )


def _validate_event_fields(s: Session, fields: dict) -> dict:
    unknown = set(fields) - _EVENT_FIELDS
    if unknown:
        raise EventError("unknown event fields: {fields}", fields=sorted(unknown))
    out = dict(fields)
    if "name" in out:
        out["name"] = (out["name"] or "").strip()
        if not out["name"]:
            raise EventError("event name is required")
        if len(out["name"]) > EVENT_NAME_MAX:
            raise EventError("event name is longer than {max} characters", max=EVENT_NAME_MAX)
    if "notes" in out and not isinstance(out["notes"], str):
        raise EventError("notes must be text")
    if "event_type" in out:
        key = out.pop("event_type")
        if key not in EVENT_TYPES:
            raise EventError("unknown event type {key!r}", key=key)
        out["event_type_id"] = s.scalar(select(EventType.id).where(EventType.key == key))
    if "date" in out and not isinstance(out["date"], dt.date):
        raise EventError("date must be a date")
    if out.get("leader_id") is not None and s.get(LeaderRow, out["leader_id"]) is None:
        raise EventError("unknown leader id {leader_id}", leader_id=out["leader_id"])
    for key in ("placement", "players"):
        value = out.get(key)
        if value is not None and not is_count(value):
            raise EventError(_WHOLE_NUMBER_ERRORS[key], max=COUNT_MAX)
    if "dropped" in out and not isinstance(out["dropped"], bool):
        raise EventError("dropped must be true or false")
    if "set_code" in out:
        code = out.pop("set_code")
        set_id = None if code is None else s.scalar(select(CardSet.id).where(CardSet.code == code))
        if code is not None and set_id is None:
            raise EventError("unknown set {code!r}", code=code)
        out["set_id"] = set_id
    return out


def is_count(value: object) -> bool:
    """A placement or player count: a whole number from 1 to COUNT_MAX (a bool is no number, though True == 1)."""
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= COUNT_MAX


def _check_place_in_field(placement: int | None, players: int | None) -> None:
    if placement is not None and players is not None and placement > players:
        raise EventError("placement {placement} is past the {players} players", placement=placement, players=players)


def _validate_round_fields(s: Session, fields: dict) -> dict:
    unknown = set(fields) - _ROUND_FIELDS
    if unknown:
        raise EventError("unknown round fields: {fields}", fields=sorted(unknown))
    if "best_of" in fields and (isinstance(fields["best_of"], bool) or fields["best_of"] not in BEST_OF):
        raise EventError("best_of must be 1 or 3")
    if "kind" in fields and fields["kind"] not in KINDS:
        raise EventError("kind must be one of {kinds}", kinds=KINDS)
    if "notes" in fields and not isinstance(fields["notes"], str):
        raise EventError("notes must be text")
    opponent = fields.get("opponent_leader_id")
    if opponent is not None and s.get(LeaderRow, opponent) is None:
        raise EventError("unknown leader id {leader_id}", leader_id=fields["opponent_leader_id"])
    return fields


def _validate_game_fields(fields: dict) -> dict:
    unknown = set(fields) - _GAME_FIELDS
    if unknown:
        raise EventError("unknown game fields: {fields}", fields=sorted(unknown))
    if "result" in fields and fields["result"] not in (*RESULTS, None):
        raise EventError("result must be one of {results} or None", results=RESULTS)
    for key in ("went_first", "chose_turn"):
        if key in fields and fields[key] is not None and not isinstance(fields[key], bool):
            raise EventError(_TRISTATE_ERRORS[key])
    return fields


def _set_best_of(row: MatchRow, best_of: int) -> None:
    """Give the round exactly `best_of` games (a bye: 0): empty ones added, extra ones (and what they held) removed."""
    row.best_of = max(best_of, 1)
    have = {g.game_no for g in row.games}
    row.games = [g for g in row.games if g.game_no <= best_of] + [
        GameRow(game_no=n) for n in range(1, best_of + 1) if n not in have
    ]


_WITH_GAMES = selectinload(EventRow.matches).selectinload(MatchRow.games)
_WITH_SET = selectinload(EventRow.card_set)


def _load_round(s: Session, round_id: int) -> MatchRow:
    row = s.get(MatchRow, round_id, options=[selectinload(MatchRow.games)])
    if row is None:
        raise EventError("round {round_id} not found", round_id=round_id)
    return row


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _load(s: Session, event_id: int) -> EventRow:
        row = s.get(EventRow, event_id, options=[_WITH_GAMES, _WITH_SET, selectinload(EventRow.event_type)])
        if row is None:
            raise EventError("event {event_id} not found", event_id=event_id)
        return row

    def list(self) -> list[Event]:
        """All events, newest first."""
        with self.db.session() as s:
            rows = s.scalars(
                select(EventRow)
                .options(_WITH_GAMES, _WITH_SET, selectinload(EventRow.event_type))
                .order_by(EventRow.date.desc(), EventRow.id.desc())
            )
            return [_to_event(r) for r in rows]

    def get(self, event_id: int) -> Event:
        with self.db.session() as s:
            return _to_event(self._load(s, event_id))

    def create(self, name: str, event_type: str, date: dt.date, leader_id: int | None = None) -> Event:
        with self.db.session() as s:
            fields = _validate_event_fields(
                s, {"name": name, "event_type": event_type, "date": date, "leader_id": leader_id}
            )
            row = EventRow(**fields)
            s.add(row)
            s.flush()
            event_id = row.id
        _log.info("event %d created (%s, %s)", event_id, event_type, date)
        return self.get(event_id)

    def update(self, event_id: int, **fields) -> Event:
        with self.db.session() as s:
            row = self._load(s, event_id)
            valid = _validate_event_fields(s, fields)
            _check_place_in_field(valid.get("placement", row.placement), valid.get("players", row.players))
            for key, value in valid.items():
                setattr(row, key, value)
        _log.info("event %d updated: %s", event_id, sorted(fields))
        return self.get(event_id)

    def delete(self, event_id: int) -> None:
        with self.db.session() as s:
            s.delete(self._load(s, event_id))
        _log.info("event %d deleted", event_id)

    def add_round(
        self, event_id: int, opponent_leader_id: int | None, kind: str = SWISS, best_of: int | None = None
    ) -> Round:
        """A new last round. A played one gets its empty games (best of 3 in top cut, 1 in Swiss, unless
        `best_of` says); a bye has no opponent and no games."""
        if kind == BYE:
            if opponent_leader_id is not None:
                raise EventError("a bye has no opponent")
            best_of = 1
        elif opponent_leader_id is None:
            raise EventError("a played round needs an opponent")
        best_of = default_best_of(kind) if best_of is None else best_of
        with self.db.session() as s:
            self._load(s, event_id)
            _validate_round_fields(s, {"opponent_leader_id": opponent_leader_id, "kind": kind, "best_of": best_of})
            last = s.scalar(select(func.max(MatchRow.round_no)).where(MatchRow.event_id == event_id)) or 0
            row = MatchRow(event_id=event_id, round_no=last + 1, opponent_leader_id=opponent_leader_id, kind=kind)
            row.games = []
            _set_best_of(row, 0 if kind == BYE else best_of)
            row.best_of = best_of
            s.add(row)
            s.flush()
            result = _to_round(row)
        _log.info("event %d: round %d added (%s, best of %d)", event_id, result.round_no, kind, best_of)
        return result

    def update_round(self, round_id: int, **fields) -> Round:
        """Change a round's opponent, kind, best-of or notes. Swiss <-> top cut also switches the best-of to that
        stage's usual one, unless that would drop games already noted. Making it a bye drops its opponent and
        games; making a bye a played round needs an opponent."""
        with self.db.session() as s:
            row = _load_round(s, round_id)
            valid = dict(_validate_round_fields(s, fields))
            kind = valid.get("kind", row.kind)
            if kind == BYE:
                if valid.get("opponent_leader_id") is not None:
                    raise EventError("a bye has no opponent")
                valid["opponent_leader_id"] = None
                valid.pop("best_of", None)
            elif valid.get("opponent_leader_id", row.opponent_leader_id) is None:
                raise EventError("a played round needs an opponent")
            elif "kind" in valid and "best_of" not in valid and row.kind != BYE:
                usual = default_best_of(kind)
                if not _to_round(row).noted_beyond(usual):
                    valid["best_of"] = usual
            best_of = valid.pop("best_of", None)
            was_bye = row.kind == BYE
            for key, value in valid.items():
                setattr(row, key, value)
            if kind == BYE:
                _set_best_of(row, 0)
                row.best_of = 1
            elif was_bye:
                _set_best_of(row, best_of or default_best_of(kind))
            elif best_of is not None and best_of != row.best_of:
                _set_best_of(row, best_of)
            s.flush()
            s.refresh(row, ["games"])
            result = _to_round(row)
        _log.info("round %d updated: %s", round_id, sorted(fields))
        return result

    def update_game(self, round_id: int, game_no: int, **fields) -> Round:
        """Set one game's result, turn order or who chose it; returns the whole round (its result may change)."""
        with self.db.session() as s:
            row = _load_round(s, round_id)
            if row.kind == BYE:
                raise EventError("a bye has no games")
            if isinstance(game_no, bool) or not isinstance(game_no, int) or not 1 <= game_no <= row.best_of:
                raise EventError(
                    "game {game_no} is not part of a best of {best_of}", game_no=game_no, best_of=row.best_of
                )
            valid = _validate_game_fields(fields)
            game = next((g for g in row.games if g.game_no == game_no), None)
            if game is None:  # rounds stored before their games were created
                game = GameRow(game_no=game_no)
                row.games.append(game)
            for key, value in valid.items():
                setattr(game, key, value)
            s.flush()
            s.refresh(row, ["games"])
            result = _to_round(row)
        _log.info("round %d game %d updated: %s", round_id, game_no, sorted(fields))
        return result

    def delete_round(self, round_id: int) -> None:
        """Delete a round and renumber the later ones so rounds stay 1..n."""
        with self.db.session() as s:
            row = _load_round(s, round_id)
            event_id, removed_no = row.event_id, row.round_no
            s.delete(row)
            s.flush()
            later = s.scalars(
                select(MatchRow)
                .where(MatchRow.event_id == event_id, MatchRow.round_no > removed_no)
                .order_by(MatchRow.round_no)
            )
            for m in later:
                m.round_no -= 1
                s.flush()
        _log.info("round %d deleted from event %d", round_id, event_id)

    def names_of_type(self, event_type: str, exclude_id: int | None = None) -> list[str]:
        """Names of every event of one type (bar `exclude_id`) — what a suggested name is numbered after."""
        with self.db.session() as s:
            query = select(EventRow.name).join(EventRow.event_type).where(EventType.key == event_type)
            if exclude_id is not None:
                query = query.where(EventRow.id != exclude_id)
            return list(s.scalars(query))

    def last_used_leader_id(self) -> int | None:
        """Own leader of the most recent event — the default for a new one."""
        with self.db.session() as s:
            return s.scalar(
                select(EventRow.leader_id)
                .where(EventRow.leader_id.is_not(None))
                .order_by(EventRow.date.desc(), EventRow.id.desc())
                .limit(1)
            )
