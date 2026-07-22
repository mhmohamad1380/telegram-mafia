"""CustomRoleService: CRUD for user-owned, private custom roles.

Encapsulates all business rules around custom roles so handlers stay thin:

* ownership scoping (a user only ever sees/edits their own roles),
* name validation (non-empty, length, per-owner uniqueness among active roles),
* a per-owner quantity cap, and
* soft deletion (``is_active = False``) so historical games keep working.

All methods return immutable :class:`CustomRoleDTO` objects (never ORM entities)
so the presentation layer is fully decoupled from SQLAlchemy.
"""

from __future__ import annotations

from app.config.logging import get_logger
from app.models.custom_role import CustomRole
from app.models.enums import RoleTeam
from app.repositories import RepositoryProvider
from app.schemas.game import CustomRoleDTO
from app.utils.exceptions import (
    CustomRoleLimitReachedError,

    CustomRoleNameDuplicateError,
    CustomRoleNameEmptyError,
    CustomRoleNameTooLongError,
    CustomRoleNotFoundError,
)

logger = get_logger(__name__)

#: Maximum number of active custom roles a single user may own.
MAX_CUSTOM_ROLES_PER_USER = 50
#: Maximum allowed length of a custom role name (matches the DB column).
MAX_NAME_LENGTH = 64
#: Maximum allowed length of a custom role description.
MAX_DESCRIPTION_LENGTH = 1000


class CustomRoleService:
    """Create, list, view, and (soft-)delete a user's private custom roles."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def list_for_owner(self, *, owner_id: int) -> list[CustomRoleDTO]:
        """Return all active custom roles owned by ``owner_id``."""
        roles = await self._repos.custom_roles.list_active_for_owner(owner_id)
        return [self._to_dto(r) for r in roles]

    async def get_for_owner(
        self, *, custom_role_id: int, owner_id: int
    ) -> CustomRoleDTO:
        """Return a single custom role, enforcing ownership.

        Raises:
            CustomRoleNotFoundError: no such active role exists for this owner.
        """
        role = await self._repos.custom_roles.get_owned(
            custom_role_id=custom_role_id, owner_id=owner_id
        )
        if role is None:
            raise CustomRoleNotFoundError()
        return self._to_dto(role)

    async def create(
        self,
        *,
        owner_id: int,
        name_fa: str,
        team: RoleTeam,
        description: str | None = None,
    ) -> CustomRoleDTO:
        """Create a new custom role for ``owner_id`` after validating input.

        Raises:
            CustomRoleNameEmptyError / CustomRoleNameTooLongError: bad name.
            CustomRoleNameDuplicateError: owner already has an active role with
                the same name.
            CustomRoleLimitReachedError: owner hit the per-user cap.
        """
        name = self._clean_name(name_fa)
        desc = self._clean_description(description)

        count = await self._repos.custom_roles.count_active_for_owner(owner_id)
        if count >= MAX_CUSTOM_ROLES_PER_USER:
            raise CustomRoleLimitReachedError()

        if await self._repos.custom_roles.name_exists_for_owner(
            owner_id=owner_id, name_fa=name
        ):
            raise CustomRoleNameDuplicateError()

        role = CustomRole(
            owner_id=owner_id,
            name_fa=name,
            team=team,
            description=desc,
            is_active=True,
        )
        await self._repos.custom_roles.add(role)
        await self._repos.session.flush()

        logger.info(
            "custom_role_created",
            owner_id=owner_id,
            custom_role_id=role.id,
            team=team.value,
        )
        return self._to_dto(role)

    async def delete(self, *, custom_role_id: int, owner_id: int) -> None:
        """Soft-delete a custom role (``is_active = False``), owner-scoped.

        Soft deletion preserves references from historical games. Raises
        :class:`CustomRoleNotFoundError` if the role doesn't exist or belongs to
        someone else (surfaced as not-found to avoid leaking existence).
        """
        role = await self._repos.custom_roles.get_owned(
            custom_role_id=custom_role_id, owner_id=owner_id
        )
        if role is None:
            raise CustomRoleNotFoundError()
        role.is_active = False
        await self._repos.session.flush()
        logger.info(
            "custom_role_deleted",
            owner_id=owner_id,
            custom_role_id=custom_role_id,
        )

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _clean_name(name_fa: str) -> str:
        name = (name_fa or "").strip()
        if not name:
            raise CustomRoleNameEmptyError()
        if len(name) > MAX_NAME_LENGTH:
            raise CustomRoleNameTooLongError()
        return name

    @staticmethod
    def _clean_description(description: str | None) -> str | None:
        if description is None:
            return None
        desc = description.strip()
        if not desc:
            return None
        return desc[:MAX_DESCRIPTION_LENGTH]

    @staticmethod
    def _to_dto(role: CustomRole) -> CustomRoleDTO:
        return CustomRoleDTO(
            id=role.id,
            owner_id=role.owner_id,
            name_fa=role.name_fa,
            team=role.team,
            description=role.description,
        )
