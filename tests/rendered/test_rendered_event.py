#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 23:54:27.137495
Revised: 2026/10/14 01:08:29.954780

The event screen in the real app: real taps and real typing, checked on screen and in what the app stored.
Every test that changes data puts the demo data back (`app.reset()`), since the app is shared by the session.
"""

import time

import pytest

from locate import (
    confirm_button,
    filled,
    first_popup_item,
    overflow_menu,
    scroll_to_end,
    scroll_until,
    snackbar,
)
from pixels import count, find, holes

NARROW = 360
# a round's badges read die, turn, result: dp from the die to the others
TURN_OFFSET, RESULT_OFFSET = 43, 83


@pytest.fixture
def event(app):
    """The newest demo event on screen; the demo data is restored afterwards."""
    app.show(f"/event/{app.newest}", "dark")
    yield app
    app.reset()


def die_badges(img, s) -> list:
    """Each round's die face (won: green six, lost: red one), top to bottom: squares of those colours with pips (the
    green record digits and red result letters have none)."""
    faces = [
        b
        for c in (s.success, s.error)
        for b in find(img, c, tol=6, min_area=150)
        if 16 <= b.w <= 26 and 16 <= b.h <= 26 and len(holes(img, b, s.on_accent)) in (1, 6)
    ]
    return sorted(faces, key=lambda f: f.y0)


def event_fields(app, s) -> list:
    """The event's outlined fields, top to bottom, without the date button: on a phone's roomier layout it is tall
    enough to pass for a field, but it sits beside the type dropdown and is clearly shorter than it."""
    found = app.fields(s)

    def date_button(f) -> bool:
        return any(g.x1 <= f.x0 and abs(g.cy - f.cy) <= 6 and g.h - f.h >= 6 for g in found)

    return [f for f in found if not date_button(f)]


def header(app, s) -> dict:
    """The header's fields by name: name, type, placement, players, set, notes."""
    found = event_fields(app, s)
    assert len(found) >= 6, [f.box for f in found]
    name, type_, *row, set_, notes = found[:6]
    placement, players = sorted(row, key=lambda f: f.x0)
    return {"name": name, "type": type_, "placement": placement, "players": players, "set": set_, "notes": notes}


def retype(app, field, text: str) -> None:
    """Click into `field`, replace everything in it with `text` and press Enter."""
    app.tap(field.cx, field.cy)
    time.sleep(0.3)
    app.clear_text()
    if text:
        app.type(text)
    app.press("enter")
    time.sleep(0.5)


# ---- round badges ---------------------------------------------------------------
def test_tapping_turn_and_result_cycles_them_on_screen_and_in_the_database(event, scheme):
    s = scheme()
    die = die_badges(event.capture(), s)[0]  # round 1: went 1st, won
    turns, results = [], []
    for _ in range(3):
        event.click(die.cx + TURN_OFFSET, die.cy)
        turns.append(event.send("round", round_no=1)["went_first"])
    for _ in range(3):
        shot = event.click(die.cx + RESULT_OFFSET, die.cy)
        results.append(event.send("round", round_no=1)["result"])
        if results[-1] == "L":  # a red result badge is drawn where the green one was
            assert filled(shot, s.error, min_w=30, max_h=40)
    assert turns == [False, None, True]  # 1st -> 2nd -> unknown -> 1st
    assert results == ["L", None, "W"]  # W -> L -> unknown -> W


# ---- an open round's editors -----------------------------------------------------
def open_first_round(app, s):
    die = die_badges(app.capture(), s)[0]
    shot = app.click(150, die.cy)  # the opponent's name: opens the row, not a badge
    return die, shot


def segment_rows(app, s) -> list:
    """The open round's segmented rows, top to bottom (kind, best of, die, turn, result): their outlines, indented
    inside the round's card (an event field cut off at the top of the screen can look as thin)."""
    return [r for r in app.rings(s.outline, min_w=300, min_h=26, max_h=44) if 30 < r.x0 < 60]


def round_notes(app, s):
    """The open round's notes field, if on screen: the one full-width field indented inside the round's card (the
    date button beside the type is indented too, but narrow; segmented rows are wide, but thinner)."""
    inside = [f for f in app.fields(s) if 30 < f.x0 < 60 and f.w >= 300 and f.h > 44]
    return inside[0] if inside else None


def editors_end(app, s):
    """Scroll until the open round's notes and the line under them (Change opponent, Delete round) are in view;
    (capture, the notes field)."""
    return scroll_until(app, lambda shot: (n := round_notes(app, s)) and n.y1 + 70 <= shot.height and n)


def all_segments(app, s) -> list:
    """Scroll until the open round's five segmented rows are all in view; them, top to bottom."""

    def five(shot):  # the last one whole, not cut off at the bottom of the screen
        rows = segment_rows(app, s)
        return rows if len(rows) >= 5 and rows[4].y1 < shot.height - 8 else None

    return scroll_until(app, five)[1]


def test_tapping_a_round_opens_its_editors(event, scheme):
    s = scheme()
    open_first_round(event, s)
    shot, notes = editors_end(event, s)  # the editors run past the bottom of the screen
    # Delete round is drawn in the error colour, Change opponent in the primary one, on the editors' last line
    # (marks of 8 px: a browser anti-aliases text more, leaving smaller cores of the exact colour)
    assert [b for b in find(shot, s.error, tol=10, min_area=8) if b.y0 > notes.y1]
    assert [b for b in find(shot, s.primary, tol=10, min_area=8) if b.y0 > notes.y1]


def test_segments_switch_and_round_notes_save(event, scheme):
    s = scheme()
    open_first_round(event, s)
    kind, _best_of, die_row, turn, result = all_segments(event, s)[:5]
    event.click(280, die_row.cy)  # "Lost die roll"
    event.click(280, turn.cy)  # "Went 2nd"
    event.click(280, result.cy)  # "Loss"
    event.click(kind.cx, kind.cy)  # "Top cut", the middle of Swiss / Top cut / Bye
    r = event.send("round", round_no=1)
    assert (r["went_first"], r["won_die_roll"]) == (False, False)
    first = event.send("event")["rounds"][0]
    # top cut made it a best of 3 (games 2 and 3 were empty): game 1 lost, the match still being played
    assert (first["top_cut"], first["best_of"], first["games"][0]["result"], first["result"]) == (True, 3, "L", None)
    _shot, notes = editors_end(event, s)  # the round notes are below the bottom of the screen
    event.tap(notes.cx, notes.cy)
    time.sleep(0.3)
    event.type("aggro start")
    event.press("tab")  # leaving the field saves it
    event.wait_until(lambda: event.send("event")["rounds"][0]["notes"] == "aggro start", what="round notes saving")


def test_making_a_played_round_a_bye_asks_before_dropping_its_games(event, scheme):
    """Round 1 holds a result, which a bye can't keep: the switch asks first, and the round becomes a bye only
    once that's confirmed."""
    s = scheme()
    open_first_round(event, s)
    kind = segment_rows(event, s)[0]
    dialog = event.click(kind.x1 - kind.w / 6, kind.cy)  # "Bye", the last of Swiss / Top cut / Bye
    assert "AlertDialog" in event.send("dialogs")
    assert event.send("event")["rounds"][0]["opponent"] is not None  # nothing saved before the answer
    button = confirm_button(dialog, s)
    event.click(button.cx, button.cy)
    event.wait_until(lambda: event.send("event")["rounds"][0]["opponent"] is None, what="the round becoming a bye")
    first = event.send("event")["rounds"][0]
    assert (first["result"], first["games"]) == ("W", [])


def editor_actions(app, s) -> tuple:
    """Scroll the open round's last line (Change opponent, Delete round) fully into view; their icons' boxes."""
    shot, notes = editors_end(app, s)  # the round notes field, just above that line

    def first_mark(color: str):  # each action's icon is the leftmost mark of its colour on that line
        marks = [b for b in find(shot, color, tol=10, min_area=8) if b.y0 > notes.y1 and b.h <= 16]
        assert marks, f"nothing drawn in {color} under the round notes"
        return min(marks, key=lambda b: b.x0)

    return first_mark(s.primary), first_mark(s.error)


def test_delete_round_asks_first_and_renumbers(event, scheme):
    s = scheme()
    open_first_round(event, s)
    _change, delete = editor_actions(event, s)
    before = [r["opponent"] for r in event.send("event")["rounds"]]
    dialog = event.click(delete.cx, delete.cy)
    assert "AlertDialog" in event.send("dialogs")
    button = confirm_button(dialog, s)
    event.click(button.cx, button.cy)
    event.wait_until(lambda: len(event.send("event")["rounds"]) == len(before) - 1, what="the round being deleted")
    after = event.send("event")["rounds"]
    assert [r["opponent"] for r in after] == before[1:]
    assert [r["round_no"] for r in after] == list(range(1, len(after) + 1))


def test_change_opponent_through_the_picker(event, scheme):
    s = scheme()
    open_first_round(event, s)
    change, _delete = editor_actions(event, s)
    before = event.send("event")["rounds"][0]["opponent"]
    event.click(change.cx, change.cy)
    assert "BottomSheet" in event.send("dialogs")
    # the picker lists the most-played opponents first, the current one at the top: search for another (the search
    # field has the focus as the sheet opens, its outline in the primary colour: the only plain field is the set's)
    set_filter = event.fields(s)[-1]
    event.type("Hancock")
    sheet = event.capture()
    event.click(sheet.width / 2, set_filter.y1 + 40)
    event.wait_until(lambda: event.send("event")["rounds"][0]["opponent"] != before, what="the opponent changing")
    assert event.send("event")["rounds"][0]["opponent"] in {"OP07-038", "OP14-041"}  # a Boa Hancock


# ---- header ------------------------------------------------------------------------
def test_typing_a_new_name_saves_it(event, scheme):
    # a dash past ASCII where the platform's input can type it (adb's can't)
    name = "Store championship — day 2" if event.types_unicode else "Store championship - day 2"
    retype(event, header(event, scheme())["name"], name)
    assert event.send("event")["name"] == name
    assert event.send("field", data="name")["value"] == name


@pytest.mark.regression
def test_a_blank_name_is_refused_on_screen_and_the_field_goes_back(event, scheme):
    """A refused edit left the field showing the refused text, as if it had been saved."""
    s = scheme()
    retype(event, header(event, s)["name"], "")
    assert snackbar(event.capture(), s, error=True)
    assert event.send("event")["name"] == "Store championship"
    assert event.send("field", data="name")["value"] == "Store championship"


@pytest.mark.regression
def test_a_placement_past_the_field_is_refused_in_the_users_language(app, scheme):
    """The reason was the repository's English sentence on a Spanish screen."""
    s = scheme()
    app.show(f"/event/{app.newest}", "dark", 0, "es")
    try:
        f = header(app, s)
        retype(app, f["placement"], "99")  # of 32 players
        assert snackbar(app.capture(), s, error=True)
        assert app.send("notices")[-1] == {
            "text": "No se pudo guardar: el puesto 99 supera los 32 jugadores",
            "error": True,
        }
        assert app.send("event")["placement"] == 3
        assert app.send("field", data="placement")["value"] == "3"
    finally:
        app.reset()


def test_placement_and_players_are_typed_in_place(event, scheme):
    f = header(event, scheme())
    retype(event, f["players"], "64")
    retype(event, header(event, scheme())["placement"], "17")
    stored = event.send("event")
    assert (stored["placement"], stored["players"]) == (17, 64)


def test_changing_the_type_from_its_dropdown(event, scheme):
    from db.models import EVENT_TYPES

    s = scheme()
    field = header(event, s)["type"]
    event.pick(field, EVENT_TYPES.index("treasure_cup"), len(EVENT_TYPES))
    assert event.send("event")["event_type"] == "treasure_cup"
    assert event.send("field", data="type")["value"] == "treasure_cup"


def test_the_date_button_opens_the_date_picker_and_dismissing_keeps_the_date(event, scheme):
    f = header(event, scheme())["type"]
    before = event.send("event")["date"]
    event.click(event.capture().width - 70, f.cy)  # the date button beside the type
    assert "DatePicker" in event.send("dialogs")
    event.press("escape")
    event.wait_until(lambda: "DatePicker" not in event.send("dialogs"), what="the date picker closing")
    assert event.send("event")["date"] == before


def test_tapping_the_playing_card_picks_your_leader(event, scheme):
    s = scheme()
    f = header(event, s)
    event.click(event.capture().width / 2, (f["players"].y1 + f["notes"].y0) / 2)
    assert "BottomSheet" in event.send("dialogs")
    sheet = event.capture()
    set_filter = event.fields(s)[-1]  # the sheet's set dropdown, just above the results
    event.click(sheet.width / 2, set_filter.y1 + 40)
    event.wait_until(lambda: "BottomSheet" not in event.send("dialogs"), what="the picker closing")
    assert event.send("event")["leader"] != "OP09-061"  # the first listed leader replaced Luffy


# ---- rounds: add -------------------------------------------------------------------
def add_round_button(app, s):
    """The Add round button's outline (primary, full width), at the end of the event."""
    found = app.rings(s.primary, min_w=300, min_h=40, max_h=60)
    assert found, "no Add round button at the end of the event"
    return found[-1]


def test_add_round_through_the_picker(event, scheme):
    s = scheme()
    scroll_to_end(event)
    add_round = add_round_button(event, s)
    before = len(event.send("event")["rounds"])
    event.click(add_round.cx, add_round.cy)
    assert "BottomSheet" in event.send("dialogs")
    sheet = event.capture()
    event.click(sheet.width / 2, event.fields(s)[-1].y1 + 40)
    event.wait_until(lambda: len(event.send("event")["rounds"]) == before + 1, what="the round being added")


# ---- delete the event --------------------------------------------------------------
def test_delete_event_from_the_menu_after_confirming(event, scheme):
    s = scheme()
    img = event.capture()
    names = [e["name"] for e in event.send("events")]
    event.click(*overflow_menu(img))
    dialog = event.click(*first_popup_item(img))
    assert "AlertDialog" in event.send("dialogs")
    button = confirm_button(dialog, s)
    event.click(button.cx, button.cy)
    event.wait_until(lambda: event.send("view")["route"] == "/events", what="going back to the list")
    assert [e["name"] for e in event.send("events")] == [n for n in names if n != "Store championship"]
    assert event.send("notices")[-1]["text"] == "Event deleted"


def test_cancelling_the_delete_keeps_the_event(event, scheme):
    s = scheme()
    img = event.capture()
    event.click(*overflow_menu(img))
    dialog = event.click(*first_popup_item(img))
    button = confirm_button(dialog, s)
    event.click(button.x0 - 60, button.cy)  # Cancel sits left of Delete
    event.wait_until(lambda: "AlertDialog" not in event.send("dialogs"), what="the dialog closing")
    assert event.send("view")["route"] == f"/event/{event.newest}"
    assert len(event.send("events")) == 5


# ---- share -------------------------------------------------------------------------
def test_share_result_renders_the_event_card(event, scheme):
    s = scheme()
    share = [b for b in filled(event.capture(), s.primary, min_w=300) if b.h >= 40][0]
    event.click(share.cx, share.cy)
    shared = event.wait_until(lambda: event.send("shared"), what="the card being shared")
    assert shared[-1]["title"] == "Store championship" and shared[-1]["mime_type"] == "image/png"
    assert shared[-1]["pixels"] == [1080, 1350]


# ---- states with their own look ------------------------------------------------------
def test_a_testing_session_has_no_standing_fields(app, scheme):
    s = scheme()
    testing = next(e for e in app.send("events") if e["name"] == "Testing with Dani")
    app.show(f"/event/{testing['id']}", "dark", NARROW)
    found = event_fields(app, s)
    # name, type, set, notes: no placement and players row (two fields side by side)
    assert len(found) == 4, [f.box for f in found]
    assert all(abs(a.y0 - b.y0) > 10 for a, b in zip(found, found[1:], strict=False))


def test_back_arrow_returns_to_the_list(app):
    app.show(f"/event/{app.newest}", "dark")
    app.click(28, 28)
    app.wait_until(lambda: app.send("view")["route"] == "/events", what="going back")


# ---- best of 3 ----------------------------------------------------------------------
@pytest.fixture
def thursday(app):
    """Thursday locals, scrolled to its end: four Swiss rounds, then R5, a top-cut best of 3 won 2-1 (L W W)."""
    ev = next(e for e in app.send("events") if e["name"] == "Thursday locals")
    app.show(f"/event/{ev['id']}", "dark")
    yield ev["id"], scroll_to_end(app)
    app.reset()


def badges(img, color: str) -> list:
    """Result-sized filled badges (36 dp, or the 42 dp score) of `color`, top to bottom."""
    return [b for b in filled(img, color, min_w=34, min_h=34, max_h=38) if b.w <= 44]


def bo3_row(img, s) -> dict:
    """The best of 3's score (its top line's right end) and the result badge of each game line under it."""
    scores = [b for c in (s.success, s.error) for b in badges(img, c) if b.w >= 40]
    score = scores[-1]  # the last round's
    results = [
        b
        for c in (s.success, s.error)
        for b in badges(img, c)
        if b.w < 40 and abs(b.cx - score.cx) <= 6 and b.y0 > score.y1
    ]
    return {"score": score, "games": sorted(results, key=lambda b: b.y0)}


def test_a_best_of_3_keeps_its_number_and_shows_each_game_under_it(thursday, scheme):
    s = scheme()
    _id, img = thursday
    row = bo3_row(img, s)
    games, score = row["games"], row["score"]
    assert len(games) == 3  # a line per game, always on screen
    assert [count(img, s.error, g.box, tol=6) > 300 for g in games] == [True, False, False]  # L W W
    assert all(b.y0 - a.y1 >= 2 for a, b in zip(games, games[1:], strict=False))  # stacked, not overlapping
    assert count(img, s.success, score.box, tol=6) > 600  # won 2-1: the score is filled green
    # the round number and its TC tag sit at the row's left, in the tertiary accent, beside the score's line
    tc = [b for b in find(img, s.tertiary, tol=12, min_area=10) if b.x1 < 70 and abs(b.cy - score.cy) <= 22]
    assert tc, "no tertiary R5 / TC label at the best of 3's left"


def test_tapping_a_games_result_changes_the_match(app, thursday, scheme):
    s = scheme()
    event_id, img = thursday
    game3 = bo3_row(img, s)["games"][2]
    shot = app.click(game3.cx, game3.cy)  # W -> L: lost 1-2
    bo3 = app.send("event", event_id=event_id)["rounds"][-1]
    assert ([g["result"] for g in bo3["games"]], bo3["result"]) == (["L", "W", "L"], "L")
    row = bo3_row(shot, s)
    assert count(shot, s.error, row["score"].box, tol=6) > 600  # the score turned red
    assert [count(shot, s.error, g.box, tol=6) > 300 for g in row["games"]] == [True, False, True]


def test_the_best_of_switch_makes_a_round_a_best_of_3(event, scheme):
    s = scheme()
    open_first_round(event, s)
    best_of = segment_rows(event, s)[1]
    event.click(280, best_of.cy)  # "Best of 3"
    first = event.send("event")["rounds"][0]
    assert (first["best_of"], first["games"][0]["result"]) == (3, "W")  # game 1 kept
    assert len(event.send("event")["rounds"][0]["games"]) == 3


# ---- byes ----------------------------------------------------------------------------
def test_add_a_bye_logs_an_automatic_win_with_the_jester(event, scheme):
    s = scheme()
    img = scroll_to_end(event)
    add_round = add_round_button(event, s)
    marks = [b for b in find(img, s.primary, tol=10, min_area=8) if b.y0 > add_round.y1 + 4]
    assert marks, "no Add a bye button under Add round"
    target = min(marks, key=lambda b: b.y0)
    before = len(event.send("event")["rounds"])
    event.click(target.cx, target.cy)
    event.wait_until(lambda: len(event.send("event")["rounds"]) == before + 1, what="the bye being added")
    rounds = event.send("event")["rounds"]
    assert (rounds[-1]["opponent"], rounds[-1]["result"]) == (None, "W")
    shot = scroll_to_end(event)
    # laid out like an opponent: a gold stripe, then a 30 dp portrait framed in gold with the jester inside
    stripes = [b for b in find(shot, s.tertiary, tol=12, min_area=100) if 5 <= b.w <= 9 and 26 <= b.h <= 32]
    assert stripes, "no gold stripe on the bye's row"
    stripe = stripes[-1]
    portrait = (stripe.x1 + 2, stripe.y0, stripe.x1 + 36, stripe.y1)
    assert count(shot, s.tertiary, portrait, tol=12) > 60  # the gold frame
    inside = shot.crop((portrait[0] + 6, portrait[1] + 4, portrait[2] - 6, portrait[3] - 4))
    assert len(inside.getcolors(maxcolors=4096) or ()) > 12  # a drawing in the frame, not a flat fill
