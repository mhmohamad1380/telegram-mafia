"""Data Transfer Objects (DTOs) exchanged between services and handlers.

These are plain, immutable Pydantic models decoupled from the ORM. Services
build them from ORM entities so handlers never touch SQLAlchemy objects directly
(which also avoids lazy-load / detached-instance issues outside a session).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.enums import GameStatus, PlayerStatus, RoleCode, RoleTeam


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
    """The private role reveal sent to a single player."""

    model_config = ConfigDict(frozen=True)

    code: RoleCode
    name_fa: str
    team: RoleTeam
    description: str | None = None


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


