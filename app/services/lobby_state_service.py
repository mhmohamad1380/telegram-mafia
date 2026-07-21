"""LobbyStateService: answers "is the lobby full yet?".

Encapsulates the single business rule that gates the whole turn-based flow: no
player may pick a seat number or receive a role until the lobby holds exactly
``player_count`` active players. Keeping this in its own service keeps the rule
in one place (Clean Architecture / SRP) and lets other services depend on it.
"""

from __future__ import annotations

from app.models.game import Game
from app.repositories import RepositoryProvider


class LobbyStateService:
    """Determines lobby completeness for a game."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def active_count(self, game_id: int) -> int:
        """Return the number of players currently occupying a seat."""
        return await self._repos.players.count_active(game_id)

    async def is_complete(self, game: Game) -> bool:
        """Return whether the lobby has exactly ``player_count`` active players."""
        active = await self._repos.players.count_active(game.id)
        return active >= game.player_count
