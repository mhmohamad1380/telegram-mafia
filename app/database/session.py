"""Async engine + session factory management.

Wraps SQLAlchemy's async engine and ``async_sessionmaker`` behind a small
:class:`Database` helper. A module-level singleton is created via
:func:`init_database` at application startup and consumed by the DI middleware.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Owns the async engine and session factory for the application's lifetime."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self._engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a transactional session scope.

        Commits on success, rolls back on exception, and always closes. Handlers
        normally receive a session from the DI middleware instead of using this
        directly, but it is handy for scripts and startup tasks.
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def dispose(self) -> None:
        """Dispose of the engine's connection pool (call on shutdown)."""
        await self._engine.dispose()


# --- Module-level singleton wiring -------------------------------------------

_database: Database | None = None


def init_database(url: str, *, echo: bool = False) -> Database:
    """Initialize and cache the global :class:`Database` singleton."""
    global _database
    if _database is None:
        _database = Database(url, echo=echo)
    return _database


def get_engine() -> AsyncEngine:
    """Return the initialized engine (raises if not initialized)."""
    if _database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _database.engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the initialized session factory (raises if not initialized)."""
    if _database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _database.session_factory
