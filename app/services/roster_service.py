"""RosterService: builds the creator-only full player+role list."""

from __future__ import annotations

from app.repositories import RepositoryProvider
from app.schemas.game import GamePlayerDTO
from app.utils.exceptions import GameNotFoundError, NotGameCreatorError


class RosterService:
    """Produces the complete roster (number, name, role) for a game.

    Access is restricted to the game creator, because it reveals every player's
    role — information that must never leak to anyone else.
    """

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def get_full_roster(
        self, *, game_id: int, requester_id: int
    ) -> list[GamePlayerDTO]:
        """Return every active player with their role, for the creator only."""
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.creator_id != requester_id:
            raise NotGameCreatorError()

        players = await self._repos.players.list_roster(game_id)

        # Resolve each player's role via their assignment (eager-loaded).
        roster: list[GamePlayerDTO] = []
        for player in players:
            role_code = None
            role_name = None
            assignment = await self._repos.assignments.get_by_player(player.id)
            if assignment is not None:
                role = assignment.game_role.role
                role_code = role.code
                role_name = role.name_fa
            roster.append(
                GamePlayerDTO(
                    player_id=player.id,
                    user_id=player.user_id,
                    display_name=(
                        player.user.display_name if player.user else str(player.user_id)
                    ),
                    number=player.number,
                    status=player.status,
                    role_code=role_code,
                    role_name_fa=role_name,
                )
            )
        return roster
