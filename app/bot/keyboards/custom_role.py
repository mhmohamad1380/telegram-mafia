"""Inline keyboard builders for the "🛠 نقش‌های من" custom-role screens.

Kept separate from the game and info keyboards so the custom-role management
surface evolves independently. Team labels reuse the shared catalog mapping so
wording stays consistent with the rest of the bot.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import CustomRoleCB, CustomRoleTeamCB
from app.models.enums import RoleTeam
from app.schemas.game import CustomRoleDTO

#: Teams a user may assign to a custom role, with their Persian labels and the
#: emoji used across the bot. Order defines the button order in the picker.
CUSTOM_ROLE_TEAMS: tuple[tuple[RoleTeam, str], ...] = (
    (RoleTeam.CITIZEN, "🟩 شهروند"),
    (RoleTeam.MAFIA, "🟥 مافیا"),
    (RoleTeam.INDEPENDENT, "🟪 مستقل"),
)

#: Short Persian label per team, for detail/list rendering.
TEAM_LABEL_FA: dict[RoleTeam, str] = {
    RoleTeam.CITIZEN: "شهروند",
    RoleTeam.MAFIA: "مافیا",
    RoleTeam.INDEPENDENT: "مستقل",
    RoleTeam.MASON: "فراماسون",
}


def build_custom_roles_keyboard(
    roles: Sequence[CustomRoleDTO],
) -> InlineKeyboardMarkup:
    """List the user's custom roles plus a "create new" action.

    Each role opens its detail screen; a footer button starts the wizard.
    """
    builder = InlineKeyboardBuilder()
    for role in roles:
        label = TEAM_LABEL_FA.get(role.team, role.team.value)
        builder.button(
            text=f"{role.name_fa} — {label}",
            callback_data=CustomRoleCB(action="open", role_id=role.id),
        )
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="➕ ساخت نقش جدید",
            callback_data=CustomRoleCB(action="new").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 منوی اصلی",
            callback_data=CustomRoleCB(action="home").pack(),
        )
    )
    return builder.as_markup()


def build_empty_custom_roles_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown when the user has no custom roles yet."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ ساخت نقش جدید",
            callback_data=CustomRoleCB(action="new").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 منوی اصلی",
            callback_data=CustomRoleCB(action="home").pack(),
        )
    )
    return builder.as_markup()


def build_custom_role_detail_keyboard(*, role_id: int) -> InlineKeyboardMarkup:
    """Detail-screen controls: delete + back to the list."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🗑 حذف نقش",
        callback_data=CustomRoleCB(action="delete_prompt", role_id=role_id),
    )
    builder.button(
        text="↩️ بازگشت به لیست",
        callback_data=CustomRoleCB(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_custom_role_delete_confirm_keyboard(
    *, role_id: int
) -> InlineKeyboardMarkup:
    """Confirm/cancel keyboard for deleting a custom role."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ بله، حذف شود",
        callback_data=CustomRoleCB(action="delete_confirm", role_id=role_id),
    )
    builder.button(
        text="❌ انصراف",
        callback_data=CustomRoleCB(action="open", role_id=role_id),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_team_picker_keyboard() -> InlineKeyboardMarkup:
    """Team (alignment) picker shown during the create-custom-role wizard."""
    builder = InlineKeyboardBuilder()
    for team, label in CUSTOM_ROLE_TEAMS:
        builder.button(
            text=label,
            callback_data=CustomRoleTeamCB(team=team.value),
        )
    builder.adjust(1)
    return builder.as_markup()
