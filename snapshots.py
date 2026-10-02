"""Dinamika uchun holat nuqtalari: har bir fayl yuklangandan keyin (davomat, baholar, akademik qarzdorlar,
buxgalteriya hisoboti…) har bir talabaning ko'rsatkichlari yoziladi — faqat oldingisidan farq qilsa.

Har bir yuklash — alohida nuqta (bir kunda bir nechta bo'lsa ham; vaqti bilan yoziladi). Qiymat o'zgarmagan bo'lsa
nuqta yozilmaydi, shuning uchun dinamikada faqat haqiqatan o'zgargan ko'rsatkichlar ko'rinadi.

Davomat ikki manbadan: «Davomat» va «Sababsiz qoldirilgan» — umumiy holat (HEMIS statistikasi bo'lsa — undan,
aks holda kunlik davomatdan); HEMIS bilan birga kunlik davomat ham yuklansa — «kunlik» ko'rsatkichlar alohida
(kunlik fayl yuklanganda ham o'zgarish ko'rinsin).
"""
from __future__ import annotations

import logging

import absence
import status
from database import db
from utils import now_iso, semester_start, today

log = logging.getLogger("snapshots")

# ko'rsatkich → (sarlavha, birlik, yaxshi yo'nalish)
METRICS = {
    "att_pct": ("Davomat", "%", "up"),
    "att_hours": ("Sababsiz qoldirilgan", "pairs", "down"),
    "day_pct": ("Davomat (kunlik)", "%", "up"),
    "day_hours": ("Sababsiz qoldirilgan (kunlik)", "pairs", "down"),
    "acad": ("Akademik qarzdorlik", "subjects", "down"),
    "kontrakt": ("Kontrakt qarzi", "money", "down"),
    "trimestr": ("Trimestr qarzi", "money", "down"),
    "gpa": ("GPA", "gpa", "up"),
}


def values(x: dict, daily: dict | None = None) -> dict[str, float]:
    """Talaba holatidan (status.build) yoziladigan qiymatlar; ma'lumot yo'q ko'rsatkich — yozilmaydi.
    daily — kunlik davomat yig'indisi (HEMIS statistikasi ham bo'lsa, kunlik ko'rsatkichlar alohida yoziladi)."""
    out: dict[str, float] = {}
    a = x.get("attendance")
    if a:
        if a.get("percent") is not None:
            out["att_pct"] = round(a["percent"], 1)
        out["att_hours"] = round(a["counted"] or 0, 1)
    if a and a.get("source") == "hemis" and daily and daily.get("total"):
        d = absence.summary_from(None, daily)
        out["day_pct"] = round(d["percent"], 1)
        out["day_hours"] = round(d["counted"] or 0, 1)
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
    """Joriy kursning barcha talabalari holatini yozadi — faqat oldingi nuqtadan farq qilganlari (har bir yuklash —
    yangi nuqta). Qaytaradi: yozilgan nuqtalar soni."""
    students = await db.fetchall("SELECT * FROM students")
    if not students:
        return 0
    at = now_iso()
    last: dict[tuple, float] = {}
    for r in await db.fetchall("SELECT student_id, metric, value FROM snapshots ORDER BY id"):
        last[(r["student_id"], r["metric"])] = r["value"]
    t = today()
    daily = await db.bulk_attendance_totals(min(semester_start(), t).isoformat(), t.isoformat())
    n = 0
    for x in await status.all_statuses(students):
        sid = x["student"]["id"]
        for m, v in values(x, daily.get(sid)).items():
            cur = last.get((sid, m))
            if cur is not None and abs(cur - v) < 1e-6:
                continue
            await db.conn.execute("INSERT INTO snapshots (student_id, metric, value, day) VALUES (?, ?, ?, ?)",
                                  (sid, m, v, at))
            n += 1
    await db.conn.commit()
    return n


async def history(sid: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in await db.fetchall("SELECT metric, value, day FROM snapshots WHERE student_id = ? ORDER BY id", (sid,)):
        out.setdefault(r["metric"], []).append(r)
    return out
