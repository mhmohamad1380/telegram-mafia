"""Persist each player's live lobby message for real-time synchronization.

Adds two nullable columns to ``game_players`` so the live-sync service can edit a
waiting player's lobby screen *in place* (via ``editMessageText`` /
``editMessageReplyMarkup``) the instant the shared lobby state changes — instead
of requiring the player to tap a refresh button:

* ``lobby_chat_id``     — Telegram chat id of the player's lobby message.
* ``lobby_message_id``  — Telegram message id of that message.

Both are NULL until the player's lobby screen is first rendered. They are purely
presentational bookkeeping and do not affect any existing behaviour.

Revision ID: 0007_lobby_live_message
Revises: 0006_capo_role_codes
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_lobby_live_message"
down_revision: str | None = "0006_capo_role_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "game_players",
        sa.Column("lobby_chat_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "game_players",
        sa.Column("lobby_message_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_players", "lobby_message_id")
    op.drop_column("game_players", "lobby_chat_id")
