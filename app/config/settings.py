"""Application settings loaded from environment variables via Pydantic Settings.

All configuration is centralized here so the rest of the codebase depends on a
single, typed, validated source of truth. Use :func:`get_settings` to obtain a
cached singleton instance.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Values are read (case-insensitively) from environment variables or a local
    ``.env`` file. See ``.env.example`` for the full list of options.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(..., description="Telegram Bot API token from @BotFather")
    bot_proxy: str | None = Field(
        default=None,
        description=(
            "Optional proxy URL for the Telegram HTTP session, e.g. "
            "'socks5://127.0.0.1:10808' or 'http://127.0.0.1:8080'. Useful where "
            "Telegram is blocked. Requires 'aiohttp-socks' for socks schemes."
        ),
    )


    # --- PostgreSQL ---
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="mafia")
    postgres_password: str = Field(default="mafia")
    postgres_db: str = Field(default="mafia")

    # --- Redis ---
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str | None = Field(default=None)

    # --- Application ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_console: bool = Field(default=True)
    environment: Literal["development", "production"] = Field(default="development")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Sync SQLAlchemy connection URL (psycopg/asyncpg not used here).

        Alembic uses the async engine directly, but this is provided for tooling
        that expects a synchronous DSN.
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis connection URL used by the aiogram FSM storage."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (singleton)."""
    return Settings()  # type: ignore[call-arg]
