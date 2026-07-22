"""Common handlers: /start, /help, /roles, /cancel, and the main-menu buttons."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot import texts
from app.bot.handlers.create_game import start_create_game
from app.bot.handlers.join_game import start_join_game
from app.bot.keyboards import (
    BTN_CANCEL,
    BTN_CREATE_GAME,
    BTN_JOIN_GAME,
    build_main_menu_keyboard,
)
from app.services import ServiceProvider
from app.utils.role_catalog import (
    ROLE_BY_CODE,
    TEAM_LABELS_FA,
    format_role_details,
)

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Greet the user, clear any stale flow, and dock the persistent menu."""
    await state.clear()
    await message.answer(texts.START, reply_markup=build_main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show usage help."""
    await message.answer(texts.HELP, reply_markup=build_main_menu_keyboard())


async def _cancel(message: Message, state: FSMContext) -> None:
    """Clear any in-progress FSM flow and return to the main menu."""
    current = await state.get_state()
    await state.clear()
    text = texts.CANCELLED if current is not None else texts.NOTHING_TO_CANCEL
    await message.answer(text, reply_markup=build_main_menu_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """``/cancel`` command handler."""
    await _cancel(message, state)


# --- Persistent main-menu buttons -------------------------------------------
#
# These match the reply-keyboard captions verbatim. Registering them on the
# ``common`` router (included first) means they always take precedence over
# state-scoped text handlers, so the menu works from any point in a flow.


@router.message(F.text == BTN_CANCEL)
async def on_menu_cancel(message: Message, state: FSMContext) -> None:
    """Main-menu «لغو عملیات» button — cancel the current flow."""
    await _cancel(message, state)


@router.message(F.text == BTN_CREATE_GAME)
async def on_menu_create(
    message: Message, state: FSMContext, services: ServiceProvider
) -> None:
    """Main-menu «ساخت بازی» button — start the create-game wizard."""
    await start_create_game(message, state, services)



@router.message(F.text == BTN_JOIN_GAME)
async def on_menu_join(message: Message, state: FSMContext) -> None:
    """Main-menu «ورود به بازی» button — start the join-game flow."""
    await start_join_game(message, state)


@router.message(Command("roles"))
async def cmd_roles(message: Message, services: ServiceProvider) -> None:
    """List every role in the catalog, grouped by team, with a short summary.

    A full, beginner-friendly breakdown (objective, ability, timing,
    limitations, interactions, and strategy) is sent as follow-up messages —
    one per team — so newcomers can learn each role without leaving Telegram.
    """
    catalog = await services.roles.list_catalog()
    if not catalog:
        await message.answer("لیست نقش‌ها هنوز مقداردهی نشده است.")
        return

    # 1) Compact grouped overview.
    lines = ["🎭 <b>لیست نقش‌ها</b>"]
    for team, label in TEAM_LABELS_FA.items():
        team_roles = [r for r in catalog if r.team == team]
        if not team_roles:
            continue
        lines.append(f"\n<b>— {label} —</b>")
        for role in team_roles:
            desc = f" — {role.description}" if role.description else ""
            lines.append(f"• {role.name_fa}{desc}")
    lines.append("\nℹ️ در ادامه توضیح کامل هر نقش ارسال می‌شود.")
    await message.answer("\n".join(lines))

    # 2) Detailed per-team breakdown (one message per team to respect limits).
    for team, label in TEAM_LABELS_FA.items():
        team_roles = [r for r in catalog if r.team == team]
        if not team_roles:
            continue
        blocks: list[str] = [f"📚 <b>راهنمای کامل نقش‌های {label}</b>"]
        for role in team_roles:
            defn = ROLE_BY_CODE.get(role.code)
            if defn is not None:
                blocks.append(format_role_details(defn))
        await message.answer("\n\n".join(blocks))
