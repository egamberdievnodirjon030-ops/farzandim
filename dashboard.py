"""Boshqaruv paneli bosh sahifasi — dekan (super-admin, barcha kurslar) va kurs koordinatori uchun umumiy qismlar:
bugungi vazifalar (chora bosqichlari, xatlar, xabarlar, so'rovlar, tashriflar), yaqin tadbir va tashriflar,
integratsiyalar holati (Manage, HEMIS fayllari, Telegram botlar). Hamma narsa — mavjud ma'lumotdan, qo'shimcha
kiritishsiz; vazifa bajarilgach o'zi yo'qoladi (soni 0)."""
from __future__ import annotations

import logging
from datetime import timedelta

import botlar
from database import db
from tenancy import central, use_course
from utils import today

log = logging.getLogger(__name__)

HEMIS_KINDS = ("attendance", "gpa", "acad_debts", "students", "grades")  # HEMIS dan olinadigan fayllar


def _task(key: str, title: str, n: int, href: str, hint: str = "", tone: str = "warn") -> dict:
    return {"key": key, "title": title, "n": int(n or 0), "href": href, "hint": hint, "tone": tone}


async def course_tasks(uid: int | None, scope: set[str] | None, unread: int, requests: int) -> list[dict]:
    """Kurs koordinatorining bugungi vazifalari (joriy kurs, o'z guruhlari)."""
    import discipline
    import visits
    try:
        ds = await discipline.panel_stats(scope)
    except Exception:  # noqa: BLE001  (bitta bo'lim xatosi butun sahifani to'xtatmasin)
        log.exception("Chora ko'rsatkichlari")
        ds = {"new": 0, "flow": {}}
    f = ds.get("flow") or {}
    try:
        vt = await visits.counts(uid)
    except Exception:  # noqa: BLE001
        log.exception("Tashrif ko'rsatkichlari")
        vt = {}
    return [
        _task("chora_new", "Chegaraga yetganlar — chora hujjatlarini tayyorlash", ds.get("new", 0), "#/chora",
              "davomat chegarasidan oshgan, hali hujjat tayyorlanmagan", "bad"),
        _task("chora_basis", "1-bosqich: imzolangan bildirishnomani (PDF) yuklash", f.get("basis", 0), "#/chora?tab=docs",
              "talaba"),
        _task("chora_order", "2-bosqich: imzolangan farmoyish / buyruqni (PDF) yuklash", f.get("order", 0),
              "#/chora?tab=docs", "talaba"),
        _task("letters", "Ota-onaga xatlarni yuborish", f.get("letters", 0), "#/chora?tab=docs", "chora chiqqan, xat hali yo'q"),
        _task("inbox", "Ota-onalar xabarlariga javob berish", unread, "#/inbox"),
        _task("requests", "Farzandni bog'lash so'rovlarini ko'rib chiqish", requests, "#/requests"),
        _task("acts", "Ijara tashrifi dalolatnomalarini to'ldirish", vt.get("need_act", 0), "#/tashrif"),
        _task("visit_answers", "Talaba javobini kutayotgan tashriflar", vt.get("students", 0), "#/tashrif", "", "info"),
        _task("selfdata", "Talabalar kiritgan ma'lumotlarni tekshirish", await _selfdata(), "#/selfdata",
              "yashash joyi va ijtimoiy toifa — talaba ilovasidan"),
    ]


async def _selfdata() -> int:
    import selfdata
    try:
        return await selfdata.pending_count()
    except Exception:  # noqa: BLE001
        log.exception("Talabalar kiritgan ma'lumotlar")
        return 0


async def events(uid: int | None, days: int = 14, limit: int = 6) -> list[dict]:
    """Yaqin tadbir va tashriflar (bugundan, bekor qilingan va qoralamalarsiz)."""
    import visits as V
    t = today()
    rows = await V.plans(uid, frm=t.isoformat(), to=(t + timedelta(days=days)).isoformat())
    out = []
    for r in rows:
        if r["status"] in (V.BEKOR, V.QORALAMA) or V.passed(r["visit_date"], r["end_time"]):
            continue
        n = len(r.get("students") or [])
        cap = r.get("capacity") if r.get("announce") else None
        out.append({"id": r["id"], "type": r["type"], "type_title": r["type_title"], "title": r["title"],
                    "date": r["visit_date"], "start": r["start_time"], "end": r["end_time"], "place": r.get("place") or "",
                    "students": n, "capacity": cap, "groups": len({s.get("group_name") for s in r.get("students") or []}),
                    "status": r["status"]})
        if len(out) >= limit:
            break
    return out


async def _imports_last(kinds: tuple[str, ...]) -> str:
    qm = ",".join("?" * len(kinds))
    r = await db.fetchone(f"SELECT MAX(uploaded_at) AS v FROM imports WHERE deleted_at IS NULL AND kind IN ({qm})", kinds)
    return (r or {}).get("v") or ""


async def integrations(bot, keys: list[str] | None = None) -> list[dict]:
    """Integratsiyalar holati: Manage (avtomatik davomat va jadval), HEMIS fayllari (oxirgi yuklash), Telegram botlar.
    keys — kurslar (dekan uchun barchasi); None — joriy kurs."""
    import integration as I
    out = []
    if I.configured() or I.INTEGRATION_WEBHOOK_SECRET:
        last = max([await central.get_meta(f"integ_last_ok_{k}") or "" for k in I.KINDS] or [""])
        errs = [I.STATE[k].get("error") for k in I.KINDS if (I.STATE.get(k) or {}).get("error")]
        dead = [I.TITLES[k] for k in I.KINDS if I.dead(k)]
        out.append({"key": "manage", "title": I.INTEGRATION_NAME or "Manage", "state": "warn" if errs or dead else "ok" if last else "wait",
                    "at": last, "text": (errs[0] if errs else f"o'chirilgan: {', '.join(dead)}" if dead else
                                         "davomat va jadval avtomatik" if last else "birinchi sinxron kutilmoqda")[:160]})
    else:
        out.append({"key": "manage", "title": "Manage", "state": "off", "at": "", "text": "sozlanmagan — davomat Excel orqali"})
    last = ""
    for k in (keys if keys is not None else [None]):
        if k is None:
            last = max(last, await _imports_last(HEMIS_KINDS))
        else:
            with use_course(None if k == "_" else k):
                last = max(last, await _imports_last(HEMIS_KINDS))
    out.append({"key": "hemis", "title": "HEMIS (fayllar)", "state": "ok" if last else "off", "at": last,
                "text": "oxirgi yuklash" if last else "hali yuklanmagan"})
    names, ok = [], True
    for label, b in (("ota-onalar", botlar.main_bot(bot)), ("talabalar", botlar.student_bot(bot) if botlar.separate() else None)):
        if b is None:
            continue
        try:
            names.append(f"{label}: @{(await b.me()).username}")
        except Exception:  # noqa: BLE001  (Telegram javob bermadi — holatda ko'rinadi)
            ok = False
            names.append(f"{label}: javob yo'q")
    out.append({"key": "telegram", "title": "Telegram (bildirishnoma)", "state": "ok" if ok and names else "warn",
                "at": "", "text": ", ".join(names) or "bot sozlanmagan"})
    return out


def groups_breakdown(rows: list[dict]) -> list[dict]:
    """Guruhlar kesimida: talabalar, muammolilar, o'rtacha davomat, chora ko'rilganlar."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r.get("group") or "—", []).append(r)
    out = []
    for g, rs in by.items():
        pc = [r["percent"] for r in rs if r.get("percent") is not None]
        out.append({"group": g, "total": len(rs), "prob": sum(1 for r in rs if r["problems"]),
                    "att": round(sum(pc) / len(pc), 1) if pc else None,
                    "chora": sum(1 for r in rs if r.get("measures")), "handled": sum(1 for r in rs if r.get("handled"))})
    return sorted(out, key=lambda x: (-x["prob"], x["group"]))


def problems_mix(rows: list[dict]) -> dict:
    """Muammolar tarkibi: har bir tur bo'yicha talabalar soni (bir talabada bir nechtasi bo'lishi mumkin)."""
    keys = ("att", "acad", "gpa", "kontrakt", "trimestr")
    return {"students": sum(1 for r in rows if r["problems"]), **{k: sum(1 for r in rows if r["flags"].get(k)) for k in keys},
            "multi": sum(1 for r in rows if r["problems"] >= 3)}
