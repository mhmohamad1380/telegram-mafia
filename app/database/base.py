"""SQLAlchemy declarative base and shared column mixins.

All ORM models inherit from :class:`Base`. Common audit columns (``id``,
``created_at``, ``updated_at``) live in :class:`TimestampMixin` /
:class:`IntPKMixin` so individual models stay concise.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# A consistent naming convention keeps generated constraint/index names stable,
# which is essential for reliable Alembic autogenerate/downgrade behavior.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IntPKMixin:
    """Adds a surrogate ``BIGINT`` primary key named ``id``."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` audit timestamps (server-side)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
