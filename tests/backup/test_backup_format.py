#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 15:13:48.809406
Revised: 2026/10/12 16:55:02.782442

The backup file format, pinned. Backups outlive app versions: a file written today must
restore after any update, so the exact shape of the current file is checked in (golden/v2.json)
and every change to it fails here, while every older pinned file (golden/v1.json) must still
restore. Changing the format means bumping VERSION, pinning the new file and keeping the old one.
"""

import datetime as dt
import json
from pathlib import Path

from backup.json_backup import VERSION, export_backup, import_backup, parse_backup
from catalog.repository import Leader
from events.repository import Event, Round

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN = GOLDEN_DIR / "v2.json"  # what this version writes
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
            Round(70, 1, 2, "W", True, True, False, "tempo"),
            Round(71, 2, 3, "L", False, None, False, ""),
            Round(72, 3, 2, None, None, None, True, ""),
        ),
        placement=3,
        players=32,
    ),
    Event(8, "Online practice", "online", dt.date(2026, 10, 6), None),
]


def exported() -> dict:
    payload = json.loads(export_backup(EVENTS, LEADERS))
    payload.pop("exported")  # the export time is the one field that legitimately differs
    return payload


def golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_export_matches_the_pinned_v2_file():
    assert VERSION == 2
    assert exported() == golden()


def test_pinned_v2_file_keeps_placement_and_players():
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
        ("Online practice", "online", dt.date(2026, 10, 6), None),
    ]
    assert events[0]["rounds"][0] == {
        "opponent": "OP01-060",
        "result": "W",
        "went_first": True,
        "won_die_roll": True,
        "top_cut": False,
        "notes": "tempo",
    }
    assert [r["top_cut"] for r in events[0]["rounds"]] == [False, False, True]


def test_pinned_v2_file_restores_into_a_fresh_install(events, leaders):
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
    assert restored["Online practice"].leader_id is None and restored["Online practice"].rounds == ()
