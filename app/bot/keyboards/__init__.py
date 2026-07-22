"""Keyboard builders for the bot's interactive flows (inline + reply)."""

from app.bot.keyboards.game import (
    build_composition_summary_keyboard,
    build_creator_lobby_keyboard,
    build_in_game_keyboard,
    build_number_keyboard,
    build_player_count_keyboard,
    build_player_lobby_keyboard,
    build_role_selection_keyboard,
    build_waiting_keyboard,
)
from app.bot.keyboards.custom_role import (
    CUSTOM_ROLE_TEAMS,
    TEAM_LABEL_FA,
    build_custom_role_delete_confirm_keyboard,
    build_custom_role_detail_keyboard,
    build_custom_roles_keyboard,
    build_empty_custom_roles_keyboard,
    build_team_picker_keyboard,
)
from app.bot.keyboards.info import (

    GAME_STATUS_LABELS_FA,
    build_delete_confirm_keyboard,
    build_game_detail_keyboard,
    build_my_games_keyboard,
    build_role_index_keyboard,
    build_role_page_keyboard,
)
from app.bot.keyboards.reply import (
    BTN_CANCEL,
    BTN_CREATE_GAME,
    BTN_CUSTOM_ROLES,
    BTN_JOIN_GAME,
    BTN_MY_GAMES,
    BTN_OWNER_TEST,
    BTN_ROLE_INFO,
    BTN_SCENARIOS,
    MAIN_MENU_BUTTONS,
    build_main_menu_keyboard,
)

from app.bot.keyboards.scenario import (
    build_scenario_count_keyboard,
    build_scenario_index_keyboard,
    build_scenario_overview_keyboard,
    build_scenario_page_keyboard,
    build_scenario_picker_keyboard,
)



__all__ = [
    "build_composition_summary_keyboard",
    "build_creator_lobby_keyboard",
    "build_in_game_keyboard",
    "build_number_keyboard",
    "build_player_count_keyboard",
    "build_player_lobby_keyboard",
    "build_role_selection_keyboard",
    "build_waiting_keyboard",
    "build_main_menu_keyboard",
    "build_role_index_keyboard",
    "build_role_page_keyboard",
    "build_my_games_keyboard",
    "build_game_detail_keyboard",
    "build_delete_confirm_keyboard",
    "GAME_STATUS_LABELS_FA",
    "build_custom_roles_keyboard",
    "build_empty_custom_roles_keyboard",
    "build_custom_role_detail_keyboard",
    "build_custom_role_delete_confirm_keyboard",
    "build_team_picker_keyboard",
    "CUSTOM_ROLE_TEAMS",
    "TEAM_LABEL_FA",
    "BTN_CANCEL",
    "BTN_CREATE_GAME",
    "BTN_CUSTOM_ROLES",
    "BTN_JOIN_GAME",
    "BTN_MY_GAMES",
    "BTN_OWNER_TEST",
    "BTN_ROLE_INFO",
    "BTN_SCENARIOS",
    "MAIN_MENU_BUTTONS",

    "build_scenario_count_keyboard",
    "build_scenario_index_keyboard",
    "build_scenario_overview_keyboard",
    "build_scenario_page_keyboard",
    "build_scenario_picker_keyboard",
]



