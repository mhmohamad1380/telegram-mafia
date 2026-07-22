"""aiogram FSM state groups for the create-game and join-game flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CreateGameStates(StatesGroup):
    """States for the game-creation wizard (creator)."""

    choose_scenario = State()      # Picking the scenario (game mode)
    choose_player_count = State()  # Awaiting the number of players
    choose_roles = State()         # Selecting roles via inline keyboard
    confirm_summary = State()      # Reviewing the auto-completed composition
    waiting_players = State()      # Roles configured; lobby open




class CustomRoleStates(StatesGroup):
    """States for the custom-role creation wizard ("🛠 نقش‌های من").

    A user builds a private role step by step: name → team → optional
    description. The in-progress values are stashed in the FSM context between
    steps and only persisted once the wizard completes.
    """

    enter_name = State()         # Awaiting the role's Persian name
    choose_team = State()        # Picking the alignment (city/mafia/independent)
    enter_description = State()   # Awaiting an optional description (or skip)


class JoinGameStates(StatesGroup):

    """States for the join-game flow (players, including the creator)."""

    enter_code = State()     # Awaiting the 6-digit game code
    waiting_turn = State()   # In lobby, waiting for the FIFO turn to arrive
    choose_number = State()  # Choosing a seat number (on this player's turn)
    game_ready = State()     # In lobby with number + role

