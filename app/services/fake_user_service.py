"""FakeUserService: synthetic players for the owner-only test flow.

Creates deterministic, clearly-labelled "Test User" accounts and lets them join
a lobby through the **real** join path (:class:`LobbyService`), so the owner test
flow exercises exactly the same code real players would — no fake shortcut.

Fake user ids live in a reserved high range (:data:`FAKE_USER_ID_BASE` ..) so
they can never collide with real Telegram ids (which are far smaller) and are
trivially identifiable/purgeable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.logging import get_logger
from app.models.user import User
from app.repositories import RepositoryProvider

logger = get_logger(__name__)

#: Base of the reserved id range for synthetic test users. Real Telegram user
#: ids are comfortably below this, so collisions are impossible.
FAKE_USER_ID_BASE = 9_000_000_000


@dataclass(frozen=True, slots=True)
class FakeParticipant:
    """A synthetic test participant (id + display name)."""

    user_id: int
    display_name: str


class FakeUserService:
    """Creates and manages synthetic test users for the owner test flow."""

    def __init__(self, repos: RepositoryProvider) -> None:
        self._repos = repos

    @staticmethod
    def is_fake_user(user_id: int) -> bool:
        """Whether ``user_id`` belongs to the reserved synthetic range."""
        return user_id >= FAKE_USER_ID_BASE

    async def ensure_fake_users(self, count: int) -> list[FakeParticipant]:
        """Create (or refresh) ``count`` synthetic test users and return them.

        The users are numbered ``Test User 1..count`` with stable ids so repeated
        test runs reuse the same rows instead of accumulating new ones.
        """
        participants: list[FakeParticipant] = []
        for i in range(1, count + 1):
            user_id = FAKE_USER_ID_BASE + i
            name = f"Test User {i}"
            await self._repos.users.upsert_from_telegram(
                telegram_id=user_id,
                username=f"test_user_{i}",
                first_name=name,
                last_name=None,
            )
            participants.append(FakeParticipant(user_id=user_id, display_name=name))
        logger.info("fake_users_ensured", count=count)
        return participants

    async def get_or_create_owner(
        self, *, owner_id: int, display_name: str | None = None
    ) -> User:
        """Ensure the owner has a user row (they may not have used the bot yet)."""
        return await self._repos.users.upsert_from_telegram(
            telegram_id=owner_id,
            username=None,
            first_name=display_name or "Bot Owner",
            last_name=None,
        )
