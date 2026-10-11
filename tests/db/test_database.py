#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.253199
Revised: 2026/10/11 16:27:24.713048
"""

import datetime as dt

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from db import Database
from db.database import _MIGRATIONS_DIR
from db.models import COLORS, EVENT_TYPES, Color, Event, EventType, Match


def test_migrate_creates_all_tables(db):
    tables = set(inspect(db.engine).get_table_names())
    assert {"color", "card_set", "leader", "leader_color", "event_type", "event", "match"} <= tables


def test_migrate_seeds_lookup_tables_in_order(db):
    with db.session() as s:
        assert [c.name for c in s.scalars(select(Color).order_by(Color.id))] == list(COLORS)
        assert [t.key for t in s.scalars(select(EventType).order_by(EventType.id))] == list(EVENT_TYPES)


def test_migrate_is_idempotent(db):
    db.migrate()
    with db.session() as s:
        assert s.scalar(text("SELECT count(*) FROM color")) == len(COLORS)


def test_migrations_downgrade_and_upgrade_cleanly(tmp_path):
    database = Database(tmp_path / "roundtrip.db")
    database.migrate()
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.attributes["connection_engine"] = database.engine
    command.downgrade(cfg, "base")
    assert "event" not in inspect(database.engine).get_table_names()
    database.migrate()
    assert "event" in inspect(database.engine).get_table_names()
    database.dispose()


def test_orm_metadata_matches_migrations(db):
    """Columns declared on the models exist in the migrated schema (no drift)."""
    from db.models import Base

    insp = inspect(db.engine)
    for table in Base.metadata.sorted_tables:
        migrated = {c["name"] for c in insp.get_columns(table.name)}
        assert {c.name for c in table.columns} == migrated, table.name


def test_foreign_keys_are_enforced(db):
    with pytest.raises(IntegrityError), db.session() as s:
        s.add(Event(name="x", event_type_id=999, date=dt.date(2026, 1, 1)))


def test_session_rolls_back_on_error(db):
    with pytest.raises(RuntimeError), db.session() as s:
        s.add(Event(name="rolled back", event_type_id=1, date=dt.date(2026, 1, 1)))
        s.flush()
        raise RuntimeError("boom")
    with db.session() as s:
        assert s.scalar(select(Event).where(Event.name == "rolled back")) is None


def test_result_check_constraint(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        s.get(Match, sample_event.rounds[0].id).result = "X"


def test_unique_round_per_event(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        s.get(Match, sample_event.rounds[1].id).round_no = 1
