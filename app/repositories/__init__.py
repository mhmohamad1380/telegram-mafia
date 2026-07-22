"""Repository package.

Exposes concrete repositories and a lightweight :class:`RepositoryProvider`
that lazily constructs repositories bound to a single :class:`AsyncSession`.
Services depend on the provider so they can compose multiple repositories inside
one transaction.
"""

from __future__ import annotations

from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.custom_role_repository import CustomRoleRepository
from app.repositories.game_event_repository import GameEventRepository

from app.repositories.game_player_repository import GamePlayerRepository
from app.repositories.game_repository import GameRepository
from app.repositories.game_role_repository import GameRoleRepository
from app.repositories.role_assignment_repository import RoleAssignmentRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository


class RepositoryProvider:
    """Lazily instantiates repositories that share one session/transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @cached_property
    def users(self) -> UserRepository:
        return UserRepository(self.session)

    @cached_property
    def roles(self) -> RoleRepository:
        return RoleRepository(self.session)

    @cached_property
    def custom_roles(self) -> CustomRoleRepository:
        return CustomRoleRepository(self.session)


    @cached_property
    def games(self) -> GameRepository:
        return GameRepository(self.session)

    @cached_property
    def players(self) -> GamePlayerRepository:
        return GamePlayerRepository(self.session)

    @cached_property
    def game_roles(self) -> GameRoleRepository:
        return GameRoleRepository(self.session)

    @cached_property
    def assignments(self) -> RoleAssignmentRepository:
        return RoleAssignmentRepository(self.session)

    @cached_property
    def events(self) -> GameEventRepository:
        return GameEventRepository(self.session)


__all__ = [
    "RepositoryProvider",
    "CustomRoleRepository",
    "GameEventRepository",

    "GamePlayerRepository",
    "GameRepository",
    "GameRoleRepository",
    "RoleAssignmentRepository",
    "RoleRepository",
    "UserRepository",
]
