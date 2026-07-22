"""Owner-only access filter.

Restricts a handler to the configured bot owner (``BOT_OWNER_ID``). Applied to
both the message handler and the callback handlers of the internal test flow so
that:

* regular users never see the test button, and
* even a hand-crafted callback from a non-owner is rejected server-side.

If ``BOT_OWNER_ID`` is unset, the filter matches no one (the feature is fully
disabled).
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config.settings import get_settings


class OwnerFilter(BaseFilter):
    """Passes only for updates originating from the configured bot owner."""

    async def __call__(self, event: TelegramObject) -> bool:  # noqa: D401
        owner_id = get_settings().bot_owner_id
        if owner_id is None:
            return False
        user = getattr(event, "from_user", None)
        if user is None and isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        return user is not None and user.id == owner_id
