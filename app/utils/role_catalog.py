"""Static, data-driven catalog of all supported mafia roles.

This is the single source of truth for role metadata: Persian display name,
team, a short one-line description, and rich beginner-friendly details
(objective, night/day ability, timing, limitations, interactions, and a
suggested strategy). Optional constraints such as ``min_players`` make role
availability data-driven — the presentation and composition layers read these
fields instead of hard-coding role-name checks, so new roles and scenarios can
be added here without touching program logic.

To add a new role:
    1. add its code to :class:`RoleCode` (and the Alembic enum migration),
    2. add a :class:`RoleDefinition` entry here.

Everything else (seeding, selection keyboard, gating, ``/roles`` help) picks it
up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import RoleCode, RoleTeam


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """Immutable metadata describing a single role.

    Attributes:
        code: Canonical, language-independent identifier.
        name_fa: Persian display name.
        team: Alignment (city / mafia / independent / mason).
        description: One-line summary (stored in the DB and shown in menus).
        objective: The role's win condition / goal, in plain language.
        night_ability: What the role can do at night.
        day_ability: What the role can do during the day (if anything).
        timing: When/how often the ability may be used.
        limitations: Notable constraints/cooldowns for beginners.
        interactions: How the role interacts with other roles (if notable).
        strategy: Beginner-friendly tips for playing the role well.
        min_players: Minimum player count required for this role to be
            selectable (``None`` = always available). Data-driven gating.
    """

    code: RoleCode
    name_fa: str
    team: RoleTeam
    description: str
    objective: str | None = None
    night_ability: str | None = None
    day_ability: str | None = None
    timing: str | None = None
    limitations: str | None = None
    interactions: str | None = None
    strategy: str | None = None
    min_players: int | None = None


#: Minimum players required to enable the whole Mason group.
MASON_MIN_PLAYERS = 15


# Ordered catalog; order is used when rendering the role-selection keyboard.
ROLE_CATALOG: tuple[RoleDefinition, ...] = (
    # --- Citizens (شهروند) ---
    RoleDefinition(
        RoleCode.CITIZEN,
        "شهروند ساده",
        RoleTeam.CITIZEN,
        "شهروند عادی بدون قدرت ویژه.",
        objective="کمک به شهر برای شناسایی و حذف تمام مافیاها.",
        night_ability="در شب کاری انجام نمی‌دهد؛ فقط می‌خوابد.",
        day_ability="در روز بحث و گفتگو می‌کند و به مافیای مشکوک رأی می‌دهد.",
        timing="فقط در روز و هنگام رأی‌گیری نقش‌آفرینی می‌کند.",
        limitations="هیچ قدرت ویژه‌ای ندارد و تنها سلاحش منطق و رأی اوست.",
        strategy="با دقت به صحبت‌ها گوش بده، تناقض‌ها را پیدا کن و عجولانه رأی نده.",
    ),
    RoleDefinition(
        RoleCode.DOCTOR,
        "دکتر",
        RoleTeam.CITIZEN,
        "هر شب یک نفر را از مرگ نجات می‌دهد.",
        objective="زنده نگه‌داشتن نقش‌های کلیدی شهر و شکست مافیا.",
        night_ability="هر شب یک بازیکن را انتخاب می‌کند؛ اگر آن شب هدف شلیک مافیا شود، زنده می‌ماند.",
        timing="هر شب یک‌بار.",
        limitations="در اکثر سناریوها نمی‌تواند دو شب پشت‌سرهم یک نفر (یا خودش) را نجات دهد.",
        interactions="می‌تواند شلیک مافیا و در برخی سناریوها شلیک تک‌تیرانداز را خنثی کند.",
        strategy="نقش‌های مهمی که لو رفته‌اند را نجات بده، اما الگوی قابل‌پیش‌بینی نساز.",
    ),
    RoleDefinition(
        RoleCode.DETECTIVE,
        "کارآگاه",
        RoleTeam.CITIZEN,
        "هر شب هویت (مافیا/شهر بودن) یک بازیکن را استعلام می‌کند.",
        objective="یافتن مافیاها و هدایت رأی‌گیری روز به سمت آن‌ها.",
        night_ability="هر شب یک نفر را انتخاب می‌کند و گرداننده مافیا یا شهر بودن او را اعلام می‌کند.",
        timing="هر شب یک‌بار.",
        limitations="نمی‌تواند نقش دقیق را بفهمد، فقط تیم را تشخیص می‌دهد.",
        interactions="گادفادر برای او «شهروند» دیده می‌شود و وکیل می‌تواند مافیا را از دید او پنهان کند.",
        strategy="اطلاعاتت را زود لو نده تا هدف شب مافیا نشوی؛ در زمان مناسب افشا کن.",
    ),
    RoleDefinition(
        RoleCode.SNIPER,
        "تک‌تیرانداز",
        RoleTeam.CITIZEN,
        "می‌تواند شب‌ها به یک بازیکن شلیک کند.",
        objective="کشتن مافیاها با شلیک دقیق و کمک به برد شهر.",
        night_ability="یک یا چند بار در طول بازی می‌تواند شب به یک بازیکن شلیک کند.",
        timing="تعداد محدودی تیر در کل بازی (بسته به سناریو).",
        limitations="اگر به اشتباه به شهروند شلیک کند، در برخی سناریوها خودش می‌میرد. تعداد تیرها محدود است.",
        interactions="شلیک او ممکن است توسط دکتر یا زره‌پوش خنثی شود.",
        strategy="تا از هدفت مطمئن نشده‌ای شلیک نکن؛ یک تیر اشتباه می‌تواند بازی را ببازد.",
    ),
    RoleDefinition(
        RoleCode.PSYCHOLOGIST,
        "روانشناس",
        RoleTeam.CITIZEN,
        "می‌تواند یک بازیکن را برای روز بعد ساکت کند.",
        objective="خنثی‌کردن بازیکنان خطرناک مافیا با ساکت‌کردن آن‌ها.",
        night_ability="هر شب یک نفر را انتخاب می‌کند؛ آن بازیکن روز بعد حق صحبت ندارد.",
        timing="هر شب یک‌بار.",
        limitations="معمولاً نمی‌تواند دو شب پیاپی یک نفر را ساکت کند.",
        strategy="کسی را ساکت کن که فکر می‌کنی مافیای سخنور و اثرگذار است.",
    ),
    RoleDefinition(
        RoleCode.IRONCLAD,
        "رویین‌تن",
        RoleTeam.CITIZEN,
        "یک بار در برابر شلیک مافیا مقاوم است.",
        objective="زنده ماندن و کمک به شهر با استفاده از جان اضافه.",
        night_ability="نیاز به اقدام شبانه ندارد؛ قدرتش انفعالی است.",
        timing="به‌صورت خودکار در اولین حمله فعال می‌شود.",
        limitations="محافظت او معمولاً فقط یک‌بار عمل می‌کند و بعد از آن مثل شهروند ساده است.",
        strategy="می‌توانی کمی جسورتر بازی کنی چون یک جان اضافه داری، اما زیاده‌روی نکن.",
    ),
    RoleDefinition(
        RoleCode.ARMORED,
        "زره‌پوش",
        RoleTeam.CITIZEN,
        "دارای زره محافظ در برابر شلیک است.",
        objective="جذب شلیک‌های مافیا و بقای بیشتر شهر.",
        night_ability="قدرت انفعالی؛ زره او یک یا چند شلیک را جذب می‌کند.",
        timing="به‌صورت خودکار هنگام حمله.",
        limitations="پس از اتمام زره، آسیب‌پذیر می‌شود.",
        strategy="از مقاومتت آگاه باش ولی هویتت را بی‌دلیل فاش نکن.",
    ),
    RoleDefinition(
        RoleCode.PRIEST,
        "کشیش",
        RoleTeam.CITIZEN,
        "می‌تواند نقش یک بازیکن اعدام‌شده را برای شهر آشکار/پاک کند.",
        objective="روشن‌کردن حقیقت درباره بازیکنان و هدایت شهر.",
        night_ability="بسته به سناریو می‌تواند وضعیت یک بازیکن را تغییر دهد یا اطلاعاتی به دست آورد.",
        timing="تعداد استفاده محدود.",
        limitations="تعداد استفاده محدود است.",
        strategy="از قدرت محدودت در لحظات حساس و تعیین‌کننده استفاده کن.",
    ),
    RoleDefinition(
        RoleCode.JUDGE,
        "قاضی",
        RoleTeam.CITIZEN,
        "می‌تواند یک‌بار رأی‌گیری ویژه یا سکوت در روز اعلام کند.",
        objective="مدیریت روند روز به نفع شهر.",
        day_ability="یک‌بار در طول بازی می‌تواند روند رأی‌گیری روز را تغییر دهد.",
        timing="فقط یک‌بار در کل بازی.",
        limitations="فقط یک‌بار قابل استفاده است.",
        strategy="قدرتت را برای روزی نگه دار که رأی‌گیری واقعاً سرنوشت‌ساز است.",
    ),
    RoleDefinition(
        RoleCode.MAYOR,
        "شهردار",
        RoleTeam.CITIZEN,
        "رأی او در روز دو برابر حساب می‌شود.",
        objective="استفاده از وزن رأی برای حذف مافیا.",
        day_ability="در رأی‌گیری روز، رأی او ارزش دوبرابری دارد.",
        timing="در هر رأی‌گیری روز.",
        limitations="هویتش را باید با احتیاط فاش کند تا هدف مافیا نشود.",
        strategy="زمان درست افشای نقش مهم است؛ خیلی زود لو نرو تا کشته نشوی.",
    ),
    RoleDefinition(
        RoleCode.GUARDIAN,
        "محافظ",
        RoleTeam.CITIZEN,
        "هر شب از یک بازیکن محافظت می‌کند.",
        objective="محافظت از نقش‌های کلیدی شهر در برابر حمله.",
        night_ability="هر شب یک بازیکن را انتخاب می‌کند تا از او در برابر حمله محافظت کند.",
        timing="هر شب یک‌بار.",
        limitations="معمولاً نمی‌تواند از خودش محافظت کند.",
        interactions="نقش او شبیه دکتر است اما ممکن است در برابر انواع دیگری از حمله عمل کند.",
        strategy="بازیکنانی که احتمال هدف‌شدنشان بالاست را پوشش بده.",
    ),
    RoleDefinition(
        RoleCode.REPORTER,
        "خبرنگار",
        RoleTeam.CITIZEN,
        "می‌تواند اطلاعاتی درباره یک بازیکن به شهر منتشر کند.",
        objective="انتشار اطلاعات درست برای کمک به شهر.",
        night_ability="هر شب یک نفر را بررسی می‌کند و خبری (مثلاً تیم او) به‌صورت عمومی منتشر می‌شود.",
        timing="هر شب یک‌بار.",
        limitations="اطلاعات منتشرشده را مافیا هم می‌بیند.",
        strategy="بدان که خبرت عمومی است؛ گاهی سکوت بهتر از افشای زودهنگام است.",
    ),
    RoleDefinition(
        RoleCode.ENCHANTER,
        "افسونگر",
        RoleTeam.CITIZEN,
        "هر شب یک بازیکن را افسون می‌کند تا قدرت شبانه‌اش را از دست بدهد.",
        objective="خنثی‌کردن قدرت‌های خطرناک شب (به‌ویژه مافیا) به سود شهر.",
        night_ability="هر شب یک بازیکن را انتخاب می‌کند؛ آن بازیکن آن شب نمی‌تواند از قدرت شبانه‌اش استفاده کند.",
        timing="هر شب یک‌بار.",
        limitations="معمولاً نمی‌تواند دو شب پیاپی یک نفر را هدف بگیرد و نمی‌داند نقش هدف چیست.",
        interactions="نسخه شهری ناتاشا است؛ می‌تواند قدرت مافیای فعال شب را برای یک شب قفل کند.",
        strategy="روی بازیکنانی تمرکز کن که رفتار شبانه مشکوک دارند تا قدرت مافیا را بگیری.",
    ),
    RoleDefinition(
        RoleCode.NATO,
        "ناتو",
        RoleTeam.CITIZEN,
        "با اعلام هشدار، شلیک‌های آن شب را خنثی/منحرف می‌کند.",
        objective="جلوگیری از کشته‌شدن شهروندان در شب‌های بحرانی.",
        night_ability="یک یا چند بار در بازی می‌تواند «حالت دفاعی» اعلام کند تا شلیک آن شب بی‌اثر شود.",
        timing="تعداد استفاده محدود در کل بازی.",
        limitations="پس از پایان دفعات مجاز، دیگر قدرتی ندارد؛ ممکن است قدرت‌های مفید شهر را هم خنثی کند.",
        interactions="می‌تواند شلیک مافیا و حتی تیر تک‌تیرانداز را در همان شب بی‌اثر کند.",
        strategy="قدرتت را برای شبی نگه دار که احتمال حمله بالاست، نه شب‌های آرام.",
    ),
    RoleDefinition(
        RoleCode.COMMANDO,
        "تکاور",
        RoleTeam.CITIZEN,
        "شب‌ها می‌تواند به یک بازیکن حمله کند و در برابر یک حمله مقاوم است.",
        objective="حذف مستقیم مافیا با قدرت رزمی و بقا در برابر حملات.",
        night_ability="می‌تواند شب یک بازیکن را هدف حمله قرار دهد؛ همچنین در برابر اولین حمله به خودش مقاوم است.",
        timing="حمله معمولاً محدود؛ مقاومت یک‌بار.",
        limitations="اگر به شهروند حمله کند به شهر ضربه می‌زند؛ مقاومتش پس از یک‌بار تمام می‌شود.",
        interactions="مانند نسخه تهاجمی‌تر تک‌تیرانداز عمل می‌کند و می‌تواند از خودش دفاع کند.",
        strategy="محتاط باش؛ فقط وقتی به مافیا بودن هدف مطمئنی حمله کن.",
    ),
    RoleDefinition(
        RoleCode.WATCHMAN,
        "نگهبان",
        RoleTeam.CITIZEN,
        "هر شب یک بازیکن را زیر نظر می‌گیرد و از مراجعه‌کنندگان به او باخبر می‌شود.",
        objective="جمع‌آوری اطلاعات درباره فعالیت‌های شبانه برای کشف مافیا.",
        night_ability="هر شب یک نفر را انتخاب می‌کند و متوجه می‌شود چه کسانی آن شب به سراغ او رفته‌اند (بدون اطلاع از نقش‌ها).",
        timing="هر شب یک‌بار.",
        limitations="فقط رفت‌وآمد را می‌بیند، نه نقش یا نیت افراد را.",
        interactions="اطلاعاتش مکمل کارآگاه است و می‌تواند تیم مافیا را از روی رفتار شبانه لو دهد.",
        strategy="بازیکنانی را رصد کن که احتمال هدف‌بودنشان زیاد است تا مهاجمان را ببینی.",
    ),
    RoleDefinition(
        RoleCode.GUNNER,
        "تفنگدار",
        RoleTeam.CITIZEN,
        "دو نوع گلوله دارد: گلوله اصلی (کشنده) و گلوله مشقی (بی‌اثر).",
        objective="واگذاری گلوله‌ها به بازیکنان برای کمک به شهر در حذف مافیا.",
        day_ability=(
            "تفنگدار دو گلوله در اختیار دارد و آن‌ها را به بازیکنان می‌دهد: "
            "«گلوله اصلی» که واقعی و کشنده است و «گلوله مشقی» که فقط ظاهر تفنگ دارد و بی‌اثر است. "
            "گیرنده گلوله می‌تواند در روز به یک نفر شلیک کند اما نمی‌داند گلوله‌اش واقعی است یا مشقی."
        ),
        timing="هر گلوله یک‌بار مصرف است؛ در مجموع دو گلوله (یک اصلی و یک مشقی).",
        limitations=(
            "تفاوت دو گلوله: گلوله اصلی باعث مرگ هدف می‌شود ولی گلوله مشقی هیچ اثری ندارد. "
            "تفنگدار خودش مستقیماً شلیک نمی‌کند و پس از دادن هر دو گلوله دیگر قدرتی ندارد. "
            "اگر گلوله اصلی به دست مافیا بیفتد، ممکن است علیه شهر استفاده شود."
        ),
        interactions=(
            "این نقش مطابق سناریوهای رایج مافیای ایرانی است؛ توزیع درست گلوله‌ها می‌تواند "
            "مافیا را حذف کند یا با گلوله مشقی، بلوف و فشار روانی روی افراد ایجاد کند."
        ),
        strategy=(
            "گلوله اصلی را به کسی بده که به شهری‌بودنش اطمینان داری تا مافیا را بزند؛ "
            "از گلوله مشقی برای محک‌زدن و ایجاد فشار روی افراد مشکوک استفاده کن."
        ),
    ),
    # --- Mafia (مافیا) ---
    RoleDefinition(
        RoleCode.GODFATHER,
        "رئیس مافیا (گادفادر)",
        RoleTeam.MAFIA,
        "رهبر تیم مافیا؛ برای کارآگاه شهروند دیده می‌شود.",
        objective="هدایت مافیا تا برابر یا بیشتر شدن تعداد مافیا و شهر.",
        night_ability="تصمیم نهایی شلیک شبانه مافیا را می‌گیرد.",
        day_ability="در روز مانند یک شهروند بی‌گناه رفتار می‌کند تا لو نرود.",
        timing="هر شب رهبری شلیک مافیا.",
        limitations="اگر کشته شود ضربه بزرگی به مافیا می‌خورد.",
        interactions="اگر کارآگاه او را استعلام کند، نتیجه «شهروند» است.",
        strategy="از مصونیتت در برابر کارآگاه هوشمندانه استفاده کن و خونسرد بمان.",
    ),
    RoleDefinition(
        RoleCode.MAFIA,
        "مافیای ساده",
        RoleTeam.MAFIA,
        "عضو عادی تیم مافیا.",
        objective="همکاری با تیم مافیا برای حذف شهروندان.",
        night_ability="همراه تیم مافیا در تصمیم شلیک شبانه شرکت می‌کند.",
        day_ability="در روز خود را شهروند جا می‌زند و رأی‌ها را منحرف می‌کند.",
        timing="هر شب همراه تیم.",
        limitations="توسط کارآگاه شناسایی می‌شود مگر وکیل از او محافظت کند.",
        interactions="توسط کارآگاه به‌عنوان «مافیا» شناسایی می‌شود مگر وکیل از او محافظت کند.",
        strategy="با شهر هماهنگ به‌نظر برس و بی‌جهت جلب توجه نکن.",
    ),
    RoleDefinition(
        RoleCode.NATASHA,
        "ناتاشا",
        RoleTeam.MAFIA,
        "عضو مافیا با توانایی اغوا کردن یک بازیکن.",
        objective="خنثی‌کردن قدرت‌های شهر برای پیروزی مافیا.",
        night_ability="هر شب می‌تواند یک بازیکن را اغوا کند تا قدرت شبانه‌اش را از دست بدهد.",
        timing="هر شب یک‌بار.",
        limitations="معمولاً نمی‌تواند دو شب پیاپی یک نفر را هدف بگیرد.",
        interactions="می‌تواند قدرت نقش‌های کلیدی شهر مثل دکتر یا کارآگاه را برای یک شب غیرفعال کند.",
        strategy="نقش‌های کلیدی شهر را هدف بگیر تا دفاع شهر فلج شود.",
    ),
    RoleDefinition(
        RoleCode.NEGOTIATOR,
        "مذاکره‌کننده",
        RoleTeam.MAFIA,
        "می‌تواند یک بازیکن را به تیم مافیا جذب کند.",
        objective="افزایش تعداد مافیا با جذب شهروندان.",
        night_ability="یک‌بار در طول بازی می‌تواند یک شهروند ساده را به مافیا تبدیل کند.",
        timing="فقط یک‌بار در کل بازی.",
        limitations="روی نقش‌های ویژه معمولاً اثر ندارد و فقط یک‌بار قابل استفاده است.",
        strategy="زمانی جذب کن که یک نفر مافیای اضافه بیشترین تأثیر را دارد.",
    ),
    RoleDefinition(
        RoleCode.BOMBER,
        "بمب‌گذار",
        RoleTeam.MAFIA,
        "می‌تواند روی یک بازیکن بمب کار بگذارد.",
        objective="کشتن بازیکنان شهر با انفجار بمب.",
        night_ability="یک بازیکن را بمب‌گذاری می‌کند؛ در صورت فعال شدن، آن بازیکن (و گاهی اطرافیان) کشته می‌شوند.",
        timing="تعداد بمب محدود.",
        limitations="تعداد بمب‌ها محدود است.",
        strategy="بمب را روی افراد مهم شهر بگذار تا بیشترین آسیب را بزنی.",
    ),
    RoleDefinition(
        RoleCode.LAWYER,
        "وکیل",
        RoleTeam.MAFIA,
        "از یک هم‌تیمی مافیا در برابر استعلام کارآگاه محافظت می‌کند.",
        objective="پنهان‌کردن مافیا از دید شهر.",
        night_ability="هر شب یک مافیا را انتخاب می‌کند تا برای کارآگاه «شهروند» دیده شود.",
        timing="هر شب یک‌بار.",
        limitations="فقط دید کارآگاه را فریب می‌دهد، جلوی کشته‌شدن را نمی‌گیرد.",
        interactions="مکمل کارآگاه در جبهه مقابل است و باعث گمراهی او می‌شود.",
        strategy="مافیایی را پوشش بده که بیشتر در معرض استعلام کارآگاه است.",
    ),
    RoleDefinition(
        RoleCode.KIDNAPPER,
        "گروگان‌گیر",
        RoleTeam.MAFIA,
        "می‌تواند یک بازیکن را برای یک شبانه‌روز از بازی خارج کند.",
        objective="فلج‌کردن نقش‌های شهر با گروگان‌گیری.",
        night_ability="یک بازیکن را گروگان می‌گیرد؛ او تا روز بعد نه رأی می‌دهد و نه قدرت شبانه دارد.",
        timing="هر شب یک‌بار (بسته به سناریو).",
        limitations="گروگان معمولاً نمی‌تواند هدف حمله شب واقع شود.",
        strategy="نقش‌های مؤثر شهر را در روزهای حساس از دور خارج کن.",
    ),
    # --- Independent (مستقل) ---
    RoleDefinition(
        RoleCode.JOKER,
        "جوکر",
        RoleTeam.INDEPENDENT,
        "اگر با رأی مردم اعدام شود، برنده می‌شود.",
        objective="وادار کردن شهر به اعدام خودش با رأی‌گیری.",
        day_ability="تلاش می‌کند شهر را وادار کند به اعدام او رأی دهند.",
        timing="در طول روزها و رأی‌گیری‌ها.",
        limitations="اگر شب کشته شود یا بازی به‌روش دیگری تمام شود، بازنده است.",
        interactions="هدفش مستقل از برد شهر و مافیاست.",
        strategy="آن‌قدر مشکوک رفتار کن که اعدام شوی، اما نه آن‌قدر که شب کشته شوی.",
    ),
    RoleDefinition(
        RoleCode.SERIAL_KILLER,
        "قاتل سریالی",
        RoleTeam.INDEPENDENT,
        "به‌تنهایی بازی می‌کند و هر شب یک نفر را می‌کشد.",
        objective="آخرین بازمانده بازی بودن.",
        night_ability="هر شب مستقل از مافیا یک بازیکن را به قتل می‌رساند.",
        timing="هر شب یک‌بار.",
        limitations="برنده شدنش معمولاً منوط به آخرین بازمانده بودن است.",
        interactions="دشمن هم شهر و هم مافیاست.",
        strategy="تعادل قدرت را زیر نظر بگیر و تهدیدهای بزرگ را حذف کن.",
    ),
    RoleDefinition(
        RoleCode.NOSTRADAMUS,
        "نوستراداموس",
        RoleTeam.INDEPENDENT,
        "با پیش‌بینی درست نقش‌ها امتیاز می‌گیرد.",
        objective="حدس‌زدن درست نقش بازیکنان برای رسیدن به شرط برد.",
        night_ability="هر شب نقش یک بازیکن را حدس می‌زند.",
        timing="هر شب یک‌بار.",
        limitations="شرط برد او بسته به سناریو متفاوت است.",
        strategy="از رفتار و اطلاعات روز برای حدس دقیق‌تر نقش‌ها استفاده کن.",
    ),
    RoleDefinition(
        RoleCode.FREEMASON,
        "فراماسون",
        RoleTeam.INDEPENDENT,
        "عضو فراماسونری (در صورت فعال بودن سناریو).",
        objective="پیشبرد هدف مشترک گروه فراماسون.",
        night_ability="اعضای فراماسون یکدیگر را می‌شناسند و هدف مشترکی دنبال می‌کنند.",
        timing="بسته به سناریو.",
        limitations="فقط در سناریوهایی که این نقش فعال است حضور دارد.",
        strategy="با اعضای هم‌گروه هماهنگ عمل کن.",
    ),
    # --- Mason group (گروه ماسون) — large games only ---
    RoleDefinition(
        RoleCode.MASON_LEADER,
        "رئیس ماسون",
        RoleTeam.MASON,
        "رهبر گروه ماسون؛ اعضای ماسون را می‌شناسد و آن‌ها را هدایت می‌کند.",
        objective="هدایت گروه ماسون در کنار شهر تا شکست کامل مافیا.",
        night_ability="اعضای ماسون را می‌شناسد و می‌تواند شب با آن‌ها هماهنگ شود؛ در برخی سناریوها یک‌بار توان معرفی/تأیید عضو دارد.",
        timing="هر شب امکان هماهنگی؛ قدرت ویژه محدود.",
        limitations="فقط در بازی‌های بزرگ (حداقل ۱۵ بازیکن) قابل استفاده است؛ اگر کشته شود گروه ماسون ضعیف می‌شود.",
        interactions="ماسون‌ها هم‌تیم شهر هستند و با برد شهر برنده می‌شوند؛ مافیا آن‌ها را دشمن می‌داند.",
        strategy="گروهت را بی‌گدار لو نده؛ اطلاعات مشترک ماسون‌ها را هوشمندانه به سود شهر خرج کن.",
        min_players=MASON_MIN_PLAYERS,
    ),
    RoleDefinition(
        RoleCode.MASON,
        "ماسون",
        RoleTeam.MASON,
        "عضو گروه ماسون که سایر اعضای ماسون را می‌شناسد.",
        objective="همکاری با گروه ماسون و شهر برای حذف مافیا.",
        night_ability="شب اعضای هم‌گروه ماسون خود را می‌شناسد و می‌تواند با آن‌ها هماهنگ باشد.",
        timing="آگاهی دائمی از هم‌گروه‌ها.",
        limitations="فقط در بازی‌های بزرگ (حداقل ۱۵ بازیکن) قابل استفاده است؛ قدرت تهاجمی مستقلی ندارد.",
        interactions="چون ماسون‌ها همدیگر را می‌شناسند، یک بلوک مطمئن از شهروندان تشکیل می‌دهند.",
        strategy="از اطمینان به هم‌گروه‌هایت برای ساختن جبهه منسجم علیه مافیا استفاده کن.",
        min_players=MASON_MIN_PLAYERS,
    ),
    RoleDefinition(
        RoleCode.ARCHITECT,
        "معمار",
        RoleTeam.MASON,
        "عضو ویژه گروه ماسون که می‌تواند ارتباط امن میان اعضا برقرار کند.",
        objective="تقویت و حفظ ساختار گروه ماسون در مسیر برد شهر.",
        night_ability="می‌تواند شب ارتباط/هماهنگی امن بین اعضای ماسون ایجاد کند یا در برخی سناریوها یک عضو را بررسی/تأیید کند.",
        timing="هر شب یا تعداد محدود، بسته به سناریو.",
        limitations="فقط در بازی‌های بزرگ (حداقل ۱۵ بازیکن) و در سناریویی که فعال باشد حضور دارد.",
        interactions="نقش پشتیبان گروه ماسون است و انسجام آن‌ها را بالا می‌برد.",
        strategy="با حفظ امنیت گروه، اطلاعات ماسون‌ها را در زمان درست به سود شهر آشکار کن.",
        min_players=MASON_MIN_PLAYERS,
    ),
)

# Fast lookup by role code.
ROLE_BY_CODE: dict[RoleCode, RoleDefinition] = {d.code: d for d in ROLE_CATALOG}


def get_role_definition(code: RoleCode) -> RoleDefinition:
    """Return the :class:`RoleDefinition` for a code (raises ``KeyError`` if absent)."""
    return ROLE_BY_CODE[code]


# Human-readable team labels (Persian) for grouping in menus.
TEAM_LABELS_FA: dict[RoleTeam, str] = {
    RoleTeam.CITIZEN: "شهروند",
    RoleTeam.MAFIA: "مافیا",
    RoleTeam.INDEPENDENT: "مستقل",
    RoleTeam.MASON: "ماسون",
}


def format_role_details(defn: RoleDefinition) -> str:
    """Render a full, beginner-friendly description block for a role.

    Includes the name, team, summary, and any of the optional detail fields that
    are present. Used by the ``/roles`` command and the private role reveal.
    """
    lines = [
        f"🎭 <b>{defn.name_fa}</b>",
        f"🏳️ تیم: {TEAM_LABELS_FA.get(defn.team, defn.team.value)}",
        "",
        f"📝 {defn.description}",
    ]
    if defn.objective:
        lines.append(f"🎯 هدف: {defn.objective}")
    if defn.night_ability:
        lines.append(f"🌙 توانایی شب: {defn.night_ability}")
    if defn.day_ability:
        lines.append(f"☀️ توانایی روز: {defn.day_ability}")
    if defn.timing:
        lines.append(f"⏱️ زمان استفاده: {defn.timing}")
    if defn.limitations:
        lines.append(f"⛔ محدودیت‌ها: {defn.limitations}")
    if defn.interactions:
        lines.append(f"🔗 تعامل با نقش‌ها: {defn.interactions}")
    if defn.strategy:
        lines.append(f"💡 نکته و استراتژی: {defn.strategy}")
    if defn.min_players:
        from app.utils.codes import to_persian_digits

        lines.append(
            f"👥 حداقل بازیکن لازم: {to_persian_digits(defn.min_players)} نفر"
        )
    return "\n".join(lines)
