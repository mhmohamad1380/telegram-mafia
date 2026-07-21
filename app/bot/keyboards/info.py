"""Inline keyboard builders for the role encyclopaedia and "my games" screens.

Kept separate from :mod:`app.bot.keyboards.game` (the in-flow game keyboards) so
the informational / management surfaces evolve independently. All user-visible
numbers use Persian digits, consistent with the rest of the bot.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import MyGamesCB, RoleInfoCB
from app.models.enums import GameStatus
from app.schemas.game import UserGameSummaryDTO
from app.services.role_info_service import RoleIndexItem

# --- Role encyclopaedia ("📖 توضیح نقش‌ها") ----------------------------------


#: Roles per row in the "all roles" index grid.
_ROLE_INDEX_COLUMNS = 2


def build_role_index_keyboard(items: Sequence[RoleIndexItem]) -> InlineKeyboardMarkup:
    """Grid of every role; tapping one opens its detail page.

    Also used as the "📋 لیست نقش‌ها" destination from a detail page.
    """
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=item.name_fa,
            callback_data=RoleInfoCB(action="show", index=item.index),
        )
    builder.adjust(_ROLE_INDEX_COLUMNS)
    # Footer: back to the main menu.
    builder.row(
        InlineKeyboardButton(
            text="🏠 منوی اصلی",
            callback_data=RoleInfoCB(action="home").pack(),
        )
    )
    return builder.as_markup()


def build_role_page_keyboard(
    *, prev_index: int, next_index: int
) -> InlineKeyboardMarkup:
    """Navigation footer for a single role page.

    Layout::

        [⬅ نقش قبلی] [➡ نقش بعدی]
        [📋 لیست نقش‌ها]
        [🏠 منوی اصلی]
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅ نقش قبلی",
            callback_data=RoleInfoCB(action="show", index=prev_index).pack(),
        ),
        InlineKeyboardButton(
            text="➡ نقش بعدی",
            callback_data=RoleInfoCB(action="show", index=next_index).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 لیست نقش‌ها",
            callback_data=RoleInfoCB(action="list").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏠 منوی اصلی",
            callback_data=RoleInfoCB(action="home").pack(),
        )
    )
    return builder.as_markup()


# --- "📂 بازی‌های من" ---------------------------------------------------------

#: Persian labels for each game status, shown in the list/detail screens.
GAME_STATUS_LABELS_FA: dict[GameStatus, str] = {
    GameStatus.CREATING: "در حال ساخت",
    GameStatus.WAITING_PLAYERS: "در انتظار بازیکنان",
    GameStatus.READY: "آماده شروع",
    GameStatus.IN_PROGRESS: "در حال اجرا",
    GameStatus.FINISHED: "پایان‌یافته",
    GameStatus.CANCELLED: "لغوشده",
}


def build_my_games_keyboard(
    games: Sequence[UserGameSummaryDTO],
) -> InlineKeyboardMarkup:
    """One button per game (code + status), each opening its detail screen."""
    builder = InlineKeyboardBuilder()
    for g in games:
        role_marker = "👑 " if g.is_creator else ""
        status = GAME_STATUS_LABELS_FA.get(g.status, g.status.value)
        builder.button(
            text=f"{role_marker}{g.code} — {status}",
            callback_data=MyGamesCB(action="open", game_id=g.game_id),
        )
    builder.adjust(1)
    return builder.as_markup()


def build_game_detail_keyboard(
    *, game_id: int, is_creator: bool, can_delete: bool
) -> InlineKeyboardMarkup:
    """Detail-screen controls: delete (creator, when allowed) + back to list."""
    builder = InlineKeyboardBuilder()
    if is_creator and can_delete:
        builder.button(
            text="🗑 حذف بازی",
            callback_data=MyGamesCB(action="delete_prompt", game_id=game_id),
        )
    builder.button(
        text="↩️ بازگشت به لیست",
        callback_data=MyGamesCB(action="list"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_delete_confirm_keyboard(*, game_id: int) -> InlineKeyboardMarkup:
    """Confirm/cancel keyboard for the irreversible game deletion."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ بله، حذف شود",
        callback_data=MyGamesCB(action="delete_confirm", game_id=game_id),
    )
    builder.button(
        text="❌ انصراف",
        callback_data=MyGamesCB(action="open", game_id=game_id),
    )
    builder.adjust(1)
    return builder.as_markup()
