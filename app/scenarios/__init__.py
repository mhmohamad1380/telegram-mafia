"""Scenario Engine: data-driven mafia scenario definitions.

This package is the single source of truth for *scenarios* (game modes). Each
scenario is an independent, immutable :class:`ScenarioDefinition` describing its
name, player-count bounds, allowed roles, night wake order, team ratio / fixed
composition, win conditions, and special day/night rules.

The design is deliberately **data-driven** and closed for modification:

* adding a new scenario means adding one :class:`ScenarioDefinition` to
  :mod:`app.scenarios.catalog` and registering it — no handler, core service, or
  engine logic changes are required;
* handlers never encode scenario rules: they ask :class:`ScenarioService`
  (built on :class:`ScenarioRegistry`, :class:`ScenarioValidator`,
  :class:`ScenarioRoleResolver`) *what* to show and *whether* something is
  allowed.

Public API:
    ScenarioDefinition, TeamRatioRule, ScenarioRegistry, ScenarioValidator,
    ScenarioRoleResolver, SCENARIO_REGISTRY, format_scenario_overview.
"""

from __future__ import annotations

from app.scenarios.definition import (
    ScenarioDefinition,
    TeamRatioRule,
    format_scenario_composition,
    format_scenario_overview,
)
from app.scenarios.registry import SCENARIO_REGISTRY, ScenarioRegistry
from app.scenarios.resolver import ScenarioResolveResult, ScenarioRoleResolver
from app.scenarios.validator import ScenarioValidator

__all__ = [
    "ScenarioDefinition",
    "TeamRatioRule",
    "ScenarioRegistry",
    "ScenarioValidator",
    "ScenarioRoleResolver",
    "ScenarioResolveResult",
    "SCENARIO_REGISTRY",
    "format_scenario_overview",
    "format_scenario_composition",
]

