"""GameHistoryService: read model for the "📜 تاریخچه بازی‌ها" screen.

Surfaces the finished/cancelled games a user has taken part in (as creator or
player) as immutable :class:`GameHistoryEntryDTO` rows. This is a pure read
service: it never mutates state and never reveals any player's role — history is
a record of *games played*, not a role reveal.
"""

from __future__ import annotations

from app.config.logging import get_logger
from app.repositories import RepositoryProvider
from app.schemas.game import GameHistoryEntryDTO

logger = get_logger(__name__)


class GameHistoryService:
    """Builds a user's past-games history from the persisted game records."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def list_for_user(self, user_id: int) -> list[GameHistoryEntryDTO]:
        """Return the user's finished/cancelled games, newest-first.

        For each qualifying game we also resolve the user's own seat number (if
        they played) and whether they were the creator, so the history card can
        be rendered without any further lookups. Roles are intentionally omitted.
        """
        games = await self._repos.games.list_history_for_user(user_id)
        entries: list[GameHistoryEntryDTO] = []
        for game in games:
            player = await self._repos.players.get_by_game_and_user(

                game_id=game.id, user_id=user_id
            )
            entries.append(
                GameHistoryEntryDTO(
                    game_id=game.id,
                    code=game.code,
                    scenario_code=game.scenario_code,
                    status=game.status,
                    player_count=game.player_count,
                    is_creator=game.creator_id == user_id,
                    my_number=player.number if player else None,
                    winner_team=game.winner_team,
                    started_at=game.started_at,
                    finished_at=game.finished_at,
                )
            )
        logger.info("game_history_listed", user_id=user_id, count=len(entries))
        return entries
