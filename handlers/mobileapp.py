"""Telefon ilovasi (Android / iOS): yuklab olish, ilovaga kirishni tasdiqlash, qurilmalar.

• /ilova (va /start dagi «📲 Telefon ilovasi» tugmasi) — Android: APK fayl shu yerning o'zida yuboriladi; iPhone:
  App Store / TestFlight havolasi (super-admin kiritgan bo'lsa) yoki Safari orqali «Bosh ekranga qo'shish».
• /start a_<kod> — ilovadan kirish: yangi foydalanuvchi avval telefon raqamini tasdiqlaydi (ro'yxatdan o'tish botda),
  keyin ilovada ko'ringan 2 xonali raqamni tanlaydi (appauth.py).
• /qurilmalar — ilovaga kirgan qurilmalar ro'yxati, istalganini chiqarib yuborish.
• Super-admin botga .apk fayl yuborsa — ilovaning yangi Android versiyasi sifatida saqlanadi; /ilova_ios <havola> —
  iPhone havolasi.
"""
from __future__ import annotations

import html
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import appauth
from config import APP_RELEASES_REPO, DATA_DIR, WEBAPP_URL
from family import known_contact
from i18n import tr
from tenancy import central, is_staff, is_super
from utils import fmt_dt

log = logging.getLogger("mobileapp")
router = Router(name="mobileapp")
router.message.filter(F.chat.type == "private")

DL_CB = "mobile:dl"
APK_NAME = "jidu-ota-ona.apk"


class AL(StatesGroup):
    contact = State()


class AlCb(CallbackData, prefix="al"):
    c: str          # kirish kodi
    p: int          # tanlangan raqam (0 — bekor qilish)


class DevCb(CallbackData, prefix="dev"):
    s: int          # seans (0 — hammasi)


def apk_path() -> Path:
    p = Path(DATA_DIR) / "app"
    p.mkdir(parents=True, exist_ok=True)
    return p / APK_NAME


def download_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr("📲 Telefon ilovasini yuklab olish"),
                                                                       callback_data=DL_CB)]])


# ---------------------------------------------------------------- GitHub Releases dan yangi APK
async def refresh_apk() -> bool:
    """GitHub'dagi eng so'nggi relizdan APK ni yuklab oladi (yangi bo'lsa). Qaytaradi: yangilandimi."""
    if not APP_RELEASES_REPO:
        return False
    import aiohttp
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as s:
            async with s.get(f"https://api.github.com/repos/{APP_RELEASES_REPO}/releases/latest",
                             headers={"Accept": "application/vnd.github+json"}) as r:
                if r.status != 200:
                    return False
                rel = await r.json()
            asset = next((a for a in rel.get("assets", []) if a.get("name", "").endswith(".apk")), None)
            tag = rel.get("tag_name") or ""
            if not asset or tag == await central.get_meta("android_apk_tag"):
                return False
            async with s.get(asset["browser_download_url"]) as r:
                if r.status != 200:
                    return False
                data = await r.read()
        if not data.startswith(b"PK"):  # APK — zip arxiv
            return False
        tmp = apk_path().with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(apk_path())
        await central.set_meta("android_apk_tag", tag)
        await central.set_meta("android_apk_version", tag.split("-", 1)[-1])
        await central.set_meta("android_apk_file_id", "")  # keyingi yuborishda yangi fayl Telegram'ga yuklanadi
        log.info("Android ilova GitHub'dan yangilandi: %s (%s bayt)", tag, len(data))
        return True
    except Exception as e:  # tarmoq xatosi — keyingi safar
        log.warning("APK ni GitHub'dan olib bo'lmadi: %s", e)
        return False


async def apk_loop() -> None:
    import asyncio
    while True:
        await refresh_apk()
        await asyncio.sleep(6 * 3600)


# ---------------------------------------------------------------- yuklab olish
async def send_download(bot: Bot, chat_id: int) -> None:
    from aiogram.types import FSInputFile
    file_id = await central.get_meta("android_apk_file_id")
    version = await central.get_meta("android_apk_version") or ""
    ios_url = await central.get_meta("ios_url")
    caption = tr(
        "🤖 <b>Android</b>{v}: faylni oching → «O'rnatish». Telefon «noma'lum manba» haqida so'rasa — "
        "Telegram uchun ruxsat bering (bir marta).\n\nIlovani ochib «Telegram orqali kirish» ni bosing — "
        "kirish shu botda tasdiqlanadi.", v=f" (versiya {html.escape(version)})" if version else "")
    if not file_id and apk_path().exists():  # GitHub'dan olingan fayl — bir marta yuklanadi, keyin file_id bilan
        msg = await bot.send_document(chat_id, FSInputFile(apk_path(), filename=APK_NAME), caption=caption)
        if msg.document:
            await central.set_meta("android_apk_file_id", msg.document.file_id)
    elif file_id:
        await bot.send_document(chat_id, file_id, caption=caption)
    else:
        await bot.send_message(chat_id, tr("🤖 Android ilovasi tez orada shu yerda paydo bo'ladi."))
    if ios_url:
        await bot.send_message(chat_id, tr("🍏 <b>iPhone (iOS)</b>: quyidagi tugma orqali o'rnating, so'ng ilovada "
                                           "«Telegram orqali kirish» ni bosing."),
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                                   text=tr("🍏 iPhone uchun o'rnatish"), url=ios_url)]]))
    elif WEBAPP_URL:
        await bot.send_message(chat_id, tr(
            "🍏 <b>iPhone (iOS)</b>: havolani <b>Safari</b>da oching → pastdagi «Ulashish» belgisi → "
            "«Bosh ekranga qo'shish». Ilova belgisi telefon ekranida paydo bo'ladi; ochib «Telegram orqali kirish» ni "
            "bosing.\n{url}", url=WEBAPP_URL + "/"), disable_web_page_preview=True)


@router.message(Command("ilova", "app", "yuklab"), StateFilter("*"))
async def cmd_download(message: Message) -> None:
    await send_download(message.bot, message.chat.id)


@router.callback_query(F.data == DL_CB)
async def cb_download(cb: CallbackQuery) -> None:
    await cb.answer()
    await send_download(cb.bot, cb.message.chat.id)


# ---------------------------------------------------------------- ilova manzili (server manzili o'zgarganda)
async def send_address(message: Message) -> None:
    if not WEBAPP_URL:
        await message.answer(tr("Ilova hozircha sozlanmagan."))
        return
    await message.answer(tr(
        "🔗 <b>Ilova manzili:</b>\n<code>{url}</code>\n\nManzilni bosib nusxalang, so'ng telefon ilovasida "
        "«Yangi manzil» maydoniga joylab «Saqlash» ni bosing.", url=html.escape(WEBAPP_URL + "/")))


@router.message(CommandStart(deep_link=True, magic=F.args == "url"), StateFilter("*"))
async def start_address(message: Message) -> None:
    await send_address(message)


@router.message(Command("manzil", "url"), StateFilter("*"))
async def cmd_address(message: Message) -> None:
    await send_address(message)


# ---------------------------------------------------------------- super-admin: yangi versiya
@router.message(F.document & F.document.file_name.lower().endswith(".apk"))
async def upload_apk(message: Message) -> None:
    if not is_super(message.from_user.id):
        return
    doc = message.document
    version = (message.caption or "").strip()[:20]
    await central.set_meta("android_apk_file_id", doc.file_id)
    await central.set_meta("android_apk_version", version)
    saved = ""
    if (doc.file_size or 0) <= 20 * 1024 * 1024:  # Bot API faylni 20 MB gacha yuklab beradi — veb sahifa uchun nusxa
        try:
            await message.bot.download(doc, destination=apk_path())
            saved = f"\nVeb sahifadan ham yuklab olinadi: {WEBAPP_URL}/ilova" if WEBAPP_URL else ""
        except Exception:
            log.exception("APK saqlanmadi")
    log.info("Android ilova yangilandi: %s (%s bayt) — %s", version, doc.file_size, message.from_user.id)
    await message.answer(f"✅ Android ilova saqlandi{f' (versiya {html.escape(version)})' if version else ''}. "
                         f"Ota-onalar /ilova yoki «📲 Telefon ilovasi» tugmasi orqali shu faylni oladi.{saved}\n\n"
                         "Versiya raqamini faylga izoh (caption) qilib yozishingiz mumkin, masalan: 1.0.3")


@router.message(Command("ilova_ios"), StateFilter("*"))
async def set_ios(message: Message) -> None:
    if not is_super(message.from_user.id):
        return
    url = (message.text.split(maxsplit=1)[1].strip() if " " in message.text else "")
    if url and not url.startswith("https://"):
        await message.answer("Havola https:// bilan boshlanishi kerak (App Store yoki TestFlight).")
        return
    await central.set_meta("ios_url", url)
    await message.answer(f"✅ iPhone havolasi: {html.escape(url)}" if url else
                         "iPhone havolasi o'chirildi — ota-onalarga Safari orqali o'rnatish yo'riqnomasi ko'rsatiladi.")


# ---------------------------------------------------------------- ilovaga kirish
async def _ask_pin(message: Message, code: str, login: dict) -> None:
    kb = InlineKeyboardBuilder()
    for n in appauth.pin_choices(login["pin"]):
        kb.button(text=str(n), callback_data=AlCb(c=code, p=n))
    kb.button(text=tr("❌ Bu men emas"), callback_data=AlCb(c=code, p=0))
    kb.adjust(3, 1)
    await message.answer(tr(
        "📱 <b>Ilovaga kirish</b>{device}\n\nIlova ekranida ko'rsatilgan <b>raqamni</b> tanlang.\n\n"
        "⚠️ Agar hozir o'zingiz ilovaga kirmayotgan bo'lsangiz yoki bu havolani sizga kimdir yuborgan bo'lsa — "
        "«Bu men emas» ni bosing.",
        device=f"\n{tr('Qurilma')}: {html.escape(login['device'])}" if login.get("device") else ""),
        reply_markup=kb.as_markup())


@router.message(CommandStart(deep_link=True, magic=F.args.startswith(appauth.START_PREFIX)), StateFilter("*"))
async def open_login(message: Message, state: FSMContext) -> None:
    await state.clear()
    code = (message.text.split(maxsplit=1)[1] if " " in message.text else "")[len(appauth.START_PREFIX):].strip()
    login = await appauth.get_login(code) if code else None
    if not login or login["state"] != "pending":
        await message.answer(tr("Bu kirish havolasi eskirgan. Ilovada «Telegram orqali kirish» ni qaytadan bosing."),
                             reply_markup=ReplyKeyboardRemove())
        return
    uid = message.from_user.id
    if not is_staff(uid) and not await known_contact(uid):  # ro'yxatdan o'tish — telefon raqami Telegram orqali
        await state.set_state(AL.contact)
        await state.update_data(code=code)
        await message.answer(
            tr("👋 Ilovaga kirish uchun avval telefon raqamingizni tasdiqlang — pastdagi tugmani bosing. Raqamni "
               "Telegram o'zi yuboradi."),
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=tr("📱 Telefon raqamni yuborish"),
                                                                       request_contact=True)]],
                                             resize_keyboard=True, one_time_keyboard=True))
        return
    await _ask_pin(message, code, login)


@router.message(AL.contact, F.contact)
async def login_contact(message: Message, state: FSMContext) -> None:
    from handlers.common import on_contact
    code = (await state.get_data()).get("code", "")
    if not await on_contact(message, state, silent=True):
        await state.clear()
        return
    await state.clear()
    login = await appauth.get_login(code)
    await message.answer(tr("✅ Raqamingiz tasdiqlandi."), reply_markup=ReplyKeyboardRemove())
    if not login or login["state"] != "pending":
        await message.answer(tr("Kirish havolasi eskirdi. Ilovada «Telegram orqali kirish» ni qaytadan bosing."))
        return
    await _ask_pin(message, code, login)


@router.message(AL.contact)
async def login_need_contact(message: Message) -> None:
    await message.answer(tr("Iltimos, pastdagi «📱 Telefon raqamni yuborish» tugmasini bosing."))


@router.callback_query(AlCb.filter())
async def login_decide(cb: CallbackQuery, callback_data: AlCb) -> None:
    res = await appauth.decide(callback_data.c, cb.from_user.id, callback_data.p or None)
    await cb.answer()
    text = {
        "approved": tr("✅ Kirish tasdiqlandi — ilovaga qayting.\n\nBildirishnomalar avvalgidek shu chatga keladi. "
                       "Qurilmalar ro'yxati: /qurilmalar"),
        "wrong_pin": tr("❌ Raqam mos kelmadi — kirish bekor qilindi. O'zingiz kirayotgan bo'lsangiz, ilovada "
                        "qaytadan urinib ko'ring."),
        "cancelled": tr("Kirish bekor qilindi. Hech kim sizning akkauntingizga kira olmadi."),
        "expired": tr("Bu kirish havolasi eskirgan. Ilovada «Telegram orqali kirish» ni qaytadan bosing."),
    }[res]
    try:
        await cb.message.edit_text(text)
    except Exception:
        await cb.message.answer(text)
    log.info("Ilovaga kirish: %s — %s", cb.from_user.id, res)


# ---------------------------------------------------------------- qurilmalar
async def _devices(uid: int) -> tuple[str, InlineKeyboardMarkup | None]:
    items = await appauth.sessions(uid)
    if not items:
        return tr("Telefon ilovasiga kirilgan qurilma yo'q. Ilovani yuklab olish: /ilova"), None
    lines = [tr("📱 <b>Ilovaga kirgan qurilmalar</b>"), ""]
    kb = InlineKeyboardBuilder()
    for i, s in enumerate(items, 1):
        name = s["device"] or tr("Qurilma")
        lines.append(f"{i}. {html.escape(name)} — {tr('oxirgi marta')}: {fmt_dt(s['last_seen'])}")
        kb.button(text=f"🚪 {i}. {name[:24]}", callback_data=DevCb(s=s["id"]))
    kb.button(text=tr("🚪 Hammasidan chiqish"), callback_data=DevCb(s=0))
    kb.adjust(1)
    lines += ["", tr("Tanimagan qurilmangiz bo'lsa — uni chiqarib yuboring.")]
    return "\n".join(lines), kb.as_markup()


@router.message(Command("qurilmalar", "devices"), StateFilter("*"))
async def cmd_devices(message: Message) -> None:
    text, kb = await _devices(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(DevCb.filter())
async def cb_device(cb: CallbackQuery, callback_data: DevCb) -> None:
    await appauth.revoke(cb.from_user.id, callback_data.s or None)
    await cb.answer(tr("Chiqarildi"))
    text, kb = await _devices(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb)
