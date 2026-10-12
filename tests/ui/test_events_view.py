#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.709234
Revised: 2026/10/12 16:55:01.605295
"""

import datetime as dt

import flet as ft
import pytest

from ui import events_view
from uitools import by_data, fire, texts, walk


def test_empty_state(ctx):
    body, fab = events_view.build(ctx)
    assert "No events yet" in texts(body[0])
    assert by_data(body[0], "logo").src == "logo_mark.png"
    assert isinstance(fab, ft.FloatingActionButton)


def test_lists_events_with_record(ctx, sample_event, events):
    events.create("Older", "testing", dt.date(2020, 1, 1))
    body = tiles(events_view.build(ctx)[0])
    assert [c.data for c in body] == [sample_event.id, sample_event.id + 1]
    shown = texts(body[0])
    assert "Sunday locals" in shown
    assert "2-1" in shown and "67%" in shown
    assert not any("· 67%" in t for t in shown)  # record and rate are separate badges
    assert any("4 rounds" in t for t in shown)
    assert any("0 rounds" in t for t in texts(body[1]))


async def test_tile_click_navigates(ctx, sample_event, page):
    body = tiles(events_view.build(ctx)[0])
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
    body = tiles(events_view.build(ctx)[0])
    assert texts(by_data(body[0], "event-type")) == ["Locais"]


def test_tile_shows_leader_portrait_or_placeholder(ctx, sample_event, events):
    events.create("No deck yet", "testing", dt.date(2020, 1, 1))
    body = tiles(events_view.build(ctx)[0])
    with_leader, without = (tile_row(t).controls[0] for t in body)
    code = ctx.leaders_by_id[sample_event.leader_id].code
    assert with_leader.data == "portrait-frame"
    image = with_leader.content.content
    assert isinstance(image, ft.Image) and image.src == f"leaders/{code}.webp"
    assert isinstance(without.content, ft.Icon) and without.data != "portrait-frame"


def test_event_name_and_leader_each_have_their_own_line(ctx, sample_event):
    body = tiles(events_view.build(ctx)[0])
    name, leader = tile_row(body[0]).controls[1].controls[:2]
    top = by_data(body[0], "tile-top")
    assert name.data == "event-name" and name.value == "Sunday locals"
    assert leader.data == "tile-leader" and leader.value == ctx.leaders_by_id[sample_event.leader_id].name
    assert texts(by_data(top, "record-badge")) == ["2-1"]  # the record sits on the type pill's line
    assert texts(by_data(top, "rate-badge")) == ["67%"]


@pytest.mark.regression
def test_tile_texts_wrap_instead_of_being_cut(ctx, sample_event):
    """Event names, leaders ("Mon…") and the date line used to end in "…" at 360 dp."""
    tile = tiles(events_view.build(ctx)[0])[0]
    for c in walk(tile):
        if isinstance(c, ft.Text):
            assert c.overflow != ft.TextOverflow.ELLIPSIS and c.max_lines is None, c.value
    top = by_data(tile, "tile-top")
    assert top.wrap and top.alignment == ft.MainAxisAlignment.SPACE_BETWEEN  # the record drops under the pill if needed


def test_type_and_record_lead_the_tile_across_its_full_width(ctx, sample_event):
    tile = tiles(events_view.build(ctx)[0])[0]
    top, below = tile.content.controls[0].content.controls  # top line, then portrait + texts
    assert top.data == "tile-top" and top.alignment == ft.MainAxisAlignment.SPACE_BETWEEN
    pill, record = top.controls
    assert texts(by_data(pill, "event-type")) == ["Locals"] and by_data(record, "record-badge")
    assert below.controls[0].data == "portrait-frame"  # the pill starts over the portrait, not beside it
    assert texts(below.controls[1].controls[2]) == [f"{sample_event.date.isoformat()} · 4 rounds"]  # no standing


def test_event_without_games_shows_a_dash(ctx, events):
    events.create("Fresh", "online", dt.date(2026, 1, 1))
    body = tiles(events_view.build(ctx)[0])
    assert texts(by_data(body[0], "record-badge")) == ["—"]
    assert "rate-badge" not in [c.data for c in walk(body[0])]


def test_tile_type_badge_shows_every_type(ctx, events):
    from db.models import EVENT_TYPES
    from ui.widgets import EVENT_TYPE_ICONS

    for i, key in enumerate(EVENT_TYPES):
        events.create(f"E{i}", key, dt.date(2026, 1, 1 + i))
    body = tiles(events_view.build(ctx)[0])
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


@pytest.mark.regression
def test_color_bar_spans_the_tile_however_tall_it_gets(ctx, sample_event):
    """The bar must follow the tile once its texts wrap; a stretching row blanked the whole list instead."""
    stack = tiles(events_view.build(ctx)[0])[0].content
    content, bar = stack.controls
    assert isinstance(stack, ft.Stack)
    assert (bar.left, bar.top, bar.bottom, bar.height, bar.width) == (0, 0, 0, None, events_view.TILE_BAR_WIDTH)
    assert content.padding.left == events_view.TILE_BAR_WIDTH + 12  # the texts never run under the bar
    assert tile_row(tiles(events_view.build(ctx)[0])[0]).vertical_alignment == ft.CrossAxisAlignment.CENTER


def tiles(body) -> list:
    """The event cards under the search field and filters."""
    results = next(c for c in body if c.data == "event-results")
    return [c for c in results.controls if isinstance(c.data, int)]


def tile_row(tile) -> ft.Row:
    """The portrait + texts row inside a tile (under its colour-bar stack and the full-width top line)."""
    return tile.content.controls[0].content.controls[1]


def test_tile_portrait_frame_uses_leader_colours(ctx, sample_event):
    from ui.theme import CARD_COLORS

    leader = ctx.leaders_by_id[sample_event.leader_id]
    frame = by_data(tiles(events_view.build(ctx)[0])[0], "portrait-frame")
    expected = [CARD_COLORS[c] for c in leader.colors]
    if len(expected) == 1:
        assert frame.bgcolor == expected[0]
    else:
        assert frame.gradient.colors[::2] == expected


# ---- search and filters ----------------------------------------------------------------
@pytest.fixture
def three_events(ctx, events, leader_ids):
    events.create("Sunday locals", "locals", dt.date(2026, 10, 5), leader_ids[0])
    events.create("Online league", "online", dt.date(2026, 10, 6), leader_ids[0])
    events.create("Regional day 1", "regional", dt.date(2026, 10, 7), leader_ids[1])
    return events


def names(body) -> list[str]:
    return [by_data(t, "event-name").value for t in tiles(body)]


async def type_query(body, value):
    field = by_data(body[0], "event-search")
    field.value = value
    await fire(field.on_change, field)


async def test_search_narrows_the_list_case_insensitively_and_counts(ctx, three_events):
    body, _fab = events_view.build(ctx)
    assert len(names(body)) == 3 and "event-count" not in [c.data for c in walk(body[2])]  # no filter: no count
    await type_query(body, "LOCALS")
    assert names(body) == ["Sunday locals"]
    assert by_data(body[2], "event-count").value == "1 of 3 events"


async def test_search_field_survives_refreshes(ctx, three_events):
    """Rebuilding the field on every keystroke would drop the keyboard focus mid-word."""
    body, _fab = events_view.build(ctx)
    field = by_data(body[0], "event-search")
    await type_query(body, "o")
    assert by_data(body[0], "event-search") is field and body[0].controls[0] is field


async def test_filter_button_opens_and_closes_the_dropdowns_in_place(ctx, three_events, page):
    body, _fab = events_view.build(ctx)
    toggle = by_data(body[0], "event-filter-toggle")
    assert body[1].controls == [] and toggle.icon == ft.Icons.FILTER_LIST
    assert body[0].controls == [by_data(body[0], "event-search"), toggle]  # beside the field: always visible
    await fire(toggle.on_click, toggle)
    assert by_data(body[1], "filter-leader") and by_data(body[1], "filter-type")
    assert toggle.icon == ft.Icons.FILTER_LIST_OFF and page.dialogs == []  # inline, no dialog
    await fire(toggle.on_click, toggle)
    assert body[1].controls == []


async def test_type_and_leader_dropdowns_filter_and_stay_open(ctx, three_events, leader_ids):
    body, _fab = events_view.build(ctx)
    toggle = by_data(body[0], "event-filter-toggle")
    await fire(toggle.on_click, toggle)
    dd = by_data(body[1], "filter-type")
    dd.value = "online"
    await fire(dd.on_select, dd)
    assert names(body) == ["Online league"]
    assert toggle.disabled and toggle.icon_color == ft.Colors.PRIMARY  # can't hide a filter that's on
    leader = by_data(body[1], "filter-leader")
    assert {o.key for o in leader.options} == {"all", str(leader_ids[0]), str(leader_ids[1])}
    leader.value = str(leader_ids[1])
    await fire(leader.on_select, leader)
    assert names(body) == []  # online AND leader 2: none
    type_dd = by_data(body[1], "filter-type")
    type_dd.value = "all"
    await fire(type_dd.on_select, type_dd)
    assert names(body) == ["Regional day 1"]


async def test_no_match_offers_to_clear_everything(ctx, three_events):
    body, _fab = events_view.build(ctx)
    await type_query(body, "worlds")
    assert names(body) == [] and "No events match" in texts(body[2])
    clear = by_data(body[2], "clear-filters")
    await fire(clear.on_click, clear)
    assert len(names(body)) == 3
    assert by_data(body[0], "event-search").value == "" and ctx.event_filters == events_view.Filters()


async def test_filters_are_kept_when_coming_back_to_the_list(ctx, three_events):
    body, _fab = events_view.build(ctx)
    await type_query(body, "regional")
    again, _fab = events_view.build(ctx)  # e.g. after opening an event and going back
    assert names(again) == ["Regional day 1"] and by_data(again[0], "event-search").value == "regional"


@pytest.mark.parametrize("lang", ["es", "gl"])
async def test_filter_texts_are_translated(ctx, three_events, lang):
    from i18n import set_lang

    set_lang(ctx.page, lang)
    body, _fab = events_view.build(ctx)
    assert by_data(body[0], "event-search").hint_text == ctx._("Search events") != "Search events"
    await type_query(body, "zzz")
    assert ctx._("No events match") in texts(body[2])


def test_tile_shows_the_standing_beside_the_leader_in_one_piece(ctx, events, sample_event):
    events.update(sample_event.id, placement=3, players=32)
    tile = tiles(events_view.build(ctx)[0])[0]
    standing = by_data(tile, "tile-standing")
    assert texts(standing) == ["#3 of 32"]  # non-breaking: never split over two lines
    date_line = tile_row(tile).controls[1].controls[2]
    assert date_line.wrap and date_line.controls[1] is standing  # after the date, dropping whole to a new line
    assert texts(by_data(tile, "tile-date")) == [f"{sample_event.date.isoformat()} · 4 rounds"]


def test_tile_without_a_standing_shows_none(ctx, sample_event):
    tile = tiles(events_view.build(ctx)[0])[0]
    assert "tile-standing" not in [c.data for c in walk(tile)]
