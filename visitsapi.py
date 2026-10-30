"""Boshqaruv paneli: «Tashriflar» bo'limining API si (rejalar, dalolatnoma, suratlar, yashash joyi, dashboard, hisobot).
Mantiq — visits.py da; bu yerda faqat ruxsatlar va so'rov/javob."""
from __future__ import annotations

import json
from datetime import date, timedelta

from aiohttp import web

import visits as V
from database import db
from tenancy import viewer_scope
from utils import today
from webapi import _file_resp, _visible, bad, ok, staff_route


def _uid(request) -> int:
    return request["user"]["id"]


async def _body(request) -> dict:
    try:
        d = await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _err(e: V.VisitError) -> web.Response:
    return web.json_response({"error": e.code, "message": e.message}, status=403 if e.code == "forbidden" else
                             404 if e.code == "not_found" else 400)


async def _plan(request, pid: int) -> dict | None:
    p = await V.get(pid)
    return p if p and V.can_manage(p, _uid(request)) else None


def _pub(p: dict, uid: int) -> dict:
    """Reja — panel uchun (talabalarning Telegram ID si chiqmaydi, faqat «botga ulangan»)."""
    p = dict(p)
    p["students"] = [{**{k: v for k, v in s.items() if k not in ("tg_id", "tg_name", "visit_code")},
                      "linked": bool(s.get("tg_id"))} for s in p.get("students") or []]
    p["can_manage"] = V.can_manage(p, uid)
    return p


@staff_route
async def api_visits(request):
    uid = _uid(request)
    q = request.query
    t = today()
    frm = q.get("from") or (t - timedelta(days=t.weekday() + 7 * 5)).isoformat()
    to = q.get("to") or (t + timedelta(days=7 * 10)).isoformat()
    rows = await V.plans(uid, frm, to, q.get("status", ""))
    return ok({"items": [_pub(r, uid) for r in rows], "from": frm, "to": to, "counts": await V.counts(uid),
               "super": V.is_super(uid), "types": V.TURLAR, "statuses": V.HOLATLAR, "answers": V.JAVOBLAR,
               "living": V.LIVING, "zones": V.ZONES, "geo": V._geo_on()})


@staff_route
async def api_visits_badge(request):
    return ok(await V.counts(_uid(request)))


@staff_route
async def api_visit_new(request):
    d = await _body(request)
    try:
        p = await V.create(d, _uid(request), viewer_scope())
    except V.VisitError as e:
        return _err(e)
    send_error = None
    if d.get("send"):  # «Saqlash va yuborish»: yuborib bo'lmasa — qoralama saqlanib qoladi, sababi aytiladi
        try:
            p = await V.send(request.app["bot"], p["id"], _uid(request))
        except V.VisitError as e:
            send_error = {"error": e.code, "message": e.message}
    return ok({"ok": True, "item": _pub(p, _uid(request)), "delivery": p.get("delivery"), "send_error": send_error})


@staff_route
async def api_visit(request):
    p = await _plan(request, int(request.match_info["pid"]))
    if not p:
        return bad("not_found", 404)
    return ok({"item": _pub(p, _uid(request))})


@staff_route
async def api_visit_update(request):
    try:
        p = await V.update(int(request.match_info["pid"]), await _body(request), _uid(request), viewer_scope())
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True, "item": _pub(p, _uid(request))})


@staff_route
async def api_visit_delete(request):
    try:
        await V.delete(int(request.match_info["pid"]), _uid(request))
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True})


@staff_route
async def api_visit_action(request):
    """Holat o'zgartiruvchi amallar: yuborish, vaqt, taklifni qabul, shundayligicha tasdiqlash, bajarildi, bekor qilish,
    talaba javobini belgilash, tadbir ishtirokchilari, botda e'lon va ro'yxatga olish."""
    pid, act, uid, bot = int(request.match_info["pid"]), request.match_info["act"], _uid(request), request.app["bot"]
    d = await _body(request)
    try:
        if act == "send":
            p = await V.send(bot, pid, uid)
        elif act == "time":
            p = await V.change_time(bot, pid, uid, d.get("visit_date"), d.get("start_time"), d.get("end_time"), d.get("reason"))
        elif act == "accept":
            p = await V.accept_proposal(bot, pid, int(d.get("student_id") or 0), uid)
        elif act == "confirm":
            p = await V.confirm(bot, pid, uid, force=True)
        elif act == "done":
            p = await V.done(pid, uid, d.get("result") or "", d.get("problem") or "")
        elif act == "cancel":
            p = await V.cancel(bot, pid, uid, d.get("reason") or "")
        elif act == "students":  # tadbir / madaniy tashrif ishtirokchilari (aktual rejada ham)
            p = await V.set_participants(bot, pid, uid, d.get("student_ids") or [], viewer_scope())
        elif act == "announce":  # botda e'lon (aktual rejada): guruhlar, joylar soni
            p = await V.announce(bot, pid, uid, d, viewer_scope())
        elif act in ("regclose", "regopen"):  # e'londa ro'yxatga olishni yopish / qayta ochish
            p = await V.set_registration(bot, pid, uid, act == "regopen")
        elif act == "answer":  # talaba og'zaki (telefonda) javob berdi — koordinator belgilaydi
            cur = await V.get(pid, full=False)
            if not cur or not V.can_manage(cur, uid):
                return bad("forbidden", 403)
            p = await V.answer(bot, pid, int(d.get("student_id") or 0), d.get("response") or "", d.get("proposed_date"),
                               d.get("proposed_time"), d.get("comment"), via="panel")
        else:
            return bad("bad_action")
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True, "item": _pub(await V.get(p["id"]), uid), "delivery": p.get("delivery")})


# ---------------------------------------------------------------- dalolatnoma va suratlar
@staff_route
async def api_visit_act_save(request):
    pid = int(request.match_info["pid"])
    aid = request.match_info.get("aid")
    try:
        a = await V.save_act(pid, await _body(request), _uid(request), int(aid) if aid else None)
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True, "act": a})


@staff_route
async def api_visit_act_delete(request):
    try:
        await V.delete_act(int(request.match_info["aid"]), _uid(request))
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True})


@staff_route
async def api_visit_act_docx(request):
    """POST — panelda yasalgan Word faylni saqlash; GET — yuklab olish."""
    aid = int(request.match_info["aid"])
    a = await db.fetchone("SELECT * FROM visit_acts WHERE id = ?", (aid,))
    p = await _plan(request, a["plan_id"]) if a else None
    if not p:
        return bad("not_found", 404)
    if request.method == "POST":
        data = await request.read()
        try:
            return ok({"ok": True, "act": await V.store_act_docx(aid, data, _uid(request))})
        except V.VisitError as e:
            return _err(e)
    f = V.file_path(a.get("docx_path"))
    if not f:
        return bad("not_found", 404)
    try:
        fio = json.loads(a["data"]).get("fio") or ""
    except ValueError:
        fio = ""
    name = "Dalolatnoma" + ("_" + "_".join(fio.split()[:2]) if fio else "") + ".docx"
    return _file_resp(name, f.read_bytes())


@staff_route
async def api_visit_photo_upload(request):
    pid = int(request.match_info["pid"])
    if not await _plan(request, pid):
        return bad("not_found", 404)
    act_id, saved = None, []
    try:
        async for part in await request.multipart():
            if part.name == "act_id":
                v = (await part.text()).strip()
                act_id = int(v) if v.isdigit() else None
            elif part.name == "file" and part.filename:
                data = bytes(await part.read(decode=False))
                saved.append(await V.add_photo(pid, part.filename, part.headers.get("Content-Type", ""), data,
                                               _uid(request), act_id))
    except V.VisitError as e:
        return _err(e)
    return ok({"ok": True, "photos": saved}) if saved else bad("empty")


@staff_route
async def api_visit_photo(request):
    fid = int(request.match_info["fid"])
    f = await V.photo(fid)
    if not f or not await _plan(request, f["plan_id"]):
        return bad("not_found", 404)
    if request.method == "DELETE":
        try:
            await V.delete_photo(fid, _uid(request))
        except V.VisitError as e:
            return _err(e)
        return ok({"ok": True})
    path = V.file_path(f["path"])
    if not path:
        return bad("not_found", 404)
    return web.Response(body=path.read_bytes(), content_type=f.get("mime") or "image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400"})


# ---------------------------------------------------------------- talabalar: tanlash, yashash joyi, yo'l, havola
@staff_route
async def api_visit_students(request):
    return ok({"items": await V.pick_students(viewer_scope(), request.query.get("q", ""))})


async def _student(request):
    st = await db.get_student(int(request.match_info["sid"]))
    return st if _visible(st) else None


@staff_route
async def api_visit_student(request):
    st = await _student(request)
    if not st:
        return bad("not_found", 404)
    if request.method == "POST":
        try:
            res = await V.set_home(st["id"], await _body(request))
        except V.VisitError as e:
            return _err(e)
    else:
        res = await V.student_visits(st["id"])
    res["account"] = {"linked": bool(res.get("account")), "via": (res.get("account") or {}).get("via"),
                      "at": (res.get("account") or {}).get("linked_at")}
    uid = _uid(request)
    every = V.is_super(uid)
    res["visits"] = [{k: v for k, v in x.items() if k in ("id", "type", "type_title", "title", "status", "status_title",
                                                          "when", "visit_date", "response", "coordinator_name")}
                     for x in res["visits"] if every or x["coordinator_id"] == uid]
    res["living_titles"], res["zones"] = V.LIVING, V.ZONES
    return ok(res)


@staff_route
async def api_visit_student_route(request):
    st = await _student(request)
    if not st:
        return bad("not_found", 404)
    try:
        return ok({"talabalar": [await V.student_route(st["id"], _here(request))],
                   "turgan_joy": None if not _here(request) else dict(zip(("lat", "lon"), _here(request)))})
    except ValueError:
        return bad("bad_location")
    except V.VisitError as e:
        return _err(e)


def _here(request) -> tuple[float, float] | None:
    q = request.query
    if q.get("lat") and q.get("lon"):
        return float(q["lat"]), float(q["lon"])
    return None


@staff_route
async def api_visit_route(request):
    """Rejadagi talabalar manziliga qanday boriladi (turgan joy berilsa — yo'nalish bilan)."""
    pid = int(request.match_info["pid"])
    if not await _plan(request, pid):
        return bad("not_found", 404)
    try:
        return ok(await V.plan_route(pid, _here(request)))
    except ValueError:
        return bad("bad_location")
    except V.VisitError as e:
        return _err(e)


@staff_route
async def api_visit_student_invite(request):
    """Talabaning shaxsiy havolasi — koordinator talabaga yuboradi (ochsa — tashrif xabarlari unga keladi)."""
    st = await _student(request)
    if not st:
        return bad("not_found", 404)
    return ok({"url": await V.invite_url(request.app["bot"], st["id"])})


@staff_route
async def api_visit_dashboard(request):
    return ok(await V.dashboard(viewer_scope()))


@staff_route
async def api_visit_districts(request):
    return web.json_response(await V.district_shapes(), headers={"Cache-Control": "private, max-age=86400"})


@staff_route
async def api_visit_report(request):
    t = today()
    frm = request.query.get("from") or date(t.year if t.month >= 9 else t.year - 1, 9, 1).isoformat()
    to = request.query.get("to") or ((t.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).isoformat()
    rep = await V.report(_uid(request), frm, to)
    rep["items"] = [_pub(r, _uid(request)) for r in rep["items"]]
    return ok(rep)


def setup(r) -> None:
    r.add_get("/api/staff/visits", api_visits)
    r.add_get("/api/staff/visits/badge", api_visits_badge)
    r.add_post("/api/staff/visits", api_visit_new)
    r.add_get("/api/staff/visits/students", api_visit_students)
    r.add_get("/api/staff/visits/dashboard", api_visit_dashboard)
    r.add_get("/api/staff/visits/districts", api_visit_districts)
    r.add_get("/api/staff/visits/report", api_visit_report)
    r.add_get("/api/staff/visits/{pid:\\d+}", api_visit)
    r.add_post("/api/staff/visits/{pid:\\d+}", api_visit_update)
    r.add_delete("/api/staff/visits/{pid:\\d+}", api_visit_delete)
    r.add_post("/api/staff/visits/{pid:\\d+}/acts", api_visit_act_save)
    r.add_post("/api/staff/visits/{pid:\\d+}/acts/{aid:\\d+}", api_visit_act_save)
    r.add_post("/api/staff/visits/{pid:\\d+}/photos", api_visit_photo_upload)
    r.add_get("/api/staff/visits/{pid:\\d+}/route", api_visit_route)
    r.add_post("/api/staff/visits/{pid:\\d+}/{act:[a-z]+}", api_visit_action)
    r.add_delete("/api/staff/visits/acts/{aid:\\d+}", api_visit_act_delete)
    r.add_route("*", "/api/staff/visits/acts/{aid:\\d+}/docx", api_visit_act_docx)
    r.add_get("/api/staff/visits/photos/{fid:\\d+}", api_visit_photo)
    r.add_delete("/api/staff/visits/photos/{fid:\\d+}", api_visit_photo)
    r.add_get("/api/staff/visits/student/{sid:\\d+}", api_visit_student)
    r.add_post("/api/staff/visits/student/{sid:\\d+}", api_visit_student)
    r.add_get("/api/staff/visits/student/{sid:\\d+}/route", api_visit_student_route)
    r.add_get("/api/staff/visits/student/{sid:\\d+}/invite", api_visit_student_invite)
