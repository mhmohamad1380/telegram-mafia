"""Database/DI middleware.

Opens one :class:`AsyncSession` per update, wraps the handler in a transaction,
and injects a fully-wired :class:`ServiceProvider` into the handler data. On
success the transaction commits; on any exception it rolls back and re-raises.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config.logging import get_logger
from app.services import ServiceProvider

logger = get_logger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Provides a per-update session + service provider with transaction scope."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._session_factory() as session:
            services = ServiceProvider(session)
            data["session"] = session
            data["services"] = services
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
