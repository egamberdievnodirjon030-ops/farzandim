"""Geolokatsiya hisob-kitoblari."""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lon: float


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ikki nuqta orasidagi masofa (metr), Haversine formulasi."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Radius bo'yicha (min_lat, max_lat, min_lon, max_lon) — SQL indeks filtri uchun."""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """1-nuqtadan 2-nuqtaga yo'nalish (0..360, shimoldan soat yo'nalishida)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dlmb) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlmb)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


_COMPASS = (
    ("⬆️", "shimolda"),
    ("↗️", "shimoli-sharqda"),
    ("➡️", "sharqda"),
    ("↘️", "janubi-sharqda"),
    ("⬇️", "janubda"),
    ("↙️", "janubi-g'arbda"),
    ("⬅️", "g'arbda"),
    ("↖️", "shimoli-g'arbda"),
)


_COMPASS_TO = (
    "shimolga",
    "shimoli-sharqqa",
    "sharqqa",
    "janubi-sharqqa",
    "janubga",
    "janubi-g'arbga",
    "g'arbga",
    "shimoli-g'arbga",
)


def _sector(bearing: float) -> int:
    return int(((bearing % 360) + 22.5) // 45) % 8


def compass(bearing: float) -> str:
    """Qayerda: "↗️ shimoli-sharqda"."""
    arrow, name = _COMPASS[_sector(bearing)]
    return f"{arrow} {name}"


def compass_to(bearing: float) -> str:
    """Qayerga: "↗️ shimoli-sharqqa"."""
    idx = _sector(bearing)
    return f"{_COMPASS[idx][0]} {_COMPASS_TO[idx]}"


def format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{int(round(meters / 10.0) * 10)} m"
    km = meters / 1000
    return f"{km:.1f} km".replace(".0 km", " km")


def format_duration(seconds: float) -> str:
    minutes = max(1, int(math.ceil(seconds / 60)))
    if minutes < 60:
        return f"{minutes} daq"
    hours, rest = divmod(minutes, 60)
    return f"{hours} soat {rest} daq" if rest else f"{hours} soat"
