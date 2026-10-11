#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.176823
Revised: 2026/10/11 16:27:24.642411
"""

import logging

from core import paths
from core.logging import APP_LOGGER, get_logger, setup_logging


def test_data_dir_uses_flet_storage_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "flet-data"))
    assert paths.data_dir() == tmp_path / "flet-data"
    assert paths.data_dir().is_dir()
    assert paths.db_path() == tmp_path / "flet-data" / paths.DB_FILENAME


def test_data_dir_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("FLET_APP_STORAGE_DATA", raising=False)
    monkeypatch.setattr(paths.Path, "home", lambda: tmp_path)
    assert paths.data_dir() == tmp_path / ".timtapper"


def test_temp_dir_uses_flet_storage_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLET_APP_STORAGE_TEMP", str(tmp_path / "t"))
    assert paths.temp_dir() == tmp_path / "t"
    assert paths.temp_dir().is_dir()


def test_temp_dir_fallback(monkeypatch):
    monkeypatch.delenv("FLET_APP_STORAGE_TEMP", raising=False)
    assert paths.temp_dir().name == "timtapper"


def test_setup_logging_is_idempotent_and_isolated(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    root = setup_logging()
    setup_logging()
    assert root.name == APP_LOGGER
    assert len(root.handlers) == 1
    assert root.propagate is False
    assert root.level == logging.DEBUG
    assert get_logger("x").name == f"{APP_LOGGER}.x"
    setup_logging("INFO")
