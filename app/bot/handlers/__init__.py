"""Handler routers aggregator.

:func:`get_main_router` wires every feature router into a single parent router
that the dispatcher includes. Order matters only where handlers could overlap;
here the routers are cleanly separated by command/state/callback prefix.
"""

from __future__ import annotations

from aiogram import Router

from app.bot.handlers import common, create_game, game_control, join_game


def get_main_router() -> Router:
    """Build and return the composed application router."""
    router = Router(name="main")
    router.include_router(common.router)
    router.include_router(create_game.router)
    router.include_router(join_game.router)
    router.include_router(game_control.router)
    return router


__all__ = ["get_main_router"]
