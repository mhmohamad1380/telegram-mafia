"""AssignmentService: atomic, race-free random role assignment."""

from __future__ import annotations

from app.config.logging import get_logger
from app.models.enums import GameEventType, PlayerStatus
from app.models.game_player import GamePlayer
from app.models.role_assignment import RoleAssignment
from app.repositories import RepositoryProvider
from app.schemas.game import PlayerRoleDTO
from app.services.randomizer_service import RandomizerService
from app.utils.exceptions import (
    NoRolesAvailableError,
    NumberNotChosenError,
    RoleAlreadyAssignedError,
)

logger = get_logger(__name__)


class AssignmentService:
    """Assigns a random, still-available role to a player.

    Correctness relies on two layers of protection working inside a single
    transaction (the DI middleware owns the commit):

    1. The game row is locked upstream (``SELECT ... FOR UPDATE``) by the lobby
       flow, serializing concurrent operations on the same game.
    2. The chosen role slot is claimed with a guarded ``UPDATE ... WHERE
       remaining > 0`` so even without the game lock the same slot can never be
       handed out twice.
    """

    def __init__(
        self,
        repos: RepositoryProvider,
        randomizer: RandomizerService,
    ) -> None:
        self._repos = repos
        self._randomizer = randomizer

    async def assign_random_role(self, *, player: GamePlayer) -> PlayerRoleDTO:
        """Assign a uniformly-random remaining role to ``player``.

        The player must have already chosen a seat number. Raises if the player
        already has a role or no roles remain.
        """
        if player.status == PlayerStatus.ASSIGNED:
            raise RoleAlreadyAssignedError()
        if player.number is None:
            raise NumberNotChosenError()

        # Load and lock the available role slots for this game.
        available = await self._repos.game_roles.list_available_for_update(
            player.game_id
        )
        if not available:
            raise NoRolesAvailableError()

        # Pick one at random, then atomically claim a slot from it. Retry with a
        # different slot if a concurrent claimer emptied it first.
        candidates = self._randomizer.shuffle(available)
        for game_role in candidates:
            claimed = await self._repos.game_roles.decrement_remaining(game_role.id)
            if not claimed:
                continue

            assignment = RoleAssignment(
                game_id=player.game_id,
                player_id=player.id,
                game_role_id=game_role.id,
            )
            await self._repos.assignments.add(assignment)

            player.status = PlayerStatus.ASSIGNED
            await self._repos.session.flush()

            role_ref = (
                game_role.role_code.value
                if game_role.role_code is not None
                else f"custom:{game_role.custom_role_id}"
            )
            await self._repos.events.record(
                game_id=player.game_id,
                event_type=GameEventType.ROLE_ASSIGNED,
                user_id=player.user_id,
                payload={
                    "player_id": player.id,
                    "role_code": role_ref,
                },
            )
            logger.info(
                "role_assigned",
                game_id=player.game_id,
                player_id=player.id,
                role_code=role_ref,
            )
            return PlayerRoleDTO(
                code=game_role.role_code,
                name_fa=game_role.display_name,
                team=game_role.team,
                description=game_role.description,
                is_custom=game_role.is_custom,
            )


        # Every candidate slot was claimed concurrently between our lock and the
        # decrement (should be impossible under the row lock, but guard anyway).
        raise NoRolesAvailableError()
