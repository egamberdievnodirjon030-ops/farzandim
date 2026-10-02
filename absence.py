"""Dars qoldirish chegaralari va choralar (universitet ichki tartibi, .env da sozlanadi):
18 soat — dekan nomiga tushuntirish xati, 36 — dekan ogohlantirishi, 54 — hayfsan, 74 — talabalar safidan chetlatish.

Semestrdagi qoldirilgan soatlar ikki manbadan olinadi: HEMIS davomat statistikasi (bo'lsa — u ustun turadi,
chunki rasmiy jami ko'rsatkich) yoki kunlik davomat yozuvlari.
"""
from __future__ import annotations

from config import ABSENCE_COUNT_EXCUSED, ABSENCE_WARN_ACTIONS, ABSENCE_WARN_LEVELS, HEMIS_STATS_HOURS_PER_UNIT
from database import db
from i18n import N_, tr
from utils import fmt_date, fmt_pairs, semester_start, today

LEVELS = ABSENCE_WARN_LEVELS
COUNTED_LABEL = N_("qoldirilgan (sababli bilan birga)") if ABSENCE_COUNT_EXCUSED else N_("sababsiz qoldirilgan")


def action_for(i: int) -> str:
    """Chora nomi joriy tilda (standart choralar tarjima qilingan; .env dagi boshqa nomlar o'zgarishsiz)."""
    return tr(ABSENCE_WARN_ACTIONS[i]) if i < len(ABSENCE_WARN_ACTIONS) else tr("{n} chegarasi", n=fmt_pairs(LEVELS[i]))


def level_index(hours: float) -> int:
    """Yetilgan eng yuqori chegara tartib raqami (0 dan), yetilmagan bo'lsa -1."""
    return max((i for i, lvl in enumerate(LEVELS) if hours >= lvl), default=-1)


def level_icon(i: int) -> str:
    return "🟢" if i < 0 else ("🟡", "🟠", "🔴", "⛔️")[min(i, 3)]


def stats_hours(row: dict) -> dict:
    """HEMIS statistikasi qatorini soatlarga o'giradi."""
    k = HEMIS_STATS_HOURS_PER_UNIT
    attended, absent, excused = row["attended"] * k, row["absent"] * k, row["excused"] * k
    unexcused = max(absent - excused, 0.0)
    total = attended + absent
    return {"attended": attended, "absent": absent, "excused": excused, "unexcused": unexcused,
            "counted": absent if ABSENCE_COUNT_EXCUSED else unexcused,
            "percent": 100 * attended / total if total else None}


async def summary(sid: int) -> dict | None:
    """Semestr boshidan buyongi qoldirishlar. Ma'lumot bo'lmasa — None."""
    since = semester_start().isoformat()
    t = today()
    return summary_from(await db.latest_att_stats(sid, since),
                        await db.attendance_totals(sid, min(semester_start(), t).isoformat(), t.isoformat()))


def summary_from(row: dict | None, tot: dict | None) -> dict | None:
    """summary() ning bazasiz qismi: HEMIS statistikasi qatori va kunlik davomat yig'indisidan."""
    if row:
        return {"source": "hemis", "as_of": row["as_of"], **stats_hours(row)}
    t = today()
    if not tot or not tot["total"]:
        return None
    unexc, exc = tot["kelmadi_soat"] or 0.0, tot["sababli_soat"] or 0.0
    return {"source": "daily", "as_of": t.isoformat(), "attended": None, "absent": unexc + exc,
            "excused": exc, "unexcused": unexc, "counted": unexc + (exc if ABSENCE_COUNT_EXCUSED else 0),
            "percent": 100 * (tot["keldi"] + tot["kechikdi"]) / tot["total"]}


def source_note(sm: dict) -> str:
    return (tr("HEMIS ma'lumoti, {d} holatiga", d=fmt_date(sm['as_of'], False)) if sm["source"] == "hemis"
            else tr("kunlik davomat bo'yicha"))


def status_lines(sm: dict) -> list[str]:
    """Farzand sahifasi va hisobotlar uchun: qancha qoldirilgan, qaysi chegara, keyingisi qancha."""
    h = sm["counted"]
    i = level_index(h)
    lines = [f"{level_icon(i)} " + tr("Semestrda {label}: <b>{h}</b>", label=tr(COUNTED_LABEL), h=fmt_pairs(h))]
    if i >= 0:
        lines.append("   " + tr("Chegara: {n} — <b>{a}</b>", n=fmt_pairs(LEVELS[i]), a=action_for(i)))
    if i + 1 < len(LEVELS):
        left = LEVELS[i + 1] - h
        lines.append("   " + tr("Keyingi chegara: {n} — {a}, qolgan: {left}", n=fmt_pairs(LEVELS[i + 1]),
                                  a=action_for(i + 1), left=fmt_pairs(left)))
    return lines


def rules_text() -> str:
    """Ota-onalar uchun chegaralar ro'yxati."""
    head = (tr("📏 <b>Dars qoldirish chegaralari</b> (semestr davomida barcha qoldirilgan soatlar):")
            if ABSENCE_COUNT_EXCUSED else
            tr("📏 <b>Dars qoldirish chegaralari</b> (semestr davomida sababsiz qoldirilgan soatlar):"))
    return head + "\n" + "\n".join(f"{level_icon(i)} " + tr("{n} — {a}", n=fmt_pairs(lvl), a=action_for(i))
                                    for i, lvl in enumerate(LEVELS))
