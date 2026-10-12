#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:43.228774
Revised: 2026/10/12 16:54:59.298574

Stats tab: overall record, splits, recent form and the matchup table, filterable by own leader and event type.
"""

import flet as ft

from i18n import event_type_label
from share import render
from stats.compute import Filters, Summary, games, matchups, percent, summarize
from ui.context import AppContext
from ui.filters import filter_dropdowns
from ui.theme import FONT_HEAVY
from ui.widgets import (
    big_number,
    caption,
    card,
    leader_row,
    rate_color,
    record_badges,
    section,
    stat_tile,
    update_if_mounted,
)


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
        def apply(filters: Filters) -> None:
            self.filters = filters
            self.refresh()

        return filter_dropdowns(self.ctx, events, self.filters, apply)

    def _summary(self, s: Summary) -> list[ft.Control]:
        _ = self.ctx._
        by_id = self.ctx.leaders_by_id
        scheme = self.ctx.scheme

        def matchup_tile(label: str, m) -> ft.Control:
            if m is None:
                value = ft.Text(_("Not enough games"), color=ft.Colors.ON_SURFACE_VARIANT)
            else:
                # the record on the name's line; a long name wraps beside it rather than being cut
                value = ft.Row(
                    [
                        leader_row(by_id.get(m.opponent_leader_id), _("Unknown leader"), size=14, show_code=False),
                        record_badges(m.record, scheme),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    data="matchup-line",
                )
            return stat_tile(label, value)

        form = ft.Row(
            [
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=scheme.results[r],
                    content=ft.Text(r, size=12, font_family=FONT_HEAVY, color=scheme.on_accent),
                )
                for r in s.recent
            ]
            or [ft.Text("—")],
            spacing=4,
            wrap=True,
        )
        rate = rate_color(s.record, scheme)
        hero = card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [caption(_("Win rate")), big_number(percent(s.record.win_rate), rate, 44)],
                                spacing=0,
                                expand=True,
                            ),
                            ft.Column(
                                [caption(_("Record")), big_number(s.record.label(), size=22)],
                                spacing=0,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                            ft.Column(
                                [caption(_("Events")), big_number(str(s.events), size=22)],
                                spacing=0,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                            ),
                        ],
                        spacing=20,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.ProgressBar(
                        value=s.record.win_rate if s.record.games else 0,
                        color=rate,
                        bgcolor=scheme.surface_highest,
                        bar_height=8,
                        border_radius=4,
                    ),
                ],
                spacing=12,
            ),
            padding=18,
            data="hero",
        )
        return [
            hero,
            ft.Row([
                stat_tile(_("Going 1st"), record_badges(s.first, scheme, size=15)),
                stat_tile(_("Going 2nd"), record_badges(s.second, scheme, size=15)),
            ]),
            ft.Row([
                stat_tile(_("Won the die roll"), record_badges(s.die_won, scheme, size=15)),
                stat_tile(_("Lost the die roll"), record_badges(s.die_lost, scheme, size=15)),
            ]),
            # a row each: side by side, a ~70 dp name column broke "Donquixote Doflamingo" mid-word at 360 dp
            matchup_tile(_("Best matchup"), s.best),
            matchup_tile(_("Worst matchup"), s.worst),
            stat_tile(_("Recent form"), form),
        ]

    def _matchups(self, ms) -> list[ft.Control]:
        _ = self.ctx._
        by_id = self.ctx.leaders_by_id
        if not ms:
            return [ft.Text(_("No games logged yet"), color=ft.Colors.ON_SURFACE_VARIANT)]
        return [
            card(
                padding=ft.Padding(12, 10, 12, 10),
                radius=14,
                content=ft.Row([
                    leader_row(by_id.get(m.opponent_leader_id), _("Unknown leader"), size=14),
                    ft.Column(
                        [
                            record_badges(m.record, self.ctx.scheme),
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
