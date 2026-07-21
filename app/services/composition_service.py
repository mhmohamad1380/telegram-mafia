"""RoleCompositionService: smart auto-completion of a partial role selection.

The creator may now pick *any* subset of roles (fewer than the player count).
This service fills the remaining slots with **simple citizens** and **simple
mafia only** — never special roles — while respecting the standard mafia/city
ratio of Iranian mafia.

The ratio logic lives behind a :class:`CompositionStrategy` (Strategy pattern),
so new scenarios (classic, professional, joker, zodiac, ...) can define their own
rules without touching the service or the rest of the system. The active
strategy is injected; the default is :class:`ClassicIranianStrategy`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

from app.config.logging import get_logger
from app.models.enums import RoleCode, RoleTeam
from app.models.role import Role
from app.repositories import RepositoryProvider
from app.schemas.game import CompositionResultDTO, TeamCompositionDTO
from app.utils.exceptions import (
    InvalidGameStateError,
    RoleNotAvailableForPlayerCountError,
    TooManyCitizensError,
    TooManyIndependentsError,
    TooManyMafiaError,
    TooManyRolesSelectedError,
)
from app.utils.role_catalog import ROLE_BY_CODE

logger = get_logger(__name__)

# Teams that play *with* the city and therefore count toward the town bucket
# when balancing the table. The Mason group wins with the city, so it is folded
# into the citizen count for ratio purposes.
_CITY_ALIGNED_TEAMS = (RoleTeam.CITIZEN, RoleTeam.MASON)



# --- Strategy pattern -------------------------------------------------------


class CompositionStrategy(ABC):
    """Defines the team-balance rules for a mafia scenario.

    Implementations translate a player count into the number of mafia (and the
    maximum number of independent roles) allowed. New scenarios subclass this.
    """

    #: Human-readable scenario name (for logging / future selection UI).
    name: str = "base"

    @abstractmethod
    def mafia_count(self, player_count: int) -> int:
        """Return the standard number of mafia for ``player_count`` players."""

    def max_independents(self, player_count: int) -> int:
        """Return the maximum number of independent roles allowed.

        Default: independents may not exceed the mafia count (they eat into the
        town's numbers, so keep them modest). Scenarios may override.
        """
        return max(0, self.mafia_count(player_count))


class ClassicIranianStrategy(CompositionStrategy):
    """Standard Iranian mafia ratio (~1 mafia per 3 players).

    Uses a well-known breakpoint table for small tables and falls back to a
    ``round(player_count / 3)`` rule for larger ones. The town always keeps a
    strict majority under this ratio.
    """

    name = "classic_iranian"

    # Inclusive upper-bound breakpoints: (max_players, mafia_count).
    _BREAKPOINTS: tuple[tuple[int, int], ...] = (
        (4, 1),    # 3-4 players   -> 1 mafia
        (7, 2),    # 5-7 players   -> 2 mafia
        (10, 3),   # 8-10 players  -> 3 mafia
        (13, 4),   # 11-13 players -> 4 mafia
        (16, 5),   # 14-16 players -> 5 mafia
        (18, 6),   # 17-18 players -> 6 mafia
    )

    def mafia_count(self, player_count: int) -> int:
        for max_players, mafia in self._BREAKPOINTS:
            if player_count <= max_players:
                return mafia
        # Larger tables: ~1 mafia per 3 players (rounded).
        return max(1, round(player_count / 3))


class RoleCompositionService:
    """Auto-completes a partial role selection using a composition strategy."""

    def __init__(
        self,
        repos: RepositoryProvider,
        strategy: CompositionStrategy | None = None,
    ) -> None:
        self._repos = repos
        self._strategy = strategy or ClassicIranianStrategy()

    async def complete_composition(
        self,
        *,
        player_count: int,
        selected_role_ids: Sequence[int],
    ) -> CompositionResultDTO:
        """Validate a partial selection and fill it up to ``player_count``.

        Args:
            player_count: Total number of players (target role count).
            selected_role_ids: Role ids chosen by the creator (each quantity 1).

        Returns:
            A :class:`CompositionResultDTO` with the final ``role_id -> quantity``
            mapping, the resulting team composition, an ordered list of role
            names, and the list of auto-added roles.

        Raises:
            TooManyRolesSelectedError: more roles selected than players.
            TooManyMafiaError / TooManyCitizensError / TooManyIndependentsError:
                the selection breaks the standard ratio.
            InvalidGameStateError: catalog is missing the base simple roles.
        """
        selected_ids = list(selected_role_ids)
        if len(selected_ids) > player_count:
            raise TooManyRolesSelectedError()

        roles = await self._repos.roles.get_by_ids(selected_ids)
        if len(roles) != len(set(selected_ids)):
            raise InvalidGameStateError("یک یا چند نقش انتخاب‌شده نامعتبر است.")

        # Enforce data-driven availability constraints (e.g. Mason group needs a
        # large table). The catalog is the single source of truth for gating.
        self._validate_player_count_constraints(roles, player_count)

        # Count selected roles by team. Mason-aligned roles play *with* the city
        # and therefore count toward the town bucket for ratio purposes.
        citizen_sel = sum(1 for r in roles if r.team in _CITY_ALIGNED_TEAMS)
        mafia_sel = sum(1 for r in roles if r.team == RoleTeam.MAFIA)
        indep_sel = sum(1 for r in roles if r.team == RoleTeam.INDEPENDENT)


        target_mafia = self._strategy.mafia_count(player_count)
        max_indep = self._strategy.max_independents(player_count)

        # --- Validate against the standard ratio ---------------------------
        if indep_sel > max_indep or indep_sel > player_count:
            raise TooManyIndependentsError()
        if mafia_sel > target_mafia:
            raise TooManyMafiaError()

        city_target = player_count - target_mafia - indep_sel
        if city_target < 0:
            # Too many independents pushed the town below zero.
            raise TooManyIndependentsError()
        if citizen_sel > city_target:
            raise TooManyCitizensError()

        # --- Auto-fill remaining slots (simple citizens / mafia only) ------
        add_mafia = target_mafia - mafia_sel
        add_citizen = city_target - citizen_sel

        simple_citizen = await self._get_role_by_code(RoleCode.CITIZEN)
        simple_mafia = await self._get_role_by_code(RoleCode.MAFIA)

        role_quantities: dict[int, int] = {rid: 1 for rid in selected_ids}
        added: list[tuple[str, int]] = []

        if add_mafia > 0:
            role_quantities[simple_mafia.id] = (
                role_quantities.get(simple_mafia.id, 0) + add_mafia
            )
            added.append((simple_mafia.name_fa, add_mafia))
        if add_citizen > 0:
            role_quantities[simple_citizen.id] = (
                role_quantities.get(simple_citizen.id, 0) + add_citizen
            )
            added.append((simple_citizen.name_fa, add_citizen))

        composition = TeamCompositionDTO(
            citizen=city_target,
            mafia=target_mafia,
            independent=indep_sel,
        )
        roles_ordered = self._ordered_role_names(
            roles=roles,
            add_mafia=add_mafia,
            add_citizen=add_citizen,
            simple_mafia=simple_mafia,
            simple_citizen=simple_citizen,
        )

        logger.info(
            "composition_completed",
            strategy=self._strategy.name,
            player_count=player_count,
            citizen=composition.citizen,
            mafia=composition.mafia,
            independent=composition.independent,
            added_mafia=add_mafia,
            added_citizen=add_citizen,
        )
        return CompositionResultDTO(
            role_quantities=role_quantities,
            composition=composition,
            roles_ordered=roles_ordered,
            added=added,
            player_count=player_count,
        )

    def compute_composition_counts(
        self, roles_by_team: Mapping[RoleTeam, int]
    ) -> TeamCompositionDTO:
        """Build a :class:`TeamCompositionDTO` from raw per-team counts."""
        return TeamCompositionDTO(
            citizen=roles_by_team.get(RoleTeam.CITIZEN, 0),
            mafia=roles_by_team.get(RoleTeam.MAFIA, 0),
            independent=roles_by_team.get(RoleTeam.INDEPENDENT, 0),
        )

    async def get_game_composition(self, *, game_id: int) -> TeamCompositionDTO:
        """Return the team composition of a game's *persisted* role pool.

        Sums ``quantity`` per team over the configured ``game_roles``. Used for
        the creator-only summary shown when the game starts (team counts only,
        no role names or player names).
        """
        game_roles = await self._repos.game_roles.list_for_game(game_id)
        counts: dict[RoleTeam, int] = {
            RoleTeam.CITIZEN: 0,
            RoleTeam.MAFIA: 0,
            RoleTeam.INDEPENDENT: 0,
        }
        for gr in game_roles:
            # City-aligned factions (e.g. Mason) are reported under the town.
            team = (
                RoleTeam.CITIZEN
                if gr.role.team in _CITY_ALIGNED_TEAMS
                else gr.role.team
            )
            counts[team] += gr.quantity
        return self.compute_composition_counts(counts)



    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _validate_player_count_constraints(
        roles: Sequence[Role], player_count: int
    ) -> None:
        """Reject roles whose catalog ``min_players`` exceeds ``player_count``.

        Keeps gating fully data-driven: the rule lives in the role catalog, not
        in hard-coded role-name checks. The presentation layer also hides these
        roles, so this is a defence-in-depth server-side guard.
        """
        for role in roles:
            defn = ROLE_BY_CODE.get(role.code)
            if defn is None or defn.min_players is None:
                continue
            if player_count < defn.min_players:
                raise RoleNotAvailableForPlayerCountError(
                    f"نقش «{role.name_fa}» فقط برای بازی‌های حداقل "
                    f"{defn.min_players} نفره مجاز است."
                )

    async def _get_role_by_code(self, code: RoleCode) -> Role:
        role = await self._repos.roles.get_by_code(code)
        if role is None:
            raise InvalidGameStateError(
                "نقش پایه در کاتالوگ یافت نشد. لطفاً دیتابیس را seed کنید."
            )
        return role


    @staticmethod
    def _ordered_role_names(
        *,
        roles: Sequence[Role],
        add_mafia: int,
        add_citizen: int,
        simple_mafia: Role,
        simple_citizen: Role,
    ) -> list[str]:
        """Produce a display-ordered list of all role names (selected + added).

        Order: mafia first, then citizens, then independents, then the
        auto-added simple mafia and simple citizens at the end.
        """
        order = {RoleTeam.MAFIA: 0, RoleTeam.CITIZEN: 1, RoleTeam.INDEPENDENT: 2}
        selected_sorted = sorted(roles, key=lambda r: (order[r.team], r.id))
        names = [r.name_fa for r in selected_sorted]
        names.extend([simple_mafia.name_fa] * add_mafia)
        names.extend([simple_citizen.name_fa] * add_citizen)
        return names
