"""ScenarioRoleResolver: turn a scenario choice into a persistable composition.

Given a scenario, a player count and (for flexible scenarios) the creator's
selected role codes, the resolver produces the final ``role_id -> quantity``
mapping that :meth:`GameService.configure_roles` persists, plus a display-ready
team breakdown.

* **Fixed scenarios** (e.g. Capo): the prescribed ``fixed_compositions`` entry
  is authoritative — the selection is ignored.
* **Flexible scenarios**: selected roles each count once and the remaining slots
  are topped up with the scenario's simple citizen / mafia fill roles while
  honouring the scenario's team ratio.

Role-code → role-id translation goes through the roles repository, so the DB
must be seeded (it always is at startup).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


from app.config.logging import get_logger
from app.models.enums import RoleCode, RoleTeam
from app.repositories import RepositoryProvider
from app.scenarios.definition import ScenarioDefinition
from app.schemas.game import CustomRoleDTO, TeamCompositionDTO

from app.utils.exceptions import (
    InvalidGameStateError,
    TooManyCitizensError,
    TooManyIndependentsError,
    TooManyMafiaError,
)

logger = get_logger(__name__)


# Teams counted with the town for ratio purposes (Mason plays with the city).
_CITY_ALIGNED_TEAMS = (RoleTeam.CITIZEN, RoleTeam.MASON)


@dataclass(frozen=True, slots=True)
class ScenarioResolveResult:
    """Outcome of resolving a scenario into a concrete role configuration.

    Attributes:
        role_quantities: Final ``role_id -> quantity`` mapping to persist.
        custom_role_quantities: Final ``custom_role_id -> quantity`` mapping for
            the creator's own custom roles selected into the game (empty unless
            custom roles were picked).
        composition: Per-team head counts for display.
        roles_ordered: Ordered Persian role names (mafia, city, independent).
        added: Auto-added fill roles as ``(name_fa, quantity)`` pairs (empty for
            fixed scenarios).
        player_count: The resolved player count.
        is_fixed: Whether the scenario prescribed the composition.
    """

    role_quantities: dict[int, int]
    composition: TeamCompositionDTO
    roles_ordered: list[str]
    added: list[tuple[str, int]]
    player_count: int
    is_fixed: bool
    custom_role_quantities: dict[int, int] = field(default_factory=dict)



class ScenarioRoleResolver:
    """Resolves scenario + selection into a persistable role composition."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    async def resolve(
        self,
        *,
        scenario: ScenarioDefinition,
        player_count: int,
        selected_codes: Sequence[RoleCode],
        selected_custom_roles: Sequence[CustomRoleDTO] = (),
    ) -> ScenarioResolveResult:
        """Resolve a scenario choice into a :class:`ScenarioResolveResult`.

        ``selected_custom_roles`` are the creator's own custom roles chosen for
        the game; each counts once toward its team's target, exactly like a
        catalog role (custom roles are ignored for fixed scenarios).
        """
        if scenario.is_fixed:
            return await self._resolve_fixed(scenario, player_count)
        return await self._resolve_flexible(
            scenario,
            player_count,
            list(selected_codes),
            list(selected_custom_roles),
        )


    # --- Fixed scenarios ----------------------------------------------------

    async def _resolve_fixed(
        self, scenario: ScenarioDefinition, player_count: int
    ) -> ScenarioResolveResult:
        comp = scenario.fixed_for(player_count)
        if not comp:
            raise InvalidGameStateError(
                "برای این تعداد بازیکن ترکیب ثابتی در سناریو تعریف نشده است."
            )

        role_quantities: dict[int, int] = {}
        counts = {RoleTeam.CITIZEN: 0, RoleTeam.MAFIA: 0, RoleTeam.INDEPENDENT: 0}
        ordered: list[tuple[RoleTeam, str, int]] = []
        for code, qty in comp.items():
            role = await self._repos.roles.get_by_code(code)
            if role is None:
                raise InvalidGameStateError(
                    "نقش موردنیاز سناریو در دیتابیس یافت نشد. لطفاً seed را اجرا کنید."
                )
            role_quantities[role.id] = role_quantities.get(role.id, 0) + qty
            team = self._bucket(role.team)
            counts[team] += qty
            ordered.append((role.team, role.name_fa, qty))

        composition = TeamCompositionDTO(
            citizen=counts[RoleTeam.CITIZEN],
            mafia=counts[RoleTeam.MAFIA],
            independent=counts[RoleTeam.INDEPENDENT],
        )
        roles_ordered = self._order_names(ordered)
        logger.info(
            "scenario_resolved_fixed",
            scenario=scenario.code,
            player_count=player_count,
            citizen=composition.citizen,
            mafia=composition.mafia,
            independent=composition.independent,
        )
        return ScenarioResolveResult(
            role_quantities=role_quantities,
            composition=composition,
            roles_ordered=roles_ordered,
            added=[],
            player_count=player_count,
            is_fixed=True,
        )

    # --- Flexible scenarios -------------------------------------------------

    async def _resolve_flexible(
        self,
        scenario: ScenarioDefinition,
        player_count: int,
        selected_codes: list[RoleCode],
        selected_custom_roles: list[CustomRoleDTO] | None = None,
    ) -> ScenarioResolveResult:
        custom_roles = selected_custom_roles or []
        if len(selected_codes) + len(custom_roles) > player_count:
            raise InvalidGameStateError(
                "تعداد نقش‌های انتخاب‌شده نمی‌تواند از تعداد بازیکنان بیشتر باشد."
            )

        # Resolve selected roles to ORM rows.
        selected_roles = []
        for code in selected_codes:
            role = await self._repos.roles.get_by_code(code)
            if role is None:
                raise InvalidGameStateError("یک یا چند نقش انتخاب‌شده نامعتبر است.")
            selected_roles.append(role)

        # Custom roles count toward their team's target exactly like catalog
        # roles; tally them alongside the catalog selection.
        citizen_sel = sum(
            1 for r in selected_roles if r.team in _CITY_ALIGNED_TEAMS
        ) + sum(1 for c in custom_roles if c.team in _CITY_ALIGNED_TEAMS)
        mafia_sel = sum(
            1 for r in selected_roles if r.team == RoleTeam.MAFIA
        ) + sum(1 for c in custom_roles if c.team == RoleTeam.MAFIA)
        indep_sel = sum(
            1 for r in selected_roles if r.team == RoleTeam.INDEPENDENT
        ) + sum(1 for c in custom_roles if c.team == RoleTeam.INDEPENDENT)


        target_mafia = scenario.mafia_count(player_count)
        max_indep = target_mafia  # independents may not exceed the mafia count

        if indep_sel > max_indep:
            raise TooManyIndependentsError()
        if mafia_sel > target_mafia:
            raise TooManyMafiaError()

        city_target = player_count - target_mafia - indep_sel
        if city_target < 0:
            raise TooManyIndependentsError()
        if citizen_sel > city_target:
            raise TooManyCitizensError()

        add_mafia = target_mafia - mafia_sel
        add_citizen = city_target - citizen_sel

        fill_citizen = await self._repos.roles.get_by_code(
            scenario.fill_citizen_code
        )
        fill_mafia = await self._repos.roles.get_by_code(scenario.fill_mafia_code)
        if fill_citizen is None or fill_mafia is None:
            raise InvalidGameStateError(
                "نقش پایه (شهروند/مافیای ساده) در دیتابیس یافت نشد."
            )

        role_quantities: dict[int, int] = {}
        for role in selected_roles:
            role_quantities[role.id] = role_quantities.get(role.id, 0) + 1

        # Custom roles are persisted via a parallel custom_role_id -> qty map.
        custom_role_quantities: dict[int, int] = {}
        for crole in custom_roles:
            custom_role_quantities[crole.id] = (
                custom_role_quantities.get(crole.id, 0) + 1
            )

        added: list[tuple[str, int]] = []

        if add_mafia > 0:
            role_quantities[fill_mafia.id] = (
                role_quantities.get(fill_mafia.id, 0) + add_mafia
            )
            added.append((fill_mafia.name_fa, add_mafia))
        if add_citizen > 0:
            role_quantities[fill_citizen.id] = (
                role_quantities.get(fill_citizen.id, 0) + add_citizen
            )
            added.append((fill_citizen.name_fa, add_citizen))

        composition = TeamCompositionDTO(
            citizen=city_target,
            mafia=target_mafia,
            independent=indep_sel,
        )

        ordered = [(r.team, r.name_fa, 1) for r in selected_roles]
        ordered.extend([(c.team, c.name_fa, 1) for c in custom_roles])
        ordered.extend([(RoleTeam.MAFIA, fill_mafia.name_fa, 1)] * add_mafia)
        ordered.extend([(RoleTeam.CITIZEN, fill_citizen.name_fa, 1)] * add_citizen)
        roles_ordered = self._order_names(ordered)


        logger.info(
            "scenario_resolved_flexible",
            scenario=scenario.code,
            player_count=player_count,
            citizen=composition.citizen,
            mafia=composition.mafia,
            independent=composition.independent,
            added_mafia=add_mafia,
            added_citizen=add_citizen,
        )
        return ScenarioResolveResult(
            role_quantities=role_quantities,
            composition=composition,
            roles_ordered=roles_ordered,
            added=added,
            player_count=player_count,
            is_fixed=False,
            custom_role_quantities=custom_role_quantities,
        )


    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _bucket(team: RoleTeam) -> RoleTeam:
        """Fold city-aligned teams (e.g. Mason) into the citizen bucket."""
        return RoleTeam.CITIZEN if team in _CITY_ALIGNED_TEAMS else team

    @staticmethod
    def _order_names(entries: list[tuple[RoleTeam, str, int]]) -> list[str]:
        """Flatten ``(team, name, qty)`` entries into an ordered name list.

        Order: mafia, then city-aligned, then independent.
        """
        order = {
            RoleTeam.MAFIA: 0,
            RoleTeam.CITIZEN: 1,
            RoleTeam.MASON: 1,
            RoleTeam.INDEPENDENT: 2,
        }
        names: list[str] = []
        for team, name, qty in sorted(entries, key=lambda e: order.get(e[0], 3)):
            names.extend([name] * qty)
        return names
