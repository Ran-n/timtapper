#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 23:54:25.703828
Revised: 2026/10/12 23:54:25.703828

the official event types: Pirates Party, release events, sealed, Heroines Battle, team battles, Store
Championship, Treasure Cup, Flagship Battle, Extra Grand Battle and World Championship join the list;
"online" goes (the OPTCG has no online tier), its events becoming "other"

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# Frozen copies, not imports from db.models: a migration must keep doing exactly what it did the day it was written.
_ADDED = (
    "pirates_party",
    "release",
    "sealed",
    "heroines_battle",
    "team",
    "store_championship",
    "treasure_cup",
    "flagship",
    "extra_battle",
    "worlds",
)
_ONLINE_ID = 5  # seeded by 0001

_event_type = sa.table("event_type", sa.column("id", sa.Integer), sa.column("key", sa.String))


def _move_events_to_other(keys: str) -> None:
    op.execute(
        sa.text(
            "UPDATE event SET event_type_id = (SELECT id FROM event_type WHERE key = 'other') "
            f"WHERE event_type_id IN (SELECT id FROM event_type WHERE key IN ({keys}))"
        )
    )


def upgrade() -> None:
    op.bulk_insert(_event_type, [{"key": key} for key in _ADDED])
    _move_events_to_other("'online'")
    op.execute(sa.text("DELETE FROM event_type WHERE key = 'online'"))


def downgrade() -> None:
    # events that were online stay "other": nothing recorded which ones they were
    _move_events_to_other(", ".join(f"'{key}'" for key in _ADDED))
    op.execute(sa.text(f"DELETE FROM event_type WHERE key IN ({', '.join(repr(k) for k in _ADDED)})"))
    op.bulk_insert(_event_type, [{"id": _ONLINE_ID, "key": "online"}])
