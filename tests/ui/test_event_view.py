#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.780273
Revised: 2026/10/13 14:54:42.508742
"""

import datetime as dt

import flet as ft
import pytest

from ui.event_view import EventScreen, picked_day
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


def test_rounds_start_collapsed_even_when_pending(screen):
    assert [by_data(screen.body, f"round-{n}").expanded for n in (1, 2, 3, 4)] == [False, False, False, False]


async def open_round(screen, n):
    tile = by_data(screen.body, f"round-{n}")
    tile.expanded = True
    await fire(tile.on_change, tile)
    screen.refresh()
    return by_data(screen.body, f"round-{n}")


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
    assert by_data(screen.body, "name").value == "Sunday locals"  # the field shows what's stored again


async def test_type_and_notes(screen, events, sample_event):
    dd = by_data(screen.body, "type")
    dd.value = "regional"
    await fire(dd.on_select, dd)
    notes = by_data(screen.body, "notes")
    notes.value = "Draws were all on time"
    await fire(notes.on_blur, notes)
    ev = events.get(sample_event.id)
    assert (ev.event_type, ev.notes) == ("regional", "Draws were all on time")


@pytest.mark.parametrize(
    ("lang", "name", "new_type", "expected"),
    [
        ("en", "Local #4", "regional", "Regional #1"),
        ("en", "Local #4", "other", "Event #1"),
        ("gl", "Local #4", "worlds", "Mundial #1"),
        ("es", "Local #4", "heroines_battle", "Heroines Battle #1"),
        ("en", "My locals", "regional", "My locals"),  # a name you typed is never replaced
        ("en", "Regional #4", "national", "Regional #4"),  # numbered, but not after its own type
    ],
)
async def test_changing_type_renames_a_suggested_name(ctx, events, sample_event, lang, name, new_type, expected):
    from i18n import set_lang

    set_lang(ctx.page, lang)
    events.update(sample_event.id, name=name)
    screen = EventScreen(ctx, sample_event.id)
    screen.build()
    dd = by_data(screen.body, "type")
    dd.value = new_type
    await fire(dd.on_select, dd)
    ev = events.get(sample_event.id)
    assert (ev.event_type, ev.name) == (new_type, expected)
    assert by_data(screen.body, "name").value == expected


async def test_renamed_type_counts_the_other_events_of_the_new_type(ctx, events, sample_event):
    events.create("Regional #1", "regional", dt.date(2026, 1, 1))
    events.create("Big regional", "regional", dt.date(2026, 2, 1))
    events.update(sample_event.id, name="Local #1")
    screen = EventScreen(ctx, sample_event.id)
    screen.build()
    dd = by_data(screen.body, "type")
    dd.value = "regional"
    await fire(dd.on_select, dd)
    assert events.get(sample_event.id).name == "Regional #3"


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
    tile = await open_round(screen, 4)
    for tag, selected in (("result", ["L"]), ("turn", ["2"]), ("die", ["won"])):
        seg = by_data(tile, tag)
        seg.selected = selected
        await fire(seg.on_change, seg)
        tile = by_data(screen.body, "round-4")
    kind = by_data(tile, "kind")
    kind.selected = ["top_cut"]
    await fire(kind.on_change, kind)
    r = next(r for r in events.get(sample_event.id).rounds if r.id == pending.id)
    game = r.game(1)
    assert (game.result, game.went_first, game.chose_turn, r.top_cut) == ("L", False, True, True)
    # top cut brings best of 3: game 1 lost, the match still being played
    assert (r.best_of, r.result) == (3, None)
    # regression: picking Win/Loss used to snap the open round shut; it stays open until you close it
    assert by_data(screen.body, "round-4").expanded is True


async def test_clearing_a_segment_stores_none(screen, events, sample_event):
    seg = by_data(by_data(screen.body, "round-1"), "turn")
    seg.selected = []
    await fire(seg.on_change, seg)
    assert events.get(sample_event.id).rounds[0].game(1).went_first is None


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
    assert by_data(screen.body, "round-5").expanded is False  # regression: it used to open on its own


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
        seen.append(round_of(events, sample_event, 3).game(1).went_first)
    assert seen == [True, False, None]


async def test_die_cycles(screen, events, sample_event):
    seen = []
    for _ in range(3):
        await tap(screen, 3, "die")
        seen.append(round_of(events, sample_event, 3).game(1).chose_turn)
    assert seen == [True, False, None]


async def test_cycling_keeps_expansion_state(screen):
    await open_round(screen, 4)
    await tap(screen, 4, "result")
    await tap(screen, 1, "result")
    assert by_data(screen.body, "round-4").expanded
    assert not by_data(screen.body, "round-1").expanded


async def test_cycle_rejected_edit_shows_error(screen, ctx, page, monkeypatch, events, sample_event):
    from events.repository import EventError

    def refuse(*_a, **_k):
        raise EventError("nope")

    monkeypatch.setattr(ctx.events, "update_game", refuse)
    await tap(screen, 4, "result")
    assert isinstance(page.dialogs[-1], ft.SnackBar) and page.dialogs[-1].data == "error"
    assert round_of(events, sample_event, 4).result is None


def test_collapsed_row_shows_turn_and_die(screen):
    first = by_data(screen.body, "round-1")  # went first, won the roll
    second = by_data(screen.body, "round-2")  # went second, lost the roll
    unknown = by_data(screen.body, "round-3")
    keycap = lambda tile: [c.icon for c in walk(by_data(tile, "turn-cycle")) if isinstance(c, ft.Icon)]  # noqa: E731
    assert keycap(first) == [ft.Icons.LOOKS_ONE] and keycap(second) == [ft.Icons.LOOKS_TWO]
    assert "—" in texts(by_data(unknown, "turn-cycle"))
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


@pytest.mark.parametrize("utc_offset", [-11, -5, 0, 1, 2, 9, 14])
def test_picked_day_is_the_local_day_not_the_utc_one(utc_offset):
    """Regression: in UTC+2 the picker's 2026-07-04 arrived as 2026-07-03T22:00Z and was saved a day early."""
    local = dt.timezone(dt.timedelta(hours=utc_offset))
    as_sent = dt.datetime(2026, 7, 4, tzinfo=local).astimezone(dt.UTC)
    assert picked_day(as_sent, local) == dt.date(2026, 7, 4)


@pytest.mark.parametrize(
    "value", [dt.datetime(2026, 7, 4), dt.date(2026, 7, 4), dt.datetime(2026, 7, 4).astimezone().astimezone(dt.UTC)]
)
def test_picked_day_in_the_device_zone(value):
    """Naive values are taken as they are; aware ones go back to this machine's own zone."""
    assert picked_day(value) == dt.date(2026, 7, 4)


async def test_date_picker_saves_the_local_day(screen, page, events, sample_event):
    btn = by_data(screen.body, "date")
    await fire(btn.on_click, btn)
    picker = page.dialogs[-1]
    picker.value = dt.datetime(2026, 7, 4).astimezone().astimezone(dt.UTC)  # how Flet sends it back
    await fire(picker.on_change, picker)
    assert events.get(sample_event.id).date == dt.date(2026, 7, 4)


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


@pytest.mark.regression
async def test_changing_an_opponent_reorders_the_picker(screen, page, sample_event, leader_ids, ctx):
    """The picker lists the most-played opponents first. Changing a round's opponent used to leave that order as it
    was until some other change refreshed it."""
    assert ctx.leaders[0].id != leader_ids[5]  # never played yet
    for n in (1, 2, 3):
        tile = by_data(screen.body, f"round-{n}")
        btn = next(c for c in walk(tile) if isinstance(c, ft.TextButton) and c.content == "Change opponent")
        await fire(btn.on_click, btn)
        await pick_leader(page.dialogs[-1], leader_ids[5], ctx.leaders_by_id[leader_ids[5]].code)
    assert ctx.leaders[0].id == leader_ids[5]


async def test_clearing_the_result_segment_keeps_the_row_open(screen, events, sample_event):
    seg = by_data(await open_round(screen, 4), "result")
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


def test_result_pill_keeps_a_margin_from_the_right_edge(screen):
    """Regression: with a 2 dp right padding the W/L pill sat almost on the row's border."""
    from ui.event_view import ROUND_EDGE

    tile = by_data(screen.body, "round-1")
    assert tile.tile_padding.right == ROUND_EDGE >= tile.tile_padding.left


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


@pytest.mark.regression
async def test_a_number_too_big_to_store_is_refused_with_a_message(screen, events, sample_event, page):
    """Twenty digits are past SQLite's integers: the save used to raise OverflowError, which no handler caught."""
    await type_into(screen, "players", "9" * 20)
    assert events.get(sample_event.id).players is None
    assert page.dialogs[-1].data == "error"
    assert by_data(screen.body, "players").value == ""  # the field shows what's stored again, not the typo


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


@pytest.mark.regression
async def test_a_refused_number_goes_back_to_the_stored_one(screen, events, sample_event):
    """A refused placement stayed typed in the field, as if it had been saved."""
    await type_into(screen, "players", "8")
    await type_into(screen, "placement", "9")
    assert by_data(screen.body, "placement").value == ""
    assert by_data(screen.body, "players").value == "8"


async def test_a_refused_round_edit_redraws_the_stored_round(screen, ctx, monkeypatch, sample_event):
    from events.repository import EventError

    def refuse(*_a, **_k):
        raise EventError("nope")

    monkeypatch.setattr(ctx.events, "update_round", refuse)
    notes = by_data(screen.body, "round-notes")
    notes.value = "typed"
    await fire(notes.on_blur, notes)
    assert by_data(screen.body, "round-notes").value == ""


@pytest.mark.regression
async def test_a_refused_edit_is_explained_in_the_users_language(ctx, events, sample_event, page):
    """The reason after "No se pudo guardar:" was the repository's English sentence."""
    from i18n import set_lang

    set_lang(page, "es")
    s = EventScreen(ctx, sample_event.id)
    s.build()
    await type_into(s, "players", "8")
    await type_into(s, "placement", "9")
    assert page.dialogs[-1].content.value == "No se pudo guardar: el puesto 9 supera los 8 jugadores"


# ---- best of 3 ----------------------------------------------------------------------
@pytest.fixture
def bo3_screen(ctx, events, sample_event, leader_ids):
    """The sample event plus a top-cut round (best of 3) as round 5."""
    events.add_round(sample_event.id, leader_ids[2], "top_cut")
    s = EventScreen(ctx, sample_event.id)
    s.build()
    return s


def test_a_best_of_3_row_shows_each_games_result_and_the_score(bo3_screen):
    tile = by_data(bo3_screen.body, "round-5")
    head = by_data(tile, "round-head")  # the collapsed row itself: the top line, then a line per game
    top = by_data(head, "round-title")
    assert texts(by_data(top, "score")) == ["0-0"] and texts(top)[0] == "R5"  # the number stays
    assert "TC" in texts(by_data(top, "top-cut-tag"))
    for n in (1, 2, 3):
        line = by_data(head, f"game-{n}")
        assert by_data(line, f"g{n}-chooser-cycle") and by_data(line, f"g{n}-turn-cycle")
        assert by_data(line, f"g{n}-result-cycle")
    assert not [c for c in walk(top) if getattr(c, "data", None) in ("turn-cycle", "die-cycle")]


async def test_tapping_a_games_result_cycles_it_and_updates_the_score(bo3_screen, events, sample_event):
    for n in (1, 2):
        await tap(bo3_screen, 5, f"g{n}-result")
    r = round_of(events, sample_event, 5)
    assert [g.result for g in r.games] == ["W", "W", None] and r.result == "W"
    assert "2-0" in texts(by_data(by_data(bo3_screen.body, "round-5"), "score"))


async def test_an_open_best_of_3_has_a_line_per_game(bo3_screen, events, sample_event):
    tile = await open_round(bo3_screen, 5)
    for n in (1, 2, 3):
        line = by_data(tile, f"game-{n}")
        assert f"Game {n}" in texts(line)
        assert by_data(line, f"g{n}-turn-cycle") and by_data(line, f"g{n}-result-cycle")
    # top cut: game 1's chooser is the higher seed, not a die
    assert by_data(by_data(tile, "game-1"), "g1-chooser-cycle")
    target = by_data(by_data(tile, "game-2"), "g2-turn-cycle")
    await fire(target.on_click, target)
    assert round_of(events, sample_event, 5).game(2).went_first is True


async def test_later_games_show_the_chooser_the_rules_give_and_can_be_overridden(bo3_screen, events, sample_event):
    r = round_of(events, sample_event, 5)
    events.update_game(r.id, 1, result="L")
    bo3_screen.refresh()
    tile = await open_round(bo3_screen, 5)
    chooser = by_data(by_data(tile, "game-2"), "g2-chooser-cycle")
    assert "You" in texts(chooser)  # lost game 1: you choose game 2
    assert "previous game's loser" in chooser.tooltip
    await fire(chooser.on_click, chooser)  # override: None -> True (stored)
    tile = by_data(bo3_screen.body, "round-5")
    chooser = by_data(by_data(tile, "game-2"), "g2-chooser-cycle")
    assert round_of(events, sample_event, 5).game(2).chose_turn is True
    assert "previous game's loser" not in chooser.tooltip


async def test_the_best_of_switch_turns_a_round_into_a_best_of_3_and_back(screen, events, sample_event):
    tile = await open_round(screen, 1)
    seg = by_data(tile, "best-of")
    seg.selected = ["3"]
    await fire(seg.on_change, seg)
    r = round_of(events, sample_event, 1)
    assert (r.best_of, r.game(1).result) == (3, "W")  # game 1 kept
    assert by_data(by_data(screen.body, "round-1"), "game-3")
    seg = by_data(by_data(screen.body, "round-1"), "best-of")
    seg.selected = ["1"]
    await fire(seg.on_change, seg)
    assert round_of(events, sample_event, 1).best_of == 1


async def test_the_best_of_switch_ignores_clearing_and_the_same_value(screen, ctx, monkeypatch):
    calls = spy(monkeypatch, ctx.events, "update_round")
    seg = by_data(await open_round(screen, 1), "best-of")
    for selected in ([], ["1"]):
        seg.selected = selected
        await fire(seg.on_change, seg)
    assert calls == []


async def test_a_top_cut_best_of_1_asks_who_chose_instead_of_the_die(ctx, events, sample_event, leader_ids):
    r = events.add_round(sample_event.id, leader_ids[2], "top_cut", best_of=1)
    s = EventScreen(ctx, sample_event.id)
    s.build()
    tile = await open_round(s, 5)
    assert by_data(tile, "chooser") and not [c for c in walk(tile) if getattr(c, "data", None) == "die"]
    assert by_data(by_data(tile, "round-title"), "chooser-cycle")
    seg = by_data(tile, "chooser")
    seg.selected = ["lost"]
    await fire(seg.on_change, seg)
    assert round_of(events, sample_event, 5).game(1).chose_turn is False
    assert r.best_of == 1


# ---- round kinds, byes, the event's set ---------------------------------------------
async def test_add_a_bye_logs_one_without_a_picker(screen, events, sample_event, page):
    btn = by_data(screen.body, "add-bye")
    await fire(btn.on_click, btn)
    last = events.get(sample_event.id).rounds[-1]
    assert (last.kind, last.result) == ("bye", "W")
    assert not [d for d in page.dialogs if isinstance(d, ft.BottomSheet)]
    tile = by_data(screen.body, "round-5")
    assert "Bye" in texts(tile) and "Automatic win" in texts(tile)
    assert by_data(tile, "bye-result")


async def test_making_a_round_a_bye_and_back(screen, ctx, events, sample_event, page, leader_ids):
    tile = await open_round(screen, 1)
    kind = by_data(tile, "kind")
    kind.selected = ["bye"]
    await fire(kind.on_change, kind)
    dialog = page.dialogs[-1]  # round 1 holds a result, which a bye can't keep: asked first
    assert isinstance(dialog, ft.AlertDialog)
    await fire(dialog.actions[1].on_click, dialog.actions[1])
    assert round_of(events, sample_event, 1).bye
    tile = by_data(screen.body, "round-1")
    assert not [c for c in walk(tile) if getattr(c, "data", None) in ("best-of", "result")]
    kind = by_data(tile, "kind")
    kind.selected = ["swiss"]
    await fire(kind.on_change, kind)
    picker = page.dialogs[-1]  # a bye had no opponent: pick one
    assert isinstance(picker, ft.BottomSheet)
    await pick_leader(picker, leader_ids[3], ctx.leaders_by_id[leader_ids[3]].code)
    r = round_of(events, sample_event, 1)
    assert (r.kind, r.opponent_leader_id) == ("swiss", leader_ids[3])


async def test_the_kind_switch_ignores_clearing_and_the_same_kind(screen, ctx, monkeypatch):
    calls = spy(monkeypatch, ctx.events, "update_round")
    kind = by_data(await open_round(screen, 1), "kind")
    for selected in ([], ["swiss"]):
        kind.selected = selected
        await fire(kind.on_change, kind)
    assert calls == []


@pytest.mark.regression
@pytest.mark.parametrize(("tag", "stored"), [("kind", "swiss"), ("best-of", "1")])
async def test_a_cleared_switch_shows_the_stored_value_again(screen, tag, stored):
    """Clearing the kind or best-of switch saved nothing but left it blank, as if the round had neither."""
    seg = by_data(await open_round(screen, 1), tag)
    seg.selected = []
    await fire(seg.on_change, seg)
    assert by_data(by_data(screen.body, "round-1"), tag).selected == [stored]


@pytest.mark.regression
async def test_a_bye_whose_picker_is_dismissed_still_shows_as_a_bye(ctx, events, sample_event, page):
    """Switching a bye to Swiss opens the picker; dismissing it saved nothing but the switch said "Swiss"."""
    events.add_round(sample_event.id, None, "bye")
    s = EventScreen(ctx, sample_event.id)
    s.build()
    kind = by_data(await open_round(s, 5), "kind")
    kind.selected = ["swiss"]
    await fire(kind.on_change, kind)
    assert isinstance(page.dialogs[-1], ft.BottomSheet)
    page.dialogs.pop()  # dismissed
    assert round_of(events, sample_event, 5).bye
    assert by_data(by_data(s.body, "round-5"), "kind").selected == ["bye"]


async def bo3_with_game_2(bo3_screen, events, sample_event):
    r = round_of(events, sample_event, 5)
    events.update_game(r.id, 2, went_first=True)
    bo3_screen.refresh()
    return by_data(await open_round(bo3_screen, 5), "best-of")


@pytest.mark.parametrize(("answer", "best_of"), [(1, 1), (0, 3)], ids=["remove", "cancel"])
async def test_a_best_of_1_that_would_drop_noted_games_asks_first(
    bo3_screen, events, sample_event, page, answer, best_of
):
    seg = await bo3_with_game_2(bo3_screen, events, sample_event)
    seg.selected = ["1"]
    await fire(seg.on_change, seg)
    dialog = page.dialogs[-1]
    assert isinstance(dialog, ft.AlertDialog) and dialog.title.value == "Remove noted games?"
    assert "Round 5" in dialog.content.value
    # until answered, the switch shows what's stored
    assert by_data(by_data(bo3_screen.body, "round-5"), "best-of").selected == ["3"]
    await fire(dialog.actions[answer].on_click, dialog.actions[answer])
    r = round_of(events, sample_event, 5)
    assert r.best_of == best_of
    assert (r.game(2).went_first is True) == (best_of == 3)


async def test_a_best_of_1_with_nothing_noted_past_game_1_needs_no_asking(bo3_screen, events, sample_event, page):
    events.update_game(round_of(events, sample_event, 5).id, 1, result="W")
    bo3_screen.refresh()
    seg = by_data(await open_round(bo3_screen, 5), "best-of")
    seg.selected = ["1"]
    await fire(seg.on_change, seg)
    assert not [d for d in page.dialogs if isinstance(d, ft.AlertDialog)]
    r = round_of(events, sample_event, 5)
    assert (r.best_of, r.game(1).result) == (1, "W")


async def test_a_bye_from_a_round_with_nothing_noted_needs_no_asking(ctx, events, sample_event, page, leader_ids):
    events.add_round(sample_event.id, leader_ids[2])
    s = EventScreen(ctx, sample_event.id)
    s.build()
    kind = by_data(await open_round(s, 5), "kind")
    kind.selected = ["bye"]
    await fire(kind.on_change, kind)
    assert not [d for d in page.dialogs if isinstance(d, ft.AlertDialog)]
    assert round_of(events, sample_event, 5).bye


async def test_top_cut_to_swiss_keeps_noted_games_without_asking(bo3_screen, events, sample_event, page):
    await bo3_with_game_2(bo3_screen, events, sample_event)
    kind = by_data(by_data(bo3_screen.body, "round-5"), "kind")
    kind.selected = ["swiss"]
    await fire(kind.on_change, kind)
    assert not [d for d in page.dialogs if isinstance(d, ft.AlertDialog)]
    r = round_of(events, sample_event, 5)
    assert (r.kind, r.best_of, r.game(2).went_first) == ("swiss", 3, True)  # game 2 noted: still a best of 3


async def test_a_new_round_continues_the_top_cut(screen, ctx, events, sample_event, page, leader_ids):
    events.add_round(sample_event.id, leader_ids[1], "top_cut")
    screen.refresh()
    btn = by_data(screen.body, "add-round")
    await fire(btn.on_click, btn)
    await pick_leader(page.dialogs[-1], leader_ids[2], ctx.leaders_by_id[leader_ids[2]].code)
    assert round_of(events, sample_event, 6).kind == "top_cut"


def test_round_notes_show_on_the_row(ctx, events, sample_event):
    events.update_round(sample_event.rounds[0].id, notes="mulliganed into the nuts")
    s = EventScreen(ctx, sample_event.id)
    s.build()
    assert texts(by_data(by_data(s.body, "round-1"), "row-notes")) == ["mulliganed into the nuts"]


async def test_the_events_set_and_dropped_are_set_in_place(screen, events, sample_event):
    dd = by_data(screen.body, "set")
    assert dd.value == "" and dd.options[0].key == ""  # not noted yet
    dd.value = "OP16"
    await fire(dd.on_select, dd)
    assert events.get(sample_event.id).set_code == "OP16"
    dd = by_data(screen.body, "set")
    dd.value = "OP16"
    await fire(dd.on_select, dd)  # the same set: nothing to save
    switch = by_data(screen.body, "dropped")
    switch.value = True
    await fire(switch.on_change, switch)
    assert events.get(sample_event.id).dropped is True


async def pick_date(screen, page, day):
    btn = by_data(screen.body, "date")
    await fire(btn.on_click, btn)
    picker = page.dialogs[-1]
    picker.value = day
    await fire(picker.on_change, picker)


async def test_a_new_event_moved_back_in_time_follows_with_its_set(ctx, page, events):
    draft = ctx.new_event("locals", dt.date(2026, 10, 12), None)
    s = EventScreen(ctx, draft.id)
    s.build()
    assert by_data(s.body, "set").value == "OP17"
    await pick_date(s, page, dt.date(2026, 7, 4))
    assert events.get(draft.id).set_code == "OP16"
    assert by_data(s.body, "set").value == "OP16"


async def test_a_set_picked_by_hand_stays_when_the_date_changes(ctx, page, events):
    draft = ctx.new_event("locals", dt.date(2026, 10, 12), None)
    s = EventScreen(ctx, draft.id)
    s.build()
    dd = by_data(s.body, "set")
    dd.value = "EB03"
    await fire(dd.on_select, dd)
    await pick_date(s, page, dt.date(2026, 7, 4))
    assert events.get(draft.id).date == dt.date(2026, 7, 4)
    assert events.get(draft.id).set_code == "EB03"


async def test_a_set_not_noted_stays_not_noted_when_the_date_changes(screen, page, events, sample_event):
    await pick_date(screen, page, dt.date(2026, 7, 4))
    assert events.get(sample_event.id).set_code is None


def test_a_set_the_catalogue_lost_still_shows(ctx, events, sample_event, seeded_db):
    from db.models import CardSet

    with seeded_db.session() as s:
        s.add(CardSet(code="ZZ01"))
    events.update(sample_event.id, set_code="ZZ01")
    s = EventScreen(ctx, sample_event.id)
    s.build()
    assert by_data(s.body, "set").options[1].key == "ZZ01"


def test_testing_sessions_have_a_set_but_no_dropped(ctx, events):
    ev = events.create("Practice", "testing", dt.date(2026, 1, 1))
    s = EventScreen(ctx, ev.id)
    s.build()
    assert by_data(s.body, "set")
    assert "dropped" not in [c.data for c in walk(s.body)]


@pytest.mark.regression
async def test_round_actions_wrap_instead_of_being_cut(screen):
    """At 360 dp "Delete round" ran past the card's edge and was cut off."""
    tile = await open_round(screen, 1)
    assert by_data(tile, "round-actions").wrap is True
