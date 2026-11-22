"""Yo'l masofasi va vaqtini hisoblash.

OSRM_URL berilgan bo'lsa — haqiqiy yo'llar bo'yicha (OSRM table/route API),
aks holda to'g'ri chiziqli masofa * yo'l koeffitsienti bilan taxminiy hisoblanadi.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

from .geo import Point, haversine_m

log = logging.getLogger(__name__)

_TABLE_CHUNK = 90


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    distance_m: float
    duration_s: float
    precise: bool  # True — OSRM orqali haqiqiy yo'l bo'yicha


class RoutingService:
    def __init__(
        self,
        osrm_url: str | None,
        road_factor: float = 1.3,
        city_speed_kmh: float = 25.0,
        timeout_sec: float = 2.5,
    ) -> None:
        self.osrm_url = osrm_url.rstrip("/") if osrm_url else None
        self.road_factor = road_factor
        self.speed_mps = city_speed_kmh * 1000 / 3600
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._session: aiohttp.ClientSession | None = None

    # -- fallback ---------------------------------------------------------
    def estimate(self, a: Point, b: Point) -> RouteEstimate:
        road = haversine_m(a.lat, a.lon, b.lat, b.lon) * self.road_factor
        return RouteEstimate(road, road / self.speed_mps, precise=False)

    # -- OSRM -------------------------------------------------------------
    async def _get(self, path: str, params: dict[str, str]) -> dict | None:
        if not self.osrm_url:
            return None
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        try:
            async with self._session.get(f"{self.osrm_url}{path}", params=params) as resp:
                if resp.status != 200:
                    log.warning("OSRM %s -> HTTP %s", path, resp.status)
                    return None
                data = await resp.json(content_type=None)
                return data if data.get("code") == "Ok" else None
        except (TimeoutError, aiohttp.ClientError, ValueError) as exc:
            log.warning("OSRM so'rovi muvaffaqiyatsiz: %s", exc)
            return None

    async def route(self, a: Point, b: Point) -> RouteEstimate:
        data = await self._get(
            f"/route/v1/driving/{a.lon:.6f},{a.lat:.6f};{b.lon:.6f},{b.lat:.6f}",
            {"overview": "false", "alternatives": "false", "steps": "false"},
        )
        if data and data.get("routes"):
            r = data["routes"][0]
            return RouteEstimate(float(r["distance"]), float(r["duration"]), precise=True)
        return self.estimate(a, b)

    async def many_to_one(self, sources: list[Point], dest: Point) -> list[RouteEstimate]:
        """Ko'p haydovchidan bitta nuqtagacha (yo'lovchi) yo'l masofasi."""
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
