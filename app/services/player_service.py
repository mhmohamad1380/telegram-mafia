"""PlayerService: player-centric queries and the private role reveal."""

from __future__ import annotations

from app.models.game_player import GamePlayer
from app.repositories import RepositoryProvider
from app.schemas.game import GamePlayerDTO, PlayerRoleDTO
from app.utils.exceptions import (
    PlayerNotInGameError,
    RoleAlreadyAssignedError,
)


class PlayerService:
    """Read-side operations for an individual player within a game."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def get_player(self, *, game_id: int, user_id: int) -> GamePlayerDTO:
        """Return the player's lobby entry (without role), or raise if absent."""
        player = await self._repos.players.get_by_game_and_user(game_id, user_id)
        if player is None:
            raise PlayerNotInGameError()
        return self._to_dto(player)

    async def get_my_role(self, *, game_id: int, user_id: int) -> PlayerRoleDTO:
        """Return the private role reveal for the requesting player.

        Only ever returns the caller's own role, satisfying the rule that a
        player's role is never shown to anyone else.
        """
        player = await self._repos.players.get_by_game_and_user(game_id, user_id)
        if player is None:
            raise PlayerNotInGameError()

        assignment = await self._repos.assignments.get_by_player(player.id)
        if assignment is None:
            raise RoleAlreadyAssignedError("هنوز نقشی به شما اختصاص نیافته است.")

        role = assignment.game_role.role
        return PlayerRoleDTO(
            code=role.code,
            name_fa=role.name_fa,
            team=role.team,
            description=role.description,
        )

    @staticmethod
    def _to_dto(player: GamePlayer) -> GamePlayerDTO:
        return GamePlayerDTO(
            player_id=player.id,
            user_id=player.user_id,
            display_name=player.user.display_name if player.user else str(player.user_id),
            number=player.number,
            status=player.status,
        )
