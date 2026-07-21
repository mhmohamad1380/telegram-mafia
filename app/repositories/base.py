"""Generic async repository base class.

Provides common CRUD primitives shared by concrete repositories. Concrete
repositories own all query logic for a single aggregate so services (and
handlers) never issue SQL directly.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Common async CRUD operations over a single ORM model.

    Repositories operate on a caller-supplied :class:`AsyncSession`; they never
    commit. Transaction boundaries are owned by the service layer / DI middleware
    so multiple repository calls can participate in one atomic unit of work.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: int) -> ModelT | None:
        """Return an entity by primary key, or ``None``."""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Stage a new entity for insert and flush to obtain its id."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete a loaded entity."""
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_by_id(self, entity_id: int) -> None:
        """Delete an entity by primary key without loading it first."""
        await self.session.execute(
            delete(self.model).where(self.model.id == entity_id)  # type: ignore[attr-defined]
        )

    async def list_all(self) -> list[ModelT]:
        """Return all entities (use sparingly; intended for small tables)."""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())
