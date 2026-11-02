"""Talabaning o'ziga — choralar va rasmiy hujjatlar ota-onaga yuborilgan paytning o'zida, talabalar boti orqali
(alohida bot sozlanmagan bo'lsa — asosiy bot). Talaba botga ulangan bo'lishi kerak (student_accounts: shaxsiy havola,
telefon raqami yoki ota-onani tasdiqlash orqali). Har bir xabar talabaning bildirishnomalar tarixiga ham yoziladi —
talaba ilovasida («🔔 Bildirishnomalar») ko'rinadi; hujjat — «📄 Hujjatlarim» da.

Matnlar talabaga qaratilgan («sizga … e'lon qilindi»), talaba tanlagan tilda."""
from __future__ import annotations

import asyncio
import logging

import botlar
from database import db
from i18n import tr, use_lang
from tenancy import central, current_course
from utils import esc, now_iso

log = logging.getLogger(__name__)


async def mark_seen(tg_id: int) -> None:
    """Talaba botda yoki ilovada faol — oxirgi faollik yoziladi, «bloklagan» belgisi olinadi (barcha kurslarda)."""
    ts = now_iso()
    for key in db.keys():
        try:
            await db.for_course(key).execute("UPDATE student_accounts SET seen_at = ?, blocked_at = NULL WHERE tg_id = ?", (ts, tg_id))
        except Exception:  # noqa: BLE001  (faollik belgisi — asosiy ishni to'xtatmasin)
            log.exception("seen_at (%s)", key)


async def mark_blocked(tg_id: int) -> None:
    """Xabar yetmadi (talaba botni bloklagan yoki o'chirgan) — panelda «bloklagan» ko'rinadi."""
    for key in db.keys():
        try:
            await db.for_course(key).execute("UPDATE student_accounts SET blocked_at = ? WHERE tg_id = ? AND blocked_at IS NULL",
                                             (now_iso(), tg_id))
        except Exception:  # noqa: BLE001
            log.exception("blocked_at (%s)", key)


async def chat_of(sid: int) -> int | None:
    """Talabaning Telegram chati (botga ulangan bo'lsa)."""
    r = await db.fetchone("SELECT tg_id FROM student_accounts WHERE student_id = ?", (sid,))
    return r["tg_id"] if r else None


def _app_kb(sid: int, route: str):
    """Talaba ilovasi sozlangan bo'lsa — «Ilovada ochish» tugmasi."""
    try:
        import studentapp
        return studentapp.open_kb(route)
    except Exception:  # noqa: BLE001  (ilova yo'q — tugmasiz)
        return None


async def _remember(sid: int, kind: str, text: str, doc_id: int | None = None) -> None:
    await db.execute("INSERT INTO student_notices (student_id, kind, text, document_id, created_at) VALUES (?, ?, ?, ?, ?)",
                     (sid, kind, text[:3500], doc_id, now_iso()))


async def send_text(bot, sid: int, build, kind: str = "chora", route: str = "/") -> bool:
    """build() — joriy tilda matn (async yoki oddiy funksiya). Talaba ulanmagan bo'lsa ham tarixga yoziladi (ilovada
    ko'rinadi). Qaytaradi: Telegramga yetkazildimi."""
    chat = await chat_of(sid)
    lang = (await central.get_lang(chat) if chat else None) or "uz"
    with use_lang(lang):
        text = build()
        if asyncio.iscoroutine(text):
            text = await text
        kb = _app_kb(sid, route)
    await _remember(sid, kind, text)
    b = botlar.student_bot(bot)
    if b is None or not chat:
        return False
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    try:
        await b.send_message(chat, text, reply_markup=kb, disable_web_page_preview=True)
        await asyncio.sleep(0.04)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        log.warning("Talabaga xabar yuborilmadi (%s): %s", sid, e)
        if isinstance(e, TelegramForbiddenError):
            await mark_blocked(chat)
    except Exception:  # noqa: BLE001  (tarmoq — ota-onaga yuborish to'xtamasin)
        log.exception("Talabaga xabar yuborilmadi (%s)", sid)
    return False


def doc_caption(doc: dict, st: dict) -> str:
    """Talabaga PDF bilan boradigan izoh."""
    from utils import doc_title, fmt_date
    lines = [f"<b>{doc_title(doc['doc_type'])}</b>", "",
             tr("Hurmatli {name}, sizga tegishli rasmiy hujjat. Xuddi shu hujjat ota-onangizga ham yuborildi.",
                name=esc(st.get("full_name") or "")),
             tr("🗓 Sana: {d}", d=fmt_date(doc["doc_date"] or doc["created_at"][:10], False))]
    if doc.get("comment"):
        c = doc["comment"]
        lines += ["", f"💬 {esc(c if len(c) <= 500 else c[:500] + '…')}"]
    if doc.get("redacted"):
        lines += ["", tr("🔒 Hujjatdagi boshqa talabalarning ma'lumotlari maxfiylik uchun yopilgan.")]
    lines += ["", tr("Savollar bo'lsa — kurs koordinatoringizga murojaat qiling.")]
    return "\n".join(lines)[:1024]


async def send_document(bot, did: int, st: dict) -> bool:
    """Rasmiy hujjat (PDF) — talabaga ham. Qaytaradi: Telegramga yetkazildimi (ilovada baribir ko'rinadi)."""
    import docstore
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    from aiogram.types import BufferedInputFile
    doc = await db.get_document(did)
    if not doc:
        return False
    chat = await chat_of(st["id"])
    lang = (await central.get_lang(chat) if chat else None) or "uz"
    with use_lang(lang):
        caption = doc_caption(doc, st)
        kb = _app_kb(st["id"], f"/doc/{did}")
    await _remember(st["id"], "doc", caption, did)
    b = botlar.student_bot(bot)
    if b is None or not chat:
        return False
    course = current_course() or "_"
    try:
        f = doc["file_id"]
        if docstore.is_local(f):
            f = BufferedInputFile(await docstore.load(bot, course, f), filename=doc.get("file_name") or "hujjat.pdf")
        elif b is not botlar.main_bot(bot):  # Telegram file_id boshqa botniki — talabalar botida ishlamaydi
            f = BufferedInputFile(await docstore.load(botlar.main_bot(bot), course, f), filename=doc.get("file_name") or "hujjat.pdf")
        m = await b.send_document(chat, f, caption=caption, reply_markup=kb)
        await db.execute("INSERT OR REPLACE INTO student_deliveries (document_id, student_id, chat_id, message_id, sent_at) "
                         "VALUES (?, ?, ?, ?, ?)", (did, st["id"], chat, m.message_id, now_iso()))
        await asyncio.sleep(0.05)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        log.warning("Talabaga hujjat yuborilmadi (%s): %s", st["id"], e)
        if isinstance(e, TelegramForbiddenError):
            await mark_blocked(chat)
    except Exception:  # noqa: BLE001
        log.exception("Talabaga hujjat yuborilmadi (%s)", st["id"])
    return False


async def recall_document(bot, did: int) -> int:
    """Hujjat qaytarib olinganda — talaba chatidagi xabar ham o'chiriladi."""
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    n = 0
    b = botlar.student_bot(bot)
    for r in await db.fetchall("SELECT * FROM student_deliveries WHERE document_id = ?", (did,)):
        try:
            if b is not None and r["message_id"]:
                await b.delete_message(r["chat_id"], r["message_id"])
                n += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
    await db.execute("DELETE FROM student_notices WHERE document_id = ?", (did,))
    return n
