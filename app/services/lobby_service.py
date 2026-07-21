"""LobbyService: joining, seat selection, leaving, and lobby state.

This service orchestrates the race-sensitive lobby operations. Every mutating
method takes a ``SELECT ... FOR UPDATE`` lock on the game row first, so all
concurrent joins / number picks / role assignments for the same game are
serialized at the database level.

Turn-based flow (FIFO)
----------------------
Players join and are stamped with an incrementing ``join_order``. Nobody may
pick a seat number or receive a role until the lobby is *complete* (exactly
``player_count`` active players). Once complete, players act strictly one at a
time in join order, enforced by :class:`TurnManagerService`. Because the game
row is locked for the whole operation, the turn check and the subsequent
mutation are atomic — two players can never act out of turn or claim the same
number/role concurrently.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.logging import get_logger
from app.models.enums import GameEventType, GameStatus, PlayerStatus
from app.models.game import Game
from app.models.game_player import GamePlayer
from app.repositories import RepositoryProvider
from app.schemas.game import (
    AssignmentResultDTO,
    GameDTO,
    LobbyStateDTO,
    TurnStateDTO,
)
from app.services.assignment_service import AssignmentService
from app.services.game_service import GameService
from app.services.lobby_state_service import LobbyStateService
from app.services.turn_manager_service import TurnManagerService
from app.utils.exceptions import (
    GameFullError,
    GameNotFoundError,
    GameNotJoinableError,
    NumberAlreadyChosenError,
    NumberAlreadyTakenError,
    PlayerAlreadyJoinedError,
    PlayerNotInGameError,
)

logger = get_logger(__name__)


class LobbyService:
    """Coordinates lobby membership, seat numbers, and role assignment."""

    def __init__(
        self,
        repos: RepositoryProvider,
        assignment_service: AssignmentService,
        game_service: GameService,
        turn_manager: TurnManagerService,
        lobby_state: LobbyStateService,
    ) -> None:
        self._repos = repos
        self._assignment = assignment_service
        self._games = game_service
        self._turns = turn_manager
        self._lobby_state = lobby_state

    # --- Joining ------------------------------------------------------------

    async def join_game(self, *, code: str, user_id: int) -> GameDTO:
        """Add a user to a game's lobby by join code.

        Rejects joins when the game isn't accepting players, is full, or the
        user is already in it. The game row is locked so capacity checks are
        race-free. Each new (or re-joining) player is stamped with the next
        ``join_order`` so the turn sequence is deterministic.
        """
        game = await self._repos.games.get_by_code_for_update(code)
        if game is None:
            raise GameNotFoundError()
        if game.status != GameStatus.WAITING_PLAYERS:
            raise GameNotJoinableError()

        existing = await self._repos.players.get_by_game_and_user(game.id, user_id)
        if existing is not None and existing.status != PlayerStatus.LEFT:
            raise PlayerAlreadyJoinedError()

        active_count = await self._repos.players.count_active(game.id)
        if active_count >= game.player_count:
            raise GameFullError()

        join_order = await self._repos.players.next_join_order(game.id)
        if existing is not None:
            # Re-join after leaving: reset the row and give a fresh join order.
            existing.status = PlayerStatus.JOINED
            existing.number = None
            existing.selected_number = None
            existing.role_assigned_at = None
            existing.join_order = join_order
            await self._repos.session.flush()
        else:
            player = GamePlayer(
                game_id=game.id,
                user_id=user_id,
                status=PlayerStatus.JOINED,
                join_order=join_order,
            )
            await self._repos.players.add(player)

        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.PLAYER_JOINED,
            user_id=user_id,
            payload={"join_order": join_order},
        )
        logger.info(
            "player_joined", game_id=game.id, user_id=user_id, join_order=join_order
        )
        return self._games._to_dto(game)  # noqa: SLF001 - internal DTO mapper reuse

    # --- Turn state ---------------------------------------------------------

    async def get_turn_state(self, *, game_id: int) -> TurnStateDTO:
        """Return the FIFO turn snapshot for a game (see :class:`TurnStateDTO`)."""
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        return await self._turns.get_turn_state(game=game)

    async def get_turn_state_by_code(self, *, code: str) -> TurnStateDTO:
        """Same as :meth:`get_turn_state` but resolved by join code."""
        game = await self._repos.games.get_by_code(code)
        if game is None:
            raise GameNotFoundError()
        return await self._turns.get_turn_state(game=game)

    # --- Seat number selection ---------------------------------------------

    async def available_numbers(self, *, game_id: int) -> list[int]:
        """Return the seat numbers (1..player_count) that are still free."""
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        taken = set(await self._repos.players.taken_numbers(game_id))
        return [n for n in range(1, game.player_count + 1) if n not in taken]

    async def choose_number(
        self, *, game_id: int, user_id: int, number: int
    ) -> GameDTO:
        """Assign a seat ``number`` to the player, race-free and in turn.

        Locks the game row, enforces the FIFO turn, verifies the number is in
        range and not already taken, then persists it. A unique constraint on
        ``(game_id, number)`` is the final backstop against duplicates.

        Raises:
            LobbyNotCompleteError / NotPlayersTurnError: If it isn't this
                player's turn (or the lobby isn't full yet).
        """
        game = await self._repos.games.get_for_update(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.status != GameStatus.WAITING_PLAYERS:
            raise GameNotJoinableError()

        player = await self._repos.players.get_by_game_and_user(game.id, user_id)
        if player is None or player.status == PlayerStatus.LEFT:
            raise PlayerNotInGameError()
        if player.number is not None:
            raise NumberAlreadyChosenError()

        # FIFO gate: lobby must be complete and it must be this player's turn.
        await self._turns.ensure_players_turn(game=game, player=player)

        if not 1 <= number <= game.player_count:
            raise NumberAlreadyTakenError("این شماره در محدوده مجاز نیست.")
        if await self._repos.players.is_number_taken(game.id, number):
            raise NumberAlreadyTakenError()

        player.number = number
        player.selected_number = number
        player.status = PlayerStatus.NUMBERED
        await self._repos.session.flush()

        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.NUMBER_CHOSEN,
            user_id=user_id,
            payload={"number": number},
        )
        logger.info("number_chosen", game_id=game.id, user_id=user_id, number=number)
        return self._games._to_dto(game)  # noqa: SLF001

    # --- Role assignment ----------------------------------------------------

    async def assign_role(self, *, game_id: int, user_id: int) -> AssignmentResultDTO:
        """Assign a random role to the current-turn player and advance the turn.

        Holds the game row lock across the whole assignment so the role pool and
        the turn cursor cannot be raced. Returns the private role reveal plus the
        next player to notify (if any) and whether everyone is now assigned.

        Raises:
            LobbyNotCompleteError / NotPlayersTurnError: If it isn't this
                player's turn.
        """
        game = await self._repos.games.get_for_update(game_id)
        if game is None:
            raise GameNotFoundError()

        player = await self._repos.players.get_by_game_and_user(game.id, user_id)
        if player is None or player.status == PlayerStatus.LEFT:
            raise PlayerNotInGameError()

        # FIFO gate: enforce turn *before* touching the role pool.
        await self._turns.ensure_players_turn(game=game, player=player)

        role_dto = await self._assignment.assign_random_role(player=player)
        player.role_assigned_at = datetime.now(timezone.utc)
        await self._repos.session.flush()

        # Determine the next player in line (if any) and whether we're done.
        next_player = await self._turns.current_turn_player(game.id)
        all_assigned = await self._maybe_mark_ready(
            game_id=game.id, player_count=game.player_count
        )

        return AssignmentResultDTO(
            role=role_dto,
            game=self._games._to_dto(game),  # noqa: SLF001
            next_user_id=next_player.user_id if next_player else None,
            all_assigned=all_assigned,
        )

    async def _maybe_mark_ready(self, *, game_id: int, player_count: int) -> bool:
        """Promote the game to READY when all seats are filled and assigned."""
        active = await self._repos.players.count_active(game_id)
        assigned = await self._repos.players.count_assigned(game_id)
        if active == player_count and assigned == player_count:
            await self._games.mark_ready(game_id=game_id)
            return True
        return False

    # --- Leaving ------------------------------------------------------------

    async def leave_game(self, *, code: str, user_id: int) -> GameDTO:
        """Remove a player from the lobby, freeing their seat and role.

        Only allowed before the game starts. The role slot (if any) is returned
        to the pool so another player can receive it. The vacated turn passes to
        the next player in join order automatically.
        """
        game = await self._repos.games.get_by_code_for_update(code)
        if game is None:
            raise GameNotFoundError()
        if game.status in (GameStatus.IN_PROGRESS, GameStatus.FINISHED):
            raise GameNotJoinableError("پس از شروع بازی امکان خروج وجود ندارد.")

        player = await self._repos.players.get_by_game_and_user(game.id, user_id)
        if player is None or player.status == PlayerStatus.LEFT:
            raise PlayerNotInGameError()

        # Free the role slot back to the pool, if assigned.
        assignment = await self._repos.assignments.get_by_player(player.id)
        if assignment is not None:
            game_role = assignment.game_role
            game_role.remaining += 1
            await self._repos.assignments.delete(assignment)

        # Free the seat + mark as left. join_order is cleared so the freed slot
        # is not reused; a re-join gets a fresh (higher) order.
        player.number = None
        player.selected_number = None
        player.role_assigned_at = None
        player.join_order = None
        player.status = PlayerStatus.LEFT
        await self._repos.session.flush()

        # If the game had advanced to READY, a departure re-opens the lobby.
        if game.status == GameStatus.READY:
            await self._repos.games.update_status(game, GameStatus.WAITING_PLAYERS)

        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.PLAYER_LEFT,
            user_id=user_id,
        )
        logger.info("player_left", game_id=game.id, user_id=user_id)
        return self._games._to_dto(game)  # noqa: SLF001

    # --- Lobby state --------------------------------------------------------

    async def get_lobby_state(self, *, game_id: int) -> LobbyStateDTO:
        """Return an aggregate snapshot of the lobby for creator-facing status."""
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        joined = await self._repos.players.count_active(game_id)
        assigned = await self._repos.players.count_assigned(game_id)
        taken = await self._repos.players.taken_numbers(game_id)
        return LobbyStateDTO(
            game=self._games._to_dto(game),  # noqa: SLF001
            joined_count=joined,
            assigned_count=assigned,
            taken_numbers=taken,
            all_assigned=(joined == game.player_count and assigned == game.player_count),
        )
