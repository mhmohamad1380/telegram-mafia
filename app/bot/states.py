"""aiogram FSM state groups for the create-game and join-game flows."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CreateGameStates(StatesGroup):
    """States for the game-creation wizard (creator)."""

    choose_player_count = State()  # Awaiting the number of players
    choose_roles = State()         # Selecting roles via inline keyboard
    confirm_summary = State()      # Reviewing the auto-completed composition
    waiting_players = State()      # Roles configured; lobby open



class JoinGameStates(StatesGroup):
    """States for the join-game flow (players, including the creator)."""

    enter_code = State()     # Awaiting the 6-digit game code
    waiting_turn = State()   # In lobby, waiting for the FIFO turn to arrive
    choose_number = State()  # Choosing a seat number (on this player's turn)
    game_ready = State()     # In lobby with number + role

