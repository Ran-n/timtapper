#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.379720
Revised: 2026/10/11 16:27:23.016497

Pillow-rendered share cards (1080x1350, the 4:5 portrait every social app
displays uncropped). Fixed dark "open sea" palette independent of the app
theme, so a shared image looks the same to whoever receives it. No card art
is drawn — leaders are identified by name, code and OPTCG color stripes,
which keeps the cards offline-renderable and clear of Bandai's artwork.

All text arrives already translated through the `_` callable; numbers come
from stats.compute so the cards always agree with the stats screen.
"""

import time
from collections.abc import Callable
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from catalog.repository import Leader
from core.logging import get_logger
from core.paths import ASSETS_DIR, temp_dir
from events.repository import Event
from stats.compute import Matchup, Record, Summary, percent, record_of

_log = get_logger("share.render")

W, H = 1080, 1350
PAD = 64
_FONTS = ASSETS_DIR / "fonts"

BG = (13, 22, 38)
PANEL = (24, 37, 60)
PANEL_HI = (33, 50, 80)
FG = (236, 240, 245)
DIM = (146, 162, 186)
ACCENT = (245, 190, 60)
RESULT_COLORS = {"W": (72, 199, 120), "L": (235, 82, 82), "D": (160, 162, 175)}
CARD_COLORS = {
    "Red": (214, 48, 49),
    "Green": (39, 174, 96),
    "Blue": (41, 128, 205),
    "Purple": (142, 68, 173),
    "Black": (70, 70, 74),
    "Yellow": (241, 196, 15),
}
UNKNOWN_COLOR = (90, 98, 112)

Translate = Callable[[str], str]


@cache
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONTS / f"Poppins-{weight}.ttf"), size)


class Card:
    """A canvas plus the drawing primitives every card shares."""

    def __init__(self) -> None:
        self.img = Image.new("RGB", (W, H), BG)
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, s: str, size: int, *, weight="Regular", fill=FG, anchor="la", max_w: int | None = None) -> int:
        """Draw text (ellipsized to max_w) and return its drawn width."""
        f = font(weight, size)
        if max_w is not None and f.getlength(s) > max_w:
            while s and f.getlength(s + "…") > max_w:
                s = s[:-1]
            s = s.rstrip() + "…"
        self.d.text(xy, s, font=f, fill=fill, anchor=anchor)
        return int(f.getlength(s))

    @staticmethod
    def fit(s: str, weight: str, size: int, max_w: int, min_size: int = 40) -> int:
        """Largest font size <= size at which `s` fits in max_w (big numbers shrink, never truncate)."""
        while size > min_size and font(weight, size).getlength(s) > max_w:
            size -= 4
        return size

    def panel(self, box, fill=PANEL, radius=28) -> None:
        self.d.rounded_rectangle(box, radius=radius, fill=fill)

    def color_bar(self, x: int, y: int, w: int, h: int, colors: tuple[str, ...]) -> None:
        """Vertical stripes, one per leader color (rounded as a whole)."""
        palette = [CARD_COLORS.get(c, UNKNOWN_COLOR) for c in colors] or [UNKNOWN_COLOR]
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=min(w, h) // 2, fill=255)
        stripes = Image.new("RGB", (w, h))
        sd = ImageDraw.Draw(stripes)
        for i, rgb in enumerate(palette):
            sd.rectangle((0, h * i // len(palette), w, h * (i + 1) // len(palette)), fill=rgb)
        self.img.paste(stripes, (x, y), mask)

    def pill(self, cx: int, cy: int, label: str, fill, *, size=30, min_w=64, fg=BG) -> None:
        f = font("SemiBold", size)
        w = max(min_w, int(f.getlength(label)) + 32)
        h = size + 22
        self.d.rounded_rectangle((cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2), radius=h // 2, fill=fill)
        self.d.text((cx, cy), label, font=f, fill=fg, anchor="mm")

    def bar(self, x: int, y: int, w: int, h: int, rate: float | None) -> None:
        self.d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=PANEL_HI)
        if rate:
            fill_w = max(h, int(w * rate))
            color = RESULT_COLORS["W"] if rate >= 0.5 else RESULT_COLORS["L"]
            self.d.rounded_rectangle((x, y, x + fill_w, y + h), radius=h // 2, fill=color)

    def header(self, title: str, subtitle: str) -> int:
        self.text((PAD, 58), "TIMTAPPER", 28, weight="ExtraBold", fill=ACCENT)
        self.text((PAD, 100), title, 64, weight="ExtraBold", max_w=W - 2 * PAD)
        self.text((PAD, 192), subtitle, 32, fill=DIM, max_w=W - 2 * PAD)
        return 260

    def footer(self, _: Translate) -> None:
        self.text((W // 2, H - 48), _("Tracked with timtapper · One Piece TCG"), 24, fill=DIM, anchor="mm")

    def leader_line(self, x: int, y: int, leader: Leader | None, size: int, max_w: int, _: Translate) -> None:
        """Color bar + name (+ code underneath), vertically centred on y."""
        colors = leader.colors if leader else ()
        name = leader.name if leader else _("Unknown leader")
        self.color_bar(x, y - size // 2 - 6, 14, size + 12, colors)
        self.text((x + 30, y), name, size, weight="SemiBold", anchor="lm", max_w=max_w - 30)

    def save(self, kind: str) -> Path:
        path = temp_dir() / f"timtapper-{kind}-{time.time_ns()}.png"
        self.img.save(path, "PNG", optimize=True)
        _log.info("rendered %s card -> %s", kind, path.name)
        return path


def _record_block(card: Card, x_right: int, y: int, rec: Record, _: Translate) -> None:
    size = Card.fit(rec.label(), "ExtraBold", 120, 400)
    card.text((x_right, y + (120 - size)), rec.label(), size, weight="ExtraBold", anchor="ra")
    card.text((x_right, y + 168), _("{rate} win rate").format(rate=percent(rec.win_rate)), 32, fill=DIM, anchor="ra")


def _split_text(rec: Record) -> str:
    return f"{rec.label()} · {percent(rec.win_rate)}" if rec.games else "—"


def event_card(event: Event, leaders: dict[int, Leader], _: Translate, type_label: str) -> Path:
    card = Card()
    y = card.header(event.name, f"{type_label} · {event.date.isoformat()}")
    rec = record_of(event)

    card.panel((PAD, y, W - PAD, y + 230))
    card.text((PAD + 40, y + 36), _("Playing"), 28, fill=DIM)
    card.leader_line(PAD + 40, y + 120, leaders.get(event.leader_id), 44, 460, _)
    own = leaders.get(event.leader_id)
    if own:
        card.text((PAD + 70, y + 168), own.code, 26, fill=DIM)
    _record_block(card, W - PAD - 40, y + 20, rec, _)
    y += 270

    rounds = list(event.rounds)
    avail = H - 110 - y
    row_h = max(52, min(84, avail // max(1, len(rounds))))
    shown = rounds if len(rounds) * row_h <= avail else rounds[: avail // row_h - 1]
    for r in shown:
        cy = y + row_h // 2
        card.panel((PAD, y + 4, W - PAD, y + row_h - 4), radius=18)
        label = _("TC") if r.top_cut else f"R{r.round_no}"
        card.text((PAD + 28, cy), label, 28, weight="SemiBold", fill=ACCENT if r.top_cut else DIM, anchor="lm")
        card.leader_line(PAD + 110, cy, leaders.get(r.opponent_leader_id), 32, 560, _)
        if r.went_first is not None:
            card.text((W - PAD - 150, cy), _("1st") if r.went_first else _("2nd"), 28, fill=DIM, anchor="rm")
        if r.result:
            card.pill(W - PAD - 70, cy, r.result, RESULT_COLORS[r.result], min_w=72)
        else:
            card.pill(W - PAD - 70, cy, "…", PANEL_HI, min_w=72, fg=DIM)
        y += row_h
    if len(shown) < len(rounds):
        card.text(
            (W // 2, y + row_h // 2),
            _("+{n} more").format(n=len(rounds) - len(shown)),
            28,
            fill=DIM,
            anchor="mm",
        )
    if not rounds:
        card.text((W // 2, y + 80), _("No rounds logged yet"), 32, fill=DIM, anchor="mm")
    card.footer(_)
    return card.save("event")


def matchups_card(scope: str, summary: Summary, ms: list[Matchup], leaders: dict[int, Leader], _: Translate) -> Path:
    card = Card()
    y = card.header(_("Matchups"), f"{scope} · {summary.record.label()} · {percent(summary.record.win_rate)}")

    card.text((PAD, y), _("Opponent"), 26, fill=DIM)
    card.text((W - PAD - 330, y), _("W-L"), 26, fill=DIM, anchor="ra")
    card.text((W - PAD, y), _("Win %"), 26, fill=DIM, anchor="ra")
    y += 50
    avail = H - 190 - y
    row_h = 76
    max_rows = avail // row_h
    for m in ms[:max_rows]:
        cy = y + row_h // 2
        card.panel((PAD, y + 4, W - PAD, y + row_h - 4), radius=18)
        card.leader_line(PAD + 24, cy, leaders.get(m.opponent_leader_id), 30, 520, _)
        card.text((W - PAD - 330, cy), m.record.label(), 30, weight="SemiBold", anchor="rm")
        card.bar(W - PAD - 300, cy - 8, 150, 16, m.record.win_rate)
        card.text((W - PAD - 24, cy), percent(m.record.win_rate), 30, weight="SemiBold", anchor="rm")
        y += row_h
    if not ms:
        card.text((W // 2, y + 80), _("No games logged yet"), 32, fill=DIM, anchor="mm")
    elif len(ms) > max_rows:
        card.text((W // 2, y + 26), _("+{n} more").format(n=len(ms) - max_rows), 26, fill=DIM, anchor="mm")

    fy = H - 160
    card.text((PAD, fy), _("Going 1st"), 26, fill=DIM)
    card.text((PAD, fy + 36), _split_text(summary.first), 32, weight="SemiBold")
    card.text((W - PAD, fy), _("Going 2nd"), 26, fill=DIM, anchor="ra")
    card.text((W - PAD, fy + 36), _split_text(summary.second), 32, weight="SemiBold", anchor="ra")
    card.footer(_)
    return card.save("matchups")


def _tile(card: Card, box, label: str, value: str, _: Translate) -> None:
    card.panel(box, radius=24)
    x0, y0, _x1, _y1 = box
    card.text((x0 + 32, y0 + 26), label, 26, fill=DIM)
    card.text((x0 + 32, y0 + 66), value, 38, weight="SemiBold")


def _matchup_tile(card: Card, box, label: str, m: Matchup | None, leaders: dict[int, Leader], _: Translate) -> None:
    card.panel(box, radius=24)
    x0, y0, x1, _y1 = box
    card.text((x0 + 32, y0 + 26), label, 26, fill=DIM)
    if m is None:
        card.text((x0 + 32, y0 + 70), _("Not enough games"), 30, fill=DIM)
        return
    card.leader_line(x0 + 32, y0 + 96, leaders.get(m.opponent_leader_id), 30, x1 - x0 - 64, _)
    card.text((x0 + 62, y0 + 136), f"{m.record.label()} · {percent(m.record.win_rate)}", 28, fill=DIM)


def summary_card(scope: str, summary: Summary, leaders: dict[int, Leader], _: Translate) -> Path:
    card = Card()
    events_txt = _("1 event") if summary.events == 1 else _("{n} events").format(n=summary.events)
    y = card.header(_("Overall record"), f"{scope} · {events_txt}")

    card.panel((PAD, y, W - PAD, y + 260))
    card.text((PAD + 40, y + 30), _("Record"), 28, fill=DIM)
    size = Card.fit(summary.record.label(), "ExtraBold", 120, 500)
    card.text((PAD + 40, y + 70 + (120 - size)), summary.record.label(), size, weight="ExtraBold")
    card.text((W - PAD - 40, y + 30), _("Win rate"), 28, fill=DIM, anchor="ra")
    card.text(
        (W - PAD - 40, y + 70), percent(summary.record.win_rate), 120, weight="ExtraBold", fill=ACCENT, anchor="ra"
    )
    y += 290

    half = (W - 2 * PAD - 24) // 2
    rows = [
        ((_("Going 1st"), _split_text(summary.first)), (_("Going 2nd"), _split_text(summary.second))),
        (
            (_("Won the die roll"), _split_text(summary.die_won)),
            (_("Lost the die roll"), _split_text(summary.die_lost)),
        ),
    ]
    for left, right in rows:
        _tile(card, (PAD, y, PAD + half, y + 140), *left, _)
        _tile(card, (W - PAD - half, y, W - PAD, y + 140), *right, _)
        y += 164
    _matchup_tile(card, (PAD, y, PAD + half, y + 180), _("Best matchup"), summary.best, leaders, _)
    _matchup_tile(card, (W - PAD - half, y, W - PAD, y + 180), _("Worst matchup"), summary.worst, leaders, _)
    y += 210

    card.text((PAD, y), _("Recent form"), 26, fill=DIM)
    y += 48
    size, gap = 72, 14
    for i, result in enumerate(summary.recent):
        x = PAD + i * (size + gap)
        card.d.rounded_rectangle((x, y, x + size, y + size), radius=16, fill=RESULT_COLORS[result])
        card.d.text((x + size // 2, y + size // 2), result, font=font("ExtraBold", 34), fill=BG, anchor="mm")
    if not summary.recent:
        card.text((PAD, y + 20), _("No games logged yet"), 30, fill=DIM)
    card.footer(_)
    return card.save("summary")
