"""Telegram Web App (bot ichida ochiladigan ilova) uchun API.

Kirish: Telegram har bir ochilishda foydalanuvchini imzolangan `initData` bilan tasdiqlaydi — server imzoni bot
tokeni bilan tekshiradi (HMAC-SHA256), login va parol kerak emas. Ma'lumotlar botning o'zi ishlatadigan
funksiyalardan olinadi (davomat, chegaralar, GPA, qarzdorlik, dinamika) — raqamlar botdagi bilan bir xil.
Ota-ona faqat o'ziga bog'langan farzandning ma'lumotini oladi; kurs koordinatori — faqat o'z kursini.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import re

import deskauth
import live
import logging
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

import absence
import academic
import chat
import export
import individual
import loc
import status
import trends
import course_trends
from config import (ADMIN_COURSE, GPA_MIN, BOT_TOKEN, DATA_DIR, LOG_DIR, PAIR_TIMES, SUPERADMIN_IDS, UNIVERSITY_NAME,
                    WEBAPP_AUTH_TTL, WEBAPP_DEV_USER, WEBAPP_URL)
from database import db
from family import all_children, ensure_parent_here, known_contact, parent_courses
from i18n import tr, use_lang
from tenancy import (central, coordinator_groups, course_keys, course_title, current_course, current_user, group_scope,
                     in_scope, reload_registry, scope_label,
                     scope_students, use_course, viewer_scope)
from utils import (WEEKDAYS, truncate2, doc_title, group_key, lesson_kind, name_score, normalize_text, parse_user_dates,
                   semester_start, today, week_bounds, week_type_of)

log = logging.getLogger("webapp")
LANGS = ("uz", "ru", "en")
FLAGS = ("notify_instant", "notify_daily", "notify_warn", "notify_pay")


# ================================================================ Telegram imzosi
def verify_init_data(init_data: str, token: str = BOT_TOKEN, ttl: int = WEBAPP_AUTH_TTL) -> dict | None:
    """Telegram Web App initData ni tekshiradi; to'g'ri bo'lsa foydalanuvchi ma'lumotini qaytaradi."""
    if not init_data or not token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0"))
        user = json.loads(pairs.get("user", "{}"))
    except (ValueError, json.JSONDecodeError):
        return None
    if ttl and time.time() - auth_date > ttl:
        return None
    return user if user.get("id") else None


async def _staff_name(uid: int) -> str:
    if uid in SUPERADMIN_IDS and uid not in ADMIN_COURSE:
        return "Super-admin"
    coords = (await central.registry())[1]
    return next((c["name"] for c in coords if c["user_id"] == uid and c.get("name")), "") or "Kurs koordinatori"


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/") or request.path.startswith(("/api/app/login", "/api/app/info")):
        return await handler(request)  # telefon ilovasining kirish so'rovi — hali seans yo'q
    user = verify_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    auth = request.headers.get("Authorization", "")
    if user is None and auth.startswith("Bearer "):
        # telefon ilovasi / brauzer: Telegram botda tasdiqlangan seans (appauth.py)
        import appauth
        found = await appauth.verify(auth[7:].strip())
        if found:
            uid0 = found[0]
            name = (await _staff_name(uid0) if uid0 in ADMIN_COURSE or uid0 in SUPERADMIN_IDS
                    else ((await known_contact(uid0)) or {}).get("name") or "")
            user = {"id": uid0, "first_name": name}
            request["app_session"] = found[1]
    if user is None and request.headers.get("X-Desk") == "1":
        # kompyuter versiyasi: imzolangan seans cookie; X-Desk sarlavhasi begona saytlardan so'rovni to'sadi (CSRF)
        uid = deskauth.verify_cookie(request.cookies.get(deskauth.COOKIE))
        if uid and (uid in ADMIN_COURSE or uid in SUPERADMIN_IDS):
            user = {"id": uid, "first_name": await _staff_name(uid)}
            request["desk"] = True
    if user is None and WEBAPP_DEV_USER and request.headers.get("X-Dev-User"):
        user = {"id": WEBAPP_DEV_USER, "first_name": "Dev"}  # faqat sinov rejimi (WEBAPP_DEV_USER)
    if user is None:
        return web.json_response({"error": "unauthorized"}, status=401)
    request["user"] = user
    uid = user["id"]
    lang = await central.get_lang(uid)
    if uid in ADMIN_COURSE or uid in SUPERADMIN_IDS:
        lang = "uz"  # kurs koordinatori va super-admin interfeysi — o'zbek tilida (bot bilan bir xil)
    request["lang"] = lang or (user.get("language_code") if user.get("language_code") in LANGS else "uz")
    token = current_user.set(uid)  # kurs koordinatorining guruh doirasi (viewer_scope) va jurnallar uchun
    try:
        with use_lang(request["lang"]):
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception:
                log.exception("Web App API xatosi: %s %s (foydalanuvchi %s)", request.method, request.path, uid)
                return web.json_response({"error": "server"}, status=500)
    finally:
        current_user.reset(token)


def ok(data) -> web.Response:
    return web.json_response(data, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


def bad(error: str, code: int = 400) -> web.Response:
    return web.json_response({"error": error}, status=code)


def _course_arg(key: str) -> str | None:
    keys = db.keys()
    if keys == ["_"]:
        return "_"
    return key if key in keys else None


# ================================================================ ma'lumotlar (ota-ona tilida)
def _gpa(v: float | None) -> float | None:
    """GPA yaxlitlanmaydi — 2 xonagacha kesilgan holda yuboriladi (ilova uni boshqa yaxlitlamaydi)."""
    return None if v is None else float(truncate2(v))


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


async def child_card(st: dict, key: str) -> dict:
    name = loc.student_name(st)
    tutor_name, tutor_phone = await db.coordinator_contact(st, key)
    return {"id": st["id"], "course": key, "name": name, "short": " ".join(name.split()[:2]), "initials": _initials(name),
            "group": st.get("group_name") or "", "year": st.get("course"), "faculty": loc.term(st.get("faculty") or ""),
            "hemis_id": st.get("hemis_id") or "", "payment_form": tr(st["payment_form"]) if st.get("payment_form") else None,
            "grant": (st.get("payment_form") or "").lower().startswith("davlat"),
            "tutor": {"name": loc.person(tutor_name) if tutor_name else None, "phone": tutor_phone}}


def _levels() -> list[dict]:
    return [{"hours": h, "pairs": h / 2, "action": absence.action_for(i)} for i, h in enumerate(absence.LEVELS)]


def _attendance(sm: dict | None) -> dict | None:
    if not sm:
        return None
    lvl = absence.level_index(sm["counted"])
    nxt = lvl + 1 if lvl + 1 < len(absence.LEVELS) else None
    return {"percent": round(sm["percent"]) if sm.get("percent") is not None else None, "source": sm["source"],
            "as_of": sm.get("as_of"), "counted_hours": sm["counted"], "counted_pairs": sm["counted"] / 2,
            "excused_hours": sm.get("excused") or 0, "level": lvl, "action": absence.action_for(lvl) if lvl >= 0 else None,
            "next": ({"hours": absence.LEVELS[nxt], "pairs": absence.LEVELS[nxt] / 2, "action": absence.action_for(nxt),
                      "left_hours": max(absence.LEVELS[nxt] - sm["counted"], 0)} if nxt is not None else None),
            "levels": _levels(), "note": absence.source_note(sm)}


async def _payments(st: dict, pays: dict, dl: dict) -> dict:
    out = {}
    for kind in ("kontrakt", "trimestr"):
        p = pays.get(kind)
        deadline = dl.get(kind)
        days_left = (deadline - today()).days if deadline else None
        if kind == "kontrakt" and (st.get("payment_form") or "").lower().startswith("davlat"):
            out[kind] = {"state": "grant"}
        elif p is None:
            out[kind] = {"state": "none"}
        else:
            out[kind] = {"state": "debt" if p["debt"] > 0 else "clear", "debt": p["debt"], "contract": p.get("contract"),
                         "paid": p.get("paid"), "percent": p.get("percent"), "as_of": p.get("as_of"),
                         "deadline": deadline.isoformat() if deadline else None, "days_left": days_left}
    return out


async def _last_update() -> str | None:
    row = await db.fetchone("SELECT MAX(v) AS v FROM (SELECT MAX(updated_at) AS v FROM students "
                            "UNION ALL SELECT value FROM settings WHERE key LIKE 'updated:%')")
    return row["v"] if row else None


async def overview(st: dict, key: str) -> dict:
    s = await status.student_status(st)
    dl = await status.deadlines()
    lessons = await individual.lessons_on(st, today())
    return {"child": await child_card(st, key), "attendance": _attendance(s["attendance"]),
            "academic": {"count": len(s["debts"]), "debts": [_debt(d) for d in s["debts"]]},
            "gpa": _gpa(s["gpa"]), "gpa_low": s["flags"]["gpa"], "gpa_min": GPA_MIN,
            "pays": await _payments(st, s["pays"], dl), "issues": s["issues"],
            "trend": await trends.short_line(st), "dynamics": await trends.mini(st), "today": [_lesson(x) for x in lessons],
            "updated": await _last_update()}


def _lesson(x: dict, att: dict | None = None) -> dict:
    kind = lesson_kind(x.get("lesson_type"))
    pt = PAIR_TIMES.get(x.get("pair")) or ("", "")
    return {"pair": x.get("pair"), "start": x.get("start_time") or pt[0], "end": x.get("end_time") or pt[1],
            "subject": loc.term(x.get("subject") or ""),
            "type": tr("Leksiya") if kind == "leksiya" else tr("Seminar") if kind == "seminar" else (x.get("lesson_type") or ""),
            "teacher": loc.person(x.get("teacher")) if x.get("teacher") else "", "room": loc.term(x.get("room") or ""),
            "subgroup": x.get("subgroup"), "status": (att or {}).get((x.get("pair"), normalize_text(x.get("subject") or "")))}


# ================================================================ ota-ona: shaxs va farzandlar
async def api_me(request: web.Request) -> web.Response:
    uid = request["user"]["id"]
    blocked = False
    for k in db.keys():
        if await db.for_course(k).is_blocked(uid):
            blocked = True
    children = [] if blocked else await all_children(uid)
    cards, unread_msgs, unread_notes = [], 0, 0
    for c in children:
        key = c.get("course_key") or "_"
        with use_course(None if key == "_" else key):
            cards.append(await child_card(c, key))
    for k in await parent_courses(uid):
        d = db.for_course(k)
        unread_notes += await d.unread_notifications(uid)
        unread_msgs += sum((await d.unread_for_parent(uid)).values())
    role = ("super" if uid in SUPERADMIN_IDS else "staff" if uid in ADMIN_COURSE else "blocked" if blocked
            else "parent" if cards else "pending" if await known_contact(uid) else "new")
    staff = None
    if role in ("staff", "super"):
        key = await _staff_course(request)
        mine = coordinator_groups(uid) if group_scope(uid) is not None else {}
        staff = {"course": key, "title": course_title(key) if key and key != "_" else "",
                 "groups": sorted(mine.values(), key=str.lower),  # koordinatorga biriktirilgan guruhlar (bo'sh — butun kurs)
                 "courses": [{"key": k, "title": course_title(k)} for k in course_keys()] if role == "super" else []}
    return ok({"user": {"id": uid, "name": request["user"].get("first_name", "")}, "lang": request["lang"],
               "role": role, "children": cards, "unread": {"messages": unread_msgs, "notifications": unread_notes},
               "university": loc.term(UNIVERSITY_NAME), "staff": staff,
               "bot": await _bot_username(request), "app_session": bool(request.get("app_session"))})


def child_route(handler):
    """/api/c/{course}/{sid}/… — faqat ota-onaga bog'langan farzand; kurs konteksti o'rnatiladi."""
    async def wrapped(request: web.Request) -> web.Response:
        key = _course_arg(request.match_info["course"])
        if key is None:
            return bad("not_found", 404)
        with use_course(None if key == "_" else key):
            st = await db.linked_student(request["user"]["id"], int(request.match_info["sid"]))
            if not st:
                return bad("forbidden", 403)
            request["student"], request["course"] = st, key
            return await handler(request)
    return wrapped


@child_route
async def api_overview(request):
    return ok(await overview(request["student"], request["course"]))


@child_route
async def api_attendance(request):
    st = request["student"]
    sm = await absence.summary(st["id"])
    d2 = today()
    d1 = semester_start()
    rows = await db.fetchall("SELECT date, pair, subject, lesson_type, teacher, status, hours FROM attendance "
                             "WHERE student_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC, pair",
                             (st["id"], d1.isoformat(), d2.isoformat()))
    subjects: dict[str, dict] = {}
    for r in rows:
        s = subjects.setdefault(r["subject"] or "", {"subject": loc.term(r["subject"] or ""), "total": 0, "keldi": 0,
                                                     "kechikdi": 0, "kelmadi": 0, "sababli": 0})
        s["total"] += 1
        s[r["status"]] = s.get(r["status"], 0) + 1
    absences = [{"date": r["date"], "weekday": tr(WEEKDAYS[date.fromisoformat(r["date"]).weekday()]), "pair": r["pair"],
                 "subject": loc.term(r["subject"] or ""), "status": r["status"], "hours": r["hours"]}
                for r in rows if r["status"] != "keldi"]
    hist = await db.att_stats_history(st["id"], d1.isoformat(), limit=12)
    mode, periods = await trends.attendance_periods(st)
    return ok({"summary": _attendance(sm), "absences": absences[:120],
               "subjects": sorted(subjects.values(), key=lambda x: -(x["kelmadi"] + x["sababli"])),
               "hemis": [{"as_of": h["as_of"], **absence.stats_hours(h)} for h in hist],
               "hemis_periods": absence.hemis_periods(hist),  # kunlik ro'yxat bo'lmaganda — davrlar bo'yicha
               "weeks": [{"start": p["start"].isoformat(), "end": p["end"].isoformat(), "pct": round(p["pct"]),
                          "unexc": p["unexc"]} for p in periods], "mode": mode})


@child_route
async def api_schedule(request):
    st = request["student"]
    try:
        base = date.fromisoformat(request.query.get("week", "")) if request.query.get("week") else today()
    except ValueError:
        base = today()
    if not request.query.get("week") and base.weekday() == 6:
        base += timedelta(days=1)  # yakshanba — kelasi hafta
    monday = week_bounds(base)[0]
    ctx = await individual.load(st)
    rows = await db.fetchall("SELECT date, pair, subject, status FROM attendance WHERE student_id = ? AND date BETWEEN ? AND ?",
                             (st["id"], monday.isoformat(), (monday + timedelta(days=5)).isoformat()))
    marks: dict[str, dict] = {}
    for r in rows:
        marks.setdefault(r["date"], {})[(r["pair"], normalize_text(r["subject"] or ""))] = r["status"]
    days = []
    for i in range(6):
        d = monday + timedelta(days=i)
        lessons = await individual.lessons_on(st, d, ctx)
        days.append({"date": d.isoformat(), "weekday": tr(WEEKDAYS[i]), "today": d == today(),
                     "lessons": [_lesson(x, marks.get(d.isoformat())) for x in lessons]})
    return ok({"monday": monday.isoformat(), "week_type": week_type_of(monday), "days": days,
               "prev": (monday - timedelta(days=7)).isoformat(), "next": (monday + timedelta(days=7)).isoformat()})


@child_route
async def api_grades(request):
    st = request["student"]
    summary = await academic.summary(st["id"])
    results = summary["results"]
    items = await db.fetchall("SELECT subject, control_type, semester, score, max_score, date FROM grades WHERE student_id = ?",
                              (st["id"],))
    detail: dict[tuple, list] = {}
    for g in items:
        detail.setdefault((str(g["semester"]), normalize_text(g["subject"])), []).append(
            {"control": loc.term(g["control_type"]), "score": g["score"], "max": g["max_score"], "date": g["date"]})
    sems = {}
    for r in results:
        sem = str(r["semester"])
        sems.setdefault(sem, []).append({"subject": loc.term(r["subject"]), "score": r["score"], "grade": r["grade"],
                                         "debt": r["debt"], "credits": r.get("credits"),
                                         "items": detail.get((sem, normalize_text(r["subject"])), [])})
    gpa, weighted = academic.gpa(results)
    by_sem = academic.semester_gpa(results)
    return ok({"gpa": _gpa(gpa), "gpa_low": academic.gpa_low(gpa), "gpa_min": GPA_MIN, "weighted": weighted,
               "semesters": [{"semester": k, "gpa": _gpa(by_sem.get(k)), "subjects": v}
                                                              for k, v in sorted(sems.items(), reverse=True)],
               "debts": len(summary["debts"]), "debt_list": [_debt(d) for d in summary["debts"]]})


def _debt(d: dict) -> dict:
    """Akademik qarz: fan nomi (ota-ona tilida), semestr, kredit, manba (HEMIS ro'yxati yoki bal bo'yicha)."""
    return {"subject": loc.term(d["subject"]), "score": d.get("score"), "grade": d.get("grade", 2),
            "semester": d.get("semester") or "", "credits": d.get("credits"), "source": d.get("source", "grades"),
            "year": d.get("year")}


@child_route
async def api_finance(request):
    st = request["student"]
    s = await status.student_status(st)
    out = await _payments(st, s["pays"], await status.deadlines())
    for kind in ("kontrakt", "trimestr"):
        hist = await db.payment_history(st["id"], kind, 8)
        out[kind]["history"] = [{"as_of": h["as_of"], "debt": h["debt"], "paid": h.get("paid"),
                                 "note": loc.term(h["note"]) if h.get("note") else None} for h in hist]
    return ok({"payment_form": tr(st["payment_form"]) if st.get("payment_form") else None, **out})


@child_route
async def api_trends(request):
    st = request["student"]
    mode, periods = await trends.attendance_periods(st)
    g = await trends.grade_changes(st)
    sems = await trends.by_semester(st)
    return ok({"mode": mode, "periods": [{"label": trends._period_label(p), "pct": round(p["pct"]), "unexc": p["unexc"]}
                                         for p in periods],
               "uploads": await trends.mini(st),  # har bir yuklangan fayl bo'yicha o'zgarishlar
               "gpa_min": GPA_MIN,
               "semesters": [{**x, "gpa": _gpa(x["gpa"])} for x in sems],
               "grades": {"ref": g["ref"], "month": g["month"], "gpa_old": _gpa(g["gpa_old"]), "gpa_new": _gpa(g["gpa_new"]),
                          "items": [{"subject": loc.term(i["subject"]), "old": i["old"], "new": i["new"],
                                     "delta": i["delta"], "old_grade": i["old_grade"], "new_grade": i["new_grade"]}
                                    for i in g["items"]],
                          "compared": [{"subject": loc.term(r["subject"]), "old": o["score"] if o else None, "new": r["score"]}
                                       for o, r in g.get("compared", [])]}})


@child_route
async def api_documents(request):
    docs = await db.documents_for(request["student"]["id"])
    return ok({"documents": [{"id": d["id"], "title": doc_title(d["doc_type"]), "type": d["doc_type"],
                              "date": d.get("doc_date") or d["created_at"][:10], "comment": d.get("comment") or "",
                              "file_name": d.get("file_name") or "hujjat.pdf", "size": d.get("file_size")}
                             for d in docs if not d.get("revoked")]})


@child_route
async def api_document_send(request):
    """Hujjatni ota-onaning Telegram chatiga yuboradi (har qanday telefonda ishonchli ochiladi)."""
    doc = await db.get_document(int(request.match_info["did"]))
    if not doc or doc["student_id"] != request["student"]["id"] or doc.get("revoked"):
        return bad("not_found", 404)
    import docstore
    from aiogram.types import BufferedInputFile
    from notifier import safe_send_document
    f = doc["file_id"]
    if docstore.is_local(f):
        f = BufferedInputFile(await docstore.load(request.app["bot"], request.match_info["course"], f),
                              filename=doc.get("file_name") or "hujjat.pdf")
    msg = await safe_send_document(request.app["bot"], request["user"]["id"], f,
                                   f"📄 <b>{doc_title(doc['doc_type'])}</b> — {loc.student_name(request['student'])}")
    return ok({"sent": bool(msg)})


@child_route
async def api_document_file(request):
    doc = await db.get_document(int(request.match_info["did"]))
    if not doc or doc["student_id"] != request["student"]["id"] or doc.get("revoked"):
        return bad("not_found", 404)
    import docstore
    data = await docstore.load(request.app["bot"], request.match_info["course"], doc["file_id"])
    return web.Response(body=data, content_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{doc.get("file_name") or "hujjat.pdf"}"'})


# ================================================================ yozishma
def _msg(m: dict) -> dict:
    return {"id": m["id"], "sender": m["sender"], "text": m["text"], "at": m["created_at"], "read": bool(m.get("read_at")),
            "author": loc.person(m["author_name"]) if m["sender"] == "staff" and m.get("author_name") else None}


@child_route
async def api_thread(request):
    st, uid = request["student"], request["user"]["id"]
    await db.mark_thread_read(st["id"], uid, "parent")
    card = await child_card(st, request["course"])
    return ok({"messages": [_msg(m) for m in await db.thread(st["id"], uid)], "tutor": card["tutor"]})


@child_route
async def api_thread_send(request):
    body = await request.json()
    user = request["user"]
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "Ota-ona"
    res = await chat.parent_send(request.app["bot"], user["id"], name, request["student"], body.get("text", ""))
    if not res["ok"]:
        return bad(res["error"])
    return ok(res)


# ================================================================ bildirishnomalar, e'lonlar, sozlamalar
async def api_notifications(request):
    uid = request["user"]["id"]
    items = []
    for k in await parent_courses(uid):
        items += [{**n, "course": k} for n in await db.for_course(k).notifications(uid)]
    items.sort(key=lambda n: n["created_at"], reverse=True)
    return ok({"items": [{"id": n["id"], "text": n["text"], "at": n["created_at"], "read": bool(n["read_at"]),
                          "kind": n.get("kind"), "student_id": n.get("student_id"), "course": n["course"]}
                         for n in items[:80]]})


async def api_notifications_read(request):
    uid = request["user"]["id"]
    for k in await parent_courses(uid):
        await db.for_course(k).mark_notifications_read(uid)
    return ok({"ok": True})


async def api_announcements(request):
    uid = request["user"]["id"]
    items = []
    for k in await parent_courses(uid):
        with use_course(None if k == "_" else k):
            keys = {c["group_key"] for c in await db.parent_children(uid) if c.get("group_key")}
            items += [{"text": loc.pick(a["text"]), "at": a["created_at"]} for a in await db.announcements_for(keys, 20)]
    items.sort(key=lambda a: a["at"], reverse=True)
    return ok({"items": items[:20]})


async def api_settings(request):
    uid = request["user"]["id"]
    courses = await parent_courses(uid)
    parent = await db.for_course(courses[0]).get_parent(uid) if courses else None
    return ok({"lang": request["lang"], "flags": {f: bool((parent or {}).get(f, 1)) for f in FLAGS}})


async def api_settings_save(request):
    uid = request["user"]["id"]
    body = await request.json()
    if body.get("lang") in LANGS:
        await central.set_lang(uid, body["lang"])
    if body.get("key") in FLAGS:
        for k in await parent_courses(uid):
            with use_course(None if k == "_" else k):
                await db.set_parent_flag(uid, body["key"], bool(body.get("value")))
    return ok({"ok": True})


async def api_info(request):
    uid = request["user"]["id"]
    tutors, texts = {}, []
    for c in await all_children(uid):
        key = c.get("course_key") or "_"
        with use_course(None if key == "_" else key):
            card = await child_card(c, key)
            if card["tutor"]["name"] or card["tutor"]["phone"]:
                t = tutors.setdefault((card["tutor"]["name"], card["tutor"]["phone"]), {**card["tutor"], "children": []})
                t["children"].append(card["short"])
            custom = await db.get_setting("info_text")
            if custom:
                texts.append(loc.pick(custom))
    return ok({"levels": _levels(), "tutors": list(tutors.values()), "texts": texts,
               "grades": [{"range": "90–100", "grade": 5}, {"range": "70–89", "grade": 4},
                          {"range": "60–69", "grade": 3}, {"range": "0–59", "grade": 2}]})


async def api_link(request):
    """Farzandi topilmagan ota-ona: ism-familiya va tug'ilgan sana (yoki HEMIS ID) bilan so'rov yuboradi."""
    uid = request["user"]["id"]
    body = await request.json()
    query, verify = normalize_text(body.get("name", "")), (body.get("verify") or "").strip()
    contact = await known_contact(uid)
    if not contact:
        return bad("no_phone")
    if len(query) < 3 or not verify:
        return bad("fields")
    import linking
    if not await linking.can_try(uid):  # F.I.Sh. va tug'ilgan sanani taxmin qilib bo'lmasin
        return bad("too_many_attempts", 429)
    cands = []
    for k in db.keys():
        with use_course(None if k == "_" else k):
            cands += [{**s, "course_key": k} for s in await db.all_students_brief() if name_score(query, s["name_norm"]) >= 0.85]
    dates = parse_user_dates(verify)
    match = [c for c in cands if (c.get("hemis_id") and normalize_text(c["hemis_id"]) == normalize_text(verify))
             or (dates and c.get("birth_date") and c["birth_date"] == dates[0].isoformat())]
    if len(match) != 1:
        await linking.record_try(uid, False)
        return bad("not_matched")  # talaba bor-yo'qligi oshkor qilinmaydi
    await linking.record_try(uid, True)
    st = match[0]
    with use_course(None if st["course_key"] == "_" else st["course_key"]):
        if await db.linked_student(uid, st["id"]):
            return ok({"state": "linked"})
        if await db.has_pending_request(uid, st["id"]):
            return ok({"state": "pending"})
        name = " ".join(x for x in (request["user"].get("first_name"), request["user"].get("last_name")) if x)
        await ensure_parent_here(uid, contact["phone"], name, contact["source"])
        await central.clear_pending(uid)
        rid = await db.create_link_request(uid, st["id"], verify)
        full = await db.get_student(st["id"])
        text = (f"🔗 <b>Farzandni bog'lash so'rovi #{rid}</b> (ilovadan)\n\n👤 Ota-ona: {name}, {contact['phone']}\n"
                f"👨‍🎓 Talaba: {full['full_name']} · {full.get('group_name') or ''} · ID {full['hemis_id']}\n"
                f"Tasdiqlash uchun kiritilgan: {verify}")
        from staffops import notify_link_request
        await notify_link_request(request.app["bot"], rid, name, full, text)
        can = await linking.student_can_confirm(st["id"])
        url = await linking.confirm_url(request.app["bot"], await linking.issue_token(rid)) if can else None
    return ok({"state": "requested", "student_can_confirm": can, "confirm_url": url, "needs_phone": not can})


async def api_link_phone(request):
    """Talaba raqami bazada yo'q — ota-ona farzandining raqamini kiritadi; talaba aynan shu raqam bilan tasdiqlaydi."""
    import linking
    uid = request["user"]["id"]
    body = await request.json()
    key = str(body.get("course") or "_")
    if key not in db.keys():
        return bad("not_found", 404)
    with use_course(None if key == "_" else key):
        done, err = await linking.set_claimed_phone(int(body.get("id") or 0), uid, str(body.get("phone") or ""))
        if not done:
            return bad(err)
        url = await linking.confirm_url(request.app["bot"], await linking.issue_token(int(body["id"])))
    return ok({"confirm_url": url})


# ================================================================ telefon ilovasi: Telegram orqali kirish
async def _bot_username(request) -> str:
    try:
        return (await request.app["bot"].me()).username or ""
    except Exception:  # tarmoq xatosi — ilova tugmasi oddiy t.me havolasisiz qoladi
        return ""


def _client_ip(request) -> str:
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?")


async def api_app_login_start(request):
    import appauth
    if not appauth.allow_start(_client_ip(request)):
        return bad("too_many", 429)
    try:
        body = await request.json()
    except Exception:
        body = {}
    d = await appauth.start(str(body.get("device") or "")[:80])
    me = await request.app["bot"].me()
    return ok({**d, "url": f"https://t.me/{me.username}?start={appauth.START_PREFIX}{d['code']}", "bot": me.username})


async def api_app_login_poll(request):
    import appauth
    return ok(await appauth.poll(request.match_info["code"]))


async def api_app_info(request):
    """Telefon ilovasining ishga tushiruvchi sahifasi uchun (ochiq): bot nomi va joriy manzil. Ilova manzil
    o'zgarganda (masalan, vaqtinchalik tunnel) yangisini botdan olish uchun bot nomini eslab qoladi."""
    resp = ok({"bot": await _bot_username(request), "url": WEBAPP_URL + "/" if WEBAPP_URL else ""})
    resp.headers["Access-Control-Allow-Origin"] = "*"  # ilovaning mahalliy sahifasi boshqa manbadan so'raydi
    return resp


async def api_app_logout(request):
    import appauth
    if request.get("app_session"):
        await appauth.revoke(request["user"]["id"], request["app_session"])
    return ok({"ok": True})


async def api_link_status(request):
    """Ota-onaning kutilayotgan so'rovlari: farzandi tasdiqlashi uchun havola (yoki kurs koordinatori kutilmoqda)."""
    import linking
    return ok({"requests": await linking.parent_requests(request.app["bot"], request["user"]["id"])})


# ================================================================ kurs koordinatori
async def _staff_course(request: web.Request) -> str | None:
    uid = request["user"]["id"]
    keys = db.keys()
    if keys == ["_"]:
        return "_"
    if uid in ADMIN_COURSE and uid not in SUPERADMIN_IDS:
        return ADMIN_COURSE[uid]
    want = (request.headers.get("X-Course-Temp") or request.headers.get("X-Course") or await central.get_active(uid)
            or ADMIN_COURSE.get(uid))
    return want if want in keys else (keys[0] if keys else None)


def staff_route(handler):
    async def wrapped(request: web.Request) -> web.Response:
        uid = request["user"]["id"]
        if uid not in ADMIN_COURSE and uid not in SUPERADMIN_IDS:
            return bad("forbidden", 403)
        key = await _staff_course(request)
        if key is None:
            return bad("no_course", 404)
        if uid in SUPERADMIN_IDS and request.headers.get("X-Course") and not request.headers.get("X-Course-Temp"):
            await central.set_active(uid, key)  # faqat kursni ataylab almashtirish saqlanadi (bir martalik ko'rish — yo'q)
        with use_course(None if key == "_" else key), use_lang("uz"):
            request["course"] = key
            return await handler(request)
    return wrapped


def _row(x: dict) -> dict:
    st = x["student"]
    att = x["attendance"] or {}
    return {"id": st["id"], "name": st["full_name"], "group": st.get("group_name") or "", "hemis_id": st.get("hemis_id"),
            "flags": x["flags"], "problems": sum(x["flags"].values()), "counted_hours": att.get("counted"),
            "percent": round(att["percent"]) if att.get("percent") is not None else None,
            "action": absence.action_for(x["level"]) if x["flags"]["att"] else None,
            "debts": [d["subject"] for d in x["debts"]], "gpa": _gpa(x["gpa"]),
            "kontrakt": (x["pays"]["kontrakt"] or {}).get("debt") if x["flags"]["kontrakt"] else None,
            "trimestr": (x["pays"]["trimestr"] or {}).get("debt") if x["flags"]["trimestr"] else None}


@staff_route
async def api_staff_panel(request):
    students = scope_students(await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name"))
    sts = await status.all_statuses(students)
    linked = {r["student_id"] for r in await db.fetchall(
        "SELECT DISTINCT ps.student_id FROM parent_students ps JOIN parents p ON p.tg_id = ps.parent_id WHERE p.active = 1")}
    rows = [_row(x) for x in sts]
    k = [r for r in rows if r["kontrakt"]]
    t = [r for r in rows if r["trimestr"]]
    inbox = scope_students(await db.inbox(200))
    pending = len(await _pending_requests())
    return ok({"course": course_title(request["course"]) if request["course"] != "_" else "",
               "total": len(rows), "linked": sum(1 for x in sts if x["student"]["id"] in linked),
               "att": sum(1 for r in rows if r["flags"]["att"]), "acad": sum(1 for r in rows if r["flags"]["acad"]),
               "gpa": sum(1 for r in rows if r["flags"]["gpa"]), "gpa_min": GPA_MIN,
               "kontrakt": {"count": len(k), "sum": sum(r["kontrakt"] for r in k)},
               "trimestr": {"count": len(t), "sum": sum(r["trimestr"] for r in t)},
               "multi": sum(1 for r in rows if r["problems"] >= 3),
               "unread": sum(i["unread"] for i in inbox), "link_requests": pending,
               "top": sorted([r for r in rows if r["problems"]], key=lambda r: (-r["problems"], r["name"]))[:30],
               "updated": await _last_update(), "scope": scope_label(request["user"]["id"]),
               "dynamics": await course_trends.course_dynamics(viewer_scope())})


async def _student_rows(q: str = "", limit: int = 3000) -> list[dict]:
    """Joriy kurs talabalari holati bilan (jadval qatorlari)."""
    students = await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name")
    if q:
        students = [s for s in students if q in (s.get("name_norm") or "") or q == normalize_text(s.get("hemis_id") or "")
                    or name_score(q, s.get("name_norm") or "") >= 0.8]
    return [_row(x) for x in await status.all_statuses(students[:max(400, limit)])]


@staff_route
async def api_staff_students(request):
    q = normalize_text(request.query.get("q", ""))
    flt = request.query.get("filter", "")
    students = scope_students(await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name"))
    if q:
        students = [s for s in students if q in (s.get("name_norm") or "") or q == normalize_text(s.get("hemis_id") or "")
                    or name_score(q, s.get("name_norm") or "") >= 0.8]
    try:
        limit = max(1, min(int(request.query.get("limit", 200)), 3000))
    except ValueError:
        limit = 200
    sts = await status.all_statuses(students[:max(400, limit)])
    rows = [_row(x) for x in sts]
    if flt in ("att", "acad", "gpa", "kontrakt", "trimestr"):
        rows = [r for r in rows if r["flags"][flt]]
    elif flt == "prob":
        rows = sorted([r for r in rows if r["problems"]], key=lambda r: -r["problems"])
    return ok({"items": rows[:limit], "total": len(rows)})


@staff_route
async def api_staff_student(request):
    st = await db.get_student(int(request.match_info["sid"]))
    if not _visible(st):
        return bad("not_found", 404)
    data = await overview(st, request["course"])
    parents = await db.fetchall("SELECT p.tg_id, p.tg_name, p.phone, p.active FROM parent_students ps "
                                "JOIN parents p ON p.tg_id = ps.parent_id WHERE ps.student_id = ?", (st["id"],))
    data["parents"] = [{**p, "lang": await central.get_lang(p["tg_id"]) or "uz"} for p in parents]
    return ok(data)


@staff_route
async def api_staff_inbox(request):
    return ok({"items": [{"sid": i["student_id"], "pid": i["parent_id"], "student": i["full_name"], "group": i["group_name"],
                          "parent": i["tg_name"] or i["phone"] or "", "last": i["last_text"], "last_sender": i["last_sender"],
                          "at": i["last_at"], "unread": i["unread"]} for i in scope_students(await db.inbox(200))]})


@staff_route
async def api_staff_thread(request):
    sid, pid = int(request.match_info["sid"]), int(request.match_info["pid"])
    st = await db.get_student(sid)
    parent = await db.get_parent(pid)
    if not _visible(st) or not parent:
        return bad("not_found", 404)
    await db.mark_thread_read(sid, pid, "staff")
    return ok({"messages": [_msg(m) for m in await db.thread(sid, pid)], "student": st["full_name"],
               "group": st.get("group_name"), "parent": parent.get("tg_name") or "", "phone": parent.get("phone"),
               "lang": await central.get_lang(pid) or "uz"})


@staff_route
async def api_staff_reply(request):
    sid, pid = int(request.match_info["sid"]), int(request.match_info["pid"])
    if not await db.linked_student(pid, sid) or not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    body = await request.json()
    user = request["user"]
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "Kurs koordinatori"
    res = await chat.staff_reply(request.app["bot"], user["id"], name, sid, pid, body.get("text", ""),
                                 await central.get_lang(pid))
    return ok(res) if res["ok"] else bad(res["error"])


@staff_route
async def api_staff_announce(request):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return bad("empty")
    groups = [group_key(g) for g in (body.get("groups") or []) if g] or None
    scope = viewer_scope()
    if scope is not None:  # koordinator — faqat o'z guruhlari ota-onalariga
        groups = sorted(scope) if groups is None else [g for g in groups if g in scope]
        if not groups:
            return bad("groups")
    sent, total = await _announce_here(request.app["bot"], text, groups, request["user"]["id"])
    return ok({"sent": sent, "recipients": total, "course": course_title(request["course"]) if request["course"] != "_" else ""})


async def _announce_here(bot, text: str, groups, admin_id: int, skip: set | None = None) -> tuple[int, int]:
    """E'lonni joriy kurs ota-onalariga yuboradi (ilova rejimida — qisqa xabar, matn ilovada).
    skip — boshqa kursdan allaqachon olgan ota-onalar (bir ota-onaga bir e'lon bir marta boradi)."""
    recipients = [p for p in await db.parent_ids_for_groups(groups) if not skip or p not in skip]
    sent = 0
    from html import escape
    from notifier import safe_send
    from keyboards import webapp_kb
    import appmode
    import live
    for pid in recipients:
        lang = await central.get_lang(pid) or "uz"
        with use_lang(lang):
            full = f"📢 {escape(loc.pick(text, lang), quote=False)}"  # apostrof («yig'ilish») kodga aylanmasin
            body = appmode.short_text("news") if appmode.APP_MODE else full
            ok_ = await safe_send(bot, pid, body, reply_markup=webapp_kb("/news"))
        sent += ok_
        if ok_:
            await db.add_notification(pid, full, None, "news")
            live.publish(pid, {"type": "news", "kind": "news", "text": loc.pick(text, lang)[:200], "route": "/news"})
    await db.add_announcement(text, groups or [], admin_id, sent)
    log.info("E'lon yuborildi: kurs %s, guruhlar %s — %s/%s ota-onaga (yuboruvchi %s)", current_course() or "_",
             ",".join(groups) if groups else "hammasi", sent, len(recipients), admin_id)
    if skip is not None:
        skip.update(recipients)
    return sent, len(recipients)


async def api_super_announce(request):
    """Super-admin: e'lon barcha kurslarning ota-onalariga (har bir ota-onaga bir marta)."""
    if request["user"]["id"] not in SUPERADMIN_IDS:
        return bad("forbidden", 403)
    text = ((await request.json()).get("text") or "").strip()
    if not text:
        return bad("empty")
    sent = total = 0
    seen: set[int] = set()
    per_course = []
    with use_lang("uz"):
        for key in db.keys():
            with use_course(None if key == "_" else key):
                s_, t_ = await _announce_here(request.app["bot"], text, None, request["user"]["id"], seen)
            sent, total = sent + s_, total + t_
            per_course.append({"course": course_title(key) if key != "_" else "Kurs", "sent": s_, "recipients": t_})
    log.info("Super-admin e'loni barcha kurslarga: %s/%s", sent, total)
    return ok({"sent": sent, "recipients": total, "courses": per_course})


@staff_route
async def api_staff_export(request):
    fmt = request.query.get("fmt", "x")
    only = request.query.get("s") or None
    only = None if only in (None, "all") else only
    data = await export.collect(request.query.get("f", ""))
    content = await asyncio.to_thread(export.build_xlsx if fmt == "x" else export.build_pdf, data, only)
    name = export.file_name(data, "xlsx" if fmt == "x" else "pdf", only)
    ctype = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "x" else "application/pdf")
    return web.Response(body=content, content_type=ctype, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@staff_route
async def api_staff_export_send(request):
    """Hisobotni kurs koordinatorining Telegram chatiga fayl qilib yuboradi (Telegram ichida ishonchli usul)."""
    from aiogram.types import BufferedInputFile
    fmt = request.query.get("fmt", "x")
    only = request.query.get("s") or None
    only = None if only in (None, "all") else only
    data = await export.collect(request.query.get("f", ""))
    content = await asyncio.to_thread(export.build_xlsx if fmt == "x" else export.build_pdf, data, only)
    name = export.file_name(data, "xlsx" if fmt == "x" else "pdf", only)
    await request.app["bot"].send_document(request["user"]["id"], BufferedInputFile(content, name),
                                           caption=f"📥 Kurs holati — {export.title_line(data)}")
    return ok({"sent": True, "file": name})


class _Collector:
    """Import natijasini bot xabari o'rniga yig'adi (bot funksiyasi o'zgarishsiz qayta ishlatiladi)."""

    def __init__(self):
        self.parts: list[str] = []

    async def edit_text(self, text, **kwargs):
        self.parts = [text]
        return self

    async def answer(self, text, **kwargs):
        self.parts.append(text)
        return self


@staff_route
async def api_staff_import(request):
    from handlers.admin import _process_import
    from importer import COMPATIBLE, KIND_TITLES, detect_kinds, load_rows
    reader = await request.multipart()
    fields, file_bytes, file_name = {}, None, "fayl.xlsx"
    async for part in reader:
        if part.name == "file":
            file_name = part.filename or file_name
            file_bytes = await part.read(decode=False)
        else:
            fields[part.name] = (await part.read(decode=True)).decode()
    if not file_bytes:
        return bad("no_file")
    if not file_name.lower().endswith((".xlsx", ".xlsm")):
        return bad("not_xlsx")
    tmp = Path(tempfile.mkdtemp()) / "import.xlsx"
    tmp.write_bytes(file_bytes)
    try:
        rows = await asyncio.to_thread(load_rows, str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    kind, force = fields.get("kind", "auto"), fields.get("force") == "1"
    detected = await asyncio.to_thread(detect_kinds, rows, file_name)
    if kind == "auto":
        if not detected:
            return ok({"state": "choose", "kinds": KIND_TITLES})
        kind = detected[0]
    elif detected and not force and not (set(detected) & COMPATIBLE.get(kind, {kind})):
        return ok({"state": "confirm", "detected": detected[0], "detected_title": KIND_TITLES[detected[0]],
                   "kind_title": KIND_TITLES[kind]})
    col = _Collector()
    done = await _process_import(request.app["bot"], col, kind, rows, fields.get("caption", ""), file_name,
                                user_id=request["user"]["id"])
    return ok({"state": "done" if done else "failed", "kind": kind, "kind_title": KIND_TITLES.get(kind, kind),
               "report": "\n".join(col.parts)})


async def api_super_courses(request):
    if request["user"]["id"] not in SUPERADMIN_IDS:
        return bad("forbidden", 403)
    from handlers.superadmin import courses_info
    return ok({"courses": await courses_info(), "active": await central.get_active(request["user"]["id"])})


# ================================================================ hujjatni ilovada ko'rish (ota-ona)
@child_route
async def api_document_pages(request):
    import docstore
    doc = await db.get_document(int(request.match_info["did"]))
    if not doc or doc["student_id"] != request["student"]["id"] or doc.get("revoked"):
        return bad("not_found", 404)
    data = await docstore.load(request.app["bot"], request.match_info["course"], doc["file_id"])
    return ok({"pages": await asyncio.to_thread(docstore.page_count, data), "title": doc_title(doc["doc_type"]),
               "file_name": doc.get("file_name") or "hujjat.pdf"})


@child_route
async def api_document_page(request):
    import docstore
    doc = await db.get_document(int(request.match_info["did"]))
    if not doc or doc["student_id"] != request["student"]["id"] or doc.get("revoked"):
        return bad("not_found", 404)
    data = await docstore.load(request.app["bot"], request.match_info["course"], doc["file_id"])
    n = int(request.match_info["n"])
    if n < 0 or n >= await asyncio.to_thread(docstore.page_count, data):
        return bad("not_found", 404)
    png = await docstore.page_png(f"doc:{doc['id']}", data, n, int(request.query.get("w", 1240) or 1240))
    return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


# ================================================================ hujjat yuborish (kurs koordinatori, super-admin)
_DOC_JOBS: "dict[str, dict]" = {}
DOC_JOB_TTL = 30 * 60


def _doc_job(request, token: str) -> dict | None:
    job = _DOC_JOBS.get(token)
    if not job or job["uid"] != request["user"]["id"] or job["course"] != request["course"] or \
            time.time() - job["at"] > DOC_JOB_TTL:
        return None
    return job


async def _job_copy(job: dict, sid: int) -> tuple[bytes, dict]:
    """Talaba uchun nusxa: boshqa talabalar yopilgan (hujjat o'qilgan bo'lsa) yoki asl fayl."""
    import redact
    if sid in job["copies"]:
        return job["copies"][sid]
    st = await db.get_student(sid)
    if job["an"].readable and st:
        r = await asyncio.to_thread(redact.redact_for, job["raw"], job["an"], sid, st["hemis_id"])
        res = (r.pdf, {"checked": True, "boxes": r.boxes, "found": r.target_found, "ambiguous": r.ambiguous})
    else:
        res = (job["raw"], {"checked": False, "boxes": 0, "found": True, "ambiguous": False})
    job["copies"][sid] = res
    return res


@staff_route
async def api_staff_doc_analyze(request):
    import redact
    from utils import detect_doc_type
    for t in [t for t, j in _DOC_JOBS.items() if time.time() - j["at"] > DOC_JOB_TTL]:
        _DOC_JOBS.pop(t, None)
    reader = await request.multipart()
    raw, fname = b"", "hujjat.pdf"
    async for part in reader:
        if part.name == "file":
            fname = part.filename or fname
            raw = bytes(await part.read(decode=False))  # pypdfium2 bytearray qabul qilmaydi
    if not raw.startswith(b"%PDF"):
        return bad("not_pdf", 400)
    if len(raw) > 20 * 1024 * 1024:
        return bad("too_big", 400)
    an = await asyncio.to_thread(redact.analyze, raw, await db.all_students_brief())
    token = secrets.token_urlsafe(12)
    _DOC_JOBS[token] = {"uid": request["user"]["id"], "course": request["course"], "raw": raw, "an": an,
                        "name": fname, "at": time.time(), "copies": {}}
    found = []
    for sid in an.mentioned[:60]:
        st = await db.get_student(sid)
        if _visible(st) and len(found) < 30:
            found.append({"id": st["id"], "name": st["full_name"], "group": st.get("group_name") or "",
                          "hemis_id": st.get("hemis_id"), "select": True, "note": ""})
    # Ismdoshlar: hujjatda qaysi birining HEMIS ID si yoki guruhi borligi tekshiriladi. Dalili yo'q ismdosh ro'yxatda
    # qoladi, lekin avtomatik belgilanmaydi — hujjat aloqasi yo'q talabaning ota-onasiga ketib qolmasin.
    text = f" {normalize_text(' '.join(w.text for pg in an.pages for w in pg.words))} "
    toks = set(text.split())
    for x in found:
        hid, grp = normalize_text(x["hemis_id"] or ""), normalize_text(x["group"])
        x["_ev"] = bool(hid and hid in toks) or bool(grp and f" {grp} " in text)
    by_name: dict[str, list] = {}
    for x in found:
        by_name.setdefault(normalize_text(x["name"]), []).append(x)
    for xs in by_name.values():
        if len(xs) > 1 and any(x["_ev"] for x in xs):
            for x in xs:
                if not x["_ev"]:
                    x["select"], x["note"] = False, "Ismdosh — hujjatda uning ID si yoki guruhi yo‘q"
        elif len(xs) > 1:
            for x in xs:
                x["note"] = "Ismdosh bor — qaysi biri ekanini tekshiring"
    for x in found:
        x.pop("_ev", None)
    return ok({"token": token, "file_name": fname, "readable": an.readable, "mode": an.mode, "pages": len(an.pages),
               "error": an.error, "found": found, "dtype": detect_doc_type(fname) or _doc_type_from_text(an) or "boshqa"})


def _doc_type_from_text(an) -> str | None:
    """Hujjat turi matndan (fayl nomidan aniqlanmasa): dastlabki ikki sahifada qaysi tur ko'proq tilga olingan;
    teng bo'lsa — og'irrog'i (hayfsan > ogohlantirish > tushuntirish). Kurs koordinatori baribir tasdiqlaydi."""
    from utils import _DOC_KEYWORDS
    words = normalize_text(" ".join(w.text for pg in an.pages[:2] for w in pg.words)).split()
    counts = {kind: sum(1 for w in words for k in keys if w.startswith(k)) for kind, keys in _DOC_KEYWORDS.items()}
    order = ["hayfsan", "ogohlantirish", "tushuntirish"]
    best = max(order, key=lambda k: (counts.get(k, 0), -order.index(k)))
    return best if counts.get(best) else None


@staff_route
async def api_staff_doc_copy(request):
    """Talaba uchun nusxa haqida: sahifalar soni, yopilgan joylar, talabaning o'zi topildimi."""
    import docstore
    job = _doc_job(request, request.match_info["token"])
    if not job:
        return bad("expired", 410)
    if not _visible(await db.get_student(int(request.match_info["sid"]))):
        return bad("not_found", 404)
    data, info = await _job_copy(job, int(request.match_info["sid"]))
    return ok({**info, "pages": await asyncio.to_thread(docstore.page_count, data)})


@staff_route
async def api_staff_doc_page(request):
    import docstore
    token, sid = request.match_info["token"], int(request.match_info["sid"])
    job = _doc_job(request, token)
    if not job:
        return bad("expired", 410)
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    data, _ = await _job_copy(job, sid)
    png = await docstore.page_png(f"job:{token}:{sid}", data, int(request.match_info["n"]),
                                  int(request.query.get("w", 1100) or 1100))
    return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "no-store"})


@staff_route
async def api_staff_doc_send(request):
    import uuid
    import docstore
    from staffops import deliver_document
    from utils import DOC_TYPES, parse_user_dates, today
    body = await request.json()
    job = _doc_job(request, str(body.get("token", "")))
    if not job:
        return bad("expired", 410)
    dtype = body.get("dtype") if body.get("dtype") in DOC_TYPES else "boshqa"
    comment = str(body.get("comment") or "").strip()[:500] or None
    sids = [int(x) for x in (body.get("sids") or [])][:30]
    if not sids:
        return bad("no_students", 400)
    dates = parse_user_dates(comment or "")
    doc_date = (dates[0] if dates else today()).isoformat()
    names = {"tushuntirish": "Tushuntirish_xati", "ogohlantirish": "Dekan_ogohlantirishi", "hayfsan": "Hayfsan"}
    fname = f"{names.get(dtype, 'Rasmiy_hujjat')}.pdf"
    batch, out = uuid.uuid4().hex[:12], []
    for sid in sids:
        st = await db.get_student(sid)
        if not _visible(st):
            continue
        data, info = await _job_copy(job, sid)
        file_id = docstore.save_local(request["course"], data)
        did = await db.add_document(sid, dtype, file_id, None, fname, len(data), doc_date, comment, request["user"]["id"],
                                    batch=batch, redacted=info["boxes"], source_file_id=None)
        sent, total = await deliver_document(request.app["bot"], did, st)
        out.append({"id": did, "student": st["full_name"], "group": st.get("group_name") or "", "sent": sent,
                    "parents": total, "boxes": info["boxes"]})
    _DOC_JOBS.pop(str(body.get("token")), None)
    log.info("Hujjat ilovadan yuborildi: %s, %s ta talaba (%s)", dtype, len(out), request["user"]["id"])
    return ok({"items": out, "title": doc_title(dtype)})


# ================================================================ super-admin: barcha kurslar talabalari
async def api_super_students(request):
    if request["user"]["id"] not in SUPERADMIN_IDS:
        return bad("forbidden", 403)
    rows = []
    with use_lang("uz"):
        for key in db.keys():
            with use_course(None if key == "_" else key):
                title = course_title(key) if key != "_" else "Kurs"
                for r in await _student_rows():
                    rows.append({**r, "course": key, "course_title": title})
    return ok({"items": rows, "total": len(rows)})


# ================================================================ super-admin: juftlik vaqtlari
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def api_super_pair_times(request):
    if request["user"]["id"] not in SUPERADMIN_IDS:
        return bad("forbidden", 403)
    if request.method == "POST":
        body = await request.json()
        times = {}
        for k, v in (body.get("times") or {}).items():
            if not v or not (v[0] or v[1]):
                continue
            a, b = str(v[0]).strip(), str(v[1]).strip()
            if not (_TIME.match(a) and _TIME.match(b)) or a >= b or not str(k).isdigit() or not 1 <= int(k) <= 10:
                return bad(f"time:{k}", 400)
            times[int(k)] = (a, b)
        await central.set_meta("pair_times", json.dumps({str(k): list(v) for k, v in sorted(times.items())}))
        PAIR_TIMES.clear()
        PAIR_TIMES.update(times)
        log.info("Juftlik vaqtlari yangilandi: %s", times)
    return ok({"times": {str(k): list(v) for k, v in sorted(PAIR_TIMES.items())}})


# ================================================================ kompyuter versiyasi
async def api_desk_link(request):
    """Telegram ichidan: kompyuter versiyasi uchun bir martalik kirish havolasi."""
    uid = request["user"]["id"]
    if uid not in ADMIN_COURSE and uid not in SUPERADMIN_IDS:
        return bad("forbidden", 403)
    if not WEBAPP_URL:
        return bad("no_url", 400)
    return ok({"url": deskauth.login_url(uid), "ttl": deskauth.TOKEN_TTL})


async def api_desk_logout(request):
    resp = ok({"ok": True})
    resp.del_cookie(deskauth.COOKIE, path="/")
    return resp


async def _pending_requests() -> list[dict]:
    """Kutilayotgan bog'lash so'rovlari; koordinator — faqat o'z guruhlari talabalari bo'yicha."""
    scope = viewer_scope()
    rows = await db.fetchall("SELECT r.*, s.group_name FROM link_requests r LEFT JOIN students s ON s.id = r.student_id "
                             "WHERE r.status = 'pending' ORDER BY r.created_at")
    return rows if scope is None else [r for r in rows if in_scope(r["group_name"], scope)]


def _visible(st: dict | None) -> bool:
    """Talaba bor va joriy kurs koordinatorining guruhlarida (guruhsiz koordinator va super-admin — butun kurs)."""
    return bool(st) and in_scope(st.get("group_name"), viewer_scope())


@staff_route
async def api_staff_requests(request):
    import linking
    out = []
    for r in await _pending_requests():
        st = await db.get_student(r["student_id"])
        p = await db.fetchone("SELECT tg_name, phone FROM parents WHERE tg_id = ?", (r["parent_id"],)) or {}
        out.append({"id": r["id"], "parent_id": r["parent_id"], "parent_name": p.get("tg_name") or "",
                    "phone": p.get("phone") or "", "lang": await central.get_lang(r["parent_id"]) or "uz",
                    "note": r["note"] or "", "at": r["created_at"], "blocked": await db.is_blocked(r["parent_id"]),
                    "student_ok": {"at": r["student_ok_at"], "tg_name": r["student_tg_name"] or "",
                                   "phone": r["student_phone"] or "",
                                   "source": (await linking.expected_phones(r))[1]} if r["student_ok_at"] else None,
                    "claimed_phone": r["claimed_phone"] or "",
                    "student_can_confirm": await linking.student_can_confirm(r["student_id"]) or bool(r["claimed_phone"]),
                    "student": {"id": st["id"], "name": st["full_name"], "group": st.get("group_name") or "",
                                "hemis_id": st.get("hemis_id")} if st else None})
    out.sort(key=lambda x: not x["student_ok"])  # talaba tasdiqlaganlari — yuqorida
    return ok({"items": out})


@staff_route
async def api_staff_request_decide(request):
    from staffops import decide_link
    body = await request.json()
    done, verdict = await decide_link(request.app["bot"], int(request.match_info["rid"]), bool(body.get("approve")),
                                      request["user"]["id"])
    return ok({"done": done, "message": verdict}) if done else bad(verdict, 409)


# ================================================================ super-admin
def super_route(handler):
    async def wrapped(request: web.Request) -> web.Response:
        if request["user"]["id"] not in SUPERADMIN_IDS:
            return bad("forbidden", 403)
        with use_lang("uz"):
            return await handler(request)
    return wrapped


@super_route
async def api_super_overview(request):
    import export
    from handlers.superadmin import courses_info
    from logsetup import errors_since
    info = {c["key"]: c for c in await courses_info()}
    rows = []
    for key in db.keys():
        with use_course(None if key == "_" else key):
            d = await export.collect("")
        c = info.get(key, {})
        rows.append({"key": key, "title": course_title(key) if key != "_" else "Kurs", "admins": c.get("admins", []),
                     "total": d["total"], "linked": d["linked"], "prob": len(d["prob"]),
                     "multi": sum(1 for r in d["prob"] if r["count"] >= 3), "att": len(d["att"]), "acad": len(d["acad"]),
                     "kontrakt": {"count": len(d["kontrakt"]), "sum": sum(r["debt"] for r in d["kontrakt"])},
                     "trimestr": {"count": len(d["trimestr"]), "sum": sum(r["debt"] for r in d["trimestr"])},
                     "parents": c.get("parents", 0)})
    last = await central.get_meta("last_backup")
    return ok({"courses": rows, "coordinators": sum(len(r["admins"]) for r in rows), "last_backup": last,
               "errors_24h": errors_since(24)})


@super_route
async def api_super_course_create(request):
    title = str((await request.json()).get("title", "")).strip()[:60]
    if len(title) < 2:
        return bad("title", 400)
    key = await central.add_course(title, request["user"]["id"])
    await db.open_course(DATA_DIR, key)
    await reload_registry()
    log.info("Yangi kurs yaratildi (kompyuter versiyasi): %s (%s)", title, key)
    return ok({"key": key, "title": title})


@super_route
async def api_super_course_rename(request):
    key, title = request.match_info["key"], str((await request.json()).get("title", "")).strip()[:60]
    if key not in course_keys() or len(title) < 2:
        return bad("bad_request", 400)
    await central.rename_course_title(key, title)
    await reload_registry()
    return ok({"key": key, "title": title})


@super_route
async def api_super_coordinator_add(request):
    from staffops import assign_coordinator
    key, body = request.match_info["key"], await request.json()
    try:
        uid = int(str(body.get("user_id", "")).strip())
    except ValueError:
        return bad("user_id", 400)
    if key not in course_keys() or uid <= 0:
        return bad("bad_request", 400)
    name = str(body.get("name", "")).strip()[:80] or None
    r = await assign_coordinator(request.app["bot"], uid, key, name, request["user"]["id"])
    return ok({"old": course_title(r["old"]) if r["old"] else None, "notified": r["notified"] and r["menu_ok"]})


@super_route
async def api_super_coordinator_remove(request):
    from staffops import unassign_coordinator
    uid = int(request.match_info["uid"])
    key = next((c["course_key"] for c in (await central.registry())[1] if c["user_id"] == uid), None)
    if key is None:
        return bad("not_found", 404)
    await unassign_coordinator(request.app["bot"], uid, key)
    return ok({"ok": True})


@super_route
async def api_super_course_groups(request):
    from staffops import course_groups
    key = request.match_info["key"]
    if key not in course_keys():
        return bad("not_found", 404)
    return ok(await course_groups(key))


@super_route
async def api_super_coordinator_groups(request):
    """Koordinatorga guruhlar biriktirish: {"groups": ["XM-21", ...]} — ro'yxat to'liq almashtiriladi."""
    from staffops import save_coord_groups
    uid, body = int(request.match_info["uid"]), await request.json()
    key = next((c["course_key"] for c in (await central.registry())[1] if c["user_id"] == uid), None)
    if key is None:
        return bad("not_found", 404)
    names = body.get("groups")
    if not isinstance(names, list):
        return bad("groups", 400)
    r = await save_coord_groups(uid, key, [str(x).strip()[:40] for x in names if str(x).strip()][:300],
                                request["user"]["id"])
    return ok({"saved": r["saved"], "taken": [{"name": n, "owner": o} for n, o in r["taken"]]})


@super_route
async def api_super_errors(request):
    from logsetup import errors_since, tail
    return ok({"count_24h": errors_since(24), "tail": tail(LOG_DIR / "errors.log", 60)[-12000:]})


@super_route
async def api_super_backup(request):
    import backup
    info = await backup.make_backup()
    sent = await backup.send(request.app["bot"], info, to={request["user"]["id"]})
    return ok({"report": backup.report(info), "sent": bool(sent)})


# ================================================================ marshrutlar

# ================================================================ so'rovnomalar va ichki nizomlar (ota-ona)
async def _parent_surveys(uid: int) -> list[dict]:
    import surveys
    out = []
    for key in await parent_courses(uid):
        with use_course(None if key == "_" else key):
            out += [{**x, "course": key} for x in await surveys.for_parent(uid)]
    return sorted(out, key=lambda x: (x["answered"], not x["open"], x["created_at"]), reverse=False)


async def api_surveys(request):
    items = await _parent_surveys(request["user"]["id"])
    return ok({"pending": [x for x in items if x["open"] and not x["answered"]],
               "done": [x for x in items if x["answered"] or not x["open"]]})


async def api_survey(request):
    import surveys
    uid, key = request["user"]["id"], _course_arg(request.match_info["course"])
    if key is None or key not in await parent_courses(uid):
        return bad("not_found", 404)
    with use_course(None if key == "_" else key):
        sid = int(request.match_info["sid"])
        s = await surveys.get(sid)
        if not s or not await surveys._child_for(uid, s):
            return bad("not_found", 404)
        if request.method == "POST":
            body = await request.json()
            err = await surveys.submit(sid, uid, body.get("answers") or {})
            if err:
                return bad(err, 409 if err == "closed" else 400)
            log.info("So'rovnoma #%s: javob (ota-ona %s, kurs %s)", sid, uid, key)
            return ok({"ok": True})
        mine = await surveys.my_answers(sid, uid)
        return ok({"id": s["id"], "course": key, "title": s["title"], "description": s["description"],
                   "open": surveys.is_open(s), "closes_at": s["closes_at"], "anonymous": bool(s["anonymous"]),
                   "answered": bool(mine),
                   "questions": [{"id": q["id"], "kind": q["kind"], "text": q["text"], "options": q["options"],
                                  "required": bool(q["required"]),
                                  "answer": (json.loads(mine[q["id"]]) if q["kind"] == "multi" and q["id"] in mine
                                             else mine.get(q["id"]))} for q in s["questions"]]})


async def api_pulse(request):
    """Yengil holat: o'qilmaganlar, javob kutayotgan so'rovnomalar va ilova versiyasi — ilova ochiq turganda
    vaqti-vaqti bilan so'raydi (jonli ulanish uzilsa ham bildirishnoma kechikmaydi, yangilash shart emas)."""
    import webserver
    uid = request["user"]["id"]
    notes = msgs = 0
    for k in await parent_courses(uid):
        d = db.for_course(k)
        notes += await d.unread_notifications(uid)
        msgs += sum((await d.unread_for_parent(uid)).values())
    pending = sum(1 for x in await _parent_surveys(uid) if x["open"] and not x["answered"])
    return ok({"notifications": notes, "messages": msgs, "surveys": pending, "v": webserver.APP_VERSION})


async def api_regulations(request):
    import regulations
    return ok({"items": [{"id": r["id"], "title": loc.pick(r["title"], request["lang"]),
                          "description": loc.pick(r["description"], request["lang"]) if r["description"] else None,
                          "kind": "pdf" if r["file"] else "url", "url": r["url"], "created_at": r["created_at"]}
                         for r in await regulations.all_items()]})


async def api_regulation_pages(request):
    import docstore
    import regulations
    r = await regulations.get(int(request.match_info["rid"]))
    data = regulations.read_pdf(r)
    if not data:
        return bad("not_found", 404)
    return ok({"pages": await asyncio.to_thread(docstore.page_count, data), "title": loc.pick(r["title"], request["lang"])})


async def api_regulation_page(request):
    import docstore
    import regulations
    r = await regulations.get(int(request.match_info["rid"]))
    data = regulations.read_pdf(r)
    if not data:
        return bad("not_found", 404)
    n = int(request.match_info["n"])
    if n < 0 or n >= await asyncio.to_thread(docstore.page_count, data):
        return bad("not_found", 404)
    png = await docstore.page_png(f"reg:{r['id']}", data, n, int(request.query.get("w", 1240) or 1240))
    return web.Response(body=png, content_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


async def api_regulation_file(request):
    import regulations
    r = await regulations.get(int(request.match_info["rid"]))
    data = regulations.read_pdf(r)
    if not data:
        return bad("not_found", 404)
    return web.Response(body=data, content_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="nizom-{r["id"]}.pdf"'})


# ================================================================ so'rovnomalar (kurs koordinatori)
@staff_route
async def api_staff_surveys(request):
    import surveys
    from staffops import notify_survey
    uid, scope = request["user"]["id"], viewer_scope()
    if request.method == "GET":
        return ok({"items": await surveys.listing(uid, scope)})
    body = await request.json()
    title = str(body.get("title") or "").strip()
    if len(title) < 3:
        return bad("title")
    try:
        questions = surveys.clean_questions(body.get("questions"))
    except ValueError as e:
        return bad(str(e))
    groups = surveys.target_keys(body.get("groups"), scope)
    if groups is None:
        return bad("groups")
    closes = str(body.get("closes_at") or "").strip() or None
    if closes and not re.match(r"^\d{4}-\d{2}-\d{2}$", closes):
        return bad("closes_at")
    sent = total = 0
    courses = ([k for k in db.keys()] if body.get("all_courses") and uid in SUPERADMIN_IDS else [request["course"]])
    for key in courses:
        with use_course(None if key == "_" else key):
            sid = await surveys.create(title, body.get("description") or "", questions,
                                       groups if key == request["course"] else [], uid, closes, bool(body.get("anonymous")))
            s_, t_ = await notify_survey(request.app["bot"], key, await surveys.get(sid))
            sent, total = sent + s_, total + t_
    return ok({"id": sid, "sent": sent, "recipients": total})


async def _staff_survey(request) -> dict | None:
    import surveys
    s = await surveys.get(int(request.match_info["sid"]))
    return s if s and surveys.visible_to(s, request["user"]["id"], viewer_scope()) else None


@staff_route
async def api_staff_survey(request):
    import surveys
    s = await _staff_survey(request)
    if not s:
        return bad("not_found", 404)
    if request.method == "DELETE":
        await surveys.delete(s["id"])
        return ok({"ok": True})
    return ok(await surveys.results(s["id"], viewer_scope()))


@staff_route
async def api_staff_survey_close(request):
    import surveys
    s = await _staff_survey(request)
    if not s:
        return bad("not_found", 404)
    await surveys.close(s["id"])
    return ok({"ok": True})


@staff_route
async def api_staff_survey_export(request):
    import surveys
    s = await _staff_survey(request)
    if not s:
        return bad("not_found", 404)
    res = await surveys.results(s["id"], viewer_scope())
    content = await asyncio.to_thread(surveys.build_xlsx, res, await surveys.raw_rows(s["id"], viewer_scope()))
    return web.Response(body=content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="sorovnoma-{s["id"]}.xlsx"'})


# ================================================================ ichki nizomlar (super-admin)
@super_route
async def api_super_regulations(request):
    import regulations
    from staffops import notify_regulation
    pdf, fields = None, {}
    if request.content_type.startswith("multipart/"):
        async for part in await request.multipart():
            if part.name == "file":
                pdf = bytes(await part.read(decode=False))
            else:
                fields[part.name] = (await part.read(decode=True)).decode()
    else:
        fields = await request.json()
    title, url = str(fields.get("title") or "").strip(), str(fields.get("url") or "").strip()
    if len(title) < 3:
        return bad("title")
    if pdf is not None and not pdf.startswith(b"%PDF"):
        return bad("not_pdf")
    if pdf is not None and len(pdf) > 20 * 1024 * 1024:
        return bad("too_big")
    if pdf is None and not re.match(r"^https?://", url):
        return bad("url")
    rid = await regulations.add(title, fields.get("description"), request["user"]["id"], pdf, None if pdf else url)
    sent = total = 0
    if str(fields.get("notify")) in ("1", "true", "on", "True"):
        sent, total = await notify_regulation(request.app["bot"], title)
    log.info("Ichki nizom qo'shildi: #%s «%s» (xabar: %s/%s)", rid, title, sent, total)
    return ok({"id": rid, "sent": sent, "recipients": total})


@super_route
async def api_super_regulation_delete(request):
    import regulations
    await regulations.delete(int(request.match_info["rid"]))
    return ok({"ok": True})



# ================================================================ yuklangan fayllar (kurs koordinatori, super-admin)
@staff_route
async def api_staff_imports(request):
    import imports
    from importer import KIND_TITLES
    uid = request["user"]["id"]
    items = await imports.listing(uid, uid in SUPERADMIN_IDS)
    names = {c["user_id"]: c.get("name") for c in (await central.registry())[1]}
    return ok({"items": [{"id": r["id"], "kind": r["kind"], "kind_title": KIND_TITLES.get(r["kind"], r["kind"]),
                          "file_name": r["file_name"], "at": r["uploaded_at"], "rows": r["rows"],
                          "by": names.get(r["uploaded_by"]) or ("Super-admin" if r["uploaded_by"] in SUPERADMIN_IDS else ""),
                          "parents": r["parents_notified"], "deletable": imports.can_delete(r, uid, uid in SUPERADMIN_IDS)}
                         for r in items]})


@staff_route
async def api_staff_import_delete(request):
    import imports
    uid = request["user"]["id"]
    r = await imports.get(int(request.match_info["iid"]))
    if not r:
        return bad("not_found", 404)
    if not imports.can_delete(r, uid, uid in SUPERADMIN_IDS):
        return bad("forbidden", 403)
    return ok(await imports.delete(request.app["bot"], r["id"], uid))

def setup_routes(app: web.Application) -> None:
    r = app.router
    r.add_get("/api/me", api_me)
    base = "/api/c/{course}/{sid:\\d+}"
    r.add_get(base + "/overview", api_overview)
    r.add_get(base + "/attendance", api_attendance)
    r.add_get(base + "/schedule", api_schedule)
    r.add_get(base + "/grades", api_grades)
    r.add_get(base + "/finance", api_finance)
    r.add_get(base + "/trends", api_trends)
    r.add_get(base + "/documents", api_documents)
    r.add_post(base + "/documents/{did:\\d+}/send", api_document_send)
    r.add_get(base + "/documents/{did:\\d+}/file", api_document_file)
    r.add_get(base + "/messages", api_thread)
    r.add_post(base + "/messages", api_thread_send)
    r.add_get("/api/notifications", api_notifications)
    r.add_post("/api/notifications/read", api_notifications_read)
    r.add_get("/api/announcements", api_announcements)
    r.add_get("/api/settings", api_settings)
    r.add_post("/api/settings", api_settings_save)
    r.add_get("/api/info", api_info)
    r.add_post("/api/link", api_link)
    r.add_get("/api/link", api_link_status)
    r.add_post("/api/link/phone", api_link_phone)
    r.add_post("/api/app/login", api_app_login_start)
    r.add_get("/api/app/login/{code}", api_app_login_poll)
    r.add_post("/api/app/logout", api_app_logout)
    r.add_get("/api/app/info", api_app_info)
    r.add_get("/api/staff/panel", api_staff_panel)
    r.add_get("/api/staff/students", api_staff_students)
    r.add_get("/api/staff/student/{sid:\\d+}", api_staff_student)
    r.add_get("/api/staff/inbox", api_staff_inbox)
    r.add_get("/api/staff/thread/{sid:\\d+}/{pid:\\d+}", api_staff_thread)
    r.add_post("/api/staff/thread/{sid:\\d+}/{pid:\\d+}", api_staff_reply)
    r.add_post("/api/staff/announce", api_staff_announce)
    r.add_get("/api/staff/export", api_staff_export)
    r.add_post("/api/staff/import", api_staff_import)
    r.add_post("/api/staff/export/send", api_staff_export_send)
    r.add_get("/api/super/courses", api_super_courses)
    r.add_get("/api/events", live.stream)
    r.add_get("/api/c/{course}/{sid:\\d+}/documents/{did:\\d+}/pages", api_document_pages)
    r.add_get("/api/c/{course}/{sid:\\d+}/documents/{did:\\d+}/page/{n:\\d+}", api_document_page)
    r.add_post("/api/staff/docs", api_staff_doc_analyze)
    r.add_get("/api/staff/docs/{token}/{sid:\\d+}", api_staff_doc_copy)
    r.add_get("/api/staff/docs/{token}/{sid:\\d+}/page/{n:\\d+}", api_staff_doc_page)
    r.add_post("/api/staff/docs/send", api_staff_doc_send)
    r.add_get("/api/super/students", api_super_students)
    r.add_post("/api/super/announce", api_super_announce)
    r.add_get("/api/super/pair_times", api_super_pair_times)
    r.add_post("/api/super/pair_times", api_super_pair_times)
    r.add_post("/api/desk/link", api_desk_link)
    r.add_post("/api/desk/logout", api_desk_logout)
    r.add_get("/api/staff/requests", api_staff_requests)
    r.add_post("/api/staff/requests/{rid:\\d+}", api_staff_request_decide)
    r.add_get("/api/super/overview", api_super_overview)
    r.add_post("/api/super/courses", api_super_course_create)
    r.add_post("/api/super/courses/{key}", api_super_course_rename)
    r.add_post("/api/super/courses/{key}/coordinators", api_super_coordinator_add)
    r.add_delete("/api/super/coordinators/{uid:\\d+}", api_super_coordinator_remove)
    r.add_get("/api/super/courses/{key}/groups", api_super_course_groups)
    r.add_post("/api/super/coordinators/{uid:\\d+}/groups", api_super_coordinator_groups)
    r.add_get("/api/super/errors", api_super_errors)
    r.add_get("/api/surveys", api_surveys)
    r.add_get("/api/surveys/{course}/{sid:\\d+}", api_survey)
    r.add_post("/api/surveys/{course}/{sid:\\d+}", api_survey)
    r.add_get("/api/pulse", api_pulse)
    r.add_get("/api/staff/imports", api_staff_imports)
    r.add_delete("/api/staff/imports/{iid:\\d+}", api_staff_import_delete)
    r.add_get("/api/regulations", api_regulations)
    r.add_get("/api/regulations/{rid:\\d+}/pages", api_regulation_pages)
    r.add_get("/api/regulations/{rid:\\d+}/page/{n:\\d+}", api_regulation_page)
    r.add_get("/api/regulations/{rid:\\d+}/file", api_regulation_file)
    r.add_get("/api/staff/surveys", api_staff_surveys)
    r.add_post("/api/staff/surveys", api_staff_surveys)
    r.add_get("/api/staff/surveys/{sid:\\d+}", api_staff_survey)
    r.add_delete("/api/staff/surveys/{sid:\\d+}", api_staff_survey)
    r.add_post("/api/staff/surveys/{sid:\\d+}/close", api_staff_survey_close)
    r.add_get("/api/staff/surveys/{sid:\\d+}/export", api_staff_survey_export)
    r.add_post("/api/super/regulations", api_super_regulations)
    r.add_delete("/api/super/regulations/{rid:\\d+}", api_super_regulation_delete)
    r.add_post("/api/super/backup", api_super_backup)

