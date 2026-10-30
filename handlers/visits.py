"""Tashriflar — bot oqimlari (tashrif-py: talaba va koordinator oqimlari).

  • Talaba shaxsiy havolani ochadi (t.me/<bot>?start=v_<kurs>_<kod>) — Telegram hisobi bog'lanadi, javob kutayotgan
    tashriflar darhol keladi. Ota-onasini o'z raqami bilan tasdiqlagan talaba ham avtomatik taniladi.
  • Tashrif xabaridagi tugmalar: ✅ tasdiqlayman, 🕒 boshqa vaqt (yoziladi: «22.10 14:00»), ❌ bu manzilda yashamayman.
  • Tadbir va madaniy tashrif ishtirokchilariga — faqat ma'lumot va eslatma (tugmasiz, visits.py).
  • Barcha talabalar tasdiqlagach, reja o'zi aktual bo'ladi. Koordinator: talaba taklif qilgan vaqtni qabul qiladi,
    javob bermaganlar bo'lsa — rejani shundayligicha tasdiqlaydi; /yol — turgan joyidan (GPS) yaqin tashriflar
    manziliga qaysi avtobus yoki metro boradi (joylashuv saqlanmaydi).
Bu router ota-ona routerlaridan oldin ulanadi; talaba bloklangan bo'lsa ham tashrif oqimi ochiq.
"""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

import visits as V
from database import db
from tenancy import is_staff, use_course

router = Router(name="visits")
router.message.filter(F.chat.type == "private")


class TV(StatesGroup):
    time = State()      # talaba qulay vaqtni yozadi
    reason = State()    # talaba «bu manzilda yashamayman» sababini yozadi
    loc = State()       # koordinator turgan joyini yuboradi (/yol)


def _course(key: str):
    return use_course(None if key == "_" else key)


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(V.START_PREFIX)))
async def open_invite(message: Message, state: FSMContext) -> None:
    arg = (message.text.split(maxsplit=1)[1] if " " in message.text else "")[len(V.START_PREFIX):].strip()
    key, _, code = arg.rpartition("_")
    st = None
    if key and (key == "_" or key in db.keys()):
        with _course(key):
            u = message.from_user
            st = await V.bind_by_code(code, u.id, " ".join(x for x in (u.full_name, f"@{u.username}" if u.username else "") if x))
            pending = [await V.get(p["id"], full=False) for p in await V.open_for_student(st["id"])] if st else []
    await state.clear()
    if not st:
        await message.answer("Bu havola eskirgan yoki noto'g'ri. Kurs koordinatoringizdan yangisini so'rang.",
                             reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(f"✅ <b>{html.escape(st['full_name'])}</b>, siz botga ulandingiz.\n\nKurs koordinatoringiz ijara "
                         "xonadoningizga tashrif rejalashtirsa, xabar shu yerga keladi — tasdiqlaysiz yoki o'zingizga qulay "
                         "vaqtni taklif qilasiz. Sizni tadbir yoki madaniy tashrifga belgilasa — nomi, joyi va vaqti, "
                         "oldidan esa eslatma keladi.", reply_markup=ReplyKeyboardRemove())
    with _course(key):
        for p in pending:
            row = next((s for s in p["students"] if s["student_id"] == st["id"]), {})
            msg = await message.answer(V.student_text(p, row), reply_markup=V.student_kb(p["id"], st["id"]))
            await V._remember(p["id"], "talaba", msg, st["id"])
        await V.catch_up(message.bot, st["id"])  # belgilangan, hali o'tmagan tadbirlar


async def _student_ok(cb: CallbackQuery, sid: int) -> bool:
    acc = await db.fetchone("SELECT tg_id FROM student_accounts WHERE student_id = ?", (sid,))
    return bool(acc and acc["tg_id"] == cb.from_user.id)


@router.callback_query(F.data.startswith("tv:"))
async def on_button(cb: CallbackQuery, state: FSMContext) -> None:
    try:
        _, action, key, pid, sid = cb.data.split(":")
        pid, sid = int(pid), int(sid)
    except ValueError:
        await cb.answer()
        return
    if key != "_" and key not in db.keys():
        await cb.answer("Bu xabar eskirgan.", show_alert=True)
        return
    uid = cb.from_user.id
    with _course(key):
        try:
            if action in ("ok", "time", "no"):
                if not await _student_ok(cb, sid):
                    await cb.answer("Bu tugma boshqa talaba uchun.", show_alert=True)
                    return
                p = await V.get(pid, full=False)
                if not p or p["status"] != V.TALABA:
                    await cb.answer("Bu tashrif bo'yicha javob berish yopilgan.", show_alert=True)
                    await _drop_kb(cb)
                    return
                if action == "ok":
                    await V.answer(cb.bot, pid, sid, V.TASDIQLADI)
                    await cb.answer("✅ Tasdiqlandi")
                    await _edit(cb, "<b>✅ Tasdiqlandi</b>\n\n" + html.escape(p["when"]) + "\n\nRahmat. Belgilangan vaqtda "
                                    "uyda bo'lishingizni so'raymiz; o'zgarish bo'lsa, xabar beramiz.")
                    return
                await state.set_state(TV.time if action == "time" else TV.reason)
                await state.update_data(k=key, p=pid, s=sid)
                await cb.answer()
                await cb.message.answer(
                    "Sizga qulay sanani va vaqtni yozing.\n\nMasalan: <code>22.10 14:00</code> yoki <code>ertaga 16:30</code>\n"
                    "Faqat vaqtni yozsangiz, sana o'zgarishsiz qoladi: <code>16:30</code>\n\nBekor qilish: /bekor"
                    if action == "time" else
                    "Iltimos, sababini qisqacha yozing (masalan: manzilim o'zgargan, yotoqxonaga ko'chdim).\n\nBekor qilish: /bekor")
                return
            if action in ("acc", "force"):
                p = await V.get(pid, full=False)
                if not p or not V.can_manage(p, uid):
                    await cb.answer("Bu reja boshqa koordinatorniki.", show_alert=True)
                    return
                if action == "acc":
                    p = await V.accept_proposal(cb.bot, pid, sid, uid)
                    await cb.answer("Vaqt o'zgartirildi")
                    await _edit(cb, f"<b>✅ Taklif qabul qilindi</b>\n\n{html.escape(p['title'])}\nYangi vaqt: "
                                    f"<b>{html.escape(p['when'])}</b>\n\nTalabalarga so'rov qaytadan yuborildi.")
                else:
                    p = await V.confirm(cb.bot, pid, uid, force=True)
                    await cb.answer("Tasdiqlandi")
                    await _edit(cb, f"<b>✅ Reja tasdiqlandi (aktual)</b>\n\n{html.escape(p['title'])}\n"
                                    f"{html.escape(p['when'])}\n\nJavob bermagan talabalar «javob bermadi» deb belgilandi.")
                return
        except V.VisitError as e:
            await cb.answer(e.message[:190], show_alert=True)
            await _drop_kb(cb)
            return
    await cb.answer()


async def _edit(cb: CallbackQuery, text: str) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=None)
    except Exception:  # noqa: BLE001  (xabar juda eski — yangisi yuboriladi)
        await cb.message.answer(text)


async def _drop_kb(cb: CallbackQuery) -> None:
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("bekor"), StateFilter(TV))
async def cancel_input(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())


@router.message(TV.time, F.text)
async def on_time(message: Message, state: FSMContext) -> None:
    d = await state.get_data()
    with _course(d["k"]):
        p = await V.get(d["p"], full=False)
        got = V.parse_proposal(message.text, p["visit_date"]) if p else None
        if not got:
            await message.answer("Vaqtni tushunolmadim. Iltimos, <code>22.10 14:00</code> yoki <code>14:00</code> "
                                 "ko'rinishida yozing. Bekor qilish: /bekor")
            return
        try:
            await V.answer(message.bot, d["p"], d["s"], V.VAQT_TAKLIF, got[0], got[1])
        except V.VisitError as e:
            await state.clear()
            await message.answer(html.escape(e.message))
            return
    await state.clear()
    await message.answer(f"<b>🕐 Taklifingiz yuborildi</b>\n\nSiz taklif qilgan vaqt: <b>"
                         f"{html.escape(V.when({'visit_date': got[0], 'start_time': ''}))}{', ' + got[1] if got[1] else ''}"
                         "</b>\n\nKurs koordinatori ko'rib chiqadi va javob beradi.")


@router.message(TV.reason, F.text)
async def on_reason(message: Message, state: FSMContext) -> None:
    d = await state.get_data()
    with _course(d["k"]):
        try:
            await V.answer(message.bot, d["p"], d["s"], V.RAD_ETDI, comment=message.text)
        except V.VisitError as e:
            await state.clear()
            await message.answer(html.escape(e.message))
            return
    await state.clear()
    await message.answer("<b>Qayd etildi</b>\n\nKurs koordinatoriga xabar berildi. U siz bilan bog'lanadi.")


# ---------------------------------------------------------------- /yol — turgan joydan yo'l (faqat koordinator)
def _loc_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Turgan joyimni yuborish", request_location=True)],
                                         [KeyboardButton(text="Joylashuvsiz ko'rsatish")]],
                               resize_keyboard=True, one_time_keyboard=True)


@router.message(Command("yol"))
async def cmd_route(message: Message, state: FSMContext) -> None:
    if not is_staff(message.from_user.id):
        return
    if not V._geo_on():
        await message.answer("Yo'l ma'lumoti o'chirilgan (.env: YOL_MALUMOTI=yoq).")
        return
    if not await V.upcoming_for_route(message.from_user.id):
        await message.answer("Bugun va ertaga sizning ijara tashrifingiz yo'q. Rejalar — boshqaruv paneli → «Tashriflar».")
        return
    await state.set_state(TV.loc)
    await message.answer("🧭 Turgan joyingizdan tashrif manziliga qaysi avtobus yoki metro borishini aytaman.\n\n"
                         "GPS ni yoqing va pastdagi tugmani bosing. Joylashuvingiz saqlanmaydi.", reply_markup=_loc_kb())


@router.message(TV.loc, F.location)
async def on_location(message: Message, state: FSMContext) -> None:
    await state.clear()
    here = (message.location.latitude, message.location.longitude)
    await message.answer("Joylashuvingiz qabul qilindi.", reply_markup=ReplyKeyboardRemove())
    sent = 0
    for p in await V.upcoming_for_route(message.from_user.id):
        sent += await V.send_route(message.bot, message.from_user.id, p,
                                   [s for s in p["students"] if s["response"] != V.RAD_ETDI], here)
    if not sent:
        await message.answer("Manzillarning joyi hali aniqlanmagan — birozdan keyin qayta urinib ko'ring.")


@router.message(TV.loc, F.text == "Joylashuvsiz ko'rsatish")
async def on_no_location(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Manzillar yaqinidagi bekatlar:", reply_markup=ReplyKeyboardRemove())
    for p in await V.upcoming_for_route(message.from_user.id):
        await V.send_route(message.bot, message.from_user.id, p, [s for s in p["students"] if s["response"] != V.RAD_ETDI])


@router.message(TV.loc)
async def on_loc_other(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi. Qayta urinish: /yol", reply_markup=ReplyKeyboardRemove())
