"""SingleDeviceService: the "pass-the-phone" single-device game flow.

This service powers :class:`~app.models.enums.RoleMode.SINGLE_DEVICE` games,
where the whole table plays on the *creator's* phone. There is no join code and
no remote joining: on the creator's screen each player in turn taps a free seat
number, privately sees their random role, then hands the device to the next
player.

Because there are no per-player Telegram accounts, each claimed seat is backed by
a synthetic "بازیکن N" user whose id is derived deterministically from the game
id and seat number (:func:`_seat_user_id`) so it can never collide with real
Telegram ids, synthetic test users, or seats of another game.

Correctness / concurrency
--------------------------
Every seat claim locks the game row first (``SELECT ... FOR UPDATE``). In a
single-device game taps are inherently serial (one phone), but the lock keeps the
operation race-free regardless, and role uniqueness additionally rides on
:class:`AssignmentService`'s guarded ``UPDATE ... WHERE remaining > 0``. All of
it runs inside the caller's single transaction (the DI middleware owns the
commit), so any failure rolls the whole seat claim back atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.config.logging import get_logger
from app.models.enums import GameEventType, GameStatus, PlayerStatus, RoleMode
from app.models.game_player import GamePlayer
from app.repositories import RepositoryProvider
from app.schemas.game import PlayerRoleDTO
from app.services.assignment_service import AssignmentService
from app.services.game_service import GameService
from app.utils.exceptions import (
    GameNotFoundError,
    InvalidGameStateError,
    NotGameCreatorError,
    NumberAlreadyTakenError,
)

logger = get_logger(__name__)

#: Base of the reserved id range for single-device synthetic seat users. Chosen
#: well above real Telegram ids and distinct from the test-user range (9e9) so
#: the three id spaces can never overlap.
SINGLE_DEVICE_USER_BASE = 800_000_000_000
#: Multiplier that separates one game's seats from another's within the range.
_SEAT_GAME_STRIDE = 1_000


def _seat_user_id(game_id: int, number: int) -> int:
    """Deterministic synthetic user id for a seat within a single-device game."""
    return SINGLE_DEVICE_USER_BASE + game_id * _SEAT_GAME_STRIDE + number


@dataclass(frozen=True, slots=True)
class SingleDeviceState:
    """Snapshot of a single-device game used to render the shared screen."""

    game_id: int
    player_count: int
    taken_numbers: tuple[int, ...]
    free_numbers: tuple[int, ...]

    @property
    def all_filled(self) -> bool:
        """Whether every seat has been claimed."""
        return not self.free_numbers


@dataclass(frozen=True, slots=True)
class SeatClaimResult:
    """Outcome of a single seat claim: the drawn role and updated state."""

    number: int
    role: PlayerRoleDTO
    state: SingleDeviceState


class SingleDeviceService:
    """Runs the seat-by-seat draw for single-device ("pass-the-phone") games."""

    def __init__(
        self,
        repos: RepositoryProvider,
        assignment_service: AssignmentService,
        game_service: GameService,
    ) -> None:
        self._repos = repos
        self._assignment = assignment_service
        self._games = game_service

    async def get_state(
        self, *, game_id: int, creator_telegram_id: int
    ) -> SingleDeviceState:
        """Return the current seat state for the creator's shared screen."""
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.creator_id != creator_telegram_id:
            raise NotGameCreatorError()
        if game.role_mode != RoleMode.SINGLE_DEVICE:
            raise InvalidGameStateError("این بازی در حالت تک‌دستگاه نیست.")
        return await self._build_state(game_id=game.id, player_count=game.player_count)

    async def claim_seat(
        self, *, game_id: int, number: int, creator_telegram_id: int
    ) -> SeatClaimResult:
        """Claim seat ``number`` for the next player and draw a random role.

        Locks the game row so the operation is race-free, creates the synthetic
        seat user + player row, assigns a uniformly-random still-available role,
        and promotes the game to ``READY`` once every seat is filled.

        Raises:
            GameNotFoundError: Unknown game.
            NotGameCreatorError: Caller is not the game's creator.
            InvalidGameStateError: Game is not single-device or not accepting seats.
            NumberAlreadyTakenError: The seat was already claimed.
        """
        game = await self._repos.games.get_for_update(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.creator_id != creator_telegram_id:
            raise NotGameCreatorError()
        if game.role_mode != RoleMode.SINGLE_DEVICE:
            raise InvalidGameStateError("این بازی در حالت تک‌دستگاه نیست.")
        if game.status != GameStatus.WAITING_PLAYERS:
            raise InvalidGameStateError("این بازی پذیرای بازیکن جدید نیست.")
        if not 1 <= number <= game.player_count:
            raise InvalidGameStateError("شماره انتخاب‌شده نامعتبر است.")
        if await self._repos.players.is_number_taken(game.id, number):
            raise NumberAlreadyTakenError()

        # Back the seat with a deterministic synthetic user, then a player row.
        seat_user_id = _seat_user_id(game.id, number)
        await self._repos.users.upsert_from_telegram(
            telegram_id=seat_user_id,
            username=None,
            first_name=f"بازیکن {number}",
            last_name=None,
        )
        join_order = await self._repos.players.next_join_order(game.id)
        player = GamePlayer(
            game_id=game.id,
            user_id=seat_user_id,
            number=number,
            selected_number=number,
            join_order=join_order,
            status=PlayerStatus.NUMBERED,
        )
        await self._repos.players.add(player)
        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.NUMBER_CHOSEN,
            user_id=seat_user_id,
            payload={"player_id": player.id, "number": number},
        )

        # Draw a uniformly-random still-available role (atomic slot claim).
        role_dto = await self._assignment.assign_random_role(player=player)
        player.role_assigned_at = datetime.now(timezone.utc)
        await self._repos.session.flush()

        # Promote to READY once every seat is filled and assigned.
        await self._maybe_mark_ready(
            game_id=game.id, player_count=game.player_count
        )

        state = await self._build_state(
            game_id=game.id, player_count=game.player_count
        )
        logger.info(
            "single_device_seat_claimed",
            game_id=game.id,
            number=number,
            remaining=len(state.free_numbers),
        )
        return SeatClaimResult(number=number, role=role_dto, state=state)

    async def _build_state(
        self, *, game_id: int, player_count: int
    ) -> SingleDeviceState:
        taken = set(await self._repos.players.taken_numbers(game_id))
        free = tuple(n for n in range(1, player_count + 1) if n not in taken)
        return SingleDeviceState(
            game_id=game_id,
            player_count=player_count,
            taken_numbers=tuple(sorted(taken)),
            free_numbers=free,
        )

    async def _maybe_mark_ready(self, *, game_id: int, player_count: int) -> bool:
        """Promote the game to READY when all seats are filled and assigned."""
        active = await self._repos.players.count_active(game_id)
        assigned = await self._repos.players.count_assigned(game_id)
        if active == player_count and assigned == player_count:
            await self._games.mark_ready(game_id=game_id)
            return True
        return False
