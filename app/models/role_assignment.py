"""RoleAssignment model: links a game player to their randomly assigned role."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.game_player import GamePlayer
    from app.models.game_role import GameRole


class RoleAssignment(Base, IntPKMixin, TimestampMixin):
    """The role a specific player received in a game.

    Kept as a dedicated table (rather than a column on ``game_players``) so the
    assignment lifecycle is explicit and auditable, and so a player row can exist
    before a role is assigned. One assignment per player is enforced by a unique
    constraint on ``player_id``.
    """

    __tablename__ = "role_assignments"
    __table_args__ = (
        # A player can only hold a single role.
        UniqueConstraint("player_id", name="assignment_player"),
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("game_players.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    game_role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("game_roles.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    # Relationships
    player: Mapped["GamePlayer"] = relationship(back_populates="assignment")
    game_role: Mapped["GameRole"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<RoleAssignment player_id={self.player_id} "
            f"game_role_id={self.game_role_id}>"
        )
