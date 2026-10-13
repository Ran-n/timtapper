#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:40.999702
Revised: 2026/10/13 07:39:22.967686

Backup: all events and rounds as one JSON file. Leaders are referenced by
card code (not local DB id), so a backup restores on any install. Restoring
replaces every event in a single transaction, and only after the whole file
has been validated — a bad file never leaves the DB half-imported.
"""

import datetime as dt
import json

from sqlalchemy import delete, select

from catalog.repository import Leader, LeaderRepository
from core.errors import TranslatableError
from core.logging import get_logger
from db import Database
from db.models import COUNT_MAX, EVENT_NAME_MAX, EVENT_TYPES, RESULTS, CardSet, EventType
from db.models import Event as EventRow
from db.models import Game as GameRow
from db.models import Match as MatchRow
from events.domain import BEST_OF, BYE, KINDS, SWISS, TOP_CUT
from events.repository import Event, is_count

_log = get_logger("backup")

FORMAT = "timtapper-backup"
# 2: events carry placement and players. 3: the official event types (no "online"); rounds are Swiss, top cut
# or byes, played as best of 1 or 3 holding their games; events note their set and whether you dropped (an older
# app would misread all of it, so it now says the version is too new instead)
VERSION = 3
READABLE_VERSIONS = (1, 2, VERSION)  # a v1 file restores with placement and players unknown
LEGACY_DRAW = "D"  # v1 files written before draws were dropped may still hold it
LEGACY_EVENT_TYPES = {"online": "other"}  # v1/v2 files: types since dropped, and what they restore as


class BackupError(TranslatableError):
    """The file is not a valid timtapper backup."""


def export_backup(events: list[Event], leaders: dict[int, Leader]) -> bytes:
    def code(leader_id: int | None) -> str | None:
        return leaders[leader_id].code if leader_id is not None else None

    payload = {
        "format": FORMAT,
        "version": VERSION,
        "exported": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "events": [
            {
                "name": ev.name,
                "event_type": ev.event_type,
                "date": ev.date.isoformat(),
                "leader": code(ev.leader_id),
                "notes": ev.notes,
                "placement": ev.placement,
                "players": ev.players,
                "dropped": ev.dropped,
                "set": ev.set_code,
                "rounds": [
                    {
                        "kind": r.kind,
                        "opponent": code(r.opponent_leader_id),  # null for a bye
                        "best_of": r.best_of,
                        "notes": r.notes,
                        # game i is the i-th entry; chose_turn as noted (null in a later game: by the rules)
                        "games": [
                            {"result": g.result, "went_first": g.went_first, "chose_turn": g.chose_turn}
                            for g in r.games
                        ],
                    }
                    for r in ev.rounds
                ],
            }
            for ev in events
        ],
    }
    _log.info("exported %d events", len(events))
    return json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")


def _opt_bool(value, *, msg: str, **where: int) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise BackupError(msg, value=value, **where)


def _opt_count(value, *, msg: str, **where: int) -> int | None:
    if value is None or is_count(value):
        return value
    raise BackupError(msg, value=value, max=COUNT_MAX, **where)


def _str(value, *, msg: str, required: bool = False, **where: int) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise BackupError(msg, value=value, **where)
    return value


def _result(value, *, msg: str, **where: int) -> str | None:
    if value == LEGACY_DRAW:  # backups from before draws were dropped: a draw is a loss for both
        return "L"
    if value not in (*RESULTS, None):
        raise BackupError(msg, value=value, **where)
    return value


def _parse_games(r: dict, i: int, j: int, best_of: int) -> list[dict]:
    games = r.get("games") or []
    if not isinstance(games, list):
        raise BackupError("event {event}, round {round}: the games are not a list", event=i, round=j)
    if len(games) > best_of:
        raise BackupError(
            "event {event}, round {round}: more games than a best of {best_of}", event=i, round=j, best_of=best_of
        )
    parsed = []
    for k, g in enumerate(games, start=1):
        if not isinstance(g, dict):
            raise BackupError("event {event}, round {round}, game {game}: expected an object", event=i, round=j, game=k)
        where = {"event": i, "round": j, "game": k}
        parsed.append({
            "result": _result(
                g.get("result"), msg="event {event}, round {round}, game {game}: invalid result {value!r}", **where
            ),
            "went_first": _opt_bool(
                g.get("went_first"),
                msg="event {event}, round {round}, game {game}: the turn order must be true/false/null, not {value!r}",
                **where,
            ),
            "chose_turn": _opt_bool(
                g.get("chose_turn"),
                msg="event {event}, round {round}, game {game}: "
                "who chose the turn order must be true/false/null, not {value!r}",
                **where,
            ),
        })
    return parsed


def _parse_round(r, i: int, j: int, version: int) -> dict:
    """Round `j` of event `i`, validated. A round from before version 3 is one game, Swiss or top cut as flagged:
    a best of 1 whose die winner chose the turn order. Every message is one whole sentence, so each translates."""
    if not isinstance(r, dict):
        raise BackupError("event {event}, round {round}: expected an object", event=i, round=j)
    if version >= 3:
        kind = r.get("kind", SWISS)
        if kind not in KINDS:
            raise BackupError(
                "event {event}, round {round}: unknown kind of round {value!r}", event=i, round=j, value=kind
            )
        best_of = r.get("best_of", 1)
        if isinstance(best_of, bool) or best_of not in BEST_OF:
            raise BackupError(
                "event {event}, round {round}: best of must be 1 or 3, not {value!r}", event=i, round=j, value=best_of
            )
        if kind == BYE:  # a bye has no games, and is stored as the app stores one: a best of 1
            best_of, games = 1, []
        else:
            games = _parse_games(r, i, j, best_of)
    else:
        top_cut = _opt_bool(
            r.get("top_cut"),
            msg="event {event}, round {round}: the top cut flag must be true/false/null, not {value!r}",
            event=i,
            round=j,
        )
        kind, best_of = (TOP_CUT if top_cut else SWISS), 1
        games = [
            {
                "result": _result(
                    r.get("result"), msg="event {event}, round {round}: invalid result {value!r}", event=i, round=j
                ),
                "went_first": _opt_bool(
                    r.get("went_first"),
                    msg="event {event}, round {round}: the turn order must be true/false/null, not {value!r}",
                    event=i,
                    round=j,
                ),
                "chose_turn": _opt_bool(
                    r.get("won_die_roll"),
                    msg="event {event}, round {round}: the die roll must be true/false/null, not {value!r}",
                    event=i,
                    round=j,
                ),
            }
        ]
    opponent = _str(
        r.get("opponent"),
        msg="event {event}, round {round}: the opponent must be a leader code, not {value!r}",
        required=kind != BYE,
        event=i,
        round=j,
    )
    if kind == BYE and opponent:
        raise BackupError(
            "event {event}, round {round}: a bye has no opponent, not {value!r}", event=i, round=j, value=opponent
        )
    return {
        "kind": kind,
        "opponent": opponent or None,
        "best_of": best_of,
        "games": games,
        "notes": _str(
            r.get("notes"), msg="event {event}, round {round}: the notes must be text, not {value!r}", event=i, round=j
        ),
    }


def _parse_event(ev, i: int, version: int) -> dict:
    """Event `i` (counting from 1) and its rounds, validated."""
    if not isinstance(ev, dict):
        raise BackupError("event {event}: expected an object", event=i)
    raw_type = ev.get("event_type")
    # not a string (a list or object can't even be looked up): no event type at all
    event_type = LEGACY_EVENT_TYPES.get(raw_type, raw_type) if isinstance(raw_type, str) else None
    if event_type not in EVENT_TYPES:
        raise BackupError("event {event}: unknown event type {value!r}", event=i, value=raw_type)
    try:
        date = dt.date.fromisoformat(ev.get("date") or "")
    except (TypeError, ValueError) as exc:
        raise BackupError("event {event}: invalid date {value!r}", event=i, value=ev.get("date")) from exc
    rounds = ev.get("rounds") or []
    if not isinstance(rounds, list):
        raise BackupError("event {event}: the rounds are not a list", event=i)
    parsed_rounds = [_parse_round(r, i, j, version) for j, r in enumerate(rounds, start=1)]
    placement = _opt_count(
        ev.get("placement"),
        msg="event {event}: the placement must be a whole number from 1 to {max}, not {value!r}",
        event=i,
    )
    players = _opt_count(
        ev.get("players"),
        msg="event {event}: the players must be a whole number from 1 to {max}, not {value!r}",
        event=i,
    )
    if placement is not None and players is not None and placement > players:
        raise BackupError(
            "event {event}: placement {placement} is past the {players} players",
            event=i,
            placement=placement,
            players=players,
        )
    name = _str(
        ev.get("name"), msg="event {event}: the name must be text, not {value!r}", required=True, event=i
    ).strip()
    if len(name) > EVENT_NAME_MAX:
        raise BackupError("event {event}: the name is longer than {max} characters", event=i, max=EVENT_NAME_MAX)
    leader = _str(ev.get("leader"), msg="event {event}: the leader must be a leader code, not {value!r}", event=i)
    return {
        "name": name,
        "event_type": event_type,
        "date": date,
        "leader": leader or None,
        "notes": _str(ev.get("notes"), msg="event {event}: the notes must be text, not {value!r}", event=i),
        "placement": placement,
        "players": players,
        "dropped": bool(
            _opt_bool(ev.get("dropped"), msg="event {event}: dropped must be true/false/null, not {value!r}", event=i)
        ),
        "set": _str(ev.get("set"), msg="event {event}: the set must be a set code, not {value!r}", event=i) or None,
        "rounds": parsed_rounds,
    }


def parse_backup(data: bytes) -> list[dict]:
    """Validate a backup file and return its events. Raises BackupError, saying which event and round are wrong."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("not a JSON file: {error}", error=str(exc)) from exc
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise BackupError("not a timtapper backup")
    version = payload.get("version")
    # a bool is no version, though true == 1 would let it through as one
    if isinstance(version, bool) or version not in READABLE_VERSIONS:
        raise BackupError("unsupported backup version {version!r}", version=version)
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise BackupError("the events are not a list")
    return [_parse_event(ev, i, version) for i, ev in enumerate(raw_events, start=1)]


def _set_id(s, code: str | None) -> int | None:
    """The set's id, adding the set when this install doesn't know it yet (a backup from a newer catalogue)."""
    if code is None:
        return None
    card_set = s.scalar(select(CardSet).where(CardSet.code == code))
    if card_set is None:
        _log.warning("unknown set %s in the backup — adding it", code)
        card_set = CardSet(code=code)
        s.add(card_set)
        s.flush()
    return card_set.id


def import_backup(db: Database, data: bytes) -> int:
    """Replace all events with the backup's. Returns the number of events restored."""
    events = parse_backup(data)
    leaders = LeaderRepository(db)
    with db.session() as s:
        type_ids = {t.key: t.id for t in s.scalars(select(EventType))}
        s.execute(delete(GameRow))
        s.execute(delete(MatchRow))
        s.execute(delete(EventRow))
        for ev in events:
            row = EventRow(
                name=ev["name"],
                event_type_id=type_ids[ev["event_type"]],
                date=ev["date"],
                leader_id=leaders.ensure(s, ev["leader"]).id if ev["leader"] else None,
                notes=ev["notes"],
                placement=ev["placement"],
                players=ev["players"],
                dropped=ev["dropped"],
                set_id=_set_id(s, ev["set"]),
            )
            s.add(row)
            s.flush()
            for no, r in enumerate(ev["rounds"], start=1):
                played = {k: g for k, g in enumerate(r["games"], start=1)}
                s.add(
                    MatchRow(
                        event_id=row.id,
                        round_no=no,
                        kind=r["kind"],
                        opponent_leader_id=leaders.ensure(s, r["opponent"]).id if r["opponent"] else None,
                        best_of=r["best_of"],
                        notes=r["notes"],
                        # every game of the best-of exists, as the app keeps them; ones the file lacks stay empty
                        games=[]
                        if r["kind"] == BYE
                        else [GameRow(game_no=k, **played.get(k, {})) for k in range(1, r["best_of"] + 1)],
                    )
                )
    _log.info("restored %d events from backup", len(events))
    return len(events)
