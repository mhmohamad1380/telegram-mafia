"""LiveGameSyncService: real-time lobby screen synchronization.

When one player acts in the lobby (joins, picks a seat number, receives a role,
or leaves), the *shared* lobby state changes for everyone: the set of free seat
numbers shrinks, the turn advances, and the "joined N/M" counter moves. The
other players who are sitting on an open lobby screen must see those changes
**immediately**, without tapping a refresh button.

This service computes, for every *eligible* waiting player, the exact screen
their stored lobby message should now show. Eligibility mirrors the spec:

* member of the same game,
* has **not** yet received a role,
* is still in the selection phase (status ``JOINED`` or ``NUMBERED``),
* and their lobby message has been rendered at least once (so there is a
  message id to edit).

It deliberately contains **no** Telegram calls — it only produces
:class:`~app.schemas.game.PlayerSyncScreenDTO` objects. The presentation layer
(:mod:`app.bot.live_broadcaster`) performs the actual ``editMessageText`` /
``editMessageReplyMarkup`` and skips no-op edits, keeping the service layer free
of any framework concern (Clean Architecture / SRP).

Recording a player's lobby message id is also funnelled through here so there is
a single, well-tested place that owns the "which message is this player's live
screen" bookkeeping.
"""

from __future__ import annotations

from app.bot import texts
from app.config.logging import get_logger
from app.models.enums import GameStatus, PlayerStatus
from app.repositories import RepositoryProvider
from app.schemas.game import PlayerSyncScreenDTO, TurnStateDTO
from app.services.turn_manager_service import TurnManagerService
from app.utils.exceptions import GameNotFoundError, PlayerNotInGameError

logger = get_logger(__name__)


class LiveGameSyncService:
    """Computes the live lobby screens to push after a lobby state change."""

    def __init__(
        self,
        repos: RepositoryProvider,
        turn_manager: TurnManagerService,
    ) -> None:
        self._repos = repos
        self._turns = turn_manager

    # --- Recording a player's live message ---------------------------------

    async def record_lobby_message(
        self, *, game_id: int, user_id: int, chat_id: int, message_id: int
    ) -> None:
        """Remember which message is a player's live lobby screen.

        Called by the handler right after it (re)renders the player's lobby
        message, so a later state change can edit that exact message in place.
        Overwrites any previous value (e.g. when a fresh message had to be sent
        because the old one was deleted / uneditable).
        """
        player = await self._repos.players.get_by_game_and_user(game_id, user_id)
        if player is None:
            raise PlayerNotInGameError()
        player.lobby_chat_id = chat_id
        player.lobby_message_id = message_id
        await self._repos.session.flush()

    async def clear_lobby_message(self, *, game_id: int, user_id: int) -> None:
        """Forget a player's live lobby message (e.g. after they leave).

        Safe to call for a non-existent player; it simply does nothing.
        """
        player = await self._repos.players.get_by_game_and_user(game_id, user_id)
        if player is None:
            return
        player.lobby_chat_id = None
        player.lobby_message_id = None
        await self._repos.session.flush()

    # --- Computing the screens to broadcast --------------------------------

    async def compute_sync_screens(
        self, *, game_id: int, exclude_user_id: int | None = None
    ) -> list[PlayerSyncScreenDTO]:
        """Return the up-to-date lobby screen for every eligible waiting player.

        ``exclude_user_id`` skips the player who just acted (their own handler
        already rendered their next screen), avoiding a redundant self-edit.

        The returned list is safe to hand straight to the broadcaster: each item
        targets a concrete stored message and describes exactly what to render.
        Players who are ineligible (already assigned, left, or never rendered a
        lobby message) are simply absent from the result and thus never updated.
        """
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()

        # Only meaningful while the lobby is still forming/assigning. Once the
        # game starts or finishes there are no waiting screens to sync.
        if game.status not in (GameStatus.WAITING_PLAYERS, GameStatus.READY):
            return []

        turn: TurnStateDTO = await self._turns.get_turn_state(game=game)
        taken = set(await self._repos.players.taken_numbers(game_id))
        free_numbers = [
            n for n in range(1, game.player_count + 1) if n not in taken
        ]

        targets = await self._repos.players.list_awaiting_turn(game_id)
        screens: list[PlayerSyncScreenDTO] = []
        for player in targets:
            if exclude_user_id is not None and player.user_id == exclude_user_id:
                continue
            if player.lobby_chat_id is None or player.lobby_message_id is None:
                continue  # defensive; list_awaiting_turn already filters these

            screen = self._screen_for_player(
                player_user_id=player.user_id,
                player_status=player.status,
                player_number=player.number,
                chat_id=player.lobby_chat_id,
                message_id=player.lobby_message_id,
                turn=turn,
                free_numbers=free_numbers,
            )
            screens.append(screen)
        return screens

    def _screen_for_player(
        self,
        *,
        player_user_id: int,
        player_status: PlayerStatus,
        player_number: int | None,
        chat_id: int,
        message_id: int,
        turn: TurnStateDTO,
        free_numbers: list[int],
    ) -> PlayerSyncScreenDTO:
        """Decide the correct waiting/number screen for a single player.

        Mirrors the handler's own turn-screen decision tree so a pushed update
        is indistinguishable from what the player would see if they refreshed
        manually — the whole point of the live sync.
        """
        # Lobby not full yet -> waiting-for-lobby screen.
        if not turn.lobby_complete:
            return PlayerSyncScreenDTO(
                user_id=player_user_id,
                game_id=turn.game.id,
                chat_id=chat_id,
                message_id=message_id,
                text=texts.waiting_for_lobby(turn),
                kind="waiting",
            )

        # Lobby full, but it's someone else's turn.
        if turn.current_user_id != player_user_id:
            return PlayerSyncScreenDTO(
                user_id=player_user_id,
                game_id=turn.game.id,
                chat_id=chat_id,
                message_id=message_id,
                text=texts.not_your_turn(),
                kind="waiting",
            )

        # It's this player's turn.
        if player_number is None:
            return PlayerSyncScreenDTO(
                user_id=player_user_id,
                game_id=turn.game.id,
                chat_id=chat_id,
                message_id=message_id,
                text=texts.your_turn_notice() + "\n\n🔢 یک شماره انتخاب کنید:",
                kind="numbers",
                available_numbers=list(free_numbers),
            )

        # Turn holder who already picked a number: prompt to get their role.
        return PlayerSyncScreenDTO(
            user_id=player_user_id,
            game_id=turn.game.id,
            chat_id=chat_id,
            message_id=message_id,
            text=texts.number_chosen(player_number),
            kind="getrole",
        )

