"""Tashrif moduli sozlamalari (.env): yo'l ma'lumoti, xarita xizmatlari, javob va eslatma muddatlari."""
from __future__ import annotations

import os
from pathlib import Path

from config import DATA_DIR


def _bool(nom: str, standart: bool) -> bool:
    v = os.getenv(nom)
    if v is None or not v.strip():
        return standart
    return v.strip().lower() not in ("0", "yoq", "yo'q", "no", "false", "off")


def _juft(nom: str, standart: tuple[float, float]) -> tuple[float, float]:
    try:
        a, b = (float(x) for x in os.getenv(nom, "").replace(";", ",").split(","))
        return a, b
    except ValueError:
        return standart


def _int(nom: str, standart: int) -> int:
    try:
        return int(os.getenv(nom, "") or standart)
    except ValueError:
        return standart


class Sozlama:
    def __init__(self) -> None:
        self.yol_malumoti = _bool("YOL_MALUMOTI", True)          # yoq — manzil hech qaysi xarita xizmatiga yuborilmaydi
        self.yandex_kalit = os.getenv("YANDEX_GEOCODER_KEY", "").strip()
        self.geo_shahar = os.getenv("GEO_SHAHAR", "Toshkent").strip() or "Toshkent"
        self.geo_markaz = _juft("GEO_MARKAZ", (41.3111, 69.2797))   # kenglik, uzunlik
        self.overpass = [x.strip() for x in os.getenv(
            "OVERPASS_URL", "https://overpass-api.de/api/interpreter,"
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter").split(",") if x.strip()]
        self.sinov = _bool("TASHRIF_SINOV", False)                  # sinovda fon oqimlari ishga tushmaydi
        self.javob_soat = _int("STUDENT_REPLY_HOURS", 24)           # talaba javobi uchun muddat
        self.eslatma_soat = _int("REMINDER_HOURS_BEFORE", 3)        # tashrifdan necha soat oldin eslatma

    @property
    def malumot_papkasi(self) -> Path:
        """Manzillar keshi va yangilangan bekatlar nusxasi."""
        p = Path(DATA_DIR) / "tashrif"
        p.mkdir(parents=True, exist_ok=True)
        return p


sozlama = Sozlama()
