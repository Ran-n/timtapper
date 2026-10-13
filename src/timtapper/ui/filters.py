#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 16:01:23.794407
Revised: 2026/10/13 01:17:14.861321

The own-leader, event-type and set dropdowns, shared by the stats tab and the events list so both
filter the same way.
"""

from collections.abc import Callable
from dataclasses import replace

import flet as ft

from catalog.repository import sort_set_codes
from db.models import EVENT_TYPES
from events.repository import Event
from i18n import event_type_label
from stats.compute import Filters, own_leaders
from ui.context import AppContext
from ui.widgets import leader_portrait

ALL = "all"
OPTION_PORTRAIT = 28  # a leader's framed face beside its name in the dropdown, as in the leader picker


def _with[T](options: list[T], picked: T | None) -> list[T]:
    """`options`, plus the picked value at the end when it isn't among them."""
    return options if picked is None or picked in options else [*options, picked]


def filter_dropdowns(
    ctx: AppContext, events: list[Event], filters: Filters, on_change: Callable[[Filters], None]
) -> ft.Column:
    """Leader (only leaders that have events, most used first), event type and set (only sets of your events),
    each with an "all" option. A leader or set picked earlier stays listed after its last event is deleted, so
    the filter still on shows its value instead of a blank field."""
    _ = ctx._
    by_id = ctx.leaders_by_id

    def set_leader(e) -> None:
        value = e.control.value
        on_change(replace(filters, own_leader_id=None if value == ALL else int(value)))

    def set_type(e) -> None:
        value = e.control.value
        on_change(replace(filters, event_type=None if value == ALL else value))

    def set_set(e) -> None:
        value = e.control.value
        on_change(replace(filters, set_code=None if value == ALL else value))

    leader_opts = [ft.DropdownOption(key=ALL, text=_("All leaders"), leading_icon=ft.Icons.GROUPS_OUTLINED)] + [
        ft.DropdownOption(
            key=str(lid), text=by_id[lid].label, leading_icon=leader_portrait(by_id[lid], OPTION_PORTRAIT)
        )
        for lid in _with(own_leaders(events), filters.own_leader_id)
        if lid in by_id
    ]
    picked = by_id.get(filters.own_leader_id)
    type_opts = [ft.DropdownOption(key=ALL, text=_("All event types"))] + [
        ft.DropdownOption(key=k, text=event_type_label(_, k)) for k in EVENT_TYPES
    ]
    # only the sets your events were played in, newest first
    set_opts = [ft.DropdownOption(key=ALL, text=_("All sets"))] + [
        ft.DropdownOption(key=code, text=code)
        for code in sort_set_codes(_with([ev.set_code for ev in events if ev.set_code], filters.set_code))
    ]
    return ft.Column(
        [
            ft.Dropdown(
                label=_("Your leader"),
                value=str(filters.own_leader_id) if filters.own_leader_id else ALL,
                options=leader_opts,
                # the chosen leader's face shows in the closed field too
                leading_icon=leader_portrait(picked, OPTION_PORTRAIT) if picked else ft.Icons.GROUPS_OUTLINED,
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
            ft.Dropdown(
                label=_("Set"),
                value=filters.set_code or ALL,
                options=set_opts,
                on_select=set_set,
                dense=True,
                width=float("inf"),
                data="filter-set",
            ),
        ],
        spacing=10,
    )
