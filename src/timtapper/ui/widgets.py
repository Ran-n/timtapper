#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.420418
Revised: 2026/10/13 13:15:07.212552

Small building blocks reused across screens.
"""

import re
from collections.abc import Callable

import flet as ft

from catalog import portraits
from catalog.repository import Leader
from core.card_colors import leader_hues
from core.die import CORNER_RADIUS, DIE_PIPS, LOST_PIPS, PIP_DIAMETER, WON_PIPS
from i18n import Translate, event_type_label
from stats.compute import Record, percent
from ui.theme import FONT_HEAVY, FONT_SEMIBOLD, Scheme

RADIUS = 18


def update_if_mounted(control: ft.Control) -> None:
    """Push a rebuilt control to the client — a no-op before it's on screen (first build)."""
    try:
        control.page  # noqa: B018 — raises RuntimeError while the control isn't attached yet
    except RuntimeError:
        return
    control.update()


def card(content: ft.Control, *, padding: ft.Padding | int = 14, radius: int = RADIUS, **kwargs) -> ft.Container:
    """The app's surface: a filled, hairline-bordered rounded panel. Extra kwargs (on_click, data…) pass through."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        ink=kwargs.get("on_click") is not None,
        **kwargs,
    )


def caption(text: str, **kwargs) -> ft.Text:
    """Small muted label above a value."""
    return ft.Text(text, size=12, color=ft.Colors.ON_SURFACE_VARIANT, **kwargs)


# Flag shown next to each language (assets/flags/*.svg): a country's flag where it
# has one; Galician gets Galicia's. SVG because Windows draws no flag emoji.
LANGUAGE_FLAGS = {"en": "flags/gb.svg", "es": "flags/es.svg", "gl": "flags/gl.svg"}


def flag(lang: str, height: int = 18) -> ft.Control:
    """A language's flag as a small 3:2 rounded chip with a hairline edge (white flags need one).
    Centered in a fixed-width wrapper: icon slots (Dropdown leading_icon) would otherwise stretch it."""
    width = height * 3 // 2
    chip = ft.Container(
        width=width,
        height=height,
        border_radius=3,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Image(src=LANGUAGE_FLAGS[lang], fit=ft.BoxFit.COVER, width=width, height=height),
    )
    return ft.Container(width=width + 20, alignment=ft.Alignment.CENTER, content=chip)


LOGO_MARK = "logo_mark.png"  # drawn by scripts/make_icon.py


def logo(size: int = 32) -> ft.Image:
    """The app's mark (tapped card + motion arc), square and transparent."""
    return ft.Image(src=LOGO_MARK, width=size, height=size, fit=ft.BoxFit.CONTAIN, data="logo")


def _color_frame(colors: list[str]) -> dict:
    """Container fill for a frame: solid for one color, equal hard-edged top-to-bottom bands (as color_bar) for more."""
    if len(colors) == 1:
        return {"bgcolor": colors[0]}
    band = 1 / len(colors)
    return {
        "gradient": ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER,
            end=ft.Alignment.BOTTOM_CENTER,
            colors=[c for c in colors for _edge in range(2)],
            stops=[edge for i in range(len(colors)) for edge in (i * band, (i + 1) * band)],
        )
    }


def portrait_border(size: int) -> int:
    """Frame width: readable at every size without eating the face (56 px -> 3, 32 px -> 2)."""
    return max(2, size // 16)


def color_bar(colors: tuple[str, ...], height: int | None = 28, width: int = 8) -> ft.Control:
    """Vertical stripes, one per leader color — the app's leader 'icon'. `height=None`: sized by its parent."""
    stripes = leader_hues(colors)
    return ft.Container(
        width=width,
        height=height,
        border_radius=width // 2,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column([ft.Container(bgcolor=c, expand=True) for c in stripes], spacing=0),
    )


def leader_portrait(leader: Leader | None, size: int = 32) -> ft.Control:
    """The leader's face cropped from its card, framed in the leader's colors (outer size stays `size`).
    No leader: an unframed silhouette. Picture unknown or not downloaded yet: a framed silhouette."""
    if leader is None:
        return _portrait_face(None, size, size // 4)
    border = portrait_border(size)
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 4,
        padding=border,
        data="portrait-frame",
        content=_portrait_face(portraits.source(leader.code), size - 2 * border, size // 4 - border),
        **_color_frame(leader_hues(leader.colors)),
    )


BYE_JOKER = "bye_joker.png"  # drawn by scripts/make_bye_joker.py; the share cards paste the same image


def bye_portrait(scheme: Scheme, size: int = 32) -> ft.Control:
    """A bye's stand-in for a leader portrait: a joker's hat (an opponent you never played), framed in the top-cut
    gold and sized like a portrait."""
    border = portrait_border(size)
    inner = size - 2 * border
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 4,
        padding=border,
        bgcolor=scheme.tertiary,
        data="bye-portrait",
        content=ft.Container(
            width=inner,
            height=inner,
            border_radius=size // 4 - border,
            bgcolor=scheme.surface_highest,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Image(src=BYE_JOKER, width=inner, height=inner, fit=ft.BoxFit.CONTAIN),
        ),
    )


def _portrait_face(src: str | bytes | None, size: int, radius: int) -> ft.Container:
    fallback = ft.Icon(ft.Icons.PERSON_ROUNDED, size=size * 0.6, color=ft.Colors.ON_SURFACE_VARIANT)
    return ft.Container(
        width=size,
        height=size,
        border_radius=radius,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        alignment=ft.Alignment.CENTER,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Image(src=src, width=size, height=size, fit=ft.BoxFit.COVER, error_content=fallback)
        if src
        else fallback,
    )


# a zero-width space after these lets a name without spaces ("Monkey.D.Dragon", 'Eustass"Captain"Kid') wrap
# between its parts instead of mid-word
ZWSP = chr(0x200B)  # zero-width space: a break opportunity that draws nothing
_NAME_BREAKS = re.compile(r'([."&])(?=\S)')


def breakable(name: str) -> str:
    """`name` with line-break opportunities after ".", '"' and "&" (invisible when it fits on one line)."""
    return _NAME_BREAKS.sub(lambda m: m.group(1) + ZWSP, name)


def leader_row(
    leader: Leader | None,
    placeholder: str,
    *,
    size: int = 16,
    show_code: bool = True,
    spacing: int = 10,
    portrait_size: int | None = None,
    break_words: bool = False,
    short: bool = False,
) -> ft.Control:
    colors = leader.colors if leader else ()
    shown = (leader.short_name if short else leader.name) if leader else placeholder
    name = ft.Text(
        breakable(shown) if break_words else shown,
        size=size,
        font_family=FONT_SEMIBOLD if leader else None,
        color=None if leader else ft.Colors.ON_SURFACE_VARIANT,
        # never cut a name: in a tight row the longest ("Donquixote Doflamingo") wraps to a second line
    )
    texts: list[ft.Control] = [name]
    if leader and show_code:
        texts.append(ft.Text(leader.code, size=size - 4, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Row(
        [
            color_bar(colors, height=portrait_size or size + 16),
            leader_portrait(leader, portrait_size or size + 16),
            ft.Column(texts, spacing=0, tight=True, expand=True),
        ],
        spacing=spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def pill(
    text: str,
    color: str,
    scheme: Scheme,
    *,
    size: int = 13,
    icon: str | None = None,
    font_family: str = FONT_SEMIBOLD,
    **kwargs,
) -> ft.Control:
    """A soft-tinted rounded label in `color`, optionally led by an icon. Extra kwargs (data…) pass through."""
    label = ft.Text(text, size=size, font_family=font_family, color=color)
    content: ft.Control = (
        ft.Row(
            [ft.Icon(icon, size=size + 2, color=color), label],
            spacing=4,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if icon
        else label
    )
    return ft.Container(
        padding=ft.Padding(10, 3, 10, 3),
        border_radius=99,
        bgcolor=scheme.tint(color, 0.22),
        content=content,
        **kwargs,
    )


# One per db.models.EVENT_TYPES value: with the tier colour below, what tells types apart.
EVENT_TYPE_ICONS: dict[str, str] = {
    "testing": ft.Icons.SCIENCE_OUTLINED,
    "pirates_party": ft.Icons.CELEBRATION_OUTLINED,
    "locals": ft.Icons.STOREFRONT_OUTLINED,
    "release": ft.Icons.NEW_RELEASES_OUTLINED,
    "sealed": ft.Icons.INVENTORY_2_OUTLINED,
    "heroines_battle": ft.Icons.FACE_3_OUTLINED,
    "team": ft.Icons.GROUPS_OUTLINED,
    "store_championship": ft.Icons.WORKSPACE_PREMIUM_OUTLINED,
    "treasure_cup": ft.Icons.DIAMOND_OUTLINED,
    "flagship": ft.Icons.SAILING_OUTLINED,
    "extra_battle": ft.Icons.BOLT_OUTLINED,
    "regional": ft.Icons.MAP_OUTLINED,
    "national": ft.Icons.FLAG_OUTLINED,
    "worlds": ft.Icons.PUBLIC,
    "other": ft.Icons.EVENT_OUTLINED,
}


# Each type's tier, colour-coded in the theme's own accents, so every theme reads them:
# the championship ladder, premier store events, store events, and casual play
EVENT_TYPE_TIERS: dict[str, str] = {
    "regional": "championship",
    "national": "championship",
    "worlds": "championship",
    "treasure_cup": "premier",
    "flagship": "premier",
    "extra_battle": "premier",
    "store_championship": "store",
    "locals": "store",
    "heroines_battle": "store",
    "testing": "casual",
    "pirates_party": "casual",
    "release": "casual",
    "sealed": "casual",
    "team": "casual",
    "other": "casual",
}


def tier_color(key: str, scheme: Scheme) -> str:
    """The accent an event type's pill is drawn in (an unknown type reads as casual, like 'Other')."""
    return {
        "championship": scheme.primary,
        "premier": scheme.tertiary,
        "store": scheme.secondary,
        "casual": scheme.fg_muted,
    }[EVENT_TYPE_TIERS.get(key, "casual")]


def event_type_pill(_: Translate, key: str, scheme: Scheme) -> ft.Control:
    """The event type as icon + translated label in its tier's colour; an unknown key reads 'Other'."""
    return pill(
        event_type_label(_, key),
        tier_color(key, scheme),
        scheme,
        size=12,
        icon=EVENT_TYPE_ICONS.get(key, EVENT_TYPE_ICONS["other"]),
        font_family=FONT_HEAVY,
        data="event-type",
    )


def rate_color(rec: Record, scheme: Scheme) -> str:
    """Green at 50%+ win rate, red below, muted with no games."""
    if not rec.games:
        return scheme.fg_muted
    return scheme.success if rec.win_rate >= 0.5 else scheme.error


def record_badges(rec: Record, scheme: Scheme, *, size: int = 13) -> ft.Control:
    """A neutral win-loss pill beside a win-rate pill in rate_color; a single muted dash with no games."""
    if not rec.games:
        return pill("—", scheme.fg_muted, scheme, size=size, data="record-badge")
    return ft.Row(
        [
            pill(rec.label(), scheme.fg_muted, scheme, size=size, data="record-badge"),
            pill(percent(rec.win_rate), rate_color(rec, scheme), scheme, size=size, data="rate-badge"),
        ],
        spacing=4,
        tight=True,
        wrap=False,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _badge(content: ft.Control, bgcolor: str, *, width: int, height: int) -> ft.Container:
    """The square-ish slot round rows line up their indicators in."""
    return ft.Container(
        width=width,
        height=height,
        border_radius=height // 3,
        alignment=ft.Alignment.CENTER,
        bgcolor=bgcolor,
        content=content,
    )


def result_badge(result: str | None, scheme: Scheme, size: int = 36) -> ft.Control:
    return _badge(
        ft.Text(
            result or "…",
            size=size * 0.4,
            font_family=FONT_HEAVY,
            color=scheme.on_accent if result else ft.Colors.ON_SURFACE_VARIANT,
        ),
        scheme.results[result] if result else ft.Colors.SURFACE_CONTAINER_HIGHEST,
        width=size,
        height=size,
    )


TURN_ICONS = {True: ft.Icons.LOOKS_ONE, False: ft.Icons.LOOKS_TWO}  # keycaps: 1️⃣ / 2️⃣


def turn_badge(went_first: bool | None, scheme: Scheme, first: str, second: str, size: int = 36) -> ft.Control:
    """Went first or second as a 1 / 2 keycap, a muted dash while unknown. `first`/`second` (translated by the
    caller) are what a screen reader says for the keycap."""
    if went_first is None:
        content: ft.Control = ft.Text("—", size=size * 0.36, color=ft.Colors.ON_SURFACE_VARIANT)
    else:
        content = ft.Icon(
            TURN_ICONS[went_first],
            size=size * 0.72,
            color=scheme.fg,
            semantics_label=first if went_first else second,
        )
    return _badge(
        content,
        scheme.surface_high if went_first is not None else ft.Colors.SURFACE_CONTAINER_HIGHEST,
        width=size + 4,
        height=size,
    )


def die_face(pips: int, color: str, pip_color: str, size: float) -> ft.Container:
    """A rounded-square die showing `pips` (1-6), drawn from containers: Flet's die icons all show five."""
    if pips not in DIE_PIPS:
        raise ValueError(f"a die has 1-6 pips, not {pips}")
    diameter = size * PIP_DIAMETER
    return ft.Container(
        width=size,
        height=size,
        border_radius=size * CORNER_RADIUS,
        bgcolor=color,
        data=f"die-face-{pips}",
        content=ft.Stack(
            [
                ft.Container(
                    width=diameter,
                    height=diameter,
                    border_radius=diameter / 2,
                    bgcolor=pip_color,
                    left=x * size - diameter / 2,
                    top=y * size - diameter / 2,
                    data="pip",
                )
                for x, y in DIE_PIPS[pips]
            ],
            width=size,
            height=size,
        ),
    )


def die_badge(won_die_roll: bool | None, scheme: Scheme, size: int = 36) -> ft.Control:
    """Won: a green six. Lost: a red one. The pip counts differ too, so it reads without colour."""
    if won_die_roll is None:
        return _badge(
            ft.Icon(ft.Icons.CASINO, size=size * 0.5, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Colors.SURFACE_CONTAINER_HIGHEST,
            width=size + 8,
            height=size,
        )
    color = scheme.success if won_die_roll else scheme.error
    return _badge(
        die_face(WON_PIPS if won_die_roll else LOST_PIPS, color, scheme.on_accent, size * 0.6),
        scheme.tint(color, 0.22),
        width=size + 8,
        height=size,
    )


def chooser_badge(chose: bool | None, scheme: Scheme, you: str, them: str, size: int = 36) -> ft.Control:
    """Who chose the turn order where no die decided it (top cut, later games): `you` in the primary accent,
    `them` neutral, a muted hand while unknown. Labels come translated from the caller."""
    if chose is None:
        return _badge(
            ft.Icon(ft.Icons.FRONT_HAND_OUTLINED, size=size * 0.45, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Colors.SURFACE_CONTAINER_HIGHEST,
            width=size + 8,
            height=size,
        )
    color = scheme.primary if chose else scheme.fg
    return _badge(
        ft.Text(you if chose else them, size=size * 0.32, font_family=FONT_HEAVY, color=color),
        scheme.tint(scheme.primary, 0.22) if chose else scheme.surface_high,
        width=size + 8,
        height=size,
    )


def score_badge(wins: int, losses: int, result: str | None, scheme: Scheme, size: int = 36) -> ft.Control:
    """A best of 3's game score ("2-1"): filled in the result's colour once decided, muted while it's played."""
    return _badge(
        ft.Text(
            f"{wins}-{losses}",
            size=size * 0.36,
            font_family=FONT_HEAVY,
            color=scheme.on_accent if result else ft.Colors.ON_SURFACE_VARIANT,
        ),
        scheme.results[result] if result else ft.Colors.SURFACE_CONTAINER_HIGHEST,
        width=size + 6,
        height=size,
    )


def big_number(value: str, color: str | None = None, size: int = 28) -> ft.Text:
    return ft.Text(value, size=size, font_family=FONT_HEAVY, color=color, max_lines=1)


def stat_tile(label: str, value: ft.Control) -> ft.Control:
    return card(ft.Column([caption(label), value], spacing=4, tight=True), expand=True)


def section(title: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(4, 20, 4, 4),
        content=ft.Text(
            title.upper(),
            style=ft.TextStyle(size=12, font_family=FONT_HEAVY, letter_spacing=1.4, color=ft.Colors.PRIMARY),
        ),
    )


def empty_state(graphic: ft.IconData | ft.Control, title: str, body: str) -> ft.Control:
    """Centered placeholder for an empty screen. An icon gets a tinted disc; a control (the logo) shows as is."""
    if isinstance(graphic, ft.Control):
        top = graphic
    else:
        top = ft.Container(
            width=96,
            height=96,
            border_radius=48,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            content=ft.Icon(graphic, size=44, color=ft.Colors.PRIMARY),
        )
    return ft.Container(
        padding=ft.Padding(24, 48, 24, 24),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                top,
                ft.Container(height=8),
                ft.Text(title, size=20, font_family=FONT_HEAVY, text_align=ft.TextAlign.CENTER),
                ft.Text(body, text_align=ft.TextAlign.CENTER, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )


def make_notifier(page: ft.Page, scheme: Callable[[], Scheme]) -> Callable[..., None]:
    """Snackbar notifier. A fresh SnackBar every time: Flet ignores in-place
    updates to one that's already been on screen for a while. Colors are
    literal: SnackBar ignores custom ColorScheme tokens."""

    def notify(msg: str, error: bool = False) -> None:
        s = scheme()
        page.show_dialog(
            ft.SnackBar(
                ft.Text(msg, color=s.on_accent if error else s.bg, font_family=FONT_SEMIBOLD if error else None),
                bgcolor=s.error if error else s.fg,
                behavior=ft.SnackBarBehavior.FLOATING,
                shape=ft.RoundedRectangleBorder(radius=14),
                duration=4000,
                data="error" if error else "info",
            )
        )

    return notify


def confirm(page: ft.Page, title: str, body: str, confirm_label: str, cancel_label: str, on_yes: Callable) -> None:
    """Yes/no dialog for destructive actions — the one place a modal is warranted."""

    async def yes(_e):
        page.pop_dialog()
        result = on_yes()
        if hasattr(result, "__await__"):
            await result

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(body),
            actions=[
                ft.TextButton(cancel_label, on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    confirm_label,
                    on_click=yes,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR, color=ft.Colors.ON_ERROR),
                ),
            ],
        )
    )
