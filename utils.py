"""Yordamchi funksiyalar: matnni normallashtirish (lotin/kirill), telefon, sana, holatlar, formatlash."""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from difflib import SequenceMatcher

from i18n import get_lang, tr
from config import HOURS_PER_PAIR, PAIR_TIMES, SEMESTER_START, TZ

# ---------------------------------------------------------------- matn
_APOSTROPHES = "'`ʻʼ‘’´ʹ′"

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g'", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m",
    "н": "n", "о": "o", "ў": "o'", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'",
    "ь": "", "ы": "i", "э": "e", "ю": "yu", "я": "ya", "і": "i",
}


def translit(text: str) -> str:
    """O'zbek/rus kirill yozuvini lotinga o'giradi (qidiruv uchun)."""
    out = []
    prev = " "
    for ch in text:
        low = ch.lower()
        if low == "е" and not prev.isalpha():
            rep = "ye"  # so'z boshidagi "е" -> "ye" (Ергаш -> Yergash)
        else:
            rep = _CYR.get(low)
        out.append(rep if rep is not None else ch)
        prev = ch
    return "".join(out)


def normalize_text(value) -> str:
    """Qidiruv uchun: kichik harf, lotin, tutuq belgisiz, ortiqcha belgilarsiz."""
    if value is None:
        return ""
    s = translit(str(value).lower())
    for a in _APOSTROPHES:
        s = s.replace(a, "")
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def group_key(value) -> str:
    """Guruh nomlarini solishtirish uchun kalit: 'IQ-21', 'iq 21' -> 'iq21'."""
    return normalize_text(value).replace(" ", "")


def name_score(query_norm: str, name_norm: str) -> float:
    """Qidiruv so'zlari ism bilan qanchalik mos (0..1). Har bir so'z ism boshlanishiga mos kelsa 1.0."""
    q, n = query_norm.split(), name_norm.split()
    if not q or not n:
        return 0.0
    if all(any(t.startswith(qt) for t in n) for qt in q):
        return 1.0
    total = 0.0
    for qt in q:
        total += max(SequenceMatcher(None, qt, t).ratio() for t in n)
    return total / len(q)


def esc(value) -> str:
    return html.escape(str(value), quote=False) if value not in (None, "") else ""


def cell_str(value) -> str:
    """Excel katagini matnga aylantiradi (123456.0 -> '123456')."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


# ---------------------------------------------------------------- telefon
def normalize_phone(value) -> str | None:
    """Istalgan ko'rinishdagi O'zbekiston raqamini 998XXXXXXXXX shakliga keltiradi."""
    digits = re.sub(r"\D", "", cell_str(value))
    if len(digits) < 9:
        return None
    return "998" + digits[-9:]


def split_phones(value) -> list[str]:
    """Bir katakda vergul/nuqta-vergul/yangi qator bilan ajratilgan bir nechta raqam."""
    phones = []
    for part in re.split(r"[,;/\n]+", cell_str(value)):
        p = normalize_phone(part)
        if p and p not in phones:
            phones.append(p)
    return phones


def fmt_phone(phone: str | None) -> str:
    if not phone or len(phone) != 12:
        return phone or ""
    return f"+{phone[:3]} {phone[3:5]} {phone[5:8]} {phone[8:10]} {phone[10:]}"


# ---------------------------------------------------------------- sana va vaqt
WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

_WEEKDAY_ALIASES = {
    "dushanba": 1, "du": 1, "seshanba": 2, "se": 2, "chorshanba": 3, "chor": 3, "ch": 3,
    "payshanba": 4, "pay": 4, "pa": 4, "juma": 5, "ju": 5, "shanba": 6, "sha": 6, "sh": 6,
    "yakshanba": 7, "ya": 7,
    "ponedelnik": 1, "vtornik": 2, "sreda": 3, "chetverg": 4, "pyatnitsa": 5, "subbota": 6, "voskresene": 7,
    "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7,
}


def now() -> datetime:
    return datetime.now(TZ)


def today() -> date:
    return now().date()


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def parse_date(value) -> date | None:
    """Excel katagidagi yoki matndagi sanani o'qiydi."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        if 20000 < value < 80000:  # Excel seriya raqami
            return date(1899, 12, 30) + timedelta(days=int(value))
        return None
    s = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%Y.%m.%d",
                "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


_USER_DATE = re.compile(
    r"(?<!\d)(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?!\d)"          # YYYY-MM-DD
    r"|(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)"   # KK.OO.YYYY yoki KK.OO.YY
)


def parse_user_dates(text: str) -> list[date]:
    """Foydalanuvchi yozgan matndan sanalarni (KK.OO.YYYY yoki YYYY-MM-DD) ajratib oladi."""
    result = []
    for m in _USER_DATE.finditer(text or ""):
        if m.group(1):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            d, mo, y = int(m.group(4)), int(m.group(5)), m.group(6)
            y = int(y) + 2000 if len(y) == 2 else int(y)
        try:
            result.append(date(y, mo, d))
        except ValueError:
            continue
    return result


def parse_weekday(value) -> int | None:
    s = cell_str(value)
    if s.isdigit() and 1 <= int(s) <= 7:
        return int(s)
    return _WEEKDAY_ALIASES.get(normalize_text(s))


def parse_time(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return f"{value.hour:02d}:{value.minute:02d}"
    if isinstance(value, float) and 0 <= value < 1:  # Excel vaqt ulushi
        minutes = round(value * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    m = re.search(r"(\d{1,2})[:.](\d{2})", str(value))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def parse_int(value) -> int | None:
    m = re.search(r"\d+", cell_str(value))
    return int(m.group()) if m else None


def parse_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    s = cell_str(value).replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def semester_start() -> date:
    return parse_date(SEMESTER_START) or date(today().year, 9, 1)


def week_bounds(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def week_type_of(d: date) -> str:
    """Semestr boshidan hisoblab toq yoki juft hafta."""
    n = (d - semester_start()).days // 7 + 1
    return "toq" if n % 2 else "juft"


def fmt_date(d: date | str, weekday: bool = True) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    s = d.strftime("%d.%m.%Y")
    return f"{s} ({tr(WEEKDAYS[d.weekday()])})" if weekday else s


def pair_time(pair: int, sched_row: dict | None = None) -> str:
    if sched_row and sched_row.get("start_time"):
        end = sched_row.get("end_time") or ""
        return f"{sched_row['start_time']}–{end}" if end else sched_row["start_time"]
    if pair in PAIR_TIMES:
        return f"{PAIR_TIMES[pair][0]}–{PAIR_TIMES[pair][1]}"
    return ""


def fmt_num(x) -> str:
    x = float(x or 0)
    return str(int(x)) if x.is_integer() else f"{x:.1f}"


def pct(part, whole) -> str:
    return f"{round(100 * part / whole)}%" if whole else "—"


# ---------------------------------------------------------------- davomat holatlari
STATUS_ICON = {"keldi": "✅", "kelmadi": "❌", "sababli": "🟡", "kechikdi": "⏰"}
STATUS_TEXT = {
    "keldi": "qatnashdi",
    "kelmadi": "sababsiz qoldirdi",
    "sababli": "sababli qoldirdi",
    "kechikdi": "kechikdi",
}
_PLUS = {"+", "✓", "✔", "✅", "v"}
_MINUS = {"-", "–", "—", "✗", "✘", "❌", "н", "нб", "nb", "н/б", "n/b"}
_STATUS_ALIASES = {
    "keldi": "keldi", "bor": "keldi", "qatnashdi": "keldi", "qatnashgan": "keldi", "present": "keldi",
    "ha": "keldi", "1": "keldi", "da": "keldi", "prisutstvoval": "keldi",
    "kelmadi": "kelmadi", "yoq": "kelmadi", "sababsiz": "kelmadi", "qoldirdi": "kelmadi",
    "sababsiz qoldirdi": "kelmadi", "absent": "kelmadi", "nb": "kelmadi", "n": "kelmadi", "0": "kelmadi",
    "qatnashmadi": "kelmadi", "kelmagan": "kelmadi", "net": "kelmadi", "otsutstvoval": "kelmadi",
    "sababli": "sababli", "sababli qoldirdi": "sababli", "uzrli": "sababli", "excused": "sababli",
    "sababli kelmadi": "sababli", "uvajitelnaya": "sababli", "kasallik": "sababli",
    "kechikdi": "kechikdi", "kechikkan": "kechikdi", "late": "kechikdi", "opozdal": "kechikdi",
}


def normalize_status(value) -> str | None:
    raw = cell_str(value).lower()
    if raw in _PLUS:
        return "keldi"
    if raw in _MINUS:
        return "kelmadi"
    t = normalize_text(raw)
    if t in _STATUS_ALIASES:
        return _STATUS_ALIASES[t]
    if "sababli" in t or "uzrli" in t:
        return "sababli"
    if "sababsiz" in t or "kelmadi" in t:
        return "kelmadi"
    if "kechik" in t:
        return "kechikdi"
    return None


def split_message(text: str, limit: int = 3900) -> list[str]:
    """Telegram 4096 belgi chegarasi uchun matnni qatorlar bo'yicha bo'ladi."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:  # juda uzun bitta qator
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts


# ---------------------------------------------------------------- rasmiy hujjatlar (PDF)
DOC_TYPES = {  # kalit: (belgi, nomi)
    "tushuntirish": ("📝", "Tushuntirish xati"),
    "ogohlantirish": ("⚠️", "Dekan ogohlantirishi"),
    "hayfsan": ("❗", "Hayfsan"),
    "boshqa": ("📄", "Rasmiy hujjat"),
}
_DOC_KEYWORDS = {
    "hayfsan": ("hayfsan", "xayfsan", "hayfson", "vygovor", "vigovor"),
    "ogohlantirish": ("ogohlantirish", "ogoxlantirish", "preduprezhdenie", "preduprejdenie"),
    "tushuntirish": ("tushuntirish", "tushuntirishi", "obyasnitelnaya", "obyasnitelnoe", "izohnoma"),
}


def doc_title(kind: str) -> str:
    icon, name = DOC_TYPES.get(kind, DOC_TYPES["boshqa"])
    return f"{icon} {tr(name)}"


def detect_doc_type(*texts) -> str | None:
    """Fayl nomi yoki izohdan hujjat turini taxmin qiladi (kurs koordinatori baribir tasdiqlaydi)."""
    words = set(normalize_text(" ".join(t or "" for t in texts)).split())
    for kind, keys in _DOC_KEYWORDS.items():
        if any(w.startswith(k) for w in words for k in keys):
            return kind
    return None


def doc_keywords() -> set[str]:
    return {k for keys in _DOC_KEYWORDS.values() for k in keys}


def fmt_size(n: int | None) -> str:
    if not n:
        return ""
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"



# ---------------------------------------------------------------- HEMIS eksportlari
_LOWER_WORDS = {"ogli", "qizi", "ugli", "kizi", "uli", "qizi", "ulı", "qızı"}
_COURSE_WORDS = {"birinchi": 1, "ikkinchi": 2, "uchinchi": 3, "tortinchi": 4, "beshinchi": 5, "oltinchi": 6,
                 "pervyy": 1, "vtoroy": 2, "tretiy": 3, "chetvertyy": 4}


def is_masked(value) -> bool:
    """HEMIS eksportida yashirilgan qiymat: «***», «+99899*****15» va h.k."""
    return "**" in cell_str(value)


def nice_name(name: str) -> str:
    """«G‘ANIJONOV SHAXRIYOR O‘G‘LI» → «G‘anijonov Shaxriyor o‘g‘li»; aralash yozilgan ism o'zgarmaydi."""
    name = " ".join(cell_str(name).split())
    letters = [ch for ch in name if ch.isupper() or ch.islower()]  # «ʻ» kabi modifikator harflar hisobga olinmaydi
    if not letters or not all(ch.isupper() for ch in letters):
        return name
    out = []
    for w in name.split(" "):
        if w.upper() == "XXX":  # HEMIS'da otasining ismi yo'q chet ellik talabalar
            continue
        plain = "".join(ch for ch in unicodedata.normalize("NFKD", w) if not unicodedata.combining(ch))
        if normalize_text(plain) in _LOWER_WORDS:
            out.append(w.lower())
        else:
            out.append(w[:1] + w[1:].lower())
    return " ".join(out)


def parse_course(value) -> int | None:
    """«3-kurs», «3», «Ikkinchi kurs» → kurs raqami."""
    n = parse_int(value)
    if n:
        return n
    for w in normalize_text(value).split():
        if w in _COURSE_WORDS:
            return _COURSE_WORDS[w]
    return None



# ---------------------------------------------------------------- fan va kichik guruh nomlari
_ROMAN_NUM = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8"}


def subject_key(name) -> str:
    """Solishtirish uchun fan kaliti: «Fransuz tili I» → «fransuz tili»; «Jahon adabiyoti (c)» → «jahon adabiyoti»."""
    s = re.sub(r"\(.*?\)", " ", cell_str(name))
    return " ".join(t for t in normalize_text(s).split() if t not in _ROMAN_NUM and not t.isdigit())


def subgroup_key(value) -> str | None:
    """«2», «2-kichik guruh», «II» → «2»."""
    s = normalize_text(value)
    if not s:
        return None
    n = parse_int(s)
    if n:
        return str(n)
    return _ROMAN_NUM.get(s.split()[0], s)


# ---------------------------------------------------------------- to'lov shakli va summalar
GRANT, CONTRACT = "Davlat granti", "To'lov-shartnoma"


def normalize_payment_form(value) -> str | None:
    """«Kontrakt», «To‘lov-shartnoma», «контракт» → «To'lov-shartnoma»; «Grant», «бюджет» → «Davlat granti»."""
    t = normalize_text(value)
    if not t:
        return None
    if any(w in t for w in ("grant", "byudjet", "budjet", "davlat buyurtma")):
        return GRANT
    if any(w in t for w in ("kontrakt", "shartnoma", "tolov", "kontrak", "platn")):
        return CONTRACT
    return cell_str(value)


def fmt_money(value) -> str:
    """12345678.5 → «12 345 679 so'm»."""
    if value is None:
        return "—"
    return f"{round(value):,}".replace(",", " ") + " " + tr("so'm")



def fmt_dt(iso: str | None) -> str:
    """«2026-09-24T18:42:07+05:00» → «24.09.2026 18:42»."""
    if not iso:
        return "—"
    d, _, t = str(iso).partition("T")
    parts = d.split("-")
    return f"{parts[2]}.{parts[1]}.{parts[0]}" + (f" {t[:5]}" if t else "") if len(parts) == 3 else str(iso)


_MONTHS_UZ = ("", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr",
              "noyabr", "dekabr")


_MONTHS_RU = ("", "января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря")
_MONTHS_EN = ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
              "November", "December")


def fmt_day_month(d) -> str:
    """date(2026, 9, 30) → «30-sentabr» / «30 сентября» / «30 September» (joriy yil bo'lmasa — yil bilan)."""
    lang = get_lang()
    this_year = d.year == today().year
    if lang == "ru":
        return f"{d.day} {_MONTHS_RU[d.month]}" + ("" if this_year else f" {d.year} г.")
    if lang == "en":
        return f"{d.day} {_MONTHS_EN[d.month]}" + ("" if this_year else f" {d.year}")
    return f"{d.day}-{_MONTHS_UZ[d.month]}" + ("" if this_year else f" {d.year}-yil")



def fmt_gpa(value) -> str:
    """3.6667 → «3,67» (o'zbek va rus tilida vergul bilan)."""
    if value is None:
        return "—"
    return f"{value:.2f}" if get_lang() == "en" else f"{value:.2f}".replace(".", ",")



def lesson_kind(value) -> str | None:
    """Mashg'ulot turi: «leksiya» (ma'ruza, лекция, katta guruh) yoki «seminar» (amaliy, laboratoriya, kichik guruh)."""
    t = normalize_text(value)
    if not t:
        return None
    if any(w in t for w in ("maruza", "leksiya", "lektsiya", "lekciya", "lecture", "katta guruh", "potok")):
        return "leksiya"
    if any(w in t for w in ("seminar", "amaliy", "amaliyot", "practical", "prakti", "kichik guruh", "laborator", "lab")):
        return "seminar"
    return None



def _ru_pairs(p: float) -> str:
    if p != int(p):
        return "пары"
    n = int(p)
    if n % 10 == 1 and n % 100 != 11:
        return "пара"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "пары"
    return "пар"


def fmt_pairs(hours) -> str:
    """Qoldirilgan vaqt juftlik (para) va soatda: 10 soat → «5 para (10 soat)» / «5 пар (10 ч)» / «5 classes (10 h)».
    1 para = HOURS_PER_PAIR soat (standart 2)."""
    h = float(hours or 0)
    p = h / HOURS_PER_PAIR if HOURS_PER_PAIR else h
    lang = get_lang()
    ps, hs = fmt_num(p), fmt_num(h)
    if lang == "en":
        return f"{ps} {'class' if p == 1 else 'classes'} ({hs} h)"
    ps, hs = ps.replace(".", ","), hs.replace(".", ",")  # o'zbek va rus tilida o'nlik vergul bilan
    if lang == "ru":
        return f"{ps} {_ru_pairs(p)} ({hs} ч)"
    return f"{ps} para ({hs} soat)"
