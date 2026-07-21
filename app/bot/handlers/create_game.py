"""Create-game wizard: player count -> role selection -> game code."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.callbacks import PlayerCountCB, RoleSetupActionCB, RoleToggleCB
from app.bot.keyboards import (
    build_composition_summary_keyboard,
    build_player_count_keyboard,
    build_role_selection_keyboard,
)

from app.bot.states import CreateGameStates
from app.config.logging import get_logger
from app.services import ServiceProvider
from app.services.game_service import MAX_PLAYERS, MIN_PLAYERS
from app.utils.codes import to_persian_digits
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="create_game")


# --- Step 1: /create_game -> ask player count -------------------------------


async def start_create_game(message: Message, state: FSMContext) -> None:
    """Start the creation wizard by asking for the player count.

    Shared entry point used by both the ``/create_game`` command and the
    persistent "🎲 ساخت بازی" menu button so their behaviour never diverges.
    """
    await state.clear()
    await state.set_state(CreateGameStates.choose_player_count)
    await message.answer(
        texts.ASK_PLAYER_COUNT,
        reply_markup=build_player_count_keyboard(),
    )


@router.message(Command("create_game"))
async def cmd_create_game(message: Message, state: FSMContext) -> None:
    """``/create_game`` command handler."""
    await start_create_game(message, state)



@router.callback_query(
    CreateGameStates.choose_player_count, PlayerCountCB.filter()
)
async def on_player_count_button(
    callback: CallbackQuery,
    callback_data: PlayerCountCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Handle a quick-pick player count button."""
    await _begin_role_selection(
        count=callback_data.count,
        state=state,
        services=services,
        user_id=callback.from_user.id,
        message=callback.message,  # type: ignore[arg-type]
    )
    await callback.answer()


@router.message(CreateGameStates.choose_player_count)
async def on_player_count_text(
    message: Message, state: FSMContext, services: ServiceProvider
) -> None:
    """Handle a custom, typed player count."""
    raw = (message.text or "").strip()
    # Accept both ASCII and Persian digits.
    normalized = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not normalized.isdigit():
        await message.answer("لطفاً یک عدد معتبر ارسال کنید.")
        return
    count = int(normalized)
    if not MIN_PLAYERS <= count <= MAX_PLAYERS:
        await message.answer(
            f"تعداد بازیکنان باید بین {to_persian_digits(MIN_PLAYERS)} تا "
            f"{to_persian_digits(MAX_PLAYERS)} باشد."
        )
        return
    await _begin_role_selection(
        count=count,
        state=state,
        services=services,
        user_id=message.from_user.id,  # type: ignore[union-attr]
        message=message,
    )


async def _begin_role_selection(
    *,
    count: int,
    state: FSMContext,
    services: ServiceProvider,
    user_id: int,
    message: Message,
) -> None:
    """Create the game record and render the role-selection keyboard."""
    try:
        game = await services.games.create_game(
            creator_telegram_id=user_id, player_count=count
        )
    except DomainError as exc:
        await message.answer(f"⚠️ {exc.message_fa}")
        return

    catalog = await services.roles.list_catalog()
    # Store wizard context in FSM.
    await state.set_state(CreateGameStates.choose_roles)
    await state.update_data(
        game_id=game.id,
        player_count=count,
        selected_ids=[],
    )
    await message.answer(
        _role_selection_text(count, 0),
        reply_markup=build_role_selection_keyboard(
            game_id=game.id,
            roles=catalog,
            selected_ids=[],
            selected_total=0,
            target_count=count,
        ),
    )


# --- Step 2: role selection -------------------------------------------------


@router.callback_query(CreateGameStates.choose_roles, RoleToggleCB.filter())
async def on_role_toggle(
    callback: CallbackQuery,
    callback_data: RoleToggleCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Toggle a role in/out of the selection and re-render the keyboard.

    Each selected role counts as one player slot (quantity 1). The creator may
    pick *any* number of roles up to the player count; the remaining slots are
    auto-filled with simple citizens/mafia at confirm time.
    """
    data = await state.get_data()
    player_count: int = data["player_count"]
    selected: list[int] = list(data.get("selected_ids", []))

    if callback_data.role_id in selected:
        selected.remove(callback_data.role_id)
    else:
        if len(selected) >= player_count:
            await callback.answer(
                "تعداد نقش‌ها نمی‌تواند از تعداد بازیکنان بیشتر باشد.",
                show_alert=True,
            )
            return
        selected.append(callback_data.role_id)


    await state.update_data(selected_ids=selected)

    catalog = await services.roles.list_catalog()
    await callback.message.edit_text(  # type: ignore[union-attr]
        _role_selection_text(player_count, len(selected)),
        reply_markup=build_role_selection_keyboard(
            game_id=callback_data.game_id,
            roles=catalog,
            selected_ids=selected,
            selected_total=len(selected),
            target_count=player_count,
        ),
    )
    await callback.answer()


@router.callback_query(
    CreateGameStates.choose_roles, RoleSetupActionCB.filter(F.action == "noop")
)
async def on_role_noop(callback: CallbackQuery) -> None:
    """No-op for section-header / counter buttons."""
    await callback.answer()


@router.callback_query(
    CreateGameStates.choose_roles, RoleSetupActionCB.filter(F.action == "locked")
)
async def on_role_locked(callback: CallbackQuery, state: FSMContext) -> None:
    """Explain why a role is locked (e.g. Mason group needs a big table)."""
    data = await state.get_data()
    player_count: int = data.get("player_count", 0)
    from app.utils.role_catalog import MASON_MIN_PLAYERS

    await callback.answer(
        "این نقش فقط در بازی‌های بزرگ فعال است.\n"
        f"برای گروه ماسون حداقل {to_persian_digits(MASON_MIN_PLAYERS)} بازیکن لازم است "
        f"(بازی فعلی: {to_persian_digits(player_count)} نفر).",
        show_alert=True,
    )



@router.callback_query(
    CreateGameStates.choose_roles, RoleSetupActionCB.filter(F.action == "cancel")
)
async def on_role_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the wizard."""
    await state.clear()
    await callback.message.edit_text(texts.CANCELLED)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(
    CreateGameStates.choose_roles, RoleSetupActionCB.filter(F.action == "confirm")
)
async def on_role_confirm(
    callback: CallbackQuery,
    callback_data: RoleSetupActionCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Auto-complete the selection and show the composition summary.

    The creator may select any subset of roles (even none). The composition
    service validates the mafia/city ratio and fills the remaining slots with
    simple citizens/mafia. The final config is persisted only after the creator
    confirms the summary (``finalize`` action).
    """
    data = await state.get_data()
    player_count: int = data["player_count"]
    selected: list[int] = list(data.get("selected_ids", []))

    try:
        result = await services.composition.complete_composition(
            player_count=player_count, selected_role_ids=selected
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    # Stash the resolved role->quantity map for the finalize step.
    await state.set_state(CreateGameStates.confirm_summary)
    await state.update_data(
        role_quantities={str(k): v for k, v in result.role_quantities.items()},
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.composition_summary(result),
        reply_markup=build_composition_summary_keyboard(
            game_id=callback_data.game_id
        ),
    )
    await callback.answer()


# --- Step 3: composition summary confirmation -------------------------------


@router.callback_query(
    CreateGameStates.confirm_summary, RoleSetupActionCB.filter(F.action == "back")
)
async def on_summary_back(
    callback: CallbackQuery,
    callback_data: RoleSetupActionCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Return from the summary to the role-selection keyboard for edits."""
    data = await state.get_data()
    player_count: int = data["player_count"]
    selected: list[int] = list(data.get("selected_ids", []))

    catalog = await services.roles.list_catalog()
    await state.set_state(CreateGameStates.choose_roles)
    await callback.message.edit_text(  # type: ignore[union-attr]
        _role_selection_text(player_count, len(selected)),
        reply_markup=build_role_selection_keyboard(
            game_id=callback_data.game_id,
            roles=catalog,
            selected_ids=selected,
            selected_total=len(selected),
            target_count=player_count,
        ),
    )
    await callback.answer()


@router.callback_query(
    CreateGameStates.confirm_summary,
    RoleSetupActionCB.filter(F.action == "finalize"),
)
async def on_summary_finalize(
    callback: CallbackQuery,
    callback_data: RoleSetupActionCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Persist the resolved role configuration and reveal the game code."""
    data = await state.get_data()
    stored: dict[str, int] = data.get("role_quantities", {})
    role_quantities = {int(k): v for k, v in stored.items()}
    if not role_quantities:
        await callback.answer("خطا در ترکیب نقش‌ها. دوباره تلاش کنید.", show_alert=True)
        return

    try:
        game = await services.games.configure_roles(
            game_id=callback_data.game_id,
            creator_telegram_id=callback.from_user.id,
            role_quantities=role_quantities,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.set_state(CreateGameStates.waiting_players)
    await state.update_data(game_id=game.id)
    await callback.message.edit_text(texts.game_created(game))  # type: ignore[union-attr]
    await callback.answer("بازی ساخته شد ✅")


def _role_selection_text(player_count: int, selected: int) -> str:
    return (
        "🎭 <b>انتخاب نقش‌ها</b>\n\n"
        f"تعداد بازیکنان: {to_persian_digits(player_count)}\n"
        f"نقش‌های انتخاب‌شده: {to_persian_digits(selected)}\n\n"
        "نقش‌های ویژه دلخواه را انتخاب کنید. لازم نیست همه‌ی جای‌ها را پر کنید؛ "
        "جای‌های باقی‌مانده به‌صورت خودکار با «شهروند ساده» و «مافیای ساده» و با "
        "رعایت نسبت استاندارد پر می‌شوند. سپس «تایید» را بزنید."
    )

