"""Talabalar o'zi kiritgan ma'lumotlar (talaba ilovasi) va talabalar botiga ulanish — kurs koordinatori va dekan uchun.

  • Yashash joyi (turi, ijara manzili, xaritadagi joy) — talaba kiritsa, koordinator ko'radi va tekshiradi
    («Tasdiqlash»; xonadon toifasini qo'yish ham tekshiruv hisoblanadi); koordinator tahrir qilsa — talaba endi
    o'zgartira olmaydi. Xonadon toifasi (yashil / sariq / qizil) — faqat koordinator.
  • Ijtimoiy toifa — talaba kiritgani «talaba o'zi kiritgan, tekshirilmagan» bo'lib turadi; koordinator tasdiqlaydi yoki
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


def _home_pending_sql() -> str:
    return "home_by = 'talaba' AND (home_checked_at IS NULL OR home_checked_at < home_at)"


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


async def pending_count(students: list[dict] | None = None) -> int:
    """Koordinator tekshirishi kerak bo'lgan, talaba kiritgan ma'lumotlar soni (yashash joyi + toifalar)."""
    students = students if students is not None else scope_students(await db.fetchall("SELECT id, group_key FROM students"))
    ids = {s["id"] for s in students}
    homes = {r["id"] for r in await db.fetchall(f"SELECT id FROM students WHERE {_home_pending_sql()}")}
    cats = await db.fetchall("SELECT student_id FROM student_categories WHERE source = 'talaba' AND checked_at IS NULL")
    return len(homes & ids) + sum(1 for r in cats if r["student_id"] in ids)


async def listing(all_: bool = False) -> dict:
    """«Talabalar kiritgan» sahifasi: yashash joylari va ijtimoiy toifalar (tekshirilmaganlar yoki hammasi)."""
    import socialcat as SC
    import visits as V
    students = {s["id"]: s for s in scope_students(await db.fetchall("SELECT * FROM students"))}
    homes = []
    for s in students.values():
        if s.get("home_by") != "talaba":
            continue
        pend = not s.get("home_checked_at") or (s.get("home_at") or "") > s["home_checked_at"]
        if not all_ and not pend:
            continue
        homes.append({"id": s["id"], "name": s["full_name"], "group": s.get("group_name") or "", "hemis_id": s.get("hemis_id"),
                      "living": s.get("living"), "living_title": V.LIVING.get(s.get("living") or "", ""),
                      "address": s.get("rent_address") or "", "lat": s.get("lat"), "lon": s.get("lon"),
                      "zone": s.get("zone"), "at": s.get("home_at"), "pending": pend})
    social = []
    for r in await db.fetchall("SELECT * FROM student_categories WHERE source = 'talaba' ORDER BY set_at DESC"):
        s = students.get(r["student_id"])
        if not s or (not all_ and r.get("checked_at")):
            continue
        social.append({"id": s["id"], "name": s["full_name"], "group": s.get("group_name") or "", "hemis_id": s.get("hemis_id"),
                       "category": r["category"], "sub": r["sub"], "label": SC.label(r["category"], r["sub"]),
                       "note": r["note"] or "", "at": r["set_at"], "pending": not r.get("checked_at")})
    homes.sort(key=lambda x: x["at"] or "", reverse=True)
    return {"homes": homes, "social": social,
            "pending": sum(1 for x in homes if x["pending"]) + sum(1 for x in social if x["pending"])}


# ---------------------------------------------------------------- API (boshqaruv paneli)
async def api_selfdata(request):
    from webapi import ok
    return ok(await listing(request.query.get("all") == "1"))


async def api_home_check(request):
    import visits as V
    from webapi import _visible, bad, ok
    sid = int(request.match_info["sid"])
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    await V.set_home(sid, {"checked": True}, by="koordinator")
    return ok({"ok": True})


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
    r.add_get("/api/staff/selfdata", staff_route(api_selfdata))
    r.add_post("/api/staff/selfdata/home/{sid:\\d+}/check", staff_route(api_home_check))
    r.add_post("/api/staff/social/confirm", staff_route(api_social_confirm))
    r.add_get("/api/staff/bot", staff_route(api_bot))

