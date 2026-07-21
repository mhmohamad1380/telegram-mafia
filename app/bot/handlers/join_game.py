"""Join-game and lobby flow with a strictly sequential (FIFO) turn.

Players join a lobby and are queued in join order. Nobody may pick a seat number
or receive a role until the lobby is full; then players act one at a time, in the
order they joined. When a player finishes, the bot proactively notifies the next
player that it's their turn.

The presentation layer only *renders* turn state — all rules (lobby
completeness, turn ownership, race-free number/role claims) are enforced in the
service layer under a row lock.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


from app.bot import texts
from app.bot.callbacks import LobbyActionCB, NumberPickCB
from app.bot.keyboards import (
    build_number_keyboard,
    build_player_lobby_keyboard,
    build_waiting_keyboard,
)
from app.bot.states import JoinGameStates
from app.config.logging import get_logger
from app.schemas.game import TurnStateDTO
from app.services import ServiceProvider
from app.utils.exceptions import DomainError, PlayerNotInGameError

logger = get_logger(__name__)
router = Router(name="join_game")

_CODE_LENGTH = 6


async def _safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit a message, ignoring Telegram's "message is not modified" error.

    This happens when a player taps the refresh button but nothing has changed
    (same text + markup); it is harmless, so we swallow it instead of surfacing
    a confusing error to the user.
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        raise



# --- Step 1: /join -> ask for code ------------------------------------------


async def start_join_game(message: Message, state: FSMContext) -> None:
    """Prompt the user for a game code.

    Shared entry point used by both the ``/join`` command and the persistent
    "🎮 ورود به بازی" menu button so their behaviour never diverges.
    """
    await state.clear()
    await state.set_state(JoinGameStates.enter_code)
    await message.answer(texts.ASK_GAME_CODE)


@router.message(Command("join"))
async def cmd_join(message: Message, state: FSMContext) -> None:
    """``/join`` command handler."""
    await start_join_game(message, state)



@router.message(JoinGameStates.enter_code)
async def on_code_entered(
    message: Message, state: FSMContext, services: ServiceProvider
) -> None:
    """Validate the code, join the lobby, then render the turn-aware screen."""
    raw = (message.text or "").strip()
    code = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if len(code) != _CODE_LENGTH or not code.isdigit():
        await message.answer("کد باید یک عدد ۶ رقمی باشد. دوباره تلاش کنید.")
        return

    user_id = message.from_user.id  # type: ignore[union-attr]
    try:
        game = await services.lobby.join_game(code=code, user_id=user_id)
    except DomainError as exc:
        await message.answer(f"⚠️ {exc.message_fa}")
        return

    await state.set_state(JoinGameStates.waiting_turn)
    await state.update_data(game_id=game.id, code=game.code)

    await message.answer(texts.joined_lobby(game))
    sent = await message.answer("⏳ در حال بررسی وضعیت...")
    await _render_turn_screen(
        services=services,
        game_id=game.id,
        user_id=user_id,
        edit_message=sent,
    )


# --- Turn-aware screen renderer ---------------------------------------------


async def _render_turn_screen(
    *,
    services: ServiceProvider,
    game_id: int,
    user_id: int,
    edit_message: Message,
) -> None:
    """Render the correct lobby screen for a player based on the turn state.

    Decision tree:
      * player already has a role -> show role + "my role" controls
      * lobby not full            -> waiting-for-lobby screen
      * not this player's turn    -> waiting (not your turn) screen
      * this player's turn:
          - no number yet         -> seat-number picker
          - number chosen         -> "get role" button
    """
    try:
        player = await services.players.get_player(game_id=game_id, user_id=user_id)
    except PlayerNotInGameError:
        await edit_message.edit_text("شما در این بازی حضور ندارید.")
        return

    # Already assigned -> allow viewing role again.
    if player.role_name_fa is not None or player.status.value == "ASSIGNED":
        try:
            role = await services.players.get_my_role(
                game_id=game_id, user_id=user_id
            )
        except DomainError:
            role = None
        if role is not None:
            await _safe_edit(
                edit_message,
                texts.role_reveal(role),
                reply_markup=build_player_lobby_keyboard(
                    game_id=game_id, has_number=True, has_role=True
                ),
            )
            return

    turn: TurnStateDTO = await services.lobby.get_turn_state(game_id=game_id)

    if not turn.lobby_complete:
        await _safe_edit(
            edit_message,
            texts.waiting_for_lobby(turn),
            reply_markup=build_waiting_keyboard(game_id=game_id),
        )
        return

    if turn.current_user_id != user_id:
        # It's someone else's turn.
        await _safe_edit(
            edit_message,
            texts.not_your_turn(),
            reply_markup=build_waiting_keyboard(game_id=game_id),
        )
        return

    # It's this player's turn.
    if player.number is None:
        numbers = await services.lobby.available_numbers(game_id=game_id)
        await _safe_edit(
            edit_message,
            texts.your_turn_notice() + "\n\n🔢 یک شماره انتخاب کنید:",
            reply_markup=build_number_keyboard(
                game_id=game_id, available_numbers=numbers
            ),
        )
    else:
        await _safe_edit(
            edit_message,
            texts.number_chosen(player.number),
            reply_markup=build_player_lobby_keyboard(
                game_id=game_id, has_number=True, has_role=False
            ),
        )



# --- Refresh / check-turn ----------------------------------------------------


@router.callback_query(LobbyActionCB.filter(F.action == "checkturn"))
async def on_check_turn(
    callback: CallbackQuery,
    callback_data: LobbyActionCB,
    services: ServiceProvider,
) -> None:
    """Re-render the turn screen when the player taps the refresh button."""
    await _render_turn_screen(
        services=services,
        game_id=callback_data.game_id,
        user_id=callback.from_user.id,
        edit_message=callback.message,  # type: ignore[arg-type]
    )
    await callback.answer()


# --- Step 2: pick a seat number ---------------------------------------------


@router.callback_query(NumberPickCB.filter())
async def on_number_pick(
    callback: CallbackQuery,
    callback_data: NumberPickCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Claim the chosen seat number (turn- and race-checked in the service)."""
    user_id = callback.from_user.id

    try:
        await services.lobby.choose_number(
            game_id=callback_data.game_id,
            user_id=user_id,
            number=callback_data.number,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        # Re-render so the player sees the up-to-date state (turn/numbers).
        await _render_turn_screen(
            services=services,
            game_id=callback_data.game_id,
            user_id=user_id,
            edit_message=callback.message,  # type: ignore[arg-type]
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.number_chosen(callback_data.number),
        reply_markup=build_player_lobby_keyboard(
            game_id=callback_data.game_id, has_number=True, has_role=False
        ),
    )
    await callback.answer("شماره ثبت شد ✅")


# --- Step 3: get / view role, leave -----------------------------------------


@router.callback_query(LobbyActionCB.filter(F.action == "assign"))
async def on_assign_role(
    callback: CallbackQuery,
    callback_data: LobbyActionCB,
    services: ServiceProvider,
    bot: Bot,
) -> None:
    """Assign a random role, reveal it privately, and notify the next player."""
    user_id = callback.from_user.id

    try:
        result = await services.lobby.assign_role(
            game_id=callback_data.game_id, user_id=user_id
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.role_reveal(result.role),
        reply_markup=build_player_lobby_keyboard(
            game_id=callback_data.game_id, has_number=True, has_role=True
        ),
    )
    await callback.answer("نقش شما مشخص شد 🎭")

    # Advance the turn: proactively ping the next player in line.
    if result.next_user_id is not None:
        await _notify_next_player(
            bot=bot,
            next_user_id=result.next_user_id,
            game_id=callback_data.game_id,
        )
    elif result.all_assigned:
        # Everyone has a role: let the creator know.
        await _notify_creator_all_assigned(
            bot=bot, services=services, game_id=callback_data.game_id
        )


async def _notify_next_player(*, bot: Bot, next_user_id: int, game_id: int) -> None:
    """Send the next player a private "it's your turn" message."""
    try:
        await bot.send_message(
            chat_id=next_user_id,
            text=texts.your_turn_notice(),
            reply_markup=build_waiting_keyboard(game_id=game_id),
        )
    except Exception as exc:  # noqa: BLE001 - the player may not have started the bot
        logger.warning(
            "notify_next_player_failed",
            user_id=next_user_id,
            game_id=game_id,
            error=str(exc),
        )


async def _notify_creator_all_assigned(
    *, bot: Bot, services: ServiceProvider, game_id: int
) -> None:
    """Notify the creator that every player now has a role."""
    try:
        state = await services.lobby.get_lobby_state(game_id=game_id)
        await bot.send_message(
            chat_id=state.game.creator_id,
            text=texts.all_assigned_notice(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "notify_creator_all_assigned_failed", game_id=game_id, error=str(exc)
        )


@router.callback_query(LobbyActionCB.filter(F.action == "myrole"))
async def on_view_role(
    callback: CallbackQuery,
    callback_data: LobbyActionCB,
    services: ServiceProvider,
) -> None:
    """Re-show the caller's own role privately."""
    user_id = callback.from_user.id
    try:
        role = await services.players.get_my_role(
            game_id=callback_data.game_id, user_id=user_id
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return
    await callback.answer(f"{role.name_fa}", show_alert=True)


@router.callback_query(LobbyActionCB.filter(F.action == "leave"))
async def on_leave(
    callback: CallbackQuery,
    callback_data: LobbyActionCB,
    state: FSMContext,
    services: ServiceProvider,
    bot: Bot,
) -> None:
    """Leave the lobby, freeing the seat and role, and re-point the turn."""
    data = await state.get_data()
    code: str = data.get("code", "")
    user_id = callback.from_user.id

    try:
        await services.lobby.leave_game(code=code, user_id=user_id)
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text("🚪 شما از بازی خارج شدید.")  # type: ignore[union-attr]
    await callback.answer()

    # If a departure re-opened someone's turn, ping the current-turn player.
    try:
        turn = await services.lobby.get_turn_state(game_id=callback_data.game_id)
        if turn.lobby_complete and turn.current_user_id is not None:
            await _notify_next_player(
                bot=bot,
                next_user_id=turn.current_user_id,
                game_id=callback_data.game_id,
            )
    except DomainError:
        pass
