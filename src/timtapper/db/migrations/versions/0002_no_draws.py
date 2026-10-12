#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 16:01:23.868438
Revised: 2026/10/12 16:55:02.335060

no draws: the OPTCG has none (a game that ends drawn is a loss for both players), so stored
draws become losses and the result check allows only W and L

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE match SET result = 'L' WHERE result = 'D'"))
    # SQLite can't alter a constraint in place: batch mode rebuilds the table, rows and all
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("ck_match_result", type_="check")
        batch.create_check_constraint("ck_match_result", "result IN ('W', 'L')")


def downgrade() -> None:
    # draws can't come back: they were stored as losses
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("ck_match_result", type_="check")
        batch.create_check_constraint("ck_match_result", "result IN ('W', 'L', 'D')")
