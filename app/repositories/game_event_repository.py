"""Repository for :class:`GameEvent` audit records."""

from __future__ import annotations

from typing import Any

from app.models.enums import GameEventType
from app.models.game_event import GameEvent
from app.repositories.base import BaseRepository


class GameEventRepository(BaseRepository[GameEvent]):
    """Append-only writer for the game audit log."""

    model = GameEvent

    async def record(
        self,
        *,
        game_id: int,
        event_type: GameEventType,
        user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> GameEvent:
        """Append an audit event for a game."""
        event = GameEvent(
            game_id=game_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload or {},
        )
        return await self.add(event)
