#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.420418
Revised: 2026/10/11 16:27:23.922239

Small building blocks reused across screens.
"""

from collections.abc import Callable

import flet as ft

from catalog.repository import Leader
from stats.compute import Record, percent
from ui.theme import CARD_COLORS, RESULT_COLORS, UNKNOWN_COLOR


def update_if_mounted(control: ft.Control) -> None:
    """Push a rebuilt control to the client — a no-op before it's on screen (first build)."""
    try:
        control.page  # noqa: B018 — raises RuntimeError while the control isn't attached yet
    except RuntimeError:
        return
    control.update()


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


def leader_row(leader: Leader | None, placeholder: str, *, size: int = 16, show_code: bool = True) -> ft.Control:
    colors = leader.colors if leader else ()
    name = ft.Text(
        leader.name if leader else placeholder,
        size=size,
        weight=ft.FontWeight.W_600 if leader else None,
        color=None if leader else ft.Colors.ON_SURFACE_VARIANT,
        overflow=ft.TextOverflow.ELLIPSIS,
        max_lines=1,
    )
    texts: list[ft.Control] = [name]
    if leader and show_code:
        texts.append(ft.Text(leader.code, size=size - 4, color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.Row(
        [color_bar(colors, height=size + 16), ft.Column(texts, spacing=0, tight=True, expand=True)],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def result_badge(result: str | None, size: int = 36) -> ft.Control:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 2,
        alignment=ft.Alignment.CENTER,
        bgcolor=RESULT_COLORS[result] if result else ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Text(
            result or "…",
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE if result else ft.Colors.ON_SURFACE_VARIANT,
        ),
    )


def record_text(rec: Record, size: int = 16) -> ft.Control:
    return ft.Text(
        f"{rec.label()} · {percent(rec.win_rate)}" if rec.games else "—",
        size=size,
        weight=ft.FontWeight.W_600,
    )


def stat_tile(label: str, value: ft.Control) -> ft.Control:
    return ft.Container(
        expand=True,
        padding=14,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        content=ft.Column([ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT), value], spacing=4, tight=True),
    )


def section(title: str) -> ft.Control:
    return ft.Container(
        padding=ft.Padding(4, 18, 4, 6),
        content=ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
    )


def make_notifier(page: ft.Page) -> Callable[..., None]:
    """Snackbar notifier. A fresh SnackBar every time: Flet ignores in-place
    updates to one that's already been on screen for a while."""

    def notify(msg: str, error: bool = False) -> None:
        page.show_dialog(
            ft.SnackBar(
                ft.Text(msg, color=ft.Colors.ON_ERROR if error else ft.Colors.ON_INVERSE_SURFACE),
                bgcolor=ft.Colors.ERROR if error else ft.Colors.INVERSE_SURFACE,
                duration=4000,
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
