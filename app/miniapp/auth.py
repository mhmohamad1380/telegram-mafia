"""Server-side authentication of Telegram Mini App ``initData``.

Telegram signs the ``window.Telegram.WebApp.initData`` string with a key
derived from the bot token. Verifying that signature on the server is the *only*
trustworthy way to know which Telegram user is talking to us — the client can
claim anything, so every sensitive operation authenticates from this, never from
a user id supplied in the request body.

Algorithm (per Telegram docs):

1. Parse ``initData`` as a URL query string into key/value pairs.
2. Remove the ``hash`` field; build the *data-check-string* by joining the
   remaining ``key=value`` pairs sorted by key with ``\n``.
3. ``secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)``.
4. Expected hash ``= HMAC_SHA256(key=secret_key, msg=data_check_string)``.
5. Constant-time compare against the supplied ``hash``.
6. Optionally reject stale ``auth_date`` (replay-window mitigation).

This module has no framework dependencies so it is trivially unit-testable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(Exception):
    """Raised when ``initData`` is missing, malformed, or fails verification."""


@dataclass(frozen=True, slots=True)
class TelegramUser:
    """The authenticated Telegram user parsed from verified ``initData``."""

    id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    photo_url: str | None
    language_code: str | None


@dataclass(frozen=True, slots=True)
class InitData:
    """Verified WebApp launch context."""

    user: TelegramUser
    auth_date: int
    start_param: str | None
    raw: dict[str, str]


def _data_check_string(pairs: list[tuple[str, str]]) -> str:
    """Build the sorted, newline-joined data-check-string (excluding ``hash``)."""
    filtered = [(k, v) for k, v in pairs if k != "hash"]
    filtered.sort(key=lambda kv: kv[0])
    return "\n".join(f"{k}={v}" for k, v in filtered)


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = 86_400,
    now: int | None = None,
) -> InitData:
    """Verify and parse a Telegram WebApp ``initData`` string.

    :param init_data: The raw ``initData`` query string from the WebApp SDK.
    :param bot_token: The bot token used to derive the verification secret.
    :param max_age_seconds: Reject if ``auth_date`` is older than this. ``0``
        disables the freshness check.
    :raises InitDataError: If missing/malformed, signature invalid, or expired.
    :returns: A verified :class:`InitData`.
    """
    if not init_data:
        raise InitDataError("empty initData")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    data = dict(pairs)

    supplied_hash = data.get("hash")
    if not supplied_hash:
        raise InitDataError("initData missing 'hash'")

    expected = hmac.new(
        _secret_key(bot_token),
        _data_check_string(pairs).encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, supplied_hash):
        raise InitDataError("initData signature mismatch")

    # --- Freshness (replay window) ---
    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError as exc:  # pragma: no cover - defensive
        raise InitDataError("initData 'auth_date' is not an integer") from exc

    if max_age_seconds > 0:
        current = now if now is not None else int(time.time())
        if auth_date <= 0 or current - auth_date > max_age_seconds:
            raise InitDataError("initData is expired")

    # --- User payload ---
    user_json = data.get("user")
    if not user_json:
        raise InitDataError("initData missing 'user'")
    try:
        user_obj = json.loads(user_json)
    except json.JSONDecodeError as exc:
        raise InitDataError("initData 'user' is not valid JSON") from exc

    try:
        user = TelegramUser(
            id=int(user_obj["id"]),
            first_name=user_obj.get("first_name"),
            last_name=user_obj.get("last_name"),
            username=user_obj.get("username"),
            photo_url=user_obj.get("photo_url"),
            language_code=user_obj.get("language_code"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InitDataError("initData 'user' is malformed") from exc

    return InitData(
        user=user,
        auth_date=auth_date,
        start_param=data.get("start_param"),
        raw=data,
    )
