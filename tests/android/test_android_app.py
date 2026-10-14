#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/14 01:08:28.522356
Revised: 2026/10/14 04:13:36.066509

The release APK on an Android emulator (scripts/android_phone.py), read through its log in logcat: what only the
phone shows. Events survive the process being killed, Share opens Android's own share sheet, and a backup restores
through Android's file picker and survives a restart. Marker `android`; needs dist/timtapper-<version>-x86_64.apk.
"""

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "rendered"))  # locate and pixels: finding controls by their colours

pytestmark = pytest.mark.android

PACKAGE = "com.breren.timtapper"
BOOT_TIMEOUT = 60  # seconds from launch to the app's "started" line
STEP_TIMEOUT = 20
SHARE_SHEETS = ("ChooserActivity", "ResolverActivity")
BACKUP_NAME = "timtapper-backup-test.json"
GOLDEN_EVENTS = 2  # in tests/backup/golden/v3.json


def release_apk() -> Path:
    from build_android import project_version

    return ROOT / "dist" / f"timtapper-{project_version()}-x86_64.apk"


class AndroidApp:
    """The release APK on the phone, read through its log lines in logcat (tag flet.python)."""

    def __init__(self, phone) -> None:
        self.phone = phone

    @property
    def size(self) -> tuple[float, float]:
        """The app area in dp."""
        shot = self.phone.screenshot()
        return shot.width / self.phone.scale, shot.height / self.phone.scale

    def capture(self):
        """The app area in dp (nearest-neighbour, so each pixel keeps its exact theme colour)."""
        from PIL import Image

        shot = self.phone.screenshot()
        size = (round(shot.width / self.phone.scale), round(shot.height / self.phone.scale))
        return shot.resize(size, Image.Resampling.NEAREST)

    def share_button(self):
        """ "Share result": the full-width bar filled in the default theme's primary colour (the phone is in light
        mode, so the app is too)."""
        from locate import filled
        from ui.theme import get_theme

        primary = get_theme(None).scheme(dark=False).primary
        deadline = time.monotonic() + STEP_TIMEOUT
        while not (bars := [b for b in filled(self.capture(), primary, min_w=300) if b.h >= 40]):
            assert time.monotonic() < deadline, "no Share result button on screen"
            time.sleep(0.5)
        return bars[0]

    def logs(self) -> list[str]:
        return self.phone.run("logcat", "-d", "-s", "flet.python:*").splitlines()

    def start(self, *, fresh: bool) -> list[str]:
        """Launch the app (on a fresh install's empty data, or on what it saved last time) and wait until it has
        started; returns this start's log lines."""
        self.phone.stop(PACKAGE)
        if fresh:
            self.phone.clear(PACKAGE)
        self.phone.run("logcat", "-c")
        self.phone.launch(PACKAGE)
        self.wait_for("timtapper.main: started", BOOT_TIMEOUT)
        time.sleep(1.5)  # the first frame after the start line
        return self.logs()

    def wait_for(self, text: str, timeout: float = STEP_TIMEOUT) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = next((line for line in self.logs() if text in line), None)
            if found:
                return found
            time.sleep(0.5)
        raise AssertionError(f"no log line with {text!r} after {timeout}s; last lines: {self.logs()[-5:]}")

    def tap(self, x: float, y: float, then: str | None = None) -> None:
        """A touch at dp (x, y) of the app area, then the log line it should produce."""
        self.phone.tap(x * self.phone.scale, y * self.phone.scale)
        if then:
            self.wait_for(then)
        time.sleep(1.5)  # the screen settles

    def new_event(self) -> None:
        width, height = self.size
        self.tap(width - 80, height - 124, then="created")  # the floating "New event" button

    def wait_for_activity(self, names: tuple[str, ...], timeout: float = STEP_TIMEOUT) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            top = self.phone.top_activity()
            if any(name in top for name in names):
                return top
            time.sleep(0.5)
        raise AssertionError(f"none of {names} came up within {timeout}s; on screen: {self.phone.top_activity()}")


@pytest.fixture(scope="module")
def phone(tmp_path_factory):
    apk = release_apk()
    if not apk.is_file():
        pytest.skip(f"no {apk.name}: run `uv run python scripts/build_android.py apk` first")
    from android_phone import Phone
    from build_android import BuildError

    try:
        device = Phone(tmp_path_factory.mktemp("android") / "emulator.log")
    except BuildError as exc:
        pytest.skip(str(exc))
    try:
        device.install(apk)
        yield device
    finally:
        device.stop(PACKAGE)
        device.uninstall(PACKAGE)
        device.close()


@pytest.fixture
def app(phone):
    yield AndroidApp(phone)
    phone.keys("back")  # a share sheet left open by a failed test


def test_events_survive_a_restart(app):
    first = app.start(fresh=True)
    assert any("138 added" in line for line in first)  # a fresh install: the bundled leaders go in
    app.new_event()
    assert any("event 1 created" in line for line in app.logs())
    again = app.start(fresh=False)  # the process killed, as Android does to a backgrounded app
    assert not [line for line in again if "138 added" in line]  # the saved database came back, leaders and all
    app.new_event()
    assert any("event 2 created" in line for line in app.logs())  # event 1 is still there


def test_share_opens_the_system_share_sheet(app):
    app.start(fresh=True)
    app.new_event()
    share = app.share_button()
    app.tap(share.cx, share.cy, then="rendered event card")
    assert app.wait_for_activity(SHARE_SHEETS)


def test_a_backup_restores_through_the_system_file_picker(app, phone):
    """The backup is picked in Android's own file picker (as a person picks it), restored, and still there after a
    restart."""
    golden = ROOT / "tests" / "backup" / "golden" / "v3.json"
    on_phone = f"/sdcard/Download/{BACKUP_NAME}"
    phone.run("push", str(golden), on_phone)
    # index it, as a downloaded file would be, so the file picker lists it
    phone.shell("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{on_phone}")
    try:
        app.start(fresh=True)
        width, height = app.size
        app.tap(width * 5 / 6, height - 40)  # the Settings tab
        for _ in range(4):  # the backup buttons sit below the theme grid
            if phone.find_on_screen("Import backup"):
                break
            phone.drag(width / 2 * phone.scale, height / 2 * phone.scale, -300 * phone.scale)
        phone.tap_on_screen("Import backup")
        app.wait_for_activity(("documentsui",))
        # the picker opens on Recent, which lists the file only once it has been picked before: else go to Downloads
        if phone.wait_on_screen(BACKUP_NAME, timeout=3) is None:
            phone.tap_on_screen("Show roots")
            phone.tap_on_screen("Downloads")
        phone.tap_on_screen(BACKUP_NAME)
        phone.tap_on_screen("Restore", exact=True)  # the button, not the dialog's "Restore this backup?"
        app.wait_for(f"restored {GOLDEN_EVENTS} events from backup")
        app.start(fresh=False)
        app.new_event()
        assert any(f"event {GOLDEN_EVENTS + 1} created" in line for line in app.logs())  # the restored ones stayed
    finally:
        phone.shell("rm", "-f", on_phone)
