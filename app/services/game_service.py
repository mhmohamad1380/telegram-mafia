"""GameService: game creation, role configuration, and lifecycle transitions."""

from __future__ import annotations

from collections.abc import Mapping

from app.config.logging import get_logger

from app.models.enums import GameEventType, GameStatus
from app.models.game import Game
from app.models.game_role import GameRole
from app.repositories import RepositoryProvider
from app.schemas.game import GameDTO
from app.utils.codes import generate_game_code
from app.utils.exceptions import (
    GameNotFoundError,
    InvalidGameStateError,
    InvalidPlayerCountError,
    NotGameCreatorError,
    RoleSelectionMismatchError,
)

logger = get_logger(__name__)

MIN_PLAYERS = 3
MAX_PLAYERS = 40
_CODE_GENERATION_ATTEMPTS = 10


class GameService:
    """Owns the game lifecycle: create, configure roles, start, finish, cancel."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    # --- Creation -----------------------------------------------------------

    async def create_game(self, *, creator_telegram_id: int, player_count: int) -> GameDTO:
        """Create a new game in ``CREATING`` state with a unique join code.

        The creator must already exist as a user (ensured by the auth
        middleware). ``player_count`` is validated against sane bounds.
        """
        if not MIN_PLAYERS <= player_count <= MAX_PLAYERS:
            raise InvalidPlayerCountError(
                f"تعداد بازیکنان باید بین {MIN_PLAYERS} تا {MAX_PLAYERS} باشد."
            )

        code = await self._generate_unique_code()
        game = Game(
            code=code,
            creator_id=creator_telegram_id,
            player_count=player_count,
            status=GameStatus.CREATING,
        )
        await self._repos.games.add(game)
        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.GAME_CREATED,
            user_id=creator_telegram_id,
            payload={"player_count": player_count, "code": code},
        )
        logger.info("game_created", game_id=game.id, code=code, player_count=player_count)
        return self._to_dto(game)

    async def _generate_unique_code(self) -> str:
        """Generate a 6-digit code, retrying on the (rare) collision."""
        for _ in range(_CODE_GENERATION_ATTEMPTS):
            code = generate_game_code()
            if not await self._repos.games.code_exists(code):
                return code
        # Extremely unlikely; surface as a domain error rather than looping forever.
        raise InvalidGameStateError("تولید کد بازی ناموفق بود. دوباره تلاش کنید.")

    # --- Role configuration -------------------------------------------------

    async def configure_roles(
        self,
        *,
        game_id: int,
        creator_telegram_id: int,
        role_quantities: Mapping[int, int],
    ) -> GameDTO:
        """Persist the selected roles for a game and mark it ready for players.

        Args:
            game_id: Target game id.
            creator_telegram_id: Must match the game's creator.
            role_quantities: Mapping of ``role_id -> quantity``. The summed
                quantities must equal the game's ``player_count``.

        The game transitions ``CREATING -> WAITING_PLAYERS``.
        """
        game = await self._get_owned_game(game_id, creator_telegram_id)
        if game.status != GameStatus.CREATING:
            raise InvalidGameStateError("نقش‌ها فقط در مرحله ساخت قابل تنظیم هستند.")

        total = sum(role_quantities.values())
        if total != game.player_count:
            raise RoleSelectionMismatchError(
                "تعداد نقش‌های انتخاب‌شده باید دقیقاً برابر تعداد بازیکنان باشد "
                f"({total} از {game.player_count})."
            )

        # Validate that all referenced roles exist and are active.
        role_ids = [rid for rid, qty in role_quantities.items() if qty > 0]
        roles = await self._repos.roles.get_by_ids(role_ids)
        if len(roles) != len(role_ids):
            raise InvalidGameStateError("یک یا چند نقش انتخاب‌شده نامعتبر است.")

        # Replace any prior configuration, then insert fresh rows.
        for role_id, quantity in role_quantities.items():
            if quantity <= 0:
                continue
            self._repos.session.add(
                GameRole(
                    game_id=game.id,
                    role_id=role_id,
                    quantity=quantity,
                    remaining=quantity,
                )
            )
        await self._repos.session.flush()

        game.status = GameStatus.WAITING_PLAYERS
        await self._repos.games.update_status(game, GameStatus.WAITING_PLAYERS)
        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.ROLES_CONFIGURED,
            user_id=creator_telegram_id,
            payload={"role_quantities": dict(role_quantities)},
        )
        logger.info("roles_configured", game_id=game.id, total_roles=total)
        return self._to_dto(game)

    # --- Lifecycle transitions ---------------------------------------------

    async def start_game(self, *, game_id: int, creator_telegram_id: int) -> GameDTO:
        """Transition a ``READY`` game to ``IN_PROGRESS``."""
        game = await self._get_owned_game(game_id, creator_telegram_id)
        if game.status != GameStatus.READY:
            raise InvalidGameStateError(
                "بازی زمانی شروع می‌شود که همه بازیکنان نقش گرفته باشند."
            )
        await self._repos.games.update_status(game, GameStatus.IN_PROGRESS)
        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.GAME_STARTED,
            user_id=creator_telegram_id,
        )
        logger.info("game_started", game_id=game.id)
        return self._to_dto(game)

    async def finish_game(self, *, game_id: int, creator_telegram_id: int) -> GameDTO:
        """Transition an in-progress (or ready) game to ``FINISHED``."""
        game = await self._get_owned_game(game_id, creator_telegram_id)
        if game.status not in (GameStatus.IN_PROGRESS, GameStatus.READY):
            raise InvalidGameStateError("این بازی قابل پایان دادن نیست.")
        await self._repos.games.update_status(game, GameStatus.FINISHED)
        await self._repos.events.record(
            game_id=game.id,
            event_type=GameEventType.GAME_FINISHED,
            user_id=creator_telegram_id,
        )
        logger.info("game_finished", game_id=game.id)
        return self._to_dto(game)

    async def mark_ready(self, *, game_id: int) -> GameDTO:
        """Transition a game to ``READY`` once all players are assigned.

        Called by the assignment flow (not the creator directly).
        """
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.status == GameStatus.WAITING_PLAYERS:
            await self._repos.games.update_status(game, GameStatus.READY)
            await self._repos.events.record(
                game_id=game.id,
                event_type=GameEventType.GAME_READY,
            )
            logger.info("game_ready", game_id=game.id)
        return self._to_dto(game)

    # --- Helpers ------------------------------------------------------------

    async def get_by_code(self, code: str) -> GameDTO:
        """Return a game DTO by code (raises if not found)."""
        game = await self._repos.games.get_by_code(code)
        if game is None:
            raise GameNotFoundError()
        return self._to_dto(game)

    async def _get_owned_game(self, game_id: int, creator_telegram_id: int) -> Game:
        game = await self._repos.games.get(game_id)
        if game is None:
            raise GameNotFoundError()
        if game.creator_id != creator_telegram_id:
            raise NotGameCreatorError()
        return game

    @staticmethod
    def _to_dto(game: Game) -> GameDTO:
        return GameDTO(
            id=game.id,
            code=game.code,
            creator_id=game.creator_id,
            player_count=game.player_count,
            status=game.status,
        )
