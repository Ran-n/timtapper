#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.873250
Revised: 2026/10/11 16:27:22.376052

ORM schema. BCNF: every non-key attribute depends on a whole candidate key
and nothing else —
- color / event_type: lookup tables (key: id, candidate: name/key).
- card_set: code -> name.
- leader: code -> name, set; its colors live in leader_color (multi-valued).
- event: id -> name, type, date, own leader, notes.
- match: id and (event_id, round_no) are both candidate keys; every other
  column depends on either of them, never on a part or a non-key.
Records, win rates and matchup tables are derived (stats/), never stored.
"""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Official OPTCG color order — also the seeded ids, so ORDER BY id is display order.
COLORS = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
EVENT_TYPES = ("testing", "locals", "regional", "national", "online", "other")
RESULTS = ("W", "L", "D")


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
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    event_type_id: Mapped[int] = mapped_column(ForeignKey("event_type.id"))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    leader_id: Mapped[int | None] = mapped_column(ForeignKey("leader.id"))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    event_type: Mapped[EventType] = relationship()
    leader: Mapped[Leader | None] = relationship()
    matches: Mapped[list[Match]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Match.round_no"
    )


class Match(Base):
    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint("event_id", "round_no", name="uq_match_event_round"),
        CheckConstraint("result IN ('W', 'L', 'D')", name="ck_match_result"),
        CheckConstraint("round_no >= 1", name="ck_match_round_no"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    round_no: Mapped[int]
    opponent_leader_id: Mapped[int] = mapped_column(ForeignKey("leader.id"), index=True)
    # NULL = round still being played; such rounds never count in stats
    result: Mapped[str | None] = mapped_column(String(1))
    went_first: Mapped[bool | None]
    won_die_roll: Mapped[bool | None]
    top_cut: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    event: Mapped[Event] = relationship(back_populates="matches")
    opponent_leader: Mapped[Leader] = relationship()
