#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 15:13:48.809406
Revised: 2026/10/12 23:54:36.964055

The backup file format, pinned. Backups outlive app versions: a file written today must
restore after any update, so the exact shape of the current file is checked in (golden/v3.json)
and every change to it fails here, while every older pinned file (golden/v1.json, v2.json) must
still restore. Changing the format means bumping VERSION, pinning the new file and keeping the old one.
"""

import datetime as dt
import json
from pathlib import Path

import pytest

from backup.json_backup import VERSION, export_backup, import_backup, parse_backup
from catalog.repository import Leader
from events.repository import Event, Game, Round

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN = GOLDEN_DIR / "v3.json"  # what this version writes
GOLDEN_V2 = GOLDEN_DIR / "v2.json"  # written while "online" was an event type: must still restore
GOLDEN_V1 = GOLDEN_DIR / "v1.json"  # written before placement and players: must still restore

LEADERS = {
    1: Leader(1, "OP01-001", "Roronoa Zoro", "OP01", ("Red",)),
    2: Leader(2, "OP01-060", "Donquixote Doflamingo", "OP01", ("Blue",)),
    3: Leader(3, "ST01-001", "Monkey.D.Luffy", "ST01", ("Red",)),
}
EVENTS = [
    Event(
        7,
        "Sunday locals",
        "locals",
        dt.date(2026, 10, 5),
        1,
        "Swiss, 3 rounds + top 4 ✓",
        (
            Round.single_game(70, 1, 2, "W", True, True, False, "tempo"),
            Round.single_game(71, 2, 3, "L", False, None, False, ""),
            Round.single_game(72, 3, 2, None, None, None, True, ""),
        ),
        placement=3,
        players=32,
        set_code="OP16",
    ),
    Event(
        8,
        "Heroines practice",
        "heroines_battle",
        dt.date(2026, 10, 6),
        None,
        dropped=True,
        rounds=(  # a best of 3 won 2-1: game 3's chooser overridden, game 2's left to the rules
            Round(73, 1, 3, 3, "top_cut", "", (Game(1, "L", True, True), Game(2, "W"), Game(3, "W", False, False))),
            Round(74, 2, None, 1, "bye"),
        ),
    ),
]


def exported() -> dict:
    payload = json.loads(export_backup(EVENTS, LEADERS))
    payload.pop("exported")  # the export time is the one field that legitimately differs
    return payload


def golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_export_matches_the_pinned_v3_file():
    assert VERSION == 3
    assert exported() == golden()


def test_pinned_v3_file_keeps_placement_and_players():
    events = parse_backup(GOLDEN.read_bytes())
    assert [(e["placement"], e["players"]) for e in events] == [(3, 32), (None, None)]


def test_pinned_v1_file_restores_with_placement_unknown(events):
    assert import_backup(events.db, GOLDEN_V1.read_bytes()) == 2
    assert {(e.placement, e.players) for e in events.list()} == {(None, None)}


def test_export_writes_utf8_and_keeps_non_ascii_readable():
    raw = export_backup(EVENTS, LEADERS)
    assert "✓".encode() in raw  # not escaped to \u2713


def test_pinned_v1_file_still_parses_to_the_same_events():
    events = parse_backup(GOLDEN_V1.read_bytes())
    assert [(e["name"], e["event_type"], e["date"], e["leader"]) for e in events] == [
        ("Sunday locals", "locals", dt.date(2026, 10, 5), "OP01-001"),
        ("Online practice", "other", dt.date(2026, 10, 6), None),  # "online" is no event type any more
    ]
    assert events[0]["rounds"][0] == {  # one game, as every round was before best of 3
        "opponent": "OP01-060",
        "kind": "swiss",
        "best_of": 1,
        "games": [{"result": "W", "went_first": True, "chose_turn": True}],
        "notes": "tempo",
    }
    assert [r["kind"] for r in events[0]["rounds"]] == ["swiss", "swiss", "top_cut"]


def test_pinned_v3_file_restores_into_a_fresh_install(events, leaders):
    assert import_backup(events.db, GOLDEN.read_bytes()) == 2
    by_code = {ld.code: ld.id for ld in leaders.all()}
    restored = {e.name: e for e in events.list()}
    locals_ = restored["Sunday locals"]
    assert locals_.leader_id == by_code["OP01-001"]
    assert [(r.round_no, r.opponent_leader_id, r.result) for r in locals_.rounds] == [
        (1, by_code["OP01-060"], "W"),
        (2, by_code["ST01-001"], "L"),
        (3, by_code["OP01-060"], None),
    ]
    assert (locals_.set_code, locals_.dropped) == ("OP16", False)
    heroines = restored["Heroines practice"]
    assert (heroines.set_code, heroines.dropped) == (None, True)
    assert heroines.event_type == "heroines_battle" and heroines.leader_id is None
    bo3, bye = heroines.rounds
    assert (bye.kind, bye.result, bye.opponent_leader_id) == ("bye", "W", None)
    assert (bo3.best_of, bo3.top_cut, bo3.result, bo3.opponent_leader_id) == (3, True, "W", by_code["ST01-001"])
    assert [(g.result, g.went_first, g.chose_turn) for g in bo3.games] == [
        ("L", True, True),
        ("W", None, None),
        ("W", False, False),
    ]


@pytest.mark.regression
def test_pinned_v2_file_restores_its_online_event_as_other(events):
    """ "online" was dropped as an event type: a v2 backup holding one must still restore, as "other"."""
    assert import_backup(events.db, GOLDEN_V2.read_bytes()) == 2
    restored = {e.name: e for e in events.list()}
    assert restored["Online practice"].event_type == "other"
    assert (restored["Sunday locals"].placement, restored["Sunday locals"].players) == (3, 32)
