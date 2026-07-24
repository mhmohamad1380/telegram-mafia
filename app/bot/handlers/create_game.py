"""Create-game wizard: scenario → player count → role selection → game code.

The wizard is scenario-driven end to end:

1. **Scenario** — the creator picks a game mode (:class:`ScenarioPickCB`); the
   scenario's overview is shown for confirmation.
2. **Player count** — quick-pick buttons are derived from the scenario's
   allowed/suggested counts; a custom count is also accepted and validated
   against the scenario bounds.
3. **Roles** — *flexible* scenarios show only the roles that scenario allows;
   *fixed* scenarios (e.g. Capo) skip selection entirely and jump to the summary
   with the prescribed composition.
4. **Summary → finalize** — the resolved ``role_id → quantity`` mapping is
   persisted and the join code revealed.

All scenario rules live behind :class:`ScenarioService`; this handler only
orchestrates the conversation.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.callbacks import (
    PlayerCountCB,
    RoleModeCB,
    RoleSetupActionCB,
    RoleToggleCB,
    ScenarioPickCB,
)
from app.bot.keyboards import (
    build_composition_summary_keyboard,
    build_role_mode_keyboard,
    build_role_selection_keyboard,
    build_scenario_count_keyboard,
    build_scenario_picker_keyboard,
)

from app.bot.states import CreateGameStates
from app.config.logging import get_logger
from app.models.enums import RoleCode, RoleMode

from app.scenarios import format_scenario_composition, format_scenario_overview
from app.schemas.game import CompositionResultDTO
from app.services import ServiceProvider
from app.services.game_service import MAX_PLAYERS, MIN_PLAYERS
from app.utils.codes import to_persian_digits
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="create_game")


# --- Step 1: /create_game -> choose scenario --------------------------------


async def start_create_game(message: Message, state: FSMContext, services: ServiceProvider) -> None:
    """Start the creation wizard by asking the creator to pick a scenario.

    Shared entry point used by both the ``/create_game`` command and the
    persistent "🎲 ساخت بازی" menu button so their behaviour never diverges.
    """
    await state.clear()
    await state.set_state(CreateGameStates.choose_scenario)
    scenarios = services.scenarios.list_scenarios()
    await message.answer(
        texts.ASK_SCENARIO,
        reply_markup=build_scenario_picker_keyboard(scenarios),
    )


@router.message(Command("create_game"))
async def cmd_create_game(
    message: Message, state: FSMContext, services: ServiceProvider
) -> None:
    """``/create_game`` command handler."""
    await start_create_game(message, state, services)


@router.callback_query(CreateGameStates.choose_scenario, ScenarioPickCB.filter())
async def on_scenario_pick(
    callback: CallbackQuery,
    callback_data: ScenarioPickCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Handle a scenario choice: show its overview and player-count options."""
    if callback_data.code == "__back__":
        scenarios = services.scenarios.list_scenarios()
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.ASK_SCENARIO,
            reply_markup=build_scenario_picker_keyboard(scenarios),
        )
        await callback.answer()
        return

    try:
        scenario = services.scenarios.get_scenario(callback_data.code)
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.set_state(CreateGameStates.choose_role_mode)
    await state.update_data(scenario_code=scenario.code)
    overview = format_scenario_overview(scenario)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{overview}\n\n{texts.ASK_ROLE_MODE}",
        reply_markup=build_role_mode_keyboard(),
    )
    await callback.answer()


# --- Step 1b: role delivery mode --------------------------------------------


@router.callback_query(CreateGameStates.choose_role_mode, RoleModeCB.filter())
async def on_role_mode_pick(
    callback: CallbackQuery,
    callback_data: RoleModeCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Record the chosen role-delivery mode, then ask for the player count.

    ``AUTO_ROLE_ASSIGNMENT`` gives each player a seat + random role the instant
    they join (no waiting); ``MANUAL_ROLE_SELECTION`` keeps the classic
    turn-based draw. The choice is stashed in the FSM and applied when the game
    is created in :func:`_begin_after_count`.
    """
    try:
        role_mode = RoleMode(callback_data.mode)
    except ValueError:
        await callback.answer("حالت نامعتبر است.", show_alert=True)
        return

    data = await state.get_data()
    scenario_code: str = data.get("scenario_code", "classic")
    scenario = services.scenarios.get_scenario(scenario_code)

    await state.set_state(CreateGameStates.choose_player_count)
    await state.update_data(role_mode=role_mode.value)
    overview = format_scenario_overview(scenario)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{overview}\n\n{texts.ASK_PLAYER_COUNT}",
        reply_markup=build_scenario_count_keyboard(scenario),
    )
    await callback.answer()


# --- Step 2: player count ---------------------------------------------------



@router.callback_query(CreateGameStates.choose_player_count, PlayerCountCB.filter())
async def on_player_count_button(
    callback: CallbackQuery,
    callback_data: PlayerCountCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Handle a quick-pick player count button."""
    await _begin_after_count(
        count=callback_data.count,
        state=state,
        services=services,
        user_id=callback.from_user.id,
        message=callback.message,  # type: ignore[arg-type]
        edit=True,
        callback=callback,
    )


@router.message(CreateGameStates.choose_player_count)
async def on_player_count_text(
    message: Message, state: FSMContext, services: ServiceProvider
) -> None:
    """Handle a custom, typed player count."""
    raw = (message.text or "").strip()
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
    await _begin_after_count(
        count=count,
        state=state,
        services=services,
        user_id=message.from_user.id,  # type: ignore[union-attr]
        message=message,
        edit=False,
        callback=None,
    )


async def _begin_after_count(
    *,
    count: int,
    state: FSMContext,
    services: ServiceProvider,
    user_id: int,
    message: Message,
    edit: bool,
    callback: CallbackQuery | None,
) -> None:
    """Validate the count for the chosen scenario, create the game, then branch.

    Fixed scenarios jump straight to the composition summary; flexible ones
    open the (scenario-scoped) role-selection keyboard.
    """
    data = await state.get_data()
    scenario_code: str = data.get("scenario_code", "classic")
    role_mode = RoleMode(
        data.get("role_mode", RoleMode.MANUAL_ROLE_SELECTION.value)
    )
    try:
        scenario = services.scenarios.get_scenario(scenario_code)
        services.scenarios.validate_player_count(scenario, count)
    except DomainError as exc:
        await _reply(message, callback, f"⚠️ {exc.message_fa}", edit=False)
        return

    try:
        game = await services.games.create_game(
            creator_telegram_id=user_id,
            player_count=count,
            scenario_code=scenario.code,
            role_mode=role_mode,
        )

    except DomainError as exc:
        await _reply(message, callback, f"⚠️ {exc.message_fa}", edit=False)
        return

    await state.update_data(
        game_id=game.id,
        player_count=count,
        selected_codes=[],
        selected_custom_ids=[],
    )


    if scenario.is_fixed:
        # No role selection: resolve the prescribed composition and summarise.
        try:
            result = await services.scenarios.resolve(
                scenario=scenario, player_count=count
            )
        except DomainError as exc:
            await _reply(message, callback, f"⚠️ {exc.message_fa}", edit=False)
            return
        await _show_summary(
            message=message,
            callback=callback,
            state=state,
            game_id=game.id,
            result=result,
            scenario_note=format_scenario_composition(scenario, count),
            edit=edit,
        )
        if callback is not None:
            await callback.answer()
        return

    # Flexible scenario: show the scenario's selectable roles plus the
    # creator's own custom roles ("نقش‌های من").
    roles = await services.scenarios.get_selectable_roles(scenario)
    custom_roles = await services.custom_roles.list_for_owner(owner_id=user_id)
    await state.set_state(CreateGameStates.choose_roles)
    text = _role_selection_text(scenario.name_fa, count, 0)
    markup = build_role_selection_keyboard(
        game_id=game.id,
        roles=roles,
        selected_ids=[],
        selected_total=0,
        target_count=count,
        custom_roles=custom_roles,
        selected_custom_ids=[],
    )
    await _reply(message, callback, text, edit=edit, reply_markup=markup)
    if callback is not None:
        await callback.answer()



# --- Step 3: role selection (flexible scenarios) ----------------------------


@router.callback_query(CreateGameStates.choose_roles, RoleToggleCB.filter())
async def on_role_toggle(
    callback: CallbackQuery,
    callback_data: RoleToggleCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Toggle a role (catalog or custom) in/out and re-render the keyboard."""
    data = await state.get_data()
    player_count: int = data["player_count"]
    scenario_code: str = data.get("scenario_code", "classic")
    selected: list[int] = list(data.get("selected_ids", []))
    selected_custom: list[int] = list(data.get("selected_custom_ids", []))

    # The combined selection may never exceed the player count.
    def _total() -> int:
        return len(selected) + len(selected_custom)

    if callback_data.is_custom:
        if callback_data.role_id in selected_custom:
            selected_custom.remove(callback_data.role_id)
        else:
            if _total() >= player_count:
                await callback.answer(
                    "تعداد نقش‌ها نمی‌تواند از تعداد بازیکنان بیشتر باشد.",
                    show_alert=True,
                )
                return
            selected_custom.append(callback_data.role_id)
    else:
        if callback_data.role_id in selected:
            selected.remove(callback_data.role_id)
        else:
            if _total() >= player_count:
                await callback.answer(
                    "تعداد نقش‌ها نمی‌تواند از تعداد بازیکنان بیشتر باشد.",
                    show_alert=True,
                )
                return
            selected.append(callback_data.role_id)

    await state.update_data(
        selected_ids=selected, selected_custom_ids=selected_custom
    )

    scenario = services.scenarios.get_scenario(scenario_code)
    roles = await services.scenarios.get_selectable_roles(scenario)
    custom_roles = await services.custom_roles.list_for_owner(
        owner_id=callback.from_user.id
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        _role_selection_text(scenario.name_fa, player_count, _total()),
        reply_markup=build_role_selection_keyboard(
            game_id=callback_data.game_id,
            roles=roles,
            selected_ids=selected,
            selected_total=_total(),
            target_count=player_count,
            custom_roles=custom_roles,
            selected_custom_ids=selected_custom,
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
    """Resolve the selection via the scenario engine and show the summary."""
    data = await state.get_data()
    player_count: int = data["player_count"]
    scenario_code: str = data.get("scenario_code", "classic")
    selected_ids: list[int] = list(data.get("selected_ids", []))
    selected_custom_ids: list[int] = list(data.get("selected_custom_ids", []))

    scenario = services.scenarios.get_scenario(scenario_code)
    # Translate selected role ids back to codes for the resolver.
    selectable = await services.scenarios.get_selectable_roles(scenario)
    code_by_id = {r.role_id: r.code for r in selectable}
    selected_codes: list[RoleCode] = [
        code_by_id[rid] for rid in selected_ids if rid in code_by_id
    ]

    # Resolve the creator's selected custom roles to DTOs (owner-scoped).
    owned_custom = await services.custom_roles.list_for_owner(
        owner_id=callback.from_user.id
    )
    custom_by_id = {c.id: c for c in owned_custom}
    selected_custom = [
        custom_by_id[cid] for cid in selected_custom_ids if cid in custom_by_id
    ]

    try:
        result = await services.scenarios.resolve(
            scenario=scenario,
            player_count=player_count,
            selected_codes=selected_codes,
            selected_custom_roles=selected_custom,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return


    await _show_summary(
        message=callback.message,  # type: ignore[arg-type]
        callback=callback,
        state=state,
        game_id=callback_data.game_id,
        result=result,
        scenario_note="",
        edit=True,
    )
    await callback.answer()


# --- Step 4: composition summary confirmation -------------------------------


@router.callback_query(
    CreateGameStates.confirm_summary, RoleSetupActionCB.filter(F.action == "back")
)
async def on_summary_back(
    callback: CallbackQuery,
    callback_data: RoleSetupActionCB,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Return from the summary to the role-selection keyboard for edits.

    For fixed scenarios there is nothing to edit, so we bounce back to the
    scenario picker instead.
    """
    data = await state.get_data()
    player_count: int = data["player_count"]
    scenario_code: str = data.get("scenario_code", "classic")
    selected: list[int] = list(data.get("selected_ids", []))
    selected_custom: list[int] = list(data.get("selected_custom_ids", []))
    scenario = services.scenarios.get_scenario(scenario_code)

    if scenario.is_fixed:
        await state.set_state(CreateGameStates.choose_scenario)
        scenarios = services.scenarios.list_scenarios()
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.ASK_SCENARIO,
            reply_markup=build_scenario_picker_keyboard(scenarios),
        )
        await callback.answer()
        return

    roles = await services.scenarios.get_selectable_roles(scenario)
    custom_roles = await services.custom_roles.list_for_owner(
        owner_id=callback.from_user.id
    )
    total = len(selected) + len(selected_custom)
    await state.set_state(CreateGameStates.choose_roles)
    await callback.message.edit_text(  # type: ignore[union-attr]
        _role_selection_text(scenario.name_fa, player_count, total),
        reply_markup=build_role_selection_keyboard(
            game_id=callback_data.game_id,
            roles=roles,
            selected_ids=selected,
            selected_total=total,
            target_count=player_count,
            custom_roles=custom_roles,
            selected_custom_ids=selected_custom,
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
    stored_custom: dict[str, int] = data.get("custom_role_quantities", {})
    role_quantities = {int(k): v for k, v in stored.items()}
    custom_role_quantities = {int(k): v for k, v in stored_custom.items()}
    if not role_quantities and not custom_role_quantities:
        await callback.answer("خطا در ترکیب نقش‌ها. دوباره تلاش کنید.", show_alert=True)
        return

    try:
        game = await services.games.configure_roles(
            game_id=callback_data.game_id,
            creator_telegram_id=callback.from_user.id,
            role_quantities=role_quantities,
            custom_role_quantities=custom_role_quantities,
        )
    except DomainError as exc:

        await callback.answer(exc.message_fa, show_alert=True)
        return

    await state.set_state(CreateGameStates.waiting_players)
    await state.update_data(game_id=game.id)
    await callback.message.edit_text(texts.game_created(game))  # type: ignore[union-attr]
    await callback.answer("بازی ساخته شد ✅")


# --- Helpers ----------------------------------------------------------------


async def _show_summary(
    *,
    message: Message,
    callback: CallbackQuery | None,
    state: FSMContext,
    game_id: int,
    result,
    scenario_note: str,
    edit: bool,
) -> None:
    """Stash the resolved composition and render the confirmation screen."""
    await state.set_state(CreateGameStates.confirm_summary)
    await state.update_data(
        role_quantities={str(k): v for k, v in result.role_quantities.items()},
        custom_role_quantities={
            str(k): v for k, v in result.custom_role_quantities.items()
        },
    )

    # Adapt the scenario result into the DTO the summary text expects.
    dto = CompositionResultDTO(
        role_quantities=result.role_quantities,
        composition=result.composition,
        roles_ordered=result.roles_ordered,
        added=result.added,
        player_count=result.player_count,
    )
    body = texts.composition_summary(dto)
    if scenario_note:
        body = f"{scenario_note}\n\n{body}"
    markup = build_composition_summary_keyboard(game_id=game_id)
    await _reply(message, callback, body, edit=edit, reply_markup=markup)


async def _reply(
    message: Message,
    callback: CallbackQuery | None,
    text: str,
    *,
    edit: bool,
    reply_markup=None,
) -> None:
    """Send or edit a message depending on whether we came from a callback."""
    if edit and callback is not None:
        await callback.message.edit_text(text, reply_markup=reply_markup)  # type: ignore[union-attr]
    else:
        await message.answer(text, reply_markup=reply_markup)


def _role_selection_text(scenario_name: str, player_count: int, selected: int) -> str:
    return (
        f"🎭 <b>انتخاب نقش‌ها</b> — {scenario_name}\n\n"
        f"تعداد بازیکنان: {to_persian_digits(player_count)}\n"
        f"نقش‌های انتخاب‌شده: {to_persian_digits(selected)}\n\n"
        "نقش‌های ویژه دلخواه را انتخاب کنید. لازم نیست همه‌ی جای‌ها را پر کنید؛ "
        "جای‌های باقی‌مانده به‌صورت خودکار با «شهروند ساده» و «مافیای ساده» و با "
        "رعایت نسبت استاندارد سناریو پر می‌شوند. سپس «تایید» را بزنید."
    )
