#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.952473
Revised: 2026/10/12 16:54:58.843511

Event screen: everything edited in place — name, type, date, own leader and
notes in the header; each round as an expandable tile with its result, turn
order, die roll, top-cut flag and notes. Rounds without a result stay open
so the round being played is one tap away.
"""

import datetime as dt
from collections.abc import Callable, Sequence

import flet as ft

from catalog.repository import Leader
from core.logging import get_logger
from db.models import EVENT_TYPES, RESULTS
from events.repository import Event, EventError, Round
from i18n import UNRANKED_EVENT_TYPES, event_type_label
from share import render
from stats.compute import percent, record_of
from ui.context import AppContext
from ui.leader_picker import open_picker
from ui.theme import FONT_HEAVY
from ui.widgets import (
    RADIUS,
    big_number,
    caption,
    card,
    confirm,
    die_badge,
    leader_row,
    rate_color,
    result_badge,
    section,
    turn_badge,
    update_if_mounted,
)

_log = get_logger("ui.event")

# what one tap on a round row's indicator steps through, ending back at "unknown"
RESULT_CYCLE = (None, *RESULTS)
TRISTATE_CYCLE = (None, True, False)
# a round row on one line: "R1"/"TC" column, the opponent, then the three indicators
ROUND_LABEL_WIDTH = 26  # "R10" and "TC" in the heavy font, without wrapping
ROUND_GAP = 4


def _next[T](value: T, cycle: Sequence[T]) -> T:
    """The element after `value` in `cycle`, wrapping; an unknown value starts the cycle over."""
    try:
        return cycle[(cycle.index(value) + 1) % len(cycle)]
    except ValueError:
        return cycle[0]


class EventScreen:
    def __init__(self, ctx: AppContext, event_id: int) -> None:
        self.ctx = ctx
        self.event_id = event_id
        self.event: Event = ctx.events.get(event_id)
        self.expanded: set[int] = {r.id for r in self.event.rounds if r.result is None}
        self.body = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ---- persistence helpers -------------------------------------------
    def _guard(self, action: Callable[[], object]) -> bool:
        """Run a repository call; report rejected input instead of crashing."""
        try:
            action()
        except EventError as exc:
            _log.warning("event %d: rejected edit: %s", self.event_id, exc)
            self.ctx.notify(self.ctx._("Could not save: {error}").format(error=exc), error=True)
            return False
        return True

    def _save_event(self, **fields) -> None:
        if self._guard(lambda: self.ctx.events.update(self.event_id, **fields)):
            self.refresh()

    def _save_round(self, round_id: int, **fields) -> None:
        if self._guard(lambda: self.ctx.events.update_round(round_id, **fields)):
            self.refresh()

    def refresh(self) -> None:
        self.event = self.ctx.events.get(self.event_id)
        self.body.controls = self._controls()
        update_if_mounted(self.body)

    # ---- header ----------------------------------------------------------
    def _header(self) -> list[ft.Control]:
        _ = self.ctx._
        ev = self.event

        def save_name(e: ft.Event[ft.TextField]) -> None:
            if (e.control.value or "").strip() != ev.name:
                self._save_event(name=e.control.value)

        def save_notes(e: ft.Event[ft.TextField]) -> None:
            if (e.control.value or "") != ev.notes:
                self._save_event(notes=e.control.value)

        def pick_date(_e) -> None:
            def on_change(e: ft.Event[ft.DatePicker]) -> None:
                if e.control.value:
                    self._save_event(
                        date=e.control.value.date() if isinstance(e.control.value, dt.datetime) else e.control.value
                    )

            self.ctx.page.show_dialog(
                ft.DatePicker(
                    value=ev.date,
                    first_date=dt.date(2022, 1, 1),
                    last_date=dt.date.today() + dt.timedelta(days=366),
                    on_change=on_change,
                )
            )

        def pick_own_leader(_e) -> None:
            open_picker(self.ctx, _("Your leader"), lambda leader: self._save_event(leader_id=leader.id))

        rec = record_of(ev)
        standing = [] if ev.event_type in UNRANKED_EVENT_TYPES else [self._standing_fields()]
        return [
            ft.TextField(
                value=ev.name,
                label=_("Event name"),
                text_size=20,
                on_blur=save_name,
                on_submit=save_name,
                data="name",
            ),
            ft.Row(
                [
                    ft.Dropdown(
                        value=ev.event_type,
                        label=_("Type"),
                        expand=True,
                        dense=True,
                        # default paddings here and on the date button clipped "Regional" to "Regiona" at 360 dp
                        content_padding=ft.Padding.only(left=10, right=0),
                        options=[ft.DropdownOption(key=k, text=event_type_label(_, k)) for k in EVENT_TYPES],
                        on_select=lambda e: self._save_event(event_type=e.control.value),
                        data="type",
                    ),
                    ft.OutlinedButton(
                        content=ev.date.isoformat(),
                        icon=ft.Icons.CALENDAR_MONTH,
                        on_click=pick_date,
                        style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12)),
                        data="date",
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            *standing,
            card(
                ft.Row(
                    [
                        ft.Column(
                            [
                                caption(_("Playing")),
                                leader_row(self.ctx.leaders_by_id.get(ev.leader_id), _("Tap to choose your leader")),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Column(
                            [
                                caption(_("Record")),
                                big_number(rec.label() if rec.games else "—", rate_color(rec, self.ctx.scheme), 24),
                                caption(percent(rec.win_rate), visible=rec.games > 0),
                            ],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=pick_own_leader,
                data="own-leader",
            ),
            ft.TextField(
                value=ev.notes,
                label=_("Notes"),
                multiline=True,
                min_lines=1,
                max_lines=5,
                on_blur=save_notes,
                data="notes",
            ),
            ft.FilledButton(
                content=_("Share result"),
                icon=ft.Icons.SHARE,
                height=52,
                width=float("inf"),
                on_click=self._share,
                data="share",
            ),
        ]

    async def _share(self, _e) -> None:
        _ = self.ctx._
        ev, leaders = self.event, self.ctx.leaders_by_id
        await self.ctx.share_file(
            lambda: render.event_card(ev, leaders, _, event_type_label(_, ev.event_type)), title=ev.name
        )

    # ---- rounds ----------------------------------------------------------
    def _segmented(
        self, options: list[tuple[str, str]], selected: str | None, on_pick: Callable[[str | None], None], tag: str
    ) -> ft.SegmentedButton:
        def on_change(e: ft.Event[ft.SegmentedButton]) -> None:
            on_pick(e.control.selected[0] if e.control.selected else None)

        return ft.SegmentedButton(
            segments=[ft.Segment(value=v, label=label) for v, label in options],
            selected=[selected] if selected else [],
            allow_empty_selection=True,
            show_selected_icon=False,
            on_change=on_change,
            data=tag,
        )

    def _standing_fields(self) -> ft.Row:
        """Where you finished and how many entered, typed in place; empty means unknown."""
        _ = self.ctx._
        ev = self.event

        def field(key: str, label: str, value: int | None, prefix: str | None) -> ft.TextField:
            def save(e: ft.Event[ft.TextField]) -> None:
                text = (e.control.value or "").strip()
                number = int(text) if text else None
                if number != getattr(self.event, key):
                    self._save_event(**{key: number})

            return ft.TextField(
                value="" if value is None else str(value),
                label=label,
                prefix=ft.Text(prefix) if prefix else None,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.NumbersOnlyInputFilter(),
                dense=True,
                expand=True,
                on_blur=save,
                on_submit=save,
                data=key,
            )

        return ft.Row(
            [
                field("placement", _("Placement"), ev.placement, "#"),
                field("players", _("Players"), ev.players, None),
            ],
            spacing=10,
            data="standing",
        )

    @staticmethod
    def _tristate(value: bool | None, yes: str, no: str) -> str | None:
        return None if value is None else (yes if value else no)

    def _round_tile(self, r: Round) -> ft.Control:
        _ = self.ctx._
        opponent: Leader | None = self.ctx.leaders_by_id.get(r.opponent_leader_id)

        def on_expand(e: ft.Event[ft.ExpansionTile]) -> None:
            (self.expanded.add if e.control.expanded else self.expanded.discard)(r.id)

        def change_opponent(_e) -> None:
            open_picker(self.ctx, _("Opponent's leader"), lambda ld: self._save_round(r.id, opponent_leader_id=ld.id))

        def save_notes(e: ft.Event[ft.TextField]) -> None:
            if (e.control.value or "") != r.notes:
                self._save_round(r.id, notes=e.control.value)

        def delete(_e) -> None:
            def do_delete() -> None:
                if self._guard(lambda: self.ctx.events.delete_round(r.id)):
                    self.ctx.invalidate_leaders()
                    self.refresh()

            confirm(
                self.ctx.page,
                _("Delete round {n}?").format(n=r.round_no),
                _("This round and its notes will be removed."),
                _("Delete"),
                _("Cancel"),
                do_delete,
            )

        def set_result(value: str | None) -> None:
            if value is not None:
                self.expanded.discard(r.id)
            self._save_round(r.id, result=value)

        def cycler(
            tag: str, field: str, current: object, cycle: Sequence, badge: ft.Control, tooltip: str
        ) -> ft.Container:
            def on_tap(_e) -> None:
                value = _next(current, cycle)
                _log.info("round %d: %s %s -> %s", r.id, field, current, value)
                self._save_round(r.id, **{field: value})

            # an inner tap target wins Flutter's gesture arena, so the tile neither expands nor collapses
            return ft.Container(
                content=badge,
                on_click=on_tap,
                ink=True,
                border_radius=12,
                tooltip=tooltip,
                data=f"{tag}-cycle",
            )

        scheme = self.ctx.scheme
        indicators = ft.Row(
            [
                cycler(
                    "turn",
                    "went_first",
                    r.went_first,
                    TRISTATE_CYCLE,
                    turn_badge(r.went_first, scheme, _("1st"), _("2nd")),
                    _("Turn order — tap to change"),
                ),
                cycler(
                    "die",
                    "won_die_roll",
                    r.won_die_roll,
                    TRISTATE_CYCLE,
                    die_badge(r.won_die_roll, scheme),
                    _("Die roll — tap to change"),
                ),
                cycler(
                    "result",
                    "result",
                    r.result,
                    RESULT_CYCLE,
                    result_badge(r.result, scheme),
                    _("Result — tap to change"),
                ),
            ],
            spacing=2,
            tight=True,
        )

        label = _("TC") if r.top_cut else f"R{r.round_no}"
        edge = ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)
        editors = ft.Column(
            [
                self._segmented([("W", _("Win")), ("L", _("Loss"))], r.result, set_result, "result"),
                self._segmented(
                    [("1", _("Went 1st")), ("2", _("Went 2nd"))],
                    self._tristate(r.went_first, "1", "2"),
                    lambda v: self._save_round(r.id, went_first=None if v is None else v == "1"),
                    "turn",
                ),
                self._segmented(
                    [("won", _("Won die roll")), ("lost", _("Lost die roll"))],
                    self._tristate(r.won_die_roll, "won", "lost"),
                    lambda v: self._save_round(r.id, won_die_roll=None if v is None else v == "won"),
                    "die",
                ),
                ft.Switch(
                    label=_("Top cut"),
                    value=r.top_cut,
                    on_change=lambda e: self._save_round(r.id, top_cut=e.control.value),
                    data="top-cut",
                ),
                ft.TextField(
                    value=r.notes,
                    label=_("Round notes"),
                    multiline=True,
                    min_lines=1,
                    max_lines=4,
                    on_blur=save_notes,
                    data="round-notes",
                ),
                ft.Row(
                    [
                        ft.TextButton(_("Change opponent"), icon=ft.Icons.SWAP_HORIZ, on_click=change_opponent),
                        ft.TextButton(
                            _("Delete round"),
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=delete,
                            style=ft.ButtonStyle(color=ft.Colors.ERROR),
                            data="delete-round",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        return ft.ExpansionTile(
            # one line: R-label, opponent, indicators. Gaps are trimmed so the name gets ~78 dp at 360 dp; at
            # 11 px, with break points after "." '"' "&", the longest unbreakable piece of any leader name
            # ("Doflamingo", 72 dp) fits, so names wrap between words beside the indicators, never mid-word
            title=ft.Row(
                [
                    ft.Text(
                        label,
                        width=ROUND_LABEL_WIDTH,
                        font_family=FONT_HEAVY,
                        color=ft.Colors.TERTIARY if r.top_cut else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    leader_row(
                        opponent,
                        _("Unknown leader"),
                        size=11,
                        show_code=False,
                        spacing=ROUND_GAP,
                        portrait_size=30,
                        break_words=True,
                        short=True,  # "Doflamingo", "Kid": the full names crowd this row
                    ),
                    indicators,
                ],
                spacing=ROUND_GAP,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                data="round-title",
            ),
            show_trailing_icon=False,
            tile_padding=ft.Padding(6, 6, 2, 6),
            expanded=r.id in self.expanded,
            maintain_state=True,
            on_change=on_expand,
            controls=[ft.Container(padding=ft.Padding(12, 0, 12, 12), content=editors)],
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER,
            shape=ft.RoundedRectangleBorder(radius=RADIUS, side=edge),
            collapsed_shape=ft.RoundedRectangleBorder(radius=RADIUS, side=edge),
            data=f"round-{r.round_no}",
        )

    def _add_round(self, _e) -> None:
        _ = self.ctx._
        top_cut = bool(self.event.rounds) and self.event.rounds[-1].top_cut

        def on_pick(leader: Leader) -> None:
            created: list[Round] = []
            if self._guard(lambda: created.append(self.ctx.events.add_round(self.event_id, leader.id, top_cut))):
                self.expanded.add(created[0].id)
                self.ctx.invalidate_leaders()
                self.refresh()

        open_picker(self.ctx, _("Opponent's leader"), on_pick)

    def _controls(self) -> list[ft.Control]:
        _ = self.ctx._
        rounds = [self._round_tile(r) for r in self.event.rounds]
        if not rounds:
            rounds = [
                ft.Text(_("No rounds yet — add one when you sit down to play."), color=ft.Colors.ON_SURFACE_VARIANT)
            ]
        return [
            *self._header(),
            section(_("Rounds")),
            *rounds,
            ft.OutlinedButton(
                content=_("Add round"),
                icon=ft.Icons.ADD,
                height=52,
                style=ft.ButtonStyle(side=ft.BorderSide(1.5, ft.Colors.PRIMARY), color=ft.Colors.PRIMARY),
                on_click=self._add_round,
                data="add-round",
            ),
            ft.Container(height=24),
        ]

    # ---- screen ------------------------------------------------------------
    def delete_event(self) -> None:
        _ = self.ctx._

        def do_delete() -> None:
            if self._guard(lambda: self.ctx.events.delete(self.event_id)):
                self.ctx.invalidate_leaders()
                self.ctx.notify(_("Event deleted"))
                self.ctx.navigate("/events")

        confirm(
            self.ctx.page,
            _("Delete this event?"),
            _("The event and all its rounds will be removed. This can't be undone."),
            _("Delete"),
            _("Cancel"),
            do_delete,
        )

    def build(self) -> ft.Control:
        self.body.controls = self._controls()
        return self.body
