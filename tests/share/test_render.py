#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.477606
Revised: 2026/10/13 11:44:59.003496
"""

import datetime as dt

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from catalog.repository import Leader
from events.repository import Event, Game, Round
from share import render
from stats.compute import matchups, summarize

LEADERS = {
    1: Leader(1, "OP01-001", "Roronoa Zoro", "OP01", ("Red",)),
    2: Leader(2, "OP01-003", "Monkey.D.Luffy", "OP01", ("Red", "Green")),
    3: Leader(3, "EB01-040", "Kyros", "EB01", ("Black", "Yellow")),
    4: Leader(4, "OP99-001", "A leader with an absurdly long name that cannot possibly fit", "OP99", ()),
}
identity = lambda s: s  # noqa: E731


def event(rounds, name="Sunday locals", leader=1):
    return Event(1, name, "locals", dt.date(2026, 10, 5), leader, "", tuple(rounds))


def rounds(n, result="W"):
    return [Round.single_game(i, i, (i % 4) + 1, result, i % 2 == 0, None, i > n - 2) for i in range(1, n + 1)]


def assert_card(path):
    assert path.exists() and path.suffix == ".png"
    with Image.open(path) as img:
        assert img.size == (render.W, render.H)
        # not a blank canvas: plenty of distinct colors were drawn
        assert len(img.convert("RGB").getcolors(maxcolors=1 << 16) or []) > 20


@pytest.mark.parametrize("n", [0, 1, 7, 30])
def test_event_card_any_round_count(n):
    assert_card(render.event_card(event(rounds(n)), LEADERS, identity, "Locals"))


def test_event_card_pending_round_unknown_leaders_and_long_name():
    ev = event([Round.single_game(1, 1, 99, None), Round.single_game(2, 2, 4, "L")], name="X" * 200, leader=None)
    assert_card(render.event_card(ev, LEADERS, identity, "Locals"))


def test_event_card_huge_record_shrinks():
    assert render.Card.fit("120-80-10", "ExtraBold", 120, 400) < 120
    assert render.Card.fit("3-1", "ExtraBold", 120, 400) == 120
    assert_card(render.event_card(event(rounds(150, "W")), LEADERS, identity, "Locals"))


def test_matchups_card():
    evs = [event(rounds(12)), event(rounds(5, "L"))]
    s, ms = summarize(evs), matchups(evs)
    assert_card(render.matchups_card("All leaders", s, ms, LEADERS, identity))


def test_matchups_card_empty_and_overflow():
    assert_card(render.matchups_card("All leaders", summarize([]), [], LEADERS, identity))
    many = [Round.single_game(i, i, 1000 + i, "W") for i in range(1, 40)]
    evs = [event(many)]
    assert_card(render.matchups_card("x", summarize(evs), matchups(evs), LEADERS, identity))


@pytest.mark.parametrize("card", ["matchups", "summary"])
def test_stats_cards_show_the_one_leader_played_in_the_header(card):
    evs = [event(rounds(5))]
    s = summarize(evs)
    draw = {
        "matchups": lambda own: render.matchups_card("Playing Zoro", s, matchups(evs), LEADERS, identity, own),
        "summary": lambda own: render.summary_card("Playing Zoro", s, LEADERS, identity, own),
    }[card]
    side, top = render.HEADER_PORTRAIT, render.HEADER_PORTRAIT_Y
    x = render.W - render.PAD - side
    with Image.open(draw(LEADERS[1])) as img:
        assert img.getpixel((x + side // 2, top + 1)) == render.CARD_COLORS["Red"]  # Zoro's frame
        face = img.getpixel((x + side // 2, top + side // 2))
        assert face not in (render.BG, render.PANEL_HI)  # his portrait inside it
    with Image.open(draw(None)) as img:  # all leaders: no portrait
        assert img.getpixel((x + side // 2, top + side // 2)) == render.BG


def test_summary_card():
    evs = [
        event(rounds(12)),
        event([Round.single_game(9, 1, 3, "L"), Round.single_game(10, 2, 3, "L"), Round.single_game(11, 3, 3, "L")]),
    ]
    assert_card(render.summary_card("Playing Zoro", summarize(evs), LEADERS, identity))


def test_summary_card_empty():
    assert_card(render.summary_card("All leaders", summarize([]), LEADERS, identity))


def test_cards_use_translations():
    seen = []

    def spy(s):
        seen.append(s)
        return s

    render.summary_card("x", summarize([event(rounds(3))]), LEADERS, spy)
    assert {"Overall record", "Recent form", "Tracked with timtapper · One Piece TCG"} <= set(seen)


def test_cards_render_into_temp_dir(tmp_path):
    path = render.event_card(event(rounds(2)), LEADERS, identity, "Locals")
    assert path.parent == tmp_path / "temp"


# ---- properties: any history renders a full card, never a crash ---------------------
any_round = st.tuples(
    st.sampled_from([1, 2, 3, 4, 99]),  # 99: a leader the catalogue doesn't know
    st.sampled_from([None, "W", "L"]),
    st.sampled_from([None, True, False]),
    st.booleans(),
)  # (opponent, result, went first, top cut)
any_history = st.lists(any_round, max_size=40).map(
    lambda rs: [
        Round.single_game(i, i, opp, res, first, None, top) for i, (opp, res, first, top) in enumerate(rs, start=1)
    ]
)
any_name = st.text(min_size=1, max_size=120)
FEW = settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


@pytest.mark.property
@FEW
@given(any_history, any_name, st.sampled_from([None, 1, 2, 3, 4, 99]))
def test_property_event_card_renders_any_event(rs, name, leader):
    assert_card(render.event_card(event(rs, name=name, leader=leader), LEADERS, identity, "Locals"))


@pytest.mark.property
@FEW
@given(st.lists(any_history, max_size=4), any_name)
def test_property_stats_cards_render_any_history(histories, scope):
    evs = [event(rs) for rs in histories]
    s = summarize(evs)
    assert_card(render.summary_card(scope, s, LEADERS, identity))
    assert_card(render.matchups_card(scope, s, matchups(evs), LEADERS, identity))


@pytest.mark.regression
@pytest.mark.parametrize(
    ("size", "max_w", "portrait"),
    [(44, 520, 96), (32, 580, 60), (30, 540, 58), (30, (render.W - 2 * render.PAD - 24) // 2 - 64, 72)],
)
def test_every_real_leader_name_is_drawn_whole(monkeypatch, size, max_w, portrait):
    """The event card's "playing" line cut "Donquixote Doflamingo" and four others with "…"."""
    from catalog.repository import load_bundled

    card = render.Card()
    drawn = []
    monkeypatch.setattr(card.d, "text", lambda xy, s, **kw: drawn.append(s))
    names = sorted({r.name for r in load_bundled()})
    for i, name in enumerate(names):
        card.leader_line(0, 100, Leader(i, "X-001", name, None, ()), size, max_w, identity, portrait=portrait)
    assert drawn == names  # nothing ellipsized


def test_an_impossible_name_still_ends_in_an_ellipsis_inside_the_box():
    card = render.Card()
    drawn = []
    card.d.text = lambda xy, s, font, **kw: drawn.append((s, font.getlength(s)))
    card.leader_line(0, 100, Leader(9, "X-001", "W" * 200, None, ()), 30, 400, identity)
    ((s, width),) = drawn
    assert s.endswith("…") and width <= 400 - 30


def test_event_card_shows_the_standing_in_its_own_band(monkeypatch):
    import dataclasses

    seen, subtitles = [], []
    real_text, real_header = render.Card.text, render.Card.header
    monkeypatch.setattr(
        render.Card,
        "text",
        lambda self, xy, s, size, **kw: seen.append((s, size)) or real_text(self, xy, s, size, **kw),
    )
    monkeypatch.setattr(
        render.Card,
        "header",
        lambda self, title, subtitle: subtitles.append(subtitle) or real_header(self, title, subtitle),
    )
    ranked = dataclasses.replace(event(rounds(3)), placement=2, players=24)
    assert_card(render.event_card(ranked, LEADERS, identity, "Locals"))
    assert ("#2", 64) in seen and ("of 24 players", 34) in seen  # big, not tucked into the subtitle
    assert subtitles == ["Locals · 2026-10-05"]


@pytest.mark.parametrize(("placement", "players", "texts"), [(3, None, ["#3", "place"]), (None, 40, ["40 players"])])
def test_standing_band_with_half_the_standing(monkeypatch, placement, players, texts):
    import dataclasses

    seen = []
    real_text = render.Card.text
    monkeypatch.setattr(
        render.Card, "text", lambda self, xy, s, size, **kw: seen.append(s) or real_text(self, xy, s, size, **kw)
    )
    assert_card(
        render.event_card(
            dataclasses.replace(event(rounds(2)), placement=placement, players=players), LEADERS, identity, "Locals"
        )
    )
    assert all(t in seen for t in texts)


def test_no_standing_no_band(monkeypatch):
    calls = []
    monkeypatch.setattr(render, "_standing_band", lambda *a, **k: calls.append(a))
    assert_card(render.event_card(event(rounds(2)), LEADERS, identity, "Locals"))
    assert calls == []


def test_share_cards_carry_the_app_logo():
    path = render.event_card(event(rounds(1)), LEADERS, identity, "Locals")
    with Image.open(path) as img, Image.open(render.LOGO_MARK) as mark:
        corner = img.convert("RGB").crop((
            render.PAD,
            72 - render.LOGO_SIZE // 2,
            render.PAD + render.LOGO_SIZE,
            72 + render.LOGO_SIZE // 2,
        ))
        assert len(corner.getcolors(maxcolors=1 << 16) or []) > 30  # the mark's drawing, not empty background
        assert mark.size[0] >= render.LOGO_SIZE


@pytest.mark.parametrize("won", [True, False])
def test_die_matches_the_app(won):
    from core.die import DIE_PIPS, LOST_PIPS, WON_PIPS

    card = render.Card()
    card.die(100, 100, 60, won)
    fill = render.RESULT_COLORS["W" if won else "L"]
    pips = DIE_PIPS[WON_PIPS if won else LOST_PIPS]
    for px, py in pips:  # a dark pip at every pip centre, the die colour between
        assert card.img.getpixel((round(70 + px * 60), round(70 + py * 60))) == render.BG
    assert card.img.getpixel((72, 100)) == fill  # left edge, clear of every pip


def test_rounds_show_the_die_only_when_the_roll_is_known(monkeypatch):
    rolls = []
    monkeypatch.setattr(render.Card, "die", lambda self, cx, cy, side, won: rolls.append(won))
    rs = [
        Round.single_game(1, 1, 2, "W", True, True),
        Round.single_game(2, 2, 3, "L", False, False),
        Round.single_game(3, 3, 2, None),
    ]
    assert_card(render.event_card(event(rs), LEADERS, identity, "Locals"))
    assert rolls == [True, False]


def test_leader_line_draws_the_framed_portrait_then_the_name():
    card = render.Card()
    luffy = Leader(1, "OP09-061", "Monkey.D.Luffy", "OP09", ("Purple", "Black"))
    name_x = card.leader_line(100, 200, luffy, 32, 600, identity, portrait=60)
    assert name_x == 100 + 60 + render.PORTRAIT_GAP
    img = card.img
    top, bottom = img.getpixel((130, 171)), img.getpixel((130, 228))  # the frame's top and bottom edges
    assert top == render.CARD_COLORS["Purple"] and bottom == render.CARD_COLORS["Black"]
    face = img.getpixel((130, 200))
    assert face not in (render.BG, render.PANEL_HI)  # the bundled portrait was pasted inside the frame


def test_portrait_without_a_picture_or_leader_is_an_empty_tile():
    card = render.Card()
    card.portrait(10, 10, 60, Leader(9, "OP99-001", "Future", "OP99", ("Red",)))  # no bundled picture
    assert card.img.getpixel((40, 12)) == render.CARD_COLORS["Red"]  # still framed in its colour
    assert card.img.getpixel((40, 40)) == render.PANEL_HI
    card.portrait(100, 10, 60, None)  # no leader at all: no frame
    assert card.img.getpixel((130, 12)) == render.PANEL_HI and card.img.getpixel((130, 40)) == render.PANEL_HI


def test_downloaded_portraits_are_used_too(tmp_path):
    from catalog import portraits

    Image.new("RGB", (160, 160), (200, 30, 160)).save(portraits.cache_dir() / "OP99-002.webp")
    card = render.Card()
    card.portrait(0, 0, 64, Leader(9, "OP99-002", "Newcomer", "OP99", ("Blue",)))
    pixel = card.img.getpixel((32, 32))
    assert all(abs(a - b) <= 8 for a, b in zip(pixel, (200, 30, 160), strict=True))  # WebP is lossy


# ---- header: long titles shrink and wrap, never cut ----------------------------------
def drawn_texts(monkeypatch, card) -> list[tuple[tuple, str, int]]:
    seen = []
    real = card.d.text
    monkeypatch.setattr(
        card.d, "text", lambda xy, s, font, **kw: seen.append((xy, s, font.size)) or real(xy, s, font=font, **kw)
    )
    return seen


def test_a_short_header_keeps_its_place(monkeypatch):
    card = render.Card()
    seen = drawn_texts(monkeypatch, card)
    assert card.header("Sunday locals", "Locals · 2026-10-05") == 260
    assert ((render.PAD, 100), "Sunday locals", 64) in seen
    assert ((render.PAD, 192), "Locals · 2026-10-05", 32) in seen


@pytest.mark.regression
def test_a_long_event_name_wraps_whole_and_pushes_the_card_down(monkeypatch):
    """A realistic name ("Regional Championship…") was cut with "…" at 64 px."""
    name = "Regional Championship Madrid 2026 Day Two Top Cut"
    card = render.Card()
    seen = drawn_texts(monkeypatch, card)
    y = card.header(name, "Regional · 2026-10-05")
    titles = [s for (x, _y), s, size in seen if size >= render.TITLE_MIN and s not in ("TIMTAPPER",)]
    assert " ".join(titles) == name and len(titles) == 2
    assert not any(s.endswith("…") for _xy, s, _size in seen)
    assert y > 260


def test_wrap_shrinks_before_it_wraps():
    room = render.W - 2 * render.PAD
    size, lines = render.Card.wrap("Store championship finals", "ExtraBold", 64, room, min_size=44)
    assert (size, lines) == (64, ["Store championship finals"])
    long = "Store championship finals at the big shop downtown"
    size, lines = render.Card.wrap(long, "ExtraBold", 64, room, min_size=44)
    assert len(lines) == 2 or size < 64
    assert " ".join(lines) == long


def test_wrap_keeps_an_unbreakable_word_on_its_own_line():
    size, lines = render.Card.wrap("W" * 80 + " end", "ExtraBold", 64, 400, min_size=44, max_lines=2)
    assert size == 44 and lines == ["W" * 80, "end"]


def test_wrap_puts_what_does_not_fit_on_the_last_line():
    size, lines = render.Card.wrap(" ".join(["word"] * 60), "Regular", 32, 300, min_size=24, max_lines=2)
    assert size == 24 and len(lines) == 2 and lines[1].count("word") > lines[0].count("word")


def test_wrap_of_an_empty_title_is_one_empty_line():
    assert render.Card.wrap("", "Regular", 32, 300, min_size=24) == (32, [""])


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=40)
@given(st.lists(st.text(st.characters(categories=("L", "N")), min_size=1, max_size=12), min_size=1, max_size=12))
def test_property_wrapped_titles_keep_every_word(words):
    title = " ".join(words)
    room = render.W - 2 * render.PAD
    size, lines = render.Card.wrap(title, "ExtraBold", 64, room, min_size=44)
    assert " ".join(lines).split() == title.split()
    assert render.TITLE_MIN <= size <= 64 and 1 <= len(lines) <= 2


# ---- best of 3 ----------------------------------------------------------------------
def bo3_round(no, *results, top_cut=True):
    kind = "top_cut" if top_cut else "swiss"
    return Round(no, no, 2, 3, kind, "", tuple(Game(n, r) for n, r in enumerate(results, start=1)))


def drawn(monkeypatch) -> list[str]:
    seen = []
    real = render.Card.text
    monkeypatch.setattr(
        render.Card, "text", lambda self, xy, s, size, **kw: seen.append(s) or real(self, xy, s, size, **kw)
    )
    pills = []
    real_pill = render.Card.pill
    monkeypatch.setattr(
        render.Card,
        "pill",
        lambda self, cx, cy, label, fill, **kw: pills.append(label) or real_pill(self, cx, cy, label, fill, **kw),
    )
    return seen, pills


def test_event_card_draws_a_best_of_3s_games_and_score(monkeypatch):
    texts_, pills = drawn(monkeypatch)
    ev = event([Round.single_game(1, 1, 2, "W", True, True), bo3_round(2, "L", "W", "W"), bo3_round(3, "W")])
    assert_card(render.event_card(ev, LEADERS, identity, "Locals"))
    # as in the app: a best of 3's score on its top line, then each game's result on a line of its own
    assert pills == ["W", "2-1", "L", "W", "W", "1-0", "W", "…", "…"]
    assert texts_.count("Game 1") == 2 and "Game 3" in texts_
    # the record counts matches (2-0: the unfinished best of 3 doesn't count), the games beside the rate
    assert "2-0" in texts_ and "100% win rate · games 4-1" in texts_


def test_event_card_names_who_chose_in_a_top_cut_best_of_1(monkeypatch):
    chips = []
    real = render.Card.chip
    monkeypatch.setattr(
        render.Card,
        "chip",
        lambda self, cx, cy, label, fg, **kw: chips.append(label) or real(self, cx, cy, label, fg, **kw),
    )
    rs = [
        Round.single_game(1, 1, 2, "W", True, True, top_cut=True),
        Round.single_game(2, 2, 2, "L", False, False, top_cut=True),
    ]
    assert_card(render.event_card(event(rs), LEADERS, identity, "Locals"))
    assert chips == ["You", "Opp"]  # no die in top cut: who chose, as the app shows it


def test_event_card_without_best_of_3_keeps_the_plain_rate(monkeypatch):
    texts_, _pills = drawn(monkeypatch)
    assert_card(render.event_card(event(rounds(3)), LEADERS, identity, "Locals"))
    assert not [t for t in texts_ if "games" in t]


def test_summary_card_shows_the_games_behind_a_best_of_3(monkeypatch):
    texts_, _pills = drawn(monkeypatch)
    assert_card(render.summary_card("All", summarize([event([bo3_round(1, "L", "W", "W")])]), LEADERS, identity))
    assert "games 2-1" in texts_


def test_event_card_draws_a_bye_and_a_top_cut_number(monkeypatch):
    texts_, pills = drawn(monkeypatch)
    rs = (Round(1, 1, None, 1, "bye"), Round.single_game(2, 2, 2, "W", True, None, top_cut=True))
    assert_card(render.event_card(event(rs), LEADERS, identity, "Locals"))
    assert {"Bye", "Automatic win", "R1", "R2", "TC"} <= set(texts_)
    assert pills == ["W", "W"]


def test_standing_band_names_the_bracket(monkeypatch):
    import dataclasses

    texts_, _pills = drawn(monkeypatch)
    ranked = dataclasses.replace(event(rounds(3)), placement=3, players=32)
    assert_card(render.event_card(ranked, LEADERS, identity, "Locals"))
    assert "TOP 4" in texts_


def test_a_dropped_event_gets_a_band_even_without_a_standing(monkeypatch):
    import dataclasses

    texts_, _pills = drawn(monkeypatch)
    assert_card(render.event_card(dataclasses.replace(event(rounds(2)), dropped=True), LEADERS, identity, "Locals"))
    assert "DROPPED" in texts_


def test_bye_portrait_pastes_the_jester_in_a_gold_frame():
    card = render.Card()
    card.bye_portrait(100, 100, 60)
    assert card.img.getpixel((101, 130)) == render.ACCENT  # the frame
    inside = card.img.crop((105, 105, 155, 155))
    assert len(inside.getcolors(maxcolors=4096) or ()) > 20  # the drawing, not a flat fill


def test_a_best_of_3s_games_line_up_under_it_in_the_apps_columns(monkeypatch):
    """Each game line repeats a best of 1's columns: who chose (You / Opp), turn order, result."""
    chips, pills = [], []
    real_chip, real_pill = render.Card.chip, render.Card.pill
    monkeypatch.setattr(
        render.Card,
        "chip",
        lambda self, cx, cy, label, fg, **kw: chips.append((cx, cy, label)) or real_chip(self, cx, cy, label, fg, **kw),
    )
    monkeypatch.setattr(
        render.Card,
        "pill",
        lambda self, cx, cy, label, fill, **kw: (
            pills.append((cx, cy, label)) or real_pill(self, cx, cy, label, fill, **kw)
        ),
    )
    rs = [Round(1, 1, 2, 3, "top_cut", "", (Game(1, "L", True, True), Game(2, "W", False), Game(3, "W", True)))]
    render.event_card(event(rs), LEADERS, identity, "Locals")
    score, *games = pills
    assert score[2] == "2-1" and [g[2] for g in games] == ["L", "W", "W"]
    assert {g[0] for g in [score, *games]} == {render.RESULT_X}  # one column for the score and every game
    assert [c[2] for c in chips] == ["You", "You", "Opp"]  # seed, then the previous game's loser chose
    assert {c[0] for c in chips} == {render.CHOOSER_X}
    assert [c[1] for c in chips] == [g[1] for g in games] and all(g[1] > score[1] for g in games)  # under it


def test_a_long_event_with_best_of_3s_stops_above_the_footer(monkeypatch):
    texts_, _pills = drawn(monkeypatch)
    panels = []
    real = render.Card.panel
    monkeypatch.setattr(render.Card, "panel", lambda self, box, **kw: panels.append(box) or real(self, box, **kw))
    rs = [bo3_round(i, "W", "L", "W") if i % 2 else Round.single_game(i, i, 2, "W") for i in range(1, 15)]
    assert_card(render.event_card(event(rs), LEADERS, identity, "Locals"))
    more = [t for t in texts_ if t.startswith("+")]
    assert more and all(box[3] <= render.H - 110 for box in panels)  # nothing runs into the footer


def test_rounds_that_fit_are_all_drawn_without_a_more_line(monkeypatch):
    texts_, _pills = drawn(monkeypatch)
    rs = [Round.single_game(1, 1, 2, "W"), bo3_round(2, "W", "W"), Round.single_game(3, 3, 2, "L")]
    assert_card(render.event_card(event(rs), LEADERS, identity, "Locals"))
    assert not [t for t in texts_ if t.startswith("+")] and {"R1", "R2", "R3"} <= set(texts_)


@pytest.mark.regression
def test_an_unreadable_downloaded_portrait_draws_an_empty_tile(caplog):
    """A damaged portrait in the download cache raised out of the renderer, so no card with that leader could be
    shared at all."""
    from catalog import portraits

    (portraits.cache_dir() / "OP99-003.webp").write_bytes(b"not a picture")
    card = render.Card()
    card.portrait(0, 0, 64, Leader(9, "OP99-003", "Damaged", "OP99", ("Green",)))
    assert card.img.getpixel((32, 32)) == render.PANEL_HI
    assert card.img.getpixel((32, 1)) == render.CARD_COLORS["Green"]  # still framed in its colour
    assert "portrait OP99-003.webp unreadable" in caplog.text
