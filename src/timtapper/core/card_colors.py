#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 07:29:35.304650
Revised: 2026/10/13 07:39:25.720073

OPTCG card colours as every leader is drawn in them: the app's portrait frames, colour bars and filter dots
(ui.widgets, ui.leader_picker) and the share cards (share.render), so a leader looks the same on screen and in
a shared image. Game identity, so they stay fixed across themes.
"""

CARD_COLORS = {
    "Red": "#d63031",
    "Green": "#27ae60",
    "Blue": "#2980cd",
    "Purple": "#8e44ad",
    "Black": "#46464a",
    "Yellow": "#f1c40f",
}
UNKNOWN_COLOR = "#5a6270"  # a colour this release doesn't know, or a leader with none


def rgb(hex_color: str) -> tuple[int, int, int]:
    """`#rrggbb` as an (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def leader_hues(colors: tuple[str, ...]) -> list[str]:
    """The hues a leader is framed in, one per card colour; unknown or missing colours fall back to UNKNOWN_COLOR."""
    return [CARD_COLORS.get(c, UNKNOWN_COLOR) for c in colors] or [UNKNOWN_COLOR]
