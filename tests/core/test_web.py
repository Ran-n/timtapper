#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.184243
Revised: 2026/10/15 00:58:28.680646

The web build's browser storage (core.web.BrowserStore), against a fake of Emscripten's FS that keeps an
"IndexedDB" copy of the mounted folder and answers syncfs on the event loop, as the browser does.
"""

import asyncio
import logging
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


async def test_failed_save_tells_the_user(folders):
    """Logging alone would let a browser user close the page believing the change was kept."""
    idb, folder = folders
    fs = FakeFS(idb)
    store = BrowserStore(folder, fs=fs)
    told = []
    store.on_save_failed = lambda: told.append(True)
    await store.open()
    fs.fail = "quota exceeded"
    store.changed()
    await store.flush()
    assert told == [True]
    fs.fail = None
    store.changed()
    await store.flush()
    assert told == [True]  # a save that works says nothing


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


# ---- the web shell's storage ------------------------------------------------------
class FakeJS:
    """run_js stand-in: the three snippets ShellStore runs, against a dict for IndexedDB and a list for the channel."""

    def __init__(self):
        self.idb, self.posted = {}, []

    def __call__(self, source):
        if "put(text, key)" in source:

            async def save(db, store, key, text):
                self.idb[(db, store, key)] = text

            return save
        if ".get(key)" in source:

            async def load(db, store, key):
                return self.idb.get((db, store, key))

            return load
        assert "BroadcastChannel" in source
        return lambda channel, kind, route: self.posted.append((channel, kind, route))


async def test_shell_store_saves_and_loads_where_the_page_reads():
    js = FakeJS()
    store = web.ShellStore(js)
    assert await store.load() is None
    await store.save('{"v":1}')
    assert js.idb == {(web.SHELL_DB, web.SHELL_STORE, web.SHELL_KEY): '{"v":1}'}
    assert await store.load() == '{"v":1}'


async def test_shell_store_reads_a_non_string_as_nothing():
    js = FakeJS()
    js.idb[(web.SHELL_DB, web.SHELL_STORE, web.SHELL_KEY)] = object()  # what a JsNull or a stray value comes back as
    assert await web.ShellStore(js).load() is None


def test_ready_tells_the_page_the_route_it_opened_at(caplog):
    caplog.set_level(logging.INFO)
    js = FakeJS()
    web.ShellStore(js).announce_ready("/event/3")
    assert js.posted == [(web.SHELL_CHANNEL, web.SHELL_READY, "/event/3")]
    assert "ready at /event/3" in caplog.text


def test_shell_store_defaults_to_pyodides_run_js(monkeypatch):
    js = FakeJS()
    monkeypatch.setattr(web, "_pyodide_run_js", lambda: js)
    assert web.ShellStore()._run_js is js


def test_shell_js_snippets_use_their_arguments():
    """The snippets get every name from Python, so the page and the app can't disagree on one."""
    for snippet in (web._SAVE_SHELL_JS, web._LOAD_SHELL_JS):
        assert "indexedDB.open(db, 1)" in snippet and "createObjectStore(store)" in snippet
    assert "postMessage({ type, route })" in web._ANNOUNCE_JS


# ---- RenderDeps: Pillow and the portraits, on demand ---------------------------------
class FakeDeps:
    """A RenderDeps' loader and portrait fetch, counting calls; `fail` makes the next Pillow load raise it."""

    def __init__(self):
        self.loads: list[str] = []
        self.fetches = 0
        self.fail: Exception | None = None

    async def load(self, package):
        self.loads.append(package)
        if self.fail is not None:
            exc, self.fail = self.fail, None
            raise exc

    async def fetch(self):
        self.fetches += 1
        await asyncio.sleep(0)


async def test_render_deps_load_pillow_and_the_portraits_once(caplog):
    fake = FakeDeps()
    deps = web.RenderDeps(fake.fetch, fake.load)
    with caplog.at_level(logging.INFO, logger="timtapper.web"):
        await deps.ready()
        await deps.ready()
    assert fake.loads == [web.PILLOW] and fake.fetches == 1
    assert "loaded pillow" in caplog.text


async def test_render_deps_fetch_the_portraits_from_the_start_and_pillow_only_when_asked():
    fake = FakeDeps()
    deps = web.RenderDeps(fake.fetch, fake.load)
    deps.prefetch()
    deps.prefetch()
    await asyncio.sleep(0.01)
    assert fake.fetches == 1 and fake.loads == []  # loading Pillow holds Python up: not right after startup
    await deps.ready()
    assert fake.fetches == 1 and fake.loads == [web.PILLOW]


async def test_render_deps_retry_pillow_after_a_failed_load():
    fake = FakeDeps()
    fake.fail = OSError("offline")
    deps = web.RenderDeps(fake.fetch, fake.load)
    with pytest.raises(OSError, match="offline"):
        await deps.ready()
    await deps.ready()
    assert fake.loads == [web.PILLOW, web.PILLOW]
