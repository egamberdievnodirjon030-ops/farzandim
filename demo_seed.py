"""Sinov uchun namunaviy (to'qima) ma'lumotlar.

    python demo_seed.py 998901234567 [998935556677] [--kurs 3-kurs]

Birinchi raqam «ota-ona telefoni» sifatida 2 ta namunaviy talabaga biriktiriladi.
Botda shu raqam bilan ro'yxatdan o'tsangiz, barcha bo'limlarni sinab ko'rasiz.
Ikkinchi (ixtiyoriy) raqam uchinchi namunaviy talabaning O'Z raqami sifatida yoziladi —
shu raqamli boshqa Telegram akkaunt bilan kirib ko'rsangiz, bot uni talaba deb rad etadi.
Ko'p kursli rejimda ma'lumotlar --kurs da ko'rsatilgan kurs papkasiga (data/<kurs>/bot.db), ko'rsatilmasa —
birinchi kursga yoziladi. Haqiqiy ishga tushirishdan oldin o'sha kursning bot.db faylini o'chiring.
"""
import asyncio
import random
import sys
from datetime import timedelta

import os
from pathlib import Path

from config import COURSES, DATA_DIR, DB_PATH, HOURS_PER_PAIR
from database import db
from utils import group_key, normalize_phone, now, semester_start, subject_key, today

GROUP = "DEMO-101"
STUDENTS = [
    {"hemis_id": "DEMO0001", "full_name": "Karimov Jasur Anvarovich", "birth_date": "2007-03-05"},
    {"hemis_id": "DEMO0002", "full_name": "Karimova Madina Anvarovna", "birth_date": "2008-11-20"},
    {"hemis_id": "DEMO0003", "full_name": "Tursunov Bekzod Olimovich", "birth_date": "2007-07-14"},
]
SCHEDULE = {  # hafta kuni: [(juftlik, fan, turi, o'qituvchi, xona)]
    1: [(1, "Iqtisodiyot nazariyasi", "ma'ruza", "A. Rahimov", "201"), (2, "Ingliz tili", "amaliy", "D. Saidova", "305")],
    2: [(1, "Xalqaro munosabatlar tarixi", "ma'ruza", "B. Qodirov", "Katta zal"), (2, "Matematika", "amaliy", "S. Aliyev", "112")],
    3: [(1, "Iqtisodiyot nazariyasi", "seminar", "A. Rahimov", "204"), (2, "Ingliz tili", "amaliy", "D. Saidova", "305"),
        (3, "Axborot texnologiyalari", "laboratoriya", "N. Yusupov", "Kompyuter xonasi")],
    4: [(1, "Matematika", "ma'ruza", "S. Aliyev", "201"), (2, "Xalqaro munosabatlar tarixi", "seminar", "B. Qodirov", "210")],
    5: [(1, "Ingliz tili", "amaliy", "D. Saidova", "305"), (2, "Axborot texnologiyalari", "ma'ruza", "N. Yusupov", "201")],
}

# Ikkinchi chet tili va tanlov fanlari: guruhga bog'lanmagan alohida jadval (shaxsiy jadval namunasi)
ELECTIVE_SCHEDULE = [  # (fan, hafta kuni, juftlik, turi, o'qituvchi, xona)
    ("Fransuz tili I", 2, 3, "amaliy", "M. Dubois", "402"), ("Fransuz tili I", 4, 3, "amaliy", "M. Dubois", "402"),
    ("Nemis tili I", 2, 3, "amaliy", "K. Weber", "403"), ("Nemis tili I", 4, 3, "amaliy", "K. Weber", "403"),
    ("Siyosat va OAV", 3, 4, "seminar", "D. Nazarova", "215"),
]
ENROLL = {"DEMO0001": ["Fransuz tili I"], "DEMO0002": ["Nemis tili I", "Siyosat va OAV"],
          "DEMO0003": ["Fransuz tili I"]}


def target_db(course: str | None) -> str:
    """Qaysi bazaga yoziladi: --kurs ko'rsatilsa — o'sha kurs papkasi; DB_PATH aniq berilsa — o'sha fayl;
    aks holda — birinchi kurs (ko'p kursli rejimda har bir kursning bazasi: data/<kurs>/bot.db)."""
    if course:
        if course not in COURSES:
            raise SystemExit(f"Noma'lum kurs: {course}. Mavjud: {', '.join(COURSES) or '—'}")
        return str(Path(DATA_DIR) / course / "bot.db")
    if os.getenv("DB_PATH") or not COURSES:
        return DB_PATH
    return str(Path(DATA_DIR) / next(iter(COURSES)) / "bot.db")


async def main(phone: str, student_phone: str | None = None, course: str | None = None) -> None:
    path = target_db(course)
    await db.connect(path)
    print(f"Baza: {path}")
    rows = []
    for i, s in enumerate(STUDENTS):
        rows.append({**s, "group_name": GROUP, "faculty": "Namunaviy fakultet", "course": 1,
                     "phones": [phone] if i < 2 else [], "tutor_name": "Namunaviy Koordinator", "tutor_phone": phone,
                     "payment_form": "Davlat granti" if i == 1 else "To'lov-shartnoma",
                     "student_phones": [student_phone] if (i == 2 and student_phone) else []})
    await db.upsert_students(rows)
    await db.replace_schedule([
        {"group_name": GROUP, "group_key": group_key(GROUP), "weekday": wd, "pair": p, "start_time": None,
         "end_time": None, "subject": subj, "lesson_type": lt, "teacher": t, "room": room, "week_type": "har"}
        for wd, lessons in SCHEDULE.items() for p, subj, lt, t, room in lessons
    ])
    ids = {r["hemis_id"]: r["id"] for r in await db.all_students_brief()}
    await db.replace_enrollment([{"student_id": ids[h], "subject": subj, "subject_key": subject_key(subj),
                                  "subgroup": None} for h, subjects in ENROLL.items() if h in ids for subj in subjects])
    await db.replace_elective_schedule([
        {"subject": subj, "subject_key": subject_key(subj), "stream": None, "group_key": None, "group_name": None,
         "weekday": wd, "pair": p, "start_time": None, "end_time": None, "lesson_type": lt, "teacher": t,
         "room": room, "week_type": "har"} for subj, wd, p, lt, t, room in ELECTIVE_SCHEDULE])
    rnd = random.Random(42)
    att = []
    d = max(semester_start(), today() - timedelta(days=21))
    while d < today():
        day = list(SCHEDULE.get(d.isoweekday(), [])) + [
            (p, subj, lt, t, room) for subj, wd, p, lt, t, room in ELECTIVE_SCHEDULE if wd == d.isoweekday()]
        for p, subj, lt, t, _ in day:
            for hid in ids:
                if any(subj == e[0] for e in ELECTIVE_SCHEDULE) and subj not in ENROLL.get(hid, []):
                    continue  # talaba bu tanlov fani / tilga biriktirilmagan
                status = rnd.choices(["keldi", "kelmadi", "sababli", "kechikdi"], [85, 8, 4, 3])[0]
                att.append((ids[hid], d.isoformat(), p, subj, lt, t, status, HOURS_PER_PAIR, 1))
        d += timedelta(days=1)
    await db.upsert_attendance(att)
    grades = []
    for hid, sid in ids.items():
        for subj in ("Iqtisodiyot nazariyasi", "Ingliz tili", "Matematika"):
            grades.append({"student_id": sid, "subject": subj, "control_type": "Joriy nazorat",
                           "score": rnd.randint(18, 30), "max_score": 30, "date": None, "semester": "1"})
    # 100 ballik umumiy baholar (kreditlar bilan): akademik qarzdorlik va GPA namunasi
    totals = {"DEMO0001": (("Iqtisodiyot nazariyasi", 86, 6), ("Ingliz tili", 74, 4), ("Matematika", 52, 6)),
              "DEMO0002": (("Iqtisodiyot nazariyasi", 91, 6), ("Ingliz tili", 95, 4), ("Matematika", 69.5, 6)),
              "DEMO0003": (("Iqtisodiyot nazariyasi", 64, 6), ("Ingliz tili", 45, 4), ("Matematika", 58, 6))}
    for hid, items in totals.items():
        if hid in ids:
            for subj, score, credits in items:
                grades.append({"student_id": ids[hid], "subject": subj, "control_type": "O'rtacha ball", "score": score,
                               "max_score": 100, "date": None, "semester": "1", "credits": credits})
    await db.upsert_grades(grades)
    # Dinamika namunasi: bir oy oldingi ballar (baholar tarixida) — Jasurda Matematika tushgan, Ingliz tili ko'tarilgan
    month_ago = (now() - timedelta(days=35)).isoformat(timespec="seconds")
    earlier = {"DEMO0001": {"Matematika": 70, "Ingliz tili": 60, "Iqtisodiyot nazariyasi": 86},
               "DEMO0002": {"Matematika": 75, "Ingliz tili": 92, "Iqtisodiyot nazariyasi": 91}}
    for hid, subjects in earlier.items():
        if hid in ids:
            for subj, score in subjects.items():
                await db.execute(
                    """INSERT INTO grade_history (student_id, subject, control_type, semester, score, max_score, credits,
                                                  recorded_at) VALUES (?, ?, 'O''rtacha ball', '1', ?, 100, NULL, ?)""",
                    (ids[hid], subj, score, month_ago))
    await db.add_announcement("Namunaviy e'lon: ota-onalar yig'ilishi shanba kuni soat 10:00 da bo'lib o'tadi.\n---ru\nОбразец объявления: родительское собрание состоится в субботу в 10:00.\n---en\nSample announcement: the parents' meeting will be held on Saturday at 10:00.",
                              [], 0, 0)
    await db.close()
    print(f"Tayyor: {len(ids)} talaba, {len(att)} davomat yozuvi, {len(grades)} baho. Telefon: {phone}")


if __name__ == "__main__":
    course = None
    if "--kurs" in sys.argv:
        i = sys.argv.index("--kurs")
        course = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        del sys.argv[i:i + 2]
    if len(sys.argv) < 2 or not normalize_phone(sys.argv[1]):
        sys.exit("Foydalanish: python demo_seed.py 998901234567 [talaba_raqami] [--kurs KURS]")
    student = normalize_phone(sys.argv[2]) if len(sys.argv) > 2 else None
    asyncio.run(main(normalize_phone(sys.argv[1]), student, course))
