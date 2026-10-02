"""Ko'p kursli rejim: bitta bot, har bir kurs koordinatori (kurs) uchun alohida data papka va ma'lumotlar bazasi.

    data/<kurs>/bot.db   — kursning talabalari, davomati, baholari, qarzdorligi, hujjatlari, savollari va
                           shu kursga ulangan ota-onalar (har bir kurs ma'lumotlari boshqasidan to'liq ajratilgan)
    data/central.db      — faqat ro'yxat: foydalanuvchi tili, ota-onaning oxirgi ochgan kursi,
                           Telegram guruh qaysi kursga biriktirilgani (talabalar ma'lumoti yo'q)

Joriy kurs har bir so'rov boshida CourseMiddleware tomonidan o'rnatiladi: kurs koordinatori — o'z kursi,
ota-ona — tanlagan farzandining kursi, guruh — biriktirilgan kurs. Kod bazaga odatdagidek `db` orqali murojaat
qiladi, `db` esa joriy kurs bazasiga ulanadi. Bir nechta kurs bo'ylab ishlash (ota-onaning barcha farzandlari,
rejalashtiruvchi) — `for key in course_keys(): with use_course(key): ...`.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from pathlib import Path

import aiosqlite

from config import (ADMIN_COURSE, ADMIN_IDS, COURSE_TITLES, COURSES, ENV_COURSE_TITLES, ENV_COURSES, SUPERADMIN_IDS,
                    _slug)

_current: contextvars.ContextVar[str | None] = contextvars.ContextVar("course", default=None)
current_user: contextvars.ContextVar[int | None] = contextvars.ContextVar("user", default=None)  # loglar uchun


def course_keys() -> list[str]:
    """Sozlangan kurslar (KURSLAR va ADMIN_IDS bo'yicha), .env dagi tartibda."""
    return list(COURSES)


def current_course() -> str | None:
    return _current.get()


def set_course(key: str | None) -> None:
    _current.set(key)


@contextmanager
def use_course(key: str | None):
    token = _current.set(key)
    try:
        yield
    finally:
        _current.reset(token)


def course_of_admin(user_id: int) -> str | None:
    return ADMIN_COURSE.get(user_id)


def course_title(key: str | None = None) -> str:
    key = key or current_course()
    return COURSE_TITLES.get(key, key or "")


def course_admins(key: str | None = None) -> set[int]:
    """Joriy (yoki berilgan) kursning koordinatorlari. Kursda koordinator bo'lmasa — super-admin(lar)
    (boshqa kurslarning koordinatorlariga emas: kurslar ma'lumotlari aralashmasin)."""
    key = key or current_course()
    if key in COURSES:
        return set(COURSES[key]) or set(SUPERADMIN_IDS)
    return set(SUPERADMIN_IDS) or set(ADMIN_IDS)


# ---------------------------------------------------------------- rollar
def is_super(user_id: int) -> bool:
    return user_id in SUPERADMIN_IDS


def is_coordinator(user_id: int) -> bool:
    return user_id in ADMIN_COURSE


def is_staff(user_id: int) -> bool:
    """Kurs koordinatori yoki super-admin — ota-ona menyusi ko'rsatilmaydi, admin buyruqlari ishlaydi."""
    return is_super(user_id) or is_coordinator(user_id)


def default_course() -> str | None:
    keys = course_keys()
    return keys[0] if keys else None


# ---------------------------------------------------------------- umumiy ro'yxat (central.db)
CENTRAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_prefs (
    tg_id INTEGER PRIMARY KEY,
    lang  TEXT NOT NULL DEFAULT 'uz'
);
-- Ota-onaning oxirgi ochgan kursi (farzandlari turli kurslarda bo'lsa, menyu tugmalari shu kursda ishlaydi)
CREATE TABLE IF NOT EXISTS active_course (
    tg_id      INTEGER PRIMARY KEY,
    course     TEXT NOT NULL,
    updated_at TEXT
);
-- Raqamini tasdiqlagan, lekin farzandi hali hech qaysi kursda topilmagan ota-ona: qo'lda bog'lash so'rovi
-- yuborilgach yoki kurs koordinatori uning raqamini yuklagach — o'sha kurs bazasiga yoziladi
CREATE TABLE IF NOT EXISTS pending_parents (
    tg_id      INTEGER PRIMARY KEY,
    phone      TEXT NOT NULL,
    name       TEXT,
    created_at TEXT
);
-- Fan, fakultet va boshqa atamalarning tarjimalari (kurs koordinatori kiritadi, barcha kurslar uchun umumiy)
CREATE TABLE IF NOT EXISTS term_translations (
    term_key   TEXT PRIMARY KEY,
    uz         TEXT NOT NULL,
    ru         TEXT,
    en         TEXT,
    updated_at TEXT
);
-- Kurslar va kurs koordinatorlari (bot ichidan boshqariladi; .env — faqat boshlang'ich sozlama)
CREATE TABLE IF NOT EXISTS courses (
    key        TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    sort       INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS coordinators (
    user_id    INTEGER PRIMARY KEY,
    course_key TEXT NOT NULL,
    name       TEXT,
    active     INTEGER NOT NULL DEFAULT 1,   -- 0 — olib tashlangan (.env dan qayta qo'shilmasligi uchun o'chirilmaydi)
    added_by   INTEGER,
    added_at   TEXT
);
-- Import shablonlari (super-admin yuklagan versiyalar; asl shablonlar — shablonlar/ papkasida)
CREATE TABLE IF NOT EXISTS templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slot        TEXT NOT NULL,        -- asl shablon fayli (masalan «4_baholar.xlsx») yoki «custom_<n>»
    kind        TEXT,                 -- import turi; NULL — oddiy hujjat namunasi (import qilinmaydi)
    file_name   TEXT NOT NULL,        -- kurs koordinatoriga yuboriladigan nom
    stored      TEXT NOT NULL,        -- data/templates/ ichidagi fayl
    version     INTEGER NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,
    uploaded_by INTEGER,
    uploaded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_templates_slot ON templates(slot, version);
CREATE TABLE IF NOT EXISTS template_meta (
    slot        TEXT PRIMARY KEY,
    title       TEXT,
    description TEXT,
    kind        TEXT,
    hidden      INTEGER NOT NULL DEFAULT 0,
    sort        INTEGER
);
-- Shablon o'zgartirilganda super-admin o'rgatgan ustun nomlari (import shu nomlarni ham taniydi)
CREATE TABLE IF NOT EXISTS column_aliases (
    grp      TEXT NOT NULL,
    alias    TEXT NOT NULL,
    field    TEXT NOT NULL,
    added_by INTEGER,
    added_at TEXT,
    PRIMARY KEY (grp, alias)
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
-- Telegram guruh qaysi kursga biriktirilgan (/guruh buyrug'ini bergan koordinatorning kursi)
CREATE TABLE IF NOT EXISTS group_courses (
    chat_id    INTEGER PRIMARY KEY,
    course     TEXT NOT NULL,
    updated_at TEXT
);
"""


class Central:
    def __init__(self) -> None:
        self.conn: aiosqlite.Connection | None = None

    async def connect(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.executescript(CENTRAL_SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def _one(self, sql: str, args: tuple) -> dict | None:
        async with self.conn.execute(sql, args) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def _write(self, sql: str, args: tuple) -> None:
        await self.conn.execute(sql, args)
        await self.conn.commit()

    # --- til
    async def get_lang(self, tg_id: int) -> str | None:
        row = await self._one("SELECT lang FROM user_prefs WHERE tg_id = ?", (tg_id,))
        return row["lang"] if row else None

    async def set_lang(self, tg_id: int, lang: str) -> None:
        await self._write("INSERT INTO user_prefs (tg_id, lang) VALUES (?, ?) "
                          "ON CONFLICT(tg_id) DO UPDATE SET lang = excluded.lang", (tg_id, lang))

    # --- ota-onaning faol kursi
    async def get_active(self, tg_id: int) -> str | None:
        row = await self._one("SELECT course FROM active_course WHERE tg_id = ?", (tg_id,))
        return row["course"] if row else None

    async def set_active(self, tg_id: int, course: str) -> None:
        await self._write("INSERT INTO active_course (tg_id, course, updated_at) VALUES (?, ?, datetime('now')) "
                          "ON CONFLICT(tg_id) DO UPDATE SET course = excluded.course, updated_at = excluded.updated_at",
                          (tg_id, course))

    # --- farzandi hali topilmagan ota-onalar
    async def set_pending(self, tg_id: int, phone: str, name: str | None) -> None:
        await self._write("INSERT INTO pending_parents (tg_id, phone, name, created_at) VALUES (?, ?, ?, datetime('now')) "
                          "ON CONFLICT(tg_id) DO UPDATE SET phone = excluded.phone, name = excluded.name",
                          (tg_id, phone, name))

    async def get_pending(self, tg_id: int) -> dict | None:
        return await self._one("SELECT * FROM pending_parents WHERE tg_id = ?", (tg_id,))

    async def clear_pending(self, tg_id: int) -> None:
        await self._write("DELETE FROM pending_parents WHERE tg_id = ?", (tg_id,))

    async def pending_all(self) -> list[dict]:
        async with self.conn.execute("SELECT * FROM pending_parents") as cur:
            return [dict(r) for r in await cur.fetchall()]

    # --- atamalar tarjimasi
    async def all_terms(self) -> list[dict]:
        async with self.conn.execute("SELECT * FROM term_translations") as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def upsert_terms(self, rows: list[dict]) -> int:
        await self.conn.executemany(
            """INSERT INTO term_translations (term_key, uz, ru, en, updated_at) VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(term_key) DO UPDATE SET uz = excluded.uz,
                 ru = COALESCE(excluded.ru, term_translations.ru), en = COALESCE(excluded.en, term_translations.en),
                 updated_at = excluded.updated_at""",
            [(r["term_key"], r["uz"], r.get("ru") or None, r.get("en") or None) for r in rows])
        await self.conn.commit()
        return len(rows)

    # --- kurslar va koordinatorlar reyestri
    async def seed_from_env(self) -> None:
        """.env dagi kurs va koordinatorlarni (yo'q bo'lsa) yozadi; bot ichidan kiritilgan o'zgarishlar ustun."""
        for i, (key, ids) in enumerate(ENV_COURSES.items()):
            await self.conn.execute("INSERT OR IGNORE INTO courses (key, title, sort, created_at) "
                                    "VALUES (?, ?, ?, datetime('now'))", (key, ENV_COURSE_TITLES.get(key, key), i))
            for uid in ids:
                await self.conn.execute("INSERT OR IGNORE INTO coordinators (user_id, course_key, added_at) "
                                        "VALUES (?, ?, datetime('now'))", (uid, key))
        await self.conn.commit()

    async def registry(self) -> tuple[list[dict], list[dict]]:
        async with self.conn.execute("SELECT * FROM courses ORDER BY sort, created_at, key") as cur:
            courses = [dict(r) for r in await cur.fetchall()]
        async with self.conn.execute("SELECT * FROM coordinators WHERE active = 1 ORDER BY added_at") as cur:
            coords = [dict(r) for r in await cur.fetchall()]
        return courses, coords

    async def add_course(self, title: str, by: int | None) -> str:
        base = _slug(title)
        key, n = base, 2
        while await self._one("SELECT 1 FROM courses WHERE key = ?", (key,)):
            key, n = f"{base}_{n}", n + 1
        row = await self._one("SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM courses", ())
        await self._write("INSERT INTO courses (key, title, sort, created_by, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                          (key, title.strip(), row["s"], by))
        return key

    async def rename_course_title(self, key: str, title: str) -> None:
        await self._write("UPDATE courses SET title = ? WHERE key = ?", (title.strip(), key))

    async def set_coordinator(self, user_id: int, course_key: str, name: str | None, by: int | None) -> None:
        await self._write(
            """INSERT INTO coordinators (user_id, course_key, name, active, added_by, added_at)
               VALUES (?, ?, ?, 1, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET course_key = excluded.course_key, active = 1,
                 name = COALESCE(excluded.name, coordinators.name), added_by = excluded.added_by,
                 added_at = excluded.added_at""", (user_id, course_key, name, by))

    async def remove_coordinator(self, user_id: int) -> None:
        await self._write("UPDATE coordinators SET active = 0 WHERE user_id = ?", (user_id,))

    # --- shablonlar
    async def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        async with self.conn.execute(sql, args) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def add_template_version(self, slot: str, kind: str | None, file_name: str, stored: str, by: int | None) -> int:
        row = await self._one("SELECT COALESCE(MAX(version), 0) + 1 AS v FROM templates WHERE slot = ?", (slot,))
        await self.conn.execute("UPDATE templates SET active = 0 WHERE slot = ?", (slot,))
        await self.conn.execute(
            "INSERT INTO templates (slot, kind, file_name, stored, version, active, uploaded_by, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, datetime('now'))", (slot, kind, file_name, stored, row["v"], by))
        await self.conn.commit()
        return row["v"]

    async def active_templates(self) -> list[dict]:
        return await self._all("SELECT * FROM templates WHERE active = 1 ORDER BY id")

    async def template_versions(self, slot: str) -> list[dict]:
        return await self._all("SELECT * FROM templates WHERE slot = ? ORDER BY version DESC", (slot,))

    async def activate_template(self, tpl_id: int) -> dict | None:
        row = await self._one("SELECT * FROM templates WHERE id = ?", (tpl_id,))
        if row:
            await self.conn.execute("UPDATE templates SET active = 0 WHERE slot = ?", (row["slot"],))
            await self.conn.execute("UPDATE templates SET active = 1 WHERE id = ?", (tpl_id,))
            await self.conn.commit()
        return row

    async def deactivate_slot(self, slot: str) -> None:
        """Asl shablonga qaytish (yoki qo'shilgan shablonni o'chirish) — versiyalar tarixda qoladi."""
        await self._write("UPDATE templates SET active = 0 WHERE slot = ?", (slot,))

    async def template_meta(self) -> dict[str, dict]:
        return {r["slot"]: r for r in await self._all("SELECT * FROM template_meta")}

    async def set_template_meta(self, slot: str, **fields) -> None:
        await self.conn.execute("INSERT OR IGNORE INTO template_meta (slot) VALUES (?)", (slot,))
        for k, v in fields.items():
            assert k in ("title", "description", "kind", "hidden", "sort")
            await self.conn.execute(f"UPDATE template_meta SET {k} = ? WHERE slot = ?", (v, slot))
        await self.conn.commit()

    async def next_custom_slot(self) -> str:
        rows = await self._all("SELECT slot FROM template_meta WHERE slot LIKE 'custom_%' "
                               "UNION SELECT slot FROM templates WHERE slot LIKE 'custom_%'")
        nums = [int(r["slot"].split("_")[1]) for r in rows if r["slot"].split("_")[1].isdigit()]
        return f"custom_{max(nums, default=0) + 1}"

    # --- o'rgatilgan ustun nomlari
    async def add_alias(self, grp: str, alias: str, field: str, by: int | None) -> None:
        await self._write("INSERT INTO column_aliases (grp, alias, field, added_by, added_at) "
                          "VALUES (?, ?, ?, ?, datetime('now')) ON CONFLICT(grp, alias) DO UPDATE SET "
                          "field = excluded.field, added_by = excluded.added_by, added_at = excluded.added_at",
                          (grp, alias, field, by))

    async def all_aliases(self) -> list[dict]:
        return await self._all("SELECT * FROM column_aliases ORDER BY added_at")

    async def get_meta(self, key: str) -> str | None:
        row = await self._one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        await self._write("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                          (key, value))

    # --- Telegram guruhlar
    async def group_course(self, chat_id: int) -> str | None:
        row = await self._one("SELECT course FROM group_courses WHERE chat_id = ?", (chat_id,))
        return row["course"] if row else None

    async def set_group_course(self, chat_id: int, course: str) -> None:
        await self._write("INSERT INTO group_courses (chat_id, course, updated_at) VALUES (?, ?, datetime('now')) "
                          "ON CONFLICT(chat_id) DO UPDATE SET course = excluded.course, updated_at = excluded.updated_at",
                          (chat_id, course))

    async def rename_course(self, old: str, new: str) -> None:
        """Kurs nomi o'zgarganda (masalan, «koordinator_123» → «3-kurs») — guruhlar va faol kurs yozuvlari ham."""
        await self.conn.execute("UPDATE group_courses SET course = ? WHERE course = ?", (new, old))
        await self.conn.execute("UPDATE active_course SET course = ? WHERE course = ?", (new, old))
        await self.conn.commit()

    async def move_group(self, old_id: int, new_id: int) -> None:
        await self._write("UPDATE group_courses SET chat_id = ? WHERE chat_id = ?", (new_id, old_id))


central = Central()



async def reload_registry() -> None:
    """Umumiy ro'yxatdagi kurs va koordinatorlarni ishlayotgan botga qo'llaydi (qayta ishga tushirishsiz).
    COURSES, COURSE_TITLES, ADMIN_COURSE, ADMIN_IDS — joyida yangilanadi (boshqa modullar shu obyektlarni ishlatadi)."""
    courses, coords = await central.registry()
    new_courses = {c["key"]: [] for c in courses}
    for c in coords:
        if c["course_key"] in new_courses:
            new_courses[c["course_key"]].append(c["user_id"])
    COURSES.clear()
    COURSES.update(new_courses)
    COURSE_TITLES.clear()
    COURSE_TITLES.update({c["key"]: c["title"] for c in courses})
    ADMIN_COURSE.clear()
    ADMIN_COURSE.update({u: k for k, ids in COURSES.items() for u in ids})
    ADMIN_IDS.clear()
    ADMIN_IDS.update(ADMIN_COURSE)
    ADMIN_IDS.update(SUPERADMIN_IDS)  # super-admin ham admin buyruqlaridan foydalanadi (tanlangan kursda)
