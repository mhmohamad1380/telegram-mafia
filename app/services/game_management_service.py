"""GameManagementService: creator-only destructive game operations.

Currently owns game deletion for the "📂 بازی‌های من" screen. Deletion is only
permitted for the game's creator and never while the game is ``IN_PROGRESS``.
Relies on the database's ``ON DELETE CASCADE`` foreign keys (players, roles,
events, and — transitively — role assignments) to release every dependent row
atomically inside the surrounding transaction.
"""

from __future__ import annotations

from app.config.logging import get_logger
from app.models.enums import GameStatus
from app.repositories import RepositoryProvider
from app.utils.exceptions import (
    GameDeletionNotAllowedError,
    GameNotFoundError,
    NotGameCreatorError,
)

logger = get_logger(__name__)


class GameManagementService:
    """Creator-only management operations (deletion) for a game."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def delete_game(self, *, game_id: int, requester_id: int) -> str:
        """Delete a game and all its dependent rows. Returns the deleted code.

        The game row is locked first so a concurrent state transition cannot
        slip a game into ``IN_PROGRESS`` between the check and the delete.

        Raises:
            GameNotFoundError: If the game does not exist.
            NotGameCreatorError: If the requester is not the creator.
            GameDeletionNotAllowedError: If the game is currently in progress.
        """
        game = await self._repos.games.get_for_update(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.creator_id != requester_id:
            raise NotGameCreatorError()
        if game.status == GameStatus.IN_PROGRESS:
            raise GameDeletionNotAllowedError()

        code = game.code
        # CASCADE foreign keys remove players, roles, assignments, and events.
        await self._repos.games.delete(game)
        logger.info("game_deleted", game_id=game_id, code=code, by=requester_id)
        return code
