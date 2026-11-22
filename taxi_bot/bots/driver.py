"""Haydovchi boti: liniyaga chiqish (jonli joylashuv), buyurtma qabul qilish, safar, balans."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Location,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    User,
)

from ..db.models import DriverStatus
from ..services.geo import format_duration
from ..services.pricing import money
from ..services.taxi import TaxiService
from ..ui.kit import NAVIGATORS, PRIMARY, SUCCESS, DCb, btn, h, inline, kb_button
from ..ui.messenger import Role
from .common import apply_role
from .passenger import ack

LIVE_FOREVER = 0x7FFFFFFF
CAR_MODELS = ["Cobalt", "Nexia 3", "Gentra", "Lacetti", "Spark", "Onix", "Malibu", "Tracker", "Damas"]
CAR_COLORS = ["Oq", "Qora", "Kumush", "Kulrang", "Ko'k", "Qizil", "Jigarrang", "Mokriy asfalt"]


class Reg(StatesGroup):
    phone = State()
    name = State()
    car_model = State()
    car_color = State()
    plate = State()
    confirm = State()


def _choices(items: list[str], per_row: int = 3) -> ReplyKeyboardMarkup:
    rows = [[kb_button(x) for x in items[i : i + per_row]] for i in range(0, len(items), per_row)]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def normalize_plate(raw: str) -> str | None:
    """`01a123bc` -> `01 A 123 BC`; yuridik: `01 123 ABC`."""
    text = re.sub(r"[^0-9A-Za-z]", "", raw).upper()
    m = re.fullmatch(r"(\d{2})([A-Z])(\d{3})([A-Z]{2})", text)
    if m:
        return " ".join(m.groups())
    m = re.fullmatch(r"(\d{2})(\d{3})([A-Z]{3})", text)
    if m:
        return " ".join(m.groups())
    if 6 <= len(text) <= 10 and sum(ch.isdigit() for ch in text) >= 3:
        return text
    return None


async def driver_start(message: Message, user: User, svc: TaxiService, state: FSMContext) -> None:
    d = await svc.get_driver_by_tg(user.id)
    v = svc.views
    if d is None or d.status == DriverStatus.REJECTED:
        await state.set_state(Reg.phone)
        prefix = "❌ Oldingi arizangiz rad etilgan. Qayta topshirishingiz mumkin.\n\n" if d else ""
        await message.answer(
            prefix + f"🚕 <b>{h(svc.settings.company_name)}</b> — haydovchilar uchun bot.\n\n"
            "Ro'yxatdan o'tish 1 daqiqa vaqt oladi. Avval <b>telefon raqamingizni</b> yuboring.\n"
            "🔒 Raqamingiz yo'lovchilarga ko'rinmaydi.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[kb_button("📱 Raqamni yuborish", style=PRIMARY, contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return
    if d.status == DriverStatus.PENDING:
        await message.answer("⏳ Arizangiz ko'rib chiqilmoqda. Tasdiqlangach shu yerga xabar keladi.")
        return
    if d.status == DriverStatus.BLOCKED:
        phone = f" Operator: {h(svc.settings.company_phone)}" if svc.settings.company_phone else ""
        await message.answer("⛔️ Hisobingiz bloklangan." + phone)
        return
    status = "🟢 liniyadasiz" if d.is_online else "🔴 liniyada emassiz"
    await message.answer(
        f"Assalomu alaykum, <b>{h(d.full_name)}</b>! 🚕\n\n"
        f"Holat: <b>{status}</b>\n"
        f"Balans: <b>{h(v.m(d.balance))}</b> · Reyting: <b>⭐ {d.rating:.2f}</b>\n\n"
        "Buyurtma olish uchun <b>🟢 Liniyaga chiqish</b> tugmasini bosing.",
        reply_markup=v.driver_menu(d.is_online),
    )


def _live_until(message: Message, loc: Location) -> datetime | None:
    if not loc.live_period or loc.live_period >= LIVE_FOREVER:
        return None
    sent = message.date if message.date.tzinfo else message.date.replace(tzinfo=UTC)
    return (sent + timedelta(seconds=loc.live_period)).astimezone(UTC).replace(tzinfo=None)


def build_driver_router() -> Router:
    router = Router(name="driver")
    apply_role(router, Role.DRIVER)

    # ================================================================== start / ro'yxatdan o'tish
    @router.message(CommandStart())
    async def start(message: Message, svc: TaxiService, state: FSMContext) -> None:
        await state.clear()
        await driver_start(message, message.from_user, svc, state)  # type: ignore[arg-type]

    @router.message(Command("register"))
    async def register(message: Message, svc: TaxiService, state: FSMContext) -> None:
        d = await svc.get_driver_by_tg(message.from_user.id)  # type: ignore[union-attr]
        if d and d.status in (DriverStatus.APPROVED, DriverStatus.BLOCKED):
            await message.answer("Siz allaqachon ro'yxatdan o'tgansiz.")
            return
        await state.set_state(Reg.phone)
        await message.answer(
            "📱 Telefon raqamingizni yuboring:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[kb_button("📱 Raqamni yuborish", style=PRIMARY, contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )

    @router.message(Reg.phone, F.contact)
    async def reg_phone(message: Message, state: FSMContext) -> None:
        if message.contact.user_id != message.from_user.id:  # type: ignore[union-attr]
            await message.answer("Iltimos, o'zingizning raqamingizni tugma orqali yuboring.")
            return
        await state.update_data(phone=message.contact.phone_number)  # type: ignore[union-attr]
        await state.set_state(Reg.name)
        default = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))  # type: ignore[union-attr]
        await message.answer(
            "👤 Ism va familiyangizni yozing (faqat kompaniya ko'radi):",
            reply_markup=_choices([default]) if default else None,
        )

    @router.message(Reg.phone)
    async def reg_phone_wrong(message: Message) -> None:
        await message.answer("Iltimos, «📱 Raqamni yuborish» tugmasini bosing.")

    @router.message(Reg.name, F.text)
    async def reg_name(message: Message, state: FSMContext) -> None:
        name = (message.text or "").strip()
        if len(name) < 3:
            await message.answer("Ism juda qisqa. Qaytadan yozing:")
            return
        await state.update_data(full_name=name[:128])
        await state.set_state(Reg.car_model)
        await message.answer("🚘 Avtomobil modeli? (tanlang yoki yozing)", reply_markup=_choices(CAR_MODELS))

    @router.message(Reg.car_model, F.text)
    async def reg_model(message: Message, state: FSMContext) -> None:
        model = (message.text or "").strip()
        if len(model) < 2:
            await message.answer("Modelni yozing, masalan: Cobalt")
            return
        await state.update_data(car_model=model[:64])
        await state.set_state(Reg.car_color)
        await message.answer("🎨 Avtomobil rangi?", reply_markup=_choices(CAR_COLORS, 4))

    @router.message(Reg.car_color, F.text)
    async def reg_color(message: Message, state: FSMContext) -> None:
        await state.update_data(car_color=(message.text or "").strip()[:32])
        await state.set_state(Reg.plate)
        await message.answer(
            "🔢 Davlat raqami? (masalan: <code>01 A 123 BC</code>)",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[kb_button("❌ Bekor qilish")]], resize_keyboard=True),
        )

    @router.message(Reg.plate, F.text == "❌ Bekor qilish")
    @router.message(Reg.confirm, F.text == "❌ Bekor qilish")
    async def reg_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Ro'yxatdan o'tish bekor qilindi. Qayta boshlash: /start")

    @router.message(Reg.plate, F.text)
    async def reg_plate(message: Message, state: FSMContext) -> None:
        plate = normalize_plate(message.text or "")
        if plate is None:
            await message.answer("Raqam noto'g'ri. Masalan: <code>01 A 123 BC</code>")
            return
        await state.update_data(car_plate=plate)
        await state.set_state(Reg.confirm)
        data = await state.get_data()
        await message.answer(
            "📝 <b>Ma'lumotlarni tekshiring:</b>\n\n"
            f"👤 {h(data['full_name'])}\n📱 {h(data['phone'])}\n"
            f"🚘 {h(data['car_color'])} {h(data['car_model'])}\n🔢 {h(plate)}",
            reply_markup=inline(
                [
                    btn("✅ Yuborish", cb=DCb(action="regok"), style=SUCCESS),
                    btn("✏️ Qayta to'ldirish", cb=DCb(action="regredo")),
                ]
            ),
        )

    @router.callback_query(DCb.filter(F.action == "regok"))
    async def reg_submit(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        data = await state.get_data()
        if await state.get_state() != Reg.confirm.state:
            await callback.answer("Ariza eskirgan. /start", show_alert=True)
            return
        await state.clear()
        await svc.register_driver(
            callback.from_user.id,
            data["full_name"],
            data["phone"],
            data["car_model"],
            data["car_color"],
            data["car_plate"],
        )
        await callback.answer("✅ Yuborildi")
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                "✅ Arizangiz yuborildi! Kompaniya tasdiqlagach, shu yerga xabar keladi.",
                reply_markup=svc.views.driver_menu(False),
            )

    @router.callback_query(DCb.filter(F.action == "regredo"))
    async def reg_redo(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        await callback.answer()
        await state.clear()
        if isinstance(callback.message, Message):
            await driver_start(callback.message, callback.from_user, svc, state)

    # ================================================================== joylashuv
    async def handle_location(message: Message, svc: TaxiService, *, edited: bool) -> None:
        if message.forward_origin is not None:
            await message.answer("⚠️ Iltimos, o'z joylashuvingizni yuboring (forward qabul qilinmaydi).")
            return
        loc = message.location
        is_live = bool(loc.live_period)
        result = await svc.update_driver_location(
            message.from_user.id,  # type: ignore[union-attr]
            loc.latitude,
            loc.longitude,
            accuracy=loc.horizontal_accuracy,
            heading=loc.heading,
            is_live=is_live,
            live_until=_live_until(message, loc),
        )
        v = svc.views
        if result.ignored == "not_driver":
            if not edited:
                await message.answer("Avval ro'yxatdan o'ting: /start")
            return
        if result.ignored == "not_approved":
            if not edited:
                await message.answer("⏳ Arizangiz hali tasdiqlanmagan.")
            return
        if result.ignored == "need_live":
            if edited:  # jonli joylashuv to'xtatildi
                await message.answer(
                    "📡 Jonli joylashuv to'xtadi — yangi buyurtmalar kelmaydi.\n\n" + v.live_location_help()
                )
            else:
                await message.answer(v.live_location_help())
            return
        if result.low_balance:
            if not edited:
                await message.answer(
                    "⚠️ <b>Balansingiz yetarli emas</b> — liniyaga chiqish uchun kamida "
                    f"{h(v.m(svc.settings.min_driver_balance))} kerak. 💰 Balans bo'limidan to'ldiring."
                )
            return
        if result.went_online:
            await message.answer(
                "🟢 <b>Siz liniyadasiz!</b> Eng yaqin buyurtmalar shu yerga keladi.\n"
                + ("📡 Jonli joylashuv ulandi — taksometr va qidiruv aniq ishlaydi." if is_live else ""),
                reply_markup=v.driver_menu(True),
            )
        elif not edited:
            await ack(message)

    @router.message(F.location)
    async def location(message: Message, svc: TaxiService) -> None:
        await handle_location(message, svc, edited=False)

    @router.edited_message(F.location)
    async def live_update(message: Message, svc: TaxiService) -> None:
        await handle_location(message, svc, edited=True)

    @router.message(F.text == "🟢 Liniyaga chiqish")
    async def go_online(message: Message, svc: TaxiService) -> None:
        result = await svc.driver_go_online(message.from_user.id)  # type: ignore[union-attr]
        v = svc.views
        if result == "online":
            await message.answer("🟢 <b>Siz liniyadasiz!</b> Buyurtmalar kutilmoqda.", reply_markup=v.driver_menu(True))
        elif result == "need_location":
            await message.answer(v.live_location_help())
        elif result == "low_balance":
            await message.answer(
                "⚠️ <b>Balansingiz yetarli emas.</b> 💰 Balans bo'limidan to'ldiring.",
            )
        elif result == "not_approved":
            await message.answer("⏳ Arizangiz hali tasdiqlanmagan.")
        else:
            await message.answer("Avval ro'yxatdan o'ting: /start")

    @router.message(F.text == "📡 Jonli joylashuv")
    async def live_help(message: Message, svc: TaxiService) -> None:
        await message.answer(svc.views.live_location_help())

    @router.message(F.text == "🔴 Liniyadan chiqish")
    async def go_offline(message: Message, svc: TaxiService) -> None:
        await svc.driver_offline(message.from_user.id)  # type: ignore[union-attr]
        await message.answer(
            "🔴 Liniyadan chiqdingiz. Yangi buyurtmalar kelmaydi.\n"
            "💡 Jonli joylashuvni ham to'xtatishingiz mumkin.",
            reply_markup=svc.views.driver_menu(False),
        )

    # ================================================================== buyurtma tugmalari
    @router.callback_query(DCb.filter(F.action == "acc"))
    async def accept(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        mid = callback.message.message_id if callback.message else None
        result = await svc.accept_offer(callback.from_user.id, callback_data.oid, mid)
        messages = {
            "taken": "⌛️ Buyurtma allaqachon boshqa haydovchiga o'tdi.",
            "busy": "Sizda faol buyurtma bor — avval uni yakunlang.",
            "low_balance": "⚠️ Balansingiz yetarli emas. 💰 Balansni to'ldiring.",
            "not_driver": "Hisobingiz faol emas.",
        }
        if result.ok:
            await callback.answer("✅ Buyurtma sizniki! Yo'lovchiga xabar berildi.")
        else:
            await callback.answer(messages.get(result.reason, "Qabul qilib bo'lmadi."), show_alert=True)

    @router.callback_query(DCb.filter(F.action == "skip"))
    async def skip(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        mid = callback.message.message_id if callback.message else None
        await svc.decline_offer(callback.from_user.id, callback_data.oid, mid)
        await callback.answer("O'tkazib yuborildi")

    @router.callback_query(DCb.filter(F.action == "arr"))
    async def arrived(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        ok = await svc.driver_arrived(callback.from_user.id, callback_data.oid)
        await callback.answer("🔔 Yo'lovchiga «yetib keldi» xabari yuborildi." if ok else "Holat o'zgargan.")

    @router.callback_query(DCb.filter(F.action == "start"))
    async def start_trip(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        ok = await svc.driver_start(callback.from_user.id, callback_data.oid)
        await callback.answer("🚀 Safar boshlandi. Oq yo'l!" if ok else "Holat o'zgargan.")

    @router.callback_query(DCb.filter(F.action == "fin"))
    async def finish(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        ok = await svc.driver_finish(callback.from_user.id, callback_data.oid)
        await callback.answer(
            "🏁 Yo'lovchidan tasdiq so'raldi. Tasdiqlangach safar yakunlanadi." if ok else "Holat o'zgargan."
        )

    @router.callback_query(DCb.filter(F.action == "call"))
    async def call(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        text = await svc.request_call(callback.from_user.id, callback_data.oid, Role.DRIVER)
        await callback.answer(text, show_alert=True)

    @router.callback_query(DCb.filter(F.action == "cx"))
    async def cancel_ask(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        order = await svc.get_order(callback_data.oid)
        await callback.answer()
        if order:
            await svc.msg.send(Role.DRIVER, callback.from_user.id, svc.views.driver_cancel_confirm(order))

    @router.callback_query(DCb.filter(F.action == "cxok"))
    async def cancel_ok(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        result = await svc.driver_cancel(callback.from_user.id, callback_data.oid, no_show=False)
        await callback.answer("Buyurtma bekor qilindi." if result == "ok" else "Bekor qilib bo'lmaydi.")
        if isinstance(callback.message, Message):
            await callback.message.delete()

    @router.callback_query(DCb.filter(F.action == "cxno"))
    async def cancel_no(callback: CallbackQuery) -> None:
        await callback.answer("Davom etamiz 👍")
        if isinstance(callback.message, Message):
            await callback.message.delete()

    @router.callback_query(DCb.filter(F.action == "noshow"))
    async def no_show(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        result = await svc.driver_cancel(callback.from_user.id, callback_data.oid, no_show=True)
        if result == "too_early":
            wait = format_duration(svc.settings.no_show_wait_min * 60)
            await callback.answer(f"⏳ Yo'lovchini kamida {wait} kuting.", show_alert=True)
        else:
            await callback.answer("Buyurtma yopildi." if result == "ok" else "Holat o'zgargan.")

    # ================================================================== balans / statistika / sozlamalar
    @router.message(F.text == "💰 Balans")
    @router.message(Command("balance"))
    async def balance(message: Message, svc: TaxiService) -> None:
        d = await svc.get_driver_by_tg(message.from_user.id)  # type: ignore[union-attr]
        if d is None:
            await message.answer("Avval ro'yxatdan o'ting: /start")
            return
        view = svc.views.driver_balance(d, payments=svc.settings.payment_provider_token is not None)
        await svc.msg.send(Role.DRIVER, message.chat.id, view)

    @router.callback_query(DCb.filter(F.action == "topup"))
    async def topup(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        token = svc.settings.payment_provider_token
        d = await svc.get_driver_by_tg(callback.from_user.id)
        if token is None or d is None or callback_data.val <= 0:
            await callback.answer("To'lov tizimi ulanmagan.", show_alert=True)
            return
        await callback.answer()
        amount = callback_data.val
        await callback.bot.send_invoice(  # type: ignore[union-attr]
            chat_id=callback.from_user.id,
            title="Balansni to'ldirish",
            description=f"{svc.settings.company_name}: haydovchi balansi (ID {d.id})",
            payload=f"topup:{d.id}:{amount}",
            provider_token=token.get_secret_value(),
            currency="UZS",
            prices=[LabeledPrice(label="Balans", amount=amount * 100)],
        )

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery, svc: TaxiService) -> None:
        parts = query.invoice_payload.split(":")
        ok = len(parts) == 3 and parts[0] == "topup" and query.total_amount == int(parts[2]) * 100
        if ok:
            d = await svc.get_driver(int(parts[1]))
            ok = d is not None and d.tg_id == query.from_user.id
        await query.answer(ok=ok, error_message=None if ok else "To'lov ma'lumotlari noto'g'ri.")

    @router.message(F.successful_payment)
    async def paid(message: Message, svc: TaxiService) -> None:
        sp = message.successful_payment
        _, driver_id, amount = sp.invoice_payload.split(":")  # type: ignore[union-attr]
        await svc.adjust_balance(
            int(driver_id),
            int(amount),
            "payment",
            note=f"Telegram to'lov ({sp.currency})",  # type: ignore[union-attr]
            external_id=sp.telegram_payment_charge_id,  # type: ignore[union-attr]
        )

    @router.message(F.text == "📊 Statistika")
    async def stats(message: Message, svc: TaxiService) -> None:
        d = await svc.get_driver_by_tg(message.from_user.id)  # type: ignore[union-attr]
        if d is None:
            return
        st = await svc.driver_stats(d.id)
        cur = svc.settings.currency
        await message.answer(
            "📊 <b>Statistika</b>\n\n"
            f"Bugun: <b>{st['today_trips']}</b> ta safar · <b>{h(money(st['today_income'], cur))}</b>\n"
            f"Bugungi xizmat haqi: {h(money(st['today_commission'], cur))}\n\n"
            f"Jami safarlar: <b>{st['total_trips']}</b>\n"
            f"Reyting: <b>⭐ {st['rating']:.2f}</b> ({st['rating_count']} ta baho)\n"
            f"💳 Balans: <b>{h(money(d.balance, cur))}</b>"
        )

    def nav_markup(current: str):
        return inline(
            *[
                btn(("✅ " if key == current else "") + name, cb=DCb(action="nav", val=i), style=SUCCESS if key == current else None)
                for i, (key, name) in enumerate(NAVIGATORS.items())
            ]
        )

    @router.message(F.text == "⚙️ Sozlamalar")
    async def settings_(message: Message, svc: TaxiService) -> None:
        d = await svc.get_driver_by_tg(message.from_user.id)  # type: ignore[union-attr]
        if d is None:
            return
        await message.answer(
            "⚙️ <b>Navigator</b> — «📍 Yo'lovchini olish manzili» bosilganda qaysi ilovada yo'l ochilsin?",
            reply_markup=nav_markup(d.navigator),
        )

    @router.callback_query(DCb.filter(F.action == "nav"))
    async def set_nav(callback: CallbackQuery, callback_data: DCb, svc: TaxiService) -> None:
        keys = list(NAVIGATORS)
        key = keys[callback_data.val] if 0 <= callback_data.val < len(keys) else "google"
        await svc.set_navigator(callback.from_user.id, key)
        await callback.answer(f"✅ {NAVIGATORS[key]}")
        if isinstance(callback.message, Message):
            try:
                await callback.message.edit_reply_markup(reply_markup=nav_markup(key))
            except TelegramAPIError:
                pass

    @router.message(F.text == "ℹ️ Yordam")
    @router.message(Command("help"))
    async def help_(message: Message, svc: TaxiService) -> None:
        s = svc.settings
        role = "\n🔄 Rolni almashtirish: /role" if s.single_bot else ""
        await message.answer(
            "ℹ️ <b>Haydovchi uchun qo'llanma</b>\n\n"
            "1️⃣ <b>🟢 Liniyaga chiqish</b> → jonli joylashuvni ulashing («Men o'chirmagunimcha»).\n"
            "2️⃣ Buyurtma kelganda <b>✅ Qabul qilish</b> ni bosing — kim birinchi bossa, o'shaniki.\n"
            "3️⃣ <b>📍 Yo'lovchini olish manzili</b> — navigatorda yo'l darhol ochiladi.\n"
            "4️⃣ <b>📞 Yo'lovchi bilan aloqa</b> — kompaniya raqami orqali ulanasiz.\n"
            "5️⃣ <b>✅ Yetib keldim</b> → <b>🚀 Safarni boshlash</b> → <b>🏁 Safarni yakunlash</b>.\n"
            "6️⃣ Yo'lovchi manzilga yetganini tasdiqlagach, balansdan "
            f"<b>{s.commission_percent:g}%</b> xizmat haqi yechiladi.\n\n"
            "🏆 Buyurtmalar avval eng yaqin va reytingi yuqori haydovchilarga ko'rinadi. "
            "1 daqiqada hech kim olmasa — keyingi radiusdagilarga.\n"
            "💬 Safar davomida shu yerga yozgan xabaringiz yo'lovchiga anonim yetkaziladi."
            + role
        )

    # ================================================================== anonim chat
    @router.message(F.voice, StateFilter(None))
    async def voice(message: Message, svc: TaxiService) -> None:
        if await svc.relay_voice(Role.DRIVER, message.from_user.id, message.voice.file_id):  # type: ignore[union-attr]
            await ack(message)
        else:
            await message.answer("Ovozli xabar faqat faol buyurtma davomida yo'lovchiga yetkaziladi.")

    @router.message(F.text, StateFilter(None))
    async def free_text(message: Message, svc: TaxiService) -> None:
        if await svc.relay_text(Role.DRIVER, message.from_user.id, message.text or ""):  # type: ignore[union-attr]
            await ack(message)
            return
        d = await svc.get_driver_by_tg(message.from_user.id)  # type: ignore[union-attr]
        if d is None:
            await message.answer("Ro'yxatdan o'tish uchun /start ni bosing.")
            return
        await message.answer("Menyudan foydalaning 👇", reply_markup=svc.views.driver_menu(d.is_online))

    return router


__all__ = ["build_driver_router", "driver_start", "normalize_plate"]
