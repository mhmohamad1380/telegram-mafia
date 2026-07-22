"""User model: a Telegram user known to the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.custom_role import CustomRole
    from app.models.game import Game
    from app.models.game_player import GamePlayer



class User(Base, TimestampMixin):
    """A Telegram user.

    The primary key is the Telegram user id itself (``BIGINT``) so we never need
    a separate lookup to map between Telegram updates and our records.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relationships
    created_games: Mapped[list["Game"]] = relationship(
        back_populates="creator",
        foreign_keys="Game.creator_id",
    )
    game_players: Mapped[list["GamePlayer"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    custom_roles: Mapped[list["CustomRole"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


    @property
    def display_name(self) -> str:
        """Human-friendly name for messages (falls back to id)."""
        if self.first_name:
            full = self.first_name
            if self.last_name:
                full = f"{full} {self.last_name}"
            return full
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} username={self.username!r}>"
