"""Creator-only in-lobby / in-game controls: status, start, roster, finish."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot import texts
from app.bot.callbacks import GameControlCB
from app.bot.keyboards import build_in_game_keyboard
from app.config.logging import get_logger
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="game_control")


@router.callback_query(GameControlCB.filter(F.action == "status"))
async def on_status(
    callback: CallbackQuery,
    callback_data: GameControlCB,
    services: ServiceProvider,
) -> None:
    """Show the creator the current lobby status."""
    try:
        state = await services.lobby.get_lobby_state(game_id=callback_data.game_id)
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    text = texts.lobby_status(state)
    if state.all_assigned:
        text += "\n\n" + texts.all_assigned_notice()
    await callback.answer(text, show_alert=True)


@router.callback_query(GameControlCB.filter(F.action == "start"))
async def on_start(
    callback: CallbackQuery,
    callback_data: GameControlCB,
    services: ServiceProvider,
) -> None:
    """Start the game (creator only)."""
    try:
        await services.games.start_game(
            game_id=callback_data.game_id,
            creator_telegram_id=callback.from_user.id,
        )
        composition = await services.composition.get_game_composition(
            game_id=callback_data.game_id
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    # Creator-only summary: team head counts (no role or player names).
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.start_game_summary(composition),
        reply_markup=build_in_game_keyboard(game_id=callback_data.game_id),
    )
    await callback.answer("بازی شروع شد ▶️")



@router.callback_query(GameControlCB.filter(F.action == "roster"))
async def on_roster(
    callback: CallbackQuery,
    callback_data: GameControlCB,
    services: ServiceProvider,
) -> None:
    """Send the full player+role roster privately to the creator."""
    try:
        players = await services.roster.get_full_roster(
            game_id=callback_data.game_id,
            requester_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.answer(texts.roster(players))  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(GameControlCB.filter(F.action == "finish"))
async def on_finish(
    callback: CallbackQuery,
    callback_data: GameControlCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Finish the game (creator only) and release resources."""
    try:
        await services.games.finish_game(
            game_id=callback_data.game_id,
            creator_telegram_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(texts.game_finished())  # type: ignore[union-attr]
    await callback.answer("بازی پایان یافت 🏁")
