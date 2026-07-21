"""GameRole model: roles selected for a specific game, with per-role counts."""

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

if TYPE_CHECKING:
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
        UniqueConstraint("game_id", "role_id", name="game_role"),
        CheckConstraint("quantity >= 1", name="quantity_positive"),
        CheckConstraint(
            "remaining >= 0 AND remaining <= quantity",
            name="remaining_bounds",
        ),
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # How many of this role are still unassigned. Starts equal to quantity.
    remaining: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="game_roles")
    role: Mapped["Role"] = relationship(back_populates="game_roles")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<GameRole game_id={self.game_id} role_id={self.role_id} "
            f"remaining={self.remaining}/{self.quantity}>"
        )
