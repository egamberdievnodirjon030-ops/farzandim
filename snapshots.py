"""Dinamika uchun holat nuqtalari: har bir fayl yuklangandan keyin (davomat, baholar, akademik qarzdorlar,
buxgalteriya hisoboti…) har bir talabaning ko'rsatkichlari yoziladi — faqat oldingisidan farq qilsa.

Bir kunda bir necha yuklash bo'lsa — o'sha kunning nuqtasi yangilanadi (kunlik yoki haftalik yuklash — bitta nuqta);
qiymat oldingi kundagiga qaytsa — o'sha kunning nuqtasi o'chiriladi (o'zgarish yo'q). Shuning uchun dinamikada
faqat haqiqatan o'zgargan ko'rsatkichlar ko'rinadi.
"""
from __future__ import annotations

import logging

import status
from database import db
from utils import today

log = logging.getLogger("snapshots")

# ko'rsatkich → (sarlavha, birlik, yaxshi yo'nalish)
METRICS = {
    "att_pct": ("Davomat", "%", "up"),
    "att_hours": ("Sababsiz qoldirilgan", "pairs", "down"),
    "acad": ("Akademik qarzdorlik", "subjects", "down"),
    "kontrakt": ("Kontrakt qarzi", "money", "down"),
    "trimestr": ("Trimestr qarzi", "money", "down"),
    "gpa": ("GPA", "gpa", "up"),
}


def values(x: dict) -> dict[str, float]:
    """Talaba holatidan (status.build) yoziladigan qiymatlar; ma'lumot yo'q ko'rsatkich — yozilmaydi."""
    out: dict[str, float] = {}
    a = x.get("attendance")
    if a:
        if a.get("percent") is not None:
            out["att_pct"] = round(a["percent"], 1)
        out["att_hours"] = round(a["counted"] or 0, 1)
    if x["results"] or x["debts"]:
        out["acad"] = float(len(x["debts"]))
    for k in ("kontrakt", "trimestr"):
        p = x["pays"].get(k)
        if p is not None and not (k == "kontrakt" and (x["student"].get("payment_form") or "").lower().startswith("davlat")):
            out[k] = float(round(p["debt"] or 0))
    if x.get("gpa") is not None:
        out["gpa"] = round(x["gpa"], 4)
    return out


async def capture() -> int:
    """Joriy kursning barcha talabalari holatini yozadi (o'zgarganlarini). Qaytaradi: yozilgan/yangilangan nuqtalar."""
    students = await db.fetchall("SELECT * FROM students")
    if not students:
        return 0
    day = today().isoformat()
    last: dict[tuple, list[dict]] = {}
    for r in await db.fetchall("SELECT id, student_id, metric, value, day FROM snapshots ORDER BY id"):
        h = last.setdefault((r["student_id"], r["metric"]), [])
        h.append(r)
        if len(h) > 2:
            h.pop(0)
    n = 0
    for x in await status.all_statuses(students):
        sid = x["student"]["id"]
        for m, v in values(x).items():
            h = last.get((sid, m), [])
            cur = h[-1] if h else None
            if cur and abs(cur["value"] - v) < 1e-6:
                continue
            if cur and cur["day"] == day:  # bugungi nuqta — yangilanadi
                prev = h[-2] if len(h) > 1 else None
                if prev and abs(prev["value"] - v) < 1e-6:
                    await db.conn.execute("DELETE FROM snapshots WHERE id = ?", (cur["id"],))  # o'zgarish bekor bo'ldi
                else:
                    await db.conn.execute("UPDATE snapshots SET value = ? WHERE id = ?", (v, cur["id"]))
            else:
                await db.conn.execute("INSERT INTO snapshots (student_id, metric, value, day) VALUES (?, ?, ?, ?)",
                                      (sid, m, v, day))
            n += 1
    await db.conn.commit()
    return n


async def history(sid: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in await db.fetchall("SELECT metric, value, day FROM snapshots WHERE student_id = ? ORDER BY id", (sid,)):
        out.setdefault(r["metric"], []).append(r)
    return out
