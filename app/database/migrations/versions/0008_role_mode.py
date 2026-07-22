"""Add per-game role assignment mode (manual vs. automatic).

Introduces the ``role_mode`` enum column on ``games`` so a game can either use
the classic manual, turn-based role draw (the default, unchanged behaviour) or
assign a random role automatically the instant a player joins.

* ``MANUAL_ROLE_SELECTION`` — default; existing flow.
* ``AUTO_ROLE_ASSIGNMENT``  — auto-assign on join (owner test flow / opt-in).

The column is created with a server default of ``MANUAL_ROLE_SELECTION`` so all
pre-existing rows keep their current semantics.

Revision ID: 0008_role_mode
Revises: 0007_lobby_live_message
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_role_mode"
down_revision: str | None = "0007_lobby_live_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_MODE_ENUM = sa.Enum(
    "MANUAL_ROLE_SELECTION",
    "AUTO_ROLE_ASSIGNMENT",
    name="role_mode",
)


def upgrade() -> None:
    bind = op.get_bind()
    _ROLE_MODE_ENUM.create(bind, checkfirst=True)
    op.add_column(
        "games",
        sa.Column(
            "role_mode",
            _ROLE_MODE_ENUM,
            nullable=False,
            server_default="MANUAL_ROLE_SELECTION",
        ),
    )


def downgrade() -> None:
    op.drop_column("games", "role_mode")
    _ROLE_MODE_ENUM.drop(op.get_bind(), checkfirst=True)
