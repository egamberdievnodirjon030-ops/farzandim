"""Boshqaruv paneli «To'lovlar»: kontrakt va trimestr qarzdorlari, to'lov cheki / kvitansiyasini yuklab qarzni yopish,
cheklar arxivi (ko'rish, bekor qilish). Kurs koordinatori — o'z guruhlari."""
from __future__ import annotations

from aiohttp import web

import receipts as R
import status
from database import RECEIPT_NOTE, db
from tenancy import scope_students
from utils import today
from webapi import _file_resp, _visible, bad, ok, staff_route


@staff_route
async def api_payments(request):
    students = scope_students(await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name"))
    sts = await status.all_statuses(students)
    dl = await status.deadlines()
    linked = {r["student_id"] for r in await db.fetchall(
        "SELECT DISTINCT ps.student_id FROM parent_students ps JOIN parents p ON p.tg_id = ps.parent_id WHERE p.active = 1")}
    out = {}
    t = today()
    for kind in R.KINDS:
        rows = []
        for x in sts:
            p = x["pays"].get(kind)
            if not p or not (p.get("debt") or 0) > 0:
                continue
            st = x["student"]
            rows.append({"id": st["id"], "name": st["full_name"], "group": st.get("group_name") or "", "hemis_id": st.get("hemis_id"),
                         "contract": p.get("contract"), "paid": p.get("paid"), "debt": p["debt"], "percent": p.get("percent"),
                         "as_of": p.get("as_of"), "linked": st["id"] in linked, "by_receipt": (p.get("note") or "").startswith(RECEIPT_NOTE)})
        rows.sort(key=lambda r: -r["debt"])
        d = dl.get(kind)
        out[kind] = {"items": rows, "sum": sum(r["debt"] for r in rows), "count": len(rows),
                     "deadline": d.isoformat() if d else None, "days_left": (d - t).days if d else None,
                     "as_of": max((r["as_of"] or "" for r in rows), default=None)}
    sids = {s["id"] for s in students}
    return ok({**out, "receipts": await R.listing(sids), "kinds": R.KINDS})


@staff_route
async def api_receipt_add(request):
    """Chek / kvitansiya: multipart — student_id, kind, amount (ixtiyoriy — bo'sh: qarz to'liq), date, note, file."""
    form, data, name = {}, None, ""
    async for part in await request.multipart():
        if part.name == "file" and part.filename:
            name, data = part.filename, bytes(await part.read(decode=False))
        elif part.name:
            form[part.name] = (await part.text()).strip()
    try:
        sid = int(form.get("student_id", ""))
    except ValueError:
        return bad("bad_student")
    if not _visible(await db.get_student(sid)):
        return bad("not_found", 404)
    amount = None
    if form.get("amount"):
        try:
            amount = float(form["amount"].replace(" ", "").replace(" ", "").replace(",", "."))
        except ValueError:
            return web.json_response({"error": "bad_amount", "message": "Summa noto'g'ri"}, status=400)
    try:
        res = await R.add(sid, form.get("kind", ""), name, data or b"", amount, form.get("date") or None, form.get("note", ""),
                          request["user"]["id"])
    except R.ReceiptError as e:
        return web.json_response({"error": e.code, "message": e.message}, status=400)
    return ok({"ok": True, **res})


@staff_route
async def api_receipt_cancel(request):
    rid = int(request.match_info["rid"])
    r = await db.fetchone("SELECT student_id FROM payment_receipts WHERE id = ?", (rid,))
    if not r or not _visible(await db.get_student(r["student_id"])):
        return bad("not_found", 404)
    try:
        return ok(await R.cancel(rid, request["user"]["id"]))
    except R.ReceiptError as e:
        return web.json_response({"error": e.code, "message": e.message}, status=400)


@staff_route
async def api_receipt_file(request):
    rid = int(request.match_info["rid"])
    got = await R.get_file(rid)
    if not got or not _visible(await db.get_student(got[0]["student_id"])):
        return bad("not_found", 404)
    r, data = got
    return _file_resp(r["name"], data, r["mime"], inline=request.query.get("view") == "1")


def setup(r) -> None:
    r.add_get("/api/staff/payments", api_payments)
    r.add_post("/api/staff/payments/receipt", api_receipt_add)
    r.add_post("/api/staff/payments/receipt/{rid:\\d+}/cancel", api_receipt_cancel)
    r.add_get("/api/staff/payments/receipt/{rid:\\d+}/file", api_receipt_file)
