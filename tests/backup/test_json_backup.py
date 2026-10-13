#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.944166
Revised: 2026/10/13 07:39:27.073612
"""

import contextlib
import dataclasses
import datetime as dt
import json
from dataclasses import astuple

import pytest
from hypothesis import given
from hypothesis import strategies as st

from backup.json_backup import FORMAT, VERSION, BackupError, export_backup, import_backup, parse_backup
from catalog.repository import Leader
from db.models import COUNT_MAX, EVENT_TYPES
from events.domain import BEST_OF
from events.repository import Event, Game, Round


def comparable(evs):
    """Everything but database ids, which differ after a restore."""
    return [(e.name, e.event_type, e.date, e.leader_id, e.notes, [astuple(r)[1:] for r in e.rounds]) for e in evs]


def dump(events, leaders):
    return export_backup(events.list(), {ld.id: ld for ld in leaders.all()})


def test_roundtrip_restores_everything(events, leaders, sample_event):
    events.update(sample_event.id, notes="note ✓")
    events.update_round(sample_event.rounds[0].id, kind="top_cut", notes="r1")
    before = events.list()
    data = dump(events, leaders)
    events.create("to be replaced", "treasure_cup", dt.date(2026, 1, 1))

    assert import_backup(events.db, data) == 1
    after = events.list()
    assert comparable(after) == comparable(before)


def test_export_uses_codes_not_ids(events, leaders, sample_event):
    payload = json.loads(dump(events, leaders))
    assert payload["format"] == FORMAT and payload["version"] == VERSION
    first = payload["events"][0]
    by_id = {ld.id: ld for ld in leaders.all()}
    assert first["leader"] == by_id[sample_event.leader_id].code
    assert first["rounds"][0]["opponent"] == by_id[sample_event.rounds[0].opponent_leader_id].code


def test_import_creates_placeholders_for_unknown_leaders(events, leaders):
    data = json.dumps({
        "format": FORMAT,
        "version": VERSION,
        "events": [
            {
                "name": "Future",
                "event_type": "locals",
                "date": "2027-01-01",
                "leader": "OP99-001",
                "rounds": [{"opponent": "OP99-002", "result": "W"}],
            }
        ],
    }).encode()
    assert import_backup(events.db, data) == 1
    codes = {ld.code for ld in leaders.all()}
    assert {"OP99-001", "OP99-002"} <= codes


def valid_event(**over):
    return {"name": "x", "event_type": "locals", "date": "2026-01-01", "rounds": []} | over


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"\xff\xfe", "not a JSON file"),
        (b"{nope", "not a JSON file"),
        (json.dumps([1, 2]).encode(), "not a timtapper backup"),
        (json.dumps({"format": "other"}).encode(), "not a timtapper backup"),
        (json.dumps({"format": FORMAT, "version": 99}).encode(), "unsupported backup version"),
        # regression: true == 1, so a file saying "version": true was read as a version 1 backup
        (json.dumps({"format": FORMAT, "version": True, "events": []}).encode(), "unsupported backup version"),
        (json.dumps({"format": FORMAT, "version": "3", "events": []}).encode(), "unsupported backup version"),
        (json.dumps({"format": FORMAT, "version": VERSION, "events": {}}).encode(), "not a list"),
    ],
)
def test_parse_rejects_bad_files(payload, message):
    with pytest.raises(BackupError, match=message):
        parse_backup(payload)


@pytest.mark.parametrize(
    ("event", "message"),
    [
        ("nope", "expected an object"),
        (valid_event(event_type="moon_cup"), "unknown event type"),
        # regression: a list or object here can't be looked up, and raised TypeError instead of BackupError
        (valid_event(event_type=["locals"]), "unknown event type"),
        (valid_event(event_type={"key": "locals"}), "unknown event type"),
        (valid_event(date="yesterday"), "invalid date"),
        (valid_event(date=None), "invalid date"),
        (valid_event(name=""), "name"),
        (valid_event(rounds="x"), "rounds are not a list"),
        (valid_event(rounds=["x"]), "expected an object"),
        (valid_event(rounds=[{"opponent": "OP01-001", "games": [{"result": "X"}]}]), "game 1: invalid result"),
        (valid_event(rounds=[{"opponent": "OP01-001", "best_of": 2}]), "best of must be 1 or 3"),
        (valid_event(rounds=[{"opponent": "OP01-001", "best_of": True}]), "best of must be 1 or 3"),
        (valid_event(rounds=[{"opponent": "OP01-001", "games": "x"}]), "games are not a list"),
        (valid_event(rounds=[{"opponent": "OP01-001", "games": [{}, {}]}]), "more games than a best of 1"),
        (valid_event(rounds=[{"opponent": "OP01-001", "games": ["x"]}]), "game 1: expected an object"),
        (
            valid_event(rounds=[{"opponent": "OP01-001", "games": [{"chose_turn": "me"}]}]),
            "who chose the turn order must be true/false/null",
        ),
        (valid_event(rounds=[{"result": "W"}]), "opponent"),
        (
            valid_event(rounds=[{"opponent": "OP01-001", "games": [{"went_first": "yes"}]}]),
            "game 1: the turn order must be true/false/null",
        ),
        (valid_event(rounds=[{"opponent": "OP01-001", "kind": "final"}]), "unknown kind of round"),
        (valid_event(rounds=[{"kind": "bye", "opponent": "OP01-001"}]), "a bye has no opponent"),
        (valid_event(dropped="yes"), "dropped must be true/false/null"),
        (valid_event(set=16), "the set must be a set code"),
        (valid_event(rounds=[{"opponent": "OP01-001", "notes": 5}]), "round 1: the notes must be text"),
        (valid_event(leader=7), "leader must be a leader code"),
        (valid_event(notes=3), "notes"),
        (valid_event(name="x" * 121), "longer than 120"),
    ],
)
def test_parse_rejects_bad_events(event, message):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [event]}).encode()
    with pytest.raises(BackupError, match=message):
        parse_backup(data)


def test_invalid_backup_leaves_data_untouched(events, sample_event):
    bad = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(), "broken"]}).encode()
    with pytest.raises(BackupError):
        import_backup(events.db, bad)
    assert [e.id for e in events.list()] == [sample_event.id]


def test_empty_backup_clears_events(events, sample_event):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": []}).encode()
    assert import_backup(events.db, data) == 0
    assert events.list() == []


# ---- properties ------------------------------------------------------------------
codes = st.from_regex(r"[A-Z]{1,4}\d{0,2}-\d{3}", fullmatch=True)
texts_ = st.text(max_size=40)
tristate = st.sampled_from([None, True, False])
games_st = st.builds(Game, st.just(0), st.sampled_from([None, "W", "L"]), tristate, tristate)
played_st = st.sampled_from(BEST_OF).flatmap(
    lambda best_of: st.builds(
        Round,
        st.just(0),
        st.just(0),
        st.integers(1, 5),
        st.just(best_of),
        st.sampled_from(["swiss", "top_cut"]),
        texts_,
        st.lists(games_st, min_size=best_of, max_size=best_of).map(
            lambda gs: tuple(dataclasses.replace(g, game_no=n) for n, g in enumerate(gs, start=1))
        ),
    )
)
byes_st = st.builds(Round, st.just(0), st.just(0), st.none(), st.just(1), st.just("bye"), texts_)
rounds_st = st.one_of(played_st, byes_st)
events_st = st.builds(
    Event,
    st.just(0),
    st.text(min_size=1, max_size=40).filter(lambda s: s.strip() == s and s),
    st.sampled_from(sorted(EVENT_TYPES)),
    st.dates(dt.date(2000, 1, 1), dt.date(2100, 12, 31)),
    st.one_of(st.none(), st.integers(1, 5)),
    texts_,
    st.lists(rounds_st, max_size=6).map(tuple),
)
# placement within the field when both are known
standings = st.one_of(st.none(), st.integers(1, 512)).flatmap(
    lambda players: st.tuples(
        st.one_of(st.none(), st.integers(1, players or 512)),
        st.just(players),
    )
)
events_st = st.tuples(events_st, standings).map(
    lambda pair: dataclasses.replace(pair[0], placement=pair[1][0], players=pair[1][1])
)


@pytest.mark.property
@given(st.lists(events_st, max_size=5), st.lists(codes, min_size=5, max_size=5, unique=True))
def test_property_export_then_parse_returns_what_was_exported(evs, leader_codes):
    leaders = {i + 1: Leader(i + 1, code, code, None, ()) for i, code in enumerate(leader_codes)}
    parsed = parse_backup(export_backup(evs, leaders))
    assert len(parsed) == len(evs)
    for ev, back in zip(evs, parsed, strict=True):
        assert (back["name"], back["event_type"], back["date"], back["notes"]) == (
            ev.name,
            ev.event_type,
            ev.date,
            ev.notes,
        )
        assert (back["placement"], back["players"]) == (ev.placement, ev.players)
        assert back["leader"] == (leaders[ev.leader_id].code if ev.leader_id else None)
        assert back["rounds"] == [
            {
                "opponent": leaders[r.opponent_leader_id].code if r.opponent_leader_id else None,
                "best_of": r.best_of,
                "games": [
                    {"result": g.result, "went_first": g.went_first, "chose_turn": g.chose_turn} for g in r.games
                ],
                "kind": r.kind,
                "notes": r.notes,
            }
            for r in ev.rounds
        ]


@pytest.mark.property
@given(st.binary(max_size=200))
def test_property_parse_never_crashes_on_garbage(data):
    """Any file the user picks either parses or raises BackupError: never anything else."""
    with contextlib.suppress(BackupError):  # the only failure allowed
        parse_backup(data)


@pytest.mark.property
@given(
    st.recursive(
        st.none() | st.booleans() | st.integers() | st.text(max_size=5),
        lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=8), c, max_size=3),
        max_leaves=12,
    )
)
def test_property_parse_rejects_wrong_shapes_cleanly(events_value):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [events_value]}).encode()
    with contextlib.suppress(BackupError):  # the only failure allowed
        parse_backup(data)


JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=5),
    lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=8), c, max_size=3),
    max_leaves=8,
)
EVENT_KEYS = ("name", "event_type", "date", "leader", "notes", "placement", "players", "dropped", "set", "rounds")
ROUND_KEYS = ("kind", "opponent", "best_of", "notes", "games")


@pytest.mark.property
@given(st.sampled_from(EVENT_KEYS), JSON_VALUES)
def test_property_any_event_field_value_parses_or_is_rejected_cleanly(key, value):
    """Every field of an otherwise valid event, set to any JSON value: parsed, or a BackupError — never a crash."""
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(**{key: value})]}).encode()
    with contextlib.suppress(BackupError):
        parse_backup(data)


@pytest.mark.property
@given(st.sampled_from(ROUND_KEYS), JSON_VALUES)
def test_property_any_round_field_value_parses_or_is_rejected_cleanly(key, value):
    round_ = {"opponent": "OP01-001", "games": [{"result": "W"}]} | {key: value}
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(rounds=[round_])]}).encode()
    with contextlib.suppress(BackupError):
        parse_backup(data)


@pytest.mark.regression
def test_old_backups_with_draws_restore_them_as_losses():
    """v1 backups written before draws were dropped may hold "D": a draw is a loss for both players."""
    event = valid_event(rounds=[{"opponent": "OP01-001", "result": "D"}, {"opponent": "OP01-001", "result": "W"}])
    data = json.dumps({"format": FORMAT, "version": 1, "events": [event]}).encode()
    assert [r["games"][0]["result"] for r in parse_backup(data)[0]["rounds"]] == ["L", "W"]


def test_rounds_before_v3_are_one_game_whose_die_winner_chose():
    old = {"opponent": "OP01-001", "result": "W", "went_first": False, "won_die_roll": True, "top_cut": True}
    data = json.dumps({"format": FORMAT, "version": 2, "events": [valid_event(rounds=[old])]}).encode()
    (r,) = parse_backup(data)[0]["rounds"]
    assert r["best_of"] == 1 and r["kind"] == "top_cut"
    assert r["games"] == [{"result": "W", "went_first": False, "chose_turn": True}]


@pytest.mark.parametrize(
    ("round_", "message"),
    [
        ({"opponent": "OP01-001", "result": "X"}, "round 1: invalid result"),
        ({"opponent": "OP01-001", "went_first": "yes"}, "round 1: the turn order must be true/false/null"),
        ({"opponent": "OP01-001", "won_die_roll": 1}, "round 1: the die roll must be true/false/null"),
    ],
)
def test_v2_rounds_are_checked_as_they_were_written(round_, message):
    data = json.dumps({"format": FORMAT, "version": 2, "events": [valid_event(rounds=[round_])]}).encode()
    with pytest.raises(BackupError, match=message):
        parse_backup(data)


def test_a_best_of_3_restores_with_its_games(events, leaders):
    games = [{"result": "L"}, {"result": "W", "went_first": True}, {"result": "W", "chose_turn": False}]
    bo3 = {"opponent": "OP01-001", "kind": "top_cut", "best_of": 3, "games": games}
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(rounds=[bo3])]}).encode()
    assert import_backup(events.db, data) == 1
    (r,) = events.list()[0].rounds
    assert (r.best_of, r.result, r.wins, r.losses) == (3, "W", 2, 1)
    assert r.chose_turn(2) is True and r.chose_turn(3) is False  # 3: noted override, not the rule (W -> they chose)


def test_a_best_of_3_with_fewer_games_gets_empty_ones(events):
    bo3 = {"opponent": "OP01-001", "best_of": 3, "games": [{"result": "W"}]}
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(rounds=[bo3])]}).encode()
    import_backup(events.db, data)
    (r,) = events.list()[0].rounds
    assert [g.game_no for g in r.games] == [1, 2, 3] and r.result is None


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"placement": 0}, "placement must be a whole number"),
        ({"players": "32"}, "players must be a whole number"),
        ({"placement": True}, "placement must be a whole number"),
        ({"players": COUNT_MAX + 1}, f"players must be a whole number from 1 to {COUNT_MAX}"),
        # regression: past SQLite's 64-bit integers, the restore crashed with OverflowError instead of saying why
        ({"players": 10**20}, "players must be a whole number"),
        ({"placement": 9, "players": 8}, "past the 8 players"),
    ],
)
def test_parse_rejects_impossible_placements(over, message):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(**over)]}).encode()
    with pytest.raises(BackupError, match=message):
        parse_backup(data)


def test_v1_files_are_still_read():
    data = json.dumps({"format": FORMAT, "version": 1, "events": [valid_event()]}).encode()
    assert parse_backup(data)[0]["placement"] is None


def test_backup_errors_name_the_event_and_round_and_translate():
    from i18n import translator

    bad = {"opponent": "OP01-001", "best_of": 3, "games": [{"result": "W"}, {"result": "X"}]}
    event = valid_event(rounds=[{"opponent": "OP01-001"}, bad])
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(), event]}).encode()
    with pytest.raises(BackupError) as caught:
        parse_backup(data)
    assert str(caught.value) == "event 2, round 2, game 2: invalid result 'X'"
    assert caught.value.translated(translator("es")) == "evento 2, ronda 2, partida 2: resultado no válido 'X'"


def test_a_bye_and_the_events_set_and_dropped_restore(events, leaders):
    ev = valid_event(
        set="OP16", dropped=True, rounds=[{"kind": "bye"}, {"opponent": "OP01-001", "games": [{"result": "W"}]}]
    )
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [ev]}).encode()
    import_backup(events.db, data)
    (restored,) = events.list()
    assert (restored.set_code, restored.dropped) == ("OP16", True)
    assert [(r.kind, r.result) for r in restored.rounds] == [("bye", "W"), ("swiss", "W")]


def test_a_bye_restores_as_a_best_of_1_whatever_the_file_says(events):
    """The app stores every bye as a best of 1 with no games; a file saying 3 mustn't leave a bye unlike the others."""
    data = json.dumps({
        "format": FORMAT,
        "version": VERSION,
        "events": [valid_event(rounds=[{"kind": "bye", "best_of": 3}])],
    })
    import_backup(events.db, data.encode())
    (bye,) = events.list()[0].rounds
    assert (bye.kind, bye.best_of, bye.games) == ("bye", 1, ())


def test_a_set_this_install_doesnt_know_is_added(events, caplog):
    data = json.dumps({"format": FORMAT, "version": VERSION, "events": [valid_event(set="OP99")]}).encode()
    import_backup(events.db, data)
    assert events.list()[0].set_code == "OP99"
    assert "unknown set OP99" in caplog.text
