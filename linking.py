"""Farzandni bog'lash — xavfsiz, lekin ota-ona uchun sodda.

1. Ota-ona telefon raqamini Telegram orqali tasdiqlaydi (raqamni Telegram o'zi beradi — soxtalashtirib bo'lmaydi).
2. Raqam universitet faylida talabaning ota-ona raqami sifatida bo'lsa — farzand avtomatik bog'lanadi.
3. Bo'lmasa — farzandning F.I.Sh. va tug'ilgan sanasi (yoki HEMIS ID). Noto'g'ri urinishlar cheklangan
   (MAX_FAILS kun ichida), javob talaba bor-yo'qligini oshkor qilmaydi.
4. Tasdiqlash — ikki bosqich:
   • talabaning o'zi (talaba raqami bazada bo'lsa): ota-ona unga bir martalik havolani yuboradi (muddati
     TOKEN_HOURS soat); talaba botda O'Z telefon raqamini tasdiqlaydi — raqam bazadagi shu talabaning raqami
     bo'lishi shart — va «Ha, bu mening ota-onam» ni bosadi. «Yo'q» desa — so'rov darhol rad etiladi va kurs
     koordinatoriga ogohlantirish boradi;
   • yakuniy tasdiq — har doim kurs koordinatori: u so'rovda talaba tasdiqlaganmi, qaysi Telegram akkaunt va
     raqam bilan tasdiqlaganini ko'radi va «Tasdiqlash» ni bosgandagina ota-ona ulanadi.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from database import db
from tenancy import central, use_course
from utils import esc, now, now_iso

log = logging.getLogger("linking")

MAX_FAILS = 5          # sutkada noto'g'ri urinishlar
TOKEN_HOURS = 72
START_PREFIX = "t_"    # t.me/<bot>?start=t_<token>


# ---------------------------------------------------------------- urinishlar cheklovi
async def can_try(uid: int) -> bool:
    since = (now() - timedelta(days=1)).isoformat(timespec="seconds")
    row = await central._one("SELECT COUNT(*) n FROM link_attempts WHERE tg_id = ? AND ok = 0 AND at >= ?", (uid, since))
    return (row["n"] if row else 0) < MAX_FAILS


async def record_try(uid: int, ok: bool) -> None:
    await central._write("INSERT INTO link_attempts (tg_id, ok, at) VALUES (?, ?, ?)", (uid, int(ok), now_iso()))


# ---------------------------------------------------------------- talaba tasdiqlashi uchun havola
async def issue_token(rid: int) -> str:
    """Joriy kurs bazasidagi so'rovga bir martalik havola (avvalgisi bo'lsa — yangilanadi)."""
    token = secrets.token_urlsafe(12).replace("-", "x").replace("_", "y")
    exp = (now() + timedelta(hours=TOKEN_HOURS)).isoformat(timespec="seconds")
    await db.execute("UPDATE link_requests SET token = ?, token_expires = ? WHERE id = ?", (token, exp, rid))
    return token


async def confirm_url(bot, token: str) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start={START_PREFIX}{token}"


async def student_can_confirm(sid: int) -> bool:
    """Talabaning o'z raqami bazada bormi (bo'lmasa — uni tasdiqlab bo'lmaydi, kurs koordinatori tasdiqlaydi)."""
    row = await db.fetchone("SELECT COUNT(*) n FROM student_self_phones WHERE student_id = ?", (sid,))
    return bool(row and row["n"])


async def by_token(token: str) -> tuple[str, dict] | None:
    """Havola bo'yicha kutilayotgan so'rov (barcha kurslardan). Muddati o'tgan yoki ko'rib chiqilgan — None."""
    for key in db.keys():
        d = db.for_course(key)
        r = await d.fetchone("SELECT * FROM link_requests WHERE token = ?", (token,))
        if r and r["status"] == "pending" and (r["token_expires"] or "") >= now_iso():
            return key, r
    return None


async def parent_requests(bot, uid: int) -> list[dict]:
    """Ota-onaning kutilayotgan so'rovlari (ilovadagi «tasdiqlash» bosqichi uchun)."""
    import loc
    out = []
    for key in db.keys():
        with use_course(key):
            for r in await db.fetchall("SELECT * FROM link_requests WHERE parent_id = ? AND status = 'pending' "
                                       "ORDER BY id DESC", (uid,)):
                st = await db.get_student(r["student_id"])
                if not st:
                    continue
                can = await student_can_confirm(st["id"])
                token = r["token"] if r["token"] and (r["token_expires"] or "") >= now_iso() else None
                ok = bool(r["student_ok_at"])  # talaba tasdiqlagan — koordinator kutilmoqda, havola kerak emas
                if can and not token and not ok:
                    token = await issue_token(r["id"])
                out.append({"id": r["id"], "course": key, "student": " ".join(loc.student_name(st).split()[:2]),
                            "group": st.get("group_name") or "", "created_at": r["created_at"],
                            "student_can_confirm": can, "student_ok": ok,
                            "confirm_url": await confirm_url(bot, token) if token and not ok else None})
    return out


def mask_phone(phone: str | None) -> str:
    p = "".join(ch for ch in (phone or "") if ch.isdigit())
    return f"+{p[:5]} *** ** {p[-2:]}" if len(p) >= 9 else "—"


async def student_decide(bot, key: str, rid: int, student_tg: int, approve: bool) -> tuple[bool, str]:
    """Talabaning qarori. Qaytaradi: (bajarildimi, talabaga ko'rsatiladigan javob)."""
    import appmode
    import live
    from i18n import tr, use_lang
    from notifier import safe_send
    from staffops import _coord_notice
    with use_course(None if key == "_" else key):
        r = await db.fetchone("SELECT * FROM link_requests WHERE id = ?", (rid,))
        if not r or r["status"] != "pending" or r["student_tg"] != student_tg or r["student_ok_at"]:
            return False, "expired"
        st = await db.get_student(r["student_id"])
        lang = await central.get_lang(r["parent_id"]) or "uz"
        if approve:  # ulanmaydi — talaba tasdig'i bilan so'rov koordinatorga yakuniy tasdiq uchun boradi
            await db.execute("UPDATE link_requests SET student_ok_at = ?, token = NULL WHERE id = ?", (now_iso(), rid))
            with use_lang(lang):
                await safe_send(bot, r["parent_id"], tr(
                    "✅ Farzandingiz ({name}) sizni tasdiqladi. Endi kurs koordinatori yakuniy tasdiqlaydi — "
                    "tasdiqlangach, sizga xabar keladi.", name=appmode.short_name(st)))
            live.publish(r["parent_id"], {"type": "link_progress", "route": "/"})
            from staffops import notify_student_confirmed
            await notify_student_confirmed(bot, {**r, "student_ok_at": now_iso()}, st)
            log.info("Bog'lash so'rovi #%s talaba tomonidan tasdiqlandi (%s), koordinator kutilmoqda", rid, student_tg)
            return True, "approved"
        await db.execute("UPDATE link_requests SET status = 'rejected', decided_by = ?, decided_at = ?, "
                         "decided_via = 'student', token = NULL WHERE id = ?", (student_tg, now_iso(), rid))
        with use_lang(lang):
            await safe_send(bot, r["parent_id"], tr("❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Kurs koordinatori "
                                                     "bilan bevosita bog'laning."))
        live.publish(r["parent_id"], {"type": "link", "approved": False, "route": "/"})
        parent = await db.get_parent(r["parent_id"])
        await _coord_notice(bot, st, f"⚠️ <b>Diqqat:</b> talaba <b>{esc(st['full_name'])}</b> bog'lash so'rovini RAD ETDI — "
                                     f"so'rovchi uning ota-onasi emasligini bildirdi (so'rov #{rid}, "
                                     f"{esc((parent or {}).get('tg_name') or '')} {esc((parent or {}).get('phone') or '')}).")
        log.warning("Bog'lash so'rovi #%s talaba tomonidan rad etildi (%s)", rid, student_tg)
        return True, "rejected"
