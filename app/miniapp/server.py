"""Standalone entry point for the Mini App API/WebSocket server.

Run with ``python -m app.miniapp.server`` (or via the ``miniapp`` service in
docker-compose). Serves the FastAPI app built by :func:`app.miniapp.app.create_app`
using uvicorn. The bot process (``python -m app.main``) and this process are
independent and share only PostgreSQL + Redis, so each can be scaled separately.
"""

from __future__ import annotations

import uvicorn

from app.config.settings import get_settings
from app.miniapp.config import get_miniapp_config


def main() -> None:
    settings = get_settings()
    config = get_miniapp_config()
    uvicorn.run(
        "app.miniapp.app:create_app",
        factory=True,
        host=config.miniapp_host,
        port=config.miniapp_port,
        # We manage our own structlog config in the app lifespan; keep uvicorn's
        # access log but let it inherit levels from the environment.
        log_level=settings.log_level.lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
