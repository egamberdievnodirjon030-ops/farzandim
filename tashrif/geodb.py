"""Manzillar joyi va bekatlari keshi — barcha kurslar uchun bitta fayl (data/tashrif/geo.db).

Yo'l moduli fon oqimlarida ishlaydi, shuning uchun bu yerda oddiy (sinxron) sqlite3: har bir oqimga o'z ulanishi.
Har bir manzil xarita xizmatidan bir marta so'raladi; bot xabarlari va sayt shu jadvaldan o'qiydi.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

from .sozlama import sozlama

SXEMA = """
CREATE TABLE IF NOT EXISTS address_geo (
  address_norm TEXT PRIMARY KEY,   -- solishtirish uchun soddalashtirilgan manzil
  address      TEXT NOT NULL,      -- manzilning oxirgi ko'rilgan yozilishi
  status       TEXT NOT NULL,      -- ok | bekatsiz | topilmadi | xato
  lat          REAL,
  lon          REAL,
  source       TEXT,               -- yandex | osm | matn | qolda | sayt
  precision    TEXT,               -- aniq | taxminiy
  found_name   TEXT,
  transit_json TEXT,               -- {"bekatlar": [...], "metro": [...]}
  transit_at   TEXT,
  tries        INTEGER NOT NULL DEFAULT 0,
  next_try_at  TEXT,
  updated_at   TEXT NOT NULL
);
"""

_local = threading.local()
_fayl: str | None = None


def fayl() -> str:
    return _fayl or str(sozlama.malumot_papkasi / "geo.db")


def fayl_qoy(yol: str | None) -> None:
    """Testlar uchun: boshqa fayl (":memory:" emas — har bir oqim o'z ulanishini ochadi)."""
    global _fayl
    _fayl = yol
    _local.__dict__.clear()


def ulanish() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "fayl", None) != fayl():
        conn = sqlite3.connect(fayl(), check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.executescript(SXEMA)
        _local.conn, _local.fayl = conn, fayl()
    return conn


def hozir() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def bajar(sql: str, *args) -> sqlite3.Cursor:
    conn = ulanish()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur


def bitta(sql: str, *args) -> sqlite3.Row | None:
    return ulanish().execute(sql, args).fetchone()


def hammasi(sql: str, *args) -> list[sqlite3.Row]:
    return ulanish().execute(sql, args).fetchall()


def qator_dict(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None
