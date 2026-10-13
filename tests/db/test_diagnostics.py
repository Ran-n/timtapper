#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 19:05:54.099962
Revised: 2026/10/13 08:59:21.744885

The startup report shown when the database won't open.
"""

from db import Database
from db.database import MIGRATIONS_DIR
from db.diagnostics import startup_report


def test_report_lists_tables_stamp_and_bundled_migrations(tmp_path):
    database = Database(tmp_path / "ok.db")
    database.migrate()
    database.dispose()
    report = startup_report(tmp_path / "ok.db", MIGRATIONS_DIR, ["INFO alembic: ran"])
    assert "color, event, event_type" in report
    assert "alembic_version: [('0006',)]" in report
    assert "0001_initial.py" in report and "0005_games.py" in report
    assert report.endswith("log:\nINFO alembic: ran")


def test_report_on_a_missing_database(tmp_path):
    report = startup_report(tmp_path / "absent.db", MIGRATIONS_DIR, [])
    assert "(0 bytes)" in report and "tables: (no database file)" in report


def test_report_on_an_empty_database_has_no_stamp(tmp_path):
    """What a phone that found no migrations was left with: a file with no tables at all."""
    path = tmp_path / "empty.db"
    database = Database(path)
    database.engine.connect().close()
    database.dispose()
    report = startup_report(path, MIGRATIONS_DIR, [])
    assert "tables: (none)\nalembic_version: None" in report


def test_report_on_an_unreadable_database(tmp_path):
    path = tmp_path / "junk.db"
    path.write_bytes(b"not a database" * 100)
    assert "(could not read: DatabaseError:" in startup_report(path, MIGRATIONS_DIR, [])


def test_report_on_missing_or_empty_migrations(tmp_path):
    assert "(no versions folder in" in startup_report(tmp_path / "x.db", tmp_path, [])
    (tmp_path / "versions").mkdir()
    assert "files: (empty)" in startup_report(tmp_path / "x.db", tmp_path, [])
