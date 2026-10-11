#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 23:25:31.706887
Revised: 2026/10/11 23:26:25.766575

Leader picker: text search, color chips (every selected color) and the set dropdown combine.
"""

from ui.leader_picker import ALL_SETS, build_picker, open_picker
from uitools import by_data, fire, texts


def shown_ids(sheet) -> list:
    return [c.data for c in by_data(sheet, "leader-results").controls if isinstance(c.data, int)]


def shown(ctx, sheet) -> list:
    return [ctx.leaders_by_id[i] for i in shown_ids(sheet)]


async def toggle(sheet, color: str) -> None:
    chip = by_data(sheet, f"color-{color}")
    chip.selected = not chip.selected  # the client flips it before on_select fires
    await fire(chip.on_select, chip)


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


def test_shows_six_color_chips_and_set_dropdown(ctx):
    sheet = make(ctx)
    chips = by_data(sheet, "color-filters").controls
    assert [c.data for c in chips] == [f"color-{c}" for c in ("Red", "Green", "Blue", "Purple", "Black", "Yellow")]
    assert not any(c.selected for c in chips)
    assert by_data(sheet, "color-filters").wrap
    options = by_data(sheet, "set-filter").options
    assert options[0].key == ALL_SETS and options[0].text == "All sets"
    assert options[1].key.startswith("OP")


async def test_color_chip_narrows_list(ctx):
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


async def test_unselecting_chip_restores_list(ctx):
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
    assert not by_data(again, "color-Yellow").selected
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
