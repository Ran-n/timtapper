#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.184243
Revised: 2026/10/13 22:03:51.184243

The web build's browser storage (core.web.BrowserStore), against a fake of Emscripten's FS that keeps an
"IndexedDB" copy of the mounted folder and answers syncfs on the event loop, as the browser does.
"""

import asyncio
import shutil

import pytest
from sqlalchemy import text

from core import web
from core.web import BrowserStore, BrowserStoreError
from db import Database


class FakeFS:
    """Emscripten FS stand-in: the mounted folder is the in-memory side, `idb` the browser's IndexedDB."""

    def __init__(self, idb, fail=None):
        self.idb, self.fail = idb, fail
        self.filesystems = type("FS", (), {"IDBFS": "IDBFS"})
        self.mounted, self.syncs, self.folder = [], [], None

    def mkdirTree(self, path):  # noqa: N802 - Emscripten's name
        self.folder = path

    def mount(self, kind, opts, path):
        self.mounted.append((kind, opts, path))

    def syncfs(self, populate, callback):
        self.syncs.append(populate)
        loop = asyncio.get_running_loop()
        if self.fail:
            loop.call_soon(callback, self.fail)
            return
        src, dst = (self.idb, self.folder) if populate else (self.folder, self.idb)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        loop.call_soon(callback)


@pytest.fixture
def folders(tmp_path):
    idb, folder = tmp_path / "idb", tmp_path / "data"
    idb.mkdir()
    folder.mkdir()
    return idb, folder


def test_is_web_only_under_pyodide():
    assert web.IS_WEB is False  # CPython here; True only where sys.platform is "emscripten"


async def test_open_mounts_idbfs_and_loads_what_was_saved(folders):
    idb, folder = folders
    (idb / "timtapper.db").write_bytes(b"saved last visit")
    fs = FakeFS(idb)
    await BrowserStore(folder, fs=fs).open()
    assert fs.mounted == [("IDBFS", {}, str(folder))]
    assert fs.syncs == [True]
    assert (folder / "timtapper.db").read_bytes() == b"saved last visit"


async def test_changes_are_saved(folders):
    idb, folder = folders
    store = BrowserStore(folder, fs=FakeFS(idb))
    await store.open()
    (folder / "timtapper.db").write_bytes(b"new event")
    store.changed()
    await store.flush()
    assert (idb / "timtapper.db").read_bytes() == b"new event"


async def test_changes_during_a_save_fold_into_one_more_save(folders):
    idb, folder = folders
    fs = FakeFS(idb)
    store = BrowserStore(folder, fs=fs)
    await store.open()
    for _ in range(5):
        store.changed()
    await store.flush()
    assert fs.syncs == [True, False]  # five commits in one tick: one save
    store.changed()
    await asyncio.sleep(0)
    store.changed()  # arrives while that save is running
    await store.flush()
    assert fs.syncs == [True, False, False, False]


async def test_flush_without_changes_returns(folders):
    idb, folder = folders
    await BrowserStore(folder, fs=FakeFS(idb)).flush()


async def test_failed_load_raises(folders):
    idb, folder = folders
    with pytest.raises(BrowserStoreError, match="IndexedDB load failed: quota"):
        await BrowserStore(folder, fs=FakeFS(idb, fail="quota")).open()


async def test_failed_save_is_logged_not_swallowed(folders, caplog):
    idb, folder = folders
    fs = FakeFS(idb)
    store = BrowserStore(folder, fs=fs)
    await store.open()
    fs.fail = "quota exceeded"
    store.changed()
    await store.flush()
    assert "could not save" in caplog.text and "IndexedDB save failed: quota exceeded" in caplog.text
    fs.fail = None
    store.changed()  # the next commit tries again
    await store.flush()
    assert fs.syncs.count(False) == 2


async def test_once_wraps_the_callback(folders):
    idb, folder = folders
    wrapped = []

    def once(fn):
        wrapped.append(fn)
        return fn

    await BrowserStore(folder, fs=FakeFS(idb), once=once).open()
    assert len(wrapped) == 1


async def test_every_database_commit_saves(folders):
    """The web build's events live in the browser only if each commit reaches IndexedDB."""
    idb, folder = folders
    fs = FakeFS(idb)
    store = BrowserStore(folder, fs=fs)
    await store.open()
    db = Database(folder / "timtapper.db", on_commit=store.changed)
    try:
        db.migrate()
        await store.flush()
        assert (idb / "timtapper.db").is_file()
        saves = fs.syncs.count(False)
        with db.session() as session:
            session.execute(text("CREATE TABLE probe (x INTEGER)"))
        await store.flush()
        assert fs.syncs.count(False) == saves + 1
    finally:
        db.dispose()


def test_defaults_to_pyodides_file_system(monkeypatch, tmp_path):
    fs, once = FakeFS(tmp_path), lambda fn: fn
    monkeypatch.setattr(web, "_pyodide_fs", lambda: (fs, once))
    store = BrowserStore(tmp_path)
    assert (store._fs, store._once) == (fs, once)
