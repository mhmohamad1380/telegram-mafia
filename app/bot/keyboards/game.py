"""Inline keyboard builders.

Each function returns an :class:`InlineKeyboardMarkup` ready to attach to a
message. Callback payloads use the typed factories in :mod:`app.bot.callbacks`.
Persian digits are used for all user-visible numbers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import (
    GameControlCB,
    LobbyActionCB,
    NumberPickCB,
    PlayerCountCB,
    RoleSetupActionCB,
    RoleToggleCB,
)
from app.schemas.game import CustomRoleDTO, RoleCatalogItemDTO
from app.utils.role_catalog import TEAM_LABELS_FA
from app.utils.codes import to_persian_digits


# Suggested quick-pick player counts shown as buttons.
SUGGESTED_PLAYER_COUNTS: tuple[int, ...] = (8, 10, 12, 15, 18)


def build_player_count_keyboard() -> InlineKeyboardMarkup:
    """Quick-pick buttons for common player counts (plus custom hint via text)."""
    builder = InlineKeyboardBuilder()
    for count in SUGGESTED_PLAYER_COUNTS:
        builder.button(
            text=to_persian_digits(count),
            callback_data=PlayerCountCB(count=count),
        )
    builder.adjust(len(SUGGESTED_PLAYER_COUNTS))
    return builder.as_markup()


def build_role_selection_keyboard(
    *,
    game_id: int,
    roles: Sequence[RoleCatalogItemDTO],
    selected_ids: Iterable[int],
    selected_total: int,
    target_count: int,
    custom_roles: Sequence[CustomRoleDTO] = (),
    selected_custom_ids: Iterable[int] = (),
) -> InlineKeyboardMarkup:
    """Build the role selection grid grouped by team.

    Selected roles are prefixed with ✅, unselected with ❌. A footer shows the
    running total and a confirm/cancel row.

    The creator's own custom roles ("نقش‌های من") are appended as an extra,
    always-selectable section so they can be mixed into any flexible scenario.
    Their callbacks carry ``is_custom=True`` because catalog and custom roles use
    independent id spaces.
    """
    selected = set(selected_ids)
    selected_custom = set(selected_custom_ids)
    builder = InlineKeyboardBuilder()


    # Group roles by team for readability, preserving catalog order.
    for team, label in TEAM_LABELS_FA.items():
        team_roles = [r for r in roles if r.team == team]
        if not team_roles:
            continue
        # Section header (non-interactive; encoded as a no-op refresh button).
        builder.row(
            InlineKeyboardButton(
                text=f"— {label} —",
                callback_data=RoleSetupActionCB(game_id=game_id, action="noop").pack(),
            )
        )
        row_buttons: list[InlineKeyboardButton] = []
        for role in team_roles:
            # Data-driven gating: a role whose ``min_players`` exceeds the
            # current player count is locked. Tapping it triggers a "locked"
            # callback that explains the requirement instead of toggling it.
            locked = (
                role.min_players is not None and target_count < role.min_players
            )
            if locked:
                text = f"🔒 {role.name_fa}"
                callback = RoleSetupActionCB(
                    game_id=game_id, action="locked"
                ).pack()
            else:
                mark = "✅" if role.role_id in selected else "❌"
                text = f"{mark} {role.name_fa}"
                callback = RoleToggleCB(
                    game_id=game_id, role_id=role.role_id
                ).pack()
            row_buttons.append(
                InlineKeyboardButton(text=text, callback_data=callback)
            )
        # Two roles per row.
        for i in range(0, len(row_buttons), 2):
            builder.row(*row_buttons[i : i + 2])

    # Creator's own custom roles — always selectable regardless of scenario.
    if custom_roles:
        builder.row(
            InlineKeyboardButton(
                text="— 🛠 نقش‌های من —",
                callback_data=RoleSetupActionCB(
                    game_id=game_id, action="noop"
                ).pack(),
            )
        )
        custom_buttons: list[InlineKeyboardButton] = []
        for crole in custom_roles:
            mark = "✅" if crole.id in selected_custom else "❌"
            custom_buttons.append(
                InlineKeyboardButton(
                    text=f"{mark} {crole.name_fa}",
                    callback_data=RoleToggleCB(
                        game_id=game_id, role_id=crole.id, is_custom=True
                    ).pack(),
                )
            )
        for i in range(0, len(custom_buttons), 2):
            builder.row(*custom_buttons[i : i + 2])

    # Footer: running counter.

    counter_text = (
        f"انتخاب‌شده: {to_persian_digits(selected_total)} از "
        f"{to_persian_digits(target_count)}"
    )
    builder.row(
        InlineKeyboardButton(
            text=counter_text,
            callback_data=RoleSetupActionCB(game_id=game_id, action="noop").pack(),
        )
    )
    # Confirm / cancel.
    builder.row(
        InlineKeyboardButton(
            text="✅ تایید و ساخت بازی",
            callback_data=RoleSetupActionCB(
                game_id=game_id, action="confirm"
            ).pack(),
        ),
        InlineKeyboardButton(
            text="❌ لغو",
            callback_data=RoleSetupActionCB(game_id=game_id, action="cancel").pack(),
        ),
    )
    return builder.as_markup()


def build_composition_summary_keyboard(*, game_id: int) -> InlineKeyboardMarkup:
    """Confirm/back buttons on the composition summary screen."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ تایید و ساخت بازی",
        callback_data=RoleSetupActionCB(game_id=game_id, action="finalize"),
    )
    builder.button(
        text="↩️ بازگشت و ویرایش",
        callback_data=RoleSetupActionCB(game_id=game_id, action="back"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_number_keyboard(
    *, game_id: int, available_numbers: Sequence[int]
) -> InlineKeyboardMarkup:

    """Grid of available seat numbers (taken numbers are omitted)."""
    builder = InlineKeyboardBuilder()
    for number in available_numbers:
        builder.button(
            text=to_persian_digits(number),
            callback_data=NumberPickCB(game_id=game_id, number=number),
        )
    # Five numbers per row.
    builder.adjust(5)
    return builder.as_markup()


def build_waiting_keyboard(*, game_id: int) -> InlineKeyboardMarkup:
    """Player-side controls while waiting for the lobby to fill / their turn.

    A single refresh button lets the player re-check whether it's their turn to
    pick a number, plus a leave button.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔄 بررسی نوبت / انتخاب شماره",
        callback_data=LobbyActionCB(game_id=game_id, action="checkturn"),
    )
    builder.button(
        text="🚪 خروج از بازی",
        callback_data=LobbyActionCB(game_id=game_id, action="leave"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_player_lobby_keyboard(
    *, game_id: int, has_number: bool, has_role: bool
) -> InlineKeyboardMarkup:

    """Player-side lobby controls that adapt to the player's progress."""
    builder = InlineKeyboardBuilder()
    if has_role:
        builder.button(
            text="👁 مشاهده نقش من",
            callback_data=LobbyActionCB(game_id=game_id, action="myrole"),
        )
    elif has_number:
        builder.button(
            text="🎲 دریافت نقش",
            callback_data=LobbyActionCB(game_id=game_id, action="assign"),
        )
    builder.button(
        text="🚪 خروج از بازی",
        callback_data=LobbyActionCB(game_id=game_id, action="leave"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_creator_lobby_keyboard(
    *, game_id: int, can_start: bool
) -> InlineKeyboardMarkup:
    """Creator controls while the lobby is filling up."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔄 وضعیت بازی",
        callback_data=GameControlCB(game_id=game_id, action="status"),
    )
    if can_start:
        builder.button(
            text="▶️ شروع بازی",
            callback_data=GameControlCB(game_id=game_id, action="start"),
        )
    builder.adjust(1)
    return builder.as_markup()


def build_in_game_keyboard(*, game_id: int) -> InlineKeyboardMarkup:
    """Creator controls once the game is in progress."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📋 لیست بازیکنان",
        callback_data=GameControlCB(game_id=game_id, action="roster"),
    )
    builder.button(
        text="🏁 پایان بازی",
        callback_data=GameControlCB(game_id=game_id, action="finish"),
    )
    builder.adjust(1)
    return builder.as_markup()
