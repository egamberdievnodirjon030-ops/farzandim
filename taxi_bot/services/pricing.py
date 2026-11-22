"""Tarif va komissiya hisoblash."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..config import Settings


@dataclass(frozen=True, slots=True)
class Tariff:
    base_fare: int
    base_km: float
    per_km: int
    free_wait_min: int
    per_wait_min: int
    min_fare: int
    price_round: int
    commission_percent: float

    @classmethod
    def from_settings(cls, s: Settings) -> Tariff:
        return cls(
            base_fare=s.base_fare,
            base_km=s.base_km,
            per_km=s.per_km,
            free_wait_min=s.free_wait_min,
            per_wait_min=s.per_wait_min,
            min_fare=s.min_fare,
            price_round=s.price_round,
            commission_percent=s.commission_percent,
        )

    def _round_up(self, value: float) -> int:
        step = max(1, self.price_round)
        return int(math.ceil(value / step - 1e-9) * step)

    def ride_price(self, distance_m: float) -> int:
        """Masofa bo'yicha narx (kutishsiz)."""
        km = max(0.0, distance_m / 1000)
        price = self.base_fare + max(0.0, km - self.base_km) * self.per_km
        return max(self.min_fare, self._round_up(price))

    def wait_charge(self, wait_seconds: float) -> int:
        # Bepul daqiqalardan keyingi har bir TO'LIQ daqiqa uchun
        paid_min = math.floor(max(0.0, wait_seconds / 60 - self.free_wait_min) + 1e-9)
        if paid_min <= 0:
            return 0
        return self._round_up(paid_min * self.per_wait_min)

    def commission(self, price: int) -> int:
        """Xizmat haqi (masalan 10%) — so'mgacha yaxlitlanadi."""
        return int(round(price * self.commission_percent / 100))

    def describe(self, currency: str) -> str:
        return (
            f"{money(self.base_fare, currency)} ({self.base_km:g} km gacha) + "
            f"{money(self.per_km, currency)}/km"
        )


def money(amount: float | None, currency: str = "so'm") -> str:
    if amount is None:
        return "—"
    return f"{int(amount):,}".replace(",", " ") + f" {currency}"
