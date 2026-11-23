"""Manzil qidirish va koordinatadan manzil aniqlash (OpenStreetMap Nominatim).

Nominatim qoidalari: sekundiga 1 tadan ko'p so'rov yubormaslik, aniq User-Agent — shuning uchun
global navbat (1 s) va xotirada kesh ishlatiladi. Kichik shahar taksisi uchun bu yetarli.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict

import aiohttp

log = logging.getLogger(__name__)

USER_AGENT = "CityTaxiTelegramBot/1.0 (self-hosted)"
CACHE_SIZE = 3000


class Geocoder:
    def __init__(self, base_url: str | None, country: str = "uz", language: str = "uz,ru") -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.country = country
        self.language = language
        self._cache: OrderedDict[tuple, object] = OrderedDict()
        self._lock = asyncio.Lock()
        self._last = 0.0
        self._session: aiohttp.ClientSession | None = None

    def _cached(self, key: tuple):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _store(self, key: tuple, value) -> None:
        self._cache[key] = value
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)

    async def _get(self, path: str, params: dict) -> object | None:
        if not self.base_url:
            return None
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=6), headers={"User-Agent": USER_AGENT}
            )
        async with self._lock:  # 1 so'rov / sekund
            wait = 1.0 - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
        try:
            async with self._session.get(f"{self.base_url}{path}", params=params) as resp:
                if resp.status != 200:
                    log.warning("Geocoder HTTP %s", resp.status)
                    return None
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            log.warning("Geocoder xatosi: %s", exc)
            return None

    @staticmethod
    def _format(item: dict) -> dict:
        a = item.get("address") or {}
        street = a.get("road") or a.get("pedestrian") or a.get("neighbourhood") or ""
        house = a.get("house_number")
        name = item.get("name") or ""
        title = name or (f"{street} {house}".strip() if street else "") or item.get("display_name", "").split(",")[0]
        area = a.get("suburb") or a.get("city_district") or a.get("quarter") or ""
        city = a.get("city") or a.get("town") or a.get("village") or ""
        sub_parts = [p for p in ([street] if name and street else []) + [area, city] if p and p != title]
        return {
            "title": title[:80] or "Belgilangan nuqta",
            "subtitle": ", ".join(dict.fromkeys(sub_parts))[:100],
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
        }

    async def search(self, query: str, near: tuple[float, float] | None = None) -> list[dict]:
        query = query.strip()
        if len(query) < 2:
            return []
        key = ("s", query.lower(), round(near[0], 1) if near else None, round(near[1], 1) if near else None)
        cached = self._cached(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        params = {
            "q": query, "format": "jsonv2", "addressdetails": "1", "limit": "7",
            "accept-language": self.language, "countrycodes": self.country,
        }
        if near:
            lat, lon = near
            params["viewbox"] = f"{lon - 0.35},{lat + 0.25},{lon + 0.35},{lat - 0.25}"
        data = await self._get("/search", params)
        result = [self._format(x) for x in data] if isinstance(data, list) else []
        if data is not None:
            self._store(key, result)
        return result

    async def reverse(self, lat: float, lon: float) -> dict | None:
        key = ("r", round(lat, 4), round(lon, 4))
        cached = self._cached(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        data = await self._get(
            "/reverse",
            {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2", "addressdetails": "1",
             "zoom": "18", "accept-language": self.language},
        )
        if not isinstance(data, dict) or "lat" not in data:
            return None
        result = self._format(data)
        result["lat"], result["lon"] = lat, lon
        self._store(key, result)
        return result

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
