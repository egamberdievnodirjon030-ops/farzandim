"""Yo'lovchi boti: 1 tugma — joylashuv, ixtiyoriy manzil, tasdiq. Hammasi shu."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReactionTypeEmoji, User

from ..db.models import OrderStatus
from ..services.geo import format_distance, haversine_m
from ..services.pricing import money
from ..services.taxi import TaxiService
from ..ui.kit import PCb, View, h
from ..ui.messenger import Role
from ..ui.views import Quote
from .common import apply_role

STATUS_UZ = {
    OrderStatus.SEARCHING: "🔎 qidirilmoqda",
    OrderStatus.ACCEPTED: "🚕 haydovchi yo'lda",
    OrderStatus.ARRIVED: "⏳ haydovchi kutmoqda",
    OrderStatus.IN_PROGRESS: "🚀 safarda",
    OrderStatus.FINISHING: "🏁 tasdiq kutilmoqda",
    OrderStatus.COMPLETED: "✅ yakunlangan",
    OrderStatus.CANCELLED: "❌ bekor qilingan",
    OrderStatus.NO_DRIVERS: "😔 haydovchi topilmadi",
}

MIN_TRIP_M = 150


async def ack(message: Message) -> None:
    """Xabar yetkazilganini reaksiya bilan bildiradi."""
    try:
        await message.react([ReactionTypeEmoji(emoji="👌")])
    except TelegramAPIError:
        pass


class Draft(StatesGroup):
    destination = State()
    confirm = State()
    rider = State()


class PlaceAdd(StatesGroup):
    waiting = State()


PLACE_KINDS = ("home", "work", "other")
MENU_TEXTS = {"📋 Safarlarim", "📍 Manzillarim", "ℹ️ Yordam"}


async def passenger_start(message: Message, user: User, svc: TaxiService) -> None:
    p = await svc.ensure_passenger(user.id, user.first_name or "")
    v = svc.views
    if not p.phone:
        await message.answer(
            v.passenger_welcome(user.first_name or "")
            + "\n\n📱 Boshlash uchun <b>telefon raqamingizni</b> yuboring — u faqat kompaniya "
            "orqali bog'lanish uchun kerak.",
            reply_markup=v.phone_request(),
        )
        return
    await message.answer(v.passenger_welcome(user.first_name or ""), reply_markup=v.passenger_menu())
    active = await svc.active_order(p.id)
    if active:
        await message.answer(
            f"ℹ️ Sizda faol buyurtma bor: <b>#{active.id}</b> — {STATUS_UZ[OrderStatus(active.status)]}."
        )


def build_passenger_router() -> Router:
    router = Router(name="passenger")
    apply_role(router, Role.PASSENGER)

    # ------------------------------------------------------------------ start / telefon
    @router.message(CommandStart())
    async def start(message: Message, svc: TaxiService, state: FSMContext) -> None:
        await state.clear()
        await passenger_start(message, message.from_user, svc)  # type: ignore[arg-type]

    @router.message(F.contact, StateFilter(None))
    async def contact(message: Message, svc: TaxiService) -> None:
        c = message.contact
        if c.user_id != message.from_user.id:  # type: ignore[union-attr]
            await message.answer(
                "Iltimos, <b>o'zingizning</b> raqamingizni «📱 Raqamni yuborish» tugmasi orqali yuboring.",
                reply_markup=svc.views.phone_request(),
            )
            return
        await svc.ensure_passenger(message.from_user.id, message.from_user.first_name or "")  # type: ignore[union-attr]
        await svc.set_passenger_phone(message.from_user.id, c.phone_number)  # type: ignore[union-attr]
        await message.answer(
            "✅ Rahmat! Endi <b>🚕 Taksi chaqirish</b> tugmasini bosing.",
            reply_markup=svc.views.passenger_menu(),
        )

    # ------------------------------------------------------------------ olish joyi
    @router.message(F.location, StateFilter(None))
    async def pickup(message: Message, svc: TaxiService, state: FSMContext) -> None:
        user = message.from_user
        p = await svc.ensure_passenger(user.id, user.first_name or "")  # type: ignore[union-attr]
        if not p.phone:
            await message.answer("📱 Avval telefon raqamingizni yuboring.", reply_markup=svc.views.phone_request())
            return
        if p.is_blocked:
            await message.answer("⛔️ Hisobingiz cheklangan. Operatorga murojaat qiling.")
            return
        active = await svc.active_order(p.id)
        if active:
            await message.answer(
                f"ℹ️ Sizda faol buyurtma bor: <b>#{active.id}</b> — {STATUS_UZ[OrderStatus(active.status)]}.\n"
                "Yangi buyurtma uchun avval uni yakunlang yoki bekor qiling."
            )
            return
        loc = message.location
        await state.set_state(Draft.destination)
        await state.update_data(
            pickup_lat=loc.latitude,
            pickup_lon=loc.longitude,
            accuracy=loc.horizontal_accuracy,
            comment=None,
            quote_msg=None,
        )
        places = await svc.list_places(p.id)
        recents = await svc.recent_destinations(p.id)
        view = svc.views.destination_prompt(
            loc.horizontal_accuracy, (loc.latitude, loc.longitude), places, recents
        )
        await message.answer(view.text, reply_markup=view.markup)

    # ------------------------------------------------------------------ manzil
    async def show_quote(
        message: Message,
        svc: TaxiService,
        state: FSMContext,
        dest: tuple[float, float] | None,
        dest_title: str | None,
    ) -> None:
        data = await state.get_data()
        if "pickup_lat" not in data:
            await state.clear()
            await message.answer("Joylashuvni qaytadan yuboring.", reply_markup=svc.views.passenger_menu())
            return
        if dest is not None:
            dist = haversine_m(data["pickup_lat"], data["pickup_lon"], dest[0], dest[1])
            if dist < MIN_TRIP_M:
                await message.answer(
                    f"📍 Manzil olish joyiga juda yaqin ({format_distance(dist)}). "
                    "Xaritada boshqa nuqtani tanlang yoki «⏭ Manzilsiz (taksometr)» tugmasini bosing."
                )
                return
        quote = await svc.build_quote(
            data["pickup_lat"],
            data["pickup_lon"],
            data.get("accuracy"),
            dest[0] if dest else None,
            dest[1] if dest else None,
            dest_title,
            data.get("comment"),
        )
        quote.rider_phone = data.get("rider_phone")
        await state.update_data(quote=asdict(quote))
        await state.set_state(Draft.confirm)
        view = svc.views.quote(quote)
        old = data.get("quote_msg")
        if old:
            await svc.msg.delete(Role.PASSENGER, message.chat.id, old)
        msg_id = await svc.msg.send(Role.PASSENGER, message.chat.id, view)
        await state.update_data(quote_msg=msg_id)

    @router.message(F.location | F.venue, StateFilter(Draft.destination, Draft.confirm))
    async def destination(message: Message, svc: TaxiService, state: FSMContext) -> None:
        if message.venue:
            loc, title = message.venue.location, message.venue.title
        else:
            loc, title = message.location, None
        await show_quote(message, svc, state, (loc.latitude, loc.longitude), title)

    @router.message(F.text.in_({"⏭ Manzilsiz davom etish", "⏭ Manzilsiz"}), StateFilter(Draft.destination, Draft.confirm))
    async def no_destination(message: Message, svc: TaxiService, state: FSMContext) -> None:
        await show_quote(message, svc, state, None, None)

    @router.message(F.text == "❌ Bekor qilish", StateFilter(Draft.destination, Draft.confirm))
    async def cancel_draft(message: Message, svc: TaxiService, state: FSMContext) -> None:
        data = await state.get_data()
        if data.get("quote_msg"):
            await svc.msg.delete(Role.PASSENGER, message.chat.id, data["quote_msg"])
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=svc.views.passenger_menu())

    @router.message(F.text, ~F.text.in_(MENU_TEXTS), StateFilter(Draft.destination, Draft.confirm))
    async def draft_comment(message: Message, svc: TaxiService, state: FSMContext) -> None:
        comment = (message.text or "").strip()[:300]
        await state.update_data(comment=comment)
        current = await state.get_state()
        data = await state.get_data()
        if current == Draft.confirm.state and data.get("quote"):
            q = Quote(**{**data["quote"], "comment": comment})
            await state.update_data(quote=asdict(q))
            await svc.msg.edit(Role.PASSENGER, message.chat.id, data.get("quote_msg"), svc.views.quote(q))
            await message.answer("💬 Izoh qo'shildi.")
        else:
            await message.answer(
                "💬 Izoh sifatida saqlandi. Endi manzilni xaritada belgilang (📎 → Joylashuv) "
                "yoki «⏭ Manzilsiz (taksometr)» tugmasini bosing."
            )

    @router.callback_query(PCb.filter(F.action == "nodest"))
    async def nodest(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        if await state.get_state() is None:
            await callback.answer("Avval 🚕 Taksi chaqirish tugmasini bosing", show_alert=True)
            return
        await callback.answer()
        await show_quote(callback.message, svc, state, None, None)  # type: ignore[arg-type]

    @router.callback_query(PCb.filter(F.action == "place"))
    async def place_pick(callback: CallbackQuery, callback_data: PCb, svc: TaxiService, state: FSMContext) -> None:
        place = await svc.get_place(callback.from_user.id, callback_data.oid)
        if place is None:
            await callback.answer("Manzil topilmadi")
            return
        if await state.get_state() is None:
            await callback.answer("Avval 🚕 Taksi chaqirish tugmasini bosing", show_alert=True)
            return
        await callback.answer()
        await show_quote(callback.message, svc, state, (place.lat, place.lon), place.title)  # type: ignore[arg-type]

    # 👤 Boshqa odam uchun buyurtma
    async def rerender_quote(message: Message, svc: TaxiService, state: FSMContext) -> None:
        data = await state.get_data()
        q = Quote(**{**data["quote"], "rider_phone": data.get("rider_phone")})
        await state.update_data(quote=asdict(q))
        await state.set_state(Draft.confirm)
        if data.get("quote_msg"):
            await svc.msg.delete(Role.PASSENGER, message.chat.id, data["quote_msg"])
        msg_id = await svc.msg.send(Role.PASSENGER, message.chat.id, svc.views.quote(q))
        await state.update_data(quote_msg=msg_id)

    @router.callback_query(PCb.filter(F.action == "rider"))
    async def rider_ask(callback: CallbackQuery, state: FSMContext) -> None:
        if await state.get_state() != Draft.confirm.state:
            await callback.answer("Buyurtma eskirgan", show_alert=True)
            return
        await state.set_state(Draft.rider)
        await callback.answer()
        await callback.message.answer(  # type: ignore[union-attr]
            "👤 <b>Kim uchun buyurtma?</b>\n\n📎 → <b>Kontakt</b> orqali odamni tanlang yoki raqamini yozing "
            "(masalan: <code>90 123 45 67</code>).\nHaydovchi u bilan kompaniya raqami orqali bog'lanadi — "
            "raqam haydovchiga ko'rinmaydi."
        )

    @router.message(Draft.rider, F.contact | F.text)
    async def rider_set(message: Message, svc: TaxiService, state: FSMContext) -> None:
        from ..services.telephony import normalize_phone

        raw = message.contact.phone_number if message.contact else (message.text or "")
        phone = normalize_phone(raw)
        if phone is None or len(phone) < 12:
            await message.answer("Raqam noto'g'ri. Masalan: <code>90 123 45 67</code> yoki kontakt yuboring.")
            return
        await state.update_data(rider_phone=phone)
        await rerender_quote(message, svc, state)

    @router.callback_query(PCb.filter(F.action == "self"))
    async def rider_self(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        if await state.get_state() != Draft.confirm.state:
            await callback.answer("Buyurtma eskirgan", show_alert=True)
            return
        await callback.answer("O'zingiz uchun")
        await state.update_data(rider_phone=None)
        await rerender_quote(callback.message, svc, state)  # type: ignore[arg-type]

    @router.callback_query(PCb.filter(F.action == "recent"))
    async def recent(callback: CallbackQuery, callback_data: PCb, svc: TaxiService, state: FSMContext) -> None:
        past = await svc.get_order(callback_data.oid)
        passenger = await svc.get_passenger_by_tg(callback.from_user.id)
        if past is None or passenger is None or past.passenger_id != passenger.id or past.dest_lat is None:
            await callback.answer("Manzil topilmadi")
            return
        if await state.get_state() is None:
            await callback.answer("Avval 🚕 Taksi chaqirish tugmasini bosing", show_alert=True)
            return
        await callback.answer()
        await show_quote(callback.message, svc, state, (past.dest_lat, past.dest_lon), past.dest_title)  # type: ignore[arg-type]

    @router.callback_query(PCb.filter(F.action == "draftx"))
    async def draft_cancel_cb(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        await state.clear()
        await callback.answer("Bekor qilindi")
        if isinstance(callback.message, Message):
            await callback.message.delete()
            await callback.message.answer("Buyurtma bekor qilindi.", reply_markup=svc.views.passenger_menu())

    @router.callback_query(PCb.filter(F.action == "confirm"))
    async def confirm(callback: CallbackQuery, svc: TaxiService, state: FSMContext) -> None:
        data = await state.get_data()
        if await state.get_state() != Draft.confirm.state or not data.get("quote"):
            await callback.answer("Buyurtma eskirgan. Qaytadan 🚕 Taksi chaqirish tugmasini bosing.", show_alert=True)
            return
        await state.clear()
        await callback.answer("🚕 Qidirilmoqda…")
        chat_id = callback.message.chat.id  # type: ignore[union-attr]
        await svc.msg.delete(Role.PASSENGER, chat_id, callback.message.message_id)  # type: ignore[union-attr]
        await svc.msg.send(
            Role.PASSENGER,
            chat_id,
            View.plain("✅ Buyurtmangiz qabul qilindi.", svc.views.passenger_menu()),
            silent=True,
        )
        order = await svc.create_order(callback.from_user.id, Quote(**data["quote"]))
        if order is None:
            await svc.msg.send(
                Role.PASSENGER, chat_id, View.plain("ℹ️ Sizda allaqachon faol buyurtma bor.")
            )

    # ------------------------------------------------------------------ buyurtma tugmalari
    @router.callback_query(PCb.filter(F.action.in_({"cancel", "close"})))
    async def cancel(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        result = await svc.passenger_cancel(callback.from_user.id, callback_data.oid, confirmed=False)
        if result == "confirm":
            await callback.answer()
            order = await svc.get_order(callback_data.oid)
            view = svc.views.passenger_cancel_confirm(order)  # type: ignore[arg-type]
            await svc.msg.send(Role.PASSENGER, callback.from_user.id, view)
        elif result == "cancelled":
            await callback.answer("Buyurtma bekor qilindi")
        elif result == "too_late":
            await callback.answer("Safar boshlangan — manzilga yetgach tasdiqlang.", show_alert=True)
        else:
            await callback.answer("Buyurtma topilmadi yoki allaqachon yakunlangan.")

    @router.callback_query(PCb.filter(F.action == "cancelok"))
    async def cancel_ok(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        result = await svc.passenger_cancel(callback.from_user.id, callback_data.oid, confirmed=True)
        await callback.answer("Buyurtma bekor qilindi" if result == "cancelled" else "Bekor qilib bo'lmadi")
        if isinstance(callback.message, Message):
            await callback.message.delete()

    @router.callback_query(PCb.filter(F.action == "keep"))
    async def keep(callback: CallbackQuery) -> None:
        await callback.answer("Buyurtma davom etmoqda 👍")
        if isinstance(callback.message, Message):
            await callback.message.delete()

    @router.callback_query(PCb.filter(F.action == "retry"))
    async def retry(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        ok = await svc.retry_search(callback.from_user.id, callback_data.oid)
        await callback.answer("🔎 Qayta qidirilmoqda…" if ok else "Bu buyurtma eskirgan yoki sizda boshqa faol buyurtma bor.")

    @router.callback_query(PCb.filter(F.action == "call"))
    async def call(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        text = await svc.request_call(callback.from_user.id, callback_data.oid, Role.PASSENGER)
        await callback.answer(text, show_alert=True)

    @router.callback_query(PCb.filter(F.action.in_({"arrive", "ok"})))
    async def arrived(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        ok = await svc.passenger_confirm_arrival(callback.from_user.id, callback_data.oid)
        await callback.answer("✅ Safar yakunlandi. Rahmat!" if ok else "Buyurtma allaqachon yakunlangan.")

    @router.callback_query(PCb.filter(F.action == "notyet"))
    async def not_yet(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        result = await svc.passenger_not_yet(callback.from_user.id, callback_data.oid)
        phone = f" Operator: {svc.settings.company_phone}" if svc.settings.company_phone else ""
        texts = {
            "ok": "Haydovchiga xabar berildi. Safar davom etmoqda.",
            "driver_busy": "Haydovchi safarni yakunlab, boshqa buyurtmaga o'tgan. Muammo bo'lsa, operatorga "
            "murojaat qiling." + phone,
        }
        await callback.answer(texts.get(result, "Buyurtma topilmadi."), show_alert=result == "driver_busy")

    @router.callback_query(PCb.filter(F.action == "rate"))
    async def rate(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        order = await svc.rate(callback.from_user.id, callback_data.oid, callback_data.val)
        if order is None:
            await callback.answer("Baho allaqachon qo'yilgan.")
            return
        await callback.answer("🙏 Rahmat!")
        await refresh_rated(callback, svc, order.id)

    async def refresh_rated(callback: CallbackQuery, svc: TaxiService, order_id: int) -> None:
        order = await svc.get_order(order_id)
        p = await svc.get_passenger_by_tg(callback.from_user.id)
        if order is None or p is None or not isinstance(callback.message, Message):
            return
        is_fav = bool(order.driver_id) and await svc.is_favorite(p.id, order.driver_id)  # type: ignore[arg-type]
        kinds = {pl.kind for pl in await svc.list_places(p.id)}
        await svc.msg.edit(
            Role.PASSENGER,
            callback.message.chat.id,
            callback.message.message_id,
            svc.views.rated(order, order.rating or 5, is_favorite=is_fav, saved_kinds=kinds),
        )

    @router.callback_query(PCb.filter(F.action == "fav"))
    async def favorite(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        ok = await svc.add_favorite(callback.from_user.id, callback_data.oid)
        await callback.answer(
            "❤️ Qo'shildi! Bu haydovchi yaqin bo'lsa, buyurtmangizni birinchi bo'lib ko'radi."
            if ok
            else "Topilmadi",
            show_alert=ok,
        )
        await refresh_rated(callback, svc, callback_data.oid)

    @router.callback_query(PCb.filter(F.action == "savedest"))
    async def save_dest(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        kind = ("home", "work")[min(max(callback_data.val, 0), 1)]
        place = await svc.save_place_from_order(callback.from_user.id, callback_data.oid, kind)
        await callback.answer("💾 Saqlandi! Keyingi safar bir bosishda tanlaysiz." if place else "Saqlab bo'lmadi")
        await refresh_rated(callback, svc, callback_data.oid)

    # ------------------------------------------------------------------ 📍 Manzillarim
    @router.message(F.text == "📍 Manzillarim")
    async def places_menu(message: Message, svc: TaxiService, state: FSMContext) -> None:
        await state.clear()
        p = await svc.ensure_passenger(message.from_user.id, message.from_user.first_name or "")  # type: ignore[union-attr]
        await svc.msg.send(Role.PASSENGER, message.chat.id, svc.views.places_menu(await svc.list_places(p.id)))

    @router.callback_query(PCb.filter(F.action == "addplace"))
    async def add_place(callback: CallbackQuery, callback_data: PCb, svc: TaxiService, state: FSMContext) -> None:
        from ..ui.kit import kb_button
        from ..ui.views import PLACE_ICONS, PLACE_NAMES

        kind = PLACE_KINDS[min(max(callback_data.val, 0), 2)]
        await state.set_state(PlaceAdd.waiting)
        await state.update_data(kind=kind)
        await callback.answer()
        from aiogram.types import ReplyKeyboardMarkup

        await callback.message.answer(  # type: ignore[union-attr]
            f"{PLACE_ICONS[kind]} <b>{PLACE_NAMES[kind]}</b> manzilini yuboring:\n"
            "📎 → <b>Joylashuv</b> → xaritada nuqtani belgilang, yoki hozir shu yerda bo'lsangiz — pastdagi tugma.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[kb_button("📍 Hozirgi joylashuvim", location=True)], [kb_button("❌ Bekor qilish")]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )

    @router.message(PlaceAdd.waiting, F.location | F.venue)
    async def place_location(message: Message, svc: TaxiService, state: FSMContext) -> None:
        data = await state.get_data()
        await state.clear()
        loc = message.venue.location if message.venue else message.location
        title = message.venue.title if message.venue else None
        place = await svc.save_place(message.from_user.id, data.get("kind", "other"), loc.latitude, loc.longitude, title)  # type: ignore[union-attr]
        p = await svc.get_passenger_by_tg(message.from_user.id)  # type: ignore[union-attr]
        await message.answer(
            "💾 Manzil saqlandi!" if place else "⚠️ Saqlab bo'lmadi (ko'pi bilan 5 ta qo'shimcha manzil).",
            reply_markup=svc.views.passenger_menu(),
        )
        if p:
            await svc.msg.send(Role.PASSENGER, message.chat.id, svc.views.places_menu(await svc.list_places(p.id)))

    @router.message(PlaceAdd.waiting)
    async def place_cancel(message: Message, svc: TaxiService, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=svc.views.passenger_menu())

    @router.callback_query(PCb.filter(F.action == "delplace"))
    async def del_place(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        ok = await svc.delete_place(callback.from_user.id, callback_data.oid)
        await callback.answer("🗑 O'chirildi" if ok else "Topilmadi")
        p = await svc.get_passenger_by_tg(callback.from_user.id)
        if p and isinstance(callback.message, Message):
            await svc.msg.edit(
                Role.PASSENGER,
                callback.message.chat.id,
                callback.message.message_id,
                svc.views.places_menu(await svc.list_places(p.id)),
            )

    @router.callback_query(PCb.filter(F.action == "unfav"))
    async def unfavorite(callback: CallbackQuery, callback_data: PCb, svc: TaxiService) -> None:
        ok = await svc.remove_favorite(callback.from_user.id, callback_data.oid)
        await callback.answer("💔 Sevimlilardan olib tashlandi" if ok else "Topilmadi")
        if ok and isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)

    # ------------------------------------------------------------------ menyu
    @router.message(F.text == "📋 Safarlarim")
    async def history(message: Message, svc: TaxiService) -> None:
        p = await svc.get_passenger_by_tg(message.from_user.id)  # type: ignore[union-attr]
        orders = await svc.passenger_history(p.id) if p else []
        if not orders:
            await message.answer("Hozircha safarlar yo'q. 🚕 Taksi chaqirish tugmasini bosing!")
            return
        lines = ["📋 <b>Oxirgi safarlaringiz</b>\n"]
        for o in orders:
            local = o.created_at.replace(tzinfo=UTC).astimezone(svc.tz)
            price = money(o.final_price, svc.settings.currency) if o.final_price else ""
            lines.append(
                f"<b>#{o.id}</b> · {local:%d.%m %H:%M} · {STATUS_UZ[OrderStatus(o.status)]}"
                + (f" · {price}" if price else "")
            )
        favorites = await svc.list_favorites(p.id) if p else []
        markup = None
        if favorites:
            from ..ui.kit import btn, inline

            lines.append("\n❤️ <b>Sevimli haydovchilaringiz</b> — buyurtmangizni birinchi ko'radi:")
            lines.extend(f"• {h(d.car_color)} {h(d.car_model)} · {h(d.car_plate)} · ⭐ {d.rating:.2f}" for d in favorites)
            markup = inline(
                *[btn(f"💔 {d.car_plate} — olib tashlash", cb=PCb(action="unfav", oid=d.id)) for d in favorites]
            )
        await message.answer("\n".join(lines), reply_markup=markup)

    @router.message(Command("help"))
    @router.message(F.text == "ℹ️ Yordam")
    async def help_(message: Message, svc: TaxiService) -> None:
        s = svc.settings
        phone = f"\n📞 Operator: {h(s.company_phone)}" if s.company_phone else ""
        role = "\n🔄 Rolni almashtirish: /role" if s.single_bot else ""
        await message.answer(
            f"ℹ️ <b>{h(s.company_name)} — qanday ishlaydi?</b>\n\n"
            "1️⃣ <b>🚕 Taksi chaqirish</b> — joylashuvingiz yuboriladi.\n"
            "2️⃣ Manzilni xaritada belgilang (📎 → Joylashuv) yoki manzilsiz davom eting.\n"
            "3️⃣ Narxni ko'rib, <b>Buyurtma berish</b> ni bosing.\n"
            "4️⃣ Eng yaqin bo'sh haydovchi topiladi, mashina harakatini xaritada kuzatasiz.\n"
            "5️⃣ Manzilga yetgach, <b>✅ Ha, yetib keldim</b> ni bosing va haydovchini baholang.\n\n"
            "✨ <b>Qulayliklar:</b>\n"
            "🏠 <b>📍 Manzillarim</b> — Uy/Ish manzilini saqlang, taksi 3 bosishda.\n"
            "❤️ Yoqqan haydovchini sevimlilarga qo'shing — buyurtmangizni birinchi u ko'radi.\n"
            "👤 Ota-onangiz yoki do'stingiz uchun ham buyurtma bera olasiz.\n"
            "🔒 Narx qat'iy — talab oshganda ham ko'tarilmaydi.\n\n"
            f"💰 Tarif: {h(svc.tariff.describe(s.currency))}\n"
            f"⏳ Kutish: {s.free_wait_min} daqiqa bepul, keyin {h(money(s.per_wait_min, s.currency))}/daq\n\n"
            "🔒 Raqamingiz haydovchiga ko'rinmaydi — aloqa kompaniya raqami orqali bo'ladi. "
            "Safar davomida shu yerga yozgan xabaringiz haydovchiga anonim yetkaziladi."
            + phone
            + role
        )

    # ------------------------------------------------------------------ anonim chat / izoh
    @router.message(F.voice, StateFilter(None))
    async def voice(message: Message, svc: TaxiService) -> None:
        if await svc.relay_voice(Role.PASSENGER, message.from_user.id, message.voice.file_id):  # type: ignore[union-attr]
            await ack(message)
        else:
            await message.answer("Ovozli xabar faqat safar davomida haydovchiga yetkaziladi.")

    @router.message(F.text, StateFilter(None))
    async def free_text(message: Message, svc: TaxiService) -> None:
        text = message.text or ""
        user_id = message.from_user.id  # type: ignore[union-attr]
        if await svc.relay_text(Role.PASSENGER, user_id, text):
            await ack(message)
            return
        if await svc.set_comment(user_id, text):
            await message.answer("💬 Izoh buyurtmaga qo'shildi — haydovchi ko'radi.")
            return
        p = await svc.get_passenger_by_tg(user_id)
        markup = svc.views.passenger_menu() if p and p.phone else svc.views.phone_request()
        await message.answer("🚕 Taksi chaqirish uchun pastdagi tugmani bosing.", reply_markup=markup)

    return router
