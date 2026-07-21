"""Typed callback data for inline keyboards (aiogram CallbackData factories)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class RoleToggleCB(CallbackData, prefix="role"):
    """Toggle a role on/off during game-setup role selection."""

    game_id: int
    role_id: int


class RoleSetupActionCB(CallbackData, prefix="rolesetup"):
    """Confirm/cancel actions on the role-selection screen."""

    game_id: int
    action: str  # "confirm" | "cancel"


class PlayerCountCB(CallbackData, prefix="pcount"):
    """Quick-pick a suggested player count."""

    count: int


class NumberPickCB(CallbackData, prefix="num"):
    """Pick a seat number in the lobby."""

    game_id: int
    number: int


class LobbyActionCB(CallbackData, prefix="lobby"):
    """Player-side lobby actions (assign role, view role, leave)."""

    game_id: int
    action: str  # "assign" | "myrole" | "leave" | "refresh"


class GameControlCB(CallbackData, prefix="gctl"):
    """Creator-only in-lobby / in-game controls."""

    game_id: int
    action: str  # "start" | "finish" | "roster" | "status"


class RoleInfoCB(CallbackData, prefix="roleinfo"):
    """Paginated role encyclopaedia navigation ("📖 توضیح نقش‌ها").

    ``action`` is one of:
        * ``"show"``  — show the role at ``index``
        * ``"list"``  — show the full role index (grid of all roles)
        * ``"home"``  — return to the main menu
    ``index`` is the 0-based position of the role in the catalog ordering.
    """

    action: str
    index: int = 0


class MyGamesCB(CallbackData, prefix="mygames"):
    """"📂 بازی‌های من" navigation and per-game management.

    ``action`` is one of:
        * ``"open"``          — open the detail screen for ``game_id``
        * ``"list"``          — back to the games list
        * ``"delete_prompt"`` — ask for delete confirmation (creator only)
        * ``"delete_confirm"``— perform the deletion (creator only)
    """

    action: str
    game_id: int = 0

