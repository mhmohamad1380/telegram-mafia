"""Filter restricting handlers to private (one-on-one) chats.

Role reveals and game management happen in private chats so roles stay secret.
"""

from __future__ import annotations

from aiogram.enums import ChatType
from aiogram.filters import BaseFilter
from aiogram.types import Message


class PrivateChatFilter(BaseFilter):
    """Passes only when the incoming message is from a private chat."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type == ChatType.PRIVATE
