"""RoleInfoService: read-only access to the role encyclopaedia.

Backs the "📖 توضیح نقش‌ها" feature. Navigation is index-based over the static
:data:`app.utils.role_catalog.ROLE_CATALOG` ordering, so a role can be shown,
paged (previous/next), and listed without any database access — the catalog is
the single source of truth for role metadata.

Kept in the service layer (rather than the handler) so the presentation code
only asks *what to show* and never reaches into the catalog directly, matching
the project's Clean Architecture / Service Layer conventions.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.role_catalog import (
    ROLE_CATALOG,
    RoleDefinition,
    format_role_details,
)


@dataclass(frozen=True, slots=True)
class RoleInfoPage:
    """A single role page plus the navigation context needed to render it.

    Attributes:
        index: 0-based position of this role in the catalog.
        total: Total number of roles (for the "x of y" indicator).
        name_fa: Persian display name of the role at ``index``.
        details: Fully-rendered, beginner-friendly description block.
        prev_index: Index of the previous role (wraps around).
        next_index: Index of the next role (wraps around).
    """

    index: int
    total: int
    name_fa: str
    details: str
    prev_index: int
    next_index: int


@dataclass(frozen=True, slots=True)
class RoleIndexItem:
    """A lightweight entry for the "list all roles" grid."""

    index: int
    name_fa: str


class RoleInfoService:
    """Serves paginated role descriptions from the static catalog."""

    #: The ordered catalog this service navigates.
    _catalog: tuple[RoleDefinition, ...] = ROLE_CATALOG

    @property
    def total(self) -> int:
        """Number of roles available in the encyclopaedia."""
        return len(self._catalog)

    def get_page(self, index: int) -> RoleInfoPage:
        """Return the role page at ``index`` (wrapping out-of-range values).

        Wrapping means the previous/next buttons cycle endlessly instead of
        dead-ending, which keeps the UX simple for a fixed-size catalog.
        """
        total = self.total
        if total == 0:  # pragma: no cover - catalog is always seeded
            raise ValueError("Role catalog is empty.")
        idx = index % total
        defn = self._catalog[idx]
        return RoleInfoPage(
            index=idx,
            total=total,
            name_fa=defn.name_fa,
            details=format_role_details(defn),
            prev_index=(idx - 1) % total,
            next_index=(idx + 1) % total,
        )

    def list_index(self) -> list[RoleIndexItem]:
        """Return every role as ``(index, name)`` for the selection grid."""
        return [
            RoleIndexItem(index=i, name_fa=defn.name_fa)
            for i, defn in enumerate(self._catalog)
        ]
