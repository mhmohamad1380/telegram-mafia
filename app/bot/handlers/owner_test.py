"""Owner-only handler for the "🧪 تست کامل بازی" end-to-end self-test.

Exposes a single entry point — the ``/owner_test`` command (and its main-menu
button) — guarded by :class:`OwnerFilter` so only the configured
``BOT_OWNER_ID`` can reach it. It runs the full real-pipeline game via
:class:`BotOwnerTestFlowService` and edits an in-place "running…" card into the
final structured report.

Everything here is presentation only: the handler never touches the DB or game
rules directly — it delegates to the service and renders the returned
:class:`~app.schemas.game.TestFlowReportDTO`.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot import texts
from app.bot.filters import OwnerFilter
from app.bot.keyboards.reply import BTN_OWNER_TEST
from app.config.logging import get_logger

from app.services import ServiceProvider

logger = get_logger(__name__)

# The whole router is owner-gated: both messages and any future callbacks are
# rejected for non-owners at the router level (defence in depth alongside the
# per-user reply keyboard that only shows the button to the owner).
router = Router(name="owner_test")
router.message.filter(OwnerFilter())


async def _run_owner_test(message: Message, services: ServiceProvider) -> None:
    """Run the full owner test flow and render the result card in place."""
    status = await message.answer(texts.OWNER_TEST_INTRO)
    report = await services.owner_test_flow.run_full_test(
        owner_id=message.from_user.id,  # type: ignore[union-attr]
        owner_display_name=(
            message.from_user.full_name if message.from_user else None
        ),
    )
    await status.edit_text(texts.owner_test_report(report))
    logger.info(
        "owner_test_completed",
        owner_id=message.from_user.id,  # type: ignore[union-attr]
        success=report.success,
    )


@router.message(Command("owner_test"))
async def cmd_owner_test(message: Message, services: ServiceProvider) -> None:
    """``/owner_test`` — run the end-to-end self-test (owner only)."""
    await _run_owner_test(message, services)


@router.message(F.text == BTN_OWNER_TEST)
async def on_menu_owner_test(
    message: Message, services: ServiceProvider
) -> None:
    """Main-menu «🧪 تست کامل بازی» button (owner only)."""
    await _run_owner_test(message, services)
