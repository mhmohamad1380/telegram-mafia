"""Ephemeral live table state (phase, turn, timer, challenge, votes) in Redis.

Persistent facts — who is in the game, seat numbers, assigned roles — live in
PostgreSQL via the existing models. But the *live* moment-to-moment state of an
online table (which phase we're in, whose speaking turn it is, how many timer
seconds remain, an open challenge, in-progress votes) is transient, changes many
times per second's worth of interaction, and does not need durable history. That
belongs in Redis, keyed per game, with a TTL so abandoned tables self-clean.

Keeping this separate from the SQLAlchemy models means the online-play feature
adds **no** migration risk to the core schema and can evolve independently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import orjson
from redis.asyncio import Redis

_KEY_PREFIX = "miniapp:state:"
# Abandoned tables evaporate after 12h of no writes.
_TTL_SECONDS = 12 * 60 * 60


class Phase(StrEnum):
    """Coarse game phases the Mini App renders (drives day/night theming)."""

    LOBBY = "lobby"
    DAY = "day"
    NIGHT = "night"
    VOTING = "voting"
    DEFENSE = "defense"
    RESULTS = "results"
    FINISHED = "finished"


@dataclass(slots=True)
class Challenge:
    """An open challenge from the current speaker to another player."""

    challenger_number: int
    target_number: int
    seconds: int


@dataclass(slots=True)
class LiveState:
    """The full live snapshot for one table.

    ``votes`` maps a voter seat number -> target seat number; it is deliberately
    hidden from clients until the voting phase closes (enforced by the service /
    route layer, not here).
    """

    phase: str = Phase.LOBBY.value
    turn_number: int | None = None
    timer_seconds: int = 0
    timer_running: bool = False
    challenge: dict[str, Any] | None = None
    votes: dict[str, int] = field(default_factory=dict)
    muted_all: bool = True
    speaking_number: int | None = None
    # Monotonic version so clients can detect/skip stale updates.
    version: int = 0

    def to_json(self) -> bytes:
        return orjson.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: bytes | str) -> "LiveState":
        data = orjson.loads(raw)
        return cls(**data)


def _key(game_id: int) -> str:
    return f"{_KEY_PREFIX}{game_id}"


class LiveStateStore:
    """Async CRUD for a game's :class:`LiveState` in Redis."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, game_id: int) -> LiveState:
        """Return the stored state, or a fresh LOBBY default if absent."""
        raw = await self._redis.get(_key(game_id))
        if raw is None:
            return LiveState()
        return LiveState.from_json(raw)

    async def save(self, game_id: int, state: LiveState) -> LiveState:
        """Persist state, bumping its version and refreshing the TTL."""
        state.version += 1
        await self._redis.set(_key(game_id), state.to_json(), ex=_TTL_SECONDS)
        return state

    async def clear(self, game_id: int) -> None:
        """Remove all live state for a finished/cancelled game."""
        await self._redis.delete(_key(game_id))
