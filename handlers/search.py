"""Ism-familiya bo'yicha qidiruv: boshqa hech qaysi handler olmagan matnli xabarlar shu yerga keladi.

Xavfsizlik: qidiruv faqat shu ota-onaga bog'langan farzandlar orasida bajariladi, shuning uchun
begona odam boshqa talabaning ismini yozib uning davomatini ko'ra olmaydi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from config import ADMIN_IDS
from database import db
from family import all_children
from tenancy import central, use_course
from i18n import tr
from keyboards import add_child_kb, child_card_kb, children_kb
from reports import student_card
from utils import name_score, normalize_text

router = Router(name="search")
router.message.filter(F.chat.type == "private")  # guruhlarda faqat handlers/groups.py ishlaydi


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def search_child(message: Message) -> None:
    uid = message.from_user.id
    if not await db.get_parent(uid):
        if await central.get_pending(uid):
            await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
            return
        await message.answer(tr("Avval ro'yxatdan o'ting: /start"))
        return
    children = await all_children(uid)  # barcha kurslardagi farzandlar
    if not children:
        await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
        return
    q = normalize_text(message.text)
    scored = sorted(((name_score(q, c["name_norm"]), c) for c in children), key=lambda x: -x[0])
    matches = [c for score, c in scored if score >= 0.75]
    if len(matches) == 1:
        st = matches[0]
        await central.set_active(uid, st["course_key"])
        with use_course(st["course_key"]):
            await db.set_current_student(uid, st["id"])
            await message.answer(await student_card(st), reply_markup=child_card_kb(st["id"]))
    elif matches:
        await message.answer(tr("Bir nechta mos farzand topildi, tanlang:"), reply_markup=children_kb(matches, add=False))
    else:
        await message.answer(
            tr("Bu ism sizga bog'langan farzandlar orasida topilmadi.\n"
               "Quyidagilardan birini tanlang yoki yangi farzandni bog'lang:"),
            reply_markup=children_kb(children),
        )


@router.message(StateFilter(None), F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(tr("Noma'lum buyruq. Bosh menyu: /start, yordam: /yordam"))


@router.message(StateFilter(None), ~F.text, ~F.contact)
async def non_text(message: Message) -> None:
    """Rasm, fayl, ovozli xabar va h.k. — bot ularni qayta ishlamaydi, yo'l-yo'riq beradi."""
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Hujjat yuborish uchun PDF fayl yuboring, Excel uchun /import. Barcha buyruqlar: /admin")
        return
    if not await db.get_parent(message.from_user.id):
        await message.answer(tr("Avval ro'yxatdan o'ting: /start"))
        return
    await message.answer(tr("Bot faqat matnli xabarlar va menyu tugmalari bilan ishlaydi. Kurs koordinatoriga fayl yoki savol "
                            "yubormoqchi bo'lsangiz, «✉️ Kurs koordinatoriga savol» bo'limidan foydalaning yoki kurs koordinatori bilan "
                            "bevosita bog'laning."))
