"""TurnManagerService: enforces the strictly sequential (FIFO) player turn.

Once the lobby is complete, players must pick a seat number and receive their
role one at a time, in the exact order they joined. This service owns that rule:

* It computes whose turn it currently is (the active, unassigned player with the
  lowest ``join_order``).
* It validates that a given player is allowed to act right now, raising
  :class:`LobbyNotCompleteError` or :class:`NotPlayersTurnError` otherwise.

All queries go through repositories; no SQL lives here. Callers are expected to
hold the game row lock (``SELECT ... FOR UPDATE``) so turn checks and the
subsequent mutation are atomic and race-free.
"""

from __future__ import annotations

from app.models.game import Game
from app.models.game_player import GamePlayer
from app.repositories import RepositoryProvider
from app.schemas.game import GameDTO, TurnStateDTO
from app.services.lobby_state_service import LobbyStateService
from app.utils.exceptions import LobbyNotCompleteError, NotPlayersTurnError


class TurnManagerService:
    """Computes and enforces the FIFO turn order for number/role selection."""

    def __init__(
        self,
        repos: RepositoryProvider,
        lobby_state: LobbyStateService,
    ) -> None:
        self._repos = repos
        self._lobby_state = lobby_state

    async def current_turn_player(self, game_id: int) -> GamePlayer | None:
        """Return the player whose turn it is, or ``None`` if all are assigned."""
        return await self._repos.players.get_current_turn_player(game_id)

    async def get_turn_state(self, *, game: Game) -> TurnStateDTO:
        """Build a :class:`TurnStateDTO` snapshot for a game."""
        joined = await self._lobby_state.active_count(game.id)
        complete = joined >= game.player_count
        current = (
            await self.current_turn_player(game.id) if complete else None
        )
        return TurnStateDTO(
            game=GameDTO(
                id=game.id,
                code=game.code,
                creator_id=game.creator_id,
                player_count=game.player_count,
                status=game.status,
            ),
            lobby_complete=complete,
            joined_count=joined,
            current_user_id=current.user_id if current else None,
            current_join_order=current.join_order if current else None,
        )

    async def ensure_players_turn(self, *, game: Game, player: GamePlayer) -> None:
        """Validate that ``player`` may act now under the FIFO rule.

        Raises:
            LobbyNotCompleteError: If the lobby is not yet full.
            NotPlayersTurnError: If it is currently another player's turn.
        """
        if not await self._lobby_state.is_complete(game):
            raise LobbyNotCompleteError()

        current = await self.current_turn_player(game.id)
        if current is None or current.id != player.id:
            raise NotPlayersTurnError()
