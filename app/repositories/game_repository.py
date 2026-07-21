"""Repository for :class:`Game` entities."""

from __future__ import annotations

from sqlalchemy import select

from app.models.enums import GameStatus
from app.models.game import Game
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
