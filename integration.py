"""Universitet tizimi («Manage») bilan integratsiya: davomat va dars jadvali — avtomatik, real vaqtga yaqin.

Ikki yo'l (birgalikda ham ishlaydi):
1. Bot o'zi so'raydi (polling): INTEGRATION_URL + INTEGRATION_ATTENDANCE / INTEGRATION_SCHEDULE yo'llari har
   INTEGRATION_INTERVAL (davomat) va INTEGRATION_SCHEDULE_INTERVAL (jadval) soniyada. API kaliti — INTEGRATION_TOKEN
   (INTEGRATION_AUTH: bearer, header:X-API-Key, query:api_key, basic yoki none).
2. Manage o'zi yuboradi (webhook): POST /api/integration/attendance yoki /schedule, X-Integration-Token sarlavhasi
   bilan (INTEGRATION_WEBHOOK_SECRET). Davomat belgilanishi bilan ota-onaga xabar ketadi.

Javob ko'rinishi va shabloni qat'iy emas: JSON (istalgan ichma-ich tuzilma, sahifalash: next havola, pageCount,
last_page va h.k.), CSV yoki Excel. Yozuvlar ro'yxati o'zi topiladi; maydonlar (student.full_name, studentId,
«Talaba», «ФИО», lesson_date …) Excel importidagi kabi nomi bo'yicha taniladi; sana unix vaqt, ISO yoki
KK.OO.YYYY; holat matn, belgi («НБ», «+»), true/false yoki «qoldirilgan soat» soni bo'lishi mumkin. Jadval
sanali darslar ro'yxati bo'lsa — hafta kuni va toq/juft hafta sanadan aniqlanadi. Biror maydon noto'g'ri
tanilsa — super-admin /integratsiya orqali qo'lda ko'rsatadi (data/integration_map.json).

Olingan ma'lumot Excel importi bilan bir xil yo'ldan o'tadi (admin._process_import_body): talabaga bog'lash, har
bir kurs bazasiga ajratish, ota-onaga darhol xabar, chegaralar, kunlik xulosa, ilovaning jonli yangilanishi.
Ma'lumot o'zgarmagan bo'lsa hech narsa qilinmaydi. Manbada o'chirilgan qoldirish (o'qituvchi to'g'rilagan) —
botda ham «keldi» bo'ladi.
"""
from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import re
import time as _time
from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from config import (DATA_DIR, INTEGRATION_ATTENDANCE, INTEGRATION_AUTH, INTEGRATION_DAYS, INTEGRATION_FIRST_SILENT,
                    INTEGRATION_HEADERS, INTEGRATION_INTERVAL, INTEGRATION_MAX_PAGES, INTEGRATION_NAME,
                    INTEGRATION_PAGE_PARAM, INTEGRATION_SCHEDULE, INTEGRATION_SCHEDULE_INTERVAL, INTEGRATION_TIMEOUT,
                    INTEGRATION_TOKEN, INTEGRATION_URL, INTEGRATION_WEBHOOK_SECRET, PAIR_TIMES, TZ,
                    INTEGRATION_CONCURRENCY, INTEGRATION_SCHEDULE_PER_GROUP, INTEGRATION_SUBJECTS,
                    INTEGRATION_ACADEMIC_YEAR, INTEGRATION_SUBJECTS_INTERVAL, INTEGRATION_SUBJECTS_UNIT,
                    INTEGRATION_DONE_MEANS,
                    HEMIS_STATS_HOURS_PER_UNIT)
from database import db
from importer import ALIASES, parse_rows, resolve_students
from tenancy import central, use_course
from utils import WEEKDAYS, cell_str, credits_from_code, esc, fmt_dt, group_key, normalize_status, normalize_text, \
    now_iso, parse_date, parse_float, parse_int, parse_time, parse_weekday, semester_start, subject_key, today, week_type_of

log = logging.getLogger("integration")

KINDS = ("attendance", "schedule", "subjects")
TITLES = {"attendance": "Davomat", "schedule": "Dars jadvali", "subjects": "Fanlar (davomat va kredit)"}
KIND_WORDS = {"attendance": "attendance", "davomat": "attendance", "schedule": "schedule", "jadval": "schedule",
              "dars_jadvali": "schedule", "timetable": "schedule", "subjects": "subjects", "fanlar": "subjects",
              "fan": "subjects", "student-subjects": "subjects"}
ENV_NAMES = {"attendance": "INTEGRATION_ATTENDANCE", "schedule": "INTEGRATION_SCHEDULE", "subjects": "INTEGRATION_SUBJECTS"}
CLI_WORDS = {"attendance": "davomat", "schedule": "jadval", "subjects": "fanlar"}
MAP_FILE = DATA_DIR / "integration_map.json"
SOURCE = "integ"  # attendance.source — integratsiyadan kelgan yozuv

# ---------------------------------------------------------------- maydonlar
# API larda uchraydigan nomlar (inglizcha, camelCase/snake_case, ichma-ich: student.full_name → «student full name»).
# Excel importining nomlari (importer.ALIASES) ham qo'shiladi. Ro'yxatda oldinroq turgan nom — ustunroq.
_REF = {
    "hemis_id": ["hemis id", "student id number", "id number", "student hemis id", "hemis", "student hemis",
                 "student code", "student number", "talaba id", "student student id number", "student external id",
                 "external id", "student id"],
    "full_name": ["student full name", "full name", "student name", "student fio", "fio", "fish", "talaba",
                  "student short name", "student", "name"],
    "group_name": ["group name", "student group name", "student group", "group", "guruh", "group title", "group code"],
}
_LESSON = {
    "pair": ["lesson pair code", "lesson pair", "pair", "pair number", "pair code", "lesson pair name", "para",
             "juftlik", "lesson number", "period", "lesson order", "para number", "slot id", "slot", "slot number"],
    "subject": ["subject name", "subject", "discipline name", "discipline", "fan", "fan nomi", "predmet", "course name",
                "subject title", "title", "lesson name", "lesson title"],
    "lesson_type": ["training type name", "training type", "lesson type name", "lesson type", "type name",
                    "mashgulot turi", "dars turi"],
    "teacher": ["employee name", "teacher name", "employee full name", "teacher full name", "instructor name",
                "instructor full name", "employee", "teacher", "instructor", "lecturer", "oqituvchi", "prepodavatel"],
    "start_time": ["lesson pair start time", "start time", "begin time", "time start", "starts at", "start",
                   "boshlanish"],
    "end_time": ["lesson pair end time", "end time", "finish time", "time end", "ends at", "end", "tugash"],
}
HINTS: dict[str, dict[str, list[str]]] = {
    "attendance": {
        **_REF, **_LESSON,
        "date": ["lesson date", "date", "attendance date", "day", "sana", "dars sanasi", "data"],
        "status": ["attendance status", "status", "attendance", "holat", "davomat", "mark", "attendance type"],
        "hours": ["hours", "soat", "academic hours", "duration hours"],
        # jami ko'rsatkichlar (kun bo'yicha emas): HEMIS statistikasi kabi
        "attended": ["attended", "attended count", "present count", "qatnashgan", "qatnashganlar soni"],
        "absent": ["absent count", "absent total", "total absent", "absent hours total", "missed", "missed count",
                   "qatnashmaganlar soni", "qatnashmagan"],
        "excused": ["excused count", "excused total", "sabablilar soni", "sababli"],
    },
    "schedule": {
        "group_name": _REF["group_name"] + ["groups name", "groups"],
        **{k: v for k, v in _LESSON.items()},
        "date": ["lesson date", "date", "day date", "sana"],
        "weekday": ["weekday", "week day", "day of week", "weekday name", "day name", "hafta kuni", "kun", "day"],
        "time_range": ["time", "lesson time", "vaqt"],
        "room": ["auditorium name", "auditorium", "room name", "room", "classroom", "xona", "auditoriya"],
        "week_type": ["week type", "parity", "week parity", "hafta turi", "toq juft"],
        "subgroup": ["subgroup", "sub group", "subgroup name", "seminar raqami", "kichik guruh", "podgruppa"],
        # fan kodi: «CTIR25C4-21» — undan fan krediti (C4 → 4 kredit) va sababsiz qoldirish chegarasi aniqlanadi
        "code": ["subject code", "course code", "discipline code", "code", "fan kodi", "kod"],
    },
    # Talabaning fanlari (Manage: student-subjects): har bir fan — kredit va shu fan bo'yicha davomat
    "subjects": {
        **_REF,
        "subject": ["subject name", "subject title", "curriculum subject name", "subject", "discipline name",
                    "discipline", "course name", "title", "fan", "fan nomi", "predmet", "name"],
        "code": ["subject code", "course code", "discipline code", "code", "fan kodi", "kod"],
        "credits": ["credit", "credits", "credit count", "credits count", "subject credit", "subject credits",
                    "total credit", "total credits", "credit amount", "kredit", "kreditlar", "ects"],
        "attended": ["attended", "attended count", "attended lessons", "attended hours", "present", "present count",
                     "presence count", "visited", "visited count", "qatnashgan", "qatnashganlar soni"],
        "absent": ["absent count", "absent total", "total absent", "absent", "absent lessons", "absent hours",
                   "absences", "absence count", "missed", "missed count", "missed hours", "missed lessons", "nb",
                   "qatnashmagan", "qatnashmaganlar soni", "qoldirgan"],
        "excused": ["excused", "excused count", "excused hours", "explicable", "explicable count", "absent on",
                    "absent on count", "reasonable", "sababli", "sabablilar soni"],
        "unexcused": ["unexcused", "unexcused count", "unexcused hours", "inexplicable", "absent off",
                      "absent off count", "not explicable", "sababsiz", "sababsizlar soni"],
        "held": ["done lesson count", "done lessons count", "done lessons", "held lessons", "held lesson count",
                 "conducted lessons", "conducted lesson count", "passed lessons", "lessons held", "held", "conducted",
                 "otilgan darslar", "otilgan"],
        # fanga ajratilgan auditoriya darslari (Manage: lessonCount) — 25% chegarasi aynan shundan
        "planned": ["lesson count", "lessons count", "total lessons", "total lesson count", "planned lessons",
                    "planned lesson count", "auditorium lessons", "auditorium hours", "auditory hours",
                    "classroom hours", "ajratilgan darslar", "auditoriya soati", "auditoriya soatlari"],
        "percent": ["attendance percent", "attendance percentage", "attendance rate", "percent", "percentage",
                    "davomat foizi", "foiz"],
        "date": ["lesson date", "date", "attendance date", "sana"],
        "status": ["attendance status", "status", "holat"],
        "semester": ["semester name", "semester", "semester code", "term", "semestr"],
        # oqim: bir xil darslarni birga o'tadigan talabalar (Manage: subjectTypes[].academicGroupId) va dars turi
        "stream": ["academic group id", "stream id", "subgroup id", "academic group", "stream", "potok"],
        "lesson_type": ["lesson type", "training type", "lesson type name", "mashgulot turi"],
    },
}
# jadvalga yoziladigan sarlavha (importer shu nomni aniq taniydi)
CANON = {
    "hemis_id": "HEMIS ID", "full_name": "F.I.Sh", "group_name": "Guruh", "date": "Sana", "pair": "Juftlik",
    "subject": "Fan", "lesson_type": "Mashg'ulot turi", "teacher": "O'qituvchi", "status": "Holat", "hours": "Soat",
    "weekday": "Hafta kuni", "start_time": "Boshlanish", "end_time": "Tugash", "time_range": "Vaqt", "room": "Xona",
    "week_type": "Hafta turi", "subgroup": "Seminar raqami", "attended": "Qatnashganlar soni",
    "absent": "Qatnashmaganlar soni", "excused": "Sabablilar soni", "code": "Fan kodi", "credits": "Kredit",
    "unexcused": "Sababsiz", "held": "O'tilgan darslar", "planned": "Ajratilgan darslar", "percent": "Davomat foizi", "semester": "Semestr",
    "stream": "Oqim",
}
FIELD_NAMES = {
    "hemis_id": "talaba ID (HEMIS)", "full_name": "F.I.Sh.", "group_name": "guruh", "date": "sana", "pair": "juftlik",
    "subject": "fan", "lesson_type": "mashg'ulot turi", "teacher": "o'qituvchi", "status": "holat",
    "hours": "soat", "weekday": "hafta kuni", "start_time": "boshlanish vaqti", "end_time": "tugash vaqti",
    "time_range": "vaqt", "room": "xona", "week_type": "hafta turi", "subgroup": "kichik guruh",
    "attended": "qatnashgan", "absent": "qatnashmagan (jami)", "excused": "sababli (jami)",
    "code": "fan kodi (kredit)", "credits": "kredit", "unexcused": "sababsiz (jami)", "held": "o'tilgan darslar",
    "planned": "ajratilgan darslar (para)", "stream": "oqim (akademik guruh)",
    "percent": "davomat foizi", "semester": "semestr",
}
# holat maydoni bo'lmasa — shu so'zli maydonlardan aniqlanadi (HEMIS: explicable, absent_on, absent_off …)
_W_EXCUSED = ("explicable", "excused", "sababli", "uzrli", "reason", "uvazh", "justified")
_W_ABSENT = ("absent", "missed", "qoldir", "propusk", "skipped", "nb", "kelmadi", "qatnashmadi")
_W_LATE = ("late", "kechik", "opozd", "delay")
_W_PRESENT = ("present", "attended", "keldi", "qatnashdi", "prisut")

# API dagi mashg'ulot turi kodlari → ota-onaga ko'rinadigan nom
LESSON_TYPES = {"lecture": "Ma'ruza", "lection": "Ma'ruza", "seminar": "Seminar", "practice": "Amaliy", "practical": "Amaliy",
                "practical lesson": "Amaliy", "lab": "Laboratoriya", "laboratory": "Laboratoriya", "lab work": "Laboratoriya",
                "exam": "Imtihon", "consultation": "Konsultatsiya", "self study": "Mustaqil ta'lim"}

STATE: dict[str, dict] = {k: {"fails": 0} for k in KINDS}
_LOCKS = {k: asyncio.Lock() for k in KINDS}


def endpoint(kind: str) -> str:
    return {"attendance": INTEGRATION_ATTENDANCE, "schedule": INTEGRATION_SCHEDULE, "subjects": INTEGRATION_SUBJECTS}[kind]


def configured(kind: str | None = None) -> bool:
    """Polling sozlanganmi (kind berilmasa — biror turi)."""
    kinds = [kind] if kind else KINDS
    return any(bool(endpoint(k)) and (INTEGRATION_URL or endpoint(k).startswith("http")) for k in kinds)


def active(kind: str) -> bool:
    """Shu tur avtomatik keladimi (polling yoki webhook)."""
    return configured(kind) or bool(INTEGRATION_WEBHOOK_SECRET)


# ---------------------------------------------------------------- qo'lda moslash (data/integration_map.json)
def overrides() -> dict:
    try:
        return json.loads(MAP_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def set_override(kind: str, field: str, key: str | None) -> None:
    data = overrides()
    m = data.setdefault(kind, {})
    if key:
        m[field] = key
    else:
        m.pop(field, None)
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


def clear_overrides(kind: str) -> None:
    data = overrides()
    data.pop(kind, None)
    MAP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


# ---------------------------------------------------------------- javobni o'qish
def flatten(obj, prefix: str = "") -> dict:
    """{"student": {"name": "A"}, "groups": [{"name": "X"}, {"name": "Y"}]} → {"student.name": "A", "groups.name": "X, Y"}."""
    out: dict = {}
    if not isinstance(obj, dict):
        return {prefix or "value": obj}
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(flatten(v, key))
        elif isinstance(v, list):
            if v and all(isinstance(x, dict) for x in v):
                parts = [flatten(x, key) for x in v]
                for sub in dict.fromkeys(s for p in parts for s in p):
                    vals = [cell_str(p.get(sub)) for p in parts if p.get(sub) not in (None, "")]
                    out[sub] = ", ".join(dict.fromkeys(vals))
            else:
                out[key] = ", ".join(cell_str(x) for x in v if x not in (None, ""))
        else:
            out[key] = v
    return out


_LIST_KEYS = ("items", "data", "results", "records", "rows", "list", "content", "result", "value", "lessons",
              "attendance", "schedule")


def find_records(payload) -> tuple[list[dict], str]:
    """JSON javobdagi yozuvlar ro'yxati (eng katta lug'atlar ro'yxati) va uning yo'li."""
    best: list | None = None
    best_path = ""

    def walk(x, path: str, depth: int) -> None:
        nonlocal best, best_path
        if depth > 6:
            return
        if isinstance(x, list):
            if x and all(isinstance(i, dict) for i in x[:50]):
                last = path.rsplit(".", 1)[-1]
                if best is None or len(x) > len(best) or (len(x) == len(best) and last in _LIST_KEYS):
                    best, best_path = x, path
            return
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}.{k}" if path else str(k), depth + 1)

    walk(payload, "", 0)
    return (best or []), best_path


def _dig(obj, path: str):
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


_NEXT = ("next", "links.next", "meta.next", "pagination.next", "next_page_url", "_links.next.href", "data.next",
         "paging.next", "@odata.nextLink", "meta.pagination.links.next", "data.pagination.next", "links.next.href")
_PAGES = ("pageCount", "totalPages", "total_pages", "last_page", "pages", "page_count", "lastPage", "num_pages")
_PAGE_ROOTS = ("", "meta", "pagination", "data.pagination", "_meta", "meta.pagination", "data", "paging", "data._meta")


def next_page(payload, url: str, page: int) -> str | None:
    """Keyingi sahifa: aniq havola (next) yoki sahifalar soni (pageCount, last_page …) bo'yicha."""
    if not isinstance(payload, dict):
        return None
    for path in _NEXT:
        v = _dig(payload, path)
        if isinstance(v, str) and v.strip():
            return urljoin(url, v.strip())
    for root in _PAGE_ROOTS:
        for name in _PAGES:
            total = parse_int(_dig(payload, f"{root}.{name}" if root else name))
            if total:
                return with_param(url, INTEGRATION_PAGE_PARAM, page + 1) if page < total else None
    return None


def with_param(url: str, name: str, value) -> str:
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != name] + [(name, str(value))]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


def table_records(rows: list[tuple]) -> list[dict]:
    """Excel/CSV jadvali → yozuvlar: sarlavha — birinchi 15 qatordan eng ko'p matnli qator."""
    if not rows:
        return []
    best_i, best_n = 0, -1
    for i, r in enumerate(rows[:15]):
        n = sum(1 for c in r if isinstance(c, str) and c.strip())
        if n > best_n:
            best_i, best_n = i, n
    head, seen = [], {}
    for j, c in enumerate(rows[best_i]):
        h = cell_str(c) or f"ustun{j + 1}"
        seen[h] = seen.get(h, 0) + 1
        head.append(h if seen[h] == 1 else f"{h} {seen[h]}")
    out = []
    for r in rows[best_i + 1:]:
        if any(c not in (None, "") for c in r):
            out.append({head[j]: r[j] for j in range(min(len(head), len(r)))})
    return out


def _decode(body: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", "replace")


def explode(rec: dict, depth: int = 0, pk: str = "") -> list[dict]:
    """Ichma-ich yozuvlar: {"date": …, "lessons": [{…}, {…}]} → har bir dars alohida yozuv (kun maydonlari bilan).
    Faqat «yozuvga o'xshash» ro'yxatlar ochiladi (elementida 3+ maydon); [{"name": "3-1a-24"}] kabilar — birlashtiriladi.
    Ochilgan yozuvda _pk — ota yozuv raqami, _ck — ichki yozuvdan kelgan maydonlar: ota yozuvdagi jami son har bir
    ichki yozuvda takrorlanadi, uni yig'ishda bir marta olish uchun (fan: lessonCount 30 = ma'ruza 15 + seminar 15)."""
    if depth > 3:
        return [rec]
    best, size = None, 0
    for k, v in rec.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            avg = sum(len(x) for x in v) / len(v)
            if avg >= 3 and len(v) * avg > size:
                best, size = k, len(v) * avg
    if best is None:
        return [rec]
    parent = {k: v for k, v in rec.items() if k != best}
    out = []
    for i, child in enumerate(rec[best]):
        out += explode({**parent, **child, "_pk": pk, "_ck": ",".join(str(k) for k in child)}, depth + 1, f"{pk}.{i}")
    return out


def parse_payload(body: bytes, ctype: str = "") -> tuple[list[dict], object, str]:
    """Javob tanasi → (yozuvlar, JSON (sahifalash uchun) yoki None, yozuvlar yo'li / format)."""
    ct = (ctype or "").lower()
    if body[:2] == b"PK" or "spreadsheet" in ct or "ms-excel" in ct:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
        try:
            rows = [tuple(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
        finally:
            wb.close()
        return table_records(rows), None, "excel"
    text = _decode(body)
    st = text.lstrip()
    if "json" in ct or st[:1] in ("[", "{"):
        payload = json.loads(text)
        recs, path = find_records(payload)
        if not recs and isinstance(payload, dict) and payload and not any(isinstance(v, list) for v in payload.values()):
            recs = [payload]  # bitta yozuv
        out = [x for i, r in enumerate(recs) for x in explode(r, 0, str(i))]
        # ichidagi ro'yxati bo'sh yozuvlar (masalan, darssiz kun: "lessons": []) — tashlab yuboriladi
        nested = {k for r in recs for k, v in r.items() if isinstance(v, list) and v and all(isinstance(i, dict) for i in v)
                  and sum(len(i) for i in v) / len(v) >= 3}
        out = [x for x in out if not any(isinstance(x.get(k), list) and not x[k] for k in nested)]
        return [flatten(x) for x in out], payload, path or "json"
    if not st:
        return [], None, "bo'sh"
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [tuple(r) for r in csv.reader(io.StringIO(text), dialect)]
    return table_records(rows), None, "csv"


# ---------------------------------------------------------------- maydonlarni tanish
def humanize(key: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key))
    return normalize_text(s)


_GENERIC_LAST = {"name", "title", "nomi", "value", "label", "text", "code", "short name", "full name", "id"}


def variants(key: str) -> list[str]:
    """«student.full_name» → [«student full name», «full name», …]: oldinroq — aniqroq."""
    segs = [h for h in (humanize(s) for s in str(key).split(".")) if h]
    if not segs:
        return []
    out = [" ".join(segs)]
    if len(segs) >= 2:
        out.append(" ".join(segs[-2:]))
        if segs[-1] in _GENERIC_LAST:
            out.append(f"{segs[-2]} {segs[-1]}")
            if segs[-1] not in ("id", "code"):
                out.append(segs[-2])
    out.append(segs[-1])
    return list(dict.fromkeys(out))


def _names(kind: str, fld: str) -> list[str]:
    base = list(HINTS[kind].get(fld, []))
    imp = "attendance_stats" if fld in ("attended", "absent", "excused") else kind
    base += [n for n in ALIASES.get(imp, {}).get(fld, []) if n != "id"]
    return list(dict.fromkeys(normalize_text(n) for n in base))


def auto_map(keys: list[str], kind: str) -> dict[str, str]:
    """Maydon → yozuvdagi kalit. Har bir kalit bir marta ishlatiladi; eng aniq moslik birinchi."""
    cands = []
    for key in keys:
        vs = variants(key)
        for fld in HINTS[kind]:
            names = _names(kind, fld)
            for vi, v in enumerate(vs):
                if v in names:
                    cands.append((names.index(v), vi, 0, fld, key))
                    break
            else:
                for vi, v in enumerate(vs):  # «Ota-ona telefoni (vergul bilan)» kabi: boshlanishi mos
                    hit = next((i for i, n in enumerate(names) if len(n) > 3 and v.startswith(n + " ")), None)
                    if hit is not None:
                        cands.append((hit, vi, 1, fld, key))
                        break
    cands.sort(key=lambda c: (c[2], c[0], c[1]))
    out: dict[str, str] = {}
    used: set[str] = set()
    for _, _, _, fld, key in cands:
        if fld not in out and key not in used:
            out[fld] = key
            used.add(key)
    # yozuvning o'z raqami («id») talaba ID si emas: talaba F.I.Sh. bilan topiladi
    if "hemis_id" in out and humanize(out["hemis_id"]) == "id":
        out.pop("hemis_id")
    return out


# «11 lesson», «Lesson 3», «5-dars», «12-mavzu», «3» — bu fan nomi emas (darsning tartib raqami)
_NOT_SUBJECT = re.compile(r"^\s*(\d+\s*(st|nd|rd|th|chi|-?chi)?\s*[-.]?\s*(lesson|lecture|seminar|dars|ders|mavzu|zanyatie|"
                          r"urok|topic|week)\b|\d+\s*$|(lesson|lecture|dars|ders|mavzu|zanyatie|urok|topic)\s*[-№#]?\s*\d+)", re.I)
_SUBJECT_KEYS = ("title", "subject", "discipline", "fan", "predmet", "course", "name")


def _bad_subject(values: list) -> bool:
    vals = [normalize_text(v) for v in values if v not in (None, "")]
    return bool(vals) and sum(1 for v in vals if _NOT_SUBJECT.match(v)) * 2 > len(vals)


def fix_subject(m: dict, records: list[dict], keys: list[str]) -> dict:
    """Fan maydonidagi qiymatlar «11 lesson» kabi bo'lsa — fan nomi boshqa maydondan (masalan, title) olinadi."""
    if "subject" not in m or not records:
        return m
    sample = records[:300]
    if not _bad_subject([r.get(m["subject"]) for r in sample]):
        return m
    used = set(m.values())
    for word in _SUBJECT_KEYS:
        for k in keys:
            h = humanize(k)
            if k in used or k.startswith("_ctx") or word not in h.split():
                continue
            vals = [r.get(k) for r in sample]
            if any(isinstance(v, str) and v.strip() for v in vals) and not _bad_subject(vals):
                return {**m, "subject": k}
    return m


def mapping_for(keys: list[str], kind: str, records: list[dict] | None = None) -> dict[str, str]:
    m = auto_map(keys, kind)
    if records:
        m = fix_subject(m, records, keys)
    for fld, key in overrides().get(kind, {}).items():
        if key == "-":
            m.pop(fld, None)
        elif key in keys:
            m = {f: k for f, k in m.items() if k != key}
            m[fld] = key
    return m


# ---------------------------------------------------------------- qiymatlar
def _epoch(v) -> datetime | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, str) and re.fullmatch(r"\d{10}(\d{3})?", v.strip()):
        v = int(v.strip())
    if isinstance(v, (int, float)) and 1e9 <= v < 1e13:
        return datetime.fromtimestamp(v / 1000 if v >= 1e12 else v, TZ)
    return None


def _iso_dt(v) -> datetime | None:
    if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{1,2}:\d{2}", v.strip()):
        s = v.strip().replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            try:
                d = datetime.fromisoformat(s[:19])
            except ValueError:
                return None
        return d.astimezone(TZ) if d.tzinfo else d
    return None


def to_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    d = _epoch(v) or _iso_dt(v)
    if d:
        return d.date()
    if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v.strip()):
        return parse_date(v.strip()[:10])
    return parse_date(v)


def to_time(v) -> str | None:
    d = _epoch(v) or _iso_dt(v)
    return f"{d.hour:02d}:{d.minute:02d}" if d else parse_time(v)


def truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v > 0
    t = normalize_text(v)
    if not t:
        return False
    if re.fullmatch(r"[\d ]+", t):
        return (parse_float(v) or 0) > 0
    return t not in ("0", "false", "no", "yoq", "net", "null", "none", "n a")


def to_status(v, key: str = "") -> str | None:
    """Holat: matn («Keldi», «НБ», «absent», «excused»), belgi yoki true/false (maydon nomiga qarab)."""
    if v is None or v == "":
        return None
    k = humanize(key)
    if isinstance(v, bool) or (isinstance(v, (int, float)) and v in (0, 1) and not isinstance(v, float)):
        on = bool(v)
        if any(w in k for w in _W_EXCUSED):
            return "sababli" if on else None
        if any(w in k for w in _W_LATE):
            return "kechikdi" if on else "keldi"
        if any(w in k for w in _W_ABSENT):
            return "kelmadi" if on else "keldi"
        return "keldi" if on else "kelmadi"
    s = normalize_status(v)
    if s:
        return s
    t = normalize_text(v)
    for words, st in ((("excused", "explicable", "justified", "reason", "uvazh"), "sababli"),
                      (("late", "tardy", "opozd"), "kechikdi"),
                      (("absent", "missing", "unexcused", "otsutst", "propusk", "nb"), "kelmadi"),
                      (("present", "attended", "here", "prisut", "keldi"), "keldi")):
        if any(w in t for w in words):
            return st
    return None


def derive_status(rec: dict) -> tuple[str | None, float | None]:
    """Holat maydoni yo'q: explicable / absent_on / is_late kabi maydonlardan."""
    flags = [(humanize(k), v) for k, v in rec.items()]
    excused = any(truthy(v) for k, v in flags if any(w in k for w in _W_EXCUSED))
    late = any(truthy(v) for k, v in flags if any(w in k for w in _W_LATE))
    absent_vals = [v for k, v in flags if any(w in k.split() or (len(w) > 3 and w in k) for w in _W_ABSENT)]
    absent = any(truthy(v) for v in absent_vals)
    hours = max((parse_float(v) or 0 for v in absent_vals
                 if not isinstance(v, bool) and parse_float(v) is not None), default=0) or None
    present = [truthy(v) for k, v in flags if any(w in k for w in _W_PRESENT)]
    if absent or (present and not any(present)):
        return ("sababli" if excused else "kelmadi"), hours if hours and hours > 1 else None
    if late:
        return "kechikdi", None
    if absent_vals or present:
        return "keldi", None
    return None, None


def _pair_by_time(start: str | None, starts: list[str]) -> int | None:
    if not start:
        return None
    for p, (s, _) in PAIR_TIMES.items():
        if s == start:
            return p
    return starts.index(start) + 1 if start in starts else None


# ---------------------------------------------------------------- yozuvlar → import jadvali
def build_table(records: list[dict], kind: str) -> tuple[list[tuple], dict]:
    """Yozuvlar → importer tushunadigan jadval (sarlavha + qatorlar) va ma'lumot (moslik, tanilmagan kalitlar)."""
    records = [flatten(r) if any(isinstance(v, (dict, list)) for v in r.values()) else r for r in records]
    keys = list(dict.fromkeys(k for r in records for k in r))
    m = mapping_for(keys, kind, records)
    info = {"mapping": m, "unmapped": [k for k in keys if k not in m.values() and k not in ("_pk", "_ck")],
            "records": len(records), "mode": kind}
    if kind == "attendance":
        daily = "date" in m
        if not daily and "absent" in m:
            info["mode"] = "attendance_stats"
            fields = ["hemis_id", "full_name", "group_name", "attended", "absent", "excused"]
        else:
            fields = ["hemis_id", "full_name", "group_name", "date", "pair", "subject", "lesson_type", "teacher",
                      "status", "hours"]
    else:
        fields = ["group_name", "weekday", "pair", "start_time", "end_time", "time_range", "subject", "lesson_type",
                  "teacher", "room", "week_type", "subgroup", "code"]
    get = lambda r, f: r.get(m[f]) if f in m else None  # noqa: E731

    def start_of(r) -> str | None:  # boshlanish vaqti yoki «13:30-14:50» dagi birinchi vaqt
        return to_time(get(r, "start_time")) or parse_time(get(r, "time_range"))

    starts = sorted({t for t in (start_of(r) for r in records) if t})
    rows: list[dict] = []
    for r in records:
        x: dict = {}
        for f in fields:
            v = get(r, f)
            if f in ("date",):
                d = to_date(v)
                v = d.isoformat() if d else v
            elif f in ("start_time", "end_time"):
                v = to_time(v) or v
            elif f == "status":
                v = to_status(v, m.get("status", ""))
            elif f == "lesson_type" and isinstance(v, str):
                v = LESSON_TYPES.get(normalize_text(v), " ".join(v.split()))
            elif f in ("subject", "teacher", "room", "group_name", "code") and isinstance(v, str):
                v = " ".join(v.replace('"', " ").split()) if f == "group_name" else " ".join(v.split())
            elif f == "pair" and v not in (None, ""):
                n = parse_int(re.sub(r"\D+", " ", cell_str(v)).split()[0]) if re.search(r"\d", cell_str(v)) else None
                v = n or v
            x[f] = v
        if kind == "attendance" and info["mode"] == "attendance":
            if not x.get("status"):
                st, hrs = derive_status(r)
                x["status"] = st
                if hrs and not x.get("hours"):
                    x["hours"] = hrs
            if not x.get("pair"):
                x["pair"] = _pair_by_time(start_of(r), starts)
        if kind == "schedule":
            d = to_date(get(r, "date"))
            if not d and r.get("_ctx_week") and x.get("weekday"):  # {monday} haftasi + hafta kuni
                wd = parse_weekday(x["weekday"])
                d = (to_date(r["_ctx_week"]) + timedelta(days=wd - 1)) if wd else None
            if d:
                x["_date"] = d
            if not x.get("weekday") and d:
                x["weekday"] = WEEKDAYS[d.weekday()]
            if not x.get("pair"):
                x["pair"] = _pair_by_time(start_of(r), starts)
        rows.append(x)
    if kind == "schedule":
        rows = _weekly(rows, "week_type" in m)
    # tanilgan va hisoblab topilgan (holat, juftlik, hafta kuni, hafta turi, soat) ustunlar; davomatda talaba
    # ustunlari doim bor (manbada o'chirilgan qoldirishni «keldi» qilish uchun)
    out_fields = [f for f in fields if f in m or any(x.get(f) not in (None, "") for x in rows)
                  or f in ("status", "pair", "weekday") or (kind == "attendance" and f in ("hemis_id", "full_name", "group_name"))]
    table = [tuple(CANON[f] for f in out_fields)]
    table += [tuple(x.get(f) for f in out_fields) for x in rows]
    info["fields"] = out_fields
    return table, info


def _weekly(rows: list[dict], explicit_week: bool) -> list[dict]:
    """Sanali darslar ro'yxati → haftalik jadval: bir xil dars bir marta; faqat toq yoki juft haftada bo'lsa —
    shu hafta turi (olingan oraliqda ikkala hafta turi ham bo'lsa)."""
    dated = [r for r in rows if r.get("_date")]
    if not dated:
        return [{k: v for k, v in r.items() if k != "_date"} for r in rows]
    parities = {week_type_of(r["_date"]) for r in dated}
    slots: dict[tuple, dict] = {}
    for r in rows:
        key = (group_key(r.get("group_name")), normalize_text(r.get("weekday")), r.get("pair"),
               normalize_text(r.get("subject")), normalize_text(r.get("subgroup")))
        s = slots.get(key)
        if s is None:
            s = slots[key] = {**{k: v for k, v in r.items() if k != "_date"}, "_weeks": set()}
        if r.get("_date"):
            s["_weeks"].add(week_type_of(r["_date"]))
    out = []
    for s in slots.values():
        weeks = s.pop("_weeks")
        if not explicit_week:
            s["week_type"] = next(iter(weeks)) if len(parities) > 1 and len(weeks) == 1 else "har"
        out.append(s)
    return out


# ---------------------------------------------------------------- talabaning fanlari (fan bo'yicha davomat va kredit)
_HOUR_WORDS = ("hour", "hours", "soat", "soatlar", "chas", "chasov")


def _in_hours(key: str) -> bool:
    """Qoldirishlar soatdami (para emas): .env dagi INTEGRATION_SUBJECTS_UNIT yoki maydon nomi («absent_hours»)."""
    if INTEGRATION_SUBJECTS_UNIT in ("hour", "hours", "soat"):
        return True
    if INTEGRATION_SUBJECTS_UNIT in ("pair", "pairs", "para"):
        return False
    return any(w in humanize(key).split() for w in _HOUR_WORDS)


_SUM_FIELDS = ("planned", "held", "attended", "absent", "excused", "unexcused", "percent")


def subject_rows(records: list[dict]) -> tuple[list[dict], dict]:
    """Yozuvlar → talaba × fan: {hemis_id, full_name, group_name, subject, code, credits, attended, absent, excused}
    (sonlar — para, HEMIS fan statistikasi kabi). Ikki ko'rinish tanilad:
    • jami ko'rsatkichlar (har bir fan — qatnashgan / qoldirgan / sababli soni yoki foizi);
    • darslar ro'yxati (har bir dars — sana va holat): holatlar sanaladi.
    Davomat sonlari bo'lmasa ham fan krediti (kredit maydoni yoki fan kodi «CTIR25C4» → 4) olinadi."""
    records = [flatten(r) if any(isinstance(v, (dict, list)) for v in r.values()) else r for r in records]
    keys = list(dict.fromkeys(k for r in records for k in r))
    m = mapping_for(keys, "subjects", records)
    totals = bool({"attended", "absent", "unexcused"} & set(m))
    lessons = not totals and bool({"status", "date"} & set(m))
    info = {"mapping": m, "unmapped": [k for k in keys if k not in m.values() and not k.startswith("_")],
            "records": len(records), "mode": "totals" if totals else "lessons" if lessons else "credits", "notes": []}
    get = lambda r, f: r.get(m[f]) if f in m else None  # noqa: E731

    def num(r, f):
        v = parse_float(get(r, f))
        if v is None:
            return None
        return v / HEMIS_STATS_HOURS_PER_UNIT if f != "percent" and _in_hours(m[f]) else v

    sem0 = semester_start()
    agg: dict[tuple, dict] = {}
    no_attended = 0
    for r in records:
        subj = " ".join(cell_str(get(r, "subject")).split())
        if not subj or _NOT_SUBJECT.match(normalize_text(subj)):
            continue
        hid = cell_str(get(r, "hemis_id") or r.get("_ctx.hemis_id")).strip()
        name = " ".join(cell_str(get(r, "full_name") or r.get("_ctx.full_name")).split())
        grp = " ".join(cell_str(get(r, "group_name") or r.get("_ctx.group")).replace('"', " ").split())
        key = (hid or normalize_text(name), subject_key(subj) or normalize_text(subj))
        o = agg.get(key)
        if o is None:
            o = agg[key] = {"hemis_id": hid or None, "full_name": name or None, "group_name": grp or None,
                            "subject": subj, "code": None, "credits": None, "credits_src": None,
                            "attended": None, "absent": None, "excused": None, "semester": None,
                            "planned": None, "held_n": None, "_row": len(agg) + 1}
        code = cell_str(get(r, "code")).strip()
        if code and not o["code"]:
            o["code"] = code
        o["semester"] = o["semester"] or cell_str(get(r, "semester")).strip() or None
        c = parse_float(get(r, "credits"))
        if c and 0 < c <= 30:
            o["credits"], o["credits_src"] = c, "manage"
        elif not o["credits"] and credits_from_code(code):
            o["credits"], o["credits_src"] = float(credits_from_code(code)), "code"
        if not lessons:
            # sonlar yig'iladi: ichki yozuvlar (ma'ruza, seminar) — qo'shiladi; ota yozuvdagi jami (har bir ichki yozuvda
            # takrorlanadi) — bir marta; alohida yozuvlar — qo'shiladi
            acc = o.setdefault("_acc", {})
            for f in _SUM_FIELDS:
                v = num(r, f)
                if v is None or v < 0:
                    continue
                a = acc.setdefault(f, {"sum": 0.0, "n": 0, "seen": set()})
                if "_pk" in r and m[f].split(".")[0] not in str(r.get("_ck") or "").split(","):
                    if r["_pk"] in a["seen"]:
                        continue
                    a["seen"].add(r["_pk"])
                a["sum"] += v
                a["n"] += 1
        else:
            d = to_date(get(r, "date"))
            if d and d < sem0:
                continue
            st = to_status(get(r, "status"), m.get("status", "")) if "status" in m else None
            if not st:
                st, _ = derive_status(r)
            if not st:
                continue
            for f in ("attended", "absent", "excused"):
                o[f] = o[f] or 0
            if st in ("keldi", "kechikdi"):
                o["attended"] += 1
            else:
                o["absent"] += 1
                o["excused"] += st == "sababli"
    for o in agg.values():
        acc = o.pop("_acc", {})
        val = lambda f: (acc[f]["sum"] / acc[f]["n"] if f == "percent" else acc[f]["sum"]) if f in acc and acc[f]["n"] else None  # noqa: E731,B023
        o["planned"], o["held_n"] = val("planned"), val("held")
        if not totals:
            continue
        att, ab, ex, un = val("attended"), val("absent"), val("excused"), val("unexcused")
        if ab is None and un is not None:
            ab = un + (ex or 0)
        if ex is None and un is not None and ab is not None:
            ex = max(ab - un, 0)
        if att is None and ab is not None:
            held, pct = val("held"), val("percent")
            if held is not None and held >= ab:
                att = held - ab  # o'tilgan (yo'qlama qilingan) darslar − qoldirilganlar
            elif pct is not None and 0 <= pct < 100 and ab > 0:
                att = round(ab * pct / (100 - pct), 1)
        if ab is None:
            continue
        if att is None:
            no_attended += 1
            continue
        o.update(attended=att, absent=ab, excused=min(ex or 0, ab))
    if not totals and not lessons and "held" in m:
        _done_as_attendance(records, m, agg, info)
    _current_semester(list(agg.values()), info)
    if no_attended:
        info["notes"].append(f"{no_attended} ta fanda faqat qoldirishlar soni bor (qatnashgan / o'tilgan darslar soni yoki "
                             "foiz yo'q) — davomat foizini hisoblab bo'lmaydi, shuning uchun bu fanlar davomati yozilmadi. "
                             "/integratsiya_moslash fanlar qatnashgan=… bilan maydonni ko'rsating")
    return list(agg.values()), info


def done_streams(records: list[dict], m: dict) -> dict[tuple, dict[str, float]]:
    """Oqim (fan × dars turi × academicGroupId) → {talaba: doneLessonCount}. Bir oqimdagi talabalar bir xil darslarni
    o'tadi: «o'tilgan darslar» bo'lsa — hammasida bir xil, talabaning «keldi» belgilari bo'lsa — har xil."""
    out: dict[tuple, dict[str, float]] = {}
    for r in records:
        subj = " ".join(cell_str(r.get(m["subject"]) if "subject" in m else "").split())
        v = parse_float(r.get(m["held"]))
        if not subj or v is None:
            continue
        if "_pk" in r and m["held"].split(".")[0] not in str(r.get("_ck") or "").split(","):
            continue  # ota yozuvdagi jami — oqim emas
        who = cell_str(r.get(m["hemis_id"]) if "hemis_id" in m else r.get("_ctx.hemis_id")).strip() \
            or normalize_text(r.get("_ctx.full_name"))
        stream = cell_str(r.get(m["stream"])) if "stream" in m else ""
        ltype = normalize_text(r.get(m["lesson_type"])) if "lesson_type" in m else ""
        key = (subject_key(subj) or normalize_text(subj), ltype, stream)
        out.setdefault(key, {})[who] = out.get(key, {}).get(who, 0) + v
    return out


def _done_as_attendance(records: list[dict], m: dict, agg: dict, info: dict) -> None:
    """doneLessonCount — talabaning «keldi» deb belgilangan darslari bo'lsa: qoldirgan = oqimdagi eng ko'p − talabaniki
    (oqimdagi eng ko'p — o'tilgan darslar). Sababli/sababsiz ajratilmaydi (Manage bermaydi) — hammasi sababsiz."""
    streams = done_streams(records, m)
    multi = {k: v for k, v in streams.items() if len(v) >= 2}
    varied = [k for k, v in multi.items() if len(set(v.values())) > 1]
    info["done"] = {"streams": len(streams), "compared": len(multi), "varied": len(varied)}
    if INTEGRATION_DONE_MEANS == "held":
        return
    if INTEGRATION_DONE_MEANS != "attended":  # auto
        if not multi:
            info["notes"].append("doneLessonCount talabaning davomatimi yoki o'tilgan darslar sonimi — aniqlash uchun bir "
                                 "oqimdan kamida 2 talaba kerak: python integration.py tahlil")
            return
        if not varied:
            info["notes"].append(f"doneLessonCount — o'tilgan darslar soni: {len(multi)} ta oqimning hammasida talabalarda bir xil "
                                 "(talabaning kelgan-kelmagani emas). Davomat bu manzildan olinmaydi.")
            return
    for key, vals in streams.items():
        held = max(vals.values())
        for who, v in vals.items():
            o = agg.get((who, key[0]))
            if o is None:
                continue
            o["attended"] = (o["attended"] or 0) + v
            o["absent"] = (o["absent"] or 0) + max(held - v, 0)
            o["excused"] = 0
    info["mode"] = "done"
    info["notes"].append(
        (f"doneLessonCount — talabaning «keldi» belgilari: {len(varied)} / {len(multi)} oqimda talabalarda har xil. "
         if INTEGRATION_DONE_MEANS != "attended" else "doneLessonCount — talabaning «keldi» belgilari (INTEGRATION_DONE_MEANS). ")
        + "Qoldirgan = oqimdagi eng ko'p − talabaniki; sababli/sababsiz ajratilmaydi.")


def _current_semester(rows: list[dict], info: dict) -> None:
    """O'quv yili bo'yicha javobda ikki semestr fanlari bo'lsa — davomat faqat joriy semestrdan olinadi (aks holda kuzgi
    fanlarning qoldirishlari bahorgi umumiy davomatga qo'shilib ketadi): talabaning davomati bor eng oxirgi semestri.
    Kreditlar barcha fanlardan olinadi."""
    def order(s: str) -> tuple:
        n = re.findall(r"\d+", s or "")
        return (int(n[-1]) if n else -1, s or "")

    by_st: dict[str, list[dict]] = {}
    for r in rows:
        by_st.setdefault(r["hemis_id"] or normalize_text(r["full_name"]), []).append(r)
    dropped = 0
    for rs in by_st.values():
        sems = {r["semester"] for r in rs if r["semester"] and r["absent"] is not None
                and (r["attended"] or 0) + (r["absent"] or 0) > 0}
        if len({r["semester"] for r in rs if r["semester"]}) < 2 or not sems:
            continue
        cur = max(sems, key=order)
        for r in rs:
            if r["semester"] and r["semester"] != cur and r["absent"] is not None:
                r["attended"] = r["absent"] = r["excused"] = None
                dropped += 1
    if dropped:
        info["notes"].append(f"Javobda bir necha semestr fanlari bor — davomat faqat joriy semestrdan olindi "
                             f"(boshqa semestrning {dropped} ta fan yozuvi davomatga qo'shilmadi, kreditlari olindi)")


async def ingest_subjects(bot, records: list[dict], origin: str = "polling") -> dict:
    """Talabaning fanlari: kreditlar va fan bo'yicha davomat — har bir kurs bazasiga (fanlar kesimi, umumiy davomat,
    25% chegarasi va ota-onaga xabarlar — fan bo'yicha HEMIS statistikasi fayli bilan bir xil)."""
    from handlers.admin import apply_subject_stats
    rows, info = subject_rows(records)
    result = {"kind": "subjects", "records": len(records), "mapping": info["mapping"], "unmapped": info["unmapped"],
              "mode": info["mode"], "courses": {}, "changed": False, "errors": 0, "origin": origin, "notes": info["notes"]}
    if not rows:
        return result
    for key in db.keys():
        with use_course(key):
            mine, missing = resolve_students([dict(r) for r in rows], await db.student_lookup())
            if not mine:
                continue
            sig = sorted((r["student_id"], subject_key(r["subject"]), r["credits"], r["planned"], r["held_n"], r["attended"],
                          r["absent"], r["excused"])
                         for r in mine)
            digest = hashlib.sha256(json.dumps(sig, default=str).encode()).hexdigest()
            prev = await db.get_setting("integ_hash_subjects")
            if prev == digest:
                result["courses"][key] = {"rows": len(mine), "changed": False}
                continue
            silent = prev is None and INTEGRATION_FIRST_SILENT
            lines = await apply_subject_stats(bot, mine, silent=silent, source=f"{INTEGRATION_NAME} (avtomatik)")
            await db.set_setting("integ_hash_subjects", digest)
            result["changed"] = True
            result["courses"][key] = {"rows": len(mine), "changed": True, "silent": silent, "report": "\n".join(lines)}
    return result


# ---------------------------------------------------------------- HTTP
def _headers_and_url(url: str) -> tuple[dict, str]:
    headers = {"Accept": "application/json, text/csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*",
               "User-Agent": "JIDU-ota-ona-bot/1.0"}
    for part in INTEGRATION_HEADERS.split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k.strip():
                headers[k.strip()] = v.strip()
    tok, mode = INTEGRATION_TOKEN, INTEGRATION_AUTH.strip()
    low = mode.lower()
    if tok and low != "none":
        if low == "bearer":
            headers["Authorization"] = f"Bearer {tok}"
        elif low == "token":
            headers["Authorization"] = f"Token {tok}"
        elif low == "basic":
            headers["Authorization"] = "Basic " + base64.b64encode(tok.encode()).decode()
        elif low.startswith("header:"):
            headers[mode.split(":", 1)[1].strip()] = tok
        elif low.startswith("query:"):
            url = with_param(url, mode.split(":", 1)[1].strip(), tok)
    return headers, url


async def _since(kind: str) -> str:
    return await central.get_meta(f"integ_last_ok_{kind}") or ""


def window(kind: str) -> tuple[date, date]:
    t = today()
    if kind == "attendance":
        return t - timedelta(days=INTEGRATION_DAYS), t
    monday = t - timedelta(days=t.weekday())
    return monday, monday + timedelta(days=13)  # shu va keyingi hafta: toq/juft hafta aniqlanadi


def per_student(kind: str) -> bool:
    """Manzilda {hemis_id} bor — har bir talaba (jadval uchun: har guruhdan bittasi) uchun alohida so'rov."""
    return "{hemis_id}" in endpoint(kind)


def mondays(kind: str) -> list[date]:
    """{monday} bo'lsa — oraliqdagi haftalar dushanbalari (jadval: shu va keyingi hafta, davomat: oxirgi kunlar)."""
    if "{monday}" not in endpoint(kind):
        return [None]
    d1, d2 = window(kind)
    m = d1 - timedelta(days=d1.weekday())
    out = []
    while m <= d2:
        out.append(m)
        m += timedelta(days=7)
    return out


PROBE_HEMIS: str | None = None  # tekshirishda aniq talaba: python integration.py jadval --hemis=381231100123


def real_hemis(hid) -> bool:
    """Haqiqiy HEMIS ID — faqat raqamlar (12 xonali). DEMO0001 kabi namunaviy ID lar so'ralmaydi."""
    return bool(re.fullmatch(r"\d{6,}", str(hid or "").strip()))


async def targets(kind: str) -> list[dict]:
    """{hemis_id} uchun talabalar: davomat — hammasi, jadval — har bir guruhdan bittasi (jadval guruhga bir xil)."""
    out, groups = [], set()
    for key in db.keys():
        with use_course(key):
            rows = await db.fetchall("SELECT hemis_id, full_name, group_name, group_key FROM students "
                                     "WHERE COALESCE(hemis_id, '') != '' ORDER BY group_key, id")
        for r in rows:
            if not real_hemis(r["hemis_id"]):  # namunaviy (DEMO0001) yoki qo'lda yozilgan ID — Manage'da yo'q
                continue
            if kind == "schedule" and INTEGRATION_SCHEDULE_PER_GROUP:
                if r["group_key"] in groups:
                    continue
                groups.add(r["group_key"])
            out.append(r)
    return out


async def build_url(kind: str, hemis: str | None = None, monday: date | None = None) -> tuple[str, bool]:
    """To'liq manzil va «to'liq oraliqmi» (incremental {since} bo'lsa — yo'q)."""
    path = endpoint(kind)
    url = path if path.startswith("http") else f"{INTEGRATION_URL}/{path.lstrip('/')}"
    d1, d2 = window(kind)
    ts = lambda d, end=False: int(datetime(d.year, d.month, d.day, 23 if end else 0, 59 if end else 0,  # noqa: E731
                                          59 if end else 0, tzinfo=TZ).timestamp())
    since = await _since(kind) if "{since}" in url else ""
    vals = {"from": d1.isoformat(), "to": d2.isoformat(), "from_ts": ts(d1), "to_ts": ts(d2, True),
            "since": since or f"{d1.isoformat()}T00:00:00", "from_dmy": d1.strftime("%d.%m.%Y"),
            "to_dmy": d2.strftime("%d.%m.%Y"), "hemis_id": hemis or "", "monday": monday.isoformat() if monday else "",
            "academic_year": INTEGRATION_ACADEMIC_YEAR}
    for k, v in vals.items():
        url = url.replace("{" + k + "}", str(v))
    return url, "{since}" not in path


async def _fetch_url(session, url: str, limit: int, probe: bool) -> tuple[list[dict], dict, bytes]:
    """Bitta manzil: barcha sahifalari. Qaytaradi: yozuvlar, ma'lumot, birinchi javob tanasi (tekshirish uchun)."""
    records: list[dict] = []
    info = {"pages": 0, "format": "", "truncated": False}
    seen: set[str] = set()
    first = b""
    page, cur = 1, url
    while cur:
        headers, real = _headers_and_url(cur)
        async with session.get(real, headers=headers) as r:
            body = await r.read()
            if r.status >= 400:
                raise IntegrationError(f"HTTP {r.status}: {_short(body)}", status=r.status)
            ctype = r.headers.get("Content-Type", "")
        first = first or body
        recs, payload, fmt = parse_payload(body, ctype)
        digest = hashlib.sha256(json.dumps(recs, default=str, sort_keys=True).encode()).hexdigest()
        if digest in seen:  # API sahifa parametrini e'tiborsiz qoldirdi
            break
        seen.add(digest)
        records += recs
        info["pages"], info["format"] = page, fmt
        if not recs:
            break
        nxt = next_page(payload, cur, page)
        if nxt and page >= limit:
            info["truncated"] = not probe
            break
        cur, page = nxt, page + 1
    return records, info, first


async def fetch(kind: str, max_pages: int | None = None) -> tuple[list[dict], dict]:
    """Barcha sahifalarni (va {hemis_id}/{monday} bo'lsa — har bir talaba va hafta uchun) olib, yozuvlarni qaytaradi."""
    import aiohttp
    probe = max_pages is not None
    limit = max_pages or INTEGRATION_MAX_PAGES
    tg = (await targets(kind)) if per_student(kind) else [None]
    if per_student(kind) and not tg and not (probe and PROBE_HEMIS):
        raise IntegrationError("bazada haqiqiy (raqamli) HEMIS ID li talaba yo'q — DEMO0001 kabi namunaviy talabalar "
                               "so'ralmaydi. «Talabalar» (kontingent) faylini yuklang yoki --hemis=381231100123 bilan sinang")
    weeks = mondays(kind)
    if probe:  # tekshirish: bitta hafta; javob bo'sh bo'lsa — keyingi talaba (5 tagacha)
        weeks = weeks[:1]
        tg = [{"hemis_id": PROBE_HEMIS, "full_name": "", "group_name": ""}] if PROBE_HEMIS and per_student(kind) else tg[:5]
    url0, complete = await build_url(kind, tg[0]["hemis_id"] if tg[0] else None, weeks[0])
    info = {"pages": 0, "format": "", "complete": complete, "truncated": False, "url": _safe_url(url0),
            "requests": 0, "failed": 0, "sample": b""}
    records: list[dict] = []
    sem = asyncio.Semaphore(INTEGRATION_CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=INTEGRATION_TIMEOUT)
    fatal: list[Exception] = []

    async def one(session, st, monday):
        if fatal:
            return
        url, _ = await build_url(kind, st["hemis_id"] if st else None, monday)
        async with sem:
            if fatal:  # boshqa so'rov kalit yoki manzil xatosini topdi — qolganlari yuborilmaydi
                return
            try:
                recs, i, body = await _fetch_url(session, url, limit, probe)
            except IntegrationError as e:
                info["failed"] += 1
                if e.status == 404 and "cannot get" in str(e).lower():  # manzil (yo'l) umuman yo'q — talabaga bog'liq emas
                    fatal.append(IntegrationError(f"bunday manzil Manage'da yo'q (HTTP 404: Cannot GET): {_safe_url(url)}. "
                                                  f".env dagi {ENV_NAMES[kind]} qatorini tekshiring", status=404))
                elif e.status in (401, 403) or not per_student(kind):  # kalit noto'g'ri — davom etishdan foyda yo'q
                    fatal.append(e)
                elif info["failed"] <= 3:
                    log.warning("%s: %s (%s) — %s", INTEGRATION_NAME, TITLES[kind], st and st["hemis_id"], e)
                return
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                info["failed"] += 1
                if not per_student(kind):
                    fatal.append(e)
                return
        info["requests"] += 1
        if recs and not records:
            info["url"] = _safe_url(url)
        info["pages"] += i["pages"]
        info["format"] = i["format"] or info["format"]
        info["truncated"] = info["truncated"] or i["truncated"]
        info["sample"] = info["sample"] or body
        for r in recs:  # javobda talaba/guruh/hafta bo'lmasa — so'rovdagisi qo'shiladi
            if st:
                r.setdefault("_ctx.hemis_id", st["hemis_id"])
                r.setdefault("_ctx.full_name", st["full_name"])
                r.setdefault("_ctx.group", st["group_name"])
            if monday:
                r.setdefault("_ctx_week", monday.isoformat())
        records.extend(recs)

    async with aiohttp.ClientSession(timeout=timeout) as session:  # timeout — har bir so'rov uchun
        if probe:
            for st in tg:
                await one(session, st, weeks[0])
                if records or fatal:
                    break
            tg = tg[:max(1, info["requests"] + info["failed"])]
        else:
            await asyncio.gather(*(one(session, st, m) for st in tg for m in weeks))
    if fatal:
        raise fatal[0]
    total = len(tg) * len(weeks)
    if info["failed"] and info["failed"] * 2 > total:
        raise IntegrationError(f"so'rovlarning ko'pi bajarilmadi: {info['failed']} / {total}")
    if info["failed"]:
        info["complete"] = False  # ba'zi talabalar olinmadi — «manbada yo'q» deb hisoblab bo'lmaydi
    return records, info


class IntegrationError(Exception):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


def _short(body: bytes) -> str:
    return " ".join(_decode(body[:300]).split())[:200]


def _safe_url(url: str) -> str:
    """Jurnal va xabarlar uchun: so'rovdagi kalit/parol yashiriladi."""
    p = urlsplit(url)
    q = [(k, "***" if re.search(r"key|token|secret|pass|auth", k, re.I) else v)
         for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunsplit((p.scheme, p.netloc.split("@")[-1], p.path, urlencode(q, safe="*{}"), ""))


# ---------------------------------------------------------------- qabul qilish (kurslarga ajratib)
class _Report:
    """admin._process_import_body uchun «xabar» o'rnini bosadi: natija matnini yig'adi."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    async def edit_text(self, text: str, **_) -> None:
        self.parts.append(text)

    async def answer(self, text: str, **_) -> None:
        self.parts.append(text)


async def ingest(bot, kind: str, records: list[dict], complete_window: tuple[date, date] | None = None,
                 origin: str = "polling") -> dict:
    """Yozuvlarni har bir kurs bazasiga ajratib, Excel importi yo'lidan o'tkazadi."""
    if kind == "subjects":
        return await ingest_subjects(bot, records, origin)
    from handlers.admin import _process_import_body
    table, info = build_table(records, kind)
    result = {"kind": kind, "records": len(records), "mapping": info["mapping"], "unmapped": info["unmapped"],
              "mode": info["mode"], "courses": {}, "changed": False, "errors": 0, "origin": origin}
    if not records:
        return result
    parsed = parse_rows(table, kind)
    if parsed.fatal:
        raise IntegrationError(parsed.fatal + " — /integratsiya → «Tekshirish» da maydonlar mosligini ko'ring.")
    result["errors"] = len(parsed.errors)
    result["error_samples"] = parsed.errors[:5]
    daily = kind == "attendance" and parsed.kind == "attendance"
    fields = info["fields"]
    col = {f: i for i, f in enumerate(fields)}
    for key in db.keys():
        with use_course(key):
            if kind == "attendance":
                rows, _ = resolve_students([dict(r) for r in parsed.rows], await db.student_lookup())
                idx = sorted({r["_row"] for r in rows})
            else:
                mine = set((await db.group_counts()).keys())
                idx = sorted({r["_row"] for r in parsed.rows if r.get("group_key") in mine})
                rows = []
            sub = [table[0]] + [table[i - 1] for i in idx]
            extra = await _reconcile(rows, complete_window, fields, col) if daily and complete_window else []
            sub += extra
            if len(sub) == 1:
                continue
            digest = hashlib.sha256(json.dumps(sub, default=str).encode()).hexdigest()
            prev = await db.get_setting(f"integ_hash_{kind}")
            if prev == digest:
                result["courses"][key] = {"rows": len(sub) - 1, "changed": False}
                continue
            first = prev is None
            silent = first and INTEGRATION_FIRST_SILENT
            rep = _Report()
            ok = await _process_import_body(bot, rep, kind, sub, "jim integ" if silent else "integ",
                                            f"{INTEGRATION_NAME} (avtomatik)", None, None)
            if not ok:
                raise IntegrationError(" ".join(rep.parts)[:300] or "import bajarilmadi")
            await db.set_setting(f"integ_hash_{kind}", digest)
            if daily:
                await _mark_source(rows)
            result["changed"] = True
            result["courses"][key] = {"rows": len(sub) - 1, "changed": True, "corrected": len(extra),
                                      "silent": silent, "report": rep.parts[0] if rep.parts else ""}
    return result


async def _reconcile(rows: list[dict], win: tuple[date, date], fields: list[str], col: dict) -> list[tuple]:
    """Avval integratsiyadan kelgan qoldirish manbada endi yo'q (o'qituvchi to'g'riladi) — «keldi» qatori."""
    d1, d2 = win
    have = {(r["student_id"], r["date"], r["pair"]) for r in rows}
    old = await db.fetchall(
        """SELECT a.student_id, a.date, a.pair, a.subject, s.hemis_id, s.full_name, s.group_name
           FROM attendance a JOIN students s ON s.id = a.student_id
           WHERE a.source = ? AND a.status != 'keldi' AND a.date BETWEEN ? AND ?""",
        (SOURCE, d1.isoformat(), d2.isoformat()))
    out = []
    for o in old:
        if (o["student_id"], o["date"], o["pair"]) in have:
            continue
        x = {"hemis_id": o["hemis_id"], "full_name": o["full_name"], "group_name": o["group_name"],
             "date": o["date"], "pair": o["pair"], "subject": o["subject"], "status": "keldi"}
        out.append(tuple(x.get(f) for f in fields))
    return out


async def _mark_source(rows: list[dict]) -> None:
    if rows:
        await db.conn.executemany("UPDATE attendance SET source = ? WHERE student_id = ? AND date = ? AND pair = ?",
                                  [(SOURCE, r["student_id"], r["date"], r["pair"]) for r in rows])
        await db.conn.commit()


# ---------------------------------------------------------------- polling va webhook
async def pull(bot, kind: str) -> dict:
    """Bir marta olish va qabul qilish (xatolar holatga yoziladi, super-adminga — takrorlansa)."""
    st = STATE[kind]
    async with _LOCKS[kind]:
        st["last_try"] = now_iso()
        try:
            records, info = await fetch(kind)
            win = window(kind) if info["complete"] and not info["truncated"] else None
            res = await ingest(bot, kind, records, win)
        except Exception as e:
            st["fails"] = st.get("fails", 0) + 1
            st["error"] = _err_text(e)
            level = logging.ERROR if st["fails"] in (3, 30) or st["fails"] % 360 == 0 else logging.WARNING
            log.log(level, "%s: %s olinmadi (%s-marta ketma-ket): %s", INTEGRATION_NAME, TITLES[kind], st["fails"],
                    st["error"], exc_info=not isinstance(e, (IntegrationError, asyncio.TimeoutError, OSError)))
            return {"error": st["error"]}
        if st.get("fails", 0) >= 3:
            log.warning("%s: %s yana olinmoqda (%s marta xatodan keyin)", INTEGRATION_NAME, TITLES[kind], st["fails"])
        st.update(fails=0, error=None, last_ok=now_iso(), pages=info["pages"], format=info["format"],
                  truncated=info["truncated"], result=res)
        if res["changed"]:
            st["last_change"] = st["last_ok"]
        await central.set_meta(f"integ_last_ok_{kind}", st["last_ok"])
        return res


async def push(bot, kind: str, body: bytes, ctype: str) -> dict:
    """Webhook: Manage yuborgan ma'lumot (JSON, CSV yoki Excel) — darhol qabul qilinadi."""
    records, _, fmt = parse_payload(body, ctype)
    async with _LOCKS[kind]:
        res = await ingest(bot, kind, records, None, origin="webhook")
    st = STATE[kind]
    st.update(last_push=now_iso(), push_result=res)
    if res["changed"]:
        st["last_change"] = st["last_push"]
    return res


def check_secret(given: str) -> bool:
    return bool(INTEGRATION_WEBHOOK_SECRET) and hmac.compare_digest(given.encode(), INTEGRATION_WEBHOOK_SECRET.encode())


def _err_text(e: Exception) -> str:
    if isinstance(e, asyncio.TimeoutError):
        return f"javob kutish vaqti tugadi ({INTEGRATION_TIMEOUT} s)"
    if isinstance(e, json.JSONDecodeError):
        return f"javob JSON emas: {e}"
    return str(e) or e.__class__.__name__


async def paused() -> bool:
    return await central.get_meta("integ_paused") == "1"


async def set_paused(value: bool) -> None:
    await central.set_meta("integ_paused", "1" if value else "0")


def interval(kind: str) -> int:
    return {"attendance": INTEGRATION_INTERVAL, "subjects": INTEGRATION_SUBJECTS_INTERVAL}.get(kind, INTEGRATION_SCHEDULE_INTERVAL)


async def loop(bot) -> None:
    """Fon vazifasi: sozlangan turlarni o'z oralig'ida olib turadi (to'xtatilgan bo'lsa — kutadi)."""
    if not configured():
        return
    log.info("%s integratsiyasi yoqildi: %s", INTEGRATION_NAME,
             ", ".join(f"{TITLES[k]} — har {interval(k)} s" for k in KINDS if configured(k)))
    await asyncio.sleep(5)
    due = {k: 0.0 for k in KINDS}
    while True:
        try:
            if not await paused():
                for kind in KINDS:
                    if configured(kind) and _time.monotonic() >= due[kind]:
                        due[kind] = _time.monotonic() + interval(kind)
                        await pull(bot, kind)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Integratsiya siklida xatolik")
        await asyncio.sleep(3)


# ---------------------------------------------------------------- super-admin uchun matnlar
def _ago(iso: str | None) -> str:
    return fmt_dt(iso) if iso else "—"


async def status_text() -> str:
    lines = [f"🔌 <b>Integratsiya: {esc(INTEGRATION_NAME)}</b>"]
    if not configured() and not INTEGRATION_WEBHOOK_SECRET:
        lines.append("\nHali sozlanmagan. Kalit berilgach .env faylida to'ldiring (README, «Integratsiya» bo'limi):\n"
                     "<code>INTEGRATION_URL=https://manage.example.uz/api\nINTEGRATION_TOKEN=…\n"
                     "INTEGRATION_ATTENDANCE=attendance?from={from}&amp;to={to}\nINTEGRATION_SCHEDULE=schedule</code>\n"
                     "so'ng botni qayta ishga tushiring va «🔍 Tekshirish» ni bosing.")
        return "\n".join(lines)
    if await paused():
        lines.append("⏸ <b>To'xtatilgan</b> — avtomatik olish o'chiq (webhook ham qabul qilinmaydi).")
    lines.append(f"Manba: <code>{esc(_safe_url(INTEGRATION_URL) or '—')}</code>"
                 + (f", kalit: {esc(INTEGRATION_AUTH)}" if INTEGRATION_TOKEN else ", kalitsiz"))
    if INTEGRATION_WEBHOOK_SECRET:
        lines.append("Webhook: <code>POST /api/integration/attendance</code> va <code>/schedule</code> — yoqilgan")
    for kind in KINDS:
        st = STATE[kind]
        lines.append(f"\n<b>{TITLES[kind]}</b>")
        if not configured(kind):
            lines.append("  avtomatik olish sozlanmagan" + (" (faqat webhook)" if INTEGRATION_WEBHOOK_SECRET else ""))
        else:
            lines.append(f"  har {interval(kind)} soniyada; oxirgi urinish: {_ago(st.get('last_try'))}, "
                         f"muvaffaqiyatli: {_ago(st.get('last_ok') or await _since(kind))}")
        if st.get("last_push"):
            pr = st["push_result"]
            lines.append(f"  webhook oxirgi marta: {_ago(st['last_push'])} — {pr['records']} yozuv"
                         + (", yangilandi" if pr["changed"] else ", o'zgarish yo'q"))
        if st.get("error"):
            lines.append(f"  ❌ xato ({st['fails']} marta ketma-ket): {esc(st['error'][:300])}")
        res = st.get("result")
        if res:
            lines.append(f"  yozuvlar: {res['records']}" + (f" ({st.get('pages')} sahifa)" if st.get("pages") else "")
                         + (f", o'qilmagan qatorlar: {res['errors']}" if res.get("errors") else "")
                         + ("; ⚠️ sahifalar chegarasiga yetdi" if st.get("truncated") else ""))
            for key, c in res["courses"].items():
                lines.append(f"  • {esc(key)}: {c['rows']} qator" + (" — yangilandi" if c["changed"] else
                                                                      " — o'zgarish yo'q")
                             + (f", to'g'rilangan: {c['corrected']}" if c.get("corrected") else ""))
        if st.get("last_change"):
            lines.append(f"  oxirgi o'zgarish: {_ago(st['last_change'])}")
    return "\n".join(lines)


def env_report() -> str:
    """Sozlamalar nega o'qilmaganini topish uchun: .env qayerda, bormi va qaysi qatorlar ko'rindi (parol ko'rsatilmaydi)."""
    from config import BASE_DIR
    env = BASE_DIR / ".env"
    lines = [f".env fayli: {env} — {'bor' if env.exists() else 'TOPILMADI'}"]
    for alt in (".env.txt", ".env.env", "env.txt"):
        if (BASE_DIR / alt).exists():
            lines.append(f"⚠️ {BASE_DIR / alt} ham bor — Blocknot faylni shu nom bilan saqlagan bo'lishi mumkin; "
                         "sozlamalarni .env ga o'tkazing")
    found = {}
    if env.exists():
        try:
            for raw in env.read_text("utf-8-sig", errors="replace").splitlines():
                k = raw.split("=", 1)[0].strip()
                if k.startswith("INTEGRATION_"):
                    found.setdefault(k, []).append(raw.split("=", 1)[1].strip() if "=" in raw else "")
        except OSError:
            pass
    for k in ("INTEGRATION_URL", "INTEGRATION_AUTH", "INTEGRATION_TOKEN", "INTEGRATION_SCHEDULE", "INTEGRATION_ATTENDANCE",
              "INTEGRATION_SUBJECTS", "INTEGRATION_ACADEMIC_YEAR"):
        vals = found.get(k)
        if not vals:
            lines.append(f"  {k}: .env da yo'q")
            continue
        last = vals[-1]
        shown = "(kiritilgan)" if k == "INTEGRATION_TOKEN" and last else (last or "bo'sh")
        lines.append(f"  {k}: {shown}" + (f"  — ⚠️ {len(vals)} marta yozilgan, oxirgisi olinadi" if len(vals) > 1 else ""))
    lines.append(f"Bot o'qigani: URL={'bor' if INTEGRATION_URL else 'yoq'}, SCHEDULE={'bor' if INTEGRATION_SCHEDULE else 'yoq'}, "
                 f"ATTENDANCE={'bor' if INTEGRATION_ATTENDANCE else 'yoq'}, SUBJECTS={'bor' if INTEGRATION_SUBJECTS else 'yoq'}, "
                 f"AUTH={INTEGRATION_AUTH}")
    if "{academic_year}" in INTEGRATION_SUBJECTS and not INTEGRATION_ACADEMIC_YEAR:
        lines.append("⚠️ INTEGRATION_SUBJECTS da {academic_year} bor, lekin INTEGRATION_ACADEMIC_YEAR to'ldirilmagan (masalan 8)")
    return "\n".join(lines)


async def probe(kind: str) -> str:
    """Ulanishni tekshirish: birinchi sahifa, tanilgan maydonlar va namunaviy qatorlar (bazaga yozilmaydi)."""
    if not configured(kind):
        return f"<b>{TITLES[kind]}</b>: manzil sozlanmagan ({ENV_NAMES[kind]}).\n" + esc(env_report())
    try:
        records, info = await fetch(kind, max_pages=1)
    except Exception as e:
        return f"<b>{TITLES[kind]}</b>\n❌ {esc(_err_text(e))}"
    lines = [f"<b>{TITLES[kind]}</b> — <code>{esc(info['url'])}</code>",
             f"Javob: {esc(info['format'] or '—')}, birinchi sahifada {len(records)} ta yozuv"]
    if not records:
        lines.append("Yozuv kelmadi — sanalar oralig'ida ma'lumot bo'lmasligi yoki yo'l noto'g'ri bo'lishi mumkin."
                     + (" Talabaning HEMIS ID si Manage'dagi bilan bir xilligini tekshiring yoki aniq talaba bilan sinang: "
                        "python integration.py jadval --hemis=381231100123 --dump (javob data papkasidagi faylga saqlanadi)."
                        if per_student(kind) else ""))
        return "\n".join(lines)
    if kind == "subjects":
        return "\n".join(lines + await _probe_subjects(records))
    table, binfo = build_table(records, kind)
    m = binfo["mapping"]
    ov = overrides().get(kind, {})
    lines.append("\n<b>Tanilgan maydonlar</b> (maydon ← API dagi nomi):")
    for f, k in m.items():
        lines.append(f"  • {FIELD_NAMES.get(f, f)} ← <code>{esc(k)}</code>" + (" ✋" if ov.get(f) == k else ""))
    need = (["date", "pair", "subject"] if binfo["mode"] == "attendance" else ["absent"]) if kind == "attendance" \
        else ["group_name", "subject"]
    miss = [f for f in need if f not in m]
    if kind == "attendance" and not ({"hemis_id", "full_name"} & set(m)):
        miss.insert(0, "hemis_id")
    if miss:
        lines.append("⚠️ Topilmadi: " + ", ".join(FIELD_NAMES.get(f, f) for f in miss))
    if binfo["unmapped"]:
        lines.append("Ishlatilmagan maydonlar: " + esc(", ".join(binfo["unmapped"][:25]))
                     + (" …" if len(binfo["unmapped"]) > 25 else ""))
    parsed = parse_rows(table, kind)
    if parsed.fatal:
        lines.append(f"❌ {esc(parsed.fatal)}")
    else:
        lines.append(f"\nO'qildi: {len(parsed.rows)} qator" + (f", xato: {len(parsed.errors)}" if parsed.errors else ""))
        for e in parsed.errors[:3]:
            lines.append(f"  ⚠️ {esc(e)}")
        for r in parsed.rows[:3]:
            if parsed.kind == "attendance":
                lines.append(f"  • {esc(r.get('hemis_id') or r.get('full_name') or '')} — {r['date']}, {r['pair']}-juftlik, "
                             f"{esc(r['subject'])}: <b>{r['status']}</b>")
            elif parsed.kind == "attendance_stats":
                lines.append(f"  • {esc(r.get('hemis_id') or r.get('full_name') or '')} — qatnashmagan {r['absent']}")
            else:
                lines.append(f"  • {esc(r['group_name'])}: {WEEKDAYS[r['weekday'] - 1] if isinstance(r['weekday'], int) else r['weekday']}, "
                             f"{r['pair']}-juftlik ({r.get('start_time') or '—'}), {esc(r['subject'])}, {r['week_type']}")
        found = 0
        for key in db.keys():
            with use_course(key):
                if kind == "attendance":
                    ok, _ = resolve_students([dict(r) for r in parsed.rows], await db.student_lookup())
                    found += len(ok)
                else:
                    mine = set((await db.group_counts()).keys())
                    found += sum(1 for r in parsed.rows if r.get("group_key") in mine)
        lines.append(f"Bot bazasidagi talabalar/guruhlarga tegishli: {found} ta qator"
                     + ("" if found else " — ⚠️ hech biri mos kelmadi (ID yoki guruh nomlarini tekshiring)"))
    lines.append(f"\nMaydon noto'g'ri tanilgan bo'lsa: <code>/integratsiya_moslash {CLI_WORDS[kind]} maydon=API_nomi</code>")
    return "\n".join(lines)


TAHLIL_GROUP: str | None = None  # python integration.py tahlil --guruh=3-10c-24


async def analyse_done() -> str:
    """doneLessonCount nimani bildirishini ma'lumotdan aniqlash: guruh(lar)dagi barcha talabalar uchun fanlarni olib,
    bir oqimdagi (academicGroupId) talabalarning qiymatlarini solishtiradi. Bazaga yozilmaydi."""
    if not configured("subjects"):
        return f"Manzil sozlanmagan ({ENV_NAMES['subjects']})."
    global targets
    orig = targets

    async def only_group(kind: str) -> list[dict]:
        rows = await orig(kind)
        if TAHLIL_GROUP:
            return [r for r in rows if group_key(r["group_name"]) == group_key(TAHLIL_GROUP)]
        first = rows[0]["group_key"] if rows else None  # standart: birinchi guruh
        return [r for r in rows if r["group_key"] == first]

    targets = only_group
    try:
        records, info = await fetch("subjects")
    finally:
        targets = orig
    recs = [flatten(r) if any(isinstance(v, (dict, list)) for v in r.values()) else r for r in records]
    keys = list(dict.fromkeys(k for r in recs for k in r))
    m = mapping_for(keys, "subjects", recs)
    students = {r.get("_ctx.hemis_id") for r in recs}
    lines = [f"So'rovlar: {info['requests']} ta talaba, xato: {info['failed']}; yozuvlar: {len(recs)}"]
    if "held" not in m:
        return "\n".join(lines + ["doneLessonCount (o'tilgan darslar) maydoni topilmadi."])
    streams = done_streams(recs, m)
    lines.append(f"Talabalar: {len(students)}, oqimlar (fan × dars turi × academicGroupId): {len(streams)}\n")
    varied = 0
    names = {}
    for r in recs:
        names[r.get("_ctx.hemis_id")] = r.get("_ctx.full_name") or r.get("_ctx.hemis_id")
    for (subj, lt, stream), vals in sorted(streams.items()):
        uniq = sorted(set(vals.values()))
        if len(vals) >= 2 and len(uniq) > 1:
            varied += 1
        dist = ", ".join(f"{v:g} — {sum(1 for x in vals.values() if x == v)} ta" for v in uniq)
        lines.append(f"• {subj} [{lt or '—'}] {stream[:8]}: {len(vals)} talaba; doneLessonCount: {dist}")
        if 1 < len(uniq) and len(vals) >= 2:
            mx = uniq[-1]
            low = sorted(((v, names.get(w, w)) for w, v in vals.items() if v < mx))[:5]
            lines.append("    kamroq: " + "; ".join(f"{n} — {v:g} (eng ko'pi {mx:g})" for v, n in low))
    multi = sum(1 for v in streams.values() if len(v) >= 2)
    lines.append("")
    if not multi:
        lines.append("Xulosa: solishtirish uchun bir oqimda kamida 2 talaba kerak (bazaga shu guruh talabalarini yuklang).")
    elif varied:
        lines.append(f"Xulosa: {varied} / {multi} oqimda bir guruhdagi talabalarda doneLessonCount HAR XIL — demak u talabaning "
                     "yo'qlamada «keldi» deb belgilangan darslari. Bot qoldirgan darslarni shundan hisoblaydi "
                     "(INTEGRATION_DONE_MEANS=auto). Kamroq chiqqan talabalarni haqiqiy davomat bilan solishtirib ko'ring.")
    else:
        lines.append(f"Xulosa: {multi} ta oqimning hammasida doneLessonCount talabalarda BIR XIL — demak u o'tilgan darslar soni, "
                     "talabaning kelgan-kelmagani emas.")
    return "\n".join(lines)


async def _probe_subjects(records: list[dict]) -> list[str]:
    rows, info = subject_rows(records)
    m = info["mapping"]
    ov = overrides().get("subjects", {})
    mode = {"totals": "har bir fan bo'yicha jami sonlar", "lessons": "darslar ro'yxati (holatlar sanaladi)",
            "done": "doneLessonCount — talabaning «keldi» belgilari (oqimdagi talabalar bilan solishtirildi)",
            "credits": "davomat sonlari YO'Q — faqat fan ma'lumotlari (kredit, ajratilgan darslar) olinadi"}[info["mode"]]
    lines = ["\n<b>Tanilgan maydonlar</b> (maydon ← API dagi nomi):"]
    for f, k in m.items():
        lines.append(f"  • {FIELD_NAMES.get(f, f)} ← <code>{esc(k)}</code>"
                     + (" (soat → para)" if f in ("attended", "absent", "excused", "unexcused", "held") and _in_hours(k) else "")
                     + (" ✋" if ov.get(f) == k else ""))
    miss = [f for f in ("subject",) if f not in m]
    if not ({"credits", "code", "planned"} & set(m)):
        miss.append("credits")
    if miss:
        lines.append("⚠️ Topilmadi: " + ", ".join(FIELD_NAMES.get(f, f) for f in miss))
    lines.append(f"Ko'rinishi: {mode}")
    for n in info["notes"]:
        lines.append(f"⚠️ {esc(n)}")
    if info["unmapped"]:
        lines.append("Ishlatilmagan maydonlar: " + esc(", ".join(info["unmapped"][:30])) + (" …" if len(info["unmapped"]) > 30 else ""))
    from subject_limits import limit_from_pairs, limit_pairs
    with_cred = [r for r in rows if r["credits"]]
    with_att = [r for r in rows if r["absent"] is not None]
    with_pl = [r for r in rows if r["planned"]]
    lines.append(f"\nFanlar: {len(rows)}, krediti bor: {len(with_cred)}, ajratilgan darslar soni bor: {len(with_pl)}, "
                 f"davomati bor: {len(with_att)}")
    for r in rows[:12]:
        att = (f"qatnashgan {r['attended']:g}, qoldirgan {r['absent']:g} (sababli {r['excused']:g})"
               if r["absent"] is not None else "davomat yo'q")
        lim = limit_from_pairs(r["planned"]) or limit_pairs(r["credits"])
        lines.append(f"  • {esc(r['subject'])}" + (f" [{esc(r['code'])}]" if r["code"] else "")
                     + (f" — {int(r['credits'])} kredit" if r["credits"] else "")
                     + (f" — {r['planned']:g} para ajratilgan" + (f", {r['held_n']:g} tasi o'tildi" if r["held_n"] is not None else "")
                        if r["planned"] else "")
                     + (f" → chegara {lim} para" if lim else " — chegara noma'lum") + f"; {att}")
    if rows and not with_att:
        lines.append("ℹ️ Bu manzilda davomat (qatnashgan / qoldirgan) yo'q. Chegaralar shu yerdan olinadi, davomatning o'zi esa "
                     "HEMIS fan statistikasi fayllaridan yoki Manage'ning davomat manzilidan (INTEGRATION_ATTENDANCE) keladi.")
    found = 0
    for key in db.keys():
        with use_course(key):
            ok, _ = resolve_students([dict(r) for r in rows], await db.student_lookup())
            found += len(ok)
    lines.append(f"Bot bazasidagi talabalarga tegishli: {found} ta qator"
                 + ("" if found or not rows else " — ⚠️ hech biri mos kelmadi (HEMIS ID ni tekshiring)"))
    lines.append("\nMaydon noto'g'ri tanilgan bo'lsa: <code>/integratsiya_moslash fanlar maydon=API_nomi</code>")
    return lines


FIELD_WORDS = {normalize_text(v): k for k, v in FIELD_NAMES.items()} | {k: k for k in FIELD_NAMES} | {
    "id": "hemis_id", "hemis": "hemis_id", "fish": "full_name", "fio": "full_name", "guruh": "group_name",
    "sana": "date", "juftlik": "pair", "para": "pair", "fan": "subject", "holat": "status", "turi": "lesson_type",
    "oqituvchi": "teacher", "soat": "hours", "kun": "weekday", "boshlanish": "start_time", "tugash": "end_time",
    "xona": "room", "hafta": "week_type", "kredit": "credits", "kod": "code", "qatnashgan": "attended",
    "qoldirgan": "absent", "sababli": "excused", "sababsiz": "unexcused", "otilgan": "held", "foiz": "percent"}


def parse_field(word: str) -> str | None:
    return FIELD_WORDS.get(normalize_text(word)) or FIELD_WORDS.get(word.strip())


if __name__ == "__main__":
    # python integration.py [davomat] [jadval] [--dump] — ulanishni terminalda tekshirish (bazaga yozilmaydi).
    # --dump: birinchi javobni data/integration_sample_<tur>.json ga saqlaydi (tuzilmasini ko'rish uchun).
    import sys

    async def _main() -> None:
        from bot import open_storage
        await open_storage()
        global PROBE_HEMIS
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        PROBE_HEMIS = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--hemis=")), None)
        if args[:1] == ["tahlil"]:
            global TAHLIL_GROUP
            TAHLIL_GROUP = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--guruh=")), None)
            text = await analyse_done()
            print(text)
            out = DATA_DIR / "integration_tahlil.txt"
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            out.write_text(text, "utf-8")
            print(f"\nNatija saqlandi: {out.resolve()}")
            await db.close()
            await central.close()
            return
        bad = [a for a in args if KIND_WORDS.get(a.lower()) is None]
        if bad:
            print(f"Noma'lum tur: {', '.join(bad)}. Mumkin: davomat, jadval, fanlar")
        kinds = [] if bad else [KIND_WORDS[a.lower()] for a in args] or [k for k in KINDS if configured(k)] or list(KINDS)
        for kind in kinds:
            print(re.sub(r"<[^>]+>", "", (await probe(kind)).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")))
            if "--dump" in sys.argv:
                if not configured(kind):
                    print(f"Javob saqlanmadi: .env da {ENV_NAMES[kind]} to'ldirilmagan (yoki bot uni o'qimadi — yuqoridagi "
                          ".env tekshiruviga qarang)")
                    print()
                    continue
                try:
                    _, info = await fetch(kind, max_pages=1)
                except Exception as e:  # noqa: BLE001
                    print("Javob saqlanmadi:", _err_text(e))
                else:
                    raw = info["sample"]
                    if not raw:
                        print("Javob saqlanmadi: Manage hech bir talaba uchun javob qaytarmadi (so'rovlar xato bilan tugadi)")
                    else:
                        try:
                            raw = json.dumps(json.loads(_decode(raw)), ensure_ascii=False, indent=2).encode()
                        except ValueError:
                            pass
                        DATA_DIR.mkdir(parents=True, exist_ok=True)
                        out = (DATA_DIR / f"integration_sample_{kind}.json").resolve()
                        out.write_bytes(raw)
                        print(f"Javob saqlandi: {out}")
                        print("Javob boshi:\n" + _decode(raw)[:2500])
            print()
        await db.close()
        await central.close()

    asyncio.run(_main())
