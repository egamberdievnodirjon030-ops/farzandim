"""Akademik qarzdorlik: 100 ballik baho 5 baholik tizimga o'tkaziladi.

    90–100 → «5»,  70–89 → «4»,  60–69 → «3»,  0–59 → «2» — shu fandan akademik qarzdor.

Ball 0,5 dan boshlab yuqoriga yaxlitlanadi: 69,5 → 70 → «4»; 59,5 → 60 → «3».
Faqat fan bo'yicha 100 ballik umumiy (yakuniy) ball hisobga olinadi — masalan, HEMIS «O'rtacha ball».
«Oraliq nazorat 25/30» kabi qism baholar akademik qarzni belgilamaydi.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from config import GPA_MIN
from database import db
from i18n import N_
from utils import normalize_text

SCALE = ((90, 5), (70, 4), (60, 3), (0, 2))
_PRIORITY = (("ortacha", "umumiy", "jami", "itogov", "reyting", "final"), ("yakuniy",))


def round_half_up(x: float) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def five_point(score100: float) -> int:
    s = round_half_up(score100)
    return next(g for lo, g in SCALE if s >= lo)


def is_total(g: dict) -> bool:
    """100 ballik umumiy ball: maksimal ball 100 (yoki ko'rsatilmagan va ball 100 dan oshmaydi)."""
    mx = g.get("max_score")
    return g.get("score") is not None and (mx == 100 or (mx in (None, 0) and g["score"] <= 100))


def _rank(control_type: str) -> int:
    t = normalize_text(control_type)
    for i, words in enumerate(_PRIORITY):
        if any(w in t for w in words):
            return i
    return len(_PRIORITY)


def subject_results(grades: list[dict]) -> list[dict]:
    """Har bir (semestr, fan) uchun bitta umumiy ball va 5 baholik baho."""
    best: dict[tuple, dict] = {}
    for g in grades:
        if not is_total(g):
            continue
        key = (g.get("semester") or "", g["subject"])
        cur = best.get(key)
        if cur is None or _rank(g["control_type"]) < _rank(cur["control_type"]):
            best[key] = g
    out = []
    for (sem, subject), g in best.items():
        grade = five_point(g["score"])
        out.append({"semester": sem, "subject": subject, "score": g["score"], "grade": grade,
                    "debt": grade == 2, "control_type": g["control_type"], "credits": g.get("credits")})
    return sorted(out, key=lambda r: (r["semester"], r["subject"]))


def gpa(results: list[dict]) -> tuple[float | None, bool]:
    """O'rtacha o'zlashtirish ko'rsatkichi (GPA) 5 baholik tizimda: Σ(baho × kredit) / Σ kredit.
    Barcha fanlarda kredit bo'lsa — kreditlar bo'yicha tortilgan, aks holda oddiy o'rtacha.
    Qaytaradi: (GPA yoki None, kreditlar hisobga olinganmi)."""
    if not results:
        return None, False
    weighted = all((r.get("credits") or 0) > 0 for r in results)
    w = [(r["credits"] if weighted else 1.0) for r in results]
    return sum(r["grade"] * k for r, k in zip(results, w)) / sum(w), weighted


def gpa_low(value: float | None) -> bool:
    """Umumiy GPA chegaradan (GPA_MIN, standart 2,6) past — talaba kursdan kursga o'tmaydi.
    Yaxlitlanmaydi: 2,599 < 2,6 — o'tmaydi (faqat suzuvchi nuqta shovqini olib tashlanadi)."""
    return value is not None and round(value, 9) < GPA_MIN


def semester_gpa(results: list[dict]) -> dict[str, float]:
    return {sem: gpa(items)[0] for sem, items in by_semester(results).items()}


def hemis_debts(rows: list[dict]) -> list[dict]:
    """HEMIS «Akadem qarzdorlar» ro'yxatidagi fanlar — qarz sifatida (balli yo'q, GPA ga ta'sir qilmaydi)."""
    return [{"semester": r.get("semester") or "", "subject": r["subject"], "score": None, "grade": 2, "debt": True,
             "control_type": "HEMIS", "credits": r.get("credits"), "source": "hemis", "year": r.get("academic_year")}
            for r in rows]


def merge_debts(grade_debts: list[dict], hemis_rows: list[dict]) -> list[dict]:
    """Baholardan aniqlangan qarzlar (0–59 → «2») + HEMIS ro'yxati. Bir fan ikki manbada bo'lsa — bir marta
    (balli yozuv qoladi). HEMIS ro'yxatida talaba necha marta (necha fan bilan) kelsa — shuncha qarzdor fan."""
    out = list(grade_debts)
    by_grades = {normalize_text(d["subject"]) for d in grade_debts}
    seen: set[tuple] = set()
    for h in hemis_debts(hemis_rows):
        subj = normalize_text(h["subject"])
        key = (str(h["semester"]), subj)
        if subj in by_grades or key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


async def summary(sid: int) -> dict:
    results = subject_results(await db.grades_for(sid))
    debts = merge_debts([r for r in results if r["debt"]], await db.academic_debts_for(sid))
    return {"results": results, "debts": debts}


def by_semester(results: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        d[r["semester"]].append(r)
    return d


GPA_TEXT = N_("GPA — o'rtacha o'zlashtirish ko'rsatkichi: fanlar bo'yicha 5 baholik baholarning o'rtachasi "
            "(kreditlar bo'lsa — kreditlar bo'yicha tortilgan).")
GPA_RULE = N_("Umumiy GPA {min} dan past bo'lsa, talaba kursdan kursga o'tkazilmaydi (GPA yaxlitlanmaydi).")
RULES_TEXT = N_("Baholash: 90–100 ball — «5», 70–89 — «4», 60–69 — «3», 0–59 — «2» (akademik qarz). "
              "Ball 0,5 dan boshlab yuqoriga yaxlitlanadi (69,5 → 70 → «4»).")
