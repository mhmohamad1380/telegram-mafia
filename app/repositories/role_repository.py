"""Repository for the global :class:`Role` catalog."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.enums import RoleCode
from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Read access to the seeded role catalog."""

    model = Role

    async def list_active(self) -> list[Role]:
        """Return all active roles ordered by team then id (stable menu order)."""
        result = await self.session.execute(
            select(Role).where(Role.is_active.is_(True)).order_by(Role.team, Role.id)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: RoleCode) -> Role | None:
        """Return a role by its code, or ``None``."""
        result = await self.session.execute(select(Role).where(Role.code == code))
        return result.scalar_one_or_none()

    async def get_by_ids(self, role_ids: Sequence[int]) -> list[Role]:
        """Return all roles whose ids are in ``role_ids``."""
        if not role_ids:
            return []
        result = await self.session.execute(
            select(Role).where(Role.id.in_(role_ids))
        )
        return list(result.scalars().all())
