"""Scenario encyclopaedia ("📚 سناریوها").

A read-only browser over the scenario catalog: an index of all scenarios plus a
paginated per-scenario overview (description, player bounds, standard ratio, win
conditions, night wake order, special rules, and — for fixed scenarios — the
prescribed composition). Purely informational; it never touches game state.

Navigation is driven by :class:`ScenarioInfoCB` and the keyboards in
:mod:`app.bot.keyboards.scenario`.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.bot.callbacks import ScenarioInfoCB
from app.bot.keyboards import (
    build_main_menu_keyboard,
    build_scenario_index_keyboard,
    build_scenario_page_keyboard,
)
from app.bot.keyboards.reply import BTN_SCENARIOS
from app.scenarios import format_scenario_composition, format_scenario_overview
from app.services import ServiceProvider

router = Router(name="scenario_info")


async def _show_index(message: Message, services: ServiceProvider, *, edit: bool) -> None:
    scenarios = services.scenarios.list_scenarios()
    markup = build_scenario_index_keyboard(scenarios)
    if edit:
        await message.edit_text(texts.SCENARIOS_INTRO, reply_markup=markup)
    else:
        await message.answer(texts.SCENARIOS_INTRO, reply_markup=markup)


@router.message(F.text == BTN_SCENARIOS)
async def on_menu_scenarios(message: Message, services: ServiceProvider) -> None:
    """Main-menu «📚 سناریوها» button — open the scenario index."""
    await _show_index(message, services, edit=False)


def _render_page(services: ServiceProvider, index: int) -> str:
    scenario = services.scenarios.get_scenario_by_index(index)
    body = format_scenario_overview(scenario)
    # For fixed scenarios, append the prescribed composition of the smallest count.
    if scenario.is_fixed:
        counts = scenario.allowed_counts()
        if counts:
            note = format_scenario_composition(scenario, counts[0])
            if note:
                body = f"{body}\n\n{note}"
    return body


@router.callback_query(ScenarioInfoCB.filter(F.action == "list"))
async def on_scenario_list(
    callback: CallbackQuery, services: ServiceProvider
) -> None:
    """Show the full scenario index."""
    await _show_index(callback.message, services, edit=True)  # type: ignore[arg-type]
    await callback.answer()


@router.callback_query(ScenarioInfoCB.filter(F.action == "show"))
async def on_scenario_show(
    callback: CallbackQuery,
    callback_data: ScenarioInfoCB,
    services: ServiceProvider,
) -> None:
    """Show a single scenario's overview page with prev/next navigation."""
    total = len(services.scenarios.list_scenarios())
    index = callback_data.index % total
    await callback.message.edit_text(  # type: ignore[union-attr]
        _render_page(services, index),
        reply_markup=build_scenario_page_keyboard(index=index, total=total),
    )
    await callback.answer()


@router.callback_query(ScenarioInfoCB.filter(F.action == "home"))
async def on_scenario_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Dismiss the encyclopaedia and return to the main menu."""
    await callback.message.delete()  # type: ignore[union-attr]
    await callback.message.answer(  # type: ignore[union-attr]
        texts.START, reply_markup=build_main_menu_keyboard()
    )
    await callback.answer()
