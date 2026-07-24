"""Persistent reply-keyboard builders.

Unlike inline keyboards (attached to a single message), a reply keyboard stays
docked at the bottom of the chat until explicitly replaced/removed. We use it for
the always-available main menu so users never have to type commands.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.miniapp.config import get_miniapp_config

# Button captions. Centralised here so the handlers that match them (in
# ``handlers/common.py``) and the keyboard builder never drift apart.
BTN_CREATE_GAME = "🎲 ساخت بازی"
BTN_JOIN_GAME = "🎮 ورود به بازی"
BTN_ROLE_INFO = "📖 توضیح نقش‌ها"
BTN_SCENARIOS = "📚 سناریوها"
BTN_MY_GAMES = "📂 بازی‌های من"
BTN_GAME_HISTORY = "📜 تاریخچه بازی‌ها"
BTN_CUSTOM_ROLES = "🛠 نقش‌های من"
BTN_LIVE_TABLE = "📱 میز آنلاین"

BTN_OWNER_TEST = "🧪 تست کامل بازی"
BTN_CANCEL = "❌ لغو عملیات"

#: All main-menu captions, for quick membership checks in handlers.
MAIN_MENU_BUTTONS: frozenset[str] = frozenset(
    {
        BTN_CREATE_GAME,
        BTN_JOIN_GAME,
        BTN_ROLE_INFO,
        BTN_SCENARIOS,
        BTN_MY_GAMES,
        BTN_GAME_HISTORY,
        BTN_CUSTOM_ROLES,
        BTN_LIVE_TABLE,
        BTN_OWNER_TEST,
        BTN_CANCEL,
    }
)


def build_main_menu_keyboard(*, is_owner: bool = False) -> ReplyKeyboardMarkup:
    """Return the always-visible main-menu reply keyboard.

    ``resize_keyboard`` makes it compact and ``is_persistent`` keeps it docked
    for the user instead of collapsing after a single use. When ``is_owner`` is
    true, an extra owner-only «🧪 تست کامل بازی» button is appended so the bot
    owner can run the end-to-end self-test straight from the menu; regular users
    never see it.

    When ``MINIAPP_URL`` is configured, a «📱 میز آنلاین» button is added that
    launches the Telegram Mini App (the online voice-table client) directly
    inside Telegram via a :class:`WebAppInfo` button.
    """
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text=BTN_CREATE_GAME))
    builder.add(KeyboardButton(text=BTN_JOIN_GAME))
    builder.add(KeyboardButton(text=BTN_ROLE_INFO))
    builder.add(KeyboardButton(text=BTN_SCENARIOS))
    builder.add(KeyboardButton(text=BTN_MY_GAMES))
    builder.add(KeyboardButton(text=BTN_GAME_HISTORY))
    builder.add(KeyboardButton(text=BTN_CUSTOM_ROLES))
    # [create | join] [roles | scenarios] [my games | history] [custom roles] ...
    layout = [2, 2, 2, 1]

    # The Mini App button only works over HTTPS; only surface it when a public
    # URL has been configured (otherwise Telegram rejects the button).
    miniapp_url = get_miniapp_config().miniapp_url
    if miniapp_url:
        builder.add(
            KeyboardButton(
                text=BTN_LIVE_TABLE,
                web_app=WebAppInfo(url=miniapp_url),
            )
        )
        layout.append(1)  # [live table]

    if is_owner:
        builder.add(KeyboardButton(text=BTN_OWNER_TEST))
        layout.append(1)  # [owner test]
    builder.add(KeyboardButton(text=BTN_CANCEL))
    layout.append(1)  # [cancel]
    builder.adjust(*layout)

    return builder.as_markup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یک گزینه را انتخاب کنید…",
    )
