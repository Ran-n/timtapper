#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.106265
Revised: 2026/10/15 00:58:27.932393

Running in a browser: `flet build web` runs the app's Python on Pyodide (WebAssembly) in a web worker, where the
file system lives in memory. BrowserStore keeps the data folder in the browser's IndexedDB instead, so events
survive a reload: loaded once at startup, saved again after every database commit.
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from core.logging import get_logger

_log = get_logger("web")

IS_WEB = sys.platform == "emscripten"


# Where the app leaves its web shell (ui/shell.py) for the page to paint on the next visit, and the channel it says
# it's ready on; scripts/shell/shell.js reads the same names (scripts/build_web.py writes them into it).
SHELL_DB = "timtapper-shell"
SHELL_STORE = "shell"
SHELL_KEY = "current"
SHELL_CHANNEL = "timtapper-shell"
SHELL_READY = "ready"

_SAVE_SHELL_JS = """(db, store, key, text) => new Promise((resolve, reject) => {
  const open = indexedDB.open(db, 1);
  open.onupgradeneeded = () => open.result.createObjectStore(store);
  open.onerror = () => reject(open.error);
  open.onsuccess = () => {
    const tx = open.result.transaction(store, "readwrite");
    tx.objectStore(store).put(text, key);
    tx.oncomplete = () => { open.result.close(); resolve(); };
    tx.onerror = () => { open.result.close(); reject(tx.error); };
  };
})"""
_LOAD_SHELL_JS = """(db, store, key) => new Promise((resolve, reject) => {
  const open = indexedDB.open(db, 1);
  open.onupgradeneeded = () => open.result.createObjectStore(store);
  open.onerror = () => reject(open.error);
  open.onsuccess = () => {
    const get = open.result.transaction(store).objectStore(store).get(key);
    get.onsuccess = () => { open.result.close(); resolve(get.result ?? null); };
    get.onerror = () => { open.result.close(); reject(get.error); };
  };
})"""
_ANNOUNCE_JS = """(channel, type, route) => {
  const c = new BroadcastChannel(channel);
  c.postMessage({ type, route });
  c.close();
}"""


class BrowserStoreError(OSError):
    """IndexedDB refused to load or save the data folder."""


def _pyodide_run_js() -> Callable[[str], Any]:  # pragma: no cover - only importable inside Pyodide
    from pyodide.code import run_js

    return run_js


class ShellStore:
    """The page side of the web shell: saves the shell's JSON where the page reads it before the app starts, and tells
    the page when the app is on screen. `run_js` (evaluates JS, returning the value) defaults to Pyodide's."""

    def __init__(self, run_js: Callable[[str], Any] | None = None) -> None:
        self._run_js = run_js or _pyodide_run_js()

    async def save(self, text: str) -> None:
        await self._run_js(_SAVE_SHELL_JS)(SHELL_DB, SHELL_STORE, SHELL_KEY, text)

    async def load(self) -> str | None:
        """The shell saved last, or None."""
        text = await self._run_js(_LOAD_SHELL_JS)(SHELL_DB, SHELL_STORE, SHELL_KEY)
        return text if isinstance(text, str) else None

    def announce_ready(self, route: str) -> None:
        """The app is on screen, at `route`: the page fades its shell out, first sending the app to the screen the
        shell was showing if that's another one."""
        self._run_js(_ANNOUNCE_JS)(SHELL_CHANNEL, SHELL_READY, route)
        _log.info("told the page the app is ready at %s", route)


def _pyodide_fs() -> tuple[Any, Callable[[Callable], Any]]:  # pragma: no cover - only importable inside Pyodide
    import pyodide_js
    from pyodide.ffi import create_once_callable

    return pyodide_js.FS, create_once_callable


class BrowserStore:
    """Keeps `folder` in IndexedDB through Emscripten's IDBFS. `fs` and `once` (the Emscripten FS object and a
    wrapper turning a Python callable into a one-shot JS callback) default to Pyodide's."""

    def __init__(self, folder: Path, fs: Any = None, once: Callable[[Callable], Any] | None = None) -> None:
        self.folder = folder
        if fs is None:
            fs, once = _pyodide_fs()
        self._fs = fs
        self._once = once or (lambda fn: fn)
        self._dirty = False
        self._saving: asyncio.Task | None = None
        # tells the user a save failed: called with no arguments, once per failed save (set once the UI exists)
        self.on_save_failed: Callable[[], None] | None = None

    async def open(self) -> None:
        """Mount the folder on IndexedDB and load what an earlier visit saved there."""
        self._fs.mkdirTree(str(self.folder))
        self._fs.mount(self._fs.filesystems.IDBFS, {}, str(self.folder))
        await self._sync(populate=True)
        _log.info("browser storage loaded into %s", self.folder)

    def changed(self) -> None:
        """Save soon. Calls while a save runs are folded into one more save after it."""
        self._dirty = True
        if self._saving is None or self._saving.done():
            self._saving = asyncio.get_running_loop().create_task(self._save())

    async def flush(self) -> None:
        """Wait for the pending save, if any."""
        if self._saving is not None:
            await self._saving

    async def _save(self) -> None:
        while self._dirty:
            self._dirty = False
            try:
                await self._sync(populate=False)
            except BrowserStoreError:
                _log.exception("could not save %s to browser storage; the last changes are lost on reload", self.folder)
                if self.on_save_failed is not None:
                    self.on_save_failed()
                return

    async def _sync(self, *, populate: bool) -> None:
        done = asyncio.get_running_loop().create_future()

        def finished(error: Any = None) -> None:
            if error:
                done.set_exception(BrowserStoreError(f"IndexedDB {'load' if populate else 'save'} failed: {error}"))
            else:
                done.set_result(None)

        self._fs.syncfs(populate, self._once(finished))
        await done


# Pyodide's own build of Pillow, the one flet bundles too: the web build leaves it out of the app's archive
# (scripts/build_web.py), so every visit downloads less, and it's loaded from Pyodide's CDN the first time it's needed
PILLOW = "pillow"


def _pyodide_load_package() -> Callable[[str], Awaitable[Any]]:  # pragma: no cover - only importable inside Pyodide
    import pyodide_js

    return pyodide_js.loadPackage


async def fetch_bytes(url: str) -> bytes:  # pragma: no cover - only importable inside Pyodide
    """`url`, relative to the site, fetched by the browser. Raises OSError on an error status."""
    from pyodide.http import pyfetch

    response = await pyfetch(url)
    if not response.ok:
        raise OSError(f"HTTP {response.status} {url}")
    return await response.bytes()


class RenderDeps:
    """What drawing pictures needs on the web that the app's archive leaves out: Pillow, and the bundled portraits
    (`fetch_portraits` brings them). Each is fetched once, the portraits from `prefetch()` on, Pillow only when first
    needed: loading it holds Python up for a moment, so it doesn't run right after startup."""

    def __init__(
        self,
        fetch_portraits: Callable[[], Awaitable[Any]],
        load_package: Callable[[str], Awaitable[Any]] | None = None,
    ) -> None:
        self._fetch_portraits = fetch_portraits
        self._load_package = load_package
        self._portraits: asyncio.Task | None = None
        self._pillow: asyncio.Task | None = None

    def prefetch(self) -> None:
        if self._portraits is None:
            self._portraits = asyncio.get_running_loop().create_task(self._fetch_portraits())

    async def ready(self) -> None:
        """Wait until Pillow and the portraits are there. Raises what loading Pillow raised; the next call retries."""
        if self._pillow is None or (self._pillow.done() and self._pillow.exception() is not None):
            self._pillow = asyncio.get_running_loop().create_task(self._load(PILLOW))
        self.prefetch()
        await asyncio.gather(self._pillow, self._portraits)

    async def _load(self, package: str) -> None:
        await (self._load_package or _pyodide_load_package())(package)
        _log.info("loaded %s", package)
