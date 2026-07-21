"""RoleService: read access to the role catalog and DTO mapping."""

from __future__ import annotations

from app.models.role import Role
from app.repositories import RepositoryProvider
from app.schemas.game import RoleCatalogItemDTO
from app.utils.role_catalog import ROLE_BY_CODE


class RoleService:
    """Exposes the seeded role catalog to the presentation layer."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def list_catalog(self) -> list[RoleCatalogItemDTO]:
        """Return all active roles as DTOs (ordered by team then id)."""
        roles = await self._repos.roles.list_active()
        return [self._to_dto(role) for role in roles]

    @staticmethod
    def _to_dto(role: Role) -> RoleCatalogItemDTO:
        # Enrich the DB row with catalog-only metadata (e.g. availability
        # constraints) so the presentation layer stays fully data-driven.
        defn = ROLE_BY_CODE.get(role.code)
        return RoleCatalogItemDTO(
            role_id=role.id,
            code=role.code,
            name_fa=role.name_fa,
            team=role.team,
            description=role.description,
            min_players=defn.min_players if defn is not None else None,
        )

