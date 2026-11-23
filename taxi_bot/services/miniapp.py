"""Telegram Mini App uchun holatlar va amallar (yo'lovchi va haydovchi ilovasi)."""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from ..db.models import (
    BotUser,
    Driver,
    DriverStatus,
    OfferStatus,
    Order,
    OrderOffer,
    OrderStatus,
    Passenger,
    utcnow,
)
from ..ui.messenger import Role
from .geo import Point, bearing_deg, bounding_box, compass, compass_to, haversine_m
from .privacy import mask_contacts
from .telephony import normalize_phone

if TYPE_CHECKING:
    from .taxi import TaxiService

ACTIVE = [
    OrderStatus.SEARCHING,
    OrderStatus.ACCEPTED,
    OrderStatus.ARRIVED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.FINISHING,
]


# Yo'lovchi joylashuvi haydovchiga faqat shu bosqichlarda ko'rsatiladi (safar boshlangach — kerak emas)
PAX_LIVE_STATUSES = [OrderStatus.SEARCHING, OrderStatus.ACCEPTED, OrderStatus.ARRIVED]
PAX_LIVE_FRESH = timedelta(minutes=3)


def _iso(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=UTC).isoformat() if dt else None


def _approx(lat: float, lon: float, order_id: int) -> list[float]:
    """Qabul qilinmagan buyurtma joyi ~300 m aniqlikda (yo'lovchining aniq joyi oshkor qilinmaydi)."""
    rnd = random.Random(order_id)
    return [round(lat + rnd.uniform(-0.0018, 0.0018), 5), round(lon + rnd.uniform(-0.0024, 0.0024), 5)]


class MiniAppMixin:
    _roles: dict[int, Role | None]

    # ------------------------------------------------------------------ rol (bitta bot rejimi)
    async def get_user_role(self: TaxiService, tg_id: int) -> Role | None:
        cache = self.__dict__.setdefault("_roles", {})
        if tg_id in cache:
            return cache[tg_id]
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
        role = Role(row.role) if row and row.role else None
        cache[tg_id] = role
        return role

    async def set_user_role(self: TaxiService, tg_id: int, role: Role) -> None:
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
            if row is None:
                s.add(BotUser(tg_id=tg_id, role=role.value))
            else:
                row.role = role.value
        self.__dict__.setdefault("_roles", {})[tg_id] = role
        if role == Role.PASSENGER:
            await self.driver_offline(tg_id)

    async def live_share(self: TaxiService, tg_id: int) -> bool:
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
        return True if row is None else bool(row.live_share)

    async def set_live_share(self: TaxiService, tg_id: int, on: bool) -> None:
        """Ilovadagi «📡 Jonli joylashuv» tugmasi: foydalanuvchi o'zi o'chirmaguncha yoqilgan turadi."""
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
            if row is None:
                s.add(BotUser(tg_id=tg_id, live_share=on))
            else:
                row.live_share = on

    async def passenger_live_location(
        self: TaxiService, tg_id: int, lat: float, lon: float, accuracy: float | None = None
    ) -> bool:
        """Yo'lovchining joriy joylashuvi — faqat faol buyurtma (qidiruv / haydovchi yo'lda / kutmoqda) davomida."""
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return False
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
            if p is None:
                return False
            order = await s.scalar(
                select(Order)
                .where(Order.passenger_id == p.id, Order.status.in_(PAX_LIVE_STATUSES))
                .order_by(Order.id.desc())
                .limit(1)
            )
            if order is None:
                return False
            order.pax_lat, order.pax_lon = lat, lon
            order.pax_accuracy = accuracy if accuracy is None or math.isfinite(accuracy) else None
            order.pax_at = utcnow()
        return True

    async def driver_busy(self: TaxiService, tg_id: int) -> bool:
        """Haydovchida hozir faol safar bormi (rolni almashtirishdan oldin tekshiriladi)."""
        async with self.db.session() as s:
            current = await s.scalar(select(Driver.current_order_id).where(Driver.tg_id == tg_id))
        return current is not None

    async def save_verified_phone(self: TaxiService, tg_id: int, phone: str) -> None:
        """Telegram tasdiqlagan raqam (ilovadagi «raqamni ulashish» yoki botga yuborilgan kontakt)."""
        phone = normalize_phone(phone) or phone
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
            if row is None:
                s.add(BotUser(tg_id=tg_id, phone=phone))
            else:
                row.phone = phone
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
            if p is not None and not p.phone:
                p.phone = phone

    async def verified_phone(self: TaxiService, tg_id: int) -> str | None:
        async with self.db.session() as s:
            row = await s.get(BotUser, tg_id)
            if row and row.phone:
                return row.phone
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == tg_id))
            return p.phone if p else None

    # ------------------------------------------------------------------ umumiy
    def app_config(self: TaxiService) -> dict:
        s = self.settings
        return {
            "company": s.company_name,
            "company_phone": s.company_phone,
            "currency": s.currency,
            "tile_url": s.tile_url,
            "tile_attribution": s.tile_attribution,
            "tariff": {
                "base_fare": s.base_fare, "base_km": s.base_km, "per_km": s.per_km,
                "free_wait_min": s.free_wait_min, "per_wait_min": s.per_wait_min, "min_fare": s.min_fare,
            },
            "commission_percent": s.commission_percent,
            "min_driver_balance": s.min_driver_balance,
            "welcome_bonus": s.welcome_bonus,
            "single_bot": s.single_bot,
            "router_urls": [u for u in s.route_urls if u.startswith("https://")],
            "geocoder": bool(s.geocoder_url),
        }

    def _eta_s(self: TaxiService, a: tuple[float, float], b: tuple[float, float]) -> int:
        return int(self.routing.estimate(Point(*a), Point(*b)).duration_s)

    async def nearby_cars(self: TaxiService, lat: float, lon: float, radius_m: float = 3000) -> list[dict]:
        """Yaqindagi bo'sh mashinalar (xaritada ko'rsatish uchun, shaxsiy ma'lumotsiz, ~50 m siljitilgan)."""
        min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius_m)
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Driver.id, Driver.lat, Driver.lon, Driver.loc_heading).where(
                        Driver.status == DriverStatus.APPROVED,
                        Driver.is_online.is_(True),
                        Driver.current_order_id.is_(None),
                        Driver.home_mode.is_(False),
                        Driver.loc_valid_until > utcnow(),
                        Driver.lat.between(min_lat, max_lat),
                        Driver.lon.between(min_lon, max_lon),
                    )
                )
            ).all()
        cars = []
        for driver_id, dlat, dlon, heading in rows:
            if haversine_m(lat, lon, dlat, dlon) > radius_m:
                continue
            rnd = random.Random(driver_id * 7919 + int(dlat * 1000))
            cars.append(
                {
                    "lat": dlat + rnd.uniform(-0.0004, 0.0004),
                    "lon": dlon + rnd.uniform(-0.0005, 0.0005),
                    "heading": heading or rnd.randint(0, 359),
                }
            )
        return cars[:40]

    # ------------------------------------------------------------------ yo'lovchi
    def _order_public(self: TaxiService, o: Order, d: Driver | None, offered: int = 0) -> dict:
        now = utcnow()
        data: dict = {
            "id": o.id,
            "status": o.status,
            "pickup": {"lat": o.pickup_lat, "lon": o.pickup_lon},
            "dest": {"lat": o.dest_lat, "lon": o.dest_lon, "title": o.dest_title} if o.has_destination else None,
            "price": o.final_price or o.est_price,
            "fixed_price": bool(o.has_destination and o.est_price),
            "final_price": o.final_price,
            "wait_charge": o.wait_charge,
            "trip_distance_m": o.trip_distance_m or o.est_distance_m,
            "comment": o.comment,
            "rider": bool(o.rider_phone),
            "created_at": _iso(o.created_at),
            "search": None,
            "driver": None,
            "eta_s": None,
        }
        if o.status == OrderStatus.SEARCHING:
            radii = self.settings.wave_radii_km
            data["search"] = {
                "radius_m": radii[min(o.wave, len(radii) - 1)] * 1000 if o.wave >= 0 else radii[0] * 1000,
                "offered": offered,
                "started_at": _iso(o.search_started_at),
                "timeout_s": self.settings.search_timeout_sec,
            }
        if d is not None:
            fresh = self._driver_location_fresh(d)
            data["driver"] = {
                "car": f"{d.car_color} {d.car_model}".strip(),
                "plate": d.car_plate,
                "rating": d.rating,
                "lat": d.lat if fresh else None,
                "lon": d.lon if fresh else None,
                "heading": d.loc_heading,
            }
            if fresh and o.status == OrderStatus.ACCEPTED:
                data["eta_s"] = self._eta_s((d.lat, d.lon), (o.pickup_lat, o.pickup_lon))  # type: ignore[arg-type]
            elif fresh and o.status == OrderStatus.IN_PROGRESS and o.has_destination:
                data["eta_s"] = self._eta_s((d.lat, d.lon), (o.dest_lat, o.dest_lon))  # type: ignore[arg-type]
        if o.status == OrderStatus.ARRIVED and o.arrived_at:
            free = self.settings.free_wait_min * 60 - (now - o.arrived_at).total_seconds()
            data["free_wait_left_s"] = max(0, int(free))
        return data

    async def passenger_state(self: TaxiService, tg_id: int) -> dict:
        p = await self.get_passenger_by_tg(tg_id)
        state: dict = {
            "registered": bool(p and p.phone),
            "blocked": bool(p and p.is_blocked),
            "order": None,
            "rate_order": None,
            "places": [],
            "recent": [],
        }
        if p is None:
            return state
        order = await self.active_order(p.id)
        if order is not None:
            driver = await self.get_driver(order.driver_id) if order.driver_id else None
            offered = await self._offered_count(order) if order.status == OrderStatus.SEARCHING else 0
            state["order"] = self._order_public(order, driver, offered)
        else:
            async with self.db.session() as s:
                last = await s.scalar(
                    select(Order)
                    .where(Order.passenger_id == p.id)
                    .order_by(Order.id.desc())
                    .limit(1)
                )
            if last is not None and last.status == OrderStatus.NO_DRIVERS:
                state["order"] = self._order_public(last, None)
            elif (
                last is not None
                and last.status == OrderStatus.COMPLETED
                and last.rating is None
                and last.completed_at
                and utcnow() - last.completed_at < timedelta(hours=2)
            ):
                driver = await self.get_driver(last.driver_id) if last.driver_id else None
                data = self._order_public(last, driver)
                data["favorite"] = bool(driver) and await self.is_favorite(p.id, driver.id)  # type: ignore[union-attr]
                state["rate_order"] = data
        state["places"] = [
            {"id": x.id, "kind": x.kind, "title": x.title, "lat": x.lat, "lon": x.lon}
            for x in await self.list_places(p.id)
        ]
        state["recent"] = [
            {"title": o.dest_title or "Oldingi manzil", "lat": o.dest_lat, "lon": o.dest_lon}
            for o in await self.recent_destinations(p.id, limit=4)
        ]
        return state

    async def app_quote(
        self: TaxiService, lat: float, lon: float, accuracy: float | None, dest: dict | None
    ) -> dict:
        q = await self.build_quote(
            lat, lon, accuracy,
            dest["lat"] if dest else None, dest["lon"] if dest else None, dest.get("title") if dest else None,
        )
        geometry, precise = None, False
        if dest:
            est, geometry = await self.routing.route_geometry(Point(lat, lon), Point(dest["lat"], dest["lon"]))
            precise = est.precise
        return {
            "price": q.price,
            "distance_m": q.distance_m,
            "duration_s": q.duration_s,
            "nearby": q.nearby_count,
            "nearest_eta_s": q.nearest_eta_s,
            "route": geometry,
            "route_precise": precise,
        }

    async def app_create_order(self: TaxiService, tg_id: int, body: dict) -> tuple[Order | None, str]:
        p = await self.get_passenger_by_tg(tg_id)
        if p is None or not p.phone:
            return None, "Avval telefon raqamingizni ulashing"
        if p.is_blocked:
            return None, "Hisobingiz cheklangan. Operatorga murojaat qiling"
        pickup = body.get("pickup") or {}
        dest = body.get("dest")
        q = await self.build_quote(
            float(pickup["lat"]), float(pickup["lon"]), pickup.get("accuracy"),
            float(dest["lat"]) if dest else None, float(dest["lon"]) if dest else None,
            (dest.get("title") or None) if dest else None,
            (body.get("comment") or "").strip()[:300] or None,
        )
        if body.get("rider_phone"):
            rider = normalize_phone(str(body["rider_phone"]))
            if rider is None or len(rider) < 12:
                return None, "Yo'lovchi raqami noto'g'ri"
            q.rider_phone = rider
        order = await self.create_order(tg_id, q)
        if order is None:
            return None, "Sizda faol buyurtma bor"
        return order, ""

    # ------------------------------------------------------------------ haydovchi
    async def driver_state(self: TaxiService, tg_id: int) -> dict:
        d = await self.get_driver_by_tg(tg_id)
        phone = await self.verified_phone(tg_id)
        if d is None:
            return {"registered": False, "phone": bool(phone), "driver": None, "offers": [], "order": None}
        now = utcnow()
        info = {
            "id": d.id,
            "status": d.status,
            "name": d.full_name,
            "car": f"{d.car_color} {d.car_model}".strip(),
            "plate": d.car_plate,
            "balance": d.balance,
            "rating": d.rating,
            "online": d.is_online,
            "location_fresh": self._driver_location_fresh(d),
            "live": d.loc_is_live,
            "home_mode": d.home_mode,
            "home_set": d.home_lat is not None,
            "navigator": d.navigator,
            "trips": d.trips_count,
        }
        offers: list[dict] = []
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(OrderOffer, Order)
                    .join(Order, Order.id == OrderOffer.order_id)
                    .where(
                        OrderOffer.driver_id == d.id,
                        OrderOffer.status == OfferStatus.SENT,
                        Order.status == OrderStatus.SEARCHING,
                    )
                    .order_by(OrderOffer.id.desc())
                )
            ).all()
        for offer, o in rows:
            bearing = (
                bearing_deg(d.lat, d.lon, o.pickup_lat, o.pickup_lon) if d.lat is not None else 0.0  # type: ignore[arg-type]
            )
            offers.append(
                {
                    "order_id": o.id,
                    "distance_m": offer.distance_m,
                    "eta_s": offer.eta_s,
                    "direction": compass(bearing),
                    "approx": _approx(o.pickup_lat, o.pickup_lon, o.id),
                    "trip_distance_m": o.est_distance_m,
                    "trip_direction": compass_to(
                        bearing_deg(o.pickup_lat, o.pickup_lon, o.dest_lat, o.dest_lon)  # type: ignore[arg-type]
                    ) if o.has_destination else None,
                    "price": o.est_price,
                    "comment": o.comment,
                    "rider": bool(o.rider_phone),
                    "sent_at": _iso(offer.created_at),
                }
            )
        order_data = None
        async with self.db.session() as s:
            order = None
            if d.current_order_id:
                order = await s.get(Order, d.current_order_id)
            if order is None:  # yo'lovchi tasdig'ini kutayotgan oxirgi safar
                order = await s.scalar(
                    select(Order)
                    .where(Order.driver_id == d.id, Order.status == OrderStatus.FINISHING)
                    .order_by(Order.id.desc())
                    .limit(1)
                )
        if order is not None and order.status in ACTIVE:
            order_data = {
                "id": order.id,
                "status": order.status,
                "pickup": {"lat": order.pickup_lat, "lon": order.pickup_lon},
                "dest": (
                    {"lat": order.dest_lat, "lon": order.dest_lon, "title": order.dest_title}
                    if order.has_destination else None
                ),
                "price": order.final_price or order.est_price,
                "fixed_price": bool(order.has_destination and order.est_price),
                "comment": order.comment,
                "rider": bool(order.rider_phone),
                "arrived_at": _iso(order.arrived_at),
                "started_at": _iso(order.started_at),
                "free_wait_min": self.settings.free_wait_min,
                "no_show_wait_min": self.settings.no_show_wait_min,
                "taximeter": None,
                "passenger_live": None,
            }
            if (
                order.status in (OrderStatus.ACCEPTED, OrderStatus.ARRIVED)
                and order.pax_at is not None
                and order.pax_lat is not None
                and now - order.pax_at <= PAX_LIVE_FRESH
            ):
                order_data["passenger_live"] = {
                    "lat": order.pax_lat, "lon": order.pax_lon, "accuracy": order.pax_accuracy,
                    "age_s": int((now - order.pax_at).total_seconds()),
                }
            if order.status == OrderStatus.IN_PROGRESS:
                price, wait, distance, _ = self._final_price(order, d)
                order_data["taximeter"] = {
                    "distance_m": distance,
                    "wait_charge": wait,
                    "price": price,
                    "minutes": int((now - order.started_at).total_seconds() // 60) if order.started_at else 0,
                }
        stats = await self.driver_stats(d.id)
        return {
            "registered": True,
            "phone": bool(phone or d.phone),
            "driver": info,
            "offers": offers,
            "order": order_data,
            "stats": stats,
        }

    async def app_register_driver(self: TaxiService, tg_id: int, body: dict) -> tuple[Driver | None, str]:
        phone = await self.verified_phone(tg_id)
        if not phone:
            return None, "Avval telefon raqamingizni ulashing"
        fields = {k: str(body.get(k) or "").strip() for k in ("full_name", "car_model", "car_color", "car_plate")}
        if len(fields["full_name"]) < 3 or len(fields["car_model"]) < 2 or not fields["car_color"]:
            return None, "Barcha maydonlarni to'ldiring"
        from ..bots.driver import normalize_plate

        plate = normalize_plate(fields["car_plate"])
        if plate is None:
            return None, "Davlat raqami noto'g'ri (masalan: 01 A 123 BC)"
        existing = await self.get_driver_by_tg(tg_id)
        if existing and existing.status in (DriverStatus.APPROVED, DriverStatus.BLOCKED):
            return existing, ""
        d = await self.register_driver(
            tg_id, mask_contacts(fields["full_name"])[0], phone, fields["car_model"], fields["car_color"], plate
        )
        return d, ""

    async def app_driver_location(
        self: TaxiService, tg_id: int, lat: float, lon: float, accuracy: float | None, heading: float | None
    ):
        """Ilova ochiq paytida har bir necha soniyada keladi; ilova yopilsa ~2 daqiqada eskiradi."""
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        head = int(heading) % 360 if heading is not None and math.isfinite(heading) else None
        return await self.update_driver_location(
            tg_id, lat, lon, accuracy=accuracy, heading=head or None, is_live=True,
            live_until=utcnow() + timedelta(minutes=2),
        )
