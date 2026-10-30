"""Ikki bot: ota-onalar boti (asosiy — kurs koordinatorlari va super-admin ham shu botda ishlaydi) va talabalar boti
(tashrif so'rovlari, tadbir va madaniy tashrif e'lonlari va eslatmalari, ota-onani tasdiqlash).

Talabaga xabar — student_bot(), ota-ona va koordinatorga — main_bot(). STUDENT_BOT_TOKEN bo'sh bo'lsa, hammasi bitta
botda ishlaydi (oldingidek): ikkala funksiya ham asosiy botni qaytaradi.
"""
from __future__ import annotations

_main = None
_student = None


def set_bots(main, student=None) -> None:
    global _main, _student
    _main, _student = main, student


def main_bot(fallback=None):
    """Ota-onalar va xodimlar boti."""
    return _main or fallback


def student_bot(fallback=None):
    """Talabalar boti (alohida bot sozlanmagan bo'lsa — asosiy bot)."""
    return _student or _main or fallback


def separate() -> bool:
    """Talabalar uchun alohida bot ishlayaptimi."""
    return _student is not None
