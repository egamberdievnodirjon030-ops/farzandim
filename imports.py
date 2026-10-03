"""Yuklangan fayllar (import) tarixi va o'chirish.

Har bir Excel yuklash — imports jadvalida bitta yozuv. Import davomida yozilgan davomat, HEMIS statistikasi, baholar,
akademik qarzdorlar, kontrakt/trimestr, jadval yozuvlari, ota-onalarga ketgan bildirishnomalar (ilovadagi markaz) va
Telegram xabarlari shu yozuvga bog'lanadi (import_id). Fayl o'chirilganda hammasi olib tashlanadi: ma'lumot bazadan,
bildirishnoma ilovadan, xabar ota-onaning Telegram chatidan (Telegram 48 soat ichida ruxsat beradi).

Talabalar ro'yxati (kontingent) o'chirilganda — shu fayl orqali kelgan va KEYIN BOSHQA FAYLDA QAYTA KELMAGAN
talabalar o'chiriladi, ular bilan birga ularning davomati, baholari, to'lovlari, hujjatlari, yozishmalari va ota-ona
bog'lanishlari ham (ota-onaning o'zi qoladi). Shuning uchun o'chirishdan oldin aniq sonlar ko'rsatiladi.
Talabalar telefonlari va tarjimalar fayllarini o'chirib bo'lmaydi.
"""
from __future__ import annotations

import logging

from datetime import datetime, timedelta

from database import IMPORT_TABLES, db
from utils import now_iso

log = logging.getLogger("imports")

NOT_DELETABLE = {"phones", "translations"}
LEGACY_WINDOW = timedelta(minutes=15)  # talabalar import_id siz yozilgan eski yuklamalar: fayl vaqtidan shu oraliqda


async def students_of(r: dict) -> list[int]:
    """Talabalar fayli o'chirilsa o'chadigan talabalar: oxirgi marta aynan shu fayl orqali kelganlar."""
    if r["kind"] != "students":
        return []
    ids = [x["id"] for x in await db.fetchall("SELECT id FROM students WHERE import_id = ?", (r["id"],))]
    if ids:
        return ids
    # eski yuklama (talabalar hali belgilanmagan): fayl yuklangan vaqtda yangilangan, keyin boshqa fayl yangilamagan
    try:
        start = datetime.fromisoformat(r["uploaded_at"])
    except (TypeError, ValueError):
        return []
    later = await db.fetchone("SELECT MIN(uploaded_at) t FROM imports WHERE kind = 'students' AND id > ? "
                              "AND deleted_at IS NULL", (r["id"],))
    end = start + LEGACY_WINDOW
    if later and later["t"]:
        end = min(end, datetime.fromisoformat(later["t"]))
    return [x["id"] for x in await db.fetchall(
        "SELECT id FROM students WHERE import_id IS NULL AND updated_at >= ? AND updated_at < ?",
        (start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")))]


async def students_impact(r: dict) -> dict:
    """O'chirishdan oldin ko'rsatiladi: nechta talaba va nechta ota-ona bog'lanishi o'chadi."""
    sids = await students_of(r)
    if not sids:
        return {"students": 0, "parents": 0}
    q = ",".join("?" * len(sids))
    p = await db.fetchone(f"SELECT COUNT(DISTINCT parent_id) n FROM parent_students WHERE student_id IN ({q})", sids)
    return {"students": len(sids), "parents": p["n"]}


async def start(kind: str, file_name: str, user_id: int | None) -> int:
    return await db.execute("INSERT INTO imports (kind, file_name, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?)",
                            (kind, file_name, user_id, now_iso()))


async def finish(imp_id: int, ok: bool) -> None:
    """Muvaffaqiyatsiz import — yozuv o'chiriladi; aks holda shu fayldan kelgan qatorlar soni yoziladi."""
    if not ok:
        await db.execute("DELETE FROM imports WHERE id = ?", (imp_id,))
        return
    n = (await db.fetchone("SELECT COUNT(*) n FROM students WHERE import_id = ?", (imp_id,)))["n"]
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
        item = {**r, "deletable": r["kind"] not in NOT_DELETABLE, "parents_notified": notes}
        if r["kind"] == "students":
            impact = await students_impact(r)
            item.update(rows=impact["students"], students=impact["students"], linked_parents=impact["parents"])
        out.append(item)
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
    stats = {"rows": 0, "notifications": 0, "messages": 0, "messages_failed": 0, "students": 0}
    r = await get(imp_id)
    sids = await students_of(r) if r else []
    if sids:  # talabalar fayli: ota-onalari ilovani yangilashi uchun — o'chirishdan oldin
        q = ",".join("?" * len(sids))
        parents += [x["parent_id"] for x in await db.fetchall(
            f"SELECT DISTINCT parent_id FROM parent_students WHERE student_id IN ({q})", sids)]
    for t in IMPORT_TABLES:
        cur = await db.conn.execute(f"DELETE FROM {t} WHERE import_id = ?", (imp_id,))
        if t == "notifications":
            stats["notifications"] += cur.rowcount
        elif t not in ("grade_history", "payment_reports"):  # yordamchi yozuvlar — ro'yxatdagi son bilan bir xil
            stats["rows"] += cur.rowcount
    if sids:
        q = ",".join("?" * len(sids))
        # talabaga tashqi kalit (FK) bilan bog'lanmagan yozuvlar — qo'lda; qolganlari (davomat, baholar, to'lovlar,
        # hujjatlar, yozishma, ota-ona bog'lanishlari...) talaba o'chganda o'zi o'chadi (ON DELETE CASCADE)
        for t in ("link_requests", "warnings_sent", "questions", "notifications"):
            await db.conn.execute(f"DELETE FROM {t} WHERE student_id IN ({q})", sids)
        await db.conn.execute(f"UPDATE parents SET current_student_id = NULL WHERE current_student_id IN ({q})", sids)
        cur = await db.conn.execute(f"DELETE FROM students WHERE id IN ({q})", sids)
        stats["students"] = cur.rowcount
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
