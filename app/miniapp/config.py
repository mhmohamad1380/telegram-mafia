"""Mini App-specific configuration, read from the same environment/``.env``.

Kept separate from :class:`app.config.settings.Settings` so the online-play
feature owns its own knobs without touching the core bot config. Field names map
to ``MINIAPP_*`` (and a couple of table-timing) environment variables.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MiniAppConfig(BaseSettings):
    """Typed settings for the Mini App API/WebSocket server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    miniapp_host: str = Field(
        default="0.0.0.0",
        description="Bind address for the Mini App API/WebSocket server.",
    )
    miniapp_port: int = Field(
        default=8080, description="Port the Mini App server listens on."
    )
    miniapp_url: str | None = Field(
        default=None,
        description=(
            "Public HTTPS URL where the Mini App frontend is served (e.g. "
            "'https://mafia.example.com'). Used both to build the Telegram "
            "WebApp button and to lock down CORS. Telegram requires HTTPS; "
            "leave unset only for local development."
        ),
    )
    miniapp_initdata_ttl: int = Field(
        default=86400,
        ge=0,
        description=(
            "Max age (seconds) of a Telegram initData payload before it is "
            "rejected as stale. Guards against replay of captured auth strings."
        ),
    )
    speaking_seconds: int = Field(
        default=60,
        ge=5,
        description="Default per-turn speaking time (seconds) at a live table.",
    )
    challenge_seconds: int = Field(
        default=30, ge=5, description="Default challenge speaking time (seconds)."
    )

    @field_validator("miniapp_url", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """Treat an empty ``MINIAPP_URL`` (Compose default) as unset."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache(maxsize=1)
def get_miniapp_config() -> MiniAppConfig:
    """Return a cached :class:`MiniAppConfig` singleton."""
    return MiniAppConfig()
