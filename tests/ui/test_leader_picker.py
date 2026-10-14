#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 23:25:31.706887
Revised: 2026/10/14 01:17:20.602835

Leader picker: text search, color dots (every selected color) and the set dropdown combine.
"""

import flet as ft
import pytest

from ui.leader_picker import ALL_SETS, build_picker, open_picker
from uitools import by_data, fire, texts


def shown_ids(sheet) -> list:
    return [c.data for c in by_data(sheet, "leader-results").controls if isinstance(c.data, int)]


def shown(ctx, sheet) -> list:
    return [ctx.leaders_by_id[i] for i in shown_ids(sheet)]


async def toggle(sheet, color: str) -> None:
    dot = by_data(sheet, f"color-{color}")
    await fire(dot.on_click, dot)


def check_of(sheet, color: str):
    """The check icon inside a colour dot, or None when it isn't selected."""
    return by_data(sheet, f"color-{color}").content.content


async def choose_set(sheet, code: str) -> None:
    dd = by_data(sheet, "set-filter")
    dd.value = code
    await fire(dd.on_select, dd)


async def type_query(sheet, query: str) -> None:
    field = by_data(sheet, "leader-search")
    field.value = query
    await fire(field.on_change, field)


def make(ctx, picked=None):
    return build_picker(ctx, "Pick", (picked if picked is not None else []).append)


@pytest.mark.regression
def test_search_hint_is_short_enough_for_a_narrow_phone(ctx):
    """ "Search name, code or color" was cut off at 360 dp on a phone ("...code or col…"), in Spanish on any screen."""
    assert by_data(make(ctx), "leader-search").hint_text == "Name, code or color"


def test_shows_six_color_dots_on_one_line(ctx):
    sheet = make(ctx)
    row = by_data(sheet, "color-filters")
    names = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
    assert [c.data for c in row.controls] == [f"color-{c}" for c in names]
    assert row.wrap is False
    assert not texts(row)  # dots only, no labels
    assert [c.tooltip for c in row.controls] == list(names)
    assert all(c.width == c.height == 44 and c.content.width == 28 for c in row.controls)
    assert all(check_of(sheet, c) is None for c in names)
    assert 6 * 44 + 5 * row.spacing <= 360 - 32  # fits the minimum window inside the sheet's padding
    options = by_data(sheet, "set-filter").options
    assert options[0].key == ALL_SETS and options[0].text == "All sets"
    assert options[1].key.startswith("OP")


async def test_color_dot_narrows_list(ctx):
    sheet = make(ctx)
    await toggle(sheet, "Purple")
    found = shown(ctx, sheet)
    assert found and all("Purple" in ld.colors for ld in found)


async def test_two_colors_need_both(ctx):
    sheet = make(ctx)
    await toggle(sheet, "Red")
    await toggle(sheet, "Green")
    found = shown(ctx, sheet)
    assert found and all({"Red", "Green"} <= set(ld.colors) for ld in found)


async def test_selected_dot_shows_ring_and_check(ctx):
    sheet = make(ctx)
    red = by_data(sheet, "color-Red").content
    assert red.border.top.width == 1 and check_of(sheet, "Red") is None
    await toggle(sheet, "Red")
    assert red.border.top.width == 3 and red.border.top.color == ft.Colors.ON_SURFACE
    assert (check_of(sheet, "Red").icon, check_of(sheet, "Red").color) == (ft.Icons.CHECK, ft.Colors.WHITE)
    await toggle(sheet, "Yellow")
    assert check_of(sheet, "Yellow").color == ft.Colors.BLACK  # white on yellow is unreadable
    await toggle(sheet, "Red")
    assert red.border.top.width == 1 and check_of(sheet, "Red") is None


def test_dot_tooltips_translated(ctx):
    from i18n import color_label, set_lang, translator

    set_lang(ctx.page, "gl")
    sheet = make(ctx)
    assert by_data(sheet, "color-Red").tooltip == color_label(translator("gl"), "Red") != "Red"


async def test_unselecting_dot_restores_list(ctx):
    sheet = make(ctx)
    before = shown_ids(sheet)
    await toggle(sheet, "Black")
    assert shown_ids(sheet) != before
    await toggle(sheet, "Black")
    assert shown_ids(sheet) == before


async def test_set_dropdown_narrows_list(ctx):
    sheet = make(ctx)
    await choose_set(sheet, "OP09")
    found = shown(ctx, sheet)
    assert found and {ld.set_code for ld in found} == {"OP09"}
    await choose_set(sheet, ALL_SETS)
    assert len(shown_ids(sheet)) > len(found)


async def test_filters_and_text_combine(ctx):
    sheet = make(ctx)
    await type_query(sheet, "luffy")
    await toggle(sheet, "Red")
    found = shown(ctx, sheet)
    assert found and all("luffy" in ld.name.lower() and "Red" in ld.colors for ld in found)
    some_set = found[0].set_code
    await choose_set(sheet, some_set)
    assert all(ld.set_code == some_set for ld in shown(ctx, sheet))


async def test_no_match_shows_message(ctx):
    sheet = make(ctx)
    await toggle(sheet, "Red")
    await toggle(sheet, "Green")
    await toggle(sheet, "Blue")
    await toggle(sheet, "Purple")
    await toggle(sheet, "Black")
    await toggle(sheet, "Yellow")
    assert shown_ids(sheet) == []
    assert "No leader matches" in texts(by_data(sheet, "leader-results"))


async def test_filters_reset_on_reopen(ctx, page):
    open_picker(ctx, "Pick", lambda _l: None)
    first = page.dialogs[-1]
    unfiltered = shown_ids(first)
    await toggle(first, "Yellow")
    await choose_set(first, "OP01")
    page.pop_dialog()
    open_picker(ctx, "Pick", lambda _l: None)
    again = page.dialogs[-1]
    assert check_of(again, "Yellow") is None
    assert by_data(again, "set-filter").value == ALL_SETS
    assert shown_ids(again) == unfiltered


async def test_pick_still_calls_on_pick(ctx, page):
    picked = []
    open_picker(ctx, "Pick", picked.append)
    sheet = page.dialogs[-1]
    await toggle(sheet, "Green")
    option = by_data(sheet, "leader-results").controls[0]
    await fire(option.on_click, option)
    assert picked and picked[0].id == option.data and "Green" in picked[0].colors
    assert page.dialogs == []


@pytest.mark.parametrize("color", ["Red", "Green", "Blue", "Purple", "Black", "Yellow"])
async def test_every_dot_has_its_colour_and_a_readable_check(ctx, color):
    from core.card_colors import CARD_COLORS

    sheet = make(ctx)
    dot = by_data(sheet, f"color-{color}")
    assert dot.content.bgcolor == CARD_COLORS[color] and dot.ink and dot.on_click is not None
    await toggle(sheet, color)
    assert check_of(sheet, color).color == (ft.Colors.BLACK if color == "Yellow" else ft.Colors.WHITE)


async def test_toggling_one_dot_leaves_the_others_alone(ctx):
    sheet = make(ctx)
    await toggle(sheet, "Blue")
    selected = [c for c in ("Red", "Green", "Blue", "Purple", "Black", "Yellow") if check_of(sheet, c) is not None]
    assert selected == ["Blue"]
    assert by_data(sheet, "color-Red").content.border.top.width == 1


async def test_dots_and_search_reset_independently(ctx):
    sheet = make(ctx)
    await toggle(sheet, "Red")
    await type_query(sheet, "zzzz-no-such-leader")
    assert shown_ids(sheet) == []
    await type_query(sheet, "")
    found = shown(ctx, sheet)
    assert found and all("Red" in ld.colors for ld in found)  # clearing the search keeps the colour filter


async def test_async_on_pick_is_awaited(ctx, page):
    picked = []

    async def on_pick(leader):
        picked.append(leader.id)

    open_picker(ctx, "Pick", on_pick)
    option = by_data(page.dialogs[-1], "leader-results").controls[0]
    await fire(option.on_click, option)
    assert picked == [option.data] and page.dialogs == []
