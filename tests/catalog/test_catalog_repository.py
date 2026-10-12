#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.019766
Revised: 2026/10/12 16:54:59.869355
"""

import datetime as dt

import pytest

from catalog.optcgapi import LeaderRecord
from catalog.repository import (
    BUNDLED_LEADERS,
    Leader,
    LeaderRepository,
    filter_leaders,
    load_bundled,
    load_bundled_sources,
    search,
    set_codes,
)


def test_bundled_catalogue_is_sane():
    records = load_bundled()
    codes = [r.code for r in records]
    assert len(records) > 100
    assert len(codes) == len(set(codes))
    assert all(r.colors for r in records)
    assert BUNDLED_LEADERS.exists()


def test_bundled_sources_list_every_set_once():
    sources = load_bundled_sources()
    assert list(sources) == sorted(set(sources))
    assert {"OP-01", "ST-01"} <= set(sources)


def test_bundled_sources_missing_key(tmp_path):
    old = tmp_path / "leaders.json"
    old.write_text('{"generated": "2026-01-01", "leaders": []}', encoding="utf-8")
    assert load_bundled_sources(old) == ()


def test_upsert_is_idempotent(seeded_db):
    repo = LeaderRepository(seeded_db)
    n = repo.count()
    assert n == len(load_bundled())
    assert repo.upsert(load_bundled()) == (0, 0)
    assert repo.count() == n


def test_upsert_adds_and_updates(db):
    repo = LeaderRepository(db)
    assert repo.upsert([LeaderRecord("OP99-001", "Old", "OP99", "Future", ("Red",))]) == (1, 0)
    assert repo.upsert([
        LeaderRecord("OP99-001", "New", "OP99", "Future set", ("Blue", "Red")),
        LeaderRecord("OP99-002", "Other", "OP99", "Future set", ("Black",)),
    ]) == (1, 1)
    by_code = {ld.code: ld for ld in repo.all()}
    assert by_code["OP99-001"].name == "New"
    assert by_code["OP99-001"].colors == ("Red", "Blue")  # official color order, not source order
    assert by_code["OP99-001"].set_code == "OP99"


def test_ensure_creates_placeholder_for_unknown_code(seeded_db):
    repo = LeaderRepository(seeded_db)
    with seeded_db.session() as s:
        row = repo.ensure(s, "OP99-123")
        assert row.name == "OP99-123"
    with seeded_db.session() as s:
        assert repo.ensure(s, "OP99-123").id == row.id


def test_all_orders_most_played_opponents_first(events, leaders, leader_ids):
    ev = events.create("t", "testing", dt.date(2026, 1, 1))
    for _ in range(2):
        events.add_round(ev.id, leader_ids[5])
    events.add_round(ev.id, leader_ids[4])
    ordered = [ld.id for ld in leaders.all()]
    assert ordered[:2] == [leader_ids[5], leader_ids[4]]


def test_leader_label_and_image():
    leader = Leader(1, "OP01-001", "Zoro", "OP01", ("Red",))
    assert leader.label == "Zoro · OP01-001"
    assert leader.image_url.endswith("/OP01-001.jpg")


def test_search():
    pool = [
        Leader(1, "OP01-001", "Roronoa Zoro", "OP01", ("Red",)),
        Leader(2, "OP01-003", "Monkey.D.Luffy", "OP01", ("Red", "Green")),
        Leader(3, "ST10-002", "Monkey.D.Luffy", "ST10", ("Red", "Purple")),
    ]
    assert search(pool, "") == pool
    assert [ld.id for ld in search(pool, "luffy")] == [2, 3]
    assert [ld.id for ld in search(pool, "luffy purple")] == [3]
    assert [ld.id for ld in search(pool, "op01-001")] == [1]
    assert search(pool, "nami") == []


# ---- picker filters ---------------------------------------------------------------
FILTER_POOL = [
    Leader(1, "OP01-001", "Roronoa Zoro", "OP01", ("Red",)),
    Leader(2, "OP01-003", "Monkey.D.Luffy", "OP01", ("Red", "Green")),
    Leader(3, "ST10-002", "Monkey.D.Luffy", "ST10", ("Red", "Purple")),
    Leader(4, "OP09-001", "Shanks", "OP09", ("Red",)),
    Leader(5, "XX-1", "Placeholder", None, ("Green",)),
]


def test_filter_by_one_color():
    assert [ld.id for ld in filter_leaders(FILTER_POOL, "", frozenset({"Green"}))] == [2, 5]


def test_filter_by_two_colors_is_and():
    assert [ld.id for ld in filter_leaders(FILTER_POOL, "", frozenset({"Red", "Green"}))] == [2]


def test_filter_by_set():
    assert [ld.id for ld in filter_leaders(FILTER_POOL, "", set_code="OP01")] == [1, 2]
    assert all(ld.set_code is not None for ld in filter_leaders(FILTER_POOL, "", set_code="XX"))
    assert filter_leaders(FILTER_POOL, "", set_code="XX") == []


def test_filter_combines_query_colors_and_set():
    assert [ld.id for ld in filter_leaders(FILTER_POOL, "luffy", frozenset({"Red"}), "ST10")] == [3]
    assert filter_leaders(FILTER_POOL, "zoro", frozenset({"Green"}), "OP01") == []


def test_filter_with_nothing_selected_equals_search():
    for query in ("", "luffy", "red", "nami"):
        assert filter_leaders(FILTER_POOL, query) == search(FILTER_POOL, query)


def test_filter_keeps_order():
    reordered = list(reversed(FILTER_POOL))
    assert [ld.id for ld in filter_leaders(reordered, "", frozenset({"Red"}))] == [4, 3, 2, 1]


def test_set_codes_order():
    codes = ["OP01", "XYZ", "ST30", "PRB01", "OP17", "EB04", "ST01", "EB01", "PRB02", "AB2", None, "OP17"]
    pool = [Leader(i, f"C{i}", "n", code, ()) for i, code in enumerate(codes)]
    assert set_codes(pool) == ["OP17", "OP01", "EB04", "EB01", "ST30", "ST01", "PRB02", "PRB01", "AB2", "XYZ"]


def test_set_codes_of_bundled_catalogue_starts_with_newest_main_set(leaders):
    codes = set_codes(leaders.all())
    op = [c for c in codes if c.startswith("OP")]
    assert codes[0] == op[0] and op == sorted(op, key=lambda c: -int(c[2:]))


@pytest.mark.parametrize(
    ("name", "short"),
    [
        ("Donquixote Doflamingo", "Doflamingo"),
        ('Eustass"Captain"Kid', "Kid"),
        ("Donquixote Rosinante", "Donquixote Rosinante"),  # only the names players shorten
        ("Shanks", "Shanks"),
    ],
)
def test_short_name_is_what_players_call_the_leader(name, short):
    assert Leader(1, "OP01-060", name, "OP01", ("Blue",)).short_name == short


def test_catalogue_keeps_the_full_names(leaders):
    names = {ld.name for ld in leaders.all()}
    assert {"Donquixote Doflamingo", 'Eustass"Captain"Kid'} <= names
