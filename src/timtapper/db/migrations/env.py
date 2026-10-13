#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.734582
Revised: 2026/10/12 23:54:35.618693

Alembic environment: runs online against the app's own engine (see Database.migrate), with SQLite's
foreign keys off while it runs (see below).
"""

from alembic import context
from sqlalchemy import create_engine

from db.models import Base

config = context.config
engine = config.attributes.get("connection_engine")
if engine is None:  # `alembic revision --autogenerate` from the CLI during development
    engine = create_engine(config.get_main_option("sqlalchemy.url") or "sqlite:///dev.db")


class ForeignKeyViolation(RuntimeError):
    """A migration left rows pointing at rows that don't exist; nothing was committed."""


def _foreign_keys(connection, on: bool) -> None:
    """Switch SQLite's foreign keys on the raw connection: the PRAGMA is ignored inside a transaction, and SQLAlchemy
    would open one for a statement sent through it."""
    connection.connection.driver_connection.execute(f"PRAGMA foreign_keys={'ON' if on else 'OFF'}")


with engine.connect() as connection:
    # Altering a table in SQLite means rebuilding it (batch mode), and with foreign keys on, dropping the old table
    # deletes every row that cascades from it: 0003 rebuilt `event` and took every round with it. So keys are off
    # while migrations run, checked before anything is committed, and back on for the app afterwards.
    # (the app's database is always SQLite, and so is the CLI's fallback above.)
    # Python's sqlite3 runs DDL outside any transaction and Alembic, taking SQLite for a database without
    # transactional DDL, commits after every step: an explicit BEGIN plus transactional_ddl make the whole upgrade
    # one transaction, all-or-nothing.
    _foreign_keys(connection, on=False)
    connection.connection.driver_connection.execute("BEGIN")
    try:
        context.configure(
            connection=connection, target_metadata=Base.metadata, render_as_batch=True, transactional_ddl=True
        )
        with context.begin_transaction():
            context.run_migrations()
            if broken := connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                raise ForeignKeyViolation(f"migration broke foreign keys: {broken[:5]}")
    finally:
        _foreign_keys(connection, on=True)
