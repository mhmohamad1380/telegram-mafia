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
    """Ensure every catalog role exists and its metadata is up to date.

    Inserts missing roles and refreshes mutable metadata (team, Persian name,
    description) for existing ones so catalog corrections — e.g. moving a role
    to the correct team — propagate to an already-seeded database on the next
    startup. Returns the number of rows inserted.
    """
    existing = {
        role.code: role
        for role in (await session.execute(select(Role))).scalars().all()
    }

    inserted = 0
    updated = 0
    for definition in ROLE_CATALOG:
        role = existing.get(definition.code)
        if role is None:
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
            continue

        # Sync mutable metadata in place if the catalog has diverged from the DB.
        if (
            role.name_fa != definition.name_fa
            or role.team != definition.team
            or role.description != definition.description
        ):
            role.name_fa = definition.name_fa
            role.team = definition.team
            role.description = definition.description
            updated += 1

    if inserted or updated:
        await session.flush()
    logger.info(
        "roles_seeded", inserted=inserted, updated=updated, total=len(ROLE_CATALOG)
    )
    return inserted

