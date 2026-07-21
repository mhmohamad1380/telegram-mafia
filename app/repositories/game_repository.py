"""Repository for :class:`Game` entities."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.models.enums import GameStatus, PlayerStatus
from app.models.game import Game
from app.models.game_player import GamePlayer
from app.repositories.base import BaseRepository



class GameRepository(BaseRepository[Game]):
    """Query and persistence operations for games."""

    model = Game

    async def get_by_code(self, code: str) -> Game | None:
        """Return a game by its join code, or ``None``."""
        result = await self.session.execute(select(Game).where(Game.code == code))
        return result.scalar_one_or_none()

    async def get_by_code_for_update(self, code: str) -> Game | None:
        """Return a game by code with a ``SELECT ... FOR UPDATE`` row lock.

        Used when mutating lobby state (joining, picking numbers, assigning
        roles) so concurrent operations on the same game are serialized and can
        never race past capacity or reuse a number/role.
        """
        result = await self.session.execute(
            select(Game).where(Game.code == code).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, game_id: int) -> Game | None:
        """Return a game by id with a row lock."""
        result = await self.session.execute(
            select(Game).where(Game.id == game_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def code_exists(self, code: str) -> bool:
        """Return whether a game with the given code already exists."""
        result = await self.session.execute(
            select(Game.id).where(Game.code == code)
        )
        return result.scalar_one_or_none() is not None

    async def update_status(self, game: Game, status: GameStatus) -> Game:
        """Set a game's status and flush."""
        game.status = status
        await self.session.flush()
        return game

    async def list_for_user(self, user_id: int) -> list[Game]:
        """Return every non-cancelled game the user creates or actively plays in.

        A game is included when the user is its creator *or* has a non-left
        player row in it. Results are newest-first so the most relevant games
        appear at the top of the "📂 بازی‌های من" list.
        """
        result = await self.session.execute(
            select(Game)
            .outerjoin(
                GamePlayer,
                (GamePlayer.game_id == Game.id)
                & (GamePlayer.user_id == user_id)
                & (GamePlayer.status != PlayerStatus.LEFT),
            )
            .where(
                Game.status != GameStatus.CANCELLED,
                or_(Game.creator_id == user_id, GamePlayer.id.is_not(None)),
            )
            .order_by(Game.id.desc())
            .distinct()
        )
        return list(result.scalars().all())

