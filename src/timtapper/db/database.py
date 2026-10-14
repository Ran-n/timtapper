#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.803606
Revised: 2026/10/14 16:30:39.715716

The on-device database: one SQLite file, schema owned by Alembic (migrations
ship inside the app and run on every start, so an app update never wipes or
breaks existing history).
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from core.logging import get_logger

_log = get_logger("db")
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


# statements that change nothing: a transaction of only these is no change to tell anyone about
READ_ONLY = ("SELECT", "PRAGMA")
_CHANGED = "timtapper_changed"  # set in a connection's info by a statement that may write, until commit or rollback


def _note_change(conn, _cursor, statement: str, _params, _context, _executemany) -> None:
    if not statement.lstrip().upper().startswith(READ_ONLY):
        conn.info[_CHANGED] = True


def _forget_change(conn) -> None:
    conn.info.pop(_CHANGED, None)


def _enable_foreign_keys(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def alembic_config(engine: Engine | None = None, migrations_dir: Path | None = None) -> Config:
    """Alembic settings for the bundled migrations, run on `engine` when given.

    `sourceless`: `flet build` ships the app as .pyc only, and without it Alembic skips revision files
    that have no .py beside them, so a fresh install found no migrations and got no tables."""
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir or MIGRATIONS_DIR))
    cfg.set_main_option("sourceless", "true")
    if engine is not None:
        cfg.attributes["connection_engine"] = engine
    return cfg


class Database:
    def __init__(self, path: Path, on_commit: Callable[[], None] | None = None) -> None:
        """`on_commit` runs after every committed transaction that changed something, migrations included (the web
        build saves the file to the browser's storage then, and refreshes its shell). Reads commit too, but aren't
        changes: on every one, the web build saved the whole file again."""
        self.path = path
        self.url = f"sqlite:///{path.as_posix()}"
        self.engine: Engine = create_engine(self.url)
        event.listen(self.engine, "connect", _enable_foreign_keys)
        if on_commit is not None:

            def committed(conn) -> None:
                if conn.info.pop(_CHANGED, False):
                    on_commit()

            event.listen(self.engine, "before_cursor_execute", _note_change)
            event.listen(self.engine, "commit", committed)
            event.listen(self.engine, "rollback", _forget_change)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        """Bring the schema up to the latest revision."""
        cfg = alembic_config(self.engine)
        if ScriptDirectory.from_config(cfg).get_current_head() is None:  # else upgrade is a silent no-op
            raise RuntimeError(f"no migrations found in {cfg.get_main_option('script_location')}")
        _log.info("migrating database at %s", self.path)
        command.upgrade(cfg, "head")

    @contextmanager
    def session(self) -> Generator[Session]:
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
