"""The static catalog of built-in scenarios.

This is the single place to add a new scenario: define a
:class:`ScenarioDefinition` here and include it in :data:`SCENARIO_CATALOG`.
The registry, validator, resolver, wizard, and encyclopaedia all read from this
tuple, so no other code changes are needed.

Scenarios come in two flavours:

* **flexible** (classic, commando, gunner, mason, inspector): the creator picks
  any subset of ``allowed_roles`` and the composition service tops up remaining
  slots with simple citizens/mafia using ``ratio_rule``;
* **fixed** (capo): the composition is fully prescribed per player count via
  ``fixed_compositions`` — the creator does not pick roles.
"""

from __future__ import annotations

from app.models.enums import RoleCode
from app.scenarios.definition import ScenarioDefinition, TeamRatioRule

# Common flexible team ratio (classic Iranian ~1 mafia / 3 players).
_CLASSIC_RATIO = TeamRatioRule()

# Roles available to most city-flexible scenarios.
_COMMON_CITY_ROLES: tuple[RoleCode, ...] = (
    RoleCode.CITIZEN,
    RoleCode.DOCTOR,
    RoleCode.DETECTIVE,
    RoleCode.SNIPER,
    RoleCode.PSYCHOLOGIST,
    RoleCode.IRONCLAD,
    RoleCode.ARMORED,
    RoleCode.PRIEST,
    RoleCode.JUDGE,
    RoleCode.MAYOR,
    RoleCode.GUARDIAN,
    RoleCode.REPORTER,
)
_COMMON_MAFIA_ROLES: tuple[RoleCode, ...] = (
    RoleCode.GODFATHER,
    RoleCode.MAFIA,
    RoleCode.NATASHA,
    RoleCode.NEGOTIATOR,
    RoleCode.BOMBER,
    RoleCode.LAWYER,
    RoleCode.KIDNAPPER,
    RoleCode.ENCHANTER,
    RoleCode.NATO,
)
_COMMON_INDEP_ROLES: tuple[RoleCode, ...] = (
    RoleCode.JOKER,
    RoleCode.SERIAL_KILLER,
    RoleCode.NOSTRADAMUS,
)


# --- Classic ----------------------------------------------------------------
CLASSIC = ScenarioDefinition(
    code="classic",
    name_fa="کلاسیک",
    description=(
        "سناریوی پایه و همیشگی مافیا. ترکیبی متعادل از نقش‌های شهر و مافیا با "
        "آزادی کامل در انتخاب نقش‌ها. مناسب برای شروع و گروه‌های تازه‌کار."
    ),
    min_players=5,
    max_players=20,
    suggested_counts=(8, 10, 12, 15),
    allowed_roles=_COMMON_CITY_ROLES + _COMMON_MAFIA_ROLES + _COMMON_INDEP_ROLES,
    wake_order=(RoleCode.GODFATHER, RoleCode.DETECTIVE, RoleCode.DOCTOR, RoleCode.SNIPER),
    ratio_rule=_CLASSIC_RATIO,
    team_ratio_text="تقریباً یک مافیا به ازای هر سه بازیکن؛ شهر همیشه در اکثریت شروع می‌کند.",
    win_conditions="شهر با حذف تمام مافیا برنده می‌شود؛ مافیا با برابر شدن تعدادش با شهر.",
    special_rules=(
        "نقش‌های ویژه دلخواه انتخاب می‌شوند و باقی جای‌ها با شهروند/مافیای ساده پر می‌شود.",
    ),
)

# --- Commando (تکاور) -------------------------------------------------------
COMMANDO = ScenarioDefinition(
    code="commando",
    name_fa="تکاور",
    description=(
        "سناریویی تهاجمی که در آن شهر یک «تکاور» جنگی دارد؛ نقشی که می‌تواند شب "
        "حمله کند و در برابر یک حمله مقاوم است. تعادل قدرت به‌نفع اکشن بیشتر است."
    ),
    min_players=8,
    max_players=20,
    suggested_counts=(10, 12, 15),
    allowed_roles=(
        _COMMON_CITY_ROLES
        + (RoleCode.COMMANDO, RoleCode.WATCHMAN)
        + _COMMON_MAFIA_ROLES
        + _COMMON_INDEP_ROLES
    ),
    wake_order=(
        RoleCode.GODFATHER,
        RoleCode.DETECTIVE,
        RoleCode.DOCTOR,
        RoleCode.COMMANDO,
        RoleCode.WATCHMAN,
    ),
    ratio_rule=_CLASSIC_RATIO,
    team_ratio_text="مشابه کلاسیک، اما با حضور تکاور قدرت تهاجمی شهر بیشتر است.",
    win_conditions="شهر با حذف تمام مافیا برنده می‌شود؛ مافیا با برابر شدن تعدادش با شهر.",
    special_rules=(
        "تکاور می‌تواند شب حمله کند و یک‌بار در برابر حمله مقاوم است.",
        "نگهبان می‌تواند مراجعه‌کنندگان شبانه به یک بازیکن را رصد کند.",
    ),
)

# --- Gunner (تفنگدار) -------------------------------------------------------
GUNNER = ScenarioDefinition(
    code="gunner",
    name_fa="تفنگدار",
    description=(
        "سناریوی تفنگدار: شهر یک «تفنگدار» دارد که دو گلوله (اصلی و مشقی) را بین "
        "بازیکنان توزیع می‌کند. بازی پر از بلوف و فشار روانی است."
    ),
    min_players=8,
    max_players=20,
    suggested_counts=(10, 12, 15),
    allowed_roles=(
        _COMMON_CITY_ROLES
        + (RoleCode.GUNNER, RoleCode.WATCHMAN)
        + _COMMON_MAFIA_ROLES
        + _COMMON_INDEP_ROLES
    ),
    wake_order=(RoleCode.GODFATHER, RoleCode.DETECTIVE, RoleCode.DOCTOR),
    ratio_rule=_CLASSIC_RATIO,
    team_ratio_text="مشابه کلاسیک؛ توزیع گلوله‌ها می‌تواند تعادل روز را تغییر دهد.",
    win_conditions="شهر با حذف تمام مافیا برنده می‌شود؛ مافیا با برابر شدن تعدادش با شهر.",
    special_rules=(
        "تفنگدار یک گلوله اصلی (کشنده) و یک گلوله مشقی (بی‌اثر) بین بازیکنان توزیع می‌کند.",
        "گیرنده گلوله نمی‌داند گلوله‌اش واقعی است یا مشقی.",
    ),
)

# --- Mason (ماسون) ----------------------------------------------------------
MASON = ScenarioDefinition(
    code="mason",
    name_fa="ماسون",
    description=(
        "سناریوی بازی‌های بزرگ با گروه «ماسون»؛ دسته‌ای از شهروندان که یکدیگر را "
        "می‌شناسند و یک بلوک مطمئن علیه مافیا تشکیل می‌دهند. فقط برای جمع‌های پرتعداد."
    ),
    min_players=15,
    max_players=25,
    suggested_counts=(15, 18, 20),
    allowed_roles=(
        _COMMON_CITY_ROLES
        + (RoleCode.MASON_LEADER, RoleCode.MASON, RoleCode.ARCHITECT)
        + _COMMON_MAFIA_ROLES
        + _COMMON_INDEP_ROLES
    ),
    wake_order=(
        RoleCode.GODFATHER,
        RoleCode.MASON_LEADER,
        RoleCode.DETECTIVE,
        RoleCode.DOCTOR,
    ),
    ratio_rule=_CLASSIC_RATIO,
    team_ratio_text="مشابه کلاسیک؛ گروه ماسون در کنار شهر محسوب می‌شود.",
    win_conditions="شهر و ماسون‌ها با حذف تمام مافیا برنده می‌شوند؛ مافیا با برابر شدن تعداد.",
    special_rules=(
        "گروه ماسون یکدیگر را می‌شناسند و با برد شهر برنده می‌شوند.",
        "این سناریو حداقل به ۱۵ بازیکن نیاز دارد.",
    ),
)

# --- Inspector (بازپرس) -----------------------------------------------------
INSPECTOR = ScenarioDefinition(
    code="inspector",
    name_fa="بازپرس",
    description=(
        "سناریوی کارآگاه‌محور که تأکید ویژه‌ای بر استعلام و اطلاعات دارد. شهر با "
        "ابزارهای تشخیصی قوی‌تر در برابر مافیای پنهان‌کار می‌ایستد."
    ),
    min_players=8,
    max_players=20,
    suggested_counts=(10, 12, 15),
    allowed_roles=(
        _COMMON_CITY_ROLES
        + (RoleCode.WATCHMAN, RoleCode.REPORTER)
        + _COMMON_MAFIA_ROLES
        + _COMMON_INDEP_ROLES
    ),
    wake_order=(
        RoleCode.GODFATHER,
        RoleCode.LAWYER,
        RoleCode.DETECTIVE,
        RoleCode.WATCHMAN,
        RoleCode.DOCTOR,
    ),
    ratio_rule=_CLASSIC_RATIO,
    team_ratio_text="مشابه کلاسیک، با تمرکز بر نقش‌های اطلاعاتی شهر.",
    win_conditions="شهر با حذف تمام مافیا برنده می‌شود؛ مافیا با برابر شدن تعدادش با شهر.",
    special_rules=(
        "نقش‌های اطلاعاتی (کارآگاه، نگهبان، خبرنگار) نقش پررنگ‌تری دارند.",
        "وکیل مافیا می‌تواند استعلام کارآگاه را گمراه کند.",
    ),
)

# --- Capo (تفنگدار کاپو) — fully fixed, 12/13 players only ------------------
# City-side (12 players): detective, suspect, armorsmith, apothecary, heir,
# kadkhoda, 2x citizen. Mafia: godfather(don), enchanter(witch), nato(hangman),
# reporter?/informer -> we map: witch->ENCHANTER, hangman->NATO, informer->LAWYER.
# 13 players: +1 simple citizen to the city.
_CAPO_MAFIA_12 = {
    RoleCode.GODFATHER: 1,   # دن مافیا
    RoleCode.ENCHANTER: 1,   # جادوگر
    RoleCode.NATO: 1,        # جلاد
    RoleCode.LAWYER: 1,      # خبرچین
}
_CAPO_CITY_12 = {
    RoleCode.DETECTIVE: 1,   # کارآگاه
    RoleCode.SUSPECT: 1,     # مظنون
    RoleCode.ARMORSMITH: 1,  # زره‌ساز
    RoleCode.APOTHECARY: 1,  # عطار
    RoleCode.HEIR: 1,        # وارث
    RoleCode.KADKHODA: 1,    # کدخدا
    RoleCode.CITIZEN: 2,     # شهروند ساده ×۲
}

CAPO = ScenarioDefinition(
    code="capo",
    name_fa="تفنگدار کاپو",
    description=(
        "سناریوی حرفه‌ای و پیچیده «تفنگدار کاپو» با نقش‌های ویژه دن مافیا، جادوگر، "
        "جلاد، خبرچین در تیم مافیا و کارآگاه، مظنون، زره‌ساز، عطار، وارث و کدخدا در "
        "تیم شهر. این سناریو فقط برای ۱۲ یا ۱۳ بازیکن قابل اجراست و ترکیب نقش‌ها "
        "کاملاً از پیش تعیین‌شده است."
    ),
    min_players=12,
    max_players=13,
    suggested_counts=(12, 13),
    # In a fixed scenario the creator does not pick roles; allowed_roles lists
    # every role that appears so the encyclopaedia/keyboards can reference them.
    allowed_roles=(
        RoleCode.GODFATHER,
        RoleCode.ENCHANTER,
        RoleCode.NATO,
        RoleCode.LAWYER,
        RoleCode.DETECTIVE,
        RoleCode.SUSPECT,
        RoleCode.ARMORSMITH,
        RoleCode.APOTHECARY,
        RoleCode.HEIR,
        RoleCode.KADKHODA,
        RoleCode.CITIZEN,
        RoleCode.CITY_TRUSTED,
    ),
    # Night wake order per the scenario spec:
    # 1) mafia team, 2) witch (independent action), 3) armorsmith,
    # 4) detective, 5) apothecary, 6) heir.
    wake_order=(
        RoleCode.GODFATHER,
        RoleCode.ENCHANTER,
        RoleCode.ARMORSMITH,
        RoleCode.DETECTIVE,
        RoleCode.APOTHECARY,
        RoleCode.HEIR,
    ),
    fixed_compositions={
        12: {**_CAPO_MAFIA_12, **_CAPO_CITY_12},
        13: {
            **_CAPO_MAFIA_12,
            **{**_CAPO_CITY_12, RoleCode.CITIZEN: 3},
        },
    },
    team_ratio_text="۴ مافیا در برابر ۸ شهر (۱۲ نفره) یا ۴ مافیا در برابر ۹ شهر (۱۳ نفره).",
    win_conditions=(
        "شهر با حذف کامل تیم مافیا برنده می‌شود؛ مافیا با برابر شدن تعدادش با شهر برنده است."
    ),
    special_rules=(
        "این سناریو فقط برای ۱۲ یا ۱۳ بازیکن قابل انتخاب است.",
        "دن مافیا: استعلام کارآگاه برای او همیشه منفی است، یک پادزهر دارد و می‌تواند یک شهروند ساده یا مظنون را سوداگری کند.",
        "جادوگر همراه تیم مافیا بیدار می‌شود ولی اکشن مستقل دارد؛ روی زره‌ساز/کارآگاه/عطار اثرهای ویژه می‌گذارد.",
        "جلاد عملکردی مشابه ناتو دارد: با حدس درست نقش، هدف بدون توجه به دفاع از بازی خارج می‌شود.",
        "خبرچین جاسوس مافیاست و برای کدخدا شهروند دیده می‌شود.",
        "مظنون عضو شهر است ولی استعلامش مثبت است و هنگام خروج شهروند اعلام می‌شود.",
        "زره‌ساز مانند دکتر عمل می‌کند و فقط یک‌بار می‌تواند خودش را زره کند.",
        "عطار یک زهر و یک پادزهر دارد؛ استفاده از پادزهر با رأی‌گیری شبانه انجام می‌شود.",
        "وارث در شب معارفه یک نفر را انتخاب می‌کند و تا انتقال نقش نامیراست؛ فقط کارآگاه/زره‌ساز/عطار را به ارث می‌برد.",
        "کدخدا می‌تواند دو نفر را به لینک شهر اضافه کند؛ بیدار کردن مافیا (جز خبرچین) او و لینک‌هایش را حذف می‌کند.",
        "پایان روز اول: انتخاب «معتمد شهر» با رأی و اجرای تفنگ کاپو (گلوله جنگی/مشقی به تعیین دن).",
        "اگر دن با تیر جنگیِ معتمد در روز اول کشته شود، پادزهر دن به جادوگر منتقل می‌شود.",
    ),
)


#: The ordered catalog of all built-in scenarios.
SCENARIO_CATALOG: tuple[ScenarioDefinition, ...] = (
    CLASSIC,
    COMMANDO,
    GUNNER,
    MASON,
    INSPECTOR,
    CAPO,
)
