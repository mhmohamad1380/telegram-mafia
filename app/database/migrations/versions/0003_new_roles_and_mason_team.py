"""new roles + mason team

Revision ID: 0003_new_roles
Revises: 0002_turn_based
Create Date: 2025-01-03 00:00:00

Extends the ``role_code`` and ``role_team`` PostgreSQL enums to support the
additional Iranian-mafia roles and the Mason group:

* ``role_team``: adds ``MASON`` (a city-aligned faction available only in large
  games).
* ``role_code``: adds the new citizen roles (افسونگر/ENCHANTER, ناتو/NATO,
  تکاور/COMMANDO, نگهبان/WATCHMAN, تفنگدار/GUNNER) and the Mason group
  (رئیس ماسون/MASON_LEADER, ماسون/MASON, معمار/ARCHITECT).

New enum values are additive, so the actual role *rows* are inserted
idempotently by the application's startup seeding (see ``app/database/seed.py``),
keeping the migration focused on the schema/enum change.

Note: ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block on
PostgreSQL, so each addition is committed autonomously via ``COMMIT``. We guard
each with ``IF NOT EXISTS`` to keep the migration safely re-runnable.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_new_roles"
down_revision: str | None = "0002_turn_based"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# New enum values to add. (enum type name, value)
_NEW_TEAMS: tuple[str, ...] = ("MASON",)
_NEW_ROLE_CODES: tuple[str, ...] = (
    "ENCHANTER",
    "NATO",
    "COMMANDO",
    "WATCHMAN",
    "GUNNER",
    "MASON_LEADER",
    "MASON",
    "ARCHITECT",
)


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction block.
    with op.get_context().autocommit_block():
        for value in _NEW_TEAMS:
            op.execute(
                f"ALTER TYPE role_team ADD VALUE IF NOT EXISTS '{value}'"
            )
        for value in _NEW_ROLE_CODES:
            op.execute(
                f"ALTER TYPE role_code ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type without a
    # full type rebuild (drop/recreate + column rewrite), which would be
    # destructive if any rows use the new values. As these additions are
    # backward-compatible, the downgrade is intentionally a no-op.
    pass
