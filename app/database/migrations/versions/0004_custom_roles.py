"""custom roles

Revision ID: 0004_custom_roles
Revises: 0003_new_roles
Create Date: 2025-01-04 00:00:00

Adds user-owned, private custom roles:

* new ``custom_roles`` table (owner-scoped name/team/description + soft-delete),
* ``game_roles.custom_role_id`` so a game slot can reference a custom role,
* ``game_roles.role_id`` relaxed to NULLABLE (a slot is backed by *either* a
  catalog role or a custom role), plus the accompanying uniqueness and
  "exactly one source" check constraint.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004_custom_roles"
down_revision: str | None = "0003_new_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- custom_roles table -------------------------------------------------
    # Reuse the existing native ``role_team`` enum (already created in 0001 and
    # extended in 0003). ``postgresql.ENUM(create_type=False)`` binds the column
    # to that existing type WITHOUT emitting a second ``CREATE TYPE`` — unlike
    # ``sa.Enum(create_type=False)``, whose flag the dialect ignores during
    # ``create_table`` (it would raise ``DuplicateObjectError``).
    role_team = postgresql.ENUM(
        "CITIZEN",
        "MAFIA",
        "INDEPENDENT",
        "MASON",
        name="role_team",
        create_type=False,
    )

    op.create_table(
        "custom_roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("name_fa", sa.String(length=64), nullable=False),
        sa.Column("team", role_team, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_custom_roles_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_roles")),
        sa.UniqueConstraint("owner_id", "name_fa", name="owner_role_name"),
    )
    op.create_index(
        op.f("ix_custom_roles_owner_id"),
        "custom_roles",
        ["owner_id"],
        unique=False,
    )

    # --- game_roles: support custom-role slots ------------------------------
    # Relax role_id to nullable (a slot may instead reference a custom role).
    op.alter_column(
        "game_roles",
        "role_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.add_column(
        "game_roles",
        sa.Column("custom_role_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_game_roles_custom_role_id_custom_roles"),
        "game_roles",
        "custom_roles",
        ["custom_role_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_game_roles_custom_role_id"),
        "game_roles",
        ["custom_role_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "game_custom_role",
        "game_roles",
        ["game_id", "custom_role_id"],
    )
    op.create_check_constraint(
        "exactly_one_role_source",
        "game_roles",
        "(role_id IS NOT NULL) <> (custom_role_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_game_roles_exactly_one_role_source"),
        "game_roles",
        type_="check",
    )
    op.drop_constraint("game_custom_role", "game_roles", type_="unique")
    op.drop_index(op.f("ix_game_roles_custom_role_id"), table_name="game_roles")
    op.drop_constraint(
        op.f("fk_game_roles_custom_role_id_custom_roles"),
        "game_roles",
        type_="foreignkey",
    )
    op.drop_column("game_roles", "custom_role_id")
    # Restore role_id NOT NULL (safe: pre-feature rows always had it set).
    op.alter_column(
        "game_roles",
        "role_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )

    op.drop_index(op.f("ix_custom_roles_owner_id"), table_name="custom_roles")
    op.drop_table("custom_roles")
