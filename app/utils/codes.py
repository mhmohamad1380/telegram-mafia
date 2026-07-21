"""Helpers for generating game join codes and other small utilities."""

from __future__ import annotations

import secrets

GAME_CODE_LENGTH = 6
_GAME_CODE_MIN = 10 ** (GAME_CODE_LENGTH - 1)  # 100000
_GAME_CODE_MAX = (10**GAME_CODE_LENGTH) - 1    # 999999


def generate_game_code() -> str:
    """Generate a cryptographically-random 6-digit numeric game code.

    Uniqueness is enforced at the DB level (unique constraint); the caller
    retries on collision. Uses :mod:`secrets` so codes are not predictable.
    """
    return str(secrets.randbelow(_GAME_CODE_MAX - _GAME_CODE_MIN + 1) + _GAME_CODE_MIN)


def to_persian_digits(value: object) -> str:
    """Convert ASCII digits in ``value`` to Persian digits for display."""
    table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return str(value).translate(table)
