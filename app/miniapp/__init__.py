"""Telegram Mini App backend.

A thin FastAPI (ASGI) application that exposes the online-play surface of the
Mafia game to the Telegram WebApp frontend. It deliberately **reuses the exact
same** SQLAlchemy models, repositories, and service layer as the aiogram bot —
there is no second ORM and no duplicated business logic. The Mini App only adds:

* HTTP transport (REST) and a WebSocket transport for realtime sync,
* authentication of Telegram WebApp ``initData`` (server-side, HMAC-verified),
* a Redis pub/sub fan-out so every table member sees state changes live.

See :func:`app.miniapp.app.create_app` for the composition root and
``app.miniapp.server`` for the standalone entry point.
"""

from __future__ import annotations

__all__ = ["create_app"]


def create_app():  # pragma: no cover - thin re-export to avoid import cycles
    """Lazy re-export of the app factory (keeps import side effects contained)."""
    from app.miniapp.app import create_app as _factory

    return _factory()
