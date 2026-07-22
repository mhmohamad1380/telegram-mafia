"""BotOwnerTestFlowService: end-to-end self-test of the real game pipeline.

Lets the bot owner exercise a *complete* game — creation, scenario setup, player
joins, role assignment, and game start — without needing real players, by
driving the very same services a live game uses:

* :class:`GameService`             — create / configure / start
* :class:`ScenarioService`         — resolve the role composition
* :class:`LobbyService`            — the real join path
* :class:`AutoRoleAssignmentService` — instant role assignment on join
* :class:`FakeUserService`         — synthetic "Test User" participants

The flow runs in :class:`~app.models.enums.RoleMode.AUTO_ROLE_ASSIGNMENT` mode so
every joiner (owner first, then the fakes) receives a seat number and a random,
unique role the moment they join — mirroring the auto feature. Each step is
guarded so any failure is captured and surfaced in a structured
:class:`~app.schemas.game.TestFlowReportDTO` (with the failing step and error),
rather than crashing the handler.

No fake shortcut path exists: the only difference from a real game is *who* the
players are (synthetic ids) and that assignment is automatic — both real product
features. This keeps the test faithful to production behaviour.
"""

from __future__ import annotations

from app.config.logging import get_logger
from app.models.enums import GameStatus, RoleMode, RoleTeam
from app.repositories import RepositoryProvider
from app.schemas.game import TestFlowReportDTO, TestStepResultDTO
from app.services.auto_role_assignment_service import AutoRoleAssignmentService
from app.services.fake_user_service import FakeUserService
from app.services.game_service import GameService
from app.services.lobby_service import LobbyService
from app.services.scenario_service import ScenarioService
from app.utils.exceptions import DomainError

logger = get_logger(__name__)

DEFAULT_TEST_PLAYER_COUNT = 8
DEFAULT_TEST_SCENARIO = "classic"


class _StepFailure(Exception):
    """Internal signal that a test step failed (carries a human message)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BotOwnerTestFlowService:
    """Orchestrates a full, real-pipeline game for the owner and reports on it."""

    def __init__(
        self,
        repos: RepositoryProvider,
        *,
        games: GameService,
        scenarios: ScenarioService,
        lobby: LobbyService,
        auto_assignment: AutoRoleAssignmentService,
        fake_users: FakeUserService,
    ) -> None:
        self._repos = repos
        self._games = games
        self._scenarios = scenarios
        self._lobby = lobby
        self._auto = auto_assignment
        self._fake_users = fake_users

    async def run_full_test(
        self,
        *,
        owner_id: int,
        player_count: int = DEFAULT_TEST_PLAYER_COUNT,
        scenario_code: str = DEFAULT_TEST_SCENARIO,
        owner_display_name: str | None = None,
    ) -> TestFlowReportDTO:
        """Run the full owner test flow and return a structured report.

        The owner is the game creator *and* the first player. ``player_count - 1``
        synthetic users fill the remaining seats. Every join auto-assigns a
        unique role. Steps: creation → scenario setup → auto join → role
        selection → role sync → game start. The first failing step short-circuits
        the run; everything is reported.
        """
        steps: list[TestStepResultDTO] = []
        game_id: int | None = None
        game_code: str | None = None
        citizen = mafia = independent = 0

        def record(key: str, label: str, detail: str | None = None) -> None:
            steps.append(
                TestStepResultDTO(key=key, label=label, ok=True, detail=detail)
            )

        try:
            # --- Step 1: create the game (AUTO role mode) -------------------
            await self._fake_users.get_or_create_owner(
                owner_id=owner_id, display_name=owner_display_name
            )
            try:
                scenario = self._scenarios.get_scenario(scenario_code)
                self._scenarios.validate_player_count(scenario, player_count)
                game = await self._games.create_game(
                    creator_telegram_id=owner_id,
                    player_count=player_count,
                    scenario_code=scenario_code,
                    role_mode=RoleMode.AUTO_ROLE_ASSIGNMENT,
                )
            except DomainError as exc:
                raise _StepFailure(exc.message_fa) from exc
            game_id = game.id
            game_code = game.code
            record("game_creation", "Game Creation", f"code={game.code}")

            # --- Step 2: resolve + persist the scenario's role composition --
            try:
                resolved = await self._scenarios.resolve(
                    scenario=scenario,
                    player_count=player_count,
                )
                await self._games.configure_roles(
                    game_id=game.id,
                    creator_telegram_id=owner_id,
                    role_quantities=resolved.role_quantities,
                    custom_role_quantities=resolved.custom_role_quantities,
                )
            except DomainError as exc:
                raise _StepFailure(exc.message_fa) from exc
            record("scenario_setup", "Scenario Setup", f"scenario={scenario_code}")

            # --- Step 3: auto-join owner + synthetic users ------------------
            fakes = await self._fake_users.ensure_fake_users(player_count - 1)
            participant_ids = [owner_id] + [f.user_id for f in fakes]
            reveals: dict[int, str] = {}
            try:
                for uid in participant_ids:
                    await self._lobby.join_game(code=game.code, user_id=uid)
                    role = await self._auto.assign_for_player(
                        game_id=game.id, user_id=uid
                    )
                    reveals[uid] = role.name_fa
            except DomainError as exc:
                raise _StepFailure(exc.message_fa) from exc
            record(
                "auto_join",
                "Auto Join Users",
                f"{len(participant_ids)} players joined",
            )

            # --- Step 4: verify every player received a role ----------------
            assigned = await self._repos.players.count_assigned(game.id)
            active = await self._repos.players.count_active(game.id)
            if not (assigned == active == player_count):
                raise _StepFailure(
                    f"assigned={assigned}, active={active}, "
                    f"expected={player_count}"
                )
            record("role_selection", "Role Selection", f"{assigned} roles assigned")

            # --- Step 5: verify roles + seats are unique / pool exhausted ---
            await self._verify_uniqueness(game_id=game.id, player_count=player_count)
            record("role_sync", "Role Sync", "roles & seats unique")

            # --- Compute team composition for the report --------------------
            citizen, mafia, independent = await self._composition_counts(game.id)

            # --- Step 6: start the game -------------------------------------
            try:
                started = await self._games.start_game(
                    game_id=game.id, creator_telegram_id=owner_id
                )
            except DomainError as exc:
                raise _StepFailure(exc.message_fa) from exc
            if started.status != GameStatus.IN_PROGRESS:
                raise _StepFailure(f"unexpected status {started.status.value}")
            record("game_start", "Game Start", "status=IN_PROGRESS")

        except _StepFailure as failure:
            # Mark the *next* (i.e. current) step as failed for the report.
            failed_label = self._next_step_label(steps)
            steps.append(
                TestStepResultDTO(
                    key="failed",
                    label=failed_label,
                    ok=False,
                    detail=failure.message,
                )
            )
            logger.warning(
                "owner_test_flow_failed",
                owner_id=owner_id,
                step=failed_label,
                error=failure.message,
            )
            return TestFlowReportDTO(
                success=False,
                steps=steps,
                game_code=game_code,
                game_id=game_id,
                player_count=player_count,
                scenario_code=scenario_code,
                failed_step=failed_label,
                error=failure.message,
            )
        except Exception as exc:  # noqa: BLE001 - report unexpected errors too
            failed_label = self._next_step_label(steps)
            steps.append(
                TestStepResultDTO(
                    key="failed",
                    label=failed_label,
                    ok=False,
                    detail=str(exc),
                )
            )
            logger.exception("owner_test_flow_crashed", owner_id=owner_id)
            return TestFlowReportDTO(
                success=False,
                steps=steps,
                game_code=game_code,
                game_id=game_id,
                player_count=player_count,
                scenario_code=scenario_code,
                failed_step=failed_label,
                error=str(exc),
            )

        logger.info(
            "owner_test_flow_succeeded",
            owner_id=owner_id,
            game_id=game_id,
            player_count=player_count,
        )
        return TestFlowReportDTO(
            success=True,
            steps=steps,
            game_code=game_code,
            game_id=game_id,
            player_count=player_count,
            scenario_code=scenario_code,
            citizen_count=citizen,
            mafia_count=mafia,
            independent_count=independent,
        )

    # --- Verification helpers ----------------------------------------------

    async def _verify_uniqueness(self, *, game_id: int, player_count: int) -> None:
        """Assert seat numbers and roles were handed out uniquely and fully."""
        taken = await self._repos.players.taken_numbers(game_id)
        if len(taken) != player_count or len(set(taken)) != player_count:
            raise _StepFailure(
                f"duplicate/short seats: {taken}"
            )
        remaining = await self._repos.game_roles.total_remaining(game_id)
        if remaining != 0:
            raise _StepFailure(f"role pool not exhausted (remaining={remaining})")

    async def _composition_counts(self, game_id: int) -> tuple[int, int, int]:
        """Return (citizen, mafia, independent) head counts for the game.

        ``MASON`` is counted on the city side (they win with the city).
        """
        citizen = mafia = independent = 0
        for gr in await self._repos.game_roles.list_for_game(game_id):
            qty = gr.quantity
            if gr.team == RoleTeam.MAFIA:
                mafia += qty
            elif gr.team == RoleTeam.INDEPENDENT:
                independent += qty
            else:  # CITIZEN or MASON
                citizen += qty
        return citizen, mafia, independent

    @staticmethod
    def _next_step_label(steps: list[TestStepResultDTO]) -> str:
        """Return the label of the step that was in progress when a failure hit."""
        order = [
            ("game_creation", "Game Creation"),
            ("scenario_setup", "Scenario Setup"),
            ("auto_join", "Auto Join Users"),
            ("role_selection", "Role Selection"),
            ("role_sync", "Role Sync"),
            ("game_start", "Game Start"),
        ]
        done = {s.key for s in steps if s.ok}
        for key, label in order:
            if key not in done:
                return label
        return "Unknown"
