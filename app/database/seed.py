"""Idempotent role-catalog seeding.

Inserts any roles from :data:`app.utils.role_catalog.ROLE_CATALOG` that are not
yet present, and refreshes display metadata for existing ones. Safe to run on
every startup.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.models.role import Role
from app.utils.role_catalog import ROLE_CATALOG

logger = get_logger(__name__)


async def seed_roles(session: AsyncSession) -> int:
    """Ensure every catalog role exists in the DB. Returns count inserted."""
    existing = {
        role.code
        for role in (await session.execute(select(Role))).scalars().all()
    }

    inserted = 0
    for definition in ROLE_CATALOG:
        if definition.code in existing:
            continue
        session.add(
            Role(
                code=definition.code,
                name_fa=definition.name_fa,
                team=definition.team,
                description=definition.description,
                is_active=True,
            )
        )
        inserted += 1

    if inserted:
        await session.flush()
    logger.info("roles_seeded", inserted=inserted, total=len(ROLE_CATALOG))
    return inserted
