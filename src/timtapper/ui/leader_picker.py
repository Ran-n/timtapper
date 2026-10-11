#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.041772
Revised: 2026/10/11 23:25:32.325182

Searchable leader picker in a bottom sheet (most-played opponents first),
narrowed by color chips (a leader must have every selected color) and a set
dropdown. Filters live in the sheet's closure, so every opening starts clean.
"""

from collections.abc import Awaitable, Callable

import flet as ft

from catalog.repository import Leader, filter_leaders, set_codes
from core.logging import get_logger
from db.models import COLORS
from i18n import color_label
from ui.context import AppContext
from ui.theme import CARD_COLORS
from ui.widgets import leader_row, update_if_mounted

_log = get_logger("ui.picker")

MAX_RESULTS = 60
ALL_SETS = ""


def build_picker(ctx: AppContext, title: str, on_pick: Callable[[Leader], Awaitable[None] | None]) -> ft.BottomSheet:
    _ = ctx._
    results = ft.ListView(expand=True, spacing=2, data="leader-results")
    state = {"query": "", "set_code": ALL_SETS}
    colors: set[str] = set()

    async def pick(leader: Leader) -> None:
        ctx.page.pop_dialog()
        outcome = on_pick(leader)
        if outcome is not None:
            await outcome

    def pick_handler(leader: Leader):
        async def handler(_e) -> None:
            await pick(leader)

        return handler

    def render() -> None:
        found = filter_leaders(ctx.leaders, state["query"], frozenset(colors), state["set_code"] or None)
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

    def refresh() -> None:
        _log.debug("filter query=%r colors=%s set=%r", state["query"], sorted(colors), state["set_code"])
        render()
        update_if_mounted(results)

    def on_change(e: ft.Event[ft.TextField]) -> None:
        state["query"] = e.control.value or ""
        refresh()

    def on_color(e: ft.Event[ft.Chip]) -> None:
        chip = e.control  # the client has already flipped chip.selected
        color = chip.data.removeprefix("color-")
        if chip.selected:
            colors.add(color)
        else:
            colors.discard(color)
        refresh()

    def on_set(e: ft.Event[ft.Dropdown]) -> None:
        state["set_code"] = e.control.value or ALL_SETS
        refresh()

    def color_chip(color: str) -> ft.Chip:
        dot = ft.Container(width=12, height=12, border_radius=6, bgcolor=CARD_COLORS[color])
        return ft.Chip(label=ft.Text(color_label(_, color)), leading=dot, on_select=on_color, data=f"color-{color}")

    render()
    field = ft.TextField(
        hint_text=_("Search name, code or color"),
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        border=ft.OutlineInputBorder(border_radius=24),
        on_change=on_change,
        data="leader-search",
    )
    # wraps instead of scrolling sideways, so the six chips fit a 360 px screen
    color_filters = ft.Row([color_chip(c) for c in COLORS], wrap=True, spacing=6, run_spacing=6, data="color-filters")
    set_filter = ft.Dropdown(
        label=_("Set"),
        value=ALL_SETS,
        options=[ft.DropdownOption(key=ALL_SETS, text=_("All sets"))]
        + [ft.DropdownOption(key=code, text=code) for code in set_codes(ctx.leaders)],
        on_select=on_set,
        dense=True,
        width=float("inf"),
        data="set-filter",
    )
    return ft.BottomSheet(
        show_drag_handle=True,
        scrollable=True,
        content=ft.Container(
            height=640,
            padding=ft.Padding(16, 0, 16, 16),
            content=ft.Column(
                [ft.Text(title, size=18, weight=ft.FontWeight.BOLD), field, color_filters, set_filter, results],
                spacing=10,
            ),
        ),
    )


def open_picker(ctx: AppContext, title: str, on_pick: Callable[[Leader], Awaitable[None] | None]) -> None:
    ctx.page.show_dialog(build_picker(ctx, title, on_pick))
