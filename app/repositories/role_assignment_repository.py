"""Repository for :class:`RoleAssignment` entities."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.game_role import GameRole
from app.models.role_assignment import RoleAssignment
from app.repositories.base import BaseRepository


class RoleAssignmentRepository(BaseRepository[RoleAssignment]):
    """Query and persistence operations for role assignments."""

    model = RoleAssignment

    async def get_by_player(self, player_id: int) -> RoleAssignment | None:
        """Return the assignment for a player (with role loaded), or ``None``."""
        result = await self.session.execute(
            select(RoleAssignment)
            .where(RoleAssignment.player_id == player_id)
            .options(
                selectinload(RoleAssignment.game_role).selectinload(GameRole.role)
            )
        )
        return result.scalar_one_or_none()
