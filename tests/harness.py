"""E2E harness: app context, DB lifecycle, and per-operation session helpers.

The suite exercises the **real** service layer against a **real** PostgreSQL and
Redis, exactly as the running bot would. To stay faithful to production wiring
without a live Telegram connection, we reproduce the two things the aiogram
middlewares give handlers:

1. a fresh :class:`~sqlalchemy.ext.asyncio.AsyncSession` per update, committed on
   success / rolled back on error (mirrors ``DatabaseMiddleware`` +
   ``Database.session``), and
2. a fully-wired :class:`~app.services.ServiceProvider` bound to that session
   (mirrors the DI middleware), so a "handler action" is just a callback that
   receives ``services`` and does its work.

:class:`AppContext.act` runs one such unit of work in its own transaction —
this is the atomic building block every test uses, and it is what makes the
concurrency tests meaningful (each concurrent actor gets an independent session,
just like two real Telegram updates would).
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

from redis.asyncio import Redis
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.seed import seed_roles
from app.database.session import Database
from app.services import ServiceProvider

T = TypeVar("T")

#: Base Telegram id for synthesised fake users. Kept high to avoid colliding
#: with any real ids that might linger in a shared dev database.
FAKE_USER_BASE = 900_000_000


class FakeUser:
    """A minimal stand-in for a Telegram user used to drive the flow."""

    __slots__ = ("id", "username", "first_name", "last_name")

    def __init__(self, index: int) -> None:
        self.id = FAKE_USER_BASE + index
        self.username = f"tester{index}"
        self.first_name = f"بازیکن{index}"
        self.last_name = None

    @property
    def display_name(self) -> str:
        return self.first_name or self.username or str(self.id)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"FakeUser(id={self.id}, name={self.display_name!r})"


class AppContext:
    """Owns the DB engine + Redis for a test run and runs units of work.

    Not a singleton: constructed once by the runner, disposed at the end.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._database = Database(
            self._settings.database_url,
            pool_size=10,
            max_overflow=10,
        )
        self._redis: Redis | None = None

    @property
    def database(self) -> Database:
        return self._database

    # --- Lifecycle ----------------------------------------------------------

    async def startup(self) -> None:
        """Seed roles (idempotent) so the catalog is present for every test."""
        async with self._database.session() as session:
            await seed_roles(session)

    async def shutdown(self) -> None:
        await self._database.dispose()
        if self._redis is not None:
            await self._redis.aclose()

    # --- Redis --------------------------------------------------------------

    def redis(self) -> Redis:
        """Return (lazily create) a Redis client using the app's settings."""
        if self._redis is None:
            self._redis = Redis.from_url(self._settings.redis_url)
        return self._redis

    # --- Units of work ------------------------------------------------------

    async def act(self, fn: Callable[[ServiceProvider], Awaitable[T]]) -> T:
        """Run ``fn`` with a fresh, committed session + wired services.

        This is the exact contract a real handler operates under: everything it
        does happens inside one transaction that commits on success. Raising
        propagates to the caller (tests wrap this via ``reporter.run`` /
        ``reporter.expect_raises`` to record outcomes without stopping).
        """
        async with self._database.session() as session:
            services = ServiceProvider(session)
            return await fn(services)

    async def read(self, fn: Callable[[ServiceProvider], Awaitable[T]]) -> T:
        """Alias of :meth:`act` for read-only clarity at call sites."""
        return await self.act(fn)

    # --- Fake users ---------------------------------------------------------

    async def ensure_users(self, users: list[FakeUser]) -> None:
        """Upsert the given fake users (mirrors the auth middleware upsert)."""

        async def _op(services: ServiceProvider) -> None:
            for u in users:
                await services.repos.users.upsert_from_telegram(
                    telegram_id=u.id,
                    username=u.username,
                    first_name=u.first_name,
                    last_name=u.last_name,
                )

        await self.act(_op)

    def make_users(self, count: int, *, start: int = 0) -> list[FakeUser]:
        """Create ``count`` fake users with stable, unique ids."""
        return [FakeUser(start + i) for i in range(count)]

    # --- Cleanup ------------------------------------------------------------

    async def cleanup_fake_data(self) -> None:
        """Remove any rows produced by fake users so reruns stay deterministic.

        Deletes games created by fake users (CASCADE clears players / roles /
        assignments / events) and the fake users + their custom roles. Safe to
        run before and after a suite.
        """
        async with self._database.session() as session:
            await session.execute(
                text(
                    "DELETE FROM games WHERE creator_id >= :base"
                ),
                {"base": FAKE_USER_BASE},
            )
            # Players referencing fake users in games created by real users are
            # unlikely in tests, but clear them defensively before users go.
            await session.execute(
                text(
                    "DELETE FROM game_players WHERE user_id >= :base"
                ),
                {"base": FAKE_USER_BASE},
            )
            await session.execute(
                text(
                    "DELETE FROM custom_roles WHERE owner_id >= :base"
                ),
                {"base": FAKE_USER_BASE},
            )
            await session.execute(
                text("DELETE FROM users WHERE id >= :base"),
                {"base": FAKE_USER_BASE},
            )


def running_in_ci() -> bool:
    """Whether we appear to be running in an automated environment."""
    return bool(os.environ.get("CI"))
