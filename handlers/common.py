"""Ro'yxatdan o'tish: /start, telefon raqamni tasdiqlash, farzandni qo'lda bog'lash, /bekor, /yordam."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, User

from config import MAX_PENDING_REQUESTS, UNIVERSITY_NAME
from database import db
import appmode
import loc
from family import all_children, ensure_parent_here, known_contact, parent_courses
from tenancy import (central, course_of_admin, course_title, is_coordinator, is_staff, is_super,
                     use_course)
from guard import REJECT_TEXT, block_user, find_evidence
from i18n import N_, set_lang, tr
from keyboards import (ADD_CHILD_CB, BTN_LANG, MENU_TEXTS, LangCb, add_child_kb, btn, child_card_kb, children_kb,
                       contact_kb, coordinator_menu, lang_kb, main_menu, super_menu)
from reports import student_card
from utils import esc, fmt_date, fmt_phone, name_score, normalize_phone, normalize_text, parse_user_dates

router = Router(name="common")
router.message.filter(F.chat.type == "private")  # guruhlarda faqat handlers/groups.py ishlaydi


class Reg(StatesGroup):
    contact = State()
    child_name = State()
    child_verify = State()


LANG_PROMPT = "🌐 Tilni tanlang · Выберите язык · Choose language"

WELCOME = N_(
    "Assalomu alaykum! 👋\n\n<b>{uni}</b> ota-onalar botiga xush kelibsiz.\n\n"
    "Bu yerda farzandingiz qaysi kunlarda, qaysi fanlardan darsga qatnashgani yoki qoldirganini, "
    "dars jadvali va baholarini ko'rishingiz, kurs koordinatoriga savol yuborishingiz mumkin.\n\n"
    "🔐 Farzandingiz ma'lumotlari faqat sizga ko'rinishi uchun avval telefon raqamingizni tasdiqlang — "
    "pastdagi tugmani bosing.\n\n"
    "ℹ️ Bot faqat ota-onalar uchun: talabalar ro'yxatdan o'ta olmaydi."
)

HELP = N_(
    "ℹ️ <b>Botdan foydalanish</b>\n\n"
    "• Farzandingiz <b>ism yoki familiyasini</b> yozib yuboring — bot uning sahifasini ochadi.\n"
    "• «📊 Davomat» — bugun, hafta, oy, semestr, fanlar kesimida yoki tanlangan sana bo'yicha.\n"
    "• «📅 Dars jadvali» — bugungi, ertangi va haftalik darslar.\n"
    "• «📝 Baholar» — joriy, oraliq va yakuniy nazorat natijalari.\n"
    "• «⚙️ Bildirishnomalar» — dars qoldirilganda darhol xabar, kunlik xulosa va ogohlantirishlar.\n"
    "• «✉️ Kurs koordinatoriga savol» — savolingiz kurs koordinatoriga yetkaziladi, javob shu yerga keladi.\n"
    "• «📄 Hujjatlar» (farzand sahifasida) — kurs koordinatori yuborgan tushuntirish xatlari, dekan ogohlantirishlari "
    "va hayfsanlar (PDF). Yangi hujjat yuborilganda u sizga darhol keladi.\n\n"
    "/start — bosh menyu, /bekor — joriy amalni bekor qilish"
)


# ---------------------------------------------------------------- start / til / bekor / yordam
@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if appmode.APP_MODE:  # ilova rejimi: bot — faqat ilovaga o'tish (til ilovada tanlanadi)
        await _start_app(message, message.from_user)
        return
    if await central.get_lang(message.from_user.id) is None and not is_staff(message.from_user.id):  # birinchi marta — avval til
        # (kurs koordinatori va super-admin interfeysi o'zbek tilida — til so'ralmaydi)
        await message.answer(LANG_PROMPT, reply_markup=lang_kb())
        return
    await _start(message, state, message.from_user)


async def _start_app(message: Message, user: User) -> None:
    """Ilova rejimidagi /start: menyu tugmalari olib tashlanadi, o'rniga ilovani ochish tugmasi."""
    uid = user.id
    if is_staff(uid):  # super-adminning tanlagan kursi saqlanadi (ilova va kompyuter versiyasi shu kurs bilan ochiladi)
        role = ("super-admin" if is_super(uid) else f"«{esc(course_title(course_of_admin(uid)))}» kurs koordinatori")
        await message.answer(f"Assalomu alaykum, {esc(user.first_name or '')}! 👋\nSiz — {role}.\n\n"
                             "Barcha ish ilovada: talabalar, xabarlar, so'rovlar, e'lon, hujjatlar, ma'lumot yuklash va "
                             "hisobotlar. Kompyuterda ishlash uchun — «💻 Kompyuter versiyasi».",
                             reply_markup=ReplyKeyboardRemove())
        await message.answer("👇", reply_markup=appmode.staff_kb(uid, "/staff"))
        return
    if await central.get_lang(uid) is None:  # tilni Telegram sozlamasidan olamiz (ilovada o'zgartiriladi)
        code = (user.language_code or "").lower()
        set_lang("ru" if code.startswith("ru") else "en" if code.startswith("en") else "uz")
        await central.set_lang(uid, "ru" if code.startswith("ru") else "en" if code.startswith("en") else "uz")
    for key in await parent_courses(uid):
        with use_course(key):
            p = await db.get_parent(uid)
            if p and not p["active"]:
                await db.set_parent_active(uid, True)
    text = tr("Assalomu alaykum! Farzandingizning davomati, baholari, to'lovlari va hujjatlari — ilovada. "
              "Bildirishnomalar shu chatga keladi.")
    if not await all_children(uid) and not await central.get_pending(uid):
        text += "\n\n" + tr("Ro'yxatdan o'tish uchun ilovani oching — telefon raqamingiz Telegram orqali tasdiqlanadi.")
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await message.answer(tr("Barcha ma'lumotlar va amallar — ilovada 👇"),
                         reply_markup=appmode.app_kb("/", tr("📱 Ilovani ochish")))


async def _start(message: Message, state: FSMContext, user: User) -> None:
    # Kurs koordinatori va super-admin — o'z menyusi (ota-ona menyusi va ro'yxatdan o'tish ularga ko'rsatilmaydi)
    if is_super(user.id):
        from handlers.superadmin import home_text
        await state.clear()
        await central.set_active(user.id, "")
        await message.answer(await home_text(), reply_markup=super_menu())
        return
    if is_coordinator(user.id):
        await state.clear()
        title = course_title(course_of_admin(user.id))
        await message.answer(f"Assalomu alaykum, {esc(user.first_name or '')}! 👋\n\n<b>«{esc(title)}»</b> kurs "
                             "koordinatori menyusi 👇\nTalabani topish uchun familiyasini shunchaki yozing. "
                             "Barcha buyruqlar: «ℹ️ Barcha buyruqlar».", reply_markup=coordinator_menu(title))
        return
    parent = await db.get_parent(user.id)
    if not parent:
        if await central.get_pending(user.id):  # raqam tasdiqlangan, farzand hali topilmagan
            await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())
            return
        await state.set_state(Reg.contact)
        await message.answer(tr(WELCOME, uni=esc(loc.term(UNIVERSITY_NAME))), reply_markup=contact_kb())
        return
    for key in await parent_courses(user.id):
        with use_course(key):
            if not (await db.get_parent(user.id))["active"]:
                await db.set_parent_active(user.id, True)
    children = await all_children(user.id)
    await message.answer(
        tr("Assalomu alaykum, {name}! Bosh menyu 👇\nFarzandingiz ism-familiyasini yozib yuborsangiz ham bo'ladi.",
           name=esc(user.first_name)),
        reply_markup=main_menu(),
    )
    if children:
        await message.answer(tr("👨‍🎓 Farzandim:") if len(children) == 1 else tr("👨‍🎓 Farzandingizni tanlang:"),
                             reply_markup=children_kb(children))
    else:
        await message.answer(tr("Sizga hali farzand bog'lanmagan."), reply_markup=add_child_kb())


@router.message(Command("til", "lang", "language", "yazyk"), StateFilter("*"))
@router.message(F.text.in_(btn(BTN_LANG)))
async def cmd_lang(message: Message) -> None:
    await message.answer(LANG_PROMPT, reply_markup=lang_kb())


@router.callback_query(LangCb.filter())
async def cb_lang(cb: CallbackQuery, callback_data: LangCb, state: FSMContext) -> None:
    await central.set_lang(cb.from_user.id, callback_data.l)
    set_lang(callback_data.l)
    await cb.answer()
    await cb.message.edit_text(tr("✅ Til tanlandi: O'zbekcha"))
    if await db.get_parent(cb.from_user.id):
        await cb.message.answer(tr("Bosh menyu 👇"), reply_markup=main_menu())
    else:
        await _start(cb.message, state, cb.from_user)


@router.message(Command("bekor"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    parent = await db.get_parent(message.from_user.id)
    await message.answer(tr("Bekor qilindi."), reply_markup=main_menu() if parent else contact_kb())


@router.message(Command("nizomlar", "nizom", "regulations"), StateFilter("*"))
async def cmd_regulations(message: Message, state: FSMContext) -> None:
    """Universitet ichki nizomlari: PDF — fayl sifatida, havola — tugma; ilova sozlangan bo'lsa — ilovada ochish."""
    import regulations
    from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
    from keyboards import webapp_kb
    await state.clear()
    items = await regulations.all_items()
    if not items:
        await message.answer(tr("📜 Universitet ichki nizomlari hali joylanmagan."))
        return
    links = [r for r in items if r["url"] and not r["file"]]
    kb = webapp_kb("/regulations", tr("📱 Ilovada ochish"))
    rows = [[InlineKeyboardButton(text=loc.pick(r["title"])[:60], url=r["url"])] for r in links[:20]]
    if kb:
        rows = kb.inline_keyboard + rows
    await message.answer(tr("📜 <b>Universitet ichki nizomlari</b>") + "\n\n"
                         + "\n".join(f"• {esc(loc.pick(r['title']))}" for r in items),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)
    for r in items:
        data = regulations.read_pdf(r)
        if data:
            await message.answer_document(BufferedInputFile(data, f"nizom-{r['id']}.pdf"),
                                          caption=esc(loc.pick(r["title"]))[:1000])


@router.message(Command("yordam", "help"), StateFilter("*"))
async def cmd_help(message: Message) -> None:
    await message.answer(tr(HELP))


# ---------------------------------------------------------------- telefon raqam
@router.message(F.contact)
async def on_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact.user_id != message.from_user.id:
        await message.answer(tr("Iltimos, o'zingizning raqamingizni pastdagi tugma orqali yuboring."),
                             reply_markup=contact_kb())
        return
    phone = normalize_phone(contact.phone_number)
    if not phone:
        await message.answer(tr("Telefon raqamni o'qib bo'lmadi. Qaytadan urinib ko'ring."), reply_markup=contact_kb())
        return
    uid = message.from_user.id
    user = message.from_user
    # Talaba emasligini tekshirish — BARCHA kurslar bo'yicha: raqam biror kursning talabalar bazasida yoki
    # foydalanuvchi talabalar guruhida bo'lsa — rad (xabar o'sha kurs koordinatoriga boradi)
    for key in db.keys():
        with use_course(key):
            ev = await find_evidence(message.bot, uid, phone, user.full_name, user.username)
            if ev:
                await state.clear()
                await block_user(message.bot, uid, phone, user.full_name, user.username, ev,
                                 "Ro'yxatdan o'tishga urinish (telefon raqam yuborildi)")
                await message.answer(tr(REJECT_TEXT), reply_markup=ReplyKeyboardRemove())
                return
    # Farzand(lar) qaysi kurs bazasida bo'lsa — ota-ona o'sha kurs(lar)da ro'yxatga olinadi
    for key in db.keys():
        with use_course(key):
            students = await db.students_by_phone(phone)
            if students or await db.get_parent(uid):
                await db.upsert_parent(uid, phone, message.from_user.full_name)
                for st in students:
                    await db.link_parent(uid, st["id"], "phone")
    children = await all_children(uid)
    await state.clear()
    if appmode.APP_MODE:  # ilova rejimi: qisqa javob, qolgani ilovada
        if children:
            await central.clear_pending(uid)
            text = tr("✅ Raqamingiz tasdiqlandi ({phone}). Farzandingiz ma'lumotlari — ilovada.", phone=fmt_phone(phone))
        else:
            await central.set_pending(uid, phone, message.from_user.full_name)
            text = tr("Raqamingiz ({phone}) universitet bazasida topilmadi. Ilovada farzandingiz ma'lumotlarini "
                      "kiriting — kurs koordinatori tasdiqlaydi.", phone=fmt_phone(phone))
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await message.answer(tr("Barcha ma'lumotlar va amallar — ilovada 👇"),
                             reply_markup=appmode.app_kb("/", tr("📱 Ilovani ochish")))
        return
    if children:
        await central.clear_pending(uid)
        names = "\n".join(f"• {esc(loc.student_name(c))} ({esc(c.get('group_name') or '—')})" for c in children)
        await message.answer(
            tr("✅ Raqamingiz tasdiqlandi ({phone}).\n\nSizga bog'langan farzand(lar):\n{names}\n\n"
               "Endi menyudan bo'lim tanlang yoki farzandingiz ism-familiyasini yozib yuboring.",
               phone=fmt_phone(phone), names=names),
            reply_markup=main_menu(),
        )
        if len(children) == 1:
            with use_course(children[0]["course_key"]):
                await db.set_current_student(uid, children[0]["id"])
                await message.answer(await student_card(children[0]), reply_markup=child_card_kb(children[0]["id"]))
        else:
            await message.answer(tr("Farzandni tanlang:"), reply_markup=children_kb(children))
        return
    await central.set_pending(uid, phone, message.from_user.full_name)  # hech qaysi kursga yozilmaydi
    await message.answer(
        tr("Raqamingiz ({phone}) universitet bazasida farzandingizga biriktirilmagan ekan.\n"
           "Uni qo'lda bog'lash mumkin: ma'lumotlarni tekshirib, kurs koordinatori tasdiqlaydi.", phone=fmt_phone(phone)),
        reply_markup=main_menu(),
    )
    await start_manual_link(message, state)


# ---------------------------------------------------------------- farzandni qo'lda bog'lash
async def start_manual_link(message: Message, state: FSMContext) -> None:
    await state.set_state(Reg.child_name)
    await state.update_data(attempts=0)
    await message.answer(tr(
        "✍️ Farzandingizning <b>familiyasi va ismini</b> to'liq yozing.\n"
        "Masalan: <i>Aliyev Vali</i>\n\nBekor qilish: /bekor"
    ))


@router.callback_query(F.data == ADD_CHILD_CB)
async def cb_add_child(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    if not await known_contact(cb.from_user.id):
        await state.set_state(Reg.contact)
        await cb.message.answer(tr("Avval telefon raqamingizni tasdiqlang."), reply_markup=contact_kb())
        return
    await start_manual_link(cb.message, state)


@router.message(Reg.child_name, F.text, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def manual_name(message: Message, state: FSMContext) -> None:
    q = normalize_text(message.text)
    if len(q.split()) < 2:
        await message.answer(tr("Iltimos, familiya va ismni birga yozing (kamida ikki so'z)."))
        return
    await state.update_data(query=q)
    await state.set_state(Reg.child_verify)
    await message.answer(tr(
        "Endi tasdiqlash uchun farzandingizning <b>tug'ilgan sanasini</b> (masalan <code>05.03.2007</code>) "
        "yoki <b>talaba ID raqamini</b> (HEMIS) yozing."
    ))


@router.message(Reg.child_verify, F.text, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def manual_verify(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    uid = message.from_user.id
    raw = message.text.strip()
    dates = parse_user_dates(raw)
    candidates = []  # barcha kurslardan; so'rov topilgan farzandning kursiga boradi
    for key in db.keys():
        with use_course(key):
            candidates += [{**s, "course_key": key} for s in await db.all_students_brief()
                           if name_score(data["query"], s["name_norm"]) >= 0.85]
    if dates:
        if candidates and not any(s["birth_date"] for s in candidates):
            # HEMIS eksportida tug'ilgan sanalar yashirilgan bo'lsa — urinish sanalmaydi, ID so'raladi
            await message.answer(tr(
                "Bu talabaning tug'ilgan sanasi universitet bazasida yo'q, shuning uchun sana bo'yicha tekshirib "
                "bo'lmaydi. Iltimos, farzandingizning <b>talaba ID raqamini</b> (HEMIS ID — 12 xonali raqam) yozing. "
                "Uni farzandingizdan so'rashingiz mumkin."
            ))
            return
        match = [s for s in candidates if s["birth_date"] == dates[0].isoformat()]
    else:
        key = normalize_text(raw).replace(" ", "")
        match = [s for s in candidates if normalize_text(s["hemis_id"]).replace(" ", "") == key]

    if len(match) != 1:
        attempts = data.get("attempts", 0) + 1
        if attempts >= 3:
            await state.clear()
            await message.answer(tr(
                "Kiritilgan ma'lumotlar bazadagi yozuv bilan mos kelmadi. Iltimos, kurs koordinatori bilan bevosita "
                "bog'laning — u raqamingizni farzandingizga biriktirib qo'yadi."),
                reply_markup=main_menu(),
            )
            return
        await state.update_data(attempts=attempts)
        await state.set_state(Reg.child_name)
        await message.answer(
            tr("Ma'lumotlar mos kelmadi ({n}/3). Familiya va ismni hujjatdagidek qaytadan yozing:", n=attempts)
        )
        return

    st = match[0]
    await state.clear()
    with use_course(st["course_key"]):
        await _create_link_request(message, uid, st, raw)


async def _create_link_request(message: Message, uid: int, st: dict, raw: str) -> None:
    """Joriy kurs (farzandning kursi) bazasida so'rov yaratadi va faqat shu kurs koordinatorlariga yuboradi."""
    if await db.linked_student(uid, st["id"]):
        await message.answer(tr("Bu farzand sizga allaqachon bog'langan."), reply_markup=main_menu())
        return
    if await db.has_pending_request(uid, st["id"]):
        await message.answer(tr("Bu farzand bo'yicha so'rovingiz kurs koordinatorida ko'rib chiqilmoqda."),
                             reply_markup=main_menu())
        return
    if await db.pending_requests_count(uid) >= MAX_PENDING_REQUESTS:
        await message.answer(tr("Sizda ko'rib chiqilmagan so'rovlar ko'p. Iltimos, javobni kuting."),
                             reply_markup=main_menu())
        return
    contact = await known_contact(uid)
    if not contact:
        await message.answer(tr("Avval telefon raqamingizni tasdiqlang."), reply_markup=contact_kb())
        return
    await ensure_parent_here(uid, contact["phone"], message.from_user.full_name, contact["source"])
    await central.clear_pending(uid)
    parent = await db.get_parent(uid)
    rid = await db.create_link_request(uid, st["id"], raw)
    full = await db.get_student(st["id"])
    admin_text = (
        f"🔗 <b>Farzandni bog'lash so'rovi #{rid}</b>\n\n"
        f"👤 Ota-ona: {esc(message.from_user.full_name)}, {fmt_phone(parent['phone'])}\n"
        f"👨‍🎓 Talaba: {esc(full['full_name'])} · {esc(full.get('group_name') or '')} · ID {esc(full['hemis_id'])}\n"
        f"Tasdiqlash uchun kiritilgan: {esc(raw)}\n"
        + (f"Bazadagi tug'ilgan sana: {fmt_date(full['birth_date'], False)}\n" if full.get("birth_date") else "")
        + "\nOta-ona bilan telefon orqali bog'lanib tekshirish tavsiya etiladi."
    )
    from staffops import notify_link_request
    await notify_link_request(message.bot, rid, message.from_user.full_name, full, admin_text)
    await message.answer(
        tr("✅ So'rovingiz kurs koordinatoriga yuborildi. Tasdiqlangach, sizga shu yerda xabar keladi."),
        reply_markup=main_menu(),
    )


@router.message(Reg.contact)
async def need_contact(message: Message) -> None:
    await message.answer(tr("Iltimos, pastdagi «📱 Telefon raqamni yuborish» tugmasini bosing."), reply_markup=contact_kb())
