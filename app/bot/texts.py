"""Centralized Persian user-facing text and message formatting helpers."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.game import (
    CompositionResultDTO,
    GameDTO,
    GamePlayerDTO,
    LobbyStateDTO,
    PlayerRoleDTO,
    TeamCompositionDTO,
    TurnStateDTO,
)
from app.utils.codes import to_persian_digits
from app.utils.role_catalog import TEAM_LABELS_FA




# --- Static strings ---------------------------------------------------------

START = (
    "🎭 <b>ربات مدیریت بازی مافیا</b>\n\n"
    "با این ربات می‌توانید بازی مافیا بسازید، بازیکنان را وارد کنید و نقش‌ها را "
    "به صورت تصادفی توزیع کنید.\n\n"
    "دستورهای اصلی:\n"
    "• /create_game — ساخت بازی جدید\n"
    "• /join — ورود به یک بازی با کد\n"
    "• /roles — مشاهده لیست نقش‌ها\n"
    "• /cancel — لغو عملیات فعلی\n"
    "• /help — راهنما"
)

HELP = (
    "📖 <b>راهنما</b>\n\n"
    "<b>سازنده بازی:</b>\n"
    "۱. دستور /create_game را بزنید.\n"
    "۲. تعداد بازیکنان را انتخاب یا وارد کنید.\n"
    "۳. نقش‌ها را انتخاب کنید (تعداد نقش‌ها باید برابر تعداد بازیکنان باشد).\n"
    "۴. کد ۶ رقمی بازی را دریافت و بین بازیکنان پخش کنید.\n"
    "۵. سازنده نیز باید مثل بقیه با /join وارد شود.\n\n"
    "<b>بازیکنان:</b>\n"
    "۱. دستور /join را بزنید و کد بازی را وارد کنید.\n"
    "۲. یک شماره انتخاب کنید.\n"
    "۳. دکمه «دریافت نقش» را بزنید تا نقش شما به‌صورت خصوصی مشخص شود.\n"
)

ASK_PLAYER_COUNT = (
    "👥 <b>تعداد بازیکنان</b>\n\n"
    "یکی از گزینه‌های زیر را انتخاب کنید یا یک عدد دلخواه ارسال کنید (مثلاً ۱۱)."
)

ASK_GAME_CODE = "🔑 کد ۶ رقمی بازی را وارد کنید:"

CANCELLED = "❌ عملیات لغو شد."

NOTHING_TO_CANCEL = "چیزی برای لغو وجود ندارد."


# --- Dynamic formatters -----------------------------------------------------


def game_created(game: GameDTO) -> str:
    """Message shown to the creator after the game is created."""
    return (
        "✅ <b>بازی ساخته شد!</b>\n\n"
        f"🔑 کد بازی: <code>{game.code}</code>\n"
        f"👥 ظرفیت: {to_persian_digits(game.player_count)} نفر\n\n"
        "این کد را بین بازیکنان پخش کنید. برای ورود، هر بازیکن (از جمله شما) "
        "دستور /join را می‌زند و همین کد را وارد می‌کند."
    )


def role_reveal(role: PlayerRoleDTO) -> str:
    """Private role reveal sent only to the owning player."""
    team_label = TEAM_LABELS_FA.get(role.team, role.team.value)
    text = (
        "🤫 <b>نقش شما</b>\n\n"
        f"🎭 <b>{role.name_fa}</b>\n"
        f"🏳️ تیم: {team_label}"
    )
    if role.description:
        text += f"\n\n📝 {role.description}"
    text += "\n\n⚠️ این نقش را برای کسی فاش نکنید."
    return text


def joined_lobby(game: GameDTO) -> str:
    return (
        "✅ شما وارد بازی شدید.\n\n"
        f"🔑 کد بازی: <code>{game.code}</code>\n"
        "حالا یک شماره برای خود انتخاب کنید:"
    )


def number_chosen(number: int) -> str:
    return (
        f"✅ شماره شما: <b>{to_persian_digits(number)}</b>\n\n"
        "برای دریافت نقش، دکمه «دریافت نقش» را بزنید."
    )


def lobby_status(state: LobbyStateDTO) -> str:
    """Creator-facing lobby status summary."""
    g = state.game
    return (
        "📊 <b>وضعیت بازی</b>\n\n"
        f"🔑 کد: <code>{g.code}</code>\n"
        f"👥 واردشده: {to_persian_digits(state.joined_count)} از "
        f"{to_persian_digits(g.player_count)}\n"
        f"🎭 نقش‌گرفته: {to_persian_digits(state.assigned_count)} از "
        f"{to_persian_digits(g.player_count)}"
    )


def lobby_not_complete(joined: int, player_count: int) -> str:
    """Shown when a player acts before the lobby is full."""
    return (
        "⏳ هنوز تمام بازیکنان وارد بازی نشده‌اند.\n\n"
        f"تعداد فعلی:\n{to_persian_digits(joined)} / {to_persian_digits(player_count)}"
    )


def waiting_for_lobby(state: TurnStateDTO) -> str:
    """Player-facing waiting screen while the lobby is still filling."""
    return (
        "⏳ <b>در انتظار ورود سایر بازیکنان</b>\n\n"
        f"تعداد فعلی: {to_persian_digits(state.joined_count)} / "
        f"{to_persian_digits(state.game.player_count)}\n\n"
        "به محض تکمیل ظرفیت و رسیدن نوبت شما، امکان انتخاب شماره فعال می‌شود."
    )


def not_your_turn() -> str:
    """Shown when a player acts out of their join order."""
    return (
        "🚫 هنوز نوبت شما نیست.\n\n"
        "لطفاً منتظر بمانید تا بازیکنان قبل از شما نقش خود را دریافت کنند."
    )


def your_turn_notice() -> str:
    """Private message sent to the next player when their turn arrives."""
    return (
        "🔔 <b>نوبت شماست!</b>\n\n"
        "نوبت شما برای انتخاب شماره و دریافت نقش رسیده است.\n"
        "برای شروع، دکمه «انتخاب شماره» را بزنید."
    )


def all_assigned_notice() -> str:
    return (
        "🎉 <b>تمام بازیکنان نقش خود را دریافت کردند!</b>\n\n"
        "بازی آماده شروع است."
    )



def game_started() -> str:
    return "▶️ <b>بازی شروع شد!</b>\n\nموفق باشید 🎭"


def game_finished() -> str:
    return "🏁 <b>بازی به پایان رسید.</b>\nتمام منابع آزاد شدند."


def roster(players: Sequence[GamePlayerDTO]) -> str:
    """Creator-only full roster: number, name, and role."""
    if not players:
        return "هیچ بازیکنی در بازی نیست."
    lines = ["📋 <b>لیست بازیکنان</b>\n"]
    for p in players:
        num = to_persian_digits(p.number) if p.number is not None else "—"
        role = p.role_name_fa or "بدون نقش"
        lines.append(f"{num}- {p.display_name}\n   🎭 {role}")
    return "\n".join(lines)


def _team_counts_block(comp: TeamCompositionDTO) -> str:
    """Render the per-team head-count block used in summaries."""
    return (
        f"🏙️ شهر: {to_persian_digits(comp.citizen)} نفر\n"
        f"🔪 مافیا: {to_persian_digits(comp.mafia)} نفر\n"
        f"🎲 مستقل: {to_persian_digits(comp.independent)} نفر"
    )


def composition_summary(result: CompositionResultDTO) -> str:
    """Pre-creation summary: team counts, auto-added roles, and full role list."""
    comp = result.composition
    lines = [
        "🧩 <b>خلاصه ترکیب بازی</b>\n",
        f"👥 بازیکنان: {to_persian_digits(result.player_count)} نفر\n",
        _team_counts_block(comp),
    ]
    if result.added:
        added_parts = [
            f"{name} ×{to_persian_digits(qty)}" for name, qty in result.added
        ]
        lines.append(
            "\n➕ نقش‌های تکمیل‌شده توسط سیستم:\n" + "، ".join(added_parts)
        )
    lines.append("\n" + "—" * 12)
    lines.append("\n🎭 <b>نقش‌ها:</b>")
    for name in result.roles_ordered:
        lines.append(f"• {name}")
    lines.append("\nاگر مورد تایید است، «تایید و ساخت بازی» را بزنید.")
    return "\n".join(lines)


def start_game_summary(comp: TeamCompositionDTO) -> str:
    """Creator-only summary sent when the game starts (team counts only).

    Deliberately omits role names and player names — only the number of members
    on each team is announced.
    """
    return (
        "▶️ <b>بازی شروع شد.</b>\n\n"
        f"👥 تعداد کل بازیکنان: {to_persian_digits(comp.total)}\n"
        f"🏙️ تعداد شهر: {to_persian_digits(comp.citizen)}\n"
        f"🔪 تعداد مافیا: {to_persian_digits(comp.mafia)}\n"
        f"🎲 تعداد مستقل: {to_persian_digits(comp.independent)}"
    )


def roles_catalog(items: Sequence[GamePlayerDTO]) -> str:  # pragma: no cover
    """Deprecated placeholder kept for API symmetry (unused)."""
    return ""

