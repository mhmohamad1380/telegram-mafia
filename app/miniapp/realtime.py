"""Realtime fan-out for the Mini App: per-table WebSocket rooms over Redis.

Every table (game) is a *room*. When anything changes — a player joins, the turn
advances, a vote is cast — the originating request publishes a JSON event to a
Redis channel named ``miniapp:game:{game_id}``. A single background subscriber
per process receives those events and forwards them to every locally-connected
WebSocket in that room.

Going through Redis (rather than a purely in-process registry) means the design
scales horizontally: the bot may publish an event from one process while players
are connected to another, and everyone still receives it. WebRTC voice signaling
(SDP offers/answers, ICE candidates) rides the same channel as ``rtc.*`` events,
so no separate signaling server is needed.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import orjson
from redis.asyncio import Redis
from starlette.websockets import WebSocket

from app.config.logging import get_logger

logger = get_logger(__name__)

_CHANNEL_PREFIX = "miniapp:game:"


def _channel(game_id: int) -> str:
    return f"{_CHANNEL_PREFIX}{game_id}"


class RealtimeHub:
    """Bridges Redis pub/sub to per-room WebSocket connections.

    One instance is created per ASGI process (in the app lifespan). It owns a
    single Redis subscriber task that pattern-subscribes to every game channel
    and dispatches to the in-process rooms.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._pubsub_task: asyncio.Task[None] | None = None
        # Games with a running speaking timer, watched by the server tick loop.
        # Exposed on the hub (which route handlers already depend on) so they can
        # flag a table active without importing the app object.
        self.hot_games: set[int] = set()

    # --- Lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Begin listening to all game channels."""
        if self._pubsub_task is None:
            self._pubsub_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        """Cancel the subscriber and drop all connections."""
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
            self._pubsub_task = None

    async def _listen(self) -> None:
        """Forward every Redis message to the matching in-process room."""
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(f"{_CHANNEL_PREFIX}*")
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                try:
                    game_id = int(channel.removeprefix(_CHANNEL_PREFIX))
                except ValueError:  # pragma: no cover - defensive
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await self._broadcast_local(game_id, data)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        finally:
            await pubsub.aclose()

    # --- Room membership ---------------------------------------------------

    async def join(self, game_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[game_id].add(ws)

    async def leave(self, game_id: int, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(game_id)
            if room is not None:
                room.discard(ws)
                if not room:
                    self._rooms.pop(game_id, None)

    # --- Publishing --------------------------------------------------------

    async def publish(self, game_id: int, event: dict[str, Any]) -> None:
        """Publish an event to a game's channel (delivered to all processes)."""
        await self._redis.publish(_channel(game_id), orjson.dumps(event))

    async def _broadcast_local(self, game_id: int, payload: str) -> None:
        """Send a raw JSON payload to every WebSocket connected here."""
        async with self._lock:
            targets = list(self._rooms.get(game_id, ()))
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:  # pragma: no cover - client vanished mid-send
                await self.leave(game_id, ws)
