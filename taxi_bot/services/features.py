"""Raqobatchilardan ajratib turadigan imkoniyatlar.

* 🏠 Saqlangan manzillar (Uy / Ish / boshqa) — taksi 3 bosishda;
* ❤️ Sevimli haydovchi — buyurtma avval unga ko'rinadi;
* 🏡 "Uyga" rejimi — haydovchilar uchun.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from ..db.models import (
    Driver,
    FavoriteDriver,
    Passenger,
    SavedPlace,
)
from ..ui.views import PLACE_NAMES

if TYPE_CHECKING:
    from .taxi import TaxiService

log = logging.getLogger(__name__)

MAX_OTHER_PLACES = 5
PLACE_KINDS = ("home", "work", "other")


class FeaturesMixin:
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

    # ------------------------------------------------------------------ haydovchi sozlamalari
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
