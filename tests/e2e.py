"""End-to-End test runner for the Mafia bot.

Runs the full, error-collecting QA suite against a **real** PostgreSQL + Redis
(exactly as the running bot would use them) and prints a single, section-grouped
report at the end. The suite never halts on the first failure — every check is
recorded and rendered together with its location, cause, exception, suggested
fix, and traceback.

Usage
-----
Inside the app container (recommended, so all deps + env are present)::

    docker compose run --rm bot python -m tests.e2e

or, with the DB/Redis reachable via the ambient environment::

    python -m tests.e2e

Exit code is ``0`` when every check passes, ``1`` otherwise — suitable as a CI /
release gate.
"""

from __future__ import annotations

import asyncio
import sys
import traceback

from tests import sections as S
from tests.harness import AppContext
from tests.reporter import Reporter

#: The ordered list of section coroutines, matching the report layout. Each is
#: an ``async def section_*(ctx, reporter)`` that records its own checks.
SECTIONS = [
    # Infrastructure first — everything else depends on these.
    S.section_database,
    S.section_redis,
    S.section_telegram_api,
    # Presentation surfaces.
    S.section_startup,
    S.section_main_menu,
    # Create-game wizard.
    S.section_scenarios,
    S.section_player_count,
    S.section_role_selection,
    S.section_auto_completion,
    S.section_game_creation,
    # Lobby + turn-based flow.
    S.section_player_join,
    S.section_turn_flow,
    S.section_start_game,
    # Management + info surfaces.
    S.section_custom_roles,
    S.section_my_games,
    S.section_role_description,
    S.section_delete_game,
    # FSM + keyboards.
    S.section_cancel,
    S.section_fsm_states,
    S.section_all_buttons,
    S.section_all_callbacks,
    S.section_inline_keyboards,
    # Live lobby sync (push-based screen updates).
    S.section_live_sync,
    # Auto role-assignment mode + owner self-test flow.
    S.section_auto_assignment,
    S.section_owner_test_flow,
    # Hardest last.
    S.section_concurrency,

]



async def _run() -> int:
    reporter = Reporter()
    ctx = AppContext()

    # Clean any leftovers from a previous run so the suite is deterministic.
    try:
        await ctx.startup()
        await ctx.cleanup_fake_data()
    except Exception as exc:  # noqa: BLE001
        reporter.section("bootstrap", "Bootstrap")
        reporter.guard(
            "Suite bootstrap (seed + cleanup)", exc,
            suggestion="Are DB and Redis up? Have migrations been applied "
                       "(alembic upgrade head)?",
        )
        print(reporter.render())
        await ctx.shutdown()
        return 1

    # Each section is fully isolated: a crash in one is recorded and the suite
    # moves on to the next, so one broken area never masks the rest.
    for section in SECTIONS:
        try:
            await section(ctx, reporter)
        except Exception as exc:  # noqa: BLE001 - defensive; sections self-guard
            reporter.guard(
                f"Section crashed: {section.__name__}", exc,
                suggestion="A section raised outside its own guards; inspect "
                           "the traceback below.",
            )
            # Ensure a traceback is visible even for this unexpected path.
            traceback.print_exc()

    # Best-effort cleanup so repeated local runs stay clean.
    try:
        await ctx.cleanup_fake_data()
    except Exception:  # noqa: BLE001
        pass
    finally:
        await ctx.shutdown()

    print(reporter.render())
    return 0 if reporter.ok else 1


def main() -> None:
    exit_code = asyncio.run(_run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
