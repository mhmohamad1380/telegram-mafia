"""Service layer package.

Exposes the individual services plus a :class:`ServiceProvider` that composes
them over a single session/transaction. The DI middleware creates a provider per
update so handlers receive fully-wired services without touching construction
details.
"""

from __future__ import annotations

from functools import cached_property

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import RepositoryProvider
from app.services.assignment_service import AssignmentService
from app.services.auto_role_assignment_service import AutoRoleAssignmentService
from app.services.composition_service import RoleCompositionService
from app.services.custom_role_service import CustomRoleService
from app.services.fake_user_service import FakeUserService


from app.services.game_management_service import GameManagementService
from app.services.game_service import GameService

from app.services.live_sync_service import LiveGameSyncService
from app.services.lobby_service import LobbyService
from app.services.lobby_state_service import LobbyStateService
from app.services.owner_test_flow_service import BotOwnerTestFlowService

from app.services.player_service import PlayerService

from app.services.randomizer_service import RandomizerService
from app.services.role_info_service import RoleInfoService
from app.services.role_service import RoleService
from app.services.roster_service import RosterService
from app.services.scenario_service import ScenarioService
from app.services.turn_manager_service import TurnManagerService

from app.services.user_games_service import UserGamesService




class ServiceProvider:
    """Lazily builds the service graph bound to one session/transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repos = RepositoryProvider(session)
        self._randomizer = RandomizerService()

    @property
    def repos(self) -> RepositoryProvider:
        return self._repos

    @cached_property
    def roles(self) -> RoleService:
        return RoleService(self._repos)

    @cached_property
    def games(self) -> GameService:
        return GameService(self._repos)

    @cached_property
    def players(self) -> PlayerService:
        return PlayerService(self._repos)

    @cached_property
    def assignments(self) -> AssignmentService:
        return AssignmentService(self._repos, self._randomizer)

    @cached_property
    def roster(self) -> RosterService:
        return RosterService(self._repos)

    @cached_property
    def composition(self) -> RoleCompositionService:
        return RoleCompositionService(self._repos)


    @cached_property
    def lobby_state(self) -> LobbyStateService:
        return LobbyStateService(self._repos)

    @cached_property
    def turns(self) -> TurnManagerService:
        return TurnManagerService(self._repos, self.lobby_state)

    @cached_property
    def lobby(self) -> LobbyService:
        return LobbyService(
            self._repos,
            self.assignments,
            self.games,
            self.turns,
            self.lobby_state,
        )

    @cached_property
    def auto_assignment(self) -> AutoRoleAssignmentService:
        return AutoRoleAssignmentService(self._repos, self.assignments, self.games)

    @cached_property
    def fake_users(self) -> FakeUserService:
        return FakeUserService(self._repos)

    @cached_property
    def owner_test_flow(self) -> BotOwnerTestFlowService:
        return BotOwnerTestFlowService(
            self._repos,
            games=self.games,
            scenarios=self.scenarios,
            lobby=self.lobby,
            auto_assignment=self.auto_assignment,
            fake_users=self.fake_users,
        )

    @cached_property
    def live_sync(self) -> LiveGameSyncService:
        return LiveGameSyncService(self._repos, self.turns)


    @cached_property
    def role_info(self) -> RoleInfoService:
        return RoleInfoService()


    @cached_property
    def user_games(self) -> UserGamesService:
        return UserGamesService(self._repos)

    @cached_property
    def game_management(self) -> GameManagementService:
        return GameManagementService(self._repos)

    @cached_property
    def custom_roles(self) -> CustomRoleService:
        return CustomRoleService(self._repos)

    @cached_property
    def scenarios(self) -> ScenarioService:
        return ScenarioService(self._repos)



__all__ = [
    "ServiceProvider",
    "AssignmentService",
    "AutoRoleAssignmentService",
    "BotOwnerTestFlowService",
    "CustomRoleService",
    "FakeUserService",


    "GameManagementService",
    "GameService",
    "LiveGameSyncService",
    "LobbyService",

    "LobbyStateService",
    "PlayerService",
    "RandomizerService",
    "RoleInfoService",
    "RoleService",
    "RosterService",
    "ScenarioService",
    "TurnManagerService",
    "UserGamesService",
]



