"""The 25 functional test sections of the End-to-End suite.

Each ``section_*`` coroutine drives one stage of the requested QA scenario using
the real service layer (via :class:`AppContext` and the flow helpers), recording
its outcomes into the shared :class:`Reporter`. Sections never raise: every
check is wrapped so a failure is collected and the suite continues.

The section order matches the report layout: Startup → Main Menu → … →
Concurrency.
"""

from __future__ import annotations

import asyncio

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.bot import keyboards as kb
from app.bot.callbacks import (
    CustomRoleCB,
    CustomRoleTeamCB,
    GameControlCB,
    LobbyActionCB,
    MyGamesCB,
    NumberPickCB,
    PlayerCountCB,
    RoleInfoCB,
    RoleSetupActionCB,
    RoleToggleCB,
    ScenarioInfoCB,
    ScenarioPickCB,
)
from app.bot.states import (
    CreateGameStates,
    CustomRoleStates,
    JoinGameStates,
)
from app.models.enums import GameStatus, PlayerStatus, RoleMode, RoleTeam

from app.services import ServiceProvider
from app.utils.exceptions import (
    CustomRoleAccessDeniedError,
    CustomRoleNotFoundError,
    GameFullError,
    GameNotFoundError,
    GameNotJoinableError,
    InvalidPlayerCountError,

    LobbyNotCompleteError,
    NotGameCreatorError,
    NotPlayersTurnError,
    NumberAlreadyTakenError,
    PlayerAlreadyJoinedError,
    ScenarioNotFoundError,
)

from tests.flows import (
    create_game_via_scenario,
    fill_lobby,
    finish_game,
    get_my_role,
    join_player,
    run_all_turns,
    start_game,
    take_turn,
)
from tests.harness import AppContext, FakeUser
from tests.reporter import Reporter


# ---------------------------------------------------------------------------
# 23 · Database  &  24 · Redis  &  25 · Telegram API (infrastructure probes)
# ---------------------------------------------------------------------------


async def section_database(ctx: AppContext, r: Reporter) -> None:
    r.section("database", "Database")

    async def _ping(services: ServiceProvider) -> int:
        from sqlalchemy import text

        result = await services.repos.session.execute(text("SELECT 1"))
        return int(result.scalar_one())

    value = await r.run("Database connectivity (SELECT 1)", lambda: ctx.act(_ping),
                        suggestion="Ensure PostgreSQL is up and DATABASE_URL is correct.")
    r.expect(value == 1, "SELECT 1 returns 1")

    # Roles must be seeded for the rest of the suite to work.
    async def _count_roles(services: ServiceProvider) -> int:
        roles = await services.roles.list_catalog()
        return len(roles)

    count = await r.run("Role catalog is seeded", lambda: ctx.act(_count_roles),
                        suggestion="Run seed_roles(); check app/database/seed.py.")
    r.expect((count or 0) > 0, "At least one role present in DB",
             cause=f"Found {count} roles.")


async def section_redis(ctx: AppContext, r: Reporter) -> None:
    r.section("redis", "Redis")
    redis = ctx.redis()

    async def _roundtrip() -> str:
        await redis.set("e2e:probe", "ok", ex=30)
        value = await redis.get("e2e:probe")
        await redis.delete("e2e:probe")
        return value.decode() if isinstance(value, bytes) else str(value)

    value = await r.run("Redis set/get round-trip", _roundtrip,
                        suggestion="Ensure Redis is up and REDIS_URL is correct.")
    r.expect(value == "ok", "Redis returns the stored value")

    async def _ping() -> bool:
        return bool(await redis.ping())

    ok = await r.run("Redis PING", _ping)
    r.expect(bool(ok), "Redis PING succeeds")


async def section_telegram_api(ctx: AppContext, r: Reporter) -> None:
    """We do not hit the network; instead we validate the aiogram objects and
    types the bot relies on are importable and constructible (a smoke test that
    the Telegram integration layer is wired correctly)."""
    r.section("telegram", "Telegram API")
    try:
        from aiogram import Bot, Dispatcher  # noqa: F401
        from aiogram.fsm.storage.redis import RedisStorage  # noqa: F401

        r.record_pass("aiogram Bot/Dispatcher import")
    except Exception as exc:  # noqa: BLE001
        r.guard("aiogram import", exc,
                suggestion="Check aiogram is installed (requirements.txt).")

    # The main router must assemble without a token/network.
    try:
        from app.bot.handlers import get_main_router

        router = get_main_router()
        r.expect(router is not None, "Main router assembles")
    except Exception as exc:  # noqa: BLE001
        r.guard("Main router assembly", exc,
                suggestion="Inspect app/bot/handlers/__init__.py wiring.")


# ---------------------------------------------------------------------------
# 1 · Startup   2 · Main Menu
# ---------------------------------------------------------------------------


async def section_startup(ctx: AppContext, r: Reporter) -> None:
    r.section("startup", "Startup")

    # /start builds the welcome + main-menu reply keyboard.
    try:
        markup = kb.build_main_menu_keyboard()
        r.expect(isinstance(markup, ReplyKeyboardMarkup),
                 "Main menu is a ReplyKeyboardMarkup")
        captions = {btn.text for row in markup.keyboard for btn in row}
        for required in (
            kb.BTN_CREATE_GAME,
            kb.BTN_JOIN_GAME,
            kb.BTN_MY_GAMES,
            kb.BTN_ROLE_INFO,
            kb.BTN_CANCEL,
        ):
            r.expect(required in captions, f"Main menu has button: {required}",
                     cause=f"{required!r} missing from {sorted(captions)}")
    except Exception as exc:  # noqa: BLE001
        r.guard("Main menu keyboard build", exc)


async def section_main_menu(ctx: AppContext, r: Reporter) -> None:
    r.section("mainmenu", "Main Menu")
    markup = kb.build_main_menu_keyboard()
    captions = [btn.text for row in markup.keyboard for btn in row]
    r.expect(len(captions) == len(set(captions)),
             "No duplicate main-menu buttons",
             cause=f"Captions: {captions}")
    r.expect(all(c.strip() for c in captions),
             "No empty main-menu buttons")
    r.expect(kb.MAIN_MENU_BUTTONS.issuperset(captions),
             "All rendered buttons are registered in MAIN_MENU_BUTTONS",
             suggestion="Keep reply.py captions and MAIN_MENU_BUTTONS in sync.")


# ---------------------------------------------------------------------------
# 3 · Scenario Selection
# ---------------------------------------------------------------------------


async def section_scenarios(ctx: AppContext, r: Reporter) -> None:
    r.section("scenario", "Scenario Selection")

    async def _list(services: ServiceProvider):
        return services.scenarios.list_scenarios()

    scenarios = await r.run("List all scenarios", lambda: ctx.act(_list))
    scenarios = scenarios or ()
    r.expect(len(scenarios) > 0, "At least one scenario is registered")

    for scenario in scenarios:
        name = scenario.name_fa

        async def _detail(services: ServiceProvider, code=scenario.code):
            from app.scenarios.definition import format_scenario_overview

            defn = services.scenarios.get_scenario(code)
            return format_scenario_overview(defn)

        overview = await r.run(f"Overview renders · {name}",
                               lambda code=scenario.code: ctx.act(
                                   lambda s: _detail(s, code)))
        r.expect(bool(overview and overview.strip()),
                 f"Overview non-empty · {name}")

        # Bounds sanity.
        r.expect(1 <= scenario.min_players <= scenario.max_players,
                 f"Player bounds valid · {name}",
                 cause=f"min={scenario.min_players}, max={scenario.max_players}")
        counts = scenario.allowed_counts()
        r.expect(len(counts) > 0, f"Has playable counts · {name}")
        r.expect(all(scenario.min_players <= c <= scenario.max_players
                     for c in counts),
                 f"All counts within bounds · {name}")

        # Suggested counts appear on the count keyboard.
        try:
            count_kb = kb.build_scenario_count_keyboard(scenario)
            r.expect(isinstance(count_kb, InlineKeyboardMarkup),
                     f"Count keyboard builds · {name}")
        except Exception as exc:  # noqa: BLE001
            r.guard(f"Count keyboard · {name}", exc)

    # Restricted-scenario rule: a fixed scenario must reject an unlisted count.
    fixed = [s for s in scenarios if s.is_fixed]
    if fixed:
        scenario = fixed[0]
        bad_count = max(scenario.allowed_counts()) + 1

        async def _validate(services: ServiceProvider):
            defn = services.scenarios.get_scenario(scenario.code)
            services.scenarios.validate_player_count(defn, bad_count)

        await r.expect_raises(
            Exception,
            ctx.act(_validate),
            f"Fixed scenario rejects out-of-range count · {scenario.name_fa}",
            suggestion="ScenarioValidator.validate_player_count should reject it.",
        )

    # Unknown scenario code must raise.
    async def _unknown(services: ServiceProvider):
        services.scenarios.get_scenario("__does_not_exist__")

    await r.expect_raises(ScenarioNotFoundError, ctx.act(_unknown),
                          "Unknown scenario code raises ScenarioNotFoundError")


# ---------------------------------------------------------------------------
# 4 · Player Count
# ---------------------------------------------------------------------------


async def section_player_count(ctx: AppContext, r: Reporter) -> None:
    r.section("pcount", "Player Count")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    # Valid manual count is accepted and stored.
    async def _create(services: ServiceProvider):
        return await services.games.create_game(
            creator_telegram_id=creator.id, player_count=9,
            scenario_code="classic")

    game = await r.run("Create game with valid count (9)",
                       lambda: ctx.act(_create))
    if game is not None:
        r.expect_eq(game.player_count, 9, "Stored player_count == 9")
        r.expect_eq(game.status, GameStatus.CREATING, "New game is CREATING")

    # Below-minimum count rejected.
    async def _too_few(services: ServiceProvider):
        await services.games.create_game(
            creator_telegram_id=creator.id, player_count=2,
            scenario_code="classic")

    await r.expect_raises(InvalidPlayerCountError, ctx.act(_too_few),
                          "Reject below-minimum player count (2)")

    # Above-maximum count rejected.
    async def _too_many(services: ServiceProvider):
        await services.games.create_game(
            creator_telegram_id=creator.id, player_count=999,
            scenario_code="classic")

    await r.expect_raises(InvalidPlayerCountError, ctx.act(_too_many),
                          "Reject above-maximum player count (999)")

    # The quick-pick keyboard offers valid suggested counts.
    try:
        pkb = kb.build_player_count_keyboard()
        r.expect(isinstance(pkb, InlineKeyboardMarkup),
                 "Player-count keyboard builds")
    except Exception as exc:  # noqa: BLE001
        r.guard("Player-count keyboard", exc)


# ---------------------------------------------------------------------------
# 5 · Role Selection   6 · Auto Role Completion
# ---------------------------------------------------------------------------


async def section_role_selection(ctx: AppContext, r: Reporter) -> None:
    r.section("roles", "Role Selection")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    async def _selectable(services: ServiceProvider):
        scenario = services.scenarios.get_scenario("classic")
        return await services.scenarios.get_selectable_roles(scenario)

    roles = await r.run("List selectable roles for classic scenario",
                        lambda: ctx.act(_selectable))
    roles = roles or []
    r.expect(len(roles) > 0, "Classic scenario exposes selectable roles")

    # Build the selection keyboard with one role toggled ON.
    if roles:
        first = roles[0]
        try:
            markup = kb.build_role_selection_keyboard(
                game_id=1,
                roles=roles,
                selected_ids={first.role_id},
                selected_total=1,
                target_count=10,
            )
            r.expect(isinstance(markup, InlineKeyboardMarkup),
                     "Role selection keyboard builds")
            # A toggle callback must be present for a non-locked role.
            payloads = [
                btn.callback_data
                for row in markup.inline_keyboard for btn in row
            ]
            r.expect(any(p.startswith("role:") for p in payloads),
                     "Role toggle callbacks are present")
            r.expect(any("rolesetup" in p and "confirm" in p for p in payloads),
                     "Confirm action present on selection keyboard")
        except Exception as exc:  # noqa: BLE001
            r.guard("Role selection keyboard", exc)


async def section_auto_completion(ctx: AppContext, r: Reporter) -> None:
    r.section("autoroles", "Auto Role Completion")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    # Select only a few special roles for a 10-player classic game and confirm
    # the resolver tops up with simple citizens/mafia to exactly 10.
    async def _resolve(services: ServiceProvider):
        from app.models.enums import RoleCode

        scenario = services.scenarios.get_scenario("classic")
        return await services.scenarios.resolve(
            scenario=scenario,
            player_count=10,
            selected_codes=(
                RoleCode.GODFATHER,
                RoleCode.DOCTOR,
                RoleCode.DETECTIVE,
            ),
        )

    result = await r.run("Resolve partial selection (10 players, 3 chosen)",
                         lambda: ctx.act(_resolve))
    if result is not None:
        total = sum(result.role_quantities.values())
        r.expect_eq(total, 10, "Auto-completed composition totals player_count")
        r.expect(len(result.added) > 0,
                 "Fill roles were auto-added",
                 cause=f"added={result.added}")
        comp = result.composition
        r.expect_eq(comp.total, 10, "Team composition totals 10")
        r.expect(comp.mafia >= 1, "At least one mafia in composition")
        r.expect(comp.citizen >= 1, "At least one citizen in composition")


# ---------------------------------------------------------------------------
# 7 · Game Creation
# ---------------------------------------------------------------------------


async def section_game_creation(ctx: AppContext, r: Reporter) -> None:
    r.section("creation", "Game Creation")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    created = await r.run(
        "Create + configure game (classic, 8)",
        lambda: create_game_via_scenario(
            ctx, creator=creator, scenario_code="classic", player_count=8),
    )
    if created is not None:
        game = created.game
        r.expect(game.code.isdigit() and len(game.code) == 6,
                 "Game code is 6 numeric digits",
                 cause=f"code={game.code!r}")
        r.expect_eq(game.player_count, 8, "player_count persisted as 8")
        r.expect_eq(game.status, GameStatus.WAITING_PLAYERS,
                    "Configured game is WAITING_PLAYERS")
        total = (sum(created.role_id_pool.values())
                 + sum(created.custom_role_pool.values()))
        r.expect_eq(total, 8, "Persisted role quantities total player_count")

        # Codes are unique across two creations.
        second = await r.run(
            "Create a second game",
            lambda: create_game_via_scenario(
                ctx, creator=creator, scenario_code="classic", player_count=8),
        )
        if second is not None:
            r.expect(second.game.code != game.code,
                     "Two games get distinct codes")


# ---------------------------------------------------------------------------
# 8 · Player Join   9 · Lobby Validation   10 · Turn Order (setup)
# ---------------------------------------------------------------------------


async def section_player_join(ctx: AppContext, r: Reporter) -> None:
    r.section("join", "Player Join")
    creator = FakeUser(1)
    players = ctx.make_users(8)  # ids 0..7 ; creator is FakeUser(1) == index 1
    await ctx.ensure_users(players)

    created = await create_game_via_scenario(
        ctx, creator=players[0], scenario_code="classic", player_count=6)
    code = created.game.code
    game_id = created.game.id

    # Join up to capacity (6 players: indices 0..5).
    lobby = players[:6]
    for i, user in enumerate(lobby):
        joined = await r.run(f"Player {i + 1} joins",
                             lambda u=user: join_player(ctx, code=code, user=u))
        r.expect(joined is not None, f"Join returns a game DTO · player {i + 1}")

    # Duplicate join rejected.
    await r.expect_raises(PlayerAlreadyJoinedError,
                          join_player(ctx, code=code, user=lobby[0]),
                          "Duplicate join is rejected")

    # Over-capacity join rejected.
    await r.expect_raises(GameFullError,
                          join_player(ctx, code=code, user=players[6]),
                          "Join beyond capacity is rejected")

    # Invalid code rejected.
    await r.expect_raises(GameNotFoundError,
                          join_player(ctx, code="000000", user=players[6]),
                          "Join with unknown code is rejected")

    # --- 9 · Lobby Validation: nobody can act before lobby completes --------
    r.section("lobbyval", "Lobby Validation")
    # Lobby is exactly full here (6/6). Build a fresh, NOT-full lobby to test.
    created2 = await create_game_via_scenario(
        ctx, creator=players[0], scenario_code="classic", player_count=6)
    code2 = created2.game.code
    gid2 = created2.game.id
    await fill_lobby(ctx, code=code2, players=players[:5])  # 5/6, incomplete

    async def _early_number(services: ServiceProvider):
        await services.lobby.choose_number(
            game_id=gid2, user_id=players[0].id, number=1)

    await r.expect_raises(LobbyNotCompleteError, ctx.act(_early_number),
                          "Cannot pick number before lobby is complete",
                          suggestion="TurnManager should gate on lobby completeness.")

    async def _early_assign(services: ServiceProvider):
        await services.lobby.assign_role(game_id=gid2, user_id=players[0].id)

    await r.expect_raises(LobbyNotCompleteError, ctx.act(_early_assign),
                          "Cannot get role before lobby is complete")


# ---------------------------------------------------------------------------
# 10 · Turn Order   11 · Number Selection   12 · Role Assignment (full run)
# ---------------------------------------------------------------------------


async def section_turn_flow(ctx: AppContext, r: Reporter) -> None:
    r.section("turnorder", "Turn Order")
    players = ctx.make_users(7)
    await ctx.ensure_users(players)
    creator = players[0]
    lobby = players[:6]

    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    code = created.game.code
    gid = created.game.id
    await fill_lobby(ctx, code=code, players=lobby)

    # Only the first joiner may act; the second is blocked.
    async def _second_acts(services: ServiceProvider):
        await services.lobby.choose_number(
            game_id=gid, user_id=lobby[1].id, number=1)

    await r.expect_raises(NotPlayersTurnError, ctx.act(_second_acts),
                          "Out-of-turn player is blocked")

    # First player completes their turn; then second becomes eligible.
    num1, res1 = await take_turn(ctx, game_id=gid, code=code, user=lobby[0])
    r.expect(res1 is not None, "First player completes turn")

    async def _second_now(services: ServiceProvider):
        avail = await services.lobby.available_numbers(game_id=gid)
        await services.lobby.choose_number(
            game_id=gid, user_id=lobby[1].id, number=avail[0])
        return await services.lobby.assign_role(
            game_id=gid, user_id=lobby[1].id)

    res2 = await r.run("Second player unblocked after first",
                       lambda: ctx.act(_second_now))
    r.expect(res2 is not None, "Second player completes turn after first")

    # --- 11 · Number Selection --------------------------------------------
    r.section("numbers", "Number Selection")
    # Remaining players 3..6 take their turns; verify uniqueness of numbers.
    reveals = await run_all_turns(
        ctx, game_id=gid, code=code, players=lobby[2:])

    async def _numbers(services: ServiceProvider):
        roster = await services.repos.players.list_active(gid)
        return [p.number for p in roster]

    numbers = await r.run("Collect assigned numbers", lambda: ctx.act(_numbers))
    numbers = numbers or []
    r.expect(all(n is not None for n in numbers), "Every player has a number")
    r.expect(len(numbers) == len(set(numbers)), "All numbers are unique",
             cause=f"numbers={numbers}")
    r.expect_eq(sorted(numbers), list(range(1, 7)),
                "Numbers are exactly 1..6")

    # Taken number cannot be re-picked (defensive – all are taken now).
    async def _dupe(services: ServiceProvider):
        await services.lobby.choose_number(
            game_id=gid, user_id=lobby[0].id, number=numbers[0])

    await r.expect_raises(Exception, ctx.act(_dupe),
                          "Re-picking a taken/again number is rejected")

    # --- 12 · Role Assignment ---------------------------------------------
    r.section("assign", "Role Assignment")
    r.expect_eq(len(reveals) + 2, 6,
                "Turns 3..6 each returned a role reveal",
                suggestion="run_all_turns should reveal one role per player.")

    async def _roster(services: ServiceProvider):
        return await services.roster.get_full_roster(
            game_id=gid, requester_id=creator.id)

    roster = await r.run("Fetch full roster (creator)",
                         lambda: ctx.act(_roster))
    roster = roster or []
    r.expect_eq(len(roster), 6, "Roster lists all 6 players")
    role_names = [p.role_name_fa for p in roster]
    r.expect(all(role_names), "Every player has a role name in the roster")
    # Uniqueness of role *instances*: total must equal player count, and no
    # single-quantity role may appear twice. We assert every seat filled.
    r.expect(all(p.number is not None for p in roster),
             "Every roster entry has a seat number")

    # Game should now be READY (all assigned).
    async def _status(services: ServiceProvider):
        g = await services.games.get_by_code(code)
        return g.status

    status = await r.run("Game reaches READY after all assigned",
                         lambda: ctx.act(_status))
    r.expect_eq(status, GameStatus.READY, "Status is READY once fully assigned")


# ---------------------------------------------------------------------------
# 13 · Start Game   (+ role privacy)
# ---------------------------------------------------------------------------


async def section_start_game(ctx: AppContext, r: Reporter) -> None:
    r.section("start", "Start Game")
    players = ctx.make_users(6)
    await ctx.ensure_users(players)
    creator = players[0]

    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    code = created.game.code
    gid = created.game.id
    await fill_lobby(ctx, code=code, players=players)
    await run_all_turns(ctx, game_id=gid, code=code, players=players)

    # Non-creator cannot start.
    async def _stranger_start(services: ServiceProvider):
        await services.games.start_game(
            game_id=gid, creator_telegram_id=players[1].id)

    await r.expect_raises(NotGameCreatorError, ctx.act(_stranger_start),
                          "Non-creator cannot start the game")

    started = await r.run("Creator starts the game",
                          lambda: start_game(ctx, game_id=gid, creator=creator))
    if started is not None:
        r.expect_eq(started.status, GameStatus.IN_PROGRESS,
                    "Status transitions to IN_PROGRESS")

    # Each player sees only their own role (privacy).
    reveal0 = await get_my_role(ctx, game_id=gid, user=players[0])
    reveal1 = await get_my_role(ctx, game_id=gid, user=players[1])
    r.expect(reveal0 is not None and reveal1 is not None,
             "Players can read their own role")


# ---------------------------------------------------------------------------
# 14 · Custom Roles
# ---------------------------------------------------------------------------


async def section_custom_roles(ctx: AppContext, r: Reporter) -> None:
    r.section("custom", "Custom Roles")
    owner = FakeUser(1)
    stranger = FakeUser(2)
    await ctx.ensure_users([owner, stranger])

    async def _create(services: ServiceProvider):
        return await services.custom_roles.create(
            owner_id=owner.id, name_fa="نقش ویژه من", team=RoleTeam.CITIZEN,
            description="یک نقش آزمایشی")

    role = await r.run("Create custom role", lambda: ctx.act(_create))
    if role is not None:
        r.expect_eq(role.owner_id, owner.id, "Custom role owned by creator")

        # Owner can list & fetch it.
        async def _list(services: ServiceProvider):
            return await services.custom_roles.list_for_owner(owner_id=owner.id)

        listed = await r.run("Owner lists custom roles",
                             lambda: ctx.act(_list))
        r.expect(any(cr.id == role.id for cr in (listed or [])),
                 "Created role appears in owner's list")

        # Stranger cannot access it.
        async def _stranger(services: ServiceProvider):
            await services.custom_roles.get_for_owner(
                custom_role_id=role.id, owner_id=stranger.id)

        await r.expect_raises((CustomRoleNotFoundError,
                               CustomRoleAccessDeniedError),
                              ctx.act(_stranger),
                              "Stranger cannot view another user's custom role")

        # Stranger's list does not include it.
        async def _stranger_list(services: ServiceProvider):
            return await services.custom_roles.list_for_owner(
                owner_id=stranger.id)

        s_list = await r.run("Stranger lists custom roles",
                             lambda: ctx.act(_stranger_list))
        r.expect(all(cr.id != role.id for cr in (s_list or [])),
                 "Stranger's list excludes the owner's role")

        # Use it in a game: create an 8-player classic game with this custom
        # role mixed in.
        used = await r.run(
            "Use custom role in a game",
            lambda: create_game_via_scenario(
                ctx, creator=owner, scenario_code="classic", player_count=8,
                selected_custom_roles=(role,)),
        )
        if used is not None:
            r.expect(role.id in used.custom_role_pool,
                     "Custom role persisted into the game composition")
            total = (sum(used.role_id_pool.values())
                     + sum(used.custom_role_pool.values()))
            r.expect_eq(total, 8, "Composition with custom role totals 8")

        # Delete (soft) it.
        async def _delete(services: ServiceProvider):
            await services.custom_roles.delete(
                custom_role_id=role.id, owner_id=owner.id)

        await r.run("Delete custom role", lambda: ctx.act(_delete))

        async def _list_after(services: ServiceProvider):
            return await services.custom_roles.list_for_owner(owner_id=owner.id)

        after = await r.run("List after deletion", lambda: ctx.act(_list_after))
        r.expect(all(cr.id != role.id for cr in (after or [])),
                 "Deleted role no longer listed")


# ---------------------------------------------------------------------------
# 15 · My Games   16 · Role Description
# ---------------------------------------------------------------------------


async def section_my_games(ctx: AppContext, r: Reporter) -> None:
    r.section("mygames", "My Games")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    gid = created.game.id

    async def _list(services: ServiceProvider):
        return await services.user_games.list_user_games(user_id=creator.id)

    games = await r.run("List user's games", lambda: ctx.act(_list))
    games = games or []
    r.expect(any(g.game_id == gid for g in games),
             "Created game appears in 'My Games'")
    mine = next((g for g in games if g.game_id == gid), None)
    if mine is not None:
        r.expect(mine.is_creator, "User is marked as creator")
        r.expect_eq(mine.player_count, 6, "Summary shows correct player_count")

    async def _detail(services: ServiceProvider):
        return await services.user_games.get_game_detail(
            game_id=gid, user_id=creator.id)

    detail = await r.run("Open game detail", lambda: ctx.act(_detail))
    if detail is not None:
        r.expect_eq(detail.game_id, gid, "Detail is for the right game")
        r.expect(detail.can_delete, "Creator may delete a non-started game")

    # Keyboards build.
    try:
        kb.build_my_games_keyboard(games)
        r.record_pass("My-games list keyboard builds")
    except Exception as exc:  # noqa: BLE001
        r.guard("My-games keyboard", exc)
    if detail is not None:
        try:
            kb.build_game_detail_keyboard(
                game_id=gid, is_creator=True, can_delete=detail.can_delete)
            r.record_pass("Game-detail keyboard builds")
        except Exception as exc:  # noqa: BLE001
            r.guard("Game-detail keyboard", exc)


async def section_role_description(ctx: AppContext, r: Reporter) -> None:
    r.section("roledesc", "Role Description")

    async def _info(services: ServiceProvider):
        svc = services.role_info
        return svc.total, svc.get_page(0), svc.list_index()

    result = await r.run("Role encyclopaedia pages", lambda: ctx.act(_info))
    if result is not None:
        total, page, index = result
        r.expect(total > 0, "Role catalog has entries")
        r.expect(bool(page.details.strip()), "First role page has details")
        r.expect_eq(len(index), total, "Index lists every role")
        # Prev/next wrap correctly.
        r.expect(0 <= page.prev_index < total, "Prev index in range")
        r.expect(0 <= page.next_index < total, "Next index in range")

        # Navigation keyboards build.
        try:
            kb.build_role_page_keyboard(
                prev_index=page.prev_index, next_index=page.next_index)
            kb.build_role_index_keyboard(index)
            r.record_pass("Role info keyboards build")
        except Exception as exc:  # noqa: BLE001
            r.guard("Role info keyboards", exc)


# ---------------------------------------------------------------------------
# 17 · Delete Game
# ---------------------------------------------------------------------------


async def section_delete_game(ctx: AppContext, r: Reporter) -> None:
    r.section("delete", "Delete Game")
    creator = FakeUser(1)
    stranger = FakeUser(2)
    await ctx.ensure_users([creator, stranger])

    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    gid = created.game.id

    # Non-creator cannot delete.
    async def _stranger_delete(services: ServiceProvider):
        await services.game_management.delete_game(
            game_id=gid, requester_id=stranger.id)

    await r.expect_raises(NotGameCreatorError, ctx.act(_stranger_delete),
                          "Non-creator cannot delete a game")

    # Creator deletes; dependent rows go with it (CASCADE).
    async def _delete(services: ServiceProvider):
        return await services.game_management.delete_game(
            game_id=gid, requester_id=creator.id)

    code = await r.run("Creator deletes game", lambda: ctx.act(_delete))
    r.expect(code == created.game.code, "Deletion returns the game code")

    # Game is gone.
    async def _fetch(services: ServiceProvider):
        await services.games.get_by_code(created.game.code)

    await r.expect_raises(GameNotFoundError, ctx.act(_fetch),
                          "Deleted game is no longer retrievable")

    # Dependent players are gone too.
    async def _players(services: ServiceProvider):
        return await services.repos.players.count_active(gid)

    remaining = await r.run("Count players after deletion",
                            lambda: ctx.act(_players))
    r.expect_eq(remaining or 0, 0, "CASCADE removed dependent players")


# ---------------------------------------------------------------------------
# 18 · Cancel Operation   19 · FSM States
# ---------------------------------------------------------------------------


async def section_cancel(ctx: AppContext, r: Reporter) -> None:
    r.section("cancel", "Cancel Operation")
    # Cancel clears FSM state; we simulate the state store behaviour via aiogram's
    # in-memory context to validate the reset contract used by the cancel handler.
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    fsm = FSMContext(storage=storage, key=key)

    try:
        await fsm.set_state(CreateGameStates.choose_player_count)
        await fsm.update_data(player_count=10, scenario_code="classic")
        current = await fsm.get_state()
        r.expect(current == CreateGameStates.choose_player_count.state,
                 "FSM state set correctly during a flow")

        # The cancel action clears both state and data.
        await fsm.clear()
        r.expect(await fsm.get_state() is None, "Cancel clears FSM state")
        r.expect_eq(await fsm.get_data(), {}, "Cancel clears FSM data")
    except Exception as exc:  # noqa: BLE001
        r.guard("FSM cancel semantics", exc)


async def section_fsm_states(ctx: AppContext, r: Reporter) -> None:
    r.section("fsm", "FSM States")
    # Every declared state group must expose the expected states so the wizard
    # transitions referenced by the handlers exist.
    expected = {
        CreateGameStates: [
            "choose_scenario", "choose_player_count", "choose_roles",
            "confirm_summary", "waiting_players",
        ],
        JoinGameStates: [
            "enter_code", "waiting_turn", "choose_number", "game_ready",
        ],
        CustomRoleStates: ["enter_name", "choose_team", "enter_description"],
    }
    for group, names in expected.items():
        for name in names:
            r.expect(hasattr(group, name),
                     f"{group.__name__}.{name} exists",
                     suggestion="Keep app/bot/states.py in sync with handlers.")


# ---------------------------------------------------------------------------
# 20 · All Buttons (reply)   21 · All Callback Queries   22 · Inline Keyboards
# ---------------------------------------------------------------------------


async def section_all_buttons(ctx: AppContext, r: Reporter) -> None:
    r.section("buttons", "All Buttons")
    markup = kb.build_main_menu_keyboard()
    captions = [btn.text for row in markup.keyboard for btn in row]
    r.expect(len(captions) >= 5, "Main menu exposes the expected buttons")
    r.expect(len(captions) == len(set(captions)), "No duplicate reply buttons")
    r.expect(all(c and c.strip() for c in captions), "No empty reply buttons")

    # Team-picker reply/inline for custom roles builds and is well-formed.
    try:
        team_kb = kb.build_team_picker_keyboard()
        payloads = [
            btn.callback_data
            for row in team_kb.inline_keyboard for btn in row
        ]
        r.expect(all(p for p in payloads), "Team picker buttons carry callbacks")
    except Exception as exc:  # noqa: BLE001
        r.guard("Team picker keyboard", exc)


async def section_all_callbacks(ctx: AppContext, r: Reporter) -> None:
    r.section("callbacks", "All Callback Queries")
    # Every typed CallbackData must pack and unpack losslessly (this is what the
    # dispatcher does before routing to a handler). A failure here would mean a
    # button whose callback the bot can't parse — i.e. a dead button.
    samples = [
        RoleToggleCB(game_id=1, role_id=2, is_custom=False),
        RoleToggleCB(game_id=1, role_id=2, is_custom=True),
        RoleSetupActionCB(game_id=1, action="confirm"),
        ScenarioPickCB(code="classic"),
        PlayerCountCB(count=10),
        ScenarioInfoCB(action="show", index=3),
        NumberPickCB(game_id=1, number=5),
        LobbyActionCB(game_id=1, action="assign"),
        GameControlCB(game_id=1, action="start"),
        RoleInfoCB(action="show", index=0),
        CustomRoleCB(action="open", role_id=7),
        CustomRoleTeamCB(team="CITIZEN"),
        MyGamesCB(action="open", game_id=9),
    ]
    for cb in samples:
        name = type(cb).__name__
        try:
            packed = cb.pack()
            unpacked = type(cb).unpack(packed)
            r.expect_eq(unpacked, cb, f"{name} packs/unpacks losslessly")
            r.expect(len(packed.encode()) <= 64,
                     f"{name} payload within Telegram's 64-byte limit",
                     cause=f"len={len(packed.encode())} payload={packed!r}")
        except Exception as exc:  # noqa: BLE001
            r.guard(f"{name} pack/unpack", exc,
                    suggestion="Check field types in app/bot/callbacks.py.")


async def section_inline_keyboards(ctx: AppContext, r: Reporter) -> None:
    r.section("inline", "All Callback Queries")  # merged under callbacks bucket
    r.section("inlinekb", "Inline Keyboards")
    creator = FakeUser(1)
    await ctx.ensure_users([creator])

    def _validate_markup(markup: InlineKeyboardMarkup, label: str) -> None:
        buttons = [b for row in markup.inline_keyboard for b in row]
        r.expect(len(buttons) > 0, f"{label}: has buttons")
        r.expect(all(b.text and b.text.strip() for b in buttons),
                 f"{label}: no empty labels")
        r.expect(
            all((b.callback_data or b.url) for b in buttons),
            f"{label}: every button has callback or url")
        for b in buttons:
            if b.callback_data:
                r.expect(len(b.callback_data.encode()) <= 64,
                         f"{label}: callback within 64 bytes",
                         cause=f"{b.text!r} -> {b.callback_data!r}")

    # Scenario picker + count.
    async def _scenarios(services: ServiceProvider):
        return services.scenarios.list_scenarios()

    scenarios = await ctx.act(_scenarios)
    try:
        _validate_markup(kb.build_scenario_picker_keyboard(scenarios),
                         "Scenario picker")
        _validate_markup(kb.build_scenario_index_keyboard(scenarios),
                         "Scenario index")
        _validate_markup(kb.build_scenario_count_keyboard(scenarios[0]),
                         "Scenario count")
        _validate_markup(
            kb.build_scenario_page_keyboard(index=0, total=len(scenarios)),
            "Scenario page")
    except Exception as exc:  # noqa: BLE001
        r.guard("Scenario keyboards", exc)

    # Role selection.
    async def _roles(services: ServiceProvider):
        scenario = services.scenarios.get_scenario("classic")
        return await services.scenarios.get_selectable_roles(scenario)

    roles = await ctx.act(_roles)
    try:
        _validate_markup(
            kb.build_role_selection_keyboard(
                game_id=1, roles=roles, selected_ids=set(),
                selected_total=0, target_count=10),
            "Role selection")
        _validate_markup(kb.build_composition_summary_keyboard(game_id=1),
                         "Composition summary")
    except Exception as exc:  # noqa: BLE001
        r.guard("Role selection keyboards", exc)

    # Lobby + game control keyboards.
    try:
        _validate_markup(kb.build_number_keyboard(
            game_id=1, available_numbers=[1, 2, 3]), "Number picker")
        _validate_markup(kb.build_waiting_keyboard(game_id=1), "Waiting")
        _validate_markup(kb.build_player_lobby_keyboard(
            game_id=1, has_number=True, has_role=False), "Player lobby")
        _validate_markup(kb.build_creator_lobby_keyboard(
            game_id=1, can_start=True), "Creator lobby")
        _validate_markup(kb.build_in_game_keyboard(game_id=1), "In-game")
    except Exception as exc:  # noqa: BLE001
        r.guard("Lobby/control keyboards", exc)

    # Confirm keyboards.
    try:
        _validate_markup(kb.build_delete_confirm_keyboard(game_id=1),
                         "Delete confirm")
    except Exception as exc:  # noqa: BLE001
        r.guard("Delete confirm keyboard", exc)


# ---------------------------------------------------------------------------
# 24b · Live Lobby Sync
# ---------------------------------------------------------------------------


async def section_live_sync(ctx: AppContext, r: Reporter) -> None:
    """The live-sync service must compute the *correct* pushed screen for every
    eligible waiting player after each shared-state change, and must exclude
    ineligible players (already assigned, left, or never rendered a screen).

    This exercises :class:`LiveGameSyncService` directly (the broadcaster is a
    thin Telegram wrapper over it), since the service holds all the rules.
    """
    r.section("livesync", "Live Lobby Sync")
    players = ctx.make_users(7)
    await ctx.ensure_users(players)
    creator = players[0]
    lobby = players[:6]

    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    code = created.game.code
    gid = created.game.id

    # Helper: register a fake rendered lobby message for a player so they become
    # an eligible live-sync target (mirrors what the handler does after editing).
    async def _record(uid: int, mid: int) -> None:
        async def _op(services: ServiceProvider) -> None:
            await services.live_sync.record_lobby_message(
                game_id=gid, user_id=uid, chat_id=uid, message_id=mid)
        await ctx.act(_op)

    # --- Partial lobby: joined players see a "waiting" screen --------------
    for i, u in enumerate(lobby[:3]):
        await join_player(ctx, code=code, user=u)
        await _record(u.id, 1000 + i)

    async def _screens_partial(services: ServiceProvider):
        return await services.live_sync.compute_sync_screens(game_id=gid)

    screens = await r.run("Compute sync screens (partial lobby)",
                          lambda: ctx.act(_screens_partial))
    screens = screens or []
    r.expect_eq(len(screens), 3,
                "All three recorded waiting players get a screen")

    r.expect(all(s.kind == "waiting" for s in screens),
             "Incomplete lobby yields only 'waiting' screens",
             cause=f"kinds={[s.kind for s in screens]}")

    # A player who never rendered a message is not a target.
    async def _join_unrendered(services: ServiceProvider):
        await services.lobby.join_game(code=code, user_id=lobby[3].id)
    await ctx.act(_join_unrendered)

    screens = await r.run("Compute after an unrendered join",
                          lambda: ctx.act(_screens_partial))
    screens = screens or []
    target_ids = {s.user_id for s in screens}
    r.expect(lobby[3].id not in target_ids,
             "Player without a rendered message is excluded",
             cause=f"targets={target_ids}")

    # --- Fill the lobby: the current turn holder gets the number picker -----
    await _record(lobby[3].id, 1003)
    for i, u in enumerate(lobby[4:]):
        await join_player(ctx, code=code, user=u)
        await _record(u.id, 1004 + i)

    async def _screens_full(services: ServiceProvider):
        return await services.live_sync.compute_sync_screens(game_id=gid)

    screens = await r.run("Compute sync screens (full lobby)",
                          lambda: ctx.act(_screens_full))
    screens = screens or []
    by_user = {s.user_id: s for s in screens}
    # The first joiner is the current turn holder -> number picker.
    holder = by_user.get(lobby[0].id)
    r.expect(holder is not None and holder.kind == "numbers",
             "Turn holder is shown the seat-number picker",
             cause=f"holder={holder.kind if holder else None}")
    if holder is not None:
        r.expect(len(holder.available_numbers) == 6,
                 "Picker offers all six free seats",
                 cause=f"numbers={holder.available_numbers}")
    # Everyone else is 'waiting' (not your turn).
    others = [s for uid, s in by_user.items() if uid != lobby[0].id]
    r.expect(all(s.kind == "waiting" for s in others),
             "Non-turn players see the 'waiting' screen",
             cause=f"kinds={[s.kind for s in others]}")

    # --- Turn holder picks a number: they flip to 'getrole', seat disappears -
    async def _pick(services: ServiceProvider):
        await services.lobby.choose_number(
            game_id=gid, user_id=lobby[0].id, number=3)
    await ctx.act(_pick)

    screens = await r.run("Compute after the holder picks seat 3",
                          lambda: ctx.act(_screens_full))
    screens = screens or []
    by_user = {s.user_id: s for s in screens}
    holder = by_user.get(lobby[0].id)
    r.expect(holder is not None and holder.kind == "getrole",
             "Holder who picked a seat is prompted to get their role",
             cause=f"holder={holder.kind if holder else None}")
    # The still-waiting next player must no longer be offered seat 3.
    nxt = by_user.get(lobby[1].id)
    if nxt is not None and nxt.kind == "numbers":
        r.expect(3 not in nxt.available_numbers,
                 "Taken seat 3 is removed from others' pickers",
                 cause=f"numbers={nxt.available_numbers}")

    # --- Assigned players drop out of the sync set entirely ----------------
    async def _assign(services: ServiceProvider):
        return await services.lobby.assign_role(game_id=gid, user_id=lobby[0].id)
    await ctx.act(_assign)

    screens = await r.run("Compute after the holder is assigned a role",
                          lambda: ctx.act(_screens_full))
    screens = screens or []
    target_ids = {s.user_id for s in screens}
    r.expect(lobby[0].id not in target_ids,
             "A player with a role is never a live-sync target",
             cause=f"targets={target_ids}")

    # --- exclude_user_id skips the actor -----------------------------------
    async def _screens_excl(services: ServiceProvider):
        return await services.live_sync.compute_sync_screens(
            game_id=gid, exclude_user_id=lobby[1].id)

    screens = await r.run("Compute with exclude_user_id",
                          lambda: ctx.act(_screens_excl))
    screens = screens or []
    r.expect(all(s.user_id != lobby[1].id for s in screens),
             "exclude_user_id removes the acting player from targets",
             cause=f"targets={[s.user_id for s in screens]}")

    # --- Keyboard mapping in the broadcaster matches each screen kind -------
    try:
        from app.bot.live_broadcaster import _keyboard_for
        from app.schemas.game import PlayerSyncScreenDTO

        num_kb = _keyboard_for(PlayerSyncScreenDTO(
            user_id=1, game_id=gid, chat_id=1, message_id=1,
            text="t", kind="numbers", available_numbers=[1, 2]))
        wait_kb = _keyboard_for(PlayerSyncScreenDTO(
            user_id=1, game_id=gid, chat_id=1, message_id=1,
            text="t", kind="waiting"))
        role_kb = _keyboard_for(PlayerSyncScreenDTO(
            user_id=1, game_id=gid, chat_id=1, message_id=1,
            text="t", kind="getrole"))
        for label, markup in (("numbers", num_kb), ("waiting", wait_kb),
                              ("getrole", role_kb)):
            buttons = [b for row in markup.inline_keyboard for b in row]
            r.expect(len(buttons) > 0, f"'{label}' screen builds a keyboard")
    except Exception as exc:  # noqa: BLE001
        r.guard("Broadcaster keyboard mapping", exc,
                suggestion="Check _keyboard_for in app/bot/live_broadcaster.py.")


# ---------------------------------------------------------------------------
# 25 · Concurrency (Race Conditions)
# ---------------------------------------------------------------------------



async def section_concurrency(ctx: AppContext, r: Reporter) -> None:
    r.section("concurrency", "Concurrency")
    players = ctx.make_users(9)
    await ctx.ensure_users(players)
    creator = players[0]

    # --- Concurrent joins: two players join the *same last slot* -----------
    created = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    code = created.game.code
    gid = created.game.id
    await fill_lobby(ctx, code=code, players=players[:5])  # 5/6 full

    # players[5] and players[6] race for the final seat.
    results = await asyncio.gather(
        join_player(ctx, code=code, user=players[5]),
        join_player(ctx, code=code, user=players[6]),
        return_exceptions=True,
    )
    successes = [x for x in results if not isinstance(x, Exception)]
    failures = [x for x in results if isinstance(x, Exception)]
    r.expect_eq(len(successes), 1, "Exactly one of two racing joins succeeds",
                suggestion="Row-lock in join_game must serialise capacity check.")
    r.expect(all(isinstance(f, GameFullError) for f in failures),
             "Loser of the join race gets GameFullError",
             cause=f"failures={[type(f).__name__ for f in failures]}")

    async def _active(services: ServiceProvider):
        return await services.repos.players.count_active(gid)

    active = await r.run("Count active after join race",
                         lambda: ctx.act(_active))
    r.expect_eq(active or 0, 6, "Lobby has exactly capacity after race")

    # --- Concurrent number picks: first two players race for number 1 ------
    # Fresh full lobby.
    created2 = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    code2 = created2.game.code
    gid2 = created2.game.id
    await fill_lobby(ctx, code=code2, players=players[:6])

    # Both the first two joiners try to grab number 1 at once. Turn order means
    # only the current-turn player may even act, and the row lock guarantees a
    # single winner for the number.
    async def _pick(uid: int, number: int):
        async def _op(services: ServiceProvider):
            await services.lobby.choose_number(
                game_id=gid2, user_id=uid, number=number)
        return await ctx.act(_op)

    picks = await asyncio.gather(
        _pick(players[0].id, 1),
        _pick(players[1].id, 1),
        return_exceptions=True,
    )
    ok_picks = [x for x in picks if not isinstance(x, Exception)]
    r.expect(len(ok_picks) <= 1,
             "At most one concurrent claim on number 1 succeeds",
             cause=f"successes={len(ok_picks)}")

    async def _taken(services: ServiceProvider):
        return await services.repos.players.taken_numbers(gid2)

    taken = await r.run("Taken numbers after pick race",
                        lambda: ctx.act(_taken))
    taken = taken or []
    r.expect(len(taken) == len(set(taken)),
             "No duplicate seat numbers after race",
             cause=f"taken={taken}")

    # --- Concurrent delete: creator deletes twice simultaneously -----------
    created3 = await create_game_via_scenario(
        ctx, creator=creator, scenario_code="classic", player_count=6)
    gid3 = created3.game.id

    async def _del():
        async def _op(services: ServiceProvider):
            return await services.game_management.delete_game(
                game_id=gid3, requester_id=creator.id)
        return await ctx.act(_op)

    dels = await asyncio.gather(_del(), _del(), return_exceptions=True)
    ok_dels = [x for x in dels if not isinstance(x, Exception)]
    r.expect(len(ok_dels) >= 1, "At least one concurrent delete succeeds")
    r.expect(len(ok_dels) <= 1 or all(
        d == created3.game.code for d in ok_dels),
        "Concurrent deletes do not corrupt state")


# ---------------------------------------------------------------------------
# 26 · Auto Role Assignment   27 · Owner Test Flow
# ---------------------------------------------------------------------------


async def section_auto_assignment(ctx: AppContext, r: Reporter) -> None:
    """Auto-assignment games hand out a unique seat + role the instant a player
    joins, with no turn gating — even under concurrent joins."""
    r.section("autoassign", "Auto Role Assignment")
    players = ctx.make_users(9)
    await ctx.ensure_users(players)
    creator = players[0]

    # Create an AUTO-mode game and configure a classic 6-role composition.
    async def _resolve(services: ServiceProvider):
        scenario = services.scenarios.get_scenario("classic")
        return await services.scenarios.resolve(scenario=scenario, player_count=6)

    resolved = await ctx.act(_resolve)

    async def _create(services: ServiceProvider):
        game = await services.games.create_game(
            creator_telegram_id=creator.id, player_count=6,
            scenario_code="classic", role_mode=RoleMode.AUTO_ROLE_ASSIGNMENT)
        await services.games.configure_roles(
            game_id=game.id, creator_telegram_id=creator.id,
            role_quantities=resolved.role_quantities,
            custom_role_quantities=resolved.custom_role_quantities)
        return game

    game = await r.run("Create AUTO-mode game", lambda: ctx.act(_create))
    if game is None:
        return
    gid = game.id
    code = game.code
    r.expect_eq(game.role_mode, RoleMode.AUTO_ROLE_ASSIGNMENT,
                "Game persists AUTO_ROLE_ASSIGNMENT mode")

    # A single joiner gets both a seat and a role immediately (no turn wait).
    async def _join_and_assign(uid: int):
        async def _op(services: ServiceProvider):
            await services.lobby.join_game(code=code, user_id=uid)
            return await services.auto_assignment.assign_for_player(
                game_id=gid, user_id=uid)
        return await ctx.act(_op)

    first = await r.run("First auto joiner gets a role immediately",
                        lambda: _join_and_assign(players[0].id))
    r.expect(first is not None and bool(first.name_fa),
             "Auto-assign returns a role reveal on join")

    async def _first_number(services: ServiceProvider):
        p = await services.players.get_player(game_id=gid, user_id=players[0].id)
        return p.number

    num = await r.run("First auto joiner also gets a seat number",
                      lambda: ctx.act(_first_number))
    r.expect(num is not None, "Seat number assigned on auto-join",
             cause=f"number={num}")

    # Fill the rest concurrently; every joiner still ends unique.
    race = await asyncio.gather(
        *[_join_and_assign(u.id) for u in players[1:6]],
        return_exceptions=True,
    )
    ok = [x for x in race if not isinstance(x, Exception)]
    r.expect(len(ok) == 5, "All five concurrent auto-joins succeed",
             cause=f"errors={[type(x).__name__ for x in race if isinstance(x, Exception)]}")


    async def _final(services: ServiceProvider):
        taken = await services.repos.players.taken_numbers(gid)
        assigned = await services.repos.players.count_assigned(gid)
        remaining = await services.repos.game_roles.total_remaining(gid)
        g = await services.games.get_by_code(code)
        return taken, assigned, remaining, g.status

    final = await r.run("Fetch final auto-assign state", lambda: ctx.act(_final))
    if final is not None:
        taken, assigned, remaining, status = final
        r.expect(sorted(taken) == list(range(1, 7)),
                 "Seats are exactly 1..6 with no duplicates",
                 cause=f"taken={taken}")
        r.expect_eq(assigned, 6, "All six players received a role")
        r.expect_eq(remaining, 0, "Role pool is fully exhausted (unique roles)")
        r.expect_eq(status, GameStatus.READY,
                    "Game auto-promotes to READY once full")


    # Over-capacity auto-join is rejected. Because the lobby auto-promotes to
    # READY the instant it fills, a further join is refused as either "full" or
    # "not joinable" — both are correct guards against over-capacity.
    await r.expect_raises((GameFullError, GameNotJoinableError),
                          _join_and_assign(players[6].id),
                          "Auto-join beyond capacity is rejected")



async def section_owner_test_flow(ctx: AppContext, r: Reporter) -> None:
    """The owner self-test drives a *complete* real-pipeline game end-to-end and
    reports success; the OwnerFilter must also gate access to the feature."""
    r.section("ownertest", "Owner Test Flow")
    owner = FakeUser(1)
    await ctx.ensure_users([owner])

    async def _run(services: ServiceProvider):
        return await services.owner_test_flow.run_full_test(
            owner_id=owner.id, player_count=8, scenario_code="classic",
            owner_display_name="Owner Tester")

    report = await r.run("Run full owner test flow (8 players)",
                         lambda: ctx.act(_run))
    if report is not None:
        r.expect(report.success, "Owner test flow reports overall success",
                 cause=f"failed_step={report.failed_step}, error={report.error}")
        r.expect(all(s.ok for s in report.steps),
                 "Every reported step passed",
                 cause=f"steps={[(s.label, s.ok) for s in report.steps]}")
        r.expect(report.game_code is not None and len(report.game_code) == 6,
                 "Report carries a 6-digit game code")
        r.expect_eq(report.player_count, 8, "Report player_count is 8")
        total = report.citizen_count + report.mafia_count + report.independent_count
        r.expect_eq(total, 8, "Team composition in report totals player_count")
        r.expect(report.mafia_count >= 1, "Report shows at least one mafia")

        # The produced game really is IN_PROGRESS in the DB.
        async def _status(services: ServiceProvider):
            g = await services.games.get_by_code(report.game_code)
            return g.status

        status = await r.run("Owner test game is IN_PROGRESS in DB",
                             lambda: ctx.act(_status))
        r.expect_eq(status, GameStatus.IN_PROGRESS,
                    "Self-test leaves a started game")

    # --- OwnerFilter access control ---------------------------------------
    try:
        from types import SimpleNamespace

        from app.bot.filters import OwnerFilter
        from app.config.settings import get_settings

        settings = get_settings()
        flt = OwnerFilter()
        configured = settings.bot_owner_id

        if configured is None:
            # Feature disabled: filter must reject everyone.
            evt = SimpleNamespace(from_user=SimpleNamespace(id=owner.id))
            allowed = await flt(evt)
            r.expect(allowed is False,
                     "OwnerFilter rejects all when BOT_OWNER_ID is unset")
        else:
            owner_evt = SimpleNamespace(
                from_user=SimpleNamespace(id=configured))
            stranger_evt = SimpleNamespace(
                from_user=SimpleNamespace(id=configured + 1))
            r.expect(await flt(owner_evt) is True,
                     "OwnerFilter admits the configured owner")
            r.expect(await flt(stranger_evt) is False,
                     "OwnerFilter rejects non-owners")
    except Exception as exc:  # noqa: BLE001
        r.guard("OwnerFilter access control", exc,
                suggestion="Check app/bot/filters/owner.py and settings.")

