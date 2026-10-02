"""Ota-onaning barcha kurslardagi farzandlari (ko'p kursli rejim).

Ota-ona qaysi kurs(lar)ga tegishli ekani alohida saqlanmaydi: u qaysi kurs bazasida ro'yxatdan o'tgan bo'lsa —
o'sha kursga tegishli. Shuning uchun ma'lumot ikki joyda saqlanmaydi va bir-biriga zid bo'lib qolmaydi.
"""
from __future__ import annotations

from database import db
from tenancy import central, current_course, use_course


async def parent_courses(user_id: int) -> list[str]:
    return [k for k in db.keys() if await db.for_course(k).get_parent(user_id)]


async def all_children(user_id: int) -> list[dict]:
    """Farzandlar barcha kurslardan; har birida "course_key" — farzand qaysi kurs bazasida (tugmalar shu kursga
    yo'naltiriladi). «course» — talabaning o'quv kursi (3-kurs), unga tegilmaydi."""
    out = []
    for key in await parent_courses(user_id):
        with use_course(key):
            out += [{**c, "course_key": key} for c in await db.parent_children(user_id)]
    return out


_FLAGS = ("notify_instant", "notify_daily", "notify_warn", "notify_pay")


async def known_contact(user_id: int) -> dict | None:
    """Foydalanuvchining tasdiqlangan raqami: istalgan kursdagi ota-ona yozuvidan yoki «kutilmoqda» ro'yxatidan."""
    for key in db.keys():
        p = await db.for_course(key).get_parent(user_id)
        if p:
            return {"phone": p["phone"], "name": p.get("tg_name"), "source": p}
    p = await central.get_pending(user_id)
    return {"phone": p["phone"], "name": p.get("name"), "source": None} if p else None


async def ensure_parent_here(user_id: int, phone: str, name: str | None, source: dict | None = None) -> None:
    """Ota-onani joriy kurs bazasiga yozadi (boshqa kursdagi bildirishnoma sozlamalari bilan)."""
    if await db.get_parent(user_id):
        return
    await db.upsert_parent(user_id, phone, name)
    if source:
        for flag in _FLAGS:
            if flag in source:
                await db.set_parent_flag(user_id, flag, bool(source[flag]))


async def adopt_parents(phones: set[str]) -> int:
    """Joriy kursga yuklanayotgan ota-ona raqamlari boshqa kursda yoki «kutilmoqda» ro'yxatida bo'lsa — ularni shu
    kursga ham yozadi, shunda talabalar importi ularni farzandiga avtomatik bog'laydi."""
    cur, known = current_course(), {}
    for key in db.keys():
        if key == cur:
            continue
        for p in await db.for_course(key).fetchall("SELECT * FROM parents WHERE active = 1"):
            known.setdefault(p["phone"], (p["tg_id"], p.get("tg_name"), p))
    for p in await central.pending_all():
        known.setdefault(p["phone"], (p["tg_id"], p.get("name"), None))
    n = 0
    for phone in phones & known.keys():
        tg_id, name, source = known[phone]
        if not await db.get_parent(tg_id):
            await ensure_parent_here(tg_id, phone, name, source)
            await central.clear_pending(tg_id)
            n += 1
    return n
