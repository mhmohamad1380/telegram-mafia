"""GameEvent model: an append-only audit trail of game lifecycle events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import GameEventType

if TYPE_CHECKING:
    from app.models.game import Game


class GameEvent(Base, IntPKMixin, TimestampMixin):
    """A single audit event within a game.

    Events form an append-only log used for debugging and (optionally) replay.
    Arbitrary structured context is stored in ``payload`` as JSONB.
    """

    __tablename__ = "game_events"

    game_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("games.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Optional actor (the user who triggered the event), if applicable.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[GameEventType] = mapped_column(
        Enum(GameEventType, name="game_event_type", native_enum=True),
        index=True,
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    # Relationships
    game: Mapped["Game"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<GameEvent game_id={self.game_id} type={self.event_type.value}>"
        )
