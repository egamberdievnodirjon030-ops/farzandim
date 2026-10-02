"""Ota-ona ↔ kurs koordinatori yozishmasi — bot ham, Web App ham shu funksiyalardan foydalanadi.

Har bir suhbat — bitta farzand va bitta ota-ona (messages jadvali). Ota-onaning ketma-ket xabarlari bitta ochiq
savolga (questions) birikadi: kurs koordinatori botdagi «💬 Javob berish» tugmasi yoki Web App orqali bittada javob
beradi, javob ota-onaga bot xabari bo'lib ham boradi.
"""
from __future__ import annotations

from aiogram import Bot

from config import MAX_OPEN_QUESTIONS
from database import db
from i18n import get_lang, tr
from notifier import safe_send
from tenancy import course_admins, current_course
from utils import esc, fmt_phone

MAX_UNANSWERED = max(MAX_OPEN_QUESTIONS, 10)  # javob kutayotgan xabarlar chegarasi (spamdan himoya)


async def parent_send(bot: Bot, parent_id: int, parent_name: str, st: dict, text: str) -> dict:
    """Ota-ona xabari: suhbatga yoziladi va farzand kursining koordinatorlariga yuboriladi.
    Qaytaradi: {"ok": bool, "id": xabar ID, "delivered": nechta koordinatorga, "error": sabab}."""
    text = (text or "").strip()[:3000]
    if not text:
        return {"ok": False, "error": "empty"}
    waiting = await db.fetchone("SELECT COUNT(*) AS n FROM messages WHERE parent_id = ? AND sender = 'parent' "
                                "AND question_id IN (SELECT id FROM questions WHERE answer IS NULL)", (parent_id,))
    if waiting and waiting["n"] >= MAX_UNANSWERED:
        return {"ok": False, "error": "too_many"}
    q = await db.open_question_for(st["id"], parent_id)
    qid = q["id"] if q else await db.add_question(parent_id, st["id"], text)
    mid = await db.add_message(st["id"], parent_id, "parent", text, parent_id, parent_name, qid)
    parent = await db.get_parent(parent_id)
    lang_hint = {"ru": "🌐 Ota-ona tili: rus — javobni rus tilida yozish tavsiya etiladi\n",
                 "en": "🌐 Ota-ona tili: ingliz — javobni ingliz tilida yozish tavsiya etiladi\n"}.get(get_lang(), "")
    admin_text = (f"✉️ <b>Ota-onadan xabar #{qid}</b>\n\n"
                  f"👤 {esc(parent_name)} ({fmt_phone(parent['phone'] if parent else '')})\n"
                  f"👨‍🎓 {esc(st['full_name'])} · {esc(st.get('group_name') or '')}\n" + lang_hint + "\n" + esc(text))
    import appmode
    import live
    from keyboards import answer_kb  # aylanma importdan saqlanish
    course = current_course() or "_"
    route = f"/staff/chat/{course}/{st['id']}/{parent_id}"
    if appmode.APP_MODE:  # ilova rejimi: qisqa xabar va ilovada javob berish tugmasi
        admin_text = (f"💬 <b>Yangi savol</b> — {esc(parent_name)} "
                      f"({esc(st['full_name'])}, {esc(st.get('group_name') or '')})")
    delivered = 0
    admins = course_admins(groups=[st.get("group_name")])  # talaba guruhi biriktirilgan koordinator(lar)
    for admin_id in admins:
        kb = appmode.app_kb(route, "📱 Ilovada javob berish") if appmode.APP_MODE else answer_kb(qid, st["id"], parent_id)
        delivered += await safe_send(bot, admin_id, admin_text, reply_markup=kb)
    live.publish_many(admins, {"type": "message", "course": course, "student_id": st["id"], "parent_id": parent_id,
                                        "text": f"{parent_name}: {text[:200]}", "route": route})
    return {"ok": True, "id": mid, "delivered": delivered, "question_id": qid}


async def staff_reply(bot: Bot, staff_id: int, staff_name: str, sid: int, parent_id: int, text: str,
                      parent_lang: str | None = None) -> dict:
    """Kurs koordinatori javobi: ochiq savol yopiladi, suhbatga yoziladi, ota-onaga bot orqali boradi."""
    text = (text or "").strip()[:3000]
    if not text:
        return {"ok": False, "error": "empty"}
    q = await db.open_question_for(sid, parent_id)
    if q:
        await db.answer_question(q["id"], text, staff_id)
    mid = await db.add_message(sid, parent_id, "staff", text, staff_id, staff_name, q["id"] if q else None)
    await db.mark_thread_read(sid, parent_id, "staff")
    import appmode
    import live
    from i18n import use_lang
    from keyboards import webapp_kb
    route = f"/chat/{current_course() or '_'}/{sid}"
    with use_lang(parent_lang or "uz"):
        if appmode.APP_MODE:  # ilova rejimi: javobning o'zi ilovada, botga — qisqa xabar
            body = appmode.short_text("chat")
        else:
            body = (f"💬 <b>{tr('Kurs koordinatori javobi')}</b>\n\n"
                    + (f"<i>{tr('Savolingiz:')}</i> {esc(q['text'][:500])}\n\n" if q else "") + esc(text))
        kb = webapp_kb(route)
    ok = await safe_send(bot, parent_id, body, reply_markup=kb)
    live.publish(parent_id, {"type": "message", "course": current_course() or "_", "student_id": sid,
                             "text": text[:200], "route": route})
    return {"ok": True, "id": mid, "delivered": bool(ok)}
