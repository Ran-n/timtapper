#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/11 16:23:41.664824
Revised: 2026/10/11 16:27:22.106761

initial schema: catalogue (color, card_set, leader, leader_color), events and matches

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Frozen copies, not imports from db.models: a migration must keep seeding
# exactly what it seeded on the day it was written.
_COLORS = ("Red", "Green", "Blue", "Purple", "Black", "Yellow")
_EVENT_TYPES = ("testing", "locals", "regional", "national", "online", "other")


def upgrade() -> None:
    color = op.create_table(
        "color",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(16), nullable=False, unique=True),
    )
    op.create_table(
        "card_set",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(120)),
    )
    op.create_table(
        "leader",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(24), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("set_id", sa.Integer, sa.ForeignKey("card_set.id")),
    )
    op.create_table(
        "leader_color",
        sa.Column("leader_id", sa.Integer, sa.ForeignKey("leader.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("color_id", sa.Integer, sa.ForeignKey("color.id"), primary_key=True),
    )
    event_type = op.create_table(
        "event_type",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(24), nullable=False, unique=True),
    )
    op.create_table(
        "event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("event_type_id", sa.Integer, sa.ForeignKey("event_type.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("leader_id", sa.Integer, sa.ForeignKey("leader.id")),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.create_table(
        "match",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_no", sa.Integer, nullable=False),
        sa.Column("opponent_leader_id", sa.Integer, sa.ForeignKey("leader.id"), nullable=False),
        sa.Column("result", sa.String(1)),
        sa.Column("went_first", sa.Boolean),
        sa.Column("won_die_roll", sa.Boolean),
        sa.Column("top_cut", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("event_id", "round_no", name="uq_match_event_round"),
        sa.CheckConstraint("result IN ('W', 'L', 'D')", name="ck_match_result"),
        sa.CheckConstraint("round_no >= 1", name="ck_match_round_no"),
    )
    op.create_index("ix_match_opponent_leader_id", "match", ["opponent_leader_id"])
    op.create_index("ix_event_date", "event", ["date"])
    op.bulk_insert(color, [{"id": i, "name": n} for i, n in enumerate(_COLORS, start=1)])
    op.bulk_insert(event_type, [{"id": i, "key": k} for i, k in enumerate(_EVENT_TYPES, start=1)])


def downgrade() -> None:
    op.drop_index("ix_event_date", "event")
    op.drop_index("ix_match_opponent_leader_id", "match")
    for table in ("match", "event", "event_type", "leader_color", "leader", "card_set", "color"):
        op.drop_table(table)
