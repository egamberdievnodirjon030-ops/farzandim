"""Tuman chegaralari: nuqta qaysi tumanda joylashgan, xarita uchun ko'pburchaklar.

Chegaralar dastur bilan birga keladi (`tashrif/malumot/tumanlar.json`,
OpenStreetMap ma'lumotidan soddalashtirilgan) va tarmoqsiz ishlatiladi:

  * umumiy dashboard xaritasida tumanlar chizig'i va rangi;
  * talaba joylashuvi bo'yicha «hududlar kesimi» — nuqta qaysi ko'pburchak
    ichida ekanligi shu yerda hisoblanadi.
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

from .sozlama import sozlama

_royxat: list[dict] | None = None
_ochildi = False
_qulf = threading.Lock()


def _fayl() -> Path:
    return Path(__file__).resolve().parent / "malumot" / "tumanlar.json"


def _shu_shaharmi(hudud) -> bool:
    try:
        janub, garb, shimol, sharq = (float(x) for x in hudud)
    except (TypeError, ValueError):
        return False
    lat, lon = sozlama.geo_markaz
    return janub <= lat <= shimol and garb <= lon <= sharq


def _och() -> list[dict]:
    """Tumanlar ro'yxati; har birida chegara halqalari va ularni o'rab turgan to'rtburchak."""
    global _royxat, _ochildi
    if _ochildi:
        return _royxat or []
    with _qulf:
        if _ochildi:
            return _royxat or []
        natija: list[dict] = []
        try:
            xom = json.loads(_fayl().read_text(encoding="utf-8"))
            qatorlar = xom["tumanlar"] if _shu_shaharmi(xom.get("hudud")) else []
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            qatorlar = []
        for q in qatorlar:
            try:
                halqalar = [[(float(p[0]), float(p[1])) for p in h] for h in q["chegara"]]
                nuqtalar = [p for h in halqalar for p in h]
                natija.append({
                    "nom": str(q["nom"]), "shahar": bool(q.get("shahar")),
                    "markaz": [float(q["markaz"][0]), float(q["markaz"][1])],
                    "chegara": halqalar,
                    "_ramka": (min(p[0] for p in nuqtalar), min(p[1] for p in nuqtalar),
                               max(p[0] for p in nuqtalar), max(p[1] for p in nuqtalar)),
                })
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        _royxat, _ochildi = natija, True
    return _royxat or []


def unut() -> None:
    """Xotiradagi ro'yxatni tashlaydi — keyingi murojaatda diskdan qayta o'qiladi."""
    global _royxat, _ochildi
    with _qulf:
        _royxat, _ochildi = None, False
    _top.cache_clear()


def royxat() -> list[dict]:
    """Xarita uchun: [{nom, shahar, markaz: [kenglik, uzunlik], chegara: [[[k, u], ...], ...]}]."""
    return [{"nom": t["nom"], "shahar": t["shahar"], "markaz": t["markaz"],
             "chegara": [[[p[0], p[1]] for p in h] for h in t["chegara"]]} for t in _och()]


def nomlar() -> list[str]:
    return [t["nom"] for t in _och()]


def _ichidami(halqalar: list[list[tuple[float, float]]], lat: float, lon: float) -> bool:
    """Nuqta ko'pburchak ichidami (nur usuli; ichki halqalar — teshiklar — ham hisobga olinadi)."""
    kesishdi = False
    for halqa in halqalar:
        for (a_lat, a_lon), (b_lat, b_lon) in zip(halqa, halqa[1:]):
            if (a_lat > lat) != (b_lat > lat) and \
                    lon < a_lon + (lat - a_lat) * (b_lon - a_lon) / (b_lat - a_lat):
                kesishdi = not kesishdi
    return kesishdi


@lru_cache(maxsize=8192)
def _top(lat: float, lon: float) -> str:
    for t in _och():
        janub, garb, shimol, sharq = t["_ramka"]
        if janub <= lat <= shimol and garb <= lon <= sharq and _ichidami(t["chegara"], lat, lon):
            return t["nom"]
    return ""


def top(lat, lon) -> str:
    """Nuqta joylashgan tuman nomi («Uchtepa»); hech biriga tushmasa — bo'sh qator."""
    try:
        return _top(round(float(lat), 5), round(float(lon), 5))
    except (TypeError, ValueError):
        return ""
