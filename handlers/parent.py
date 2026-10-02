"""Ota-ona bo'limlari: farzandlar, davomat, jadval, baholar, e'lonlar, sozlamalar, kurs koordinatoriga savol."""
from __future__ import annotations

from datetime import timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message

from config import MAX_OPEN_QUESTIONS
import absence
from database import db
import loc
import chat
import trends
from family import all_children, parent_courses
from tenancy import central, course_admins, use_course
from i18n import N_, tr
from keyboards import (BTN_ASK, BTN_ATTENDANCE, BTN_CHILDREN, BTN_GRADES, BTN_INFO, BTN_NEWS, BTN_SCHEDULE, BTN_SETTINGS, MENU_TEXTS, btn, AttCb, ChildCb, DocGetCb, SchCb, SetCb, add_child_kb, attendance_kb, back_kb, child_card_kb, children_kb, documents_kb, finance_kb, main_menu, schedule_kb, settings_kb)
from reports import (absences_report, announcements_text, day_report, document_caption, documents_report,
                     academic_report, finance_menu, grades_report, hemis_report, updated_note, payment_report, period_report, schedule_report, student_card, student_header,
                     subjects_report)
from utils import esc, fmt_phone, parse_user_dates, semester_start, split_message, today, week_bounds

router = Router(name="parent")
router.message.filter(F.chat.type == "private")  # guruhlarda faqat handlers/groups.py ishlaydi

DEFAULT_INFO = N_(
    "ℹ️ <b>Foydali ma'lumot</b>\n\n"
    "Bu bot orqali farzandingizning darslarga qatnashishi, dars jadvali va baholarini kuzatib borishingiz mumkin. "
    "Ma'lumotlar universitetning HEMIS tizimidan kurs koordinatori tomonidan muntazam yuklab boriladi, shuning uchun "
    "eng so'nggi darslar bir necha soat kechikib ko'rinishi mumkin.\n\n"
    "<b>Belgilar:</b> ✅ qatnashdi, ❌ sababsiz qoldirdi, 🟡 sababli qoldirdi, ⏰ kechikdi, "
    "⚪ ma'lumot hali kiritilmagan, 📘 rejadagi dars.\n\n"
    "<b>Qidiruv:</b> farzandingizning ism yoki familiyasini yozib yuborsangiz, bot uning sahifasini ochadi "
    "(lotin va kirill yozuvi ham qabul qilinadi).\n\n"
    "Savollaringiz bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limidan yozing."
)


class AskQ(StatesGroup):
    text = State()


class DatePick(StatesGroup):
    waiting = State()


# ---------------------------------------------------------------- yordamchilar
async def _parent_or_warn(message: Message, user_id: int) -> dict | None:
    parent = await db.get_parent(user_id)
    if not parent:
        if await central.get_pending(user_id):  # raqam tasdiqlangan, farzand hali hech qaysi kursda topilmagan
            await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
            return None
        await message.answer(tr("Avval ro'yxatdan o'ting: /start"))
    return parent


async def send_parts(message: Message, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    parts = split_message(text)
    for i, part in enumerate(parts):
        await message.answer(part, reply_markup=kb if i == len(parts) - 1 else None)


async def show(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None) -> None:
    """Callback javobini shu xabarni tahrirlab ko'rsatadi; uzun bo'lsa yangi xabarlar bilan."""
    parts = split_message(text)
    if len(parts) == 1:
        try:
            await cb.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "not modified" not in str(e):
                await cb.message.answer(text, reply_markup=kb)
    else:
        await send_parts(cb.message, text, kb)
    await cb.answer()


async def render(act: str, st: dict) -> tuple[str, InlineKeyboardMarkup]:
    if act == "att":
        since = semester_start().isoformat()
        has_daily = (await db.attendance_totals(st["id"], since, today().isoformat()))["total"]
        has_hemis = await db.latest_att_stats(st["id"], since)
        if has_hemis and not has_daily:  # faqat HEMIS jami ko'rsatkichlari bor
            return await hemis_report(st) + await updated_note("att"), back_kb(st["id"], "card")
        return (f"{student_header(st)}\n\n" + tr("📊 <b>Davomat</b> — davrni tanlang:"),
                attendance_kb(st["id"], hemis=bool(has_hemis)))
    if act == "sch":
        hint = tr("📅 <b>Dars jadvali</b> — kunni tanlang:")
        if today().weekday() == 6:
            hint += "\n" + tr("Bugun yakshanba — kelasi hafta jadvali.")
        return f"{student_header(st)}\n\n" + hint, schedule_kb(st["id"])
    if act == "gr":
        return await grades_report(st) + await updated_note("gr"), back_kb(st["id"], "card")
    if act in ("fin", "pay"):
        return await finance_menu(st), finance_kb(st["id"])
    if act in ("fk", "ft"):
        return await payment_report(st, "kontrakt" if act == "fk" else "trimestr"), back_kb(st["id"], "fin")
    if act == "acad":
        return await academic_report(st), back_kb(st["id"], "card")
    if act == "doc":
        docs = await db.documents_for(st["id"])
        return documents_report(st, docs), documents_kb(st["id"], docs)
    return await student_card(st), child_card_kb(st["id"])


async def open_for_message(message: Message, user_id: int, act: str, state: FSMContext) -> None:
    """Menyu tugmasi bosilganda: bitta farzand bo'lsa darhol ochadi, bir nechta bo'lsa tanlatadi."""
    parent = await _parent_or_warn(message, user_id)
    if not parent:
        return
    children = await all_children(user_id)
    if not children:
        await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
        return
    if len(children) == 1:
        st = children[0]
        with use_course(st["course_key"]):
            await db.set_current_student(user_id, st["id"])
            if act == "ask":
                await start_ask(message, state, st)
                return
            text, kb = await render(act, st)
        await send_parts(message, text, kb)
        return
    await message.answer(tr("Qaysi farzandingiz bo'yicha?"), reply_markup=children_kb(children, act, add=False))


async def start_ask(message: Message, state: FSMContext, st: dict) -> None:
    if not course_admins():
        await message.answer(tr("Hozircha kurs koordinatori bog'lanmagan. Keyinroq urinib ko'ring."))
        return
    await state.set_state(AskQ.text)
    await state.update_data(sid=st["id"])
    await message.answer(
        tr("✉️ <b>{name}</b> bo'yicha savolingizni bitta xabarda yozing. "
           "Kurs koordinatori javobi shu yerga keladi.\n\nBekor qilish: /bekor", name=esc(loc.student_name(st)))
    )


# ---------------------------------------------------------------- menyu tugmalari (istalgan holatda ishlaydi)
@router.message(F.text.in_(btn(BTN_CHILDREN)), StateFilter("*"))
async def menu_children(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _parent_or_warn(message, message.from_user.id):
        return
    children = await all_children(message.from_user.id)
    if not children:
        await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
        return
    if len(children) == 1:  # bitta farzand — sahifasi darhol ochiladi
        st = children[0]
        with use_course(st["course_key"]):
            await message.answer(await student_card(st), reply_markup=child_card_kb(st["id"]))
        return
    await message.answer(tr("👨‍🎓 Farzandingizni tanlang:"), reply_markup=children_kb(children))


@router.message(F.text.in_(btn(BTN_ATTENDANCE)), StateFilter("*"))
async def menu_attendance(message: Message, state: FSMContext) -> None:
    await state.clear()
    await open_for_message(message, message.from_user.id, "att", state)


@router.message(F.text.in_(btn(BTN_SCHEDULE)), StateFilter("*"))
async def menu_schedule(message: Message, state: FSMContext) -> None:
    await state.clear()
    await open_for_message(message, message.from_user.id, "sch", state)


@router.message(F.text.in_(btn(BTN_GRADES)), StateFilter("*"))
async def menu_grades(message: Message, state: FSMContext) -> None:
    await state.clear()
    await open_for_message(message, message.from_user.id, "gr", state)


@router.message(F.text.in_(btn(BTN_ASK)), StateFilter("*"))
async def menu_ask(message: Message, state: FSMContext) -> None:
    await state.clear()
    await open_for_message(message, message.from_user.id, "ask", state)


@router.message(F.text.in_(btn(BTN_NEWS)), StateFilter("*"))
async def menu_news(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await _parent_or_warn(message, message.from_user.id):
        return
    items = []  # e'lonlar farzandlarning barcha kurslaridan
    for key in await parent_courses(message.from_user.id):
        with use_course(key):
            keys = {c["group_key"] for c in await db.parent_children(message.from_user.id) if c.get("group_key")}
            items += await db.announcements_for(keys, 10)
    items.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    await send_parts(message, announcements_text(items[:10]))


@router.message(F.text.in_(btn(BTN_SETTINGS)), StateFilter("*"))
async def menu_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    parent = await _parent_or_warn(message, message.from_user.id)
    if not parent:
        return
    await message.answer(
        tr("⚙️ <b>Bildirishnomalar</b>\n\nQaysi xabarlarni olishni xohlaysiz? Tugmani bosib yoqing yoki o'chiring."),
        reply_markup=settings_kb(parent),
    )


@router.message(F.text.in_(btn(BTN_INFO)), StateFilter("*"))
async def menu_info(message: Message, state: FSMContext) -> None:
    await state.clear()
    custom = await db.get_setting("info_text")
    text = loc.pick(custom) if custom else tr(DEFAULT_INFO)  # kurs koordinatori matni — ota-ona tilidagi qism
    by_tutor: dict[tuple[str, str], list[str]] = {}
    for c in await all_children(message.from_user.id):
        course_db = db.for_course(c["course_key"])  # talaba faylida bo'lmasa — /koordinator bilan kiritilgani
        name, phone = await course_db.coordinator_contact(c, c["course_key"])
        if name or phone:
            key = (name or "", phone or "")
            shown = loc.student_name(c).split()  # farzandning ismi (ota-ona tilida)
            by_tutor.setdefault(key, []).append(shown[1] if len(shown) > 1 else " ".join(shown))
    tutors = [f"• {esc(loc.person(name))} {fmt_phone(phone)}".rstrip() + f" — {esc(', '.join(kids))}"
              for (name, phone), kids in by_tutor.items()]
    text += "\n\n" + absence.rules_text()
    if tutors:
        text += "\n\n" + tr("🧑‍🏫 <b>Kurs koordinatorlari</b>") + "\n" + "\n".join(tutors)
    await send_parts(message, text)


# ---------------------------------------------------------------- farzand bo'limlari (inline)
@router.callback_query(ChildCb.filter())
async def cb_child(cb: CallbackQuery, callback_data: ChildCb, state: FSMContext) -> None:
    st = await db.linked_student(cb.from_user.id, callback_data.sid)
    if not st:
        await cb.answer(tr("Bu ma'lumot sizga bog'lanmagan."), show_alert=True)
        return
    await db.set_current_student(cb.from_user.id, st["id"])
    if callback_data.act == "ask":
        await cb.answer()
        await start_ask(cb.message, state, st)
        return
    if callback_data.act == "dyn":  # dinamika: taqqoslash matni va grafik
        text, png = await trends.report(st)
        await show(cb, text + await updated_note("att"), back_kb(st["id"], "card"))
        if png:
            await cb.message.answer_photo(BufferedInputFile(png, "dinamika.png"),
                                          caption=tr("📈 {name}: davomat va baholar dinamikasi", name=esc(loc.student_name(st))))
        return
    text, kb = await render(callback_data.act, st)
    await show(cb, text, kb)


@router.callback_query(DocGetCb.filter())
async def cb_get_document(cb: CallbackQuery, callback_data: DocGetCb) -> None:
    doc = await db.get_document(callback_data.did)
    st = await db.linked_student(cb.from_user.id, doc["student_id"]) if doc else None
    if not doc or not st or doc["revoked"]:
        await cb.answer(tr("Hujjat topilmadi yoki u sizga tegishli emas."), show_alert=True)
        return
    await cb.answer()
    await cb.message.answer_document(doc["file_id"], caption=document_caption(doc, st))


@router.callback_query(AttCb.filter())
async def cb_attendance(cb: CallbackQuery, callback_data: AttCb, state: FSMContext) -> None:
    st = await db.linked_student(cb.from_user.id, callback_data.sid)
    if not st:
        await cb.answer(tr("Bu ma'lumot sizga bog'lanmagan."), show_alert=True)
        return
    t, p = today(), callback_data.p
    if p == "cust":
        await state.set_state(DatePick.waiting)
        await state.update_data(sid=st["id"])
        await cb.answer()
        await cb.message.answer(
            tr("🗓 Sanani <b>KK.OO.YYYY</b> ko'rinishida yozing, masalan <code>15.09.2026</code>.\n"
               "Oraliq uchun ikki sana: <code>01.09.2026 - 20.09.2026</code>\n\nBekor qilish: /bekor")
        )
        return
    if p == "d0":
        text = await day_report(st, t)
    elif p == "d1":
        text = await day_report(st, t - timedelta(days=1))
    elif p == "w0":
        text = await period_report(st, week_bounds(t)[0], t, tr("Shu hafta"))
    elif p == "w1":
        mon, sun = week_bounds(t - timedelta(days=7))
        text = await period_report(st, mon, sun, tr("O'tgan hafta"))
    elif p == "m0":
        text = await period_report(st, t.replace(day=1), t, tr("Shu oy"))
    elif p == "sem":
        text = await period_report(st, min(semester_start(), t), t, tr("Semestr boshidan"))
    elif p == "subj":
        text = await subjects_report(st)
    elif p == "hemis":
        text = await hemis_report(st)
    else:  # abs
        text = await absences_report(st)
    await show(cb, text + await updated_note("att"), back_kb(st["id"], "att"))


@router.message(DatePick.waiting, F.text, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def custom_date(message: Message, state: FSMContext) -> None:
    dates = parse_user_dates(message.text)
    if not dates:
        await message.answer(tr("Sana tushunilmadi. Masalan: <code>15.09.2026</code> yoki <code>01.09.2026 - 20.09.2026</code>"))
        return
    d1, d2 = min(dates[:2]), max(dates[:2])
    if (d2 - d1).days > 200:
        await message.answer(tr("Oraliq juda katta. Iltimos, 200 kundan oshmaydigan davrni kiriting."))
        return
    data = await state.get_data()
    await state.clear()
    st = await db.linked_student(message.from_user.id, data.get("sid", 0))
    if not st:
        await message.answer(tr("Farzand topilmadi. Qaytadan tanlang: «👨‍🎓 Farzandim»."))
        return
    text = await day_report(st, d1) if d1 == d2 else await period_report(st, d1, d2, tr("Tanlangan davr"))
    await send_parts(message, text + await updated_note("att"), back_kb(st["id"], "att"))


@router.callback_query(SchCb.filter())
async def cb_schedule(cb: CallbackQuery, callback_data: SchCb) -> None:
    st = await db.linked_student(cb.from_user.id, callback_data.sid)
    if not st:
        await cb.answer(tr("Bu ma'lumot sizga bog'lanmagan."), show_alert=True)
        return
    t, p = today(), callback_data.p
    if p.startswith("wd"):  # hafta kuni: shu haftaning (yakshanba kuni — kelasi haftaning) o'sha kuni
        monday = week_bounds(t)[0] + timedelta(days=7 if t.weekday() == 6 else 0)
        i = min(max(int(p[2:] or 0), 0), 5)
        d = monday + timedelta(days=i)
        await show(cb, await schedule_report(st, d, d) + await updated_note("sch"), schedule_kb(st["id"], selected=i))
        return
    if p == "d0":  # oldingi versiya tugmalari (chatdagi eski xabarlar) ham ishlaydi
        d1 = d2 = t
    elif p == "d1":
        d1 = d2 = t + timedelta(days=1)
    elif p == "w0":
        d1, d2 = week_bounds(t)
    else:
        d1, d2 = week_bounds(t + timedelta(days=7))
    await show(cb, await schedule_report(st, d1, d2) + await updated_note("sch"), back_kb(st["id"], "sch"))


# ---------------------------------------------------------------- sozlamalar
@router.callback_query(SetCb.filter())
async def cb_settings(cb: CallbackQuery, callback_data: SetCb) -> None:
    parent = await db.get_parent(cb.from_user.id)
    if not parent:
        await cb.answer(tr("Avval /start orqali ro'yxatdan o'ting."), show_alert=True)
        return
    new_value = not bool(parent.get(callback_data.key))
    for key in await parent_courses(cb.from_user.id):  # sozlama ota-onaning barcha kurslarida bir xil
        with use_course(key):
            await db.set_parent_flag(cb.from_user.id, callback_data.key, new_value)
    parent[callback_data.key] = int(new_value)
    try:
        await cb.message.edit_reply_markup(reply_markup=settings_kb(parent))
    except TelegramBadRequest:
        pass
    await cb.answer(tr("Yoqildi ✅") if new_value else tr("O'chirildi"))


# ---------------------------------------------------------------- kurs koordinatoriga savol
@router.message(AskQ.text, F.text, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def ask_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    st = await db.linked_student(message.from_user.id, data.get("sid", 0))
    await state.clear()
    if not st:
        await message.answer(tr("Farzand topilmadi. Qaytadan urinib ko'ring."), reply_markup=main_menu())
        return
    if await db.open_questions_count(message.from_user.id) >= MAX_OPEN_QUESTIONS:
        await message.answer(tr("Sizda javob kutilayotgan savollar ko'p. Iltimos, avvalgilariga javobni kuting."))
        return
    res = await chat.parent_send(message.bot, message.from_user.id, message.from_user.full_name, st, message.text)
    if not res["ok"]:
        await message.answer(tr("Sizda javob kutilayotgan savollar ko'p. Iltimos, avvalgilariga javobni kuting."))
    elif res["delivered"]:
        await message.answer(tr("✅ Savolingiz kurs koordinatoriga yuborildi. Javob shu yerga keladi."), reply_markup=main_menu())
    else:
        await message.answer(tr("Savol saqlandi, lekin hozir kurs koordinatoriga yetkazib bo'lmadi. Keyinroq ko'rib chiqiladi."),
                             reply_markup=main_menu())


@router.message(AskQ.text, ~F.text)
async def ask_not_text(message: Message) -> None:
    await message.answer(tr("Iltimos, savolingizni matn ko'rinishida yozing. Bekor qilish: /bekor"))
