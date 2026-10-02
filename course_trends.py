"""Kurs dinamikasi — kurs koordinatorining asosiy dashboardi («Kurs holati») uchun ixcham ko'rsatkichlar.

Har bir ko'rsatkich: oxirgi qiymat, oldingi davrga nisbatan o'zgarish va kichik grafik uchun nuqtalar.
  • Davomat, % — kunlik davomat bo'lsa haftalar bo'yicha (oxirgi 6 hafta), bo'lmasa HEMIS statistikasi yuklashlari
    orasidagi davrlar bo'yicha (har bir davrda qatnashilgan ulush);
  • Chegaraga yetganlar — semestr boshidan qoldirilgan soatlari birinchi chegaradan oshgan talabalar soni;
  • Kontrakt va trimestr qarzi — buxgalteriya hisobotlari sanalari bo'yicha jami qarz.
Talabaning ma'lumoti biror sanada yuklanmagan bo'lsa (masalan, hisobot faqat bir guruh uchun yuklangan), uning
oldingi holati olinadi — qisman yuklash grafikni buzmaydi. scope — koordinatorning guruhlari (None — butun kurs).
"""
from __future__ import annotations

from datetime import date, timedelta

import absence
from config import ABSENCE_COUNT_EXCUSED
from database import db
from utils import fmt_money, fmt_num, fmt_pairs, semester_start, today, week_bounds

POINTS = 6  # grafikdagi davrlar soni


def _students_sql(scope: set[str] | None) -> tuple[str, tuple]:
    if scope is None:
        return "SELECT id FROM students", ()
    return f"SELECT id FROM students WHERE group_key IN ({','.join('?' * len(scope)) or 'NULL'})", tuple(sorted(scope))


def _label(d: date) -> str:
    return d.strftime("%d.%m")


def _carry(rows: list[dict], key: str) -> list[tuple[str, dict]]:
    """Sanalar bo'yicha holat: har bir sanada har bir talabaning shu sanagacha bo'lgan oxirgi yozuvi."""
    dates = sorted({r[key] for r in rows})
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r[key], []).append(r)
    state: dict[int, dict] = {}
    out = []
    for d in dates:
        for r in by_date[d]:
            state[r["student_id"]] = r
        out.append((d, dict(state)))
    return out


def _item(key: str, title: str, unit: str, points: list[dict], better: str, caption: str, note: str = "") -> dict:
    vals = [p["value"] for p in points]
    delta = round(vals[-1] - vals[-2], 1) if len(vals) > 1 else None
    return {"key": key, "title": title, "unit": unit, "points": points, "value": vals[-1] if vals else None,
            "delta": delta, "better": better, "caption": caption, "note": note}


async def _attendance(scope) -> list[dict]:
    S, p = _students_sql(scope)
    t, since = today(), semester_start()
    mon, _ = week_bounds(t)
    start = max(mon - timedelta(weeks=POINTS - 1), since)
    counted = "('kelmadi','sababli')" if ABSENCE_COUNT_EXCUSED else "('kelmadi')"
    weeks = await db.fetchall(
        f"""SELECT date(date, '-' || ((CAST(strftime('%w', date) AS INTEGER) + 6) % 7) || ' days') AS wk,
                   COUNT(*) AS total, SUM(status IN ('keldi', 'kechikdi')) AS att
            FROM attendance WHERE student_id IN ({S}) AND date BETWEEN ? AND ? GROUP BY wk ORDER BY wk""",
        p + (start.isoformat(), t.isoformat()))
    if weeks:  # kunlik davomat — haftalar bo'yicha
        pct = [{"label": _label(date.fromisoformat(w["wk"])), "value": round(100 * w["att"] / w["total"], 1)}
               for w in weeks if w["total"]]
        # chegaraga yetganlar: har bir hafta oxirigacha semestr boshidan to'plangan soatlar
        per = await db.fetchall(
            f"""SELECT student_id, date(date, '-' || ((CAST(strftime('%w', date) AS INTEGER) + 6) % 7) || ' days') AS wk,
                       SUM(hours) AS h FROM attendance
                WHERE student_id IN ({S}) AND date BETWEEN ? AND ? AND status IN {counted}
                GROUP BY student_id, wk""", p + (since.isoformat(), t.isoformat()))
        totals: dict[int, float] = {}
        by_wk: dict[str, list[dict]] = {}
        for r in per:
            by_wk.setdefault(r["wk"], []).append(r)
        lvl, crossed = absence.LEVELS[0], []
        for wk in sorted(set(by_wk) | {w["wk"] for w in weeks}):
            for r in by_wk.get(wk, []):
                totals[r["student_id"]] = totals.get(r["student_id"], 0) + (r["h"] or 0)
            if wk >= (start - timedelta(days=start.weekday())).isoformat():  # semestr hafta o'rtasida boshlansa ham
                crossed.append({"label": _label(date.fromisoformat(wk)), "value": sum(1 for h in totals.values() if h >= lvl)})
        return [_item("att", "Davomat", "%", pct, "up", "o'tgan haftaga nisbatan"),
                _item("limit", "Chegaraga yetganlar", "ta", crossed, "down", "o'tgan haftaga nisbatan",
                      f"{fmt_pairs(lvl)} va undan ko'p")]
    rows = await db.fetchall(f"SELECT student_id, as_of, attended, absent, excused FROM attendance_stats "
                             f"WHERE student_id IN ({S}) AND as_of >= ?", p + (since.isoformat(),))
    if not rows:
        return []
    snaps = _carry(rows, "as_of")[-(POINTS + 1):]
    pct, crossed, prev = [], [], None
    lvl = absence.LEVELS[0]
    for d, state in snaps:
        hrs = {sid: absence.stats_hours(r) for sid, r in state.items()}
        crossed.append({"label": _label(date.fromisoformat(d)), "value": sum(1 for h in hrs.values() if h["counted"] >= lvl)})
        if prev is not None:  # davr ichida qatnashilgan ulush — ikkala sanada ham bor talabalar bo'yicha
            common = hrs.keys() & prev.keys()
            att = sum(hrs[s]["attended"] - prev[s]["attended"] for s in common)
            absn = sum(hrs[s]["absent"] - prev[s]["absent"] for s in common)
            if att + absn > 0:
                pct.append({"label": _label(date.fromisoformat(d)), "value": round(100 * att / (att + absn), 1)})
        else:
            tot = sum(h["attended"] + h["absent"] for h in hrs.values())
            if tot:
                pct.append({"label": _label(date.fromisoformat(d)),
                            "value": round(100 * sum(h["attended"] for h in hrs.values()) / tot, 1)})
        prev = hrs
    return [_item("att", "Davomat", "%", pct[-POINTS:], "up", "oldingi HEMIS yuklashiga nisbatan"),
            _item("limit", "Chegaraga yetganlar", "ta", crossed[-POINTS:], "down", "oldingi HEMIS yuklashiga nisbatan",
                  f"{fmt_pairs(lvl)} va undan ko'p")]


async def _payments(scope) -> list[dict]:
    S, p = _students_sql(scope)
    out = []
    for kind, title in (("kontrakt", "Kontrakt qarzi"), ("trimestr", "Trimestr qarzi")):
        rows = await db.fetchall(f"SELECT student_id, as_of, debt FROM payments WHERE kind = ? AND student_id IN ({S})",
                                 (kind,) + p)
        if not rows:
            continue
        pts = []
        for d, state in _carry(rows, "as_of")[-POINTS:]:
            debts = [r["debt"] or 0 for r in state.values()]
            pts.append({"label": _label(date.fromisoformat(d)), "value": round(sum(debts)),
                        "count": sum(1 for x in debts if x > 0)})
        out.append(_item(kind, title, "so'm", pts, "down", "oldingi hisobotga nisbatan",
                         f"qarzdorlar: {pts[-1]['count']} ta"))
    return out


async def course_dynamics(scope: set[str] | None) -> list[dict]:
    return await _attendance(scope) + await _payments(scope)


def fmt_value(it: dict, v) -> str:
    if v is None:
        return "—"
    return f"{fmt_num(v)}%" if it["unit"] == "%" else fmt_money(v) if it["unit"] == "so'm" else f"{fmt_num(v)} ta"


def text_lines(items: list[dict]) -> list[str]:
    """Bot uchun: har bir ko'rsatkich bitta qatorda — qiymat va o'zgarish (🟢 yaxshilandi, 🔴 yomonlashdi)."""
    out = []
    for it in items:
        line = f"{it['title']}: <b>{fmt_value(it, it['value'])}</b>"
        d = it["delta"]
        if d:
            good = (d > 0) == (it["better"] == "up")
            mag = f"{fmt_num(abs(d))} p.p." if it["unit"] == "%" else fmt_value(it, abs(d))
            line += f" {'🟢' if good else '🔴'} {'▲' if d > 0 else '▼'} {mag} ({it['caption']})"
        elif d == 0:
            line += f" — o'zgarmadi ({it['caption']})"
        out.append("   • " + line)
    return out
