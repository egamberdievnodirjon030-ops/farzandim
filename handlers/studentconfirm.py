"""Talaba ota-onasini tasdiqlaydi: ota-ona yuborgan bir martalik havola (t.me/<bot>?start=t_<token>).

Talaba havolani ochadi → kim bog'lanmoqchi ekanini ko'radi → O'Z telefon raqamini Telegram tugmasi orqali yuboradi
(raqam bazadagi shu talabaning raqami bo'lishi shart — boshqa odam talaba nomidan tasdiqlay olmaydi) →
«✅ Ha, bu mening ota-onam» yoki «❌ Yo'q». «Ha» dan keyin so'rov kurs koordinatoriga boradi —
yakuniy tasdiqni u beradi (kim tasdiqlaganini ko'radi). Talaba ota-ona menyusiga kirmaydi, ota-ona sifatida ro'yxatga olinmaydi.
Bu router appgate va ota-ona routerlaridan oldin ulanadi; talaba avval bloklangan bo'lsa ham shu jarayon ishlaydi.
"""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import linking
from database import db
from i18n import tr
from tenancy import use_course
from utils import normalize_phone

router = Router(name="studentconfirm")
router.message.filter(F.chat.type == "private")


class SC(StatesGroup):
    contact = State()


class ScCb(CallbackData, prefix="sc"):
    k: str      # kurs
    r: int      # so'rov
    ok: int


def _phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=tr("📱 Raqamimni yuborish"), request_contact=True)]],
                               resize_keyboard=True, one_time_keyboard=True)


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(linking.START_PREFIX)))
async def open_link(message: Message, state: FSMContext) -> None:
    token = (message.text.split(maxsplit=1)[1] if " " in message.text else "")[len(linking.START_PREFIX):].strip()
    found = await linking.by_token(token) if token else None
    if not found:
        await state.clear()
        await message.answer(tr("Bu havola eskirgan yoki allaqachon ishlatilgan. Ota-onangizdan yangisini so'rang."),
                             reply_markup=ReplyKeyboardRemove())
        return
    key, r = found
    with use_course(None if key == "_" else key):
        st = await db.get_student(r["student_id"])
        parent = await db.get_parent(r["parent_id"]) or {}
    await state.set_state(SC.contact)
    await state.update_data(k=key, r=r["id"], token=token)
    await message.answer(
        tr("👨‍👩‍👧 <b>Ota-onani tasdiqlash</b>\n\n{who} ({phone}) o'zini <b>{student}</b> ning ota-onasi deb "
           "ko'rsatib, universitetning ota-onalar botiga ulanmoqchi. Ulansa, u sizning davomatingiz, baholaringiz va "
           "to'lovlaringizni ko'radi.\n\nAvval siz shu talaba ekaningizni tasdiqlang — pastdagi tugma bilan "
           "<b>o'z telefon raqamingizni</b> yuboring.",
           who=html.escape(parent.get("tg_name") or tr("Foydalanuvchi")), phone=linking.mask_phone(parent.get("phone")),
           student=html.escape(st["full_name"] if st else "—")),
        reply_markup=_phone_kb())


@router.message(SC.contact, F.contact)
async def on_student_contact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    c = message.contact
    if c.user_id != message.from_user.id:
        await message.answer(tr("Iltimos, o'zingizning raqamingizni pastdagi tugma orqali yuboring."), reply_markup=_phone_kb())
        return
    phone = normalize_phone(c.phone_number)
    key, rid = data["k"], data["r"]
    with use_course(None if key == "_" else key):
        r = await db.fetchone("SELECT * FROM link_requests WHERE id = ?", (rid,))
        if not r or r["status"] != "pending":
            await state.clear()
            await message.answer(tr("Bu so'rov allaqachon ko'rib chiqilgan."), reply_markup=ReplyKeyboardRemove())
            return
        allowed, _src = await linking.expected_phones(r)
        if not phone or phone not in allowed or message.from_user.id == r["parent_id"]:
            await state.clear()
            await message.answer(tr("Bu raqam shu talabaning raqami sifatida ko'rsatilmagan, shuning uchun tasdiqlab "
                                    "bo'lmaydi. So'rovni kurs koordinatori ko'rib chiqadi."),
                                 reply_markup=ReplyKeyboardRemove())
            return
        u = message.from_user
        await db.execute("UPDATE link_requests SET student_tg = ?, student_phone = ?, student_tg_name = ? WHERE id = ?",
                         (u.id, phone, " ".join(x for x in (u.full_name, f"@{u.username}" if u.username else "") if x), rid))
        parent = await db.get_parent(r["parent_id"]) or {}
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text=tr("✅ Ha, bu mening ota-onam"), callback_data=ScCb(k=key, r=rid, ok=1))
    kb.button(text=tr("❌ Yo'q, tanimayman"), callback_data=ScCb(k=key, r=rid, ok=0))
    kb.adjust(1)
    await message.answer(tr("Rahmat, siz tasdiqlandingiz.\n\n<b>{who}</b> ({phone}) — sizning ota-onangizmi?",
                            who=html.escape(parent.get("tg_name") or "—"), phone=linking.mask_phone(parent.get("phone"))),
                         reply_markup=ReplyKeyboardRemove())
    await message.answer(tr("Tanlang:"), reply_markup=kb.as_markup())


@router.message(SC.contact)
async def need_contact(message: Message) -> None:
    await message.answer(tr("Iltimos, pastdagi «📱 Raqamimni yuborish» tugmasini bosing."), reply_markup=_phone_kb())


@router.callback_query(ScCb.filter())
async def decide(cb: CallbackQuery, callback_data: ScCb) -> None:
    done, res = await linking.student_decide(cb.bot, callback_data.k, callback_data.r, cb.from_user.id, bool(callback_data.ok))
    if not done:
        await cb.answer(tr("Bu so'rov allaqachon ko'rib chiqilgan."), show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(tr("✅ Rahmat! Tasdig'ingiz kurs koordinatoriga yuborildi — u yakuniy tasdiqlagach, "
                                  "ota-onangiz ulanadi.") if res == "approved" else
                               tr("Rahmat. So'rov rad etildi, kurs koordinatoriga xabar berildi."))
