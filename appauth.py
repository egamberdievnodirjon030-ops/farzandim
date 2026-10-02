"""Telefon ilovasi (Android / iOS) va oddiy brauzer uchun kirish — tasdiq Telegram botda.

1. Ilova «Telegram orqali kirish» ni bosadi → server bir martalik kod (10 daqiqa) va 2 xonali raqam (PIN) beradi.
   Ilova PIN ni katta qilib ko'rsatadi va Telegram'da botni ochadi: t.me/<bot>?start=a_<kod>.
2. Botda: yangi foydalanuvchi avval telefon raqamini Telegram tugmasi bilan tasdiqlaydi (ro'yxatdan o'tish — botda),
   so'ng uchta raqamdan ilovada ko'ringanini tanlaydi. Bu — «raqam moslash»: kimdir boshqa odamga kirish havolasini
   yuborib, uning akkauntiga kirib olmoqchi bo'lsa, qurbon ilovadagi raqamni ko'rmaydi va tasdiqlay olmaydi.
   Noto'g'ri raqam — kirish bekor qilinadi.
3. Ilova serverdan tasdiqni so'raydi (polling) va bir marta seans kalitini oladi. Kalit qurilmada saqlanadi, serverda
   faqat uning SHA-256 xeshi turadi. Seans SESSION_DAYS kun ishlatilmasa tugaydi; botdagi /qurilmalar dan istalgan
   qurilmani chiqarib yuborish mumkin.

Bildirishnomalar avvalgidek Telegram chatga keladi.
"""
from __future__ import annotations

import hashlib
import random
import secrets
import time
from datetime import timedelta

from tenancy import central
from utils import now, now_iso

LOGIN_MINUTES = 10
SESSION_DAYS = 180
START_PREFIX = "a_"
_SEEN_EVERY = 300          # last_seen ni har so'rovda emas, 5 daqiqada bir yozamiz
_seen: dict[int, float] = {}
_starts: dict[str, list[float]] = {}   # IP → kirish so'rovlari vaqtlari (spamga qarshi)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def allow_start(ip: str, limit: int = 20, window: int = 3600) -> bool:
    t = time.time()
    lst = [x for x in _starts.get(ip, []) if t - x < window]
    if len(lst) >= limit:
        _starts[ip] = lst
        return False
    lst.append(t)
    _starts[ip] = lst
    return True


async def start(device: str | None) -> dict:
    code = secrets.token_urlsafe(18)
    pin = random.SystemRandom().randint(10, 99)
    exp = (now() + timedelta(minutes=LOGIN_MINUTES)).isoformat(timespec="seconds")
    await central._write("DELETE FROM app_logins WHERE expires_at < ?", (now_iso(),))
    await central._write("INSERT INTO app_logins (code, pin, device, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                         (code, pin, (device or "")[:80] or None, now_iso(), exp))
    return {"code": code, "pin": pin, "expires_in": LOGIN_MINUTES * 60}


async def get_login(code: str) -> dict | None:
    r = await central._one("SELECT * FROM app_logins WHERE code = ?", (code,))
    if not r or r["expires_at"] < now_iso():
        return None
    return r


def pin_choices(pin: int) -> list[int]:
    rnd = random.SystemRandom()
    opts = {pin}
    while len(opts) < 3:
        opts.add(rnd.randint(10, 99))
    out = list(opts)
    rnd.shuffle(out)
    return out


async def decide(code: str, tg_id: int, pin: int | None) -> str:
    """Botdagi qaror. pin=None — «bekor qilish». Qaytaradi: approved | wrong_pin | cancelled | expired."""
    r = await get_login(code)
    if not r or r["state"] != "pending":
        return "expired"
    if pin is None:
        await central._write("UPDATE app_logins SET state = 'cancelled', tg_id = ? WHERE code = ?", (tg_id, code))
        return "cancelled"
    if pin != r["pin"]:
        await central._write("UPDATE app_logins SET state = 'cancelled', tg_id = ? WHERE code = ?", (tg_id, code))
        return "wrong_pin"
    await central._write("UPDATE app_logins SET state = 'approved', tg_id = ?, approved_at = ? WHERE code = ?",
                         (tg_id, now_iso(), code))
    return "approved"


async def poll(code: str) -> dict:
    """Ilova so'raydi: pending | cancelled | expired | approved (+ seans kaliti — faqat bir marta)."""
    r = await get_login(code)
    if not r:
        return {"state": "expired"}
    if r["state"] != "approved":
        return {"state": r["state"]}
    await central._write("UPDATE app_logins SET state = 'used' WHERE code = ? AND state = 'approved'", (code,))
    token = secrets.token_urlsafe(32)
    await central._write("INSERT INTO app_sessions (token_hash, tg_id, device, created_at, last_seen) "
                         "VALUES (?, ?, ?, ?, ?)", (_hash(token), r["tg_id"], r["device"], now_iso(), now_iso()))
    return {"state": "approved", "token": token}


async def verify(token: str) -> tuple[int, int] | None:
    """Seans kaliti → (foydalanuvchi, seans id) yoki None."""
    if not token or len(token) > 100:
        return None
    r = await central._one("SELECT id, tg_id, last_seen FROM app_sessions WHERE token_hash = ? AND revoked_at IS NULL",
                           (_hash(token),))
    if not r:
        return None
    limit = (now() - timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    if (r["last_seen"] or "") < limit:
        return None
    if time.time() - _seen.get(r["id"], 0) > _SEEN_EVERY:
        _seen[r["id"]] = time.time()
        await central._write("UPDATE app_sessions SET last_seen = ? WHERE id = ?", (now_iso(), r["id"]))
    return r["tg_id"], r["id"]


async def sessions(tg_id: int) -> list[dict]:
    limit = (now() - timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    return await central._all("SELECT id, device, created_at, last_seen FROM app_sessions WHERE tg_id = ? AND "
                              "revoked_at IS NULL AND last_seen >= ? ORDER BY last_seen DESC", (tg_id, limit))


async def revoke(tg_id: int, sid: int | None = None) -> None:
    """Bitta seans (sid) yoki foydalanuvchining hamma seanslari."""
    if sid is None:
        await central._write("UPDATE app_sessions SET revoked_at = ? WHERE tg_id = ? AND revoked_at IS NULL",
                             (now_iso(), tg_id))
    else:
        await central._write("UPDATE app_sessions SET revoked_at = ? WHERE tg_id = ? AND id = ?", (now_iso(), tg_id, sid))
