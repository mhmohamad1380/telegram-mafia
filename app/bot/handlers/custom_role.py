"""Handlers for the "🛠 نقش‌های من" custom-role management feature.

Lets a user build a private library of custom roles (name + team + optional
description) through a small FSM wizard, browse them, and delete them. All
persistence goes through :class:`CustomRoleService`; the transaction is committed
by :class:`DatabaseMiddleware` once the handler returns.

Listing/detail navigation edits the inline card in place, while the creation
wizard is a linear message flow that ends by returning to the list.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.callbacks import CustomRoleCB, CustomRoleTeamCB
from app.bot.keyboards import (
    BTN_CUSTOM_ROLES,
    build_custom_role_delete_confirm_keyboard,
    build_custom_role_detail_keyboard,
    build_custom_roles_keyboard,
    build_empty_custom_roles_keyboard,
    build_main_menu_keyboard,
    build_team_picker_keyboard,
)
from app.bot.states import CustomRoleStates
from app.config.logging import get_logger
from app.models.enums import RoleTeam
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="custom_role")


# --- Listing -----------------------------------------------------------------


async def _show_list(target: Message, services: ServiceProvider, user_id: int) -> None:
    """Render the user's custom-role list (or the empty-state) on ``target``."""
    roles = await services.custom_roles.list_for_owner(owner_id=user_id)
    if not roles:
        await target.answer(
            texts.CUSTOM_ROLES_EMPTY,
            reply_markup=build_empty_custom_roles_keyboard(),
        )
        return
    await target.answer(
        texts.CUSTOM_ROLES_INTRO,
        reply_markup=build_custom_roles_keyboard(roles),
    )


@router.message(F.text == BTN_CUSTOM_ROLES)
async def on_menu_custom_roles(
    message: Message,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Main-menu «🛠 نقش‌های من» button — open the custom-role list."""
    await state.clear()
    await _show_list(message, services, message.from_user.id)


@router.callback_query(CustomRoleCB.filter(F.action == "list"))
async def on_custom_roles_list(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Return to the list from a detail/confirmation screen (edits in place)."""
    await state.clear()
    roles = await services.custom_roles.list_for_owner(owner_id=callback.from_user.id)
    if not roles:
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.CUSTOM_ROLES_EMPTY,
            reply_markup=build_empty_custom_roles_keyboard(),
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            texts.CUSTOM_ROLES_INTRO,
            reply_markup=build_custom_roles_keyboard(roles),
        )
    await callback.answer()


@router.callback_query(CustomRoleCB.filter(F.action == "open"))
async def on_custom_role_open(
    callback: CallbackQuery,
    callback_data: CustomRoleCB,
    services: ServiceProvider,
) -> None:
    """Open the detail screen for one custom role."""
    try:
        role = await services.custom_roles.get_for_owner(
            custom_role_id=callback_data.role_id,
            owner_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.custom_role_detail(role),
        reply_markup=build_custom_role_detail_keyboard(role_id=role.id),
    )
    await callback.answer()


@router.callback_query(CustomRoleCB.filter(F.action == "home"))
async def on_custom_role_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Dismiss the card and return to the main menu prompt."""
    await state.clear()
    await callback.message.edit_text(texts.START)  # type: ignore[union-attr]
    await callback.answer()


# --- Deletion ----------------------------------------------------------------


@router.callback_query(CustomRoleCB.filter(F.action == "delete_prompt"))
async def on_custom_role_delete_prompt(
    callback: CallbackQuery,
    callback_data: CustomRoleCB,
    services: ServiceProvider,
) -> None:
    """Ask for confirmation before deleting a custom role."""
    try:
        role = await services.custom_roles.get_for_owner(
            custom_role_id=callback_data.role_id,
            owner_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.confirm_delete_custom_role(role),
        reply_markup=build_custom_role_delete_confirm_keyboard(role_id=role.id),
    )
    await callback.answer()


@router.callback_query(CustomRoleCB.filter(F.action == "delete_confirm"))
async def on_custom_role_delete_confirm(
    callback: CallbackQuery,
    callback_data: CustomRoleCB,
    services: ServiceProvider,
) -> None:
    """Soft-delete the custom role, then return to the refreshed list."""
    try:
        role = await services.custom_roles.get_for_owner(
            custom_role_id=callback_data.role_id,
            owner_id=callback.from_user.id,
        )
        await services.custom_roles.delete(
            custom_role_id=callback_data.role_id,
            owner_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.custom_role_deleted(role.name_fa)
    )
    await callback.answer("نقش حذف شد 🗑")


# --- Creation wizard ---------------------------------------------------------


@router.callback_query(CustomRoleCB.filter(F.action == "new"))
async def on_custom_role_new(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Start the create-custom-role wizard by asking for the name."""
    await state.set_state(CustomRoleStates.enter_name)
    await callback.message.answer(  # type: ignore[union-attr]
        texts.CUSTOM_ROLE_ASK_NAME,
        reply_markup=build_main_menu_keyboard(),
    )
    await callback.answer()


@router.message(CustomRoleStates.enter_name, F.text)
async def on_custom_role_name(message: Message, state: FSMContext) -> None:
    """Capture the role name and move on to the team picker."""
    name = (message.text or "").strip()
    if not name:
        await message.answer("نام نقش نمی‌تواند خالی باشد. دوباره وارد کنید:")
        return
    if len(name) > 64:
        await message.answer("نام نقش نباید بیش از ۶۴ کاراکتر باشد. دوباره وارد کنید:")
        return
    await state.update_data(name_fa=name)
    await state.set_state(CustomRoleStates.choose_team)
    await message.answer(
        texts.CUSTOM_ROLE_ASK_TEAM,
        reply_markup=build_team_picker_keyboard(),
    )


@router.callback_query(
    CustomRoleStates.choose_team, CustomRoleTeamCB.filter()
)
async def on_custom_role_team(
    callback: CallbackQuery,
    callback_data: CustomRoleTeamCB,
    state: FSMContext,
) -> None:
    """Capture the chosen team and ask for an optional description."""
    try:
        team = RoleTeam(callback_data.team)
    except ValueError:
        await callback.answer("تیم نامعتبر است.", show_alert=True)
        return
    await state.update_data(team=team.value)
    await state.set_state(CustomRoleStates.enter_description)
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.CUSTOM_ROLE_ASK_DESCRIPTION
    )
    await callback.answer()


@router.message(CustomRoleStates.enter_description, F.text)
async def on_custom_role_description(
    message: Message,
    state: FSMContext,
    services: ServiceProvider,
) -> None:
    """Capture the (optional) description, persist the role, and finish."""
    raw = (message.text or "").strip()
    description = None if raw == texts.CUSTOM_ROLE_SKIP_DESCRIPTION else raw

    data = await state.get_data()
    name_fa = data.get("name_fa", "")
    team_value = data.get("team", RoleTeam.CITIZEN.value)
    try:
        team = RoleTeam(team_value)
    except ValueError:
        team = RoleTeam.CITIZEN

    try:
        role = await services.custom_roles.create(
            owner_id=message.from_user.id,
            name_fa=name_fa,
            team=team,
            description=description,
        )
    except DomainError as exc:
        await message.answer(exc.message_fa)
        return

    await state.clear()
    await message.answer(
        texts.custom_role_created(role),
        reply_markup=build_main_menu_keyboard(),
    )
    # Follow up with the refreshed list so the new role is immediately usable.
    await _show_list(message, services, message.from_user.id)
