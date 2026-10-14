#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.106265
Revised: 2026/10/13 22:53:34.407353

Running in a browser: `flet build web` runs the app's Python on Pyodide (WebAssembly) in a web worker, where the
file system lives in memory. BrowserStore keeps the data folder in the browser's IndexedDB instead, so events
survive a reload: loaded once at startup, saved again after every database commit.
"""

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.logging import get_logger

_log = get_logger("web")

IS_WEB = sys.platform == "emscripten"


class BrowserStoreError(OSError):
    """IndexedDB refused to load or save the data folder."""


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
