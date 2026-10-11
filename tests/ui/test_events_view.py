#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.709234
Revised: 2026/10/11 17:13:51.857220
"""

import datetime as dt

import flet as ft

from ui import events_view
from uitools import by_data, fire, texts


def test_empty_state(ctx):
    body, fab = events_view.build(ctx)
    assert "No events yet" in texts(body[0])
    assert by_data(body[0], "logo").src == "logo_mark.png"
    assert isinstance(fab, ft.FloatingActionButton)


def test_lists_events_with_record(ctx, sample_event, events):
    events.create("Older", "testing", dt.date(2020, 1, 1))
    body, _fab = events_view.build(ctx)
    assert [c.data for c in body] == [sample_event.id, sample_event.id + 1]
    shown = texts(body[0])
    assert "Sunday locals" in shown
    assert "2-1 · 67%" in shown
    assert any("4 rounds" in t for t in shown)
    assert any("0 rounds" in t for t in texts(body[1]))


async def test_tile_click_navigates(ctx, sample_event, page):
    body, _fab = events_view.build(ctx)
    await fire(body[0].on_click, body[0])
    assert page.routes == [f"/event/{sample_event.id}"]


async def test_new_event_reuses_last_leader(ctx, sample_event, page, events):
    _body, fab = events_view.build(ctx)
    await fire(fab.on_click, fab)
    created = events.list()[0]
    assert created.id != sample_event.id
    assert created.leader_id == sample_event.leader_id
    assert created.date == dt.date.today()
    assert page.routes == [f"/event/{created.id}"]


def test_translated(ctx):
    from i18n import set_lang

    set_lang(ctx.page, "gl")
    body, fab = events_view.build(ctx)
    assert "Aínda non hai eventos" in texts(body[0])
    assert fab.content.value == "Novo evento"


def test_tile_shows_leader_portrait_or_placeholder(ctx, sample_event, events):
    events.create("No deck yet", "testing", dt.date(2020, 1, 1))
    body, _fab = events_view.build(ctx)
    with_leader, without = (row.content.controls[1] for row in body)
    code = ctx.leaders_by_id[sample_event.leader_id].code
    assert isinstance(with_leader.content, ft.Image) and with_leader.content.src == f"leaders/{code}.webp"
    assert isinstance(without.content, ft.Icon)
