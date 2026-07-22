"""Add Capo-scenario role codes to the role_code enum.

The Capo (کاپو) scenario introduces six new city roles that back its special
"gunner" mechanics. These values must exist in the native ``role_code`` enum
before the application's startup seeding can insert the corresponding role rows
(otherwise the seed fails with ``invalid input value for enum role_code``).

New enum values are additive; the actual role *rows* are inserted idempotently
by ``app/database/seed.py`` at startup, so this migration only extends the enum.

Note: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block on
PostgreSQL, so the additions are committed autonomously via an autocommit block.
Each is guarded with ``IF NOT EXISTS`` to keep the migration re-runnable.

Revision ID: 0006_capo_role_codes
Revises: 0005_scenario_code
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_capo_role_codes"
down_revision: str | None = "0005_scenario_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# New citizen role codes introduced by the Capo scenario.
_NEW_ROLE_CODES: tuple[str, ...] = (
    "SUSPECT",
    "ARMORSMITH",
    "APOTHECARY",
    "HEIR",
    "KADKHODA",
    "CITY_TRUSTED",
)


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block.
    with op.get_context().autocommit_block():
        for value in _NEW_ROLE_CODES:
            op.execute(
                f"ALTER TYPE role_code ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL cannot remove enum values without a destructive type rebuild.
    # These additions are backward-compatible, so the downgrade is a no-op.
    pass
