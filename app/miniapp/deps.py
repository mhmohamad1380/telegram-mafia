"""FastAPI dependencies for the Mini App: auth, DB session, service wiring.

The single most important dependency here is :func:`require_user`, which turns
the ``Authorization: tma <initData>`` header into a verified Telegram user by
delegating to :func:`app.miniapp.auth.verify_init_data`. Routes depend on it so
they can trust ``user.id`` — it is never taken from the request body.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.miniapp.auth import InitData, InitDataError, verify_init_data
from app.miniapp.config import MiniAppConfig, get_miniapp_config
from app.miniapp.live_state import LiveStateStore
from app.miniapp.realtime import RealtimeHub
from app.miniapp.service import MiniAppService
from app.services import ServiceProvider


def get_settings_dep() -> Settings:
    return get_settings()


def get_config_dep() -> MiniAppConfig:
    return get_miniapp_config()


def get_hub(request: Request) -> RealtimeHub:
    """The process-wide realtime hub, created in the app lifespan."""
    return request.app.state.hub


def get_store(request: Request) -> LiveStateStore:
    """The Redis-backed live-state store, created in the app lifespan."""
    return request.app.state.live_store


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async DB session, committing on success.

    Mirrors the bot's DatabaseMiddleware: one unit of work per request, rolled
    back on any exception so a failed mutation never leaks a partial write.
    """
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_init_data(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    config: Annotated[MiniAppConfig, Depends(get_config_dep)],
    authorization: Annotated[str | None, Header()] = None,
) -> InitData:
    """Verify the ``Authorization: tma <initData>`` header (or 401)."""
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing initData",
            headers={"WWW-Authenticate": "tma"},
        )
    raw = authorization.removeprefix("tma ").strip()
    try:
        return verify_init_data(
            raw,
            bot_token=settings.bot_token,
            max_age_seconds=config.miniapp_initdata_ttl,
        )
    except InitDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "tma"},
        ) from exc


InitDataDep = Annotated[InitData, Depends(require_init_data)]


async def require_user(
    init_data: InitDataDep,
    session: SessionDep,
) -> int:
    """Ensure the verified Telegram user exists in our DB, returning its id.

    Upserts on first contact so a player who opens the Mini App before ever
    messaging the bot still gets a User row (same behaviour as AuthMiddleware).
    """
    services = ServiceProvider(session)
    tg = init_data.user
    await services.repos.users.upsert_from_telegram(
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )
    return tg.id


UserIdDep = Annotated[int, Depends(require_user)]


def get_service(
    session: SessionDep,
    store: Annotated[LiveStateStore, Depends(get_store)],
) -> MiniAppService:
    """Compose the request-scoped :class:`MiniAppService`."""
    return MiniAppService(ServiceProvider(session), store)


ServiceDep = Annotated[MiniAppService, Depends(get_service)]
ConfigDep = Annotated[MiniAppConfig, Depends(get_config_dep)]
