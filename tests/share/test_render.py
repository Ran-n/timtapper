#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:44.477606
Revised: 2026/10/12 16:55:00.872711
"""

import datetime as dt

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from catalog.repository import Leader
from events.repository import Event, Round
from share import render
from stats.compute import games, matchups, summarize

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
    return [Round(i, i, (i % 4) + 1, result, i % 2 == 0, None, i > n - 2) for i in range(1, n + 1)]


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
    ev = event([Round(1, 1, 99, None), Round(2, 2, 4, "L")], name="X" * 200, leader=None)
    assert_card(render.event_card(ev, LEADERS, identity, "Locals"))


def test_event_card_huge_record_shrinks():
    assert render.Card.fit("120-80-10", "ExtraBold", 120, 400) < 120
    assert render.Card.fit("3-1", "ExtraBold", 120, 400) == 120
    assert_card(render.event_card(event(rounds(150, "W")), LEADERS, identity, "Locals"))


def test_matchups_card():
    evs = [event(rounds(12)), event(rounds(5, "L"))]
    s, ms = summarize(evs), matchups(games(evs))
    assert_card(render.matchups_card("All leaders", s, ms, LEADERS, identity))


def test_matchups_card_empty_and_overflow():
    assert_card(render.matchups_card("All leaders", summarize([]), [], LEADERS, identity))
    many = [Round(i, i, 1000 + i, "W") for i in range(1, 40)]
    evs = [event(many)]
    assert_card(render.matchups_card("x", summarize(evs), matchups(games(evs)), LEADERS, identity))


def test_summary_card():
    evs = [event(rounds(12)), event([Round(9, 1, 3, "L"), Round(10, 2, 3, "L"), Round(11, 3, 3, "L")])]
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
    lambda rs: [Round(i, i, opp, res, first, None, top) for i, (opp, res, first, top) in enumerate(rs, start=1)]
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
    assert_card(render.matchups_card(scope, s, matchups(games(evs)), LEADERS, identity))


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
    rs = [Round(1, 1, 2, "W", True, True), Round(2, 2, 3, "L", False, False), Round(3, 3, 2, None)]
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
