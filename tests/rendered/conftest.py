#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:03.055435
Revised: 2026/10/12 13:16:03.055435

One real app for the whole rendered-test session: scripts/app_driver.py runs it,
scripts/app_window.py captures and clicks it. Windows only; marked `desktop`.
"""

import json
import queue
import subprocess
import sys
import threading
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

    def show(self, route: str, mode: str = "dark", width: int = 0) -> Image.Image:
        self.send("show", route=route, mode=mode, width=width)
        return self.window.capture()

    def capture(self) -> Image.Image:
        return self.window.capture()

    def click(self, x: float, y: float) -> Image.Image:
        """A real click, then the settled screen it produced."""
        self.window.click(x, y)
        return self.window.capture()

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
