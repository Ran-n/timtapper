#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.803606
Revised: 2026/10/11 16:27:22.277157

The on-device database: one SQLite file, schema owned by Alembic (migrations
ship inside the app and run on every start, so an app update never wipes or
breaks existing history).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.logging import get_logger

_log = get_logger("db")
_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _enable_foreign_keys(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.url = f"sqlite:///{path.as_posix()}"
        self.engine: Engine = create_engine(self.url)
        event.listen(self.engine, "connect", _enable_foreign_keys)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        """Bring the schema up to the latest revision."""
        cfg = Config()
        cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
        cfg.attributes["connection_engine"] = self.engine
        _log.info("migrating database at %s", self.path)
        command.upgrade(cfg, "head")

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Unit of work: commits on success, rolls back (and re-raises) on error."""
        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            _log.warning("transaction rolled back", exc_info=True)
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
        _log.info("database closed")
