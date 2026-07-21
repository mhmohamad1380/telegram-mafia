"""Application settings loaded from environment variables via Pydantic Settings.

All configuration is centralized here so the rest of the codebase depends on a
single, typed, validated source of truth. Use :func:`get_settings` to obtain a
cached singleton instance.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator
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
            "Telegram is blocked. Requires 'aiohttp-socks' for socks schemes. "
            "Leave unset/empty to connect directly with no proxy."
        ),
    )

    @field_validator("bot_proxy", "redis_password", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        """Treat empty/whitespace-only strings as unset (``None``).

        Docker Compose expands an unset ``${BOT_PROXY:-}`` to an empty string
        rather than leaving it undefined, which would otherwise be interpreted
        as a (bogus) proxy URL. Normalizing to ``None`` keeps the proxy strictly
        opt-in.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value



    # --- PostgreSQL ---
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="mafia")
    postgres_password: str = Field(default="mafia")
    postgres_db: str = Field(default="mafia")
    # Connection-pool sizing. Kept small by default so the app is friendly to
    # memory-constrained hosts (each PostgreSQL connection is a separate backend
    # process). Raise these for high-traffic deployments with more RAM.
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)


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
