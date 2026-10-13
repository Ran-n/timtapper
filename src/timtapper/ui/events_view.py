#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.863138
Revised: 2026/10/13 01:17:15.470523

Events tab: every event newest first, with its record, behind a search field and the leader, type and set
filters; FAB starts a new one.
"""

import datetime as dt
from dataclasses import replace

import flet as ft

from core.logging import get_logger
from events.repository import Event
from i18n import bracket_label, standing_label
from stats.compute import Filters, filter_events, record_of
from ui.context import AppContext
from ui.filters import filter_dropdowns
from ui.theme import FONT_HEAVY, FONT_SEMIBOLD
from ui.widgets import (
    card,
    color_bar,
    empty_state,
    event_type_pill,
    leader_portrait,
    logo,
    record_badges,
    update_if_mounted,
)

_log = get_logger("ui.events")

TILE_BAR_WIDTH = 6
NBSP = chr(0x00A0)  # a space a line never breaks at


def event_tile(ctx: AppContext, event: Event) -> ft.Control:
    _ = ctx._
    leader = ctx.leaders_by_id.get(event.leader_id)
    rounds = _("1 round") if len(event.rounds) == 1 else _("{n} rounds").format(n=len(event.rounds))
    muted = ft.Colors.ON_SURFACE_VARIANT
    # the leader's colour bar is pinned to the top and bottom of a stack, so it spans the tile however
    # many lines the texts wrap to (a stretching row would do the same, but blanks the whole list)
    bar = color_bar(leader.colors if leader else (), height=None, width=TILE_BAR_WIDTH)
    bar.left, bar.top, bar.bottom = 0, 0, 0
    # the type pill and the record get a line of their own across the tile's full width, starting over the
    # portrait; below it the name, the leader and the date sit beside the portrait and wrap, never cut
    top = ft.Row(
        [event_type_pill(_, event.event_type, ctx.scheme), record_badges(record_of(event), ctx.scheme)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        wrap=True,  # a fallback only: at 360 dp the full width holds both
        spacing=8,
        run_spacing=4,
        data="tile-top",
    )
    # where you finished, after the date: on the same line when it fits, else the whole of it on the next
    # (its spaces never break, so "#3 of 32" is never split)
    # the bracket first, as standings are talked about ("Top 4 · #3 of 32"), or "Dropped"
    label = " · ".join(
        part
        for part in (
            bracket_label(_, event.placement, event.dropped),
            standing_label(_, event.placement, event.players),
        )
        if part
    )
    standing = (
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.EMOJI_EVENTS_OUTLINED, size=14, color=ft.Colors.TERTIARY),
                    ft.Text(label.replace(" ", NBSP), size=12, font_family=FONT_SEMIBOLD, color=ft.Colors.TERTIARY),
                ],
                spacing=3,
                tight=True,
                data="tile-standing",
            )
        ]
        if label
        else []
    )
    texts = ft.Column(
        [
            ft.Text(event.name, size=17, font_family=FONT_HEAVY, data="event-name"),
            ft.Text(
                leader.name if leader else _("No leader chosen"),
                size=14,
                font_family=FONT_SEMIBOLD if leader else None,
                color=None if leader else muted,
                data="tile-leader",
            ),
            ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=13, color=muted),
                            ft.Text(f"{event.date.isoformat()} · {rounds}", size=12, color=muted),
                        ],
                        spacing=6,
                        tight=True,
                        data="tile-date",
                    ),
                    *standing,
                ],
                wrap=True,
                spacing=10,
                run_spacing=2,
            ),
        ],
        spacing=2,
        expand=True,
    )
    content = ft.Container(
        padding=ft.Padding.only(left=TILE_BAR_WIDTH + 12),
        content=ft.Column(
            [
                top,
                # no chevron: the whole card is the tap target
                ft.Row(
                    [leader_portrait(leader, 56), texts], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )
    return card(
        ft.Stack([content, bar]),
        padding=ft.Padding(12, 12, 8, 12),
        on_click=lambda _e: ctx.navigate(f"/event/{event.id}"),
        data=event.id,
    )


def new_event(ctx: AppContext) -> None:
    event = ctx.new_event("locals", dt.date.today(), ctx.events.last_used_leader_id())
    _log.info("new event %d from the events tab", event.id)
    ctx.navigate(f"/event/{event.id}")


def build(ctx: AppContext) -> tuple[list[ft.Control], ft.FloatingActionButton]:
    _ = ctx._
    events = ctx.events.list()
    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        content=ft.Text(_("New event")),
        on_click=lambda _e: new_event(ctx),
    )
    if not events:
        return [
            empty_state(
                logo(120),
                _("No events yet"),
                _("Log a testing session, a locals or a major — then add each round as you play it."),
            )
        ], fab
    return EventList(ctx, events).build(), fab


class EventList:
    """The events, behind a search field whose filter button opens the leader and type dropdowns in place.

    The search field is built once (rebuilding it would drop focus mid-word); only the dropdowns and the
    tiles below it are redrawn when a filter changes."""

    def __init__(self, ctx: AppContext, events: list[Event]) -> None:
        self.ctx = ctx
        self.events = events
        self.dropdowns = ft.Column(data="event-filter-dropdowns")
        self.results = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, data="event-results")
        self.toggle = ft.IconButton(on_click=self._toggle, data="event-filter-toggle")
        self.search = ft.TextField(
            value=ctx.event_filters.query,
            hint_text=ctx._("Search events"),
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            expand=True,
            on_change=self._search,
            data="event-search",
        )
        # the button sits beside the field, not inside it: Flutter draws a field's suffix only while focused
        self.search_row = ft.Row([self.search, self.toggle], spacing=4, data="event-search-row")

    @property
    def filters(self) -> Filters:
        return self.ctx.event_filters

    def build(self) -> list[ft.Control]:
        self.refresh()
        return [self.search_row, self.dropdowns, self.results]

    def apply(self, filters: Filters) -> None:
        _log.info("events filtered: %s", filters)
        self.ctx.event_filters = filters
        self.refresh()

    def _search(self, e) -> None:
        f = self.filters
        self.apply(replace(f, query=e.control.value or ""))

    def _toggle(self, _e) -> None:
        self.ctx.event_filters_open = not self.ctx.event_filters_open
        self.refresh()

    def _clear(self, _e) -> None:
        self.search.value = ""
        update_if_mounted(self.search)
        self.apply(Filters())

    def refresh(self) -> None:
        _ = self.ctx._
        f = self.filters
        # a leader, type or set filter keeps the dropdowns open, so what narrows the list is always on screen
        picked = f.own_leader_id is not None or f.event_type is not None or f.set_code is not None
        open_ = self.ctx.event_filters_open or picked
        self.toggle.icon = ft.Icons.FILTER_LIST_OFF if open_ else ft.Icons.FILTER_LIST
        self.toggle.icon_color = ft.Colors.PRIMARY if picked else None
        self.toggle.tooltip = _("Filters")
        self.toggle.disabled = picked  # closing would hide a filter that's still on
        self.dropdowns.controls = [filter_dropdowns(self.ctx, self.events, f, self.apply)] if open_ else []

        shown = filter_events(self.events, f)
        controls: list[ft.Control] = []
        if f.active:
            controls.append(
                ft.Text(
                    _("{shown} of {total} events").format(shown=len(shown), total=len(self.events)),
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    data="event-count",
                )
            )
        controls += [event_tile(self.ctx, ev) for ev in shown] or [
            empty_state(ft.Icons.SEARCH_OFF, _("No events match"), _("Try another search or filter.")),
            ft.TextButton(
                _("Clear filters"), icon=ft.Icons.FILTER_LIST_OFF, on_click=self._clear, data="clear-filters"
            ),
        ]
        self.results.controls = controls
        for control in (self.toggle, self.dropdowns, self.results):
            update_if_mounted(control)
