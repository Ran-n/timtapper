#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 19:04:50.022328
Revised: 2026/10/12 19:13:14.200746

Startup report: what the app sees when its database won't open (versions, the database file, its
tables, the bundled migrations), shown on the failure screen so a phone with no debugger attached
can still say what went wrong.
"""

import sqlite3
import sys
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

import alembic
import sqlalchemy

from core.version import VERSION


def _tables(path: Path) -> str:
    if not path.is_file():
        return "(no database file)"
    try:
        # closing: sqlite3's own context manager only commits, it leaves the file open
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
            names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
            stamp = (
                conn.execute("SELECT version_num FROM alembic_version").fetchall()
                if "alembic_version" in names
                else None
            )
    except sqlite3.Error as exc:
        return f"(could not read: {type(exc).__name__}: {exc})"
    return f"{', '.join(names) or '(none)'}\nalembic_version: {stamp}"


def _migrations(folder: Path) -> str:
    versions = folder / "versions"
    if not versions.is_dir():
        return f"(no versions folder in {folder})"
    return ", ".join(sorted(p.name for p in versions.iterdir())) or "(empty)"


def startup_report(db_path: Path, migrations_dir: Path, log_lines: Iterable[str]) -> str:
    size = db_path.stat().st_size if db_path.is_file() else 0
    return "\n".join([
        f"timtapper {VERSION} · Python {sys.version.split()[0]} · SQLite {sqlite3.sqlite_version}",
        f"SQLAlchemy {sqlalchemy.__version__} · Alembic {alembic.__version__}",
        f"database: {db_path} ({size} bytes)",
        f"tables: {_tables(db_path)}",
        f"migrations: {migrations_dir}",
        f"files: {_migrations(migrations_dir)}",
        "log:",
        *log_lines,
    ])
