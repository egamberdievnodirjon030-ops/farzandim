"""Telegram buyruqlar menyusi — rol bo'yicha: ota-ona, kurs koordinatori, super-admin.
Koordinator bot ichidan qo'shilsa yoki olib tashlansa — uning menyusi darhol yangilanadi (apply_commands)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from config import ADMIN_IDS
from tenancy import is_super

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Bosh menyu"),
    BotCommand(command="yordam", description="Botdan foydalanish"),
    BotCommand(command="bekor", description="Joriy amalni bekor qilish"),
    BotCommand(command="nizomlar", description="📜 Universitet ichki nizomlari"),
]
ADMIN_COMMANDS = PUBLIC_COMMANDS + [
    BotCommand(command="admin", description="Kurs koordinatori buyruqlari"),
    BotCommand(command="import", description="Excel fayl yuklash"),
    BotCommand(command="elon", description="E'lon yuborish"),
    BotCommand(command="stat", description="Statistika"),
    BotCommand(command="talaba", description="Talabani qidirish"),
    BotCommand(command="jadval", description="Talabaning shaxsiy dars jadvali"),
    BotCommand(command="tayyor", description="Import sessiyasini yakunlash"),
    BotCommand(command="panel", description="📊 Kurs holati"),
    BotCommand(command="kompyuter", description="💻 Kompyuter versiyasi (brauzerda)"),
    BotCommand(command="koordinator", description="Ota-onalarga ko'rinadigan ismingiz"),
    BotCommand(command="tarjimalar", description="🌐 Fan va fakultet nomlari tarjimasi"),
    BotCommand(command="hisobot", description="📥 Hisobot: Excel yoki PDF"),
    BotCommand(command="muddat", description="To'lov muddatlari"),
    BotCommand(command="qarzdorlar", description="Moliyaviy qarzdorlar (kontrakt, trimestr)"),
    BotCommand(command="akademik", description="Akademik qarzdorlar"),
    BotCommand(command="chegaralar", description="Dars qoldirish chegaralariga yetganlar"),
    BotCommand(command="hujjat", description="PDF hujjatni ota-onaga yuborish"),
    BotCommand(command="hujjatlar", description="Talabaga yuborilgan hujjatlar"),
    BotCommand(command="yuklamalar", description="📂 Yuklangan fayllar (o'chirish)"),
    BotCommand(command="shablon", description="Excel namunalari"),
    BotCommand(command="guruhlar", description="Talabalar Telegram guruhlari"),
    BotCommand(command="tekshir", description="Ro'yxatdan o'tganlarni qayta tekshirish"),
    BotCommand(command="bloklar", description="Talaba deb bloklanganlar"),
]


SUPER_COMMANDS = [
    BotCommand(command="start", description="🛡 Super-admin menyusi"),
    BotCommand(command="kurslar", description="🏫 Kurslar va koordinatorlar"),
    BotCommand(command="yangi_kurs", description="➕ Yangi kurs"),
    BotCommand(command="umumiy", description="📊 Barcha kurslar holati"),
    BotCommand(command="shablonlar", description="📑 Shablonlar: o'zgartirish va qo'shish"),
    BotCommand(command="zaxira", description="💾 Zaxira nusxa hozir"),
    BotCommand(command="xatolar", description="🧾 Xatolar jurnali"),
] + [c for c in ADMIN_COMMANDS if c.command not in ("start",)]


APP_PUBLIC_COMMANDS = [BotCommand(command="start", description="📱 Ilovani ochish"),
                       BotCommand(command="nizomlar", description="📜 Universitet ichki nizomlari")]
APP_STAFF_COMMANDS = APP_PUBLIC_COMMANDS + [BotCommand(command="kompyuter", description="💻 Kompyuter versiyasi")]


async def apply_commands(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchining roliga mos buyruqlar menyusi (super-admin / kurs koordinatori / ota-ona).
    Ilova rejimida — faqat /start (xodimlarga /kompyuter ham): qolgan ish ilovada."""
    import appmode
    try:
        if appmode.APP_MODE:
            if is_super(user_id) or user_id in ADMIN_IDS:
                await bot.set_my_commands(APP_STAFF_COMMANDS, scope=BotCommandScopeChat(chat_id=user_id))
            else:
                await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=user_id))
            return True
        if is_super(user_id):
            await bot.set_my_commands(SUPER_COMMANDS, scope=BotCommandScopeChat(chat_id=user_id))
        elif user_id in ADMIN_IDS:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=user_id))
        else:
            await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=user_id))
        return True
    except Exception:  # foydalanuvchi botni hali ochmagan bo'lishi mumkin
        logging.getLogger(__name__).warning("%s uchun buyruqlar menyusi o'rnatilmadi (botga /start yuborsin)", user_id)
        return False


async def setup_commands(bot: Bot) -> None:
    import appmode
    await bot.set_my_commands(APP_PUBLIC_COMMANDS if appmode.APP_MODE else PUBLIC_COMMANDS, scope=BotCommandScopeDefault())
    for uid in list(ADMIN_IDS):
        await apply_commands(bot, uid)
