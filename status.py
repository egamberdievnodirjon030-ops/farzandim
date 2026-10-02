"""Talabaning umumiy holati — ota-onaning «umumiy holat» ekrani va kurs koordinatori paneli uchun.

Bir joyda hisoblanadi: davomat (foiz, qoldirilgan soatlar, chegara), akademik qarzdorlik, o'rtacha baho,
kontrakt va trimestr qarzi, «e'tibor talab qiladigan masalalar». Panel uchun barcha talabalar bir necha umumiy
so'rov bilan olinadi (har bir talaba uchun alohida so'rov emas).
"""
from __future__ import annotations

from datetime import date

import absence
import academic
import loc
from database import db
from i18n import tr
from utils import fmt_date, fmt_money, fmt_pairs, parse_date, semester_start, today

PAY_KINDS = ("kontrakt", "trimestr")
PAY_LABEL = {"kontrakt": "Kontrakt", "trimestr": "Trimestr"}


async def deadlines() -> dict[str, date | None]:
    return {k: parse_date(await db.get_setting(f"deadline:{k}")) for k in PAY_KINDS}


def _average(results: list[dict]) -> float | None:
    """Oxirgi semestrdagi fanlar bo'yicha o'rtacha 100 ballik baho."""
    if not results:
        return None
    sems = [r["semester"] for r in results if str(r["semester"]).isdigit()]
    last = max(sems, key=int) if sems else None
    cur = [r["score"] for r in results if last is None or r["semester"] == last]
    return sum(cur) / len(cur) if cur else None


def build(st: dict, att_row, att_tot, grades: list[dict], pays: dict, dl: dict, hemis: list[dict] | None = None) -> dict:
    sm = absence.summary_from(att_row, att_tot)
    level = absence.level_index(sm["counted"]) if sm else -1
    results = academic.subject_results(grades)
    debts = academic.merge_debts([r for r in results if r["debt"]], hemis or [])  # + HEMIS qarzdorlar ro'yxati
    t = today()
    issues = []
    if level >= 0:
        issues.append(f"{absence.level_icon(level)} " + tr("Semestrda {h} dars qoldirilgan — {a}",
                                                            h=fmt_pairs(sm['counted']), a=absence.action_for(level)))
    if debts:
        issues.append(tr("📚 Akademik qarz: {n} ta fan ({names})", n=len(debts),
                         names=", ".join(loc.term(d['subject']) for d in debts[:3]) + (", …" if len(debts) > 3 else "")))
    for k in PAY_KINDS:
        p = pays.get(k)
        if p and p["debt"] > 0:
            late = dl.get(k) and dl[k] < t
            issues.append(("💰 " + tr("Kontrakt qarzi: {v}", v=fmt_money(p['debt'])) if k == "kontrakt"
                           else "💳 " + tr("Trimestr qarzi: {v}", v=fmt_money(p['debt'])))
                          + (" — " + tr("muddat ({d}) o'tgan", d=fmt_date(dl[k], False)) if late else ""))
    g, weighted = academic.gpa(results)
    return {"student": st, "attendance": sm, "level": level, "results": results, "debts": debts,
            "average": _average(results), "gpa": g, "gpa_weighted": weighted, "pays": pays, "issues": issues,
            "flags": {"att": level >= 0, "acad": bool(debts),
                      "kontrakt": bool(pays.get("kontrakt") and pays["kontrakt"]["debt"] > 0),
                      "trimestr": bool(pays.get("trimestr") and pays["trimestr"]["debt"] > 0)}}


async def student_status(st: dict) -> dict:
    since = semester_start().isoformat()
    t = today()
    return build(st, await db.latest_att_stats(st["id"], since),
                 await db.attendance_totals(st["id"], min(semester_start(), t).isoformat(), t.isoformat()),
                 await db.grades_for(st["id"]),
                 {k: await db.latest_payment(st["id"], k) for k in PAY_KINDS}, await deadlines(),
                 await db.academic_debts_for(st["id"]))


async def all_statuses(students: list[dict]) -> list[dict]:
    since = semester_start().isoformat()
    t = today()
    att = await db.bulk_latest_att_stats(since)
    tot = await db.bulk_attendance_totals(min(semester_start(), t).isoformat(), t.isoformat())
    grades = await db.bulk_grades()
    pays = {k: await db.bulk_latest_payments(k) for k in PAY_KINDS}
    dl = await deadlines()
    hemis = await db.bulk_academic_debts()
    return [build(st, att.get(st["id"]), tot.get(st["id"]), grades.get(st["id"], []),
                  {k: pays[k].get(st["id"]) for k in PAY_KINDS}, dl, hemis.get(st["id"], [])) for st in students]
