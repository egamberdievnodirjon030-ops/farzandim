"""Ilova rejimi: WEBAPP_URL sozlangan bo'lsa bot faqat ilovaga o'tish vositasi va qisqa bildirishnomalar kanali.

Barcha amallar ilovada (Telegram Web App) va kompyuter versiyasida bajariladi. Bot:
  • /start — qisqa salom va «📱 Ilovani ochish» (kurs koordinatori va super-admin — «💻 Kompyuter versiyasi» ham);
  • bildirishnomalar — bir qatorli qisqa xabar («Farzandingiz davomatida o'zgarish bo'ldi») va tugma, u ilovada
    aynan shu farzandning tegishli bo'limini ochadi; to'liq matn ilovadagi bildirishnomalar markazida saqlanadi;
  • ro'yxatdan o'tish — ilova telefon raqamini Telegram orqali so'raydi, bot uni qabul qilib tasdiqlaydi.

WEBAPP_URL bo'sh bo'lsa (yoki BOT_FULL_MENU=1) — bot avvalgidek to'liq menyular bilan ishlaydi.
"""
from __future__ import annotations

import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import WEBAPP_PORT, WEBAPP_URL
from i18n import tr

APP_MODE = bool(WEBAPP_URL and WEBAPP_PORT) and os.getenv("BOT_FULL_MENU", "").strip() not in ("1", "true", "yes")

# qisqa bildirishnoma matnlari (tur → matn); {name} — farzandning qisqa ismi, {title} — hujjat nomi
SHORT = {
    "att_new": "📋 {name}: davomatda o'zgarish bo'ldi.",
    "att_change": "📋 {name}: davomatda o'zgarish bo'ldi.",
    "att_warn": "⚠️ {name}: dars qoldirish bo'yicha ogohlantirish.",
    "att_good": "✅ {name}: davomatda ijobiy o'zgarish.",
    "grade": "📝 {name}: baholarda yangilanish bo'ldi.",
    "acad": "❗ {name}: akademik qarzdorlik bo'yicha xabar.",
    "pay": "💰 {name}: to'lov ma'lumotlarida o'zgarish.",
    "pay_remind": "💰 {name}: to'lov muddati yaqinlashmoqda.",
    "doc": "📄 {name}: yangi hujjat — «{title}».",
    "news": "📢 Kurs koordinatoridan yangi e'lon.",
    "chat": "💬 Kurs koordinatoridan javob keldi.",
    "digest": "🌙 Kunlik xulosa tayyor.",
    "link": "✅ Farzandingiz ma'lumotlari ilovada.",
    "link_ok": "✅ Kurs koordinatori so'rovingizni tasdiqladi: {name}.",
    "link_no": "❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Kurs koordinatori bilan bevosita bog'laning.",
    "survey": "📋 Yangi so'rovnoma: «{title}». Fikringiz biz uchun muhim — bir necha daqiqa.",
    "reg": "📜 Universitet ichki nizomlariga qo'shildi: «{title}».",
}
KIND_OF = {"att_new": "att", "att_change": "att", "att_warn": "att", "att_good": "att", "grade": "grade", "acad": "grade",
           "pay": "pay", "pay_remind": "pay", "doc": "doc", "news": "news", "chat": "chat", "digest": "digest",
           "link": "link", "link_ok": "link", "link_no": "link",
           "survey": "survey", "reg": "reg"}


def short_name(st: dict | None) -> str:
    """Farzandning qisqa ismi (familiya va ism) joriy tilda."""
    if not st:
        return ""
    import loc
    parts = loc.student_name(st).split()
    return " ".join(parts[:2])


def short_text(sub: str, st: dict | None = None, **kw) -> str:
    return tr(SHORT[sub], name=short_name(st), **kw)


def app_button(route: str = "/", text: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text or tr("📱 Ilovada ochish"), web_app=WebAppInfo(url=f"{WEBAPP_URL}/#{route}"))


def app_kb(route: str = "/", text: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[app_button(route, text)]])


def staff_kb(uid: int, route: str = "/") -> InlineKeyboardMarkup:
    import deskauth
    return InlineKeyboardMarkup(inline_keyboard=[
        [app_button(route, "📱 Ilovani ochish")],
        [InlineKeyboardButton(text="💻 Kompyuter versiyasi", url=deskauth.login_url(uid))]])
