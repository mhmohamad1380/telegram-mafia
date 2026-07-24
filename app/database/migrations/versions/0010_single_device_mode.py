"""Add SINGLE_DEVICE ("pass-the-phone") value to the role_mode enum.

In single-device mode the whole game is played on the creator's phone: there is
no join code and no remote joining. Each player in turn taps a free seat number
on the creator's screen, privately sees their random role, then passes the phone
on. This migration only extends the PostgreSQL enum; no columns change.

Revision ID: 0010_single_device_mode
Revises: 0009_game_history_invite_instant
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_single_device_mode"
down_revision: str | None = "0009_game_history_invite_instant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("ALTER TYPE role_mode ADD VALUE IF NOT EXISTS 'SINGLE_DEVICE'")
    )


def downgrade() -> None:
    # Note: removing enum values from PostgreSQL requires recreating the type;
    # we leave SINGLE_DEVICE in the enum on downgrade (safe, unused).
    pass
