"""Fan bo'yicha sababsiz qoldirish chegarasi (universitet ichki tartibi).

Fanga ajratilgan auditoriya soatining 25 foizi va undan ortig'ini sababsiz qoldirgan talaba shu fandan yakuniy
nazoratga kiritilmaydi va kreditlarni o'zlashtirmagan (akademik qarzdor) hisoblanadi:
2 kreditli fan — 2 para (2,5 ga to'g'ri kelsa ham 2), 4 kreditli — 5 para, 6 kreditli — 7 para.
Umumiy qoida: 1 kredit = 5 para auditoriya mashg'uloti; chegara = 25% (pastga yaxlitlanadi) → kredit × 1,25.

Fan krediti: kurs koordinatori kiritgan qiymat → baholar fayli (kredit ustuni) → fan kodi (Manage dars jadvali:
«CTIR25C4-21» → 4 kredit) → akademik qarzdorlar ro'yxati.
Kredit noma'lum bo'lsa chegara ko'rsatilmaydi (taxmin qilinmaydi).
"""
from __future__ import annotations

import math

from config import SUBJECT_LIMIT_PAIRS, SUBJECT_LIMIT_PERCENT, AUDITORIUM_PAIRS_PER_CREDIT
from database import db
from utils import normalize_text, semester_start, subject_key, today


def limit_pairs(credits: float | None) -> int | None:
    """Kredit → sababsiz qoldirish chegarasi (para). .env dagi SUBJECT_LIMIT_PAIRS jadvali ustun."""
    if not credits or credits <= 0:
        return None
    c = round(float(credits), 2)
    if c in SUBJECT_LIMIT_PAIRS:
        return SUBJECT_LIMIT_PAIRS[c]
    return max(1, math.floor(c * AUDITORIUM_PAIRS_PER_CREDIT * SUBJECT_LIMIT_PERCENT / 100 + 1e-9))


def limit_from_pairs(pairs: float | None) -> int | None:
    """Fanga ajratilgan auditoriya mashg'ulotlari (para, Manage: lessonCount) → chegara: 25%, pastga yaxlitlanadi
    (30 para → 7, 20 → 5, 10 → 2)."""
    if not pairs or pairs <= 0:
        return None
    return max(1, math.floor(pairs * SUBJECT_LIMIT_PERCENT / 100 + 1e-9))


async def credits_info() -> dict[str, dict]:
    """Joriy kurs bo'yicha fan kaliti → {credits, src, code}. Ustunlik: koordinator kiritgani → baholar fayli →
    fan kodi (Manage jadvali: «CTIR25C4» → 4) → akademik qarzdorlar ro'yxati."""
    out: dict[str, dict] = {}
    for r in await db.fetchall("SELECT subject, MAX(credits) AS c FROM academic_debts WHERE credits > 0 GROUP BY subject"):
        k = subject_key(r["subject"]) or normalize_text(r["subject"])
        if k:
            out[k] = {"credits": r["c"], "src": "debts"}
    pairs = {}
    for r in await db.fetchall("SELECT subject_key, credits, code, source, pairs, held FROM subject_credits "
                               "WHERE credits > 0 OR pairs > 0"):
        if r["credits"] and r["credits"] > 0:
            out[r["subject_key"]] = {"credits": r["credits"], "src": r["source"] or "code", "code": r["code"]}
        if r["pairs"] and r["pairs"] > 0:
            pairs[r["subject_key"]] = (r["pairs"], r["held"])
    for r in await db.fetchall("SELECT subject, MAX(credits) AS c FROM grades WHERE credits > 0 GROUP BY subject"):
        k = subject_key(r["subject"]) or normalize_text(r["subject"])
        if k:
            out[k] = {"credits": r["c"], "src": "grades"}
    for r in await db.fetchall("SELECT key, value FROM settings WHERE key LIKE 'credits:%'"):
        try:
            v = float(r["value"])
        except (TypeError, ValueError):
            continue
        if v > 0:  # 0 — avtomatik (fayllar va fan kodidagi kredit)
            out[r["key"].split(":", 1)[1]] = {"credits": v, "src": "manual"}
    # Manage'dagi fanga ajratilgan darslar soni (lessonCount) — qoida aynan shundan (auditoriya soatining 25%):
    # kreditdan aniqroq, faqat koordinator qo'lda kiritgan kredit undan ustun
    for k, (p, held) in pairs.items():
        cur = out.setdefault(k, {"credits": None, "src": None})
        cur["pairs"], cur["held"] = p, held
    return out


async def rules_map() -> dict[str, dict]:
    """Fan kaliti → {credits, pairs} (evaluate uchun)."""
    return {k: {"credits": v.get("credits"), "pairs": None if v.get("src") == "manual" else v.get("pairs")}
            for k, v in (await credits_info()).items()}


async def credits_map() -> dict[str, float]:
    """Fan kaliti → kredit (credits_info ustunligi bo'yicha)."""
    return {k: v["credits"] for k, v in (await credits_info()).items() if v.get("credits")}


async def set_credits(key: str, credits: float | None) -> None:
    await db.set_setting(f"credits:{key}", str(credits or 0))


def evaluate(unexcused: float, rule: float | dict | None) -> dict:
    """Fan bo'yicha holat: chegara, qolgan, holat (ok | warn — 1 para qoldi | over — chegaraga yetdi/oshdi).
    rule — kredit yoki {credits, pairs} (pairs — fanga ajratilgan auditoriya darslari, bo'lsa — undan)."""
    credits, pairs = (rule.get("credits"), rule.get("pairs")) if isinstance(rule, dict) else (rule, None)
    lim = limit_from_pairs(pairs) or limit_pairs(credits)
    if lim is None:
        return {"credits": credits, "pairs": pairs, "limit": None, "left": None, "state": None}
    u = round(unexcused or 0)
    state = "over" if u >= lim else "warn" if u >= lim - 1 and u > 0 else "ok"
    return {"credits": credits, "pairs": pairs, "limit": lim, "left": max(lim - u, 0), "state": state}


async def per_student_subjects(where: str, params=()) -> dict[tuple[int, str], dict]:
    """Talaba × fan: semestr boshidan kunlik davomat va fan bo'yicha HEMIS statistikasi (qaysi biri ko'proq darsni
    qamrasa — o'sha). Qaytaradi: (talaba, fan kaliti) → {subject, total, came, kelmadi, sababli, …} (darslar/para)."""
    out: dict[tuple[int, str], dict] = {}
    rows = await db.fetchall(
        f"""SELECT a.student_id, s.full_name, s.group_name, s.hemis_id, a.subject, COUNT(*) AS total,
                   SUM(a.status IN ('keldi', 'kechikdi')) AS came, SUM(a.status = 'kelmadi') AS kelmadi,
                   SUM(a.status = 'sababli') AS sababli
            FROM attendance a JOIN students s ON s.id = a.student_id
            WHERE {where} AND a.date BETWEEN ? AND ? GROUP BY a.student_id, a.subject""",
        (*params, semester_start().isoformat(), today().isoformat()))
    for r in rows:
        k = subject_key(r["subject"]) or normalize_text(r["subject"])
        o = out.setdefault((r["student_id"], k), {"sid": r["student_id"], "name": r["full_name"], "group": r["group_name"],
                                                  "hemis_id": r["hemis_id"], "subject": r["subject"], "key": k, "total": 0,
                                                  "came": 0, "kelmadi": 0, "sababli": 0, "source": "daily"})
        for f in ("total", "came", "kelmadi", "sababli"):
            o[f] += r[f] or 0
    for r in await db.latest_subject_stats(where, params):
        if r["as_of"] < semester_start().isoformat():
            continue
        total = (r["attended"] or 0) + (r["absent"] or 0)
        cur = out.get((r["student_id"], r["subject_key"]))
        if total and (not cur or total > cur["total"]):
            out[(r["student_id"], r["subject_key"])] = {
                "sid": r["student_id"], "name": r["full_name"], "group": r["group_name"], "hemis_id": r["hemis_id"],
                "subject": (cur or {}).get("subject") or r["subject"], "key": r["subject_key"], "total": total,
                "came": r["attended"] or 0, "kelmadi": max((r["absent"] or 0) - (r["excused"] or 0), 0),
                "sababli": r["excused"] or 0, "source": "hemis", "as_of": r["as_of"]}
    return out
