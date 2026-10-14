#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 22:03:51.346234
Revised: 2026/10/14 08:10:02.410702

The built web app (scripts/build_web.py -> build/web), served under /timtapper/ as GitHub Pages and Codeberg Pages
serve it, driven in headless Chrome: what only a real browser shows, i.e. that the data folder survives a reload,
that sharing and backups reach the browser as downloads, and that a backup restores in another browser.

Marker `web`, kept out of the default run: it needs a build (a few minutes) and Chrome. Taps are at the phone-sized
viewport's coordinates (412 x 892), and each step waits for the app's own log line rather than a fixed time.
"""

import json
import sys
import time
import zipfile
from pathlib import Path

import pytest
from PIL import Image

pytestmark = pytest.mark.web

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SITE = ROOT / "build" / "web"
VIEWPORT = {"width": 412, "height": 892}
BOOT_TIMEOUT = 90  # seconds: Pyodide and the app's packages load on the first visit
STEP_TIMEOUT = 20
NO_WEB_SHARE = "delete Navigator.prototype.share; delete Navigator.prototype.canShare;"

NEW_EVENT = (325, 768)
BACK = (28, 28)
SHARE = (205, 469)  # on an event with no leader yet
SETTINGS_TAB = (343, 860)
EXPORT = (98, 481)  # after scrolling Settings down by 600
IMPORT = (290, 481)
RESTORE = (297, 503)


def _site_built() -> bool:
    archive = SITE / "assets" / "app" / "app.zip"
    if not archive.is_file():
        return False
    with zipfile.ZipFile(archive) as z:
        return "assets/data/leaders.json" in z.namelist()


@pytest.fixture(scope="module")
def base_url():
    if not _site_built():
        pytest.skip("no web build: run `uv run python scripts/build_web.py` first")
    from serve_site import SiteServer

    server = SiteServer(SITE).start()
    yield server.url
    server.stop()


class WebApp:
    """One browser profile (its own IndexedDB) on the served app; `logs` holds the console, Python's included."""

    def __init__(self, playwright, profile: Path, url: str, *, web_share: bool = True) -> None:
        self.url = url
        self.context = playwright.chromium.launch_persistent_context(
            str(profile), channel="chrome", headless=True, viewport=VIEWPORT, accept_downloads=True
        )
        if not web_share:
            self.context.add_init_script(NO_WEB_SHARE)
        self.page = self.context.pages[0]
        self.logs: list[str] = []
        self.page.on("console", lambda m: self.logs.append(m.text))

    def open(self) -> list[str]:
        """Load the app at its start page and wait until it has started; returns this boot's log lines."""
        start = len(self.logs)
        self.page.goto(self.url, wait_until="load")
        return self._booted(start)

    def reload(self) -> list[str]:
        start = len(self.logs)
        self.page.reload(wait_until="load")
        return self._booted(start)

    def _booted(self, start: int) -> list[str]:
        self.wait_for("timtapper.main: started", start, BOOT_TIMEOUT)
        self.page.wait_for_timeout(1000)  # the first frame after the start line
        return self.logs[start:]

    def wait_for(self, text: str, start: int = 0, timeout: float = STEP_TIMEOUT) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = next((line for line in self.logs[start:] if text in line), None)
            if found:
                return found
            self.page.wait_for_timeout(250)
        raise AssertionError(f"no log line with {text!r} after {timeout}s; last lines: {self.logs[-5:]}")

    def tap(self, xy: tuple[int, int], then: str | None = None) -> None:
        start = len(self.logs)
        self.page.mouse.click(*xy)
        if then:
            self.wait_for(then, start)
        self.page.wait_for_timeout(1500)  # the screen settles, and any save to IndexedDB completes

    def download(self, xy: tuple[int, int], into: Path) -> Path:
        with self.page.expect_download(timeout=STEP_TIMEOUT * 1000) as info:
            self.page.mouse.click(*xy)
        into.mkdir(parents=True, exist_ok=True)
        target = into / info.value.suggested_filename
        info.value.save_as(target)
        return target

    def open_backup_section(self) -> None:
        self.tap(SETTINGS_TAB)
        self.page.mouse.move(200, 400)
        self.page.mouse.wheel(0, 600)
        self.page.wait_for_timeout(1500)

    def close(self) -> None:
        self.context.close()


@pytest.mark.regression
def test_events_survive_a_reload_on_any_screen(playwright, base_url, tmp_path):
    """The web app's database lived in memory only, so a reload lost every event; and a reload on an inner
    screen asked the static host for /event/1, a 404."""
    app = WebApp(playwright, tmp_path / "profile", base_url, web_share=False)
    try:
        first = app.open()
        assert any("browser storage loaded" in line for line in first)
        assert any("138 added" in line for line in first)  # a new browser: the bundled leaders go in
        app.tap(NEW_EVENT, then="event 1 created")
        assert app.page.url.endswith("#/event/1")
        again = app.reload()  # on the event screen
        app.tap(BACK)
        app.open_backup_section()
        backup = app.download(EXPORT, tmp_path / "downloads")
    finally:
        app.close()
    assert not [line for line in again if "138 added" in line]  # the saved database came back, leaders and all
    assert not any("404" in line for line in again)
    assert [e["name"] for e in json.loads(backup.read_text(encoding="utf-8"))["events"]] == ["Local #1"]


@pytest.mark.regression
def test_share_downloads_the_card_where_the_browser_cannot_share(playwright, base_url, tmp_path):
    """The web app handed the browser a path in its in-memory file system: a 404, and no card."""
    app = WebApp(playwright, tmp_path / "profile", base_url, web_share=False)
    try:
        app.open()
        app.tap(NEW_EVENT, then="event 1 created")
        card = app.download(SHARE, tmp_path / "downloads")
    finally:
        app.close()
    with Image.open(card) as image:
        assert (image.format, image.size) == ("PNG", (1080, 1350))


def test_backup_restores_in_another_browser_and_stays(playwright, base_url, tmp_path):
    source = WebApp(playwright, tmp_path / "source", base_url, web_share=False)
    try:
        source.open()
        source.tap(NEW_EVENT, then="event 1 created")
        source.open()  # back to the start page, the events tab
        source.open_backup_section()
        backup = source.download(EXPORT, tmp_path / "exported")
    finally:
        source.close()
    events = json.loads(backup.read_text(encoding="utf-8"))["events"]
    assert len(events) == 1

    target = WebApp(playwright, tmp_path / "target", base_url, web_share=False)
    try:
        target.open()
        target.open_backup_section()
        with target.page.expect_file_chooser() as chooser:
            target.page.mouse.click(*IMPORT)
        chooser.value.set_files(str(backup))
        target.page.wait_for_timeout(2000)
        target.tap(RESTORE, then="restored 1 events")
        target.reload()
        target.open_backup_section()
        again = target.download(EXPORT, tmp_path / "again")
    finally:
        target.close()
    assert json.loads(again.read_text(encoding="utf-8"))["events"] == events
