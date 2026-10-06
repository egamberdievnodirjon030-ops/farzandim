"""Excel (.xlsx) fayllarni o'qish: talabalar, davomat, dars jadvali, baholar.

Ustun nomlari qat'iy emas — sarlavha qatori avtomatik topiladi va turli yozilishlar
(lotin/kirill, tutuq belgili/belgisiz, «F.I.Sh» / «FIO» va h.k.) tanib olinadi.
"""
from __future__ import annotations

import re
from datetime import date
from dataclasses import dataclass, field

import openpyxl

from config import HOURS_PER_PAIR
from utils import (cell_str, group_key, is_masked, nice_name, normalize_payment_form, normalize_status,
                   normalize_text, parse_course,
                   parse_date, parse_float, parse_int, parse_time, parse_weekday, split_phones, normalize_phone,
                   subgroup_key, subject_key)

_ID = ["hemis id", "talaba id", "talaba id raqami", "student id", "id", "hemis", "id raqami"]
_NAME = ["f i sh", "fish", "fio", "familiya ism sharif", "familiya ism otasining ismi", "talaba",
         "talaba f i sh", "talabaning f i sh", "ism familiya", "familiya ism", "full name", "fullname",
         "f i o", "student", "familiya imya otchestvo", "fio studenta", "full name of student",
         "talabaning familiyasi ismi sharifi", "familiyasi ismi sharifi"]
_GROUP = ["guruh", "guruh nomi", "guruhi", "group", "gruppa"]
# Talabaning O'Z telefoni. Qo'shimchasiz «Telefon» ustuni ham shu yerga tushadi: HEMIS ro'yxatlarida
# bu odatda talabaning raqami. Ota-ona raqamlari faqat aniq nom bilan («Ota-ona telefoni» va h.k.) olinadi.
_STREAM = ["seminar raqami", "seminar guruhi", "seminar nomeri", "oqim", "oqimi", "oqim raqami", "til guruhi", "tanlov guruhi", "kichik guruh", "kichik guruhi", "guruhcha",
                   "podgruppa", "potok", "stream", "subgroup", "kichik guruh raqami"]
_SELF_PHONE = ["talaba telefoni", "talabaning telefoni", "talaba telefon raqami", "talabaning telefon raqami",
               "talaba raqami", "shaxsiy telefon", "shaxsiy telefon raqami", "oz telefoni", "telefon",
               "telefon raqami", "telefon raqam", "tel", "tel raqami", "mobil telefon", "mobil raqam", "phone",
               "phone number", "mobile", "telefon studenta", "mobilniy telefon", "nomer telefona"]

ALIASES: dict[str, dict[str, list[str]]] = {
    "students": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "faculty": ["fakultet", "faculty", "fakulteti"],
        "course": ["kurs", "course", "bosqich", "talaba kursi", "kursi", "oquv kursi"],
        "full_name_cyr": ["f i sh kirill", "fish kirill", "fio kirill", "f i o kirill", "kirill yozuvida", "kirillcha",
                          "ism familiya kirill", "familiya ism kirill", "fio rus", "f i sh ruscha"],
        "payment_form": ["tolov shakli", "tolov turi", "tolov asosi", "moliyalashtirish manbai", "moliyalashtirish",
                         "oqish asosi", "forma oplaty", "istochnik finansirovaniya", "payment form"],
        "birth_date": ["tugilgan sana", "tugilgan kun", "tugilgan sanasi", "birth date", "date of birth",
                       "data rojdeniya"],
        "phones": ["ota ona telefoni", "ota ona telefon", "ota onasi telefoni", "ota ona tel", "telefon ota ona",
                   "telefon ota onasi", "tel ota ona", "vasiy telefoni", "ota ona yoki vasiy telefoni",
                   "ota onalar telefoni", "parent phone", "ota ona telefon raqami", "ota ona raqami",
                   "telefon roditeley", "telefon roditelya"],
        "phones_father": ["otasi telefoni", "otasining telefoni", "ota telefoni", "otasi tel", "telefon ottsa",
                          "telefon otsa", "telefon otasi", "tel otasi"],
        "phones_mother": ["onasi telefoni", "onasining telefoni", "ona telefoni", "onasi tel", "telefon materi",
                          "telefon onasi", "tel onasi"],
        "student_phones": _SELF_PHONE,
        # kurs koordinatori (oldingi nomi — tyutor; eski fayllar ham o'qilaveradi)
        "tutor_name": ["kurs koordinatori", "koordinator", "koordinatori", "kurs koordinatori f i sh",
                       "kurs koordinatorining f i sh", "tyutor", "tutor", "tyutor f i sh", "tyutori", "kurator"],
        "tutor_phone": ["kurs koordinatori telefoni", "koordinator telefoni", "kurs koordinatori tel",
                        "kurs koordinatori telefon raqami", "kurs koordinatorining telefoni", "tyutor telefoni",
                        "tyutor tel", "tutor phone", "tyutor telefon raqami", "kurator telefoni"],
    },
    # HEMIS «O'quvchilarni darslarga qatnashish statistikasi» — har bir talaba uchun jami ko'rsatkichlar
    "attendance_stats": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "attended": ["qatnashganlar soni", "qatnashganlar", "qatnashgan soat", "qatnashgan", "qatnashgan darslar"],
        "absent": ["qatnashmaganlar soni", "qatnashmaganlar", "qatnashmagan soat", "qatnashmagan",
                   "qoldirilgan soat", "qoldirgan soat", "qoldirilgan darslar", "jami qoldirilgan"],
        "excused": ["sabablilar soni", "sabablilar", "sababli", "sababli soat", "sababli qoldirilgan"],
        "self_marked": ["ozi yoqlamadan otganlari soni", "ozi yoqlamadan otganlar"],
        "teacher_marked": ["oqituvchisi tomonidan yoqlamadan otganlari soni",
                           "oqituvchi tomonidan yoqlamadan otganlar"],
    },
    "attendance": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "date": ["sana", "date", "kun", "dars sanasi", "data", "data zanyatiya"],
        "pair": ["juftlik", "para", "pair", "juftlik raqami", "juft"],
        "subject": ["fan", "fan nomi", "subject", "predmet", "fanlar"],
        "lesson_type": ["mashgulot turi", "dars turi", "turi", "type"],
        "teacher": ["oqituvchi", "teacher", "prepodavatel", "oqituvchi f i sh"],
        "status": ["holat", "holati", "davomat", "status", "qatnashuv"],
        "hours": ["soat", "soatlar", "hours", "akademik soat", "soati"],
    },
    "schedule": {
        "group_name": _GROUP,
        "weekday": ["hafta kuni", "kun", "weekday", "kuni"],
        "pair": ["juftlik", "para", "pair", "juftlik raqami", "juft"],
        "start_time": ["boshlanish", "boshlanishi", "start", "boshlanish vaqti"],
        "end_time": ["tugash", "tugashi", "end", "tugash vaqti"],
        "time_range": ["vaqt", "vaqti", "time"],
        "subject": ["fan", "fan nomi", "subject", "predmet"],
        "lesson_type": ["mashgulot turi", "dars turi", "turi", "type"],
        "teacher": ["oqituvchi", "teacher", "prepodavatel"],
        "room": ["xona", "auditoriya", "room", "aud", "xonasi"],
        "week_type": ["hafta turi", "hafta", "toq juft"],
        "code": ["fan kodi", "kod", "code", "fan kod", "subject code", "kodi"],
        "subgroup": ["seminar raqami", "seminar guruhi", "seminar nomeri", "kichik guruh", "kichik guruhi", "guruhcha",
                     "podgruppa", "subgroup", "kichik guruh raqami"],
    },
    # Tanlov fanlari va 2-til darslari jadvali: akademik guruhga bog'lanmagan, fan va oqim bo'yicha
    "elsched": {
        "subject": ["fan", "fan nomi", "tanlov fani", "ikkinchi til", "subject", "predmet"],
        "stream": _STREAM,
        "group_name": _GROUP,
        "weekday": ["hafta kuni", "kun", "weekday", "kuni"],
        "pair": ["juftlik", "para", "pair", "juftlik raqami", "juft"],
        "start_time": ["boshlanish", "boshlanishi", "start", "boshlanish vaqti"],
        "end_time": ["tugash", "tugashi", "end", "tugash vaqti"],
        "time_range": ["vaqt", "vaqti", "time"],
        "lesson_type": ["mashgulot turi", "dars turi", "turi", "type"],
        "teacher": ["oqituvchi", "teacher", "prepodavatel"],
        "room": ["xona", "auditoriya", "room", "aud", "xonasi"],
        "week_type": ["hafta turi", "hafta", "toq juft"],
        "code": ["fan kodi", "kod", "code", "fan kod", "subject code", "kodi"],
    },
    # Talabaning shaxsiy fanlari: tanlov fanlari, ikkinchi chet tili, oqim
    "enroll": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "subject": ["fan", "fan nomi", "fanlar", "tanlov fani", "tanlov fanlari", "tanlagan fani", "tanlagan fanlari",
                    "tanlov", "elektiv fan", "subject", "predmet"],
        "lang2": ["ikkinchi til", "2 til", "ikkinchi chet tili", "ikkinchi xorijiy til", "2 chet tili",
                  "ikkinchi tili", "second language", "vtoroy yazyk"],
        "subgroup": _STREAM,
    },
    # Fan, fakultet va boshqa nomlarning tarjimalari (/tarjimalar dan olingan jadval)
    "translations": {
        "term_type": ["turi", "tur", "nom turi"],
        "uz": ["ozbekcha", "uzbekcha", "asl nomi", "ozbek tilida", "nomi ozbekcha", "uz"],
        "ru": ["ruscha", "rus tilida", "ruscha nomi", "ru", "russkiy"],
        "en": ["inglizcha", "ingliz tilida", "inglizcha nomi", "en", "english"],
    },
    "phones": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "student_phones": _SELF_PHONE,
    },
    "grades": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "subject": ["fan", "fan nomi", "subject", "predmet"],
        "control_type": ["nazorat turi", "nazorat", "baho turi", "control type", "turi"],
        "score": ["ball", "baho", "score", "natija", "toplangan ball"],
        "max_score": ["maksimal ball", "max ball", "maks ball", "max", "maksimal", "maks"],
        "date": ["sana", "date"],
        "semester": ["semestr", "semester"],
        "credits": ["kredit", "kreditlar", "kredit soni", "kreditlar soni", "credit", "credits", "zachetnye edinitsy"],
    },
    # HEMIS «Performance GPA»: talabaning rasmiy GPA si
    "gpa": {
        "hemis_id": _ID,
        "full_name": _NAME,
        "group_name": _GROUP,
        "gpa": ["gpa", "gpa ball", "umumiy gpa", "gpa bali", "srednij ball gpa"],
        "load": ["fan kredit", "fan / kredit", "fanlar kredit", "fan va kredit"],
        "debts": ["qarz", "qarzlar", "qarzdor fanlar", "qarzdor fanlar soni", "akademik qarz"],
        "method": ["gpa usuli", "usul", "gpa turi"],
        "changed": ["ozgartirilgan", "o zgartirilgan", "o zgartirilgan sana", "yangilangan", "sana"],
        "course": ["kurs", "course"],
    },
    # HEMIS «Akadem qarzdorlar» ro'yxati: har bir qator — talabaning bitta qarzdor fani
    "acad_debts": {
        "hemis_id": _ID,
        "full_name": _NAME + ["toliq ismi", "to liq ismi", "talabaning toliq ismi", "talaba f i sh", "talaba fio"],
        "group_name": _GROUP,
        "subject": ["fanlar", "fan", "fan nomi", "qarzdor fan", "qarzdor fanlar", "fanlar nomi", "predmet", "subject"],
        "semester": ["semestr", "semester", "semestri"],
        "credits": ["kredit", "kreditlar", "kredit soni", "credit", "credits"],
        "course": ["kurs", "course", "bosqich"],
        "year": ["oquv yili", "o quv yili", "uchebnyy god", "academic year"],
    },
}

REQUIRED = {
    "translations": ["uz"],
    "students": ["hemis_id", "full_name", "group_name"],
    "attendance": ["date", "pair", "subject", "status"],
    "schedule": ["group_name", "weekday", "pair", "subject"],
    "grades": ["subject", "control_type", "score"],
    "phones": ["student_phones"],
    "attendance_stats": ["absent"],
    "enroll": [],
    "elsched": ["subject", "weekday", "pair"],
    "acad_debts": ["subject"],
    "gpa": ["gpa"],
}
NEED_STUDENT_REF = {"attendance", "grades", "phones", "attendance_stats", "enroll", "acad_debts", "gpa"}  # HEMIS ID yoki F.I.Sh ustunidan biri bo'lishi shart

FIELD_TITLES = {
    "hemis_id": "HEMIS ID", "full_name": "F.I.Sh", "group_name": "Guruh", "date": "Sana",
    "pair": "Juftlik", "subject": "Fan", "status": "Holat", "weekday": "Hafta kuni",
    "control_type": "Nazorat turi", "score": "Ball", "student_phones": "Talaba telefoni",
    "absent": "Qatnashmaganlar soni", "credits": "Kredit", "semester": "Semestr",
}

KIND_TITLES = {"translations": "Tarjimalar (fan va fakultet nomlari)", "students": "Talabalar", "attendance": "Davomat", "schedule": "Dars jadvali", "grades": "Baholar",
               "attendance_stats": "Davomat (HEMIS statistikasi)", "enroll": "Tanlov fanlari va 2-til (biriktirish)",
               "elsched": "Tanlov fanlari va 2-til jadvali",
               "phones": "Talaba telefonlari", "debts": "Kontrakt qarzdorligi",
               "debts_t": "Trimestr qarzdorligi", "acad_debts": "Akademik qarzdorlar (HEMIS ro'yxati)",
               "gpa": "GPA (HEMIS)"}


@dataclass
class ParseResult:
    rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fatal: str | None = None
    skipped: int = 0
    columns: dict[str, str] = field(default_factory=dict)  # maydon -> fayldagi sarlavha
    kind: str = ""                                          # aniqlangan format (masalan, attendance_stats)
    notes: list[str] = field(default_factory=list)          # kurs koordinatoriga qo'shimcha izohlar
    meta: dict = field(default_factory=dict)                # jadval ustidagi ma'lumotlar (guruh, semestr)


# Bu so'zlar bor sarlavha hech qachon talabaning o'z telefoni deb olinmaydi
_PARENT_WORDS = {"ota", "ona", "otasi", "onasi", "otasining", "onasining", "roditel", "roditeley", "roditelya",
                 "parent", "parents", "ottsa", "otsa", "materi", "vasiy", "vasiysi"}


def _map_header(cells: tuple, aliases: dict[str, list[str]]) -> dict[str, int]:
    norm = [normalize_text(c) for c in cells]
    colmap: dict[str, int] = {}
    used: set[int] = set()
    # 1) aniq moslik
    for fld, names in aliases.items():
        for i, h in enumerate(norm):
            if i not in used and h and h in names:
                colmap[fld] = i
                used.add(i)
                break
    # 2) boshlanishi mos (masalan «Ota-ona telefoni (vergul bilan)»)
    for fld, names in aliases.items():
        if fld in colmap:
            continue
        for i, h in enumerate(norm):
            if fld == "student_phones" and _PARENT_WORDS & set(h.split()):
                continue
            if fld == "course" and "koordinator" in h:  # «Kurs koordinatori» — bu kurs raqami emas
                continue
            if i not in used and h and any(h.startswith(n + " ") for n in names):
                colmap[fld] = i
                used.add(i)
                break
    return colmap


def _is_sample(row: tuple) -> bool:
    return any(isinstance(v, str) and v.strip().upper().startswith("NAMUNA") for v in row)


def load_rows(path: str) -> list[tuple]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    finally:
        wb.close()


def parse_file(path: str, kind: str) -> ParseResult:
    return parse_rows(load_rows(path), kind)


# Tanlangan import turi bilan mos keladigan aniqlangan turlar
COMPATIBLE = {"translations": {"translations"}, "students": {"students"}, "attendance": {"attendance"}, "schedule": {"schedule"},
              "elsched": {"elsched"}, "grades": {"grades"}, "enroll": {"enroll", "grades"},
              "phones": {"phones", "students"}, "debts": {"debts"}, "debts_t": {"debts_t"},
              "acad_debts": {"acad_debts"}, "gpa": {"gpa"}}


def detect_kinds(all_rows: list[tuple], file_name: str = "") -> list[str]:
    """Fayl ustunlariga qarab qaysi import turiga tegishli ekanini aniqlaydi (ishonchli belgilar bo'yicha)."""
    fn = normalize_text(file_name)
    head = " ".join(normalize_text(cell_str(c)) for row in all_rows[:12] for c in row if c not in (None, ""))
    found: list[str] = []
    # HEMIS «Performance GPA»: talaba + GPA ustuni. Unda HEMIS ID, F.I.Sh., guruh, kurs ham bor — talabalar ro'yxati
    # deb adashmasligi uchun birinchi va yagona tur sifatida aniqlanadi
    gpa_cols = set(_best_header(all_rows, ALIASES["gpa"])[0])
    if "gpa" in gpa_cols and gpa_cols & {"hemis_id", "full_name"}:
        return ["gpa"]
    debts = parse_debts(all_rows)
    if not debts.fatal:
        tri = ("trimestr" in fn or "trimestr" in head
               or (debts.meta.get("format") == "vedomost" and "kontrakt" not in head and "kontrakt" not in fn))
        found.append("debts_t" if tri else "debts")
    stats = set(_best_header(all_rows, ALIASES["attendance_stats"])[0])
    daily = set(_best_header(all_rows, ALIASES["attendance"])[0])
    if "absent" in stats or {"date", "pair", "status"} <= daily:
        found.append("attendance")
    grades = set(_best_header(all_rows, ALIASES["grades"])[0])
    wide = parse_grades_wide(all_rows) if "absent" not in stats else None
    if {"subject", "score"} <= grades or (wide is not None and (wide.meta.get("semester") or wide.meta.get("group"))):
        found.append("grades")
    sched = set(_best_header(all_rows, ALIASES["schedule"])[0])
    if {"weekday", "pair", "subject"} <= sched:
        # «Oqim», «Til guruhi» — tanlov/2-til jadvali; «Kichik guruh» ikkalasida ham bo'lishi mumkin
        streamy = any(w in head for w in ("oqim", "til guruhi", "tanlov guruhi", "potok")) or \
            any(w in fn for w in ("tanlov", "2til", "2 til", "ikkinchi til"))
        found.append("elsched" if streamy else "schedule")
    stud = set(_best_header(all_rows, ALIASES["students"])[0])
    if ({"hemis_id", "full_name", "group_name"} <= stud and "absent" not in stats and "date" not in daily
            and stud & {"course", "birth_date", "faculty", "phones", "student_phones", "payment_form", "tutor_name"}):
        found.append("students")
    acad = set(_best_header(all_rows, ALIASES["acad_debts"])[0])
    if ({"full_name", "subject"} <= acad and "score" not in grades and "date" not in daily and "weekday" not in sched
            and ("credits" in acad or "semester" in acad or "qarzdor" in fn or "debtor" in fn or "qarzdor" in head)):
        found.append("acad_debts")
    enr = set(_best_header(all_rows, ALIASES["enroll"])[0])
    if ("acad_debts" not in found and (enr & {"lang2", "subject"}) and (enr & {"hemis_id", "full_name"}) and "score" not in grades
            and "weekday" not in sched and "date" not in daily and "absent" not in stats):
        found.append("enroll")
    tr_cols = set(_best_header(all_rows, ALIASES["translations"])[0])
    if "uz" in tr_cols and tr_cols & {"ru", "en"}:
        found.insert(0, "translations")
    return list(dict.fromkeys(found))


def _best_header(all_rows: list[tuple], aliases: dict) -> tuple[dict, int]:
    best, header_idx = {}, -1
    for idx, row in enumerate(all_rows[:15]):
        cm = _map_header(row, aliases)
        if len(cm) > len(best):
            best, header_idx = cm, idx
    return best, header_idx


def parse_rows(all_rows: list[tuple], kind: str) -> ParseResult:
    if kind in ("debts", "debts_t"):
        return parse_debts(all_rows, kind)
    if kind == "attendance":
        # HEMIS statistikasi (jami ko'rsatkichlar) yoki kunlik (dars bo'yicha) davomat — ustunlarga qarab
        stats, _ = _best_header(all_rows, ALIASES["attendance_stats"])
        daily, _ = _best_header(all_rows, ALIASES["attendance"])
        if "absent" in stats and "date" not in daily:
            kind = "attendance_stats"
    if kind == "enroll":
        best, _ = _best_header(all_rows, ALIASES["enroll"])
        if "subject" not in best and "lang2" not in best:
            wide = parse_grades_wide(all_rows, enroll=True)
            if wide is not None:
                return wide
            res = ParseResult(kind=kind)
            res.fatal = ("«Tanlov fanlari va 2-til» fayli uchun ustunlar topilmadi: «Fan» (yoki «Tanlov fani», "
                         "«Ikkinchi til») ustuni yoki fanlar ustunlarda bo'lgan jadval bo'lishi kerak. /shablon dagi "
                         "7-namunaga qarang.")
            return res
    if kind == "grades":
        daily, _ = _best_header(all_rows, ALIASES["grades"])
        if "subject" not in daily or "control_type" not in daily:
            wide = parse_grades_wide(all_rows)
            if wide is not None:
                return wide
    res = ParseResult(kind=kind)
    aliases = ALIASES[kind]
    best, header_idx = {}, -1
    for idx, row in enumerate(all_rows[:15]):
        cm = _map_header(row, aliases)
        if len(cm) > len(best):
            best, header_idx = cm, idx
    missing = [f for f in REQUIRED[kind] if f not in best]
    if kind in NEED_STUDENT_REF and "hemis_id" not in best and "full_name" not in best:
        missing.append("hemis_id")
    if header_idx < 0 or missing:
        titles = ", ".join(FIELD_TITLES.get(m, m) for m in missing) or "sarlavha qatori"
        res.fatal = (f"«{KIND_TITLES[kind]}» fayli uchun zarur ustun(lar) topilmadi: {titles}. "
                     f"Birinchi varaqda sarlavha qatori borligini tekshiring yoki /shablon dagi namunadan foydalaning.")
        return res

    header = all_rows[header_idx]
    res.columns = {f: cell_str(header[i]) for f, i in best.items()}

    def get(row, fld):
        i = best.get(fld)
        return row[i] if i is not None and i < len(row) else None

    parser = {"students": _student, "attendance": _attendance, "schedule": _schedule, "grades": _grade,
              "phones": _self_phones, "attendance_stats": _att_stats, "enroll": _enroll, "translations": _translation,
              "elsched": _elective, "acad_debts": _acad_debt, "gpa": _gpa}[kind]
    has_ref = kind == "students" or kind in NEED_STUDENT_REF
    # jadval ustidagi «Guruh: 3-1a-24» kabi qatorlar — qatorda guruh bo'sh bo'lsa shundan olinadi
    meta = {}
    for row in all_rows[:header_idx]:
        vals = [cell_str(c) for c in row if cell_str(c)]
        if len(vals) >= 2:
            meta[normalize_text(vals[0])] = vals[1]
    meta_group = meta.get("guruh") or meta.get("guruh nomi") or ""
    res.meta = {"group": meta_group} if meta_group else {}
    masked = 0
    for n, row in enumerate(all_rows[header_idx + 1:], start=header_idx + 2):
        if not any(v not in (None, "") for v in row):
            continue
        # HEMIS'dagi ikkinchi sarlavha qatori yoki izoh qatori: talaba ko'rsatilmagan — xato emas
        if has_ref and not cell_str(get(row, "hemis_id")) and not cell_str(get(row, "full_name")):
            continue
        if kind == "students" and any(is_masked(get(row, f)) for f in ("birth_date", "student_phones")):
            masked += 1
        if _is_sample(row):
            res.skipped += 1
            continue
        try:
            out = parser(lambda f: get(row, f))
        except ValueError as e:
            res.errors.append(f"{n}-qator: {e}")
            continue
        for item in (out if isinstance(out, list) else [out]):
            item["_row"] = n
            if meta_group and "group_name" in item and not item["group_name"]:
                item["group_name"] = meta_group
            res.rows.append(item)
    if masked:
        res.notes.append(f"⚠️ {masked} ta qatorda tug'ilgan sana yoki telefon yashirilgan (***) — ular saqlanmadi. "
                         "Ularsiz ham bot ishlaydi, lekin talabaning raqami bo'yicha aniqlash va tug'ilgan sana "
                         "bo'yicha qo'lda bog'lash ishlamaydi (qo'lda bog'lashda HEMIS ID ishlatiladi).")
    return res


_SUBJ_TITLE = re.compile(r"(?i)\bo\W?quvchilar(?:ni)?\s+(.+?)\s+fanidan\b")


def stats_subject(all_rows: list[tuple], file_name: str = "") -> str | None:
    """HEMIS statistikasi bitta fan bo'yicha bo'lsa — fan nomi: «O'quvchilarni <fan> fanidan darslarga qatnashish
    statistikasi» sarlavhasidan yoki «Oquvchilar_<fan>_fanidan_davomati_statistikasi_….xlsx» fayl nomidan."""
    for row in all_rows[:6]:
        for c in row:
            if isinstance(c, str):
                m = _SUBJ_TITLE.search(" ".join(c.split()))
                if m:
                    return m.group(1).strip(" «»\"'")
    m = _SUBJ_TITLE.search(re.sub(r"[_]+", " ", file_name or ""))
    return m.group(1).strip() if m else None


def _gpa(g) -> dict:
    """HEMIS «Performance GPA» qatori: «4.05», «25 / 120.0» (fanlar / kredit), «Qarz» (soni), o'zgartirilgan sana."""
    raw = cell_str(g("gpa")).replace(",", ".").strip()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"GPA noto'g'ri: «{raw or 'bo‘sh'}»")
    if not 0 <= value <= 5:
        raise ValueError(f"GPA 0–5 oralig'ida emas: {raw}")
    subjects = credits = None
    m = re.match(r"\s*(\d+)\s*/\s*([\d.,]+)", cell_str(g("load")))
    if m:
        subjects, credits = int(m.group(1)), float(m.group(2).replace(",", "."))
    debts = re.search(r"\d+", cell_str(g("debts")))
    changed = None
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})(?:\s+(\d{1,2}):(\d{2}))?", cell_str(g("changed")))
    if m:
        d, mo, y, hh, mm = m.groups()
        changed = f"{y}-{int(mo):02d}-{int(d):02d}" + (f"T{int(hh):02d}:{mm}" if hh else "")
    year = re.search(r"\d{4}\s*[-–]\s*\d{4}", cell_str(g("course")))
    return {"hemis_id": cell_str(g("hemis_id")) or None, "full_name": nice_name(cell_str(g("full_name"))),
            "group_name": cell_str(g("group_name")) or None, "gpa": value, "subjects": subjects, "credits": credits,
            "debts": int(debts.group(0)) if debts else None, "method": cell_str(g("method")) or None,
            "changed_at": changed, "year": year.group(0).replace(" ", "") if year else None}


def _acad_debt(g) -> dict:
    """HEMIS akademik qarzdorlar ro'yxati qatori: talaba va uning bitta qarzdor fani."""
    subject = re.sub(r"\s+", " ", cell_str(g("subject"))).strip()
    if not subject:
        raise ValueError("fan ko'rsatilmagan")
    sem = re.search(r"\d+", cell_str(g("semester")))
    course = re.search(r"\d+", cell_str(g("course")))
    try:
        credits = float(str(g("credits")).replace(",", ".")) if g("credits") not in (None, "") else None
    except ValueError:
        credits = None
    return {"hemis_id": cell_str(g("hemis_id")) or None, "full_name": nice_name(cell_str(g("full_name"))),
            "group_name": cell_str(g("group_name")) or None, "subject": subject,
            "semester": sem.group(0) if sem else "", "credits": credits,
            "course": int(course.group(0)) if course else None, "year": cell_str(g("year")) or None}


def _student(g) -> dict:
    hemis, name, group = cell_str(g("hemis_id")), cell_str(g("full_name")), cell_str(g("group_name"))
    if not hemis or not name:
        raise ValueError("HEMIS ID yoki F.I.Sh bo'sh")
    phones = []
    for fld in ("phones", "phones_father", "phones_mother"):
        for p in split_phones(g(fld)):
            if p not in phones:
                phones.append(p)
    bd = None if is_masked(g("birth_date")) else parse_date(g("birth_date"))
    return {
        "hemis_id": hemis,
        "full_name": nice_name(name),
        "group_name": group or None,
        "faculty": cell_str(g("faculty")) or None,
        "course": parse_course(g("course")),
        "payment_form": normalize_payment_form(g("payment_form")),
        "full_name_cyr": " ".join(cell_str(g("full_name_cyr")).split()) or None,
        "birth_date": bd.isoformat() if bd else None,
        "phones": phones,
        "student_phones": [] if is_masked(g("student_phones")) else split_phones(g("student_phones")),
        "tutor_name": cell_str(g("tutor_name")) or None,
        "tutor_phone": normalize_phone(g("tutor_phone")),
    }


def _student_ref(g) -> dict:
    hemis, name = cell_str(g("hemis_id")), cell_str(g("full_name"))
    if not hemis and not name:
        raise ValueError("talaba ko'rsatilmagan (HEMIS ID yoki F.I.Sh)")
    return {"hemis_id": hemis, "full_name": nice_name(name), "group_name": cell_str(g("group_name"))}


def _attendance(g) -> dict:
    ref = _student_ref(g)
    d = parse_date(g("date"))
    if not d:
        raise ValueError(f"sana noto'g'ri: {cell_str(g('date'))!r}")
    pair = parse_int(g("pair"))
    if not pair:
        raise ValueError("juftlik raqami yo'q")
    subject = cell_str(g("subject"))
    if not subject:
        raise ValueError("fan nomi yo'q")
    status = normalize_status(g("status"))
    if not status:
        raise ValueError(f"holat tanilmadi: {cell_str(g('status'))!r} (keldi / kelmadi / sababli / kechikdi)")
    hours = parse_float(g("hours"))
    return {**ref, "date": d.isoformat(), "pair": pair, "subject": subject,
            "lesson_type": cell_str(g("lesson_type")) or None, "teacher": cell_str(g("teacher")) or None,
            "status": status, "hours": hours if hours else HOURS_PER_PAIR}


def _att_stats(g) -> dict:
    ref = _student_ref(g)
    absent = parse_float(g("absent"))
    if absent is None:
        raise ValueError(f"qatnashmaganlar soni noto'g'ri: {cell_str(g('absent'))!r}")
    num = lambda f: parse_float(g(f)) or 0.0  # noqa: E731
    return {**ref, "attended": num("attended"), "absent": absent, "excused": num("excused"),
            "self_marked": num("self_marked"), "teacher_marked": num("teacher_marked")}


def _enroll(g) -> list[dict]:
    ref = _student_ref(g)
    names = []
    for fld in ("lang2", "subject"):
        for x in re.split(r"[,;\n]+", cell_str(g(fld))):
            x = " ".join(x.split())
            if x and x not in ("-", "—") and x not in names:
                names.append(x)
    sub = subgroup_key(g("subgroup"))
    return [{**ref, "subject": x, "subject_key": subject_key(x), "subgroup": sub} for x in names if subject_key(x)]


def _schedule(g) -> list[dict]:
    groups = [x.strip() for x in re.split(r"[,;\n]+", cell_str(g("group_name"))) if x.strip()]
    if not groups:
        raise ValueError("guruh ko'rsatilmagan")
    base = _lesson_base(g)
    base["subgroup"] = subgroup_key(g("subgroup"))
    return [{**base, "group_name": grp, "group_key": group_key(grp)} for grp in groups]


def _elective(g) -> list[dict]:
    """Tanlov fani / 2-til darsi: fan + oqim; guruh ko'rsatilsa — faqat shu akademik guruh talabalari uchun."""
    base = _lesson_base(g)
    base.update(subject_key=subject_key(base["subject"]), stream=subgroup_key(g("stream")))
    groups = [x.strip() for x in re.split(r"[,;\n]+", cell_str(g("group_name"))) if x.strip()]
    if not groups:
        return [{**base, "group_name": None, "group_key": None}]
    return [{**base, "group_name": grp, "group_key": group_key(grp)} for grp in groups]


def _lesson_base(g) -> dict:
    wd = parse_weekday(g("weekday"))
    if not wd:
        raise ValueError(f"hafta kuni tanilmadi: {cell_str(g('weekday'))!r}")
    pair = parse_int(g("pair"))
    if not pair:
        raise ValueError("juftlik raqami yo'q")
    subject = cell_str(g("subject"))
    if not subject:
        raise ValueError("fan nomi yo'q")
    start, end = parse_time(g("start_time")), parse_time(g("end_time"))
    if not start and g("time_range"):
        times = re.findall(r"\d{1,2}[:.]\d{2}", cell_str(g("time_range")))
        start = parse_time(times[0]) if times else None
        end = parse_time(times[1]) if len(times) > 1 else None
    wt = normalize_text(g("week_type"))
    week_type = "toq" if wt.startswith("toq") else "juft" if wt.startswith("juft") else "har"
    return {"weekday": wd, "pair": pair, "start_time": start, "end_time": end, "subject": subject,
            "lesson_type": cell_str(g("lesson_type")) or None, "teacher": cell_str(g("teacher")) or None,
            "room": cell_str(g("room")) or None, "week_type": week_type, "code": cell_str(g("code")) or None}


def _translation(g) -> dict:
    uz = " ".join(cell_str(g("uz")).split())
    ru, en = " ".join(cell_str(g("ru")).split()), " ".join(cell_str(g("en")).split())
    if not uz:
        raise ValueError("o'zbekcha nom bo'sh")
    return {"uz": uz, "ru": ru or None, "en": en or None}


def _self_phones(g) -> dict | list:
    raw = cell_str(g("student_phones"))
    if not raw:
        return []  # raqami yo'q talaba — xato emas
    ref = _student_ref(g)
    phones = split_phones(raw)
    if not phones:
        raise ValueError(f"telefon raqam tanilmadi: {raw!r}")
    return {**ref, "student_phones": phones}


def _grade(g) -> dict:
    ref = _student_ref(g)
    subject, ctype = cell_str(g("subject")), cell_str(g("control_type"))
    if not subject or not ctype:
        raise ValueError("fan yoki nazorat turi yo'q")
    score = parse_float(g("score"))
    if score is None:
        raise ValueError(f"ball noto'g'ri: {cell_str(g('score'))!r}")
    d = parse_date(g("date"))
    return {**ref, "subject": subject, "control_type": ctype, "score": score,
            "max_score": parse_float(g("max_score")), "date": d.isoformat() if d else None,
            "semester": cell_str(g("semester")), "credits": parse_float(g("credits"))}


# ---------------------------------------------------------------- HEMIS «O'rtacha ball» (keng jadval)
_WIDE_NOT_SUBJECT = {"", "no", "n", "t r", "tr", "tolov shakli", "tolov turi", "hemis id", "talaba id", "id",
                     "guruh", "guruh nomi", "kurs", "kursi", "ortacha", "ortacha ball", "jami", "gpa", "reyting",
                     "fakultet", "yonalish", "mutaxassislik"}
_SCORE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)")


def parse_grades_wide(all_rows: list[tuple], enroll: bool = False) -> ParseResult | None:
    """Har bir fan alohida ustunda, qatorda talaba; jadval ustida «Guruh», «Semestr» yozilgan fayl.
    Katakdagi «78 [1]» dan ball (78) olinadi. enroll=True — shaxsiy fanlar: bo'sh bo'lmagan katak = talaba shu
    fanni o'qiydi (belgi, «+», ball — farqi yo'q). Format mos kelmasa — None."""
    names = set(_NAME)
    header_idx = name_col = None
    for idx, row in enumerate(all_rows[:20]):
        cells = [normalize_text(cell_str(c)) for c in row]
        for j, c in enumerate(cells):
            if c in names and sum(1 for x in cells if x) >= 4:
                header_idx, name_col = idx, j
                break
        if header_idx is not None:
            break
    if header_idx is None:
        return None
    header = all_rows[header_idx]
    meta = {}
    for row in all_rows[:header_idx]:
        vals = [cell_str(c) for c in row if cell_str(c)]
        if len(vals) >= 2:
            meta[normalize_text(vals[0])] = vals[1]
    id_col = next((j for j, c in enumerate(header) if normalize_text(cell_str(c)) in set(_ID)), None)
    pay_col = next((j for j, c in enumerate(header) if normalize_text(cell_str(c)) in ("tolov shakli", "tolov turi")),
                   None)
    grp_col = next((j for j, c in enumerate(header) if normalize_text(cell_str(c)) in set(_GROUP)), None)
    subjects = [(j, " ".join(cell_str(c).split())) for j, c in enumerate(header)
                if j != name_col and normalize_text(cell_str(c)) not in _WIDE_NOT_SUBJECT and cell_str(c)
                and not cell_str(c).startswith("№")]
    if len(subjects) < 1:
        return None
    group = meta.get("guruh") or meta.get("guruh nomi") or ""
    semester = meta.get("semestr") or ""
    sem_no = parse_int(semester)
    res = ParseResult(kind="enroll_wide" if enroll else "grades_wide",
                      meta={"group": group, "semester": semester, "year": meta.get("oquv yili", "")})
    res.columns = {"full_name": cell_str(header[name_col])}
    res.notes.append(("Jadval ko'rinishidagi fayl aniqlandi (bo'sh bo'lmagan katak — talaba shu fanni o'qiydi)"
                      if enroll else "HEMIS «O'rtacha ball» jadvali aniqlandi")
                     + f": guruh {group or '—'}, {len(subjects)} ta fan ustuni.")
    for n, row in enumerate(all_rows[header_idx + 1:], start=header_idx + 2):
        name = cell_str(row[name_col]) if name_col < len(row) else ""
        if not name:
            continue
        if _is_sample(row):
            res.skipped += 1
            continue
        pay = normalize_payment_form(row[pay_col]) if pay_col is not None and pay_col < len(row) else None
        if pay:
            res.meta.setdefault("payment_forms", []).append({"hemis_id": cell_str(row[id_col]) if id_col is not None
                                                              and id_col < len(row) else "",
                                                              "full_name": nice_name(name), "group_name": group,
                                                              "payment_form": pay, "_row": n})
        ref = {"hemis_id": cell_str(row[id_col]) if id_col is not None and id_col < len(row) else "",
               "full_name": nice_name(name),
               "group_name": (cell_str(row[grp_col]) if grp_col is not None and grp_col < len(row) else "") or group}
        for j, subj in subjects:
            raw = row[j] if j < len(row) else None
            if raw in (None, "") or cell_str(raw) in ("-", "—", "0"):
                continue
            if enroll:
                res.rows.append({**ref, "subject": subj, "subject_key": subject_key(subj), "subgroup": None, "_row": n})
                continue
            if isinstance(raw, (int, float)):
                score = float(raw)
            else:
                m = _SCORE.match(cell_str(raw))
                if not m:
                    continue
                score = float(m.group(1).replace(",", "."))
            res.rows.append({**ref, "subject": subj, "control_type": "O'rtacha ball", "score": score,
                             "max_score": 100.0, "date": None,
                             "semester": str(sem_no) if sem_no else cell_str(semester), "_row": n})
    if enroll:
        _split_common(res)
    return res


COMMON_SHARE = 0.8  # keng jadvalda shuncha ulush talabada bor fan — umumiy fan (hammaga ko'rsatiladi)


def _split_common(res: ParseResult) -> None:
    """Keng jadvaldan olingan shaxsiy fanlar: deyarli hammada bor fanlar (masalan, bitta-ikkita talabaning
    bahosi hali qo'yilmagan umumiy fan) shaxsiy ro'yxatga yozilmaydi — aks holda u darsni ko'rmay qoladi."""
    students = {(r["hemis_id"], r["full_name"]) for r in res.rows}
    if len(students) < 5:
        return
    count: dict[str, int] = {}
    for r in res.rows:
        count[r["subject"]] = count.get(r["subject"], 0) + 1
    common = sorted(s for s, n in count.items() if n / len(students) >= COMMON_SHARE)
    personal = sorted(s for s in count if s not in common)
    res.rows = [r for r in res.rows if r["subject"] not in common]
    if common:
        res.notes.append(f"Umumiy fan deb olindi (talabalarning {round(COMMON_SHARE * 100)}%+ ida bor, hammaga "
                         f"ko'rsatiladi): {', '.join(common)}.")
    res.notes.append(f"Shaxsiy fanlar (tanlov, 2-til): {', '.join(personal) or '—'}.")


# ---------------------------------------------------------------- kontrakt to'lovi va qarzdorlik
_DATE_IN_HEADER = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})")
_YEAR_LABEL = re.compile(r"(20\d{2})\s*[-–/]\s*(20\d{2})")


def _money(v) -> float | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = cell_str(v).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def parse_debts(all_rows: list[tuple], kind: str = "debts") -> ParseResult:
    """Buxgalteriya hisobotlari: «Kontrakt qarzdorlar» (kontrakt, to'langan, Jami, Qoldiq: manfiy — qarz) yoki
    aylanma vedomost (davr boshi/oxiridagi qoldiq DT/KT, shartnoma summasi, to'langan, foiz). Ikki qatorli sarlavha
    birlashtiriladi. JSHSHIR faqat o'qiladi, saqlanmaydi."""
    res = ParseResult(kind=kind)
    names = set(_NAME) | {"talaba f i sh", "talabaning familiyasi ismi va sharifi"}
    header_idx = name_col = None
    for idx, row in enumerate(all_rows[:15]):
        for j, c in enumerate(row):
            t = normalize_text(cell_str(c))
            if t and (t in names or "f i sh" in t or "familiyasi" in t or t == "fio"):
                header_idx, name_col = idx, j
                break
        if header_idx is not None:
            break
    if header_idx is None:
        res.fatal = ("Qarzdorlik fayli uchun «F.I.Sh.» ustuni topilmadi. Buxgalteriya hisobotini (kontrakt qarzdorlar "
                     "ro'yxati yoki aylanma vedomost) o'zgartirmasdan yuboring yoki /shablon dagi namunaga qarang.")
        return res
    top = [cell_str(c) for c in all_rows[header_idx]]
    start = header_idx + 1
    sub = [cell_str(c) for c in all_rows[header_idx + 1]] if header_idx + 1 < len(all_rows) else []
    if sub and not (name_col < len(sub) and sub[name_col]) and sum(1 for x in sub if x and not _money(x)) >= 2:
        start += 1  # ikki qatorli sarlavha: guruh nomi + DT/KT
        last = ""
        heads = []
        for j in range(max(len(top), len(sub))):
            t = top[j] if j < len(top) else ""
            last = t or (last if j < len(sub) and sub[j] else "")
            heads.append(" ".join(x for x in (t or last, sub[j] if j < len(sub) else "") if x))
    else:
        heads = top
    norm = [normalize_text(h) for h in heads]

    def col(*tests):
        for j, h in enumerate(norm):
            if j != name_col and h and any(t(h) for t in tests):
                return j
        return None

    c = {
        "course": col(lambda h: "kursi" in h or "bosqich" in h or h == "kurs"),
        "contract": col(lambda h: "kontrakt miqdori" in h or "kontrakt summasi" in h or "shartnoma summasi" in h
                        or "shartnoma miqdori" in h),
        "paid": col(lambda h: "tolangan summa" in h and "foiz" not in h),
        "total": col(lambda h: h == "jami" or h.startswith("jami ")),
        "balance": col(lambda h: h == "qoldiq"),
        "start": col(lambda h: "holatga qoldiq" in h),
        "start_dt": col(lambda h: "boshiga" in h and h.endswith(" dt")),
        "start_kt": col(lambda h: "boshiga" in h and h.endswith(" kt")),
        "end_dt": col(lambda h: ("ohiriga" in h or "oxiriga" in h) and ("qarz" in h or h.endswith(" dt"))),
        "end_kt": col(lambda h: ("ohiriga" in h or "oxiriga" in h) and ("haqdor" in h or "xaqdor" in h
                                                                        or h.endswith(" kt"))),
        "percent": col(lambda h: "foiz" in h),
        "note": col(lambda h: h.startswith("izoh")),
        "status": col(lambda h: "holati" in h),
    }
    fmt = "vedomost" if c["end_dt"] is not None else "qarzdorlar" if c["balance"] is not None else None
    if fmt is None:
        res.fatal = ("Qarzdorlik ustuni topilmadi: «Qoldiq» (manfiy — qarz) yoki «Davr oxiriga qoldiq DT-Qarz» bo'lishi "
                     "kerak. Buxgalteriya hisobotini o'zgartirmasdan yuboring.")
        return res
    res.columns = {k: heads[j] for k, j in c.items() if j is not None}
    res.columns["full_name"] = heads[name_col]
    dates = []
    for h in heads:
        for d, m, y in _DATE_IN_HEADER.findall(h):
            try:
                dates.append(date(int(y), int(m), int(d)))
            except ValueError:
                pass
    year = next((f"{a}-{b}" for h in heads for a, b in _YEAR_LABEL.findall(h)), None)
    res.meta = {"format": fmt, "as_of": max(dates).isoformat() if dates else None, "year": year}

    def v(row, key):
        j = c[key]
        return _money(row[j]) if j is not None and j < len(row) else None

    for n, row in enumerate(all_rows[start:], start=start + 1):
        name = cell_str(row[name_col]) if name_col < len(row) else ""
        nn = normalize_text(name)
        if not name or nn.startswith(("jami", "itogo", "hammasi", "total")):
            continue
        if _is_sample(row):
            res.skipped += 1
            continue
        contract = v(row, "contract") or 0.0
        if fmt == "vedomost":
            debt, over = v(row, "end_dt") or 0.0, v(row, "end_kt") or 0.0
            paid = v(row, "paid") or 0.0
            base = (v(row, "start_dt") or 0.0) - (v(row, "start_kt") or 0.0) + contract
            pct = v(row, "percent")
            if pct is None and base > 0:
                pct = 100 * paid / base
        else:
            bal = v(row, "balance")
            if bal is None:
                res.errors.append(f"{n}-qator: «Qoldiq» bo'sh ({name})")
                continue
            debt, over = max(0.0, -bal), max(0.0, bal)
            paid = max(0.0, contract + bal) if contract else (v(row, "total") or 0.0)
            pct = 100 * paid / contract if contract > 0 else None
        course = parse_course(row[c["course"]]) if c["course"] is not None and c["course"] < len(row) else None
        note = cell_str(row[c["note"]]) if c["note"] is not None and c["note"] < len(row) else ""
        res.rows.append({"hemis_id": "", "full_name": nice_name(name), "group_name": "", "course": course,
                         "contract": contract or None, "paid": paid, "debt": round(debt, 2), "overpaid": round(over, 2),
                         "percent": round(pct, 1) if pct is not None else None, "note": note or None, "_row": n})
    fmt_title = "aylanma vedomost (DT/KT)" if fmt == "vedomost" else "kontrakt qarzdorlar ro'yxati"
    res.notes.append(f"Buxgalteriya hisoboti aniqlandi: {fmt_title}"
                     + (f", {year} o'quv yili" if year else "") + ".")
    return res


def resolve_by_name(rows: list[dict], students: list[dict]) -> tuple[list[dict], list[str]]:
    """HEMIS ID siz fayllar (buxgalteriya): F.I.Sh. bo'yicha; bir xil ismlilar kurs bo'yicha ajratiladi."""
    index: dict[str, list[dict]] = {}
    for st in students:
        index.setdefault(st["name_norm"], []).append(st)
    ok, errors = [], []
    for r in rows:
        cand = index.get(normalize_text(r["full_name"]), [])
        if len(cand) > 1 and r.get("course"):
            cand = [x for x in cand if x.get("course") == r["course"]] or cand
        if len(cand) == 1:
            r["student_id"] = cand[0]["id"]
            ok.append(r)
        elif not cand:
            errors.append(f"{r['_row']}-qator: talaba bazada topilmadi ({r['full_name']})")
        else:
            errors.append(f"{r['_row']}-qator: bir xil F.I.Sh. li {len(cand)} ta talaba — aniqlab bo'lmadi "
                          f"({r['full_name']})")
    return ok, errors


def resolve_students(rows: list[dict], lookup: dict) -> tuple[list[dict], list[str]]:
    """Davomat/baho qatorlaridagi talabani bazadagi id ga bog'laydi."""
    ok, errors = [], []
    for r in rows:
        sid = None
        if r.get("hemis_id"):
            sid = lookup["hemis"].get(normalize_text(r["hemis_id"]).replace(" ", ""))
        if sid is None and r.get("full_name"):
            nn = normalize_text(r["full_name"])
            sid = lookup["name_group"].get((nn, group_key(r.get("group_name")))) or lookup["name"].get(nn)
        if sid is None:
            errors.append(f"{r['_row']}-qator: talaba bazada topilmadi ({r.get('hemis_id') or r.get('full_name')})")
            continue
        r["student_id"] = sid
        ok.append(r)
    return ok, errors
