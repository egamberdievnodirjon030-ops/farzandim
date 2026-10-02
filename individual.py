"""Talabaning shaxsiy (individual) dars jadvali.

  • Asosiy fanlar — akademik guruh jadvalidan (/import → Dars jadvali).
  • Ikkinchi chet tili va tanlov fanlari — guruhga bog'lanmagan alohida jadvaldan (/import → Tanlov fanlari va 2-til
    jadvali): fan, oqim, kun, juftlik. Talabaga faqat u biriktirilgan fan va oqim darslari qo'shiladi
    (/import → Tanlov fanlari va 2-til: biriktirish). Shuning uchun bu darslarni faqat shu talabaning ota-onasi ko'radi.
  • Agar tanlov/til darslari guruh jadvaliga ham kiritilgan bo'lsa: guruhda kimningdir ro'yxatida bor fanlar faqat
    shu fanni o'qiydiganlarga ko'rsatiladi (kichik guruh bo'yicha ham).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher

from database import db
from utils import subgroup_key, subject_key, week_type_of

def subject_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short.split()) >= 2 and long_.startswith(short + " "):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.88


@dataclass
class Context:
    group_keys: set[str] = field(default_factory=set)   # guruhdagi shaxsiy (tanlov/til) fanlar
    mine: list[dict] = field(default_factory=list)      # talabaning o'z ro'yxati

    @property
    def status(self) -> str:
        """none — guruh uchun ma'lumot yo'q; missing — guruhda bor, shu talabada yo'q; ok."""
        if not self.group_keys:
            return "none"
        return "ok" if self.mine else "missing"


async def load(st: dict) -> Context:
    keys = await db.group_subject_keys(st["group_key"]) if st.get("group_key") else set()
    return Context(keys, await db.enrollment_for(st["id"]))


def apply(lessons: list[dict], ctx: Context, strict: bool = False) -> list[dict]:
    """strict=True (/toldir uchun): guruhda shaxsiy fanlar bor, talabaniki kiritilmagan bo'lsa — faqat umumiy
    darslar qaytadi, aks holda unga boshqa tilning darsi «qatnashdi» deb yozilib qolardi."""
    if ctx.status == "missing" and strict:
        return [les for les in lessons
                if not any(subject_match(subject_key(les["subject"]), g) for g in ctx.group_keys)]
    if ctx.status != "ok":
        return lessons
    out = []
    for les in lessons:
        k = subject_key(les["subject"])
        if not any(subject_match(k, g) for g in ctx.group_keys):
            out.append(les)          # umumiy dars
            continue
        my = [e for e in ctx.mine if subject_match(k, e["subject_key"])]
        if not my:
            continue                 # talaba bu tanlov/tilni o'qimaydi
        if les.get("subgroup"):
            subs = {e["subgroup"] for e in my if e.get("subgroup")}
            if subs and subgroup_key(les["subgroup"]) not in subs:
                continue             # boshqa kichik guruhning darsi
        out.append(les)
    return out


def personal(lessons: list[dict], st: dict, ctx: Context) -> list[dict]:
    """Tanlov/til jadvalidan talaba biriktirilgan fan (va oqim) darslari."""
    out = []
    for les in lessons:
        if les.get("group_key") and les["group_key"] != st.get("group_key"):
            continue                 # dars boshqa akademik guruh uchun
        my = [e for e in ctx.mine if subject_match(les["subject_key"], e["subject_key"])]
        if not my:
            continue                 # talaba bu fanga biriktirilmagan — ko'rsatilmaydi
        if les.get("stream"):
            streams = {e["subgroup"] for e in my if e.get("subgroup")}
            if streams and subgroup_key(les["stream"]) not in streams:
                continue             # boshqa oqimning darsi
        out.append({**les, "_personal": True})
    return out


async def lessons_on(st: dict, d: date, ctx: Context | None = None, strict: bool = False) -> list[dict]:
    """Talabaning shu kungi darslari: guruhdagi asosiy fanlar + o'zining tanlov fani va 2-til darslari."""
    ctx = ctx or await load(st)
    wd, wt = d.isoweekday(), week_type_of(d)
    rows = apply(await db.schedule_for(st["group_key"], wd, wt), ctx, strict) if st.get("group_key") else []
    rows += personal(await db.elective_lessons(wd, wt), st, ctx)
    return sorted(rows, key=lambda r: (r["pair"], bool(r.get("_personal"))))


async def fill_attended(d1: date, d2: date, hours: float) -> int:
    """Shaxsiy jadvaldagi, lekin davomat yozuvi yo'q darslarni «keldi» deb belgilaydi (/toldir).
    Talaba o'qimaydigan tanlov fani yoki boshqa til darsi unga yozilmaydi."""
    students = await db.fetchall(
        """SELECT * FROM students WHERE group_key IN (SELECT DISTINCT group_key FROM schedule)
           OR id IN (SELECT DISTINCT student_id FROM student_subjects)""")
    cache: dict[tuple[str, str], list[dict]] = {}
    el_cache: dict[str, list[dict]] = {}
    total = 0
    for st in students:
        ctx = await load(st)
        rows = []
        d = d1
        while d <= d2:
            key = (st.get("group_key") or "", d.isoformat())
            if key not in cache:
                cache[key] = (await db.schedule_for(st["group_key"], d.isoweekday(), week_type_of(d))
                              if st.get("group_key") else [])
            if d.isoformat() not in el_cache:
                el_cache[d.isoformat()] = await db.elective_lessons(d.isoweekday(), week_type_of(d))
            seen = set()
            day = apply(cache[key], ctx, strict=True) + personal(el_cache[d.isoformat()], st, ctx)
            for les in sorted(day, key=lambda r: r["pair"]):
                if les["pair"] in seen:  # bir juftlikda bir nechta dars qolsa — birinchisi
                    continue
                seen.add(les["pair"])
                rows.append((st["id"], d.isoformat(), les["pair"], les["subject"], les.get("lesson_type"),
                             les.get("teacher"), "keldi", hours, 1))
            d += timedelta(days=1)
        if rows:
            before = db.conn.total_changes
            await db.conn.executemany(
                """INSERT OR IGNORE INTO attendance
                       (student_id, date, pair, subject, lesson_type, teacher, status, hours, notified)
                   VALUES (?,?,?,?,?,?,?,?,?)""", rows)
            total += db.conn.total_changes - before
    await db.conn.commit()
    return total


async def unmatched_subjects(rows: list[dict]) -> list[str]:
    """Import tekshiruvi: talabaning guruh jadvalida mos darsi topilmagan fanlar (nomi farq qilishi mumkin)."""
    by_group: dict[str, set[str]] = {}
    elective = await db.elective_subject_keys()
    missing = set()
    for r in rows:
        if any(subject_match(r["subject_key"], k) for k in elective):
            continue                 # tanlov/til jadvalida bor
        st = await db.get_student(r["student_id"])
        gk = st.get("group_key") if st else None
        if gk and gk not in by_group:
            by_group[gk] = {subject_key(x["subject"]) for x in await db.group_schedule(gk)}
        keys = by_group.get(gk, set()) if gk else set()
        if (keys or elective) and not any(subject_match(r["subject_key"], k) for k in keys):
            missing.add(r["subject"])
    return sorted(missing)


async def unassigned_subjects(rows: list[dict]) -> list[str]:
    """Tanlov/til jadvalidagi, lekin hali hech bir talaba biriktirilmagan fanlar."""
    enrolled = await db.enrolled_subject_keys()
    return sorted({r["subject"] for r in rows if not any(subject_match(r["subject_key"], k) for k in enrolled)})
