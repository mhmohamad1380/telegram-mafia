"""UserGamesService: read-side aggregation for the "📂 بازی‌های من" feature.

Builds the list of games a user participates in (as creator or member) and the
per-game detail screen. It never exposes any other player's role — only lobby
progress, the caller's own seat/role status, and (when relevant) whose turn it
currently is, identified by seat number/name rather than role.

All data access goes through repositories; no SQL lives here.
"""

from __future__ import annotations

from app.models.enums import GameStatus, PlayerStatus
from app.repositories import RepositoryProvider

from app.schemas.game import UserGameDetailDTO, UserGameSummaryDTO
from app.utils.exceptions import GameNotFoundError, PlayerNotInGameError


class UserGamesService:
    """Aggregates a user's games for listing and detail views."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def list_user_games(self, *, user_id: int) -> list[UserGameSummaryDTO]:
        """Return summaries of every game the user creates or plays in."""
        games = await self._repos.games.list_for_user(user_id)
        summaries: list[UserGameSummaryDTO] = []
        for game in games:
            joined = await self._repos.players.count_active(game.id)
            player = await self._repos.players.get_by_game_and_user(
                game.id, user_id
            )
            has_role = await self._player_has_role(player.id) if player else False
            summaries.append(
                UserGameSummaryDTO(
                    game_id=game.id,
                    code=game.code,
                    status=game.status,
                    player_count=game.player_count,
                    joined_count=joined,
                    is_creator=game.creator_id == user_id,
                    my_number=player.number if player else None,
                    has_role=has_role,
                )
            )
        return summaries

    async def get_game_detail(
        self, *, game_id: int, user_id: int
    ) -> UserGameDetailDTO:
        """Return the full detail screen for one game the user belongs to.

        Raises:
            GameNotFoundError: If the game does not exist.
            PlayerNotInGameError: If the requester is neither the creator nor a
                current member of the game.
        """
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()

        is_creator = game.creator_id == user_id
        player = await self._repos.players.get_by_game_and_user(game.id, user_id)
        is_member = player is not None and player.status != PlayerStatus.LEFT
        if not is_creator and not is_member:
            raise PlayerNotInGameError()

        joined = await self._repos.players.count_active(game.id)
        assigned = await self._repos.players.count_assigned(game.id)
        has_role = await self._player_has_role(player.id) if player else False

        # Resolve the current turn holder (only meaningful once the lobby is
        # full and assignment is under way). We expose the seat number/name of
        # whose turn it is — never their role.
        current_number: int | None = None
        current_name: str | None = None
        is_my_turn = False
        if joined >= game.player_count and game.status in (
            GameStatus.WAITING_PLAYERS,
            GameStatus.READY,
        ):
            current = await self._repos.players.get_current_turn_player(game.id)
            if current is not None:
                current_number = current.number
                current_name = (
                    current.user.display_name
                    if current.user
                    else str(current.user_id)
                )
                is_my_turn = current.user_id == user_id

        return UserGameDetailDTO(
            game_id=game.id,
            code=game.code,
            status=game.status,
            player_count=game.player_count,
            joined_count=joined,
            assigned_count=assigned,
            is_creator=is_creator,
            my_number=player.number if player else None,
            has_role=has_role,
            current_turn_number=current_number,
            current_turn_name=current_name,
            is_my_turn=is_my_turn,
            can_delete=is_creator and game.status != GameStatus.IN_PROGRESS,
        )

    async def _player_has_role(self, player_id: int) -> bool:
        """Return whether the given player row already has a role assignment."""
        assignment = await self._repos.assignments.get_by_player(player_id)
        return assignment is not None
