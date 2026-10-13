#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.055435
Revised: 2026/10/13 00:30:08.214395

One real app for the whole rendered-test session: scripts/app_driver.py runs it,
scripts/app_window.py captures and clicks it. Windows only; marked `desktop`.
"""

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPLY_TIMEOUT = 60  # seconds; the first reply waits for the app to start


class DriverError(RuntimeError):
    """The app driver failed a command, exited, or stopped answering."""


class DrivenApp:
    def __init__(self, log_path: Path) -> None:
        from app_window import AppWindow

        self.log_path = log_path
        self._log = log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "app_driver.py"), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
        )
        self._replies: queue.Queue[dict | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.window = AppWindow()
        ready = self._next()
        self.newest = ready["newest"]
        self.window.wait_open()
        self.capture()
        # the first click after the window opens can be lost while it takes focus: spend it on the inert title
        self.window.click(200 * self.scale, 28 * self.scale)

    def _read(self) -> None:
        for line in self.proc.stdout:
            if line.startswith("@@"):
                self._replies.put(json.loads(line[2:]))
        self._replies.put(None)  # stdout closed: the driver exited

    def _next(self) -> dict:
        try:
            reply = self._replies.get(timeout=REPLY_TIMEOUT)
        except queue.Empty:
            raise DriverError(f"no reply in {REPLY_TIMEOUT}s; driver log: {self.log_path}") from None
        if reply is None:
            raise DriverError(f"driver exited (code {self.proc.poll()}); log: {self.log_path}")
        if not reply["ok"]:
            raise DriverError(f"{reply['error']}; driver log: {self.log_path}")
        return reply

    def send(self, cmd: str, **args):
        self.proc.stdin.write(json.dumps({"cmd": cmd, **args}) + "\n")
        self.proc.stdin.flush()
        return self._next().get("result")

    @property
    def scale(self) -> float:
        return self.window.scale

    def show(self, route: str, mode: str = "dark", width: int = 0, lang: str = "en") -> Image.Image:
        self.send("show", route=route, mode=mode, width=width, lang=lang)
        return self.capture()

    def capture(self) -> Image.Image:
        """The settled window in dp, whatever the display scaling: every size and position the tests assert
        is in dp. Nearest-neighbour keeps each pixel an exact theme colour (no blended edges to mis-match)."""
        img = self.window.capture()
        if self.scale == 1:
            return img
        size = (round(img.width / self.scale), round(img.height / self.scale))
        return img.resize(size, Image.Resampling.NEAREST)

    def click(self, x: float, y: float) -> Image.Image:
        """A real click at dp (x, y) of a capture, then the settled screen it produced."""
        self.window.click(x * self.scale, y * self.scale)
        return self.capture()

    def fields(self, s) -> list:
        """The outlined input fields on screen now, in dp (see locate.fields)."""
        from locate import fields

        return fields(self.window.capture(), s, self.scale)

    def rings(self, color: str, **size) -> list:
        """Outlines in `color` on screen now (outlined buttons), in dp (see locate.rings)."""
        from locate import rings

        return rings(self.window.capture(), color, self.scale, **size)

    def pick(self, field, index: int, options: int) -> None:
        """Open the dropdown `field` and tap its option `index` (of `options`), wherever the menu opens."""
        from locate import menu_rows

        before = self.capture()
        after = self.click(field.cx, field.cy)
        self.click(*menu_rows(before, after, field, options)[index])

    def tap(self, x: float, y: float) -> None:
        """A real click at dp (x, y) without waiting for the screen to settle (a spinner never does)."""
        self.window.click(x * self.scale, y * self.scale)

    def type(self, text: str) -> None:
        self.window.type_text(text)

    def press(self, *keys: str) -> None:
        self.window.press(*keys)

    def scroll(self, x: float, y: float, notches: int) -> Image.Image:
        """Turn the wheel over dp (x, y) (positive: towards the end), then the settled screen."""
        self.window.scroll(x * self.scale, y * self.scale, notches)
        return self.capture()

    def reset(self) -> None:
        """The demo data as it started (tests that change data call this in `finally`)."""
        self.newest = self.send("reset")

    def wait_until(self, check, timeout: float = 15, what: str = "the app"):
        """Poll `check()` until it returns something truthy; that value, or a failure naming `what`."""
        deadline = time.monotonic() + timeout
        while not (result := check()):
            if time.monotonic() > deadline:
                raise AssertionError(f"{what} did not happen within {timeout:.0f}s")
            time.sleep(0.2)
        return result

    def quit(self) -> None:
        try:
            self.send("quit")
            self.proc.wait(timeout=30)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            self._log.close()


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("rendered tests drive a Windows desktop window")
    driven = DrivenApp(tmp_path_factory.mktemp("driver") / "driver.log")
    yield driven
    driven.quit()


@pytest.fixture
def scheme():
    """The palette the driver shows by default (gruvbox), per mode."""
    from ui.theme import get_theme

    return lambda mode="dark": get_theme("gruvbox").scheme(dark=mode == "dark")
