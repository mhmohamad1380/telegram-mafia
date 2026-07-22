"""AutoRoleAssignmentService: instant, race-free role assignment on join.

This service powers :class:`~app.models.enums.RoleMode.AUTO_ROLE_ASSIGNMENT`
games. Unlike the classic manual flow (fill the lobby, then draw a role in turn),
here a player is given a seat number **and** a random, still-available role the
moment they join — with no waiting for the lobby to fill and no manual "get role"
tap.

Correctness / concurrency
--------------------------
Every assignment locks the game row first (``SELECT ... FOR UPDATE``), so two
players joining the same auto game are serialized: seat numbers and roles can
never be handed out twice even under a burst of simultaneous joins. The actual
role claim additionally rides on :class:`AssignmentService`'s guarded
``UPDATE ... WHERE remaining > 0``, giving a second, independent guarantee of
uniqueness. All of this runs inside the caller's single transaction (the DI
middleware owns the commit), so a failure rolls the whole step back atomically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.logging import get_logger
from app.models.enums import GameStatus, PlayerStatus, RoleMode
from app.repositories import RepositoryProvider
from app.schemas.game import PlayerRoleDTO
from app.services.assignment_service import AssignmentService
from app.services.game_service import GameService
from app.utils.exceptions import (
    GameNotFoundError,
    InvalidGameStateError,
    NoRolesAvailableError,
    PlayerNotInGameError,
    RoleAlreadyAssignedError,
)

logger = get_logger(__name__)


class AutoRoleAssignmentService:
    """Assigns a seat number + random role to a player immediately on join."""

    def __init__(
        self,
        repos: RepositoryProvider,
        assignment_service: AssignmentService,
        game_service: GameService,
    ) -> None:
        self._repos = repos
        self._assignment = assignment_service
        self._games = game_service

    async def assign_for_player(
        self, *, game_id: int, user_id: int
    ) -> PlayerRoleDTO:
        """Give ``user_id`` the lowest free seat and a random role, atomically.

        Locks the game row so concurrent auto-joins are serialized. Requires the
        game to be in ``AUTO_ROLE_ASSIGNMENT`` mode and still accepting players,
        and the player to already be in the lobby without a role.

        Raises:
            GameNotFoundError: Unknown game.
            InvalidGameStateError: Game is not auto-mode or not joinable.
            PlayerNotInGameError: The user isn't an active player.
            RoleAlreadyAssignedError: The player already has a role.
            NoRolesAvailableError: No seats or roles remain (misconfiguration).
        """
        game = await self._repos.games.get_for_update(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.role_mode != RoleMode.AUTO_ROLE_ASSIGNMENT:
            raise InvalidGameStateError(
                "این بازی در حالت تخصیص خودکار نقش نیست."
            )
        if game.status != GameStatus.WAITING_PLAYERS:
            raise InvalidGameStateError("این بازی پذیرای بازیکن جدید نیست.")

        player = await self._repos.players.get_by_game_and_user(game.id, user_id)
        if player is None or player.status == PlayerStatus.LEFT:
            raise PlayerNotInGameError()
        if player.status == PlayerStatus.ASSIGNED:
            raise RoleAlreadyAssignedError()

        # Claim the lowest free seat number (unique per game, race-free under the
        # row lock; the DB unique constraint is the final backstop).
        if player.number is None:
            taken = set(await self._repos.players.taken_numbers(game.id))
            free = [
                n for n in range(1, game.player_count + 1) if n not in taken
            ]
            if not free:
                raise NoRolesAvailableError("شماره‌ای برای تخصیص باقی نمانده است.")
            player.number = free[0]
            player.selected_number = free[0]
            player.status = PlayerStatus.NUMBERED
            await self._repos.session.flush()

        # Draw a uniformly-random still-available role (atomic slot claim).
        role_dto = await self._assignment.assign_random_role(player=player)
        player.role_assigned_at = datetime.now(timezone.utc)
        await self._repos.session.flush()

        # Promote to READY once every seat is filled and assigned.
        await self._maybe_mark_ready(
            game_id=game.id, player_count=game.player_count
        )

        logger.info(
            "auto_role_assigned",
            game_id=game.id,
            user_id=user_id,
            number=player.number,
        )
        return role_dto

    async def _maybe_mark_ready(self, *, game_id: int, player_count: int) -> bool:
        """Promote the game to READY when all seats are filled and assigned."""
        active = await self._repos.players.count_active(game_id)
        assigned = await self._repos.players.count_assigned(game_id)
        if active == player_count and assigned == player_count:
            await self._games.mark_ready(game_id=game_id)
            return True
        return False
