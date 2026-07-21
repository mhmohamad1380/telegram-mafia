"""Repository for :class:`User` entities."""

from __future__ import annotations

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Query and persistence operations for users."""

    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Return the user with the given Telegram id, or ``None``."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def upsert_from_telegram(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> User:
        """Create or update a user record from Telegram profile data.

        The Telegram id doubles as our primary key, so this is a simple
        get-or-create with a lightweight profile refresh on each call.
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                id=telegram_id,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            await self.add(user)
            return user

        # Refresh profile fields if they changed.
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        await self.session.flush()
        return user
