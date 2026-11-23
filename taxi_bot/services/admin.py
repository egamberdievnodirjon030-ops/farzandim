"""Admin paneli uchun ma'lumotlar va amallar (web-panel va Telegram /admin ishlatadi)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from ..db.models import (
    Driver,
    DriverStatus,
    Order,
    OrderStatus,
    Passenger,
    Transaction,
    utcnow,
)
from ..ui.kit import Card, View
from ..ui.messenger import Role

if TYPE_CHECKING:
    from .taxi import TaxiService

log = logging.getLogger(__name__)

ACTIVE = [
    OrderStatus.SEARCHING,
    OrderStatus.ACCEPTED,
    OrderStatus.ARRIVED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.FINISHING,
]
CANCELLABLE = [*ACTIVE, OrderStatus.NO_DRIVERS]


def _iso(dt: datetime | None) -> str | None:
    """UTC (timezone'siz) vaqtni brauzer uchun ISO ko'rinishga."""
    return dt.replace(tzinfo=UTC).isoformat() if dt else None


class AdminMixin:
    # ------------------------------------------------------------------ umumiy ko'rsatkichlar
    async def admin_summary(self: TaxiService) -> dict:
        stats = await self.admin_stats()
        now = utcnow()
        async with self.db.session() as s:
            by_status = dict(
                (
                    await s.execute(
                        select(Order.status, func.count(Order.id))
                        .where(Order.status.in_(ACTIVE))
                        .group_by(Order.status)
                    )
                ).all()
            )
            busy = await s.scalar(
                select(func.count(Driver.id)).where(
                    Driver.status == DriverStatus.APPROVED, Driver.current_order_id.is_not(None)
                )
            )
            drivers_total = await s.scalar(
                select(func.count(Driver.id)).where(Driver.status == DriverStatus.APPROVED)
            )
            passengers_total = await s.scalar(select(func.count(Passenger.id)))
            low_balance = await s.scalar(
                select(func.count(Driver.id)).where(
                    Driver.status == DriverStatus.APPROVED,
                    Driver.balance < self.settings.min_driver_balance,
                )
            )
        return {
            **stats,
            "busy": busy or 0,
            "drivers_total": drivers_total or 0,
            "passengers_total": passengers_total or 0,
            "low_balance": low_balance or 0,
            "active_by_status": {str(k): v for k, v in by_status.items()},
            "currency": self.settings.currency,
            "commission_percent": self.settings.commission_percent,
            "server_time": _iso(now),
        }

    # ------------------------------------------------------------------ xarita
    async def admin_map(self: TaxiService) -> dict:
        now = utcnow()
        async with self.db.session() as s:
            drivers = (
                await s.scalars(
                    select(Driver).where(
                        Driver.status == DriverStatus.APPROVED,
                        Driver.is_online.is_(True),
                        Driver.lat.is_not(None),
                    )
                )
            ).all()
            orders = (await s.scalars(select(Order).where(Order.status.in_(ACTIVE)))).all()
        return {
            "drivers": [
                {
                    "id": d.id,
                    "lat": d.lat,
                    "lon": d.lon,
                    "state": (
                        "busy"
                        if d.current_order_id
                        else ("free" if d.loc_valid_until and d.loc_valid_until > now else "stale")
                    ),
                    "plate": d.car_plate,
                    "car": f"{d.car_color} {d.car_model}".strip(),
                    "name": d.full_name,
                    "rating": d.rating,
                    "order_id": d.current_order_id,
                    "updated_at": _iso(d.loc_updated_at),
                }
                for d in drivers
            ],
            "orders": [
                {
                    "id": o.id,
                    "status": o.status,
                    "pickup": [o.pickup_lat, o.pickup_lon],
                    "dest": [o.dest_lat, o.dest_lon] if o.has_destination else None,
                    "driver_id": o.driver_id,
                }
                for o in orders
            ],
        }

    # ------------------------------------------------------------------ ro'yxatlar
    async def admin_orders(self: TaxiService, scope: str = "active", limit: int = 200) -> list[dict]:
        q = (
            select(Order, Passenger, Driver)
            .join(Passenger, Passenger.id == Order.passenger_id)
            .outerjoin(Driver, Driver.id == Order.driver_id)
            .order_by(Order.id.desc())
            .limit(min(max(limit, 1), 1000))
        )
        if scope == "active":
            q = q.where(Order.status.in_(ACTIVE))
        elif scope == "today":
            q = q.where(Order.created_at >= self._local_day_start())
        async with self.db.session() as s:
            rows = (await s.execute(q)).all()
        return [
            {
                "id": o.id,
                "status": o.status,
                "created_at": _iso(o.created_at),
                "passenger": {"id": p.id, "name": p.first_name, "phone": p.phone},
                "rider_phone": o.rider_phone,
                "driver": (
                    {"id": d.id, "name": d.full_name, "phone": d.phone, "plate": d.car_plate} if d else None
                ),
                "has_destination": o.has_destination,
                "distance_m": o.trip_distance_m or o.est_distance_m,
                "price": o.final_price or o.est_price,
                "commission": o.commission,
                "comment": o.comment,
                "cancelled_by": o.cancelled_by,
                "cancel_reason": o.cancel_reason,
                "rating": o.rating,
            }
            for o, p, d in rows
        ]

    async def admin_drivers(self: TaxiService, status: str | None = None) -> list[dict]:
        q = select(Driver).order_by(Driver.status != DriverStatus.PENDING, Driver.id.desc())
        if status:
            q = q.where(Driver.status == status)
        now = utcnow()
        async with self.db.session() as s:
            rows = (await s.scalars(q)).all()
        return [
            {
                "id": d.id,
                "name": d.full_name,
                "phone": d.phone,
                "car": f"{d.car_color} {d.car_model}".strip(),
                "plate": d.car_plate,
                "status": d.status,
                "online": d.is_online,
                "location_fresh": bool(d.loc_valid_until and d.loc_valid_until > now),
                "busy": d.current_order_id is not None,
                "balance": d.balance,
                "rating": d.rating,
                "rating_count": d.rating_count,
                "trips": d.trips_count,
                "cancels": d.cancel_count,
                "home_mode": d.home_mode,
                "created_at": _iso(d.created_at),
            }
            for d in rows
        ]

    async def admin_passengers(self: TaxiService, limit: int = 500) -> list[dict]:
        async with self.db.session() as s:
            cancels = dict(
                (
                    await s.execute(
                        select(Order.passenger_id, func.count(Order.id))
                        .where(Order.status == OrderStatus.CANCELLED)
                        .group_by(Order.passenger_id)
                    )
                ).all()
            )
            rows = (await s.scalars(select(Passenger).order_by(Passenger.id.desc()).limit(limit))).all()
        return [
            {
                "id": p.id,
                "name": p.first_name,
                "phone": p.phone,
                "trips": p.trips_count,
                "cancels": cancels.get(p.id, 0),
                "blocked": p.is_blocked,
                "created_at": _iso(p.created_at),
            }
            for p in rows
        ]

    async def admin_finance(self: TaxiService, days: int = 14) -> dict:
        days = min(max(days, 1), 366)
        start = self._local_day_start() - timedelta(days=days - 1)
        async with self.db.session() as s:
            orders = (
                await s.execute(
                    select(Order.completed_at, Order.final_price, Order.commission).where(
                        Order.status == OrderStatus.COMPLETED, Order.completed_at >= start
                    )
                )
            ).all()
            topups = (
                await s.execute(
                    select(Transaction.created_at, Transaction.amount).where(
                        Transaction.kind.in_(["topup", "payment", "bonus"]),
                        Transaction.created_at >= start,
                    )
                )
            ).all()
            balances = await s.scalar(
                select(func.coalesce(func.sum(Driver.balance), 0)).where(Driver.status == DriverStatus.APPROVED)
            )
        tz = self.tz
        table: dict[str, dict] = {}
        for i in range(days):
            day = (datetime.now(tz) - timedelta(days=i)).strftime("%Y-%m-%d")
            table[day] = {"date": day, "trips": 0, "turnover": 0, "commission": 0, "topups": 0}
        for completed_at, price, commission in orders:
            key = completed_at.replace(tzinfo=UTC).astimezone(tz).strftime("%Y-%m-%d")
            if key in table:
                table[key]["trips"] += 1
                table[key]["turnover"] += price or 0
                table[key]["commission"] += commission or 0
        for created_at, amount in topups:
            key = created_at.replace(tzinfo=UTC).astimezone(tz).strftime("%Y-%m-%d")
            if key in table:
                table[key]["topups"] += amount or 0
        rows = sorted(table.values(), key=lambda r: r["date"], reverse=True)
        totals = {k: sum(r[k] for r in rows) for k in ("trips", "turnover", "commission", "topups")}
        return {"days": rows, "totals": totals, "driver_balances": int(balances or 0)}

    async def admin_transactions(self: TaxiService, limit: int = 100) -> list[dict]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(Transaction, Driver.full_name, Driver.car_plate)
                    .join(Driver, Driver.id == Transaction.driver_id)
                    .order_by(Transaction.id.desc())
                    .limit(min(max(limit, 1), 1000))
                )
            ).all()
        return [
            {
                "id": t.id,
                "driver_id": t.driver_id,
                "driver": name,
                "plate": plate,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "kind": t.kind,
                "order_id": t.order_id,
                "note": t.note,
                "created_at": _iso(t.created_at),
            }
            for t, name, plate in rows
        ]

    # ------------------------------------------------------------------ amallar
    async def admin_cancel_order(self: TaxiService, order_id: int, by: str = "admin") -> bool:
        """Operator buyurtmani majburan bekor qiladi (qotib qolgan holatlar uchun). Komissiya yechilmaydi."""
        bundle = await self._order_bundle(order_id)
        if bundle is None:
            return False
        order, passenger, driver = bundle
        async with self._lock(order_id):
            async with self.db.session() as s:
                res = await s.execute(
                    update(Order)
                    .execution_options(synchronize_session=False)
                    .where(Order.id == order_id, Order.status.in_(CANCELLABLE))
                    .values(
                        status=OrderStatus.CANCELLED,
                        cancelled_by="admin",
                        cancel_reason=by[:64],
                        cancelled_at=utcnow(),
                    )
                )
                if res.rowcount != 1:
                    return False
                if driver is not None:
                    await s.execute(
                        update(Driver)
                        .execution_options(synchronize_session=False)
                        .where(Driver.id == driver.id, Driver.current_order_id == order_id)
                        .values(current_order_id=None)
                    )
            self.dispatch.wake(order_id)
            await self._withdraw_offers(order_id)
            await self._drop_live(order, passenger)
            text = f"Buyurtma #{order_id} operator tomonidan bekor qilindi."
            card = Card("❌ Buyurtma bekor qilindi").para(text)
            await self.msg.replace(Role.PASSENGER, passenger.tg_id, order.passenger_msg_id, View.of(card))
            if driver is not None:
                await self.msg.replace(Role.DRIVER, driver.tg_id, order.driver_msg_id, View.of(card))
        self._forget(order_id)
        log.info("Buyurtma #%s admin tomonidan bekor qilindi (%s)", order_id, by)
        return True

    async def admin_set_driver_status(self: TaxiService, driver_id: int, status: DriverStatus) -> Driver | None:
        """Haydovchi holatini o'zgartiradi va unga Telegram'da xabar beradi."""
        before = await self.get_driver(driver_id)
        if before is None:
            return None
        d = await self.set_driver_status(driver_id, status)
        if d is None:
            return None
        money = self.views.m(d.balance)
        if status == DriverStatus.APPROVED and before.status == DriverStatus.PENDING:
            text = (
                "🎉 <b>Tabriklaymiz! Arizangiz tasdiqlandi.</b>\n\n"
                f"💳 Balans: {money}\n"
                "Buyurtma olish uchun <b>🟢 Liniyaga chiqish</b> tugmasini bosing."
            )
        elif status == DriverStatus.APPROVED:
            text = "✅ Hisobingiz faollashtirildi."
        elif status == DriverStatus.REJECTED:
            text = "❌ Afsuski, arizangiz rad etildi. Batafsil ma'lumot uchun operatorga murojaat qiling."
        else:
            text = "⛔️ Hisobingiz bloklandi."
        await self.msg.send(Role.DRIVER, d.tg_id, View.plain(text, self.views.driver_menu(False)))
        return d

    async def set_passenger_blocked(self: TaxiService, passenger_id: int, blocked: bool) -> bool:
        async with self.db.session() as s:
            p = await s.get(Passenger, passenger_id)
            if p is None:
                return False
            p.is_blocked = blocked
        return True
