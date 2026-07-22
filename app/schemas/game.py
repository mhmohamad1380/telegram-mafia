"""Data Transfer Objects (DTOs) exchanged between services and handlers.

These are plain, immutable Pydantic models decoupled from the ORM. Services
build them from ORM entities so handlers never touch SQLAlchemy objects directly
(which also avoids lazy-load / detached-instance issues outside a session).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    GameStatus,
    PlayerStatus,
    RoleCode,
    RoleMode,
    RoleTeam,
)



class RoleCatalogItemDTO(BaseModel):
    """A role as shown in the selection menu and role list."""

    model_config = ConfigDict(frozen=True)

    role_id: int
    code: RoleCode
    name_fa: str
    team: RoleTeam
    description: str | None = None
    # Minimum player count required to enable this role (None = always). Sourced
    # from the role catalog; drives data-driven gating in the selection UI and
    # the composition service.
    min_players: int | None = None



class CustomRoleDTO(BaseModel):
    """A user-owned custom role as shown in management screens.

    Decoupled from the ORM so handlers can render the owner's roles without a
    live session. Custom roles have no catalog :class:`RoleCode`.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    owner_id: int
    name_fa: str
    team: RoleTeam
    description: str | None = None


class RoleSelectionDTO(BaseModel):

    """A selected role with the chosen quantity during game setup."""

    model_config = ConfigDict(frozen=True)

    role_id: int
    code: RoleCode
    name_fa: str
    team: RoleTeam
    quantity: int


class GameDTO(BaseModel):
    """A game summary."""

    model_config = ConfigDict(frozen=True)

    id: int
    code: str
    creator_id: int
    player_count: int
    status: GameStatus
    #: How roles reach players: manual FIFO turn vs. instant auto-assign on join.
    role_mode: RoleMode = RoleMode.MANUAL_ROLE_SELECTION



class GamePlayerDTO(BaseModel):

    """A player entry in the lobby / roster."""

    model_config = ConfigDict(frozen=True)

    player_id: int
    user_id: int
    display_name: str
    number: int | None
    status: PlayerStatus
    # Role fields are only populated when the caller is allowed to see them
    # (e.g. the roster shown privately to the creator).
    role_code: RoleCode | None = None
    role_name_fa: str | None = None


class PlayerRoleDTO(BaseModel):
    """The private role reveal sent to a single player.

    ``code`` is ``None`` for user-defined custom roles (they have no catalog
    :class:`RoleCode`); ``is_custom`` distinguishes the two for presentation.
    """

    model_config = ConfigDict(frozen=True)

    code: RoleCode | None = None
    name_fa: str
    team: RoleTeam
    description: str | None = None
    is_custom: bool = False



class LobbyStateDTO(BaseModel):
    """Aggregate snapshot of a lobby used to render creator-facing status."""

    model_config = ConfigDict(frozen=True)

    game: GameDTO
    joined_count: int
    assigned_count: int
    taken_numbers: list[int]
    all_assigned: bool


class TurnStateDTO(BaseModel):
    """Snapshot of the sequential (FIFO) turn state of a lobby.

    Used to decide whether a player may act and, if so, whether it is their
    turn. ``current_user_id`` is the Telegram id of the player whose turn it is
    (``None`` once everyone has a role).
    """

    model_config = ConfigDict(frozen=True)

    game: GameDTO
    lobby_complete: bool
    joined_count: int
    current_user_id: int | None = None
    current_join_order: int | None = None


class AssignmentResultDTO(BaseModel):
    """Result of a turn-based role assignment.

    Bundles the private role reveal with the information the presentation layer
    needs to advance the turn: who is next (if anyone) and whether every player
    has now been assigned.
    """

    model_config = ConfigDict(frozen=True)

    role: PlayerRoleDTO
    game: GameDTO
    next_user_id: int | None = None
    all_assigned: bool = False


class PlayerSyncScreenDTO(BaseModel):
    """One waiting player's freshly-computed live lobby screen.

    Produced by :class:`~app.services.live_sync_service.LiveGameSyncService` for
    every player whose lobby message should be edited in place after a state
    change. Carries everything the presentation layer needs to perform the edit
    without any further service calls:

    * ``chat_id`` / ``message_id`` — where to edit (the player's stored message).
    * ``text`` — the new message body.
    * ``kind`` + ``available_numbers`` — describe which keyboard to rebuild:
        - ``"waiting"``: waiting-for-lobby / not-your-turn screen.
        - ``"numbers"``: it's this player's turn to pick a seat number.
        - ``"getrole"``: turn holder who already picked a seat and may now
          draw their role.
    Keyboards are built in the bot layer (services stay Telegram-agnostic).

    """

    model_config = ConfigDict(frozen=True)

    user_id: int
    game_id: int
    chat_id: int
    message_id: int
    text: str
    kind: str  # "waiting" | "numbers"
    available_numbers: list[int] = []


class TestStepResultDTO(BaseModel):
    """One step of the owner test flow with its pass/fail outcome."""

    model_config = ConfigDict(frozen=True)

    #: Machine key, e.g. ``"game_creation"``.
    key: str
    #: Human-friendly label shown in the report, e.g. ``"Game Creation"``.
    label: str
    #: Whether the step succeeded.
    ok: bool
    #: Optional extra detail (error message on failure, summary on success).
    detail: str | None = None


class TestFlowReportDTO(BaseModel):
    """Full result of a :class:`BotOwnerTestFlowService` run.

    Bundles every executed step plus the aggregate outcome so the presentation
    layer can render the "🧪 Test Flow Result" card. ``failed_step`` is the label
    of the first failing step (``None`` on success).
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    steps: list[TestStepResultDTO]
    game_code: str | None = None
    game_id: int | None = None
    player_count: int = 0
    scenario_code: str | None = None
    citizen_count: int = 0
    mafia_count: int = 0
    independent_count: int = 0
    failed_step: str | None = None
    error: str | None = None


class UserGameSummaryDTO(BaseModel):


    """One entry in a user's "📂 بازی‌های من" list.

    Summarises a game the user participates in (as creator or plain member),
    including their own progress (seat number, whether they got a role) so the
    list screen can be rendered without any further lookups.
    """

    model_config = ConfigDict(frozen=True)

    game_id: int
    code: str
    status: GameStatus
    player_count: int
    joined_count: int
    is_creator: bool
    my_number: int | None = None
    has_role: bool = False


class UserGameDetailDTO(BaseModel):
    """Full detail for a single game on the "📂 بازی‌های من" detail screen.

    Extends the summary with lobby progress and the current turn holder (when
    the assignment phase is underway) so a member can see whose turn it is
    without seeing anyone's role. Role names are never included here.
    """

    model_config = ConfigDict(frozen=True)

    game_id: int
    code: str
    status: GameStatus
    player_count: int
    joined_count: int
    assigned_count: int
    is_creator: bool
    my_number: int | None = None
    has_role: bool = False
    # Turn info, populated once the lobby is full and assignment has begun.
    current_turn_number: int | None = None
    current_turn_name: str | None = None
    is_my_turn: bool = False
    # True when the game can be deleted by its creator (i.e. not IN_PROGRESS).
    can_delete: bool = False


class TeamCompositionDTO(BaseModel):

    """Per-team head counts for a game's role composition."""

    model_config = ConfigDict(frozen=True)

    citizen: int
    mafia: int
    independent: int

    @property
    def total(self) -> int:
        return self.citizen + self.mafia + self.independent


class CompositionResultDTO(BaseModel):
    """Outcome of auto-completing a partial role selection.

    ``role_quantities`` is the final ``role_id -> quantity`` mapping (selected
    roles plus any auto-added simple citizens/mafia). ``added`` lists the
    auto-added roles as ``(name_fa, quantity)`` pairs for the summary screen.
    ``roles_ordered`` is the full ordered list of role names for display.
    """

    model_config = ConfigDict(frozen=True)

    role_quantities: dict[int, int]
    composition: TeamCompositionDTO
    roles_ordered: list[str]
    added: list[tuple[str, int]]
    player_count: int


