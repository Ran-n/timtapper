#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 16:26:54.210886
Revised: 2026/10/12 16:55:02.481745

event placement and player count: where you finished and how many entered (both optional)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("event") as batch:
        batch.add_column(sa.Column("placement", sa.Integer))
        batch.add_column(sa.Column("players", sa.Integer))
        batch.create_check_constraint("ck_event_placement", "placement IS NULL OR placement >= 1")
        batch.create_check_constraint("ck_event_players", "players IS NULL OR players >= 1")
        batch.create_check_constraint(
            "ck_event_place_in_field", "placement IS NULL OR players IS NULL OR placement <= players"
        )


def downgrade() -> None:
    with op.batch_alter_table("event") as batch:
        batch.drop_constraint("ck_event_place_in_field", type_="check")
        batch.drop_constraint("ck_event_players", type_="check")
        batch.drop_constraint("ck_event_placement", type_="check")
        batch.drop_column("players")
        batch.drop_column("placement")
