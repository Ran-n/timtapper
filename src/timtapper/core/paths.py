#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.442318
Revised: 2026/10/12 21:53:36.718636

Where the app keeps its files. A packaged Flet app (and `flet run`) exports
FLET_APP_STORAGE_DATA / FLET_APP_STORAGE_TEMP; a plain `python main.py` run
falls back to ~/.timtapper so development never writes into the repo.
"""

import os
import tempfile
import time
from pathlib import Path

from core.logging import get_logger

_log = get_logger("paths")

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_DIR / "assets"
DB_FILENAME = "timtapper.db"
TEMP_PREFIX = "timtapper-"
# a shared card or backup is handed to the share sheet, which may read it a while later; after this it's spent
TEMP_MAX_AGE = 24 * 60 * 60  # seconds


def data_dir() -> Path:
    path = Path(os.environ.get("FLET_APP_STORAGE_DATA") or Path.home() / ".timtapper")
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_dir() -> Path:
    path = Path(os.environ.get("FLET_APP_STORAGE_TEMP") or Path(tempfile.gettempdir()) / "timtapper")
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / DB_FILENAME


def temp_file(name: str) -> Path:
    """A path in the temp folder for `name` (which must start with TEMP_PREFIX), after deleting this app's
    temp files older than TEMP_MAX_AGE: every share writes a new file, and nothing else ever removes them."""
    if not name.startswith(TEMP_PREFIX):
        raise ValueError(f"temp file names start with {TEMP_PREFIX!r}: {name!r}")
    folder = temp_dir()
    cutoff = time.time() - TEMP_MAX_AGE
    for old in folder.glob(f"{TEMP_PREFIX}*"):
        try:
            if old.is_file() and old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError as exc:  # in use or already gone: try again next time
            _log.warning("could not delete old temp file %s: %s", old.name, exc)
    return folder / name
