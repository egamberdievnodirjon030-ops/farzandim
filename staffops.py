"""Kurs koordinatori va super-admin amallari — bot va kompyuter versiyasi (Web) uchun umumiy.

Bir xil amal (so'rovni tasdiqlash, kurs koordinatorini tayinlash yoki olib tashlash) botdan ham, kompyuter
versiyasidan ham bajarilganda natija va ota-onaga / koordinatorga boradigan xabar bir xil bo'lishi uchun.
"""
from __future__ import annotations

import html
import logging
import re

import appmode
import live
from botcommands import apply_commands
from database import db
from i18n import tr, use_lang
from keyboards import coordinator_menu
from notifier import safe_send
from tenancy import central, course_title, is_super, reload_registry, use_course
from utils import fmt_phone, group_key

log = logging.getLogger("staff")


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


# ---------------------------------------------------------------- ota-onaning farzandni bog'lash so'rovi
async def decide_link(bot, rid: int, approve: bool, admin_id: int) -> tuple[bool, str]:
    """So'rovni tasdiqlaydi yoki rad etadi va ota-onaga (uning tilida) xabar yuboradi.
    Qaytaradi: (bajarildimi, kurs koordinatoriga ko'rsatiladigan qisqa natija)."""
    from tenancy import in_scope, viewer_scope
    req = await db.get_link_request(rid)
    if not req or req["status"] != "pending":
        return False, "Bu so'rov allaqachon ko'rib chiqilgan."
    st0 = await db.get_student(req["student_id"])
    if st0 and not in_scope(st0.get("group_name"), viewer_scope()):
        return False, "Bu talaba sizga biriktirilgan guruhlarda emas."
    if approve and await db.is_blocked(req["parent_id"]):
        return False, "Bu foydalanuvchi talaba deb bloklangan. Avval /bloklar orqali ruxsat bering."
    st = await db.get_student(req["student_id"])
    lang = await central.get_lang(req["parent_id"]) or "uz"
    if approve:
        await db.link_parent(req["parent_id"], req["student_id"], "student" if req.get("student_ok_at") else "manual")
        await db.decide_link_request(rid, "approved", admin_id)
        await db.execute("UPDATE link_requests SET decided_via = ?, token = NULL WHERE id = ?",
                         ("student+coordinator" if req.get("student_ok_at") else "coordinator", rid))
        if req.get("student_ok_at") and req.get("claimed_phone") and req.get("student_phone") == req["claimed_phone"]:
            await db.add_self_phone(req["student_id"], req["claimed_phone"])  # endi tasdiqlangan talaba raqami
        with use_lang(lang):
            if appmode.APP_MODE:
                text, kb = appmode.short_text("link_ok", st), appmode.app_kb("/")
            else:
                text = tr("✅ Kurs koordinatori so'rovingizni tasdiqladi. Endi <b>{name}</b> ma'lumotlarini "
                          "ko'rishingiz mumkin: «👨‍🎓 Farzandim» bo'limini oching.",
                          name=esc(st["full_name"]) if st else "—")
                kb = None
        await safe_send(bot, req["parent_id"], text, reply_markup=kb)
        live.publish(req["parent_id"], {"type": "link", "approved": True, "route": "/"})
        log.info("Bog'lash so'rovi tasdiqlandi: #%s (ota-ona %s → talaba %s)", rid, req["parent_id"], req["student_id"])
        return True, "✅ Tasdiqlandi"
    await db.decide_link_request(rid, "rejected", admin_id)
    await db.execute("UPDATE link_requests SET decided_via = 'coordinator', token = NULL WHERE id = ?", (rid,))
    with use_lang(lang):
        if appmode.APP_MODE:
            text, kb = appmode.short_text("link_no"), appmode.app_kb("/")
        else:
            text = tr("❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Iltimos, kurs koordinatori bilan bevosita "
                      "bog'laning.")
            kb = None
    await safe_send(bot, req["parent_id"], text, reply_markup=kb)
    live.publish(req["parent_id"], {"type": "link", "approved": False, "route": "/"})
    log.info("Bog'lash so'rovi rad etildi: #%s", rid)
    return True, "❌ Rad etildi"


# ---------------------------------------------------------------- kurs koordinatorlari (super-admin)
async def assign_coordinator(bot, uid: int, key: str, name: str | None, by: int | None) -> dict:
    """Kurs koordinatorini tayinlaydi (boshqa kursda bo'lsa — ko'chiradi), menyusini yangilaydi va xabar beradi."""
    old = next((c["course_key"] for c in (await central.registry())[1] if c["user_id"] == uid), None)
    await central.set_coordinator(uid, key, name, by)
    await reload_registry()
    menu_ok = await apply_commands(bot, uid)
    notified = True
    try:
        await bot.send_message(
            uid, f"✅ Siz «{esc(course_title(key))}» kurs koordinatori etib tayinlandingiz.\n"
                 "Kurs koordinatori menyusini ochish uchun: /start", reply_markup=coordinator_menu(course_title(key)))
    except Exception:
        notified = False
    log.info("Kurs koordinatori qo'shildi: %s → %s (%s)", uid, key, name or "-")
    return {"old": old if old and old != key else None, "notified": notified, "menu_ok": menu_ok}


async def unassign_coordinator(bot, uid: int, key: str) -> None:
    """Kurs koordinatorini olib tashlaydi (kurs ma'lumotlari o'chmaydi) va unga xabar beradi."""
    await central.remove_coordinator(uid)
    await reload_registry()
    await apply_commands(bot, uid)
    try:
        from aiogram.types import ReplyKeyboardRemove
        await bot.send_message(uid, f"Siz «{esc(course_title(key))}» kurs koordinatorlari ro'yxatidan chiqarildingiz.",
                               reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass
    log.info("Kurs koordinatori olib tashlandi: %s (%s)", uid, key)


# ---------------------------------------------------------------- koordinatorlarga guruh biriktirish (super-admin)
def _coord_label(coords: list[dict], uid: int) -> str:
    return next((c["name"] for c in coords if c["user_id"] == uid and c.get("name")), None) or f"ID {uid}"


async def course_groups(key: str) -> dict:
    """Kursdagi guruhlar (talabalar bazasidagi va hali yuklanmagan, lekin biriktirilgan) va ularning egasi.
    Qaytaradi: {"groups": [{key, name, students, owner, owner_label}], "coordinators": [{user_id, label, groups}]}"""
    _, coords = await central.registry()
    coords = [c for c in coords if c["course_key"] == key]
    groups = await db.for_course(key).group_counts() if key in db.keys() else {}
    assigned = await central.course_coord_groups(key)
    active = {c["user_id"] for c in coords}
    owner: dict[str, int] = {}
    for g in assigned:
        if g["user_id"] in active:
            owner[g["group_key"]] = g["user_id"]
            groups.setdefault(g["group_key"], {"name": g["group_name"], "students": 0})
    items = [{"key": k, "name": v["name"], "students": v["students"], "owner": owner.get(k),
              "owner_label": _coord_label(coords, owner[k]) if k in owner else None}
             for k, v in sorted(groups.items(), key=lambda kv: kv[1]["name"].lower())]
    return {"groups": items, "coordinators": [
        {"user_id": c["user_id"], "label": _coord_label(coords, c["user_id"]), "is_super": is_super(c["user_id"]),
         "groups": [g["name"] for g in items if g["owner"] == c["user_id"]]} for c in coords]}


def split_group_names(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;\n]+", text or "") if x.strip()]


async def save_coord_groups(uid: int, key: str, names: list[str], by: int | None) -> dict:
    """Koordinatorning guruhlarini almashtiradi. Boshqa koordinatorga biriktirilgan guruh olinmaydi (bitta guruh —
    bitta koordinator: ma'lumotlar chalkashmasin). Qaytaradi: {"saved": [nomlar], "taken": [(nom, egasi)]}"""
    info = await course_groups(key)
    known = {g["key"]: g for g in info["groups"]}
    chosen: dict[str, str] = {}
    taken: list[tuple[str, str]] = []
    for name in names:
        k = group_key(name)
        if not k or k in chosen:
            continue
        g = known.get(k)
        if g and g["owner"] not in (None, uid):
            taken.append((g["name"], g["owner_label"]))
            continue
        chosen[k] = g["name"] if g else name.strip()
    await central.set_coord_groups(uid, key, chosen, by)
    await reload_registry()
    log.info("Koordinator guruhlari: %s (%s) → %s", uid, key, ", ".join(chosen.values()) or "-")
    return {"saved": sorted(chosen.values(), key=str.lower), "taken": taken}


# ---------------------------------------------------------------- so'rovnoma va ichki nizom — ota-onalarga xabar
async def _broadcast(bot, pids, kind: str, title: str, route: str) -> int:
    """Qisqa xabar (ota-ona tilida) + «Ilovada ochish» tugmasi, bildirishnomalar markazi va jonli voqea (ilova ochiq
    bo'lsa — darhol, yangilashsiz)."""
    import loc
    from keyboards import webapp_kb
    from notifier import safe_send
    sent = 0
    for pid in pids:
        lang = await central.get_lang(pid) or "uz"
        with use_lang(lang):
            text = tr(appmode.SHORT[kind], title=esc(loc.pick(title, lang)))
            ok = await safe_send(bot, pid, text, reply_markup=webapp_kb(route, tr("📱 Ilovada ochish")))
        sent += ok
        await db.add_notification(pid, text, None, kind)
        live.publish(pid, {"type": "notification", "kind": kind, "text": text, "route": route})
    return sent


async def notify_survey(bot, course: str, s: dict) -> tuple[int, int]:
    """Yangi so'rovnoma — uning guruhlaridagi (yoki butun kursdagi) ota-onalarga."""
    import surveys
    pids = await surveys.recipients(s)
    sent = await _broadcast(bot, pids, "survey", s["title"], f"/survey/{course}/{s['id']}")
    log.info("So'rovnoma #%s yuborildi: %s/%s ota-onaga", s["id"], sent, len(pids))
    return sent, len(pids)


async def notify_regulation(bot, title: str) -> tuple[int, int]:
    """Yangi ichki nizom — barcha kurslarning ota-onalariga (har biriga bir marta)."""
    seen: set[int] = set()
    sent = total = 0
    for key in db.keys():
        d = db.for_course(key)
        pids = [r["tg_id"] for r in await d.fetchall("SELECT tg_id FROM parents WHERE active = 1") if r["tg_id"] not in seen]
        seen.update(pids)
        with use_course(None if key == "_" else key):
            sent += await _broadcast(bot, pids, "reg", title, "/regulations")
        total += len(pids)
    return sent, total


async def _coord_notice(bot, st: dict, text: str) -> None:
    """Talaba guruhi koordinator(lar)iga qisqa xabar (bog'lash bo'yicha talabaning qarori)."""
    from tenancy import course_admins
    for admin_id in course_admins(groups=[st.get("group_name")]):
        await safe_send(bot, admin_id, text)


# ---------------------------------------------------------------- yangi bog'lash so'rovi — kurs koordinatorlariga
async def notify_link_request(bot, rid: int, parent_name: str, st: dict, detailed: str) -> None:
    """Ilova rejimida — qisqa xabar va «Ilovada ko'rib chiqish»; aks holda — batafsil matn va botdagi tugmalar."""
    from keyboards import link_request_kb
    from tenancy import course_admins, current_course
    course = current_course() or "_"
    if appmode.APP_MODE:
        text = (f"🔗 <b>Farzandni bog'lash so'rovi</b> — {esc(parent_name)} → {esc(st['full_name'])} "
                f"({esc(st.get('group_name') or '')})")
        kb = appmode.app_kb("/staff/requests", "📱 Ilovada ko'rib chiqish")
    else:
        text, kb = detailed, link_request_kb(rid)
    import linking
    if await linking.student_can_confirm(st["id"]):
        text += ("\n\n⏳ Talabaning o'z raqami bazada bor — ota-onaga talabaga yuborish uchun havola berildi. Talaba "
                 "tasdiqlasa, sizga alohida xabar keladi (kim tasdiqlagani bilan); yakuniy tasdiq — sizda.")
    admins = course_admins(groups=[st.get("group_name")])  # talaba guruhi biriktirilgan koordinator(lar)
    for admin_id in admins:
        await safe_send(bot, admin_id, text, reply_markup=kb)
    live.publish_many(admins, {"type": "request", "course": course, "route": "/staff/requests",
                                        "text": f"{parent_name} → {st['full_name']}"})


async def notify_student_confirmed(bot, r: dict, st: dict) -> None:
    """Talaba ota-onasini tasdiqladi — so'rov koordinatorga yakuniy tasdiq uchun (kim tasdiqlagani bilan) boradi."""
    from keyboards import link_request_kb
    from tenancy import course_admins, current_course
    parent = await db.get_parent(r["parent_id"]) or {}
    text = (f"🔗✅ <b>Bog'lash so'rovi #{r['id']} — talaba tasdiqladi</b>\n\n"
            f"👤 Ota-ona: {esc(parent.get('tg_name') or '')}, {fmt_phone(parent.get('phone') or '')}\n"
            f"👨‍🎓 Talaba: {esc(st['full_name'])} · {esc(st.get('group_name') or '')} · ID {esc(st.get('hemis_id') or '')}\n\n"
            f"Tasdiqlagan: Telegram akkaunt «{esc(r.get('student_tg_name') or '—')}», raqami "
            f"{fmt_phone(r.get('student_phone') or '') or '—'} — "
            + ("bazadagi shu talabaning raqami bilan mos.\n\n" if not r.get("claimed_phone") or r.get("src") == "db" else
               "⚠️ <b>bu raqam bazada yo'q — uni ota-ona kiritgan.</b> Raqam haqiqatan talabaniki ekanini "
               "tekshiring (masalan, talabaning o'zidan yoki guruh sardoridan so'rang).\n\n")
            + 
            f"<b>Yakuniy tasdiq sizda:</b> «Tasdiqlash» ni bosgandagina ota-ona ulanadi.")
    kb = appmode.app_kb("/staff/requests", "📱 Ilovada ko'rib chiqish") if appmode.APP_MODE else link_request_kb(r["id"])
    admins = course_admins(groups=[st.get("group_name")])
    for admin_id in admins:
        await safe_send(bot, admin_id, text, reply_markup=kb)
    live.publish_many(admins, {"type": "request", "course": current_course() or "_", "route": "/staff/requests",
                               "text": f"✅ Talaba tasdiqladi: {st['full_name']}"})


# ---------------------------------------------------------------- rasmiy hujjatni ota-onalarga yetkazish
async def _send_text(bot, chat_id: int, text: str, kb):
    """Matnli xabar; yuborilgan xabarni (message_id kerak) yoki None qaytaradi."""
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
    try:
        return await bot.send_message(chat_id, text, reply_markup=kb)
    except TelegramForbiddenError:
        await db.set_parent_active(chat_id, False)
    except TelegramBadRequest as e:
        log.warning("Xabar yuborilmadi %s: %s", chat_id, e)
    return None


async def deliver_document(bot, did: int, st: dict) -> tuple[int, int]:
    """Hujjatni farzandning ota-onalariga yetkazadi. Ilova rejimida — hujjat nomi yozilgan qisqa xabar va hujjatni
    ilovada ochadigan tugma; aks holda — faylning o'zi. Qaytaradi: (yetkazildi, jami ota-onalar)."""
    import docstore
    from aiogram.types import BufferedInputFile
    from notifier import safe_send_document
    from reports import document_caption
    from tenancy import current_course
    from utils import DOC_TYPES
    doc = await db.get_document(did)
    course = current_course() or "_"
    route = f"/go/doc/{course}/{st['id']}"
    parents = await db.parents_of_student(st["id"])
    sent = 0
    for pid in parents:
        lang = await central.get_lang(pid) or "uz"
        with use_lang(lang):
            caption = document_caption(doc, st)
            if appmode.APP_MODE:
                title = tr(DOC_TYPES.get(doc["doc_type"], DOC_TYPES["boshqa"])[1])
                m = await _send_text(bot, pid, appmode.short_text("doc", st, title=title), appmode.app_kb(route))
            else:
                f = doc["file_id"]
                if docstore.is_local(f):
                    f = BufferedInputFile(await docstore.load(bot, course, f), filename=doc.get("file_name") or "hujjat.pdf")
                m = await safe_send_document(bot, pid, f, caption)
        if m:
            sent += 1
            await db.record_delivery(did, pid, m.message_id)
            await db.add_notification(pid, caption, st["id"], "doc")
            live.publish(pid, {"type": "notification", "kind": "doc", "course": course, "student_id": st["id"],
                               "text": caption[:300], "route": route})
    return sent, len(parents)
