#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.176823
Revised: 2026/10/12 19:13:15.548013
"""

import logging

from core import paths
from core.logging import APP_LOGGER, LogTail, get_logger, setup_logging


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


def test_log_tail_collects_while_attached_and_restores_levels():
    lib = logging.getLogger("tail-test.lib")
    lib.setLevel(logging.WARNING)
    tail = LogTail(limit=2)
    with tail.attached("tail-test.lib"):
        assert lib.level == logging.INFO  # raised so INFO reaches the tail
        for n in range(3):
            lib.info("step %d", n)
        lib.debug("below the level")
    lib.info("after detaching")
    assert list(tail.lines) == ["INFO tail-test.lib: step 1", "INFO tail-test.lib: step 2"]
    assert lib.level == logging.WARNING and tail not in lib.handlers


def test_log_tail_leaves_a_more_verbose_logger_alone():
    lib = logging.getLogger("tail-test.verbose")
    lib.setLevel(logging.DEBUG)
    tail = LogTail()
    with tail.attached("tail-test.verbose"):
        assert lib.level == logging.DEBUG
        lib.debug("kept")
    assert list(tail.lines) == ["DEBUG tail-test.verbose: kept"]
