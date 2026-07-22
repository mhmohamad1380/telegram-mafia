"""CustomRole model: user-owned, private role definitions.

Each custom role belongs to exactly one :class:`User` (its owner) and is only
ever visible to, editable by, and usable by that owner. Deletion is *soft*
(``is_active = False``) so historical games that referenced the role keep
working and the row can be audited, while the role disappears from the owner's
management screens and future game setups.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin, TimestampMixin
from app.models.enums import RoleTeam

if TYPE_CHECKING:
    from app.models.game_role import GameRole
    from app.models.user import User


class CustomRole(Base, IntPKMixin, TimestampMixin):
    """A private, user-defined role.

    Mirrors the essential, presentation-relevant fields of the global
    :class:`~app.models.role.Role` (Persian name, team, description) but scoped
    to an owner. Unlike catalog roles it has no :class:`RoleCode`; games
    reference it via :class:`GameRole.custom_role_id`.
    """

    __tablename__ = "custom_roles"
    __table_args__ = (
        # A user cannot have two *active* custom roles with the same name. Soft
        # deletes set ``is_active = False`` and clear/rename is not required
        # because we filter on ``is_active`` everywhere the constraint matters;
        # the DB-level uniqueness still prevents duplicate live names because we
        # only ever insert active rows and never reactivate a name in use.
        UniqueConstraint("owner_id", "name_fa", name="owner_role_name"),
    )

    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name_fa: Mapped[str] = mapped_column(String(64), nullable=False)
    team: Mapped[RoleTeam] = mapped_column(
        Enum(RoleTeam, name="role_team", native_enum=True, create_type=False),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Soft-delete flag: False means the role is hidden from the owner and cannot
    # be selected in new games, without breaking existing references.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="custom_roles")
    game_roles: Mapped[list["GameRole"]] = relationship(back_populates="custom_role")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<CustomRole id={self.id} owner_id={self.owner_id} "
            f"name={self.name_fa!r} team={self.team.value} active={self.is_active}>"
        )
