"""GameRole model: roles selected for a specific game, with per-role counts.

A game-role slot references **either** a global catalog :class:`Role`
(``role_id``) **or** a user-owned :class:`CustomRole` (``custom_role_id``) —
exactly one of the two is set (enforced by a check constraint). Resolver
properties (:pyattr:`display_name`, :pyattr:`team`, :pyattr:`description`,
:pyattr:`role_code`) expose a uniform interface so the assignment, roster, and
composition layers don't care which kind of role backs the slot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import RoleCode, RoleTeam

if TYPE_CHECKING:
    from app.models.custom_role import CustomRole
    from app.models.game import Game
    from app.models.role import Role


class GameRole(Base, IntPKMixin, TimestampMixin):
    """A role included in a game's configuration.

    ``quantity`` is how many copies of this role exist in the game (e.g. 2 simple
    mafia). ``remaining`` is decremented as the role gets assigned to players,
    enabling atomic "is this role still available?" checks.
    """

    __tablename__ = "game_roles"
    __table_args__ = (
        # Uniqueness is enforced separately per source so a game can hold at most
        # one row per catalog role and one row per custom role.
        UniqueConstraint("game_id", "role_id", name="game_role"),
        UniqueConstraint("game_id", "custom_role_id", name="game_custom_role"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        CheckConstraint(
            "remaining >= 0 AND remaining <= quantity",
            name="remaining_bounds",
        ),
        # Exactly one role source must be set.
        CheckConstraint(
            "(role_id IS NOT NULL) <> (custom_role_id IS NOT NULL)",
            name="exactly_one_role_source",
        ),
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    custom_role_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("custom_roles.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # How many of this role are still unassigned. Starts equal to quantity.
    remaining: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="game_roles")
    role: Mapped["Role | None"] = relationship(back_populates="game_roles")
    custom_role: Mapped["CustomRole | None"] = relationship(
        back_populates="game_roles"
    )

    # --- Uniform resolvers (catalog role OR custom role) --------------------

    @property
    def is_custom(self) -> bool:
        """Whether this slot is backed by a user-owned custom role."""
        return self.custom_role_id is not None

    @property
    def display_name(self) -> str:
        """Persian display name, regardless of the backing source."""
        if self.custom_role is not None:
            return self.custom_role.name_fa
        return self.role.name_fa if self.role is not None else "?"

    @property
    def team(self) -> RoleTeam:
        """Team/alignment, regardless of the backing source."""
        if self.custom_role is not None:
            return self.custom_role.team
        return self.role.team if self.role is not None else RoleTeam.CITIZEN

    @property
    def description(self) -> str | None:
        """Optional description, regardless of the backing source."""
        if self.custom_role is not None:
            return self.custom_role.description
        return self.role.description if self.role is not None else None

    @property
    def role_code(self) -> RoleCode | None:
        """Catalog role code, or ``None`` for custom roles (they have no code)."""
        return self.role.code if self.role is not None else None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        src = (
            f"custom_role_id={self.custom_role_id}"
            if self.is_custom
            else f"role_id={self.role_id}"
        )
        return (
            f"<GameRole game_id={self.game_id} {src} "
            f"remaining={self.remaining}/{self.quantity}>"
        )
