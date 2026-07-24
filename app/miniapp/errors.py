"""Mini App-specific domain errors.

These subclass the shared :class:`~app.utils.exceptions.DomainError` so the
FastAPI exception handler treats them identically to core errors (HTTP 400 with
the Persian ``message_fa``). They live here — beside the online-play code that
raises them — rather than in the core exceptions module, keeping the Mini App a
self-contained feature layered over the existing domain.
"""

from __future__ import annotations

from app.utils.exceptions import DomainError


class NotTableMemberError(DomainError):
    """Raised when a non-member tries to access an online table."""

    message_fa = "شما عضو این میز نیستید."


class NotSpeakerTurnError(DomainError):
    """Raised when a player acts (mic/challenge) outside their speaking turn."""

    message_fa = "اکنون نوبت صحبت شما نیست."


class ChallengeAlreadyUsedError(DomainError):
    """Raised when a speaker declares a second challenge in one turn."""

    message_fa = "شما در این نوبت قبلاً یک چالش اعلام کرده‌اید."


class NotVotingPhaseError(DomainError):
    """Raised when a vote is cast outside the voting phase."""

    message_fa = "اکنون زمان رأی‌گیری نیست."
