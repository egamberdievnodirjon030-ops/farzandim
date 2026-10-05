"""Bot sozlamalari. Barcha qiymatlar .env faylidan o'qiladi (namuna: .env.example)."""
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", encoding="utf-8-sig")  # Windows Blocknot qo'shadigan BOM belgisiga chidamli


def _int_list(value: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s;]+", value or "") if x.strip().lstrip("-").isdigit()]


def _pair_times(value: str) -> dict[int, tuple[str, str]]:
    """'1=08:30-09:50;2=10:00-11:20' ko'rinishidagi satrni lug'atga aylantiradi."""
    result: dict[int, tuple[str, str]] = {}
    for part in (value or "").split(";"):
        m = re.match(r"\s*(\d+)\s*=\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*$", part)
        if m:
            result[int(m.group(1))] = (m.group(2), m.group(3))
    return result


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# Kurs koordinatorlarining Telegram ID raqamlari, vergul bilan: 123456789,987654321
ADMIN_IDS: set[int] = set(_int_list(os.getenv("ADMIN_IDS", "")))

DB_PATH = str(BASE_DIR / os.getenv("DB_PATH", "data/bot.db"))  # nisbiy yo'l loyiha papkasiga nisbatan
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")


# Ko'p kursli rejim: har bir kurs koordinatori (kurs) — alohida data papka va ma'lumotlar bazasi:
#   data/<kurs>/bot.db. Format: KURSLAR=1-kurs:111111111;2-kurs:222222222,333333333
# (bitta kursni bir nechta koordinator birga yuritishi mumkin). KURSLAR ga yozilmagan ADMIN_IDS dagi har bir
# koordinator o'zining alohida kursini oladi: data/koordinator_<ID>/.
def _slug(name: str) -> str:
    s = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip().lower())
    return s.strip("_") or "kurs"


def _parse_courses(raw: str, admin_order: list[int]) -> tuple[dict[str, list[int]], dict[str, str]]:
    courses: dict[str, list[int]] = {}
    titles: dict[str, str] = {}
    for part in raw.split(";"):
        if ":" not in part:
            continue
        name, _, ids = part.partition(":")
        key = _slug(name)
        titles.setdefault(key, name.strip())
        courses.setdefault(key, [])
        for uid in _int_list(ids):
            if uid not in courses[key]:
                courses[key].append(uid)
    assigned = {u for ids in courses.values() for u in ids}
    for uid in admin_order:
        if uid not in assigned:
            key = f"koordinator_{uid}"
            courses[key], titles[key] = [uid], f"Koordinator {uid}"
            assigned.add(uid)
    return {k: v for k, v in courses.items() if v}, titles


_ADMIN_ORDER = _int_list(os.getenv("ADMIN_IDS", ""))
# .env dagi kurslar — faqat boshlang'ich sozlama: bot birinchi ishga tushganda umumiy ro'yxatga (central.db) yoziladi,
# keyin kurs va koordinatorlar bot ichidan (super-admin) boshqariladi. Quyidagi lug'atlar ishlash vaqtida
# tenancy.reload_registry() tomonidan joyida yangilanadi (barcha modullar shu obyektlarning o'zini ishlatadi).
ENV_COURSES, ENV_COURSE_TITLES = _parse_courses(os.getenv("KURSLAR", ""), _ADMIN_ORDER)
COURSES: dict[str, list[int]] = {k: list(v) for k, v in ENV_COURSES.items()}
COURSE_TITLES: dict[str, str] = dict(ENV_COURSE_TITLES)
ADMIN_IDS.update(u for ids in COURSES.values() for u in ids)  # KURSLAR dagi koordinatorlar ham admin
ADMIN_COURSE: dict[int, str] = {u: k for k, ids in COURSES.items() for u in ids}

# Super-admin: barcha kurslarni boshqaradi (kurs va koordinator qo'shish, zaxira nusxa, xatolar jurnali).
# Faqat .env orqali — xavfsizlik uchun bot ichidan qo'shilmaydi.
SUPERADMIN_IDS: set[int] = set(_int_list(os.getenv("SUPERADMIN_IDS", "")))

# Zaxira nusxa: har kuni belgilangan vaqtda barcha kurs bazalari va central.db — bitta arxivga, super-adminga
BACKUP_DIR = BASE_DIR / os.getenv("BACKUP_DIR", "backups")
BACKUP_TIME = os.getenv("BACKUP_TIME", "03:00")
BACKUP_KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "14"))
BACKUP_PASSWORD = os.getenv("BACKUP_PASSWORD", "").strip()   # bo'lsa — arxiv AES-256 bilan shifrlanadi
BACKUP_SEND = os.getenv("BACKUP_SEND", "1").strip() != "0"    # arxivni super-admin(lar)ga Telegram orqali yuborish

# Loglar: logs/bot.log (hammasi), logs/errors.log (ogohlantirish va xatolar); xatolar super-adminga darhol
LOG_DIR = BASE_DIR / os.getenv("LOG_DIR", "logs")
ALERT_COOLDOWN_MIN = int(os.getenv("ALERT_COOLDOWN_MIN", "10"))  # bir xil xato haqida xabar — shuncha daqiqada bir
TEMPLATES_DIR = BASE_DIR / "shablonlar"
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
UNIVERSITY_NAME = os.getenv("UNIVERSITY_NAME", "Jahon iqtisodiyoti va diplomatiya universiteti")

# Semestr boshlanish sanasi: semestr statistikasi va toq/juft haftalarni hisoblash uchun
SEMESTER_START = os.getenv("SEMESTER_START", "2026-09-01")

# Kunlik xulosa qachon yuboriladi va qaysi kun uchun (0 = shu kun, 1 = kechagi kun)
DAILY_DIGEST_TIME = os.getenv("DAILY_DIGEST_TIME", "19:00")
DIGEST_DAY_OFFSET = int(os.getenv("DIGEST_DAY_OFFSET", "0"))

# Shundan eski qoldirilgan darslar haqida darhol xabar yuborilmaydi (birinchi katta importda spam bo'lmasligi uchun)
NOTIFY_MAX_AGE_DAYS = int(os.getenv("NOTIFY_MAX_AGE_DAYS", "3"))

# Semestr davomida qoldirilgan soatlar chegaralari va har biriga mos chora (universitet ichki tartibi)
ABSENCE_WARN_LEVELS = sorted(set(_int_list(os.getenv("ABSENCE_WARN_LEVELS", "18,36,54,74"))))
ABSENCE_WARN_ACTIONS = [a.strip() for a in os.getenv(
    "ABSENCE_WARN_ACTIONS",
    "Dekan nomiga tushuntirish xati|Dekan ogohlantirishi|Hayfsan|Talabalar safidan chetlatish").split("|")]
# 0 — chegaralarga faqat sababsiz qoldirilgan soatlar hisoblanadi; 1 — sababli soatlar ham qo'shiladi
ABSENCE_COUNT_EXCUSED = os.getenv("ABSENCE_COUNT_EXCUSED", "0").strip() == "1"
# HEMIS davomat statistikasidagi bir birlik necha soat: sonlar juftlikda (para) — 2 (standart), soatda — 1
HEMIS_STATS_HOURS_PER_UNIT = float(os.getenv("HEMIS_STATS_HOURS_PER_UNIT", "2"))
# Bitta fan bo'yicha sababsiz qoldirilgan darslar ulushi (foizda) shundan oshsa ogohlantirish
SUBJECT_WARN_PERCENT = float(os.getenv("SUBJECT_WARN_PERCENT", "25"))
# Umumiy GPA shundan past bo'lsa — talaba kursdan kursga o'tmaydi (GPA yaxlitlanmaydi: 2,599 — o'tmaydi)
GPA_MIN = float(os.getenv("GPA_MIN", "2.6"))
SUBJECT_WARN_MIN_LESSONS = int(os.getenv("SUBJECT_WARN_MIN_LESSONS", "4"))

# Faylda "soat" ustuni bo'lmasa, bitta juftlik necha akademik soat hisoblanadi
HOURS_PER_PAIR = float(os.getenv("HOURS_PER_PAIR", "2"))

# Juftlik vaqtlari (jadval faylida vaqt ko'rsatilmagan hollar uchun).
# Universitetning rasmiy qo'ng'iroq jadvali bo'yicha .env da to'ldiring, masalan:
# PAIR_TIMES=1=08:30-09:50;2=10:00-11:20;3=11:30-12:50
PAIR_TIMES = _pair_times(os.getenv("PAIR_TIMES", ""))

MAX_PENDING_REQUESTS = 3   # bitta ota-onaning bir vaqtdagi tasdiqlanmagan so'rovlari
MAX_OPEN_QUESTIONS = 5     # bitta ota-onaning javobsiz savollari

# Telegram Web App (bot ichida ochiladigan ilova). WEBAPP_URL — ilovaning ochiq HTTPS manzili
# (masalan https://bot.uwed.uz); bo'sh bo'lsa, ilova tugmalari ko'rsatilmaydi, server esa baribir ishlaydi.
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
# Telefon ilovasi (Android APK) — GitHub Releases dan avtomatik olinadi (mobile/README.md). Bo'sh — o'chiq.
APP_RELEASES_REPO = os.getenv("APP_RELEASES_REPO", "egamberdievnodirjon030-ops/farzandim").strip()
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080") or 0)  # 0 — veb-server ishga tushmaydi
WEBAPP_AUTH_TTL = int(os.getenv("WEBAPP_AUTH_TTL", "86400"))  # Telegram imzosi amal qilish muddati, soniya
WEBAPP_DEV_USER = int(os.getenv("WEBAPP_DEV_USER", "0") or 0)  # faqat sinov: brauzerda shu ID bilan kirish

# To'lov muddatidan necha kun oldin qarzdor talabalarning ota-onalariga eslatma yuboriladi va qaysi vaqtda
PAY_REMIND_DAYS = sorted(set(_int_list(os.getenv("PAY_REMIND_DAYS", "7,3,1"))), reverse=True)
PAY_REMIND_TIME = os.getenv("PAY_REMIND_TIME", "10:00")

# ---------------------------------------------------------------- tashqi tizim bilan integratsiya («Manage»)
# Davomat va dars jadvali universitet tizimidan avtomatik olinadi (integration.py). INTEGRATION_URL bo'sh — o'chiq.
# Yo'llarda {from}, {to} (YYYY-MM-DD), {from_ts}, {to_ts} (unix), {since} (oxirgi muvaffaqiyatli olish) ishlatiladi.
INTEGRATION_NAME = os.getenv("INTEGRATION_NAME", "Manage").strip() or "Manage"
INTEGRATION_URL = os.getenv("INTEGRATION_URL", "").strip().rstrip("/")
INTEGRATION_TOKEN = os.getenv("INTEGRATION_TOKEN", "").strip()
# bearer | header:X-API-Key | query:api_key | basic (TOKEN = login:parol) | none
INTEGRATION_AUTH = os.getenv("INTEGRATION_AUTH", "bearer").strip() or "bearer"
INTEGRATION_ATTENDANCE = os.getenv("INTEGRATION_ATTENDANCE", "").strip()
INTEGRATION_SCHEDULE = os.getenv("INTEGRATION_SCHEDULE", "").strip()
INTEGRATION_INTERVAL = max(15, int(os.getenv("INTEGRATION_INTERVAL", "60") or 60))            # davomat, soniya
INTEGRATION_SCHEDULE_INTERVAL = max(60, int(os.getenv("INTEGRATION_SCHEDULE_INTERVAL", "900") or 900))
INTEGRATION_DAYS = max(1, int(os.getenv("INTEGRATION_DAYS", "7") or 7))  # davomat: oxirgi necha kun olinadi
INTEGRATION_PAGE_PARAM = os.getenv("INTEGRATION_PAGE_PARAM", "page").strip()
INTEGRATION_MAX_PAGES = int(os.getenv("INTEGRATION_MAX_PAGES", "500") or 500)
INTEGRATION_TIMEOUT = int(os.getenv("INTEGRATION_TIMEOUT", "60") or 60)
INTEGRATION_HEADERS = os.getenv("INTEGRATION_HEADERS", "").strip()   # qo'shimcha sarlavhalar: «A: 1; B: 2»
# Manage o'zi ma'lumot yuborsa (webhook): POST /api/integration/attendance | /schedule, sarlavha X-Integration-Token
INTEGRATION_WEBHOOK_SECRET = os.getenv("INTEGRATION_WEBHOOK_SECRET", "").strip()
# Birinchi olishda ota-onalarga xabar yuborilmaydi (eski qoldirishlar «yangi» bo'lib ketmasligi uchun)
INTEGRATION_FIRST_SILENT = os.getenv("INTEGRATION_FIRST_SILENT", "1").strip() != "0"
