"""ScenarioValidator: pure, side-effect-free validation of scenario choices.

All scenario *rules* about what is allowed live here so handlers and services
never re-implement them. The validator raises domain errors (translated to
Persian for the user) on invalid input and is otherwise silent.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.enums import RoleCode
from app.scenarios.definition import ScenarioDefinition
from app.utils.codes import to_persian_digits
from app.utils.exceptions import (
    InvalidGameStateError,
    InvalidPlayerCountError,
    RoleNotAvailableForPlayerCountError,
)


class ScenarioValidator:
    """Validates player counts and role selections against a scenario."""

    def validate_player_count(
        self, scenario: ScenarioDefinition, player_count: int
    ) -> None:
        """Ensure ``player_count`` is playable under ``scenario``.

        Raises:
            InvalidPlayerCountError: count is out of bounds or (for fixed
                scenarios) not one of the prescribed counts.
        """
        if not scenario.min_players <= player_count <= scenario.max_players:
            raise InvalidPlayerCountError(
                f"سناریوی «{scenario.name_fa}» فقط برای "
                f"{to_persian_digits(scenario.min_players)} تا "
                f"{to_persian_digits(scenario.max_players)} بازیکن است."
            )
        if scenario.is_fixed and player_count not in scenario.fixed_compositions:
            allowed = "، ".join(
                to_persian_digits(c) for c in scenario.allowed_counts()
            )
            raise InvalidPlayerCountError(
                f"سناریوی «{scenario.name_fa}» فقط برای {allowed} بازیکن قابل اجراست."
            )

    def ensure_role_selectable(
        self,
        scenario: ScenarioDefinition,
        role_code: RoleCode,
        player_count: int,
    ) -> None:
        """Ensure ``role_code`` may be picked for ``scenario`` at ``player_count``.

        Raises:
            InvalidGameStateError: role is not part of the scenario, or the
                scenario is fixed (no free selection).
            RoleNotAvailableForPlayerCountError: the role's catalog
                ``min_players`` exceeds ``player_count``.
        """
        if scenario.is_fixed:
            raise InvalidGameStateError(
                "در این سناریو ترکیب نقش‌ها از پیش تعیین‌شده است و قابل تغییر نیست."
            )
        if role_code not in scenario.allowed_roles:
            raise InvalidGameStateError("این نقش در سناریوی انتخابی موجود نیست.")

        from app.utils.role_catalog import ROLE_BY_CODE

        defn = ROLE_BY_CODE.get(role_code)
        if defn is not None and defn.min_players is not None:
            if player_count < defn.min_players:
                raise RoleNotAvailableForPlayerCountError(
                    f"نقش «{defn.name_fa}» فقط برای بازی‌های حداقل "
                    f"{to_persian_digits(defn.min_players)} نفره مجاز است."
                )

    def validate_selection_size(
        self,
        scenario: ScenarioDefinition,
        selected_codes: Sequence[RoleCode],
        player_count: int,
    ) -> None:
        """Ensure the number of selected roles does not exceed ``player_count``."""
        if scenario.is_fixed:
            raise InvalidGameStateError(
                "در این سناریو انتخاب نقش وجود ندارد؛ ترکیب ثابت است."
            )
        if len(selected_codes) > player_count:
            raise InvalidGameStateError(
                "تعداد نقش‌های انتخاب‌شده نمی‌تواند از تعداد بازیکنان بیشتر باشد."
            )

    def is_role_selectable(
        self,
        scenario: ScenarioDefinition,
        role_code: RoleCode,
        player_count: int,
    ) -> bool:
        """Non-raising variant of :meth:`ensure_role_selectable` for the UI."""
        try:
            self.ensure_role_selectable(scenario, role_code, player_count)
        except (InvalidGameStateError, RoleNotAvailableForPlayerCountError):
            return False
        return True
