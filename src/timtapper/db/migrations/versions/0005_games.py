#!/usr/bin/env python3
"""
Authors: Ran# <ran.hash@proton.me>
Created: 2026/10/12 23:54:26.174204
Revised: 2026/10/13 13:15:07.473556

rounds: a round is Swiss, top cut or a bye (no opponent, won without playing),
played as a best of 1 or 3 whose games each keep their result, turn order and who chose it; events note the set
they were played in and whether you dropped. Every existing round becomes a best of 1 (Swiss or top cut, as it
was flagged) whose only game keeps the round's result, turn order and die roll (the die winner chose the turn
order); the round itself keeps no result, it is derived from its games.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("match.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_no", sa.Integer, nullable=False),
        sa.Column("result", sa.String(1)),
        sa.Column("went_first", sa.Boolean),
        sa.Column("chose_turn", sa.Boolean),
        sa.UniqueConstraint("match_id", "game_no", name="uq_game_match_no"),
        sa.CheckConstraint("game_no BETWEEN 1 AND 3", name="ck_game_no"),
        sa.CheckConstraint("result IN ('W', 'L')", name="ck_game_result"),
    )
    op.execute(
        sa.text(
            "INSERT INTO game (match_id, game_no, result, went_first, chose_turn) "
            "SELECT id, 1, result, went_first, won_die_roll FROM match"
        )
    )
    with op.batch_alter_table("match") as batch:
        batch.add_column(sa.Column("kind", sa.String(8), nullable=False, server_default="swiss"))
        batch.add_column(sa.Column("best_of", sa.Integer, nullable=False, server_default="1"))
    op.execute(sa.text("UPDATE match SET kind = CASE WHEN top_cut THEN 'top_cut' ELSE 'swiss' END"))
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("ck_match_result", type_="check")
        batch.drop_column("result")
        batch.drop_column("went_first")
        batch.drop_column("won_die_roll")
        batch.drop_column("top_cut")
        batch.alter_column("opponent_leader_id", existing_type=sa.Integer, nullable=True)
        batch.create_check_constraint("ck_match_best_of", "best_of IN (1, 3)")
        batch.create_check_constraint("ck_match_kind", "kind IN ('swiss', 'top_cut', 'bye')")
        batch.create_check_constraint("ck_match_bye_has_no_opponent", "(kind = 'bye') = (opponent_leader_id IS NULL)")
    with op.batch_alter_table("event") as batch:
        batch.add_column(sa.Column("dropped", sa.Boolean, nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("set_id", sa.Integer, sa.ForeignKey("card_set.id", name="fk_event_set")))


def downgrade() -> None:
    # a round goes back to one game, game 1's (games 2 and 3 are lost); byes go, having no opponent
    with op.batch_alter_table("event") as batch:
        batch.drop_column("set_id")
        batch.drop_column("dropped")
    op.execute(sa.text("DELETE FROM match WHERE kind = 'bye'"))
    with op.batch_alter_table("match") as batch:
        batch.drop_constraint("ck_match_bye_has_no_opponent", type_="check")
        batch.drop_constraint("ck_match_kind", type_="check")
        batch.drop_constraint("ck_match_best_of", type_="check")
        batch.alter_column("opponent_leader_id", existing_type=sa.Integer, nullable=False)
        batch.add_column(sa.Column("result", sa.String(1)))
        batch.add_column(sa.Column("went_first", sa.Boolean))
        batch.add_column(sa.Column("won_die_roll", sa.Boolean))
        batch.add_column(sa.Column("top_cut", sa.Boolean, nullable=False, server_default=sa.false()))
        batch.create_check_constraint("ck_match_result", "result IN ('W', 'L')")
    op.execute(sa.text("UPDATE match SET top_cut = (kind = 'top_cut')"))
    for column, source in (("result", "result"), ("went_first", "went_first"), ("won_die_roll", "chose_turn")):
        op.execute(
            sa.text(
                f"UPDATE match SET {column} = (SELECT {source} FROM game WHERE game.match_id = match.id "
                "AND game.game_no = 1)"
            )
        )
    with op.batch_alter_table("match") as batch:
        batch.drop_column("kind")
        batch.drop_column("best_of")
    op.drop_table("game")
