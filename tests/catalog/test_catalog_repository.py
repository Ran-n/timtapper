#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.019766
Revised: 2026/10/14 07:43:51.549755
"""

import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from catalog.optcgapi import LeaderRecord
from catalog.repository import (
    BUNDLED_LEADERS,
    Leader,
    LeaderRepository,
    filter_leaders,
    install_bundled,
    is_main_set,
    load_bundled,
    load_bundled_releases,
    load_bundled_sources,
    search,
    set_codes,
    set_on,
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


def test_leader_label():
    leader = Leader(1, "OP01-001", "Zoro", "OP01", ("Red",))
    assert leader.label == "Zoro · OP01-001"


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


# ---- release dates and the set an event is played in ---------------------------------
def test_bundled_releases_missing_key(tmp_path):
    old = tmp_path / "leaders.json"
    old.write_text('{"generated": "2026-01-01", "leaders": []}', encoding="utf-8")
    assert load_bundled_releases(old) == {}


def test_install_bundled_stores_leaders_and_release_dates(db):
    repo = LeaderRepository(db)
    install_bundled(repo)
    assert repo.count() == len(load_bundled())
    assert repo.release_dates() == load_bundled_releases()


def test_install_bundled_reads_the_list_once(db, monkeypatch):
    """It runs on every start: the list used to be read and parsed twice, once for the leaders and once for the
    release dates."""
    reads = []
    real_read = type(BUNDLED_LEADERS).read_text

    def counted(self, *args, **kwargs):
        reads.append(self)
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(type(BUNDLED_LEADERS), "read_text", counted)
    install_bundled(LeaderRepository(db))
    assert reads == [BUNDLED_LEADERS]


def test_set_releases_adds_updates_and_keeps(db):
    repo = LeaderRepository(db)
    repo.upsert([LeaderRecord("OP98-001", "Old", "OP98", "Past", ("Red",))])
    assert repo.release_dates() == {}
    assert repo.set_releases({"OP98": dt.date(2026, 1, 1), "OP99": dt.date(2026, 4, 1)}) == 2  # OP99: no leaders yet
    assert repo.set_releases({"OP98": dt.date(2026, 1, 2)}) == 1  # corrected; OP99 left out keeps its date
    assert repo.set_releases({"OP98": dt.date(2026, 1, 2)}) == 0
    assert repo.release_dates() == {"OP98": dt.date(2026, 1, 2), "OP99": dt.date(2026, 4, 1)}
    repo.upsert([LeaderRecord("OP99-001", "New", "OP99", "Future", ("Blue",))])  # the set row it made is reused
    assert {ld.set_code for ld in repo.all()} == {"OP98", "OP99"}
    assert repo.release_dates()["OP99"] == dt.date(2026, 4, 1)


@pytest.mark.parametrize(
    ("code", "main"),
    [("OP01", True), ("OP17", True), ("EB03", False), ("ST29", False), ("PRB02", False), ("XYZ", False)],
)
def test_is_main_set(code, main):
    assert is_main_set(code) is main


RELEASES = {
    "OP14": dt.date(2026, 1, 16),
    "EB03": dt.date(2026, 2, 20),
    "OP15": dt.date(2026, 4, 3),
    "OP16": dt.date(2026, 6, 12),
    "ST31": dt.date(2026, 7, 31),
}
CODES = ["OP14", "EB03", "OP15", "OP16", "OP17", "ST31"]  # OP17: in the catalogue, date not known yet


@pytest.mark.parametrize(
    ("day", "played_in"),
    [
        (dt.date(2026, 4, 3), "OP15"),  # out that very day
        (dt.date(2026, 4, 2), "OP14"),
        (dt.date(2026, 3, 1), "OP14"),  # EB03 is out, but it joins OP14's format
        (dt.date(2026, 8, 15), "OP16"),  # a starter after it changes nothing; OP17 has no date yet
        (dt.date(2030, 1, 1), "OP16"),
        (dt.date(2025, 12, 31), None),  # before any set it knows of
    ],
)
def test_set_on_picks_the_newest_main_set_out_by_then(day, played_in):
    assert set_on(day, CODES, RELEASES) == played_in


def test_set_on_without_any_main_set_dated_falls_back_to_the_newest():
    assert set_on(dt.date(2026, 1, 1), CODES, {"ST31": dt.date(2026, 7, 31)}) == "OP17"
    assert set_on(dt.date(2026, 1, 1), CODES, {}) == "OP17"


def test_set_on_without_any_set():
    assert set_on(dt.date(2026, 1, 1), [], RELEASES) is None


def test_set_on_ignores_dated_sets_outside_the_catalogue():
    """Only sets with leaders are in the set dropdown, so only they are picked."""
    assert set_on(dt.date(2026, 5, 1), ["OP14"], RELEASES) == "OP14"


def test_set_on_with_the_bundled_dates(leaders):
    codes = set_codes(leaders.all())
    releases = leaders.release_dates()
    assert set_on(dt.date(2022, 12, 2), codes, releases) == "OP01"
    assert set_on(dt.date(2024, 5, 3), codes, releases) == "OP06"  # EB01's release day
    assert set_on(dt.date(2026, 10, 12), codes, releases) == "OP17"


@pytest.mark.property
@given(st.dates(dt.date(2020, 1, 1), dt.date(2030, 12, 31)), st.dates(dt.date(2020, 1, 1), dt.date(2030, 12, 31)))
def test_property_set_on_never_goes_back_in_time(a, b):
    """A later day never gets an older set, and the set picked is always out by then."""
    early, late = sorted((a, b))
    first, second = set_on(early, CODES, RELEASES), set_on(late, CODES, RELEASES)
    if first is not None:
        assert RELEASES[first] <= early
        assert second is not None and RELEASES[second] >= RELEASES[first]
