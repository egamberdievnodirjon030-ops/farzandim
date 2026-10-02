"""Kompyuter versiyasi (boshqaruv paneli) uchun kirish.

Kurs koordinatori yoki super-admin botda «💻 Kompyuter versiyasi» tugmasini (yoki /kompyuter) bosadi — bot
10 daqiqa amal qiladigan BIR MARTALIK havola yuboradi. Havola brauzerda ochilganda «Kirish» tugmasi chiqadi
(havolani oldindan tekshiruvchi dasturlar uni ishlatib qo'ymasligi uchun seans faqat tugma bosilganda yaratiladi),
so'ng 12 soat amal qiladigan imzolangan seans cookie o'rnatiladi.

Cookie serverda saqlanmaydi — BOT_TOKEN dan olingan kalit bilan imzolanadi, shuning uchun bot qayta ishga
tushganda seans uzilmaydi. Huquq har bir so'rovda qayta tekshiriladi: kurs koordinatori lavozimidan olinsa,
uning seansi darhol kuchini yo'qotadi.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from config import BOT_TOKEN, WEBAPP_URL

COOKIE = "jidu_desk"
TOKEN_TTL = 10 * 60          # bir martalik havola: 10 daqiqa
SESSION_TTL = 12 * 3600      # seans: 12 soat
_KEY = hashlib.sha256(b"jidu-desk-session:" + BOT_TOKEN.encode()).digest()
_tokens: dict[str, tuple[int, float]] = {}


def _purge() -> None:
    now = time.time()
    for t in [t for t, (_, exp) in _tokens.items() if exp < now]:
        _tokens.pop(t, None)


def issue(uid: int) -> str:
    """Yangi bir martalik kirish kaliti (foydalanuvchining oldingi ishlatilmagan kalitlari bekor qilinadi)."""
    _purge()
    for t in [t for t, (u, _) in _tokens.items() if u == uid]:
        _tokens.pop(t, None)
    token = secrets.token_urlsafe(24)
    _tokens[token] = (uid, time.time() + TOKEN_TTL)
    return token


def login_url(uid: int) -> str:
    return f"{WEBAPP_URL}/desk/login?t={issue(uid)}"


def peek(token: str) -> int | None:
    """Kalit hali amal qiladimi (ishlatmasdan) — «Kirish» sahifasini ko'rsatish uchun."""
    v = _tokens.get(token or "")
    return v[0] if v and v[1] >= time.time() else None


def consume(token: str) -> int | None:
    """Kalitni ishlatadi: bir marta, muddati o'tmagan bo'lsa — foydalanuvchi ID, aks holda None."""
    v = _tokens.pop(token or "", None)
    if not v or v[1] < time.time():
        return None
    return v[0]


def _sign(payload: str) -> str:
    return hmac.new(_KEY, payload.encode(), hashlib.sha256).hexdigest()


def make_cookie(uid: int, now: float | None = None) -> str:
    exp = int((now or time.time()) + SESSION_TTL)
    payload = f"{uid}.{exp}"
    return f"{payload}.{_sign(payload)}"


def verify_cookie(value: str | None) -> int | None:
    try:
        uid_s, exp_s, sig = (value or "").split(".")
        if not hmac.compare_digest(sig, _sign(f"{uid_s}.{exp_s}")):
            return None
        if int(exp_s) < time.time():
            return None
        return int(uid_s)
    except (ValueError, TypeError):
        return None


def cookie_secure() -> bool:
    return WEBAPP_URL.startswith("https://")
