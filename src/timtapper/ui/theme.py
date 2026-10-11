#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.341252
Revised: 2026/10/11 16:27:23.851801

App theme and the color vocabulary shared by every screen.
"""

import flet as ft

SEED = "#c62828"  # Luffy red

THEME_MODES = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}

# OPTCG card colors, same hues as the share cards (share/render.py CARD_COLORS)
CARD_COLORS = {
    "Red": "#d63031",
    "Green": "#27ae60",
    "Blue": "#2980cd",
    "Purple": "#8e44ad",
    "Black": "#46464a",
    "Yellow": "#f1c40f",
}
UNKNOWN_COLOR = "#5a6270"
RESULT_COLORS = {"W": "#2e9d5b", "L": "#d64545", "D": "#7d7f8c"}


def apply_theme(page: ft.Page, mode: str) -> None:
    page.theme = ft.Theme(color_scheme_seed=SEED)
    page.dark_theme = ft.Theme(color_scheme_seed=SEED)
    page.theme_mode = THEME_MODES.get(mode, ft.ThemeMode.SYSTEM)
