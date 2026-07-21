"""ORM models package.

Importing every model here ensures they are all registered on ``Base.metadata``
before Alembic autogenerate or ``create_all`` runs.
"""

from app.models.enums import (
    GameEventType,
    GameStatus,
    PlayerStatus,
    RoleCode,
    RoleTeam,
)
from app.models.game import Game
from app.models.game_event import GameEvent
from app.models.game_player import GamePlayer
from app.models.game_role import GameRole
from app.models.role import Role
from app.models.role_assignment import RoleAssignment
from app.models.user import User

__all__ = [
    # Enums
    "GameEventType",
    "GameStatus",
    "PlayerStatus",
    "RoleCode",
    "RoleTeam",
    # Models
    "Game",
    "GameEvent",
    "GamePlayer",
    "GameRole",
    "Role",
    "RoleAssignment",
    "User",
]
