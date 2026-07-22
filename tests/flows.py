"""Reusable, high-level game flows built on top of :class:`AppContext`.

These helpers compose the service-layer calls a real user would trigger through
the handlers, so individual test sections read like a script of user actions:
create a game, fill the lobby, then let each player take their turn to pick a
number and receive a role. Each helper runs every step in its own committed
transaction via :meth:`AppContext.act`, faithfully reproducing the "one Telegram
update = one transaction" model.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import RoleCode
from app.schemas.game import (
    AssignmentResultDTO,
    CustomRoleDTO,
    GameDTO,
    PlayerRoleDTO,
)
from app.services import ServiceProvider

from tests.harness import AppContext, FakeUser


@dataclass(slots=True)
class CreatedGame:
    """The outcome of creating + configuring a game via a scenario."""

    game: GameDTO
    scenario_code: str
    player_count: int
    role_id_pool: dict[int, int]  # catalog role_id -> quantity
    custom_role_pool: dict[int, int]  # custom_role_id -> quantity


async def create_game_via_scenario(
    ctx: AppContext,
    *,
    creator: FakeUser,
    scenario_code: str,
    player_count: int,
    selected_codes: tuple[RoleCode, ...] = (),
    selected_custom_roles: tuple[CustomRoleDTO, ...] = (),
) -> CreatedGame:
    """Create a game and persist its resolved role composition.

    Mirrors the create-game wizard: pick scenario → pick count → resolve roles
    (auto-completing fill roles) → create game → configure roles. Returns a
    :class:`CreatedGame` describing the persisted composition.
    """

    async def _resolve(services: ServiceProvider):
        scenario = services.scenarios.get_scenario(scenario_code)
        result = await services.scenarios.resolve(
            scenario=scenario,
            player_count=player_count,
            selected_codes=selected_codes,
            selected_custom_roles=selected_custom_roles,
        )
        return result

    resolved = await ctx.act(_resolve)

    async def _create(services: ServiceProvider) -> GameDTO:
        return await services.games.create_game(
            creator_telegram_id=creator.id,
            player_count=player_count,
            scenario_code=scenario_code,
        )

    game = await ctx.act(_create)

    async def _configure(services: ServiceProvider) -> GameDTO:
        return await services.games.configure_roles(
            game_id=game.id,
            creator_telegram_id=creator.id,
            role_quantities=resolved.role_quantities,
            custom_role_quantities=resolved.custom_role_quantities,
        )

    configured = await ctx.act(_configure)

    return CreatedGame(
        game=configured,
        scenario_code=scenario_code,
        player_count=player_count,
        role_id_pool=dict(resolved.role_quantities),
        custom_role_pool=dict(resolved.custom_role_quantities),
    )


async def join_player(ctx: AppContext, *, code: str, user: FakeUser) -> GameDTO:
    """Join one player to a lobby by code (own transaction)."""

    async def _op(services: ServiceProvider) -> GameDTO:
        return await services.lobby.join_game(code=code, user_id=user.id)

    return await ctx.act(_op)


async def fill_lobby(
    ctx: AppContext, *, code: str, players: list[FakeUser]
) -> None:
    """Join every player in ``players`` sequentially (FIFO join order)."""
    for user in players:
        await join_player(ctx, code=code, user=user)


async def take_turn(
    ctx: AppContext, *, game_id: int, code: str, user: FakeUser
) -> tuple[int, AssignmentResultDTO]:
    """Perform one player's full turn: pick the lowest free number, get a role.

    Returns the chosen number and the assignment result. Each of the two steps
    runs in its own transaction, exactly as two Telegram callbacks would.
    """

    async def _pick_number(services: ServiceProvider) -> int:
        available = await services.lobby.available_numbers(game_id=game_id)
        number = available[0]
        await services.lobby.choose_number(
            game_id=game_id, user_id=user.id, number=number
        )
        return number

    number = await ctx.act(_pick_number)

    async def _assign(services: ServiceProvider) -> AssignmentResultDTO:
        return await services.lobby.assign_role(game_id=game_id, user_id=user.id)

    result = await ctx.act(_assign)
    return number, result


async def run_all_turns(
    ctx: AppContext,
    *,
    game_id: int,
    code: str,
    players: list[FakeUser],
) -> dict[int, PlayerRoleDTO]:
    """Drive every player's turn in join order; return user_id -> role reveal.

    Turn order is enforced by the service layer, so this simply iterates the
    players in the order they joined and lets each act on their turn.
    """
    reveals: dict[int, PlayerRoleDTO] = {}
    for user in players:
        _, result = await take_turn(ctx, game_id=game_id, code=code, user=user)
        if result is not None:
            reveals[user.id] = result.role
    return reveals


async def get_my_role(
    ctx: AppContext, *, game_id: int, user: FakeUser
) -> PlayerRoleDTO:
    async def _op(services: ServiceProvider) -> PlayerRoleDTO:
        return await services.players.get_my_role(
            game_id=game_id, user_id=user.id
        )

    return await ctx.act(_op)


async def start_game(
    ctx: AppContext, *, game_id: int, creator: FakeUser
) -> GameDTO:
    async def _op(services: ServiceProvider) -> GameDTO:
        return await services.games.start_game(
            game_id=game_id, creator_telegram_id=creator.id
        )

    return await ctx.act(_op)


async def finish_game(
    ctx: AppContext, *, game_id: int, creator: FakeUser
) -> GameDTO:
    async def _op(services: ServiceProvider) -> GameDTO:
        return await services.games.finish_game(
            game_id=game_id, creator_telegram_id=creator.id
        )

    return await ctx.act(_op)
