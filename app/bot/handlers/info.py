"""Handlers for the informational / management menu surfaces.

Covers two self-contained, read-mostly features reachable from the persistent
main menu:

* "📖 توضیح نقش‌ها" — a paginated role encyclopaedia (no DB access; served from
  the static catalog via :class:`RoleInfoService`).
* "📂 بازی‌های من" — the user's games list, per-game detail, and creator-only
  deletion (via :class:`UserGamesService` / :class:`GameManagementService`).

All navigation uses inline keyboards and edits the current message in place, so
each feature occupies a single, tidy chat card.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.callbacks import MyGamesCB, RoleInfoCB
from app.bot.keyboards import (
    BTN_MY_GAMES,
    BTN_ROLE_INFO,
    build_delete_confirm_keyboard,
    build_game_detail_keyboard,
    build_my_games_keyboard,
    build_role_index_keyboard,
    build_role_page_keyboard,
)
from app.config.logging import get_logger
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)
router = Router(name="info")


# --- Role encyclopaedia ("📖 توضیح نقش‌ها") ----------------------------------


@router.message(F.text == BTN_ROLE_INFO)
async def on_menu_role_info(message: Message, services: ServiceProvider) -> None:
    """Open the role encyclopaedia at its index (grid of all roles)."""
    items = services.role_info.list_index()
    await message.answer(
        texts.ROLE_INFO_INTRO,
        reply_markup=build_role_index_keyboard(items),
    )


@router.callback_query(RoleInfoCB.filter(F.action == "list"))
async def on_role_list(
    callback: CallbackQuery,
    services: ServiceProvider,
) -> None:
    """Show the full role index (from a role detail page)."""
    items = services.role_info.list_index()
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.ROLE_INFO_INTRO,
        reply_markup=build_role_index_keyboard(items),
    )
    await callback.answer()


@router.callback_query(RoleInfoCB.filter(F.action == "show"))
async def on_role_show(
    callback: CallbackQuery,
    callback_data: RoleInfoCB,
    services: ServiceProvider,
) -> None:
    """Show a single role's full description with prev/next navigation."""
    page = services.role_info.get_page(callback_data.index)
    text = texts.role_info_page(
        index=page.index, total=page.total, details=page.details
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=build_role_page_keyboard(
            prev_index=page.prev_index, next_index=page.next_index
        ),
    )
    await callback.answer()


@router.callback_query(RoleInfoCB.filter(F.action == "home"))
async def on_role_home(callback: CallbackQuery) -> None:
    """Dismiss the encyclopaedia card and return to the main menu prompt."""
    await callback.message.edit_text(texts.START)  # type: ignore[union-attr]
    await callback.answer()


# --- "📂 بازی‌های من" ---------------------------------------------------------


@router.message(F.text == BTN_MY_GAMES)
async def on_menu_my_games(message: Message, services: ServiceProvider) -> None:
    """List every game the user creates or plays in."""
    games = await services.user_games.list_user_games(user_id=message.from_user.id)
    if not games:
        await message.answer(texts.MY_GAMES_EMPTY)
        return
    await message.answer(
        texts.MY_GAMES_INTRO,
        reply_markup=build_my_games_keyboard(games),
    )


@router.callback_query(MyGamesCB.filter(F.action == "list"))
async def on_my_games_list(
    callback: CallbackQuery,
    services: ServiceProvider,
) -> None:
    """Return to the games list from a detail screen."""
    games = await services.user_games.list_user_games(
        user_id=callback.from_user.id
    )
    if not games:
        await callback.message.edit_text(texts.MY_GAMES_EMPTY)  # type: ignore[union-attr]
        await callback.answer()
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.MY_GAMES_INTRO,
        reply_markup=build_my_games_keyboard(games),
    )
    await callback.answer()


@router.callback_query(MyGamesCB.filter(F.action == "open"))
async def on_my_game_open(
    callback: CallbackQuery,
    callback_data: MyGamesCB,
    services: ServiceProvider,
) -> None:
    """Open the detail screen for one of the user's games."""
    try:
        detail = await services.user_games.get_game_detail(
            game_id=callback_data.game_id,
            user_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.my_game_detail(detail),
        reply_markup=build_game_detail_keyboard(
            game_id=detail.game_id,
            is_creator=detail.is_creator,
            can_delete=detail.can_delete,
        ),
    )
    await callback.answer()


@router.callback_query(MyGamesCB.filter(F.action == "delete_prompt"))
async def on_my_game_delete_prompt(
    callback: CallbackQuery,
    callback_data: MyGamesCB,
    services: ServiceProvider,
) -> None:
    """Ask the creator to confirm an irreversible game deletion."""
    try:
        detail = await services.user_games.get_game_detail(
            game_id=callback_data.game_id,
            user_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    if not detail.is_creator:
        await callback.answer(
            "فقط سازنده بازی می‌تواند آن را حذف کند.", show_alert=True
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        texts.confirm_delete_game(detail),
        reply_markup=build_delete_confirm_keyboard(game_id=detail.game_id),
    )
    await callback.answer()


@router.callback_query(MyGamesCB.filter(F.action == "delete_confirm"))
async def on_my_game_delete_confirm(
    callback: CallbackQuery,
    callback_data: MyGamesCB,
    services: ServiceProvider,
) -> None:
    """Perform the deletion (creator only) and confirm to the user."""
    try:
        code = await services.game_management.delete_game(
            game_id=callback_data.game_id,
            requester_id=callback.from_user.id,
        )
    except DomainError as exc:
        await callback.answer(exc.message_fa, show_alert=True)
        return

    await callback.message.edit_text(texts.game_deleted(code))  # type: ignore[union-attr]
    await callback.answer("بازی حذف شد 🗑")
