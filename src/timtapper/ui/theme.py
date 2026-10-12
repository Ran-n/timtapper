#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.341252
Revised: 2026/10/12 16:54:59.437757

App themes and the color vocabulary shared by every screen.

A theme is a named pair of hand-picked palettes (light + dark); the mode
(system/light/dark) picks which one shows. Colors are literal hex rather than
seed-derived so the palettes look like their originals, and so controls that
ignore custom ColorScheme tokens (SnackBar) can be given the right color.
"""

from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from i18n import Translate

FONT = "Poppins"
FONT_SEMIBOLD = "PoppinsSemiBold"
FONT_HEAVY = "PoppinsExtraBold"
FONTS = {
    FONT: "fonts/Poppins-Regular.ttf",
    FONT_SEMIBOLD: "fonts/Poppins-SemiBold.ttf",
    FONT_HEAVY: "fonts/Poppins-ExtraBold.ttf",
}

THEME_MODES = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}
DEFAULT_MODE = "system"

# OPTCG card colors, same hues as the share cards (share/render.py CARD_COLORS).
# Game identity, so they stay fixed across themes.
CARD_COLORS = {
    "Red": "#d63031",
    "Green": "#27ae60",
    "Blue": "#2980cd",
    "Purple": "#8e44ad",
    "Black": "#46464a",
    "Yellow": "#f1c40f",
}
UNKNOWN_COLOR = "#5a6270"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(color: str, base: str, amount: float) -> str:
    """`amount` of `color` blended over `base` (0 → base, 1 → color), as #rrggbb."""
    c, b = _rgb(color), _rgb(base)
    return "#" + "".join(f"{round(b[i] + (c[i] - b[i]) * amount):02x}" for i in range(3))


@dataclass(frozen=True)
class Scheme:
    """One palette (a theme in one brightness). Accents double as text on `bg` and as fills under `bg`-colored text."""

    dark: bool
    bg: str  # page background
    surface: str  # cards
    surface_high: str  # raised elements, chips, empty badges
    surface_highest: str  # inputs, strongest container
    fg: str
    fg_muted: str
    outline: str
    primary: str
    secondary: str
    tertiary: str
    error: str
    success: str

    @property
    def on_accent(self) -> str:
        return self.bg

    def tint(self, color: str, amount: float = 0.2) -> str:
        """A soft fill of `color` that sits on a card."""
        return mix(color, self.surface, amount)

    @property
    def outline_variant(self) -> str:
        return mix(self.outline, self.surface, 0.45)

    @property
    def results(self) -> dict[str, str]:
        return {"W": self.success, "L": self.error}

    def color_scheme(self) -> ft.ColorScheme:
        return ft.ColorScheme(
            primary=self.primary,
            on_primary=self.on_accent,
            primary_container=self.tint(self.primary, 0.28),
            on_primary_container=self.fg,
            secondary=self.secondary,
            on_secondary=self.on_accent,
            secondary_container=self.tint(self.secondary, 0.28),
            on_secondary_container=self.fg,
            tertiary=self.tertiary,
            on_tertiary=self.on_accent,
            tertiary_container=self.tint(self.tertiary, 0.28),
            on_tertiary_container=self.fg,
            error=self.error,
            on_error=self.on_accent,
            error_container=self.tint(self.error, 0.28),
            on_error_container=self.fg,
            surface=self.bg,
            on_surface=self.fg,
            on_surface_variant=self.fg_muted,
            surface_dim=self.bg,
            surface_bright=self.surface_high,
            surface_container_lowest=self.bg,
            surface_container_low=mix(self.surface, self.bg, 0.5),
            surface_container=self.surface,
            surface_container_high=self.surface_high,
            surface_container_highest=self.surface_highest,
            surface_tint=self.bg,  # no Material 3 elevation tint over the palette
            outline=self.outline,
            outline_variant=self.outline_variant,
            inverse_surface=self.fg,
            on_inverse_surface=self.bg,
            inverse_primary=mix(self.primary, self.fg, 0.5),
            shadow="#000000",
            scrim="#000000",
        )

    def theme(self) -> ft.Theme:
        title = ft.TextStyle(size=22, font_family=FONT_HEAVY, color=self.fg)
        label = ft.TextStyle(font_family=FONT_SEMIBOLD)
        button = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14), text_style=label)
        return ft.Theme(
            color_scheme=self.color_scheme(),
            font_family=FONT,
            scaffold_bgcolor=self.bg,
            canvas_color=self.bg,
            divider_color=self.outline_variant,
            filled_button_theme=ft.FilledButtonTheme(style=button),
            outlined_button_theme=ft.OutlinedButtonTheme(style=button),
            text_button_theme=ft.TextButtonTheme(style=button),
            floating_action_button_theme=ft.FloatingActionButtonTheme(
                bgcolor=self.primary,
                foreground_color=self.on_accent,
                shape=ft.RoundedRectangleBorder(radius=18),
                text_style=label,
            ),
            dialog_theme=ft.DialogTheme(
                bgcolor=self.surface,
                shape=ft.RoundedRectangleBorder(radius=24),
                title_text_style=ft.TextStyle(size=20, font_family=FONT_HEAVY, color=self.fg),
            ),
            bottom_sheet_theme=ft.BottomSheetTheme(bgcolor=self.surface),
            appbar_theme=ft.AppBarTheme(
                bgcolor=self.bg,
                color=self.fg,
                elevation=0,
                elevation_on_scroll=0,
                center_title=False,
                title_text_style=title,
            ),
            navigation_bar_theme=ft.NavigationBarTheme(
                bgcolor=self.surface,
                indicator_color=self.tint(self.primary, 0.35),
                elevation=0,
            ),
        )


@dataclass(frozen=True)
class AppTheme:
    key: str
    name: Callable[[Translate], str]  # proper names (Gruvbox, Nord…) ignore the translator
    light: Scheme
    dark: Scheme

    def label(self, _: Translate) -> str:
        return self.name(_)

    def scheme(self, dark: bool) -> Scheme:
        return self.dark if dark else self.light


THEMES: dict[str, AppTheme] = {
    t.key: t
    for t in (
        AppTheme(
            "gruvbox",
            lambda _: "Gruvbox",
            light=Scheme(
                dark=False,
                bg="#fbf1c7",
                surface="#f2e5bc",
                surface_high="#ebdbb2",
                surface_highest="#d5c4a1",
                fg="#3c3836",
                fg_muted="#7c6f64",
                outline="#a89984",
                primary="#af3a03",
                secondary="#427b58",
                tertiary="#b57614",
                error="#9d0006",
                success="#79740e",
            ),
            dark=Scheme(
                dark=True,
                bg="#282828",
                surface="#32302f",
                surface_high="#3c3836",
                surface_highest="#504945",
                fg="#ebdbb2",
                fg_muted="#a89984",
                outline="#665c54",
                primary="#fe8019",
                secondary="#8ec07c",
                tertiary="#fabd2f",
                error="#fb4934",
                success="#b8bb26",
            ),
        ),
        AppTheme(
            "catppuccin",
            lambda _: "Catppuccin",
            light=Scheme(
                dark=False,
                bg="#eff1f5",
                surface="#e6e9ef",
                surface_high="#dce0e8",
                surface_highest="#ccd0da",
                fg="#4c4f69",
                fg_muted="#6c6f85",
                outline="#9ca0b0",
                primary="#8839ef",
                secondary="#179299",
                tertiary="#fe640b",
                error="#d20f39",
                success="#3a8f27",  # Latte green, darkened for text contrast
            ),
            dark=Scheme(
                dark=True,
                bg="#1e1e2e",
                surface="#262637",
                surface_high="#313244",
                surface_highest="#45475a",
                fg="#cdd6f4",
                fg_muted="#a6adc8",
                outline="#6c7086",
                primary="#cba6f7",
                secondary="#94e2d5",
                tertiary="#fab387",
                error="#f38ba8",
                success="#a6e3a1",
            ),
        ),
        AppTheme(
            "nord",
            lambda _: "Nord",
            light=Scheme(
                dark=False,
                bg="#eceff4",
                surface="#e5e9f0",
                surface_high="#d8dee9",
                surface_highest="#cbd2de",
                fg="#2e3440",
                fg_muted="#4c566a",
                outline="#8a94a7",
                primary="#5e81ac",
                secondary="#4c8a99",
                tertiary="#b0812e",
                error="#bf616a",
                success="#6b8f50",
            ),
            dark=Scheme(
                dark=True,
                bg="#2e3440",
                surface="#353c4a",
                surface_high="#3b4252",
                surface_highest="#434c5e",
                fg="#eceff4",
                fg_muted="#b4bccb",
                outline="#616e88",
                primary="#88c0d0",
                secondary="#81a1c1",
                tertiary="#ebcb8b",
                error="#bf616a",
                success="#a3be8c",
            ),
        ),
        AppTheme(
            "solarized",
            lambda _: "Solarized",
            light=Scheme(
                dark=False,
                bg="#fdf6e3",
                surface="#f5efdc",
                surface_high="#eee8d5",
                surface_highest="#e1dbc6",
                fg="#586e75",
                fg_muted="#839496",
                outline="#93a1a1",
                primary="#268bd2",
                secondary="#2aa198",
                tertiary="#b58900",
                error="#dc322f",
                success="#738500",  # darkened for text contrast
            ),
            dark=Scheme(
                dark=True,
                bg="#002b36",
                surface="#073642",
                surface_high="#0b3f4c",
                surface_highest="#174955",
                fg="#93a1a1",
                fg_muted="#839496",
                outline="#586e75",
                primary="#268bd2",
                secondary="#2aa198",
                tertiary="#b58900",
                error="#dc322f",
                success="#859900",
            ),
        ),
        AppTheme(
            "tokyonight",
            lambda _: "Tokyo Night",
            light=Scheme(
                dark=False,
                bg="#e1e2e7",
                surface="#e9e9ed",
                surface_high="#d0d5e3",
                surface_highest="#c4c8da",
                fg="#3760bf",
                fg_muted="#6172b0",
                outline="#a8aecb",
                primary="#2e7de9",
                secondary="#007197",
                tertiary="#8c6c3e",
                error="#f52a65",
                success="#587539",
            ),
            dark=Scheme(
                dark=True,
                bg="#1a1b26",
                surface="#1f2335",
                surface_high="#24283b",
                surface_highest="#292e42",
                fg="#c0caf5",
                fg_muted="#a9b1d6",
                outline="#414868",
                primary="#7aa2f7",
                secondary="#7dcfff",
                tertiary="#e0af68",
                error="#f7768e",
                success="#9ece6a",
            ),
        ),
        AppTheme(
            "classic",
            lambda _: _("Classic"),
            light=Scheme(
                dark=False,
                bg="#fff8f6",
                surface="#fceae7",
                surface_high="#f6dfdb",
                surface_highest="#f0d4cf",
                fg="#231918",
                fg_muted="#534341",
                outline="#857370",
                primary="#c62828",
                secondary="#775652",
                tertiary="#705c2e",
                error="#ba1a1a",
                success="#2e7d4f",
            ),
            dark=Scheme(
                dark=True,
                bg="#1a1111",
                surface="#231918",
                surface_high="#2b2120",
                surface_highest="#362b2a",
                fg="#f1dfdc",
                fg_muted="#d8c2be",
                outline="#a08c89",
                primary="#ffb4a8",
                secondary="#e7bdb7",
                tertiary="#dfc38c",
                error="#ffb4ab",
                success="#7fd8a0",
            ),
        ),
    )
}
DEFAULT_THEME = "gruvbox"


def get_theme(key: str | None) -> AppTheme:
    return THEMES.get(key or "", THEMES[DEFAULT_THEME])


def is_dark(page: ft.Page, mode: str) -> bool:
    """Which palette is on screen: the mode, or the device's brightness when following the system."""
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return getattr(page, "platform_brightness", None) == ft.Brightness.DARK


def apply_theme(page: ft.Page, theme: AppTheme, mode: str) -> None:
    page.fonts = FONTS
    page.theme = theme.light.theme()
    page.dark_theme = theme.dark.theme()
    page.theme_mode = THEME_MODES.get(mode, THEME_MODES[DEFAULT_MODE])
