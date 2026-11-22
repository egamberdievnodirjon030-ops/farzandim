"""Raqobatchilardan ajratib turadigan imkoniyatlar.

* 🏠 Saqlangan manzillar (Uy / Ish / boshqa) — taksi 3 bosishda;
* ❤️ Sevimli haydovchi — buyurtma avval unga ko'rinadi;
* 👨‍👩‍👧 Safarni yaqinlarga ulashish — havola orqali jonli kuzatuv;
* 🆘 SOS — dispetcherga mashina joylashuvi bilan xabar;
* ⚡ Avto-qabul va 🏡 "Uyga" rejimi — haydovchilar uchun.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from sqlalchemy import delete, func, select

from ..db.models import (
    DRIVER_ACTIVE_STATUSES,
    Driver,
    FavoriteDriver,
    Order,
    Passenger,
    SavedPlace,
    TripWatcher,
)
from ..ui.kit import View, h
from ..ui.messenger import Role
from ..ui.views import PLACE_NAMES

if TYPE_CHECKING:
    from .taxi import TaxiService

log = logging.getLogger(__name__)

MAX_OTHER_PLACES = 5
MAX_WATCHERS = 5
PLACE_KINDS = ("home", "work", "other")


class FeaturesMixin:
    share_username: str | None = None

    # ------------------------------------------------------------------ ulashish havolasi
    def share_url(self: TaxiService, order: Order) -> str | None:
        if not self.share_username or not order.track_token:
            return None
        link = f"https://t.me/{self.share_username}?start=trk_{order.track_token}"
        text = "🚕 Men taksidaman — safarimni jonli kuzatib turing"
        return "https://t.me/share/url?" + urlencode({"url": link, "text": text})

    # ------------------------------------------------------------------ saqlangan manzillar
    async def list_places(self: TaxiService, passenger_id: int) -> list[SavedPlace]:
        async with self.db.session() as s:
            rows = (await s.scalars(select(SavedPlace).where(SavedPlace.passenger_id == passenger_id))).all()
        order = {k: i for i, k in enumerate(PLACE_KINDS)}
        return sorted(rows, key=lambda p: (order.get(p.kind, 9), p.id))

    async def get_place(self: TaxiService, passenger_tg: int, place_id: int) -> SavedPlace | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(SavedPlace)
                .join(Passenger, Passenger.id == SavedPlace.passenger_id)
                .where(SavedPlace.id == place_id, Passenger.tg_id == passenger_tg)
            )

    async def save_place(
        self: TaxiService, passenger_tg: int, kind: str, lat: float, lon: float, title: str | None = None
    ) -> SavedPlace | None:
        if kind not in PLACE_KINDS:
            return None
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == passenger_tg))
            if p is None:
                return None
            if kind in ("home", "work"):
                await s.execute(
                    delete(SavedPlace).where(SavedPlace.passenger_id == p.id, SavedPlace.kind == kind)
                )
            else:
                count = await s.scalar(
                    select(func.count(SavedPlace.id)).where(
                        SavedPlace.passenger_id == p.id, SavedPlace.kind == "other"
                    )
                )
                if (count or 0) >= MAX_OTHER_PLACES:
                    return None
            place = SavedPlace(
                passenger_id=p.id,
                kind=kind,
                title=(title or PLACE_NAMES[kind]).strip()[:64],
                lat=lat,
                lon=lon,
            )
            s.add(place)
            await s.flush()
            return place

    async def save_place_from_order(
        self: TaxiService, passenger_tg: int, order_id: int, kind: str
    ) -> SavedPlace | None:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg or not bundle[0].has_destination:
            return None
        order = bundle[0]
        return await self.save_place(passenger_tg, kind, order.dest_lat, order.dest_lon)  # type: ignore[arg-type]

    async def delete_place(self: TaxiService, passenger_tg: int, place_id: int) -> bool:
        place = await self.get_place(passenger_tg, place_id)
        if place is None:
            return False
        async with self.db.session() as s:
            await s.execute(delete(SavedPlace).where(SavedPlace.id == place.id))
        return True

    # ------------------------------------------------------------------ sevimli haydovchilar
    async def is_favorite(self: TaxiService, passenger_id: int, driver_id: int) -> bool:
        async with self.db.session() as s:
            return bool(
                await s.scalar(
                    select(FavoriteDriver.id).where(
                        FavoriteDriver.passenger_id == passenger_id, FavoriteDriver.driver_id == driver_id
                    )
                )
            )

    async def add_favorite(self: TaxiService, passenger_tg: int, order_id: int) -> bool:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg or bundle[2] is None:
            return False
        passenger, driver = bundle[1], bundle[2]
        if await self.is_favorite(passenger.id, driver.id):
            return True
        async with self.db.session() as s:
            s.add(FavoriteDriver(passenger_id=passenger.id, driver_id=driver.id))
        return True

    async def remove_favorite(self: TaxiService, passenger_tg: int, driver_id: int) -> bool:
        async with self.db.session() as s:
            p = await s.scalar(select(Passenger).where(Passenger.tg_id == passenger_tg))
            if p is None:
                return False
            res = await s.execute(
                delete(FavoriteDriver).where(
                    FavoriteDriver.passenger_id == p.id, FavoriteDriver.driver_id == driver_id
                )
            )
            return bool(res.rowcount)

    async def list_favorites(self: TaxiService, passenger_id: int) -> list[Driver]:
        async with self.db.session() as s:
            return list(
                (
                    await s.scalars(
                        select(Driver)
                        .join(FavoriteDriver, FavoriteDriver.driver_id == Driver.id)
                        .where(FavoriteDriver.passenger_id == passenger_id)
                        .order_by(FavoriteDriver.id.desc())
                    )
                ).all()
            )

    # ------------------------------------------------------------------ yaqinlar kuzatuvi
    async def watch_trip(self: TaxiService, token: str, tg_id: int) -> str:
        """Natija: ok | not_found | ended | limit."""
        async with self.db.session() as s:
            order = await s.scalar(select(Order).where(Order.track_token == token))
            if order is None:
                return "not_found"
            if order.status not in DRIVER_ACTIVE_STATUSES or order.driver_id is None:
                return "ended"
            exists = await s.scalar(
                select(TripWatcher.id).where(TripWatcher.order_id == order.id, TripWatcher.tg_id == tg_id)
            )
            if not exists:
                count = await s.scalar(select(func.count(TripWatcher.id)).where(TripWatcher.order_id == order.id))
                if (count or 0) >= MAX_WATCHERS:
                    return "limit"
                s.add(TripWatcher(order_id=order.id, tg_id=tg_id))
            driver = await s.get(Driver, order.driver_id)
        await self.msg.send(Role.PASSENGER, tg_id, self.views.watcher_card(order, driver))  # type: ignore[arg-type]
        if driver is not None and self._driver_location_fresh(driver):
            await self._watchers_live(order.id, driver.lat, driver.lon, driver.loc_heading, only_tg=tg_id)  # type: ignore[arg-type]
        return "ok"

    async def _watchers(self: TaxiService, order_id: int) -> list[TripWatcher]:
        async with self.db.session() as s:
            return list((await s.scalars(select(TripWatcher).where(TripWatcher.order_id == order_id))).all())

    async def _watchers_status(self: TaxiService, order_id: int, text: str, *, final: bool = False) -> None:
        watchers = await self._watchers(order_id)
        for w in watchers:
            if final and w.live_msg_id:
                await self.msg.delete(Role.PASSENGER, w.tg_id, w.live_msg_id)
            await self.msg.send(Role.PASSENGER, w.tg_id, View.plain(text), silent=not final)
        if final and watchers:
            async with self.db.session() as s:
                await s.execute(delete(TripWatcher).where(TripWatcher.order_id == order_id))

    async def _watchers_reset_live(self: TaxiService, order_id: int) -> None:
        """Haydovchi almashganda eski mashina joylashuvi yaqinlardan o'chiriladi."""
        watchers = await self._watchers(order_id)
        for w in watchers:
            if w.live_msg_id:
                await self.msg.delete(Role.PASSENGER, w.tg_id, w.live_msg_id)
        if watchers:
            async with self.db.session() as s:
                for w in watchers:
                    row = await s.get(TripWatcher, w.id)
                    if row:
                        row.live_msg_id = None

    async def _watchers_live(
        self: TaxiService,
        order_id: int,
        lat: float,
        lon: float,
        heading: int | None,
        *,
        only_tg: int | None = None,
    ) -> None:
        for w in await self._watchers(order_id):
            if only_tg is not None and w.tg_id != only_tg:
                continue
            if w.live_msg_id:
                await self.msg.edit_live_location(Role.PASSENGER, w.tg_id, w.live_msg_id, lat, lon, heading)
                continue
            live_id = await self.msg.send_live_location(Role.PASSENGER, w.tg_id, lat, lon, heading)
            if live_id:
                async with self.db.session() as s:
                    row = await s.get(TripWatcher, w.id)
                    if row:
                        row.live_msg_id = live_id

    # ------------------------------------------------------------------ SOS
    async def sos(self: TaxiService, passenger_tg: int, order_id: int) -> bool:
        bundle = await self._order_bundle(order_id)
        if bundle is None or bundle[1].tg_id != passenger_tg or bundle[2] is None:
            return False
        order, passenger, driver = bundle
        if order.status not in DRIVER_ACTIVE_STATUSES:
            return False
        log.warning("SOS: buyurtma #%s", order_id)
        await self.msg.notify_admins(
            View.plain(
                f"🆘 <b>SOS — buyurtma #{order.id}</b>\n\n"
                f"🙋 Yo'lovchi: <code>{h(passenger.phone or '—')}</code>"
                + (f" (safarda: <code>{h(order.rider_phone)}</code>)" if order.rider_phone else "")
                + f"\n🚕 Haydovchi: {h(driver.full_name)} · <code>{h(driver.phone or '—')}</code>\n"
                f"🚘 {h(driver.car_color)} {h(driver.car_model)} · <b>{h(driver.car_plate)}</b>\n\n"
                "Mashinaning so'nggi joylashuvi quyida. Darhol bog'laning!"
            )
        )
        if driver.lat is not None and driver.lon is not None:
            for chat_id in self.msg.admin_chat_ids:
                await self.msg.send_live_location(Role.DRIVER, chat_id, driver.lat, driver.lon, driver.loc_heading)
        await self._watchers_status(
            order.id, f"🆘 Yaqiningiz safar davomida SOS tugmasini bosdi. Dispetcherga xabar berildi (#{order.id})."
        )
        return True

    # ------------------------------------------------------------------ haydovchi sozlamalari
    async def toggle_auto_accept(self: TaxiService, tg_id: int) -> Driver | None:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is not None:
                d.auto_accept = not d.auto_accept
            return d

    async def set_home(self: TaxiService, tg_id: int, lat: float, lon: float) -> Driver | None:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is not None:
                d.home_lat, d.home_lon = lat, lon
            return d

    async def toggle_home_mode(self: TaxiService, tg_id: int) -> Driver | None:
        async with self.db.session() as s:
            d = await s.scalar(select(Driver).where(Driver.tg_id == tg_id))
            if d is not None and d.home_lat is not None:
                d.home_mode = not d.home_mode
            return d
