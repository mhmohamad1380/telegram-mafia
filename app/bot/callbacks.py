"""Typed callback data for inline keyboards (aiogram CallbackData factories)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class RoleToggleCB(CallbackData, prefix="role"):
    """Toggle a role on/off during game-setup role selection.

    ``is_custom`` distinguishes a user-owned custom role from a catalog role.
    This matters because catalog roles and custom roles live in separate tables
    with independent primary-key sequences, so their ids can collide; the flag
    tells the handler which selection bucket (and which id space) ``role_id``
    refers to.
    """

    game_id: int
    role_id: int
    is_custom: bool = False



class RoleSetupActionCB(CallbackData, prefix="rolesetup"):
    """Confirm/cancel actions on the role-selection screen."""

    game_id: int
    action: str  # "confirm" | "cancel"


class ScenarioPickCB(CallbackData, prefix="scpick"):
    """Pick a scenario (game mode) during the create-game wizard."""

    code: str


class PlayerCountCB(CallbackData, prefix="pcount"):
    """Quick-pick a suggested player count."""

    count: int


class RoleModeCB(CallbackData, prefix="rmode"):
    """Pick how roles are handed out during the create-game wizard.

    ``mode`` is a :class:`~app.models.enums.RoleMode` value:
        * ``MANUAL_ROLE_SELECTION`` — classic turn-based draw after the lobby
          fills.
        * ``AUTO_ROLE_ASSIGNMENT`` — every player gets a seat + random role the
          instant they join, with no waiting for others.
    """

    mode: str



class SingleDeviceCB(CallbackData, prefix="sdev"):
    """Actions on the shared single-device ("pass-the-phone") screen.

    All taps happen on the creator's device, so these callbacks are authorised
    by game ownership rather than by the tapping user's identity.

    ``action`` is one of:
        * ``"pick"``   — the current player claims seat ``number`` (draws a role)
        * ``"hide"``   — hide the just-revealed role and advance to the next seat
        * ``"start"``  — begin the game once every seat is filled
        * ``"finish"`` — end the game
        * ``"cancel"`` — abort setup
    ``number`` is the chosen seat (0 when not applicable).
    """

    game_id: int
    action: str
    number: int = 0


class ScenarioInfoCB(CallbackData, prefix="scinfo"):

    """Paginated scenario encyclopaedia navigation ("📚 سناریوها").

    ``action`` is one of:
        * ``"show"`` — show the scenario at ``index``
        * ``"list"`` — show the full scenario index
        * ``"home"`` — return to the main menu
    ``index`` is the 0-based catalog position of the scenario.
    """

    action: str
    index: int = 0



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


class CustomRoleCB(CallbackData, prefix="crole"):
    """"🛠 نقش‌های من" navigation and per-role management.

    ``action`` is one of:
        * ``"list"``          — show the user's custom-role list
        * ``"new"``           — start the create-custom-role wizard
        * ``"open"``          — open the detail screen for ``role_id``
        * ``"delete_prompt"`` — ask for delete confirmation
        * ``"delete_confirm"``— perform the (soft) deletion
        * ``"home"``          — dismiss the card / back to main menu
    ``role_id`` is the target custom role (0 when not applicable).
    """

    action: str
    role_id: int = 0


class CustomRoleTeamCB(CallbackData, prefix="croleteam"):
    """Pick the alignment (team) while creating a custom role.

    ``team`` is a :class:`~app.models.enums.RoleTeam` value.
    """

    team: str


class GameHistoryCB(CallbackData, prefix="ghist"):
    """"📜 تاریخچه بازی‌ها" navigation.

    ``action`` is one of:
        * ``"list"`` — (re)show the history list
        * ``"home"`` — dismiss the card / back to main menu
    """

    action: str


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

