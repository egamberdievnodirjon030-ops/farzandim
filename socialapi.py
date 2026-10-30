"""Boshqaruv paneli: talabalarning ijtimoiy toifalari (socialcat.py) — kurs holati kartalari, toifa bo'yicha ro'yxat,
qo'lda belgilash (bir nechta talabaga birdan) va olib tashlash, talaba kartasi. Kurs koordinatori — o'z guruhlari."""
from __future__ import annotations

import json

from aiohttp import web

import socialcat as SC
from database import db
from tenancy import viewer_scope
from webapi import _visible, bad, ok, staff_route


def _meta() -> dict:
    return {k: {"title": c["title"], "short": c["short"], "subs": c["subs"]} for k, c in SC.CATS.items()}


async def _body(request) -> dict:
    try:
        d = await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _err(e: SC.SocialError) -> web.Response:
    return web.json_response({"error": e.code, "message": e.message}, status=400)


@staff_route
async def api_social(request):
    return ok({**await SC.summary(viewer_scope()), "meta": _meta()})


@staff_route
async def api_social_list(request):
    try:
        items = await SC.listing(viewer_scope(), request.query.get("cat", ""))
    except SC.SocialError as e:
        return _err(e)
    return ok({"items": items, "meta": _meta()})


@staff_route
async def api_social_assign(request):
    """Qo'lda: tanlangan talabalarga toifa (kichik toifa, izoh bilan)."""
    d = await _body(request)
    try:
        ids = list(dict.fromkeys(int(x) for x in d.get("student_ids") or []))
    except (TypeError, ValueError):
        return bad("bad_student")
    if not ids:
        return bad("no_students")
    added = same = 0
    try:
        for sid in ids:
            if not _visible(await db.get_student(sid)):
                continue
            if await SC.add(sid, str(d.get("category", "")), str(d.get("sub") or ""), str(d.get("note") or ""),
                            "qolda", request["user"]["id"]):
                added += 1
            else:
                same += 1
    except SC.SocialError as e:
        return _err(e)
    return ok({"ok": True, "added": added, "same": same})


@staff_route
async def api_social_remove(request):
    d = await _body(request)
    try:
        sid = int(d.get("student_id"))
    except (TypeError, ValueError):
        return bad("bad_student")
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    return ok({"ok": await SC.remove(sid, str(d.get("category", "")), str(d.get("sub") or ""))})


@staff_route
async def api_social_student(request):
    sid = int(request.match_info["sid"])
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    return ok({"items": await SC.of_student(sid), "meta": _meta()})


def setup(r) -> None:
    r.add_get("/api/staff/social", api_social)
    r.add_get("/api/staff/social/list", api_social_list)
    r.add_post("/api/staff/social/assign", api_social_assign)
    r.add_post("/api/staff/social/remove", api_social_remove)
    r.add_get("/api/staff/social/student/{sid:\\d+}", api_social_student)
