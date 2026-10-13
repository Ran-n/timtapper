#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.253199
Revised: 2026/10/13 08:59:21.660533
"""

import compileall
import datetime as dt
import shutil
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from db import Database
from db import database as database_module
from db.database import MIGRATIONS_DIR, alembic_config
from db.models import COLORS, EVENT_TYPES, Color, Event, EventType, Game, Match


def test_migrate_creates_all_tables(db):
    tables = set(inspect(db.engine).get_table_names())
    assert {"color", "card_set", "leader", "leader_color", "event_type", "event", "match"} <= tables


def test_migrate_seeds_lookup_tables_in_order(db):
    with db.session() as s:
        assert [c.name for c in s.scalars(select(Color).order_by(Color.id))] == list(COLORS)
        # every type, though not in display order: 0004 appended the official types (screens use EVENT_TYPES' order)
        assert {t.key for t in s.scalars(select(EventType))} == set(EVENT_TYPES)


def test_migrate_is_idempotent(db):
    db.migrate()
    with db.session() as s:
        assert s.scalar(text("SELECT count(*) FROM color")) == len(COLORS)


def test_migrations_downgrade_and_upgrade_cleanly(tmp_path):
    database = Database(tmp_path / "roundtrip.db")
    database.migrate()
    cfg = alembic_config(database.engine)
    command.downgrade(cfg, "base")
    assert "event" not in inspect(database.engine).get_table_names()
    database.migrate()
    assert "event" in inspect(database.engine).get_table_names()
    database.dispose()


def _sourceless_copy(dest: Path) -> Path:
    """The migrations as `flet build` ships them: legacy .pyc beside each module, no .py sources."""
    shutil.copytree(MIGRATIONS_DIR, dest, ignore=shutil.ignore_patterns("__pycache__"))
    assert compileall.compile_dir(dest, legacy=True, quiet=1)
    for source in dest.rglob("*.py"):
        source.unlink()
    return dest


@pytest.mark.regression
def test_migrate_runs_compiled_only_migrations(tmp_path, monkeypatch):
    """The 0.5.0 APK opened on "no such table: color": Alembic skipped the .pyc-only revisions."""
    monkeypatch.setattr(database_module, "MIGRATIONS_DIR", _sourceless_copy(tmp_path / "migrations"))
    database = Database(tmp_path / "apk.db")
    database.migrate()
    assert {"color", "event", "match"} <= set(inspect(database.engine).get_table_names())
    with database.session() as s:
        assert s.scalar(text("SELECT version_num FROM alembic_version")) == _head_revision()
    database.dispose()


def test_migrate_refuses_to_run_without_migrations(tmp_path, monkeypatch):
    """No revisions found must fail loudly, not leave an empty database behind."""
    empty = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS_DIR, empty, ignore=shutil.ignore_patterns("__pycache__", "versions"))
    (empty / "versions").mkdir()
    monkeypatch.setattr(database_module, "MIGRATIONS_DIR", empty)
    database = Database(tmp_path / "empty.db")
    with pytest.raises(RuntimeError, match="no migrations found"):
        database.migrate()
    assert inspect(database.engine).get_table_names() == []
    database.dispose()


def test_migrating_a_database_with_history_keeps_it(sample_event, events, seeded_db):
    """Every start runs the migrations: an app update must never touch existing events."""
    before = events.list()
    seeded_db.migrate()
    assert events.list() == before
    with seeded_db.session() as s:
        assert s.scalar(text("SELECT version_num FROM alembic_version")) == _head_revision()


def test_each_migration_step_upgrades_a_database_with_data(tmp_path):
    """Step through every revision one at a time, adding history once the tables exist."""
    from alembic.script import ScriptDirectory

    database = Database(tmp_path / "steps.db")
    cfg = alembic_config(database.engine)
    revisions = [r.revision for r in reversed(list(ScriptDirectory.from_config(cfg).walk_revisions()))]
    seeded = False
    for revision in revisions:
        command.upgrade(cfg, revision)
        if not seeded and "event" in inspect(database.engine).get_table_names():
            with database.engine.begin() as conn:  # plain SQL: the ORM model has columns later revisions add
                conn.execute(text("INSERT INTO leader (id, code, name) VALUES (1, 'OP01-001', 'Roronoa Zoro')"))
                conn.execute(text("INSERT INTO event (name, event_type_id, date) VALUES ('kept', 1, '2026-01-01')"))
                conn.execute(text("INSERT INTO match (event_id, round_no, opponent_leader_id) VALUES (1, 1, 1)"))
            seeded = True
        with database.engine.connect() as conn:
            assert conn.execute(text("SELECT name FROM event")).scalar() == "kept"
            # a round too: rebuilding a table it cascades from used to delete it (see the 0003 regression below)
            assert conn.execute(text("SELECT count(*) FROM match")).scalar() == 1, revision
    database.dispose()


def _head_revision() -> str:
    from alembic.script import ScriptDirectory

    cfg = alembic_config()
    return ScriptDirectory.from_config(cfg).get_current_head()


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


def first_game(s, round_id: int) -> Game:
    return s.scalar(select(Game).where(Game.match_id == round_id, Game.game_no == 1))


def test_result_check_constraint(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        first_game(s, sample_event.rounds[0].id).result = "X"


def test_unique_round_per_event(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        s.get(Match, sample_event.rounds[1].id).round_no = 1


@pytest.mark.regression
def test_draws_are_rejected(sample_event, seeded_db):
    """The OPTCG has no draws: the schema refuses one."""
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        first_game(s, sample_event.rounds[0].id).result = "D"


def test_migration_0002_turns_stored_draws_into_losses(tmp_path):
    """A draw is a loss for both players, so history logged with draws keeps its games as losses."""
    database = Database(tmp_path / "draws.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0001")
    with database.engine.begin() as conn:
        conn.execute(text("INSERT INTO leader (id, code, name) VALUES (1, 'OP01-001', 'Zoro')"))
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (1, 'old', 1, '2026-01-01')"))
        for no, result in enumerate(("W", "D", "L", None), start=1):
            conn.execute(
                text("INSERT INTO match (event_id, round_no, opponent_leader_id, result) VALUES (1, :no, 1, :r)"),
                {"no": no, "r": result},
            )
    command.upgrade(cfg, "0002")
    with database.engine.connect() as conn:
        rows = conn.execute(text("SELECT result FROM match ORDER BY round_no")).scalars().all()
    assert rows == ["W", "L", "L", None]
    command.downgrade(cfg, "0001")  # and back, cleanly (draws stay losses)
    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM match WHERE result = 'L'")).scalar() == 2
    database.dispose()


@pytest.mark.parametrize(
    ("placement", "players"), [(0, None), (None, 0), (5, 4)], ids=["placement-0", "players-0", "past-field"]
)
def test_schema_refuses_impossible_placements(sample_event, seeded_db, placement, players):
    """The repository checks these too; the schema is the last line."""
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        row = s.get(Event, sample_event.id)
        row.placement, row.players = placement, players


def test_migration_0003_adds_empty_placement_to_existing_events(tmp_path):
    database = Database(tmp_path / "placement.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0002")
    with database.engine.begin() as conn:
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (1, 'old', 1, '2026-01-01')"))
    command.upgrade(cfg, "0003")
    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT name, placement, players FROM event")).one() == ("old", None, None)
    command.downgrade(cfg, "0002")
    assert "placement" not in {c["name"] for c in inspect(database.engine).get_columns("event")}
    database.dispose()


KINDS = "SELECT e.name, t.key FROM event e JOIN event_type t ON t.id = e.event_type_id"


def _type_keys(database) -> list[str]:
    with database.engine.connect() as conn:
        return [k for (k,) in conn.execute(text("SELECT key FROM event_type ORDER BY id"))]


def test_migration_0004_swaps_online_for_the_official_event_types(tmp_path):
    database = Database(tmp_path / "types.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0003")
    with database.engine.begin() as conn:  # 5 = online, 2 = locals (seeded by 0001)
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (1, 'web', 5, '2026-01-01')"))
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (2, 'shop', 2, '2026-01-02')"))
    command.upgrade(cfg, "0004")
    assert set(_type_keys(database)) == set(EVENT_TYPES)
    with database.engine.connect() as conn:
        kinds = {name: key for name, key in conn.execute(text(KINDS))}
    assert kinds == {"web": "other", "shop": "locals"}  # online became other, nothing else moved

    with database.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO event (id, name, event_type_id, date) "
                "SELECT 3, 'party', id, '2026-01-03' FROM event_type WHERE key = 'pirates_party'"
            )
        )
    command.downgrade(cfg, "0003")
    assert _type_keys(database) == ["testing", "locals", "regional", "national", "online", "other"]
    with database.engine.connect() as conn:
        kinds = {name: key for name, key in conn.execute(text(KINDS))}
    assert kinds == {"web": "other", "shop": "locals", "party": "other"}  # newer types fall back to other
    database.dispose()


@pytest.mark.parametrize(("column", "value"), [("game_no", 0), ("game_no", 4)], ids=["game-0", "game-4"])
def test_schema_refuses_games_outside_a_best_of_3(sample_event, seeded_db, column, value):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        setattr(first_game(s, sample_event.rounds[0].id), column, value)


def test_schema_refuses_a_best_of_2(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        s.get(Match, sample_event.rounds[0].id).best_of = 2


def test_schema_refuses_two_game_ones_in_a_round(sample_event, seeded_db):
    with pytest.raises(IntegrityError), seeded_db.session() as s:
        s.add(Game(match_id=sample_event.rounds[0].id, game_no=1))


def test_deleting_a_round_deletes_its_games(sample_event, events, seeded_db):
    events.delete_round(sample_event.rounds[0].id)
    with seeded_db.session() as s:
        assert first_game(s, sample_event.rounds[0].id) is None


def test_migration_0005_makes_every_round_a_best_of_1_keeping_its_game(tmp_path):
    database = Database(tmp_path / "games.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0004")
    with database.engine.begin() as conn:
        conn.execute(text("INSERT INTO leader (id, code, name) VALUES (1, 'OP01-001', 'Roronoa Zoro')"))
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (1, 'old', 2, '2026-01-01')"))
        conn.execute(
            text(
                "INSERT INTO match (id, event_id, round_no, opponent_leader_id, result, went_first, won_die_roll, "
                "top_cut) VALUES (1, 1, 1, 1, 'W', 0, 1, 1), (2, 1, 2, 1, NULL, NULL, NULL, 0)"
            )
        )
    command.upgrade(cfg, "0005")
    with database.engine.connect() as conn:
        kinds = conn.execute(text("SELECT id, best_of, kind FROM match ORDER BY id")).all()
        assert kinds == [(1, 1, "top_cut"), (2, 1, "swiss")]  # as each was flagged
        games = conn.execute(
            text("SELECT match_id, game_no, result, went_first, chose_turn FROM game ORDER BY match_id")
        )
        assert games.all() == [(1, 1, "W", 0, 1), (2, 1, None, None, None)]  # the die winner chose the turn order
    assert "result" not in {c["name"] for c in inspect(database.engine).get_columns("match")}

    with database.engine.begin() as conn:  # a best of 3 added after the upgrade: only game 1 survives a downgrade
        conn.execute(text("UPDATE match SET best_of = 3 WHERE id = 1"))
        conn.execute(text("INSERT INTO game (match_id, game_no, result) VALUES (1, 2, 'L')"))
    command.downgrade(cfg, "0004")
    with database.engine.connect() as conn:
        rows = conn.execute(text("SELECT id, result, went_first, won_die_roll FROM match ORDER BY id")).all()
        assert rows == [(1, "W", 0, 1), (2, None, None, None)]
    assert "game" not in inspect(database.engine).get_table_names()
    database.dispose()


def test_migration_0006_gives_sets_a_release_date_and_takes_it_back(tmp_path):
    database = Database(tmp_path / "releases.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0005")
    with database.engine.begin() as conn:
        conn.execute(text("INSERT INTO card_set (id, code, name) VALUES (1, 'OP01', 'Romance Dawn')"))
        conn.execute(text("INSERT INTO leader (id, code, name, set_id) VALUES (1, 'OP01-001', 'Roronoa Zoro', 1)"))
        conn.execute(
            text("INSERT INTO event (id, name, event_type_id, date, set_id) VALUES (1, 'old', 2, '2026-01-01', 1)")
        )
    command.upgrade(cfg, "0006")
    with database.engine.begin() as conn:
        assert conn.execute(text("SELECT code, name, release_date FROM card_set")).all() == [
            ("OP01", "Romance Dawn", None)  # not known until the catalogue fills it in
        ]
        conn.execute(text("UPDATE card_set SET release_date = '2022-12-02'"))
    command.downgrade(cfg, "0005")
    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT code, name FROM card_set")).all() == [("OP01", "Romance Dawn")]
        assert conn.execute(text("SELECT set_id FROM event")).scalar() == 1  # the event keeps its set
        assert conn.execute(text("SELECT set_id FROM leader")).scalar() == 1
    assert "release_date" not in {c["name"] for c in inspect(database.engine).get_columns("card_set")}
    database.dispose()


@pytest.mark.regression
def test_migration_0003_keeps_every_round(tmp_path):
    """0003 rebuilt the event table with foreign keys on: dropping the old table cascaded into `match` and deleted
    every round of every event (anyone upgrading from 0.4 lost their history)."""
    database = Database(tmp_path / "rounds.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0002")
    with database.engine.begin() as conn:
        conn.execute(text("INSERT INTO leader (id, code, name) VALUES (1, 'OP01-001', 'Roronoa Zoro')"))
        conn.execute(text("INSERT INTO event (id, name, event_type_id, date) VALUES (1, 'e', 2, '2026-01-01')"))
        conn.execute(text("INSERT INTO match (event_id, round_no, opponent_leader_id, result) VALUES (1, 1, 1, 'W')"))
    command.upgrade(cfg, "head")
    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM match")).scalar() == 1
        assert conn.execute(text("SELECT result FROM game")).scalar() == "W"
    database.dispose()


def test_a_migration_that_breaks_foreign_keys_commits_nothing(tmp_path):
    database = Database(tmp_path / "dangling.db")
    cfg = alembic_config(database.engine)
    command.upgrade(cfg, "0004")
    raw = database.engine.raw_connection()
    try:  # a round of an event that doesn't exist, slipped in with the keys off
        raw.driver_connection.execute("PRAGMA foreign_keys=OFF")
        raw.driver_connection.execute("INSERT INTO match (event_id, round_no, opponent_leader_id) VALUES (999, 1, 999)")
        raw.driver_connection.commit()
    finally:
        raw.close()
    with pytest.raises(RuntimeError, match="migration broke foreign keys"):
        command.upgrade(cfg, "0005")
    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0004"
        assert "game" not in inspect(database.engine).get_table_names()
    database.dispose()


def test_foreign_keys_are_back_on_after_migrating(db):
    with db.engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
