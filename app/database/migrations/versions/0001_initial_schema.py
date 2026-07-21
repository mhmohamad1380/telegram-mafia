"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00

Creates the full schema: users, roles, games, game_roles, game_players,
role_assignments, game_events — along with the native PostgreSQL enums,
indexes, foreign keys, unique constraints, and check constraints.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --- Enum definitions -------------------------------------------------------

game_status = postgresql.ENUM(
    "CREATING",
    "WAITING_PLAYERS",
    "READY",
    "IN_PROGRESS",
    "FINISHED",
    "CANCELLED",
    name="game_status",
)
role_team = postgresql.ENUM(
    "CITIZEN", "MAFIA", "INDEPENDENT", name="role_team"
)
player_status = postgresql.ENUM(
    "JOINED", "NUMBERED", "ASSIGNED", "LEFT", name="player_status"
)
game_event_type = postgresql.ENUM(
    "GAME_CREATED",
    "ROLES_CONFIGURED",
    "PLAYER_JOINED",
    "PLAYER_LEFT",
    "NUMBER_CHOSEN",
    "ROLE_ASSIGNED",
    "GAME_READY",
    "GAME_STARTED",
    "GAME_FINISHED",
    "GAME_CANCELLED",
    name="game_event_type",
)
role_code = postgresql.ENUM(
    "CITIZEN",
    "DOCTOR",
    "DETECTIVE",
    "SNIPER",
    "PSYCHOLOGIST",
    "IRONCLAD",
    "ARMORED",
    "PRIEST",
    "JUDGE",
    "MAYOR",
    "GUARDIAN",
    "REPORTER",
    "GODFATHER",
    "MAFIA",
    "NATASHA",
    "NEGOTIATOR",
    "BOMBER",
    "LAWYER",
    "KIDNAPPER",
    "JOKER",
    "SERIAL_KILLER",
    "NOSTRADAMUS",
    "FREEMASON",
    name="role_code",
)


def upgrade() -> None:
    bind = op.get_bind()

    # Create enums explicitly (so they exist before table creation).
    game_status.create(bind, checkfirst=True)
    role_team.create(bind, checkfirst=True)
    player_status.create(bind, checkfirst=True)
    game_event_type.create(bind, checkfirst=True)
    role_code.create(bind, checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True
    )

    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "code",
            postgresql.ENUM(name="role_code", create_type=False),
            nullable=False,
        ),
        sa.Column("name_fa", sa.String(length=64), nullable=False),
        sa.Column(
            "team",
            postgresql.ENUM(name="role_team", create_type=False),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)

    # --- games ---
    op.create_table(
        "games",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("creator_id", sa.BigInteger(), nullable=False),
        sa.Column("player_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="game_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "player_count >= 3 AND player_count <= 40",
            name=op.f("ck_games_player_count_range"),
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            name=op.f("fk_games_creator_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
    )
    op.create_index(op.f("ix_games_code"), "games", ["code"], unique=True)
    op.create_index(
        op.f("ix_games_creator_id"), "games", ["creator_id"], unique=False
    )
    op.create_index(op.f("ix_games_status"), "games", ["status"], unique=False)

    # --- game_roles ---
    op.create_table(
        "game_roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity >= 1", name=op.f("ck_game_roles_quantity_positive")),
        sa.CheckConstraint(
            "remaining >= 0 AND remaining <= quantity",
            name=op.f("ck_game_roles_remaining_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_game_roles_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_game_roles_role_id_roles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_roles")),
        sa.UniqueConstraint("game_id", "role_id", name=op.f("uq_game_roles_game_id")),
    )
    op.create_index(
        op.f("ix_game_roles_game_id"), "game_roles", ["game_id"], unique=False
    )
    op.create_index(
        op.f("ix_game_roles_role_id"), "game_roles", ["role_id"], unique=False
    )

    # --- game_players ---
    op.create_table(
        "game_players",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="player_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "number IS NULL OR number >= 1",
            name=op.f("ck_game_players_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_game_players_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_game_players_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_players")),
        sa.UniqueConstraint("game_id", "user_id", name=op.f("uq_game_players_game_id")),
        sa.UniqueConstraint(
            "game_id", "number", name=op.f("uq_game_players_game_id_number")
        ),
    )
    op.create_index(
        op.f("ix_game_players_game_id"), "game_players", ["game_id"], unique=False
    )
    op.create_index(
        op.f("ix_game_players_user_id"), "game_players", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_game_players_status"), "game_players", ["status"], unique=False
    )

    # --- role_assignments ---
    op.create_table(
        "role_assignments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("game_role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_role_assignments_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["game_players.id"],
            name=op.f("fk_role_assignments_player_id_game_players"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["game_role_id"],
            ["game_roles.id"],
            name=op.f("fk_role_assignments_game_role_id_game_roles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignments")),
        sa.UniqueConstraint(
            "player_id", name=op.f("uq_role_assignments_player_id")
        ),
    )
    op.create_index(
        op.f("ix_role_assignments_game_id"),
        "role_assignments",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_assignments_player_id"),
        "role_assignments",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_assignments_game_role_id"),
        "role_assignments",
        ["game_role_id"],
        unique=False,
    )

    # --- game_events ---
    op.create_table(
        "game_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "event_type",
            postgresql.ENUM(name="game_event_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_game_events_game_id_games"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_game_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_events")),
    )
    op.create_index(
        op.f("ix_game_events_game_id"), "game_events", ["game_id"], unique=False
    )
    op.create_index(
        op.f("ix_game_events_event_type"),
        "game_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("game_events")
    op.drop_table("role_assignments")
    op.drop_table("game_players")
    op.drop_table("game_roles")
    op.drop_table("games")
    op.drop_table("roles")
    op.drop_table("users")

    bind = op.get_bind()
    role_code.drop(bind, checkfirst=True)
    game_event_type.drop(bind, checkfirst=True)
    player_status.drop(bind, checkfirst=True)
    role_team.drop(bind, checkfirst=True)
    game_status.drop(bind, checkfirst=True)
