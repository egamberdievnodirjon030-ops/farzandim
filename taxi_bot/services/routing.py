"""Yo'l masofasi, vaqti va xaritadagi marshrut chizig'i (haqiqiy ko'chalar bo'yicha, burilishlari bilan).

* `OSRM_URL` — o'zingizning OSRM serveringiz (README): hamma hisob-kitoblar shu orqali, cheklovsiz.
* `ROUTE_URLS` — ommaviy OSRM serverlari (standart: OpenStreetMap jamoasining FOSSGIS serveri va OSRM demo).
  Ular faqat marshrut chizig'i va narx hisobi uchun ishlatiladi: natijalar keshlanadi, so'rovlar sekundiga
  ko'pi bilan bitta (ularning foydalanish qoidasi), ishlamay qolgan server bir daqiqaga chetlab o'tiladi.
  Haydovchilarni saralashdagi ko'p sonli hisob (table) ommaviy serverlarga yuborilmaydi.
* Hech biri ishlamasa — to'g'ri chiziqli masofa * yo'l koeffitsienti (taxminiy).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

import aiohttp

from .geo import Point, haversine_m

log = logging.getLogger(__name__)

_TABLE_CHUNK = 90
_CACHE_SIZE = 600
_CACHE_TTL = 15 * 60
_PUBLIC_INTERVAL = 1.05  # ommaviy serverlar: sekundiga ko'pi bilan 1 so'rov
_PUBLIC_MAX_WAIT = 4.0  # navbat shundan uzun bo'lsa — kutmasdan taxminiy hisob
_DOWN_FOR = 60.0
USER_AGENT = "ShaharTaksi/1.0 (Telegram taxi bot; OSRM route display)"


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    distance_m: float
    duration_s: float
    precise: bool  # True — haqiqiy yo'llar bo'yicha (OSRM)


class RoutingService:
    def __init__(
        self,
        osrm_url: str | None,
        road_factor: float = 1.3,
        city_speed_kmh: float = 25.0,
        timeout_sec: float = 2.5,
        public_urls: list[str] | None = None,
        public_timeout_sec: float = 4.0,
    ) -> None:
        self.osrm_url = osrm_url.rstrip("/") if osrm_url else None
        self.public_urls = [u.rstrip("/") for u in (public_urls or []) if u]
        self.road_factor = road_factor
        self.speed_mps = city_speed_kmh * 1000 / 3600
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._public_timeout = aiohttp.ClientTimeout(total=public_timeout_sec)
        self._session: aiohttp.ClientSession | None = None
        self._cache: OrderedDict[tuple, tuple[float, RouteEstimate, list[list[float]]]] = OrderedDict()
        self._public_lock = asyncio.Lock()
        self._public_last = 0.0
        self._down_until: dict[str, float] = {}

    # -- fallback ---------------------------------------------------------
    def estimate(self, a: Point, b: Point) -> RouteEstimate:
        road = haversine_m(a.lat, a.lon, b.lat, b.lon) * self.road_factor
        return RouteEstimate(road, road / self.speed_mps, precise=False)

    # -- HTTP -------------------------------------------------------------
    def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})
        return self._session

    async def _fetch(self, base: str, path: str, params: dict[str, str], timeout: aiohttp.ClientTimeout) -> dict | None:
        try:
            async with self._http().get(f"{base}{path}", params=params, timeout=timeout) as resp:
                if resp.status != 200:
                    log.warning("OSRM %s%s -> HTTP %s", base, path.split("/")[1:3], resp.status)
                    return None
                data = await resp.json(content_type=None)
                return data if data.get("code") == "Ok" else None
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            log.warning("OSRM so'rovi muvaffaqiyatsiz (%s): %s", base, exc.__class__.__name__)
            return None

    async def _get(self, path: str, params: dict[str, str]) -> dict | None:
        """O'z OSRM serveringiz (cheklovsiz)."""
        if not self.osrm_url:
            return None
        return await self._fetch(self.osrm_url, path, params, self._timeout)

    async def _get_public(self, path: str, params: dict[str, str]) -> dict | None:
        """Ommaviy serverlar: navbat bilan, sekundiga 1 tadan, ishlamaganini vaqtincha chetlab."""
        for base in self.public_urls:
            if self._down_until.get(base, 0) > time.monotonic():
                continue
            try:
                await asyncio.wait_for(self._public_lock.acquire(), _PUBLIC_MAX_WAIT)
            except TimeoutError:
                return None  # navbat uzun — bu safar taxminiy hisob
            try:
                wait = self._public_last + _PUBLIC_INTERVAL - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
                data = await self._fetch(base, path, params, self._public_timeout)
                self._public_last = time.monotonic()
            finally:
                self._public_lock.release()
            if data is not None:
                return data
            self._down_until[base] = time.monotonic() + _DOWN_FOR
        return None

    # -- marshrut ---------------------------------------------------------
    @staticmethod
    def _key(a: Point, b: Point) -> tuple:
        return (round(a.lat, 5), round(a.lon, 5), round(b.lat, 5), round(b.lon, 5))

    async def _route_full(self, a: Point, b: Point) -> tuple[RouteEstimate, list[list[float]]] | None:
        key = self._key(a, b)
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            self._cache.move_to_end(key)
            return hit[1], hit[2]
        path = f"/route/v1/driving/{a.lon:.6f},{a.lat:.6f};{b.lon:.6f},{b.lat:.6f}"
        params = {"overview": "full", "geometries": "geojson", "alternatives": "false", "steps": "false"}
        data = await self._get(path, params) if self.osrm_url else await self._get_public(path, params)
        if not data or not data.get("routes"):
            return None
        r = data["routes"][0]
        coords = [[lat, lon] for lon, lat in r["geometry"]["coordinates"]]
        est = RouteEstimate(float(r["distance"]), float(r["duration"]), precise=True)
        self._cache[key] = (time.monotonic() + _CACHE_TTL, est, coords)
        while len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)
        return est, coords

    async def route(self, a: Point, b: Point) -> RouteEstimate:
        full = await self._route_full(a, b)
        return full[0] if full else self.estimate(a, b)

    async def route_quick(self, a: Point, b: Point, budget_s: float = 2.0) -> RouteEstimate:
        """Shoshilinch joylar uchun (masalan buyurtmani qabul qilish): kechiksa — taxminiy hisob."""
        try:
            return await asyncio.wait_for(self.route(a, b), budget_s)
        except TimeoutError:
            return self.estimate(a, b)

    async def route_geometry(self, a: Point, b: Point) -> tuple[RouteEstimate, list[list[float]]]:
        """Marshrut chizig'i [[lat, lon], ...] — ko'chalar bo'yicha, burilishlari bilan (xaritada chizish uchun)."""
        full = await self._route_full(a, b)
        if full:
            return full
        return self.estimate(a, b), [[a.lat, a.lon], [b.lat, b.lon]]

    async def many_to_one(self, sources: list[Point], dest: Point) -> list[RouteEstimate]:
        """Ko'p haydovchidan bitta nuqtagacha (yo'lovchi) yo'l masofasi — faqat o'z OSRM serveringiz bilan."""
        if not sources:
            return []
        if not self.osrm_url:
            return [self.estimate(s, dest) for s in sources]
        results: list[RouteEstimate] = []
        for start in range(0, len(sources), _TABLE_CHUNK):
            chunk = sources[start : start + _TABLE_CHUNK]
            coords = ";".join(
                [f"{dest.lon:.6f},{dest.lat:.6f}"] + [f"{p.lon:.6f},{p.lat:.6f}" for p in chunk]
            )
            data = await self._get(
                f"/table/v1/driving/{coords}",
                {
                    "sources": ";".join(str(i) for i in range(1, len(chunk) + 1)),
                    "destinations": "0",
                    "annotations": "distance,duration",
                },
            )
            for idx, src in enumerate(chunk):
                try:
                    dist = data["distances"][idx][0] if data else None
                    dur = data["durations"][idx][0] if data else None
                except (KeyError, IndexError, TypeError):
                    dist = dur = None
                if dist is None or dur is None:
                    results.append(self.estimate(src, dest))
                else:
                    results.append(RouteEstimate(float(dist), float(dur), precise=True))
        return results

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
