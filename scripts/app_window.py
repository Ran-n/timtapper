#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:02.424894
Revised: 2026/10/12 16:54:57.117944

Find, capture and click the running timtapper desktop window (Windows only).

The outside half of driving the real app: scripts/app_driver.py runs the app,
this module looks at it and pokes it the way a person would. Captures are the
window's client area in physical pixels (Pillow's ImageGrab(window=...));
clicks are real mouse events at client-area pixel coordinates, so they go
through Flutter's hit testing like a user's tap.
"""

import ctypes
import time
from ctypes import wintypes

from PIL import Image, ImageChops, ImageGrab

WINDOW_TITLE = "timtapper driven"  # unique, so a running copy of the app is never captured instead

_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004


class WindowError(RuntimeError):
    """The app window could not be found or captured."""


def _user32():
    user32 = ctypes.windll.user32
    # physical pixels everywhere, so capture and click coordinates agree on scaled displays
    # returns E_ACCESSDENIED (no exception) when this process already set it, which is fine
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    return user32


class AppWindow:
    def __init__(self, title: str = WINDOW_TITLE) -> None:
        self.title = title
        self.user32 = _user32()

    @property
    def hwnd(self) -> int:
        hwnd = self.user32.FindWindowW(None, self.title)
        if not hwnd:
            raise WindowError(f"window {self.title!r} not found")
        return hwnd

    @property
    def scale(self) -> float:
        """Physical pixels per dp: Windows' display scaling for the monitor the window is on (1.25 at 125%)."""
        return self.user32.GetDpiForWindow(self.hwnd) / 96

    def wait_open(self, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while not self.user32.FindWindowW(None, self.title):
            if time.monotonic() > deadline:
                raise WindowError(f"window {self.title!r} did not open within {timeout:.0f}s")
            time.sleep(0.2)

    def focus(self) -> None:
        """Bring the window to the front: a covered window captures whatever covers it."""
        self.user32.SetForegroundWindow(self.hwnd)
        time.sleep(0.2)

    def grab(self) -> Image.Image:
        self.focus()
        return ImageGrab.grab(window=self.hwnd).convert("RGB")

    def capture(self, settle: float = 0.4, timeout: float = 8.0) -> Image.Image:
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
                raise WindowError(f"window never settled within {timeout:.0f}s")
            last = now

    def click(self, x: float, y: float) -> None:
        """A real left click at client-area pixel (x, y)."""
        self.focus()
        point = wintypes.POINT(round(x), round(y))
        self.user32.ClientToScreen(self.hwnd, ctypes.byref(point))
        self.user32.SetCursorPos(point.x, point.y)
        time.sleep(0.05)
        self.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        self.user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        # park the pointer outside the window so hover highlights don't leak into the next capture
        self.user32.SetCursorPos(0, 0)
