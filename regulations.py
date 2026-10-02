"""Universitet ichki nizomlari — barcha kurslar uchun umumiy ro'yxat (super-admin boshqaradi).

Har bir nizom — PDF fayl (data/regulations/ da saqlanadi, ilovada sahifalab ko'rsatiladi) yoki tashqi havola
(masalan, universitet saytidagi sahifa). Nomi va izohi ---ru / ---en bilan uch tilda yozilishi mumkin.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from config import DATA_DIR
from tenancy import central
from utils import now_iso


def folder() -> Path:
    p = Path(DATA_DIR) / "regulations"
    p.mkdir(parents=True, exist_ok=True)
    return p


async def all_items() -> list[dict]:
    return await central._all("SELECT * FROM regulations ORDER BY sort, id DESC")


async def get(rid: int) -> dict | None:
    return await central._one("SELECT * FROM regulations WHERE id = ?", (rid,))


async def add(title: str, description: str | None, by: int, pdf: bytes | None = None, url: str | None = None) -> int:
    name = None
    if pdf:
        name = f"{secrets.token_hex(10)}.pdf"
        (folder() / name).write_bytes(pdf)
    cur = await central.conn.execute(
        "INSERT INTO regulations (title, description, file, url, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title.strip()[:300], (description or "").strip()[:1000] or None, name, (url or "").strip() or None, by,
         now_iso()))
    await central.conn.commit()
    return cur.lastrowid


async def delete(rid: int) -> None:
    r = await get(rid)
    if r and r.get("file"):
        (folder() / Path(r["file"]).name).unlink(missing_ok=True)
    await central._write("DELETE FROM regulations WHERE id = ?", (rid,))


def read_pdf(r: dict) -> bytes | None:
    if not r or not r.get("file"):
        return None
    p = folder() / Path(r["file"]).name  # yo'l bilan chalg'itishga yo'l qo'yilmaydi
    return p.read_bytes() if p.exists() else None
