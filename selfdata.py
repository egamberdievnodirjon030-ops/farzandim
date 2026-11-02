"""Talabalar o'zi kiritgan ma'lumotlar (talaba ilovasi) va talabalar botiga ulanish — kurs koordinatori va dekan uchun.
Talaba kiritgani talaba kartasida ko'rinadi (alohida sahifa yo'q):

  • Yashash joyi (turi, ijara manzili, xaritadagi joy) — kartada «Talaba o'zi kiritgan» va «Tasdiqlash» (visitsapi:
    checked); xonadon toifasini qo'yish ham tekshiruv hisoblanadi; koordinator tahrir qilsa — talaba endi o'zgartira
    olmaydi. Xonadon toifasi (yashil / sariq / qizil) — faqat koordinator.
  • Ijtimoiy toifa — talaba kiritgani kartada «talaba o'zi kiritgan, tekshirilmagan»; koordinator tasdiqlaydi yoki
    olib tashlaydi.
  • Talabalar boti: kim ulangan (shaxsiy havola, telefon raqami yoki ota-onani tasdiqlash orqali), oxirgi faollik
    (botda xabar yoki tugma, ilovani ochish), botni bloklagani (xabar yetmagan).
"""
from __future__ import annotations

from datetime import timedelta

from database import db
from tenancy import scope_students
from utils import now

ACTIVE_DAYS = 7  # «faol» — oxirgi 7 kunda botda yoki ilovada bo'lgan


async def bot_map() -> dict[int, dict]:
    """Talaba → talabalar botidagi hisobi (joriy kurs)."""
    return {r["student_id"]: r for r in await db.fetchall("SELECT student_id, tg_id, via, linked_at, seen_at, blocked_at "
                                                           "FROM student_accounts")}


def bot_info(acc: dict | None) -> dict:
    """Panel uchun: ulanganmi, qanday, oxirgi faollik, bloklaganmi, oxirgi 7 kunda faolmi."""
    if not acc:
        return {"on": False}
    seen = acc.get("seen_at") or ""
    recent = bool(seen) and seen >= (now() - timedelta(days=ACTIVE_DAYS)).isoformat(timespec="seconds")
    return {"on": True, "via": acc.get("via") or "", "linked_at": acc.get("linked_at"), "seen_at": seen or None,
            "blocked": bool(acc.get("blocked_at")), "active": recent and not acc.get("blocked_at")}


async def bot_stats(students: list[dict]) -> dict:
    """Ko'rsatkich: talabalar botiga ulanganlar (bloklaganlar va oxirgi 7 kunda faollar bilan)."""
    m = await bot_map()
    infos = [bot_info(m.get(s["id"])) for s in students]
    on = [i for i in infos if i["on"]]
    return {"total": len(students), "linked": len(on), "blocked": sum(1 for i in on if i["blocked"]),
            "active": sum(1 for i in on if i["active"]), "via": {v: sum(1 for i in on if i["via"] == v) for v in
                                                                 ("havola", "telefon", "tasdiq") if any(i["via"] == v for i in on)}}


# ---------------------------------------------------------------- API (boshqaruv paneli)
async def api_social_confirm(request):
    import socialcat as SC
    from webapi import _visible, bad, ok
    d = await request.json()
    try:
        sid = int(d.get("student_id"))
    except (TypeError, ValueError):
        return bad("bad_student")
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    return ok({"ok": await SC.confirm(sid, str(d.get("category", "")), str(d.get("sub") or ""), request["user"]["id"])})


async def api_bot(request):
    """Talabalar botiga ulanish: ko'rsatkichlar (ro'yxat — «Talabalar» jadvalidagi «Bot» ustuni va filtrida)."""
    from webapi import ok
    students = scope_students(await db.fetchall("SELECT id, group_key FROM students"))
    return ok(await bot_stats(students))


def setup(r) -> None:
    from webapi import staff_route
    r.add_post("/api/staff/social/confirm", staff_route(api_social_confirm))
    r.add_get("/api/staff/bot", staff_route(api_bot))

