"""Role model: the global catalog of playable roles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import RoleCode, RoleTeam

if TYPE_CHECKING:
    from app.models.game_role import GameRole


class Role(Base, IntPKMixin, TimestampMixin):
    """A role definition in the global catalog (seeded once).

    Games reference these definitions through :class:`GameRole`. Roles are never
    duplicated per-game here; the per-game selection & counts live in
    ``game_roles``.
    """

    __tablename__ = "roles"

    code: Mapped[RoleCode] = mapped_column(
        Enum(RoleCode, name="role_code", native_enum=True),
        unique=True,
        index=True,
        nullable=False,
    )
    name_fa: Mapped[str] = mapped_column(String(64), nullable=False)
    team: Mapped[RoleTeam] = mapped_column(
        Enum(RoleTeam, name="role_team", native_enum=True),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whether the role is enabled in the catalog and offered during game setup.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    game_roles: Mapped[list["GameRole"]] = relationship(back_populates="role")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Role code={self.code.value} team={self.team.value}>"
