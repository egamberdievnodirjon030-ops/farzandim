"""Ko'p tillilik: o'zbek (asosiy), rus va ingliz. Ota-ona interfeysi uchun.

Matnlar kodda o'zbekcha yoziladi va tr() orqali joriy tilga o'giriladi; kalit — o'zbekcha matnning o'zi.
Joriy til har bir so'rov boshida LangMiddleware tomonidan o'rnatiladi (contextvar), ota-onalarga ommaviy
xabar yuborishda esa har bir qabul qiluvchi uchun use_lang() bilan. Tarjimasi yo'q matn o'zbekcha chiqadi.
Kurs koordinatori interfeysi o'zbek tilida.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager

from i18n_data import TR

LANGS = ("uz", "ru", "en")
LANG_BUTTONS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}
_current: contextvars.ContextVar[str] = contextvars.ContextVar("lang", default="uz")


def get_lang() -> str:
    return _current.get()


def set_lang(lang: str | None) -> None:
    _current.set(lang if lang in LANGS else "uz")


@contextmanager
def use_lang(lang: str | None):
    token = _current.set(lang if lang in LANGS else "uz")
    try:
        yield
    finally:
        _current.reset(token)


def tr(text: str, **kw) -> str:
    """O'zbekcha matnni joriy tilga o'giradi; {nomli} o'rinlarni to'ldiradi."""
    lang = _current.get()
    s = text if lang == "uz" else (TR.get(text) or {}).get(lang) or text
    return s.format(**kw) if kw else s


def N_(text: str) -> str:
    """Belgi: bu matn tarjima qilinadi (modul darajasidagi o'zgarmaslar uchun); tr() ishlatilgan joyda o'giriladi."""
    return text


def variants(text: str) -> set[str]:
    """Matnning barcha tillardagi ko'rinishlari (menyu tugmalarini tanish uchun)."""
    return {text} | {v for v in (TR.get(text) or {}).values() if v}
