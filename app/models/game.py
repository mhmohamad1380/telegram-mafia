"""Game model: a single mafia game session/lobby."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import GameStatus

if TYPE_CHECKING:
    from app.models.game_player import GamePlayer
    from app.models.game_role import GameRole
    from app.models.user import User


class Game(Base, IntPKMixin, TimestampMixin):
    """A mafia game, from creation through the lobby to completion.

    A game holds a unique 6-digit join ``code``, the target ``player_count``, a
    lifecycle ``status``, and references to its creator, selected roles, and
    players.
    """

    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint(
            "player_count >= 3 AND player_count <= 40",
            name="player_count_range",
        ),
    )

    # 6-digit numeric join code, unique across all games.
    code: Mapped[str] = mapped_column(
        String(6), unique=True, index=True, nullable=False
    )
    creator_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    player_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Scenario (game mode) code, e.g. "classic" / "capo". References the
    # data-driven scenario catalog rather than a DB table so scenarios stay
    # purely code-defined. Defaults to the classic scenario.
    scenario_code: Mapped[str] = mapped_column(
        String(32), default="classic", server_default="classic", nullable=False
    )
    status: Mapped[GameStatus] = mapped_column(

        Enum(GameStatus, name="game_status", native_enum=True),
        default=GameStatus.CREATING,
        index=True,
        nullable=False,
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        back_populates="created_games",
        foreign_keys=[creator_id],
    )
    players: Mapped[list["GamePlayer"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    game_roles: Mapped[list["GameRole"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Game id={self.id} code={self.code} status={self.status.value}>"
