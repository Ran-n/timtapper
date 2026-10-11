#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.041772
Revised: 2026/10/11 16:27:23.634621

Searchable leader picker in a bottom sheet (most-played opponents first).
"""

from collections.abc import Awaitable, Callable

import flet as ft

from catalog.repository import Leader, search
from ui.context import AppContext
from ui.widgets import leader_row, update_if_mounted

MAX_RESULTS = 60


def build_picker(ctx: AppContext, title: str, on_pick: Callable[[Leader], Awaitable[None] | None]) -> ft.BottomSheet:
    _ = ctx._
    results = ft.ListView(expand=True, spacing=2)

    async def pick(leader: Leader) -> None:
        ctx.page.pop_dialog()
        outcome = on_pick(leader)
        if outcome is not None:
            await outcome

    def pick_handler(leader: Leader):
        async def handler(_e) -> None:
            await pick(leader)

        return handler

    def render(query: str) -> None:
        found = search(ctx.leaders, query)
        results.controls = [
            ft.Container(
                content=leader_row(leader, ""),
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=12,
                ink=True,
                on_click=pick_handler(leader),
                data=leader.id,
            )
            for leader in found[:MAX_RESULTS]
        ] or [ft.Container(padding=24, content=ft.Text(_("No leader matches"), color=ft.Colors.ON_SURFACE_VARIANT))]

    def on_change(e: ft.Event[ft.TextField]) -> None:
        render(e.control.value)
        update_if_mounted(results)

    render("")
    field = ft.TextField(
        hint_text=_("Search name, code or color"),
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        border_radius=24,
        on_change=on_change,
    )
    return ft.BottomSheet(
        show_drag_handle=True,
        scrollable=True,
        content=ft.Container(
            height=560,
            padding=ft.Padding(16, 0, 16, 16),
            content=ft.Column([ft.Text(title, size=18, weight=ft.FontWeight.BOLD), field, results], spacing=10),
        ),
    )


def open_picker(ctx: AppContext, title: str, on_pick: Callable[[Leader], Awaitable[None] | None]) -> None:
    ctx.page.show_dialog(build_picker(ctx, title, on_pick))
