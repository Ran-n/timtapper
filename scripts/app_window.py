#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 13:16:02.424894
Revised: 2026/10/14 01:08:28.738846

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
_MOUSEEVENTF_WHEEL = 0x0800
_WHEEL_DELTA = 120  # one notch
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_INPUT_KEYBOARD = 1
_MAPVK_VK_TO_VSC = 0
# virtual-key codes for the keys tests press
KEYS = {"enter": 0x0D, "tab": 0x09, "escape": 0x1B, "backspace": 0x08, "ctrl": 0x11, "a": 0x41}


class _KeyInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):  # only here so the union is as large as Windows expects
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyInput), ("mi", _MouseInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


class WindowError(RuntimeError):
    """The app window could not be found or captured."""


def _user32():
    user32 = ctypes.windll.user32
    # physical pixels everywhere, so capture and click coordinates agree on scaled displays
    # returns E_ACCESSDENIED (no exception) when this process already set it, which is fine
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    return user32


# Flet's desktop client, which owns the app's window: named after the app when started from the project (it reads
# pyproject.toml), flet.exe otherwise
CLIENT_EXES = ("timtapper.exe", "flet.exe")
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _exe_name(user32, hwnd: int) -> str:
    """The file name of the program that owns window `hwnd`, lowercase ("" if it can't be read)."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(handle)


def find_window(title: str, exes: tuple[str, ...] = CLIENT_EXES) -> int:
    """The top-level window titled exactly `title` that one of `exes` owns, or 0: an editor whose workspace has the
    same name (VS Code titles its window after the folder) must never be taken for the app."""
    user32 = _user32()
    found = []
    buffer = ctypes.create_unicode_buffer(512)

    def check(hwnd, _lparam):
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        if buffer.value == title and _exe_name(user32, hwnd) in exes:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(_EnumWindowsProc(check), 0)
    return found[0] if found else 0


class AppWindow:
    def __init__(self, title: str = WINDOW_TITLE) -> None:
        self.title = title
        self.user32 = _user32()

    @property
    def hwnd(self) -> int:
        hwnd = find_window(self.title)
        if not hwnd:
            raise WindowError(f"window {self.title!r} not found")
        return hwnd

    @property
    def scale(self) -> float:
        """Physical pixels per dp: Windows' display scaling for the monitor the window is on (1.25 at 125%)."""
        return self.user32.GetDpiForWindow(self.hwnd) / 96

    def wait_open(self, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while not find_window(self.title):
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

    def _send_keys(self, *events: tuple[int, int, int]) -> None:
        """(virtual key, scan code, flags) per event, as one SendInput call."""
        inputs = (_Input * len(events))(
            *(_Input(_INPUT_KEYBOARD, _InputUnion(ki=_KeyInput(vk, scan, flags, 0, 0))) for vk, scan, flags in events)
        )
        sent = self.user32.SendInput(len(events), inputs, ctypes.sizeof(_Input))
        if sent != len(events):
            raise WindowError(f"SendInput delivered {sent} of {len(events)} key events")
        time.sleep(0.05)

    def type_text(self, text: str, focus: bool = True) -> None:
        """Type `text` into the focused field, character by character (any Unicode, as a keyboard would).
        focus=False types into whatever has the focus now, e.g. a system dialog the app opened."""
        if focus:
            self.focus()
        for ch in text:
            code = ord(ch)
            self._send_keys((0, code, _KEYEVENTF_UNICODE), (0, code, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP))

    def press(self, *keys: str, focus: bool = True) -> None:
        """Press `keys` together and release them in reverse (press("ctrl", "a") selects all); focus=False as in
        type_text."""
        if focus:
            self.focus()
        # with the scan code too: Flutter reads the physical key, and a bare virtual key reaches it as no key at all
        codes = [(KEYS[k], self.user32.MapVirtualKeyW(KEYS[k], _MAPVK_VK_TO_VSC)) for k in keys]
        self._send_keys(
            *((vk, scan, 0) for vk, scan in codes), *((vk, scan, _KEYEVENTF_KEYUP) for vk, scan in reversed(codes))
        )

    def scroll(self, x: float, y: float, notches: int) -> None:
        """Turn the mouse wheel over client pixel (x, y): positive scrolls the content up (towards the end)."""
        self.focus()
        point = wintypes.POINT(round(x), round(y))
        self.user32.ClientToScreen(self.hwnd, ctypes.byref(point))
        self.user32.SetCursorPos(point.x, point.y)
        time.sleep(0.05)
        self.user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, ctypes.c_uint32(-notches * _WHEEL_DELTA).value, 0)
        time.sleep(0.05)
        self.user32.SetCursorPos(0, 0)
