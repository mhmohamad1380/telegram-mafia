"""FastAPI application factory (composition root) for the Mini App.

Wires the shared async database, a Redis client (reused for both live-state
storage and pub/sub fan-out), the :class:`RealtimeHub`, and a background
one-second timer loop that ticks every active table's speaking clock. The same
settings/logging/DB stack as the bot is reused verbatim — this is a second
*transport* over the existing core, not a second application.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.requests import Request

from app.config.logging import configure_logging, get_logger
from app.config.settings import get_settings
from app.database.session import init_database
from app.miniapp.config import get_miniapp_config
from app.miniapp.live_state import LiveStateStore
from app.miniapp.realtime import RealtimeHub
from app.miniapp.routes import router
from app.miniapp.service import MiniAppService
from app.services import ServiceProvider
from app.utils.exceptions import DomainError

logger = get_logger(__name__)


async def _timer_loop(app: FastAPI) -> None:
    """Tick every table's speaking clock once per second.

    The set of "hot" game ids (those with a running timer) lives on the hub, so
    that request handlers can flag a table active through the dependency they
    already hold. On each tick we advance them; when one expires we publish an
    ``invalidate`` so clients refetch and the manager can start the next turn.
    This loop is best-effort and stateless across restarts — the authoritative
    countdown lives in Redis via :class:`LiveStateStore`.
    """
    hub: RealtimeHub = app.state.hub
    store: LiveStateStore = app.state.live_store
    session_factory = app.state.session_factory
    hot = hub.hot_games
    while True:
        await asyncio.sleep(1.0)
        for game_id in list(hot):
            try:
                async with session_factory() as session:
                    service = MiniAppService(ServiceProvider(session), store)
                    live, expired = await service.tick(game_id=game_id)
                    if live.timer_running or expired:
                        await store.save(game_id, live)
                    if not live.timer_running:
                        hot.discard(game_id)
                    if expired:
                        await hub.publish(
                            game_id, {"type": "invalidate", "game_id": game_id}
                        )
            except Exception:  # pragma: no cover - never let the loop die
                logger.exception("timer_tick_failed", game_id=game_id)
                hot.discard(game_id)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, console=settings.log_console)
    logger.info("miniapp_starting", environment=settings.environment)

    database = init_database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
    redis = Redis.from_url(settings.redis_url)

    app.state.session_factory = database.session_factory
    app.state.redis = redis
    app.state.live_store = LiveStateStore(redis)
    app.state.hub = RealtimeHub(redis)

    await app.state.hub.start()
    timer_task = asyncio.create_task(_timer_loop(app))
    logger.info("miniapp_ready")
    try:
        yield
    finally:
        timer_task.cancel()
        try:
            await timer_task
        except asyncio.CancelledError:
            pass
        await app.state.hub.stop()
        await redis.aclose()
        await database.dispose()
        logger.info("miniapp_stopped")


def create_app() -> FastAPI:
    """Build and configure the Mini App ASGI application."""
    settings = get_settings()
    config = get_miniapp_config()
    app = FastAPI(
        title="Mafia Mini App API",
        version="1.0.0",
        lifespan=_lifespan,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    # The Mini App is served from ``miniapp_url``; allow it (and Telegram's
    # WebView origins) to call the API. When unset we fall back to permissive
    # CORS for local development only.
    origins = [config.miniapp_url] if config.miniapp_url else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        """Translate domain errors into 400s carrying the Persian message."""
        return JSONResponse(status_code=400, content={"detail": exc.message_fa})

    app.include_router(router)
    return app
