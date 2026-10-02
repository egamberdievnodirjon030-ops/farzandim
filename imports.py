"""Yuklangan fayllar (import) tarixi va o'chirish.

Har bir Excel yuklash — imports jadvalida bitta yozuv. Import davomida yozilgan davomat, HEMIS statistikasi, baholar,
akademik qarzdorlar, kontrakt/trimestr, jadval yozuvlari, ota-onalarga ketgan bildirishnomalar (ilovadagi markaz) va
Telegram xabarlari shu yozuvga bog'lanadi (import_id). Fayl o'chirilganda hammasi olib tashlanadi: ma'lumot bazadan,
bildirishnoma ilovadan, xabar ota-onaning Telegram chatidan (Telegram 48 soat ichida ruxsat beradi).

Talabalar ro'yxati va tarjimalarni o'chirib bo'lmaydi — ular boshqa barcha ma'lumotlarning asosi (talaba o'chsa,
uning ota-onasi, xabarlari, hujjatlari ham yo'qoladi).
"""
from __future__ import annotations

import logging

from database import IMPORT_TABLES, db
from utils import now_iso

log = logging.getLogger("imports")

NOT_DELETABLE = {"students", "phones", "translations"}


async def start(kind: str, file_name: str, user_id: int | None) -> int:
    return await db.execute("INSERT INTO imports (kind, file_name, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?)",
                            (kind, file_name, user_id, now_iso()))


async def finish(imp_id: int, ok: bool) -> None:
    """Muvaffaqiyatsiz import — yozuv o'chiriladi; aks holda shu fayldan kelgan qatorlar soni yoziladi."""
    if not ok:
        await db.execute("DELETE FROM imports WHERE id = ?", (imp_id,))
        return
    n = 0
    for t in IMPORT_TABLES:
        if t in ("notifications", "grade_history", "payment_reports"):
            continue
        n += (await db.fetchone(f"SELECT COUNT(*) n FROM {t} WHERE import_id = ?", (imp_id,)))["n"]
    await db.execute("UPDATE imports SET rows = ? WHERE id = ?", (n, imp_id))


async def listing(uid: int, everyone: bool, limit: int = 60) -> list[dict]:
    """Yuklangan fayllar (yangidan eskiga): kurs koordinatori — o'zi yuklaganlar, super-admin — hammasi."""
    rows = await db.fetchall(
        "SELECT * FROM imports WHERE deleted_at IS NULL" + ("" if everyone else " AND uploaded_by = ?")
        + " ORDER BY id DESC LIMIT ?", (limit,) if everyone else (uid, limit))
    out = []
    for r in rows:
        notes = (await db.fetchone("SELECT COUNT(DISTINCT parent_id) n FROM notifications WHERE import_id = ?",
                                   (r["id"],)))["n"]
        out.append({**r, "deletable": r["kind"] not in NOT_DELETABLE, "parents_notified": notes})
    return out


async def get(imp_id: int) -> dict | None:
    return await db.fetchone("SELECT * FROM imports WHERE id = ? AND deleted_at IS NULL", (imp_id,))


def can_delete(r: dict, uid: int, is_super: bool) -> bool:
    return r["kind"] not in NOT_DELETABLE and (is_super or r["uploaded_by"] == uid)


async def delete(bot, imp_id: int, by: int) -> dict:
    """Fayldan kelgan hamma narsani o'chiradi. Qaytaradi: nimalar o'chirilgani haqida sonlar."""
    import live
    import snapshots
    parents = [r["parent_id"] for r in await db.fetchall(
        "SELECT DISTINCT parent_id FROM notifications WHERE import_id = ?", (imp_id,))]
    stats = {"rows": 0, "notifications": 0, "messages": 0, "messages_failed": 0}
    for t in IMPORT_TABLES:
        cur = await db.conn.execute(f"DELETE FROM {t} WHERE import_id = ?", (imp_id,))
        if t == "notifications":
            stats["notifications"] += cur.rowcount
        elif t not in ("grade_history", "payment_reports"):  # yordamchi yozuvlar — ro'yxatdagi son bilan bir xil
            stats["rows"] += cur.rowcount
    msgs = await db.fetchall("SELECT chat_id, message_id FROM sent_messages WHERE import_id = ?", (imp_id,))
    await db.conn.execute("DELETE FROM sent_messages WHERE import_id = ?", (imp_id,))
    await db.conn.execute("UPDATE imports SET deleted_at = ?, deleted_by = ? WHERE id = ?", (now_iso(), by, imp_id))
    await db.conn.commit()
    for m in msgs:  # ota-onaning Telegram chatidan ham
        try:
            await bot.delete_message(m["chat_id"], m["message_id"])
            stats["messages"] += 1
        except Exception:  # 48 soatdan o'tgan yoki ota-ona botni o'chirgan
            stats["messages_failed"] += 1
    try:
        await snapshots.capture()  # dinamika — o'chirishdan keyingi holat
    except Exception:
        log.exception("Dinamika yangilanmadi")
    for pid in set(parents) | {m["chat_id"] for m in msgs}:
        live.publish(pid, {"type": "refresh"})  # ochiq ilova darhol yangilanadi
    log.info("Yuklangan fayl o'chirildi: #%s (%s) — %s", imp_id, by, stats)
    return stats
