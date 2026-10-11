#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.228774
Revised: 2026/10/11 16:27:23.780876

Stats tab: overall record, splits, recent form and the matchup table, filterable by own leader and event type.
"""

import flet as ft

from db.models import EVENT_TYPES
from i18n import event_type_label
from share import render
from stats.compute import Filters, Summary, games, matchups, own_leaders, percent, summarize
from ui.context import AppContext
from ui.theme import RESULT_COLORS
from ui.widgets import leader_row, record_text, section, stat_tile, update_if_mounted

ALL = "all"


class StatsScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.filters = Filters()
        self.body = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def scope_label(self) -> str:
        _ = self.ctx._
        leader = self.ctx.leaders_by_id.get(self.filters.own_leader_id)
        scope = _("Playing {leader}").format(leader=leader.name) if leader else _("All leaders")
        if self.filters.event_type:
            scope += f" · {event_type_label(_, self.filters.event_type)}"
        return scope

    def _filters_row(self, events) -> ft.Control:
        _ = self.ctx._
        by_id = self.ctx.leaders_by_id

        def set_leader(e) -> None:
            value = e.control.value
            self.filters = Filters(None if value == ALL else int(value), self.filters.event_type)
            self.refresh()

        def set_type(e) -> None:
            value = e.control.value
            self.filters = Filters(self.filters.own_leader_id, None if value == ALL else value)
            self.refresh()

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
                    value=str(self.filters.own_leader_id) if self.filters.own_leader_id else ALL,
                    options=leader_opts,
                    on_select=set_leader,
                    dense=True,
                    width=float("inf"),
                    data="filter-leader",
                ),
                ft.Dropdown(
                    label=_("Event type"),
                    value=self.filters.event_type or ALL,
                    options=type_opts,
                    on_select=set_type,
                    dense=True,
                    width=float("inf"),
                    data="filter-type",
                ),
            ],
            spacing=10,
        )

    def _summary(self, s: Summary) -> list[ft.Control]:
        _ = self.ctx._
        by_id = self.ctx.leaders_by_id

        def matchup_tile(label: str, m) -> ft.Control:
            if m is None:
                value = ft.Text(_("Not enough games"), color=ft.Colors.ON_SURFACE_VARIANT)
            else:
                value = ft.Column(
                    [
                        leader_row(by_id.get(m.opponent_leader_id), _("Unknown leader"), size=14, show_code=False),
                        record_text(m.record, 14),
                    ],
                    spacing=4,
                    tight=True,
                )
            return stat_tile(label, value)

        form = ft.Row(
            [
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=RESULT_COLORS[r],
                    content=ft.Text(r, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )
                for r in s.recent
            ]
            or [ft.Text("—")],
            spacing=4,
            wrap=True,
        )
        return [
            ft.Row([
                stat_tile(_("Record"), ft.Text(s.record.label(), size=28, weight=ft.FontWeight.BOLD)),
                stat_tile(
                    _("Win rate"),
                    ft.Text(percent(s.record.win_rate), size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                ),
                stat_tile(_("Events"), ft.Text(str(s.events), size=28, weight=ft.FontWeight.BOLD)),
            ]),
            ft.Row([stat_tile(_("Going 1st"), record_text(s.first)), stat_tile(_("Going 2nd"), record_text(s.second))]),
            ft.Row([
                stat_tile(_("Won the die roll"), record_text(s.die_won)),
                stat_tile(_("Lost the die roll"), record_text(s.die_lost)),
            ]),
            ft.Row([matchup_tile(_("Best matchup"), s.best), matchup_tile(_("Worst matchup"), s.worst)]),
            stat_tile(_("Recent form"), form),
        ]

    def _matchups(self, ms) -> list[ft.Control]:
        _ = self.ctx._
        by_id = self.ctx.leaders_by_id
        if not ms:
            return [ft.Text(_("No games logged yet"), color=ft.Colors.ON_SURFACE_VARIANT)]
        return [
            ft.Container(
                padding=ft.Padding(12, 8, 12, 8),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                content=ft.Row([
                    leader_row(by_id.get(m.opponent_leader_id), _("Unknown leader"), size=14),
                    ft.Column(
                        [
                            record_text(m.record, 14),
                            ft.Text(
                                _("1st {first} · 2nd {second}").format(
                                    first=m.first.label() if m.first.games else "—",
                                    second=m.second.label() if m.second.games else "—",
                                ),
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                ]),
            )
            for m in ms
        ]

    async def _share_summary(self, _e) -> None:
        _ = self.ctx._
        s, scope, leaders = self._summary_data(), self.scope_label(), self.ctx.leaders_by_id
        await self.ctx.share_file(lambda: render.summary_card(scope, s, leaders, _), title=_("Overall record"))

    async def _share_matchups(self, _e) -> None:
        _ = self.ctx._
        events = self.ctx.events.list()
        s, ms = summarize(events, self.filters), matchups(games(events, self.filters))
        scope, leaders = self.scope_label(), self.ctx.leaders_by_id
        await self.ctx.share_file(lambda: render.matchups_card(scope, s, ms, leaders, _), title=_("Matchups"))

    def _summary_data(self) -> Summary:
        return summarize(self.ctx.events.list(), self.filters)

    def _controls(self) -> list[ft.Control]:
        _ = self.ctx._
        events = self.ctx.events.list()
        s = summarize(events, self.filters)
        ms = matchups(games(events, self.filters))
        has_games = s.record.games > 0
        return [
            self._filters_row(events),
            *self._summary(s),
            ft.FilledButton(
                content=_("Share summary"),
                icon=ft.Icons.SHARE,
                height=52,
                width=float("inf"),
                disabled=not has_games,
                on_click=self._share_summary,
                data="share-summary",
            ),
            section(_("Matchups")),
            *self._matchups(ms),
            ft.Row(
                [
                    ft.TextButton(
                        _("Share matchups"),
                        icon=ft.Icons.SHARE,
                        disabled=not has_games,
                        on_click=self._share_matchups,
                        data="share-matchups",
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=24),
        ]

    def refresh(self) -> None:
        self.body.controls = self._controls()
        update_if_mounted(self.body)

    def build(self) -> ft.Control:
        self.body.controls = self._controls()
        return self.body
