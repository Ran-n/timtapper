#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.709234
Revised: 2026/10/12 02:17:26.178782
"""

import datetime as dt

import flet as ft

from ui import events_view
from uitools import by_data, fire, texts, walk


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
    assert "2-1" in shown and "67%" in shown
    assert not any("· 67%" in t for t in shown)  # record and rate are separate badges
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


def test_event_type_badge_translated(ctx, sample_event):
    from i18n import set_lang

    set_lang(ctx.page, "gl")
    body, _fab = events_view.build(ctx)
    assert texts(by_data(body[0], "event-type")) == ["Locais"]


def test_tile_shows_leader_portrait_or_placeholder(ctx, sample_event, events):
    events.create("No deck yet", "testing", dt.date(2020, 1, 1))
    body, _fab = events_view.build(ctx)
    with_leader, without = (row.content.controls[1] for row in body)
    code = ctx.leaders_by_id[sample_event.leader_id].code
    assert with_leader.data == "portrait-frame"
    image = with_leader.content.content
    assert isinstance(image, ft.Image) and image.src == f"leaders/{code}.webp"
    assert isinstance(without.content, ft.Icon) and without.data != "portrait-frame"


def test_event_name_has_its_own_row(ctx, sample_event):
    body, _fab = events_view.build(ctx)
    texts_column = body[0].content.controls[2]
    name, leader_row = texts_column.controls[1], texts_column.controls[2]
    assert name.data == "event-name" and name.value == "Sunday locals"
    assert texts(by_data(leader_row, "record-badge")) == ["2-1"]  # the record badges sit beside the leader name
    assert texts(by_data(leader_row, "rate-badge")) == ["67%"]


def test_event_type_badge_is_first(ctx, sample_event):
    body, _fab = events_view.build(ctx)
    texts_column = body[0].content.controls[2]
    assert texts(by_data(texts_column.controls[0], "event-type")) == ["Locals"]
    # the type moved out of the date line
    assert texts(texts_column.controls[3]) == [f"{sample_event.date.isoformat()} · 4 rounds"]


def test_event_without_games_shows_a_dash(ctx, events):
    events.create("Fresh", "online", dt.date(2026, 1, 1))
    body, _fab = events_view.build(ctx)
    assert texts(by_data(body[0], "record-badge")) == ["—"]
    assert "rate-badge" not in [c.data for c in walk(body[0])]


def test_tile_type_badge_shows_every_type(ctx, events):
    from db.models import EVENT_TYPES
    from ui.widgets import EVENT_TYPE_ICONS

    for i, key in enumerate(EVENT_TYPES):
        events.create(f"E{i}", key, dt.date(2026, 1, 1 + i))
    body, _fab = events_view.build(ctx)
    shown = {texts(by_data(tile, "event-type"))[0]: tile for tile in body}
    assert set(shown) == {"Testing", "Locals", "Regional", "National", "Online", "Other"}
    for tile in body:
        badge_icons = [c.icon for c in walk(by_data(tile, "event-type")) if isinstance(c, ft.Icon)]
        assert len(badge_icons) == 1 and badge_icons[0] in EVENT_TYPE_ICONS.values()


def test_unknown_event_type_reads_other(ctx, sample_event):
    import dataclasses

    tile = events_view.event_tile(ctx, dataclasses.replace(sample_event, event_type="worlds"))
    badge = by_data(tile, "event-type")
    assert texts(badge) == ["Other"]
    assert [c.icon for c in walk(badge) if isinstance(c, ft.Icon)] == [ft.Icons.EVENT_OUTLINED]


def test_color_bar_spans_the_tile(ctx, sample_event):
    body, _fab = events_view.build(ctx)
    bar = body[0].content.controls[0]
    assert bar.height == events_view.TILE_BAR_HEIGHT


def test_tile_portrait_frame_uses_leader_colours(ctx, sample_event):
    from ui.theme import CARD_COLORS

    leader = ctx.leaders_by_id[sample_event.leader_id]
    frame = by_data(events_view.build(ctx)[0][0], "portrait-frame")
    expected = [CARD_COLORS[c] for c in leader.colors]
    if len(expected) == 1:
        assert frame.bgcolor == expected[0]
    else:
        assert frame.gradient.colors[::2] == expected
