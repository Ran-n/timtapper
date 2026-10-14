#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.041772
Revised: 2026/10/14 01:17:20.519557

Searchable leader picker in a bottom sheet (most-played opponents first),
narrowed by color dots (a leader must have every selected color) and a set
dropdown. Filters live in the sheet's closure, so every opening starts clean.
"""

from collections.abc import Awaitable, Callable

import flet as ft

from catalog.repository import Leader, filter_leaders, set_codes
from core.card_colors import CARD_COLORS
from core.logging import get_logger
from db.models import COLORS
from i18n import color_label
from ui.context import AppContext
from ui.widgets import leader_row, update_if_mounted

_log = get_logger("ui.picker")

MAX_RESULTS = 60
ALL_SETS = ""
DOT_SIZE = 28
TAP_SIZE = 44


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
        if len(found) > MAX_RESULTS:  # say the list stops, so a leader further down isn't taken for missing
            results.controls.append(
                ft.Container(
                    padding=ft.Padding(12, 8, 12, 8),
                    content=ft.Text(
                        _("{shown} of {total} leaders — search to find the rest").format(
                            shown=MAX_RESULTS, total=len(found)
                        ),
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    data="more-leaders",
                )
            )

    def refresh() -> None:
        _log.debug("filter query=%r colors=%s set=%r", state["query"], sorted(colors), state["set_code"])
        render()
        update_if_mounted(results)

    def on_change(e: ft.Event[ft.TextField]) -> None:
        state["query"] = e.control.value or ""
        refresh()

    def on_color(e: ft.Event[ft.Container]) -> None:
        # containers carry no selected state: the `colors` set is the single source of truth
        target = e.control
        color = target.data.removeprefix("color-")
        colors.symmetric_difference_update({color})
        paint_dot(target.content, color)
        update_if_mounted(target)
        refresh()

    def on_set(e: ft.Event[ft.Dropdown]) -> None:
        state["set_code"] = e.control.value or ALL_SETS
        refresh()

    def paint_dot(dot: ft.Container, color: str) -> None:
        """Ring + check when selected (the check keeps it readable without the ring); hairline edge otherwise."""
        selected = color in colors
        dot.border = ft.Border.all(3, ft.Colors.ON_SURFACE) if selected else ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
        check_color = ft.Colors.BLACK if color == "Yellow" else ft.Colors.WHITE  # white on yellow is unreadable
        dot.content = ft.Icon(ft.Icons.CHECK, size=16, color=check_color) if selected else None

    def color_dot(color: str) -> ft.Container:
        dot = ft.Container(
            width=DOT_SIZE,
            height=DOT_SIZE,
            border_radius=DOT_SIZE / 2,
            bgcolor=CARD_COLORS[color],
            alignment=ft.Alignment.CENTER,
        )
        paint_dot(dot, color)
        return ft.Container(  # the tap target, at Material's minimum touch size
            width=TAP_SIZE,
            height=TAP_SIZE,
            border_radius=TAP_SIZE / 2,
            alignment=ft.Alignment.CENTER,
            ink=True,
            tooltip=color_label(_, color),
            on_click=on_color,
            data=f"color-{color}",
            content=dot,
        )

    render()
    field = ft.TextField(
        # short enough for a 360 dp phone in every language (the icon says "search"): "Search name, code or color"
        # was cut off there, its Spanish on any 360 dp screen
        hint_text=_("Name, code or color"),
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        border=ft.OutlineInputBorder(border_radius=24),
        on_change=on_change,
        data="leader-search",
    )
    # one row of dots fits a 360 px screen: 6 x 44 + 5 x 4 = 284 px of the 328 px inside the sheet's padding
    color_filters = ft.Row(
        [color_dot(c) for c in COLORS],
        wrap=False,
        spacing=4,
        alignment=ft.MainAxisAlignment.START,
        data="color-filters",
    )
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
