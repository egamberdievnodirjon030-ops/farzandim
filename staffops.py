"""Kurs koordinatori va super-admin amallari — bot va kompyuter versiyasi (Web) uchun umumiy.

Bir xil amal (so'rovni tasdiqlash, kurs koordinatorini tayinlash yoki olib tashlash) botdan ham, kompyuter
versiyasidan ham bajarilganda natija va ota-onaga / koordinatorga boradigan xabar bir xil bo'lishi uchun.
"""
from __future__ import annotations

import html
import logging

import appmode
import live
from botcommands import apply_commands
from database import db
from i18n import tr, use_lang
from keyboards import coordinator_menu
from notifier import safe_send
from tenancy import central, course_title, reload_registry

log = logging.getLogger("staff")


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


# ---------------------------------------------------------------- ota-onaning farzandni bog'lash so'rovi
async def decide_link(bot, rid: int, approve: bool, admin_id: int) -> tuple[bool, str]:
    """So'rovni tasdiqlaydi yoki rad etadi va ota-onaga (uning tilida) xabar yuboradi.
    Qaytaradi: (bajarildimi, kurs koordinatoriga ko'rsatiladigan qisqa natija)."""
    req = await db.get_link_request(rid)
    if not req or req["status"] != "pending":
        return False, "Bu so'rov allaqachon ko'rib chiqilgan."
    if approve and await db.is_blocked(req["parent_id"]):
        return False, "Bu foydalanuvchi talaba deb bloklangan. Avval /bloklar orqali ruxsat bering."
    st = await db.get_student(req["student_id"])
    lang = await central.get_lang(req["parent_id"]) or "uz"
    if approve:
        await db.link_parent(req["parent_id"], req["student_id"], "manual")
        await db.decide_link_request(rid, "approved", admin_id)
        with use_lang(lang):
            if appmode.APP_MODE:
                text, kb = appmode.short_text("link_ok", st), appmode.app_kb("/")
            else:
                text = tr("✅ Kurs koordinatori so'rovingizni tasdiqladi. Endi <b>{name}</b> ma'lumotlarini "
                          "ko'rishingiz mumkin: «👨‍🎓 Farzandim» bo'limini oching.",
                          name=esc(st["full_name"]) if st else "—")
                kb = None
        await safe_send(bot, req["parent_id"], text, reply_markup=kb)
        live.publish(req["parent_id"], {"type": "link", "approved": True, "route": "/"})
        log.info("Bog'lash so'rovi tasdiqlandi: #%s (ota-ona %s → talaba %s)", rid, req["parent_id"], req["student_id"])
        return True, "✅ Tasdiqlandi"
    await db.decide_link_request(rid, "rejected", admin_id)
    with use_lang(lang):
        if appmode.APP_MODE:
            text, kb = appmode.short_text("link_no"), appmode.app_kb("/")
        else:
            text = tr("❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Iltimos, kurs koordinatori bilan bevosita "
                      "bog'laning.")
            kb = None
    await safe_send(bot, req["parent_id"], text, reply_markup=kb)
    live.publish(req["parent_id"], {"type": "link", "approved": False, "route": "/"})
    log.info("Bog'lash so'rovi rad etildi: #%s", rid)
    return True, "❌ Rad etildi"


# ---------------------------------------------------------------- kurs koordinatorlari (super-admin)
async def assign_coordinator(bot, uid: int, key: str, name: str | None, by: int | None) -> dict:
    """Kurs koordinatorini tayinlaydi (boshqa kursda bo'lsa — ko'chiradi), menyusini yangilaydi va xabar beradi."""
    old = next((c["course_key"] for c in (await central.registry())[1] if c["user_id"] == uid), None)
    await central.set_coordinator(uid, key, name, by)
    await reload_registry()
    menu_ok = await apply_commands(bot, uid)
    notified = True
    try:
        await bot.send_message(
            uid, f"✅ Siz «{esc(course_title(key))}» kurs koordinatori etib tayinlandingiz.\n"
                 "Kurs koordinatori menyusini ochish uchun: /start", reply_markup=coordinator_menu(course_title(key)))
    except Exception:
        notified = False
    log.info("Kurs koordinatori qo'shildi: %s → %s (%s)", uid, key, name or "-")
    return {"old": old if old and old != key else None, "notified": notified, "menu_ok": menu_ok}


async def unassign_coordinator(bot, uid: int, key: str) -> None:
    """Kurs koordinatorini olib tashlaydi (kurs ma'lumotlari o'chmaydi) va unga xabar beradi."""
    await central.remove_coordinator(uid)
    await reload_registry()
    await apply_commands(bot, uid)
    try:
        from aiogram.types import ReplyKeyboardRemove
        await bot.send_message(uid, f"Siz «{esc(course_title(key))}» kurs koordinatorlari ro'yxatidan chiqarildingiz.",
                               reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass
    log.info("Kurs koordinatori olib tashlandi: %s (%s)", uid, key)


# ---------------------------------------------------------------- yangi bog'lash so'rovi — kurs koordinatorlariga
async def notify_link_request(bot, rid: int, parent_name: str, st: dict, detailed: str) -> None:
    """Ilova rejimida — qisqa xabar va «Ilovada ko'rib chiqish»; aks holda — batafsil matn va botdagi tugmalar."""
    from keyboards import link_request_kb
    from tenancy import course_admins, current_course
    course = current_course() or "_"
    if appmode.APP_MODE:
        text = (f"🔗 <b>Farzandni bog'lash so'rovi</b> — {esc(parent_name)} → {esc(st['full_name'])} "
                f"({esc(st.get('group_name') or '')})")
        kb = appmode.app_kb("/staff/requests", "📱 Ilovada ko'rib chiqish")
    else:
        text, kb = detailed, link_request_kb(rid)
    for admin_id in course_admins():
        await safe_send(bot, admin_id, text, reply_markup=kb)
    live.publish_many(course_admins(), {"type": "request", "course": course, "route": "/staff/requests",
                                        "text": f"{parent_name} → {st['full_name']}"})


# ---------------------------------------------------------------- rasmiy hujjatni ota-onalarga yetkazish
async def _send_text(bot, chat_id: int, text: str, kb):
    """Matnli xabar; yuborilgan xabarni (message_id kerak) yoki None qaytaradi."""
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    try:
        return await bot.send_message(chat_id, text, reply_markup=kb)
    except TelegramForbiddenError:
        await db.set_parent_active(chat_id, False)
    except TelegramBadRequest as e:
        log.warning("Xabar yuborilmadi %s: %s", chat_id, e)
    return None


async def deliver_document(bot, did: int, st: dict) -> tuple[int, int]:
    """Hujjatni farzandning ota-onalariga yetkazadi. Ilova rejimida — hujjat nomi yozilgan qisqa xabar va hujjatni
    ilovada ochadigan tugma; aks holda — faylning o'zi. Qaytaradi: (yetkazildi, jami ota-onalar)."""
    import docstore
    from aiogram.types import BufferedInputFile
    from notifier import safe_send_document
    from reports import document_caption
    from tenancy import current_course
    from utils import DOC_TYPES
    doc = await db.get_document(did)
    course = current_course() or "_"
    route = f"/go/doc/{course}/{st['id']}"
    parents = await db.parents_of_student(st["id"])
    sent = 0
    for pid in parents:
        lang = await central.get_lang(pid) or "uz"
        with use_lang(lang):
            caption = document_caption(doc, st)
            if appmode.APP_MODE:
                title = tr(DOC_TYPES.get(doc["doc_type"], DOC_TYPES["boshqa"])[1])
                m = await _send_text(bot, pid, appmode.short_text("doc", st, title=title), appmode.app_kb(route))
            else:
                f = doc["file_id"]
                if docstore.is_local(f):
                    f = BufferedInputFile(await docstore.load(bot, course, f), filename=doc.get("file_name") or "hujjat.pdf")
                m = await safe_send_document(bot, pid, f, caption)
        if m:
            sent += 1
            await db.record_delivery(did, pid, m.message_id)
            await db.add_notification(pid, caption, st["id"], "doc")
            live.publish(pid, {"type": "notification", "kind": "doc", "course": course, "student_id": st["id"],
                               "text": caption[:300], "route": route})
    return sent, len(parents)
