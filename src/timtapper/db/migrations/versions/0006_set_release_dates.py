#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/13 08:59:20.460453
Revised: 2026/10/13 08:59:31.269137

sets keep their English release date, so a new event can be put in the set that was out on its date. Existing sets
start without one; the bundled catalogue fills them in on the next start.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("card_set") as batch:
        batch.add_column(sa.Column("release_date", sa.Date))


def downgrade() -> None:
    with op.batch_alter_table("card_set") as batch:
        batch.drop_column("release_date")
