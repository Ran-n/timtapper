#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:57:38.978707
Revised: 2026/10/14 07:45:08.472443

Themes: every palette is complete and readable, preferences round-trip, and
appearance changes rebuild the screen.
"""

import dataclasses
import re

import flet as ft
import pytest

from ui import context as context_mod
from ui.app import install_routing
from ui.theme import DEFAULT_THEME, FONTS, THEMES, Scheme, apply_theme, get_theme, is_dark, mix, page_fonts

HEX = re.compile(r"^#[0-9a-f]{6}$")
SCHEMES = [(t.key, dark) for t in THEMES.values() for dark in (False, True)]


def luminance(hex_color: str) -> float:
    def channel(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_default_theme_is_gruvbox():
    assert DEFAULT_THEME == "gruvbox"
    assert get_theme(None).key == get_theme("no-such-theme").key == "gruvbox"


@pytest.mark.parametrize(("key", "dark"), SCHEMES)
def test_scheme_is_complete_and_matches_its_brightness(key, dark):
    s = THEMES[key].scheme(dark)
    assert s.dark is dark
    for f in dataclasses.fields(Scheme):
        value = getattr(s, f.name)
        if isinstance(value, str):
            assert HEX.match(value), f"{key}/{f.name}={value!r}"
    assert (luminance(s.bg) < luminance(s.fg)) is dark


@pytest.mark.parametrize(("key", "dark"), SCHEMES)
def test_scheme_text_is_readable(key, dark):
    s = THEMES[key].scheme(dark)
    assert contrast(s.fg, s.bg) >= 4.5
    assert contrast(s.fg, s.surface) >= 4.5
    assert contrast(s.fg_muted, s.surface) >= 2.5
    for accent in (s.primary, s.success, s.error):
        assert contrast(accent, s.on_accent) >= 3, f"{key}: {accent} under {s.on_accent}"


@pytest.mark.parametrize(("key", "dark"), SCHEMES)
def test_scheme_builds_a_flet_theme(key, dark):
    s = THEMES[key].scheme(dark)
    theme = s.theme()
    assert theme.color_scheme.primary == s.primary
    assert theme.color_scheme.surface_container == s.surface
    assert theme.scaffold_bgcolor == s.bg
    assert set(s.results) == {"W", "L"}


def test_mix():
    assert mix("#ffffff", "#000000", 0) == "#000000"
    assert mix("#ffffff", "#000000", 1) == "#ffffff"
    assert mix("#ff0000", "#0000ff", 0.5) == "#800080"


def test_theme_labels_translate_only_generic_names():
    def shout(text):
        return text.upper()

    assert THEMES["gruvbox"].label(shout) == "Gruvbox"
    assert THEMES["dracula"].label(shout) == "Dracula"
    assert THEMES["rosepine"].label(shout) == "Rosé Pine"
    assert THEMES["classic"].label(shout) == "CLASSIC"


@pytest.mark.parametrize(
    ("mode", "brightness", "expected"),
    [
        ("dark", ft.Brightness.LIGHT, True),
        ("light", ft.Brightness.DARK, False),
        ("system", ft.Brightness.DARK, True),
        ("system", ft.Brightness.LIGHT, False),
        ("system", None, False),
    ],
)
def test_is_dark(page, mode, brightness, expected):
    page.platform_brightness = brightness
    assert is_dark(page, mode) is expected


def test_apply_theme(page):
    apply_theme(page, THEMES["nord"], "light")
    assert page.theme_mode == ft.ThemeMode.LIGHT
    assert page.theme.color_scheme.primary == THEMES["nord"].light.primary
    assert page.dark_theme.color_scheme.primary == THEMES["nord"].dark.primary
    assert page.fonts == FONTS  # off the web: the bundled files, as they are
    apply_theme(page, THEMES["nord"], "bogus")
    assert page.theme_mode == ft.ThemeMode.SYSTEM


async def test_load_prefs_restores_theme(ctx, monkeypatch, page):
    class Prefs:
        async def get(self, key):
            return {"timtapper.palette": "catppuccin", "timtapper.theme": "dark"}.get(key)

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.load_prefs()
    assert ctx.theme.key == "catppuccin" and ctx.scheme is THEMES["catppuccin"].dark


async def test_load_prefs_unknown_theme_falls_back_to_gruvbox(ctx, monkeypatch):
    class Prefs:
        async def get(self, key):
            return {"timtapper.palette": "deleted-theme"}.get(key)

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.load_prefs()
    assert ctx.theme.key == "gruvbox"


@pytest.mark.regression
async def test_load_prefs_unknown_mode_falls_back_to_system(ctx, monkeypatch):
    """An unknown stored mode was kept: the page followed the system, but Settings showed no mode picked."""

    class Prefs:
        async def get(self, key):
            return {"timtapper.theme": "auto"}.get(key)

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    await ctx.load_prefs()
    assert ctx.theme_mode == "system"


def test_notifications_use_the_active_palette(ctx, page):
    page.platform_brightness = ft.Brightness.DARK
    ctx.notify("boom", error=True)
    ctx.notify("ok")
    error, info = page.dialogs[-2:]
    s = THEMES["gruvbox"].dark
    assert (error.data, error.bgcolor, error.content.color) == ("error", s.error, s.on_accent)
    assert (info.data, info.bgcolor, info.content.color) == ("info", s.fg, s.bg)


async def test_theme_change_rebuilds_the_screen(ctx, page, monkeypatch):
    class Prefs:
        async def set(self, key, value):
            return True

    monkeypatch.setattr(context_mod.ft, "SharedPreferences", Prefs)
    install_routing(ctx)()
    before = page.views[-1]
    await ctx.change_theme("solarized")
    assert page.views[-1] is not before
    assert page.theme.color_scheme.primary == THEMES["solarized"].light.primary


@pytest.mark.parametrize(("mode", "rebuilt"), [("system", True), ("dark", False)])
def test_device_brightness_rebuilds_only_when_following_system(ctx, page, mode, rebuilt):
    install_routing(ctx)()
    ctx.theme_mode = mode
    before = page.views[-1]
    page.on_platform_brightness_change(None)
    assert (page.views[-1] is not before) is rebuilt


@pytest.mark.regression
def test_the_web_asks_for_each_releases_fonts_at_their_own_address():
    """A browser's WebView drew no text at all after an update: fonts it had stored badly kept being used. Each
    release now asks for its fonts at an address of its own."""
    fonts = page_fonts(web=True, version="1.4.1")
    assert fonts == {family: f"{path}?v=1.4.1" for family, path in FONTS.items()}
    assert page_fonts(web=False) == FONTS


@pytest.mark.regression
def test_the_web_shell_never_shares_the_apps_font_files():
    """The shell's own font requests left the stored copy the app then read; they now go to other addresses."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[2] / "scripts" / "shell" / "shell.css").read_text(encoding="utf-8")
    urls = re.findall(r'url\("([^"]+)"\)', css)
    assert all(url.endswith("?shell") for url in urls if url.startswith("fonts/"))
    assert not set(urls) & set(page_fonts(web=True).values()) and not set(urls) & set(FONTS.values())
