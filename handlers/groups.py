"""Talabalar Telegram guruhlari: botni qo'shish, a'zolarni qayd etish, ota-ona bo'lib kirgan talabani aniqlash.

Bot guruhda hech narsa yozmaydi (faqat kurs koordinatorining /guruh buyrug'iga javob beradi).
A'zolarni ko'ra olishi uchun bot guruhda administrator bo'lishi kerak.
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated, Message, User

from config import ADMIN_IDS
from tenancy import central, course_admins, current_course
from database import db
from guard import check_existing_parent
from keyboards import tg_group_kb
from notifier import safe_send
from utils import esc, group_key

router = Router(name="groups")
GROUP_TYPES = {"group", "supergroup"}
router.message.filter(F.chat.type.in_(GROUP_TYPES))

_ADMIN_STATUSES = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
_GONE = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
_PRESENT = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR,
            ChatMemberStatus.RESTRICTED}

NOT_ADMIN_HINT = (
    "Bot a'zolarni aniqlay olishi uchun guruh sozlamalarida uni <b>administrator</b> qiling "
    "(eng kam huquqlar bilan; xabarlarni o'chirish va boshqa huquqlar shart emas)."
)


async def _notify_admins(bot: Bot, text: str, **kwargs) -> None:
    for admin_id in course_admins():  # guruh biriktirilgan kursning koordinator(lar)i
        await safe_send(bot, admin_id, text, **kwargs)


async def _observe(bot: Bot, user: User | None, group: dict, source: str) -> None:
    if not user or user.is_bot or user.id in ADMIN_IDS:
        return
    await db.record_member(user.id, group["chat_id"], user.full_name, user.username, source)
    await check_existing_parent(bot, user.id, user.full_name, user.username,
                                f"Talabalar guruhida aniqlandi: «{group.get('title') or group['chat_id']}»", group)


# ---------------------------------------------------------------- bot guruhga qo'shildi / chiqarildi
@router.my_chat_member(F.chat.type.in_(GROUP_TYPES))
async def on_bot_status(event: ChatMemberUpdated, bot: Bot) -> None:
    chat, status = event.chat, event.new_chat_member.status
    known = await db.get_tg_group(chat.id)
    if status in _GONE:
        if known and known["active"]:
            await db.update_tg_group(chat.id, active=0)
            await _notify_admins(bot, f"ℹ️ Bot «{esc(chat.title)}» guruhidan chiqarildi.")
        return
    is_admin = status in _ADMIN_STATUSES
    if not known or not known["active"]:
        if event.from_user.id not in ADMIN_IDS:
            # begona odam botni ixtiyoriy guruhga qo'shsa, u guruh a'zolari talaba deb hisoblanib qolmasin
            try:
                await bot.leave_chat(chat.id)
            except Exception:
                pass
            return
        await db.add_tg_group(chat.id, chat.title, event.from_user.id, is_admin)
        if current_course():  # guruh botni qo'shgan koordinatorning kursiga biriktiriladi
            await central.set_group_course(chat.id, current_course())
        await _notify_admins(
            bot,
            f"✅ Bot «{esc(chat.title)}» guruhiga qo'shildi va <b>talabalar guruhi</b> sifatida ro'yxatga olindi. "
            "Bu guruh a'zolari ota-onalar botiga kira olmaydi.\n\n"
            + ("" if is_admin else "⚠️ " + NOT_ADMIN_HINT + "\n\n")
            + "Guruhni akademik guruh nomiga bog'lash uchun guruhning o'zida yozing: <code>/guruh IQ-21</code>\n"
            "Agar bu talabalar guruhi bo'lmasa, pastdagi tugmani bosing.",
            reply_markup=tg_group_kb(chat.id),
        )
        return
    await db.update_tg_group(chat.id, title=chat.title, bot_admin=int(is_admin))
    if not is_admin and known["bot_admin"]:
        await _notify_admins(bot, f"⚠️ «{esc(chat.title)}» guruhida bot administratorlikdan olindi. " + NOT_ADMIN_HINT)
    elif is_admin and not known["bot_admin"]:
        await _notify_admins(bot, f"✅ «{esc(chat.title)}» guruhida bot administrator qilindi — "
                                  "a'zolarni aniqlash ishlaydi.")


# ---------------------------------------------------------------- a'zolar qo'shilishi (bot admin bo'lsa keladi)
@router.chat_member(F.chat.type.in_(GROUP_TYPES))
async def on_member_update(event: ChatMemberUpdated, bot: Bot) -> None:
    group = await db.get_tg_group(event.chat.id)
    if not group or not group["active"]:
        return
    if event.new_chat_member.status in _PRESENT:
        await _observe(bot, event.new_chat_member.user, group, "qo'shildi")


# ---------------------------------------------------------------- /guruh IQ-21 (faqat kurs koordinatori)
@router.message(Command("guruh"))
async def cmd_bind_group(message: Message, command: CommandObject) -> None:
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return
    name = (command.args or "").strip()
    if not await db.get_tg_group(message.chat.id):
        await db.add_tg_group(message.chat.id, message.chat.title, message.from_user.id, False)
    if not name or not group_key(name):
        await message.reply("Foydalanish: <code>/guruh IQ-21</code>")
        return
    await db.update_tg_group(message.chat.id, group_name=name, group_key=group_key(name), active=1)
    if current_course():  # ko'p kursli rejim: guruh shu koordinatorning kursiga biriktiriladi
        await central.set_group_course(message.chat.id, current_course())
    await message.reply(f"✅ Bu Telegram guruh «{esc(name)}» akademik guruhiga bog'landi.")


# ---------------------------------------------------------------- guruhdagi har qanday xabar
@router.message()
async def on_group_message(message: Message, bot: Bot) -> None:
    if message.migrate_to_chat_id:
        await db.migrate_tg_group(message.chat.id, message.migrate_to_chat_id)
        await central.move_group(message.chat.id, message.migrate_to_chat_id)
        return
    group = await db.get_tg_group(message.chat.id)
    if not group or not group["active"]:
        return
    for user in message.new_chat_members or []:
        await _observe(bot, user, group, "qo'shildi")
    if message.sender_chat is None:  # anonim administratorlar va kanal nomidan yozilganlar hisobga olinmaydi
        await _observe(bot, message.from_user, group, "xabar")
