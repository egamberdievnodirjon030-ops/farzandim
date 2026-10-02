"""Talabalarni aniqlash: bot faqat ota-onalar uchun.

Foydalanuvchi talaba deb hisoblanadi, agar:
  • uning Telegram raqami kurs koordinatori yuklagan bazada talabaning O'Z raqami sifatida turgan bo'lsa, yoki
  • u bot qo'shilgan talabalar Telegram guruhlaridan birining a'zosi bo'lsa.
Bunday foydalanuvchi ro'yxatdan o'tkazilmaydi (yoki oldin o'tgan bo'lsa, kirishi yopiladi)
va kurs koordinatorlariga darhol xabar yuboriladi. Kurs koordinatori xato aniqlangan ota-onaga bir tugma bilan ruxsat beradi.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from config import ADMIN_IDS
from tenancy import course_admins
from database import db
from keyboards import guard_kb
from i18n import N_
from notifier import safe_send
from utils import esc, fmt_phone

log = logging.getLogger(__name__)

REJECT_TEXT = N_(
    "⛔️ Kechirasiz, bu bot faqat <b>ota-onalar</b> uchun mo'ljallangan.\n\n"
    "Siz talaba sifatida aniqlandingiz, shuning uchun kirish rad etildi va bu haqda kurs koordinatoriga xabar berildi.\n\n"
    "Agar siz ota-ona bo'lsangiz va bu xatolik bo'lsa, kurs koordinatori bilan bog'laning — tekshirgach, kirishga ruxsat beradi."
)
BLOCKED_TEXT = N_(
    "⛔️ Bu bot faqat ota-onalar uchun. Sizning kirishingiz yopilgan.\n"
    "Xatolik bo'lsa, kurs koordinatori bilan bog'laning."
)

_MEMBER = {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER}
_live_sem = asyncio.Semaphore(8)


async def _is_member(bot: Bot, chat_id: int, user_id: int) -> bool:
    for _ in range(2):
        try:
            async with _live_sem:
                m = await bot.get_chat_member(chat_id, user_id)
            return m.status in _MEMBER or (m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", False))
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            # foydalanuvchi guruhda umuman bo'lmagan yoki bot guruhdan chiqarilgan
            log.debug("get_chat_member %s/%s: %s", chat_id, user_id, e)
            return False
    return False


async def live_group_check(bot: Bot, user_id: int, groups: list[dict] | None = None) -> list[dict]:
    """Bot administrator bo'lgan talabalar guruhlarida foydalanuvchi a'zoligini Telegram orqali tekshiradi."""
    if groups is None:
        groups = [g for g in await db.tg_groups() if g["bot_admin"]]
    if not groups:
        return []
    try:
        flags = await asyncio.wait_for(
            asyncio.gather(*(_is_member(bot, g["chat_id"], user_id) for g in groups)), timeout=25
        )
    except asyncio.TimeoutError:
        log.warning("Guruh a'zoligini tekshirish vaqti tugadi (user %s)", user_id)
        return []
    return [g for g, ok in zip(groups, flags) if ok]


async def find_evidence(bot: Bot, user_id: int, phone: str | None, name: str | None = None,
                        username: str | None = None, live: bool = True) -> dict | None:
    """Foydalanuvchi talaba ekanini ko'rsatuvchi dalillar. Talaba emas bo'lsa — None."""
    if user_id in ADMIN_IDS:
        return None
    block = await db.get_block(user_id)
    if block and block["status"] == "allowed":  # kurs koordinatori ota-ona deb tasdiqlagan
        return None
    ev = {"students": [], "groups": [], "also_parent_of": []}
    if phone:
        ev["students"] = await db.students_by_self_phone(phone)
        if ev["students"]:
            ev["also_parent_of"] = await db.students_by_phone(phone)
    ev["groups"] = await db.member_groups(user_id)
    if live and not ev["groups"]:
        found = await live_group_check(bot, user_id)
        for g in found:
            await db.record_member(user_id, g["chat_id"], name, username, "tekshiruv")
        ev["groups"] = found
    return ev if (ev["students"] or ev["groups"]) else None


def _group_label(g: dict) -> str:
    title = esc(g.get("title") or str(g["chat_id"]))
    return f"«{title}»" + (f" ({esc(g['group_name'])})" if g.get("group_name") else "")


def _evidence_lines(ev: dict) -> list[str]:
    lines = []
    for s in ev["students"]:
        lines.append(f"• raqam bazada talabaning o'z raqami sifatida turibdi: <b>{esc(s['full_name'])}</b> · "
                     f"{esc(s.get('group_name') or '—')} · ID {esc(s['hemis_id'])}")
    for g in ev["groups"]:
        lines.append(f"• talabalar Telegram guruhi a'zosi: {_group_label(g)}")
    return lines


def _reason(ev: dict) -> str:
    parts = (["telefon"] if ev["students"] else []) + (["guruh"] if ev["groups"] else [])
    return "+".join(parts)


async def block_user(bot: Bot, user_id: int, phone: str | None, name: str | None, username: str | None,
                     ev: dict, context: str, notify: bool = True, registered: bool = False) -> None:
    """Kirishni yopadi va kurs koordinatorlariga tugmali xabar yuboradi."""
    lines = _evidence_lines(ev)
    await db.add_block(user_id, phone, name, username, _reason(ev), "\n".join(lines))
    if not notify:
        return
    who = esc(name or "—") + (f" (@{esc(username)})" if username else "")
    text = [
        ("🚫 <b>Ro'yxatdan o'tgan foydalanuvchi talaba deb aniqlandi</b>" if registered
         else "🚫 <b>Talaba ota-onalar botiga kirishga urindi</b>") + f"\n<i>{esc(context)}</i>\n",
        f"👤 Telegram: {who}, ID <code>{user_id}</code>",
        f"📱 Raqam: {fmt_phone(phone) if phone else 'yuborilmagan'}",
        "\n<b>Aniqlash asosi:</b>",
        *lines,
    ]
    if ev.get("also_parent_of"):
        kids = ", ".join(esc(s["full_name"]) for s in ev["also_parent_of"][:5])
        text.append(f"\n⚠️ Bu raqam <b>{kids}</b> uchun ota-ona telefoni sifatida ham yozilgan — "
                    "oilada umumiy raqam bo'lishi mumkin. Telefon orqali aniqlashtirish tavsiya etiladi.")
    text.append("\nKirish " + ("yopildi va xabarnomalar to'xtatildi" if registered else "rad etildi")
                + ". Agar bu haqiqatan ota-ona bo'lsa, «Ruxsat berish» tugmasini bosing.")
    for admin_id in course_admins():  # joriy kursning koordinator(lar)i
        await safe_send(bot, admin_id, "\n".join(text), reply_markup=guard_kb(user_id))


async def check_existing_parent(bot: Bot, user_id: int, name: str | None, username: str | None,
                                context: str, group: dict | None = None) -> bool:
    """Ro'yxatdan o'tgan ota-ona keyinchalik talaba ekani ma'lum bo'lsa — kirishini yopadi."""
    parent = await db.get_parent(user_id)
    if not parent or user_id in ADMIN_IDS:
        return False
    if await db.get_block(user_id):  # allaqachon bloklangan yoki kurs koordinatori ruxsat bergan
        return False
    ev = await find_evidence(bot, user_id, parent["phone"], name, username, live=False)
    if ev is None and group:
        ev = {"students": [], "groups": [group], "also_parent_of": []}
    if not ev:
        return False
    await block_user(bot, user_id, parent["phone"], name or parent.get("tg_name"), username, ev, context,
                     registered=True)
    return True


async def recheck_parents(bot: Bot, live: bool = False, progress=None, notify_limit: int = 20) -> dict:
    """Barcha ro'yxatdan o'tganlarni qayta tekshiradi (import yoki /tekshir buyrug'idan keyin)."""
    parents = await db.parents_to_recheck()
    groups = [g for g in await db.tg_groups() if g["bot_admin"]] if live else []
    found = notified = 0
    for i, p in enumerate(parents, 1):
        ev = await find_evidence(bot, p["tg_id"], p["phone"], p.get("tg_name"), None, live=False)
        if ev is None and groups:
            hit = await live_group_check(bot, p["tg_id"], groups)
            for g in hit:
                await db.record_member(p["tg_id"], g["chat_id"], p.get("tg_name"), None, "tekshiruv")
            if hit:
                ev = {"students": [], "groups": hit, "also_parent_of": []}
        if ev:
            found += 1
            send = notified < notify_limit
            await block_user(bot, p["tg_id"], p["phone"], p.get("tg_name"), None, ev,
                             "Qayta tekshiruv natijasi", notify=send, registered=True)
            notified += send
        if progress and i % 25 == 0:
            await progress(i, len(parents), found)
    return {"checked": len(parents), "found": found, "notified": notified, "groups": len(groups)}
