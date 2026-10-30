"""Tashriflar (tashrif moduli): kurs koordinatorining ijara xonadonlariga tashriflari, madaniy tashriflar, tadbirlar
va koordinatorlik soatlari — rejadan hisobotgacha.

Ish oqimi (tashrif-py loyihasidan; dekan o'rinbosari tasdig'i bu modulda yo'q):

    qoralama ─┬─ ijara tashrifi ─► talaba_tasdigida ─┬─► tasdiqlangan ─► bajarildi
              │                    (hammasi tasdiqladi yoki koordinator shundayligicha tasdiqladi)
              └─ tadbir / madaniy tashrif / koordinatorlik soati ─┘
    (bajarildi'dan tashqari istalgan holatdan → bekor_qilingan)

Uchta asosiy qoida:
  • tashrif vaqti o'zgarsa, barcha tasdiqlar bekor bo'ladi va so'rov qaytadan yuboriladi (talaba 14:00 ga rozi edi,
    19:00 ga emas);
  • hisobotga faqat tasdiqlangan rejalar kiradi;
  • har bir harakat jurnalga yoziladi — kim, qachon, nima qildi.

Talaba tashrifni botda tasdiqlaydi (✅), boshqa vaqt taklif qiladi (🕒) yoki «bu manzilda yashamayman» deydi (❌).
Talaba tasdiqlashi bilan kurs koordinatoriga shu manzilga qanday borilishi (bekat, avtobus, metro) keladi — yo'l
ma'lumoti faqat koordinatorga, talabaga hech qachon. Barcha talabalar tasdiqlagach, reja o'zi aktual bo'ladi.
Tashrifdan keyin dalolatnoma (16 band, imzolar) to'ldiriladi; uning 14-bandi (xonadon toifasi) dashboard'ga tushadi.

Tadbir va madaniy tashrifga koordinator ishtirokchi talabalarni belgilaydi (bittalab yoki butun guruh). Reja aktual
bo'lishi bilan ularga botda nomi, sanasi, vaqti va joyi keladi (javob so'ralmaydi); oldingi kuni kechqurun va
boshlanishidan bir necha soat oldin eslatma boradi; vaqt o'zgarsa yoki bekor qilinsa — xabar beriladi.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from config import DATA_DIR, SUPERADMIN_IDS, TZ
from database import db
from tenancy import central, current_course, use_course
from utils import esc, group_key, now, now_iso, today

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- holatlar, turlar, javoblar
TURLAR = {"ijara_tashrifi": "Ijara xonadoniga tashrif", "madaniy_tashrif": "Madaniy tashrif", "tadbir": "Tadbir",
          "koordinatorlik_soati": "Koordinatorlik soati"}
IJARA, KOORD_SOAT = "ijara_tashrifi", "koordinatorlik_soati"
MADANIY, TADBIR = "madaniy_tashrif", "tadbir"
ISHTIROK = (MADANIY, TADBIR)  # ishtirokchi talabalar belgilanadi — botda ma'lumot va eslatma (javob so'ralmaydi)
QORALAMA, TALABA, TASDIQLANGAN = "qoralama", "talaba_tasdigida", "tasdiqlangan"
BAJARILDI, BEKOR = "bajarildi", "bekor_qilingan"
HOLATLAR = {QORALAMA: "Qoralama", TALABA: "Talaba tasdig'i kutilmoqda", TASDIQLANGAN: "Tasdiqlangan",
            BAJARILDI: "Bajarildi", BEKOR: "Bekor qilingan"}
KUTILMOQDA, TASDIQLADI, VAQT_TAKLIF, RAD_ETDI, JAVOB_BERMADI = (
    "kutilmoqda", "tasdiqladi", "vaqt_taklif_qildi", "rad_etdi", "javob_bermadi")
JAVOBLAR = {KUTILMOQDA: "javob kutilmoqda", TASDIQLADI: "tasdiqladi", VAQT_TAKLIF: "boshqa vaqt taklif qildi",
            RAD_ETDI: "bu manzilda yashamaydi", JAVOB_BERMADI: "javob bermadi"}
LIVING = {"ijara": "Ijara xonadonida", "ttj": "Talabalar turar joyida", "uy": "O'z uyida", "qarindosh": "Qarindoshinikida"}
ZONES = {"yashil": "Yashil", "sariq": "Sariq", "qizil": "Qizil"}

# Dalolatnoma bandlari (6–14) va javob variantlari — tashrif-py dagi qog'oz namunadan
ACT_Q = {"contract": ("bor", "yoq"), "loc": ("qulay", "noqulay"), "climate": ("qoniqarsiz", "qoniqarli", "yaxshi"),
         "study": ("ha", "yoq"), "air": ("ha", "yoq"), "safety": ("ha", "yoq"), "bed": ("xona", "oshxona", "balkon"),
         "common": ("qoniqarsiz", "qoniqarli", "yaxshi"), "category": ("qizil", "sariq", "yashil")}
ACT_TEXT = ("fio", "group", "course", "faculty", "phone", "address", "owner", "ownerPhone", "coresidents",
            "problems", "advice")

# amal → (qaysi holatlardan, qaysi holatga, kimlar) — tashrif-py states.py
_OTISHLAR = {
    "yuborish": ((QORALAMA,), None, {"koordinator"}),
    "tasdiqlash": ((TALABA,), TASDIQLANGAN, {"koordinator", "tizim"}),
    "bajarildi": ((TASDIQLANGAN,), BAJARILDI, {"koordinator"}),
    "vaqt": ((QORALAMA, TALABA, TASDIQLANGAN), None, {"koordinator"}),
    "bekor": ((QORALAMA, TALABA, TASDIQLANGAN), BEKOR, {"koordinator"}),
}


class VisitError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato (kod — panel uchun)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code, self.message = code, message or code


def after_send(kind: str) -> str:
    if kind == IJARA:
        return TALABA
    return TASDIQLANGAN


def allowed(status: str, kind: str, action: str, who: str) -> str:
    """Harakat ruxsat etilganmi; ha bo'lsa — yangi holat, yo'q bo'lsa VisitError."""
    src, dst, roles = _OTISHLAR[action]
    if who not in roles:
        raise VisitError("forbidden", "Bu harakat sizga ruxsat etilmagan")
    if status not in src:
        raise VisitError("state", f"«{HOLATLAR.get(status, status)}» holatidagi rejada bu harakat mumkin emas")
    if action == "yuborish":
        return after_send(kind)
    if action == "vaqt":
        return status if status == QORALAMA else after_send(kind)
    return dst


def with_students(kind: str) -> bool:
    """Rejaga talabalar biriktiriladimi: ijara tashrifi (javob beradi) yoki tadbir / madaniy tashrif (ishtirokchi)."""
    return kind == IJARA or kind in ISHTIROK


def is_actual(status: str) -> bool:
    """Hisobotga kiradigan holat."""
    return status in (TASDIQLANGAN, BAJARILDI)


def editable(status: str) -> bool:
    return status == QORALAMA


# ---------------------------------------------------------------- vaqt
_DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
OYLAR = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
KUNLAR = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]


def _local(d: str, t: str = "00:00") -> datetime:
    return datetime.fromisoformat(f"{d}T{t}").replace(tzinfo=TZ)


def _mins(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _hhmm(m: int) -> str:
    m = max(0, min(m, 23 * 60 + 59))
    return f"{m // 60:02d}:{m % 60:02d}"


def passed(d: str, t: str = "23:59") -> bool:
    return _local(d, t) < now()


def when(p: dict) -> str:
    """«20-oktabr, seshanba, 14:00–16:00»."""
    try:
        x = date.fromisoformat(p["visit_date"])
        s = f"{x.day}-{OYLAR[x.month - 1]}, {KUNLAR[x.weekday()]}"
    except (ValueError, KeyError):
        s = p.get("visit_date") or ""
    return s + (f", {p['start_time']}–{p['end_time']}" if p.get("start_time") else "")


_KUN_SOZLARI = ((re.compile(r"^(bugun)\b"), 0), (re.compile(r"^(ertaga|erta)\b"), 1), (re.compile(r"^(indinga|indin)\b"), 2))


def parse_proposal(text: str, base: str) -> tuple[str, str | None] | None:
    """Talaba yozgan qulay vaqt (tashrif-py vaqtni_tushun): «14:00» (sana o'zgarmaydi), «22.10 14:00», «22.10.2026 14:00»,
    «2026-10-22 14:00», «ertaga 16:30» / «bugun» / «indinga» (tashrif sanasiga nisbatan), «25-oktabr 15:00».
    Qaytaradi: (sana, vaqt yoki None) yoki tushunilmasa None."""
    s = " ".join(str(text or "").lower().split())
    if not s:
        return None
    day, rest = None, s
    for rx, n in _KUN_SOZLARI:
        m = rx.match(rest)
        if m:
            day = (date.fromisoformat(base) + timedelta(days=n)).isoformat()
            rest = rest[m.end():].strip()
            break
    if not day:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\b", rest)
        if m:
            day, rest = f"{m.group(1)}-{m.group(2)}-{m.group(3)}", rest[m.end():].strip()
        else:
            m = re.match(r"^(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", rest)
            if m:
                y = m.group(3) or base[:4]
                y = "20" + y if len(y) == 2 else y
                day, rest = f"{y}-{int(m.group(2)):02d}-{int(m.group(1)):02d}", rest[m.end():].strip()
            else:
                m = re.match(r"^(\d{1,2})[-\s]?([a-zʻ‘’']+)", rest)
                if m:
                    for i, oy in enumerate(OYLAR):
                        if m.group(2).startswith(oy[:3]):
                            day, rest = f"{base[:4]}-{i + 1:02d}-{int(m.group(1)):02d}", rest[m.end():].strip()
                            break
    rest = re.sub(r"^(soat|da|kuni|—|-|,)\s*", "", rest).strip()
    hhmm = None
    m = re.search(r"(\d{1,2})[:.\s](\d{2})", rest) or re.match(r"^(\d{1,2})$", rest)
    if m:
        hhmm = f"{min(23, int(m.group(1))):02d}:{min(59, int(m.group(2))) if m.lastindex and m.lastindex > 1 else 0:02d}"
    if not day and not hhmm:
        return None
    if day:
        try:
            date.fromisoformat(day)
        except ValueError:
            return None
    return day or base, hhmm


# ---------------------------------------------------------------- xodimlar
def is_super(uid: int | None) -> bool:
    return uid in SUPERADMIN_IDS


async def staff_name(uid: int | None) -> str:
    if uid is None:
        return ""
    coords = (await central.registry())[1]
    name = next((c["name"] for c in coords if c["user_id"] == uid and c.get("name")), "")
    return name or ("Super-admin" if uid in SUPERADMIN_IDS else "Kurs koordinatori")


def can_manage(p: dict, uid: int | None) -> bool:
    """Rejani ko'rish va o'zgartirish: uni tuzgan koordinator yoki super-admin."""
    return uid is not None and (p["coordinator_id"] == uid or is_super(uid))


# ---------------------------------------------------------------- o'qish
async def _students_of(pid: int) -> list[dict]:
    return await db.fetchall(
        """SELECT vs.*, s.full_name, s.group_name, s.group_key, s.hemis_id, s.course, s.faculty, s.lat, s.lon, s.living,
                  s.visit_code, a.tg_id, a.tg_name,
                  (SELECT phone FROM student_self_phones WHERE student_id = s.id LIMIT 1) AS phone
           FROM visit_students vs JOIN students s ON s.id = vs.student_id
           LEFT JOIN student_accounts a ON a.student_id = vs.student_id
           WHERE vs.plan_id = ? ORDER BY s.full_name""", (pid,))


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    c = {k: sum(1 for r in rows if r["response"] == k) for k in JAVOBLAR}
    return {"total": n, **c, "all_ok": n > 0 and c[TASDIQLADI] == n}


async def get(pid: int, full: bool = True) -> dict | None:
    p = await db.fetchone("SELECT * FROM visit_plans WHERE id = ?", (pid,))
    if not p:
        return None
    p["students"] = await _students_of(pid)
    p["answers"] = summary(p["students"])
    p["type_title"] = TURLAR.get(p["type"], p["type"])
    p["status_title"] = HOLATLAR.get(p["status"], p["status"])
    p["actual"], p["editable"] = is_actual(p["status"]), editable(p["status"])
    p["when"] = when(p)
    if full:
        p["events"] = await db.fetchall("SELECT * FROM visit_events WHERE plan_id = ? ORDER BY at, id", (pid,))
        p["acts"] = [_act_row(a) for a in await db.fetchall(
            "SELECT * FROM visit_acts WHERE plan_id = ? ORDER BY id", (pid,))]
        p["photos"] = await db.fetchall(
            "SELECT id, act_id, name, size, mime, created_at FROM visit_photos WHERE plan_id = ? ORDER BY id", (pid,))
    return p


async def plans(uid: int | None, frm: str = "", to: str = "", status: str = "") -> list[dict]:
    """Ko'rinadigan rejalar: koordinator — o'ziniki, super-admin — kursning barchasi."""
    where, args = ["1 = 1"], []
    if not is_super(uid):
        where.append("coordinator_id = ?")
        args.append(uid)
    if frm:
        where.append("visit_date >= ?")
        args.append(frm)
    if to:
        where.append("visit_date <= ?")
        args.append(to)
    if status:
        sts = [x for x in status.split(",") if x in HOLATLAR]
        if sts:
            where.append(f"status IN ({','.join('?' * len(sts))})")
            args += sts
    rows = await db.fetchall(f"SELECT * FROM visit_plans WHERE {' AND '.join(where)} ORDER BY visit_date, start_time, id",
                             tuple(args))
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    qm = ",".join("?" * len(ids))
    studs: dict[int, list] = {}
    for s in await db.fetchall(
            f"""SELECT vs.plan_id, vs.student_id, vs.response, vs.address, vs.proposed_date, vs.proposed_time, vs.comment,
                       s.full_name, s.group_name, a.tg_id
                FROM visit_students vs JOIN students s ON s.id = vs.student_id
                LEFT JOIN student_accounts a ON a.student_id = vs.student_id WHERE vs.plan_id IN ({qm})
                ORDER BY s.full_name""", tuple(ids)):
        studs.setdefault(s["plan_id"], []).append(s)
    acts = {r["plan_id"]: r["n"] for r in await db.fetchall(
        f"SELECT plan_id, COUNT(*) n FROM visit_acts WHERE plan_id IN ({qm}) GROUP BY plan_id", tuple(ids))}
    for r in rows:
        r["students"] = studs.get(r["id"], [])
        r["answers"] = summary(r["students"])
        r["type_title"], r["status_title"] = TURLAR.get(r["type"], r["type"]), HOLATLAR.get(r["status"], r["status"])
        r["actual"], r["editable"], r["acts_n"] = is_actual(r["status"]), editable(r["status"]), acts.get(r["id"], 0)
    return rows


async def counts(uid: int | None) -> dict:
    """Kurs holati va menyu belgisi uchun: bu hafta, talaba javobini kutayotganlar, bajarilganlar, dalolatnomasizlar."""
    t = today()
    mon = t - timedelta(days=t.weekday())
    rows = await plans(uid, frm=(t - timedelta(days=200)).isoformat())
    week = [r for r in rows if mon.isoformat() <= r["visit_date"] <= (mon + timedelta(days=6)).isoformat()
            and r["status"] != BEKOR]
    return {"week": len(week), "week_actual": sum(1 for r in week if r["actual"]),
            "students": sum(1 for r in rows if r["status"] == TALABA),
            "drafts": sum(1 for r in rows if r["status"] == QORALAMA),
            "done": sum(1 for r in rows if r["status"] == BAJARILDI),
            "need_act": sum(1 for r in rows if r["type"] == IJARA and r["status"] == BAJARILDI and not r["acts_n"])}


async def student_visits(sid: int) -> dict:
    """Talaba kartasi uchun: yashash joyi, tashriflari va dalolatnomalari."""
    st = await db.get_student(sid) or {}
    rows = await db.fetchall(
        """SELECT p.*, vs.response, vs.address AS s_address FROM visit_plans p JOIN visit_students vs ON vs.plan_id = p.id
           WHERE vs.student_id = ? ORDER BY p.visit_date DESC, p.start_time DESC""", (sid,))
    for r in rows:
        r["type_title"], r["status_title"] = TURLAR.get(r["type"], r["type"]), HOLATLAR.get(r["status"], r["status"])
        r["when"] = when(r)
    acts = [_act_row(a) for a in await db.fetchall(
        "SELECT * FROM visit_acts WHERE student_id = ? ORDER BY id DESC", (sid,))]
    acc = await db.fetchone("SELECT tg_id, tg_name, via, linked_at FROM student_accounts WHERE student_id = ?", (sid,))
    zone = acts[0]["category"] if acts and acts[0]["category"] else st.get("zone")
    return {"living": st.get("living") or ("ijara" if (st.get("address") or "").strip() else None),
            "zone": zone, "zone_from": "act" if acts and acts[0]["category"] else ("manual" if st.get("zone") else None),
            "address": st.get("address") or "", "lat": st.get("lat"), "lon": st.get("lon"),
            "visits": rows, "acts": acts, "account": acc}


# ---------------------------------------------------------------- jurnal
async def _log(pid: int, kind: str, action: str, uid: int | None = None, name: str | None = None,
               frm: str | None = None, to: str | None = None, detail: str | None = None) -> None:
    await db.conn.execute(
        """INSERT INTO visit_events (plan_id, at, actor_kind, actor_id, actor_name, action, from_status, to_status, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (pid, now_iso(), kind, uid, name, action, frm, to, detail))
    await db.conn.commit()


async def _set_status(pid: int, status: str, **extra) -> None:
    cols = ["status = ?", "updated_at = ?"] + [f"{k} = ?" for k in extra]
    await db.execute(f"UPDATE visit_plans SET {', '.join(cols)} WHERE id = ?", (status, now_iso(), *extra.values(), pid))


# ---------------------------------------------------------------- yaratish va tahrirlash
def _check(d: dict) -> None:
    if not str(d.get("title") or "").strip():
        raise VisitError("no_title", "Reja nomi kiritilmagan")
    if d.get("type") not in TURLAR:
        raise VisitError("bad_type", "Reja turi noto'g'ri")
    if not _DATE.match(str(d.get("visit_date") or "")):
        raise VisitError("bad_date", "Sana noto'g'ri")
    if not _TIME.match(str(d.get("start_time") or "")) or not _TIME.match(str(d.get("end_time") or "")):
        raise VisitError("bad_time", "Vaqt noto'g'ri (HH:MM)")
    if _mins(d["end_time"]) <= _mins(d["start_time"]):
        raise VisitError("bad_time", "Tugash vaqti boshlanishidan keyin bo'lishi kerak")


async def _attach(pid: int, sids: list[int], scope: set[str] | None, address: bool = True) -> int:
    """Talabalarni rejaga biriktirish (ko'rinish doirasidagilar). Ijara manzili — faqat ijara tashrifiga."""
    n = 0
    for sid in dict.fromkeys(int(x) for x in sids or []):
        st = await db.get_student(sid)
        if not st or (scope is not None and st.get("group_key") not in scope):
            continue
        await db.conn.execute("INSERT OR IGNORE INTO visit_students (plan_id, student_id, address, response) VALUES (?, ?, ?, ?)",
                              (pid, sid, ((st.get("address") or "").strip() or None) if address else None, KUTILMOQDA))
        n += 1
    await db.conn.commit()
    return n


async def create(d: dict, uid: int, scope: set[str] | None = None) -> dict:
    _check(d)
    if d["type"] == IJARA and not d.get("student_ids"):
        raise VisitError("no_students", "Ijara tashrifiga kamida bitta talaba biriktiriladi")
    name = await staff_name(uid)
    ts = now_iso()
    pid = await db.execute(
        """INSERT INTO visit_plans (coordinator_id, coordinator_name, type, title, visit_date, start_time, end_time, place,
                                    note, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, name, d["type"], str(d["title"]).strip()[:200], d["visit_date"], d["start_time"], d["end_time"],
         (d.get("place") or "").strip()[:300] or None, (d.get("note") or "").strip()[:1000] or None, QORALAMA, ts, ts))
    if d["type"] == IJARA:
        if not await _attach(pid, d["student_ids"], scope):
            await db.execute("DELETE FROM visit_plans WHERE id = ?", (pid,))
            raise VisitError("no_students", "Talabalar topilmadi")
    elif d["type"] in ISHTIROK and d.get("student_ids"):
        await _attach(pid, d["student_ids"], scope, address=False)
    await _log(pid, "koordinator", "yaratildi", uid, name, to=QORALAMA)
    _wake_geo()
    return await get(pid)


async def update(pid: int, d: dict, uid: int, scope: set[str] | None = None) -> dict:
    p = await _own(pid, uid)
    if not editable(p["status"]):
        raise VisitError("state", f"«{HOLATLAR[p['status']]}» holatidagi rejani tahrirlab bo'lmaydi — vaqtini o'zgartiring "
                                  "yoki tahrirga qaytaring")
    nxt = {**p, **{k: v for k, v in d.items() if k in ("title", "visit_date", "start_time", "end_time", "place", "note")
                   and v is not None}}
    _check(nxt)
    await db.execute("""UPDATE visit_plans SET title = ?, visit_date = ?, start_time = ?, end_time = ?, place = ?, note = ?,
                        updated_at = ? WHERE id = ?""",
                     (str(nxt["title"]).strip()[:200], nxt["visit_date"], nxt["start_time"], nxt["end_time"],
                      (nxt.get("place") or "").strip()[:300] or None, (nxt.get("note") or "").strip()[:1000] or None,
                      now_iso(), pid))
    if with_students(p["type"]) and d.get("student_ids") is not None:
        if p["type"] == IJARA and not d["student_ids"]:
            raise VisitError("no_students", "Ijara tashrifiga kamida bitta talaba biriktiriladi")
        await db.execute("DELETE FROM visit_students WHERE plan_id = ?", (pid,))
        if not await _attach(pid, d["student_ids"], scope, address=p["type"] == IJARA) and p["type"] == IJARA:
            raise VisitError("no_students", "Ijara tashrifiga kamida bitta talaba biriktiriladi")
    await _log(pid, "koordinator", "tahrirlandi", uid, await staff_name(uid))
    _wake_geo()
    return await get(pid)


async def delete(pid: int, uid: int) -> None:
    p = await _own(pid, uid)
    if p["status"] != QORALAMA or p.get("sent_at"):
        raise VisitError("state", "Faqat yuborilmagan qoralama o'chiriladi — qolganini bekor qiling")
    for f in await db.fetchall("SELECT path FROM visit_photos WHERE plan_id = ?", (pid,)):
        _unlink(f["path"])
    await db.execute("DELETE FROM visit_plans WHERE id = ?", (pid,))


async def set_participants(bot, pid: int, uid: int, sids: list[int], scope: set[str] | None = None) -> dict:
    """Tadbir / madaniy tashrif ishtirokchilari — reja aktual bo'lgandan keyin ham o'zgaradi: yangi qo'shilganlarga
    botda darhol ma'lumot, ro'yxatdan chiqarilganlarga (xabar olgan bo'lsa) — bildirish."""
    p = await _own(pid, uid)
    if p["type"] not in ISHTIROK:
        raise VisitError("bad_type", "Ishtirokchilar faqat tadbir va madaniy tashrifga belgilanadi")
    if p["status"] not in (QORALAMA, TASDIQLANGAN):
        raise VisitError("state", f"«{HOLATLAR[p['status']]}» holatidagi rejada ishtirokchilar o'zgartirilmaydi")
    if p["status"] == TASDIQLANGAN and passed(p["visit_date"], p["end_time"]):
        raise VisitError("past", "Tadbir o'tib ketgan — ishtirokchilar ro'yxati o'zgartirilmaydi")
    want = list(dict.fromkeys(int(x) for x in sids or []))
    old = {s["student_id"]: s for s in p["students"]}
    gone = [s for k, s in old.items() if k not in want]
    if gone:
        await db.execute(f"DELETE FROM visit_students WHERE plan_id = ? AND student_id IN ({','.join('?' * len(gone))})",
                         (pid, *(s["student_id"] for s in gone)))
    added = await _attach(pid, [x for x in want if x not in old], scope, address=False)
    if added or gone:
        await _log(pid, "koordinator", "ishtirokchilar_ozgartirildi", uid, await staff_name(uid),
                   detail=f"qo'shildi: {added}, chiqarildi: {len(gone)}; jami {len(old) - len(gone) + added} ta")
    p = await get(pid)
    if not added and not gone:
        return p
    if p["status"] == TASDIQLANGAN and p.get("sent_at"):
        p["delivery"] = await _inform(bot, p, [s for s in p["students"] if s["student_id"] not in old])
        for s in gone:
            if s.get("tg_id") and s.get("notified_at"):
                await _send(bot, s["tg_id"], event_text(p, f"<b>ℹ️ Siz {_nom(p).lower()} ishtirokchilari ro'yxatidan "
                                                           "chiqarildingiz</b>", short=True))
    return p


async def _own(pid: int, uid: int | None) -> dict:
    p = await get(pid, full=False)
    if not p:
        raise VisitError("not_found", "Reja topilmadi")
    if not can_manage(p, uid):
        raise VisitError("forbidden", "Bu reja boshqa koordinatorniki")
    return p


# ---------------------------------------------------------------- yuborish va talaba javoblari
def _deadline(p: dict) -> str:
    """Talaba javobi muddati — tashrif boshlanishidan kech emas."""
    from tashrif.sozlama import sozlama
    return min(now() + timedelta(hours=sozlama.javob_soat), _local(p["visit_date"], p["start_time"])).isoformat(
        timespec="seconds")


async def send(bot, pid: int, uid: int) -> dict:
    p = await _own(pid, uid)
    nxt = allowed(p["status"], p["type"], "yuborish", "koordinator")
    if passed(p["visit_date"], p["end_time"]):
        raise VisitError("past", "Sanasi o'tib ketgan rejani yuborib bo'lmaydi")
    if p["type"] == IJARA and not p["students"]:
        raise VisitError("no_students", "Tashrifga talaba biriktirilmagan")
    ts = now_iso()
    if nxt == TALABA:
        await db.execute("""UPDATE visit_students SET response = ?, proposed_date = NULL, proposed_time = NULL, comment = NULL,
                            responded_at = NULL, reminder_sent_at = NULL WHERE plan_id = ?""", (KUTILMOQDA, pid))
        await _set_status(pid, nxt, sent_at=ts, student_deadline=_deadline(p))
    else:
        await _set_status(pid, nxt, sent_at=ts)
    await _log(pid, "koordinator", "yuborildi", uid, await staff_name(uid), p["status"], nxt)
    p = await get(pid)
    if nxt == TALABA:
        p["delivery"] = await _notify_students(bot, p)
    elif p["type"] in ISHTIROK and p["students"]:
        p["delivery"] = await _inform(bot, p, p["students"])
    return p


async def answer(bot, pid: int, sid: int, resp: str, proposed_date: str | None = None, proposed_time: str | None = None,
                 comment: str | None = None, via: str = "bot") -> dict:
    """Talaba javobi (botda yoki koordinator talabaning og'zaki javobini panelda belgilaydi)."""
    p = await get(pid, full=False)
    if not p:
        raise VisitError("not_found", "Reja topilmadi")
    if p["status"] != TALABA:
        raise VisitError("state", "Bu tashrif bekor qilingan." if p["status"] == BEKOR
                         else "Bu tashrif bo'yicha javob berish muddati yopilgan.")
    row = next((s for s in p["students"] if s["student_id"] == sid), None)
    if not row:
        raise VisitError("not_attached", "Siz bu tashrifga biriktirilmagansiz")
    if resp not in (TASDIQLADI, VAQT_TAKLIF, RAD_ETDI):
        raise VisitError("bad_answer", "Javob turi noto'g'ri")
    if resp == VAQT_TAKLIF:
        proposed_date = proposed_date or p["visit_date"]
        if not _DATE.match(proposed_date) or (proposed_time and not _TIME.match(proposed_time)):
            raise VisitError("bad_time", "Taklif qilingan vaqt noto'g'ri")
    else:
        proposed_date = proposed_time = None
    await db.execute("""UPDATE visit_students SET response = ?, proposed_date = ?, proposed_time = ?, comment = ?,
                        responded_at = ? WHERE plan_id = ? AND student_id = ?""",
                     (resp, proposed_date, proposed_time, (comment or "").strip()[:500] or None, now_iso(), pid, sid))
    detail = f"taklif: {proposed_date} {proposed_time or ''}".strip() if resp == VAQT_TAKLIF else comment
    if via != "bot":
        detail = ((detail + "; ") if detail else "") + "koordinator belgiladi"
    await _log(pid, "talaba", f"talaba_{resp}", sid, row["full_name"], detail=detail)
    await _collapse(bot, pid, "talaba", sid)
    p = await get(pid)
    st = next(s for s in p["students"] if s["student_id"] == sid)
    await _notify_answer(bot, p, st, resp)
    if p["answers"]["all_ok"]:
        return await confirm(bot, pid, None, kind="tizim")
    return p


async def confirm(bot, pid: int, uid: int | None, kind: str = "koordinator", force: bool = False) -> dict:
    """Reja aktual bo'ladi: barcha talabalar tasdiqladi (tizim) yoki koordinator javobsizlarini «javob bermadi» deb
    shundayligicha tasdiqladi (force). Talabalarga yakuniy xabar, koordinatorga — bildirish."""
    p = await get(pid, full=False)
    if not p:
        raise VisitError("not_found", "Reja topilmadi")
    if kind == "koordinator" and not can_manage(p, uid):
        raise VisitError("forbidden", "Bu reja boshqa koordinatorniki")
    nxt = allowed(p["status"], p["type"], "tasdiqlash", kind)
    a = p["answers"]
    if not a["all_ok"] and not force:
        raise VisitError("not_all", f"Hali {a[KUTILMOQDA] + a[VAQT_TAKLIF]} ta talaba tasdiqlamagan — kuting yoki "
                                    "«shundayligicha tasdiqlash» ni tanlang")
    if force:
        await db.execute("UPDATE visit_students SET response = ? WHERE plan_id = ? AND response = ?",
                         (JAVOB_BERMADI, pid, KUTILMOQDA))
    await _set_status(pid, nxt)
    await _log(pid, kind, "tasdiqlandi_javobsiz" if force else "tasdiqlandi", uid,
               await staff_name(uid) if uid else None, p["status"], nxt, f"tasdiqlagan: {a[TASDIQLADI]}/{a['total']}")
    for k in ("talaba", "uzatish", "taklif"):
        await _collapse(bot, pid, k)
    p = await get(pid)
    if kind == "tizim":
        await _to_coordinator(bot, p, f"<b>✅ Barcha talabalar tasdiqladi</b>\n\n{esc(p['title'])}\n{esc(p['when'])}\n\n"
                                      "Reja aktual holatga o'tdi.")
    for s in p["students"]:
        if s.get("tg_id") and s["response"] == TASDIQLADI:
            await _send(bot, s["tg_id"], f"<b>✅ Tashrif tasdiqlandi</b>\n\n<b>Sana va vaqt:</b> {esc(p['when'])}\n"
                                         f"<b>Kurs koordinatori:</b> {esc(p['coordinator_name'] or '')}\n\n"
                                         "Belgilangan vaqtda uyda bo'lishingizni so'raymiz.")
    return p


async def change_time(bot, pid: int, uid: int, d: str | None = None, start: str | None = None, end: str | None = None,
                      reason: str | None = None) -> dict:
    """Vaqt o'zgarsa — barcha tasdiqlar bekor, ijara tashrifi talabalar tasdig'idan qaytadan o'tadi."""
    p = await _own(pid, uid)
    nxt = allowed(p["status"], p["type"], "vaqt", "koordinator")
    new = {**p, "visit_date": d or p["visit_date"], "start_time": start or p["start_time"], "end_time": end or p["end_time"]}
    _check(new)
    if passed(new["visit_date"], new["end_time"]):
        raise VisitError("past", "Yangi vaqt o'tmishda bo'lmasligi kerak")
    await db.execute("""UPDATE visit_plans SET visit_date = ?, start_time = ?, end_time = ?, status = ?, student_deadline = ?,
                        reminded_at = NULL, eve_reminded_at = NULL, updated_at = ? WHERE id = ?""",
                     (new["visit_date"], new["start_time"], new["end_time"], nxt, _deadline(new), now_iso(), pid))
    if nxt == TALABA:
        await db.execute("""UPDATE visit_students SET response = ?, proposed_date = NULL, proposed_time = NULL,
                            responded_at = NULL, reminder_sent_at = NULL WHERE plan_id = ?""", (KUTILMOQDA, pid))
    await _log(pid, "koordinator", "vaqti_ozgartirildi", uid, await staff_name(uid), p["status"], nxt,
               f"{p['visit_date']} {p['start_time']} → {new['visit_date']} {new['start_time']}" + (f" ({reason})" if reason else ""))
    for k in ("taklif", "uzatish", "talaba"):
        await _collapse(bot, pid, k)
    p = await get(pid)
    if nxt == TALABA:
        p["delivery"] = await _notify_students(bot, p, again=True)
    elif p.get("sent_at") and p["type"] in ISHTIROK:  # aktual tadbir — ishtirokchilarga yangi vaqt
        text = event_text(p, f"<b>🔄 {_nom(p)} vaqti o'zgartirildi</b>", "Yangi vaqtni yozib qo'ying — oldidan eslatma boradi.")
        for s in p["students"]:
            await _send(bot, s.get("tg_id"), text)
    return p


async def accept_proposal(bot, pid: int, sid: int, uid: int) -> dict:
    """Talaba taklif qilgan vaqt qabul qilinadi (davomiylik saqlanadi)."""
    p = await _own(pid, uid)
    row = next((s for s in p["students"] if s["student_id"] == sid), None)
    if not row or row["response"] != VAQT_TAKLIF:
        raise VisitError("no_proposal", "Bu talaba vaqt taklif qilmagan")
    start = row["proposed_time"] or p["start_time"]
    dur = _mins(p["end_time"]) - _mins(p["start_time"])
    return await change_time(bot, pid, uid, row["proposed_date"] or p["visit_date"], start, _hhmm(_mins(start) + dur),
                             f"{row['full_name']} taklifi qabul qilindi")


async def done(pid: int, uid: int, result: str = "", problem: str = "") -> dict:
    p = await _own(pid, uid)
    nxt = allowed(p["status"], p["type"], "bajarildi", "koordinator")
    if not passed(p["visit_date"], p["start_time"]):
        raise VisitError("early", "Tashrif vaqti hali kelmagan")
    await _set_status(pid, nxt, completed_at=now_iso(), result=(result or "").strip()[:2000] or None,
                      problem=(problem or "").strip()[:2000] or None)
    await _log(pid, "koordinator", "bajarildi", uid, await staff_name(uid), p["status"], nxt, (result or "").strip() or None)
    return await get(pid)


async def cancel(bot, pid: int, uid: int, reason: str) -> dict:
    p = await get(pid, full=False)
    if not p:
        raise VisitError("not_found", "Reja topilmadi")
    if not can_manage(p, uid):
        raise VisitError("forbidden", "Bu reja boshqa koordinatorniki")
    nxt = allowed(p["status"], p["type"], "bekor", "koordinator")
    if not (reason or "").strip():
        raise VisitError("no_reason", "Bekor qilish sababi yozilishi shart")
    await _set_status(pid, nxt, cancel_reason=reason.strip()[:500])
    await _log(pid, "koordinator", "bekor_qilindi", uid, await staff_name(uid), p["status"], nxt, reason.strip())
    for k in ("talaba", "taklif", "uzatish"):
        await _collapse(bot, pid, k)
    p = await get(pid)
    if p.get("sent_at"):
        text = event_text(p, f"<b>❌ {_nom(p)} bekor qilindi</b>", f"<b>Sabab:</b> {esc(reason)}", short=True) \
            if p["type"] in ISHTIROK else f"<b>❌ Tashrif bekor qilindi</b>\n\n{esc(p['when'])}\n<b>Sabab:</b> {esc(reason)}"
        for s in p["students"]:
            if s.get("tg_id"):
                await _send(bot, s["tg_id"], text)
    return p


# ---------------------------------------------------------------- talabaning Telegram hisobi
_CODE_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
START_PREFIX = "v_"


async def invite_code(sid: int) -> str:
    """Talabaning shaxsiy havolasi uchun kod (t.me/<bot>?start=v_<kurs>_<kod>) — bir marta yaratiladi."""
    st = await db.get_student(sid)
    if st and st.get("visit_code"):
        return st["visit_code"]
    code = "".join(secrets.choice(_CODE_ABC) for _ in range(10))
    await db.execute("UPDATE students SET visit_code = ? WHERE id = ?", (code, sid))
    return code


async def invite_url(bot, sid: int) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start={START_PREFIX}{current_course() or '_'}_{await invite_code(sid)}"


async def bind_by_code(code: str, tg_id: int, tg_name: str = "") -> dict | None:
    """Shaxsiy havola ochildi — talabaning Telegram hisobi bog'lanadi (joriy kurs bazasida)."""
    st = await db.fetchone("SELECT * FROM students WHERE visit_code = ?", ((code or "").strip().upper(),))
    if not st:
        return None
    await db.execute("""INSERT INTO student_accounts (student_id, tg_id, tg_name, via, linked_at) VALUES (?, ?, ?, 'havola', ?)
                        ON CONFLICT(student_id) DO UPDATE SET tg_id = excluded.tg_id, tg_name = excluded.tg_name,
                        via = excluded.via, linked_at = excluded.linked_at""", (st["id"], tg_id, tg_name[:80], now_iso()))
    return st


async def remember_confirmed_student(sid: int, tg_id: int, tg_name: str = "") -> None:
    """Ota-onani tasdiqlagan talaba (o'z raqami bilan) — tashrif xabarlari ham unga boradi (hisobi bo'lmasa)."""
    await db.execute("INSERT OR IGNORE INTO student_accounts (student_id, tg_id, tg_name, via, linked_at) "
                     "VALUES (?, ?, ?, 'tasdiq', ?)", (sid, tg_id, (tg_name or "")[:80], now_iso()))


async def students_of_tg(tg_id: int) -> list[dict]:
    return await db.fetchall("SELECT s.* FROM student_accounts a JOIN students s ON s.id = a.student_id WHERE a.tg_id = ?",
                             (tg_id,))


async def open_for_student(sid: int) -> list[dict]:
    """Talaba javobini kutayotgan tashriflar (havola ochilganda darhol ko'rsatiladi)."""
    return await db.fetchall(
        """SELECT p.* FROM visit_plans p JOIN visit_students vs ON vs.plan_id = p.id
           WHERE vs.student_id = ? AND p.status = ? AND vs.response IN (?, ?) ORDER BY p.visit_date""",
        (sid, TALABA, KUTILMOQDA, VAQT_TAKLIF))


async def catch_up(bot, sid: int) -> int:
    """Talaba botga endi ulandi: u belgilangan, hali o'tmagan aktual tadbir va madaniy tashriflar haqida xabar
    (reja yuborilganda xabar yetmagan bo'lsa)."""
    rows = await db.fetchall(
        f"""SELECT p.id FROM visit_plans p JOIN visit_students vs ON vs.plan_id = p.id
            WHERE vs.student_id = ? AND vs.notified_at IS NULL AND p.status = ? AND p.sent_at IS NOT NULL
            AND p.type IN ({','.join('?' * len(ISHTIROK))}) AND p.visit_date >= ? ORDER BY p.visit_date, p.start_time""",
        (sid, TASDIQLANGAN, *ISHTIROK, today().isoformat()))
    n = 0
    for r in rows:
        p = await get(r["id"], full=False)
        if p and not passed(p["visit_date"], p["end_time"]):
            n += (await _inform(bot, p, [s for s in p["students"] if s["student_id"] == sid], quiet=True))["sent"]
    return n


# ---------------------------------------------------------------- bot xabarlari
def _kb(rows: list[list[tuple[str, str]]]):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t, url=v) if v.startswith("http") else InlineKeyboardButton(text=t, callback_data=v)
        for t, v in row] for row in rows if row])


def cb(action: str, pid: int, sid: int = 0) -> str:
    """Tugma ma'lumoti: tv:<amal>:<kurs>:<reja>:<talaba> (kurs — qaysi bazaga tegishli)."""
    return f"tv:{action}:{current_course() or '_'}:{pid}:{sid}"


def student_kb(pid: int, sid: int):
    return _kb([[("✅ Tasdiqlayman", cb("ok", pid, sid))], [("🕒 Boshqa vaqt taklif qilaman", cb("time", pid, sid))],
                [("❌ Bu manzilda yashamayman", cb("no", pid, sid))]])


async def _send(bot, chat_id: int | None, text: str, kb=None):
    if bot is None or not chat_id:
        return None
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    try:
        msg = await bot.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)
        await asyncio.sleep(0.04)
        return msg
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        log.warning("Tashrif xabari yuborilmadi %s: %s", chat_id, e)
    except Exception:  # noqa: BLE001  (tarmoq — reja holati baribir saqlangan)
        log.exception("Tashrif xabari yuborilmadi %s", chat_id)
    return None


async def _remember(pid: int, kind: str, msg, sid: int | None = None) -> None:
    if getattr(msg, "message_id", None) and getattr(msg, "chat", None):
        await db.execute("INSERT INTO visit_messages (plan_id, student_id, chat_id, message_id, kind, sent_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)", (pid, sid, msg.chat.id, msg.message_id, kind, now_iso()))


async def _collapse(bot, pid: int, kind: str, sid: int | None = None) -> None:
    """Eski xabarlardagi tugmalar olinadi — ikki marta bosib bo'lmasin."""
    rows = await db.fetchall("SELECT * FROM visit_messages WHERE plan_id = ? AND kind = ?" + (" AND student_id = ?" if sid else ""),
                             (pid, kind, sid) if sid else (pid, kind))
    for m in rows:
        if bot is not None:
            try:
                await bot.edit_message_reply_markup(chat_id=m["chat_id"], message_id=m["message_id"], reply_markup=None)
            except Exception:  # noqa: BLE001  (xabar o'chirilgan yoki allaqachon tugmasiz)
                pass
    if rows:
        await db.execute(f"DELETE FROM visit_messages WHERE id IN ({','.join(str(m['id']) for m in rows)})")


def student_text(p: dict, row: dict, again: bool = False) -> str:
    lines = ["<b>🔄 Tashrif vaqti o'zgartirildi</b>" if again else "<b>🏠 Ijara xonadoningizga tashrif rejalashtirildi</b>", "",
             f"<b>Sana va vaqt:</b> {esc(p['when'])}"]
    if row.get("address"):
        lines.append(f"<b>Manzil:</b> {esc(row['address'])}")
    lines.append(f"<b>Kurs koordinatori:</b> {esc(p.get('coordinator_name') or '')}")
    if p.get("note"):
        lines.append(f"<b>Izoh:</b> {esc(p['note'])}")
    lines += ["", "Iltimos, shu vaqt sizga qulaymi — tasdiqlang yoki boshqa vaqt taklif qiling."]
    if p.get("student_deadline"):
        try:
            dl = datetime.fromisoformat(p["student_deadline"]).astimezone(TZ)
            lines.append(f"<i>Javob kutilmoqda: {dl.day}-{OYLAR[dl.month - 1]}, {dl:%H:%M} gacha.</i>")
        except ValueError:
            pass
    return "\n".join(lines)


async def _notify_students(bot, p: dict, again: bool = False) -> dict:
    """Talabalarga tashrif xabari; botga ulanmaganlari — koordinatorga shaxsiy havolalari bilan."""
    await _collapse(bot, p["id"], "talaba")
    sent, missed = 0, []
    for s in p["students"]:
        msg = await _send(bot, s.get("tg_id"), student_text(p, s, again), student_kb(p["id"], s["student_id"])) \
            if s.get("tg_id") else None
        if msg is not None:
            sent += 1
            await _remember(p["id"], "talaba", msg, s["student_id"])
            await _notified(p["id"], s["student_id"])
        else:
            missed.append(s)
    await _report_missed(bot, p, missed, "Shaxsiy havolani talabaga yuboring (u ochsa, tashrif so'rovi darhol keladi) "
                                         "yoki javobini o'zingiz panelda belgilang:")
    return {"sent": sent, "missed": len(missed), "missed_names": [s["full_name"] for s in missed]}


async def _notified(pid: int, sid: int) -> None:
    await db.execute("UPDATE visit_students SET notified_at = ? WHERE plan_id = ? AND student_id = ?", (now_iso(), pid, sid))


async def _report_missed(bot, p: dict, missed: list[dict], how: str) -> None:
    """Botga ulanmagan talabalar — koordinatorga, shaxsiy havolalari bilan."""
    if not missed or bot is None:
        return
    lines = [f"• {esc(s['full_name'])} — {await invite_url(bot, s['student_id'])}" for s in missed]
    text = (f"<b>⚠️ Botga ulanmagan talabalar — {len(missed)} ta</b>\n\n{esc(p['title'])} — {esc(p['when'])}\n\n"
            f"Quyidagilarga xabar yetmadi. {how}\n")
    for line in lines:  # butun guruhlar belgilanganda ro'yxat uzun — Telegram chegarasidan (4096) oshmasin
        if len(text) + len(line) > 3800:
            await _to_coordinator(bot, p, text)
            text = "<b>⚠️ Botga ulanmagan talabalar (davomi)</b>\n"
        text += "\n" + line
    await _to_coordinator(bot, p, text)


# ---------------------------------------------------------------- tadbir va madaniy tashrif ishtirokchilari
def _nom(p: dict) -> str:
    return TURLAR.get(p["type"], "Tadbir")


def _kun(d: str) -> str:
    """«bugun», «ertaga» yoki sana (eslatma sarlavhasi uchun)."""
    t = today()
    if d == t.isoformat():
        return "bugun"
    if d == (t + timedelta(days=1)).isoformat():
        return "ertaga"
    return when({"visit_date": d, "start_time": ""})


def event_text(p: dict, head: str, tail: str = "", short: bool = False) -> str:
    """Ishtirokchiga xabar: nomi, sanasi va vaqti, joyi (+ koordinator va izoh)."""
    lines = [head, "", f"<b>{esc(_nom(p))}:</b> {esc(p['title'])}", f"<b>Sana va vaqt:</b> {esc(when(p))}"]
    if p.get("place"):
        lines.append(f"<b>Joyi:</b> {esc(p['place'])}")
    if not short:
        lines.append(f"<b>Kurs koordinatori:</b> {esc(p.get('coordinator_name') or '')}")
        if p.get("note"):
            lines.append(f"<b>Izoh:</b> {esc(p['note'])}")
    if tail:
        lines += ["", tail]
    return "\n".join(lines)


def invite_text(p: dict) -> str:
    from tashrif.sozlama import sozlama
    icon = "🎭" if p["type"] == MADANIY else "🎉"
    return event_text(p, f"<b>{icon} Siz {_nom(p).lower()} ishtirokchilari ro'yxatiga kiritildingiz</b>",
                      "Belgilangan vaqtda yetib keling. " + ("Oldingi kuni va boshlanishidan oldin eslatma yuboriladi."
                                                             if sozlama.ertaga_soat is not None else
                                                             "Boshlanishidan oldin eslatma yuboriladi."))


async def _inform(bot, p: dict, rows: list[dict], quiet: bool = False) -> dict:
    """Ishtirokchilarga botda ma'lumot (javob so'ralmaydi); ulanmaganlari — koordinatorga havolalar bilan."""
    sent, missed = 0, []
    text = invite_text(p)
    for s in rows:
        msg = await _send(bot, s.get("tg_id"), text) if s.get("tg_id") else None
        if msg is not None:
            sent += 1
            await _notified(p["id"], s["student_id"])
        else:
            missed.append(s)
    if not quiet:
        await _report_missed(bot, p, missed, f"Shaxsiy havolani talabaga yuboring — ochsa, botga ulanadi va "
                                             f"{_nom(p).lower()} haqidagi xabar darhol keladi:")
    return {"sent": sent, "missed": len(missed), "missed_names": [s["full_name"] for s in missed]}


async def _to_coordinator(bot, p: dict, text: str, kb=None):
    return await _send(bot, p["coordinator_id"], text, kb)


async def _notify_answer(bot, p: dict, s: dict, resp: str) -> None:
    mark = {TASDIQLADI: "✅", VAQT_TAKLIF: "🕒"}.get(resp, "⚠️")
    if resp == VAQT_TAKLIF:
        line = f"Taklif qilgan vaqti: <b>{esc(when({'visit_date': s['proposed_date'], 'start_time': ''}))}" \
               f"{', ' + esc(s['proposed_time']) if s.get('proposed_time') else ''}</b>"
    else:
        line = f"Javob: <b>{esc(JAVOBLAR.get(resp, resp))}</b>"
    text = "\n".join([f"{mark} <b>{esc(s['full_name'])}</b> javob berdi", "", f"<b>Tashrif:</b> {esc(p['when'])}", line]
                     + ([f"Izoh: {esc(s['comment'])}"] if s.get("comment") else [])
                     + ["", f"Tasdiqlagan: {p['answers'][TASDIQLADI]}/{p['answers']['total']}"])
    kb = _kb([[("✅ Taklifni qabul qilish (vaqtni o'zgartirish)", cb("acc", p["id"], s["student_id"]))]]) \
        if resp == VAQT_TAKLIF else None
    msg = await _to_coordinator(bot, p, text, kb)
    if kb is not None:
        await _remember(p["id"], "taklif", msg, s["student_id"])
    if resp == TASDIQLADI:  # talaba «shu vaqtda uyda bo'laman» dedi — koordinatorga shu manzilga yo'l (faqat unga)
        await send_route(bot, p["coordinator_id"], p, [s])


# ---------------------------------------------------------------- eslatmalar (fon vazifasi)
async def reminders(bot) -> dict:
    """Joriy kurs: javob muddati o'tgan talabalarga eslatma (koordinatorga «shundayligicha tasdiqlash» tugmasi); tadbir va
    madaniy tashrif ishtirokchilariga oldingi kuni kechqurun (REMINDER_EVE_HOUR dan) eslatma; tashrifdan
    REMINDER_HOURS_BEFORE soat oldin talabalar va koordinatorga eslatma (+ ijara manziliga yo'l). Har biri bir marta."""
    from tashrif.sozlama import sozlama
    out = {"answer": 0, "visit": 0, "eve": 0}
    ts = now()
    for r in await db.fetchall("SELECT id, student_deadline FROM visit_plans WHERE status = ? AND student_deadline IS NOT NULL",
                               (TALABA,)):
        try:
            if datetime.fromisoformat(r["student_deadline"]) > ts:
                continue
        except ValueError:
            continue
        p = await get(r["id"], full=False)
        quiet = [s for s in p["students"] if s["response"] == KUTILMOQDA and not s["reminder_sent_at"]]
        if not quiet:
            continue
        for s in quiet:
            await db.execute("UPDATE visit_students SET reminder_sent_at = ? WHERE plan_id = ? AND student_id = ?",
                             (now_iso(), p["id"], s["student_id"]))
            msg = await _send(bot, s.get("tg_id"), f"<b>🔔 Javobingiz kutilmoqda</b>\n\n{esc(p['when'])} ga rejalashtirilgan "
                                                   "tashrifni tasdiqlashingiz yoki boshqa vaqt taklif qilishingiz kerak.",
                              student_kb(p["id"], s["student_id"])) if s.get("tg_id") else None
            await _remember(p["id"], "talaba", msg, s["student_id"])
        msg = await _to_coordinator(bot, p, f"<b>⚠️ Javob bermagan talabalar bor</b>\n\n{esc(p['title'])}\n{esc(p['when'])}\n\n"
                                            f"Javob bermaganlar: {esc(', '.join(s['full_name'] for s in quiet))}\n\n"
                                            "Ularga eslatma yuborildi. Rejani shundayligicha tasdiqlash yoki vaqtini o'zgartirish "
                                            "mumkin.",
                                    _kb([[("✅ Shundayligicha tasdiqlash", cb("force", p["id"]))]]))
        await _remember(p["id"], "uzatish", msg)
        out["answer"] += len(quiet)
    eve = sozlama.ertaga_soat
    if eve is not None and ts.hour >= eve:  # ertangi tadbirlar — kechqurun bir marta
        tom = (ts.date() + timedelta(days=1)).isoformat()
        for r in await db.fetchall(
                f"""SELECT id FROM visit_plans WHERE status = ? AND visit_date = ? AND eve_reminded_at IS NULL
                    AND type IN ({','.join('?' * len(ISHTIROK))})""", (TASDIQLANGAN, tom, *ISHTIROK)):
            await db.execute("UPDATE visit_plans SET eve_reminded_at = ? WHERE id = ?", (now_iso(), r["id"]))
            p = await get(r["id"], full=False)
            text = event_text(p, f"<b>⏰ Eslatma: ertaga — {_nom(p).lower()}</b>", "Vaqtida yetib kelishni rejalashtiring.")
            for s in p["students"]:
                if s.get("tg_id") and not _fresh(s.get("notified_at"), ts, 3):
                    out["eve"] += bool(await _send(bot, s["tg_id"], text))
    edge = ts + timedelta(hours=sozlama.eslatma_soat)
    for r in await db.fetchall("SELECT id, visit_date, start_time FROM visit_plans WHERE status = ? AND reminded_at IS NULL",
                               (TASDIQLANGAN,)):
        at = _local(r["visit_date"], r["start_time"])
        if at > edge or at < ts:
            continue
        await db.execute("UPDATE visit_plans SET reminded_at = ? WHERE id = ?", (now_iso(), r["id"]))
        p = await get(r["id"], full=False)
        kun = _kun(p["visit_date"])
        for s in p["students"]:
            if not s.get("tg_id") or s["response"] == RAD_ETDI:
                continue
            if p["type"] in ISHTIROK:
                if not _fresh(s.get("notified_at"), ts, 1):  # xabar hozirgina borgan bo'lsa — takrorlanmaydi
                    await _send(bot, s["tg_id"], event_text(p, f"<b>⏰ Eslatma: {kun} — {_nom(p).lower()}</b>",
                                                            "Kechikmasdan yetib keling.", short=True))
            else:
                await _send(bot, s["tg_id"], f"<b>⏰ Eslatma: {kun} tashrif bor</b>\n\n<b>Vaqt:</b> {p['start_time']}–"
                                             f"{p['end_time']}\n" + (f"<b>Manzil:</b> {esc(s['address'])}\n" if s.get("address") else "")
                            + f"<b>Kurs koordinatori:</b> {esc(p.get('coordinator_name') or '')}")
        await _to_coordinator(bot, p, f"<b>⏰ {kun.capitalize() if kun in ('bugun', 'ertaga') else 'Yaqinlashayotgan'}: "
                                      f"{esc(_nom(p).lower())}</b>\n\n{esc(p['title'])}\n{esc(p['when'])}"
                                      + (f"\nTalabalar: {p['answers']['total']} ta" if p["students"] else ""))
        if p["type"] == IJARA:
            await send_route(bot, p["coordinator_id"], p, [s for s in p["students"] if s["response"] != RAD_ETDI])
        out["visit"] += 1
    return out


def _fresh(iso: str | None, ts: datetime, hours: float) -> bool:
    """Xabar oxirgi `hours` soat ichida yuborilganmi (eslatma takrorlanmasin)."""
    try:
        return bool(iso) and ts - datetime.fromisoformat(iso) < timedelta(hours=hours)
    except ValueError:
        return False


async def loop(bot) -> None:
    """Har 5 daqiqada: barcha kurslar bo'yicha eslatmalar."""
    await asyncio.sleep(20)
    while True:
        for key in db.keys():
            try:
                with use_course(key):
                    n = await reminders(bot)
                if n["answer"] or n["visit"] or n["eve"]:
                    log.info("[%s] Tashrif eslatmalari: javob %s, tashrif %s, ertangi tadbir %s", key, n["answer"],
                             n["visit"], n["eve"])
            except Exception:  # noqa: BLE001  (sikl to'xtab qolmasligi kerak)
                log.exception("Tashrif eslatmalari (%s)", key)
        await asyncio.sleep(300)


# ---------------------------------------------------------------- yo'l ma'lumoti (faqat koordinatorga)
def _geo_on() -> bool:
    from tashrif.sozlama import sozlama
    return sozlama.yol_malumoti


def _wake_geo() -> None:
    try:
        from tashrif import yol
        yol.uygot()
    except Exception:  # noqa: BLE001
        pass


def _all_addresses() -> list[str]:
    """Yo'l modulining fon oqimi uchun: barcha kurslardagi talabalar manzillari va yaqin tashriflar manzillari
    (oqimda — oddiy sqlite3 bilan, faqat o'qish)."""
    out: list[str] = []
    for key in db.keys():
        path = Path(DATA_DIR) / key / "bot.db"
        if not path.exists():
            continue
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5) as c:
                out += [r[0] for r in c.execute(
                    "SELECT DISTINCT address FROM students WHERE address IS NOT NULL AND TRIM(address) <> '' "
                    "AND COALESCE(living, 'ijara') = 'ijara'")]
                out += [r[0] for r in c.execute(
                    """SELECT DISTINCT vs.address FROM visit_students vs JOIN visit_plans p ON p.id = vs.plan_id
                       WHERE vs.address IS NOT NULL AND TRIM(vs.address) <> '' AND p.visit_date >= ?""",
                    (today().isoformat(),))]
        except sqlite3.Error:
            log.warning("Manzillar o'qilmadi: %s", key)
    return out


def start_geo() -> None:
    """Bot ishga tushganda: manzillarni xaritadan aniqlash va bekatlar (fon oqimlari)."""
    from tashrif import yol
    yol.manzillar_manbai = _all_addresses
    yol.ulan()
    yol.boshla()


def _point(s: dict) -> dict:
    return {"id": s.get("student_id") or s.get("id"), "full_name": s["full_name"], "address": s.get("address") or "",
            "lat": s.get("lat"), "lon": s.get("lon")}


async def route_rows(students: list[dict], here: tuple[float, float] | None = None) -> list[dict]:
    """Har bir talaba manzili bo'yicha yo'l (bekatlar, metro, havolalar; turgan joy bo'lsa — yo'nalish).
    Tarmoqqa chiqmaydi — saqlangan natija va shahar nusxasidan (aniqlanmagan manzil navbatga qo'yiladi)."""
    from tashrif import yol

    def work():
        out = []
        for s in students:
            q = yol.qator(s["full_name"], s.get("address") or "", s.get("id"))
            if s.get("lat") is not None and s.get("lon") is not None:
                addr = (s.get("address") or "").strip() or yol.nuqta_manzili(s["lat"], s["lon"])
                yol.joy_belgila(addr, s["lat"], s["lon"])
                q = yol.qator(s["full_name"], addr, s.get("id"))
            joy = q["yol"]
            if here and joy and joy.get("lat") is not None:
                pt = (joy["lat"], joy["lon"])
                q["yonalish"] = yol.yonalish(here, pt)
                q["xarita"] = yol.yonalish_havolasi(here, pt)
                q["taksi"] = yol.taksi_havolasi(*pt, boshi=here)
            elif joy is None and q["manzil"]:
                yol.uygot()
            out.append(q)
        return out
    return await asyncio.to_thread(work)


def _dist(m) -> str:
    m = int(m or 0)
    return f"{max(10, round(m / 10) * 10)} m" if m < 1000 else f"{m / 1000:.1f}".replace(".", ",") + " km"


def _walk(m) -> str:
    return f"{max(1, round(int(m or 0) * 1.3 / 80))} daqiqa piyoda"


def route_text(title: str, rows: list[dict], here: bool = False) -> str:
    """Botdagi «Qanday boriladi» / «Turgan joyingizdan yo'l» xabari (tashrif-py texts.py)."""
    lines = ["<b>🧭 Turgan joyingizdan yo'l</b>" if here else "<b>🚌 Qanday boriladi</b>"] + ([esc(title)] if title else [])
    for q in rows:
        short = " ".join((q["ism"] or "").split()[:2])
        lines += ["", f"<b>{esc(short or 'Manzil')}</b> — {esc(q.get('korinish') or q['manzil'] or 'manzil kiritilmagan')}"]
        if not q["manzil"]:
            continue
        y = q.get("yol")
        if y is None:
            lines.append("   ⏳ Xaritadan aniqlanmoqda — birozdan keyin /yol yuboring.")
            continue
        if y.get("lat") is None:
            lines.append("   ❔ Xarita bu manzilni topa olmadi — talaba kartasida joylashuvini ko'rsating (panelda).")
            continue
        if y.get("aniqlik") == "taxminiy":
            lines.append("   <i>Uy xaritada topilmadi — joy taxminiy.</i>")
        if here and q.get("yonalish"):
            yn = q["yonalish"]
            lines.append(f"   Masofa: {_dist(yn['masofa'])}")
            for t in yn.get("togri") or []:
                lines.append(f"   🚌 <b>{esc(', '.join(t['raqamlar']))}</b>-avtobus: «{esc(t['chiqish']['nom'])}» bekatidan "
                             f"(sizdan {_dist(t['chiqish']['masofa'])}) → «{esc(t['tushish']['nom'])}» bekatigacha "
                             f"(manzilgacha {_dist(t['tushish']['masofa'])})")
            if yn.get("metro"):
                m = yn["metro"]
                lines.append(f"   🚇 Metro: «{esc(m['chiqish']['nom'])}» (sizdan {_dist(m['chiqish']['masofa'])}) → "
                             f"«{esc(m['tushish']['nom'])}» (manzilgacha {_dist(m['tushish']['masofa'])})")
            if not yn.get("togri"):
                for a in yn.get("almashish") or []:
                    lines.append(f"   🔁 Almashish bilan: <b>{esc(a['birinchi'])}</b>-avtobus «{esc(a['chiqish']['nom'])}» → "
                                 f"«{esc(a['bekat'])}» da <b>{esc(a['ikkinchi'])}</b> ga o'ting → «{esc(a['tushish']['nom'])}»")
            if yn["masofa"] <= 1200:
                lines.append(f"   🚶 Piyoda ham bo'ladi: {_walk(yn['masofa'])}")
            continue
        stops = y.get("bekatlar") or []
        pick = [b for b in stops if b.get("raqamlar")][:3] or stops[:2]
        for b in pick:
            lines.append(f"   🚏 {esc(b.get('nom') or 'Bekat')} — {_dist(b['masofa'])}, {_walk(b['masofa'])}"
                         + (f"\n        avtobuslar: <b>{esc(', '.join(b['raqamlar'][:14]))}</b>" if b.get("raqamlar") else ""))
        for m in (y.get("metro") or [])[:1]:
            lines.append(f"   🚇 {esc(m['nom'])} metro bekati — {_dist(m['masofa'])}")
        if not pick and not y.get("metro"):
            lines.append("   Yaqin atrofda bekat topilmadi — xaritadan qarang.")
    lines += ["", "<i>Bekatlar OpenStreetMap ma'lumoti bo'yicha; masofa to'g'ri chiziqda. Aniq yo'l — tugma orqali.</i>"]
    return "\n".join(lines)


def route_kb(rows: list[dict]):
    btn = []
    for q in rows[:6]:
        short = " ".join((q["ism"] or "").split()[:2]) or "Manzil"
        line = []
        if q.get("xarita"):
            line.append((f"🗺 {short} — yo'l"[:60], q["xarita"]))
        elif q.get("qidiruv"):
            line.append((f"🔎 {short} — xaritada"[:60], q["qidiruv"]))
        if q.get("taksi"):
            line.append(("🚕 Yandex Go", q["taksi"]))
        btn.append(line)
    return _kb(btn) if any(btn) else None


async def send_route(bot, chat_id: int, p: dict, students: list[dict], here: tuple[float, float] | None = None) -> bool:
    """«Qanday boriladi» — faqat kurs koordinatoriga (talabaga hech qachon)."""
    if bot is None or not chat_id or not _geo_on() or p.get("type") != IJARA:
        return False
    rows = [q for q in await route_rows([_point(s) for s in students if (s.get("address") or s.get("lat") is not None)],
                                        here) if q["manzil"]]
    if not rows:
        return False
    for i in range(0, len(rows), 5):
        part = rows[i:i + 5]
        await _send(bot, chat_id, route_text(when(p) if i == 0 else "", part, here=bool(here)), route_kb(part))
    return True


async def upcoming_for_route(uid: int, days: int = 2) -> list[dict]:
    """/yol: koordinatorning yaqin kunlardagi (bugun va ertaga) ijara tashriflari."""
    t = today()
    rows = await plans(uid, frm=t.isoformat(), to=(t + timedelta(days=days - 1)).isoformat())
    return [await get(r["id"], full=False) for r in rows
            if r["type"] == IJARA and r["status"] in (TALABA, TASDIQLANGAN) and r["coordinator_id"] == uid]


# ---------------------------------------------------------------- talabaning yashash joyi
def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


async def set_home(sid: int, d: dict) -> dict:
    """Talaba kartasi: yashash turi, xonadon toifasi (qo'lda), ijara manzili va xaritadagi nuqta.
    Joylashuv koordinata, xarita havolasi (qisqa havola ham) yoki xaritadan tanlangan nuqta bo'lishi mumkin."""
    st = await db.get_student(sid)
    if not st:
        raise VisitError("not_found", "Talaba topilmadi")
    sets: dict = {}
    if "living" in d:
        sets["living"] = d["living"] if d["living"] in LIVING else None
    if "zone" in d:
        sets["zone"] = d["zone"] if d["zone"] in ZONES else None
    if "address" in d:
        sets["address"] = (d.get("address") or "").strip()[:300] or None
    if "location" in d:
        txt = (d.get("location") or "").strip()
        if not txt:
            sets["lat"] = sets["lon"] = None
        else:
            from tashrif import yol
            pt = await asyncio.to_thread(yol.joyni_tani, txt)
            if not pt:
                raise VisitError("bad_location", "Joylashuvni tushunmadim: koordinata (41.3418, 69.2879) yoki xarita havolasini "
                                                 "kiriting")
            sets["lat"], sets["lon"] = pt
    elif "lat" in d or "lon" in d:
        lat, lon = _num(d.get("lat")), _num(d.get("lon"))
        if (lat is None) != (lon is None) or (lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180)):
            raise VisitError("bad_location", "Koordinata noto'g'ri")
        sets["lat"], sets["lon"] = lat, lon
    if sets:
        await db.execute(f"UPDATE students SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), sid))
    st = await db.get_student(sid)
    if ("lat" in sets or "address" in sets) and _geo_on():
        from tashrif import yol
        if st.get("lat") is not None:
            await asyncio.to_thread(yol.joy_belgila, st.get("address") or "", st["lat"], st["lon"])
        _wake_geo()
    out = await student_visits(sid)
    if st.get("lat") is not None:
        out["near"] = await asyncio.to_thread(_nearest_stop, st["lat"], st["lon"])
    return out


def _nearest_stop(lat: float, lon: float) -> str:
    """Kiritilgan joy noto'g'ri joyga tushmaganini ko'rish uchun: eng yaqin bekat nomi."""
    from tashrif import yol
    try:
        b = (yol._mahalliy(lat, lon) or {}).get("bekatlar") or []
        return f"{b[0]['nom']} bekati yaqinida" if b and b[0].get("nom") else ""
    except Exception:  # noqa: BLE001
        return ""


async def student_route(sid: int, here: tuple[float, float] | None = None) -> dict:
    """Panel: «Qanday boriladi» — xaritada chizish uchun bekat va metro koordinatalari bilan (tashrif-py talaba_yoli)."""
    st = await db.get_student(sid)
    if not st:
        raise VisitError("not_found", "Talaba topilmadi")
    if not _geo_on():
        raise VisitError("geo_off", "Yo'l ma'lumoti o'chirilgan (YOL_MALUMOTI=yoq)")
    from tashrif import yol
    return await asyncio.to_thread(yol.talaba_yoli, {"id": st["id"], "full_name": st["full_name"],
                                                     "address": st.get("address") or "", "lat": st.get("lat"),
                                                     "lon": st.get("lon")}, here)


async def plan_route(pid: int, here: tuple[float, float] | None = None) -> dict:
    """Panel: rejadagi barcha talabalar manzili bo'yicha «Qanday boriladi» (xarita uchun koordinatalar bilan)."""
    if not _geo_on():
        raise VisitError("geo_off", "Yo'l ma'lumoti o'chirilgan (YOL_MALUMOTI=yoq)")
    p = await get(pid, full=False)
    from tashrif import yol

    def work():
        return [yol.talaba_yoli({"id": s["student_id"], "full_name": s["full_name"], "address": s.get("address") or "",
                                 "lat": s.get("lat"), "lon": s.get("lon")}, here) for s in p["students"]]
    return {"talabalar": await asyncio.to_thread(work),
            "turgan_joy": {"lat": here[0], "lon": here[1]} if here else None}


# ---------------------------------------------------------------- dashboard: talabalar qayerda yashaydi
async def dashboard(scope: set[str] | None) -> dict:
    """Ko'rsatkichlar (yashash turi, xonadon toifasi), xaritadagi nuqtalar, tumanlar va xonadonlar kesimi.
    Tarmoqdan hech narsa so'ralmaydi (tashrif-py panel.py)."""
    from tashrif import tuman, yol
    rows = [r for r in await db.fetchall("SELECT id, full_name, group_name, group_key, address, lat, lon, living, zone "
                                          "FROM students ORDER BY full_name")
            if scope is None or r["group_key"] in scope]
    acts = {}
    for a in await db.fetchall("SELECT student_id, category, plan_id, updated_at FROM visit_acts WHERE category IS NOT NULL "
                               "AND student_id IS NOT NULL ORDER BY updated_at"):
        acts[a["student_id"]] = a["category"]  # eng so'nggisi
    geo_on = _geo_on()

    def work():
        saved = yol.joylar() if geo_on else {}
        out = []
        for s in rows:
            addr = (s.get("address") or "").strip()
            living = s.get("living") or ("ijara" if addr else None)
            if s.get("lat") is not None and s.get("lon") is not None:
                joy = {"lat": s["lat"], "lon": s["lon"], "aniqlik": "aniq", "holat": "ok"}
            elif not addr:
                joy = {"holat": "manzilsiz"}
            else:
                pt = yol.koordinata_matndan(addr)
                q = saved.get(yol.kalit(addr)) if not pt else None
                if pt:
                    joy = {"lat": pt[0], "lon": pt[1], "aniqlik": "aniq", "holat": "ok"}
                elif q and q["lat"] is not None:
                    joy = {"lat": q["lat"], "lon": q["lon"], "aniqlik": q["aniqlik"] or "taxminiy", "holat": "ok"}
                else:
                    joy = {"holat": "topilmadi" if (q and q["holat"] == "topilmadi") or not geo_on else "navbatda"}
            bino, xon = yol.manzil_kaliti(addr)
            if not bino and "lat" in joy:
                bino = f"n:{joy['lat']:.5f},{joy['lon']:.5f}"
            tn = tuman.top(joy["lat"], joy["lon"]) if "lat" in joy else ""
            if not tn and addr:
                written = yol.tahlil(addr)["tuman"]
                tn = next((n for n in tuman.nomlar() if written and yol._tuman_bir(written, n)), "") or \
                    (yol._tuman_lotincha(written) if written else "")
            out.append({"id": s["id"], "name": s["full_name"], "group": s.get("group_name") or "", "address": addr,
                         "living": living, "zone": acts.get(s["id"]) or s.get("zone"),
                         "zone_from": "act" if s["id"] in acts else ("manual" if s.get("zone") else None),
                         **joy, "tuman": tn or "", "bino": bino, "xonadon": f"{bino}#{xon}" if bino else ""})
        return out
    items = await asyncio.to_thread(work)
    from tashrif.sozlama import sozlama
    living = {k: sum(1 for x in items if x["living"] == k) for k in LIVING}
    rent = [x for x in items if x["living"] == "ijara"]
    flats: dict[str, list] = {}
    for x in rent:
        if x["xonadon"]:
            flats.setdefault(x["xonadon"], []).append(x)
    zones = {z: {"students": sum(1 for x in rent if x["zone"] == z),
                 "flats": sum(1 for v in flats.values() if any(x["zone"] == z for x in v))} for z in ZONES}
    zones["none"] = {"students": sum(1 for x in rent if not x["zone"]),
                     "flats": sum(1 for v in flats.values() if not any(x["zone"] for x in v))}
    districts: dict[str, dict] = {}
    for x in rent:
        d = districts.setdefault(x["tuman"] or "—", {"name": x["tuman"] or "—", "students": 0, "flats": set(),
                                                    **{z: 0 for z in ZONES}})
        d["students"] += 1
        if x["xonadon"]:
            d["flats"].add(x["xonadon"])
        if x["zone"]:
            d[x["zone"]] += 1
    dist = sorted(({**v, "flats": len(v["flats"])} for v in districts.values()), key=lambda v: -v["students"])
    by_size: dict[int, int] = {}
    for v in flats.values():
        by_size[len(v)] = by_size.get(len(v), 0) + 1
    return {"total": len(items), "living": living, "unknown": sum(1 for x in items if not x["living"]),
            "zones": zones, "flats": len(flats), "by_size": sorted(by_size.items()),
            "located": sum(1 for x in rent if "lat" in x), "queue": sum(1 for x in rent if x["holat"] == "navbatda"),
            "not_found": sum(1 for x in rent if x["holat"] == "topilmadi"),
            "no_address": sum(1 for x in rent if x["holat"] == "manzilsiz"),
            "items": items, "districts": dist, "center": list(sozlama.geo_markaz), "geo": geo_on}


async def district_shapes() -> list[dict]:
    """Xarita uchun tuman chegaralari (dastur bilan kelgan, soddalashtirilgan)."""
    from tashrif import tuman
    return await asyncio.to_thread(tuman.royxat)


# ---------------------------------------------------------------- dalolatnoma
def _act_row(a: dict) -> dict:
    try:
        data = json.loads(a.get("data") or "{}")
    except ValueError:
        data = {}
    return {"id": a["id"], "plan_id": a["plan_id"], "student_id": a["student_id"], "category": a.get("category"),
            "data": data, "docx": bool(a.get("docx_path")), "docx_at": a.get("docx_at"),
            "created_at": a["created_at"], "updated_at": a["updated_at"]}


def _clean_sig(s) -> dict | None:
    """Imzo — vektor ko'rinishida {w, h, d} (d: "x,y x,y;..."; eng uzun tomoni 1000) — tashrif-py sigPack."""
    if not isinstance(s, dict):
        return None
    d = str(s.get("d") or "")
    if not d or len(d) > 60000 or not re.fullmatch(r"[\d,; .\-]+", d):
        return None
    try:
        w, h = float(s.get("w") or 0), float(s.get("h") or 0)
    except (TypeError, ValueError):
        return None
    return {"w": w, "h": h, "d": d} if w > 0 and h > 0 else None


async def save_act(pid: int, d: dict, uid: int, act_id: int | None = None) -> dict:
    p = await _own(pid, uid)
    if p["type"] != IJARA:
        raise VisitError("not_rent", "Dalolatnoma faqat ijara xonadoniga tashrif uchun")
    if p["status"] not in (TASDIQLANGAN, BAJARILDI):
        raise VisitError("state", "Dalolatnoma tasdiqlangan (yoki o'tkazilgan) tashrif uchun to'ldiriladi")
    data = {k: str(d.get(k) or "").strip()[:2000] for k in ACT_TEXT}
    for k, opts in ACT_Q.items():
        data[k] = d.get(k) if d.get(k) in opts else ""
    for k in ("sigCoord", "sigStudent"):
        sig = _clean_sig(d.get(k))
        if sig:
            data[k] = sig
    sid = d.get("studentId")
    sid = int(sid) if str(sid or "").isdigit() and any(s["student_id"] == int(sid) for s in p["students"]) else None
    ts = now_iso()
    if act_id:
        old = await db.fetchone("SELECT * FROM visit_acts WHERE id = ? AND plan_id = ?", (act_id, pid))
        if not old:
            raise VisitError("not_found", "Dalolatnoma topilmadi")
        await db.execute("UPDATE visit_acts SET student_id = ?, data = ?, category = ?, updated_at = ? WHERE id = ?",
                         (sid, json.dumps(data, ensure_ascii=False), data["category"] or None, ts, act_id))
    else:
        act_id = await db.execute(
            "INSERT INTO visit_acts (plan_id, student_id, data, category, created_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (pid, sid, json.dumps(data, ensure_ascii=False), data["category"] or None,
                                             uid, ts, ts))
        await _log(pid, "koordinator", "dalolatnoma", uid, await staff_name(uid),
                   detail=data["fio"] or None)
    return _act_row(await db.fetchone("SELECT * FROM visit_acts WHERE id = ?", (act_id,)))


async def delete_act(act_id: int, uid: int) -> None:
    a = await db.fetchone("SELECT * FROM visit_acts WHERE id = ?", (act_id,))
    if not a:
        raise VisitError("not_found", "Dalolatnoma topilmadi")
    await _own(a["plan_id"], uid)
    _unlink(a.get("docx_path"))
    await db.execute("DELETE FROM visit_acts WHERE id = ?", (act_id,))


def _dir() -> Path:
    p = Path(DATA_DIR) / (current_course() or "_") / "tashrif"
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_path(rel: str | None) -> Path | None:
    if not rel:
        return None
    p = (Path(DATA_DIR) / (current_course() or "_") / rel).resolve()
    base = (Path(DATA_DIR) / (current_course() or "_")).resolve()
    return p if str(p).startswith(str(base)) and p.is_file() else None


def _unlink(rel: str | None) -> None:
    p = file_path(rel)
    if p:
        p.unlink(missing_ok=True)


async def store_act_docx(act_id: int, data: bytes, uid: int) -> dict:
    """Panelda yasalgan Word fayl (imzolar bilan) — talabaning hujjati sifatida saqlanadi."""
    a = await db.fetchone("SELECT * FROM visit_acts WHERE id = ?", (act_id,))
    if not a:
        raise VisitError("not_found", "Dalolatnoma topilmadi")
    await _own(a["plan_id"], uid)
    if not data.startswith(b"PK") or len(data) > 25 * 1024 * 1024:
        raise VisitError("bad_file", "Word fayl emas")
    _unlink(a.get("docx_path"))
    name = f"dalolatnoma_{act_id}_{secrets.token_hex(6)}.docx"
    (_dir() / name).write_bytes(data)
    await db.execute("UPDATE visit_acts SET docx_path = ?, docx_at = ? WHERE id = ?", (f"tashrif/{name}", now_iso(), act_id))
    return _act_row(await db.fetchone("SELECT * FROM visit_acts WHERE id = ?", (act_id,)))


PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


async def add_photo(pid: int, name: str, mime: str, data: bytes, uid: int, act_id: int | None = None) -> dict:
    p = await _own(pid, uid)
    if mime not in PHOTO_TYPES:
        raise VisitError("bad_file", "Faqat JPG, PNG yoki WEBP surat")
    if len(data) > 16 * 1024 * 1024:
        raise VisitError("too_big", "Surat 16 MB dan katta")
    if act_id and not await db.fetchone("SELECT 1 FROM visit_acts WHERE id = ? AND plan_id = ?", (act_id, pid)):
        act_id = None
    fn = f"rasm_{secrets.token_hex(16)}{PHOTO_TYPES[mime]}"
    (_dir() / fn).write_bytes(data)
    fid = await db.execute("INSERT INTO visit_photos (plan_id, act_id, name, path, size, mime, uploaded_by, created_at) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (p["id"], act_id, (name or "rasm")[:120], f"tashrif/{fn}", len(data), mime, uid, now_iso()))
    return await db.fetchone("SELECT id, act_id, name, size, mime, created_at FROM visit_photos WHERE id = ?", (fid,))


async def photo(fid: int) -> dict | None:
    return await db.fetchone("SELECT * FROM visit_photos WHERE id = ?", (fid,))


async def delete_photo(fid: int, uid: int) -> None:
    f = await photo(fid)
    if not f:
        raise VisitError("not_found", "Surat topilmadi")
    await _own(f["plan_id"], uid)
    _unlink(f["path"])
    await db.execute("DELETE FROM visit_photos WHERE id = ?", (fid,))


# ---------------------------------------------------------------- hisobot
async def report(uid: int | None, frm: str, to: str) -> dict:
    """Hisobot: faqat tasdiqlangan va bajarilgan rejalar (aktual) — turlar, koordinatorlar, oylar, dalolatnomalar."""
    rows = [r for r in await plans(uid, frm=frm, to=to) if r["actual"]]
    by_type = {k: {"plans": sum(1 for r in rows if r["type"] == k), "done": sum(1 for r in rows if r["type"] == k
                                                                                and r["status"] == BAJARILDI)}
               for k in TURLAR}
    coords: dict[int, dict] = {}
    for r in rows:
        c = coords.setdefault(r["coordinator_id"], {"id": r["coordinator_id"], "name": r["coordinator_name"] or "",
                                                    "plans": 0, "done": 0, "students": 0, "acts": 0,
                                                    **{k: 0 for k in TURLAR}})
        c["plans"] += 1
        c[r["type"]] += 1
        c["done"] += r["status"] == BAJARILDI
        c["students"] += len(r["students"])
        c["acts"] += r["acts_n"]
    months: dict[str, dict] = {}
    for r in rows:
        m = months.setdefault(r["visit_date"][:7], {"month": r["visit_date"][:7], **{k: 0 for k in TURLAR}})
        m[r["type"]] += 1
    rent = [r for r in rows if r["type"] == IJARA]
    return {"from": frm, "to": to, "total": len(rows), "done": sum(1 for r in rows if r["status"] == BAJARILDI),
            "by_type": by_type, "coordinators": sorted(coords.values(), key=lambda c: -c["plans"]),
            "months": sorted(months.values(), key=lambda m: m["month"]),
            "students": len({s["student_id"] for r in rent for s in r["students"]}),
            "acts": sum(r["acts_n"] for r in rent), "items": rows}


# ---------------------------------------------------------------- talabalar ro'yxati (reja tuzish uchun)
async def pick_students(scope: set[str] | None, q: str = "") -> list[dict]:
    """Rejaga talaba tanlash (ijara tashrifi, tadbir, madaniy tashrif): guruhi, manzili, yashash turi, joyi va botga
    ulanganmi."""
    from utils import normalize_text
    rows = await db.fetchall(
        """SELECT s.id, s.full_name, s.name_norm, s.group_name, s.group_key, s.hemis_id, s.address, s.living, s.zone,
                  s.lat, s.lon, a.tg_id FROM students s LEFT JOIN student_accounts a ON a.student_id = s.id
           ORDER BY s.group_name, s.full_name""")
    qn = normalize_text(q)
    out = []
    for r in rows:
        if scope is not None and r["group_key"] not in scope:
            continue
        if qn and qn not in (r["name_norm"] or "") and qn not in normalize_text(r["address"] or "") \
                and qn != group_key(r["group_name"] or ""):
            continue
        out.append({"id": r["id"], "name": r["full_name"], "group": r["group_name"] or "", "hemis_id": r["hemis_id"],
                    "address": r["address"] or "", "living": r["living"] or ("ijara" if (r["address"] or "").strip() else None),
                    "zone": r["zone"], "located": r["lat"] is not None, "linked": bool(r["tg_id"])})
    return out

