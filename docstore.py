"""Rasmiy hujjatlar ombori va ko'rish: PDF ni ilovaning o'zida ochish (sahifalar rasm ko'rinishida).

Hujjat ikki joyda bo'lishi mumkin:
  • Telegram serverida (botdan yuborilgan hujjatlar) — bazada file_id;
  • server papkasida data/<kurs>/documents/ (ilova va kompyuter versiyasidan yuborilganlar) — «local:<nom>.pdf».
Android'dagi Telegram PDF ni o'zi ko'rsata olmaydi, shuning uchun sahifalar PNG rasmga aylantiriladi (pypdfium2) —
bu har qanday telefonda ishlaydi. Fayllar va tayyor rasmlar xotirada qisqa muddat saqlanadi (LRU).
"""
from __future__ import annotations

import asyncio
import io
import secrets
from collections import OrderedDict
from pathlib import Path

import pypdfium2 as pdfium

from config import DATA_DIR

LOCAL = "local:"
MAX_PAGES = 60
_BYTES: "OrderedDict[str, bytes]" = OrderedDict()   # file_id -> PDF
_PNG: "OrderedDict[tuple, bytes]" = OrderedDict()    # (file_id, sahifa, kenglik) -> PNG


def _lru_put(cache: OrderedDict, key, value, limit: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


def folder(course: str) -> Path:
    p = Path(DATA_DIR) / (course or "_") / "documents"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_local(course: str, data: bytes) -> str:
    """PDF ni kurs papkasiga saqlaydi; qaytaradi: bazaga yoziladigan file_id («local:<tasodifiy nom>.pdf»)."""
    name = f"{secrets.token_hex(12)}.pdf"
    (folder(course) / name).write_bytes(data)
    return LOCAL + name


def is_local(file_id: str | None) -> bool:
    return bool(file_id) and file_id.startswith(LOCAL)


async def load(bot, course: str, file_id: str) -> bytes:
    """Hujjat baytlari: mahalliy papkadan yoki Telegram serveridan."""
    if file_id in _BYTES:
        _BYTES.move_to_end(file_id)
        return _BYTES[file_id]
    if is_local(file_id):
        name = Path(file_id[len(LOCAL):]).name  # yo'l bilan chalg'itishga yo'l qo'yilmaydi
        data = (folder(course) / name).read_bytes()
    else:
        buf = await bot.download(file_id)
        data = buf.read()
    _lru_put(_BYTES, file_id, data, 12)
    return data


def page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return min(len(pdf), MAX_PAGES)
    finally:
        pdf.close()


def _render(data: bytes, index: int, width: int) -> bytes:
    pdf = pdfium.PdfDocument(data)
    try:
        page = pdf[index]
        scale = max(0.5, min(4.0, width / page.get_width()))
        img = page.render(scale=scale).to_pil()
        out = io.BytesIO()
        img.convert("RGB").save(out, format="PNG", optimize=True)
        return out.getvalue()
    finally:
        pdf.close()


async def page_png(key: str, data: bytes, index: int, width: int = 1240) -> bytes:
    """Sahifa rasmi (PNG). width — piksel (telefon ekrani uchun 1240 yetarli: kattalashtirganda ham aniq)."""
    width = max(480, min(int(width), 2000))
    ck = (key, index, width)
    if ck in _PNG:
        _PNG.move_to_end(ck)
        return _PNG[ck]
    png = await asyncio.to_thread(_render, data, index, width)
    _lru_put(_PNG, ck, png, 48)
    return png
