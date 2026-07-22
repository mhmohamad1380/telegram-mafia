"""Repository for :class:`GameRole` entities (per-game role pool + counts)."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.models.game_role import GameRole
from app.repositories.base import BaseRepository


class GameRoleRepository(BaseRepository[GameRole]):
    """Query and persistence operations for a game's role pool."""

    model = GameRole

    async def list_for_game(self, game_id: int) -> list[GameRole]:
        """Return all role rows configured for a game, with the role loaded."""
        result = await self.session.execute(
            select(GameRole)
            .where(GameRole.game_id == game_id)
            .options(
                selectinload(GameRole.role),
                selectinload(GameRole.custom_role),
            )
            .order_by(GameRole.id)
        )
        return list(result.scalars().all())


    async def list_available_for_update(self, game_id: int) -> list[GameRole]:
        """Return role rows with ``remaining > 0``, row-locked for update.

        The lock ensures that when two players request a role simultaneously,
        one transaction waits for the other so the same slot can't be handed out
        twice.
        """
        result = await self.session.execute(
            select(GameRole)
            .where(GameRole.game_id == game_id, GameRole.remaining > 0)
            .options(
                selectinload(GameRole.role),
                selectinload(GameRole.custom_role),
            )
            .order_by(GameRole.id)
            .with_for_update(of=GameRole)

        )
        return list(result.scalars().all())

    async def total_remaining(self, game_id: int) -> int:
        """Return the total number of unassigned role slots in the game."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(GameRole.remaining), 0)).where(
                GameRole.game_id == game_id
            )
        )
        return int(result.scalar_one())

    async def total_quantity(self, game_id: int) -> int:
        """Return the total number of role slots configured for the game."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(GameRole.quantity), 0)).where(
                GameRole.game_id == game_id
            )
        )
        return int(result.scalar_one())

    async def decrement_remaining(self, game_role_id: int) -> bool:
        """Atomically decrement ``remaining`` for a role slot.

        Uses a guarded ``UPDATE ... WHERE remaining > 0`` so the decrement only
        succeeds if a slot is actually available. Returns ``True`` if a row was
        updated (slot claimed), ``False`` otherwise.
        """
        result = await self.session.execute(
            update(GameRole)
            .where(GameRole.id == game_role_id, GameRole.remaining > 0)
            .values(remaining=GameRole.remaining - 1)
        )
        return (result.rowcount or 0) > 0

    async def reset_remaining(self, game_id: int) -> None:
        """Restore ``remaining`` to ``quantity`` for every role in the game."""
        await self.session.execute(
            update(GameRole)
            .where(GameRole.game_id == game_id)
            .values(remaining=GameRole.quantity)
        )
