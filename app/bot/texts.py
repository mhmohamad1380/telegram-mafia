"""Centralized Persian user-facing text and message formatting helpers."""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.game import (
    CompositionResultDTO,
    CustomRoleDTO,
    GameDTO,

    GamePlayerDTO,
    LobbyStateDTO,
    PlayerRoleDTO,
    TeamCompositionDTO,
    TurnStateDTO,
    UserGameDetailDTO,
    UserGameSummaryDTO,
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

ASK_SCENARIO = (
    "🎬 <b>انتخاب سناریو</b>\n\n"
    "ابتدا سناریوی (حالت) بازی را انتخاب کنید. هر سناریو نقش‌ها، تعداد بازیکنان "
    "و قوانین ویژه‌ی خودش را دارد."
)

ASK_PLAYER_COUNT = (
    "👥 <b>تعداد بازیکنان</b>\n\n"
    "یکی از گزینه‌های زیر را انتخاب کنید یا یک عدد دلخواه ارسال کنید (مثلاً ۱۱)."
)

SCENARIOS_INTRO = (
    "📚 <b>دانشنامه سناریوها</b>\n\n"
    "یکی از سناریوها را برای مشاهده‌ی جزئیات کامل انتخاب کنید."
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


# --- Role encyclopaedia ("📖 توضیح نقش‌ها") ----------------------------------

ROLE_INFO_INTRO = (
    "📖 <b>توضیح نقش‌ها</b>\n\n"
    "برای مطالعهٔ توضیح کامل هر نقش، آن را از فهرست زیر انتخاب کنید. "
    "در هر صفحه می‌توانید با دکمه‌های «نقش قبلی/بعدی» بین نقش‌ها جابه‌جا شوید."
)


def role_info_page(*, index: int, total: int, details: str) -> str:
    """Wrap a single role's rendered details with a position indicator."""
    position = f"{to_persian_digits(index + 1)} از {to_persian_digits(total)}"
    return f"{details}\n\n🔢 نقش {position}"


# --- "📂 بازی‌های من" ---------------------------------------------------------

MY_GAMES_EMPTY = (
    "📂 <b>بازی‌های من</b>\n\n"
    "شما در هیچ بازی فعالی حضور ندارید.\n"
    "برای ساخت بازی از «🎲 ساخت بازی» و برای ورود از «🎮 ورود به بازی» استفاده کنید."
)

MY_GAMES_INTRO = (
    "📂 <b>بازی‌های من</b>\n\n"
    "لیست بازی‌هایی که ساخته‌اید یا در آن‌ها حضور دارید. برای مدیریت هر بازی روی "
    "آن بزنید. (نشان 👑 یعنی سازندهٔ آن بازی شما هستید.)"
)


def _status_label(detail: UserGameDetailDTO | UserGameSummaryDTO) -> str:
    # Local import avoids a keyboards<->texts import cycle at module load.
    from app.bot.keyboards.info import GAME_STATUS_LABELS_FA

    return GAME_STATUS_LABELS_FA.get(detail.status, detail.status.value)


def my_game_detail(detail: UserGameDetailDTO) -> str:
    """Full detail screen for one of the user's games.

    Shows lobby progress and the caller's own seat/role status. When the
    assignment phase is under way, it also shows *whose turn* it is by seat
    number and name — never anyone's role.
    """
    role_marker = "👑 سازنده" if detail.is_creator else "🙋 بازیکن"
    lines = [
        "📂 <b>جزئیات بازی</b>\n",
        f"🔑 کد: <code>{detail.code}</code>",
        f"📌 وضعیت: {_status_label(detail)}",
        f"🎭 نقش شما: {role_marker}",
        f"👥 واردشده: {to_persian_digits(detail.joined_count)} از "
        f"{to_persian_digits(detail.player_count)}",
        f"🎯 نقش‌گرفته: {to_persian_digits(detail.assigned_count)} از "
        f"{to_persian_digits(detail.player_count)}",
    ]
    if detail.my_number is not None:
        lines.append(f"🔢 شمارهٔ شما: {to_persian_digits(detail.my_number)}")
    lines.append(
        "✅ نقش خود را دریافت کرده‌اید."
        if detail.has_role
        else "⏳ هنوز نقشی دریافت نکرده‌اید."
    )
    if detail.is_my_turn:
        lines.append("\n🔔 <b>اکنون نوبت شماست!</b>")
    elif detail.current_turn_number is not None:
        who = detail.current_turn_name or "—"
        lines.append(
            f"\n⏳ نوبت فعلی: شمارهٔ "
            f"{to_persian_digits(detail.current_turn_number)} ({who})"
        )
    return "\n".join(lines)


def game_deleted(code: str) -> str:
    return (
        f"🗑 بازی با کد <code>{code}</code> حذف شد.\n"
        "تمام بازیکنان، نقش‌ها و اطلاعات مرتبط آزاد شدند."
    )


def confirm_delete_game(detail: UserGameDetailDTO) -> str:
    return (
        "⚠️ <b>حذف بازی</b>\n\n"
        f"آیا از حذف بازی با کد <code>{detail.code}</code> مطمئن هستید؟\n"
        "این عملیات غیرقابل بازگشت است و تمام بازیکنان و نقش‌ها حذف می‌شوند."
    )


# --- "🛠 نقش‌های من" (custom roles) -------------------------------------------

CUSTOM_ROLES_EMPTY = (
    "🛠 <b>نقش‌های من</b>\n\n"
    "شما هنوز هیچ نقش سفارشی نساخته‌اید.\n"
    "با نقش‌های سفارشی می‌توانید نقش‌های دلخواه خود را برای استفاده در بازی‌ها "
    "تعریف کنید.\n\n"
    "برای ساخت اولین نقش، «➕ ساخت نقش جدید» را بزنید."
)

CUSTOM_ROLES_INTRO = (
    "🛠 <b>نقش‌های من</b>\n\n"
    "لیست نقش‌های سفارشی شما در ادامه آمده است. برای مشاهده یا حذف هر نقش روی "
    "آن بزنید، یا یک نقش تازه بسازید."
)

CUSTOM_ROLE_ASK_NAME = (
    "🛠 <b>ساخت نقش جدید</b>\n\n"
    "نام نقش را وارد کنید (مثلاً: «نگهبان شب»).\n"
    "حداکثر ۶۴ کاراکتر."
)

CUSTOM_ROLE_ASK_TEAM = (
    "🏳️ <b>تیم نقش</b>\n\n"
    "این نقش به کدام تیم تعلق دارد؟"
)

CUSTOM_ROLE_ASK_DESCRIPTION = (
    "📝 <b>توضیحات نقش</b>\n\n"
    "یک توضیح کوتاه برای این نقش بنویسید (اختیاری).\n"
    "اگر نمی‌خواهید توضیحی اضافه کنید، «بدون توضیح» را بنویسید یا از دکمهٔ زیر "
    "استفاده کنید."
)

#: Value the user can type to skip the optional description step.
CUSTOM_ROLE_SKIP_DESCRIPTION = "بدون توضیح"


def custom_role_created(role: CustomRoleDTO) -> str:
    """Confirmation shown after a custom role is saved."""
    # Local import avoids a keyboards<->texts import cycle at module load.
    from app.bot.keyboards.custom_role import TEAM_LABEL_FA

    team_label = TEAM_LABEL_FA.get(role.team, role.team.value)
    text = (
        "✅ <b>نقش سفارشی ساخته شد!</b>\n\n"
        f"🎭 نام: <b>{role.name_fa}</b>\n"
        f"🏳️ تیم: {team_label}"
    )
    if role.description:
        text += f"\n📝 {role.description}"
    return text


def custom_role_detail(role: CustomRoleDTO) -> str:
    """Detail screen for a single custom role."""
    from app.bot.keyboards.custom_role import TEAM_LABEL_FA

    team_label = TEAM_LABEL_FA.get(role.team, role.team.value)
    text = (
        "🛠 <b>جزئیات نقش سفارشی</b>\n\n"
        f"🎭 نام: <b>{role.name_fa}</b>\n"
        f"🏳️ تیم: {team_label}"
    )
    text += f"\n📝 {role.description}" if role.description else "\n📝 بدون توضیح"
    return text


def confirm_delete_custom_role(role: CustomRoleDTO) -> str:
    return (
        "⚠️ <b>حذف نقش سفارشی</b>\n\n"
        f"آیا از حذف نقش «{role.name_fa}» مطمئن هستید؟\n"
        "این عملیات غیرقابل بازگشت است."
    )


def custom_role_deleted(name_fa: str) -> str:
    return f"🗑 نقش سفارشی «{name_fa}» حذف شد."



