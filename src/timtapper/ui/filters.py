#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 16:01:23.794407
Revised: 2026/10/12 16:55:02.633487

The own-leader and event-type dropdowns, shared by the stats tab and the events list so both
filter the same way.
"""

from collections.abc import Callable

import flet as ft

from db.models import EVENT_TYPES
from events.repository import Event
from i18n import event_type_label
from stats.compute import Filters, own_leaders
from ui.context import AppContext

ALL = "all"


def filter_dropdowns(
    ctx: AppContext, events: list[Event], filters: Filters, on_change: Callable[[Filters], None]
) -> ft.Column:
    """Leader (only leaders that have events, most used first) and event type, each with an "all" option."""
    _ = ctx._
    by_id = ctx.leaders_by_id

    def set_leader(e) -> None:
        value = e.control.value
        on_change(Filters(None if value == ALL else int(value), filters.event_type, filters.query))

    def set_type(e) -> None:
        value = e.control.value
        on_change(Filters(filters.own_leader_id, None if value == ALL else value, filters.query))

    leader_opts = [ft.DropdownOption(key=ALL, text=_("All leaders"))] + [
        ft.DropdownOption(key=str(lid), text=by_id[lid].label) for lid in own_leaders(events) if lid in by_id
    ]
    type_opts = [ft.DropdownOption(key=ALL, text=_("All event types"))] + [
        ft.DropdownOption(key=k, text=event_type_label(_, k)) for k in EVENT_TYPES
    ]
    return ft.Column(
        [
            ft.Dropdown(
                label=_("Your leader"),
                value=str(filters.own_leader_id) if filters.own_leader_id else ALL,
                options=leader_opts,
                on_select=set_leader,
                dense=True,
                width=float("inf"),
                data="filter-leader",
            ),
            ft.Dropdown(
                label=_("Event type"),
                value=filters.event_type or ALL,
                options=type_opts,
                on_select=set_type,
                dense=True,
                width=float("inf"),
                data="filter-type",
            ),
        ],
        spacing=10,
    )
