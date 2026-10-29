"""Chora ko'rish: davomat chegarasidan oshganlar va ichki tartib qoidalarini buzganlarga intizomiy choralar.

Akademik nizom (6-bob, 113-modda): sababsiz qoldirilgan darslar 36 soatdan oshsa — dekan farmoyishi bilan
«Ogohlantirish», 54 soatdan oshsa — universitet buyrug'i bilan «Hayfsan» (chegaralar — ABSENCE_WARN_LEVELS).

Jarayon: bot chegaradan oshganlarni o'zi topadi (kurs koordinatoriga darhol signal) → koordinator sababini aniqlaydi
(ota-onadan so'raydi, sababli bo'lsa ro'yxatdan chiqaradi) → tanlanganlar uchun hujjatlar avtomatik tayyorlanadi
(bildirishnoma, farmoyish/buyruq, dalolatnoma — shablonlar/chora/*.docx) → imzolangach raqam va sana kiritilib
«chiqarildi» deb belgilanadi, imzolangan nusxa va asoslovchi hujjatlar biriktiriladi → «Chora ko'rilganlar»
(o'quv yili boshidan, hujjatlari va dinamikasi bilan). Ichki tartib qoidalarini buzish bo'yicha choralar qo'lda qo'shiladi.
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
}
AUTO = ("ogohlantirish", "hayfsan")  # davomat bo'yicha avtomatik aniqlanadiganlar
GROUNDS = {"davomat": "Davomat (sababsiz dars qoldirish)", "tartib": "Ichki tartib qoidalarini buzish"}
DOC_KINDS = {"bildirishnoma": "Bildirishnoma", "farmoyish": "Dekan farmoyishi", "buyruq": "Buyruq (hayfsan)",
             "dalolatnoma": "Dalolatnoma", "tushuntirish": "Tushuntirish xati", "asos": "Asoslovchi hujjat",
             "imzolangan": "Imzolangan nusxa", "boshqa": "Boshqa hujjat"}
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
}
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
    out = ["bildirishnoma"]
    doc = (MEASURES.get(measure) or {}).get("doc")
    if doc and template_for(doc, ground, measure):
        out.append(doc)
    out.append("dalolatnoma")
    return out


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
    for m in AUTO:
        out[m].sort(key=lambda x: (x["state"] not in ("new", "more"), -x["hours"], x["name"]))
    out["counts"] = {m: sum(1 for x in out[m] if x["state"] in ("new", "more")) for m in AUTO}
    out["thresholds"] = {m: threshold(m) for m in AUTO}
    out["period"] = {"from": semester_start().isoformat(), "to": today().isoformat()}
    return out


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
                       user: int | None = None) -> dict:
    """items: [{"sid": …, "note": …}]. Davomat — joriy sababsiz soat yoziladi; ichki tartib — qoida matni (rule)."""
    if measure not in MEASURES or ground not in GROUNDS:
        return {"ok": False, "error": "bad_measure"}
    if ground == "tartib" and not (rule or "").strip():
        return {"ok": False, "error": "no_rule"}
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
        "INSERT INTO disc_orders (measure, ground, rule, period_from, period_to, hours, status, note, created_at, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
        (measure, ground, (rule or "").strip()[:2000] or None, semester_start().isoformat() if ground == "davomat" else None,
         today().isoformat() if ground == "davomat" else None, lim, (note or "").strip()[:2000] or None, now, user))
    notes = {int(it["sid"]): (it.get("note") or "").strip()[:1000] for it in items if str(it.get("sid", "")).isdigit()}
    for sid in sids:
        h = await _hours(sid) if ground == "davomat" else None
        c = await _case(sid, measure, ground) if ground == "davomat" else None
        if c and c["status"] in ("draft", "issued"):
            continue  # boshqa hujjatda
        if c and c["status"] in ("asked", "excused", "removed", "cancelled"):
            await db.execute("UPDATE disc_cases SET status = 'draft', order_id = ?, hours = ?, note = COALESCE(?, note), "
                             "updated_at = ?, by_user = ? WHERE id = ?", (oid, h, notes.get(sid) or None, now, user, c["id"]))
        else:
            await db.execute("INSERT INTO disc_cases (student_id, measure, ground, status, hours, note, order_id, created_at, "
                             "updated_at, by_user) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)",
                             (sid, measure, ground, h, notes.get(sid) or None, oid, now, now, user))
    n = (await db.fetchone("SELECT COUNT(*) n FROM disc_cases WHERE order_id = ?", (oid,)))["n"]
    if not n:
        await db.execute("DELETE FROM disc_orders WHERE id = ?", (oid,))
        return {"ok": False, "error": "already_in_order"}
    return {"ok": True, "id": oid, "students": n}


async def order(oid: int) -> dict | None:
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return None
    o = dict(o)
    o["cases"] = [dict(r) for r in await db.fetchall(
        """SELECT c.*, s.full_name, s.group_name, s.group_key, s.course, s.faculty, s.hemis_id FROM disc_cases c
           JOIN students s ON s.id = c.student_id WHERE c.order_id = ? ORDER BY s.full_name""", (oid,))]
    o["files"] = [dict(r) for r in await db.fetchall("SELECT id, kind, name, size, uploaded_at, case_id FROM disc_files "
                                                      "WHERE order_id = ? OR case_id IN (SELECT id FROM disc_cases WHERE "
                                                      "order_id = ?) ORDER BY id", (oid, oid))]
    o["title"] = MEASURES.get(o["measure"], {}).get("title", o["measure"])
    o["ground_title"] = GROUNDS.get(o["ground"], o["ground"])
    o["doc_kinds"] = [{"kind": k, "title": DOC_KINDS[k]} for k in doc_kinds(o["ground"], o["measure"])]
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


async def delete_order(oid: int) -> dict:
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    if o["status"] == "issued":
        return {"ok": False, "error": "issued"}
    for c in await db.fetchall("SELECT * FROM disc_cases WHERE order_id = ?", (oid,)):
        if c["ground"] == "davomat" and c["asked_at"]:  # ota-onadan so'ralgani yo'qolmasin
            await db.execute("UPDATE disc_cases SET status = 'asked', order_id = NULL, updated_at = ? WHERE id = ?", (now_iso(), c["id"]))
        else:
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


async def issue_order(bot, oid: int, number: str, d: str, notify: bool = True, user: int | None = None) -> dict:
    """Farmoyish/buyruq imzolandi: raqam, sana — chora rasman ko'rilgan; ota-onalarga xabar (ixtiyoriy)."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    try:
        date.fromisoformat(d)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_date"}
    first = o["status"] != "issued"
    now = now_iso()
    await db.execute("UPDATE disc_orders SET number = ?, date = ?, status = 'issued', issued_at = COALESCE(issued_at, ?), "
                     "issued_by = COALESCE(issued_by, ?) WHERE id = ?", ((number or "").strip()[:40] or None, d, now, user, oid))
    await db.execute("UPDATE disc_cases SET status = 'issued', updated_at = ? WHERE order_id = ?", (now, oid))
    sent = 0
    if first and notify and bot is not None:
        sent = await notify_parents(bot, oid)
    return {"ok": True, "notified": sent}


async def cancel_order(oid: int) -> dict:
    """Chiqarilgan chorani bekor qilish (xato kiritilgan bo'lsa) — talabalar yana ro'yxatga qaytadi."""
    o = await db.fetchone("SELECT * FROM disc_orders WHERE id = ?", (oid,))
    if not o:
        return {"ok": False, "error": "not_found"}
    await db.execute("UPDATE disc_orders SET status = 'cancelled' WHERE id = ?", (oid,))
    await db.execute("UPDATE disc_cases SET status = 'cancelled', updated_at = ? WHERE order_id = ?", (now_iso(), oid))
    return {"ok": True}


async def notify_parents(bot, oid: int) -> int:
    from notifier import send_each
    from i18n import tr
    import loc
    o = await order(oid)
    if not o:
        return 0
    sent = 0
    doc = "Dekan farmoyishi" if o["measure"] == "ogohlantirish" else "Universitet buyrug'i" if o["measure"] == "hayfsan" else "Qaror"
    for c in o["cases"]:
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
                    + "\n\n" + tr("Farzandingiz bilan suhbatlashing. Savollar bo'lsa — kurs koordinatoriga yozing."))
        sent += await send_each(bot, pids, build, c["student_id"], "att", "threshold")
    return sent


# ---------------------------------------------------------------- hujjat yaratish
async def build_doc(oid: int, kind: str) -> tuple[str, bytes] | None:
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
    prior = await _prior({c["student_id"] for c in cases})
    d_issue = o.get("date")
    yr = academic_year_start()
    sem = "1" if today().month >= 8 or today().month == 1 else "2"
    values = {
        "RAQAM": o.get("number") or "______", "SANA": _date_quoted(d_issue), "SANA_UZUN": _date_long(d_issue),
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
        rows.append({"FISH": (c["full_name"] or "").upper(), "BOSQICH": c.get("course") or (stages[0] if stages else ""),
                     "FAKULTET": fac, "FAKULTET_QISQA": _faculty_short(fac), "GURUH": c.get("group_name") or "",
                     "SOAT": _num(c.get("hours")), "PARA": _num((c.get("hours") or 0) / 2), "AVVAL": prior_text(prev),
                     "IZOH": c.get("note") or ""})
    data = docxfill.fill(path.read_bytes(), values, rows)
    label = {"bildirishnoma": "Bildirishnoma", "farmoyish": "Dekan_farmoyishi", "buyruq": "Buyruq_hayfsan",
             "dalolatnoma": "Dalolatnoma"}[kind]
    return f"{label}_{MEASURES[o['measure']]['short']}_{_dmy(d_issue or today())}.docx", data


async def build_zip(oid: int) -> tuple[str, bytes] | None:
    o = await order(oid)
    if not o:
        return None
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k in doc_kinds(o["ground"], o["measure"]):
            res = await build_doc(oid, k)
            if res:
                z.writestr(res[0], res[1])
        for f in o["files"]:
            p = _course_dir().parent / f["path"]
            if p.exists():
                z.writestr(f"ilovalar/{f['id']}_{f['name']}", p.read_bytes())
    return f"Chora_{MEASURES[o['measure']]['short']}_{o['id']}.zip", buf.getvalue()


# ---------------------------------------------------------------- fayllar (imzolangan nusxa, tushuntirish xati, asos)
def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\-() ]+", "_", (name or "fayl").strip())[:120]
    return name or "fayl"


def _unlink(rel: str) -> None:
    try:
        (_course_dir().parent / rel).unlink()
    except OSError:
        pass


async def add_file(oid: int | None, case_id: int | None, kind: str, name: str, data: bytes, user: int | None = None) -> dict:
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
    fid = await db.execute("INSERT INTO disc_files (order_id, case_id, kind, name, path, size, mime, uploaded_at, by_user) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (oid, case_id, kind, _safe_name(name), rel, len(data), mime,
                                                                  now_iso(), user))
    return {"ok": True, "id": fid}


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


async def file_order(fid: int) -> int | None:
    f = await db.fetchone("SELECT order_id, case_id FROM disc_files WHERE id = ?", (fid,))
    if not f:
        return None
    if f["order_id"]:
        return f["order_id"]
    c = await db.fetchone("SELECT order_id FROM disc_cases WHERE id = ?", (f["case_id"],))
    return c["order_id"] if c else None


# ---------------------------------------------------------------- chora ko'rilganlar: tarix va dinamika
async def history(scope: set[str] | None = ..., measure: str = "", ground: str = "") -> dict:
    """O'quv yili boshidan rasman ko'rilgan choralar: ro'yxat (hujjatlari bilan), ko'rsatkichlar, oylar bo'yicha dinamika."""
    if scope is ...:
        from tenancy import viewer_scope
        scope = viewer_scope()
    rows = await db.fetchall(
        """SELECT c.id AS case_id, c.student_id, c.measure, c.ground, c.hours, c.note, o.id AS order_id, o.number, o.date,
                  o.rule, o.issued_at, s.full_name, s.group_name, s.group_key, s.hemis_id, s.course
           FROM disc_cases c JOIN disc_orders o ON o.id = c.order_id JOIN students s ON s.id = c.student_id
           WHERE c.status = 'issued' AND COALESCE(o.date, substr(o.issued_at, 1, 10)) >= ?
           ORDER BY COALESCE(o.date, o.issued_at) DESC, s.full_name""", (ay_start(),))
    rows = [dict(r) for r in rows if scope is None or r["group_key"] in scope]
    files: dict[int, list] = {}
    for f in await db.fetchall("SELECT id, order_id, case_id, kind, name, size FROM disc_files"):
        files.setdefault(f["order_id"] or -f["case_id"], []).append(dict(f))
    for r in rows:
        r["files"] = files.get(r["order_id"], []) + files.get(-r["case_id"], [])
        r["title"] = MEASURES.get(r["measure"], {}).get("title", r["measure"])
        r["ground_title"] = GROUNDS.get(r["ground"], r["ground"])
    all_rows = rows
    if measure:
        rows = [r for r in rows if r["measure"] == measure]
    if ground:
        rows = [r for r in rows if r["ground"] == ground]
    # oylar bo'yicha dinamika (o'quv yili boshidan joriy oygacha)
    start, t = academic_year_start(), today()
    months, y, m = [], start.year, start.month
    while (y, m) <= (t.year, t.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    dyn = []
    cum = {"ogohlantirish": 0, "hayfsan": 0, "boshqa": 0}
    for y, m in months:
        key = f"{y}-{m:02d}"
        cnt = {k: sum(1 for r in all_rows if (r["date"] or r["issued_at"] or "")[:7] == key and r["measure"] == k) for k in cum}
        by_ground = {g: sum(1 for r in all_rows if (r["date"] or r["issued_at"] or "")[:7] == key and r["ground"] == g)
                     for g in GROUNDS}
        for k in cum:
            cum[k] += cnt[k]
        dyn.append({"month": key, "label": MONTHS[m - 1], **cnt, "davomat": by_ground["davomat"],
                    "tartib": by_ground["tartib"], "cumulative": dict(cum)})
    kpi = {
        "ogohlantirish": sum(1 for r in all_rows if r["measure"] == "ogohlantirish"),
        "hayfsan": sum(1 for r in all_rows if r["measure"] == "hayfsan"),
        "boshqa": sum(1 for r in all_rows if r["measure"] == "boshqa"),
        "davomat": sum(1 for r in all_rows if r["ground"] == "davomat"),
        "tartib": sum(1 for r in all_rows if r["ground"] == "tartib"),
        "students": len({r["student_id"] for r in all_rows}),
        "repeat": sum(1 for v in _count_by(all_rows).values() if v > 1),
    }
    by_group: dict[str, int] = {}
    for r in all_rows:
        by_group[r["group_name"] or "—"] = by_group.get(r["group_name"] or "—", 0) + 1
    return {"items": rows, "kpi": kpi, "dynamics": dyn, "by_group": sorted(by_group.items(), key=lambda x: -x[1]),
            "since": ay_start()}


def _count_by(rows: list[dict]) -> dict[int, int]:
    out: dict[int, int] = {}
    for r in rows:
        out[r["student_id"]] = out.get(r["student_id"], 0) + 1
    return out


async def student_measures(sid: int) -> list[dict]:
    """Talabaga o'quv yilida rasman ko'rilgan choralar (talaba kartasi va ota-ona sahifasi uchun)."""
    rows = await db.fetchall(
        """SELECT c.measure, c.ground, c.hours, c.note, o.number, o.date, o.rule FROM disc_cases c
           JOIN disc_orders o ON o.id = c.order_id WHERE c.student_id = ? AND c.status = 'issued' AND c.created_at >= ?
           ORDER BY o.date""", (sid, ay_start()))
    return [{**dict(r), "title": MEASURES.get(r["measure"], {}).get("title", r["measure"])} for r in rows]


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
    need = {"T_FISH"}
    if not need <= found:
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

