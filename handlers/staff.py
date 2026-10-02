"""Kurs koordinatori menyusi (pastki tugmalar). Ota-ona menyusi kurs koordinatori va super-adminga ko'rsatilmaydi.

Har bir tugma mavjud buyruqni chaqiradi (tugma va buyruq bir xil natija beradi). Kurs koordinatori oddiy matn
yozsa — talaba qidiruvi (familiya, ism yoki HEMIS ID). Tugma bosilganda boshlangan boshqa amal bekor qilinadi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from handlers import admin as A
import deskauth
from config import WEBAPP_URL
from keyboards import (BTN_C_ANNOUNCE, BTN_C_DESK, BTN_C_DEBTS, BTN_C_DOC, BTN_C_HELP, BTN_C_IMPORT, BTN_C_LIMITS, BTN_C_PANEL,
                       BTN_C_REPORT, BTN_C_SEARCH, BTN_C_STAT, BTN_C_TEMPLATES, BTN_C_TERMS, COORD_BUTTONS,
                       SUPER_BUTTONS)
from tenancy import is_staff, is_super

router = Router(name="staff")
router.message.filter(lambda m: m.from_user is not None and is_staff(m.from_user.id))


class Find(StatesGroup):
    query = State()


def _cmd(name: str, args: str | None = None) -> CommandObject:
    return CommandObject(prefix="/", command=name, args=args)


@router.message(F.text == BTN_C_IMPORT)
async def b_import(message: Message, state: FSMContext) -> None:
    await A.cmd_import(message, state)


@router.message(F.text == BTN_C_TEMPLATES)
async def b_templates(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_templates(message)


@router.message(F.text == BTN_C_PANEL)
async def b_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_panel(message, _cmd("panel"))


@router.message(F.text == BTN_C_SEARCH)
async def b_search(message: Message, state: FSMContext) -> None:
    await state.set_state(Find.query)
    await message.answer("🔎 Talabaning familiyasi, ismi yoki HEMIS ID sini yozing.\n"
                         "Keyinchalik tugmasiz ham bo'ladi: familiyani shunchaki yozing.")


@router.message(Find.query, F.text, ~F.text.startswith("/"), ~F.text.in_(COORD_BUTTONS | SUPER_BUTTONS))
async def on_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_find_student(message, _cmd("talaba", message.text))


@router.message(F.text == BTN_C_STAT)
async def b_stat(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_stat(message)


@router.message(F.text == BTN_C_ANNOUNCE)
async def b_announce(message: Message, state: FSMContext) -> None:
    await A.cmd_broadcast(message, state)


@router.message(F.text == BTN_C_DOC)
async def b_doc(message: Message, state: FSMContext) -> None:
    await A.cmd_document(message, state)


@router.message(F.text == BTN_C_DEBTS)
async def b_debts(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_debtors(message, _cmd("qarzdorlar"))


@router.message(F.text == BTN_C_LIMITS)
async def b_limits(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_levels(message)


@router.message(F.text == BTN_C_REPORT)
async def b_report(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_report(message, _cmd("hisobot"))


@router.message(F.text == BTN_C_TERMS)
async def b_terms(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_terms(message)


@router.message(F.text == BTN_C_DESK)
@router.message(Command("kompyuter"))
async def b_desk(message: Message, state: FSMContext) -> None:
    """Kompyuter versiyasi: bir martalik kirish havolasi (10 daqiqa, bir marta) — tugma ichida."""
    await state.clear()
    if not WEBAPP_URL:
        await message.answer("💻 Kompyuter versiyasi ilova manzili (<code>WEBAPP_URL</code>) sozlangandan keyin "
                             "ishlaydi — README, «Telegram Web App» bo'limi.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="💻 Boshqaruv panelini ochish", url=deskauth.login_url(message.from_user.id))]])
    await message.answer(
        "💻 <b>Kompyuter versiyasi</b> — kurs boshqaruv paneli brauzerda: talabalar jadvali, xabarlar, "
        "so'rovlar, e'lon, fayl yuklash va hisobotlar" + (", barcha kurslar va koordinatorlar"
                                                           if is_super(message.from_user.id) else "") + ".\n\n"
        "Tugmani kompyuterda (Telegram Desktop yoki web.telegram.org) bosing — panel brauzerda ochiladi.\n"
        "🔒 Havola <b>10 daqiqa</b> amal qiladi va <b>bir marta</b> ishlatiladi — uni hech kimga yubormang. "
        "Kirgandan so'ng seans 12 soat davom etadi.", reply_markup=kb, disable_web_page_preview=True)


@router.message(F.text == BTN_C_HELP)
async def b_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await A.cmd_admin(message)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"), ~F.text.in_(COORD_BUTTONS | SUPER_BUTTONS))
async def free_text_search(message: Message) -> None:
    """Kurs koordinatori oddiy matn yozsa — talaba qidiruvi (ota-onaga mo'ljallangan javob emas)."""
    await A.cmd_find_student(message, _cmd("talaba", message.text))
