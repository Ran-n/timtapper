#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.780273
Revised: 2026/10/12 16:55:01.467670
"""

import datetime as dt

import flet as ft
import pytest

from ui.event_view import EventScreen
from uitools import by_data, fire, pick_leader, texts, walk


@pytest.fixture
def screen(ctx, sample_event):
    s = EventScreen(ctx, sample_event.id)
    s.build()
    return s


def test_header_shows_event(screen, sample_event, ctx):
    shown = texts(screen.body)
    assert by_data(screen.body, "name").value == "Sunday locals"
    assert by_data(screen.body, "type").value == "locals"
    assert ctx.leaders_by_id[sample_event.leader_id].name in shown
    assert "2-1" in shown and "67%" in shown


def test_pending_rounds_start_expanded(screen):
    assert [by_data(screen.body, f"round-{n}").expanded for n in (1, 2, 3, 4)] == [False, False, False, True]


async def test_rename_saves_on_blur(screen, events, sample_event):
    field = by_data(screen.body, "name")
    field.value = "  Store championship "
    await fire(field.on_blur, field)
    assert events.get(sample_event.id).name == "Store championship"


async def test_blank_name_is_rejected_with_message(screen, events, sample_event, page):
    field = by_data(screen.body, "name")
    field.value = "   "
    await fire(field.on_blur, field)
    assert events.get(sample_event.id).name == "Sunday locals"
    assert isinstance(page.dialogs[-1], ft.SnackBar)


async def test_type_and_notes(screen, events, sample_event):
    dd = by_data(screen.body, "type")
    dd.value = "regional"
    await fire(dd.on_select, dd)
    notes = by_data(screen.body, "notes")
    notes.value = "Draws were all on time"
    await fire(notes.on_blur, notes)
    ev = events.get(sample_event.id)
    assert (ev.event_type, ev.notes) == ("regional", "Draws were all on time")


async def test_date_picker(screen, page, events, sample_event):
    btn = by_data(screen.body, "date")
    await fire(btn.on_click, btn)
    picker = page.dialogs[-1]
    assert isinstance(picker, ft.DatePicker)
    picker.value = dt.datetime(2026, 7, 4)
    await fire(picker.on_change, picker)
    assert events.get(sample_event.id).date == dt.date(2026, 7, 4)


async def test_change_own_leader_through_picker(screen, page, events, sample_event, leader_ids, ctx):
    tile = by_data(screen.body, "own-leader")
    await fire(tile.on_click, tile)
    sheet = page.dialogs[-1]
    await pick_leader(sheet, leader_ids[4], ctx.leaders_by_id[leader_ids[4]].code)
    assert events.get(sample_event.id).leader_id == leader_ids[4]
    assert sheet not in page.dialogs


async def test_round_result_turn_die_and_top_cut(screen, events, sample_event):
    pending = sample_event.rounds[3]
    tile = by_data(screen.body, "round-4")
    for tag, selected in (("result", ["L"]), ("turn", ["2"]), ("die", ["won"])):
        seg = by_data(tile, tag)
        seg.selected = selected
        await fire(seg.on_change, seg)
        tile = by_data(screen.body, "round-4")
    switch = by_data(tile, "top-cut")
    switch.value = True
    await fire(switch.on_change, switch)
    r = next(r for r in events.get(sample_event.id).rounds if r.id == pending.id)
    assert (r.result, r.went_first, r.won_die_roll, r.top_cut) == ("L", False, True, True)
    assert by_data(screen.body, "round-4").expanded is False  # collapses once decided


async def test_clearing_a_segment_stores_none(screen, events, sample_event):
    seg = by_data(by_data(screen.body, "round-1"), "turn")
    seg.selected = []
    await fire(seg.on_change, seg)
    assert events.get(sample_event.id).rounds[0].went_first is None


async def test_round_notes(screen, events, sample_event):
    field = by_data(by_data(screen.body, "round-2"), "round-notes")
    field.value = "misplayed T4"
    await fire(field.on_blur, field)
    assert events.get(sample_event.id).rounds[1].notes == "misplayed T4"


async def test_delete_round_after_confirmation(screen, page, events, sample_event):
    btn = by_data(by_data(screen.body, "round-2"), "delete-round")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog)
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert [r.round_no for r in events.get(sample_event.id).rounds] == [1, 2, 3]


async def test_cancel_delete_round_keeps_it(screen, page, events, sample_event):
    btn = by_data(by_data(screen.body, "round-2"), "delete-round")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    await fire(dialog.actions[0].on_click, dialog.actions[0])
    assert len(events.get(sample_event.id).rounds) == 4


async def test_add_round_via_picker(screen, page, events, sample_event, leader_ids, ctx):
    btn = by_data(screen.body, "add-round")
    await fire(btn.on_click, btn)
    await pick_leader(page.dialogs[-1], leader_ids[5], ctx.leaders_by_id[leader_ids[5]].code)
    rounds = events.get(sample_event.id).rounds
    assert rounds[-1].opponent_leader_id == leader_ids[5] and rounds[-1].round_no == 5
    assert by_data(screen.body, "round-5").expanded is True


async def test_delete_event(screen, page, events, sample_event):
    screen.delete_event()
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert events.list() == []
    assert page.routes[-1] == "/events"


async def test_share_renders_event_card(screen, ctx, monkeypatch):
    calls = []

    async def fake_share(render, *, title, mime_type="image/png"):
        calls.append((render(), title))

    monkeypatch.setattr(ctx, "share_file", fake_share)
    btn = by_data(screen.body, "share")
    await fire(btn.on_click, btn)
    path, title = calls[0]
    assert path.suffix == ".png" and title == "Sunday locals"


def test_empty_event_hint(ctx, events):
    ev = events.create("Fresh", "testing", dt.date(2026, 1, 1))
    s = EventScreen(ctx, ev.id)
    s.build()
    assert any("No rounds yet" in t for t in texts(s.body))


# ---- tap-to-cycle indicators on the collapsed row ------------------------------------
async def tap(screen, round_no: int, tag: str) -> None:
    target = by_data(by_data(screen.body, f"round-{round_no}"), f"{tag}-cycle")
    await fire(target.on_click, target)


def round_of(events, sample_event, round_no: int):
    return next(r for r in events.get(sample_event.id).rounds if r.round_no == round_no)


async def test_result_cycles_through_all_values(screen, events, sample_event):
    seen = []
    for _ in range(3):
        await tap(screen, 4, "result")
        seen.append(round_of(events, sample_event, 4).result)
    assert seen == ["W", "L", None]  # no draw step: the OPTCG has no draws


async def test_turn_cycles(screen, events, sample_event):
    seen = []
    for _ in range(3):
        await tap(screen, 3, "turn")
        seen.append(round_of(events, sample_event, 3).went_first)
    assert seen == [True, False, None]


async def test_die_cycles(screen, events, sample_event):
    seen = []
    for _ in range(3):
        await tap(screen, 3, "die")
        seen.append(round_of(events, sample_event, 3).won_die_roll)
    assert seen == [True, False, None]


async def test_cycling_keeps_expansion_state(screen):
    await tap(screen, 4, "result")  # pending round 4 starts expanded
    await tap(screen, 1, "result")  # decided round 1 starts collapsed
    assert by_data(screen.body, "round-4").expanded
    assert not by_data(screen.body, "round-1").expanded


async def test_cycle_rejected_edit_shows_error(screen, ctx, page, monkeypatch, events, sample_event):
    from events.repository import EventError

    def refuse(*_a, **_k):
        raise EventError("nope")

    monkeypatch.setattr(ctx.events, "update_round", refuse)
    await tap(screen, 4, "result")
    assert isinstance(page.dialogs[-1], ft.SnackBar) and page.dialogs[-1].data == "error"
    assert round_of(events, sample_event, 4).result is None


def test_collapsed_row_shows_turn_and_die(screen):
    first = by_data(screen.body, "round-1")  # went first, won the roll
    second = by_data(screen.body, "round-2")  # went second, lost the roll
    unknown = by_data(screen.body, "round-3")
    assert "1st" in texts(first.title) and "2nd" in texts(second.title) and "—" in texts(unknown.title)
    icons = lambda tile: [c.icon for c in walk(by_data(tile, "die-cycle")) if isinstance(c, ft.Icon)]  # noqa: E731
    face = lambda tile: [c.data for c in walk(by_data(tile, "die-cycle")) if str(c.data).startswith("die-face")]  # noqa: E731
    assert face(first) == ["die-face-6"] and icons(first) == []  # a won roll is a six
    assert face(second) == ["die-face-1"] and icons(second) == []  # a lost one is a one
    assert face(unknown) == [] and icons(unknown) == [ft.Icons.CASINO]


def test_indicators_have_tooltips_and_touch_size(screen):
    tile = by_data(screen.body, "round-1")
    for tag, tip in (("turn", "Turn order"), ("die", "Die roll"), ("result", "Result")):
        target = by_data(tile, f"{tag}-cycle")
        assert target.tooltip.startswith(tip)
        assert target.content.width >= 36 and target.content.height >= 36


async def test_die_face_follows_each_tap(screen):
    def face_of(round_no):
        cycle = by_data(by_data(screen.body, f"round-{round_no}"), "die-cycle")
        found = [c.data for c in walk(cycle) if str(c.data).startswith("die-face")]
        return found[0] if found else None

    assert face_of(3) is None  # unknown roll: the grey die icon
    seen = []
    for _ in range(3):
        await tap(screen, 3, "die")
        seen.append(face_of(3))
    assert seen == ["die-face-6", "die-face-1", None]


# ---- edits that change nothing, and edits the repository refuses -----------------
def refuse(*_a, **_k):
    from events.repository import EventError

    raise EventError("nope")


def spy(monkeypatch, obj, name) -> list:
    calls = []
    real = getattr(obj, name)

    def wrapper(*a, **k):
        calls.append((a, k))
        return real(*a, **k)

    monkeypatch.setattr(obj, name, wrapper)
    return calls


@pytest.mark.parametrize(("tag", "value"), [("name", " Sunday locals "), ("notes", "")])
async def test_unchanged_header_field_saves_nothing(screen, ctx, monkeypatch, tag, value):
    calls = spy(monkeypatch, ctx.events, "update")
    field = by_data(screen.body, tag)
    field.value = value
    await fire(field.on_blur, field)
    assert calls == []


async def test_unchanged_round_notes_save_nothing(screen, ctx, monkeypatch):
    calls = spy(monkeypatch, ctx.events, "update_round")
    field = by_data(by_data(screen.body, "round-2"), "round-notes")
    field.value = None  # the client sends None for an untouched empty field
    await fire(field.on_blur, field)
    assert calls == []


async def test_dismissed_date_picker_keeps_the_date(screen, page, events, sample_event):
    btn = by_data(screen.body, "date")
    await fire(btn.on_click, btn)
    picker = page.dialogs[-1]
    picker.value = None
    await fire(picker.on_change, picker)
    assert events.get(sample_event.id).date == dt.date(2026, 10, 5)


async def test_date_picker_accepts_a_plain_date(screen, page, events, sample_event):
    btn = by_data(screen.body, "date")
    await fire(btn.on_click, btn)
    picker = page.dialogs[-1]
    picker.value = dt.date(2026, 3, 1)
    await fire(picker.on_change, picker)
    assert events.get(sample_event.id).date == dt.date(2026, 3, 1)


async def test_expanding_and_collapsing_is_remembered(screen, sample_event):
    tile = by_data(screen.body, "round-1")
    tile.expanded = True
    await fire(tile.on_change, tile)
    assert sample_event.rounds[0].id in screen.expanded
    tile.expanded = False
    await fire(tile.on_change, tile)
    assert sample_event.rounds[0].id not in screen.expanded
    screen.refresh()
    assert by_data(screen.body, "round-1").expanded is False


async def test_change_opponent_through_picker(screen, page, events, sample_event, leader_ids, ctx):
    tile = by_data(screen.body, "round-1")
    btn = next(c for c in walk(tile) if isinstance(c, ft.TextButton) and c.content == "Change opponent")
    await fire(btn.on_click, btn)
    await pick_leader(page.dialogs[-1], leader_ids[5], ctx.leaders_by_id[leader_ids[5]].code)
    assert round_of(events, sample_event, 1).opponent_leader_id == leader_ids[5]


async def test_clearing_the_result_segment_keeps_the_row_open(screen, events, sample_event):
    seg = by_data(by_data(screen.body, "round-4"), "result")
    seg.selected = []
    await fire(seg.on_change, seg)
    assert round_of(events, sample_event, 4).result is None
    assert by_data(screen.body, "round-4").expanded is True


async def test_refused_round_delete_keeps_the_round_and_says_why(screen, ctx, page, monkeypatch, events, sample_event):
    monkeypatch.setattr(ctx.events, "delete_round", refuse)
    btn = by_data(by_data(screen.body, "round-2"), "delete-round")
    await fire(btn.on_click, btn)
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert len(events.get(sample_event.id).rounds) == 4
    assert isinstance(page.dialogs[-1], ft.SnackBar) and page.dialogs[-1].data == "error"


async def test_refused_add_round_adds_nothing_and_says_why(screen, ctx, page, monkeypatch, events, sample_event):
    monkeypatch.setattr(ctx.events, "add_round", refuse)
    btn = by_data(screen.body, "add-round")
    await fire(btn.on_click, btn)
    await pick_leader(page.dialogs[-1], ctx.leaders_by_id[sample_event.leader_id].id, "")
    assert len(events.get(sample_event.id).rounds) == 4
    assert page.dialogs[-1].data == "error"


async def test_refused_event_delete_stays_on_the_event(screen, ctx, page, monkeypatch, events, sample_event):
    monkeypatch.setattr(ctx.events, "delete", refuse)
    screen.delete_event()
    dialog = page.dialogs[-1]
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert [e.id for e in events.list()] == [sample_event.id]
    assert page.routes == [] and page.dialogs[-1].data == "error"


@pytest.mark.parametrize(
    ("value", "cycle", "expected"),
    [(None, (None, "W", "L"), "W"), ("L", (None, "W", "L"), None), ("?", (None, True, False), None)],
)
def test_next_steps_and_wraps_and_restarts_on_unknown(value, cycle, expected):
    from ui.event_view import _next

    assert _next(value, cycle) == expected


@pytest.mark.regression
def test_round_row_is_one_line_and_the_name_wraps_beside_the_indicators(screen, ctx, sample_event):
    """Beside the indicators, names used to be cut ("Sh…"); then they moved to a second line. Now one line."""
    from ui.event_view import ROUND_GAP

    tile = by_data(screen.body, "round-1")
    assert tile.trailing is None and tile.subtitle is None and tile.show_trailing_icon is False
    label, opponent, indicators = tile.title.controls
    assert {c.data for c in walk(indicators)} >= {"turn-cycle", "die-cycle", "result-cycle"}
    assert opponent.expand and opponent.spacing == ROUND_GAP  # takes the rest of the line
    name = next(c for c in walk(opponent) if isinstance(c, ft.Text))
    assert name.value == ctx.leaders_by_id[sample_event.rounds[0].opponent_leader_id].name
    assert name.max_lines is None and name.overflow != ft.TextOverflow.ELLIPSIS  # wraps, never cut


def test_round_rows_show_names_small_with_break_points(screen):
    tile = by_data(screen.body, "round-1")
    _label, opponent, _indicators = tile.title.controls
    name = next(c for c in walk(opponent) if isinstance(c, ft.Text))
    assert name.size == 11


# ---- placement and players ------------------------------------------------------------
async def type_into(screen, key, text):
    field = by_data(screen.body, key)
    field.value = text
    await fire(field.on_blur, field)


async def test_placement_and_players_are_typed_in_place(screen, events, sample_event, page):
    assert by_data(screen.body, "placement").value == "" and by_data(screen.body, "players").value == ""
    await type_into(screen, "players", "32")
    await type_into(screen, "placement", " 3 ")
    ev = events.get(sample_event.id)
    assert (ev.placement, ev.players) == (3, 32)
    assert by_data(screen.body, "placement").value == "3"
    await type_into(screen, "placement", "")
    assert events.get(sample_event.id).placement is None  # emptied: unknown again
    assert not [d for d in page.dialogs if getattr(d, "data", None) == "error"]


async def test_number_fields_only_take_digits(screen):
    for key in ("placement", "players"):
        field = by_data(screen.body, key)
        assert isinstance(field.input_filter, ft.NumbersOnlyInputFilter)
        assert field.keyboard_type == ft.KeyboardType.NUMBER


async def test_placement_past_the_field_is_refused_with_a_message(screen, events, sample_event, page):
    await type_into(screen, "players", "8")
    await type_into(screen, "placement", "9")
    assert events.get(sample_event.id).placement is None
    assert page.dialogs[-1].data == "error"


async def test_unchanged_standing_saves_nothing(screen, ctx, monkeypatch):
    calls = spy(monkeypatch, ctx.events, "update")
    await type_into(screen, "placement", "")
    assert calls == []


def test_testing_sessions_have_no_standing_fields(ctx, events):
    ev = events.create("Practice", "testing", dt.date(2026, 1, 1))
    s = EventScreen(ctx, ev.id)
    s.build()
    assert "standing" not in [c.data for c in walk(s.body)]


async def test_switching_to_testing_hides_the_standing(screen, events, sample_event):
    dd = by_data(screen.body, "type")
    dd.value = "testing"
    await fire(dd.on_select, dd)
    assert "standing" not in [c.data for c in walk(screen.body)]
