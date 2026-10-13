#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 00:30:07.042312
Revised: 2026/10/13 08:13:33.986576

The share cards, pinned: each card rendered from fixed data is compared with a checked-in image (golden/*.png),
so a change to how a card looks fails here until the new image is looked at and approved. Pillow draws them the
same everywhere it has raqm text layout, so these run in the default suite. After an intended change, rerun with
TIMTAPPER_UPDATE_BASELINES=1, open every rewritten image, and commit it.
"""

import datetime as dt
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops, features

from catalog.repository import Leader
from events.repository import Event, Game, Round
from share import render
from stats.compute import Filters, matchups, summarize

pytestmark = pytest.mark.snapshot

GOLDEN = Path(__file__).resolve().parent / "golden"
UPDATE = os.environ.get("TIMTAPPER_UPDATE_BASELINES") == "1"
PIXEL_TOLERANCE = 48  # a channel difference past this counts as changed (font hinting jitter stays well below)
MAX_CHANGED = 400  # of 1080 x 1350: a moved or redrawn element changes thousands

LEADERS = {
    1: Leader(1, "OP09-061", "Monkey.D.Luffy", "OP09", ("Purple", "Black")),
    2: Leader(2, "OP09-001", "Shanks", "OP09", ("Red",)),
    3: Leader(3, "OP01-060", "Donquixote Doflamingo", "OP01", ("Blue",)),
    4: Leader(4, "OP07-038", "Boa Hancock", "OP07", ("Blue",)),
}
EN = lambda s: s  # noqa: E731


def swiss(no, opp, result, first, die):
    return Round.single_game(no, no, opp, result, first, die)


EVENT = Event(
    1,
    "Regional Championship Madrid — Day 2",
    "regional",
    dt.date(2026, 10, 10),
    1,
    rounds=(
        Round(1, 1, None, 1, "bye"),
        swiss(2, 2, "W", True, True),
        swiss(3, 3, "L", False, False),
        swiss(4, 4, "W", True, None),
        Round(5, 5, 3, 3, "top_cut", "", (Game(1, "L", True, True), Game(2, "W", False), Game(3, "W", True))),
    ),
    placement=3,
    players=64,
    set_code="OP16",
)
OTHER = Event(
    2,
    "Thursday locals",
    "locals",
    dt.date(2026, 10, 6),
    1,
    rounds=tuple(
        swiss(i, opp, result, first, die)
        for i, (opp, result, first, die) in enumerate(
            [(2, "W", True, True), (3, "W", False, False), (4, "L", True, False), (2, "W", False, True)], start=10
        )
    ),
)


def check(name: str, path: Path, tmp_path: Path) -> None:
    # the goldens are laid out by raqm (kerning, shaping); Pillow's basic layout moves every glyph, so without it
    # every card "changes" — say why instead. Pillow's wheels bundle raqm but load fribidi from the system.
    if not features.check("raqm"):
        pytest.fail("Pillow has no raqm text layout: install the system's fribidi (Debian: libfribidi0)")
    actual = Image.open(path).convert("RGB")
    golden = GOLDEN / f"{name}.png"
    if UPDATE:
        GOLDEN.mkdir(exist_ok=True)
        actual.save(golden, optimize=True)
        pytest.skip(f"{name}.png rewritten: look at it before committing")
    assert golden.is_file(), f"no golden {golden.name}; create it with TIMTAPPER_UPDATE_BASELINES=1"
    expected = Image.open(golden).convert("RGB")
    assert actual.size == expected.size
    r, g, b = ImageChops.difference(actual, expected).split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > PIXEL_TOLERANCE else 0)
    changed = worst.histogram()[255]
    if changed > MAX_CHANGED:
        actual.save(tmp_path / f"{name}-actual.png")
        worst.save(tmp_path / f"{name}-diff.png")
        pytest.fail(f"{name}: {changed} pixels changed (box {worst.getbbox()}); see {tmp_path}")


def test_event_card_matches_golden(tmp_path):
    """A bye, Swiss rounds, a top-cut best of 3, the standing with its bracket and a title long enough to wrap."""
    check("event-card", render.event_card(EVENT, LEADERS, EN, "Regional"), tmp_path)


def test_matchups_card_matches_golden(tmp_path):
    events = [EVENT, OTHER]
    scope = "Playing Monkey.D.Luffy"
    card = render.matchups_card(scope, summarize(events), matchups(events), LEADERS, EN, LEADERS[1])
    check("matchups-card", card, tmp_path)


def test_summary_card_matches_golden(tmp_path):
    events = [EVENT, OTHER]
    check(
        "summary-card", render.summary_card("All leaders · OP16", summarize(events, Filters()), LEADERS, EN), tmp_path
    )


def test_event_card_in_spanish_matches_golden(tmp_path):
    from i18n import event_type_label, translator

    _ = translator("es")
    check("event-card-es", render.event_card(EVENT, LEADERS, _, event_type_label(_, "regional")), tmp_path)
