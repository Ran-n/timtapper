#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.780273
Revised: 2026/10/11 16:57:39.861520
"""

import datetime as dt

import flet as ft
import pytest

from ui.event_view import EventScreen
from uitools import by_data, fire, pick_leader, texts


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
