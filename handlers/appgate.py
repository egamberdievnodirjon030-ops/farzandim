"""Ilova rejimi (appmode.APP_MODE): ota-onaning botdagi matnlari va eski tugmalari — ilovaga yo'naltiriladi.

Bot faqat ilovaga o'tish vositasi: /start, telefon raqamini tasdiqlash (ilova Telegram orqali so'raydi) va
bildirishnomalar. Ota-ona botga matn yozsa yoki eski xabardagi tugmani bossa — «hammasi ilovada» va tugma.
Kurs koordinatori va super-admin bu routerga tushmaydi: ularning buyruqlari zaxira sifatida ishlayveradi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import appmode
from i18n import tr
from tenancy import is_staff

router = Router(name="appgate")


def _parent_private(event) -> bool:
    chat = event.chat if isinstance(event, Message) else (event.message.chat if event.message else None)
    return appmode.APP_MODE and chat is not None and chat.type == "private" and not is_staff(event.from_user.id)


router.message.filter(_parent_private)
router.callback_query.filter(_parent_private)


def _kb():
    return appmode.app_kb("/", tr("📱 Ilovani ochish"))


@router.message(F.text & ~F.text.startswith("/"))
async def text_to_app(message: Message, state: FSMContext) -> None:
    await state.clear()
    # oldingi versiyadan qolgan menyu tugmalari chatdan olib tashlanadi (ota-ona /start ni qayta bosmasa ham)
    await message.answer("📱", reply_markup=ReplyKeyboardRemove())
    await message.answer(tr("Barcha ma'lumotlar va amallar — ilovada 👇"), reply_markup=_kb())


@router.callback_query()
async def old_button_to_app(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await cb.message.answer(tr("Barcha ma'lumotlar va amallar — ilovada 👇"), reply_markup=_kb())
