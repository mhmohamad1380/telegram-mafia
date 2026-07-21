"""Authentication middleware.

Upserts the Telegram user for every incoming message/callback so downstream
handlers and services can rely on the user existing. The resolved user id is
injected as ``user_id`` in the handler data.

Must run *after* :class:`DatabaseMiddleware` so a session/services are available.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app.services import ServiceProvider


class AuthMiddleware(BaseMiddleware):
    """Ensures the sending Telegram user exists in the database."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: User | None = self._extract_user(event)
        if tg_user is not None and not tg_user.is_bot:
            services: ServiceProvider = data["services"]
            await services.repos.users.upsert_from_telegram(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            # Flush so the user row is visible to subsequent queries in this txn.
            await services.repos.session.flush()
            data["user_id"] = tg_user.id
        return await handler(event, data)

    @staticmethod
    def _extract_user(event: TelegramObject) -> User | None:
        if isinstance(event, Message):
            return event.from_user
        if isinstance(event, CallbackQuery):
            return event.from_user
        return None
