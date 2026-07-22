"""ScenarioRegistry: lookup and listing over the scenario catalog.

The registry is the only component that knows *which* scenarios exist. It is a
thin, immutable index over :data:`app.scenarios.catalog.SCENARIO_CATALOG`. A
module-level singleton :data:`SCENARIO_REGISTRY` is shared everywhere; tests may
build their own registry with a custom catalog.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.scenarios.catalog import SCENARIO_CATALOG
from app.scenarios.definition import ScenarioDefinition


class ScenarioRegistry:
    """Ordered, immutable index of scenarios keyed by their ``code``."""

    def __init__(self, scenarios: Sequence[ScenarioDefinition]) -> None:
        self._ordered: tuple[ScenarioDefinition, ...] = tuple(scenarios)
        self._by_code: dict[str, ScenarioDefinition] = {
            s.code: s for s in self._ordered
        }
        if len(self._by_code) != len(self._ordered):
            raise ValueError("Duplicate scenario code in registry.")

    def all(self) -> tuple[ScenarioDefinition, ...]:
        """Return every scenario in catalog order."""
        return self._ordered

    def get(self, code: str) -> ScenarioDefinition | None:
        """Return the scenario with ``code`` (or ``None`` if unknown)."""
        return self._by_code.get(code)

    def exists(self, code: str) -> bool:
        return code in self._by_code

    def index_of(self, code: str) -> int | None:
        """Return the 0-based catalog position of ``code`` (or ``None``)."""
        for i, s in enumerate(self._ordered):
            if s.code == code:
                return i
        return None

    def __len__(self) -> int:
        return len(self._ordered)


#: Shared registry backed by the built-in catalog.
SCENARIO_REGISTRY = ScenarioRegistry(SCENARIO_CATALOG)
