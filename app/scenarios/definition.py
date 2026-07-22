"""Immutable scenario definitions and their formatting.

A :class:`ScenarioDefinition` is a pure-data description of a mafia game mode.
It contains *everything* the rest of the system needs to know about a scenario
without embedding any behaviour in handlers or core services:

* identity: ``code`` / ``name_fa`` / ``description``,
* player bounds: ``min_players`` / ``max_players`` / ``suggested_counts``,
* the roles a creator may pick (``allowed_roles``),
* the night wake order (``wake_order``),
* team-balance rules — either a fixed per-count composition
  (``fixed_compositions``) or a :class:`TeamRatioRule` (``ratio_rule``),
* the standard team ratio text, win conditions, and special day/night rules
  (all free-form Persian text shown to players).

Everything is ``frozen`` so definitions are safe to share as module-level
singletons.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.models.enums import RoleCode, RoleTeam


@dataclass(frozen=True, slots=True)
class TeamRatioRule:
    """Rule that maps a player count to the standard number of mafia.

    ``breakpoints`` is a tuple of inclusive ``(max_players, mafia_count)`` pairs
    evaluated in order; the first whose ``max_players >= player_count`` wins.
    For counts beyond every breakpoint, ``fallback_ratio`` is applied as
    ``round(player_count * fallback_ratio)`` (min 1).

    This mirrors the classic Iranian ~1-mafia-per-3-players rule but is fully
    data-driven so each scenario can tune its own balance.
    """

    breakpoints: tuple[tuple[int, int], ...] = (
        (4, 1),
        (7, 2),
        (10, 3),
        (13, 4),
        (16, 5),
        (18, 6),
    )
    fallback_ratio: float = 1 / 3

    def mafia_count(self, player_count: int) -> int:
        for max_players, mafia in self.breakpoints:
            if player_count <= max_players:
                return mafia
        return max(1, round(player_count * self.fallback_ratio))


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """Immutable, data-driven description of a single mafia scenario.

    Attributes:
        code: Stable, language-independent identifier (e.g. ``"capo"``).
        name_fa: Persian display name shown in menus.
        description: One-paragraph Persian summary shown on the intro screen.
        min_players / max_players: Inclusive player-count bounds.
        suggested_counts: Quick-pick counts offered to the creator (filtered to
            the ``[min_players, max_players]`` range at render time).
        allowed_roles: Roles the creator may enable for this scenario, in
            display order. The auto-fill roles (simple citizen/mafia) should be
            included so the composition can top up with them.
        wake_order: Night wake order (role codes) — pure data used for the
            scenario overview and any future night engine.
        ratio_rule: Team-balance rule for flexible scenarios. Ignored when a
            matching ``fixed_compositions`` entry exists for the player count.
        fixed_compositions: Optional exact ``player_count -> {RoleCode: qty}``
            composition. When present for a count, the scenario is fully
            prescribed (no free role selection) and the mapping is authoritative.
        team_ratio_text: Free-form Persian description of the standard ratio.
        win_conditions: Free-form Persian description of win conditions.
        special_rules: Ordered Persian bullet points for special day/night rules.
        fill_citizen_code / fill_mafia_code: Role codes used to top up remaining
            slots for flexible scenarios (defaults: simple citizen / mafia).
    """

    code: str
    name_fa: str
    description: str
    min_players: int
    max_players: int
    suggested_counts: tuple[int, ...]
    allowed_roles: tuple[RoleCode, ...]
    wake_order: tuple[RoleCode, ...] = ()
    ratio_rule: TeamRatioRule | None = None
    fixed_compositions: Mapping[int, Mapping[RoleCode, int]] = field(
        default_factory=dict
    )
    team_ratio_text: str = ""
    win_conditions: str = ""
    special_rules: tuple[str, ...] = ()
    fill_citizen_code: RoleCode = RoleCode.CITIZEN
    fill_mafia_code: RoleCode = RoleCode.MAFIA

    # --- Derived helpers ----------------------------------------------------

    @property
    def is_fixed(self) -> bool:
        """True when this scenario prescribes an exact composition per count."""
        return bool(self.fixed_compositions)

    def supports_player_count(self, player_count: int) -> bool:
        """Whether ``player_count`` is playable under this scenario."""
        if not self.min_players <= player_count <= self.max_players:
            return False
        if self.is_fixed:
            return player_count in self.fixed_compositions
        return True

    def allowed_counts(self) -> list[int]:
        """The concrete list of playable player counts.

        For fixed scenarios this is exactly the configured composition keys;
        for flexible scenarios it is the whole ``[min, max]`` range.
        """
        if self.is_fixed:
            return sorted(self.fixed_compositions)
        return list(range(self.min_players, self.max_players + 1))

    def fixed_for(self, player_count: int) -> Mapping[RoleCode, int] | None:
        """Return the fixed composition for ``player_count`` (or ``None``)."""
        return self.fixed_compositions.get(player_count)

    def mafia_count(self, player_count: int) -> int:
        """Standard mafia count for ``player_count`` under this scenario."""
        if self.is_fixed:
            comp = self.fixed_compositions.get(player_count, {})
            from app.utils.role_catalog import ROLE_BY_CODE

            return sum(
                qty
                for code, qty in comp.items()
                if (d := ROLE_BY_CODE.get(code)) is not None
                and d.team == RoleTeam.MAFIA
            )
        rule = self.ratio_rule or TeamRatioRule()
        return rule.mafia_count(player_count)


def _persian(n: int) -> str:
    from app.utils.codes import to_persian_digits

    return to_persian_digits(n)


def format_scenario_overview(defn: ScenarioDefinition) -> str:
    """Render the full Persian intro/overview block for a scenario.

    Shown after the creator selects a scenario (step 2 of the wizard) and from
    the scenario encyclopaedia. Includes description, player bounds, standard
    ratio, win conditions, night wake order, and special rules.
    """
    from app.utils.role_catalog import ROLE_BY_CODE

    counts = defn.allowed_counts()
    if counts:
        counts_fa = "، ".join(_persian(c) for c in counts)
    else:  # pragma: no cover - every scenario has at least one count
        counts_fa = "-"

    lines = [
        f"🎬 <b>{defn.name_fa}</b>",
        "",
        defn.description,
        "",
        f"👥 تعداد بازیکنان: {counts_fa} نفر",
    ]
    if defn.team_ratio_text:
        lines.append(f"⚖️ نسبت استاندارد تیم‌ها: {defn.team_ratio_text}")
    if defn.win_conditions:
        lines.append(f"🏆 شرایط برد: {defn.win_conditions}")

    if defn.wake_order:
        names = []
        for i, code in enumerate(defn.wake_order, start=1):
            d = ROLE_BY_CODE.get(code)
            name = d.name_fa if d is not None else code.value
            names.append(f"{_persian(i)}. {name}")
        lines.append("")
        lines.append("🌙 <b>ترتیب بیدار شدن نقش‌ها:</b>")
        lines.extend(names)

    if defn.special_rules:
        lines.append("")
        lines.append("📌 <b>قوانین ویژه:</b>")
        lines.extend(f"• {rule}" for rule in defn.special_rules)

    return "\n".join(lines)


def format_scenario_composition(
    defn: ScenarioDefinition, player_count: int
) -> str:
    """Render the fixed role composition of a scenario for a given count.

    Only meaningful for fixed scenarios; returns an empty string otherwise.
    Groups roles by team with Persian names and quantities.
    """
    comp = defn.fixed_for(player_count)
    if not comp:
        return ""
    from app.utils.role_catalog import ROLE_BY_CODE, TEAM_LABELS_FA

    by_team: dict[RoleTeam, list[str]] = {}
    for code, qty in comp.items():
        d = ROLE_BY_CODE.get(code)
        if d is None:
            continue
        label = d.name_fa if qty == 1 else f"{d.name_fa} ×{_persian(qty)}"
        by_team.setdefault(d.team, []).append(label)

    lines = [
        f"🎭 <b>ترکیب نقش‌ها ({_persian(player_count)} نفره):</b>",
        "",
    ]
    for team, team_label in TEAM_LABELS_FA.items():
        roles = by_team.get(team)
        if not roles:
            continue
        lines.append(f"<b>{team_label}:</b>")
        lines.extend(f"• {r}" for r in roles)
        lines.append("")
    return "\n".join(lines).strip()


def sequence_as_tuple(values: Sequence[RoleCode]) -> tuple[RoleCode, ...]:
    """Small helper to build role-code tuples (keeps catalog defs terse)."""
    return tuple(values)
