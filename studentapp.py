"""Talaba ilovasi — talabalar boti ichidagi Web App (ota-onalar ilovasi kabi, bot bilan birgalikda): talaba o'z
davomati, dars jadvali, baholari, to'lovlari, choralari va rasmiy hujjatlarini ko'radi; tadbir va madaniy
tashriflarga ro'yxatdan o'tadi (vaqt to'qnashuvi — Manage'dagi shaxsiy jadvali bo'yicha), ijara tashrifini tasdiqlaydi;
bildirishnomalar (choralar, hujjatlar) tarixi.

Kirish — Telegram imzosi: talabalar botidan (STUDENT_BOT_TOKEN) yoki — alohida bot sozlanmagan bo'lsa — asosiy botdan.
Talaba kimligi — student_accounts (botga ulangan Telegram hisobi: shaxsiy havola, telefon raqami yoki ota-onani
tasdiqlash orqali). Har bir so'rovda tekshiriladi: talaba faqat o'zini ko'radi.

Sahifa: /talaba (ota-ona ilovasining o'zi — app.js «talaba rejimi»da), API: /api/s/…"""
from __future__ import annotations

import logging

from aiohttp import web

import botlar
from config import UNIVERSITY_NAME, WEBAPP_URL
from database import db
from i18n import tr
from tenancy import central, use_course

log = logging.getLogger(__name__)
PATH = "/talaba"


def open_kb(route: str = "/"):
    """Talabalar botidagi xabar uchun «📱 Ilovada ochish» tugmasi (WEBAPP_URL sozlanmagan bo'lsa — None)."""
    if not WEBAPP_URL:
        return None
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=tr("📱 Ilovada ochish"), web_app=WebAppInfo(url=f"{WEBAPP_URL}{PATH}#{route}"))]])


def menu_button():
    """Talabalar boti menyu tugmasi (chap pastda) — ilovani ochadi."""
    if not WEBAPP_URL:
        return None
    from aiogram.types import MenuButtonWebApp, WebAppInfo
    return MenuButtonWebApp(text="📱 Ilova", web_app=WebAppInfo(url=f"{WEBAPP_URL}{PATH}"))


async def my_students(uid: int) -> list[tuple[str, dict]]:
    """Shu Telegram hisobiga ulangan talaba(lar) — barcha kurslardan: [(kurs, talaba)]."""
    out = []
    for key in db.keys():
        d = db.for_course(key)
        for r in await d.fetchall("SELECT student_id FROM student_accounts WHERE tg_id = ?", (uid,)):
            st = await d.fetchone("SELECT * FROM students WHERE id = ?", (r["student_id"],))
            if st:
                out.append((key, st))
    return out


def self_route(handler):
    """/api/s/{course}/{sid}/… — faqat shu Telegram hisobiga ulangan talabaning o'zi; kurs konteksti o'rnatiladi."""
    async def wrapped(request: web.Request) -> web.Response:
        from webapi import _course_arg, bad
        key = _course_arg(request.match_info["course"])
        if key is None:
            return bad("not_found", 404)
        with use_course(None if key == "_" else key):
            sid = int(request.match_info["sid"])
            if not await db.fetchone("SELECT 1 FROM student_accounts WHERE tg_id = ? AND student_id = ?",
                                     (request["user"]["id"], sid)):
                return bad("forbidden", 403)
            st = await db.get_student(sid)
            if not st:
                return bad("not_found", 404)
            from datetime import timedelta
            from utils import now, now_iso
            # ilovadagi har bir amal — «botda faol» (5 daqiqada bir marta yoziladi)
            await db.execute("UPDATE student_accounts SET seen_at = ?, blocked_at = NULL WHERE tg_id = ? AND student_id = ? "
                             "AND (seen_at IS NULL OR seen_at < ?)", (now_iso(), request["user"]["id"], sid,
                                                                      (now() - timedelta(minutes=5)).isoformat(timespec="seconds")))
            request["student"], request["course"], request["self"] = st, key, True
            return await handler(request)
    return wrapped


# ---------------------------------------------------------------- yashash joyi (talaba o'zi kiritadi)
NEED_ADDRESS = ("ijara", "qarindosh")  # manzil shart
NEED_POINT = ("ijara",)  # xaritadagi joy shart (tashrif va yo'l uchun)


def home_state(st: dict) -> dict:
    """Talabaning yashash joyi: to'ldirilganmi va talaba o'zi o'zgartira oladimi. Xonadon toifasi (yashil / sariq /
    qizil) talabaga ko'rsatilmaydi va u tomonidan o'zgartirilmaydi — faqat kurs koordinatori."""
    living = st.get("living") or ("ijara" if (st.get("rent_address") or "").strip() else None)
    address = (st.get("rent_address") or "").strip()
    has_point = st.get("lat") is not None
    filled = bool(living) and (living not in NEED_ADDRESS or bool(address)) and (living not in NEED_POINT or has_point)
    started = bool(st.get("living") or address or has_point)
    # koordinator kiritgan yoki fayldan kelgan ma'lumot — talaba o'zgartirmaydi; bo'sh yoki o'zi kiritgan — o'zgartiradi
    editable = (st.get("home_by") == "talaba") or not started
    return {"living": living, "address": address, "lat": st.get("lat"), "lon": st.get("lon"), "filled": filled,
            "editable": editable, "by": st.get("home_by"), "at": st.get("home_at"),
            "need_address": list(NEED_ADDRESS), "need_point": list(NEED_POINT)}


@self_route
async def api_home(request):
    import visits as V
    from webapi import ok
    st = request["student"]
    if request.method == "POST":
        cur = home_state(st)
        if not cur["editable"]:
            return web.json_response({"error": "locked", "message": tr("Yashash joyingizni kurs koordinatori kiritgan — "
                                                                       "o'zgargan bo'lsa, unga murojaat qiling.")}, status=403)
        body = await request.json()
        living = str(body.get("living") or "")
        address = str(body.get("address") or "").strip()
        location = str(body.get("location") or "").strip()
        if living not in V.LIVING:
            return web.json_response({"error": "bad_living", "message": tr("Qayerda yashashingizni tanlang")}, status=400)
        if living in NEED_ADDRESS and len(address) < 8:
            return web.json_response({"error": "no_address", "message": tr("Manzilni to'liq yozing: tuman, ko'cha (mavze), uy, "
                                                                           "xonadon")}, status=400)
        if living in NEED_POINT and not location:
            return web.json_response({"error": "no_point", "message": tr("Xaritadagi joyni ko'rsating: «Turgan joyim» yoki "
                                                                         "«Xaritadan tanlash»")}, status=400)
        d = {"living": living, "address": address, "location": location}  # bo'sh joy — olib tashlanadi
        try:  # toifa (zone) — talabadan qabul qilinmaydi
            await V.set_home(st["id"], d, by="talaba")
        except V.VisitError as e:
            return web.json_response({"error": e.code, "message": e.message}, status=400)
        st = await db.get_student(st["id"])
    return ok({**home_state(st), "titles": {k: tr(v) for k, v in V.LIVING.items()}})


# ---------------------------------------------------------------- ijtimoiy toifa (talaba o'zi belgilaydi)
async def social_needed(st: dict) -> bool:
    """Toifasi yo'q va hali javob bermagan — ilovada (yashash joyidan keyin) so'raladi."""
    if st.get("social_at"):
        return False
    return not await db.fetchone("SELECT 1 FROM student_categories WHERE student_id = ?", (st["id"],))


@self_route
async def api_social(request):
    import socialcat as SC
    from webapi import ok
    st = request["student"]
    if request.method == "POST":
        body = await request.json()
        items = [] if body.get("none") else [x for x in body.get("items") or [] if isinstance(x, dict)]
        try:
            await SC.student_set(st["id"], items)
        except SC.SocialError as e:
            return web.json_response({"error": e.code, "message": tr(e.message)}, status=400)
        st = await db.get_student(st["id"])
    rows = await SC.of_student(st["id"])
    return ok({"items": [{"category": r["category"], "sub": r["sub"], "label": tr(r["label"]), "note": r["note"] or "",
                          "mine": r["source"] == "talaba", "pending": r["pending"]} for r in rows],
               "meta": {k: {"title": tr(c["title"]), "subs": {a: tr(b) for a, b in c["subs"].items()}} for k, c in SC.CATS.items()},
               "answered": bool(st.get("social_at")), "needed": await social_needed(st)})


# ---------------------------------------------------------------- shaxs
async def api_me(request):
    from webapi import child_card, ok
    uid = request["user"]["id"]
    cards, unread = [], 0
    import studentnotify
    await studentnotify.mark_seen(uid)  # talaba ilovani ochdi — «botda faol»
    for key, st in await my_students(uid):
        with use_course(None if key == "_" else key):
            card = await child_card(st, key)
            card["home_needed"] = not home_state(st)["filled"]  # ilova ochilganda — avval yashash joyi so'raladi
            card["social_needed"] = await social_needed(st)  # so'ng — ijtimoiy toifa
            cards.append(card)
            unread += (await db.fetchone("SELECT COUNT(*) n FROM student_notices WHERE student_id = ? AND read_at IS NULL",
                                         (st["id"],)))["n"]
    import loc
    sb = botlar.student_bot(request.app["bot"])
    try:
        bot_name = (await sb.me()).username if sb else ""
    except Exception:  # noqa: BLE001
        bot_name = ""
    return ok({"user": {"id": uid, "name": request["user"].get("first_name", "")}, "lang": request["lang"],
               "role": "student" if cards else "unlinked", "children": cards,
               "unread": {"messages": 0, "notifications": unread}, "university": loc.term(UNIVERSITY_NAME),
               "staff": None, "bot": bot_name, "app_session": bool(request.get("app_session")), "student": True})


async def api_settings(request):
    from webapi import ok
    return ok({"lang": request["lang"], "flags": {}})


async def api_settings_save(request):
    from webapi import LANGS, ok
    body = await request.json()
    if body.get("lang") in LANGS:
        await central.set_lang(request["user"]["id"], body["lang"])
    return ok({"ok": True})


# ---------------------------------------------------------------- bildirishnomalar (choralar, hujjatlar)
_KIND = {"chora": "warn", "xat": "warn", "doc": "doc"}


async def api_notices(request):
    from webapi import ok
    items = []
    for key, st in await my_students(request["user"]["id"]):
        d = db.for_course(key)
        for n in await d.fetchall("SELECT * FROM student_notices WHERE student_id = ? ORDER BY id DESC LIMIT 80", (st["id"],)):
            items.append({"id": n["id"], "text": n["text"], "at": n["created_at"], "read": bool(n["read_at"]),
                          "kind": _KIND.get(n["kind"], n["kind"]), "student_id": st["id"], "course": key,
                          "document_id": n["document_id"]})
    items.sort(key=lambda n: n["at"], reverse=True)
    return ok({"items": items[:80]})


async def api_notices_read(request):
    from utils import now_iso
    from webapi import ok
    for key, st in await my_students(request["user"]["id"]):
        await db.for_course(key).execute("UPDATE student_notices SET read_at = ? WHERE student_id = ? AND read_at IS NULL",
                                         (now_iso(), st["id"]))
    return ok({"ok": True})


async def api_pulse(request):
    from webserver import APP_VERSION
    from webapi import ok
    n = 0
    for key, st in await my_students(request["user"]["id"]):
        n += (await db.for_course(key).fetchone(
            "SELECT COUNT(*) n FROM student_notices WHERE student_id = ? AND read_at IS NULL", (st["id"],)))["n"]
    return ok({"v": APP_VERSION, "notifications": n, "messages": 0, "surveys": 0})


# ---------------------------------------------------------------- choralar
@self_route
async def api_measures(request):
    import discipline
    from webapi import ok
    grounds = {"davomat": tr("Davomat (sababsiz dars qoldirish)"), "tartib": tr("Ichki tartib qoidalarini buzish"),
               "trimestr": tr("Trimestr to'lovi qarzdorligi")}
    items = [{"measure": m["measure"], "title": tr(m["title"]), "ground": grounds.get(m["ground"], m["ground"]),
              "number": m.get("number"), "date": m.get("date"), "letter": bool(m.get("letter_date"))}
             for m in await discipline.student_measures(request["student"]["id"])]
    return ok({"items": items})


# ---------------------------------------------------------------- tadbir va tashriflar
def _plan(p: dict, sid: int) -> dict:
    import visits as V
    me = next((s for s in p.get("students") or [] if s["student_id"] == sid), None)
    return {"id": p["id"], "type": p["type"], "type_title": tr(p["type_title"]), "title": p["title"], "date": p["visit_date"],
            "start": p["start_time"], "end": p["end_time"], "place": p.get("place") or "", "when": p.get("when") or "",
            "status": p["status"], "capacity": p.get("capacity"), "count": len(p.get("students") or []),
            "reg": V.reg_state(p), "response": (me or {}).get("response"), "source": (me or {}).get("source"),
            "can_confirm": bool(me) and p["type"] == V.IJARA and p["status"] == V.TALABA
                           and (me or {}).get("response") in (V.KUTILMOQDA, V.VAQT_TAKLIF)}


@self_route
async def api_events(request):
    import visits as V
    from webapi import ok
    sid = request["student"]["id"]
    ag = await V.student_agenda(sid)
    mine = [_plan(p, sid) for p in ag["mine"]]
    for p in await V.open_for_student(sid):  # javob kutayotgan ijara tashrifi
        if not any(x["id"] == p["id"] for x in mine):
            mine.append(_plan(await V.get(p["id"], full=False), sid))
    opened = []
    for p in ag["open"]:
        x = _plan(p, sid)
        clash = await V.conflicts(p, sid)
        x["conflicts"] = [{"kind": c["kind"], "time": c["time"], "title": c["title"], "sub": c.get("sub") or "",
                           "exam": bool(c.get("exam"))} for c in clash]
        opened.append(x)
    mine.sort(key=lambda x: (x["date"], x["start"] or ""))
    return ok({"mine": mine, "open": opened})


@self_route
async def api_event_action(request):
    """{action: reg | unreg | confirm, force: bool} — ro'yxatdan o'tish (to'qnashuv bo'lsa — avval ko'rsatiladi,
    force bilan «baribir qo'shilaman»), chiqish, ijara tashrifini tasdiqlash."""
    import visits as V
    from webapi import ok
    sid, pid = request["student"]["id"], int(request.match_info["pid"])
    body = await request.json()
    act, bot = body.get("action"), request.app["bot"]
    try:
        if act == "reg":
            p = await V.get(pid, full=False)
            clash = await V.conflicts(p, sid) if await V.can_register(p, sid) else []
            if clash and not body.get("force"):
                return ok({"ok": False, "conflicts": [{"kind": c["kind"], "time": c["time"], "title": c["title"],
                                                       "sub": c.get("sub") or "", "exam": bool(c.get("exam"))} for c in clash]})
            await V.register(bot, pid, sid, conflict=V.conflict_note(clash) if clash else None)
        elif act == "unreg":
            await V.unregister(bot, pid, sid)
        elif act == "confirm":
            await V.answer(bot, pid, sid, V.TASDIQLADI, via="bot")
        else:
            return web.json_response({"error": "bad_action"}, status=400)
    except V.VisitError as e:
        return web.json_response({"error": e.code, "message": e.message}, status=400)
    return ok({"ok": True})


# ---------------------------------------------------------------- hujjat — talabalar botidagi chatga
@self_route
async def api_document_send(request):
    import docstore
    from aiogram.types import BufferedInputFile
    from utils import doc_title
    from webapi import bad, ok
    doc = await db.get_document(int(request.match_info["did"]))
    if not doc or doc["student_id"] != request["student"]["id"] or doc.get("revoked"):
        return bad("not_found", 404)
    main = request.app["bot"]
    data = await docstore.load(botlar.main_bot(main), request["course"], doc["file_id"])
    sb = botlar.student_bot(main)
    try:
        await sb.send_document(request["user"]["id"], BufferedInputFile(data, filename=doc.get("file_name") or "hujjat.pdf"),
                               caption=f"📄 <b>{doc_title(doc['doc_type'])}</b>")
        return ok({"sent": True})
    except Exception as e:  # noqa: BLE001  (talaba botni bloklagan va h.k.)
        log.warning("Talabaga hujjat yuborilmadi: %s", e)
        return ok({"sent": False})


def setup(r) -> None:
    import webapi as W
    r.add_get("/api/s/me", api_me)
    r.add_get("/api/s/settings", api_settings)
    r.add_post("/api/s/settings", api_settings_save)
    r.add_get("/api/s/notifications", api_notices)
    r.add_post("/api/s/notifications/read", api_notices_read)
    r.add_get("/api/s/pulse", api_pulse)
    base = "/api/s/{course}/{sid:\\d+}"
    # ota-ona ilovasidagi bilan bir xil ma'lumot — talabaning o'zi uchun (child_route o'rniga self_route)
    for tail, h in (("overview", W.api_overview), ("attendance", W.api_attendance), ("schedule", W.api_schedule),
                    ("grades", W.api_grades), ("finance", W.api_finance), ("trends", W.api_trends),
                    ("documents", W.api_documents), ("documents/{did:\\d+}/file", W.api_document_file),
                    ("documents/{did:\\d+}/pages", W.api_document_pages),
                    ("documents/{did:\\d+}/page/{n:\\d+}", W.api_document_page)):
        r.add_get(f"{base}/{tail}", self_route(h.inner))
    r.add_post(base + "/documents/{did:\\d+}/send", api_document_send)
    r.add_get(base + "/measures", api_measures)
    r.add_get(base + "/home", api_home)
    r.add_post(base + "/home", api_home)
    r.add_get(base + "/social", api_social)
    r.add_post(base + "/social", api_social)
    r.add_get(base + "/events", api_events)
    r.add_post(base + "/events/{pid:\\d+}", api_event_action)

