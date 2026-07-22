"""Add scenario_code to games.

Introduces the data-driven scenario (game mode) reference on each game. The
column is non-null with a server default of ``"classic"`` so existing rows are
back-filled to the classic scenario transparently.

Revision ID: 0005_scenario_code
Revises: 0004_custom_roles
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_scenario_code"
down_revision = "0004_custom_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "scenario_code",
            sa.String(length=32),
            nullable=False,
            server_default="classic",
        ),
    )


def downgrade() -> None:
    op.drop_column("games", "scenario_code")
