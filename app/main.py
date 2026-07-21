"""Application entry point.

Wires configuration, logging, database, Redis-backed FSM storage, middlewares,
and handlers, then starts long-polling. Run with ``python -m app.main``.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis


from app.bot.handlers import get_main_router
from app.bot.middlewares import AuthMiddleware, DatabaseMiddleware
from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.database.seed import seed_roles
from app.database.session import init_database

logger = get_logger(__name__)


async def _seed(session_factory) -> None:
    """Seed the role catalog on startup (idempotent)."""
    async with session_factory() as session:
        await seed_roles(session)
        await session.commit()


async def main() -> None:
    """Compose and run the bot."""
    settings = get_settings()
    configure_logging(level=settings.log_level, console=settings.log_console)
    logger.info("starting_bot", environment=settings.environment)

    # --- Database ---
    database = init_database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    await _seed(database.session_factory)

    # --- Redis FSM storage ---
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    # --- Bot & Dispatcher ---
    # Route Telegram traffic through a proxy when configured (e.g. where
    # Telegram is blocked). SOCKS schemes require the 'aiohttp-socks' package.
    session = AiohttpSession(proxy=settings.bot_proxy) if settings.bot_proxy else None
    if settings.bot_proxy:
        logger.info("using_proxy", proxy=settings.bot_proxy)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)


    # Middlewares: DB/session+DI first, then auth (which needs services).
    db_mw = DatabaseMiddleware(database.session_factory)
    auth_mw = AuthMiddleware()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(db_mw)
        observer.middleware(auth_mw)

    # Handlers
    dp.include_router(get_main_router())

    # --- Run ---
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("polling_started")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()
        await database.dispose()
        logger.info("bot_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("interrupted")
