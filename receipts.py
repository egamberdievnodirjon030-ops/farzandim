"""To'lov cheki / kvitansiyasi — kurs koordinatori yuklaydi (PDF yoki rasm): talabaning kontrakt yoki trimestr qarzi
yopiladi (summa qarzdan kam bo'lsa — qarz kamayadi) va u qarzdorlar ro'yxatidan chiqadi. Qarz holati payments ga shu
kungi yozuv sifatida qo'shiladi — buxgalteriyaning keyingi (sanasi keyinroq) hisobotida qarz hali ko'rinsa, o'sha ustun.
Chek bekor qilinsa — avvalgi holat tiklanadi."""
from __future__ import annotations

import json
import mimetypes
import secrets
from pathlib import Path

from config import DATA_DIR
from database import RECEIPT_NOTE, db
from tenancy import current_course
from utils import now_iso, today

KINDS = {"kontrakt": "Kontrakt", "trimestr": "Trimestr"}
EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_FILE = 15 * 1024 * 1024


class ReceiptError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _dir() -> Path:
    return DATA_DIR / (current_course() or "_") / "cheklar"


def _safe(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in "._- " else "_" for c in (name or "chek"))
    return keep.strip()[:80] or "chek"


async def add(sid: int, kind: str, name: str, data: bytes, amount: float | None = None, paid_date: str | None = None,
              note: str = "", uid: int | None = None) -> dict:
    """Chekni saqlaydi va qarzni yopadi (qisman). Qaytaradi: {id, debt_before, amount, debt_after}."""
    if kind not in KINDS:
        raise ReceiptError("bad_kind", "To'lov turi noto'g'ri")
    if Path(name or "").suffix.lower() not in EXTS:
        raise ReceiptError("bad_file", "Chek PDF yoki rasm (JPG, PNG) bo'lsin")
    if not data:
        raise ReceiptError("empty", "Fayl bo'sh")
    if len(data) > MAX_FILE:
        raise ReceiptError("too_big", "Fayl juda katta (15 MB gacha)")
    cur = await db.latest_payment(sid, kind)
    debt = float((cur or {}).get("debt") or 0)
    if debt <= 0:
        raise ReceiptError("no_debt", "Bu talabada qarz yo'q")
    if amount is not None and amount <= 0:
        raise ReceiptError("bad_amount", "Summa noto'g'ri")
    amt = min(amount, debt) if amount else debt
    left = round(debt - amt, 2)
    as_of = max(today().isoformat(), (cur or {}).get("as_of") or "")
    prev = await db.fetchone("SELECT * FROM payments WHERE student_id = ? AND kind = ? AND as_of = ?", (sid, kind, as_of))
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    fname = f"{secrets.token_hex(5)}_{_safe(name)}"
    (d / fname).write_bytes(data)
    rid = await db.execute(
        "INSERT INTO payment_receipts (student_id, kind, amount, debt_before, debt_after, paid_date, as_of, prev, name, path, "
        "mime, size, note, uploaded_at, by_user) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, kind, amt, debt, left, paid_date or None, as_of, json.dumps(prev, default=str) if prev else None, _safe(name),
         str((d / fname).relative_to(DATA_DIR)), mimetypes.guess_type(name)[0] or "application/octet-stream", len(data),
         (note or "").strip()[:300] or None, now_iso(), uid))
    contract = (cur or {}).get("contract")
    paid = float((cur or {}).get("paid") or 0) + amt
    await db.upsert_payments([{"student_id": sid, "contract": contract, "paid": paid, "debt": left,
                               "percent": round(100 * paid / contract, 1) if contract else None,
                               "note": f"{RECEIPT_NOTE}{rid}" + (f" ({paid_date})" if paid_date else "")}],
                             as_of, (cur or {}).get("year_label"), kind)
    return {"id": rid, "debt_before": debt, "amount": amt, "debt_after": left}


def _is_mine(note: str | None, rid: int) -> bool:
    """payments qatori aynan shu chek bilan yozilganmi (№ 1 va № 12 adashmasin)."""
    rest = (note or "")[len(RECEIPT_NOTE):] if (note or "").startswith(RECEIPT_NOTE) else ""
    return rest.split(" ")[0] == str(rid)


async def cancel(rid: int, uid: int | None = None) -> dict:
    """Chekni bekor qilish — qarz avvalgi holatiga qaytadi (shu sanadagi yozuv chek bilan yaratilgan bo'lsa)."""
    r = await db.fetchone("SELECT * FROM payment_receipts WHERE id = ?", (rid,))
    if not r or r["cancelled_at"]:
        raise ReceiptError("not_found", "Chek topilmadi")
    row = await db.fetchone("SELECT * FROM payments WHERE student_id = ? AND kind = ? AND as_of = ?",
                            (r["student_id"], r["kind"], r["as_of"]))
    if row and _is_mine(row["note"], rid):
        if r["prev"]:
            p = json.loads(r["prev"])
            await db.execute("UPDATE payments SET contract = ?, paid = ?, debt = ?, overpaid = ?, percent = ?, note = ? "
                             "WHERE student_id = ? AND kind = ? AND as_of = ?",
                             (p.get("contract"), p.get("paid"), p.get("debt") or 0, p.get("overpaid") or 0, p.get("percent"),
                              p.get("note"), r["student_id"], r["kind"], r["as_of"]))
        else:
            await db.execute("DELETE FROM payments WHERE student_id = ? AND kind = ? AND as_of = ?",
                             (r["student_id"], r["kind"], r["as_of"]))
    await db.execute("UPDATE payment_receipts SET cancelled_at = ?, cancelled_by = ? WHERE id = ?", (now_iso(), uid, rid))
    return {"ok": True}


async def listing(sids: set[int] | None, limit: int = 300) -> list[dict]:
    rows = await db.fetchall(
        """SELECT r.*, s.full_name, s.group_name, s.group_key, s.hemis_id FROM payment_receipts r
           JOIN students s ON s.id = r.student_id ORDER BY r.id DESC LIMIT ?""", (limit,))
    return [{k: v for k, v in r.items() if k not in ("path", "prev")} for r in rows if sids is None or r["student_id"] in sids]


async def get_file(rid: int) -> tuple[dict, bytes] | None:
    r = await db.fetchone("SELECT * FROM payment_receipts WHERE id = ?", (rid,))
    if not r:
        return None
    p = DATA_DIR / r["path"]
    return (r, p.read_bytes()) if p.exists() else None
