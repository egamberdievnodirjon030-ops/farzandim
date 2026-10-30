"""Tashriflar va tadbirlar — bot oqimlari (tashrif-py: talaba va koordinator oqimlari).

Ikki bot (botlar.py): talabaga tegishli hammasi — talabalar botida, koordinatorniki — asosiy (ota-onalar) botda.
STUDENT_BOT_TOKEN bo'sh bo'lsa, barcha routerlar bitta botda ishlaydi.

  router          — talaba: shaxsiy havola (t.me/<talabalar_boti>?start=v_<kurs>_<kod>), tashrif xabaridagi tugmalar
                    (✅ tasdiqlayman, 🕒 boshqa vaqt — «22.10 14:00», ❌ bu manzilda yashamayman), e'londagi
                    «✅ Ro'yxatdan o'tish» / «↩️ Ro'yxatdan chiqish».
  staff_router    — koordinator: talaba taklif qilgan vaqtni qabul qilish, javob bermaganlar bilan «shundayligicha
                    tasdiqlash», /yol — turgan joyidan (GPS) yaqin tashriflar manziliga qaysi avtobus yoki metro boradi.
  home_router     — faqat alohida talabalar botida: /start (hisob taniladi, kutilayotgan xabarlar keladi), telefon
                    raqami bilan ulanish, «📅 Tadbirlarim».
  redirect_router — faqat alohida bot bo'lsa, asosiy botda: eski talaba havolalari va tugmalari talabalar botiga
                    yo'naltiriladi.
Asosiy botda bu routerlar ota-ona routerlaridan oldin ulanadi; talaba bloklangan bo'lsa ham tashrif oqimi ochiq.
"""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)

import botlar
import visits as V
from database import db
from tenancy import is_staff, use_course
from utils import normalize_phone

router = Router(name="visits")
router.message.filter(F.chat.type == "private")
staff_router = Router(name="visits_staff")
staff_router.message.filter(F.chat.type == "private")
home_router = Router(name="student_home")
home_router.message.filter(F.chat.type == "private")
redirect_router = Router(name="student_redirect")
redirect_router.message.filter(F.chat.type == "private")

STUDENT_ACTS = r"^tv:(ok|time|no|reg|unreg):"
MY_EVENTS = "📅 Tadbirlarim"


class TV(StatesGroup):
    time = State()      # talaba qulay vaqtni yozadi
    reason = State()    # talaba «bu manzilda yashamayman» sababini yozadi
    loc = State()       # koordinator turgan joyini yuboradi (/yol)


def _course(key: str):
    return use_course(None if key == "_" else key)


def _parse(data: str) -> tuple[str, str, int, int] | None:
    try:
        _, action, key, pid, sid = data.split(":")
        return action, key, int(pid), int(sid)
    except ValueError:
        return None


def _menu_kb() -> ReplyKeyboardMarkup | None:
    """Alohida talabalar botida — doimiy «📅 Tadbirlarim» tugmasi."""
    if not botlar.separate():
        return None
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=MY_EVENTS)]], resize_keyboard=True)


async def _greet(message: Message, found: list[tuple[str, dict]]) -> None:
    """Talaba tanildi: kim ekani, bot nima qilishi va kutilayotgan xabarlar (barcha kurslardan)."""
    names = ", ".join(f"<b>{html.escape(st['full_name'])}</b>" + (f" ({html.escape(st['group_name'])})"
                                                                    if st.get("group_name") else "") for _, st in found)
    await message.answer(f"✅ {names}, siz {'talabalar botiga' if botlar.separate() else 'botga'} ulandingiz.\n\n"
                         "Shu yerga keladi:\n"
                         "• kurs koordinatori ijara xonadoningizga tashrif rejalashtirsa — tasdiqlaysiz yoki qulay vaqt "
                         "taklif qilasiz;\n• tadbir va madaniy tashriflar e'lonlari — «Ro'yxatdan o'tish» tugmasi bilan;\n"
                         "• siz ishtirokchi bo'lgan tadbirlar haqida ma'lumot va eslatmalar.\n\n"
                         f"Yaqin tadbirlaringiz — «{MY_EVENTS}».", reply_markup=_menu_kb() or ReplyKeyboardRemove())
    for key, st in found:
        with _course(key):
            await V.catch_up(message.bot, st["id"])


# ---------------------------------------------------------------- talaba: shaxsiy havola
@router.message(CommandStart(deep_link=True, magic=F.args.startswith(V.START_PREFIX)))
async def open_invite(message: Message, state: FSMContext) -> None:
    arg = (message.text.split(maxsplit=1)[1] if " " in message.text else "")[len(V.START_PREFIX):].strip()
    key, _, code = arg.rpartition("_")
    st = None
    if key and (key == "_" or key in db.keys()):
        with _course(key):
            u = message.from_user
            st = await V.bind_by_code(code, u.id, " ".join(x for x in (u.full_name, f"@{u.username}" if u.username else "") if x))
    await state.clear()
    if not st:
        await message.answer("Bu havola eskirgan yoki noto'g'ri. Kurs koordinatoringizdan yangisini so'rang.",
                             reply_markup=ReplyKeyboardRemove())
        return
    await _greet(message, [(key, st)])


async def _student_ok(cb: CallbackQuery, sid: int) -> bool:
    acc = await db.fetchone("SELECT tg_id FROM student_accounts WHERE student_id = ?", (sid,))
    return bool(acc and acc["tg_id"] == cb.from_user.id)


# ---------------------------------------------------------------- talaba: tashrif va e'lon tugmalari
@router.callback_query(F.data.regexp(STUDENT_ACTS))
async def on_student_button(cb: CallbackQuery, state: FSMContext) -> None:
    got = _parse(cb.data)
    if not got:
        await cb.answer()
        return
    action, key, pid, sid = got
    if key != "_" and key not in db.keys():
        await cb.answer("Bu xabar eskirgan.", show_alert=True)
        return
    if action in ("reg", "unreg"):
        await _registration(cb, action, key, pid, sid)
        return
    with _course(key):
        if not await _student_ok(cb, sid):
            await cb.answer("Bu tugma boshqa talaba uchun.", show_alert=True)
            return
        p = await V.get(pid, full=False)
        if not p or p["status"] != V.TALABA:
            await cb.answer("Bu tashrif bo'yicha javob berish yopilgan.", show_alert=True)
            await _drop_kb(cb)
            return
        try:
            if action == "ok":
                await V.answer(cb.bot, pid, sid, V.TASDIQLADI)
                await cb.answer("✅ Tasdiqlandi")
                await _edit(cb, "<b>✅ Tasdiqlandi</b>\n\n" + html.escape(p["when"]) + "\n\nRahmat. Belgilangan vaqtda "
                                "uyda bo'lishingizni so'raymiz; o'zgarish bo'lsa, xabar beramiz.")
                return
        except V.VisitError as e:
            await cb.answer(e.message[:190], show_alert=True)
            await _drop_kb(cb)
            return
    await state.set_state(TV.time if action == "time" else TV.reason)
    await state.update_data(k=key, p=pid, s=sid)
    await cb.answer()
    await cb.message.answer(
        "Sizga qulay sanani va vaqtni yozing.\n\nMasalan: <code>22.10 14:00</code> yoki <code>ertaga 16:30</code>\n"
        "Faqat vaqtni yozsangiz, sana o'zgarishsiz qoladi: <code>16:30</code>\n\nBekor qilish: /bekor"
        if action == "time" else
        "Iltimos, sababini qisqacha yozing (masalan: manzilim o'zgargan, yotoqxonaga ko'chdim).\n\nBekor qilish: /bekor")


async def _registration(cb: CallbackQuery, action: str, key: str, pid: int, sid: int) -> None:
    """E'londagi «Ro'yxatdan o'tish» / «Ro'yxatdan chiqish» — xabar joriy holatga keltiriladi."""
    with _course(key):
        if not await _student_ok(cb, sid):
            await cb.answer("Bu tugma boshqa talaba uchun.", show_alert=True)
            return
        try:
            p = await (V.register if action == "reg" else V.unregister)(cb.bot, pid, sid)
            await cb.answer("✅ Ro'yxatdan o'tdingiz" if action == "reg" else "Ro'yxatdan chiqdingiz")
        except V.VisitError as e:
            await cb.answer(e.message[:190], show_alert=True)
            p = await V.get(pid, full=False)
        if not p:
            await _drop_kb(cb)
            return
        text, kb = await V.elon_message(p, sid)
    try:
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:  # noqa: BLE001  (o'zgarmagan yoki juda eski xabar)
        pass


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


@router.message(Command("bekor"), StateFilter(TV.time, TV.reason))
async def cancel_input(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=_menu_kb() or ReplyKeyboardRemove())


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


# ---------------------------------------------------------------- koordinator: taklif va «shundayligicha tasdiqlash»
@staff_router.callback_query(F.data.regexp(r"^tv:(acc|force):"))
async def on_staff_button(cb: CallbackQuery) -> None:
    got = _parse(cb.data)
    if not got:
        await cb.answer()
        return
    action, key, pid, sid = got
    if key != "_" and key not in db.keys():
        await cb.answer("Bu xabar eskirgan.", show_alert=True)
        return
    uid = cb.from_user.id
    with _course(key):
        try:
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
        except V.VisitError as e:
            await cb.answer(e.message[:190], show_alert=True)
            await _drop_kb(cb)


# ---------------------------------------------------------------- /yol — turgan joydan yo'l (faqat koordinator)
def _loc_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Turgan joyimni yuborish", request_location=True)],
                                         [KeyboardButton(text="Joylashuvsiz ko'rsatish")]],
                               resize_keyboard=True, one_time_keyboard=True)


@staff_router.message(Command("yol"))
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


@staff_router.message(TV.loc, F.location)
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


@staff_router.message(TV.loc, F.text == "Joylashuvsiz ko'rsatish")
async def on_no_location(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Manzillar yaqinidagi bekatlar:", reply_markup=ReplyKeyboardRemove())
    for p in await V.upcoming_for_route(message.from_user.id):
        await V.send_route(message.bot, message.from_user.id, p, [s for s in p["students"] if s["response"] != V.RAD_ETDI])


@staff_router.message(TV.loc)
async def on_loc_other(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi. Qayta urinish: /yol", reply_markup=ReplyKeyboardRemove())


# ---------------------------------------------------------------- talabalar boti: /start, telefon, «Tadbirlarim»
def _phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)]],
                               resize_keyboard=True, one_time_keyboard=True)


@home_router.message(CommandStart())
async def student_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    found = await V.student_opened(message.from_user.id)
    if found:
        await _greet(message, found)
        return
    await message.answer("🎓 <b>JIDU talabalar boti</b>\n\nBu yerga ijara xonadoningizga tashrif so'rovlari, tadbir va "
                         "madaniy tashriflar e'lonlari («Ro'yxatdan o'tish» tugmasi bilan) va eslatmalar keladi.\n\n"
                         "Ulanish uchun pastdagi tugma bilan <b>o'z telefon raqamingizni</b> yuboring — u universitet "
                         "bazasidagi raqamingiz bilan solishtiriladi. Raqamingiz bazada bo'lmasa, kurs koordinatoringizdan "
                         "shaxsiy havola so'rang.", reply_markup=_phone_kb())


@home_router.message(StateFilter(None), F.contact)
async def student_phone(message: Message) -> None:
    c = message.contact
    if c.user_id != message.from_user.id:
        await message.answer("Iltimos, o'zingizning raqamingizni pastdagi tugma orqali yuboring.", reply_markup=_phone_kb())
        return
    phone = normalize_phone(c.phone_number)
    u = message.from_user
    found = await V.bind_by_phone(phone, u.id, " ".join(x for x in (u.full_name, f"@{u.username}" if u.username else "") if x)) \
        if phone else []
    if not found:
        await message.answer("Bu raqam talabalar ro'yxatida topilmadi (yoki bir nechta talabada bor). Kurs koordinatoringizdan "
                             "shaxsiy havola so'rang — uni ochsangiz, darhol ulanasiz.", reply_markup=ReplyKeyboardRemove())
        return
    await _greet(message, found)


@home_router.message(Command("tadbirlar"))
@home_router.message(F.text == MY_EVENTS)
async def my_events(message: Message) -> None:
    found = await V.student_opened(message.from_user.id)
    if not found:
        await message.answer("Avval botga ulaning: /start", reply_markup=_phone_kb())
        return
    lines, opened = [], []
    for key, st in found:
        with _course(key):
            a = await V.student_agenda(st["id"])
            for p in a["mine"]:
                extra = " — <i>javobingiz kutilmoqda</i>" if p["status"] == V.TALABA and p["response"] in (V.KUTILMOQDA, V.VAQT_TAKLIF) else ""
                lines.append(f"• <b>{html.escape(p['when'])}</b> — {html.escape(V.TURLAR.get(p['type'], ''))}: "
                             f"{html.escape(p['title'])}" + (f" ({html.escape(p['place'])})" if p.get("place") else "") + extra)
            for p in a["open"]:
                text, kb = await V.elon_message(p, st["id"])
                opened.append((key, p["id"], st["id"], text, kb))
    await message.answer("<b>📅 Yaqin tashrif va tadbirlaringiz</b>\n\n" + ("\n".join(lines) if lines else "Hozircha yo'q.")
                         + (f"\n\nRo'yxatdan o'tish mumkin bo'lgan e'lonlar: {len(opened)} ta — quyida." if opened else ""),
                         reply_markup=_menu_kb())
    for key, pid, sid, text, kb in opened:
        msg = await message.answer(text, reply_markup=kb, disable_web_page_preview=True)
        with _course(key):
            await V.remember_announce(pid, sid, msg)


@home_router.message()
async def student_other(message: Message) -> None:
    await message.answer(f"Bu bot xabarlar uchun: tashrif so'rovlari, tadbir e'lonlari va eslatmalar shu yerga keladi.\n\n"
                         f"Yaqin tadbirlaringiz — «{MY_EVENTS}» yoki /tadbirlar.", reply_markup=_menu_kb())


# ---------------------------------------------------------------- asosiy botda: talabalar botiga yo'naltirish
@redirect_router.message(CommandStart(deep_link=True, magic=F.args.regexp(r"^(v_|t_)")))
async def to_student_bot(message: Message) -> None:
    me = await botlar.student_bot(message.bot).me()
    payload = message.text.split(maxsplit=1)[1].strip()
    await message.answer("🎓 Talabalar uchun alohida bot bor — bu havola o'sha botda ochiladi. Pastdagi tugmani bosing.",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                             text=f"@{me.username} da ochish", url=f"https://t.me/{me.username}?start={payload}")]]))


@redirect_router.callback_query(F.data.regexp(STUDENT_ACTS + "|^sc:"))
async def old_student_button(cb: CallbackQuery) -> None:
    me = await botlar.student_bot(cb.bot).me()
    await cb.answer(f"Bu tugma endi talabalar botida ishlaydi: @{me.username}. Botni oching — so'rovlar o'sha yerga keladi.",
                    show_alert=True)
