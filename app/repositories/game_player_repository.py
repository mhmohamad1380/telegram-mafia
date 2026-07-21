"""Repository for :class:`GamePlayer` entities (lobby membership + seats)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.enums import PlayerStatus
from app.models.game_player import GamePlayer
from app.repositories.base import BaseRepository


class GamePlayerRepository(BaseRepository[GamePlayer]):
    """Query and persistence operations for players within a game."""

    model = GamePlayer

    # Statuses that count as "actively occupying a seat/role".
    _ACTIVE_STATUSES = (
        PlayerStatus.JOINED,
        PlayerStatus.NUMBERED,
        PlayerStatus.ASSIGNED,
    )

    async def get_by_game_and_user(
        self, game_id: int, user_id: int
    ) -> GamePlayer | None:
        """Return the player row for a user within a game, or ``None``.

        The related ``user`` is eagerly loaded so callers can safely read
        ``player.user`` after the query returns without triggering a lazy load
        outside the async context (which raises ``MissingGreenlet``).
        """
        result = await self.session.execute(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.user_id == user_id,
            )
            .options(selectinload(GamePlayer.user))
        )
        return result.scalar_one_or_none()


    async def next_join_order(self, game_id: int) -> int:
        """Return the next 1-based join order for a game.

        Computed as ``max(join_order) + 1`` across every row of the game
        (including players who left) so ordering values are never reused and the
        FIFO sequence is stable even after departures.
        """
        result = await self.session.execute(
            select(func.coalesce(func.max(GamePlayer.join_order), 0)).where(
                GamePlayer.game_id == game_id
            )
        )
        return int(result.scalar_one()) + 1

    async def get_current_turn_player(self, game_id: int) -> GamePlayer | None:
        """Return the active, not-yet-assigned player with the lowest join order.

        This is the single player whose turn it is to pick a number and receive
        a role. Returns ``None`` when every active player already has a role.
        """
        result = await self.session.execute(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status.in_(
                    (PlayerStatus.JOINED, PlayerStatus.NUMBERED)
                ),
                GamePlayer.join_order.is_not(None),
            )
            .options(selectinload(GamePlayer.user))
            .order_by(GamePlayer.join_order.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()


    async def list_active_ordered(self, game_id: int) -> list[GamePlayer]:
        """Return active players ordered by their join order (FIFO)."""
        result = await self.session.execute(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
            .order_by(GamePlayer.join_order.asc().nulls_last())
        )
        return list(result.scalars().all())

    async def count_active(self, game_id: int) -> int:

        """Count players currently occupying a seat in the game."""
        result = await self.session.execute(
            select(func.count())
            .select_from(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
        )
        return int(result.scalar_one())

    async def count_assigned(self, game_id: int) -> int:
        """Count players who already received a role."""
        result = await self.session.execute(
            select(func.count())
            .select_from(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status == PlayerStatus.ASSIGNED,
            )
        )
        return int(result.scalar_one())

    async def taken_numbers(self, game_id: int) -> list[int]:
        """Return the sorted list of seat numbers currently taken in the game."""
        result = await self.session.execute(
            select(GamePlayer.number)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.number.is_not(None),
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
            .order_by(GamePlayer.number)
        )
        return [row for row in result.scalars().all() if row is not None]

    async def is_number_taken(self, game_id: int, number: int) -> bool:
        """Return whether a seat number is already taken by an active player."""
        result = await self.session.execute(
            select(GamePlayer.id).where(
                GamePlayer.game_id == game_id,
                GamePlayer.number == number,
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_active(self, game_id: int) -> list[GamePlayer]:
        """Return active players ordered by seat number (NULLs last)."""
        result = await self.session.execute(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
            .order_by(GamePlayer.number.nulls_last())
        )
        return list(result.scalars().all())

    async def list_roster(self, game_id: int) -> list[GamePlayer]:
        """Return active players with user + role assignment eagerly loaded.

        Used to render the creator-only roster (number, name, role).
        """
        result = await self.session.execute(
            select(GamePlayer)
            .where(
                GamePlayer.game_id == game_id,
                GamePlayer.status.in_(self._ACTIVE_STATUSES),
            )
            .options(
                selectinload(GamePlayer.user),
                selectinload(GamePlayer.assignment),
            )
            .order_by(GamePlayer.number.nulls_last())
        )
        return list(result.scalars().unique().all())
