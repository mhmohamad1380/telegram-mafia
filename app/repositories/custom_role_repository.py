"""Repository for :class:`CustomRole` entities (user-owned private roles)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.custom_role import CustomRole
from app.repositories.base import BaseRepository


class CustomRoleRepository(BaseRepository[CustomRole]):
    """Query and persistence operations for user-owned custom roles.

    All reads are scoped by ``owner_id`` so a user can only ever reach their own
    roles; the service layer enforces the same invariant defensively.
    """

    model = CustomRole

    async def list_active_for_owner(self, owner_id: int) -> list[CustomRole]:
        """Return the owner's active (non-deleted) roles, newest first."""
        result = await self.session.execute(
            select(CustomRole)
            .where(
                CustomRole.owner_id == owner_id,
                CustomRole.is_active.is_(True),
            )
            .order_by(CustomRole.id.desc())
        )
        return list(result.scalars().all())

    async def get_owned(
        self, *, custom_role_id: int, owner_id: int
    ) -> CustomRole | None:
        """Return an active role by id **only if** it belongs to ``owner_id``."""
        result = await self.session.execute(
            select(CustomRole).where(
                CustomRole.id == custom_role_id,
                CustomRole.owner_id == owner_id,
                CustomRole.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def count_active_for_owner(self, owner_id: int) -> int:
        """Return how many active custom roles the owner currently has."""
        result = await self.session.execute(
            select(func.count())
            .select_from(CustomRole)
            .where(
                CustomRole.owner_id == owner_id,
                CustomRole.is_active.is_(True),
            )
        )
        return int(result.scalar_one())

    async def name_exists_for_owner(self, *, owner_id: int, name_fa: str) -> bool:
        """Whether the owner already has an active role with this exact name."""
        result = await self.session.execute(
            select(func.count())
            .select_from(CustomRole)
            .where(
                CustomRole.owner_id == owner_id,
                CustomRole.name_fa == name_fa,
                CustomRole.is_active.is_(True),
            )
        )
        return int(result.scalar_one()) > 0
