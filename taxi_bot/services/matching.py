"""Eng yaqin bo'sh haydovchilarni tanlash va saralash qoidalari.

Qoidalar:
  1. Faqat bo'sh (yo'lovchisi yo'q), liniyadagi, tasdiqlangan, balansi yetarli va
     joylashuvi yangi (eskirmagan) haydovchilar.
  2. Masofa diapazonlari bo'yicha to'lqinlar: 1 km → 2 km → 3.5 km → ...
     Har bir to'lqin `wave_timeout_sec` (standart 60 s) kutadi.
  3. Har bir to'lqin ichida reytingi yuqori haydovchilar birinchi ko'radi
     (`priority_rating` dan yuqorilar `priority_headstart_sec` oldin oladi),
     so'ng reyting kamayishi va yetib kelish vaqti bo'yicha.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Candidate:
    driver_id: int
    tg_id: int
    rating: float
    straight_m: float  # to'g'ri chiziq bo'yicha
    road_m: float  # yo'l bo'yicha (OSRM yoki taxminiy)
    eta_s: float
    precise: bool  # True — road_m haqiqiy yo'l bo'yicha hisoblangan
    bearing: float = 0.0  # haydovchidan yo'lovchiga yo'nalish
    accuracy_m: float | None = None

    @property
    def band_m(self) -> float:
        """Diapazonga tegishlilik masofasi: aniq yo'l masofasi bo'lsa — u, aks holda to'g'ri chiziq."""
        return self.road_m if self.precise else self.straight_m


def rank_key(c: Candidate) -> tuple[float, float, float]:
    # Reyting 0.05 aniqlikda guruhlanadi — 4.93 va 4.91 deyarli teng, keyin yaqinlik hal qiladi.
    return (-round(c.rating * 20) / 20, c.eta_s, c.band_m)


def select_wave(
    candidates: list[Candidate],
    radius_m: float,
    priority_rating: float,
) -> tuple[list[Candidate], list[Candidate]]:
    """Diapazon ichidagilarni (ustuvor, qolganlar) ga ajratadi — ikkalasi ham saralangan."""
    in_band = sorted((c for c in candidates if c.band_m <= radius_m), key=rank_key)
    priority = [c for c in in_band if c.rating >= priority_rating]
    rest = [c for c in in_band if c.rating < priority_rating]
    return priority, rest


def bayesian_rating(rating_sum: int, rating_count: int, prior: float, weight: int) -> float:
    """Yangi haydovchilar uchun adolatli reyting (bir nechta baho bilan sakrab ketmaydi)."""
    if rating_count <= 0:
        return round(prior, 2)
    return round((rating_sum + prior * weight) / (rating_count + weight), 2)
