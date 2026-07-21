"""RandomizerService: cryptographically-sound random selection helpers.

Isolated so the randomness source is a single, swappable dependency (useful for
deterministic testing by injecting a seeded implementation).
"""

from __future__ import annotations

import secrets
from typing import TypeVar

T = TypeVar("T")


class RandomizerService:
    """Provides unbiased random selection using :mod:`secrets`."""

    def choice(self, items: list[T]) -> T:
        """Return a uniformly-random element from a non-empty list.

        Raises:
            IndexError: If ``items`` is empty.
        """
        if not items:
            raise IndexError("cannot choose from an empty sequence")
        return items[secrets.randbelow(len(items))]

    def shuffle(self, items: list[T]) -> list[T]:
        """Return a new list with the elements of ``items`` shuffled.

        Implements a Fisher-Yates shuffle backed by :func:`secrets.randbelow`.
        """
        result = list(items)
        for i in range(len(result) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            result[i], result[j] = result[j], result[i]
        return result
