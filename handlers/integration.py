"""Super-admin: universitet tizimi («Manage») bilan integratsiya holati, tekshirish va maydonlarni moslash.

/integratsiya — holat (oxirgi olish, yozuvlar, xatolar) va tugmalar: hozir yangilash, ulanishni tekshirish,
to'xtatish/yoqish. /integratsiya_moslash davomat sana=lesson_date — maydon noto'g'ri tanilsa qo'lda ko'rsatish.
/manage_kalit — Manage'dagi curl buyrug'ini (Authorization: Basic …) yuborish: kalit va manzil shundan olinadi,
xabar darhol o'chiriladi, ulanish sinab ko'riladi.
"""
from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import integration as I
from tenancy import is_super
from utils import esc, split_message

router = Router(name="integration")
router.message.filter(lambda m: m.from_user is not None and is_super(m.from_user.id))
router.callback_query.filter(lambda c: is_super(c.from_user.id))


class IntCb(CallbackData, prefix="integ"):
    action: str


class KeyIn(StatesGroup):
    curl = State()


KIND_ARG = {"fanlar": "subjects", "fan": "subjects", "jadval": "schedule", "davomat": "attendance"}
KEY_HELP = ("🔑 <b>Manage kalitini kiritish</b>\n\n"
            "Manage'dagi so'rovni <b>curl</b> ko'rinishida to'liq nusxalab, shu yerga bitta xabar qilib yuboring — "
            "<code>Authorization: Basic …</code> qatori bilan birga, masalan:\n\n"
            "<code>curl -X 'GET' 'https://my.uwed.uz/api/integration/v1/student-subjects?hemisId=…&amp;academicYearId=8' "
            "-H 'accept: */*' -H 'Accept-Language: uz' -H 'Authorization: Basic …'</code>\n\n"
            "Bot manzil, kalit va sarlavhalarni o'zi ajratadi, xabaringizni <b>darhol o'chiradi</b> (kalit chatda qolmaydi) "
            "va ulanishni sinab ko'radi. Fanlar, dars jadvali yoki davomat — har biri uchun o'z curl'ini yuborish mumkin.\n"
            "Bekor qilish: /bekor")


async def _apply_curl(message: Message, text: str, kind: str | None) -> None:
    try:
        await message.delete()  # kalit chatda qolmasin
        deleted = True
    except Exception:  # noqa: BLE001
        deleted = False
    try:
        info = I.save_curl(text, kind, message.from_user.id if message.from_user else None)
    except ValueError as e:
        await message.answer(f"❌ {esc(e)}\n\nQaytadan: /manage_kalit")
        return
    kind = info["kind"]
    owner = I.key_owner()
    lines = [f"🔑 Kalit saqlandi{f' ({esc(owner)})' if owner else ''}."
             + (" Xabaringiz xavfsizlik uchun o'chirildi." if deleted else
                " ⚠️ Xabaringizni o'chira olmadim — uni o'zingiz o'chiring (ichida kalit bor)."),
             f"Ma'lumot: <b>{esc(I.TITLES[kind])}</b>",
             f"Manzil: <code>{esc(info['url'])}/{esc(info['path'])}</code>"]
    if info.get("headers"):
        lines.append(f"Sarlavhalar: <code>{esc(info['headers'])}</code>")
    try:
        records, finfo = await I.fetch(kind, max_pages=1)
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n❌ Sinov so'rovi: {esc(I._err_text(e))}")
    else:
        lines.append(f"\n✅ Manage javob berdi: {len(records)} ta yozuv. Ma'lumotlar olinmoqda — natija: /integratsiya")
        asyncio.create_task(I.pull(message.bot, kind))
    await _send(message, "\n".join(lines))


async def _kb():
    b = InlineKeyboardBuilder()
    if I.configured():
        b.button(text="🔄 Hozir yangilash", callback_data=IntCb(action="sync"))
        b.button(text="🔍 Tekshirish", callback_data=IntCb(action="probe"))
    if I.configured() or I.INTEGRATION_WEBHOOK_SECRET:
        if await I.paused():
            b.button(text="▶️ Yoqish", callback_data=IntCb(action="resume"))
        else:
            b.button(text="⏸ To'xtatish", callback_data=IntCb(action="pause"))
    b.button(text="🔑 Kalitni kiritish (curl)", callback_data=IntCb(action="key"))
    b.button(text="♻️ Holatni yangilash", callback_data=IntCb(action="status"))
    b.adjust(2, 2, 1)
    return b.as_markup()


async def _send(message: Message, text: str, kb=None) -> None:
    parts = split_message(text)
    for i, p in enumerate(parts):
        await message.answer(p, reply_markup=kb if i == len(parts) - 1 else None, disable_web_page_preview=True)


@router.message(Command("integratsiya", "integration", "manage"))
async def cmd_status(message: Message) -> None:
    await _send(message, await I.status_text(), await _kb())


@router.message(Command("manage_kalit", "kalit", "integratsiya_kalit"))
async def cmd_key(message: Message, command: CommandObject, state: FSMContext) -> None:
    """/manage_kalit [fanlar|jadval|davomat] [curl …] | /manage_kalit tozalash"""
    args = (command.args or "").strip()
    if args.lower() in ("tozalash", "ochirish", "o'chirish", "reset"):
        I.clear_conf()
        await message.answer("Bot orqali kiritilgan kalit o'chirildi — endi .env dagi sozlamalar ishlatiladi.")
        return
    first = args.split(maxsplit=1)[0].lower() if args else ""
    kind = KIND_ARG.get(first)
    if kind:
        args = args[len(first):].strip()
    if args.lower().startswith("curl"):
        await _apply_curl(message, args, kind)
        return
    await state.set_state(KeyIn.curl)
    await state.update_data(kind=kind)
    await message.answer(KEY_HELP, disable_web_page_preview=True)


@router.message(KeyIn.curl, Command("bekor", "cancel"))
async def key_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(KeyIn.curl, F.text)
async def key_text(message: Message, state: FSMContext) -> None:
    kind = (await state.get_data()).get("kind")
    await state.clear()
    if not message.text.strip().lower().startswith("curl"):
        try:
            await message.delete()
        except Exception:  # noqa: BLE001
            pass
        await message.answer("Bu curl buyrug'i emas — «curl» bilan boshlanadigan to'liq buyruqni yuboring: /manage_kalit")
        return
    await _apply_curl(message, message.text, kind)


@router.message(F.text.regexp(r"(?is)^\s*curl\s.*authorization\s*:"))
async def key_pasted(message: Message) -> None:
    """curl buyrug'i buyruqsiz yuborilsa ham — kalit sifatida qabul qilinadi."""
    await _apply_curl(message, message.text, None)


@router.callback_query(IntCb.filter())
async def on_action(cb: CallbackQuery, callback_data: IntCb, state: FSMContext) -> None:
    a = callback_data.action
    if a == "key":
        await state.set_state(KeyIn.curl)
        await state.update_data(kind=None)
        await cb.answer()
        await cb.message.answer(KEY_HELP, disable_web_page_preview=True)
        return
    if a == "pause":
        await I.set_paused(True)
        await cb.answer("To'xtatildi")
    elif a == "resume":
        await I.set_paused(False)
        await cb.answer("Yoqildi")
    elif a == "probe":
        await cb.answer("Tekshirilmoqda…")
        for kind in I.KINDS:
            if I.configured(kind):
                await _send(cb.message, await I.probe(kind))
        return
    elif a == "sync":
        await cb.answer("Olinmoqda…")
        lines = []
        for kind in I.KINDS:
            if not I.configured(kind):
                continue
            res = await I.pull(cb.bot, kind)
            if res.get("error"):
                lines.append(f"❌ {I.TITLES[kind]}: {esc(res['error'][:300])}")
            else:
                ch = sum(1 for c in res["courses"].values() if c["changed"])
                lines.append(f"✅ {I.TITLES[kind]}: {res['records']} yozuv, "
                             + (f"{ch} kursda yangilandi" if ch else "o'zgarish yo'q"))
                for c in res["courses"].values():
                    if c.get("report"):
                        lines.append(c["report"])
        await _send(cb.message, "\n\n".join(lines) or "Sozlangan manba yo'q.")
        return
    else:
        await cb.answer()
    await _send(cb.message, await I.status_text(), await _kb())


@router.message(Command("integratsiya_moslash"))
async def cmd_map(message: Message, command: CommandObject) -> None:
    """/integratsiya_moslash davomat sana=lesson_date juftlik=lesson_pair.code | davomat tozalash"""
    args = (command.args or "").split()
    kind = I.KIND_WORDS.get(args[0].lower()) if args else None
    if not kind:
        cur = I.overrides()
        lines = ["Maydonni qo'lda moslash:\n<code>/integratsiya_moslash davomat sana=lesson_date</code>\n"
                 "<code>/integratsiya_moslash jadval xona=auditorium.name</code>\n"
                 "<code>/integratsiya_moslash davomat holat=-</code> — maydonni ishlatmaslik\n"
                 "<code>/integratsiya_moslash davomat tozalash</code> — hammasi avtomatik\n\n"
                 "Maydonlar: " + ", ".join(sorted(set(I.FIELD_NAMES.values()))) + "\n"
                 "API dagi nomlarni «🔍 Tekshirish» ko'rsatadi (ichma-ich: <code>student.full_name</code>)."]
        for k, m in cur.items():
            if m:
                lines.append(f"\n{I.TITLES.get(k, k)}: " + ", ".join(f"{I.FIELD_NAMES.get(f, f)}={esc(v)}" for f, v in m.items()))
        await message.answer("\n".join(lines))
        return
    if len(args) > 1 and args[1].lower() in ("tozalash", "reset", "clear"):
        I.clear_overrides(kind)
        await message.answer(f"{I.TITLES[kind]}: qo'lda moslashlar o'chirildi — maydonlar avtomatik taniladi.")
        return
    done, bad = [], []
    for pair in args[1:]:
        if "=" not in pair:
            bad.append(pair)
            continue
        word, key = pair.split("=", 1)
        fld = I.parse_field(word)
        if not fld or not key:
            bad.append(pair)
            continue
        I.set_override(kind, fld, key)
        done.append(f"{I.FIELD_NAMES.get(fld, fld)} ← {key}")
    text = (f"{I.TITLES[kind]}: " + ("; ".join(esc(d) for d in done) if done else "hech narsa o'zgarmadi"))
    if bad:
        text += "\nTanilmadi: " + esc(", ".join(bad))
    text += "\n«🔍 Tekshirish» bilan natijani ko'ring: /integratsiya"
    await message.answer(text)
