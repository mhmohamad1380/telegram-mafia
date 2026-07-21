"""turn-based flow: add join_order, selected_number, role_assigned_at

Revision ID: 0002_turn_based
Revises: 0001_initial
Create Date: 2025-01-02 00:00:00

Adds the columns backing the strictly sequential (FIFO) player turn:

* ``join_order``       — 1-based order in which players joined; drives the turn.
* ``selected_number``  — audit mirror of the seat number chosen on the turn.
* ``role_assigned_at`` — timestamp of the role assignment (NULL until assigned).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_turn_based"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "game_players",
        sa.Column("join_order", sa.Integer(), nullable=True),
    )
    op.add_column(
        "game_players",
        sa.Column("selected_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "game_players",
        sa.Column(
            "role_assigned_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_game_players_join_order"),
        "game_players",
        ["join_order"],
        unique=False,
    )

    # Backfill join_order for any pre-existing active rows, ordered by creation,
    # so existing lobbies remain playable after the upgrade.
    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY game_id ORDER BY created_at, id
                ) AS rn
            FROM game_players
            WHERE status <> 'LEFT'
        )
        UPDATE game_players AS gp
        SET join_order = ordered.rn
        FROM ordered
        WHERE gp.id = ordered.id;
        """
    )
    # Mirror any already-chosen seat numbers into selected_number.
    op.execute(
        "UPDATE game_players SET selected_number = number WHERE number IS NOT NULL;"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_game_players_join_order"), table_name="game_players")
    op.drop_column("game_players", "role_assigned_at")
    op.drop_column("game_players", "selected_number")
    op.drop_column("game_players", "join_order")
