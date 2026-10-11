#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.863138
Revised: 2026/10/11 16:27:23.487401

Events tab: every event newest first, with its record; FAB starts a new one.
"""

import datetime as dt

import flet as ft

from core.logging import get_logger
from events.repository import Event
from i18n import event_type_label
from stats.compute import record_of
from ui.context import AppContext
from ui.widgets import leader_row, record_text

_log = get_logger("ui.events")


def event_tile(ctx: AppContext, event: Event) -> ft.Control:
    _ = ctx._
    leader = ctx.leaders_by_id.get(event.leader_id)
    rec = record_of(event)
    return ft.Container(
        padding=14,
        border_radius=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        ink=True,
        on_click=lambda _e: ctx.navigate(f"/event/{event.id}"),
        data=event.id,
        content=ft.Column(
            [
                ft.Row([
                    ft.Text(
                        event.name,
                        size=17,
                        weight=ft.FontWeight.BOLD,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    record_text(rec),
                ]),
                ft.Text(
                    f"{event_type_label(_, event.event_type)} · {event.date.isoformat()} · "
                    + (_("1 round") if len(event.rounds) == 1 else _("{n} rounds").format(n=len(event.rounds))),
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                leader_row(leader, _("No leader chosen"), size=15),
            ],
            spacing=6,
        ),
    )


def empty_state(ctx: AppContext) -> ft.Control:
    _ = ctx._
    return ft.Container(
        padding=40,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(ft.Icons.STYLE_OUTLINED, size=56, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(_("No events yet"), size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    _("Log a testing session, a locals or a major — then add each round as you play it."),
                    text_align=ft.TextAlign.CENTER,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )


def new_event(ctx: AppContext) -> None:
    _ = ctx._
    event = ctx.events.create(_("New event"), "locals", dt.date.today(), leader_id=ctx.events.last_used_leader_id())
    _log.info("new event %d from the events tab", event.id)
    ctx.navigate(f"/event/{event.id}")


def build(ctx: AppContext) -> tuple[list[ft.Control], ft.FloatingActionButton]:
    _ = ctx._
    events = ctx.events.list()
    body: list[ft.Control] = [event_tile(ctx, ev) for ev in events] or [empty_state(ctx)]
    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD, content=ft.Text(_("New event")), on_click=lambda _e: new_event(ctx)
    )
    return body, fab
