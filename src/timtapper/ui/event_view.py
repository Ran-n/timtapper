#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.952473
Revised: 2026/10/14 13:16:03.927932

Event screen: everything edited in place — name, type, date, standing, set,
own leader and notes in the header; each round as an expandable tile: Swiss,
top cut or a bye, a best of 1 or 3 whose games each note who chose the turn
order, the turn order and the result. Rounds start collapsed — the row's
badges cycle those with a tap — and only open, and stay open, when you open
them. A change that would drop games holding something asks first.
"""

import datetime as dt
from collections.abc import Callable, Sequence

import flet as ft

from catalog.repository import Leader, set_codes
from core.logging import get_logger
from db.models import EVENT_TYPES, RESULTS
from events.domain import BYE, SWISS, TOP_CUT
from events.naming import numbered
from events.repository import Event, EventError, Round
from i18n import UNRANKED_EVENT_TYPES, event_name_template, event_type_label
from stats.compute import percent, record_of
from ui.context import AppContext
from ui.leader_picker import open_picker
from ui.theme import FONT_HEAVY
from ui.widgets import (
    RADIUS,
    big_number,
    bye_portrait,
    caption,
    card,
    chooser_badge,
    confirm,
    die_badge,
    leader_row,
    rate_color,
    result_badge,
    score_badge,
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
NO_SET = ""  # the set dropdown's "Not noted"
ROUND_EDGE = 8  # the result pill's breathing room from the row's right edge


def _next[T](value: T, cycle: Sequence[T]) -> T:
    """The element after `value` in `cycle`, wrapping; an unknown value starts the cycle over."""
    try:
        return cycle[(cycle.index(value) + 1) % len(cycle)]
    except ValueError:
        return cycle[0]


def picked_day(value: dt.date, local: dt.tzinfo | None = None) -> dt.date:
    """The day a date picker shows as picked. Flet sends it back as that day's local midnight in UTC —
    in Spain, 22:00 the evening before — so an aware datetime goes back to local time (the device's
    zone unless `local` is given) before its date is taken."""
    if isinstance(value, dt.datetime):
        return (value.astimezone(local) if value.tzinfo else value).date()
    return value


class EventScreen:
    def __init__(self, ctx: AppContext, event_id: int) -> None:
        self.ctx = ctx
        self.event_id = event_id
        self.event: Event = ctx.events.get(event_id)
        self.expanded: set[int] = set()  # rounds you opened; kept open across edits until you close them
        self.body = ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ---- persistence helpers -------------------------------------------
    def _guard(self, action: Callable[[], object]) -> bool:
        """Run a repository call; report rejected input, or a database that failed to write, instead of crashing
        (the transaction rolled back: nothing of the edit was stored)."""
        _ = self.ctx._
        try:
            action()
        except EventError as exc:
            _log.warning("event %d: rejected edit: %s", self.event_id, exc)
            self.ctx.notify(_("Could not save: {error}").format(error=exc.translated(_)), error=True)
            return False
        except Exception as exc:
            _log.exception("event %d: edit failed", self.event_id)
            self.ctx.notify(_("Could not save the change ({error})").format(error=type(exc).__name__), error=True)
            return False
        return True

    def _save_event(self, **fields) -> None:
        # refreshed either way: after a rejected edit the fields show what's stored again, not the typo
        self._guard(lambda: self.ctx.events.update(self.event_id, **fields))
        self.refresh()

    def _change_type(self, event_type: str) -> None:
        """A name still as suggested ("Local #3") follows the type to that type's next one ("Regional #2")."""
        ev = self.event
        fields: dict = {"event_type": event_type}
        if numbered(event_name_template(self.ctx._, ev.event_type), ev.name) is not None:
            fields["name"] = self.ctx.suggested_name(event_type, exclude_id=ev.id)
        self._save_event(**fields)

    def _save_round(self, round_id: int, **fields) -> None:
        saved = self._guard(lambda: self.ctx.events.update_round(round_id, **fields))
        # a new opponent (or none, as a bye) changes the play counts the leader picker is ordered by
        if saved and ("opponent_leader_id" in fields or fields.get("kind") == BYE):
            self.ctx.invalidate_leaders()
        self.refresh()

    def _cut_round(self, r: Round, keep: int, **fields) -> None:
        """Save a change that leaves the round only its first `keep` games (a bye: none). When a game it drops
        holds a result or a turn order, ask first; until then the switches show what's stored."""
        if not r.noted_beyond(keep):
            self._save_round(r.id, **fields)
            return
        _ = self.ctx._
        self.refresh()
        confirm(
            self.ctx.page,
            _("Remove noted games?"),
            _("Round {n}: the games this change drops hold results or turn orders, which will be removed.").format(
                n=r.round_no
            ),
            _("Remove"),
            _("Cancel"),
            lambda: self._save_round(r.id, **fields),
        )

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
                    self._save_event(**self.ctx.redate(ev, picked_day(e.control.value)))

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
        ranked = ev.event_type not in UNRANKED_EVENT_TYPES
        standing = [self._standing_fields()] if ranked else []
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
                        on_select=lambda e: self._change_type(e.control.value),
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
            self._format_row(ranked),
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
        from share import render  # PIL, only when a card is shared: it held up the web app's first screen

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

    def _format_row(self, ranked: bool) -> ft.Row:
        """The set the event was played in (its format: the newest legal set) and, where there
        are standings, whether you dropped."""
        _ = self.ctx._
        ev = self.event

        def set_set(e) -> None:
            code = e.control.value or None
            if code != ev.set_code:
                self._save_event(set_code=code)

        codes = set_codes(self.ctx.leaders)
        if ev.set_code and ev.set_code not in codes:  # a set the catalogue no longer lists still shows
            codes = [ev.set_code, *codes]
        controls: list[ft.Control] = [
            ft.Dropdown(
                value=ev.set_code or NO_SET,
                label=_("Set"),
                options=[ft.DropdownOption(key=NO_SET, text=_("Not noted"))]
                + [ft.DropdownOption(key=code, text=code) for code in codes],
                on_select=set_set,
                dense=True,
                expand=True,
                data="set",
            )
        ]
        if ranked:
            controls.append(
                ft.Switch(
                    label=_("Dropped"),
                    value=ev.dropped,
                    on_change=lambda e: self._save_event(dropped=e.control.value),
                    data="dropped",
                )
            )
        return ft.Row(controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, data="format")

    @staticmethod
    def _tristate(value: bool | None, yes: str, no: str) -> str | None:
        return None if value is None else (yes if value else no)

    def _save_game(self, round_id: int, game_no: int, **fields) -> None:
        self._guard(lambda: self.ctx.events.update_game(round_id, game_no, **fields))
        self.refresh()

    def _cycler(
        self, r: Round, tag: str, current: object, cycle: Sequence, badge: ft.Control, tooltip: str, save
    ) -> ft.Container:
        """A badge that steps its value through `cycle` on each tap (`save(value)` stores it)."""

        def on_tap(_e) -> None:
            value = _next(current, cycle)
            _log.info("round %d: %s %s -> %s", r.id, tag, current, value)
            save(value)

        # an inner tap target wins Flutter's gesture arena, so the tile neither expands nor collapses
        return ft.Container(
            content=badge, on_click=on_tap, ink=True, border_radius=12, tooltip=tooltip, data=f"{tag}-cycle"
        )

    def _game_badges(self, r: Round, game_no: int, *, tag: str = "") -> list[ft.Control]:
        """Game `game_no`, read left to right: who chose the turn order (the die in Swiss
        game 1), the turn order, the result. Each badge cycles its value on tap."""
        _ = self.ctx._
        scheme = self.ctx.scheme
        game = r.game(game_no)

        def save(field: str):
            return lambda value: self._save_game(r.id, game_no, **{field: value})

        if r.die_decided(game_no):
            chooser = self._cycler(
                r,
                f"{tag}die",
                game.chose_turn,
                TRISTATE_CYCLE,
                die_badge(game.chose_turn, scheme),
                _("Die roll — tap to change"),
                save("chose_turn"),
            )
        else:
            chooser = self._cycler(
                r,
                f"{tag}chooser",
                game.chose_turn,
                TRISTATE_CYCLE,
                chooser_badge(r.chose_turn(game_no), scheme, _("You"), _("Opp")),
                _("Who chose the turn order: the previous game's loser — tap to change")
                if r.chose_by_rule(game_no)
                else _("Who chose the turn order — tap to change"),
                save("chose_turn"),
            )
        return [
            chooser,
            self._cycler(
                r,
                f"{tag}turn",
                game.went_first,
                TRISTATE_CYCLE,
                turn_badge(game.went_first, scheme, _("1st"), _("2nd")),
                _("Turn order — tap to change"),
                save("went_first"),
            ),
            self._cycler(
                r,
                f"{tag}result",
                game.result,
                RESULT_CYCLE,
                result_badge(game.result, scheme),
                _("Result — tap to change"),
                save("result"),
            ),
        ]

    def _indicators(self, r: Round) -> ft.Control:
        """The top line's right end. A best of 1: its game's badges. A best of 3: the score (its games are on the
        lines below). A bye: its automatic win."""
        if r.bye:
            return ft.Container(result_badge("W", self.ctx.scheme), data="bye-result")
        if r.best_of == 1:
            return ft.Row(self._game_badges(r, 1), spacing=2, tight=True)
        return ft.Container(score_badge(r.wins, r.losses, r.result, self.ctx.scheme), data="score")

    def _game_lines(self, r: Round) -> list[ft.Control]:
        """A best of 3's games, always on the row under the opponent, one line each: "Game 1" and its chooser,
        turn and result badges, lined up with a best of 1's."""
        _ = self.ctx._
        return [
            ft.Row(
                [
                    ft.Container(width=ROUND_LABEL_WIDTH),  # under the round number
                    ft.Text(
                        _("Game {n}").format(n=n), size=12, font_family=FONT_HEAVY, color=ft.Colors.ON_SURFACE_VARIANT
                    ),
                    ft.Container(expand=True),
                    *self._game_badges(r, n, tag=f"g{n}-"),
                ],
                spacing=ROUND_GAP,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                data=f"game-{n}",
            )
            for n in range(1, r.best_of + 1)
        ]

    def _single_game_editors(self, r: Round) -> list[ft.Control]:
        """A best of 1's game as segmented buttons: the die (Swiss) or who chose (top cut), turn order, result."""
        _ = self.ctx._
        game = r.game(1)
        chooser = (
            [("won", _("Won die roll")), ("lost", _("Lost die roll"))]
            if r.die_decided(1)
            else [("won", _("You chose turn")), ("lost", _("They chose turn"))]
        )
        return [
            self._segmented(
                chooser,
                self._tristate(game.chose_turn, "won", "lost"),
                lambda v: self._save_game(r.id, 1, chose_turn=None if v is None else v == "won"),
                "die" if r.die_decided(1) else "chooser",
            ),
            self._segmented(
                [("1", _("Went 1st")), ("2", _("Went 2nd"))],
                self._tristate(game.went_first, "1", "2"),
                lambda v: self._save_game(r.id, 1, went_first=None if v is None else v == "1"),
                "turn",
            ),
            self._segmented(
                [("W", _("Win")), ("L", _("Loss"))], game.result, lambda v: self._save_game(r.id, 1, result=v), "result"
            ),
        ]

    def _round_label(self, r: Round) -> ft.Control:
        """The round number, always; a top-cut round carries a small "TC" under it."""
        _ = self.ctx._
        number = ft.Text(
            f"R{r.round_no}",
            font_family=FONT_HEAVY,
            color=ft.Colors.TERTIARY if r.top_cut else ft.Colors.ON_SURFACE_VARIANT,
        )
        if not r.top_cut:
            return ft.Container(number, width=ROUND_LABEL_WIDTH)
        stage = ft.Text(_("TC"), size=10, font_family=FONT_HEAVY, color=ft.Colors.TERTIARY)
        return ft.Column([number, stage], spacing=0, tight=True, width=ROUND_LABEL_WIDTH, data="top-cut-tag")

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

        # cleared or unchanged, a switch is redrawn showing what's stored, not left on a choice nothing saved
        def set_best_of(value: str | None) -> None:
            if value is None or int(value) == r.best_of:
                self.refresh()
                return
            self._cut_round(r, int(value), best_of=int(value))

        def set_kind(kind: str | None) -> None:
            if kind is None or kind == r.kind:
                self.refresh()
                return
            if r.bye:  # a bye has no opponent: pick the one this round is now played against
                self.refresh()  # still a bye until one is picked (the picker may be dismissed)
                open_picker(
                    self.ctx,
                    _("Opponent's leader"),
                    lambda ld: self._save_round(r.id, kind=kind, opponent_leader_id=ld.id),
                )
                return
            # a bye keeps no games; Swiss <-> top cut only changes the best-of when no noted game goes
            self._cut_round(r, 0 if kind == BYE else r.best_of, kind=kind)

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

        # a best of 1 edits its game here; a best of 3's games are on the row itself
        games = self._single_game_editors(r) if r.best_of == 1 and not r.bye else []
        editors = ft.Column(
            [
                self._segmented(
                    [(SWISS, _("Swiss")), (TOP_CUT, _("Top cut")), (BYE, _("Bye"))], r.kind, set_kind, "kind"
                ),
                *(
                    []
                    if r.bye
                    else [
                        self._segmented(
                            [("1", _("Best of 1")), ("3", _("Best of 3"))], str(r.best_of), set_best_of, "best-of"
                        )
                    ]
                ),
                *games,
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
                        *(
                            []
                            if r.bye
                            else [
                                ft.TextButton(_("Change opponent"), icon=ft.Icons.SWAP_HORIZ, on_click=change_opponent)
                            ]
                        ),
                        ft.TextButton(
                            _("Delete round"),
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=delete,
                            style=ft.ButtonStyle(color=ft.Colors.ERROR),
                            data="delete-round",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    # at 360 dp "Change opponent" and "Delete round" don't fit side by side: the second drops a line
                    wrap=True,
                    run_spacing=0,
                    data="round-actions",
                ),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        if r.bye:
            # laid out like an opponent: the stripe and portrait slots, here in the top-cut gold with a coffee break
            scheme = self.ctx.scheme
            who: ft.Control = ft.Row(
                [
                    ft.Container(width=8, height=30, border_radius=4, bgcolor=scheme.tertiary),
                    bye_portrait(scheme, 30),
                    ft.Column(
                        [
                            ft.Text(_("Bye"), size=13, font_family=FONT_HEAVY),
                            ft.Text(_("Automatic win"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=0,
                        tight=True,
                        expand=True,
                    ),
                ],
                spacing=ROUND_GAP,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        else:
            # at 11 px, with break points after "." '"' "&", the longest unbreakable piece of any leader name
            # ("Doflamingo", 72 dp) fits, so names wrap between words beside the badges, never mid-word
            who = leader_row(
                opponent,
                _("Unknown leader"),
                size=11,
                show_code=False,
                spacing=ROUND_GAP,
                portrait_size=30,
                break_words=True,
                short=True,  # "Doflamingo", "Kid": the full names crowd this row
            )
        top_line = ft.Row(
            [self._round_label(r), who, self._indicators(r)],
            spacing=ROUND_GAP,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            data="round-title",
        )
        played_bo3 = r.best_of == 3 and not r.bye
        return ft.ExpansionTile(
            # R-number, opponent, then the badges; a best of 3 adds a line per game under it (its score up top)
            title=ft.Column([top_line, *self._game_lines(r)], spacing=6, data="round-head") if played_bo3 else top_line,
            # the round's notes stay on the row, wrapped rather than cut
            subtitle=ft.Text(r.notes, size=11, color=ft.Colors.ON_SURFACE_VARIANT, data="row-notes")
            if r.notes
            else None,
            show_trailing_icon=False,
            tile_padding=ft.Padding(6, 6, ROUND_EDGE, 6),
            expanded=r.id in self.expanded,
            maintain_state=True,
            on_change=on_expand,
            controls=[ft.Container(padding=ft.Padding(12, 0, 12, 12), content=editors)],
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            collapsed_bgcolor=ft.Colors.SURFACE_CONTAINER,
            shape=ft.RoundedRectangleBorder(radius=RADIUS, side=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            collapsed_shape=ft.RoundedRectangleBorder(radius=RADIUS, side=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            data=f"round-{r.round_no}",
        )

    def _next_kind(self) -> str:
        """A new round continues the last one's stage: top cut after top cut, else Swiss (a bye is a Swiss round)."""
        last = self.event.rounds[-1] if self.event.rounds else None
        return TOP_CUT if last is not None and last.top_cut else SWISS

    def _add_round(self, _e) -> None:
        _ = self.ctx._
        kind = self._next_kind()

        def on_pick(leader: Leader) -> None:
            if self._guard(lambda: self.ctx.events.add_round(self.event_id, leader.id, kind)):
                self.ctx.invalidate_leaders()
                self.refresh()

        open_picker(self.ctx, _("Opponent's leader"), on_pick)

    def _add_bye(self, _e) -> None:
        self._guard(lambda: self.ctx.events.add_round(self.event_id, None, BYE))
        self.refresh()

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
            # a bye needs no opponent, so no picker: one tap logs it
            ft.Row(
                [
                    ft.TextButton(
                        _("Add a bye"), icon=ft.Icons.FAST_FORWARD_OUTLINED, on_click=self._add_bye, data="add-bye"
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
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
