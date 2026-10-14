#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 01:08:28.414462
Revised: 2026/10/14 01:08:28.414462

The real desktop app (main.py) on a fresh data folder, read through its log: what only Windows shows. Events
survive the app being killed, Share reaches Windows' share or save dialog, and a backup restores through Windows'
Open dialog and stays. Marker `desktop` (it takes over the mouse); close a running timtapper first.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "src" / "timtapper"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "rendered"))  # locate and pixels: finding controls by their colours

pytestmark = pytest.mark.desktop

TITLE = "timtapper"  # main.py's window title: the real app, not the driver's
BOOT_TIMEOUT = 60  # seconds from launch to the app's "started" line
STEP_TIMEOUT = 20
GOLDEN = ROOT / "tests" / "backup" / "golden" / "v3.json"
GOLDEN_EVENTS = 2


class DesktopApp:
    """The real desktop app (main.py, as `flet run` starts it) on its own data folder, read through its log."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.log_path = folder / "app.log"
        self.proc: subprocess.Popen | None = None
        self.window = None

    def start(self) -> list[str]:
        """Start the app on whatever its data folder holds and wait until it has started; this start's log lines."""
        from app_window import AppWindow

        start = len(self.logs())
        env = os.environ | {
            "FLET_APP_STORAGE_DATA": str(self.folder / "data"),
            "FLET_APP_STORAGE_TEMP": str(self.folder / "temp"),
            "PYTHONUTF8": "1",
        }
        with self.log_path.open("a", encoding="utf-8") as log:
            self.proc = subprocess.Popen(
                [sys.executable, "main.py"], cwd=APP_DIR, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        self.wait_for("timtapper.main: started", start, BOOT_TIMEOUT)
        self.window = AppWindow(TITLE)
        self.window.wait_open()
        self.window.capture()
        # the first click after the window opens can be lost while it takes focus: spend it on the inert title
        self.window.click(200 * self.window.scale, 28 * self.window.scale)
        return self.logs()[start:]

    def kill(self) -> None:
        """End the app the hard way, Python and the Flutter client both (as a crash or a shutdown would)."""
        if self.proc is not None and self.proc.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True, check=False)
            self.proc.wait(timeout=30)
        deadline = time.monotonic() + 15
        while self._window_open() and time.monotonic() < deadline:
            time.sleep(0.2)

    def _window_open(self) -> bool:
        from app_window import find_window

        return bool(find_window(TITLE))

    def logs(self) -> list[str]:
        if not self.log_path.is_file():
            return []
        return self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()

    def wait_for(self, text: str, start: int = 0, timeout: float = STEP_TIMEOUT) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = next((line for line in self.logs()[start:] if text in line), None)
            if found:
                return found
            if self.proc is not None and self.proc.poll() is not None:
                raise AssertionError(f"the app exited (code {self.proc.returncode}); log: {self.log_path}")
            time.sleep(0.25)
        raise AssertionError(f"no log line with {text!r} after {timeout}s; last lines: {self.logs()[-5:]}")

    # ---- the screen, in dp ---------------------------------------------------------------
    def capture(self):
        from PIL import Image

        img = self.window.capture()
        scale = self.window.scale
        return (
            img
            if scale == 1
            else img.resize((round(img.width / scale), round(img.height / scale)), Image.Resampling.NEAREST)
        )

    def tap(self, x: float, y: float, then: str | None = None) -> None:
        start = len(self.logs())
        self.window.click(x * self.window.scale, y * self.window.scale)
        if then:
            self.wait_for(then, start)
        time.sleep(1)

    def new_event(self) -> str:
        img = self.capture()
        start = len(self.logs())
        self.tap(img.width - 80, img.height - 124)  # the floating "New event" button
        return self.wait_for("created", start)

    def scheme(self):
        """The palette on screen: the theme and mode you last chose (saved preferences are the computer's, not the
        data folder's), found by the page's background colour."""
        from pixels import rgb
        from ui.theme import THEMES

        img = self.capture()
        bg = img.getpixel((4, img.height // 2))
        for theme in THEMES.values():
            for dark in (True, False):
                scheme = theme.scheme(dark=dark)
                if rgb(scheme.bg) == bg:
                    return scheme
        raise AssertionError(f"no theme has the background {bg}")


@pytest.fixture
def app(tmp_path):
    if sys.platform != "win32":
        pytest.skip("the desktop app is tested on Windows")
    from app_window import find_window

    if find_window(TITLE):
        pytest.skip("close the running timtapper first: its window would be driven instead")
    desktop = DesktopApp(tmp_path)
    yield desktop
    desktop.kill()


def test_events_survive_a_restart(app):
    first = app.start()
    assert any("138 added" in line for line in first)  # a fresh data folder: the bundled leaders go in
    assert "event 1 created" in app.new_event()
    app.kill()
    again = app.start()
    assert not [line for line in again if "138 added" in line]  # the saved database came back, leaders and all
    assert "event 2 created" in app.new_event()  # event 1 is still there


def test_share_reaches_the_systems_share_or_save_dialog(app):
    from locate import filled

    app.start()
    app.new_event()
    s = app.scheme()
    share = [b for b in filled(app.capture(), s.primary, min_w=300) if b.h >= 40][0]
    start = len(app.logs())
    app.window.click(share.cx * app.window.scale, share.cy * app.window.scale)
    # the Windows share UI where share_plus has one, else the save dialog: either is the system's own
    opened = app.wait_for("share sheet", start)
    if "falling back to save dialog" in opened:
        time.sleep(1.5)
        app.window.press("escape", focus=False)  # to the dialog, which has the focus now
        app.wait_for("cancelled", start)


def test_a_backup_restores_through_the_systems_open_dialog(app):
    from locate import confirm_button, filled

    app.start()
    img = app.capture()
    app.tap(img.width * 5 / 6, img.height - 40)  # the Settings tab
    for _ in range(4):  # the backup buttons sit below the theme grid
        img = app.capture()
        app.window.scroll(img.width / 2 * app.window.scale, img.height / 2 * app.window.scale, 10)
    s = app.scheme()
    img = app.capture()
    tonal = filled(img, s.tint(s.secondary, 0.28), min_w=100, min_h=28, max_h=60)
    export = tonal[-1]  # Export backup, the last tonal button; Import backup is the outlined one under it
    app.tap(export.x0 + 60, export.y1 + 26)
    time.sleep(2)  # the open dialog takes the focus, its file name box first
    app.window.type_text(str(GOLDEN), focus=False)
    app.window.press("enter", focus=False)
    time.sleep(2)
    button = confirm_button(app.capture(), s)  # "Restore this backup?"
    app.tap(button.cx, button.cy, then=f"restored {GOLDEN_EVENTS} events from backup")
    app.kill()
    app.start()
    assert f"event {GOLDEN_EVENTS + 1} created" in app.new_event()  # the restored ones stayed
