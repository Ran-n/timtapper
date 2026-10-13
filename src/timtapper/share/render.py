#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:42.379720
Revised: 2026/10/13 13:15:07.289924

Pillow-rendered share cards (1080x1350, the 4:5 portrait every social app
displays uncropped). Fixed dark "open sea" palette independent of the app
theme, so a shared image looks the same to whoever receives it. Leaders show
as their portrait (the app's small face crop of the card art, bundled or
already downloaded, so rendering stays offline) framed in their OPTCG colors,
next to their name.

All text arrives already translated through the `_` callable; numbers come
from stats.compute so the cards always agree with the stats screen.
"""

import time
from collections.abc import Callable
from functools import cache
from itertools import accumulate
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from catalog import portraits
from catalog.repository import Leader
from core import card_colors
from core.card_colors import rgb
from core.die import CORNER_RADIUS, DIE_PIPS, LOST_PIPS, PIP_DIAMETER, WON_PIPS
from core.logging import get_logger
from core.paths import ASSETS_DIR, temp_file
from events.repository import Event, Round
from i18n import bracket_label
from stats.compute import Matchup, Record, Summary, games_record_of, percent, record_of

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
RESULT_COLORS = {"W": (72, 199, 120), "L": (235, 82, 82)}
# the app's card colours (core.card_colors), as the RGB tuples Pillow draws in
CARD_COLORS = {name: rgb(hex_color) for name, hex_color in card_colors.CARD_COLORS.items()}

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

    @staticmethod
    def wrap(s: str, weight: str, size: int, max_w: int, min_size: int, max_lines: int = 2) -> tuple[int, list[str]]:
        """The font size and lines that show `s` whole in max_w: one line, shrinking down to min_size, before
        wrapping between words into up to `max_lines`. Only text too long even then keeps an overflowing last
        line (which `text` ellipsizes as a last resort)."""
        sizes = range(size, min_size - 1, -4)
        for allowed in range(1, max_lines + 1):
            for candidate in sizes:
                f = font(weight, candidate)
                lines = _word_lines(s, f, max_w)
                if len(lines) <= allowed and all(f.getlength(line) <= max_w for line in lines):
                    return candidate, lines
        lines = _word_lines(s, font(weight, min_size), max_w)
        return min_size, [*lines[: max_lines - 1], " ".join(lines[max_lines - 1 :])]

    def panel(self, box, fill=PANEL, radius=28) -> None:
        self.d.rounded_rectangle(box, radius=radius, fill=fill)

    def portrait(self, x: int, y: int, side: int, leader: Leader | None) -> None:
        """The leader's face in a frame of its colors (equal bands, top to bottom), as the app shows it.
        No leader: an empty tile. No picture yet (a leader added after this release): an empty framed tile."""
        radius = side // 4
        if leader is None:
            self.d.rounded_rectangle((x, y, x + side - 1, y + side - 1), radius=radius, fill=PANEL_HI)
            return
        self.img.paste(_stripes(side, side, leader.colors), (x, y), _rounded_mask(side, side, radius))
        border = max(3, side // 16)
        inner = side - 2 * border
        self.img.paste(
            _face(leader.code, inner), (x + border, y + border), _rounded_mask(inner, inner, radius - border)
        )

    def bye_portrait(self, x: int, y: int, side: int) -> None:
        """A bye's stand-in for a portrait, the same as the app's: the joker's hat in a gold frame."""
        border = max(3, side // 16)
        inner = side - 2 * border
        self.d.rounded_rectangle((x, y, x + side - 1, y + side - 1), radius=side // 4, fill=ACCENT)
        face = Image.new("RGB", (inner, inner), PANEL_HI)
        with Image.open(BYE_JOKER) as joker:
            hat = joker.convert("RGBA").resize((inner, inner), Image.Resampling.LANCZOS)
        face.paste(hat, (0, 0), hat)
        self.img.paste(face, (x + border, y + border), _rounded_mask(inner, inner, side // 4 - border))

    def die(self, cx: int, cy: int, side: int, won: bool) -> None:
        """The roll as the app shows it: a six on green when you won it, a one on red when you lost it."""
        x0, y0 = cx - side // 2, cy - side // 2
        fill = RESULT_COLORS["W" if won else "L"]
        self.d.rounded_rectangle((x0, y0, x0 + side, y0 + side), radius=round(side * CORNER_RADIUS), fill=fill)
        r = side * PIP_DIAMETER / 2
        for px, py in DIE_PIPS[WON_PIPS if won else LOST_PIPS]:
            x, y = x0 + px * side, y0 + py * side
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=BG)

    def pill(self, cx: int, cy: int, label: str, fill, *, size=30, min_w=64, fg=BG) -> None:
        f = font("SemiBold", size)
        w = max(min_w, int(f.getlength(label)) + 32)
        h = size + 22
        self.d.rounded_rectangle((cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2), radius=h // 2, fill=fill)
        self.d.text((cx, cy), label, font=f, fill=fg, anchor="mm")

    def keycap(self, cx: int, cy: int, digit: int, side: int) -> None:
        """Went first or second as the app shows it: a rounded square with the number knocked out of it (1 / 2)."""
        x0, y0 = cx - side // 2, cy - side // 2
        self.d.rounded_rectangle((x0, y0, x0 + side, y0 + side), radius=round(side * 0.22), fill=FG)
        self.d.text((cx, cy), str(digit), font=font("ExtraBold", round(side * 0.7)), fill=PANEL, anchor="mm")

    def chip(self, cx: int, cy: int, label: str, fg, *, height: int = 40) -> None:
        """A small neutral badge with `label` in `fg`: who chose the turn order where no die decided it."""
        f = font("SemiBold", 22)
        w = max(56, int(f.getlength(label)) + 20)
        self.d.rounded_rectangle(
            (cx - w // 2, cy - height // 2, cx + w // 2, cy + height // 2), radius=height // 3, fill=PANEL_HI
        )
        self.d.text((cx, cy), label, font=f, fill=fg, anchor="mm")

    def bar(self, x: int, y: int, w: int, h: int, rate: float | None) -> None:
        self.d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=PANEL_HI)
        if rate:
            fill_w = max(h, int(w * rate))
            color = RESULT_COLORS["W"] if rate >= 0.5 else RESULT_COLORS["L"]
            self.d.rounded_rectangle((x, y, x + fill_w, y + h), radius=h // 2, fill=color)

    def header(self, title: str, subtitle: str, leader: Leader | None = None) -> int:
        """Logo, title and subtitle; with `leader` (stats narrowed to the one you played), its framed
        portrait sits top right and the texts keep clear of it."""
        # the app's mark beside the wordmark, so a shared image says where it came from
        with Image.open(LOGO_MARK) as mark:
            logo = mark.convert("RGBA").resize((LOGO_SIZE, LOGO_SIZE), Image.Resampling.LANCZOS)
        self.img.paste(logo, (PAD, 72 - LOGO_SIZE // 2), logo)
        self.text((PAD + LOGO_SIZE + 12, 58), "TIMTAPPER", 28, weight="ExtraBold", fill=ACCENT)
        room = W - 2 * PAD
        if leader is not None:
            self.portrait(W - PAD - HEADER_PORTRAIT, HEADER_PORTRAIT_Y, HEADER_PORTRAIT, leader)
            room -= HEADER_PORTRAIT + PORTRAIT_GAP
        # a long title (an event's own name) shrinks, then wraps, and pushes everything below it down
        y = 100
        size, lines = Card.wrap(title, "ExtraBold", TITLE_SIZE, room, min_size=TITLE_MIN)
        for line in lines:
            self.text((PAD, y), line, size, weight="ExtraBold", max_w=room)
            y += round(size * TITLE_LEADING)
        size, lines = Card.wrap(subtitle, "Regular", SUBTITLE_SIZE, room, min_size=SUBTITLE_MIN)
        for i, line in enumerate(lines):
            self.text((PAD, y + i * SUBTITLE_LINE), line, size, fill=DIM, max_w=room)
        return y + (len(lines) - 1) * SUBTITLE_LINE + 68

    def footer(self, _: Translate) -> None:
        self.text((W // 2, H - 48), _("Tracked with timtapper · One Piece TCG"), 24, fill=DIM, anchor="mm")

    def leader_line(
        self, x: int, y: int, leader: Leader | None, size: int, max_w: int, _: Translate, portrait: int | None = None
    ) -> int:
        """Framed portrait + name, vertically centred on y; returns where the name starts. The portrait is
        `portrait` px (default 1.75x the text size). A long name shrinks to fit rather than being cut (down to
        3/5 of `size`; only a name too long even then gets an ellipsis)."""
        side = portrait or round(size * 1.75)
        self.portrait(x, y - side // 2, side, leader)
        name_x = x + side + PORTRAIT_GAP
        name = leader.name if leader else _("Unknown leader")
        room = max_w - side - PORTRAIT_GAP
        fitted = Card.fit(name, "SemiBold", size, room, min_size=size * 3 // 5)
        self.text((name_x, y), name, fitted, weight="SemiBold", anchor="lm", max_w=room)
        return name_x

    def save(self, kind: str) -> Path:
        path = temp_file(f"timtapper-{kind}-{time.time_ns()}.png")
        self.img.save(path, "PNG", optimize=True)
        _log.info("rendered %s card -> %s", kind, path.name)
        return path


PORTRAIT_GAP = 20
# the columns every game's badges sit in, right to left: result, turn order, who chose it (as in the app)
RESULT_X, TURN_X, CHOOSER_X = W - PAD - 70, W - PAD - 150, W - PAD - 228
TITLE_SIZE, TITLE_MIN = 64, 44
TITLE_LEADING = 1.44  # line pitch as a multiple of the size: 92 px at 64, where the subtitle always sat
SUBTITLE_SIZE, SUBTITLE_MIN = 32, 24
SUBTITLE_LINE = 44
LOGO_MARK = ASSETS_DIR / "logo_mark.png"  # drawn by scripts/make_icon.py, the same mark the app shows
BYE_JOKER = ASSETS_DIR / "bye_joker.png"  # drawn by scripts/make_bye_joker.py, the same jester the app shows
LOGO_SIZE = 52
STANDING_H = 110
# the own leader's portrait in a stats card's header: from the wordmark's top to the subtitle's foot
HEADER_PORTRAIT = 172
HEADER_PORTRAIT_Y = 54


def _stripes(w: int, h: int, colors: tuple[str, ...]) -> Image.Image:
    """Equal horizontal bands, one per leader color, top to bottom (unknown colors: the neutral grey)."""
    palette = [rgb(hue) for hue in card_colors.leader_hues(colors)]
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for i, band in enumerate(palette):
        draw.rectangle((0, h * i // len(palette), w, h * (i + 1) // len(palette)), fill=band)
    return img


def _face(code: str, side: int) -> Image.Image:
    """`code`'s portrait as a side x side square; an empty one when there is no picture, or it can't be read (a
    damaged download shouldn't stop the whole card from being shared)."""
    path = portraits.local_file(code)
    if path is not None:
        try:
            with Image.open(path) as src:
                return src.convert("RGB").resize((side, side), Image.Resampling.LANCZOS)
        except OSError as exc:  # UnidentifiedImageError is one too
            _log.warning("portrait %s unreadable, drawn empty: %s", path.name, exc)
    return Image.new("RGB", (side, side), PANEL_HI)


def _word_lines(s: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """`s` broken between words into lines no wider than max_w (a single word wider than that gets its own)."""
    lines: list[str] = []
    for word in s.split():
        if lines and f.getlength(f"{lines[-1]} {word}") <= max_w:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines or [""]


def _rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    return mask


def _standing_band(card: Card, y: int, event: Event, _: Translate) -> int:
    """Where you finished, big and gold in a band of its own: the first thing a shared result is read for, with
    its bracket ("Top 4", "Dropped") at the right end. Returns the y below it."""
    placement, players = event.placement, event.players
    card.panel((PAD, y, W - PAD, y + STANDING_H), fill=PANEL_HI)
    cy = y + STANDING_H // 2
    x = PAD + 40
    if placement is not None:
        x += card.text((x, cy), f"#{placement}", 64, weight="ExtraBold", fill=ACCENT, anchor="lm") + 20
        rest = _("of {players} players").format(players=players) if players is not None else _("place")
    elif players is not None:
        rest = _("{players} players").format(players=players)
    else:
        rest = ""
    card.text((x, cy + 4), rest, 34, weight="SemiBold", fill=FG if placement is None else DIM, anchor="lm")
    bracket = bracket_label(_, placement, event.dropped)
    if bracket:
        card.text((W - PAD - 40, cy + 4), bracket.upper(), 34, weight="ExtraBold", fill=ACCENT, anchor="rm")
    return y + STANDING_H


def _game_badges(card: Card, r: Round, game_no: int, cy: int, h: int, _: Translate, *, pill: int = 30) -> None:
    """One game in the app's columns, read left to right: who chose the turn order (the die in Swiss game 1,
    else You / Opp), 1st/2nd, W/L. A best of 1's row and each game line of a best of 3 share these columns."""
    game = r.game(game_no)
    chose = r.chose_turn(game_no)
    if chose is not None:
        if r.die_decided(game_no):
            card.die(CHOOSER_X, cy, min(42, h - 24), chose)
        else:
            card.chip(CHOOSER_X, cy, _("You") if chose else _("Opp"), ACCENT if chose else DIM, height=min(40, h - 16))
    if game.went_first is not None:
        card.keycap(TURN_X, cy, 1 if game.went_first else 2, min(38, h - 22))
    _result_pill(card, RESULT_X, cy, game.result, game.result or "…", size=pill)


def _result_pill(card: Card, cx: int, cy: int, result: str | None, label: str, *, size: int = 30) -> None:
    fill, fg = (RESULT_COLORS[result], BG) if result else (PANEL_HI, DIM)
    card.pill(cx, cy, label, fill, size=size, min_w=round(size * 2.4), fg=fg)


def _round_heights(rounds: list[Round], row_h: int) -> list[int]:
    """Each round's height: one row, plus a line per game for a best of 3 (its games are listed under it)."""
    game_h = _game_line_h(row_h)
    return [row_h + (r.best_of * game_h if r.best_of == 3 and not r.bye else 0) for r in rounds]


def _game_line_h(row_h: int) -> int:
    return max(44, round(row_h * 0.66))


def _draw_round(card: Card, r: Round, y: int, row_h: int, leaders: dict[int, Leader], _: Translate) -> int:
    """One round in a panel, laid out as the app's round row; returns its height."""
    (height,) = _round_heights([r], row_h)
    card.panel((PAD, y + 4, W - PAD, y + height - 4), radius=18)
    cy = y + row_h // 2
    # the round number always; a top-cut round carries "TC" under it, as in the app
    card.text(
        (PAD + 28, cy - 12 if r.top_cut else cy),
        f"R{r.round_no}",
        28,
        weight="SemiBold",
        fill=ACCENT if r.top_cut else DIM,
        anchor="lm",
    )
    if r.top_cut:
        card.text((PAD + 28, cy + 18), _("TC"), 20, weight="SemiBold", fill=ACCENT, anchor="lm")
    side = min(60, row_h - 16)
    if r.bye:
        card.bye_portrait(PAD + 100, cy - side // 2, side)
        name_x = PAD + 100 + side + PORTRAIT_GAP
        card.text((name_x, cy - 14), _("Bye"), 32, weight="SemiBold", anchor="lm")
        card.text((name_x, cy + 20), _("Automatic win"), 24, fill=DIM, anchor="lm")
        _result_pill(card, RESULT_X, cy, "W", "W")
        return height
    card.leader_line(PAD + 100, cy, leaders.get(r.opponent_leader_id), 32, 520, _, portrait=side)
    if r.best_of == 1:
        _game_badges(card, r, 1, cy, row_h, _)
        return height
    # a best of 3: the score on the top line, then each game on its own line under it
    _result_pill(card, RESULT_X, cy, r.result, f"{r.wins}-{r.losses}")
    game_h = _game_line_h(row_h)
    for n in range(1, r.best_of + 1):
        line_cy = y + row_h + (n - 1) * game_h + game_h // 2 - 4
        card.text((PAD + 100, line_cy), _("Game {n}").format(n=n), 24, weight="SemiBold", fill=DIM, anchor="lm")
        _game_badges(card, r, n, line_cy, game_h, _, pill=24)
    return height


def _record_block(card: Card, x_right: int, y: int, rec: Record, games: Record, _: Translate) -> None:
    """Match record and win rate; the game record too once a best of 3 makes it differ."""
    size = Card.fit(rec.label(), "ExtraBold", 120, 400)
    card.text((x_right, y + (120 - size)), rec.label(), size, weight="ExtraBold", anchor="ra")
    line = _("{rate} win rate").format(rate=percent(rec.win_rate))
    if games != rec:
        line += " · " + _("games {record}").format(record=games.label())
    card.text((x_right, y + 168), line, 32, fill=DIM, anchor="ra")


def _split_text(rec: Record) -> str:
    return f"{rec.label()} · {percent(rec.win_rate)}" if rec.games else "—"


def event_card(event: Event, leaders: dict[int, Leader], _: Translate, type_label: str) -> Path:
    card = Card()
    y = card.header(event.name, f"{type_label} · {event.date.isoformat()}")
    rec = record_of(event)

    card.panel((PAD, y, W - PAD, y + 230))
    card.text((PAD + 40, y + 36), _("Playing"), 28, fill=DIM)
    own = leaders.get(event.leader_id)
    name_x = card.leader_line(PAD + 40, y + 130, own, 44, 520, _, portrait=96)
    if own:
        card.text((name_x, y + 176), own.code, 26, fill=DIM)
    _record_block(card, W - PAD - 40, y + 20, rec, games_record_of(event), _)
    y += 250
    if event.placement is not None or event.players is not None or event.dropped:
        y = _standing_band(card, y, event, _)
    y += 20

    rounds = list(event.rounds)
    avail = H - 110 - y
    # the tallest rows that fit every round; at the smallest, as many as fit and a "+n more" line
    row_h = next((h for h in range(84, 51, -4) if sum(_round_heights(rounds, h)) <= avail), 52)
    heights = _round_heights(rounds, row_h)
    shown = rounds
    if sum(heights) > avail:  # as many as fit with a row's room left for the "+n more" line
        shown = rounds[: sum(1 for total in accumulate(heights) if total <= avail - row_h)]
    for r in shown:
        y += _draw_round(card, r, y, row_h, leaders, _)
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


def matchups_card(
    scope: str,
    summary: Summary,
    ms: list[Matchup],
    leaders: dict[int, Leader],
    _: Translate,
    own: Leader | None = None,
) -> Path:
    """`own`: the one leader these stats are narrowed to, shown in the header; None for all leaders."""
    card = Card()
    y = card.header(_("Matchups"), f"{scope} · {summary.record.label()} · {percent(summary.record.win_rate)}", own)

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
        card.leader_line(PAD + 20, cy, leaders.get(m.opponent_leader_id), 30, 540, _, portrait=row_h - 18)
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
    name_x = card.leader_line(x0 + 32, y0 + 110, leaders.get(m.opponent_leader_id), 30, x1 - x0 - 64, _, portrait=72)
    card.text((name_x, y0 + 146), f"{m.record.label()} · {percent(m.record.win_rate)}", 28, fill=DIM)


def summary_card(
    scope: str, summary: Summary, leaders: dict[int, Leader], _: Translate, own: Leader | None = None
) -> Path:
    """`own`: the one leader these stats are narrowed to, shown in the header; None for all leaders."""
    card = Card()
    events_txt = _("1 event") if summary.events == 1 else _("{n} events").format(n=summary.events)
    y = card.header(_("Overall record"), f"{scope} · {events_txt}", own)

    card.panel((PAD, y, W - PAD, y + 260))
    card.text((PAD + 40, y + 30), _("Record"), 28, fill=DIM)
    size = Card.fit(summary.record.label(), "ExtraBold", 120, 500)
    card.text((PAD + 40, y + 70 + (120 - size)), summary.record.label(), size, weight="ExtraBold")
    card.text((W - PAD - 40, y + 30), _("Win rate"), 28, fill=DIM, anchor="ra")
    card.text(
        (W - PAD - 40, y + 70), percent(summary.record.win_rate), 120, weight="ExtraBold", fill=ACCENT, anchor="ra"
    )
    if summary.games != summary.record:  # best-of-3 rounds: the games behind the matches
        card.text((PAD + 40, y + 206), _("games {record}").format(record=summary.games.label()), 28, fill=DIM)
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
    # tall enough for the 72 px portrait with the record under the name
    _matchup_tile(card, (PAD, y, PAD + half, y + 200), _("Best matchup"), summary.best, leaders, _)
    _matchup_tile(card, (W - PAD - half, y, W - PAD, y + 200), _("Worst matchup"), summary.worst, leaders, _)
    y += 228

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
