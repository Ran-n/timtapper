#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 23:47:06.054826
Revised: 2026/10/14 09:51:57.338853

Drive an Android phone, normally the test emulator, through adb (the Android SDK's platform-tools): boot it when
none is running, install and start apps, capture the screen between the system bars, and send real touches, keys
and drags. The phone counterpart of scripts/app_window.py, used by the Android rendered tests (tests/rendered/) and
the Android platform tests (tests/android/). The emulator image is the generic `generic_phone_api34` AVD unless
TIMTAPPER_AVD names another; ANDROID_SERIAL picks one of several running devices.
"""

import io
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from build_android import sdk_tool
from PIL import Image

from core.logging import get_logger

_log = get_logger("scripts.android_phone")

BOOT_TIMEOUT = 180  # seconds for a cold emulator boot
DEFAULT_AVD = "generic_phone_api34"  # Pixel 7 shape (1080 x 2400, 420 dpi), API 34, x86_64
SOFT_KEYBOARD_SETTING = "show_ime_with_hard_keyboard"
KEYCODES = {"enter": 66, "tab": 61, "escape": 111, "backspace": 67, "back": 4, "end": 123, "ctrl": 113, "a": 29}


class PhoneError(RuntimeError):
    """adb failed, or the phone didn't come up."""


class Phone:
    """An Android phone (an emulator) through adb. Uses the one already running, else boots the AVD `avd` headless
    and shuts it down again in close(); close() also puts back the display size and keyboard setting this changed.
    `avd` defaults to TIMTAPPER_AVD, else the generic test AVD."""

    def __init__(self, log_path: Path, avd: str | None = None) -> None:
        avd = avd or os.environ.get("TIMTAPPER_AVD", DEFAULT_AVD)
        self.adb = str(sdk_tool("platform-tools/adb"))
        self.log_path = log_path
        self.emulator: subprocess.Popen | None = None
        self._emulator_log = None
        self.serial = self._running_device()
        if self.serial is None:
            self.serial = self._boot(sdk_tool("emulator/emulator"), avd)
        self.density = int(re.search(r"(\d+)", self.shell("wm", "density")).group(1))
        self.insets = self._settled_bars()  # a size reset by an earlier session may still be taking effect
        self._resized = False
        self._sizes: dict[tuple[int, int], tuple[str, tuple[int, int]]] = {}  # app area -> display size, bars
        # typing goes through the (emulated) hardware keyboard: keep the on-screen one from covering the app.
        # close() puts the phone's own setting back
        self._ime_setting = self.shell("settings", "get", "secure", SOFT_KEYBOARD_SETTING).strip()
        self.shell("settings", "put", "secure", SOFT_KEYBOARD_SETTING, "0")

    # ---- adb ---------------------------------------------------------------------------
    def run(self, *args: str, binary: bool = False, check: bool = True, timeout: float = 120):
        command = [self.adb, *(["-s", self.serial] if self.serial else []), *args]
        result = subprocess.run(command, capture_output=True, check=False, timeout=timeout)
        if check and result.returncode:
            raise PhoneError(f"adb {' '.join(args[:2])} failed: {result.stderr.decode(errors='replace').strip()}")
        return result.stdout if binary else result.stdout.decode(errors="replace")

    def shell(self, *args: str, check: bool = True) -> str:
        return self.run("shell", " ".join(shlex.quote(a) for a in args), check=check)

    def _running_device(self) -> str | None:
        out = subprocess.run([self.adb, "devices"], capture_output=True, text=True, check=True).stdout
        online = [line.split()[0] for line in out.splitlines()[1:] if line.endswith("\tdevice")]
        wanted = os.environ.get("ANDROID_SERIAL")
        if wanted:
            return wanted if wanted in online else None
        return online[0] if online else None

    def _boot(self, emulator: Path, avd: str) -> str:
        _log.info("booting emulator %s", avd)
        self._emulator_log = self.log_path.open("w", encoding="utf-8")
        self.emulator = subprocess.Popen(
            [str(emulator), "-avd", avd, "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot-save"],
            stdout=self._emulator_log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if self.emulator.poll() is not None:
                raise PhoneError(f"emulator {avd} exited (code {self.emulator.returncode}); log: {self.log_path}")
            serial = self._running_device()
            if serial:
                booted = subprocess.run(
                    [self.adb, "-s", serial, "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True
                )
                if booted.stdout.strip() == "1":
                    return serial
            time.sleep(2)
        self._shut_down_emulator()
        raise PhoneError(f"emulator {avd} did not boot within {BOOT_TIMEOUT}s; log: {self.log_path}")

    # ---- apps ----------------------------------------------------------------------------
    def install(self, apk: Path) -> None:
        self.run("install", "-r", "-t", str(apk))

    def launch(self, package: str) -> None:
        self.shell("monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")

    def stop(self, package: str) -> None:
        self.shell("am", "force-stop", package)

    def clear(self, package: str) -> None:
        """The app's data deleted, as a fresh install has it."""
        self.shell("pm", "clear", package)

    def uninstall(self, package: str) -> None:
        self.run("uninstall", package, check=False)

    def top_activity(self) -> str:
        """The activity on screen now, e.g. "android/com.android.internal.app.ChooserActivity"."""
        activities = self.shell("dumpsys", "activity", "activities")
        found = re.search(r"topResumedActivity=ActivityRecord\{\S+ \S+ (\S+)", activities)
        return found.group(1) if found else ""

    def find_on_screen(self, label: str, exact: bool = False) -> tuple[int, int] | None:
        """The centre (physical pixels, whole screen) of the first on-screen element whose text or description is
        `label` (else, unless `exact`, contains it), from the accessibility tree: system screens and Flutter's
        semantics alike."""
        dump = self.run("exec-out", "uiautomator", "dump", "/dev/tty")
        nodes = [dict(re.findall(r'(\w[\w-]*)="([^"]*)"', n)) for n in re.findall(r"<node [^>]*>", dump)]
        labels = [(n, n.get("text", ""), n.get("content-desc", "")) for n in nodes]
        # an exact label first: "Preview the file x.json" (an icon beside the file) also contains "x.json"
        matches = [n for n, text, desc in labels if label in (text, desc)]
        if not exact:
            matches = matches or [n for n, text, desc in labels if label in text or label in desc]
        if not matches:
            return None
        x0, y0, x1, y1 = map(int, re.findall(r"\d+", matches[0].get("bounds", "")))
        return (x0 + x1) // 2, (y0 + y1) // 2

    def wait_on_screen(self, label: str, timeout: float = 20, exact: bool = False) -> tuple[int, int] | None:
        """Where an element labelled `label` (see find_on_screen) is, once it shows; None if it doesn't in time."""
        deadline = time.monotonic() + timeout
        while (found := self.find_on_screen(label, exact)) is None:
            if time.monotonic() > deadline:
                return None
            time.sleep(0.5)
        return found

    def tap_on_screen(self, label: str, timeout: float = 20, exact: bool = False) -> None:
        """Wait for an element labelled `label` (see find_on_screen) to show and stay put, then touch it: a dialog
        is listed while it still animates in, and Flutter ignores touches until it has."""
        deadline = time.monotonic() + timeout
        found = self.wait_on_screen(label, timeout, exact)
        while found is not None:
            time.sleep(0.5)
            again = self.find_on_screen(label, exact)
            if again == found:
                self.wait_still()
                self.shell("input", "tap", str(found[0]), str(found[1]))
                return
            if time.monotonic() > deadline:
                break
            found = again
        raise PhoneError(f"nothing labelled {label!r} stayed on screen within {timeout:.0f}s")

    # ---- the screen ------------------------------------------------------------------------
    @property
    def scale(self) -> float:
        """Physical pixels per dp."""
        return self.density / 160

    def bars(self) -> tuple[int, int]:
        """The status bar's and navigation bar's heights in pixels."""
        windows = self.shell("dumpsys", "window")
        top = re.search(r"type=statusBars frame=\[\d+,\d+\]\[\d+,(\d+)\]", windows)
        bottom = re.search(r"type=navigationBars frame=\[\d+,(\d+)\]\[\d+,(\d+)\]", windows)
        if not top or not bottom:
            raise PhoneError("could not read the status and navigation bars from `dumpsys window`")
        return int(top.group(1)), int(bottom.group(2)) - int(bottom.group(1))

    def size_app(self, width_dp: int, height_dp: int) -> None:
        """Size the display so apps get `width_dp` x `height_dp` between the status and navigation bars. The bars'
        heights change with the display size (the status bar follows the camera cutout, which is scaled), so the size
        is set again from the bars it produced until the space between them is right."""
        width, height = round(width_dp * self.scale), round(height_dp * self.scale)
        if (width, height) in self._sizes:  # found before: one resize, so the app sees a single change
            display, bars = self._sizes.pop((width, height))
            self.shell("wm", "size", display)
            self._resized = True
            if self._settled_bars() == bars:
                self._sizes[(width, height)] = (display, bars)
                self.insets = bars
                time.sleep(1)
                return
            _log.warning("the system bars at %s changed since last time; measuring again", display)
        top, bottom = self._settled_bars()
        for _ in range(3):
            self.shell("wm", "size", f"{width}x{height + top + bottom}")
            self._resized = True
            new = self._settled_bars()
            if new == (top, bottom):
                break
            top, bottom = new
        else:
            raise PhoneError(f"the system bars kept changing while sizing the display: {top}, {bottom}")
        self.insets = (top, bottom)
        self._sizes[(width, height)] = (f"{width}x{height + top + bottom}", self.insets)
        time.sleep(1)  # apps lay themselves out again

    def _settled_bars(self, timeout: float = 10) -> tuple[int, int]:
        """The bars once a new display size has taken: two readings half a second apart that agree (read straight
        after `wm size`, they can still be the old size's)."""
        deadline = time.monotonic() + timeout
        last = self.bars()
        while True:
            time.sleep(0.5)
            now = self.bars()
            if now == last:
                return now
            if time.monotonic() > deadline:
                raise PhoneError(f"the system bars never settled after resizing: {last} then {now}")
            last = now

    def wait_still(self, settle: float = 0.4, timeout: float = 8) -> None:
        """Wait until nothing moves between the system bars: two screenshots `settle` seconds apart that match (the
        status bar is left out: the emulator's network icons come and go)."""
        deadline = time.monotonic() + timeout
        last = self.screenshot().tobytes()
        while True:
            time.sleep(settle)
            now = self.screenshot().tobytes()
            if now == last:
                return
            if time.monotonic() > deadline:
                raise PhoneError(f"the screen never stood still within {timeout:.0f}s")
            last = now

    def screenshot(self) -> Image.Image:
        """What apps draw between the status bar and the navigation bar, in physical pixels. The bars are read again
        for every screenshot: after a resize (or a cold boot) they can still change after two readings agreed, and a
        crop from the old ones shifted the whole capture by a few pixels against its baseline. A capture taken while
        they move differs from the next one, so a settled capture is cropped as the app is laid out."""
        shot = Image.open(io.BytesIO(self.run("exec-out", "screencap", "-p", binary=True))).convert("RGB")
        self.insets = top, bottom = self.bars()  # taps (tap, drag) then follow this capture's crop
        return shot.crop((0, top, shot.width, shot.height - bottom))

    def tap(self, x: float, y: float) -> None:
        """A touch at pixel (x, y) of a screenshot()."""
        self.shell("input", "tap", str(round(x)), str(round(y + self.insets[0])))

    def text(self, text: str) -> None:
        """Type ASCII `text` into the focused field (adb's key events can't carry anything else)."""
        if not text.isascii():
            raise PhoneError(f"adb types ASCII only, not {text!r}")
        self.shell("input", "text", text.replace(" ", "%s"))

    def keys(self, *names: str) -> None:
        """Press keys one after another (KEYCODES names), in one adb call."""
        self.shell("input", "keyevent", *(str(KEYCODES[k]) for k in names))

    def combination(self, *names: str) -> None:
        """Press keys together (KEYCODES names), e.g. ctrl+a."""
        self.shell("input", "keycombination", *(str(KEYCODES[k]) for k in names))

    def drag(self, x: float, y: float, dy: float) -> None:
        """A finger drag from pixel (x, y) of a screenshot() by `dy` (negative: up) that stops before it lifts, so a
        list doesn't fling on past where the finger left it."""
        x, y0 = round(x), round(y + self.insets[0])
        y1 = round(y0 + dy)
        moves = "; ".join(f"input motionevent MOVE {x} {round(y0 + (y1 - y0) * i / 8)}" for i in range(1, 9))
        self.run("shell", f"input motionevent DOWN {x} {y0}; {moves}; sleep 0.3; input motionevent UP {x} {y1}")
        time.sleep(0.2)

    # ---- the end ---------------------------------------------------------------------------
    def close(self) -> None:
        try:
            if self._resized:
                self.shell("wm", "size", "reset", check=False)
            if self._ime_setting not in ("", "null"):
                self.shell("settings", "put", "secure", SOFT_KEYBOARD_SETTING, self._ime_setting, check=False)
            else:
                self.shell("settings", "delete", "secure", SOFT_KEYBOARD_SETTING, check=False)
        finally:
            self._shut_down_emulator()

    def _shut_down_emulator(self) -> None:
        """Only an emulator this Phone booted: one that was already running isn't ours to stop."""
        if self.emulator is None:
            return
        self.run("emu", "kill", check=False)
        try:
            self.emulator.wait(timeout=60)
        except subprocess.TimeoutExpired:
            _log.warning("emulator did not exit after `adb emu kill`; killing it")
            self.emulator.kill()
        self.emulator = None
        self._emulator_log.close()
        _log.info("emulator shut down")
