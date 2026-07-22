"""Persistent reply-keyboard builders.

Unlike inline keyboards (attached to a single message), a reply keyboard stays
docked at the bottom of the chat until explicitly replaced/removed. We use it for
the always-available main menu so users never have to type commands.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Button captions. Centralised here so the handlers that match them (in
# ``handlers/common.py``) and the keyboard builder never drift apart.
BTN_CREATE_GAME = "🎲 ساخت بازی"
BTN_JOIN_GAME = "🎮 ورود به بازی"
BTN_ROLE_INFO = "📖 توضیح نقش‌ها"
BTN_MY_GAMES = "📂 بازی‌های من"
BTN_CUSTOM_ROLES = "🛠 نقش‌های من"
BTN_CANCEL = "❌ لغو عملیات"

#: All main-menu captions, for quick membership checks in handlers.
MAIN_MENU_BUTTONS: frozenset[str] = frozenset(
    {
        BTN_CREATE_GAME,
        BTN_JOIN_GAME,
        BTN_ROLE_INFO,
        BTN_MY_GAMES,
        BTN_CUSTOM_ROLES,
        BTN_CANCEL,
    }
)



def build_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Return the always-visible main-menu reply keyboard.

    ``resize_keyboard`` makes it compact and ``is_persistent`` keeps it docked
    for the user instead of collapsing after a single use.
    """
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=BTN_CREATE_GAME))
    builder.add(KeyboardButton(text=BTN_JOIN_GAME))
    builder.add(KeyboardButton(text=BTN_ROLE_INFO))
    builder.add(KeyboardButton(text=BTN_MY_GAMES))
    builder.add(KeyboardButton(text=BTN_CUSTOM_ROLES))
    builder.add(KeyboardButton(text=BTN_CANCEL))
    # [create | join] then [roles | my games] then [custom roles | cancel]
    builder.adjust(2, 2, 2)


    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یک گزینه را انتخاب کنید…",
    )
