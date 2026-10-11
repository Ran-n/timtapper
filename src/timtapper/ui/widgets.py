#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.420418
Revised: 2026/10/11 17:10:30.429110

Small building blocks reused across screens.
"""

from collections.abc import Callable

import flet as ft

from catalog import portraits
from catalog.repository import Leader
from stats.compute import Record, percent
from ui.theme import CARD_COLORS, FONT_HEAVY, FONT_SEMIBOLD, UNKNOWN_COLOR, Scheme

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


def color_bar(colors: tuple[str, ...], height: int = 28, width: int = 8) -> ft.Control:
    """Vertical stripes, one per leader color — the app's leader 'icon'."""
    stripes = [CARD_COLORS.get(c, UNKNOWN_COLOR) for c in colors] or [UNKNOWN_COLOR]
    return ft.Container(
        width=width,
        height=height,
        border_radius=width // 2,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column([ft.Container(bgcolor=c, expand=True) for c in stripes], spacing=0),
    )


def leader_portrait(leader: Leader | None, size: int = 32) -> ft.Control:
    """The leader's face cropped from its card; a neutral silhouette when unknown or not downloaded yet."""
    src = portraits.source(leader.code) if leader else None
    fallback = ft.Icon(ft.Icons.PERSON_ROUNDED, size=size * 0.6, color=ft.Colors.ON_SURFACE_VARIANT)
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 4,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        alignment=ft.Alignment.CENTER,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Image(src=src, width=size, height=size, fit=ft.BoxFit.COVER, error_content=fallback)
        if src
        else fallback,
    )


def leader_row(leader: Leader | None, placeholder: str, *, size: int = 16, show_code: bool = True) -> ft.Control:
    colors = leader.colors if leader else ()
    name = ft.Text(
        leader.name if leader else placeholder,
        size=size,
        font_family=FONT_SEMIBOLD if leader else None,
        color=None if leader else ft.Colors.ON_SURFACE_VARIANT,
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )
    texts: list[ft.Control] = [name]
    if leader and show_code:
        texts.append(ft.Text(leader.code, size=size - 4, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Row(
        [
            color_bar(colors, height=size + 16),
            leader_portrait(leader, size + 16),
            ft.Column(texts, spacing=0, tight=True, expand=True),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def pill(text: str, color: str, scheme: Scheme, *, size: int = 13) -> ft.Control:
    """A soft-tinted rounded label in `color`."""
    return ft.Container(
        padding=ft.Padding(10, 3, 10, 3),
        border_radius=99,
        bgcolor=scheme.tint(color, 0.22),
        content=ft.Text(text, size=size, font_family=FONT_SEMIBOLD, color=color),
    )


def rate_color(rec: Record, scheme: Scheme) -> str:
    """Green at 50%+ win rate, red below, muted with no games."""
    if not rec.games:
        return scheme.fg_muted
    return scheme.success if rec.win_rate >= 0.5 else scheme.error


def record_pill(rec: Record, scheme: Scheme) -> ft.Control:
    return pill(f"{rec.label()} · {percent(rec.win_rate)}" if rec.games else "—", rate_color(rec, scheme), scheme)


def result_badge(result: str | None, scheme: Scheme, size: int = 36) -> ft.Control:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 3,
        alignment=ft.Alignment.CENTER,
        bgcolor=scheme.results[result] if result else ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Text(
            result or "…",
            size=size * 0.4,
            font_family=FONT_HEAVY,
            color=scheme.on_accent if result else ft.Colors.ON_SURFACE_VARIANT,
        ),
    )


def record_text(rec: Record, size: int = 16) -> ft.Control:
    return ft.Text(
        f"{rec.label()} · {percent(rec.win_rate)}" if rec.games else "—", size=size, font_family=FONT_SEMIBOLD
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
