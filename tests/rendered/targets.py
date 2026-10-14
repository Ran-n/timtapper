#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:14:27.670040
Revised: 2026/10/14 08:10:02.328580

The real app on each platform it ships to, behind one interface, so every rendered test runs on all of them:

    desktop   scripts/app_driver.py in a Windows window: Win32 captures, mouse and keyboard (marker `desktop`)
    web       the driven web build in headless Chrome through Playwright (marker `web`)
    android   the driven APK on an emulator through adb (marker `android`)

Each start the same demo data (scripts/demo_driver.py) and answer the same driver commands; captures come back in
dp and taps go to dp coordinates, whatever the platform's pixel density. The browser and the phone are given the
desktop window's client area (396 x 853 dp, 344 dp wide at the 360 dp minimum window).
"""

import io
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image, ImageChops

from core.logging import get_logger

_log = get_logger("tests.rendered.targets")

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

REPLY_TIMEOUT = 60  # seconds a command may take; the first reply waits for the app to start
BOOT_TIMEOUT = 180  # a browser loading Pyodide, or a phone starting the APK, the first time
# the desktop window's client area at 100% scaling (the 412 x 892 dp window minus its frame), which the browser and
# the phone are sized to as well, so a layout is asserted on the same dp everywhere
CLIENT_HEIGHT = 853
WINDOW_FRAME = 16
DEFAULT_WINDOW_WIDTH = 412


def client_width(window_width: int) -> int:
    """The dp a `show` width gives the app: 0 is the default window; 360 (the minimum) leaves 344."""
    return (window_width or DEFAULT_WINDOW_WIDTH) - WINDOW_FRAME


class DriverError(RuntimeError):
    """The app driver failed a command, exited, or stopped answering."""


class Target:
    """The real app on one platform, as the rendered tests see it: driver commands, settled captures in dp, and real
    taps, typing and scrolling at dp coordinates. Subclasses say how to grab the screen and send input."""

    name = ""
    types_unicode = True  # whether type() can enter any character, or ASCII only
    newest = 0

    # ---- per platform ------------------------------------------------------------
    @property
    def scale(self) -> float:
        """Physical pixels per dp."""
        raise NotImplementedError

    def _send(self, cmd: str, **args):
        """Send one driver command and return its result."""
        raise NotImplementedError

    def grab(self) -> Image.Image:
        """The app's screen now, in physical pixels."""
        raise NotImplementedError

    def tap_px(self, x: float, y: float) -> None:
        raise NotImplementedError

    def type(self, text: str) -> None:
        raise NotImplementedError

    def press(self, *keys: str) -> None:
        """Press `keys` together ("enter", "tab", "escape", "backspace", or "ctrl", "a" to select all)."""
        raise NotImplementedError

    def scroll_px(self, x: float, y: float, notches: int) -> None:
        raise NotImplementedError

    def clear_text(self) -> None:
        """Empty the focused text field: select everything, then delete it."""
        self.press("ctrl", "a")
        self.press("backspace")

    def resize(self, window_width: int) -> None:
        """Give the app the room a desktop window `window_width` dp wide has (0: the default)."""

    def quit(self) -> None:
        raise NotImplementedError

    # ---- the same everywhere -----------------------------------------------------
    def send(self, cmd: str, **args):
        """One driver command (scripts/demo_driver.py) and its result; a "show" first gives the app the room its
        `width` asks for, wherever the platform takes that from."""
        if cmd == "show":
            self.resize(args.get("width", 0))
        return self._send(cmd, **args)

    def show(self, route: str, mode: str = "dark", width: int = 0, lang: str = "en") -> Image.Image:
        self.send("show", route=route, mode=mode, width=width, lang=lang)
        return self.capture()

    def settled(self, settle: float = 0.4, timeout: float = 8.0) -> Image.Image:
        """A capture once rendering has settled: two grabs `settle` seconds apart that match.
        Waits out route transitions, sheet animations, ink ripples and image loads."""
        deadline = time.monotonic() + timeout
        last = self.grab()
        while True:
            time.sleep(settle)
            now = self.grab()
            if now.size == last.size and ImageChops.difference(now, last).getbbox() is None:
                return now
            if time.monotonic() > deadline:
                raise DriverError(f"{self.name}: the screen never settled within {timeout:.0f}s")
            last = now

    def capture(self) -> Image.Image:
        """The settled screen in dp, whatever the pixel density: every size and position the tests assert is in dp.
        Nearest-neighbour keeps each pixel an exact theme colour (no blended edges to mis-match)."""
        return self.to_dp(self.settled())

    def to_dp(self, img: Image.Image) -> Image.Image:
        if self.scale == 1:
            return img
        size = (round(img.width / self.scale), round(img.height / self.scale))
        return img.resize(size, Image.Resampling.NEAREST)

    def click(self, x: float, y: float) -> Image.Image:
        """A real tap at dp (x, y) of a capture, then the settled screen it produced."""
        self.tap(x, y)
        return self.capture()

    def tap(self, x: float, y: float) -> None:
        """A real tap at dp (x, y) without waiting for the screen to settle (a spinner never does)."""
        self.tap_px(x * self.scale, y * self.scale)

    def scroll(self, x: float, y: float, notches: int) -> Image.Image:
        """Scroll over dp (x, y) by `notches` mouse-wheel notches' worth (positive: towards the end), then the
        settled screen."""
        self.scroll_px(x * self.scale, y * self.scale, notches)
        return self.capture()

    def fields(self, s) -> list:
        """The outlined input fields on screen now, in dp (see locate.fields)."""
        from locate import fields

        return fields(self.settled(), s, self.scale)

    def rings(self, color: str, **size) -> list:
        """Outlines in `color` on screen now (outlined buttons), in dp (see locate.rings)."""
        from locate import rings

        return rings(self.settled(), color, self.scale, **size)

    def pick(self, field, index: int, options: int) -> None:
        """Open the dropdown `field` and tap its option `index` (of `options`), wherever the menu opens."""
        from locate import menu_rows

        before = self.capture()
        after = self.click(field.cx, field.cy)
        self.click(*menu_rows(before, after, field, options)[index])

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


# ---- desktop ---------------------------------------------------------------------------
class DesktopTarget(Target):
    """The app in a Windows window: scripts/app_driver.py runs it (commands on stdin), scripts/app_window.py captures
    it and sends real mouse and keyboard input."""

    name = "desktop"

    def __init__(self, log_path: Path) -> None:
        from app_window import AppWindow

        self.log_path = log_path
        self._log_file = log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "app_driver.py"), "serve"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log_file,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
        )
        self._replies: queue.Queue[dict | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.window = AppWindow()
        self.newest = self._next()["newest"]
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

    def _send(self, cmd: str, **args):
        self.proc.stdin.write(json.dumps({"cmd": cmd, **args}) + "\n")
        self.proc.stdin.flush()
        return self._next().get("result")

    @property
    def scale(self) -> float:
        return self.window.scale

    def grab(self) -> Image.Image:
        return self.window.grab()

    def tap_px(self, x: float, y: float) -> None:
        self.window.click(x, y)

    def type(self, text: str) -> None:
        self.window.type_text(text)

    def press(self, *keys: str) -> None:
        self.window.press(*keys)

    def scroll_px(self, x: float, y: float, notches: int) -> None:
        self.window.scroll(x, y, notches)

    def quit(self) -> None:
        try:
            self.send("quit")
            self.proc.wait(timeout=30)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            self._log_file.close()


# ---- the driven builds: web and Android ----------------------------------------------------
class RemoteTarget(Target):
    """A driven build (scripts/build_driven.py) that polls the harness for its commands (scripts/serve_site.py)."""

    def _listen(self, site: Path | None, port: int = 0) -> None:
        from serve_site import DriverChannel, SiteServer

        self.channel = DriverChannel()
        self.server = SiteServer(site, self.channel, port).start()

    def _ready(self) -> None:
        self.newest = self._result(self.channel.wait(0, BOOT_TIMEOUT))["newest"]

    def _result(self, reply: dict):
        if not reply.get("ok"):
            raise DriverError(f"{self.name}: {reply.get('error')}")
        return reply.get("result", reply)

    def _send(self, cmd: str, **args):
        return self._result(self.channel.send(cmd, REPLY_TIMEOUT, **args))

    def _stop_listening(self) -> None:
        self.server.stop()


class WebTarget(RemoteTarget):
    """The driven web build in headless Chrome at device scale 1, sized like the desktop window's client area; taps
    are touches (as on a phone, and no mouse left hovering over the next capture)."""

    name = "web"
    KEYS = {"enter": "Enter", "tab": "Tab", "escape": "Escape", "backspace": "Backspace", "ctrl": "Control", "a": "a"}
    WHEEL_NOTCH = 100  # Chrome's pixels per wheel notch

    def __init__(self, site: Path, playwright) -> None:
        """`playwright`: the run's one sync Playwright (tests/conftest.py), which this target leaves running."""
        self._listen(site)
        self.logs: list[str] = []
        try:
            self.browser = playwright.chromium.launch(channel="chrome", headless=True)
            self.context = self.browser.new_context(
                viewport=self._viewport(0), device_scale_factor=1, has_touch=True, accept_downloads=True
            )
            self.page = self.context.new_page()
            self.page.on("console", lambda m: self.logs.append(m.text))
            self.page.goto(self.server.url, wait_until="load")
            self._ready()
        except Exception:
            self.quit()
            raise

    @staticmethod
    def _viewport(window_width: int) -> dict:
        return {"width": client_width(window_width), "height": CLIENT_HEIGHT}

    @property
    def scale(self) -> float:
        return 1.0

    def resize(self, window_width: int) -> None:
        if self.page.viewport_size != self._viewport(window_width):
            self.page.set_viewport_size(self._viewport(window_width))

    def grab(self) -> Image.Image:
        return Image.open(io.BytesIO(self.page.screenshot())).convert("RGB")

    def tap_px(self, x: float, y: float) -> None:
        self.page.touchscreen.tap(x, y)

    def type(self, text: str) -> None:
        self.page.keyboard.type(text, delay=20)

    def press(self, *keys: str) -> None:
        self.page.keyboard.press("+".join(self.KEYS[k] for k in keys))
        time.sleep(0.05)

    def scroll_px(self, x: float, y: float, notches: int) -> None:
        self.page.mouse.move(x, y)
        self.page.mouse.wheel(0, notches * self.WHEEL_NOTCH)
        # park the pointer off the page, so hover highlights don't leak into the next capture
        self.page.mouse.move(-1, -1)
        time.sleep(0.1)

    def quit(self) -> None:
        try:
            if hasattr(self, "page"):
                self.send("quit")
        finally:
            for close in ("context", "browser"):
                if hasattr(self, close):
                    getattr(self, close).close()
            self._stop_listening()


class AndroidTarget(RemoteTarget):
    """The driven APK on an Android phone (scripts/android_phone.py: the emulator, booted for the session when none
    runs): screencap captures, `input` touches, keys and drags. Everything it changes on the phone (the installed
    app, the port mapping, the display size, a booted emulator) is undone in quit()."""

    name = "android"
    types_unicode = False  # `adb shell input text` sends key events, which carry ASCII only
    PACKAGE = "com.breren.timtapper.driven"
    NOTCH_DP = 50  # dp a drag moves per mouse-wheel notch asked for
    CLEAR_KEYS = 80  # backspaces that empty any field the tests type into

    def __init__(self, apk: Path, log_path: Path) -> None:
        from android_phone import Phone
        from driven_main import DRIVER_PORT

        self.phone = Phone(log_path)
        self.port = DRIVER_PORT
        self.width: int | None = None
        try:
            self.phone.install(apk)
            self._listen(None, DRIVER_PORT)
            self.phone.run("reverse", f"tcp:{DRIVER_PORT}", f"tcp:{DRIVER_PORT}")
            self.resize(0)
            self.phone.clear(self.PACKAGE)  # a fresh database: the driven app seeds the demo into it
            self.phone.launch(self.PACKAGE)
            self._ready()
        except Exception:
            self.quit()
            raise

    @property
    def scale(self) -> float:
        return self.phone.scale

    def resize(self, window_width: int) -> None:
        if window_width != self.width:
            self.phone.size_app(client_width(window_width), CLIENT_HEIGHT)
            self.width = window_width

    def grab(self) -> Image.Image:
        return self.phone.screenshot()

    def tap_px(self, x: float, y: float) -> None:
        self.phone.tap(x, y)

    def type(self, text: str) -> None:
        self.phone.text(text)

    def press(self, *keys: str) -> None:
        if len(keys) == 1:
            self.phone.keys(*keys)
        else:
            self.phone.combination(*keys)

    def clear_text(self) -> None:
        """To the field's end, then backspace over everything: Flutter on Android doesn't take adb's ctrl+a."""
        self.phone.keys("end", *["backspace"] * self.CLEAR_KEYS)

    def scroll_px(self, x: float, y: float, notches: int) -> None:
        """Drags of at most the room above (x, y), so the finger never leaves the app at its top."""
        remaining = abs(notches) * self.NOTCH_DP * self.scale
        room = y - 80 * self.scale
        while remaining > 0:
            step = min(remaining, room)
            self.phone.drag(x, y, -step if notches > 0 else step)
            remaining -= step

    def quit(self) -> None:
        """Undo everything this target did on the phone, and shut down the emulator if it booted it."""
        try:
            if hasattr(self, "channel"):
                try:
                    self.send("quit")
                except DriverError as exc:  # the app is gone already: it's stopped and removed below either way
                    _log.warning("android: the driven app did not answer quit: %s", exc)
                self._stop_listening()
            self.phone.stop(self.PACKAGE)
            self.phone.run("reverse", "--remove", f"tcp:{self.port}", check=False)
            self.phone.uninstall(self.PACKAGE)
        finally:
            self.phone.close()


def open_target(name: str, tmp: Path, playwright=None) -> Target:
    """Start the app on target `name` (desktop, web or android), or raise pytest's skip when it can't run here.
    The web target drives Chrome through `playwright`, the run's shared sync Playwright."""
    import pytest

    if name == "desktop":
        if sys.platform != "win32":
            pytest.skip("the desktop target drives a Windows window")
        return DesktopTarget(tmp / "driver.log")
    from build_driven import artifact

    if name == "web":
        site = artifact("web")
        if not (site / "index.html").is_file():
            pytest.skip("no driven web build: run `uv run python scripts/build_driven.py web` first")
        return WebTarget(site, playwright)
    apk = artifact("apk")
    if not apk.is_file():
        pytest.skip(f"no driven APK ({apk.name}): run `uv run python scripts/build_driven.py apk` first")
    from build_android import BuildError, sdk_tool

    try:
        sdk_tool("platform-tools/adb")
    except BuildError as exc:
        pytest.skip(str(exc))
    return AndroidTarget(apk, tmp / "emulator.log")
