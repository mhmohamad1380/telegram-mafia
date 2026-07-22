"""GamePlayer model: a user's membership in a specific game lobby."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import PlayerStatus

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.role_assignment import RoleAssignment
    from app.models.user import User


class GamePlayer(Base, IntPKMixin, TimestampMixin):
    """A player seat within a game.

    A user may only appear once per game (enforced by a unique constraint), and
    each seat ``number`` is unique within a game while the player is active.
    The seat number is nullable until the player picks one.
    """

    __tablename__ = "game_players"
    __table_args__ = (
        # A user can only be in a given game once.
        UniqueConstraint("game_id", "user_id", name="game_user"),
        # A seat number is unique within a game (NULLs are allowed & ignored by
        # Postgres unique semantics, so freed seats do not collide).
        UniqueConstraint("game_id", "number", name="game_number"),
        CheckConstraint("number IS NULL OR number >= 1", name="number_positive"),
    )

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Seat number chosen by the player; NULL until chosen / after leaving.
    number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Order in which the player joined the lobby (1-based). Drives the strictly
    # sequential (FIFO) turn in which players pick a number and get a role.
    # Nullable so pre-existing rows / left players don't violate NOT NULL.
    join_order: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # The seat number the player selected on their turn (mirrors ``number`` but
    # kept as an explicit audit field per the turn-based spec).
    selected_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # When the player's role was assigned; NULL until they take their turn.
    role_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Telegram chat id + message id of the player's *live* lobby screen (the
    # message showing the turn/number picker). Persisted so the live-sync
    # service can edit it in place whenever the shared lobby state changes,
    # instead of asking the player to refresh. Both NULL until the first render.
    lobby_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lobby_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    status: Mapped[PlayerStatus] = mapped_column(
        Enum(PlayerStatus, name="player_status", native_enum=True),
        default=PlayerStatus.JOINED,
        index=True,
        nullable=False,
    )


    # Relationships
    game: Mapped["Game"] = relationship(back_populates="players")
    user: Mapped["User"] = relationship(back_populates="game_players")
    assignment: Mapped["RoleAssignment | None"] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<GamePlayer game_id={self.game_id} user_id={self.user_id} "
            f"number={self.number} status={self.status.value}>"
        )
