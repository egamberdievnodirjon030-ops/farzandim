"""Buyurtma holatlari bo'yicha kartalar va klaviaturalar (o'zbek tilida)."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from ..config import Settings
from ..db.models import Driver, Order, OrderStatus
from ..services.geo import compass, format_distance, format_duration
from ..services.matching import Candidate
from ..services.pricing import Tariff, money
from .kit import (
    DANGER,
    PRIMARY,
    SUCCESS,
    Card,
    DCb,
    PCb,
    View,
    btn,
    h,
    inline,
    kb_button,
    nav_url,
)


@dataclass
class Quote:
    pickup_lat: float
    pickup_lon: float
    pickup_accuracy: float | None
    dest_lat: float | None
    dest_lon: float | None
    dest_title: str | None
    distance_m: float | None
    duration_s: float | None
    price: int | None
    nearby_count: int
    nearest_eta_s: float | None
    comment: str | None = None


def car_line(d: Driver) -> str:
    return f"{d.car_color} {d.car_model}".strip()


class Views:
    def __init__(self, settings: Settings, tariff: Tariff) -> None:
        self.s = settings
        self.t = tariff

    def m(self, amount: float | None) -> str:
        return money(amount, self.s.currency)

    def taximeter_text(self) -> str:
        return f"Taksometr: {self.t.describe(self.s.currency)}"

    # =================================================================== YO'LOVCHI
    def passenger_menu(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [kb_button("🚕 Taksi chaqirish", style=SUCCESS, location=True, emoji="taxi")],
                [kb_button("📋 Safarlarim"), kb_button("ℹ️ Yordam")],
            ],
            resize_keyboard=True,
            is_persistent=True,
            input_field_placeholder="🚕 Taksi chaqirish tugmasini bosing",
        )

    def phone_request(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[[kb_button("📱 Raqamni yuborish", style=PRIMARY, contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    def destination_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [kb_button("⏭ Manzilsiz davom etish", style=PRIMARY)],
                [kb_button("❌ Bekor qilish", style=DANGER)],
            ],
            resize_keyboard=True,
            input_field_placeholder="📎 → Joylashuv → manzilni tanlang",
        )

    def passenger_welcome(self, first_name: str) -> str:
        return (
            f"Assalomu alaykum, <b>{h(first_name)}</b>! 👋\n\n"
            f"<b>{h(self.s.company_name)}</b> — shahar ichida tez va qulay taksi.\n\n"
            "🚕 <b>Taksi chaqirish</b> tugmasini bosing — joylashuvingiz yuboriladi va "
            "eng yaqin bo'sh haydovchi topiladi.\n\n"
            "🔒 Raqamingiz va shaxsiy ma'lumotlaringiz haydovchiga ko'rinmaydi."
        )

    def destination_prompt(self, accuracy: float | None) -> str:
        acc = ""
        if accuracy and accuracy > self.s.bad_accuracy_m:
            acc = (
                f"\n⚠️ Joylashuv aniqligi past (±{int(accuracy)} m). GPS ni yoqib, qaytadan "
                "yuborishingiz yoki xaritada aniq nuqtani tanlashingiz mumkin."
            )
        return (
            "✅ <b>Olish joyi qabul qilindi.</b>" + acc + "\n\n"
            "🏁 <b>Qayerga borasiz?</b>\n"
            "📎 → <b>Joylashuv</b> → xaritada manzilni belgilang va yuboring.\n\n"
            "Manzilni bilmasangiz — <b>⏭ Manzilsiz davom etish</b> (narx taksometr bo'yicha)."
        )

    def recent_destinations(self, orders: list[Order], pickup: tuple[float, float]) -> View:
        from ..services.geo import haversine_m

        buttons = []
        for o in orders:
            dist = haversine_m(pickup[0], pickup[1], o.dest_lat or 0, o.dest_lon or 0)
            title = o.dest_title or "Oldingi manzil"
            buttons.append(
                btn(f"🕘 {title[:28]} · {format_distance(dist)}", cb=PCb(action="recent", oid=o.id))
            )
        return View.plain("🕘 <b>Oxirgi manzillaringiz:</b>", inline(*buttons))

    def quote(self, q: Quote) -> View:
        card = Card("🚕 Buyurtmani tasdiqlang")
        card.map(q.pickup_lat, q.pickup_lon, "📍 Olish joyi")
        acc = f" (±{int(q.pickup_accuracy)} m)" if q.pickup_accuracy else ""
        card.row("📍 Olish joyi", "aniqlandi" + acc)
        if q.dest_lat is not None and q.distance_m is not None:
            dest = q.dest_title + " · " if q.dest_title else ""
            card.row("🏁 Manzil", f"{dest}{format_distance(q.distance_m)} · ~{format_duration(q.duration_s or 0)}")
            card.row("💰 Narx", self.m(q.price))
        else:
            card.row("🏁 Manzil", "ko'rsatilmagan")
            card.row("💰 Narx", self.taximeter_text())
        if q.nearby_count:
            eta = f" · eng yaqini ~{format_duration(q.nearest_eta_s or 60)}" if q.nearest_eta_s else ""
            card.row("🚕 Yaqin atrofda", f"{q.nearby_count} ta bo'sh mashina{eta}")
        else:
            card.row("🚕 Yaqin atrofda", "hozircha bo'sh mashina yo'q — qidiruv kengaytiriladi")
        card.row("💬 Izoh", q.comment)
        card.para("💬 Haydovchi uchun izoh qoldirish uchun shunchaki yozing (masalan: 3-podyezd oldida).")
        markup = inline(
            btn("🚕 Buyurtma berish", cb=PCb(action="confirm"), style=SUCCESS, emoji="taxi"),
            btn("❌ Bekor qilish", cb=PCb(action="draftx"), style=DANGER),
        )
        return View.of(card, markup)

    def searching(self, o: Order, radius_m: float | None, offered: int) -> View:
        card = Card("🔎 Haydovchi qidirilmoqda…")
        card.row("🧾 Buyurtma", f"#{o.id}")
        if radius_m:
            card.row("📡 Qidiruv radiusi", format_distance(radius_m))
        if offered:
            card.row("🚕 Taklif yuborildi", f"{offered} ta haydovchiga")
        card.row("💰 Narx", self.m(o.est_price) if o.est_price else "taksometr")
        card.row("💬 Izoh", o.comment)
        card.foot("Eng yaqin va reytingi yuqori haydovchilar birinchi ko'radi.")
        return View.of(card, inline(btn("❌ Bekor qilish", cb=PCb(action="cancel", oid=o.id), style=DANGER)))

    def no_drivers(self, o: Order) -> View:
        card = Card("😔 Hozircha bo'sh haydovchi topilmadi")
        card.para("Bir ozdan so'ng qayta urinib ko'ring — haydovchilar doimiy ravishda bo'shab turadi.")
        return View.of(
            card,
            inline(
                btn("🔄 Qayta qidirish", cb=PCb(action="retry", oid=o.id), style=PRIMARY),
                btn("❌ Bekor qilish", cb=PCb(action="close", oid=o.id), style=DANGER),
            ),
        )

    def _car_rows(self, card: Card, d: Driver) -> None:
        card.row("🚘 Avtomobil", car_line(d))
        card.row("🔢 Davlat raqami", d.car_plate)
        card.row("⭐ Reyting", f"{d.rating:.2f}")

    def driver_found(self, o: Order, d: Driver) -> View:
        card = Card("🚕 Haydovchi topildi!")
        self._car_rows(card, d)
        if o.pickup_eta_s:
            card.row("⏱ Yetib keladi", f"~{format_duration(o.pickup_eta_s)}")
        card.row("💰 Narx", self.m(o.est_price) if o.est_price else "taksometr")
        card.foot("Mashina harakatini quyidagi jonli xaritada kuzatishingiz mumkin.")
        return View.of(
            card,
            inline(
                btn("📞 Haydovchi bilan aloqa", cb=PCb(action="call", oid=o.id), style=PRIMARY),
                btn("❌ Bekor qilish", cb=PCb(action="cancel", oid=o.id), style=DANGER),
            ),
        )

    def driver_arrived(self, o: Order, d: Driver) -> View:
        card = Card("🚕 Haydovchi yetib keldi!")
        card.para(f"{car_line(d)} · {d.car_plate} sizni kutmoqda.")
        card.row("⏳ Bepul kutish", f"{self.s.free_wait_min} daq")
        card.row("💵 Keyin", f"{self.m(self.s.per_wait_min)}/daq")
        return View.of(
            card,
            inline(
                btn("📞 Haydovchi bilan aloqa", cb=PCb(action="call", oid=o.id), style=PRIMARY),
                btn("❌ Bekor qilish", cb=PCb(action="cancel", oid=o.id), style=DANGER),
            ),
        )

    def trip_started(self, o: Order, d: Driver) -> View:
        card = Card("🚀 Safar boshlandi — oq yo'l!")
        card.row("🚘 Avtomobil", f"{car_line(d)} · {d.car_plate}")
        card.row("💰 Narx", self.m(o.est_price) if o.est_price else self.taximeter_text())
        card.foot("Manzilga yetgach, quyidagi tugmani bosing.")
        return View.of(
            card,
            inline(
                btn("🏁 Manzilga yetib keldim", cb=PCb(action="arrive", oid=o.id), style=SUCCESS),
                btn("📞 Haydovchi bilan aloqa", cb=PCb(action="call", oid=o.id), style=PRIMARY),
            ),
        )

    def confirm_arrival(self, o: Order) -> View:
        card = Card("🏁 Manzilga yetib keldingizmi?")
        if o.trip_distance_m:
            card.row("🛣 Bosib o'tilgan yo'l", format_distance(o.trip_distance_m))
        if o.wait_charge:
            card.row("⏳ Kutish", self.m(o.wait_charge))
        card.row("💰 To'lov", self.m(o.final_price))
        card.para("Tasdiqlaganingizdan so'ng safar yakunlanadi. To'lovni haydovchiga bering.")
        return View.of(
            card,
            inline(
                btn("✅ Ha, yetib keldim", cb=PCb(action="ok", oid=o.id), style=SUCCESS),
                btn("❌ Yo'q, hali emas", cb=PCb(action="notyet", oid=o.id), style=DANGER),
            ),
        )

    def completed_passenger(self, o: Order) -> View:
        card = Card("✅ Safar yakunlandi!")
        card.row("💰 To'lov", self.m(o.final_price))
        if o.trip_distance_m:
            card.row("🛣 Masofa", format_distance(o.trip_distance_m))
        card.para("Haydovchini baholang — bu boshqa yo'lovchilarga ham yordam beradi:")
        stars = [
            btn(f"{n}⭐", cb=PCb(action="rate", oid=o.id, val=n), style=SUCCESS if n == 5 else None)
            for n in range(1, 6)
        ]
        return View.of(card, inline(stars))

    def rated(self, o: Order, stars: int) -> View:
        card = Card("🙏 Rahmat!")
        card.row("Bahoyingiz", "⭐" * stars)
        card.row("💰 To'lov", self.m(o.final_price))
        return View.of(card, inline(btn("✅ Baholandi", disabled=True)))

    def cancelled_passenger(self, o: Order, reason: str) -> View:
        card = Card("❌ Buyurtma bekor qilindi")
        card.para(reason)
        return View.of(card)

    def passenger_cancel_confirm(self, o: Order) -> View:
        card = Card("Buyurtmani bekor qilasizmi?")
        card.para("Haydovchi sizning oldingizga yo'lda.")
        return View.of(
            card,
            inline(
                [
                    btn("Ha, bekor qilish", cb=PCb(action="cancelok", oid=o.id), style=DANGER),
                    btn("Yo'q", cb=PCb(action="keep", oid=o.id), style=SUCCESS),
                ]
            ),
        )

    # =================================================================== HAYDOVCHI
    def driver_menu(self, online: bool) -> ReplyKeyboardMarkup:
        if online:
            first = [
                kb_button("📡 Jonli joylashuv")
                if self.s.require_live_location
                else kb_button("📍 Joylashuvni yangilash", location=True),
                kb_button("🔴 Liniyadan chiqish", style=DANGER),
            ]
        else:
            first = [
                kb_button(
                    "🟢 Liniyaga chiqish",
                    style=SUCCESS,
                    location=not self.s.require_live_location,
                )
            ]
        return ReplyKeyboardMarkup(
            keyboard=[
                first,
                [kb_button("💰 Balans"), kb_button("📊 Statistika")],
                [kb_button("⚙️ Sozlamalar"), kb_button("ℹ️ Yordam")],
            ],
            resize_keyboard=True,
            is_persistent=True,
        )

    def live_location_help(self) -> str:
        return (
            "📡 <b>Liniyaga chiqish uchun jonli joylashuvni ulashing:</b>\n\n"
            "1. 📎 (biriktirish) tugmasini bosing\n"
            "2. <b>Joylashuv</b> → <b>Jonli joylashuvni ulashish</b>\n"
            "3. <b>«Men o'chirmagunimcha»</b> ni tanlang\n\n"
            "Shunda buyurtmalar aynan sizga eng yaqin joydan keladi va taksometr aniq ishlaydi."
        )

    def offer(self, o: Order, c: Candidate) -> View:
        card = Card(f"🔔 Yangi buyurtma #{o.id}")
        card.row("📍 Yo'lovchigacha", f"{format_distance(c.road_m)} · ~{format_duration(c.eta_s)}")
        card.row("🧭 Yo'nalish", compass(c.bearing))
        if o.has_destination and o.est_distance_m:
            card.row("🏁 Safar", format_distance(o.est_distance_m))
            card.row("💰 Narx", self.m(o.est_price))
        else:
            card.row("🏁 Safar", "manzil ko'rsatilmagan")
            card.row("💰 Narx", "taksometr")
        card.row("💬 Izoh", o.comment)
        card.foot("Aniq manzil qabul qilgandan so'ng ochiladi.")
        return View.of(
            card,
            inline(
                btn("✅ Qabul qilish", cb=DCb(action="acc", oid=o.id), style=SUCCESS),
                btn("⏭ O'tkazib yuborish", cb=DCb(action="skip", oid=o.id)),
            ),
        )

    def offer_gone(self, o: Order) -> View:
        return View.plain(f"⌛️ Buyurtma #{o.id} boshqa haydovchi tomonidan olindi.")

    def driver_order(self, o: Order, d: Driver) -> View:
        call = btn("📞 Yo'lovchi bilan aloqa", cb=DCb(action="call", oid=o.id), style=PRIMARY)
        status = OrderStatus(o.status)
        if status == OrderStatus.ACCEPTED:
            card = Card(f"🚕 Buyurtma #{o.id} — yo'lovchi oldiga")
            card.map(o.pickup_lat, o.pickup_lon, "📍 Yo'lovchini olish joyi")
            if o.pickup_eta_s:
                card.row("⏱ Yetib borish", f"~{format_duration(o.pickup_eta_s)}")
            card.row("💰 Narx", self.m(o.est_price) if o.est_price else "taksometr")
            if o.has_destination and o.est_distance_m:
                card.row("🏁 Safar", format_distance(o.est_distance_m))
            card.row("💬 Izoh", o.comment)
            markup = inline(
                btn(
                    "📍 Yo'lovchini olish manzili",
                    url=nav_url(d.navigator, o.pickup_lat, o.pickup_lon),
                    style=SUCCESS,
                    emoji="pin",
                ),
                call,
                btn("✅ Yetib keldim", cb=DCb(action="arr", oid=o.id), style=PRIMARY),
                btn("❌ Bekor qilish", cb=DCb(action="cx", oid=o.id), style=DANGER),
            )
        elif status == OrderStatus.ARRIVED:
            card = Card(f"⏳ Buyurtma #{o.id} — yo'lovchi kutilmoqda")
            card.map(o.pickup_lat, o.pickup_lon, "📍 Olish joyi")
            card.row("⏳ Bepul kutish", f"{self.s.free_wait_min} daq, keyin {self.m(self.s.per_wait_min)}/daq")
            card.row("💬 Izoh", o.comment)
            markup = inline(
                btn("🚀 Safarni boshlash", cb=DCb(action="start", oid=o.id), style=SUCCESS),
                call,
                btn("🚫 Yo'lovchi chiqmadi", cb=DCb(action="noshow", oid=o.id), style=DANGER),
            )
        elif status == OrderStatus.IN_PROGRESS:
            card = Card(f"🚀 Buyurtma #{o.id} — safar davom etmoqda")
            if o.has_destination:
                card.map(o.dest_lat, o.dest_lon, "🏁 Manzil")  # type: ignore[arg-type]
                card.row("💰 Narx", self.m(o.est_price))
            else:
                card.row("💰 Narx", self.taximeter_text())
            nav = (
                btn(
                    "🏁 Manzilga yo'l",
                    url=nav_url(d.navigator, o.dest_lat, o.dest_lon),  # type: ignore[arg-type]
                    style=PRIMARY,
                )
                if o.has_destination
                else None
            )
            markup = inline(
                nav,
                call,
                btn("🏁 Safarni yakunlash", cb=DCb(action="fin", oid=o.id), style=SUCCESS),
            )
        elif status == OrderStatus.FINISHING:
            card = Card(f"⏳ Buyurtma #{o.id} — yo'lovchi tasdig'i kutilmoqda")
            if o.trip_distance_m:
                card.row("🛣 Masofa", format_distance(o.trip_distance_m))
            if o.wait_charge:
                card.row("⏳ Kutish", self.m(o.wait_charge))
            card.row("💰 To'lov", self.m(o.final_price))
            if self.s.finish_confirm_timeout_min:
                card.foot(
                    f"Yo'lovchi {int(self.s.finish_confirm_timeout_min)} daqiqa ichida javob bermasa, "
                    "safar avtomatik yakunlanadi."
                )
            markup = inline(btn("⏳ Tasdiq kutilmoqda…", disabled=True), call)
        elif status == OrderStatus.COMPLETED:
            card = Card(f"✅ Buyurtma #{o.id} yakunlandi")
            card.row("💰 To'lov", self.m(o.final_price))
            card.row(f"🧾 Xizmat haqi ({self.s.commission_percent:g}%)", self.m(o.commission))
            card.row("💳 Balans", self.m(d.balance))
            if o.auto_completed:
                card.foot("Yo'lovchi javob bermagani uchun avtomatik yakunlandi.")
            markup = None
        else:
            card = Card(f"❌ Buyurtma #{o.id} bekor qilindi")
            markup = None
        return View.of(card, markup)

    def driver_cancel_confirm(self, o: Order) -> View:
        card = Card(f"Buyurtma #{o.id} ni bekor qilasizmi?")
        card.para("Yo'lovchi uchun boshqa haydovchi qidiriladi.")
        return View.of(
            card,
            inline(
                [
                    btn("Ha, bekor qilish", cb=DCb(action="cxok", oid=o.id), style=DANGER),
                    btn("Yo'q", cb=DCb(action="cxno", oid=o.id), style=SUCCESS),
                ]
            ),
        )

    def driver_balance(self, d: Driver, payments: bool) -> View:
        card = Card("💰 Balans")
        card.row("💳 Joriy balans", self.m(d.balance))
        card.row("🧾 Xizmat haqi", f"har bir safardan {self.s.commission_percent:g}%")
        card.row("⚠️ Minimal balans", self.m(self.s.min_driver_balance))
        card.row("🆔 Sizning ID", str(d.id))
        rows = []
        if payments:
            rows.append(
                [
                    btn(f"+{self.m(a)}", cb=DCb(action="topup", val=a), style=SUCCESS)
                    for a in self.s.topup_amounts[:3]
                ]
            )
        else:
            card.para(self.s.payment_instructions)
        rows.append(btn("📋 ID ni nusxalash", copy=str(d.id)))
        return View.of(card, inline(*rows))


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
