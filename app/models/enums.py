"""Enumerations shared across models, schemas, and services.

These are stored in the database as native PostgreSQL enums (see the mapped
models) and used throughout the domain layer for type-safe comparisons.
"""

from __future__ import annotations

import enum


class GameStatus(str, enum.Enum):
    """Lifecycle status of a game."""

    CREATING = "CREATING"          # Creator is still selecting player count / roles
    WAITING_PLAYERS = "WAITING_PLAYERS"  # Lobby open, players joining
    READY = "READY"               # Everyone joined & got a role, awaiting start
    IN_PROGRESS = "IN_PROGRESS"   # Game started
    FINISHED = "FINISHED"         # Game ended
    CANCELLED = "CANCELLED"       # Aborted before finishing


class RoleMode(str, enum.Enum):
    """How players receive their roles within a game.

    * ``MANUAL_ROLE_SELECTION`` — the classic, turn-based flow: the lobby must
      fill, then players act one at a time to pick a seat number and *draw* a
      random role. This is the default and is unchanged by the auto feature.
    * ``AUTO_ROLE_ASSIGNMENT`` — the instant the player joins they are given a
      free seat number and a random, still-available role automatically, with no
      waiting for the lobby to fill and no manual "get role" step. Used by the
      owner test flow and available when a creator opts in at game creation.
    """

    MANUAL_ROLE_SELECTION = "MANUAL_ROLE_SELECTION"
    AUTO_ROLE_ASSIGNMENT = "AUTO_ROLE_ASSIGNMENT"
    #: On-demand instant reveal. The player taps "🎭 مشاهده نقش" and is given a
    #: seat + random role immediately (idempotent), with no waiting for the lobby
    #: to fill and no FIFO turn. The role pool is auto-completed on first reveal.
    INSTANT_ROLE = "INSTANT_ROLE"



class RoleTeam(str, enum.Enum):

    """The alignment/team a role belongs to.

    ``MASON`` is a distinct group that plays *with* the city (they win when the
    city wins) but forms its own recognisable faction and is only available in
    large games. Keeping it as a separate team lets scenarios and the
    composition strategy reason about it explicitly (data-driven), rather than
    hard-coding role-name checks.
    """

    CITIZEN = "CITIZEN"
    MAFIA = "MAFIA"
    INDEPENDENT = "INDEPENDENT"
    MASON = "MASON"



class GameResult(str, enum.Enum):
    """The per-player outcome of a finished game, used in game history."""

    WIN = "WIN"
    LOSS = "LOSS"
    UNKNOWN = "UNKNOWN"


class PlayerStatus(str, enum.Enum):
    """Status of a player within a game lobby."""


    JOINED = "JOINED"          # In lobby, no seat number chosen yet
    NUMBERED = "NUMBERED"      # Picked a seat number, awaiting role
    ASSIGNED = "ASSIGNED"      # Has a role assigned
    LEFT = "LEFT"              # Left the lobby (seat + role freed)


class GameEventType(str, enum.Enum):
    """Audit event types recorded in the ``game_events`` table."""

    GAME_CREATED = "GAME_CREATED"
    ROLES_CONFIGURED = "ROLES_CONFIGURED"
    PLAYER_JOINED = "PLAYER_JOINED"
    PLAYER_LEFT = "PLAYER_LEFT"
    NUMBER_CHOSEN = "NUMBER_CHOSEN"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    GAME_READY = "GAME_READY"
    GAME_STARTED = "GAME_STARTED"
    GAME_FINISHED = "GAME_FINISHED"
    GAME_CANCELLED = "GAME_CANCELLED"


class RoleCode(str, enum.Enum):
    """Stable identifier for every supported role.

    The display names (in Persian) live in the seed catalog; these codes are the
    canonical, language-independent keys stored in the ``roles`` table.
    """

    # --- Citizens ---
    CITIZEN = "CITIZEN"                # شهروند ساده
    DOCTOR = "DOCTOR"                  # دکتر
    DETECTIVE = "DETECTIVE"            # کارآگاه
    SNIPER = "SNIPER"                  # تک‌تیرانداز
    PSYCHOLOGIST = "PSYCHOLOGIST"      # روانشناس
    IRONCLAD = "IRONCLAD"              # رویین‌تن
    ARMORED = "ARMORED"               # زره‌پوش
    PRIEST = "PRIEST"                  # کشیش
    JUDGE = "JUDGE"                    # قاضی
    MAYOR = "MAYOR"                    # شهردار
    GUARDIAN = "GUARDIAN"              # محافظ
    REPORTER = "REPORTER"              # خبرنگار
    ENCHANTER = "ENCHANTER"            # افسونگر
    NATO = "NATO"                      # ناتو
    COMMANDO = "COMMANDO"              # تکاور
    WATCHMAN = "WATCHMAN"              # نگهبان
    GUNNER = "GUNNER"                  # تفنگدار
    SUSPECT = "SUSPECT"                # مظنون (تفنگدار کاپو)
    ARMORSMITH = "ARMORSMITH"          # زره‌ساز (تفنگدار کاپو)
    APOTHECARY = "APOTHECARY"          # عطار (تفنگدار کاپو)
    HEIR = "HEIR"                      # وارث (تفنگدار کاپو)
    KADKHODA = "KADKHODA"              # کدخدا (تفنگدار کاپو)
    CITY_TRUSTED = "CITY_TRUSTED"      # معتمد شهر (تفنگدار کاپو)


    # --- Mafia ---
    GODFATHER = "GODFATHER"            # رئیس مافیا (گادفادر)
    MAFIA = "MAFIA"                    # مافیای ساده
    NATASHA = "NATASHA"                # ناتاشا
    NEGOTIATOR = "NEGOTIATOR"          # مذاکره‌کننده
    BOMBER = "BOMBER"                  # بمب‌گذار
    LAWYER = "LAWYER"                  # وکیل
    KIDNAPPER = "KIDNAPPER"            # گروگان‌گیر

    # --- Independent ---
    JOKER = "JOKER"                    # جوکر
    SERIAL_KILLER = "SERIAL_KILLER"    # قاتل سریالی
    NOSTRADAMUS = "NOSTRADAMUS"        # نوستراداموس
    FREEMASON = "FREEMASON"            # فراماسون

    # --- Mason group (large games only) ---
    MASON_LEADER = "MASON_LEADER"      # رئیس ماسون
    MASON = "MASON"                    # ماسون
    ARCHITECT = "ARCHITECT"            # معمار

