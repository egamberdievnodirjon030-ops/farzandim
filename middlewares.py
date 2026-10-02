"""Middleware'lar: joriy kursni aniqlash (ko'p kursli rejim), talaba deb bloklanganlarni to'xtatish, tilni o'rnatish."""
from __future__ import annotations

import logging

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject

from config import ADMIN_IDS
from database import db
from tenancy import central, course_of_admin, current_user, is_super, use_course
from guard import BLOCKED_TEXT
from i18n import set_lang, tr


# Ota-ona tugmalari: farzand qaysi kursda ekanini bildiradi («t» maydoni) — prefiks bo'yicha
_PARENT_CB: dict[str, type] = {}


def register_parent_callbacks(*classes) -> None:
    for cls in classes:
        _PARENT_CB[cls.__prefix__] = cls


def course_from_callback(data: str | None) -> str | None:
    cls = _PARENT_CB.get((data or "").split(":", 1)[0])
    if not cls:
        return None
    try:
        return getattr(cls.unpack(data), "t", None) or None
    except (ValueError, TypeError):
        return None


async def _is_parent_in(user_id: int, key: str) -> bool:
    return bool(await db.for_course(key).get_parent(user_id))


async def resolve_course(event: TelegramObject, data: dict[str, Any]) -> str | None:
    """Kurs koordinatori — o'z kursi; super-admin — tanlagan kursi; guruh — biriktirilgan kurs;
    ota-ona — tanlagan farzandining kursi."""
    keys = db.keys()
    if not keys:
        return None  # hali birorta kurs yo'q — super-admin bot ichida yaratadi
    user = data.get("event_from_user")
    chat = data.get("event_chat")
    if chat is not None and chat.type in ("group", "supergroup"):
        key = await central.group_course(chat.id)
        if key in keys:
            return key
        admin_key = course_of_admin(user.id) if user else None
        return admin_key if admin_key in keys else keys[0]
    if user is None:
        return keys[0]
    admin_key = course_of_admin(user.id)
    if is_super(user.id):  # super-admin — «🔀 Kursga kirish» bilan tanlagan kurs
        key = await central.get_active(user.id)
        return key if key in keys else admin_key if admin_key in keys else keys[0]
    if admin_key in keys:
        return admin_key
    if isinstance(event, CallbackQuery):
        key = course_from_callback(event.data)
        if key in keys and await _is_parent_in(user.id, key):
            await central.set_active(user.id, key)
            return key
    key = await central.get_active(user.id)
    if key in keys and await _is_parent_in(user.id, key):
        return key
    for key in keys:
        if await _is_parent_in(user.id, key):
            return key
    return keys[0]


class CourseMiddleware(BaseMiddleware):
    """Ko'p kursli rejimda har bir so'rovni tegishli kurs bazasiga yo'naltiradi (bitta baza rejimida — o'tkazib yuboradi)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        token = current_user.set(user.id if user else None)
        try:
            if not db.multi:
                return await handler(event, data)
            key = await resolve_course(event, data)
            data["course"] = key
            with use_course(key):
                try:
                    return await handler(event, data)
                except Exception as e:  # kurs va foydalanuvchi hali ma'lum — jurnalga shu yerda (keyin umumiy ushlagich javob beradi)
                    if not isinstance(e, (TelegramBadRequest, TelegramForbiddenError)):
                        logging.getLogger("bot").error("Kutilmagan xato: %s", e, exc_info=e)
                        e._logged = True
                    raise
        finally:
            current_user.reset(token)


class LangMiddleware(BaseMiddleware):
    """Foydalanuvchi tanlagan tilni joriy til qilib o'rnatadi (tr() shu tilda ishlaydi)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        if user and user.id in ADMIN_IDS and (chat is None or chat.type == "private"):
            lang = "uz"  # kurs koordinatori interfeysi va bazadagi asl nomlar bilan ishlash — o'zbek tilida
        else:
            lang = (await central.get_lang(user.id) if user else None) or "uz"
        set_lang(lang)
        data["lang"] = lang
        return await handler(event, data)


async def _blocked_anywhere(user_id: int) -> bool:
    """Talaba deb bloklangan bo'lsa — barcha kurslar bo'yicha (bitta kursda bloklangan boshqasiga ham kira olmaydi)."""
    for key in db.keys():
        if await db.for_course(key).is_blocked(user_id):
            return True
    return False


def _student_confirm(event, data: dict) -> bool:
    """Talaba ota-onasini tasdiqlash jarayoni (havola, o'z raqami, «Ha/Yo'q») — talaba deb bloklangan bo'lsa ham ochiq."""
    if isinstance(event, Message):
        return bool(event.text and event.text.startswith("/start t_")) or \
            (bool(event.contact) and (data.get("raw_state") or "").startswith("SC:"))
    if isinstance(event, CallbackQuery):
        return (event.data or "").startswith("sc:")
    return False


class BlockedUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        private = chat is None or chat.type == "private"
        if user and private and user.id not in ADMIN_IDS and not _student_confirm(event, data) \
                and await _blocked_anywhere(user.id):
            if isinstance(event, Message):
                await event.answer(tr(BLOCKED_TEXT), reply_markup=ReplyKeyboardRemove())
            elif isinstance(event, CallbackQuery):
                await event.answer(tr(BLOCKED_TEXT), show_alert=True)
            return None
        return await handler(event, data)
