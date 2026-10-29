"""Chora ko'rish: davomat chegarasidan oshganlar va ichki tartib qoidalarini buzganlarga intizomiy choralar.

Akademik nizom (6-bob, 113-modda): sababsiz qoldirilgan darslar 36 soatdan oshsa — dekan farmoyishi bilan
«Ogohlantirish», 54 soatdan oshsa — universitet buyrug'i bilan «Hayfsan» (chegaralar — ABSENCE_WARN_LEVELS).

Jarayon: bot chegaradan oshganlarni o'zi topadi (kurs koordinatoriga darhol signal) → koordinator sababini aniqlaydi
(ota-onadan so'raydi, sababli bo'lsa ro'yxatdan chiqaradi) → tanlanganlar uchun hujjatlar avtomatik tayyorlanadi
(bildirishnoma, farmoyish/buyruq, ota-onaga ogohlantirish xati, dalolatnoma — shablonlar/chora/*.docx) → imzolangach
raqam va sana kiritilib «chiqarildi» deb belgilanadi, imzolangan nusxa va asoslovchi hujjatlar (talabaga yoki butun
hujjatga) biriktiriladi, talabaning PDF nusxasi ota-onasiga bot orqali yuboriladi → «Chora ko'rilganlar» (o'quv yili
boshidan, hujjatlari va dinamikasi bilan). Ichki tartib qoidalarini buzish bo'yicha choralar qo'lda qo'shiladi;
trimestr to'lovi qarzdorlariga — ota-onaga ogohlantirish xati.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import re
import secrets
import zipfile
from datetime import date
from pathlib import Path

import absence
import docxfill
from config import BASE_DIR, DATA_DIR
from database import db
from tenancy import COORD_GROUPS, central, course_admins, course_title, current_course, scope_students
from utils import academic_year_start, esc, fmt_pairs, group_key, now_iso, semester_start, today

log = logging.getLogger("discipline")

MEASURES = {
    "ogohlantirish": {"title": "Dekan ogohlantirishi", "short": "Ogohlantirish", "doc": "farmoyish", "level": 1, "default": 36},
    "hayfsan": {"title": "Hayfsan", "short": "Hayfsan", "doc": "buyruq", "level": 2, "default": 54},
    "boshqa": {"title": "Boshqa chora", "short": "Boshqa", "doc": None, "level": None, "default": None},
    "xat": {"title": "Ota-onaga ogohlantirish xati", "short": "Ogohlantirish xati", "doc": None, "level": None, "default": None},
}
AUTO = ("ogohlantirish", "hayfsan")  # davomat bo'yicha avtomatik aniqlanadiganlar
GROUNDS = {"davomat": "Davomat (sababsiz dars qoldirish)", "tartib": "Ichki tartib qoidalarini buzish",
           "trimestr": "Trimestr to'lovi qarzdorligi"}
DOC_KINDS = {"bildirishnoma": "Bildirishnoma", "farmoyish": "Dekan farmoyishi", "buyruq": "Buyruq (hayfsan)",
             "xat": "Ota-onaga xat", "dalolatnoma": "Dalolatnoma", "tushuntirish": "Tushuntirish xati",
             "asos": "Asoslovchi hujjat", "imzolangan": "Imzolangan nusxa", "boshqa": "Boshqa hujjat"}
# ichki tartib bo'yicha tez tanlanadigan qoidalar (hujjatga shu matn yoziladi; o'zgartirish mumkin)
RULE_PRESETS = [
    "“Odob-axloq Kodeksi”ning 11-moddasi 1-qismi 9-bandi (kiyinish talablari)",
    "“Jahon iqtisodiyoti va diplomatiya universiteti “Odob-axloq Kodeksi”ning 4-bob, 11-moddasining 4-qismi "
    "(kiyinish talablari)",
    "“JIDU Ichki tartib-qoidalari (ichki mehnat tartibi)”",
    "“Odob-axloq Kodeksi” (odob-axloq qoidalari)",
]
TEMPLATES = {  # (hujjat, asos, chora) → shablon
    ("bildirishnoma", "davomat", "ogohlantirish"): "bildirishnoma_ogohlantirish.docx",
    ("bildirishnoma", "davomat", "hayfsan"): "bildirishnoma_hayfsan.docx",
    ("bildirishnoma", "tartib", None): "bildirishnoma_tartib.docx",
    ("farmoyish", "davomat", "ogohlantirish"): "ogohlantirish_davomat.docx",
    ("farmoyish", "tartib", "ogohlantirish"): "ogohlantirish_tartib.docx",
    ("buyruq", "davomat", "hayfsan"): "hayfsan_davomat.docx",
    ("buyruq", "tartib", "hayfsan"): "hayfsan_tartib.docx",
    ("dalolatnoma", None, None): "dalolatnoma.docx",
    ("xat", "davomat", None): "xat_davomat.docx",
    ("xat", "tartib", None): "xat_tartib.docx",
    ("xat", "trimestr", None): "xat_trimestr.docx",
}
TEMPLATE_TITLES = {
    "bildirishnoma_ogohlantirish.docx": "Bildirishnoma — dekan ogohlantirishi (davomat)",
    "bildirishnoma_hayfsan.docx": "Bildirishnoma — hayfsan (davomat)",
    "bildirishnoma_tartib.docx": "Bildirishnoma — ichki tartib qoidalari buzilishi",
    "ogohlantirish_davomat.docx": "Dekan farmoyishi — ogohlantirish (davomat)",
    "ogohlantirish_tartib.docx": "Dekan farmoyishi — ogohlantirish (ichki tartib)",
    "hayfsan_davomat.docx": "Buyruq — hayfsan (davomat)",
    "hayfsan_tartib.docx": "Buyruq — hayfsan (ichki tartib)",
    "dalolatnoma.docx": "Dalolatnoma (tushuntirish xatidan bosh tortganlik)",
    "xat_davomat.docx": "Ota-onaga xat — uzrli sababsiz dars qoldirish",
    "xat_tartib.docx": "Ota-onaga xat — ichki tartib qoidalarini buzish",
    "xat_trimestr.docx": "Ota-onaga xat — trimestr to'lovi qarzdorligi",
}
LETTERS = {"xat_davomat.docx", "xat_tartib.docx", "xat_trimestr.docx"}  # har bir talabaga alohida (jadvalsiz)
BUILTIN_DIR = BASE_DIR / "shablonlar" / "chora"
CUSTOM_DIR = DATA_DIR / "templates" / "chora"  # super-admin/koordinator yuklagan shablonlar (barcha kurslar uchun)
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
MAX_FILE = 20 * 1024 * 1024


# ---------------------------------------------------------------- yordamchilar
def threshold(measure: str) -> float | None:
    m = MEASURES.get(measure) or {}
    lvl = m.get("level")
    if lvl is None:
        return None
    return float(absence.LEVELS[lvl]) if lvl < len(absence.LEVELS) else float(m["default"])


def ay_start() -> str:
    return academic_year_start().isoformat()


def _course_dir() -> Path:
    return DATA_DIR / (current_course() or "_") / "chora"


def template_path(name: str) -> Path:
    custom = CUSTOM_DIR / name
    return custom if custom.exists() else BUILTIN_DIR / name


def template_for(kind: str, ground: str, measure: str) -> str | None:
    for key in ((kind, ground, measure), (kind, ground, None), (kind, None, None)):
        if key in TEMPLATES:
            return TEMPLATES[key]
    return None


def doc_kinds(ground: str, measure: str) -> list[str]:
    """Shu chora uchun tayyorlanadigan hujjatlar."""
    letter = ["xat"] if template_for("xat", ground, measure) else []
    if measure == "xat":  # faqat ota-onaga ogohlantirish xati
        return letter
    out = ["bildirishnoma"]
    doc = (MEASURES.get(measure) or {}).get("doc")
    if doc and template_for(doc, ground, measure):
        out.append(doc)
    return out + letter + ["dalolatnoma"]


def short_name(full: str | None) -> str:
    """«Egamberdiyev Nodirbek» → «N.Egamberdiyev» (hujjatlardagi kabi)."""
    words = [w for w in re.split(r"\s+", (full or "").strip()) if w]
    if len(words) < 2:
        return words[0] if words else ""
    sur = re.compile(r"(ov|ova|ev|eva|yev|yeva|iy|aya|ina|in|lar)$", re.I)
    fam = next((w for w in words[:2] if sur.search(w)), words[0])
    first = next(w for w in words[:2] if w is not fam)
    return f"{first[0].upper()}.{fam[0].upper()}{fam[1:]}"


async def coordinator_names(groups: set[str] | None = None) -> list[str]:
    """Hujjatdagi kurs koordinator(lar)i: sozlamada yozilgan bo'lsa — o'sha, bo'lmasa — botdagi koordinatorlar
    (guruhlari biriktirilgan bo'lsa — hujjatdagi talabalar guruhlariniki)."""
    custom = (await db.get_setting("disc:coordinators") or "").strip()
    if custom:
        return [x.strip() for x in re.split(r"[,;\n]+", custom) if x.strip()]
    key = current_course()
    rows = await central._all("SELECT user_id, name FROM coordinators WHERE course_key = ? AND active = 1 ORDER BY added_at",
                              (key,)) if key else []
    if groups:
        own = [r for r in rows if set(COORD_GROUPS.get(r["user_id"], {})) & groups]
        rows = own or [r for r in rows if not COORD_GROUPS.get(r["user_id"])] or rows
    return [n for n in (short_name(r["name"]) for r in rows) if n]


def names_ning(names: list[str]) -> str:
    if not names:
        return "______________"
    if len(names) == 1:
        return names[0] + "ning"
    return ", ".join(names[:-1]) + " va " + names[-1] + "larning"


def _faculty_short(f: str) -> str:
    words = [w for w in re.split(r"[\s\-]+", f or "") if w]
    return "".join(w[0].upper() for w in words) if len(words) > 1 else (f or "")


def _date_long(d: str | None, blank: bool = True) -> str:
    """2026-10-24 → «2026-yil 24-oktabr»; sanasiz — bo'sh joy."""
    if d:
        x = date.fromisoformat(d)
        return f"{x.year}-yil {x.day}-{MONTHS[x.month - 1]}"
    return f"{today().year}-yil “____” __________" if blank else ""


def _date_quoted(d: str | None) -> str:
    """2026-10-24 → «2026-yil “24” oktabr» (farmoyish shakli)."""
    if d:
        x = date.fromisoformat(d)
        return f"{x.year}-yil “{x.day:02d}” {MONTHS[x.month - 1]}"
    return f"{today().year}-yil “____” __________"


def _dmy(d: str | date | None) -> str:
    if not d:
        return ""
    x = date.fromisoformat(d) if isinstance(d, str) else d
    return x.strftime("%d.%m.%Y")


def _num(h: float | None) -> str:
    if h is None:
        return ""
    return str(int(h)) if float(h).is_integer() else f"{h:.1f}".replace(".", ",")


# ---------------------------------------------------------------- holat: kim chegaradan oshgan
async def summaries(students: list[dict]) -> dict[int, dict]:
    since = semester_start().isoformat()
    stats = await db.bulk_latest_att_stats(since)
    tot = await db.bulk_attendance_totals(since, today().isoformat())
    out = {}
    for s in students:
        sm = absence.summary_from(stats.get(s["id"]), tot.get(s["id"]))
        if sm:
            out[s["id"]] = sm
    return out


async def _latest_cases(ground: str = "davomat") -> dict[tuple[int, str], dict]:
    rows = await db.fetchall("SELECT * FROM disc_cases WHERE ground = ? AND created_at >= ? ORDER BY id", (ground, ay_start()))
    return {(r["student_id"], r["measure"]): r for r in rows}


async def _prior(sids: set[int] | None = None) -> dict[int, list[dict]]:
    """Talabaga o'quv yili davomida rasman ko'rilgan choralar (chiqarilgan)."""
    rows = await db.fetchall(
        """SELECT c.student_id, c.measure, c.ground, o.number, o.date FROM disc_cases c JOIN disc_orders o ON o.id = c.order_id
           WHERE c.status = 'issued' AND c.created_at >= ? ORDER BY o.date, c.id""", (ay_start(),))
    out: dict[int, list[dict]] = {}
    for r in rows:
        if sids is None or r["student_id"] in sids:
            out.setdefault(r["student_id"], []).append(dict(r))
    return out


def prior_text(items: list[dict]) -> str:
    if not items:
        return "—"
    return "; ".join(f"{MEASURES.get(p['measure'], {}).get('short', p['measure'])}"
                     + (f" (№ {p['number']}, {_dmy(p['date'])})" if p.get("number") or p.get("date") else "")
                     for p in items)


async def candidates(scope: set[str] | None = ..., sids: set[int] | None = None) -> dict:
    """Davomat bo'yicha chora kerak bo'lgan talabalar: {measure: [...], excluded: [...], counts}. scope — guruhlar
    (... — joriy foydalanuvchi doirasi, None — butun kurs)."""
    students = await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name")
    students = scope_students(students) if scope is ... else scope_students(students, scope) if scope is not None else students
    if sids is not None:
        students = [s for s in students if s["id"] in sids]
    sums = await summaries(students)
    cases = await _latest_cases()
    prior = await _prior()
    parents = {r["student_id"]: r["n"] for r in await db.fetchall(
        "SELECT student_id, COUNT(*) n FROM parent_students GROUP BY student_id")}
    out: dict = {m: [] for m in AUTO}
    out["excluded"] = []
    for s in students:
        sm = sums.get(s["id"])
        if not sm:
            continue
        h = float(sm["counted"] or 0)
        for m in AUTO:
            lim = threshold(m)
            if lim is None or h < lim:
                continue
            c = cases.get((s["id"], m))
            st = c["status"] if c else "new"
            base = {"sid": s["id"], "name": s["full_name"], "group": s.get("group_name") or "", "hemis_id": s.get("hemis_id"),
                    "course": s.get("course"), "hours": h, "pairs": h / 2, "percent": sm.get("percent"),
                    "source": absence.source_note(sm), "parents": parents.get(s["id"], 0), "measure": m,
                    "case_id": c["id"] if c else None, "note": c["note"] if c else None,
                    "asked_at": c["asked_at"] if c else None, "order_id": c["order_id"] if c else None,
                    "prior": prior.get(s["id"], []), "prior_text": prior_text(prior.get(s["id"], []))}
            if st == "issued":
                continue
            if st in ("excused", "removed"):
                if h <= float(c["hours"] or 0) + 0.01:
                    out["excluded"].append({**base, "state": st, "excused_hours": c["hours"]})
                    continue
                st = "more"  # sababli deb chiqarilgandan keyin yana qoldirgan
            if st == "cancelled":
                st = "new"
            out[m].append({**base, "state": st, "excused_hours": c["hours"] if c and st == "more" else None})
    stage: dict[int, int] = {}
    for m in AUTO:
        for x in out[m]:
            if x["state"] == "draft" and x["order_id"]:
                if x["order_id"] not in stage:
                    stage[x["order_id"]] = ((await order(x["order_id"])) or {}).get("stages", {}).get("current", 1)
                x["stage"] = stage[x["order_id"]]
        out[m].sort(key=lambda x: (x["state"] not in ("new", "more"), -x["hours"], x["name"]))
    out["counts"] = {m: sum(1 for x in out[m] if x["state"] in ("new", "more")) for m in AUTO}
    out["thresholds"] = {m: threshold(m) for m in AUTO}
    out["period"] = {"from": semester_start().isoformat(), "to": today().isoformat()}
    return out


async def trimestr_candidates(scope: set[str] | None = ...) -> dict:
    """Trimestr to'lovi qarzdorlari (oxirgi hisobot bo'yicha) — ota-onaga ogohlantirish xati uchun."""
    rows = [dict(r) for r in await db.debtors("trimestr")]
    extra = {r["id"]: r for r in await db.fetchall("SELECT id, hemis_id, address FROM students")}
    for r in rows:
        r["hemis_id"], r["address"] = (extra.get(r["id"]) or {}).get("hemis_id"), (extra.get(r["id"]) or {}).get("address")
    rows = scope_students(rows) if scope is ... else scope_students(rows, scope) if scope is not None else rows
    last: dict[int, dict] = {}
    for c in await db.fetchall("""SELECT c.*, o.number, o.date FROM disc_cases c LEFT JOIN disc_orders o ON o.id = c.order_id
                                  WHERE c.ground = 'trimestr' AND c.created_at >= ? ORDER BY c.id""", (ay_start(),)):
        if c["status"] != "cancelled":
            last[c["student_id"]] = dict(c)
    parents = {r["student_id"]: r["n"] for r in await db.fetchall(
        "SELECT student_id, COUNT(*) n FROM parent_students GROUP BY student_id")}
    items = []
    for r in rows:
        c = last.get(r["id"])
        state = "new" if not c else "draft" if c["status"] == "draft" else "sent"
        items.append({"sid": r["id"], "name": r["full_name"], "group": r["group_name"] or "", "hemis_id": r["hemis_id"],
                      "course": r["course"], "debt": r["debt"], "as_of": r["as_of"], "contract": r["contract"],
                      "percent": r["percent"], "address": r["address"] or "", "parents": parents.get(r["id"], 0),
                      "state": state, "case_id": c["id"] if c else None, "order_id": c["order_id"] if c else None,
                      "sent_number": c.get("number") if c else None, "sent_date": c.get("date") if c else None,
                      "sent_amount": c.get("amount") if c else None})
    rank = {"new": 0, "sent": 1, "draft": 2}
    items.sort(key=lambda x: (rank[x["state"]], -(x["debt"] or 0), x["name"]))
    return {"items": items, "count": sum(1 for x in items if x["state"] == "new"),
            "as_of": max((x["as_of"] for x in items), default=None)}


async def set_address(sid: int, address: str) -> dict:
    """Ota-onaga xat uchun yashash manzili (kontingent faylida bo'lmasa — qo'lda)."""
    if not await db.get_student(sid):
        return {"ok": False, "error": "not_found"}
    await db.execute("UPDATE students SET address = ? WHERE id = ?", (" ".join((address or "").split())[:300] or None, sid))
    return {"ok": True}


async def _case(sid: int, measure: str, ground: str = "davomat") -> dict | None:
    return await db.fetchone("SELECT * FROM disc_cases WHERE student_id = ? AND measure = ? AND ground = ? AND created_at >= ? "
                             "ORDER BY id DESC LIMIT 1", (sid, measure, ground, ay_start()))


async def _hours(sid: int) -> float:
    st = await db.get_student(sid)
    sm = (await summaries([st])).get(sid) if st else None
    return float(sm["counted"] or 0) if sm else 0.0


async def set_case(sid: int, measure: str, action: str, note: str = "", user: int | None = None) -> dict:
    """Ro'yxatdagi talaba holati: excuse (sababli — ro'yxatdan chiqariladi), remove (o'chirish), restore (qaytarish)."""
    if measure not in AUTO or action not in ("excuse", "remove", "restore"):
        return {"ok": False, "error": "bad_action"}
    c = await _case(sid, measure)
    if c and c["status"] in ("draft", "issued"):
        return {"ok": False, "error": "in_order"}
    now = now_iso()
    if action == "restore":
        if c and c["status"] in ("excused", "removed"):
            if c["asked_at"]:  # sababi so'ralgani esda qoladi
                await db.execute("UPDATE disc_cases SET status = 'asked', note = NULL, updated_at = ?, by_user = ? WHERE id = ?",
                                 (now, user, c["id"]))
            else:
                await db.execute("DELETE FROM disc_cases WHERE id = ?", (c["id"],))
        return {"ok": True}
    status = "excused" if action == "excuse" else "removed"
    h = await _hours(sid)
    if c and c["status"] in ("asked", "excused", "removed", "cancelled"):
        await db.execute("UPDATE disc_cases SET status = ?, hours = ?, note = ?, updated_at = ?, by_user = ? WHERE id = ?",
                         (status, h, note.strip()[:1000] or None, now, user, c["id"]))
    else:
        await db.execute("INSERT INTO disc_cases (student_id, measure, ground, status, hours, note, created_at, updated_at, by_user) "
                         "VALUES (?, ?, 'davomat', ?, ?, ?, ?, ?, ?)", (sid, measure, status, h, note.strip()[:1000] or None,
                                                                       now, now, user))
    return {"ok": True}


async def ask_parents(bot, sid: int, measure: str, staff_id: int, staff_name: str) -> dict:
    """Ota-onadan sababini so'rash: bot orqali xabar (javobi «Xabarlar» bo'limiga keladi)."""
    import chat
    st = await db.get_student(sid)
    if not st or measure not in AUTO:
        return {"ok": False, "error": "not_found"}
    pids = [r["parent_id"] for r in await db.fetchall("SELECT parent_id FROM parent_students WHERE student_id = ?", (sid,))]
    if not pids:
        return {"ok": False, "error": "no_parents"}
    h = await _hours(sid)
    lim = threshold(measure)
    act = "dekan farmoyishi bilan ogohlantirish" if measure == "ogohlantirish" else "universitet buyrug'i bilan hayfsan"
    text = (f"Assalomu alaykum. Farzandingiz {st['full_name']} ({st.get('group_name') or ''}) semestr boshidan "
            f"{fmt_pairs(h)} darsni sababsiz qoldirgan. Akademik nizomga ko'ra sababsiz qoldirishlar {_num(lim)} soatdan "
            f"oshsa, {act} e'lon qilinadi.\n\nAgar qoldirishlarning sababi bo'lsa (kasallik, oilaviy holat va h.k.), "
            "iltimos, shu yerga yozing va tasdiqlovchi hujjatni (ma'lumotnoma) rasm yoki fayl qilib yuboring.")
    sent = 0
    for pid in pids:
        res = await chat.staff_reply(bot, staff_id, staff_name, sid, pid, text, await central.get_lang(pid))
        sent += bool(res.get("delivered"))
    now = now_iso()
    c = await _case(sid, measure)
    if c and c["status"] in ("asked", "excused", "removed", "cancelled"):
        await db.execute("UPDATE disc_cases SET status = CASE WHEN status = 'cancelled' THEN 'asked' ELSE status END, "
                         "asked_at = ?, updated_at = ? WHERE id = ?", (now, now, c["id"]))
    elif not c or c["status"] not in ("draft", "issued"):
        await db.execute("INSERT INTO disc_cases (student_id, measure, ground, status, hours, asked_at, created_at, updated_at, by_user) "
                         "VALUES (?, ?, 'davomat', 'asked', ?, ?, ?, ?, ?)", (sid, measure, h, now, now, now, staff_id))
    return {"ok": True, "parents": len(pids), "delivered": sent}


# ---------------------------------------------------------------- hujjatlar to'plami (farmoyish / buyruq)
async def create_order(measure: str, ground: str, items: list[dict], rule: str = "", note: str = "",
                       user: int | None = None, deadline: str | None = None) -> dict:
    """items: [{"sid": …, "note": …}]. Davomat — joriy sababsiz soat yoziladi; ichki tartib — qoida matni (rule);
    trimestr — oxirgi hisobotdagi qarz (ota-onaga xat, deadline — to'lash muddati)."""
    if measure not in MEASURES or ground not in GROUNDS:
        return {"ok": False, "error": "bad_measure"}
    if (ground == "trimestr") != (measure == "xat") and ground != "tartib":
        return {"ok": False, "error": "bad_measure"}
    if ground == "tartib" and not (rule or "").strip():
        return {"ok": False, "error": "no_rule"}
    try:
        deadline = date.fromisoformat(deadline).isoformat() if deadline else None
    except ValueError:
        return {"ok": False, "error": "bad_date"}
    sids = []
    for it in items:
        try:
            sid = int(it.get("sid"))
        except (TypeError, ValueError):
            continue
        if await db.get_student(sid) and sid not in sids:
            sids.append(sid)
    if not sids:
        return {"ok": False, "error": "no_students"}
    now = now_iso()
    lim = threshold(measure) if ground == "davomat" else None
    oid = await db.execute(
        "INSERT INTO disc_orders (measure, ground, rule, period_from, period_to, hours, status, note, deadline, created_at, "
        "created_by) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)",
        (measure, ground, (rule or "").strip()[:2000] or None, semester_start().isoformat() if ground == "davomat" else None,
         today().isoformat() if ground == "davomat" else None, lim, (note or "").strip()[:2000] or None, deadline, now, user))
    notes = {int(it["sid"]): (it.get("note") or "").strip()[:1000] for it in items if str(it.get("sid", "")).isdigit()}
    for sid in sids:
        h = await _hours(sid) if ground == "davomat" else None
        c = await _case(sid, measure, ground) if ground in ("davomat", "trimestr") else None
        if c and c["status"] == "draft" or (c and c["status"] == "issued" and ground == "davomat"):
            continue  # boshqa hujjatda
        amount = as_of = None
        if ground == "trimestr":
            p = await db.latest_payment(sid, "trimestr")
            if not p or not p.get("debt"):
                continue  # qarzi yo'q
            amount, as_of = float(p["debt"]), p["as_of"]
        if c and c["status"] in ("asked", "excused", "removed", "cancelled"):
            await db.execute("UPDATE disc_cases SET status = 'draft', order_id = ?, hours = ?, note = COALESCE(?, note), "
                             "amount = ?, as_of = ?, updated_at = ?, by_user = ? WHERE id = ?",
                             (oid, h, notes.get(sid) or None, amount, as_of, now, user, c["id"]))
        else:
            await db.execute("INSERT INTO disc_cases (student_id, measure, ground, status, hours, note, order_id, amount, as_of, "
                             "created_at, updated_at, by_user) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?)",
                             (sid, measure, ground, h, notes.get(sid) or None, oid, amount, as_of, now, now, user))
    n = (await db.fetchone("SELECT COUNT(*) n FROM disc_cases WHERE order_id = ?", (oid,)))["n"]
    if not n:
        await db.execute("DELETE FROM disc_orders WHERE id = ?", (oid,))
        return {"ok": False, "error": "already_in_order"}
    return {"ok": True, "id": oid, "students": n}


STAGES = {1: "Asos: tushuntirish xati yoki bildirishnoma", 2: "Farmoyish / buyruq", 3: "Ota-onaga xat", 4: "Yakunlangan"}


def _stages(o: dict) -> dict:
    """Chora jarayoni bosqichlari: 1 — asos (talabaning tushuntirish xati / dalolatnoma yoki kurs koordinatori
    bildirishnomasi), 2 — dekan farmoyishi / universitet buyrug'i (imzolangan, raqam va sana), 3 — ota-onaga xat.
    Faqat xat (trimestr va h.k.) — bitta bosqich."""
    cases, issued = o["cases"], o["status"] == "issued"
    n = len(cases)
    sent = sum(1 for c in cases if c.get("letter_date"))
    if o["measure"] == "xat":
        return {"letters_only": True, "current": 0 if o["status"] == "cancelled" else 4 if issued else 3,
                "letters": {"done": issued, "sent": sent, "total": n}}
    with_basis = sum(1 for c in cases if c.get("basis"))
    by_note = o.get("basis_kind") == "bildirishnoma"
    b_done = by_note or (n > 0 and with_basis == n)
    l_done = issued and n > 0 and sent == n
    current = 0 if o["status"] == "cancelled" else 1 if not (b_done or issued) else 2 if not issued else 3 if not l_done else 4
    return {"letters_only": False, "current": current,
            "basis": {"done": b_done or issued, "recorded": b_done, "bildirishnoma": by_note, "date": o.get("basis_date"),
                      "number": o.get("basis_number"), "students": with_basis, "total": n,
                      "tushuntirish": sum(1 for c in cases if c.get("basis") == "tushuntirish"),
                      "dalolatnoma": sum(1 for c in cases if c.get("basis") == "dalolatnoma")},
            "order": {"done": issued, "number": o.get("number"), "date": o.get("date")},
            "letters": {"done": l_done, "sent": sent, "total": n}}


async def order(oid: int) -> dict | None:
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return None
    o = dict(o)
    o["cases"] = [dict(r) for r in await db.fetchall(
        """SELECT c.*, s.full_name, s.group_name, s.group_key, s.course, s.faculty, s.hemis_id, s.address FROM disc_cases c
           JOIN students s ON s.id = c.student_id WHERE c.order_id = ? ORDER BY s.full_name""", (oid,))]
    o["files"] = [dict(r) for r in await db.fetchall("SELECT id, kind, name, size, mime, uploaded_at, case_id, sent_at, send_note FROM "
                                                      "disc_files WHERE order_id = ? OR case_id IN (SELECT id FROM disc_cases "
                                                      "WHERE order_id = ?) ORDER BY id", (oid, oid))]
    per_case: dict[int, int] = {}
    for f in o["files"]:
        if f["case_id"]:
            per_case[f["case_id"]] = per_case.get(f["case_id"], 0) + 1
    for c in o["cases"]:
        c["files_n"] = per_case.get(c["id"], 0)
    o["title"] = MEASURES.get(o["measure"], {}).get("title", o["measure"])
    o["ground_title"] = GROUNDS.get(o["ground"], o["ground"])
    o["doc_kinds"] = [{"kind": k, "title": DOC_KINDS[k]} for k in doc_kinds(o["ground"], o["measure"])]
    o["stages"] = _stages(o)
    o["done"] = done(o)
    if o["measure"] != "xat":  # farmoyish/buyruqdagi «Asos:» — 1-bosqich hujjatlaridan
        o["basis_text"] = await _basis_text(o, o["cases"], await coordinator_names(
            {c["group_key"] for c in o["cases"] if c.get("group_key")}))
    return o


async def orders(status: str | None = None, scope: set[str] | None = ...) -> list[dict]:
    rows = await db.fetchall("SELECT id FROM disc_orders WHERE created_at >= ? " + ("AND status = ? " if status else "")
                             + "ORDER BY id DESC", (ay_start(), status) if status else (ay_start(),))
    out = []
    for r in rows:
        o = await order(r["id"])
        if scope is ...:
            from tenancy import viewer_scope
            sc = viewer_scope()
        else:
            sc = scope
        if sc is not None and not any(group_key(c["group_name"]) in sc for c in o["cases"]):
            continue
        out.append(o)
    return out


async def delete_order(oid: int, force: bool = False) -> dict:
    """Loyihani o'chirish; force — chiqarilgan yoki bekor qilingan chorani ham butunlay (tarix va statistikadan, fayllari
    bilan). Ota-onalarga yuborilgan xabar va hujjatlar ularda qoladi."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    if o["status"] == "issued" and not force:
        return {"ok": False, "error": "issued"}
    for c in await db.fetchall("SELECT * FROM disc_cases WHERE order_id = ?", (oid,)):
        if c["ground"] == "davomat" and c["asked_at"] and o["status"] == "draft":  # ota-onadan so'ralgani yo'qolmasin
            await db.execute("UPDATE disc_cases SET status = 'asked', order_id = NULL, updated_at = ? WHERE id = ?", (now_iso(), c["id"]))
            continue
        for f in await db.fetchall("SELECT * FROM disc_files WHERE case_id = ?", (c["id"],)):
            _unlink(f["path"])
        await db.execute("DELETE FROM disc_files WHERE case_id = ?", (c["id"],))
        await db.execute("DELETE FROM disc_cases WHERE id = ?", (c["id"],))
    for f in await db.fetchall("SELECT * FROM disc_files WHERE order_id = ?", (oid,)):
        _unlink(f["path"])
    await db.execute("DELETE FROM disc_files WHERE order_id = ?", (oid,))
    await db.execute("DELETE FROM disc_orders WHERE id = ?", (oid,))
    return {"ok": True}


async def remove_case(oid: int, case_id: int) -> dict:
    """Hujjatdan bitta talabani chiqarish (tayyorlanayotgan hujjat)."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    c = await db.fetchone("SELECT * FROM disc_cases WHERE id = ? AND order_id = ?", (case_id, oid))
    if not o or not c:
        return {"ok": False, "error": "not_found"}
    if o["status"] == "issued":
        return {"ok": False, "error": "issued"}
    if c["ground"] == "davomat" and c["asked_at"]:
        await db.execute("UPDATE disc_cases SET status = 'asked', order_id = NULL, updated_at = ? WHERE id = ?", (now_iso(), case_id))
    else:
        await db.execute("DELETE FROM disc_cases WHERE id = ?", (case_id,))
    left = (await db.fetchone("SELECT COUNT(*) n FROM disc_cases WHERE order_id = ?", (oid,)))["n"]
    if not left:
        await delete_order(oid)
    return {"ok": True, "left": left}


async def issue_order(bot, oid: int, number: str, d: str, notify: bool = False, user: int | None = None) -> dict:
    """2-bosqich: farmoyish/buyruq imzolandi — raqam, sana (chora rasman ko'rilgan). Avval 1-bosqich (asos) bo'lishi
    shart. Ota-onalarga xabar odatda 3-bosqichda (xat bilan) boradi; faqat xat bo'lsa — shu yerda (notify)."""
    o = await order(oid)
    if not o:
        return {"ok": False, "error": "not_found"}
    try:
        date.fromisoformat(d)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_date"}
    first = o["status"] != "issued"
    if first and o["measure"] != "xat" and not o["stages"]["basis"]["done"]:
        return {"ok": False, "error": "no_basis"}
    now = now_iso()
    number = (number or "").strip()[:40] or None
    await db.execute("UPDATE disc_orders SET number = ?, date = ?, status = 'issued', issued_at = COALESCE(issued_at, ?), "
                     "issued_by = COALESCE(issued_by, ?) WHERE id = ?", (number, d, now, user, oid))
    await db.execute("UPDATE disc_cases SET status = 'issued', updated_at = ? WHERE order_id = ?", (now, oid))
    if o["measure"] == "xat":  # xatning o'zi — chiquvchi raqam va sana
        await db.execute("UPDATE disc_cases SET letter_no = ?, letter_date = ?, letter_at = COALESCE(letter_at, ?) "
                         "WHERE order_id = ?", (number, d, now, oid))
    sent = 0
    if first and notify and bot is not None:
        sent = await notify_parents(bot, oid)
    auto = await send_originals(bot, oid, user=user) if first else None  # imzolangan asl nusxa oldin yuklangan bo'lsa
    return {"ok": True, "notified": sent, "auto": auto}


def done(o: dict) -> bool:
    """Jarayon tugagan (barcha bosqichlar) yoki bekor qilingan — «Hujjatlar» dan tozalash mumkin."""
    return o["status"] == "cancelled" or o["stages"]["current"] == 4


async def archive_order(oid: int, on: bool = True) -> dict:
    """Tozalash: yakunlangan chora «Hujjatlar» yorlig'idan olinadi («Chora ko'rilganlar»da hujjatlari bilan qoladi)."""
    o = await order(oid)
    if not o:
        return {"ok": False, "error": "not_found"}
    if on and not done(o):
        return {"ok": False, "error": "not_done"}
    await db.execute("UPDATE disc_orders SET archived_at = ? WHERE id = ?", (now_iso() if on else None, oid))
    return {"ok": True}


async def archive_done(scope: set[str] | None = ...) -> dict:
    """Barcha yakunlangan choralarni tozalash."""
    n = 0
    for o in await orders(scope=scope):
        if not o.get("archived_at") and done(o):
            await db.execute("UPDATE disc_orders SET archived_at = ? WHERE id = ?", (now_iso(), o["id"]))
            n += 1
    return {"ok": True, "archived": n}


async def set_basis(oid: int, kind: str | None, d: str | None = None, number: str = "") -> dict:
    """1-bosqich: kurs koordinatori bildirishnomasi dekanga topshirildi (sana, raqam) yoki bekor qilish (kind=None)."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    if kind not in ("bildirishnoma", None):
        return {"ok": False, "error": "bad_kind"}
    if kind:
        try:
            d = date.fromisoformat(d).isoformat() if d else today().isoformat()
        except ValueError:
            return {"ok": False, "error": "bad_date"}
    await db.execute("UPDATE disc_orders SET basis_kind = ?, basis_date = ?, basis_number = ? WHERE id = ?",
                     (kind, d if kind else None, (number or "").strip()[:40] or None if kind else None, oid))
    return {"ok": True}


async def set_case_basis(case_id: int, basis: str | None) -> dict:
    """1-bosqich (talaba bo'yicha): tushuntirish xati olindi yoki yozishdan bosh tortdi (dalolatnoma); None — bekor."""
    if basis not in ("tushuntirish", "dalolatnoma", None):
        return {"ok": False, "error": "bad_kind"}
    c = await db.fetchone("SELECT id FROM disc_cases WHERE id = ?", (case_id,))
    if not c:
        return {"ok": False, "error": "not_found"}
    await db.execute("UPDATE disc_cases SET basis = ?, basis_at = ? WHERE id = ?", (basis, now_iso() if basis else None, case_id))
    return {"ok": True}


async def mark_letters(bot, oid: int, items: list[dict], d: str, notify: bool = True, send_pdf: bool = False,
                       user: int | None = None) -> dict:
    """3-bosqich: ota-onaga xatlar yuborildi — har bir talabaning xati chiquvchi raqami va sanasi; ota-onalarga bot
    orqali xabar (va yuklangan imzolangan xat PDF nusxasi — send_pdf)."""
    o = await order(oid)
    if not o:
        return {"ok": False, "error": "not_found"}
    if o["measure"] == "xat":
        return {"ok": False, "error": "letter_order"}
    if o["status"] != "issued":
        return {"ok": False, "error": "not_issued"}
    try:
        d = date.fromisoformat(d).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_date"}
    cases = {c["id"]: c for c in o["cases"]}
    now, marked, fresh = now_iso(), [], set()
    for it in items:
        try:
            cid = int(it.get("case_id"))
        except (TypeError, ValueError):
            continue
        if cid not in cases:
            continue
        if not cases[cid].get("letter_date"):
            fresh.add(cid)
        await db.execute("UPDATE disc_cases SET letter_no = ?, letter_date = ?, letter_at = COALESCE(letter_at, ?) WHERE id = ?",
                         ((str(it.get("number") or "").strip()[:40]) or None, d, now, cid))
        marked.append(cid)
    if not marked:
        return {"ok": False, "error": "no_students"}
    notified = pdfs = 0
    if bot is not None and fresh:
        if notify:
            notified = await notify_parents(bot, oid, fresh)
        if send_pdf:
            for cid in fresh:
                f = await db.fetchone("SELECT id FROM disc_files WHERE case_id = ? AND kind = 'xat' AND sent_at IS NULL "
                                      "AND lower(name) LIKE '%.pdf' ORDER BY id DESC LIMIT 1", (cid,))
                if f and (await send_file(bot, f["id"], user)).get("ok"):
                    pdfs += 1
    return {"ok": True, "marked": len(marked), "notified": notified, "pdf": pdfs}


async def cancel_order(oid: int) -> dict:
    """Chiqarilgan chorani bekor qilish (xato kiritilgan bo'lsa) — talabalar yana ro'yxatga qaytadi."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    await db.execute("UPDATE disc_orders SET status = 'cancelled' WHERE id = ?", (oid,))
    await db.execute("UPDATE disc_cases SET status = 'cancelled', updated_at = ? WHERE order_id = ?", (now_iso(), oid))
    return {"ok": True}


async def notify_parents(bot, oid: int, case_ids: set[int] | None = None) -> int:
    from notifier import send_each
    from i18n import tr
    import loc
    o = await order(oid)
    if not o:
        return 0
    sent = 0
    doc = "Dekan farmoyishi" if o["measure"] == "ogohlantirish" else "Universitet buyrug'i" if o["measure"] == "hayfsan" else "Qaror"
    if o["measure"] == "xat":
        return await _notify_letter(bot, o)
    for c in o["cases"]:
        if case_ids is not None and c["id"] not in case_ids:
            continue
        pids = [r["parent_id"] for r in await db.fetchall("SELECT parent_id FROM parent_students WHERE student_id = ?",
                                                          (c["student_id"],))]
        if not pids:
            continue
        st = await db.get_student(c["student_id"])

        async def build(st=st, c=c) -> str:
            why = (tr("sababsiz {h} dars qoldirgani uchun", h=fmt_pairs(c["hours"] or 0)) if o["ground"] == "davomat"
                   else tr("ichki tartib qoidalarini buzgani uchun"))
            return (("⚠️ " if o["measure"] == "ogohlantirish" else "⛔ ") + "<b>" + tr(MEASURES[o["measure"]]["title"]) + "</b>\n\n"
                    + f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})\n"
                    + tr("{doc} bilan «{m}» e'lon qilindi — {why}.", doc=tr(doc), m=tr(MEASURES[o["measure"]]["short"]), why=why)
                    + (f"\n№ {esc(o['number'])}" if o.get("number") else "") + (f", {_dmy(o['date'])}" if o.get("date") else "")
                    + ("\n\n✉️ " + tr("Bu haqda sizga ogohlantirish xati yuborildi") + (f" (№ {esc(c['letter_no'])}" if c.get("letter_no") else " (")
                       + (", " if c.get("letter_no") else "") + _dmy(c["letter_date"]) + ")." if c.get("letter_date") else "")
                    + "\n\n" + tr("Farzandingiz bilan suhbatlashing. Savollar bo'lsa — kurs koordinatoriga yozing."))
        sent += await send_each(bot, pids, build, c["student_id"], "att", "threshold")
    return sent


async def _notify_letter(bot, o: dict) -> int:
    """Ota-onaga ogohlantirish xati yuborildi — bot orqali qisqa xabar (xatning o'zi pochta yoki PDF orqali)."""
    from notifier import send_each
    from i18n import tr
    import loc
    sent = 0
    for c in o["cases"]:
        pids = [r["parent_id"] for r in await db.fetchall("SELECT parent_id FROM parent_students WHERE student_id = ?",
                                                          (c["student_id"],))]
        if not pids:
            continue
        st = await db.get_student(c["student_id"])

        async def build(st=st, c=c) -> str:
            why = {"davomat": tr("uzrli sababsiz dars qoldirish"), "tartib": tr("ichki tartib qoidalarini buzish"),
                   "trimestr": tr("qayta o'qish (trimestr) shartnomasi bo'yicha to'lov qarzdorligi")}.get(o["ground"], "")
            lines = ["✉️ <b>" + tr("Ogohlantirish xati") + "</b>", "",
                     f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})",
                     tr("Fakultet dekanati sizga ogohlantirish xati yubordi: {why}.", why=why)]
            if o["ground"] == "trimestr" and c.get("amount"):
                lines.append(tr("Qarzdorlik: {s} so'm ({d} holatiga).", s=_money(c["amount"]), d=_dmy(c.get("as_of")))
                             + (" " + tr("To'lash muddati — {d}.", d=_dmy(o["deadline"])) if o.get("deadline") else ""))
            if o.get("number") or o.get("date"):
                lines.append((f"№ {esc(o['number'])}" if o.get("number") else "") + (", " if o.get("number") and o.get("date") else "")
                             + _dmy(o.get("date")))
            lines += ["", tr("Farzandingiz bilan suhbatlashing. Savollar bo'lsa — kurs koordinatoriga yozing.")]
            return "\n".join(lines)
        sent += await send_each(bot, pids, build, c["student_id"], "pay" if o["ground"] == "trimestr" else "att", "threshold")
    return sent


# ---------------------------------------------------------------- hujjat yaratish
async def _basis_text(o: dict, cases: list[dict], names: list[str]) -> str:
    """Farmoyish/buyruqdagi «Asos:» — 1-bosqich hujjatlari (hayfsanda — avvalgi dekan farmoyishi ham)."""
    parts = []
    if o["measure"] == "hayfsan":
        seen = []
        for items in (await _prior({c["student_id"] for c in cases})).values():
            for p in items:
                if p["measure"] == "ogohlantirish" and (p.get("number"), p.get("date")) not in seen:
                    seen.append((p.get("number"), p.get("date")))
        for num, d in seen:
            parts.append("dekanning " + (f"{_date_long(d)}dagi " if d else "") + (f"{num}-sonli " if num else "") + "farmoyishi")
    if o.get("basis_kind") == "bildirishnoma":
        parts.append(f"kurs koordinatori {names_ning(names)} " + (f"{_date_long(o['basis_date'])}dagi " if o.get("basis_date") else "")
                     + "bildirishnomasi")
    if any(c.get("basis") == "tushuntirish" for c in cases):
        parts.append("talabaning tushuntirish xati" if len(cases) == 1 else "talabalarning tushuntirish xatlari")
    if any(c.get("basis") == "dalolatnoma" for c in cases):
        parts.append("tushuntirish xati yozishdan bosh tortganlik to‘g‘risidagi dalolatnoma")
    if not any(p.startswith("kurs koordinatori") or p.startswith("talaba") for p in parts):
        parts.append(f"kurs koordinatori {names_ning(names)} bildirishnomasi")
    return ", ".join(parts)


def _money(x) -> str:
    """4617000 → «4 617 000» (bo'linmas bo'shliq bilan, hujjatdagidek)."""
    return f"{int(round(float(x or 0))):,}".replace(",", "\xa0")


def _upper_name(full: str | None) -> str:
    """Hujjatdagidek katta harflarda: «Aliyev Vali Karim o'g'li» → «ALIYEV VALI KARIM O‘G‘LI»."""
    s = re.sub(r"(?<=[OoGg])['`ʻʼ‘’]", "‘", " ".join((full or "").split()))
    return re.sub(r"['`ʼ]", "’", s).upper()


def _order_no(o: dict) -> str:
    """Hayfsan buyrug'i raqami «215-T» shaklida yoziladi (shablonda «-T-sonli» bor)."""
    n = (o.get("number") or "").strip()
    return re.sub(r"\s*-\s*T$", "", n, flags=re.I) if o["measure"] == "hayfsan" else n


def _chora_text(o: dict) -> str:
    """Xatdagi «ko'rilgan chora» jumlasi (bo'sh joy bilan boshlanadi; faqat xat bo'lsa — bo'sh)."""
    m = o["measure"]
    if m == "xat":
        return ""
    if m not in ("ogohlantirish", "hayfsan"):
        return " Shu munosabat bilan farzandingizga nisbatan intizomiy chora ko‘rildi." if o["status"] == "issued" else ""
    name = "“Ogohlantirish”" if m == "ogohlantirish" else "“Hayfsan”"
    if o["status"] == "issued":
        when = f"{_date_long(o['date'])}dagi " if o.get("date") else ""
        num = f"{_order_no(o)}{'-T' if m == 'hayfsan' and _order_no(o) else ''}-sonli " if o.get("number") else ""
        who = "dekanning" if m == "ogohlantirish" else "universitetning"
        doc = "farmoyishi" if m == "ogohlantirish" else "buyrug‘i"
        return f" Shu munosabat bilan farzandingizga {who} {when}{num}{doc} bilan {name} e’lon qilindi.".replace("  ", " ")
    doc = "dekan farmoyishi" if m == "ogohlantirish" else "universitet buyrug‘i"
    return f" Shu munosabat bilan farzandingizga {doc} bilan {name} e’lon qilinadi."


def _limit_text(h: float) -> str:
    """Xatdagi chegara jumlasi (davomat): qaysi chegaradan oshgani."""
    lv = absence.LEVELS
    warn, rep, out = (lv[i] if i < len(lv) else d for i, d in ((1, 36), (2, 54), (3, 74)))
    if h > out:
        return (f"Farzandingiz qoldirgan darslar hajmi hayfsan uchun belgilangan {_num(rep)} soatdan tashqari, talabalar safidan "
                f"chetlatish uchun belgilangan {_num(out)} soat chegarasidan ham oshib ketgan.")
    if h > rep:
        return f"Farzandingiz qoldirgan darslar hajmi hayfsan uchun belgilangan {_num(rep)} soat chegarasidan oshgan."
    if h > warn:
        return (f"Farzandingiz qoldirgan darslar hajmi dekan ogohlantirishi uchun belgilangan {_num(warn)} soat chegarasidan "
                "oshgan.")
    return f"Farzandingiz qoldirgan darslar hajmi dekan ogohlantirishi uchun belgilangan {_num(warn)} soat chegarasiga yaqinlashmoqda."


def _letter_date(o: dict, c: dict) -> str:
    d = o.get("date") if o["measure"] == "xat" else c.get("letter_date")
    if d:
        x = date.fromisoformat(d)
        return f"“{x.day:02d}” {MONTHS[x.month - 1]} {x.year}-y."
    return f"“____” ____________ {today().year}-y."


async def _letter(o: dict, c: dict, names: list[str], stage: str) -> bytes:
    """Bitta talabaning ota-onasiga ogohlantirish xati."""
    yr = academic_year_start().year
    h = float(c.get("hours") or 0)
    note = (c.get("note") or "").strip().rstrip(".")
    values = {
        "XAT_RAQAM": (o.get("number") if o["measure"] == "xat" else c.get("letter_no")) or "___________",
        "XAT_SANA": _letter_date(o, c), "FISH": c["full_name"] or "", "FISH_KATTA": _upper_name(c["full_name"]),
        "FISH_KATTA_NING": _upper_name(c["full_name"]) + "NING", "GURUH": c.get("group_name") or "",
        "BOSQICH": c.get("course") or stage or "___", "MANZIL": c.get("address") or "_" * 40,
        "OQUV_YILI": f"{yr}-{yr + 1}", "OTGAN_OQUV_YILI": f"{yr - 1}-{yr}",
        "SEMESTR": "1" if today().month >= 8 or today().month == 1 else "2",
        "HOLAT_SANA": _dmy(c.get("as_of") or o.get("period_to") or today()), "SOAT": _num(h), "PARA": _num(h / 2),
        "CHEGARA_MATNI": _limit_text(h), "CHORA_MATNI": _chora_text(o), "QOIDA": o.get("rule") or "______________",
        "IZOH": note, "IZOH_MATNI": f" Holat: {note}." if note else "", "QARZ": _money(c.get("amount")),
        "MUDDAT": _dmy(o.get("deadline")) or "__________", "TEL": (await db.get_setting("disc:phone") or "").strip()
        or "_______________", "IJROCHI": ", ".join(names) or "______________",
    }
    path = template_path(template_for("xat", o["ground"], o["measure"]))
    return docxfill.fill(path.read_bytes(), values)


def _letter_name(o: dict, c: dict) -> str:
    tag = {"davomat": "nb", "tartib": "tartib", "trimestr": "trimestr"}.get(o["ground"], "xat")
    words = [re.sub(r"[^\w\-]+", "", w) for w in (c["full_name"] or "").split()[:2]]
    return f"xat_{tag}_{'_'.join(w for w in words if w) or c['student_id']}.docx"


async def build_doc(oid: int, kind: str, case_id: int | None = None) -> tuple[str, bytes] | None:
    """Hujjat: jadvalli (bildirishnoma, farmoyish/buyruq, dalolatnoma) — bitta fayl; ota-onaga xat — har bir talabaga
    alohida (case_id berilsa — o'sha talabaniki, bir nechta talaba bo'lsa — ZIP)."""
    o = await order(oid)
    if not o or kind not in doc_kinds(o["ground"], o["measure"]):
        return None
    tpl = template_for(kind, o["ground"], o["measure"])
    path = template_path(tpl)
    cases = o["cases"]
    groups = {c["group_key"] for c in cases if c.get("group_key")}
    names = await coordinator_names(groups)
    faculty = (await db.get_setting("disc:faculty") or "").strip()
    stages = sorted({int(c["course"]) for c in cases if c.get("course")})
    if not stages:
        m = re.match(r"(\d+)", course_title() or "")
        stages = [int(m.group(1))] if m else []
    d_issue = o.get("date")
    if kind == "xat":
        pick = [c for c in cases if case_id is None or c["id"] == case_id]
        if not pick:
            return None
        stage = ", ".join(map(str, stages))
        if len(pick) == 1:
            return _letter_name(o, pick[0]), await _letter(o, pick[0], names, stage)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for c in pick:
                z.writestr(_letter_name(o, c), await _letter(o, c, names, stage))
        return f"Ota-onaga_xatlar_{MEASURES[o['measure']]['short'].replace(' ', '_')}_{_dmy(d_issue or today())}.zip", buf.getvalue()
    prior = await _prior({c["student_id"] for c in cases})
    yr = academic_year_start()
    sem = "1" if today().month >= 8 or today().month == 1 else "2"
    asos = await _basis_text(o, cases, names)
    if kind == "dalolatnoma" and any(c.get("basis") == "dalolatnoma" for c in cases):
        cases = [c for c in cases if c.get("basis") == "dalolatnoma"]  # faqat tushuntirish xati yozmaganlar
    values = {
        "ASOS": asos, "ASOS_BOSH": asos[:1].upper() + asos[1:],
        "RAQAM": _order_no(o) or "______", "SANA": _date_quoted(d_issue), "SANA_UZUN": _date_long(d_issue),
        "SANA_QISQA": _dmy(d_issue or today()), "BOSQICH": ", ".join(map(str, stages)) or "___",
        "DAN": _dmy(o.get("period_from") or semester_start()), "GACHA": _dmy(o.get("period_to") or today()),
        "SOAT": _num(o.get("hours") or threshold(o["measure"])), "KOORDINATORLAR": ", ".join(names) or "______________",
        "KOORDINATORLAR_NING": names_ning(names), "OQUV_YILI": f"{yr.year}/{yr.year + 1}", "SEMESTR": sem,
        "SONI": len(cases), "QOIDA": o.get("rule") or "______________",
        "CHORA": {"ogohlantirish": "dekan farmoyishi bilan “Ogohlantirish” e’lon qilish",
                  "hayfsan": "universitet buyrug‘i bilan “Hayfsan” e’lon qilish"}.get(o["measure"], "tegishli intizomiy chora"),
    }
    rows = []
    for c in cases:
        fac = faculty or c.get("faculty") or "Xalqaro munosabatlar"
        prev = [p for p in prior.get(c["student_id"], []) if not (p["measure"] == o["measure"] and p.get("number") == o.get("number"))]
        rows.append({"FISH": _upper_name(c["full_name"]), "BOSQICH": c.get("course") or (stages[0] if stages else ""),
                     "FAKULTET": fac, "FAKULTET_QISQA": _faculty_short(fac), "GURUH": c.get("group_name") or "",
                     "SOAT": _num(c.get("hours")), "PARA": _num((c.get("hours") or 0) / 2), "AVVAL": prior_text(prev),
                     "IZOH": c.get("note") or ""})
    data = docxfill.fill(path.read_bytes(), values, rows)
    label = {"bildirishnoma": "Bildirishnoma", "farmoyish": "Dekan_farmoyishi", "buyruq": "Buyruq_hayfsan",
             "dalolatnoma": "Dalolatnoma"}[kind]
    return f"{label}_{MEASURES[o['measure']]['short'].replace(' ', '_')}_{_dmy(d_issue or today())}.docx", data


async def build_zip(oid: int) -> tuple[str, bytes] | None:
    o = await order(oid)
    if not o:
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k in doc_kinds(o["ground"], o["measure"]):
            if k == "xat":
                for c in o["cases"]:
                    res = await build_doc(oid, k, c["id"])
                    if res:
                        z.writestr(f"ota-onaga_xatlar/{res[0]}", res[1])
                continue
            res = await build_doc(oid, k)
            if res:
                z.writestr(res[0], res[1])
        names = {c["id"]: c["full_name"] for c in o["cases"]}
        for f in o["files"]:
            row = await db.fetchone("SELECT path FROM disc_files WHERE id = ?", (f["id"],))
            p = _course_dir().parent / row["path"] if row else None
            if p and p.exists():
                who = f"{_safe_name(names.get(f['case_id'], ''))}_" if f.get("case_id") else ""
                z.writestr(f"ilovalar/{who}{f['id']}_{f['name']}", p.read_bytes())
    return f"Chora_{MEASURES[o['measure']]['short'].replace(' ', '_')}_{o['id']}.zip", buf.getvalue()


# ---------------------------------------------------------------- fayllar (imzolangan nusxa, tushuntirish xati, asos)
def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\-() ]+", "_", (name or "fayl").strip())[:120]
    return name or "fayl"


def _unlink(rel: str) -> None:
    try:
        (_course_dir().parent / rel).unlink()
    except OSError:
        pass


def _clean_no(v) -> str | None:
    return re.sub(r"^\s*№\s*", "", str(v or "")).strip()[:40] or None


def _clean_date(v) -> str | None:
    try:
        return date.fromisoformat(str(v)).isoformat() if v else None
    except ValueError:
        return None


async def add_file(oid: int | None, case_id: int | None, kind: str, name: str, data: bytes, user: int | None = None,
                   number: str | None = None, doc_date: str | None = None) -> dict:
    """number/doc_date — asl nusxaning o'z raqami va sanasi (masalan, dalolatnoma); bo'lmasa arxivda choradan olinadi."""
    if kind not in DOC_KINDS:
        kind = "boshqa"
    if not data:
        return {"ok": False, "error": "empty"}
    if len(data) > MAX_FILE:
        return {"ok": False, "error": "too_big"}
    if oid is not None and not await db.fetchone("SELECT 1 FROM disc_orders WHERE id = ?", (oid,)):
        return {"ok": False, "error": "not_found"}
    if case_id is not None and not await db.fetchone("SELECT 1 FROM disc_cases WHERE id = ?", (case_id,)):
        return {"ok": False, "error": "not_found"}
    d = _course_dir() / (str(oid) if oid else f"case{case_id}")
    d.mkdir(parents=True, exist_ok=True)
    fname = f"{secrets.token_hex(4)}_{_safe_name(name)}"
    (d / fname).write_bytes(data)
    rel = str((d / fname).relative_to(_course_dir().parent))
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    fid = await db.execute("INSERT INTO disc_files (order_id, case_id, kind, name, path, size, mime, uploaded_at, by_user, "
                           "doc_number, doc_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (oid, case_id, kind, _safe_name(name), rel, len(data), mime, now_iso(), user, _clean_no(number),
                            _clean_date(doc_date)))
    if case_id and kind in ("tushuntirish", "dalolatnoma"):  # 1-bosqich: talabaning asosi
        await db.execute("UPDATE disc_cases SET basis = COALESCE(basis, ?), basis_at = COALESCE(basis_at, ?) WHERE id = ?",
                         (kind, now_iso(), case_id))
    return {"ok": True, "id": fid}


async def set_file_meta(fids: list[int], number: str | None, doc_date: str | None) -> dict:
    """Arxiv: asl nusxa(lar)ning raqami va sanasi (bo'sh — choradan olinadi)."""
    if doc_date and not _clean_date(doc_date):
        return {"ok": False, "error": "bad_date"}
    for fid in fids:
        await db.execute("UPDATE disc_files SET doc_number = ?, doc_date = ? WHERE id = ?", (_clean_no(number), _clean_date(doc_date), fid))
    return {"ok": True}


# ---------------------------------------------------------------- asl nusxalar arxivi (raqam va F.I.Sh. bo'yicha qidiruv)
ARCHIVE_TYPES = {"farmoyish": "Dekan farmoyishi (ogohlantirish)", "buyruq": "Buyruq (hayfsan)", "bildirishnoma": "Bildirishnoma",
                 "dalolatnoma": "Dalolatnoma", "xat": "Ota-onaga xat", "tushuntirish": "Tushuntirish xati",
                 "qaror": "Qaror (boshqa chora)", "asos": "Asoslovchi hujjat", "boshqa": "Boshqa hujjat"}


def _arch_type(kind: str, o: dict | None) -> str:
    if kind in ("imzolangan", "farmoyish", "buyruq"):
        m = (o or {}).get("measure")
        return "buyruq" if m == "hayfsan" else "farmoyish" if m == "ogohlantirish" else "xat" if m == "xat" else \
            kind if kind in ("farmoyish", "buyruq") else "qaror"
    return kind if kind in ARCHIVE_TYPES else "boshqa"


def _no_key(v: str | None) -> str:
    """Raqamni solishtirish uchun: «№ 215-T» → «215t», «01-12/101» → «0112101»."""
    return re.sub(r"[^0-9a-zа-я]", "", (v or "").lower().replace("№", ""))


async def doc_archive(q: str = "", kind: str = "", scope: set[str] | None = ...) -> dict:
    """Yuklangan asl nusxalar — hujjat bo'yicha (bitta farmoyish/buyruq/bildirishnoma bir necha talabaga): turi, raqami,
    sanasi, talabalar, fayllar. q — raqam (17, 215-T, 01-12/101) yoki talaba F.I.Sh.; kind — hujjat turi.
    «missing» — raqami bor, lekin asl nusxasi yuklanmagan farmoyish/buyruq va bildirishnomalar."""
    from utils import normalize_text
    if scope is ...:
        from tenancy import viewer_scope
        scope = viewer_scope()
    orders_ = {o["id"]: o for o in [dict(r) for r in await db.fetchall("SELECT * FROM disc_orders")]}
    cases = {c["id"]: dict(c) for c in await db.fetchall(
        """SELECT c.*, s.full_name, s.group_name, s.group_key FROM disc_cases c JOIN students s ON s.id = c.student_id""")}
    by_order: dict[int, list[dict]] = {}
    for c in cases.values():
        if c["order_id"]:
            by_order.setdefault(c["order_id"], []).append(c)
    entries: dict[tuple, dict] = {}
    files = await db.fetchall("SELECT id, order_id, case_id, kind, name, size, uploaded_at, sent_at, send_note, doc_number, doc_date "
                              "FROM disc_files ORDER BY id")
    for f in files:
        c = cases.get(f["case_id"]) if f["case_id"] else None
        oid = f["order_id"] or (c or {}).get("order_id")
        o = orders_.get(oid)
        t = _arch_type(f["kind"], o)
        if c:
            studs = [c]
        elif t == "dalolatnoma":
            oc = by_order.get(oid, [])
            studs = [x for x in oc if x.get("basis") == "dalolatnoma"] or oc
        else:
            studs = by_order.get(oid, [])
        if t in ("farmoyish", "buyruq", "qaror"):
            no, d = o and o.get("number"), o and o.get("date")
        elif t == "bildirishnoma":
            no, d = o and o.get("basis_number"), o and o.get("basis_date")
        elif t == "xat":  # xatning o'z chiquvchi raqami; farmoyish raqami emas (faqat-xat choralarida — choraniki)
            own = (o or {}).get("measure") == "xat"
            no = (c or {}).get("letter_no") or ((o or {}).get("number") if own else None)
            d = (c or {}).get("letter_date") or ((o or {}).get("date") if own else None)
        else:
            no, d = None, None
        no, d = f["doc_number"] or no, f["doc_date"] or d or (f["uploaded_at"] or "")[:10]
        key = (t, oid, c["id"] if c else None, _no_key(no))
        e = entries.setdefault(key, {"type": t, "title": ARCHIVE_TYPES[t], "number": no, "date": d, "order_id": oid,
                                     "measure": (o or {}).get("measure"), "ground": (o or {}).get("ground"),
                                     "rule": (o or {}).get("rule"), "students": [], "files": []})
        e["files"].append({k: f[k] for k in ("id", "kind", "name", "size", "uploaded_at", "sent_at", "send_note")})
        for x in studs:
            if all(y["id"] != x["student_id"] for y in e["students"]):
                e["students"].append({"id": x["student_id"], "name": x["full_name"], "group": x["group_name"] or "",
                                      "group_key": x["group_key"]})
    # raqami bor, lekin asl nusxasi yo'q (o'quv yilida)
    missing = []
    have = {(e["type"], e["order_id"]) for e in entries.values()}
    for o in orders_.values():
        if o["created_at"] < ay_start() or o["status"] == "cancelled":
            continue
        studs = [{"id": c["student_id"], "name": c["full_name"], "group": c["group_name"] or "", "group_key": c["group_key"]}
                 for c in by_order.get(o["id"], [])]
        t = _arch_type("imzolangan", o)
        if o["status"] == "issued" and t != "xat" and (t, o["id"]) not in have:
            missing.append({"type": t, "title": ARCHIVE_TYPES[t], "number": o.get("number"), "date": o.get("date"),
                            "order_id": o["id"], "measure": o["measure"], "ground": o["ground"], "students": studs, "upload": "imzolangan"})
        if o.get("basis_kind") == "bildirishnoma" and ("bildirishnoma", o["id"]) not in have:
            missing.append({"type": "bildirishnoma", "title": ARCHIVE_TYPES["bildirishnoma"], "number": o.get("basis_number"),
                            "date": o.get("basis_date"), "order_id": o["id"], "measure": o["measure"], "ground": o["ground"],
                            "students": studs, "upload": "bildirishnoma"})
    items = list(entries.values())

    def visible(e):
        return scope is None or any(s["group_key"] in scope for s in e["students"])

    qn, qk = normalize_text(q or ""), _no_key(q)

    def rank(e):  # 0 — raqam aniq mos, 1 — raqam ichida, 2 — F.I.Sh./tur, None — mos emas
        if not q:
            return 2
        nk = _no_key(e.get("number"))
        if qk and nk and nk == qk:
            return 0
        if qk and nk and (qk in nk):
            return 1
        if qn and (any(qn in normalize_text(s["name"]) for s in e["students"]) or qn in normalize_text(e["title"])):
            return 2
        return None
    out = []
    for lst in (items, missing):
        sel = [e for e in lst if visible(e) and (not kind or e["type"] == kind) and rank(e) is not None]
        sel.sort(key=lambda e: (rank(e), -(int((e.get("date") or "0000-00-00").replace("-", "")))))
        for e in sel:
            e["exact"] = bool(q) and rank(e) == 0
            for s_ in e["students"]:
                s_.pop("group_key", None)
        out.append(sel)
    counts = {t: sum(1 for e in items if visible(e) and e["type"] == t) for t in ARCHIVE_TYPES}
    return {"items": out[0], "missing": out[1], "counts": {k: v for k, v in counts.items() if v}, "types": ARCHIVE_TYPES}


async def get_file(fid: int) -> tuple[dict, bytes] | None:
    f = await db.fetchone("SELECT * FROM disc_files WHERE id = ?", (fid,))
    if not f:
        return None
    p = _course_dir().parent / f["path"]
    return (dict(f), p.read_bytes()) if p.exists() else None


async def delete_file(fid: int) -> dict:
    f = await db.fetchone("SELECT * FROM disc_files WHERE id = ?", (fid,))
    if not f:
        return {"ok": False, "error": "not_found"}
    _unlink(f["path"])
    await db.execute("DELETE FROM disc_files WHERE id = ?", (fid,))
    return {"ok": True}


# ---------------------------------------------------------------- chora ko'rilganlar: tarix va dinamika
async def _files_index() -> dict[int, list[dict]]:
    """Fayllar: kalit — hujjat (order_id) yoki talaba ishi (−case_id)."""
    out: dict[int, list] = {}
    for f in await db.fetchall("SELECT id, order_id, case_id, kind, name, size, mime, uploaded_at, sent_at, send_note FROM disc_files "
                               "ORDER BY id"):
        out.setdefault(f["order_id"] or -f["case_id"], []).append({**dict(f), "shared": bool(f["order_id"])})
    return out


def _why(r: dict) -> str:
    if r["ground"] == "davomat":
        return f"sababsiz {fmt_pairs(r.get('hours') or 0)}"
    if r["ground"] == "trimestr":
        return f"{_money(r.get('amount'))} so‘m"
    return r.get("rule") or ""


async def history(scope: set[str] | None = ..., measure: str = "", ground: str = "", letters: str = "") -> dict:
    """O'quv yili boshidan rasman ko'rilgan choralar: ro'yxat (hujjatlari bilan), ko'rsatkichlar, oylar bo'yicha dinamika.
    letters: «1» — ota-onaga xat yuborilganlar (chora turidan qat'i nazar), «0» — xati hali yuborilmaganlar."""
    if scope is ...:
        from tenancy import viewer_scope
        scope = viewer_scope()
    rows = await db.fetchall(
        """SELECT c.id AS case_id, c.student_id, c.measure, c.ground, c.hours, c.note, c.amount, c.as_of, c.basis, c.letter_no,
                  c.letter_date, o.id AS order_id, o.number, o.date, o.rule, o.issued_at, o.deadline, o.basis_kind, o.basis_date,
                  s.full_name, s.group_name, s.group_key, s.hemis_id, s.course
           FROM disc_cases c JOIN disc_orders o ON o.id = c.order_id JOIN students s ON s.id = c.student_id
           WHERE c.status = 'issued' AND COALESCE(o.date, substr(o.issued_at, 1, 10)) >= ?
           ORDER BY COALESCE(o.date, o.issued_at) DESC, s.full_name""", (ay_start(),))
    rows = [dict(r) for r in rows if scope is None or r["group_key"] in scope]
    files = await _files_index()
    for r in rows:
        own = files.get(-r["case_id"], [])
        r["files"] = files.get(r["order_id"], []) + own
        r["own_files"] = len(own)
        r["has_original"] = bool(r["files"])
        r["title"] = MEASURES.get(r["measure"], {}).get("title", r["measure"])
        r["ground_title"] = GROUNDS.get(r["ground"], r["ground"])
        r["why"] = _why(r)
    all_rows = rows
    if measure:
        rows = [r for r in rows if r["measure"] == measure]
    if ground:
        rows = [r for r in rows if r["ground"] == ground]
    if letters in ("0", "1"):
        rows = [r for r in rows if bool(r["letter_date"]) == (letters == "1")]
    # oylar bo'yicha dinamika (o'quv yili boshidan joriy oygacha)
    start, t = academic_year_start(), today()
    months, y, m = [], start.year, start.month
    while (y, m) <= (t.year, t.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    dyn = []
    cum = {k: 0 for k in MEASURES}
    for y, m in months:
        key = f"{y}-{m:02d}"
        cnt = {k: sum(1 for r in all_rows if (r["date"] or r["issued_at"] or "")[:7] == key and r["measure"] == k) for k in cum}
        by_ground = {g: sum(1 for r in all_rows if (r["date"] or r["issued_at"] or "")[:7] == key and r["ground"] == g)
                     for g in GROUNDS}
        for k in cum:
            cum[k] += cnt[k]
        dyn.append({"month": key, "label": MONTHS[m - 1], **cnt, **by_ground, "cumulative": dict(cum)})
    matrix = {m: {g: sum(1 for r in all_rows if r["measure"] == m and r["ground"] == g) for g in GROUNDS} for m in MEASURES}
    for x in dyn:  # har oy: chora turi × asos (davomat / ichki tartib / trimestr)
        key = x["month"]
        x["by"] = {m: {g: sum(1 for r in all_rows if (r["date"] or r["issued_at"] or "")[:7] == key and r["measure"] == m
                              and r["ground"] == g) for g in GROUNDS} for m in MEASURES}
    kpi = {k: sum(1 for r in all_rows if r["measure"] == k) for k in MEASURES}
    kpi.update({g: sum(1 for r in all_rows if r["ground"] == g) for g in GROUNDS})
    kpi.update({"students": len({r["student_id"] for r in all_rows}),
                "repeat": sum(1 for v in _count_by(all_rows).values() if v > 1),
                "no_original": sum(1 for r in all_rows if not r["has_original"]), "total": len(all_rows),
                "letters": _letters_kpi(all_rows)})
    by_group: dict[str, int] = {}
    for r in all_rows:
        by_group[r["group_name"] or "—"] = by_group.get(r["group_name"] or "—", 0) + 1
    return {"items": rows, "kpi": kpi, "dynamics": dyn, "matrix": matrix, "by_group": sorted(by_group.items(), key=lambda x: -x[1]),
            "since": ay_start()}


def _letters_kpi(rows: list[dict]) -> dict:
    """Ota-onaga yuborilgan xatlar: jami, asosi (davomat / ichki tartib / trimestr), qaysi chora bo'yicha, botda yetkazilgani
    (imzolangan xat ota-onaga yuborilgan) va hali yuborilmaganlar (farmoyish/buyruq chiqqan, xat yo'q)."""
    sent = [r for r in rows if r["letter_date"]]
    out = {"sent": len(sent), "pending": sum(1 for r in rows if not r["letter_date"]),
           "students": len({r["student_id"] for r in sent}), "last": max((r["letter_date"] for r in sent), default=None),
           "in_bot": sum(1 for r in sent if any(f["sent_at"] and (f["kind"] == "xat" or r["measure"] == "xat") for f in r["files"]))}
    out.update({g: sum(1 for r in sent if r["ground"] == g) for g in GROUNDS})
    out["by_measure"] = {m: sum(1 for r in sent if r["measure"] == m) for m in MEASURES}
    return out


def _count_by(rows: list[dict]) -> dict[int, int]:
    out: dict[int, int] = {}
    for r in rows:
        out[r["student_id"]] = out.get(r["student_id"], 0) + 1
    return out


async def student_measures(sid: int) -> list[dict]:
    """Talabaga o'quv yilida rasman ko'rilgan choralar (talaba kartasi va ota-ona sahifasi uchun)."""
    rows = await db.fetchall(
        """SELECT c.id AS case_id, c.order_id, c.measure, c.ground, c.hours, c.note, c.amount, o.number, o.date, o.rule
           FROM disc_cases c JOIN disc_orders o ON o.id = c.order_id WHERE c.student_id = ? AND c.status = 'issued'
           AND c.created_at >= ? ORDER BY o.date""", (sid, ay_start()))
    files = await _files_index()
    return [{**dict(r), "title": MEASURES.get(r["measure"], {}).get("title", r["measure"]),
             "files": len(files.get(r["order_id"], [])) + len(files.get(-r["case_id"], []))} for r in rows]


async def bulk_measures() -> dict[int, list[dict]]:
    """Har bir talabaga o'quv yilida rasman ko'rilgan choralar («Talabalar» jadvalidagi «Chora» ustuni)."""
    out: dict[int, list[dict]] = {}
    for r in await db.fetchall(
            """SELECT c.student_id, c.measure, c.ground, c.letter_date, o.number, o.date FROM disc_cases c
               JOIN disc_orders o ON o.id = c.order_id WHERE c.status = 'issued' AND c.created_at >= ?
               ORDER BY COALESCE(o.date, c.created_at)""", (ay_start(),)):
        out.setdefault(r["student_id"], []).append({"measure": r["measure"], "ground": r["ground"], "number": r["number"],
                                                    "date": r["date"], "letter": bool(r["letter_date"]),
                                                    "title": MEASURES.get(r["measure"], {}).get("title", r["measure"])})
    return out


CASE_STATES = {"asked": "Sababi so‘ralgan", "excused": "Sababli deb topilgan", "removed": "Ro‘yxatdan o‘chirilgan",
               "draft": "Hujjat tayyorlanmoqda", "issued": "Chiqarilgan", "cancelled": "Bekor qilingan"}


async def student_record(sid: int) -> dict | None:
    """Talabaning o'quv yilidagi barcha choralari — asl hujjatlari (yuklangan PDF/skan) va shablondan hujjatlar bilan."""
    st = await db.get_student(sid)
    if not st:
        return None
    rows = await db.fetchall(
        """SELECT c.*, o.number, o.date, o.status AS order_status, o.rule, o.deadline, o.measure AS o_measure, o.basis_kind,
                  o.basis_date FROM disc_cases c LEFT JOIN disc_orders o ON o.id = c.order_id
           WHERE c.student_id = ? AND c.created_at >= ? ORDER BY COALESCE(o.date, c.created_at) DESC, c.id DESC""",
        (sid, ay_start()))
    files = await _files_index()
    cases, stages = [], {}
    for r in rows:
        r = dict(r)
        if r["order_id"] and r["order_id"] not in stages:
            stages[r["order_id"]] = ((await order(r["order_id"])) or {}).get("stages")
        r["stages"] = stages.get(r["order_id"])
        r["title"] = MEASURES.get(r["measure"], {}).get("title", r["measure"])
        r["ground_title"] = GROUNDS.get(r["ground"], r["ground"])
        r["state_title"] = CASE_STATES.get(r["status"], r["status"])
        r["why"] = _why(r)
        r["files"] = files.get(-r["id"], []) + (files.get(r["order_id"], []) if r["order_id"] else [])
        r["docs"] = ([{"kind": k, "title": DOC_KINDS[k] + (" (shu talaba)" if k == "xat" else "")}
                      for k in doc_kinds(r["ground"], r["measure"])] if r["order_id"] else [])
        cases.append(r)
    sm = (await summaries([st])).get(sid)
    return {"student": {"id": sid, "name": st["full_name"], "group": st.get("group_name") or "", "hemis_id": st.get("hemis_id"),
                        "course": st.get("course"), "address": st.get("address") or "",
                        "hours": float(sm["counted"] or 0) if sm else None},
            "cases": cases, "parents": (await db.fetchone("SELECT COUNT(*) n FROM parent_students WHERE student_id = ?",
                                                          (sid,)))["n"]}


ORIGINAL_ORDER = ("imzolangan", "farmoyish", "buyruq")  # butun farmoyish/buyruqning imzolangan asl nusxasi
ORIGINAL_CASE = ("xat", "imzolangan")                    # talabaning o'z hujjati: imzolangan xat, ko'chirma


def _doc_type(measure: str, kind: str) -> str:
    """Ota-ona «📄 Hujjatlar» bo'limidagi tur."""
    if kind == "xat" or measure == "xat":
        return "xat"
    return measure if measure in ("ogohlantirish", "hayfsan") else "tushuntirish" if kind == "tushuntirish" else "boshqa"


async def _deliver_pdf(bot, data: bytes, name: str, sids: list[int], dtype: str, d: str | None, comment: str | None,
                       user: int | None) -> dict:
    """PDF ni talabalarning ota-onalariga: har bir ota-ona faqat o'z farzandini ko'radi — boshqa talabalarning F.I.Sh.,
    guruhi va shu qatordagi ma'lumotlari qora rang bilan yopiladi («Hujjat yuborish» bilan bir xil). Yopib bo'lmasa
    (skan o'qilmadi va hujjatda bir necha talaba bor, talaba hujjatda topilmadi, ismdosh bor) — yuborilmaydi."""
    import asyncio
    import uuid
    import docstore
    import redact
    from staffops import deliver_document
    an = await asyncio.to_thread(redact.analyze, data, await db.all_students_brief())
    batch, out = uuid.uuid4().hex[:12], {"students": 0, "parents": 0, "skipped": [], "doc_id": None}
    for sid in sids:
        st = await db.get_student(sid)
        if not st:
            continue
        if an.readable:
            r = await asyncio.to_thread(redact.redact_for, data, an, sid, st.get("hemis_id") or "")
            if not r.target_found:
                out["skipped"].append({"name": st["full_name"], "reason": "hujjatda talaba topilmadi"})
                continue
            if r.ambiguous:
                out["skipped"].append({"name": st["full_name"], "reason": "ismdosh bor — «Hujjat yuborish» orqali tekshirib yuboring"})
                continue
            pdf, boxes = r.pdf, r.boxes
        elif len(sids) > 1:
            out["skipped"].append({"name": st["full_name"], "reason": an.error or "skan o'qilmadi — boshqa talabalarni yopib "
                                   "bo'lmaydi; «Hujjat yuborish» orqali yuboring"})
            continue
        else:
            pdf, boxes = data, 0  # bitta talabaning hujjati
        file_id = docstore.save_local(current_course() or "_", pdf)
        did = await db.add_document(sid, dtype, file_id, None, name, len(pdf), d or today().isoformat(), comment, user or 0,
                                    batch=batch, redacted=boxes)
        sent, total = await deliver_document(bot, did, st) if bot is not None else (0, 0)
        out["students"] += 1
        out["parents"] += sent
        out["doc_id"] = did
        if not total:
            out["skipped"].append({"name": st["full_name"], "reason": "ota-onasi botga ulanmagan (hujjat saqlandi)"})
    return out


def _note(res: dict, total: int) -> str:
    parts = [f"ota-onaga yuborildi: {res['students']} / {total} talaba ({res['parents']} ota-ona)"]
    parts += [f"{x['name']} — {x['reason']}" for x in res["skipped"][:10]]
    return "; ".join(parts)[:900]


async def send_originals(bot, oid: int, fids: list[int] | None = None, user: int | None = None) -> dict:
    """Chora rasman ko'rilgan (farmoyish/buyruq chiqarilgan, xat yuborilgan) bo'lsa — yuklangan asl nusxa (PDF) ota-onalarga
    avtomatik: butun hujjatniki — har bir talabaga (boshqalari yopilgan), talabaniki — o'sha talabaga. Har bir fayl bir marta."""
    o = await order(oid)
    out = {"files": 0, "students": 0, "parents": 0, "skipped": []}
    if not o or o["status"] != "issued" or bot is None:
        return out
    rows = await db.fetchall("SELECT * FROM disc_files WHERE (order_id = ? OR case_id IN (SELECT id FROM disc_cases WHERE "
                             "order_id = ?)) AND sent_at IS NULL ORDER BY id", (oid, oid))
    cases = {c["id"]: c for c in o["cases"]}
    for f in rows:
        if fids is not None and f["id"] not in fids:
            continue
        if not (f["name"] or "").lower().endswith(".pdf"):
            continue
        if f["case_id"]:
            if f["kind"] not in ORIGINAL_CASE or f["case_id"] not in cases:
                continue
            sids, c = [cases[f["case_id"]]["student_id"]], cases[f["case_id"]]
            kind_no = (c.get("letter_no") if f["kind"] == "xat" else None) or o.get("number")
            d = (c.get("letter_date") if f["kind"] == "xat" else None) or o.get("date")
        else:
            if f["kind"] not in ORIGINAL_ORDER:
                continue
            sids, kind_no, d = [c["student_id"] for c in o["cases"]], o.get("number"), o.get("date")
        got = await get_file(f["id"])
        if not got:
            continue
        doc = "Ogohlantirish xati" if f["kind"] == "xat" or o["measure"] == "xat" else (
            "Dekan farmoyishi" if o["measure"] == "ogohlantirish" else "Universitet buyrug'i" if o["measure"] == "hayfsan" else "Qaror")
        comment = doc + (f" № {kind_no}" if kind_no else "") + (f", {_dmy(d)}" if d else "")
        res = await _deliver_pdf(bot, got[1], f["name"], sids, _doc_type(o["measure"], f["kind"]), d, comment, user)
        await db.execute("UPDATE disc_files SET sent_doc_id = ?, sent_at = ?, send_note = ? WHERE id = ?",
                         (res["doc_id"], now_iso() if res["students"] else None, _note(res, len(sids)), f["id"]))
        out["files"] += 1
        out["students"] += res["students"]
        out["parents"] += res["parents"]
        out["skipped"] += res["skipped"]
    return out


async def send_file(bot, fid: int, user: int | None = None) -> dict:
    """Talabaga biriktirilgan PDF — qo'lda ota-onasiga (bot orqali, «📄 Hujjatlar» bo'limiga), boshqa talabalar yopilgan.
    Butun hujjatga biriktirilgan fayl bu yerdan yuborilmaydi — u chora chiqarilganda avtomatik yuboriladi."""
    f = await db.fetchone("SELECT * FROM disc_files WHERE id = ?", (fid,))
    if not f:
        return {"ok": False, "error": "not_found"}
    if not f["case_id"]:
        return {"ok": False, "error": "shared_file"}
    if not (f["name"] or "").lower().endswith(".pdf"):
        return {"ok": False, "error": "not_pdf"}
    c = await db.fetchone("SELECT * FROM disc_cases WHERE id = ?", (f["case_id"],))
    if not c or not await db.get_student(c["student_id"]):
        return {"ok": False, "error": "not_found"}
    got = await get_file(fid)
    if not got:
        return {"ok": False, "error": "not_found"}
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (c["order_id"],)) if c["order_id"] else None
    no = (c.get("letter_no") if f["kind"] == "xat" else None) or (o or {}).get("number")
    d = (c.get("letter_date") if f["kind"] == "xat" else None) or (o or {}).get("date")
    res = await _deliver_pdf(bot, got[1], f["name"], [c["student_id"]], _doc_type(c["measure"], f["kind"]), d,
                             (f"№ {no}" if no else None), user)
    if not res["students"]:
        return {"ok": False, "error": "not_sent", "skipped": res["skipped"]}
    await db.execute("UPDATE disc_files SET sent_doc_id = ?, sent_at = ?, send_note = ? WHERE id = ?",
                     (res["doc_id"], now_iso(), _note(res, 1), fid))
    return {"ok": True, "sent": res["parents"], "parents": res["parents"], "document_id": res["doc_id"], "skipped": res["skipped"]}


async def panel_stats(scope: set[str] | None = ...) -> dict:
    """«Kurs holati» uchun aniq sonlar: kutilayotgan choralar, holatlar, hujjatlar, o'quv yilidagi choralar."""
    if scope is ...:
        from tenancy import viewer_scope
        scope = viewer_scope()
    cand = await candidates(scope=scope)
    pending = {m: cand["counts"][m] for m in AUTO}
    states: dict[str, int] = {}
    for m in AUTO:
        for x in cand[m]:
            states[x["state"]] = states.get(x["state"], 0) + 1
    for x in cand["excluded"]:
        states[x["state"]] = states.get(x["state"], 0) + 1
    drafts = await orders("draft", scope)
    issued = [o for o in await orders("issued", scope) if o["measure"] != "xat"]
    mine = lambda o: [c for c in o["cases"] if scope is None or c["group_key"] in scope]  # noqa: E731
    flow = {"need": sum(pending.values()), "asked": states.get("asked", 0),
            "basis": sum(len(mine(o)) for o in drafts if o["measure"] != "xat" and o["stages"]["current"] == 1),
            "order": sum(len(mine(o)) for o in drafts if o["measure"] != "xat" and o["stages"]["current"] == 2),
            "letters": sum(1 for o in issued for c in mine(o) if not c.get("letter_date")),
            "done": sum(1 for o in issued for c in mine(o) if c.get("letter_date"))}
    h = await history(scope)
    tri = await trimestr_candidates(scope)
    return {"pending": pending, "new": sum(pending.values()), "states": states, "flow": flow,
            "drafts": len(drafts), "draft_students": sum(len(o["cases"]) for o in drafts),
            "thresholds": cand["thresholds"], "kpi": h["kpi"],
            "dynamics": [{k: x[k] for k in ("label", *MEASURES)} for x in h["dynamics"]],
            "trimestr": {"new": tri["count"], "total": len(tri["items"]),
                         "sent": sum(1 for x in tri["items"] if x["state"] == "sent")}}


# ---------------------------------------------------------------- signal: yangi chegaradan oshganlar
async def signal_new(bot, sids: set[int] | None = None) -> dict:
    """Davomat chegarasidan (36/54 soat) yangi oshgan talabalar — kurs koordinator(lar)iga darhol Telegram xabari
    (har bir talaba va chora uchun bir marta). Qaytaradi: {measure: [talabalar]}."""
    cand = await candidates(scope=None, sids=sids)
    fresh: dict[str, list[dict]] = {m: [] for m in AUTO}
    ay = ay_start()
    for m in AUTO:
        for x in cand[m]:
            if x["state"] not in ("new", "more"):
                continue
            mark = f"{ay}:{m}:{int(x['hours'])}" if x["state"] == "more" else f"{ay}:{m}"
            if await db.warning_sent(x["sid"], "disc_signal", mark):
                continue
            if bot is not None:  # botsiz chaqiruvda belgilanmaydi — signal keyingi safar yuboriladi
                await db.mark_warning(x["sid"], "disc_signal", mark)
            fresh[m].append(x)
    if not any(fresh.values()) or bot is None:
        return fresh
    from notifier import safe_send
    key = current_course()
    for uid in course_admins(key):
        groups = set(COORD_GROUPS.get(uid, {}))
        mine = {m: [x for x in xs if not groups or group_key(x["group"]) in groups] for m, xs in fresh.items()}
        if not any(mine.values()):
            continue
        lines = [f"🔔 <b>Chora ko'rish kerak</b> — {esc(course_title(key))}"]
        for m, xs in mine.items():
            if not xs:
                continue
            icon = "⚠️" if m == "ogohlantirish" else "⛔"
            lines.append(f"\n{icon} <b>{MEASURES[m]['title']}</b> — sababsiz {_num(threshold(m))} soatdan oshdi: {len(xs)} ta")
            for x in xs[:25]:
                lines.append(f"• {esc(x['name'])} ({esc(x['group'])}) — {fmt_pairs(x['hours'])}"
                             + (" — sababli deb chiqarilgandan keyin yana qoldirgan" if x["state"] == "more" else ""))
            if len(xs) > 25:
                lines.append(f"… va yana {len(xs) - 25} ta")
        lines.append("\nHujjatlar (bildirishnoma, farmoyish/buyruq) tayyor: Boshqaruv paneli → «Chora ko'rish». "
                     "Sababli qoldirgan bo'lsa — ro'yxatdan chiqaring yoki ota-onadan sababini so'rang.")
        try:
            await safe_send(bot, uid, "\n".join(lines))
        except Exception:  # noqa: BLE001
            log.exception("Chora signali yuborilmadi: %s", uid)
    return fresh


def signal_lines(fresh: dict) -> list[str]:
    """Import hisobotiga: yangi chora kerak bo'lganlar."""
    n = {m: len(xs) for m, xs in (fresh or {}).items() if xs}
    if not n:
        return []
    return ["\n🔔 <b>Chora ko'rish kerak</b> (koordinatorga signal yuborildi): "
            + ", ".join(f"{MEASURES[m]['title'].lower()} — {k} ta" for m, k in n.items())
            + ". Boshqaruv paneli → «Chora ko'rish»."]


# ---------------------------------------------------------------- shablonlar
def templates_list() -> list[dict]:
    out = []
    for name, title in TEMPLATE_TITLES.items():
        custom = (CUSTOM_DIR / name).exists()
        out.append({"name": name, "title": title, "custom": custom,
                    "placeholders": sorted(docxfill.placeholders(template_path(name).read_bytes()))})
    return out


def save_template(name: str, data: bytes) -> dict:
    if name not in TEMPLATE_TITLES:
        return {"ok": False, "error": "not_found"}
    try:
        found = docxfill.placeholders(data)
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        return {"ok": False, "error": "not_docx"}
    if name in LETTERS:  # xat — bitta talabaga: ismi bo'lishi shart
        if not found & {"FISH", "FISH_KATTA", "FISH_KATTA_NING"}:
            return {"ok": False, "error": "no_name", "found": sorted(found)}
    elif "T_FISH" not in found:
        return {"ok": False, "error": "no_table", "found": sorted(found)}
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    (CUSTOM_DIR / name).write_bytes(data)
    return {"ok": True, "placeholders": sorted(found)}


def reset_template(name: str) -> dict:
    try:
        (CUSTOM_DIR / name).unlink()
    except OSError:
        pass
    return {"ok": True}

