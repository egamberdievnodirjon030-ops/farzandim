"""Shaxsiy ma'lumotlarni himoya qilish.

Yo'lovchi va haydovchi bir-biriga telefon raqami yoki Telegram profilini yozib yubora olmaydi:
izoh va anonim chat xabarlaridagi raqamlar, @username va t.me havolalari yashiriladi.
Bu ham maxfiylik talabi, ham kompaniyani chetlab o'tib "to'g'ridan-to'g'ri" kelishishning oldini oladi.
"""

from __future__ import annotations

import re

MASK = "•••"
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s\-().]{5,}\d")
_HANDLE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/\S+|@[A-Za-z][A-Za-z0-9_]{3,}", re.IGNORECASE)
MIN_PHONE_DIGITS = 7


def mask_contacts(text: str) -> tuple[str, bool]:
    """(yashirilgan matn, nimadir yashirildimi)."""
    changed = False

    def phone(m: re.Match[str]) -> str:
        nonlocal changed
        if sum(ch.isdigit() for ch in m.group(0)) >= MIN_PHONE_DIGITS:
            changed = True
            return MASK
        return m.group(0)

    def handle(_m: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return MASK

    text = _PHONE_CANDIDATE.sub(phone, text)
    text = _HANDLE.sub(handle, text)
    return text, changed
