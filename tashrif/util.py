"""Yo'l modulining yordamchilari (tashrif-py util.py dan)."""
from __future__ import annotations

from datetime import datetime, timezone

from utils import now

APOSTROFLAR = "ʻʼ‘’'`´"


def bugun() -> str:
    return now().strftime("%Y-%m-%d")


def utc_hozir() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def oddiy_ism(s) -> str:
    """Solishtirish uchun ismni soddalashtiradi (apostrof va qo'sh bo'shliqsiz)."""
    v = str(s or "").lower()
    for a in APOSTROFLAR:
        v = v.replace(a, "")
    return " ".join(v.split())
