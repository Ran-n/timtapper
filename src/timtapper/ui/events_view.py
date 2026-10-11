#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.863138
Revised: 2026/10/11 17:13:51.771259

Events tab: every event newest first, with its record; FAB starts a new one.
"""

import datetime as dt

import flet as ft

from core.logging import get_logger
from events.repository import Event
from i18n import event_type_label
from stats.compute import record_of
from ui.context import AppContext
from ui.theme import FONT_HEAVY, FONT_SEMIBOLD
from ui.widgets import card, color_bar, empty_state, leader_portrait, logo, record_pill

_log = get_logger("ui.events")


def event_tile(ctx: AppContext, event: Event) -> ft.Control:
    _ = ctx._
    leader = ctx.leaders_by_id.get(event.leader_id)
    rounds = _("1 round") if len(event.rounds) == 1 else _("{n} rounds").format(n=len(event.rounds))
    muted = ft.Colors.ON_SURFACE_VARIANT
    return card(
        ft.Row(
            [
                color_bar(leader.colors if leader else (), height=74, width=6),
                leader_portrait(leader, 56),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    event.name,
                                    size=17,
                                    font_family=FONT_HEAVY,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                record_pill(record_of(event), ctx.scheme),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            leader.name if leader else _("No leader chosen"),
                            size=14,
                            font_family=FONT_SEMIBOLD if leader else None,
                            color=None if leader else muted,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CALENDAR_TODAY_OUTLINED, size=13, color=muted),
                                ft.Text(
                                    f"{event.date.isoformat()} · {event_type_label(_, event.event_type)} · {rounds}",
                                    size=12,
                                    color=muted,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=4,
                    expand=True,
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=muted),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(12, 12, 8, 12),
        on_click=lambda _e: ctx.navigate(f"/event/{event.id}"),
        data=event.id,
    )


def new_event(ctx: AppContext) -> None:
    _ = ctx._
    event = ctx.events.create(_("New event"), "locals", dt.date.today(), leader_id=ctx.events.last_used_leader_id())
    _log.info("new event %d from the events tab", event.id)
    ctx.navigate(f"/event/{event.id}")


def build(ctx: AppContext) -> tuple[list[ft.Control], ft.FloatingActionButton]:
    _ = ctx._
    events = ctx.events.list()
    body: list[ft.Control] = [event_tile(ctx, ev) for ev in events] or [
        empty_state(
            logo(120),
            _("No events yet"),
            _("Log a testing session, a locals or a major — then add each round as you play it."),
        )
    ]
    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        content=ft.Text(_("New event")),
        on_click=lambda _e: new_event(ctx),
    )
    return body, fab
