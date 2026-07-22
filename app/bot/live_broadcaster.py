"""Presentation-side broadcaster for live lobby synchronization.

Bridges the framework-agnostic :class:`~app.services.live_sync_service.\
LiveGameSyncService` (which only *computes* what each waiting player's screen
should show) to actual Telegram ``editMessageText`` calls.

The single public entry point, :func:`broadcast_lobby_sync`, is meant to be
called by a handler right after it mutates shared lobby state (a join, a seat
pick, a role assignment, or a departure). It:

1. asks the service for the up-to-date screen of every eligible waiting player
   (excluding the actor, whose own handler already refreshed their view), and
2. edits each player's stored lobby message in place, rebuilding the correct
   inline keyboard for the screen ``kind``.

It is intentionally *best-effort and non-fatal*: a failure to edit one player's
message (they blocked the bot, deleted the message, or nothing changed) is
logged and skipped so it can never break the acting player's flow. The "message
is not modified" error in particular is treated as success — it simply means
that player was already looking at the correct screen.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.bot.keyboards import (
    build_number_keyboard,
    build_player_lobby_keyboard,
    build_waiting_keyboard,
)
from app.config.logging import get_logger
from app.schemas.game import PlayerSyncScreenDTO
from app.services import ServiceProvider

logger = get_logger(__name__)


def _keyboard_for(screen: PlayerSyncScreenDTO):
    """Rebuild the inline keyboard matching a computed screen's ``kind``."""
    if screen.kind == "numbers":
        return build_number_keyboard(
            game_id=screen.game_id,
            available_numbers=screen.available_numbers,
        )
    if screen.kind == "getrole":
        return build_player_lobby_keyboard(
            game_id=screen.game_id, has_number=True, has_role=False
        )
    # "waiting" (and any unknown kind) -> refresh/leave controls.
    return build_waiting_keyboard(game_id=screen.game_id)


async def broadcast_lobby_sync(
    *,
    bot: Bot,
    services: ServiceProvider,
    game_id: int,
    exclude_user_id: int | None = None,
) -> int:
    """Push the latest lobby screen to every eligible waiting player.

    Returns the number of messages successfully edited (useful for tests and
    diagnostics). Never raises: each per-player failure is swallowed and logged
    so a broadcast can never disrupt the caller's own response.
    """
    try:
        screens = await services.live_sync.compute_sync_screens(
            game_id=game_id, exclude_user_id=exclude_user_id
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must not crash a handler
        logger.warning(
            "live_sync_compute_failed", game_id=game_id, error=str(exc)
        )
        return 0

    updated = 0
    for screen in screens:
        try:
            await bot.edit_message_text(
                text=screen.text,
                chat_id=screen.chat_id,
                message_id=screen.message_id,
                reply_markup=_keyboard_for(screen),
            )
            updated += 1
        except TelegramBadRequest as exc:
            # "not modified" means the player already saw the right screen.
            if "message is not modified" in str(exc).lower():
                updated += 1
                continue
            logger.debug(
                "live_sync_edit_skipped",
                game_id=game_id,
                user_id=screen.user_id,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - blocked bot, deleted msg, etc.
            logger.debug(
                "live_sync_edit_failed",
                game_id=game_id,
                user_id=screen.user_id,
                error=str(exc),
            )
    logger.info(
        "live_sync_broadcast",
        game_id=game_id,
        targets=len(screens),
        updated=updated,
    )
    return updated
