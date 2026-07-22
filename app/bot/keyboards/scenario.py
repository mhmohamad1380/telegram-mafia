"""Inline keyboards for scenario selection (wizard) and the encyclopaedia.

Kept separate from :mod:`app.bot.keyboards.game` so the scenario feature is
self-contained. All builders take plain :class:`ScenarioDefinition` data and use
the typed callbacks :class:`ScenarioPickCB` / :class:`ScenarioInfoCB`.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import ScenarioInfoCB, ScenarioPickCB
from app.scenarios import ScenarioDefinition
from app.utils.codes import to_persian_digits


def build_scenario_picker_keyboard(
    scenarios: Sequence[ScenarioDefinition],
) -> InlineKeyboardMarkup:
    """Grid of scenarios to pick as the game mode (create-game step 1)."""
    builder = InlineKeyboardBuilder()
    for scenario in scenarios:
        builder.button(
            text=scenario.name_fa,
            callback_data=ScenarioPickCB(code=scenario.code),
        )
    builder.adjust(2)
    return builder.as_markup()


def build_scenario_overview_keyboard(scenario: ScenarioDefinition) -> InlineKeyboardMarkup:
    """Confirm/back buttons shown under a scenario's overview in the wizard.

    Confirming re-picks the same scenario (advancing to player-count); back
    returns to the picker grid.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ ادامه با این سناریو",
        callback_data=ScenarioPickCB(code=scenario.code),
    )
    builder.button(
        text="↩️ انتخاب سناریوی دیگر",
        callback_data=ScenarioPickCB(code="__back__"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_scenario_count_keyboard(
    scenario: ScenarioDefinition,
) -> InlineKeyboardMarkup:
    """Quick-pick player counts valid for ``scenario`` (create-game step 2).

    Flexible scenarios show their ``suggested_counts`` (clamped to bounds);
    fixed scenarios show exactly their prescribed counts.
    """
    builder = InlineKeyboardBuilder()
    if scenario.is_fixed:
        counts: tuple[int, ...] = tuple(scenario.allowed_counts())
    else:
        suggested = [
            c
            for c in scenario.suggested_counts
            if scenario.min_players <= c <= scenario.max_players
        ]
        counts = tuple(suggested) or (scenario.min_players,)
    from app.bot.callbacks import PlayerCountCB

    for count in counts:
        builder.button(
            text=to_persian_digits(count),
            callback_data=PlayerCountCB(count=count),
        )
    builder.adjust(min(len(counts), 5) or 1)
    return builder.as_markup()


# --- Encyclopaedia ----------------------------------------------------------


def build_scenario_index_keyboard(
    scenarios: Sequence[ScenarioDefinition],
) -> InlineKeyboardMarkup:
    """Grid of all scenarios for the "📚 سناریوها" encyclopaedia index."""
    builder = InlineKeyboardBuilder()
    for i, scenario in enumerate(scenarios):
        builder.button(
            text=scenario.name_fa,
            callback_data=ScenarioInfoCB(action="show", index=i),
        )
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="🏠 بازگشت",
            callback_data=ScenarioInfoCB(action="home").pack(),
        )
    )
    return builder.as_markup()


def build_scenario_page_keyboard(
    *, index: int, total: int
) -> InlineKeyboardMarkup:
    """Prev/next navigation for a single scenario page in the encyclopaedia."""
    builder = InlineKeyboardBuilder()
    prev_index = (index - 1) % total
    next_index = (index + 1) % total
    builder.row(
        InlineKeyboardButton(
            text="◀️ قبلی",
            callback_data=ScenarioInfoCB(action="show", index=prev_index).pack(),
        ),
        InlineKeyboardButton(
            text=f"{to_persian_digits(index + 1)}/{to_persian_digits(total)}",
            callback_data=ScenarioInfoCB(action="list").pack(),
        ),
        InlineKeyboardButton(
            text="بعدی ▶️",
            callback_data=ScenarioInfoCB(action="show", index=next_index).pack(),
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📑 فهرست سناریوها",
            callback_data=ScenarioInfoCB(action="list").pack(),
        ),
        InlineKeyboardButton(
            text="🏠 بازگشت",
            callback_data=ScenarioInfoCB(action="home").pack(),
        ),
    )
    return builder.as_markup()
