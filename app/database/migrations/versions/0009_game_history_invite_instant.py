"""Game history, invite links, and instant role mode.

* Adds ``started_at`` / ``finished_at`` timestamps to ``games``.
* Adds ``INSTANT_ROLE`` to the ``role_mode`` enum.
* Adds ``winner_team`` nullable column to ``games`` (set when game finishes).
* Adds ``game_result`` nullable column to ``game_players`` (WIN/LOSS/UNKNOWN).

Revision ID: 0009_game_history_invite_instant
Revises: 0008_role_mode
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_game_history_invite_instant"
down_revision: str | None = "0008_role_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add INSTANT_ROLE to the role_mode enum (PostgreSQL ALTER TYPE).
    bind.execute(
        sa.text("ALTER TYPE role_mode ADD VALUE IF NOT EXISTS 'INSTANT_ROLE'")
    )

    # 2. Add game_result enum.
    game_result_enum = sa.Enum("WIN", "LOSS", "UNKNOWN", name="game_result")
    game_result_enum.create(bind, checkfirst=True)

    # 3. Add timestamps + winner_team to games.
    op.add_column(
        "games",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("winner_team", sa.String(32), nullable=True),
    )

    # 4. Add per-player result column.
    op.add_column(
        "game_players",
        sa.Column(
            "game_result",
            game_result_enum,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("game_players", "game_result")
    op.drop_column("games", "winner_team")
    op.drop_column("games", "finished_at")
    op.drop_column("games", "started_at")
    sa.Enum(name="game_result").drop(op.get_bind(), checkfirst=True)
    # Note: removing enum values from PostgreSQL requires recreating the type;
    # we leave INSTANT_ROLE in the enum on downgrade (safe, unused).
