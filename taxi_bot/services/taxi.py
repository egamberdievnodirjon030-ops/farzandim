"""Taksi xizmatining asosiy biznes-logikasi.

Barcha holat o'zgarishlari shartli (atomik) `UPDATE ... WHERE status = ...` orqali bajariladi,
shuning uchun bir vaqtda bosilgan tugmalar (masalan, ikki haydovchi bir buyurtmani qabul qilsa)
hech qachon ziddiyatga olib kelmaydi — faqat bittasi muvaffaqiyatli bo'ladi.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select, update

from ..config import Settings
from ..db import Database
from ..db.models import (
    DRIVER_ACTIVE_STATUSES,
    Driver,
    DriverStatus,
    FavoriteDriver,
    OfferStatus,
    Order,
    OrderOffer,
    OrderStatus,
    Passenger,
    Transaction,
    utcnow,
)
from ..ui.kit import DANGER, SUCCESS, ACb, Card, View, btn, h, inline
from ..ui.messenger import EFFECT_PARTY, Messenger, Role
from ..ui.views import Quote, Views
from .dispatch import DispatchEngine
from .features import FeaturesMixin
from .geo import Point, bearing_deg, bounding_box, haversine_m
from .matching import Candidate, bayesian_rating, home_gain
from .pricing import Tariff
from .routing import RoutingService
from .telephony import TelephonyService, normalize_phone

log = logging.getLogger(__name__)

LIVE_EDIT_INTERVAL = 4.0  # yo'lovchidagi jonli xaritani yangilash oralig'i (s)
TRACK_MIN_SEGMENT_M = 15.0
TRACK_MAX_ACCURACY_M = 100.0
TRACK_MAX_SPEED_KMH = 160.0


class _Abort(Exception):
    """Tranzaksiyani bekor qilish (rollback) uchun."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class LocationResult:
    went_online: bool = False
    low_balance: bool = False
    ignored: str | None = None  # not_driver | not_approved | need_live


@dataclass
class ActionResult:
    ok: bool
    reason: str = ""


def _upd(model):
    return update(model).execution_options(synchronize_session=False)


class TaxiService(FeaturesMixin):
    def __init__(
        self,
        settings: Settings,
        db: Database,
        messenger: Messenger,
        routing: RoutingService | None = None,
        telephony: TelephonyService | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.msg = messenger
        self.tariff = Tariff.from_settings(settings)
        self.views = Views(settings, self.tariff)
        self.routing = routing or RoutingService(
            settings.osrm_url, settings.road_factor, settings.city_speed_kmh
        )
        self.telephony = telephony or TelephonyService(settings)
        self.dispatch = DispatchEngine(self)
        self.tz = ZoneInfo("Asia/Tashkent")
        self._locks: dict[int, asyncio.Lock] = {}
        self._live_edit_at: dict[int, float] = {}
        self._call_at: dict[tuple[int, str], float] = {}

    # ======================================================================== yordamchi
    def _lock(self, order_id: int) -> asyncio.Lock:
        lock = self._locks.get(order_id)
        if lock is None:
            lock = self._locks[order_id] = asyncio.Lock()
        return lock

    def _forget(self, order_id: int) -> None:
        self._locks.pop(order_id, None)
        self._live_edit_at.pop(order_id, None)
        self._call_at.pop((order_id, "driver"), None)
        self._call_at.pop((order_id, "passenger"), None)

    async def get_order(self, order_id: int) -> Order | None:
        async with self.db.session() as s:
            return await s.get(Order, order_id)

    async def get_driver_by_tg(self, tg_id: int) -> Driver | None:
        async with self.db.session() as s:
            return await s.scalar(select(Driver).where(Driver.tg_id == tg_id))

    async def get_driver(self, driver_id: int) -> Driver | None:
        async with self.db.session() as s:
            return await s.get(Driver, driver_id)

    async def get_passenger_by_tg(self, tg_id: int) -> Passenger | None:
        async with self.db.session() as s:
            return await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))

    async def _order_bundle(self, order_id: int) -> tuple[Order, Passenger, Driver | None] | None:
        async with self.db.session() as s:
            order = await s.get(Order, order_id)
            if order is None:
                return None
            passenger = await s.get(Passenger, order.passenger_id)
            driver = await s.get(Driver, order.driver_id) if order.driver_id else None
            return order, passenger, driver  # type: ignore[return-value]

    async def _set_order_fields(self, order_id: int, **values) -> None:
        async with self.db.session() as s:
            await s.execute(_upd(Order).where(Order.id == order_id).values(**values))

    def _driver_location_fresh(self, d: Driver) -> bool:
        return (
            d.lat is not None
            and d.lon is not None
            and d.loc_valid_until is not None
            and d.loc_valid_until > utcnow()
        )

    # ======================================================================== yo'lovchi
    async def ensure_passenger(self, tg_id: int, first_name: str) -> Passenger:
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
            if p is None:
                p = Passenger(tg_id=tg_id, first_name=first_name[:128])
                s.add(p)
                await s.flush()
            elif first_name and p.first_name != first_name:
                p.first_name = first_name[:128]
            return p

    async def set_passenger_phone(self, tg_id: int, phone: str) -> Passenger | None:
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
            if p is not None:
                p.phone = normalize_phone(phone)
            return p

    async def active_order(self, passenger_id: int) -> Order | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(Order)
                .where(
                    Order.passenger_id == passenger_id,
                    Order.status.in_(
                        [
                            OrderStatus.SEARCHING,
                            OrderStatus.ACCEPTED,
                            OrderStatus.ARRIVED,
                            OrderStatus.IN_PROGRESS,
                            OrderStatus.FINISHING,
                        ]
                    ),
                )
                .order_by(Order.id.desc())
                .limit(1)
            )

    async def recent_destinations(self, passenger_id: int, limit: int = 3) -> list[Order]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(Order)
                    .where(
                        Order.passenger_id == passenger_id,
                        Order.status == OrderStatus.COMPLETED,
                        Order.dest_lat.is_not(None),
                    )
                    .order_by(Order.id.desc())
                    .limit(20)
                )
            ).all()
        seen: set[tuple[float, float]] = set()
        result: list[Order] = []
        for o in rows:
            key = (round(o.dest_lat or 0, 3), round(o.dest_lon or 0, 3))
            if key in seen:
                continue
            seen.add(key)
            result.append(o)
            if len(result) >= limit:
                break
        return result

    async def passenger_history(self, passenger_id: int, limit: int = 5) -> list[Order]:
        async with self.db.session() as s:
            return list(
                (
                    await s.scalars(
                        select(Order)
                        .where(Order.passenger_id == passenger_id)
                        .order_by(Order.id.desc())
                        .limit(limit)
                    )
                ).all()
            )

    async def build_quote(
        self,
        pickup_lat: float,
        pickup_lon: float,
        accuracy: float | None,
        dest_lat: float | None = None,
        dest_lon: float | None = None,
        dest_title: str | None = None,
        comment: str | None = None,
    ) -> Quote:
        pickup = Point(pickup_lat, pickup_lon)
        distance = duration = price = None
        if dest_lat is not None and dest_lon is not None:
            route = await self.routing.route(pickup, Point(dest_lat, dest_lon))
            distance, duration = route.distance_m, route.duration_s
            price = self.tariff.ride_price(route.distance_m)
        nearby = await self._nearby(pickup, self.settings.wave_radii_km[-1] * 1000)
        nearest = min((c.eta_s for c in nearby), default=None)
        return Quote(
            pickup_lat=pickup_lat,
            pickup_lon=pickup_lon,
            pickup_accuracy=accuracy,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            dest_title=dest_title,
            distance_m=distance,
            duration_s=duration,
            price=price,
            nearby_count=len(nearby),
            nearest_eta_s=nearest,
            comment=comment,
        )

    async def create_order(
        self, passenger_tg: int, q: Quote, card_message_id: int | None = None
    ) -> Order | None:
        """Buyurtma yaratadi va qidiruvni boshlaydi. Faol buyurtma bo'lsa — None."""
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == passenger_tg))
            if p is None or p.is_blocked:
                return None
            existing = await s.scalar(
                select(Order.id).where(
                    Order.passenger_id == p.id,
                    Order.status.in_(
                        [
                            OrderStatus.SEARCHING,
                            OrderStatus.ACCEPTED,
                            OrderStatus.ARRIVED,
                            OrderStatus.IN_PROGRESS,
                            OrderStatus.FINISHING,
                        ]
                    ),
                )
            )
            if existing:
                return None
            now = utcnow()
            order = Order(
                passenger_id=p.id,
                status=OrderStatus.SEARCHING,
                pickup_lat=q.pickup_lat,
                pickup_lon=q.pickup_lon,
                pickup_accuracy=q.pickup_accuracy,
                dest_lat=q.dest_lat,
                dest_lon=q.dest_lon,
                dest_title=q.dest_title,
                comment=q.comment,
                est_distance_m=int(q.distance_m) if q.distance_m is not None else None,
                est_duration_s=int(q.duration_s) if q.duration_s is not None else None,
                est_price=q.price,
                rider_phone=q.rider_phone,
                created_at=now,
                search_started_at=now,
            )
            s.add(order)
            await s.flush()

        view = self.views.searching(order, None, 0)
        msg_id = None
        if card_message_id and await self.msg.edit(Role.PASSENGER, passenger_tg, card_message_id, view):
            msg_id = card_message_id
        else:
            msg_id = await self.msg.send(Role.PASSENGER, passenger_tg, view)
        if msg_id:
            await self._set_order_fields(order.id, passenger_msg_id=msg_id)
            order.passenger_msg_id = msg_id
        self.dispatch.start(order.id)
        return order

    async def set_comment(self, passenger_tg: int, text: str) -> Order | None:
        """Qidiruv yoki yo'ldagi buyurtmaga izoh qo'shadi."""
        p = await self.get_passenger_by_tg(passenger_tg)
        if p is None:
            return None
        order = await self.active_order(p.id)
        if order is None or order.status != OrderStatus.SEARCHING:
            return None
        comment = text.strip()[:300]
        await self._set_order_fields(order.id, comment=comment)
        order.comment = comment
        async with self._lock(order.id):
            fresh = await self.get_order(order.id)
            if fresh and fresh.status == OrderStatus.SEARCHING:
                await self.msg.edit(
                    Role.PASSENGER,
                    passenger_tg,
                    fresh.passenger_msg_id,
                    self.views.searching(fresh, None, await self._offered_count(fresh)),
                )
        return order

    async def passenger_cancel(self, passenger_tg: int, order_id: int, confirmed: bool) -> str:
        """Natija: cancelled | confirm | too_late | not_found."""
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg:
            return "not_found"
        order, passenger, driver = bundle
        status = OrderStatus(order.status)
        if status in (OrderStatus.IN_PROGRESS, OrderStatus.FINISHING):
            return "too_late"
        if status in (OrderStatus.ACCEPTED, OrderStatus.ARRIVED) and not confirmed:
            return "confirm"
        if status not in (
            OrderStatus.SEARCHING,
            OrderStatus.NO_DRIVERS,
            OrderStatus.ACCEPTED,
            OrderStatus.ARRIVED,
        ):
            return "not_found"

        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == status)
                    .values(
                        status=OrderStatus.CANCELLED,
                        cancelled_by="passenger",
                        cancel_reason="passenger",
                        cancelled_at=utcnow(),
                    )
                )
                if res.rowcount != 1:
                    return "not_found"
                if driver is not None:
                    await s.execute(
                        _upd(Driver)
                        .where(Driver.id == driver.id, Driver.current_order_id == order_id)
                        .values(current_order_id=None)
                    )
            self.dispatch.wake(order_id)
            await self._withdraw_offers(order_id)
            order.status = OrderStatus.CANCELLED
            await self.msg.edit(
                Role.PASSENGER,
                passenger_tg,
                order.passenger_msg_id,
                self.views.cancelled_passenger(order, "Siz buyurtmani bekor qildingiz."),
            )
            await self._drop_live(order, passenger)
            await self._watchers_status(order_id, "❌ Safar bekor qilindi.", final=True)
            if driver is not None:
                card = Card(f"❌ Buyurtma #{order_id} bekor qilindi")
                card.para("Yo'lovchi buyurtmani bekor qildi. Siz yana yangi buyurtmalarni qabul qilasiz.")
                await self.msg.replace(
                    Role.DRIVER, driver.tg_id, order.driver_msg_id, View.of(card)
                )
        self._forget(order_id)
        return "cancelled"

    async def retry_search(self, passenger_tg: int, order_id: int) -> bool:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg:
            return False
        order, _passenger, _ = bundle
        async with self.db.session() as s:
            res = await s.execute(
                _upd(Order)
                .where(Order.id == order_id, Order.status == OrderStatus.NO_DRIVERS)
                .values(
                    status=OrderStatus.SEARCHING,
                    search_round=Order.search_round + 1,
                    search_started_at=utcnow(),
                    wave=0,
                )
            )
            if res.rowcount != 1:
                return False
        order = await self.get_order(order_id)
        await self.msg.edit(
            Role.PASSENGER, passenger_tg, order.passenger_msg_id, self.views.searching(order, None, 0)
        )
        self.dispatch.start(order_id)
        return True

    async def passenger_confirm_arrival(self, passenger_tg: int, order_id: int) -> bool:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg:
            return False
        order, _, driver = bundle
        if driver is None or order.status not in (OrderStatus.IN_PROGRESS, OrderStatus.FINISHING):
            return False
        return await self._complete(order_id, auto=False)

    async def passenger_not_yet(self, passenger_tg: int, order_id: int) -> bool:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg:
            return False
        order, _passenger, driver = bundle
        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == OrderStatus.FINISHING)
                    .values(
                        status=OrderStatus.IN_PROGRESS,
                        finish_requested_at=None,
                        final_price=None,
                        wait_charge=None,
                    )
                )
                if res.rowcount != 1:
                    return False
            order = await self.get_order(order_id)
            if driver is not None:
                await self.msg.edit(
                    Role.PASSENGER,
                    passenger_tg,
                    order.passenger_msg_id,
                    self.views.trip_started(order, driver, self.share_url(order)),
                )
                new_id = await self.msg.replace(
                    Role.DRIVER,
                    driver.tg_id,
                    order.driver_msg_id,
                    self.views.driver_order(order, driver),
                )
                await self._set_order_fields(order_id, driver_msg_id=new_id)
                await self.msg.send(
                    Role.DRIVER,
                    driver.tg_id,
                    View.plain("ℹ️ Yo'lovchi hali manzilga yetmaganini bildirdi. Safar davom etmoqda."),
                    silent=True,
                )
        return True

    async def rate(self, passenger_tg: int, order_id: int, stars: int) -> Order | None:
        stars = max(1, min(5, stars))
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == passenger_tg))
            if p is None:
                return None
            res = await s.execute(
                _upd(Order)
                .where(
                    Order.id == order_id,
                    Order.passenger_id == p.id,
                    Order.status == OrderStatus.COMPLETED,
                    Order.rating.is_(None),
                )
                .values(rating=stars)
            )
            if res.rowcount != 1:
                return None
            order = await s.get(Order, order_id, populate_existing=True)
            await s.execute(
                _upd(Driver)
                .where(Driver.id == order.driver_id)
                .values(
                    rating_sum=Driver.rating_sum + stars,
                    rating_count=Driver.rating_count + 1,
                )
            )
            d = await s.get(Driver, order.driver_id, populate_existing=True)
            d.rating = bayesian_rating(
                d.rating_sum, d.rating_count, self.settings.rating_prior, self.settings.rating_prior_weight
            )
            return order

    # ======================================================================== haydovchi
    async def register_driver(
        self,
        tg_id: int,
        full_name: str,
        phone: str,
        car_model: str,
        car_color: str,
        car_plate: str,
    ) -> Driver:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is None:
                d = Driver(tg_id=tg_id, rating=self.settings.rating_prior)
                s.add(d)
            d.full_name = full_name[:128]
            d.phone = normalize_phone(phone)
            d.car_model = car_model[:64]
            d.car_color = car_color[:32]
            d.car_plate = car_plate[:16]
            if d.status != DriverStatus.APPROVED:
                d.status = DriverStatus.PENDING
            await s.flush()
        card = Card("🆕 Yangi haydovchi arizasi")
        card.row("🆔 ID", str(d.id)).row("👤 F.I.Sh", d.full_name).row("📱 Telefon", d.phone or "—")
        card.row("🚘 Avtomobil", f"{d.car_color} {d.car_model}").row("🔢 Raqam", d.car_plate)
        await self.msg.notify_admins(
            View.of(
                card,
                inline(
                    [
                        btn("✅ Tasdiqlash", cb=ACb(action="ok", id=d.id), style=SUCCESS),
                        btn("❌ Rad etish", cb=ACb(action="no", id=d.id), style=DANGER),
                    ]
                ),
            )
        )
        return d

    async def set_driver_status(self, driver_id: int, status: DriverStatus) -> Driver | None:
        async with self.db.session() as s:
            d = await s.get(Driver, driver_id)
            if d is None:
                return None
            previous = d.status
            d.status = status
            if status != DriverStatus.APPROVED:
                d.is_online = False
            bonus = (
                status == DriverStatus.APPROVED
                and previous == DriverStatus.PENDING
                and self.settings.welcome_bonus > 0
                and d.trips_count == 0
                and d.balance == 0
            )
        if bonus:
            d = await self.adjust_balance(driver_id, self.settings.welcome_bonus, "bonus", "Xush kelibsiz bonusi") or d
        if status != DriverStatus.APPROVED:
            await self._withdraw_driver_offers(driver_id)
        return d

    async def set_navigator(self, tg_id: int, navigator: str) -> None:
        async with self.db.session() as s:
            await s.execute(_upd(Driver).where(Driver.tg_id == tg_id).values(navigator=navigator))

    async def update_driver_location(
        self,
        tg_id: int,
        lat: float,
        lon: float,
        *,
        accuracy: float | None = None,
        heading: int | None = None,
        is_live: bool = False,
        live_until: datetime | None = None,
    ) -> LocationResult:
        s_ = self.settings
        now = utcnow()
        result = LocationResult()
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is None:
                return LocationResult(ignored="not_driver")
            if d.status != DriverStatus.APPROVED:
                return LocationResult(ignored="not_approved")
            if s_.require_live_location and not is_live and d.current_order_id is None:
                # Jonli joylashuv to'xtatildi yoki oddiy nuqta yuborildi
                if d.loc_is_live:
                    d.loc_is_live = False
                    d.loc_valid_until = now
                return LocationResult(ignored="need_live")
            if is_live:
                idle_until = now + timedelta(minutes=s_.live_location_idle_ttl_min)
                valid_until = min(live_until, idle_until) if live_until else idle_until
            else:
                valid_until = now + timedelta(minutes=s_.static_location_ttl_min)
            d.lat, d.lon = lat, lon
            d.loc_accuracy = accuracy
            d.loc_heading = heading
            d.loc_is_live = is_live
            d.loc_updated_at = now
            d.loc_valid_until = valid_until
            d.loc_reminded = False
            if not d.is_online:
                if d.balance >= s_.min_driver_balance:
                    d.is_online = True
                    result.went_online = True
                else:
                    result.low_balance = True
            active_order_id = d.current_order_id
            driver_snapshot = d
        if active_order_id:
            await self._on_active_location(driver_snapshot, active_order_id, lat, lon, accuracy, heading)
        return result

    async def driver_go_online(self, tg_id: int) -> str:
        """Natija: online | need_location | low_balance | not_approved | not_driver."""
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is None:
                return "not_driver"
            if d.status != DriverStatus.APPROVED:
                return "not_approved"
            if d.balance < self.settings.min_driver_balance:
                return "low_balance"
            fresh = self._driver_location_fresh(d) and (
                d.loc_is_live or not self.settings.require_live_location
            )
            if not fresh:
                return "need_location"
            d.is_online = True
            return "online"

    async def driver_offline(self, tg_id: int) -> bool:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is None:
                return False
            d.is_online = False
            driver_id = d.id
        await self._withdraw_driver_offers(driver_id)
        return True

    async def _on_active_location(
        self,
        d: Driver,
        order_id: int,
        lat: float,
        lon: float,
        accuracy: float | None,
        heading: int | None,
    ) -> None:
        bundle = await self._order_bundle(order_id)
        if bundle is None:
            return
        order, passenger, _ = bundle
        if order.status not in DRIVER_ACTIVE_STATUSES:
            return
        now = utcnow()
        # Taksometr: bosib o'tilgan yo'lni yig'ish (GPS shovqini va sakrashlar filtrlanadi)
        if order.status == OrderStatus.IN_PROGRESS:
            async with self._lock(order_id):
                fresh = await self.get_order(order_id)
                if fresh is not None and fresh.status == OrderStatus.IN_PROGRESS:
                    values = self._track_step(fresh, lat, lon, accuracy, now)
                    if values:
                        await self._set_order_fields(order_id, **values)
        # Yo'lovchidagi va yaqinlaridagi jonli xarita (Telegram limitlari uchun siyraklashtirilgan)
        loop_now = time.monotonic()
        if loop_now - self._live_edit_at.get(order_id, 0.0) >= LIVE_EDIT_INTERVAL:
            self._live_edit_at[order_id] = loop_now
            if order.passenger_live_msg_id:
                await self.msg.edit_live_location(
                    Role.PASSENGER, passenger.tg_id, order.passenger_live_msg_id, lat, lon, heading
                )
            await self._watchers_live(order_id, lat, lon, heading)
        if not order.passenger_live_msg_id and order.status in (OrderStatus.ACCEPTED, OrderStatus.ARRIVED):
            async with self._lock(order_id):
                fresh = await self.get_order(order_id)
                if fresh and not fresh.passenger_live_msg_id and fresh.status in DRIVER_ACTIVE_STATUSES:
                    live_id = await self.msg.send_live_location(
                        Role.PASSENGER, passenger.tg_id, lat, lon, heading
                    )
                    if live_id:
                        await self._set_order_fields(order_id, passenger_live_msg_id=live_id)
        # Yaqinlashish xabari va GPS bo'yicha avtomatik "Yetib keldim"
        if order.status == OrderStatus.ACCEPTED:
            s_ = self.settings
            dist = haversine_m(lat, lon, order.pickup_lat, order.pickup_lon)
            if (
                s_.auto_arrive_radius_m > 0
                and dist <= s_.auto_arrive_radius_m
                and (accuracy is None or accuracy <= 50)
            ):
                await self.driver_arrived(d.tg_id, order_id, auto=True)
            elif dist <= s_.near_notify_radius_m and not order.near_notified:
                async with self.db.session() as s:
                    res = await s.execute(
                        _upd(Order)
                        .where(Order.id == order_id, Order.near_notified.is_(False))
                        .values(near_notified=True)
                    )
                if res.rowcount == 1:
                    await self.msg.send(Role.PASSENGER, passenger.tg_id, self.views.near_alert(order, d, dist))

    @staticmethod
    def _track_step(order: Order, lat: float, lon: float, accuracy: float | None, now: datetime) -> dict:
        if order.track_lat is None or order.track_lon is None:
            return {"track_lat": lat, "track_lon": lon, "track_at": now}
        if accuracy is not None and accuracy > TRACK_MAX_ACCURACY_M:
            return {}
        seg = haversine_m(order.track_lat, order.track_lon, lat, lon)
        if seg < TRACK_MIN_SEGMENT_M:
            return {}
        dt = max(1.0, (now - (order.track_at or now)).total_seconds())
        if seg / dt * 3.6 > TRACK_MAX_SPEED_KMH:
            return {"track_lat": lat, "track_lon": lon, "track_at": now}  # sakrash — hisoblanmaydi
        return {
            "trip_distance_m": (order.trip_distance_m or 0.0) + seg,
            "track_lat": lat,
            "track_lon": lon,
            "track_at": now,
        }

    # -------------------------------------------------------------- qidiruv (dispatch)
    def _candidate_query(self, lat: float, lon: float, radius_m: float) -> Select:
        min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius_m)
        return select(Driver).where(
            Driver.status == DriverStatus.APPROVED,
            Driver.is_online.is_(True),
            Driver.current_order_id.is_(None),
            Driver.loc_valid_until > utcnow(),
            Driver.balance >= self.settings.min_driver_balance,
            Driver.lat.between(min_lat, max_lat),
            Driver.lon.between(min_lon, max_lon),
        )

    async def _to_candidates(
        self,
        drivers: Sequence[Driver],
        pickup: Point,
        radius_m: float,
        *,
        favorites: set[int] | None = None,
        order: Order | None = None,
    ) -> list[Candidate]:
        favorites = favorites or set()
        near: list[tuple[Driver, float, bool]] = []
        for d in drivers:
            dist = haversine_m(d.lat, d.lon, pickup.lat, pickup.lon)  # type: ignore[arg-type]
            if dist > radius_m:
                continue
            home_bound = False
            if d.home_mode and d.home_lat is not None and d.home_lon is not None:
                # 🏡 "Uyga" rejimi: faqat uy tomonga olib boradigan, manzili ma'lum buyurtmalar
                if order is None or not order.has_destination:
                    continue
                gain = home_gain(d.lat, d.lon, d.home_lat, d.home_lon, order.dest_lat, order.dest_lon)  # type: ignore[arg-type]
                if gain < self.settings.home_mode_min_gain:
                    continue
                home_bound = True
            near.append((d, dist, home_bound))
        if not near:
            return []
        routes = await self.routing.many_to_one([Point(d.lat, d.lon) for d, _, _ in near], pickup)  # type: ignore[arg-type]
        return [
            Candidate(
                driver_id=d.id,
                tg_id=d.tg_id,
                rating=d.rating,
                straight_m=dist,
                road_m=r.distance_m,
                eta_s=r.duration_s,
                precise=r.precise,
                bearing=bearing_deg(d.lat, d.lon, pickup.lat, pickup.lon),  # type: ignore[arg-type]
                accuracy_m=d.loc_accuracy,
                auto_accept=bool(d.auto_accept),
                favorite=d.id in favorites,
                home_bound=home_bound,
            )
            for (d, dist, home_bound), r in zip(near, routes, strict=True)
        ]

    async def _nearby(self, pickup: Point, radius_m: float) -> list[Candidate]:
        async with self.db.session() as s:
            drivers = (
                await s.scalars(
                    self._candidate_query(pickup.lat, pickup.lon, radius_m).where(Driver.home_mode.is_(False))
                )
            ).all()
        return await self._to_candidates(drivers, pickup, radius_m)

    async def find_candidates(
        self, order: Order, radius_m: float, *, favorites_only: bool = False
    ) -> list[Candidate]:
        """Buyurtma uchun hali taklif olmagan bo'sh haydovchilar."""
        async with self.db.session() as s:
            passenger_tg = await s.scalar(select(Passenger.tg_id).where(Passenger.id == order.passenger_id))
            favorites = set(
                (
                    await s.scalars(
                        select(FavoriteDriver.driver_id).where(FavoriteDriver.passenger_id == order.passenger_id)
                    )
                ).all()
            )
            if favorites_only and not favorites:
                return []
            excluded = select(OrderOffer.driver_id).where(
                OrderOffer.order_id == order.id,
                or_(
                    OrderOffer.search_round == order.search_round,
                    OrderOffer.status.in_([OfferStatus.DECLINED, OfferStatus.DRIVER_CANCELLED]),
                ),
            )
            q = self._candidate_query(order.pickup_lat, order.pickup_lon, radius_m).where(
                Driver.id.not_in(excluded), Driver.tg_id != passenger_tg
            )
            if favorites_only:
                q = q.where(Driver.id.in_(favorites))
            drivers = (await s.scalars(q)).all()
        return await self._to_candidates(
            drivers, Point(order.pickup_lat, order.pickup_lon), radius_m, favorites=favorites, order=order
        )

    async def auto_assign(self, order: Order, c: Candidate) -> bool:
        """⚡ Avto-qabul: buyurtma haydovchiga bosishsiz biriktiriladi."""
        async with self.db.session() as s:
            d = await s.get(Driver, c.driver_id)
            o = await s.get(Order, order.id)
            if (
                d is None
                or o is None
                or not d.auto_accept
                or d.current_order_id is not None
                or o.status != OrderStatus.SEARCHING
                or o.search_round != order.search_round
            ):
                return False
            offer = OrderOffer(
                order_id=o.id,
                driver_id=d.id,
                search_round=o.search_round,
                wave=o.wave,
                distance_m=int(c.road_m),
                eta_s=int(c.eta_s),
            )
            s.add(offer)
            await s.flush()
            offer_id = offer.id
        result = await self.accept_offer(c.tg_id, order.id, None, auto=True)
        if not result.ok:
            async with self.db.session() as s:
                await s.execute(
                    _upd(OrderOffer)
                    .where(OrderOffer.id == offer_id, OrderOffer.status == OfferStatus.SENT)
                    .values(status=OfferStatus.WITHDRAWN)
                )
        return result.ok

    async def send_offers(self, order: Order, candidates: list[Candidate], wave: int) -> list[int]:
        sem = asyncio.Semaphore(max(1, self.settings.max_offer_concurrency))

        async def offer_one(c: Candidate) -> int | None:
            async with sem:
                async with self.db.session() as s:
                    d = await s.get(Driver, c.driver_id)
                    o = await s.get(Order, order.id)
                    if (
                        d is None
                        or o is None
                        or d.current_order_id is not None
                        or not d.is_online
                        or o.status != OrderStatus.SEARCHING
                        or o.search_round != order.search_round
                    ):
                        return None
                    offer = OrderOffer(
                        order_id=o.id,
                        driver_id=d.id,
                        search_round=o.search_round,
                        wave=wave,
                        distance_m=int(c.road_m),
                        eta_s=int(c.eta_s),
                    )
                    s.add(offer)
                    await s.flush()
                    offer_id = offer.id
                message_id = await self.msg.send(Role.DRIVER, c.tg_id, self.views.offer(o, c))
                async with self.db.session() as s:
                    current = await s.get(Order, order.id)
                    still_open = (
                        current is not None
                        and current.status == OrderStatus.SEARCHING
                        and current.search_round == order.search_round
                    )
                    await s.execute(
                        _upd(OrderOffer)
                        .where(OrderOffer.id == offer_id, OrderOffer.status == OfferStatus.SENT)
                        .values(
                            message_id=message_id,
                            status=OfferStatus.SENT if (message_id and still_open) else OfferStatus.WITHDRAWN,
                        )
                    )
                if message_id and not still_open:
                    await self.msg.delete(Role.DRIVER, c.tg_id, message_id)
                    return None
                return c.driver_id if message_id else None

        results = await asyncio.gather(*(offer_one(c) for c in candidates))
        return [r for r in results if r is not None]

    async def all_declined(self, order_id: int, search_round: int, driver_ids: list[int]) -> bool:
        async with self.db.session() as s:
            pending = await s.scalar(
                select(func.count(OrderOffer.id)).where(
                    OrderOffer.order_id == order_id,
                    OrderOffer.search_round == search_round,
                    OrderOffer.driver_id.in_(driver_ids),
                    OrderOffer.status == OfferStatus.SENT,
                )
            )
        return not pending

    async def _offered_count(self, order: Order) -> int:
        async with self.db.session() as s:
            return int(
                await s.scalar(
                    select(func.count(OrderOffer.id)).where(
                        OrderOffer.order_id == order.id,
                        OrderOffer.search_round == order.search_round,
                    )
                )
                or 0
            )

    async def on_search_progress(self, order_id: int, wave: int, radius_m: float) -> None:
        async with self._lock(order_id):
            bundle = await self._order_bundle(order_id)
            if bundle is None:
                return
            order, passenger, _ = bundle
            if order.status != OrderStatus.SEARCHING:
                return
            await self._set_order_fields(order_id, wave=wave)
            await self.msg.edit(
                Role.PASSENGER,
                passenger.tg_id,
                order.passenger_msg_id,
                self.views.searching(order, radius_m, await self._offered_count(order)),
            )

    async def on_search_failed(self, order_id: int, search_round: int | None) -> None:
        async with self._lock(order_id):
            async with self.db.session() as s:
                cond = [Order.id == order_id, Order.status == OrderStatus.SEARCHING]
                if search_round is not None:
                    cond.append(Order.search_round == search_round)
                res = await s.execute(_upd(Order).where(*cond).values(status=OrderStatus.NO_DRIVERS))
                if res.rowcount != 1:
                    return
            await self._withdraw_offers(order_id)
            bundle = await self._order_bundle(order_id)
            if bundle is None:
                return
            order, passenger, _ = bundle
            new_id = await self.msg.replace(
                Role.PASSENGER, passenger.tg_id, order.passenger_msg_id, self.views.no_drivers(order)
            )
            await self._set_order_fields(order_id, passenger_msg_id=new_id)

    async def _withdraw_offers(self, order_id: int, keep_driver_id: int | None = None) -> None:
        async with self.db.session() as s:
            q = (
                select(OrderOffer, Driver.tg_id)
                .join(Driver, Driver.id == OrderOffer.driver_id)
                .where(OrderOffer.order_id == order_id, OrderOffer.status == OfferStatus.SENT)
            )
            if keep_driver_id is not None:
                q = q.where(OrderOffer.driver_id != keep_driver_id)
            rows = (await s.execute(q)).all()
            ids = [offer.id for offer, _ in rows]
            if ids:
                await s.execute(
                    _upd(OrderOffer)
                    .where(OrderOffer.id.in_(ids), OrderOffer.status == OfferStatus.SENT)
                    .values(status=OfferStatus.WITHDRAWN)
                )
        await asyncio.gather(
            *(self.msg.delete(Role.DRIVER, tg, offer.message_id) for offer, tg in rows if offer.message_id)
        )

    async def _withdraw_driver_offers(self, driver_id: int, except_order_id: int | None = None) -> None:
        async with self.db.session() as s:
            q = (
                select(OrderOffer, Driver.tg_id)
                .join(Driver, Driver.id == OrderOffer.driver_id)
                .where(OrderOffer.driver_id == driver_id, OrderOffer.status == OfferStatus.SENT)
            )
            if except_order_id is not None:
                q = q.where(OrderOffer.order_id != except_order_id)
            rows = (await s.execute(q)).all()
            ids = [offer.id for offer, _ in rows]
            if ids:
                await s.execute(
                    _upd(OrderOffer).where(OrderOffer.id.in_(ids)).values(status=OfferStatus.WITHDRAWN)
                )
        for offer, tg in rows:
            if offer.message_id:
                await self.msg.delete(Role.DRIVER, tg, offer.message_id)
            self.dispatch.wake(offer.order_id)

    # -------------------------------------------------------------- taklifga javob
    async def accept_offer(
        self, driver_tg: int, order_id: int, message_id: int | None = None, *, auto: bool = False
    ) -> ActionResult:
        now = utcnow()
        try:
            async with self.db.session() as s:
                d = await s.scalar(select(Driver).where(Driver.tg_id == driver_tg))
                if d is None or d.status != DriverStatus.APPROVED:
                    raise _Abort("not_driver")
                if d.current_order_id is not None:
                    raise _Abort("busy")
                if d.balance < self.settings.min_driver_balance:
                    raise _Abort("low_balance")
                offer = await s.scalar(
                    select(OrderOffer)
                    .where(OrderOffer.order_id == order_id, OrderOffer.driver_id == d.id)
                    .order_by(OrderOffer.id.desc())
                    .limit(1)
                )
                if offer is None:
                    raise _Abort("taken")
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == OrderStatus.SEARCHING)
                    .values(
                        status=OrderStatus.ACCEPTED,
                        driver_id=d.id,
                        accepted_at=now,
                        pickup_eta_s=offer.eta_s,
                    )
                )
                if res.rowcount != 1:
                    raise _Abort("taken")
                res = await s.execute(
                    _upd(Driver)
                    .where(Driver.id == d.id, Driver.current_order_id.is_(None))
                    .values(current_order_id=order_id)
                )
                if res.rowcount != 1:
                    raise _Abort("busy")
                await s.execute(
                    _upd(OrderOffer).where(OrderOffer.id == offer.id).values(status=OfferStatus.ACCEPTED)
                )
                driver_id = d.id
                offer_message_id = offer.message_id
        except _Abort as exc:
            if exc.reason == "taken" and message_id:
                await self.msg.delete(Role.DRIVER, driver_tg, message_id)
            return ActionResult(False, exc.reason)

        self.dispatch.wake(order_id)
        await asyncio.gather(
            self._withdraw_offers(order_id, keep_driver_id=driver_id),
            self._withdraw_driver_offers(driver_id, except_order_id=order_id),
        )

        async with self._lock(order_id):
            order, passenger, driver = await self._order_bundle(order_id)  # type: ignore[misc]
            assert driver is not None
            # Aniq yetib kelish vaqti (haydovchining joriy joylashuvidan)
            if self._driver_location_fresh(driver):
                route = await self.routing.route(
                    Point(driver.lat, driver.lon), Point(order.pickup_lat, order.pickup_lon)  # type: ignore[arg-type]
                )
                order.pickup_eta_s = int(route.duration_s)
            order.track_token = order.track_token or secrets.token_urlsafe(9)
            near = self._driver_location_fresh(driver) and haversine_m(
                driver.lat, driver.lon, order.pickup_lat, order.pickup_lon  # type: ignore[arg-type]
            ) <= self.settings.near_notify_radius_m
            card_id = message_id or offer_message_id
            view = self.views.driver_order(order, driver, auto=auto)
            if not (card_id and await self.msg.edit(Role.DRIVER, driver_tg, card_id, view)):
                card_id = await self.msg.send(Role.DRIVER, driver_tg, view)
            passenger_msg = await self.msg.replace(
                Role.PASSENGER,
                passenger.tg_id,
                order.passenger_msg_id,
                self.views.driver_found(order, driver, self.share_url(order)),
                effect=None,
            )
            live_id = None
            if self._driver_location_fresh(driver):
                live_id = await self.msg.send_live_location(
                    Role.PASSENGER, passenger.tg_id, driver.lat, driver.lon, driver.loc_heading  # type: ignore[arg-type]
                )
            await self._set_order_fields(
                order_id,
                driver_msg_id=card_id,
                passenger_msg_id=passenger_msg,
                passenger_live_msg_id=live_id,
                pickup_eta_s=order.pickup_eta_s,
                track_token=order.track_token,
                near_notified=near,
            )
        if await self._watchers(order_id):  # qayta qidiruvdan keyin yangi haydovchi
            await self._watchers_status(
                order_id, f"🚕 Yangi haydovchi topildi: {driver.car_color} {driver.car_model} · {driver.car_plate}"
            )
        return ActionResult(True)

    async def decline_offer(self, driver_tg: int, order_id: int, message_id: int | None = None) -> None:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == driver_tg))
            if d is None:
                return
            await s.execute(
                _upd(OrderOffer)
                .where(
                    OrderOffer.order_id == order_id,
                    OrderOffer.driver_id == d.id,
                    OrderOffer.status == OfferStatus.SENT,
                )
                .values(status=OfferStatus.DECLINED)
            )
        if message_id:
            await self.msg.delete(Role.DRIVER, driver_tg, message_id)
        self.dispatch.wake(order_id)

    # -------------------------------------------------------------- safar bosqichlari
    async def _driver_order(self, driver_tg: int, order_id: int) -> tuple[Order, Passenger, Driver] | None:
        bundle = await self._order_bundle(order_id)
        if bundle is None:
            return None
        order, passenger, driver = bundle
        if driver is None or driver.tg_id != driver_tg:
            return None
        return order, passenger, driver

    async def driver_arrived(self, driver_tg: int, order_id: int, *, auto: bool = False) -> bool:
        bundle = await self._driver_order(driver_tg, order_id)
        if bundle is None:
            return False
        _, passenger, driver = bundle
        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == OrderStatus.ACCEPTED)
                    .values(status=OrderStatus.ARRIVED, arrived_at=utcnow())
                )
                if res.rowcount != 1:
                    return False
            order = await self.get_order(order_id)
            await self.msg.edit(Role.DRIVER, driver_tg, order.driver_msg_id, self.views.driver_order(order, driver))
            new_id = await self.msg.replace(
                Role.PASSENGER,
                passenger.tg_id,
                order.passenger_msg_id,
                self.views.driver_arrived(order, driver, self.share_url(order)),
            )
            await self._set_order_fields(order_id, passenger_msg_id=new_id)
        if auto:
            await self.msg.send(
                Role.DRIVER,
                driver_tg,
                View.plain("📍 Siz manzildasiz — yo'lovchiga «yetib keldi» xabari avtomatik yuborildi."),
                silent=True,
            )
        await self._watchers_status(order_id, "⏳ Haydovchi yetib keldi va yaqiningizni kutmoqda.")
        return True

    async def driver_start(self, driver_tg: int, order_id: int) -> bool:
        bundle = await self._driver_order(driver_tg, order_id)
        if bundle is None:
            return False
        _, passenger, driver = bundle
        now = utcnow()
        values: dict = {"status": OrderStatus.IN_PROGRESS, "started_at": now, "trip_distance_m": 0.0}
        if self._driver_location_fresh(driver):
            values.update(
                track_lat=driver.lat, track_lon=driver.lon, track_at=now, start_lat=driver.lat, start_lon=driver.lon
            )
        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == OrderStatus.ARRIVED)
                    .values(**values)
                )
                if res.rowcount != 1:
                    # "Yetib keldim" bosilmagan bo'lsa ham safarni boshlash mumkin
                    res = await s.execute(
                        _upd(Order)
                        .where(Order.id == order_id, Order.status == OrderStatus.ACCEPTED)
                        .values(arrived_at=now, **values)
                    )
                    if res.rowcount != 1:
                        return False
            order = await self.get_order(order_id)
            await self.msg.edit(Role.DRIVER, driver_tg, order.driver_msg_id, self.views.driver_order(order, driver))
            new_id = await self.msg.replace(
                Role.PASSENGER,
                passenger.tg_id,
                order.passenger_msg_id,
                self.views.trip_started(order, driver, self.share_url(order)),
            )
            await self._set_order_fields(order_id, passenger_msg_id=new_id)
        await self._watchers_status(order_id, "🚀 Safar boshlandi. Mashinani xaritada kuzatishingiz mumkin.")
        return True

    def _final_price(self, order: Order, driver: Driver) -> tuple[int, int, float, dict]:
        """(yakuniy narx, kutish haqi, masofa, qo'shimcha maydonlar)."""
        extra: dict = {}
        distance = order.trip_distance_m or 0.0
        if self._driver_location_fresh(driver) and order.track_lat is not None:
            step = self._track_step(order, driver.lat, driver.lon, driver.loc_accuracy, utcnow())  # type: ignore[arg-type]
            if "trip_distance_m" in step:
                distance = step["trip_distance_m"]
            extra.update(step)
        if self._driver_location_fresh(driver) and order.start_lat is not None:
            # Taksometr ma'lumoti yetarli bo'lmasa: boshlanish va tugash nuqtasi orasidagi masofa
            straight = haversine_m(order.start_lat, order.start_lon, driver.lat, driver.lon)  # type: ignore[arg-type]
            if distance < straight * 0.9:  # GPS yo'li uzilib qolgan — taxminiy yo'l masofasi
                distance = straight * self.settings.road_factor
            else:
                distance = max(distance, straight)
        wait_seconds = 0.0
        if order.arrived_at and order.started_at:
            wait_seconds = (order.started_at - order.arrived_at).total_seconds()
        wait = self.tariff.wait_charge(wait_seconds)
        if order.has_destination and order.est_price:
            ride = order.est_price
            distance = distance or float(order.est_distance_m or 0)
        else:
            ride = self.tariff.ride_price(distance)
        extra["trip_distance_m"] = distance
        return ride + wait, wait, distance, extra

    async def driver_finish(self, driver_tg: int, order_id: int) -> bool:
        bundle = await self._driver_order(driver_tg, order_id)
        if bundle is None:
            return False
        order, passenger, driver = bundle
        if order.status != OrderStatus.IN_PROGRESS:
            return False
        price, wait, _distance, extra = self._final_price(order, driver)
        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(Order.id == order_id, Order.status == OrderStatus.IN_PROGRESS)
                    .values(
                        status=OrderStatus.FINISHING,
                        finish_requested_at=utcnow(),
                        final_price=price,
                        wait_charge=wait,
                        **extra,
                    )
                )
                if res.rowcount != 1:
                    return False
            order = await self.get_order(order_id)
            await self.msg.edit(Role.DRIVER, driver_tg, order.driver_msg_id, self.views.driver_order(order, driver))
            new_id = await self.msg.replace(
                Role.PASSENGER, passenger.tg_id, order.passenger_msg_id, self.views.confirm_arrival(order)
            )
            await self._set_order_fields(order_id, passenger_msg_id=new_id)
        return True

    async def _complete(self, order_id: int, *, auto: bool) -> bool:
        """Safarni yakunlaydi: yo'lovchi tasdig'i (yoki muddat o'tgani) — 10% komissiya yechiladi."""
        async with self._lock(order_id):
            bundle = await self._order_bundle(order_id)
            if bundle is None or bundle[2] is None:
                return False
            order, passenger, driver = bundle
            assert driver is not None
            if order.status == OrderStatus.FINISHING and order.final_price is not None:
                price, extra = order.final_price, {}
            elif order.status == OrderStatus.IN_PROGRESS:
                price, wait, _d, extra = self._final_price(order, driver)
                extra["wait_charge"] = wait
            else:
                return False
            commission = self.tariff.commission(price)
            now = utcnow()
            async with self.db.session() as s:
                res = await s.execute(
                    _upd(Order)
                    .where(
                        Order.id == order_id,
                        Order.status.in_([OrderStatus.IN_PROGRESS, OrderStatus.FINISHING]),
                    )
                    .values(
                        status=OrderStatus.COMPLETED,
                        completed_at=now,
                        final_price=price,
                        commission=commission,
                        auto_completed=auto,
                        finish_requested_at=order.finish_requested_at or now,
                        **extra,
                    )
                )
                if res.rowcount != 1:
                    return False
                await s.execute(
                    _upd(Driver)
                    .where(Driver.id == driver.id)
                    .values(
                        balance=Driver.balance - commission,
                        current_order_id=None,
                        trips_count=Driver.trips_count + 1,
                    )
                )
                balance = await s.scalar(select(Driver.balance).where(Driver.id == driver.id))
                s.add(
                    Transaction(
                        driver_id=driver.id,
                        amount=-commission,
                        balance_after=balance,
                        kind="commission",
                        order_id=order_id,
                        note=f"Buyurtma #{order_id}: {self.settings.commission_percent:g}% xizmat haqi",
                    )
                )
                await s.execute(
                    _upd(Passenger)
                    .where(Passenger.id == passenger.id)
                    .values(trips_count=Passenger.trips_count + 1)
                )
            order = await self.get_order(order_id)
            driver = await self.get_driver(driver.id)
            assert order is not None and driver is not None
            await self._drop_live(order, passenger)
            p_id = await self.msg.replace(
                Role.PASSENGER,
                passenger.tg_id,
                order.passenger_msg_id,
                self.views.completed_passenger(order),
                effect=EFFECT_PARTY,
            )
            d_id = await self.msg.replace(
                Role.DRIVER, driver.tg_id, order.driver_msg_id, self.views.driver_order(order, driver)
            )
            await self._set_order_fields(order_id, passenger_msg_id=p_id, driver_msg_id=d_id)
            await self._watchers_status(order_id, "✅ Safar yakunlandi — yaqiningiz manzilga yetib keldi.", final=True)
            if driver.balance < self.settings.min_driver_balance:
                await self.msg.send(
                    Role.DRIVER,
                    driver.tg_id,
                    View.plain(
                        "⚠️ <b>Balansingiz yetarli emas.</b> Yangi buyurtmalar kelishi uchun balansni "
                        "to'ldiring: 💰 Balans."
                    ),
                )
        self._forget(order_id)
        return True

    async def driver_cancel(self, driver_tg: int, order_id: int, *, no_show: bool) -> str:
        """Natija: ok | too_early | not_found."""
        bundle = await self._driver_order(driver_tg, order_id)
        if bundle is None:
            return "not_found"
        order, passenger, driver = bundle
        now = utcnow()
        if no_show:
            if order.status != OrderStatus.ARRIVED or order.arrived_at is None:
                return "not_found"
            waited = (now - order.arrived_at).total_seconds() / 60
            if waited < self.settings.no_show_wait_min:
                return "too_early"
        elif order.status not in (OrderStatus.ACCEPTED, OrderStatus.ARRIVED):
            return "not_found"

        async with self._lock(order_id):
            async with self.db.session() as s:
                if no_show:
                    res = await s.execute(
                        _upd(Order)
                        .where(Order.id == order_id, Order.status == OrderStatus.ARRIVED)
                        .values(
                            status=OrderStatus.CANCELLED,
                            cancelled_by="driver",
                            cancel_reason="no_show",
                            cancelled_at=now,
                        )
                    )
                else:
                    res = await s.execute(
                        _upd(Order)
                        .where(
                            Order.id == order_id,
                            Order.driver_id == driver.id,
                            Order.status.in_([OrderStatus.ACCEPTED, OrderStatus.ARRIVED]),
                        )
                        .values(
                            status=OrderStatus.SEARCHING,
                            driver_id=None,
                            search_round=Order.search_round + 1,
                            search_started_at=now,
                            accepted_at=None,
                            arrived_at=None,
                            pickup_eta_s=None,
                            wave=0,
                        )
                    )
                if res.rowcount != 1:
                    return "not_found"
                await s.execute(
                    _upd(Driver)
                    .where(Driver.id == driver.id, Driver.current_order_id == order_id)
                    .values(
                        current_order_id=None,
                        cancel_count=Driver.cancel_count + (0 if no_show else 1),
                    )
                )
                if not no_show:
                    await s.execute(
                        _upd(OrderOffer)
                        .where(
                            OrderOffer.order_id == order_id,
                            OrderOffer.driver_id == driver.id,
                            OrderOffer.status == OfferStatus.ACCEPTED,
                        )
                        .values(status=OfferStatus.DRIVER_CANCELLED)
                    )
            await self._drop_live(order, passenger)
            order = await self.get_order(order_id)
            text = "Yo'lovchi chiqmadi — buyurtma yopildi." if no_show else "Buyurtma bekor qilindi."
            card = Card(f"❌ Buyurtma #{order_id}")
            card.para(text)
            await self.msg.edit(Role.DRIVER, driver_tg, order.driver_msg_id, View.of(card))
            if no_show:
                await self._watchers_status(order_id, "❌ Safar bekor qilindi.", final=True)
                view = self.views.cancelled_passenger(
                    order, "Haydovchi sizni kutdi, ammo siz chiqmadingiz. Buyurtma bekor qilindi."
                )
                await self.msg.replace(Role.PASSENGER, passenger.tg_id, order.passenger_msg_id, view)
            else:
                await self._watchers_reset_live(order_id)
                await self._watchers_status(order_id, "🔄 Haydovchi almashtirilmoqda — yangi haydovchi qidirilmoqda.")
                view = self.views.searching(order, None, 0)
                view.text = "⚠️ Haydovchi buyurtmani bekor qildi. Yangi haydovchi qidirilmoqda…\n\n" + view.text
                new_id = await self.msg.replace(Role.PASSENGER, passenger.tg_id, order.passenger_msg_id, view)
                await self._set_order_fields(order_id, passenger_msg_id=new_id, driver_msg_id=None)
        if no_show:
            self._forget(order_id)
        else:
            self.dispatch.start(order_id)
        return "ok"

    async def _drop_live(self, order: Order, passenger: Passenger) -> None:
        """Haydovchi joylashuvi yo'lovchidan o'chiriladi (shaxsiy ma'lumot saqlanmaydi)."""
        if order.passenger_live_msg_id:
            await self.msg.delete(Role.PASSENGER, passenger.tg_id, order.passenger_live_msg_id)
            await self._set_order_fields(order.id, passenger_live_msg_id=None)
            order.passenger_live_msg_id = None

    # -------------------------------------------------------------- aloqa
    async def request_call(self, requester_tg: int, order_id: int, side: Role) -> str:
        bundle = await self._order_bundle(order_id)
        if bundle is None:
            return "❌ Buyurtma topilmadi."
        order, passenger, driver = bundle
        if driver is None or order.status not in DRIVER_ACTIVE_STATUSES:
            return "❌ Bu buyurtma faol emas."
        if side == Role.DRIVER and driver.tg_id != requester_tg:
            return "❌ Buyurtma topilmadi."
        if side == Role.PASSENGER and passenger.tg_id != requester_tg:
            return "❌ Buyurtma topilmadi."
        key = (order_id, side.value)
        now = time.monotonic()
        last = self._call_at.get(key, 0.0)
        if now - last < self.settings.call_cooldown_sec:
            wait = int(self.settings.call_cooldown_sec - (now - last)) + 1
            return f"⏳ Qo'ng'iroq ulanmoqda. Qayta urinish uchun {wait} soniya kuting."
        if order.call_count >= self.settings.calls_per_order:
            return "⚠️ Bu buyurtma uchun qo'ng'iroqlar soni tugadi. Chat orqali yozing."
        rider = order.rider_phone or passenger.phone  # boshqa odam uchun buyurtmada — aynan o'sha odam
        first, second = (driver.phone, rider) if side == Role.DRIVER else (passenger.phone, driver.phone)
        other = "yo'lovchi" if side == Role.DRIVER else "haydovchi"
        if not first or not second:
            return "⚠️ Telefon raqami topilmadi. Chat orqali yozing — xabaringiz yetkaziladi."
        self._call_at[key] = now
        await self._set_order_fields(order_id, call_count=Order.call_count + 1)
        result = await self.telephony.connect(first, second, order_id)
        if result.ok and result.mode == "callback":
            return (
                f"📞 Hozir kompaniya raqamidan sizga qo'ng'iroq keladi — javob bering, "
                f"so'ng {other} bilan ulanasiz. Raqamlar yashirin."
            )
        if result.ok and result.mode == "operator":
            who = "Haydovchi" if side == Role.DRIVER else "Yo'lovchi"
            await self.msg.notify_admins(
                View.plain(
                    f"📞 <b>Aloqa so'rovi — buyurtma #{order_id}</b>\n"
                    f"{who} {other} bilan bog'lanishni so'radi.\n\n"
                    f"Haydovchi: <code>{h(driver.phone)}</code>\n"
                    f"Yo'lovchi: <code>{h(rider)}</code>"
                    + (f" (buyurtmachi: <code>{h(passenger.phone)}</code>)" if order.rider_phone else "")
                    + "\n\n"
                    "Kompaniya raqamidan ikkala tomonni ulang."
                )
            )
            phone = f"\nYoki o'zingiz qo'ng'iroq qiling: {self.settings.company_phone}" if self.settings.company_phone else ""
            return f"📞 Operator sizni hozir kompaniya raqami orqali {other} bilan bog'laydi.{phone}"
        if self.settings.company_phone:
            return f"📞 Kompaniya raqamiga qo'ng'iroq qiling: {self.settings.company_phone}"
        return "⚠️ Hozircha qo'ng'iroq imkoni yo'q. Chat orqali yozing — xabaringiz yetkaziladi."

    # -------------------------------------------------------------- anonim chat
    async def relay_from(self, role: Role, tg_id: int) -> tuple[Order, Passenger, Driver] | None:
        """Faol safardagi suhbatdosh (raqamlar va profil ko'rinmaydi)."""
        async with self.db.session() as s:
            if role == Role.DRIVER:
                d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
                if d is None or d.current_order_id is None:
                    return None
                order = await s.get(Order, d.current_order_id)
            else:
                p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
                if p is None:
                    return None
                order = await s.scalar(
                    select(Order)
                    .where(Order.passenger_id == p.id, Order.status.in_(list(DRIVER_ACTIVE_STATUSES)))
                    .order_by(Order.id.desc())
                    .limit(1)
                )
            if order is None or order.driver_id is None or order.status not in DRIVER_ACTIVE_STATUSES:
                return None
            passenger = await s.get(Passenger, order.passenger_id)
            driver = await s.get(Driver, order.driver_id)
            return order, passenger, driver  # type: ignore[return-value]

    async def relay_text(self, role: Role, tg_id: int, text: str) -> bool:
        pair = await self.relay_from(role, tg_id)
        if pair is None:
            return False
        order, passenger, driver = pair
        if role == Role.DRIVER:
            target_role, target, prefix = Role.PASSENGER, passenger.tg_id, "🚕 Haydovchi"
        else:
            target_role, target, prefix = Role.DRIVER, driver.tg_id, "🙋 Yo'lovchi"
        sent = await self.msg.send(
            target_role, target, View.plain(f"💬 <b>{prefix}</b> (#{order.id}):\n{h(text[:1000])}")
        )
        return sent is not None

    async def relay_voice(self, role: Role, tg_id: int, file_id: str) -> bool:
        pair = await self.relay_from(role, tg_id)
        if pair is None:
            return False
        order, passenger, driver = pair
        if role == Role.DRIVER:
            return await self.msg.relay_voice(
                role, file_id, Role.PASSENGER, passenger.tg_id, f"🚕 Haydovchi (#{order.id})"
            )
        return await self.msg.relay_voice(role, file_id, Role.DRIVER, driver.tg_id, f"🙋 Yo'lovchi (#{order.id})")

    # ======================================================================== balans
    async def adjust_balance(
        self,
        driver_id: int,
        amount: int,
        kind: str,
        note: str | None = None,
        external_id: str | None = None,
    ) -> Driver | None:
        async with self.db.session() as s:
            if external_id and await s.scalar(
                select(Transaction.id).where(Transaction.external_id == external_id)
            ):
                return await s.get(Driver, driver_id)  # takroriy to'lov — qayta yozilmaydi
            res = await s.execute(
                _upd(Driver).where(Driver.id == driver_id).values(balance=Driver.balance + amount)
            )
            if res.rowcount != 1:
                return None
            d = await s.get(Driver, driver_id, populate_existing=True)
            s.add(
                Transaction(
                    driver_id=driver_id,
                    amount=amount,
                    balance_after=d.balance,
                    kind=kind,
                    note=note,
                    external_id=external_id,
                )
            )
        if amount > 0:
            await self.msg.send(
                Role.DRIVER,
                d.tg_id,
                View.plain(
                    f"💳 Balansingiz <b>{self.views.m(amount)}</b> ga to'ldirildi.\n"
                    f"Joriy balans: <b>{self.views.m(d.balance)}</b>"
                ),
            )
        return d

    def _local_day_start(self) -> datetime:
        local_now = datetime.now(self.tz)
        start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    async def driver_stats(self, driver_id: int) -> dict:
        day = self._local_day_start()
        async with self.db.session() as s:
            row = (
                await s.execute(
                    select(
                        func.count(Order.id),
                        func.coalesce(func.sum(Order.final_price), 0),
                        func.coalesce(func.sum(Order.commission), 0),
                    ).where(
                        Order.driver_id == driver_id,
                        Order.status == OrderStatus.COMPLETED,
                        Order.completed_at >= day,
                    )
                )
            ).one()
            d = await s.get(Driver, driver_id)
        return {
            "today_trips": int(row[0]),
            "today_income": int(row[1]),
            "today_commission": int(row[2]),
            "total_trips": d.trips_count if d else 0,
            "rating": d.rating if d else 0,
            "rating_count": d.rating_count if d else 0,
        }

    async def admin_stats(self) -> dict:
        day = self._local_day_start()
        async with self.db.session() as s:
            online = await s.scalar(
                select(func.count(Driver.id)).where(
                    Driver.is_online.is_(True), Driver.status == DriverStatus.APPROVED
                )
            )
            free = await s.scalar(
                select(func.count(Driver.id)).where(
                    Driver.is_online.is_(True),
                    Driver.status == DriverStatus.APPROVED,
                    Driver.current_order_id.is_(None),
                    Driver.loc_valid_until > utcnow(),
                )
            )
            active = await s.scalar(
                select(func.count(Order.id)).where(
                    Order.status.in_(
                        [
                            OrderStatus.SEARCHING,
                            OrderStatus.ACCEPTED,
                            OrderStatus.ARRIVED,
                            OrderStatus.IN_PROGRESS,
                            OrderStatus.FINISHING,
                        ]
                    )
                )
            )
            done = (
                await s.execute(
                    select(
                        func.count(Order.id),
                        func.coalesce(func.sum(Order.final_price), 0),
                        func.coalesce(func.sum(Order.commission), 0),
                    ).where(Order.status == OrderStatus.COMPLETED, Order.completed_at >= day)
                )
            ).one()
            failed = await s.scalar(
                select(func.count(Order.id)).where(
                    Order.status == OrderStatus.NO_DRIVERS, Order.created_at >= day
                )
            )
            pending = await s.scalar(
                select(func.count(Driver.id)).where(Driver.status == DriverStatus.PENDING)
            )
        return {
            "online": online or 0,
            "free": free or 0,
            "active": active or 0,
            "today_done": int(done[0]),
            "today_turnover": int(done[1]),
            "today_commission": int(done[2]),
            "today_no_drivers": failed or 0,
            "pending_drivers": pending or 0,
        }

    async def find_driver(self, ident: int) -> Driver | None:
        """ID yoki Telegram ID bo'yicha."""
        async with self.db.session() as s:
            return await s.scalar(select(Driver).where(or_(Driver.id == ident, Driver.tg_id == ident)))

    # ======================================================================== fon jarayonlari
    async def resume(self) -> None:
        """Qayta ishga tushganda qidirilayotgan buyurtmalarni tiklaydi."""
        async with self.db.session() as s:
            ids = (await s.scalars(select(Order.id).where(Order.status == OrderStatus.SEARCHING))).all()
        for oid in ids:
            self.dispatch.start(oid)
        if ids:
            log.info("%s ta qidiruv tiklandi", len(ids))

    async def maintenance_tick(self) -> None:
        s_ = self.settings
        now = utcnow()
        # 1) Yo'lovchi javob bermagan safarlarni avtomatik yakunlash
        if s_.finish_confirm_timeout_min > 0:
            limit = now - timedelta(minutes=s_.finish_confirm_timeout_min)
            async with self.db.session() as s:
                ids = (
                    await s.scalars(
                        select(Order.id).where(
                            Order.status == OrderStatus.FINISHING, Order.finish_requested_at < limit
                        )
                    )
                ).all()
            for oid in ids:
                await self._complete(oid, auto=True)
        # 2) Joylashuvi eskirgan haydovchilarga eslatma / liniyadan chiqarish
        async with self.db.session() as s:
            stale = (
                await s.scalars(
                    select(Driver).where(
                        Driver.is_online.is_(True),
                        Driver.current_order_id.is_(None),
                        or_(Driver.loc_valid_until.is_(None), Driver.loc_valid_until < now),
                    )
                )
            ).all()
            to_remind = [d for d in stale if not d.loc_reminded]
            to_offline = [
                d
                for d in stale
                if d.loc_valid_until is None or d.loc_valid_until < now - timedelta(hours=1)
            ]
            for d in to_remind:
                d.loc_reminded = True
            for d in to_offline:
                d.is_online = False
        for d in to_remind:
            if d in to_offline:
                continue
            text = (
                "📍 <b>Joylashuvingiz eskirdi</b> — buyurtmalar kelmayapti.\n\n"
                + (self.views.live_location_help() if s_.require_live_location else "«📍 Joylashuvni yangilash» tugmasini bosing.")
            )
            await self.msg.send(Role.DRIVER, d.tg_id, View.plain(text, self.views.driver_menu(True)))
        for d in to_offline:
            await self.msg.send(
                Role.DRIVER,
                d.tg_id,
                View.plain("🔴 Joylashuv uzoq vaqt yangilanmagani uchun liniyadan chiqdingiz.", self.views.driver_menu(False)),
                silent=True,
            )
        # 3) Qidiruv vazifasi yo'qolgan buyurtmalar (xavfsizlik uchun)
        async with self.db.session() as s:
            ids = (await s.scalars(select(Order.id).where(Order.status == OrderStatus.SEARCHING))).all()
        for oid in ids:
            if not self.dispatch.is_running(oid):
                self.dispatch.start(oid)

    async def run_maintenance(self, interval: float = 30.0) -> None:
        while True:
            try:
                await self.maintenance_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Maintenance xatosi")
            await asyncio.sleep(interval)

    async def close(self) -> None:
        await self.dispatch.stop_all()
        await self.routing.close()


__all__ = ["ActionResult", "LocationResult", "TaxiService"]
