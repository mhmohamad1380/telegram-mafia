"""Domain-level exceptions.

Services raise these to signal business-rule violations. Handlers catch them and
translate to user-facing (Persian) messages, keeping the service layer free of
any Telegram/presentation concerns.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain/business errors.

    ``message_fa`` is a ready-to-send, user-facing Persian message.
    """

    message_fa: str = "خطایی رخ داد."

    def __init__(self, message_fa: str | None = None) -> None:
        if message_fa is not None:
            self.message_fa = message_fa
        super().__init__(self.message_fa)


# --- Game lifecycle ---------------------------------------------------------


class GameNotFoundError(DomainError):
    message_fa = "بازی‌ای با این کد پیدا نشد."


class GameNotJoinableError(DomainError):
    message_fa = "امکان ورود به این بازی وجود ندارد."


class GameFullError(DomainError):
    message_fa = "ظرفیت این بازی تکمیل شده است."


class GameAlreadyStartedError(DomainError):
    message_fa = "این بازی قبلاً شروع شده است."


class InvalidGameStateError(DomainError):
    message_fa = "این عملیات در وضعیت فعلی بازی مجاز نیست."


class NotGameCreatorError(DomainError):
    message_fa = "فقط سازنده بازی می‌تواند این کار را انجام دهد."


# --- Roles / setup ----------------------------------------------------------


class InvalidPlayerCountError(DomainError):
    message_fa = "تعداد بازیکنان نامعتبر است."


class RoleSelectionMismatchError(DomainError):
    message_fa = "تعداد نقش‌های انتخاب‌شده باید دقیقاً برابر تعداد بازیکنان باشد."


class NoRolesAvailableError(DomainError):
    message_fa = "نقشی برای تخصیص باقی نمانده است."


class TooManyRolesSelectedError(DomainError):
    """Raised when the creator selected more roles than the player count."""

    message_fa = "تعداد نقش‌های انتخاب‌شده از تعداد بازیکنان بیشتر است."


class TooManyMafiaError(DomainError):
    """Raised when selected mafia roles exceed the standard ratio."""

    message_fa = "تعداد نقش‌های مافیا از مقدار مجاز برای این تعداد بازیکن بیشتر است."


class TooManyCitizensError(DomainError):
    """Raised when selected citizen roles exceed the standard ratio."""

    message_fa = "تعداد نقش‌های شهر از مقدار مجاز برای این تعداد بازیکن بیشتر است."


class TooManyIndependentsError(DomainError):
    """Raised when selected independent roles exceed the allowed maximum."""

    message_fa = "تعداد نقش‌های مستقل از مقدار مجاز برای این تعداد بازیکن بیشتر است."


class RoleNotAvailableForPlayerCountError(DomainError):
    """Raised when a selected role requires more players than the game has.

    Used for roles gated by ``min_players`` (e.g. the Mason group, which is only
    available in large games).
    """

    message_fa = "یکی از نقش‌های انتخاب‌شده برای این تعداد بازیکن مجاز نیست."




# --- Lobby / players --------------------------------------------------------


class PlayerAlreadyJoinedError(DomainError):
    message_fa = "شما قبلاً وارد این بازی شده‌اید."


class PlayerNotInGameError(DomainError):
    message_fa = "شما در این بازی حضور ندارید."


class NumberAlreadyTakenError(DomainError):
    message_fa = "این شماره قبلاً انتخاب شده است. لطفاً شماره دیگری انتخاب کنید."


class NumberAlreadyChosenError(DomainError):
    message_fa = "شما قبلاً شماره خود را انتخاب کرده‌اید."


class RoleAlreadyAssignedError(DomainError):
    message_fa = "نقش شما قبلاً مشخص شده است."


class NumberNotChosenError(DomainError):
    message_fa = "ابتدا باید شماره خود را انتخاب کنید."


# --- Turn-based flow (FIFO) -------------------------------------------------


class LobbyNotCompleteError(DomainError):
    """Raised when a player acts before every seat is filled."""

    message_fa = "هنوز تمام بازیکنان وارد بازی نشده‌اند."


class NotPlayersTurnError(DomainError):
    """Raised when a player acts out of their join order."""

    message_fa = (
        "هنوز نوبت شما نیست.\n\n"
        "لطفاً منتظر بمانید تا بازیکنان قبل از شما نقش خود را دریافت کنند."
    )

