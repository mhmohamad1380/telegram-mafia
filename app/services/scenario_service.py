"""ScenarioService: the presentation-facing façade over the Scenario Engine.

Handlers talk only to this service; it composes the (stateless) scenario
:class:`~app.scenarios.registry.ScenarioRegistry`,
:class:`~app.scenarios.validator.ScenarioValidator`, and the repository-backed
:class:`~app.scenarios.resolver.ScenarioRoleResolver` so no scenario rule leaks
into the bot layer.

Responsibilities:
    * list scenarios and fetch a scenario (with player-count filtering),
    * validate a chosen player count for a scenario,
    * report whether a scenario needs role selection (flexible) or is fixed,
    * expose the roles a creator may pick (as catalog DTOs) for a scenario,
    * resolve a scenario choice into the final ``role_id -> quantity`` mapping
      to persist (delegating to the resolver).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import RoleCode
from app.repositories import RepositoryProvider
from app.scenarios import (
    SCENARIO_REGISTRY,
    ScenarioDefinition,
    ScenarioRegistry,
    ScenarioResolveResult,
    ScenarioRoleResolver,
    ScenarioValidator,
)
from app.schemas.game import CustomRoleDTO, RoleCatalogItemDTO

from app.utils.exceptions import ScenarioNotFoundError
from app.utils.role_catalog import ROLE_BY_CODE


class ScenarioService:
    """Facade coordinating scenario lookup, validation, and resolution."""

    def __init__(
        self,
        repos: RepositoryProvider,
        *,
        registry: ScenarioRegistry | None = None,
        validator: ScenarioValidator | None = None,
        resolver: ScenarioRoleResolver | None = None,
    ) -> None:
        self._repos = repos
        self._registry = registry or SCENARIO_REGISTRY
        self._validator = validator or ScenarioValidator()
        self._resolver = resolver or ScenarioRoleResolver(repos)

    # --- Listing / lookup ---------------------------------------------------

    def list_scenarios(self) -> tuple[ScenarioDefinition, ...]:
        """Return every scenario in catalog order."""
        return self._registry.all()

    def get_scenario(self, code: str) -> ScenarioDefinition:
        """Return the scenario for ``code`` or raise :class:`ScenarioNotFoundError`."""
        scenario = self._registry.get(code)
        if scenario is None:
            raise ScenarioNotFoundError()
        return scenario

    def get_scenario_by_index(self, index: int) -> ScenarioDefinition:
        """Return the scenario at ``index`` (wrapping) — used by the encyclopaedia."""
        scenarios = self._registry.all()
        if not scenarios:  # pragma: no cover - catalog is never empty
            raise ScenarioNotFoundError()
        return scenarios[index % len(scenarios)]

    def index_of(self, code: str) -> int:
        idx = self._registry.index_of(code)
        return idx if idx is not None else 0

    # --- Validation ---------------------------------------------------------

    def validate_player_count(
        self, scenario: ScenarioDefinition, player_count: int
    ) -> None:
        """Raise if ``player_count`` is not playable under ``scenario``."""
        self._validator.validate_player_count(scenario, player_count)

    def ensure_role_selectable(
        self,
        scenario: ScenarioDefinition,
        role_code: RoleCode,
        player_count: int,
    ) -> None:
        """Raise if ``role_code`` may not be toggled for this scenario/count."""
        self._validator.ensure_role_selectable(scenario, role_code, player_count)

    def is_role_selectable(
        self,
        scenario: ScenarioDefinition,
        role_code: RoleCode,
        player_count: int,
    ) -> bool:
        return self._validator.is_role_selectable(
            scenario, role_code, player_count
        )

    # --- Selection support --------------------------------------------------

    def requires_role_selection(self, scenario: ScenarioDefinition) -> bool:
        """Whether the creator must pick roles (flexible) vs. a fixed scenario."""
        return not scenario.is_fixed

    async def get_selectable_roles(
        self, scenario: ScenarioDefinition
    ) -> list[RoleCatalogItemDTO]:
        """Return the roles a creator may enable for ``scenario`` as DTOs.

        Only meaningful for flexible scenarios; ordered as declared in the
        scenario's ``allowed_roles``. Roles missing from the DB are skipped
        defensively (the DB is always seeded from the same catalog).
        """
        dtos: list[RoleCatalogItemDTO] = []
        for code in scenario.allowed_roles:
            role = await self._repos.roles.get_by_code(code)
            if role is None:
                continue
            defn = ROLE_BY_CODE.get(role.code)
            dtos.append(
                RoleCatalogItemDTO(
                    role_id=role.id,
                    code=role.code,
                    name_fa=role.name_fa,
                    team=role.team,
                    description=role.description,
                    min_players=defn.min_players if defn is not None else None,
                )
            )
        return dtos

    # --- Resolution ---------------------------------------------------------

    async def resolve(
        self,
        *,
        scenario: ScenarioDefinition,
        player_count: int,
        selected_codes: Sequence[RoleCode] = (),
        selected_custom_roles: Sequence[CustomRoleDTO] = (),
    ) -> ScenarioResolveResult:
        """Resolve a scenario choice into a persistable composition.

        ``selected_custom_roles`` lets the creator mix their own custom roles
        ("نقش‌های من") into a flexible scenario; each is treated like a catalog
        role of the same team.
        """
        self._validator.validate_player_count(scenario, player_count)
        return await self._resolver.resolve(
            scenario=scenario,
            player_count=player_count,
            selected_codes=selected_codes,
            selected_custom_roles=selected_custom_roles,
        )

