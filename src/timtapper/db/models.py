#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.873250
Revised: 2026/10/13 22:57:42.101759

ORM schema. BCNF: every non-key attribute depends on a whole candidate key
and nothing else —
- color / event_type: lookup tables (key: id, candidate: name/key).
- card_set: code -> name, release date.
- leader: code -> name, set; its colors live in leader_color (multi-valued).
- event: id -> name, type, date, own leader, notes, placement, players, dropped, set.
- match (a round): id and (event_id, round_no) are both candidate keys; every other
  column depends on either of them, never on a part or a non-key.
- game: id and (match_id, game_no) are candidate keys likewise. A round's result is
  derived from its games (2 wins of 3, or 1 of 1), so it is not stored anywhere.
Records, win rates and matchup tables are derived (stats/), never stored.
"""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Official OPTCG color order — also the seeded ids, so ORDER BY id is display order.
COLORS = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
# Bandai's official event tiers, casual to world level, plus your own testing and "other" (display order)
EVENT_TYPES = (
    "testing",
    "pirates_party",
    "locals",
    "release",
    "sealed",
    "heroines_battle",
    "team",
    "store_championship",
    "treasure_cup",
    "flagship",
    "extra_battle",
    "regional",
    "national",
    "worlds",
    "other",
)
RESULTS = ("W", "L")  # no draws in the OPTCG: a drawn game is a loss for both players
EVENT_NAME_MAX = 120  # SQLite doesn't enforce String lengths, so the repository and backup import do
# the most a placement or player count can be (the biggest events draw a few thousand): past SQLite's 64-bit
# integers a typed or imported number would crash the write instead of being turned down
COUNT_MAX = 100_000


class Base(DeclarativeBase):
    pass


class Color(Base):
    __tablename__ = "color"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), unique=True)


class CardSet(Base):
    __tablename__ = "card_set"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    release_date: Mapped[dt.date | None] = mapped_column(Date)  # its English release; None: not known yet


class LeaderColor(Base):
    __tablename__ = "leader_color"
    leader_id: Mapped[int] = mapped_column(ForeignKey("leader.id", ondelete="CASCADE"), primary_key=True)
    color_id: Mapped[int] = mapped_column(ForeignKey("color.id"), primary_key=True)


class Leader(Base):
    __tablename__ = "leader"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    set_id: Mapped[int | None] = mapped_column(ForeignKey("card_set.id"))

    card_set: Mapped[CardSet | None] = relationship()
    colors: Mapped[list[Color]] = relationship(secondary="leader_color", order_by=Color.id)


class EventType(Base):
    __tablename__ = "event_type"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(24), unique=True)


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (
        CheckConstraint("placement IS NULL OR placement >= 1", name="ck_event_placement"),
        CheckConstraint("players IS NULL OR players >= 1", name="ck_event_players"),
        CheckConstraint("placement IS NULL OR players IS NULL OR placement <= players", name="ck_event_place_in_field"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(EVENT_NAME_MAX))
    event_type_id: Mapped[int] = mapped_column(ForeignKey("event_type.id"))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    leader_id: Mapped[int | None] = mapped_column(ForeignKey("leader.id"))
    notes: Mapped[str] = mapped_column(Text, default="")
    placement: Mapped[int | None]  # final standing (1 = won the event); unknown or not applicable: NULL
    players: Mapped[int | None]  # how many players entered
    dropped: Mapped[bool] = mapped_column(default=False)  # you left before the event ended
    set_id: Mapped[int | None] = mapped_column(ForeignKey("card_set.id"))  # the format: the newest set allowed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    event_type: Mapped[EventType] = relationship()
    card_set: Mapped[CardSet | None] = relationship()
    leader: Mapped[Leader | None] = relationship()
    matches: Mapped[list[Match]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Match.round_no"
    )


class Match(Base):
    """A round: Swiss or top cut against one opponent, played as a best of 1 or 3, or a bye (no opponent, no
    games, won). Its result is derived from its games (a bye's from its kind), never stored."""

    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint("event_id", "round_no", name="uq_match_event_round"),
        CheckConstraint("round_no >= 1", name="ck_match_round_no"),
        CheckConstraint("best_of IN (1, 3)", name="ck_match_best_of"),
        CheckConstraint("kind IN ('swiss', 'top_cut', 'bye')", name="ck_match_kind"),
        CheckConstraint("(kind = 'bye') = (opponent_leader_id IS NULL)", name="ck_match_bye_has_no_opponent"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    round_no: Mapped[int]
    kind: Mapped[str] = mapped_column(String(8), default="swiss")
    opponent_leader_id: Mapped[int | None] = mapped_column(ForeignKey("leader.id"), index=True)
    best_of: Mapped[int] = mapped_column(default=1)
    notes: Mapped[str] = mapped_column(Text, default="")

    event: Mapped[Event] = relationship(back_populates="matches")
    opponent_leader: Mapped[Leader | None] = relationship()
    games: Mapped[list[Game]] = relationship(
        back_populates="match", cascade="all, delete-orphan", order_by="Game.game_no"
    )


class Game(Base):
    """One game of a round. Every column is optional: NULL means not played yet, or not noted."""

    __tablename__ = "game"
    __table_args__ = (
        UniqueConstraint("match_id", "game_no", name="uq_game_match_no"),
        CheckConstraint("game_no BETWEEN 1 AND 3", name="ck_game_no"),
        CheckConstraint("result IN ('W', 'L')", name="ck_game_result"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id", ondelete="CASCADE"))
    game_no: Mapped[int]
    result: Mapped[str | None] = mapped_column(String(1))
    went_first: Mapped[bool | None]
    # you chose the turn order: in game 1 by winning the die (Swiss) or the higher seed (top cut); NULL in a later
    # game means "as the rules say" (the previous game's loser chose), a value there overrides them
    chose_turn: Mapped[bool | None]

    match: Mapped[Match] = relationship(back_populates="games")
