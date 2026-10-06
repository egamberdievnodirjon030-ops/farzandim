"""SQLite ma'lumotlar bazasi: sxema va barcha so'rovlar."""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from tenancy import central, current_course

from utils import group_key, normalize_text, now_iso, subject_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hemis_id     TEXT NOT NULL UNIQUE,
    full_name    TEXT NOT NULL,
    name_norm    TEXT NOT NULL,
    group_name   TEXT,
    group_key    TEXT,
    faculty      TEXT,
    course       INTEGER,
    birth_date   TEXT,
    tutor_name   TEXT,
    tutor_phone  TEXT,
    updated_at   TEXT,
    payment_form TEXT,     -- «Davlat granti» yoki «To'lov-shartnoma»
    full_name_cyr TEXT     -- rasmiy kirill yozuvi (ixtiyoriy): rus tilidagi ota-onaga shu ko'rsatiladi
);
CREATE INDEX IF NOT EXISTS idx_students_group ON students(group_key);

CREATE TABLE IF NOT EXISTS student_phones (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    phone      TEXT NOT NULL,
    PRIMARY KEY (student_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_student_phones_phone ON student_phones(phone);

CREATE TABLE IF NOT EXISTS parents (
    tg_id              INTEGER PRIMARY KEY,
    phone              TEXT NOT NULL,
    tg_name            TEXT,
    current_student_id INTEGER,
    notify_instant     INTEGER NOT NULL DEFAULT 1,
    notify_daily       INTEGER NOT NULL DEFAULT 1,
    notify_warn        INTEGER NOT NULL DEFAULT 1,
    notify_pay         INTEGER NOT NULL DEFAULT 1,
    active             INTEGER NOT NULL DEFAULT 1,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parents_phone ON parents(phone);

CREATE TABLE IF NOT EXISTS parent_students (
    parent_id  INTEGER NOT NULL REFERENCES parents(tg_id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    via        TEXT NOT NULL DEFAULT 'phone',
    created_at TEXT NOT NULL,
    PRIMARY KEY (parent_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_parent_students_student ON parent_students(student_id);

CREATE TABLE IF NOT EXISTS link_requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    note       TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_by INTEGER,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    pair        INTEGER NOT NULL,
    subject     TEXT NOT NULL,
    lesson_type TEXT,
    teacher     TEXT,
    status      TEXT NOT NULL CHECK (status IN ('keldi','kelmadi','sababli','kechikdi')),
    hours       REAL NOT NULL DEFAULT 2,
    notified    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (student_id, date, pair)
);
CREATE INDEX IF NOT EXISTS idx_attendance_student_date ON attendance(student_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_notified ON attendance(notified);

CREATE TABLE IF NOT EXISTS schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL,
    group_key   TEXT NOT NULL,
    weekday     INTEGER NOT NULL,
    pair        INTEGER NOT NULL,
    start_time  TEXT,
    end_time    TEXT,
    subject     TEXT NOT NULL,
    lesson_type TEXT,
    teacher     TEXT,
    room        TEXT,
    week_type   TEXT NOT NULL DEFAULT 'har',
    subgroup    TEXT      -- kichik guruh (masalan, chet tili 1- va 2-kichik guruhga bo'lingan)
);

-- Tanlov fanlari va 2-til darslari: akademik guruhga bog'lanmagan (bir oqimda turli guruhlar talabalari).
-- Talabaning shaxsiy jadvaliga faqat u biriktirilgan fan (va oqim) darslari qo'shiladi.
CREATE TABLE IF NOT EXISTS elective_schedule (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject     TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    stream      TEXT,     -- oqim (masalan, «2»); bo'sh — fanning yagona oqimi
    group_key   TEXT,     -- ko'rsatilsa — faqat shu akademik guruh talabalari uchun
    group_name  TEXT,
    weekday     INTEGER NOT NULL,
    pair        INTEGER NOT NULL,
    start_time  TEXT,
    end_time    TEXT,
    lesson_type TEXT,
    teacher     TEXT,
    room        TEXT,
    week_type   TEXT NOT NULL DEFAULT 'har'
);
CREATE INDEX IF NOT EXISTS idx_elective_day ON elective_schedule(weekday);

-- Talabaning shaxsiy fanlari: tanlov fanlari, ikkinchi chet tili, oqim (kichik guruh).
-- Shaxsiy jadval = guruh jadvali, undan talaba o'qimaydigan tanlov/til darslari olib tashlanadi.
CREATE TABLE IF NOT EXISTS student_subjects (
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject     TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    subgroup    TEXT,
    PRIMARY KEY (student_id, subject_key)
);
CREATE INDEX IF NOT EXISTS idx_schedule_group ON schedule(group_key, weekday);

CREATE TABLE IF NOT EXISTS grades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject      TEXT NOT NULL,
    control_type TEXT NOT NULL,
    score        REAL,
    max_score    REAL,
    date         TEXT,
    semester     TEXT NOT NULL DEFAULT '',
    credits      REAL,
    UNIQUE (student_id, subject, control_type, semester)
);

-- HEMIS «Performance GPA»: rasmiy GPA. Har yuklash — yangi yozuv (tarix); joriy GPA — talabaning eng oxirgi yozuvi.
-- Fayl o'chirilsa, uning yozuvlari o'chadi va oldingi yuklamadagi GPA o'z-o'zidan joriy bo'ladi.
CREATE TABLE IF NOT EXISTS gpa_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    gpa         REAL NOT NULL,
    subjects    INTEGER,
    credits     REAL,
    debts       INTEGER,
    method      TEXT,
    year        TEXT,
    changed_at  TEXT,
    recorded_at TEXT NOT NULL,
    import_id   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_gpa_records_student ON gpa_records(student_id, id);

-- HEMIS «Akadem qarzdorlar» ro'yxati: har bir qator — talabaning bitta qarzdor fani (import to'liq almashtiradi)
CREATE TABLE IF NOT EXISTS academic_debts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject       TEXT NOT NULL,
    semester      TEXT NOT NULL DEFAULT '',
    credits       REAL,
    academic_year TEXT,
    created_at    TEXT NOT NULL,
    UNIQUE (student_id, subject, semester)
);
CREATE INDEX IF NOT EXISTS idx_acad_debts_student ON academic_debts(student_id);

CREATE TABLE IF NOT EXISTS warnings_sent (
    student_id INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    level      TEXT NOT NULL,
    sent_at    TEXT NOT NULL,
    PRIMARY KEY (student_id, kind, level)
);

CREATE TABLE IF NOT EXISTS announcements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    created_by INTEGER,
    created_at TEXT NOT NULL,
    sent_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id   INTEGER NOT NULL,
    student_id  INTEGER,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    answer      TEXT,
    answered_by INTEGER,
    answered_at TEXT
);

-- Talabalarning O'Z telefon raqamlari (ota-ona sifatida ro'yxatdan o'tishga urinishni aniqlash uchun)
CREATE TABLE IF NOT EXISTS student_self_phones (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    phone      TEXT NOT NULL,
    PRIMARY KEY (student_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_self_phones_phone ON student_self_phones(phone);

-- Bot qo'shilgan talabalar Telegram guruhlari
CREATE TABLE IF NOT EXISTS tg_groups (
    chat_id    INTEGER PRIMARY KEY,
    title      TEXT,
    group_name TEXT,
    group_key  TEXT,
    bot_admin  INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1,
    added_by   INTEGER,
    added_at   TEXT NOT NULL
);

-- Talabalar guruhlarida ko'rilgan Telegram foydalanuvchilar
CREATE TABLE IF NOT EXISTS tg_group_members (
    tg_id      INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    name       TEXT,
    username   TEXT,
    source     TEXT,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    PRIMARY KEY (tg_id, chat_id)
);

-- Talaba deb aniqlanganlar: status 'blocked' — kirish yopiq, 'allowed' — kurs koordinatori ota-ona deb tasdiqlagan
CREATE TABLE IF NOT EXISTS access_blocks (
    tg_id      INTEGER PRIMARY KEY,
    phone      TEXT,
    name       TEXT,
    username   TEXT,
    reason     TEXT,
    detail     TEXT,
    status     TEXT NOT NULL DEFAULT 'blocked',
    created_at TEXT NOT NULL,
    decided_by INTEGER,
    decided_at TEXT
);

-- Talabaga oid rasmiy PDF hujjatlar: tushuntirish xati, dekan ogohlantirishi, hayfsan.
-- Fayl Telegram serverida saqlanadi, bazada faqat uning file_id si turadi.
CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    doc_type       TEXT NOT NULL,
    file_id        TEXT NOT NULL,
    file_unique_id TEXT,
    file_name      TEXT,
    file_size      INTEGER,
    doc_date       TEXT,
    comment        TEXT,
    created_by     INTEGER,
    created_at     TEXT NOT NULL,
    revoked        INTEGER NOT NULL DEFAULT 0,
    revoked_by     INTEGER,
    revoked_at     TEXT,
    batch          TEXT,     -- bitta yuborishda bir nechta talabaga ketgan nusxalar guruhi
    redacted       INTEGER NOT NULL DEFAULT 0,  -- boshqa talabalar ma'lumotlari yopilgan joylar soni
    source_file_id TEXT      -- kurs koordinatori yuklagan asl faylning file_unique_id si (takrorni aniqlash uchun)
);
CREATE INDEX IF NOT EXISTS idx_documents_student ON documents(student_id);

-- Qaysi ota-onaga qaysi xabar bilan yetkazilgani (xato yuborilsa, 48 soat ichida o'chirish uchun)
CREATE TABLE IF NOT EXISTS document_deliveries (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id   INTEGER NOT NULL,
    message_id  INTEGER,
    sent_at     TEXT NOT NULL,
    PRIMARY KEY (document_id, parent_id)
);

-- HEMIS davomat statistikasi: har bir yuklash sanasidagi jami ko'rsatkichlar (asl birliklarda)
CREATE TABLE IF NOT EXISTS attendance_stats (
    student_id     INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    as_of          TEXT NOT NULL,
    attended       REAL NOT NULL DEFAULT 0,
    absent         REAL NOT NULL DEFAULT 0,
    excused        REAL NOT NULL DEFAULT 0,
    self_marked    REAL,
    teacher_marked REAL,
    imported_at    TEXT NOT NULL,
    PRIMARY KEY (student_id, as_of)
);

-- HEMIS davomat statistikasi BITTA FAN bo'yicha («O'quvchilarni … fanidan darslarga qatnashish statistikasi»).
-- Umumiy davomatga (attendance_stats) qo'shilmaydi — faqat fanlar kesimida ko'rsatiladi. Birliklar — HEMIS'dagidek (para).
CREATE TABLE IF NOT EXISTS subject_att_stats (
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject     TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    as_of       TEXT NOT NULL,
    attended    REAL NOT NULL DEFAULT 0,
    absent      REAL NOT NULL DEFAULT 0,
    excused     REAL NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    import_id   INTEGER,
    PRIMARY KEY (student_id, subject_key, as_of)
);

-- To'lov-kontrakt: buxgalteriya hisobotidan har bir sana holatidagi ko'rsatkichlar (so'mda).
-- JSHSHIR (shaxsiy raqam) saqlanmaydi — talaba F.I.Sh. bo'yicha topiladi.
CREATE TABLE IF NOT EXISTS payments (
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL DEFAULT 'kontrakt',   -- 'kontrakt' — yillik kontrakt, 'trimestr' — trimestr to'lovi
    as_of       TEXT NOT NULL,
    year_label  TEXT,
    contract    REAL,      -- shartnoma (kontrakt) summasi
    paid        REAL,      -- to'langan
    debt        REAL NOT NULL DEFAULT 0,   -- qarzdorlik (0 — qarz yo'q)
    overpaid    REAL NOT NULL DEFAULT 0,   -- ortiqcha to'langan (haqdorlik)
    percent     REAL,      -- to'langan, %
    note        TEXT,
    imported_at TEXT NOT NULL,
    PRIMARY KEY (student_id, kind, as_of)
);
-- Yuklangan fayllar (import): har bir yozuvda import_id — qaysi fayldan kelgani; o'chirilsa shu fayldan kelgan
-- ma'lumotlar, ota-onalarga ketgan bildirishnomalar va Telegram xabarlari ham olib tashlanadi
CREATE TABLE IF NOT EXISTS imports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    file_name   TEXT,
    uploaded_by INTEGER,
    uploaded_at TEXT NOT NULL,
    rows        INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT,
    deleted_by  INTEGER
);
CREATE TABLE IF NOT EXISTS sent_messages (
    import_id  INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    sent_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent_messages ON sent_messages(import_id);
-- Har bir fayl yuklangandan keyingi holat (dinamika uchun): faqat o'zgargan qiymat yoziladi; bir kunda bir necha
-- yuklash — o'sha kunning bitta nuqtasi. metric: att_pct, att_hours, acad, kontrakt, trimestr, gpa
CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    metric     TEXT NOT NULL,
    value      REAL NOT NULL,
    day        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots ON snapshots(student_id, metric, id);
-- Ota-onalar so'rovnomalari: kurs koordinatori (yoki super-admin) tuzadi, ota-onalar ilovada javob beradi.
-- target_groups — guruh kalitlari, vergul bilan (bo'sh — butun kurs). Bitta ota-ona — bitta javob.
CREATE TABLE IF NOT EXISTS surveys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT,
    target_groups TEXT NOT NULL DEFAULT '',
    anonymous     INTEGER NOT NULL DEFAULT 0,
    created_by    INTEGER,
    created_at    TEXT NOT NULL,
    closes_at     TEXT,
    closed        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS survey_questions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    pos       INTEGER NOT NULL,
    kind      TEXT NOT NULL CHECK (kind IN ('single', 'multi', 'scale', 'text')),
    text      TEXT NOT NULL,
    options   TEXT NOT NULL DEFAULT '[]',
    required  INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS survey_responses (
    survey_id    INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    parent_id    INTEGER NOT NULL,
    student_id   INTEGER,
    group_key    TEXT,
    submitted_at TEXT NOT NULL,
    PRIMARY KEY (survey_id, parent_id)
);
CREATE TABLE IF NOT EXISTS survey_answers (
    survey_id   INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    parent_id   INTEGER NOT NULL,
    question_id INTEGER NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    value       TEXT NOT NULL,
    PRIMARY KEY (survey_id, parent_id, question_id)
);
-- Buxgalteriya hisoboti qaysi talabalarni qamrab olgani: group_key '*' — butun kurs, aks holda — shu guruh
-- (guruhlari biriktirilgan koordinator yuklagan). Qamrovdagi talaba hisobotda bo'lmasa — qarzi mavjud emas.
CREATE TABLE IF NOT EXISTS payment_reports (
    kind      TEXT NOT NULL,
    as_of     TEXT NOT NULL,
    group_key TEXT NOT NULL,
    PRIMARY KEY (kind, as_of, group_key)
);

-- Foydalanuvchi tanlagan til (uz | ru | en) — ota-ona ro'yxatdan o'tmasidan oldin ham saqlanadi
CREATE TABLE IF NOT EXISTS user_prefs (
    tg_id INTEGER PRIMARY KEY,
    lang  TEXT NOT NULL DEFAULT 'uz'
);

-- Baholar tarixi: har bir import paytida yangi yoki o'zgargan ball (dinamika — «oxirgi oyda qanday o'zgardi»)
CREATE TABLE IF NOT EXISTS grade_history (
    student_id   INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject      TEXT NOT NULL,
    control_type TEXT NOT NULL,
    semester     TEXT NOT NULL DEFAULT '',
    score        REAL,
    max_score    REAL,
    credits      REAL,
    recorded_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_grade_history ON grade_history(student_id, recorded_at);

-- Ota-ona va kurs koordinatori orasidagi yozishma (Web App va bot — bitta suhbat)
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    parent_id   INTEGER NOT NULL,
    sender      TEXT NOT NULL,          -- parent | staff
    author_id   INTEGER,
    author_name TEXT,
    text        TEXT NOT NULL,
    question_id INTEGER,
    created_at  TEXT NOT NULL,
    read_at     TEXT                    -- qabul qiluvchi o'qigan vaqt
);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(student_id, parent_id, id);
-- Ota-onaga yuborilgan bildirishnomalar (Web App'dagi bildirishnomalar markazi)
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER NOT NULL,
    student_id INTEGER,
    kind       TEXT,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications_parent ON notifications(parent_id, id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

PARENT_FLAGS = {"notify_instant", "notify_daily", "notify_warn", "notify_pay"}


# Yuklangan fayldan keladigan ma'lumotlar jadvallari (import_id ustuni bilan) — fayl o'chirilsa shu yozuvlar o'chadi
IMPORT_TABLES = ("attendance", "attendance_stats", "subject_att_stats", "payments", "payment_reports", "grades", "grade_history",
                 "academic_debts", "schedule", "elective_schedule", "student_subjects", "notifications", "gpa_records")


def _imp() -> int | None:
    from tenancy import current_import
    return current_import.get()


class Database:
    def __init__(self) -> None:
        self.conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------ asosiy
    async def connect(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.execute("PRAGMA journal_mode = WAL")
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()

    async def _migrate(self) -> None:
        """Oldingi versiyada yaratilgan bazaga yangi ustunlarni qo'shadi (ma'lumotlarga tegmaydi)."""
        async with self.conn.execute("PRAGMA table_info(documents)") as cur:
            have = {r[1] for r in await cur.fetchall()}
        for col, ddl in (("batch", "TEXT"), ("redacted", "INTEGER NOT NULL DEFAULT 0"), ("source_file_id", "TEXT")):
            if col not in have:
                await self.conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {ddl}")
        async with self.conn.execute("PRAGMA table_info(schedule)") as cur:
            if "subgroup" not in {r[1] for r in await cur.fetchall()}:
                await self.conn.execute("ALTER TABLE schedule ADD COLUMN subgroup TEXT")
        async with self.conn.execute("PRAGMA table_info(notifications)") as cur:
            ncols = {r[1] for r in await cur.fetchall()}
        for col, ddl in (("student_id", "INTEGER"), ("kind", "TEXT")):
            if col not in ncols:
                await self.conn.execute(f"ALTER TABLE notifications ADD COLUMN {col} {ddl}")
        async with self.conn.execute("PRAGMA table_info(attendance)") as cur:
            if "source" not in {r[1] for r in await cur.fetchall()}:  # integratsiyadan kelgan yozuv ('integ')
                await self.conn.execute("ALTER TABLE attendance ADD COLUMN source TEXT")
        async with self.conn.execute("PRAGMA table_info(grades)") as cur:
            if "credits" not in {r[1] for r in await cur.fetchall()}:
                await self.conn.execute("ALTER TABLE grades ADD COLUMN credits REAL")
        async with self.conn.execute("SELECT (SELECT COUNT(*) FROM messages), (SELECT COUNT(*) FROM questions)") as cur:
            msgs, qs = await cur.fetchone()
        if not msgs and qs:  # oldingi versiya: savol-javoblar — yozishmaga
            await self.conn.execute(
                """INSERT INTO messages (student_id, parent_id, sender, author_id, text, question_id, created_at, read_at)
                   SELECT student_id, parent_id, 'parent', parent_id, text, id, created_at, created_at
                   FROM questions WHERE student_id IS NOT NULL""")
            await self.conn.execute(
                """INSERT INTO messages (student_id, parent_id, sender, author_id, text, question_id, created_at, read_at)
                   SELECT student_id, parent_id, 'staff', answered_by, answer, id, answered_at, answered_at
                   FROM questions WHERE student_id IS NOT NULL AND answer IS NOT NULL""")
        async with self.conn.execute("SELECT (SELECT COUNT(*) FROM grade_history), (SELECT COUNT(*) FROM grades)") as cur:
            hist, grades = await cur.fetchone()
        if not hist and grades:  # oldingi versiya: tarix hozirgi baholardan boshlanadi
            await self.conn.execute(
                """INSERT INTO grade_history (student_id, subject, control_type, semester, score, max_score, credits,
                                              recorded_at)
                   SELECT student_id, subject, control_type, semester, score, max_score, credits,
                          strftime('%Y-%m-%dT%H:%M:%S', 'now')
                   FROM grades""")
        async with self.conn.execute("PRAGMA table_info(students)") as cur:
            cols = {r[1] for r in await cur.fetchall()}
        if "payment_form" not in cols:
            await self.conn.execute("ALTER TABLE students ADD COLUMN payment_form TEXT")
        if "full_name_cyr" not in cols:
            await self.conn.execute("ALTER TABLE students ADD COLUMN full_name_cyr TEXT")
        async with self.conn.execute("PRAGMA table_info(payments)") as cur:
            if "kind" not in {r[1] for r in await cur.fetchall()}:
                # oldingi versiya: kontrakt va trimestr ajratilmagan — mavjud yozuvlar «kontrakt» deb olinadi
                await self.conn.executescript("""
                    PRAGMA foreign_keys = OFF;
                    ALTER TABLE payments RENAME TO payments_old;
                    CREATE TABLE payments (
                        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                        kind TEXT NOT NULL DEFAULT 'kontrakt', as_of TEXT NOT NULL, year_label TEXT,
                        contract REAL, paid REAL, debt REAL NOT NULL DEFAULT 0, overpaid REAL NOT NULL DEFAULT 0,
                        percent REAL, note TEXT, imported_at TEXT NOT NULL,
                        PRIMARY KEY (student_id, kind, as_of));
                    INSERT INTO payments (student_id, kind, as_of, year_label, contract, paid, debt, overpaid, percent,
                                          note, imported_at)
                        SELECT student_id, 'kontrakt', as_of, year_label, contract, paid, debt, overpaid, percent,
                               note, imported_at FROM payments_old;
                    DROP TABLE payments_old;
                    PRAGMA foreign_keys = ON;""")
        async with self.conn.execute("PRAGMA table_info(parents)") as cur:
            if "notify_pay" not in {r[1] for r in await cur.fetchall()}:
                await self.conn.execute("ALTER TABLE parents ADD COLUMN notify_pay INTEGER NOT NULL DEFAULT 1")
        async with self.conn.execute("PRAGMA table_info(link_requests)") as cur:
            have = {r[1] for r in await cur.fetchall()}
        # talaba tasdiqlashi: bir martalik havola (token), muddati, tasdiqlagan talabaning Telegram ID si, ismi, raqami
        # va tasdiqlagan vaqti (student_ok_at) — yakuniy tasdiqni baribir kurs koordinatori beradi; claimed_phone — talaba
        # raqami bazada bo'lmasa, ota-ona kiritgan farzand raqami (talaba aynan shu raqam bilan tasdiqlashi kerak)
        for col, ddl in (("token", "TEXT"), ("token_expires", "TEXT"), ("student_tg", "INTEGER"), ("decided_via", "TEXT"),
                         ("student_ok_at", "TEXT"), ("student_phone", "TEXT"), ("student_tg_name", "TEXT"),
                         ("claimed_phone", "TEXT")):
            if col not in have:
                await self.conn.execute(f"ALTER TABLE link_requests ADD COLUMN {col} {ddl}")
        for t in IMPORT_TABLES + ("students",):  # qaysi yuklangan fayldan kelgani (o'chirish uchun)
            async with self.conn.execute(f"PRAGMA table_info({t})") as cur:
                if "import_id" not in {r[1] for r in await cur.fetchall()}:
                    await self.conn.execute(f"ALTER TABLE {t} ADD COLUMN import_id INTEGER")

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def fetchone(self, sql: str, params=()) -> dict | None:
        async with self.conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def fetchall(self, sql: str, params=()) -> list[dict]:
        async with self.conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def _tag(self, table: str, where: str, params: list[tuple]) -> None:
        """Joriy import davomida yozilgan qatorlarga import_id qo'yadi (import bo'lmasa — hech narsa qilmaydi)."""
        imp = _imp()
        if imp is None or not params:
            return
        await self.conn.executemany(f"UPDATE {table} SET import_id = ? WHERE {where}", [(imp, *p) for p in params])

    async def execute(self, sql: str, params=()) -> int:
        cur = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cur.lastrowid

    # ------------------------------------------------------------ talabalar
    async def upsert_students(self, rows: list[dict]) -> tuple[int, int, list[tuple[int, int]]]:
        """Talabalarni qo'shadi/yangilaydi. Qaytaradi: (yangi, yangilangan, yangi bog'langan (ota-ona, talaba))."""
        existing = {r["hemis_id"] for r in await self.fetchall("SELECT hemis_id FROM students")}
        inserted = updated = 0
        ts = now_iso()
        for r in rows:
            await self.conn.execute(
                """INSERT INTO students (hemis_id, full_name, name_norm, group_name, group_key, faculty,
                                         course, birth_date, tutor_name, tutor_phone, updated_at, payment_form,
                                         full_name_cyr)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(hemis_id) DO UPDATE SET
                     full_name   = excluded.full_name,
                     name_norm   = excluded.name_norm,
                     group_name  = COALESCE(excluded.group_name, students.group_name),
                     group_key   = COALESCE(excluded.group_key, students.group_key),
                     faculty     = COALESCE(excluded.faculty, students.faculty),
                     course      = COALESCE(excluded.course, students.course),
                     birth_date  = COALESCE(excluded.birth_date, students.birth_date),
                     tutor_name  = COALESCE(excluded.tutor_name, students.tutor_name),
                     tutor_phone = COALESCE(excluded.tutor_phone, students.tutor_phone),
                     payment_form = COALESCE(excluded.payment_form, students.payment_form),
                     full_name_cyr = COALESCE(excluded.full_name_cyr, students.full_name_cyr),
                     updated_at  = excluded.updated_at""",
                (
                    r["hemis_id"], r["full_name"], normalize_text(r["full_name"]),
                    r.get("group_name") or None, group_key(r.get("group_name")) or None,
                    r.get("faculty") or None, r.get("course"), r.get("birth_date"),
                    r.get("tutor_name") or None, r.get("tutor_phone") or None, ts, r.get("payment_form") or None,
                    r.get("full_name_cyr") or None,
                ),
            )
            if r["hemis_id"] in existing:
                updated += 1
            else:
                inserted += 1
                existing.add(r["hemis_id"])
            phones = r.get("phones") or []
            self_phones = r.get("student_phones") or []
            if phones or self_phones:
                async with self.conn.execute("SELECT id FROM students WHERE hemis_id = ?", (r["hemis_id"],)) as cur:
                    sid = (await cur.fetchone())[0]
            if phones:
                await self.conn.execute("DELETE FROM student_phones WHERE student_id = ?", (sid,))
                await self.conn.executemany(
                    "INSERT OR IGNORE INTO student_phones (student_id, phone) VALUES (?, ?)",
                    [(sid, p) for p in phones],
                )
            if self_phones:
                await self._replace_self_phones(sid, self_phones)
        # talaba oxirgi marta qaysi fayldan kelgani — o'sha fayl o'chirilsa, faqat keyin qayta kelmaganlar o'chadi
        await self._tag("students", "hemis_id = ?", [(r["hemis_id"],) for r in rows])
        # Oldin ro'yxatdan o'tgan, lekin endi raqami bazada paydo bo'lgan ota-onalarni avtomatik bog'lash
        new_links = await self.fetchall(
            """SELECT DISTINCT p.tg_id AS parent_id, sp.student_id
               FROM parents p
               JOIN student_phones sp ON sp.phone = p.phone
               LEFT JOIN parent_students ps ON ps.parent_id = p.tg_id AND ps.student_id = sp.student_id
               WHERE ps.parent_id IS NULL
                 AND p.tg_id NOT IN (SELECT tg_id FROM access_blocks WHERE status = 'blocked')"""
        )
        await self.conn.executemany(
            "INSERT OR IGNORE INTO parent_students (parent_id, student_id, via, created_at) VALUES (?, ?, 'phone', ?)",
            [(x["parent_id"], x["student_id"], ts) for x in new_links],
        )
        await self.conn.commit()
        return inserted, updated, [(x["parent_id"], x["student_id"]) for x in new_links]

    # ------------------------------------------------------------ talabalarning o'z raqamlari
    async def _replace_self_phones(self, sid: int, phones: list[str]) -> None:
        await self.conn.execute("DELETE FROM student_self_phones WHERE student_id = ?", (sid,))
        await self.conn.executemany(
            "INSERT OR IGNORE INTO student_self_phones (student_id, phone) VALUES (?, ?)", [(sid, p) for p in phones]
        )

    async def set_self_phones(self, rows: list[dict]) -> int:
        """rows: {student_id, student_phones}. Fayldagi talabalarning eski raqamlari yangisiga almashtiriladi."""
        merged: dict[int, list[str]] = {}
        for r in rows:
            lst = merged.setdefault(r["student_id"], [])
            lst.extend(p for p in r["student_phones"] if p not in lst)
        for sid, phones in merged.items():
            await self._replace_self_phones(sid, phones)
        await self.conn.commit()
        return len(merged)

    async def add_self_phone(self, sid: int, phone: str) -> None:
        await self.execute("INSERT OR IGNORE INTO student_self_phones (student_id, phone) VALUES (?, ?)", (sid, phone))

    async def students_by_self_phone(self, phone: str) -> list[dict]:
        return await self.fetchall(
            """SELECT s.* FROM students s JOIN student_self_phones sp ON sp.student_id = s.id
               WHERE sp.phone = ? ORDER BY s.full_name""",
            (phone,),
        )

    async def phone_conflicts(self, limit: int = 10) -> tuple[int, list[dict]]:
        """Bir vaqtning o'zida talabaning o'z raqami va ota-ona raqami sifatida yozilgan raqamlar."""
        rows = await self.fetchall(
            """SELECT ss.phone, a.full_name AS student, b.full_name AS child
               FROM student_self_phones ss
               JOIN student_phones sp ON sp.phone = ss.phone
               JOIN students a ON a.id = ss.student_id
               JOIN students b ON b.id = sp.student_id
               ORDER BY ss.phone"""
        )
        return len({r["phone"] for r in rows}), rows[:limit]

    async def get_student(self, sid: int) -> dict | None:
        return await self.fetchone("SELECT * FROM students WHERE id = ?", (sid,))

    async def students_by_phone(self, phone: str) -> list[dict]:
        return await self.fetchall(
            """SELECT s.* FROM students s JOIN student_phones sp ON sp.student_id = s.id
               WHERE sp.phone = ? ORDER BY s.full_name""",
            (phone,),
        )

    async def all_students_brief(self, groups: set[str] | None = None) -> list[dict]:
        """groups — guruh kalitlari: berilsa, faqat shu guruhlar talabalari (koordinatorning o'z guruhlari)."""
        rows = await self.fetchall(
            "SELECT id, hemis_id, full_name, name_norm, group_name, group_key, birth_date, course FROM students"
        )
        return rows if groups is None else [r for r in rows if (r["group_key"] or "") in groups]

    async def group_counts(self) -> dict[str, dict]:
        """Kursdagi guruhlar: kalit → {name, students}."""
        rows = await self.fetchall("SELECT group_key, MAX(group_name) AS name, COUNT(*) AS n FROM students "
                                   "WHERE COALESCE(group_key, '') != '' GROUP BY group_key ORDER BY name")
        return {r["group_key"]: {"name": r["name"], "students": r["n"]} for r in rows}

    async def student_lookup(self, groups: set[str] | None = None) -> dict:
        """Davomat/baho fayllaridagi qatorlarni talabaga bog'lash uchun lug'atlar (groups — faqat shu guruhlar)."""
        rows = await self.all_students_brief(groups)
        by_hemis, by_name_group, by_name = {}, {}, {}
        for r in rows:
            by_hemis[normalize_text(r["hemis_id"]).replace(" ", "")] = r["id"]
            by_name_group[(r["name_norm"], r["group_key"] or "")] = r["id"]
            by_name[r["name_norm"]] = None if r["name_norm"] in by_name else r["id"]  # takrorlansa — noaniq
        return {"hemis": by_hemis, "name_group": by_name_group, "name": by_name}

    async def student_parent_count(self, sid: int) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS n FROM parent_students WHERE student_id = ?", (sid,))
        return row["n"]

    # ------------------------------------------------------------ ota-onalar
    async def get_parent(self, tg_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM parents WHERE tg_id = ?", (tg_id,))

    async def upsert_parent(self, tg_id: int, phone: str, tg_name: str) -> None:
        await self.execute(
            """INSERT INTO parents (tg_id, phone, tg_name, created_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(tg_id) DO UPDATE SET phone = excluded.phone, tg_name = excluded.tg_name, active = 1""",
            (tg_id, phone, tg_name, now_iso()),
        )

    async def set_parent_flag(self, tg_id: int, key: str, value: bool) -> None:
        if key not in PARENT_FLAGS:
            raise ValueError(key)
        await self.execute(f"UPDATE parents SET {key} = ? WHERE tg_id = ?", (int(value), tg_id))

    async def set_parent_active(self, tg_id: int, active: bool) -> None:
        await self.execute("UPDATE parents SET active = ? WHERE tg_id = ?", (int(active), tg_id))

    async def set_current_student(self, tg_id: int, sid: int) -> None:
        await self.execute("UPDATE parents SET current_student_id = ? WHERE tg_id = ?", (sid, tg_id))

    async def link_parent(self, tg_id: int, sid: int, via: str = "phone") -> None:
        await self.execute(
            "INSERT OR IGNORE INTO parent_students (parent_id, student_id, via, created_at) VALUES (?, ?, ?, ?)",
            (tg_id, sid, via, now_iso()),
        )

    async def parent_children(self, tg_id: int) -> list[dict]:
        return await self.fetchall(
            """SELECT s.* FROM students s JOIN parent_students ps ON ps.student_id = s.id
               WHERE ps.parent_id = ? ORDER BY s.full_name""",
            (tg_id,),
        )

    async def linked_student(self, tg_id: int, sid: int) -> dict | None:
        """Talaba shu ota-onaga bog'langan bo'lsagina qaytaradi (xavfsizlik tekshiruvi)."""
        return await self.fetchone(
            """SELECT s.* FROM students s JOIN parent_students ps ON ps.student_id = s.id
               WHERE ps.parent_id = ? AND s.id = ?""",
            (tg_id, sid),
        )

    async def parents_of_student(self, sid: int, flag: str | None = None) -> list[int]:
        cond = f" AND p.{flag} = 1" if flag in PARENT_FLAGS else ""
        rows = await self.fetchall(
            f"""SELECT p.tg_id FROM parents p JOIN parent_students ps ON ps.parent_id = p.tg_id
                WHERE ps.student_id = ? AND p.active = 1{cond}""",
            (sid,),
        )
        return [r["tg_id"] for r in rows]

    async def parents_for_digest(self) -> list[int]:
        rows = await self.fetchall("SELECT tg_id FROM parents WHERE active = 1 AND notify_daily = 1")
        return [r["tg_id"] for r in rows]

    async def parent_ids_for_groups(self, keys: list[str] | None) -> list[int]:
        """keys bo'sh bo'lsa — barcha faol ota-onalar."""
        if not keys:
            rows = await self.fetchall("SELECT tg_id FROM parents WHERE active = 1")
        else:
            marks = ",".join("?" * len(keys))
            rows = await self.fetchall(
                f"""SELECT DISTINCT p.tg_id FROM parents p
                    JOIN parent_students ps ON ps.parent_id = p.tg_id
                    JOIN students s ON s.id = ps.student_id
                    WHERE p.active = 1 AND s.group_key IN ({marks})""",
                tuple(keys),
            )
        return [r["tg_id"] for r in rows]

    # ------------------------------------------------------------ bog'lash so'rovlari
    async def create_link_request(self, parent_id: int, sid: int, note: str) -> int:
        return await self.execute(
            "INSERT INTO link_requests (parent_id, student_id, note, created_at) VALUES (?, ?, ?, ?)",
            (parent_id, sid, note, now_iso()),
        )

    async def pending_requests_count(self, parent_id: int) -> int:
        row = await self.fetchone(
            "SELECT COUNT(*) AS n FROM link_requests WHERE parent_id = ? AND status = 'pending'", (parent_id,)
        )
        return row["n"]

    async def has_pending_request(self, parent_id: int, sid: int) -> bool:
        row = await self.fetchone(
            "SELECT 1 FROM link_requests WHERE parent_id = ? AND student_id = ? AND status = 'pending'",
            (parent_id, sid),
        )
        return row is not None

    async def get_link_request(self, rid: int) -> dict | None:
        return await self.fetchone("SELECT * FROM link_requests WHERE id = ?", (rid,))

    async def decide_link_request(self, rid: int, status: str, admin_id: int) -> None:
        await self.execute(
            "UPDATE link_requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
            (status, admin_id, now_iso(), rid),
        )

    # ------------------------------------------------------------ davomat
    async def upsert_attendance(self, rows: list[tuple]) -> set[int]:
        """rows: (student_id, date, pair, subject, lesson_type, teacher, status, hours, notified)."""
        await self.conn.executemany(
            """INSERT INTO attendance (student_id, date, pair, subject, lesson_type, teacher, status, hours, notified)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(student_id, date, pair) DO UPDATE SET
                 subject     = excluded.subject,
                 lesson_type = COALESCE(excluded.lesson_type, attendance.lesson_type),
                 teacher     = COALESCE(excluded.teacher, attendance.teacher),
                 hours       = excluded.hours,
                 notified    = CASE WHEN attendance.status = excluded.status
                                    THEN attendance.notified ELSE excluded.notified END,
                 status      = excluded.status""",
            rows,
        )
        await self._tag("attendance", "student_id = ? AND date = ? AND pair = ?", [(r[0], r[1], r[2]) for r in rows])
        await self.conn.commit()
        return {r[0] for r in rows}

    async def attendance_between(self, sid: int, d1: str, d2: str) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM attendance WHERE student_id = ? AND date BETWEEN ? AND ? ORDER BY date, pair",
            (sid, d1, d2),
        )

    async def absences_between(self, sid: int, d1: str, d2: str) -> list[dict]:
        return await self.fetchall(
            """SELECT * FROM attendance WHERE student_id = ? AND date BETWEEN ? AND ? AND status != 'keldi'
               ORDER BY date, pair""",
            (sid, d1, d2),
        )

    _AGG = """COUNT(*) AS total,
              COALESCE(SUM(status = 'keldi'), 0)    AS keldi,
              COALESCE(SUM(status = 'kelmadi'), 0)  AS kelmadi,
              COALESCE(SUM(status = 'sababli'), 0)  AS sababli,
              COALESCE(SUM(status = 'kechikdi'), 0) AS kechikdi,
              COALESCE(SUM(CASE WHEN status = 'kelmadi' THEN hours END), 0) AS kelmadi_soat,
              COALESCE(SUM(CASE WHEN status = 'sababli' THEN hours END), 0) AS sababli_soat"""

    async def attendance_totals(self, sid: int, d1: str, d2: str) -> dict:
        return await self.fetchone(
            f"SELECT {self._AGG} FROM attendance WHERE student_id = ? AND date BETWEEN ? AND ?", (sid, d1, d2)
        )

    # ------------------------------------------------------------ panel uchun ommaviy so'rovlar
    async def bulk_attendance_totals(self, d1: str, d2: str) -> dict[int, dict]:
        rows = await self.fetchall(
            f"SELECT student_id, {self._AGG} FROM attendance WHERE date BETWEEN ? AND ? GROUP BY student_id", (d1, d2))
        return {r["student_id"]: r for r in rows}

    async def bulk_latest_att_stats(self, since: str) -> dict[int, dict]:
        rows = await self.fetchall(
            """SELECT a.* FROM attendance_stats a WHERE a.as_of = (SELECT MAX(b.as_of) FROM attendance_stats b
               WHERE b.student_id = a.student_id AND b.as_of >= ?)""", (since,))
        return {r["student_id"]: r for r in rows}

    # ------------------------------------------------------------ to'lov hisobotlari qamrovi
    async def add_payment_report(self, kind: str, as_of: str, groups: set[str] | None) -> None:
        """Yuklangan hisobot qamrovi: groups None — butun kurs, aks holda — shu guruhlar."""
        await self.conn.executemany("INSERT OR IGNORE INTO payment_reports (kind, as_of, group_key) VALUES (?, ?, ?)",
                                    [(kind, as_of, g) for g in (sorted(groups) if groups is not None else ["*"])])
        await self._tag("payment_reports", "kind = ? AND as_of = ? AND group_key = ?",
                        [(kind, as_of, g) for g in (sorted(groups) if groups is not None else ["*"])])
        await self.conn.commit()

    async def payment_coverage(self, kind: str) -> list[tuple[str, str]]:
        """[(sana, guruh_kaliti | '*'), ...]. Qamrov yozilmagan eski hisobotlar — butun kurs uchun deb olinadi."""
        rows = [(r["as_of"], r["group_key"]) for r in
                await self.fetchall("SELECT as_of, group_key FROM payment_reports WHERE kind = ?", (kind,))]
        known = {d for d, _ in rows}
        rows += [(r["as_of"], "*") for r in await self.fetchall(
            "SELECT DISTINCT as_of FROM payments WHERE kind = ?", (kind,)) if r["as_of"] not in known]
        return rows

    @staticmethod
    def covered_at(coverage: list[tuple[str, str]], gkey: str | None) -> str | None:
        """Talaba guruhini qamragan eng oxirgi hisobot sanasi (yo'q bo'lsa — None: bu turda ma'lumot yo'q)."""
        return max((d for d, g in coverage if g == "*" or g == (gkey or "")), default=None)

    @staticmethod
    def _clear(sid: int, kind: str, as_of: str) -> dict:
        """Hisobot talaba guruhini qamragan, lekin talaba unda yo'q — qarzdorlik mavjud emas."""
        return {"student_id": sid, "kind": kind, "as_of": as_of, "year_label": None, "contract": None, "paid": None,
                "debt": 0.0, "overpaid": 0.0, "percent": None, "note": None, "imported_at": None, "absent": True}

    async def bulk_latest_payments(self, kind: str) -> dict[int, dict]:
        """Har bir talabaning shu turdagi joriy holati: oxirgi yozuvi yoki — keyingi hisobot uning guruhini qamragan,
        lekin talaba unda yo'q bo'lsa (masalan, qarzini to'lagan) — «qarzdorlik mavjud emas»."""
        rows = await self.fetchall(
            """SELECT p.* FROM payments p WHERE p.kind = ? AND p.as_of = (SELECT MAX(p2.as_of) FROM payments p2
               WHERE p2.student_id = p.student_id AND p2.kind = p.kind)""", (kind,))
        latest = {r["student_id"]: r for r in rows}
        cov = await self.payment_coverage(kind)
        if not cov:
            return latest
        out = {}
        for st in await self.fetchall("SELECT id, group_key FROM students"):
            d = self.covered_at(cov, st["group_key"])
            p = latest.get(st["id"])
            if d and (p is None or p["as_of"] < d):
                out[st["id"]] = self._clear(st["id"], kind, d)
            elif p is not None:
                out[st["id"]] = p
        return out

    async def bulk_grades(self) -> dict[int, list[dict]]:
        out: dict[int, list[dict]] = {}
        for r in await self.fetchall("SELECT * FROM grades"):
            out.setdefault(r["student_id"], []).append(r)
        return out

    async def subject_stats(self, sid: int, d1: str, d2: str) -> list[dict]:
        return await self.fetchall(
            f"""SELECT subject, {self._AGG} FROM attendance
                WHERE student_id = ? AND date BETWEEN ? AND ? GROUP BY subject ORDER BY subject""",
            (sid, d1, d2),
        )

    async def unnotified_absences(self) -> list[dict]:
        return await self.fetchall(
            """SELECT a.*, s.full_name, s.group_name FROM attendance a JOIN students s ON s.id = a.student_id
               WHERE a.notified = 0 AND a.status != 'keldi' ORDER BY a.student_id, a.date, a.pair"""
        )

    async def mark_notified(self, ids: list[int]) -> None:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            await self.conn.execute(
                f"UPDATE attendance SET notified = 1 WHERE id IN ({','.join('?' * len(chunk))})", chunk
            )
        await self.conn.commit()

    # ------------------------------------------------------------ dars jadvali
    async def replace_schedule(self, rows: list[dict]) -> tuple[int, int]:
        """Fayldagi guruhlarning eski jadvalini o'chirib, yangisini yozadi."""
        keys = sorted({r["group_key"] for r in rows})
        for k in keys:
            await self.conn.execute("DELETE FROM schedule WHERE group_key = ?", (k,))
        await self.conn.executemany(
            """INSERT INTO schedule (group_name, group_key, weekday, pair, start_time, end_time,
                                     subject, lesson_type, teacher, room, week_type, subgroup)
               VALUES (:group_name, :group_key, :weekday, :pair, :start_time, :end_time,
                       :subject, :lesson_type, :teacher, :room, :week_type, :subgroup)""",
            [{"subgroup": None, **r} for r in rows],
        )
        await self._tag("schedule", "group_key = ?", [(k,) for k in keys])
        await self.conn.commit()
        return len(rows), len(keys)

    async def schedule_for(self, gkey: str, weekday: int, week_type: str) -> list[dict]:
        return await self.fetchall(
            """SELECT * FROM schedule WHERE group_key = ? AND weekday = ? AND week_type IN ('har', ?)
               ORDER BY pair""",
            (gkey, weekday, week_type),
        )

    async def group_schedule(self, gkey: str) -> list[dict]:
        return await self.fetchall("SELECT * FROM schedule WHERE group_key = ? ORDER BY weekday, pair", (gkey,))

    # ------------------------------------------------------------ tanlov fanlari va 2-til jadvali
    async def replace_elective_schedule(self, rows: list[dict]) -> tuple[int, list[str]]:
        """Fayldagi fanlarning eski darslari yangisiga almashtiriladi; boshqa fanlar o'zgarmaydi."""
        keys = sorted({r["subject_key"] for r in rows})
        for k in keys:
            await self.conn.execute("DELETE FROM elective_schedule WHERE subject_key = ?", (k,))
        await self.conn.executemany(
            """INSERT INTO elective_schedule (subject, subject_key, stream, group_key, group_name, weekday, pair,
                                              start_time, end_time, lesson_type, teacher, room, week_type)
               VALUES (:subject, :subject_key, :stream, :group_key, :group_name, :weekday, :pair,
                       :start_time, :end_time, :lesson_type, :teacher, :room, :week_type)""",
            [{k: r.get(k) for k in ("subject", "subject_key", "stream", "group_key", "group_name", "weekday", "pair",
                                    "start_time", "end_time", "lesson_type", "teacher", "room", "week_type")}
             for r in rows],
        )
        await self._tag("elective_schedule", "subject_key = ?", [(k,) for k in keys])
        await self.conn.commit()
        return len(rows), sorted({r["subject"] for r in rows})

    async def elective_lessons(self, weekday: int, week_type: str) -> list[dict]:
        return await self.fetchall(
            """SELECT * FROM elective_schedule WHERE weekday = ? AND week_type IN ('har', ?) ORDER BY pair""",
            (weekday, week_type))

    async def elective_subject_keys(self) -> set[str]:
        return {r["subject_key"] for r in await self.fetchall("SELECT DISTINCT subject_key FROM elective_schedule")}

    async def enrolled_subject_keys(self) -> set[str]:
        return {r["subject_key"] for r in await self.fetchall("SELECT DISTINCT subject_key FROM student_subjects")}

    # ------------------------------------------------------------ talabaning shaxsiy fanlari
    async def replace_enrollment(self, rows: list[dict]) -> tuple[int, int]:
        """rows: {student_id, subject, subject_key, subgroup}. Fayldagi talabalarning eski ro'yxati almashtiriladi."""
        sids = sorted({r["student_id"] for r in rows})
        for sid in sids:
            await self.conn.execute("DELETE FROM student_subjects WHERE student_id = ?", (sid,))
        await self.conn.executemany(
            """INSERT OR REPLACE INTO student_subjects (student_id, subject, subject_key, subgroup)
               VALUES (:student_id, :subject, :subject_key, :subgroup)""",
            [{k: r.get(k) for k in ("student_id", "subject", "subject_key", "subgroup")} for r in rows],
        )
        await self._tag("student_subjects", "student_id = ?", [(sid,) for sid in sids])
        await self.conn.commit()
        return len(sids), len(rows)

    async def enrollment_for(self, sid: int) -> list[dict]:
        return await self.fetchall(
            "SELECT subject, subject_key, subgroup FROM student_subjects WHERE student_id = ? ORDER BY subject", (sid,))

    async def group_subject_keys(self, gkey: str) -> set[str]:
        """Guruhda kamida bitta talaba uchun kiritilgan fanlar — bular shaxsiy (tanlov/til) darslar hisoblanadi."""
        rows = await self.fetchall(
            """SELECT DISTINCT ss.subject_key FROM student_subjects ss JOIN students s ON s.id = ss.student_id
               WHERE s.group_key = ?""", (gkey,))
        return {r["subject_key"] for r in rows}

    # ------------------------------------------------------------ baholar
    async def upsert_grades(self, rows: list[dict]) -> list[dict]:
        """Baholarni yozadi va yangi yoki o'zgargan baholar ro'yxatini qaytaradi."""
        old = {
            (r["student_id"], r["subject"], r["control_type"], r["semester"]): r["score"]
            for r in await self.fetchall("SELECT student_id, subject, control_type, semester, score FROM grades")
        }
        changed = [
            r for r in rows
            if (r["student_id"], r["subject"], r["control_type"], r["semester"]) not in old
            or old[(r["student_id"], r["subject"], r["control_type"], r["semester"])] != r["score"]
        ]
        await self.conn.executemany(
            """INSERT INTO grades (student_id, subject, control_type, score, max_score, date, semester, credits)
               VALUES (:student_id, :subject, :control_type, :score, :max_score, :date, :semester, :credits)
               ON CONFLICT(student_id, subject, control_type, semester) DO UPDATE SET
                 score = excluded.score,
                 credits = COALESCE(excluded.credits, grades.credits),
                 max_score = COALESCE(excluded.max_score, grades.max_score),
                 date = COALESCE(excluded.date, grades.date)""",
            [{**r, "credits": r.get("credits")} for r in rows],
        )
        ts = now_iso()
        await self.conn.executemany(
            """INSERT INTO grade_history (student_id, subject, control_type, semester, score, max_score, credits,
                                          recorded_at) VALUES (?,?,?,?,?,?,?,?)""",
            [(r["student_id"], r["subject"], r["control_type"], r["semester"], r["score"], r.get("max_score"),
              r.get("credits"), ts) for r in changed])
        await self._tag("grades", "student_id = ? AND subject = ? AND control_type = ? AND semester = ?",
                        [(r["student_id"], r["subject"], r["control_type"], r["semester"]) for r in rows])
        await self._tag("grade_history", "recorded_at = ?", [(ts,)])
        await self.conn.commit()
        return changed

    # ------------------------------------------------------------ yozishma (Web App va bot)
    async def add_message(self, sid: int, parent_id: int, sender: str, text: str, author_id: int | None = None,
                          author_name: str | None = None, question_id: int | None = None) -> int:
        cur = await self.conn.execute(
            """INSERT INTO messages (student_id, parent_id, sender, author_id, author_name, text, question_id, created_at)
               VALUES (?,?,?,?,?,?,?,?)""", (sid, parent_id, sender, author_id, author_name, text, question_id, now_iso()))
        await self.conn.commit()
        return cur.lastrowid

    async def thread(self, sid: int, parent_id: int, limit: int = 200) -> list[dict]:
        rows = await self.fetchall("SELECT * FROM messages WHERE student_id = ? AND parent_id = ? ORDER BY id DESC LIMIT ?",
                                   (sid, parent_id, limit))
        return rows[::-1]

    async def mark_thread_read(self, sid: int, parent_id: int, reader: str) -> None:
        """reader — kim o'qidi: parent (kurs koordinatori xabarlarini) yoki staff (ota-ona xabarlarini)."""
        other = "staff" if reader == "parent" else "parent"
        await self.execute("UPDATE messages SET read_at = ? WHERE student_id = ? AND parent_id = ? AND sender = ? "
                           "AND read_at IS NULL", (now_iso(), sid, parent_id, other))

    async def unread_for_parent(self, parent_id: int) -> dict[int, int]:
        rows = await self.fetchall("SELECT student_id, COUNT(*) AS n FROM messages WHERE parent_id = ? AND sender = 'staff' "
                                   "AND read_at IS NULL GROUP BY student_id", (parent_id,))
        return {r["student_id"]: r["n"] for r in rows}

    async def inbox(self, limit: int = 100) -> list[dict]:
        """Kurs koordinatori uchun: har bir suhbatning oxirgi xabari va o'qilmaganlar soni."""
        return await self.fetchall(
            """SELECT m.student_id, m.parent_id, m.text AS last_text, m.sender AS last_sender, m.created_at AS last_at,
                      (SELECT COUNT(*) FROM messages u WHERE u.student_id = m.student_id AND u.parent_id = m.parent_id
                        AND u.sender = 'parent' AND u.read_at IS NULL) AS unread,
                      s.full_name, s.group_name, p.tg_name, p.phone
               FROM messages m
               JOIN (SELECT student_id, parent_id, MAX(id) AS mid FROM messages GROUP BY student_id, parent_id) x
                 ON x.mid = m.id
               JOIN students s ON s.id = m.student_id
               LEFT JOIN parents p ON p.tg_id = m.parent_id
               ORDER BY unread > 0 DESC, m.id DESC LIMIT ?""", (limit,))

    async def open_question_for(self, sid: int, parent_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM questions WHERE student_id = ? AND parent_id = ? AND answer IS NULL "
                                   "ORDER BY id DESC LIMIT 1", (sid, parent_id))

    # ------------------------------------------------------------ bildirishnomalar markazi
    async def add_notification(self, parent_id: int, text: str, student_id: int | None = None,
                               kind: str | None = None) -> None:
        """kind: att | pay | grade | digest | link — Web App'da «Ochish» qaysi bo'limga olib borishini belgilaydi."""
        await self.execute("INSERT INTO notifications (parent_id, text, created_at, student_id, kind, import_id) "
                           "VALUES (?,?,?,?,?,?)", (parent_id, text, now_iso(), student_id, kind, _imp()))

    async def notifications(self, parent_id: int, limit: int = 60) -> list[dict]:
        return await self.fetchall("SELECT * FROM notifications WHERE parent_id = ? ORDER BY id DESC LIMIT ?",
                                   (parent_id, limit))

    async def unread_notifications(self, parent_id: int) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS n FROM notifications WHERE parent_id = ? AND read_at IS NULL",
                                  (parent_id,))
        return row["n"] if row else 0

    async def mark_notifications_read(self, parent_id: int) -> None:
        await self.execute("UPDATE notifications SET read_at = ? WHERE parent_id = ? AND read_at IS NULL",
                           (now_iso(), parent_id))

    async def grade_history(self, sid: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM grade_history WHERE student_id = ? ORDER BY recorded_at", (sid,))

    async def attendance_rows(self, sid: int, d1: str, d2: str) -> list[dict]:
        return await self.fetchall("SELECT date, status, hours FROM attendance WHERE student_id = ? AND date BETWEEN ? AND ?",
                                   (sid, d1, d2))

    # ------------------------------------------------------------ HEMIS akademik qarzdorlar ro'yxati
    async def replace_academic_debts(self, rows: list[dict], scope: set[int] | None = None) -> int:
        """Ro'yxatni yangilaydi: scope dagi talabalarning (fayldagi guruhlar talabalari) eski yozuvlari o'chiriladi va
        fayldagilar yoziladi — ro'yxatdan chiqqan fan qarz yopilgan hisoblanadi; boshqa guruhlarga tegilmaydi.
        scope=None — butun kurs. Bir talabaning bir xil fani (semestri bilan) bir marta saqlanadi."""
        now = now_iso()
        if scope is None:
            await self.conn.execute("DELETE FROM academic_debts")
        else:
            ids = sorted(scope | {r["student_id"] for r in rows})
            for i in range(0, len(ids), 500):
                chunk = ids[i:i + 500]
                await self.conn.execute(f"DELETE FROM academic_debts WHERE student_id IN ({','.join('?' * len(chunk))})", chunk)
        await self.conn.executemany(
            "INSERT OR IGNORE INTO academic_debts (student_id, subject, semester, credits, academic_year, created_at) "
            "VALUES (?,?,?,?,?,?)",
            [(r["student_id"], r["subject"], r.get("semester") or "", r.get("credits"), r.get("year"), now) for r in rows])
        await self._tag("academic_debts", "created_at = ?", [(now,)])
        await self.conn.commit()
        row = await self.fetchone("SELECT COUNT(*) AS n FROM academic_debts")
        return row["n"] if row else 0

    # ------------------------------------------------------------ rasmiy GPA (HEMIS)
    async def add_gpa(self, rows: list[dict]) -> int:
        ts, imp = now_iso(), _imp()
        await self.conn.executemany(
            "INSERT INTO gpa_records (student_id, gpa, subjects, credits, debts, method, year, changed_at, recorded_at, "
            "import_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(r["student_id"], r["gpa"], r.get("subjects"), r.get("credits"), r.get("debts"), r.get("method"),
              r.get("year"), r.get("changed_at"), ts, imp) for r in rows])
        await self.conn.commit()
        return len(rows)

    async def gpa_for(self, sid: int) -> dict | None:
        return await self.fetchone("SELECT * FROM gpa_records WHERE student_id = ? ORDER BY id DESC LIMIT 1", (sid,))

    async def gpa_history(self, sid: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM gpa_records WHERE student_id = ? ORDER BY id", (sid,))

    async def bulk_gpa(self) -> dict[int, dict]:
        rows = await self.fetchall(
            """SELECT g.* FROM gpa_records g
               JOIN (SELECT student_id, MAX(id) AS mid FROM gpa_records GROUP BY student_id) m ON g.id = m.mid""")
        return {r["student_id"]: r for r in rows}

    async def academic_debts_for(self, sid: int) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM academic_debts WHERE student_id = ? ORDER BY semester, subject", (sid,))

    async def bulk_academic_debts(self) -> dict[int, list[dict]]:
        out: dict[int, list[dict]] = {}
        for r in await self.fetchall("SELECT * FROM academic_debts ORDER BY semester, subject"):
            out.setdefault(r["student_id"], []).append(r)
        return out

    async def grades_for(self, sid: int) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM grades WHERE student_id = ? ORDER BY semester DESC, subject, control_type", (sid,)
        )

    # ------------------------------------------------------------ ogohlantirishlar
    async def warning_sent(self, sid: int, kind: str, level: str) -> bool:
        row = await self.fetchone(
            "SELECT 1 FROM warnings_sent WHERE student_id = ? AND kind = ? AND level = ?", (sid, kind, level)
        )
        return row is not None

    async def mark_warning(self, sid: int, kind: str, level: str) -> None:
        await self.execute(
            "INSERT OR IGNORE INTO warnings_sent (student_id, kind, level, sent_at) VALUES (?, ?, ?, ?)",
            (sid, kind, level, now_iso()),
        )

    async def unmark_warning(self, sid: int, kind: str, level: str) -> None:
        """Talaba chegaradan pastga tushsa — keyin yana oshganda ota-ona qayta ogohlantiriladi."""
        await self.execute("DELETE FROM warnings_sent WHERE student_id = ? AND kind = ? AND level = ?", (sid, kind, level))

    # ------------------------------------------------------------ e'lonlar
    async def add_announcement(self, text: str, target_keys: list[str], admin_id: int, sent: int) -> int:
        return await self.execute(
            "INSERT INTO announcements (text, target, created_by, created_at, sent_count) VALUES (?, ?, ?, ?, ?)",
            (text, ",".join(target_keys), admin_id, now_iso(), sent),
        )

    async def announcements_for(self, keys: set[str], limit: int = 10) -> list[dict]:
        rows = await self.fetchall("SELECT * FROM announcements ORDER BY id DESC LIMIT 200")
        result = []
        for r in rows:
            target = {k for k in r["target"].split(",") if k}
            if not target or target & keys:
                result.append(r)
            if len(result) >= limit:
                break
        return result

    # ------------------------------------------------------------ savollar
    async def add_question(self, parent_id: int, sid: int | None, text: str) -> int:
        return await self.execute(
            "INSERT INTO questions (parent_id, student_id, text, created_at) VALUES (?, ?, ?, ?)",
            (parent_id, sid, text, now_iso()),
        )

    async def get_question(self, qid: int) -> dict | None:
        return await self.fetchone("SELECT * FROM questions WHERE id = ?", (qid,))

    async def answer_question(self, qid: int, answer: str, admin_id: int) -> None:
        await self.execute(
            "UPDATE questions SET answer = ?, answered_by = ?, answered_at = ? WHERE id = ?",
            (answer, admin_id, now_iso(), qid),
        )

    async def open_questions_count(self, parent_id: int) -> int:
        row = await self.fetchone(
            "SELECT COUNT(*) AS n FROM questions WHERE parent_id = ? AND answer IS NULL", (parent_id,)
        )
        return row["n"]

    # ------------------------------------------------------------ sozlamalar va statistika
    # ------------------------------------------------------------ talabalar Telegram guruhlari
    async def get_tg_group(self, chat_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM tg_groups WHERE chat_id = ?", (chat_id,))

    async def add_tg_group(self, chat_id: int, title: str, added_by: int, bot_admin: bool) -> None:
        await self.execute(
            """INSERT INTO tg_groups (chat_id, title, bot_admin, active, added_by, added_at) VALUES (?,?,?,1,?,?)
               ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title, bot_admin = excluded.bot_admin,
                 active = 1""",
            (chat_id, title, int(bot_admin), added_by, now_iso()),
        )

    async def update_tg_group(self, chat_id: int, **fields) -> None:
        allowed = {"title", "group_name", "group_key", "bot_admin", "active"}
        keys = [k for k in fields if k in allowed]
        if keys:
            await self.execute(f"UPDATE tg_groups SET {', '.join(k + ' = ?' for k in keys)} WHERE chat_id = ?",
                               (*[fields[k] for k in keys], chat_id))

    async def migrate_tg_group(self, old_id: int, new_id: int) -> None:
        await self.execute("UPDATE OR IGNORE tg_groups SET chat_id = ? WHERE chat_id = ?", (new_id, old_id))
        await self.execute("UPDATE OR IGNORE tg_group_members SET chat_id = ? WHERE chat_id = ?", (new_id, old_id))

    async def tg_groups(self, active_only: bool = True) -> list[dict]:
        cond = "WHERE g.active = 1" if active_only else ""
        return await self.fetchall(
            f"""SELECT g.*, (SELECT COUNT(*) FROM tg_group_members m WHERE m.chat_id = g.chat_id) AS members
                FROM tg_groups g {cond} ORDER BY g.group_name, g.title"""
        )

    async def remove_tg_group(self, chat_id: int) -> None:
        """Guruh talabalar guruhi emas deb topilsa: guruh va undagi a'zolar yozuvlari o'chiriladi."""
        await self.execute("DELETE FROM tg_group_members WHERE chat_id = ?", (chat_id,))
        await self.execute("UPDATE tg_groups SET active = 0 WHERE chat_id = ?", (chat_id,))

    async def record_member(self, tg_id: int, chat_id: int, name: str | None, username: str | None,
                            source: str) -> None:
        ts = now_iso()
        await self.execute(
            """INSERT INTO tg_group_members (tg_id, chat_id, name, username, source, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(tg_id, chat_id) DO UPDATE SET name = excluded.name, username = excluded.username,
                 last_seen = excluded.last_seen""",
            (tg_id, chat_id, name, username, source, ts, ts),
        )

    async def member_groups(self, tg_id: int) -> list[dict]:
        return await self.fetchall(
            """SELECT g.* FROM tg_group_members m JOIN tg_groups g ON g.chat_id = m.chat_id
               WHERE m.tg_id = ? AND g.active = 1""",
            (tg_id,),
        )

    # ------------------------------------------------------------ talaba deb aniqlanganlar (bloklar)
    async def get_block(self, tg_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM access_blocks WHERE tg_id = ?", (tg_id,))

    async def is_blocked(self, tg_id: int) -> bool:
        return bool(await self.fetchone(
            "SELECT 1 FROM access_blocks WHERE tg_id = ? AND status = 'blocked'", (tg_id,)))

    async def add_block(self, tg_id: int, phone: str | None, name: str | None, username: str | None,
                        reason: str, detail: str) -> None:
        await self.execute(
            """INSERT INTO access_blocks (tg_id, phone, name, username, reason, detail, status, created_at)
               VALUES (?,?,?,?,?,?,'blocked',?)
               ON CONFLICT(tg_id) DO UPDATE SET phone = COALESCE(excluded.phone, access_blocks.phone),
                 name = excluded.name, username = excluded.username, reason = excluded.reason,
                 detail = excluded.detail, status = 'blocked', created_at = excluded.created_at,
                 decided_by = NULL, decided_at = NULL""",
            (tg_id, phone, name, username, reason, detail, now_iso()),
        )
        # talaba deb topilgan foydalanuvchi xabar olmaydi; shaxsiy chatdagi har qanday so'rovini
        # BlockedUserMiddleware to'xtatadi. Bog'lanishlar saqlanadi — kurs koordinatori ruxsat bersa, qayta tiklanadi.
        await self.execute("UPDATE parents SET active = 0 WHERE tg_id = ?", (tg_id,))

    async def set_block_status(self, tg_id: int, status: str, admin_id: int) -> None:
        await self.execute(
            "UPDATE access_blocks SET status = ?, decided_by = ?, decided_at = ? WHERE tg_id = ?",
            (status, admin_id, now_iso(), tg_id),
        )
        await self.execute("UPDATE parents SET active = ? WHERE tg_id = ?", (int(status == "allowed"), tg_id))

    async def list_blocks(self, status: str = "blocked", limit: int = 20) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM access_blocks WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit)
        )

    async def parents_to_recheck(self) -> list[dict]:
        """Kurs koordinatori ota-ona deb tasdiqlamagan va bloklanmagan barcha ro'yxatdan o'tganlar."""
        return await self.fetchall(
            """SELECT p.* FROM parents p
               WHERE p.tg_id NOT IN (SELECT tg_id FROM access_blocks)"""
        )

    # ------------------------------------------------------------ rasmiy hujjatlar
    async def add_document(self, sid: int, doc_type: str, file_id: str, file_unique_id: str | None,
                           file_name: str | None, file_size: int | None, doc_date: str | None,
                           comment: str | None, admin_id: int, batch: str | None = None, redacted: int = 0,
                           source_file_id: str | None = None) -> int:
        cur = await self.conn.execute(
            """INSERT INTO documents (student_id, doc_type, file_id, file_unique_id, file_name, file_size,
                                      doc_date, comment, created_by, created_at, batch, redacted, source_file_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, doc_type, file_id, file_unique_id, file_name, file_size, doc_date, comment, admin_id, now_iso(),
             batch, redacted, source_file_id),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_document(self, doc_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM documents WHERE id = ?", (doc_id,))

    async def documents_for(self, sid: int) -> list[dict]:
        return await self.fetchall(
            """SELECT * FROM documents WHERE student_id = ? AND revoked = 0
               ORDER BY COALESCE(doc_date, substr(created_at, 1, 10)) DESC, id DESC""",
            (sid,),
        )

    async def same_file_sent(self, sid: int, source_file_uid: str | None) -> dict | None:
        """Aynan shu asl fayl shu talabaga avval yuborilganmi (yopilgan nusxalar ham asl fayl bo'yicha)."""
        if not source_file_uid:
            return None
        return await self.fetchone(
            """SELECT * FROM documents WHERE student_id = ? AND revoked = 0
               AND (file_unique_id = ? OR source_file_id = ?)""",
            (sid, source_file_uid, source_file_uid),
        )

    async def documents_in_batch(self, batch: str) -> list[dict]:
        return await self.fetchall("SELECT * FROM documents WHERE batch = ? AND revoked = 0", (batch,))

    async def record_delivery(self, doc_id: int, parent_id: int, message_id: int | None) -> None:
        await self.execute(
            """INSERT OR REPLACE INTO document_deliveries (document_id, parent_id, message_id, sent_at)
               VALUES (?,?,?,?)""",
            (doc_id, parent_id, message_id, now_iso()),
        )

    async def deliveries(self, doc_id: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM document_deliveries WHERE document_id = ?", (doc_id,))

    async def revoke_document(self, doc_id: int, admin_id: int) -> None:
        await self.execute("UPDATE documents SET revoked = 1, revoked_by = ?, revoked_at = ? WHERE id = ?",
                           (admin_id, now_iso(), doc_id))

    # ------------------------------------------------------------ HEMIS davomat statistikasi
    async def upsert_subject_stats(self, rows: list[dict], subject: str, as_of: str) -> list[tuple[int, dict | None, dict]]:
        """Bitta fan bo'yicha HEMIS statistikasi. Qaytaradi: (talaba, shu fan bo'yicha oldingi holat yoki None, yangi)."""
        key = subject_key(subject) or normalize_text(subject)
        out, ts = [], now_iso()
        for r in rows:
            prev = await self.fetchone("SELECT * FROM subject_att_stats WHERE student_id = ? AND subject_key = ? AND as_of < ? "
                                       "ORDER BY as_of DESC LIMIT 1", (r["student_id"], key, as_of))
            await self.conn.execute(
                """INSERT INTO subject_att_stats (student_id, subject, subject_key, as_of, attended, absent, excused, imported_at)
                   VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(student_id, subject_key, as_of) DO UPDATE SET subject = excluded.subject,
                   attended = excluded.attended, absent = excluded.absent, excused = excluded.excused, imported_at = excluded.imported_at""",
                (r["student_id"], subject, key, as_of, r["attended"], r["absent"], r["excused"], ts))
            out.append((r["student_id"], prev, r))
        await self._tag("subject_att_stats", "student_id = ? AND subject_key = ? AND as_of = ?",
                        [(r["student_id"], key, as_of) for r in rows])
        await self.conn.commit()
        return out

    async def latest_subject_stats(self, where: str = "1 = 1", params=()) -> list[dict]:
        """Har bir talaba va fan bo'yicha oxirgi HEMIS statistikasi (where — students s jadvali bo'yicha shart)."""
        return await self.fetchall(
            f"""SELECT x.*, s.full_name, s.group_name, s.hemis_id FROM subject_att_stats x JOIN students s ON s.id = x.student_id
                WHERE {where} AND x.as_of = (SELECT MAX(as_of) FROM subject_att_stats y
                                             WHERE y.student_id = x.student_id AND y.subject_key = x.subject_key)""", params)

    async def upsert_att_stats(self, rows: list[dict], as_of: str) -> list[tuple[int, dict | None, dict]]:
        """Qaytaradi: (talaba, shu sanadan oldingi oxirgi holat yoki None, yangi holat)."""
        out = []
        ts = now_iso()
        for r in rows:
            sid = r["student_id"]
            prev = await self.fetchone(
                "SELECT * FROM attendance_stats WHERE student_id = ? AND as_of < ? ORDER BY as_of DESC LIMIT 1",
                (sid, as_of))
            await self.conn.execute(
                """INSERT INTO attendance_stats (student_id, as_of, attended, absent, excused, self_marked,
                                                 teacher_marked, imported_at) VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(student_id, as_of) DO UPDATE SET attended = excluded.attended,
                     absent = excluded.absent, excused = excluded.excused, self_marked = excluded.self_marked,
                     teacher_marked = excluded.teacher_marked, imported_at = excluded.imported_at""",
                (sid, as_of, r["attended"], r["absent"], r["excused"], r.get("self_marked"),
                 r.get("teacher_marked"), ts))
            out.append((sid, prev, {**r, "as_of": as_of}))
        await self._tag("attendance_stats", "student_id = ? AND as_of = ?", [(r["student_id"], as_of) for r in rows])
        await self.conn.commit()
        return out

    async def latest_att_stats(self, sid: int, since: str | None = None) -> dict | None:
        """Oxirgi holat; since berilsa — faqat shu sanadan keyingi (joriy semestr) yozuvlar."""
        return await self.fetchone(
            "SELECT * FROM attendance_stats WHERE student_id = ? AND as_of >= ? ORDER BY as_of DESC LIMIT 1",
            (sid, since or "0000-00-00"))

    async def att_stats_history(self, sid: int, since: str, limit: int = 10) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM attendance_stats WHERE student_id = ? AND as_of >= ? ORDER BY as_of DESC LIMIT ?",
            (sid, since, limit))
        return list(reversed(rows))

    # ------------------------------------------------------------ to'lov shakli va kontrakt qarzdorligi
    async def set_payment_forms(self, forms: dict[int, str]) -> int:
        await self.conn.executemany("UPDATE students SET payment_form = ? WHERE id = ?",
                                    [(f, sid) for sid, f in forms.items() if f])
        await self.conn.commit()
        return len(forms)

    async def upsert_payments(self, rows: list[dict], as_of: str, year_label: str | None, kind: str = "kontrakt"
                              ) -> list[tuple[int, dict | None, dict]]:
        """kind: 'kontrakt' yoki 'trimestr'. Qaytaradi: (talaba, shu turdagi oldingi holat yoki None, yangi holat)."""
        out, ts = [], now_iso()
        for r in rows:
            sid = r["student_id"]
            prev = await self.fetchone(
                """SELECT * FROM payments WHERE student_id = ? AND kind = ? AND as_of < ?
                   ORDER BY as_of DESC LIMIT 1""", (sid, kind, as_of))
            await self.conn.execute(
                """INSERT INTO payments (student_id, kind, as_of, year_label, contract, paid, debt, overpaid, percent,
                                         note, imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(student_id, kind, as_of) DO UPDATE SET year_label = excluded.year_label,
                     contract = excluded.contract, paid = excluded.paid, debt = excluded.debt,
                     overpaid = excluded.overpaid, percent = excluded.percent, note = excluded.note,
                     imported_at = excluded.imported_at""",
                (sid, kind, as_of, year_label, r.get("contract"), r.get("paid"), r["debt"], r.get("overpaid") or 0,
                 r.get("percent"), r.get("note"), ts))
            out.append((sid, prev, {**r, "as_of": as_of, "kind": kind, "imported_at": ts}))
        await self._tag("payments", "student_id = ? AND kind = ? AND as_of = ?", [(r["student_id"], kind, as_of) for r in rows])
        await self.conn.commit()
        return out

    async def latest_payment(self, sid: int, kind: str = "kontrakt") -> dict | None:
        """Joriy holat (bulk_latest_payments bilan bir xil qoida); None — bu turda hisobot yuklanmagan."""
        p = await self.fetchone(
            "SELECT * FROM payments WHERE student_id = ? AND kind = ? ORDER BY as_of DESC LIMIT 1", (sid, kind))
        st = await self.fetchone("SELECT group_key FROM students WHERE id = ?", (sid,))
        d = self.covered_at(await self.payment_coverage(kind), st["group_key"] if st else None)
        if d and (p is None or p["as_of"] < d):
            return self._clear(sid, kind, d)
        return p

    async def payment_history(self, sid: int, kind: str = "kontrakt", limit: int = 8) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM payments WHERE student_id = ? AND kind = ? ORDER BY as_of DESC LIMIT ?", (sid, kind, limit))
        return list(reversed(rows))

    async def debtors(self, kind: str = "kontrakt") -> list[dict]:
        """Shu turdagi oxirgi hisobot bo'yicha qarzi bor talabalar, qarz kamayish tartibida."""
        rows = await self.fetchall(
            """SELECT s.id, s.full_name, s.group_name, s.course, p.debt, p.percent, p.as_of, p.contract
               FROM payments p JOIN students s ON s.id = p.student_id
               WHERE p.kind = ? AND p.as_of = (SELECT MAX(as_of) FROM payments p2
                                               WHERE p2.student_id = p.student_id AND p2.kind = p.kind)
                 AND p.debt > 0
               ORDER BY p.debt DESC""", (kind,))
        # keyingi hisobot talaba guruhini qamragan, lekin talaba unda yo'q — qarzdorlar ro'yxatidan chiqadi
        cur = await self.bulk_latest_payments(kind)
        return [r for r in rows if (cur.get(r["id"]) or {}).get("debt", 0) > 0]

    async def get_lang(self, tg_id: int) -> str | None:
        row = await self.fetchone("SELECT lang FROM user_prefs WHERE tg_id = ?", (tg_id,))
        return row["lang"] if row else None

    async def set_lang(self, tg_id: int, lang: str) -> None:
        await self.conn.execute(
            "INSERT INTO user_prefs (tg_id, lang) VALUES (?, ?) ON CONFLICT(tg_id) DO UPDATE SET lang = excluded.lang",
            (tg_id, lang))
        await self.conn.commit()

    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = await self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    async def stats(self, groups: set[str] | None = None) -> dict:
        """Kurs statistikasi; groups — faqat shu guruhlar talabalari bo'yicha (koordinatorning o'z guruhlari)."""
        q = self.fetchone
        if groups is None:
            S, gp = "SELECT id FROM students", ()
            G = ""
        else:
            marks = ",".join("?" * len(groups)) or "NULL"
            S, gp = f"SELECT id FROM students WHERE group_key IN ({marks})", tuple(sorted(groups))
            G = f" AND group_key IN ({marks})"
        return {
            "students": (await q(f"SELECT COUNT(*) n FROM students WHERE 1{G}", gp))["n"],
            "students_with_phone": (await q(f"SELECT COUNT(DISTINCT student_id) n FROM student_phones WHERE student_id IN ({S})", gp))["n"],
            "parents": (await q(f"""SELECT COUNT(*) n FROM parents WHERE {'1' if groups is None else
                                 f'tg_id IN (SELECT parent_id FROM parent_students WHERE student_id IN ({S}))'}""",
                                () if groups is None else gp))["n"],
            "parents_active": (await q(f"""SELECT COUNT(*) n FROM parents WHERE active = 1{'' if groups is None else
                                        f' AND tg_id IN (SELECT parent_id FROM parent_students WHERE student_id IN ({S}))'}""",
                                       () if groups is None else gp))["n"],
            "students_linked": (await q(
                f"""SELECT COUNT(DISTINCT student_id) n FROM parent_students
                   WHERE parent_id NOT IN (SELECT tg_id FROM access_blocks WHERE status = 'blocked')
                     AND student_id IN ({S})""", gp))["n"],
            "attendance": (await q(f"SELECT COUNT(*) n FROM attendance WHERE student_id IN ({S})", gp))["n"],
            "attendance_last": (await q(f"SELECT MAX(date) d FROM attendance WHERE student_id IN ({S})", gp))["d"],
            "schedule_groups": (await q(f"SELECT COUNT(DISTINCT group_key) n FROM schedule WHERE 1{G}", gp))["n"],
            "grades": (await q(f"SELECT COUNT(*) n FROM grades WHERE student_id IN ({S})", gp))["n"],
            "pending_requests": (await q(f"SELECT COUNT(*) n FROM link_requests WHERE status = 'pending' "
                                         f"AND student_id IN ({S})", gp))["n"],
            "open_questions": (await q(f"SELECT COUNT(*) n FROM questions WHERE answer IS NULL"
                                       + ("" if groups is None else f" AND student_id IN ({S})"),
                                       () if groups is None else gp))["n"],
            "students_self_phone": (await q(f"SELECT COUNT(DISTINCT student_id) n FROM student_self_phones "
                                            f"WHERE student_id IN ({S})", gp))["n"],
            "tg_groups": (await q("SELECT COUNT(*) n FROM tg_groups WHERE active = 1"))["n"],
            "tg_groups_admin": (await q("SELECT COUNT(*) n FROM tg_groups WHERE active = 1 AND bot_admin = 1"))["n"],
            "tg_members": (await q("SELECT COUNT(DISTINCT tg_id) n FROM tg_group_members"))["n"],
            "blocked": (await q("SELECT COUNT(*) n FROM access_blocks WHERE status = 'blocked'"))["n"],
            "documents": (await q(f"SELECT COUNT(*) n FROM documents WHERE revoked = 0 AND student_id IN ({S})", gp))["n"],
            "grant": (await q(f"SELECT COUNT(*) n FROM students WHERE payment_form = 'Davlat granti'{G}", gp))["n"],
            "contract": (await q(f"SELECT COUNT(*) n FROM students WHERE payment_form = 'To''lov-shartnoma'{G}", gp))["n"],
        }

    async def coordinator_contact(self, st: dict, course_key: str | None) -> tuple[str | None, str | None]:
        """Ota-onaga ko'rinadigan kurs koordinatori: talabalar faylidagi «Kurs koordinatori» → talaba guruhi
        biriktirilgan koordinatorning /koordinator bilan kiritgani → kurs bo'yicha umumiy /koordinator."""
        from tenancy import group_coordinators
        name, phone = st.get("tutor_name"), st.get("tutor_phone")
        if name or phone:
            return name, phone
        for uid in group_coordinators(st.get("group_name") or st.get("group_key"), course_key):
            n, p = await self.get_setting(f"coordinator_name:{uid}"), await self.get_setting(f"coordinator_phone:{uid}")
            if n or p:
                return n, p
        return await self.get_setting("coordinator_name"), await self.get_setting("coordinator_phone")



class CourseDB:
    """`db` — joriy kurs bazasi (tenancy.current_course() bo'yicha). Har bir kursning bazasi alohida fayl:
    data/<kurs>/bot.db. `db.connect(path)` — bitta baza rejimi (sinov va namunaviy ma'lumotlar uchun)."""

    def __init__(self) -> None:
        self._dbs: dict[str, Database] = {}
        self._single: Database | None = None
        self.multi = False  # ko'p kursli rejim (bot.py) — kurslar soni nol bo'lishi ham mumkin

    async def connect(self, path: str) -> None:
        d = Database()
        await d.connect(path)
        self._single = d
        if central.conn is None:
            await central.connect(":memory:")

    async def open_courses(self, data_dir, keys: list[str]) -> None:
        self.multi = True
        for key in keys:
            await self.open_course(data_dir, key)

    async def open_course(self, data_dir, key: str) -> None:
        """Kurs bazasini ochadi (yangi kurs — papka va baza yaratiladi); qayta ishga tushirishsiz."""
        if key not in self._dbs:
            d = Database()
            await d.connect(str(Path(data_dir) / key / "bot.db"))
            self._dbs[key] = d

    def keys(self) -> list[str]:
        """Barcha kurslar (bitta baza rejimida — bitta)."""
        return list(self._dbs) if self.multi else ["_"]

    def current(self) -> Database:
        if self._single is not None:
            return self._single
        key = current_course()
        if key in self._dbs:
            return self._dbs[key]
        raise RuntimeError(f"Joriy kurs aniqlanmagan yoki noma'lum: {key!r}")

    def for_course(self, key: str) -> Database:
        return self._single or self._dbs[key]

    async def close(self) -> None:
        single = self._single is not None
        for d in ([self._single] if self._single else []) + list(self._dbs.values()):
            await d.close()
        self._dbs, self._single, self.multi = {}, None, False
        if single:  # bitta baza rejimida umumiy ro'yxat xotirada ochilgan — u ham yopiladi
            await central.close()

    def __getattr__(self, name):
        return getattr(self.current(), name)


db = CourseDB()
