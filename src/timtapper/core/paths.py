#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.442318
Revised: 2026/10/11 16:27:21.867104

Where the app keeps its files. A packaged Flet app (and `flet run`) exports
FLET_APP_STORAGE_DATA / FLET_APP_STORAGE_TEMP; a plain `python main.py` run
falls back to ~/.timtapper so development never writes into the repo.
"""

import os
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_DIR / "assets"
DB_FILENAME = "timtapper.db"


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
