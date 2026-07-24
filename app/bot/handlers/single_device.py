"""Single-device ("pass-the-phone") game flow handlers.

The whole table plays on the creator's device. There is no join code and no
remote joining: the shared screen shows a grid of free seat numbers; each player
in turn taps a seat, privately sees their random role, taps "hide", and passes
the phone on. Once every seat is filled the creator starts the game.

All callbacks are authorised by game ownership (the tapping account is always the
creator's), never by the tapping user's identity — see :class:`SingleDeviceCB`.
The seat draw, role assignment and READY-promotion all live in
:class:`~app.services.single_device_service.SingleDeviceService`; these handlers
only render screens and translate taps into service calls.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot import texts
from app.bot.callbacks import SingleDeviceCB
from app.bot.keyboards import (
    build_in_game_keyboard,
    build_single_device_reveal_keyboard,
    build_single_device_seats_keyboard,
)
from app.bot.states import CreateGameStates
from app.config.logging import get_logger
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="single_device")


async def render_seats(
    callback: CallbackQuery,
    *,
    game_id: int,
    services: ServiceProvider,
) -> None:
    """(Re)draw the shared seat-selection screen from the current game state."""
    state = await services.single_device.get_state(
        game_id=game_id, creator_telegram_id=callback.from_user.id
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.single_device_screen(
            taken=len(state.taken_numbers), total=state.player_count
        ),
        reply_markup=build_single_device_seats_keyboard(
            game_id=game_id,
            free_numbers=list(state.free_numbers),
            can_start=state.all_filled,
        ),
    )


@router.callback_query(
    CreateGameStates.single_device, SingleDeviceCB.filter(F.action == "pick")
)
async def on_pick(
    callback: CallbackQuery,
    callback_data: SingleDeviceCB,
    services: ServiceProvider,
) -> None:
    """Claim the tapped seat, draw a role, and reveal it privately on-screen."""
    try:
        result = await services.single_device.claim_seat(
            game_id=callback_data.game_id,
            number=callback_data.number,
            creator_telegram_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.single_device_reveal(result.role, number=result.number),
        reply_markup=build_single_device_reveal_keyboard(
            game_id=callback_data.game_id
        ),
    )
    await callback.answer()


@router.callback_query(
    CreateGameStates.single_device, SingleDeviceCB.filter(F.action == "hide")
)
async def on_hide(
    callback: CallbackQuery,
    callback_data: SingleDeviceCB,
    services: ServiceProvider,
) -> None:
    """Hide the revealed role and return to the seat grid for the next player."""
    try:
        await render_seats(
            callback, game_id=callback_data.game_id, services=services
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return
    await callback.answer()


@router.callback_query(
    CreateGameStates.single_device, SingleDeviceCB.filter(F.action == "start")
)
async def on_start(
    callback: CallbackQuery,
    callback_data: SingleDeviceCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Start the game once every seat is filled (creator only)."""
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

    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.start_game_summary(composition),
        reply_markup=build_in_game_keyboard(game_id=callback_data.game_id),
    )
    await callback.answer("بازی شروع شد ▶️")


@router.callback_query(
    CreateGameStates.single_device, SingleDeviceCB.filter(F.action == "cancel")
)
async def on_cancel(
    callback: CallbackQuery,
    callback_data: SingleDeviceCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Abort a single-device game before it starts and release its resources."""
    try:
        await services.games.finish_game(
            game_id=callback_data.game_id,
            creator_telegram_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(texts.CANCELLED)  # type: ignore[union-attr]
    await callback.answer()
