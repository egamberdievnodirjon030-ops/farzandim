"""Super-admin: kurslar va kurs koordinatorlarini bot ichidan boshqarish (serverga kirish va qayta ishga tushirish
shart emas), barcha kurslar holati, zaxira nusxa va xatolar jurnali.

Kurs koordinatorini qo'shish — Telegram'ning o'zidan foydalanuvchini tanlash tugmasi (yoki ID raqami) orqali;
olib tashlash — tasdiq bilan, kurs ma'lumotlari o'chmaydi. «🔀 Kursga kirish» — super-admin tanlangan kursda
kurs koordinatori vositalari bilan ishlaydi.
"""
from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import asyncio
import shutil
import tempfile
from pathlib import Path

import backup
import templates
import export
from config import ADMIN_COURSE, DATA_DIR, LOG_DIR
from database import db
from keyboards import (BTN_S_BACKUP, BTN_S_COURSES, BTN_S_ENTER, BTN_S_ERRORS, BTN_S_MENU, BTN_S_NEW, BTN_S_OVERVIEW,
                       BTN_S_TEMPLATES, SupCb, TplCb, TplMapCb, coord_groups_kb, coordinator_menu, course_card_kb, courses_kb,
                       map_field_kb, pick_user_kb, super_menu, template_card_kb, template_save_kb, templates_kb)
from logsetup import errors_since, tail
from tenancy import central, course_title, is_super, reload_registry, use_course
from utils import fmt_dt, fmt_money, normalize_text

log = logging.getLogger(__name__)
router = Router(name="superadmin")
router.message.filter(lambda m: m.from_user is not None and is_super(m.from_user.id))
router.callback_query.filter(lambda c: is_super(c.from_user.id))


class Sup(StatesGroup):
    new_course = State()
    rename = State()
    pick_user = State()
    name = State()
    groups = State()    # koordinator guruhlari nomlari kutilmoqda


class Tpl(StatesGroup):
    title = State()     # yangi shablon nomi
    file = State()      # shablon fayli kutilmoqda
    map = State()       # tanilmagan ustunlar so'ralmoqda
    confirm = State()   # saqlashni tasdiqlash
    edit = State()      # nomi va izohi


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


# ---------------------------------------------------------------- ma'lumotlar
async def courses_info() -> list[dict]:
    courses, coords = await central.registry()
    out = []
    for c in courses:
        groups = await central.course_coord_groups(c["key"])
        admins = [{"user_id": x["user_id"], "label": f"{x['name'] or 'ID ' + str(x['user_id'])}",
                   "groups": [g["group_name"] for g in groups if g["user_id"] == x["user_id"]]}
                  for x in coords if x["course_key"] == c["key"]]
        s = {"students": 0, "parents_active": 0}
        if c["key"] in db.keys():
            s = await db.for_course(c["key"]).stats()
        out.append({**c, "admins": admins, "students": s["students"], "parents": s["parents_active"]})
    return out


async def home_text() -> str:
    info = await courses_info()
    last = await central.get_meta("last_backup")
    errs = errors_since(24)
    return "\n".join([
        "🛡 <b>Super-admin</b>", "",
        f"🏫 Kurslar: <b>{len(info)}</b> · 👤 kurs koordinatorlari: <b>{sum(len(c['admins']) for c in info)}</b>",
        f"👨‍🎓 Talabalar: {sum(c['students'] for c in info)} · 👨‍👩‍👧 ota-onalar: {sum(c['parents'] for c in info)}",
        f"💾 Oxirgi zaxira nusxa: {fmt_dt(last) if last else 'hali olinmagan'}",
        f"🧾 So'nggi 24 soatdagi tizim xatolari: {errs}" + (" — /xatolar" if errs else " ✅"),
        "", "Menyudan tanlang 👇",
    ])


async def course_card(key: str) -> tuple[str, object]:
    c = next((x for x in await courses_info() if x["key"] == key), None)
    if not c:
        return "Kurs topilmadi.", None
    lines = [f"🏫 <b>{esc(c['title'])}</b>", f"Ma'lumotlar: <code>data/{esc(key)}/</code>",
             f"👨‍🎓 Talabalar: {c['students']} · 👨‍👩‍👧 ota-onalar: {c['parents']}", "",
             "👤 <b>Kurs koordinatorlari:</b>"]
    from staffops import course_groups
    owned = {x["user_id"]: x["groups"] for x in (await course_groups(key))["coordinators"]}
    lines += [f"   • {esc(a['label'])} (ID <code>{a['user_id']}</code>)\n      👥 "
              + (esc(", ".join(owned.get(a["user_id"]) or [])) or "guruhlar biriktirilmagan — butun kurs")
              for a in c["admins"]] or ["   hali yo'q — xabarlar super-adminga boradi"]
    if len(c["admins"]) > 1:
        lines.append("\nℹ️ Kursda bir nechta koordinator bo'lsa, har biriga guruhlarini biriktiring: fayl yuklaganda "
                     "(buxgalteriya hisoboti ham) faqat o'z guruhlari talabalari tanilinadi.")
    return "\n".join(lines), course_card_kb(key, c["admins"])


# ---------------------------------------------------------------- menyu
@router.message(F.text == BTN_S_MENU)
@router.message(Command("super"))
async def s_home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await central.set_active(message.from_user.id, "")  # kursdan chiqish — super-admin menyusi
    await message.answer(await home_text(), reply_markup=super_menu())


@router.message(F.text == BTN_S_COURSES)
@router.message(Command("kurslar"))
async def s_courses(message: Message, state: FSMContext) -> None:
    await state.clear()
    info = await courses_info()
    if not info:
        await message.answer("Hali kurs yo'q. «➕ Yangi kurs» tugmasi bilan yarating.")
        return
    lines = ["🏫 <b>Kurslar va koordinatorlar</b>", ""]
    for c in info:
        who = ", ".join(a["label"] for a in c["admins"]) or "koordinator yo'q"
        lines.append(f"• <b>{esc(c['title'])}</b> — {esc(who)} · talabalar {c['students']}, ota-onalar {c['parents']}")
    lines.append("\nKursni tanlang — koordinator qo'shish, olib tashlash, nomini o'zgartirish:")
    await message.answer("\n".join(lines), reply_markup=courses_kb(info))


@router.callback_query(SupCb.filter(F.a == "list"))
async def cb_list(cb: CallbackQuery) -> None:
    await cb.answer()
    info = await courses_info()
    await cb.message.edit_text("🏫 <b>Kurslar va koordinatorlar</b> — kursni tanlang:", reply_markup=courses_kb(info))


@router.callback_query(SupCb.filter(F.a == "course"))
async def cb_course(cb: CallbackQuery, callback_data: SupCb) -> None:
    await cb.answer()
    text, kb = await course_card(callback_data.k)
    await cb.message.edit_text(text, reply_markup=kb)


# ---------------------------------------------------------------- yangi kurs, nomini o'zgartirish
@router.message(F.text == BTN_S_NEW)
@router.message(Command("yangi_kurs"))
async def s_new_course(message: Message, state: FSMContext) -> None:
    await state.set_state(Sup.new_course)
    await message.answer("➕ Yangi kurs nomini yozing (masalan: <code>2-kurs</code> yoki <code>3-kurs, Xalqaro "
                         "munosabatlar</code>). Kurs uchun alohida papka va baza yaratiladi.\n\nBekor qilish: /bekor")


@router.message(Sup.new_course, F.text, ~F.text.startswith("/"))
async def on_new_course(message: Message, state: FSMContext) -> None:
    await state.clear()
    title = message.text.strip()[:60]
    key = await central.add_course(title, message.from_user.id)
    await db.open_course(DATA_DIR, key)
    await reload_registry()
    log.info("Yangi kurs yaratildi: %s (%s)", title, key)
    text, kb = await course_card(key)
    await message.answer(f"✅ Kurs yaratildi — endi unga kurs koordinatorini qo'shing.\n\n{text}", reply_markup=kb)


@router.callback_query(SupCb.filter(F.a == "rename"))
async def cb_rename(cb: CallbackQuery, callback_data: SupCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Sup.rename)
    await state.update_data(k=callback_data.k)
    await cb.message.answer(f"«{esc(course_title(callback_data.k))}» kursining yangi nomini yozing (papka nomi "
                            "o'zgarmaydi, ma'lumotlar joyida qoladi).\n\nBekor qilish: /bekor")


@router.message(Sup.rename, F.text, ~F.text.startswith("/"))
async def on_rename(message: Message, state: FSMContext) -> None:
    key = (await state.get_data())["k"]
    await state.clear()
    await central.rename_course_title(key, message.text.strip()[:60])
    await reload_registry()
    text, kb = await course_card(key)
    await message.answer("✅ Kurs nomi o'zgartirildi.\n\n" + text, reply_markup=kb)


# ---------------------------------------------------------------- kurs koordinatorini qo'shish
@router.callback_query(SupCb.filter(F.a == "addc"))
async def cb_add(cb: CallbackQuery, callback_data: SupCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Sup.pick_user)
    await state.update_data(k=callback_data.k)
    await cb.message.answer(
        f"👤 «{esc(course_title(callback_data.k))}» kursiga yangi kurs koordinatori.\n\n"
        "Pastdagi <b>«👤 Foydalanuvchini tanlash»</b> tugmasini bosing va Telegram kontaktlaringizdan tanlang — "
        "yoki uning Telegram ID raqamini yozing (uni @userinfobot orqali bilish mumkin).",
        reply_markup=pick_user_kb())


@router.message(Sup.pick_user, F.users_shared)
async def on_user_shared(message: Message, state: FSMContext) -> None:
    u = message.users_shared.users[0]
    name = " ".join(x for x in (u.first_name, u.last_name) if x) or (f"@{u.username}" if u.username else None)
    await _ask_name_or_save(message, state, u.user_id, name)


@router.message(Sup.pick_user, F.text)
async def on_user_id(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text.startswith("✖️") or text == "/bekor":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=super_menu())
        return
    if not text.isdigit() or len(text) < 5:
        await message.answer("Telegram ID — faqat raqamlar (masalan <code>8634767200</code>). Yoki «👤 Foydalanuvchini "
                             "tanlash» tugmasini bosing.", reply_markup=pick_user_kb())
        return
    await _ask_name_or_save(message, state, int(text), None)


async def _ask_name_or_save(message: Message, state: FSMContext, uid: int, name: str | None) -> None:
    await state.update_data(uid=uid)
    if name:
        await _save_coordinator(message, state, name)
        return
    await state.set_state(Sup.name)
    await message.answer("Kurs koordinatorining ismini yozing (ro'yxatda ko'rinadi), masalan <code>N. Egamberdiyev</code>. "
                         "O'tkazib yuborish: <code>-</code>")


@router.message(Sup.name, F.text, ~F.text.startswith("/"))
async def on_name(message: Message, state: FSMContext) -> None:
    await _save_coordinator(message, state, None if message.text.strip() == "-" else message.text.strip()[:60])


async def _save_coordinator(message: Message, state: FSMContext, name: str | None) -> None:
    from staffops import assign_coordinator
    data = await state.get_data()
    await state.clear()
    key, uid = data["k"], data["uid"]
    r = await assign_coordinator(message.bot, uid, key, name, message.from_user.id)
    moved = f"\n↪️ Oldin «{esc(course_title(r['old']))}» kursida edi — endi shu kursda." if r["old"] else ""
    warn = ("" if r["notified"] and r["menu_ok"] else
            "\n⚠️ Bu foydalanuvchi botni hali ochmagan — unga bot havolasini yuboring, u /start bossin.")
    text, kb = await course_card(key)
    await message.answer(f"✅ Kurs koordinatori qo'shildi: <b>{esc(name or uid)}</b>.{moved}{warn}\n\n{text}",
                         reply_markup=super_menu())
    await message.answer("Kurs:", reply_markup=kb)


# ---------------------------------------------------------------- kurs koordinatoriga guruhlar biriktirish
async def _groups_screen(key: str, uid: int) -> tuple[str, object, list[dict]]:
    from staffops import course_groups
    info = await course_groups(key)
    me = next((c for c in info["coordinators"] if c["user_id"] == uid), None)
    label = me["label"] if me else f"ID {uid}"
    mine = me["groups"] if me else []
    text = (f"👥 <b>{esc(label)}</b> — «{esc(course_title(key))}» kursidagi guruhlari\n\n"
            + (f"Biriktirilgan: <b>{esc(', '.join(mine))}</b>\n\n" if mine else
               "Guruh biriktirilmagan — koordinator butun kurs talabalari bilan ishlaydi.\n\n")
            + "Fayl yuklaganda (davomat, baholar, buxgalteriya hisoboti va boshqalar) faqat shu guruhlar talabalari "
              "tanilinadi, boshqa guruhlar qatorlari o'tkazib yuboriladi.\n\n"
              "✅ — biriktirilgan · 🔒 — boshqa koordinatorniki · ▫️ — bo'sh. Bosib almashtiring.")
    if is_super(uid):
        text += ("\n\n⚠️ <b>Bu foydalanuvchi super-admin</b> (.env dagi SUPERADMIN_IDS) — u baribir butun kursni "
                 "ko'radi, guruhlar unga amal qilmaydi. Sinab ko'rish uchun boshqa Telegram hisobini koordinator qiling.")
    if not info["groups"]:
        text += ("\n\nKursda hali talabalar yuklanmagan — guruh nomlarini «✍️ Guruh nomlarini yozish» orqali "
                 "kiriting (masalan: <code>XM-21, XM-22</code>).")
    return text, coord_groups_kb(key, uid, info["groups"]), info["groups"]


@router.callback_query(SupCb.filter(F.a == "grp"))
async def cb_groups(cb: CallbackQuery, callback_data: SupCb, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    text, kb, _ = await _groups_screen(callback_data.k, callback_data.u)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(SupCb.filter(F.a == "gt"))
async def cb_group_toggle(cb: CallbackQuery, callback_data: SupCb) -> None:
    from staffops import save_coord_groups
    key, uid = callback_data.k, callback_data.u
    _, _, groups = await _groups_screen(key, uid)
    if not 0 <= callback_data.g < len(groups):
        await cb.answer("Ro'yxat o'zgargan — qaytadan oching.", show_alert=True)
        return
    g = groups[callback_data.g]
    if g["owner"] not in (None, uid):
        await cb.answer(f"«{g['name']}» — {g['owner_label']} ga biriktirilgan. Avval undan olib tashlang.", show_alert=True)
        return
    mine = [x["name"] for x in groups if x["owner"] == uid]
    mine = [x for x in mine if x != g["name"]] if g["owner"] == uid else mine + [g["name"]]
    await save_coord_groups(uid, key, mine, cb.from_user.id)
    await cb.answer("Olib tashlandi" if g["owner"] == uid else "Biriktirildi")
    text, kb, _ = await _groups_screen(key, uid)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(SupCb.filter(F.a == "gc"))
async def cb_groups_clear(cb: CallbackQuery, callback_data: SupCb) -> None:
    from staffops import save_coord_groups
    await save_coord_groups(callback_data.u, callback_data.k, [], cb.from_user.id)
    await cb.answer("Guruhlar olib tashlandi")
    text, kb, _ = await _groups_screen(callback_data.k, callback_data.u)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(SupCb.filter(F.a == "gw"))
async def cb_groups_write(cb: CallbackQuery, callback_data: SupCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Sup.groups)
    await state.update_data(k=callback_data.k, u=callback_data.u)
    await cb.message.answer("✍️ Guruh nomlarini vergul bilan yozing, masalan: <code>XM-21, XM-22, XM-23</code>\n"
                            "Ular koordinatorning hozirgi guruhlariga <b>qo'shiladi</b>. Bekor qilish: /bekor")


@router.message(Sup.groups, F.text, ~F.text.startswith("/"))
async def on_groups_text(message: Message, state: FSMContext) -> None:
    from staffops import course_groups, save_coord_groups, split_group_names
    data = await state.get_data()
    await state.clear()
    key, uid = data["k"], data["u"]
    mine = next((c["groups"] for c in (await course_groups(key))["coordinators"] if c["user_id"] == uid), [])
    r = await save_coord_groups(uid, key, mine + split_group_names(message.text), message.from_user.id)
    note = ""
    if r["taken"]:
        note = ("⚠️ Boshqa koordinatorga biriktirilgani uchun qo'shilmadi: "
                + esc(", ".join(f"{n} ({o})" for n, o in r["taken"])) + "\n\n")
    text, kb, _ = await _groups_screen(key, uid)
    await message.answer(note + text, reply_markup=kb)


# ---------------------------------------------------------------- kurs koordinatorini olib tashlash
@router.callback_query(SupCb.filter(F.a == "delc"))
async def cb_del(cb: CallbackQuery, callback_data: SupCb) -> None:
    await cb.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, olib tashlash", callback_data=SupCb(a="delc_ok", k=callback_data.k, u=callback_data.u))
    kb.button(text="❌ Yo'q", callback_data=SupCb(a="course", k=callback_data.k))
    kb.adjust(2)
    await cb.message.edit_text(f"ID <code>{callback_data.u}</code> ni «{esc(course_title(callback_data.k))}» kurs "
                               "koordinatorlaridan olib tashlaysizmi?\nKurs ma'lumotlari o'chmaydi.",
                               reply_markup=kb.as_markup())


@router.callback_query(SupCb.filter(F.a == "delc_ok"))
async def cb_del_ok(cb: CallbackQuery, callback_data: SupCb) -> None:
    from staffops import unassign_coordinator
    await cb.answer("Olib tashlandi")
    await unassign_coordinator(cb.bot, callback_data.u, callback_data.k)
    text, kb = await course_card(callback_data.k)
    await cb.message.edit_text("✅ Olib tashlandi.\n\n" + text, reply_markup=kb)


# ---------------------------------------------------------------- kursga kirish
@router.message(F.text == BTN_S_ENTER)
@router.message(Command("kursga_kirish"))
async def s_enter(message: Message, state: FSMContext) -> None:
    await state.clear()
    info = await courses_info()
    if not info:
        await message.answer("Hali kurs yo'q.")
        return
    await message.answer("🔀 Qaysi kursda ishlaysiz? Tanlangan kursda kurs koordinatori vositalari (import, panel, "
                         "e'lon, hisobot…) ishlaydi.", reply_markup=courses_kb(info, action="enter"))


@router.callback_query(SupCb.filter(F.a == "enter"))
async def cb_enter(cb: CallbackQuery, callback_data: SupCb) -> None:
    await cb.answer()
    await central.set_active(cb.from_user.id, callback_data.k)
    title = course_title(callback_data.k)
    await cb.message.answer(f"🔀 Endi siz <b>«{esc(title)}»</b> kursida ishlayapsiz — kurs koordinatori menyusi 👇\n"
                            "Qaytish: «🛡 Super-admin menyusi».",
                            reply_markup=coordinator_menu(title, super_admin=True))


# ---------------------------------------------------------------- barcha kurslar holati
@router.message(F.text == BTN_S_OVERVIEW)
@router.message(Command("umumiy"))
async def s_overview(message: Message, state: FSMContext) -> None:
    await state.clear()
    wait = await message.answer("⏳ Barcha kurslar holati hisoblanmoqda…")
    lines = ["📊 <b>Barcha kurslar holati</b>", ""]
    tot = {"students": 0, "linked": 0, "prob": 0, "many": 0, "k": 0.0, "t": 0.0}
    for key in db.keys():
        with use_course(key):
            d = await export.collect("")
        k_sum, t_sum = sum(r["debt"] for r in d["kontrakt"]), sum(r["debt"] for r in d["trimestr"])
        many = sum(1 for r in d["prob"] if r["count"] >= 3)
        cover = f"{round(100 * d['linked'] / d['total'])}%" if d["total"] else "—"
        lines.append(f"🏫 <b>{esc(course_title(key))}</b>: talabalar {d['total']}, ota-onasi ulangan {cover}\n"
                     f"   muammoli {len(d['prob'])} (3+: {many}), davomat past {len(d['att'])}, akademik {len(d['acad'])}\n"
                     f"   💰 kontrakt {len(d['kontrakt'])} ({fmt_money(k_sum)}), 💳 trimestr {len(d['trimestr'])} "
                     f"({fmt_money(t_sum)})")
        tot["students"] += d["total"]; tot["linked"] += d["linked"]; tot["prob"] += len(d["prob"])
        tot["many"] += many; tot["k"] += k_sum; tot["t"] += t_sum
    lines += ["", f"<b>Jami</b>: talabalar {tot['students']}, ota-onasi ulangan "
              + (f"{round(100 * tot['linked'] / tot['students'])}%" if tot["students"] else "—")
              + f", muammoli {tot['prob']} (3+: {tot['many']}), kontrakt qarzi {fmt_money(tot['k'])}, "
              f"trimestr qarzi {fmt_money(tot['t'])}"]
    await wait.edit_text("\n".join(lines))


# ---------------------------------------------------------------- zaxira nusxa va xatolar jurnali
@router.message(F.text == BTN_S_BACKUP)
@router.message(Command("zaxira"))
async def s_backup(message: Message, state: FSMContext) -> None:
    await state.clear()
    wait = await message.answer("⏳ Zaxira nusxa tayyorlanmoqda (barcha kurs bazalari va umumiy ro'yxat)…")
    info = await backup.make_backup()
    await backup.send(message.bot, info, to={message.from_user.id})
    await wait.delete()


@router.message(F.text == BTN_S_ERRORS)
@router.message(Command("xatolar"))
async def s_errors(message: Message, state: FSMContext) -> None:
    await state.clear()
    path = LOG_DIR / "errors.log"
    last = tail(path, 25)
    head = f"🧾 <b>Xatolar jurnali</b> — so'nggi 24 soatda tizim xatolari: {errors_since(24)}\n"
    if not last.strip():
        await message.answer(head + "\nJurnal bo'sh ✅")
        return
    await message.answer(head + "\nOxirgi yozuvlar:\n<pre>" + esc(last[-3300:]) + "</pre>")
    data = path.read_bytes()
    await message.answer_document(BufferedInputFile(data[-5_000_000:], "errors.log"),
                                  caption="To'liq jurnal (ogohlantirish va xatolar). Barcha yozuvlar: logs/bot.log")


@router.message(StateFilter(Sup.new_course, Sup.rename, Sup.name, Sup.groups, Tpl.title, Tpl.file, Tpl.map, Tpl.confirm, Tpl.edit),
                F.text.startswith("/bekor"))
async def s_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=super_menu())


# ================================================================ shablonlar
_TRIVIAL = {"", "n", "no", "nomer", "raqam", "t r", "tr"}


def _trivial(text: str) -> bool:
    """«№», «T/r» kabi tartib raqami ustunlari — so'ralmaydi."""
    t = text.strip()
    return t in ("№", "#", "№ п/п", "п/п") or normalize_text(t) in _TRIVIAL


async def _templates_list(target: Message, edit: bool = False) -> None:
    items = await templates.catalog(include_hidden=True)
    text = ("📑 <b>Shablonlar</b> — kurs koordinatorlari /shablon orqali oladigan import namunalari (barcha kurslar "
            "uchun umumiy).\n\n📄 asl · ✏️ o'zgartirilgan · 🆕 qo'shilgan · 🙈 koordinatorlarga ko'rinmaydi\n\n"
            "Shablonni tanlang — yuklab olish, yangi versiya yuklash (shaklini o'zgartirish), versiyalar, asl holiga "
            "qaytarish.")
    if edit:
        await target.edit_text(text, reply_markup=templates_kb(items))
    else:
        await target.answer(text, reply_markup=templates_kb(items))


@router.message(F.text == BTN_S_TEMPLATES)
@router.message(Command("shablonlar"))
async def s_templates(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _templates_list(message)


@router.callback_query(TplCb.filter(F.a == "list"))
async def tp_list(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await _templates_list(cb.message, edit=True)


async def _card(slot: str) -> tuple[str, object] | tuple[None, None]:
    t = await templates.get(slot)
    if not t:
        return None, None
    versions = await central.template_versions(slot)
    if t["changed"]:
        state = f"✏️ o'zgartirilgan — {t['version']}-versiya, {fmt_dt(t['updated'])}"
    elif not t["builtin"]:
        state = f"🆕 qo'shilgan — {t['version']}-versiya, {fmt_dt(t['updated'])}"
    else:
        state = "📄 asl shablon (bot bilan kelgan)"
    lines = [f"📑 <b>{esc(t['title'])}</b>", f"Turi: {esc(templates.kind_title(t['kind']))}", f"Holati: {state}",
             f"Fayl: <code>{esc(t['file_name'])}</code>"]
    if t["hidden"]:
        lines.append("🙈 Kurs koordinatorlariga ko'rinmaydi")
    if t["description"]:
        lines.append(f"\nIzoh (koordinatorlarga fayl bilan birga ko'rinadi):\n{esc(t['description'])}")
    if t["kind"] and t["kind"] not in ("debts", "debts_t"):
        grp = t["kind"] if t["kind"] != "attendance" else None
        req = templates.REQUIRED.get(grp or "", [])
        if req:
            lines.append("\nMajburiy ustunlar: " + ", ".join(templates.label(f) for f in req))
    return "\n".join(lines), template_card_kb(t, bool(versions))


@router.callback_query(TplCb.filter(F.a == "open"))
async def tp_open(cb: CallbackQuery, callback_data: TplCb, state: FSMContext) -> None:
    await state.clear()
    text, kb = await _card(callback_data.s)
    if not text:
        await cb.answer("Shablon topilmadi.", show_alert=True)
        return
    await cb.answer()
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(TplCb.filter(F.a == "get"))
async def tp_get(cb: CallbackQuery, callback_data: TplCb) -> None:
    t = await templates.get(callback_data.s)
    await cb.answer()
    if t:
        await cb.message.answer_document(FSInputFile(t["path"], filename=t["file_name"]),
                                         caption=f"📑 {esc(t['title'])}" + (f" · v{t['version']}" if t["version"] else ""))


# ---------------------------------------------------------------- yangi versiya / yangi shablon
@router.callback_query(TplCb.filter(F.a == "up"))
async def tp_upload(cb: CallbackQuery, callback_data: TplCb, state: FSMContext) -> None:
    t = await templates.get(callback_data.s)
    if not t:
        await cb.answer("Shablon topilmadi.", show_alert=True)
        return
    await cb.answer()
    await state.set_state(Tpl.file)
    await state.update_data(slot=t["slot"], kind=t["kind"], title=t["title"], new=False)
    await cb.message.answer(_upload_hint(t["kind"], t["title"]))


@router.callback_query(TplCb.filter(F.a == "new"))
async def tp_new(cb: CallbackQuery) -> None:
    await cb.answer()
    kb = InlineKeyboardBuilder()
    for kind, title in templates.NEW_KINDS:
        kb.button(text=title, callback_data=TplCb(a="newk", k=kind))
    kb.button(text="📄 Hujjat namunasi (import qilinmaydi)", callback_data=TplCb(a="newk", k="doc"))
    kb.button(text="« Orqaga", callback_data=TplCb(a="list"))
    kb.adjust(2)
    await cb.message.edit_text(
        "➕ <b>Yangi shablon</b>\n\nQaysi ma'lumot uchun? Import turiga bog'langan shablon — kurs koordinatorlari uni "
        "to'ldirib /import bilan yuklaydi (masalan, «Baholar»ning boshqa ko'rinishi). Hujjat namunasi — Word, PDF yoki "
        "Excel shakl, koordinatorlarga shunchaki tarqatiladi.", reply_markup=kb.as_markup())


@router.callback_query(TplCb.filter(F.a == "newk"))
async def tp_new_kind(cb: CallbackQuery, callback_data: TplCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Tpl.title)
    await state.update_data(kind=None if callback_data.k == "doc" else callback_data.k, new=True)
    await cb.message.answer(f"Turi: <b>{esc(templates.kind_title(None if callback_data.k == 'doc' else callback_data.k))}</b>"
                            "\n\nShablon nomini yozing (kurs koordinatorlariga shunday ko'rinadi), masalan "
                            "<code>Baholar — o'qituvchi jurnali</code>.\nBekor qilish: /bekor")


@router.message(Tpl.title, F.text, ~F.text.startswith("/"))
async def tp_title(message: Message, state: FSMContext) -> None:
    title = " ".join(message.text.split())[:80]
    await state.update_data(title=title)
    await state.set_state(Tpl.file)
    await message.answer(_upload_hint((await state.get_data())["kind"], title))


def _upload_hint(kind: str | None, title: str) -> str:
    if not kind:
        return (f"📎 «{esc(title)}» uchun faylni yuboring (Word, PDF, Excel yoki boshqa hujjat). Bekor qilish: /bekor")
    return (f"📎 «{esc(title)}» shablonining faylini (.xlsx) yuboring.\n\nBot sarlavhalarni import bilan bir xil "
            "tekshiradi: tanimagan ustunlar uchun qaysi ma'lumot ekanini sizdan so'raydi — bu nom import paytida ham "
            "taniladi. Majburiy ustun bo'lmasa, shablon qabul qilinmaydi.\nBekor qilish: /bekor")


@router.message(Tpl.file, F.document)
async def tp_file(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    doc, kind = message.document, data.get("kind")
    name = doc.file_name or "shablon"
    if kind and not name.lower().endswith((".xlsx", ".xlsm")):
        await message.answer("Import shabloni .xlsx formatida bo'lishi kerak. Faylni qayta yuboring yoki /bekor.")
        return
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("Fayl 20 MB dan katta — Telegram bot uni yuklab ololmaydi.")
        return
    tmp = Path(tempfile.mkdtemp()) / ("shablon" + Path(name).suffix.lower())  # kengaytma kerak: openpyxl .xlsx ni taniydi
    await message.bot.download(doc, destination=tmp)
    await state.update_data(tmp=str(tmp), file_name=name, asked=[], learned=[])
    if not kind:
        await _confirm(message, state)
        return
    try:
        analysis = await asyncio.to_thread(templates.analyze, tmp, kind)
    except Exception as e:
        log.warning("Shablonni o'qib bo'lmadi: %s", e)
        await message.answer(f"❌ Faylni o'qib bo'lmadi: {esc(e)}\nBoshqa fayl yuboring yoki /bekor.")
        return
    await _next_column(message, state, analysis)


async def _next_column(message: Message, state: FSMContext, analysis: dict) -> None:
    """Tanilmagan ustunlarni birma-bir so'raydi; hammasi hal bo'lgach — qayta tekshiradi."""
    data = await state.get_data()
    asked = set(data.get("asked") or [])
    todo = [u for u in analysis["unknown"] if u["col"] not in asked and not _trivial(u["text"])]
    if todo and analysis["group"]:
        u = todo[0]
        free = templates.free_fields(analysis["group"], analysis, {})
        req = set(templates.REQUIRED.get(analysis["group"], []))
        fields = sorted(free, key=lambda f: (f not in req, templates.label(f)))
        known = ", ".join(f"«{esc(k['text'])}» → {templates.label(k['field'])}" for k in analysis["known"]) or "—"
        await state.set_state(Tpl.map)
        await state.update_data(col=u["col"], col_text=u["text"], group=analysis["group"])
        await message.answer(
            f"🔎 Tanilgan ustunlar: {known}\n\n❓ <b>«{esc(u['text'])}»</b> ustunini bot tanimadi "
            f"({len(todo)} ta qoldi). Bu qaysi ma'lumot?" + ("\n⭐ — majburiy ustun" if req & set(free) else ""),
            reply_markup=map_field_kb([(f, ("⭐ " if f in req else "") + templates.label(f)) for f in fields]))
        return
    final = await asyncio.to_thread(templates.analyze, Path(data["tmp"]), data["kind"])
    if final["fatal"]:
        await state.set_state(Tpl.file)
        await message.answer(f"❌ <b>Shablon qabul qilinmadi.</b>\n{esc(final['fatal'])}\n\nFaylni tuzatib qayta yuboring "
                             "(yoki tanilmagan ustunni to'g'ri belgilang). Bekor qilish: /bekor")
        return
    await _confirm(message, state, final)


@router.callback_query(TplMapCb.filter(), Tpl.map)
async def tp_map(cb: CallbackQuery, callback_data: TplMapCb, state: FSMContext) -> None:
    data = await state.get_data()
    await cb.answer()
    asked = list(data.get("asked") or [])
    learned = list(data.get("learned") or [])
    if callback_data.f == "skipall":
        analysis = await asyncio.to_thread(templates.analyze, Path(data["tmp"]), data["kind"])
        asked += [u["col"] for u in analysis["unknown"]]
        await cb.message.edit_text("⏭ Qolgan tanilmagan ustunlar e'tiborsiz qoldirildi.")
    elif callback_data.f == "skip":
        asked.append(data["col"])
        await cb.message.edit_text(f"🚫 «{esc(data['col_text'])}» — e'tiborsiz qoldirildi (import o'qimaydi).")
    else:
        await templates.learn(data["group"], data["col_text"], callback_data.f, cb.from_user.id)
        asked.append(data["col"])
        learned.append(f"«{data['col_text']}» → {templates.label(callback_data.f)}")
        log.info("Ustun nomi o'rgatildi: %s «%s» → %s", data["group"], data["col_text"], callback_data.f)
        await cb.message.edit_text(f"✅ «{esc(data['col_text'])}» — <b>{templates.label(callback_data.f)}</b>. "
                                   "Import bu nomni endi taniydi.")
    await state.update_data(asked=asked, learned=learned)
    analysis = await asyncio.to_thread(templates.analyze, Path(data["tmp"]), data["kind"])
    await _next_column(cb.message, state, analysis)


async def _confirm(message: Message, state: FSMContext, analysis: dict | None = None) -> None:
    data = await state.get_data()
    await state.set_state(Tpl.confirm)
    lines = [f"📑 <b>{esc(data['title'])}</b> — {'yangi shablon' if data.get('new') else 'yangi versiya'}",
             f"Fayl: <code>{esc(data['file_name'])}</code>"]
    if analysis:
        if analysis["wide"]:
            lines.append("✅ Fanlar ustunlarda (HEMIS «O'rtacha ball» ko'rinishi) — import to'g'ri o'qiydi.")
        elif analysis["group"]:
            lines.append("✅ Import o'qiydigan ustunlar: " + ", ".join(
                f"«{esc(k['text'])}» → {templates.label(k['field'])}" for k in analysis["known"]))
        else:
            lines.append("✅ Buxgalteriya hisoboti formati — import to'g'ri o'qiydi.")
        ignored = [u["text"] for u in analysis["unknown"]]
        if ignored:
            lines.append("🚫 E'tiborsiz: " + esc(", ".join(ignored)))
    if data.get("learned"):
        lines.append("🧠 Import o'rgandi: " + esc("; ".join(data["learned"])))
    lines.append("\nSaqlaymizmi? Eski versiya tarixda qoladi — istalgan payt qaytish mumkin.")
    await message.answer("\n".join(lines), reply_markup=template_save_kb())


@router.callback_query(TplCb.filter(F.a == "save"), Tpl.confirm)
async def tp_save(cb: CallbackQuery, callback_data: TplCb, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await cb.answer("Saqlanmoqda…")
    slot = data.get("slot") or await central.next_custom_slot()
    if data.get("new"):
        await central.set_template_meta(slot, title=data["title"], kind=data["kind"])
    version = await templates.save_version(slot, data["kind"], Path(data["tmp"]), data["file_name"], cb.from_user.id)
    shutil.rmtree(Path(data["tmp"]).parent, ignore_errors=True)
    log.info("Shablon saqlandi: %s v%s (%s)", slot, version, data["file_name"])
    sent = 0
    if callback_data.k == "n":
        sent = await _send_to_coordinators(cb.bot, slot, "yangi" if data.get("new") else "yangilandi")
    await cb.message.edit_text(f"✅ «{esc(data['title'])}» saqlandi — {version}-versiya."
                               + (f"\n📨 Kurs koordinatorlariga yuborildi: {sent} ta." if callback_data.k == "n" else
                                  "\nKurs koordinatorlari /shablon orqali oladi."))
    text, kb = await _card(slot)
    await cb.message.answer(text, reply_markup=kb)


async def _send_to_coordinators(bot, slot: str, what: str) -> int:
    t = await templates.get(slot)
    if not t:
        return 0
    caption = (f"📑 <b>{'Yangi shablon' if what == 'yangi' else 'Shablon yangilandi'}</b>: {esc(t['title'])} "
               f"(v{t['version']})\n" + (f"{esc(t['description'])}\n" if t["description"] else "")
               + "Keyingi yuklashlarda shu shakldan foydalaning. Barcha shablonlar: /shablon")
    sent = 0
    for uid in sorted(set(ADMIN_COURSE)):
        try:
            await bot.send_document(uid, FSInputFile(t["path"], filename=t["file_name"]), caption=caption[:1024])
            sent += 1
        except Exception as e:
            log.warning("Shablon koordinatorga yuborilmadi (%s): %s", uid, e)
    return sent


# ---------------------------------------------------------------- nomi va izohi, versiyalar, asl holi
@router.callback_query(TplCb.filter(F.a == "edit"))
async def tp_edit(cb: CallbackQuery, callback_data: TplCb, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Tpl.edit)
    await state.update_data(slot=callback_data.s)
    await cb.message.answer("✏️ Yangi nom va izohni yuboring: <b>birinchi qator — nomi</b>, keyingi qatorlar — izoh "
                            "(kurs koordinatorlariga fayl bilan birga ko'rinadi, masalan qanday to'ldirish). Faqat nom "
                            "yozsangiz, izoh o'chadi.\nBekor qilish: /bekor")


@router.message(Tpl.edit, F.text, ~F.text.startswith("/"))
async def tp_edit_save(message: Message, state: FSMContext) -> None:
    slot = (await state.get_data())["slot"]
    await state.clear()
    first, _, rest = message.text.strip().partition("\n")
    await central.set_template_meta(slot, title=" ".join(first.split())[:80], description=rest.strip()[:800] or None)
    text, kb = await _card(slot)
    await message.answer("✅ Saqlandi.\n\n" + text, reply_markup=kb)


@router.callback_query(TplCb.filter(F.a == "vers"))
async def tp_versions(cb: CallbackQuery, callback_data: TplCb) -> None:
    await cb.answer()
    versions = await central.template_versions(callback_data.s)
    kb = InlineKeyboardBuilder()
    lines = ["📜 <b>Versiyalar</b> (yangisi yuqorida):"]
    for v in versions[:10]:
        mark = "✅ joriy" if v["active"] else ""
        lines.append(f"v{v['version']} · {fmt_dt(v['uploaded_at'])} · {esc(v['file_name'])} {mark}")
        kb.button(text=f"⬇️ v{v['version']}", callback_data=TplCb(a="getv", s=callback_data.s, v=v["id"]))
        if not v["active"]:
            kb.button(text=f"↩️ v{v['version']} ni tiklash", callback_data=TplCb(a="restore", s=callback_data.s, v=v["id"]))
    kb.button(text="« Orqaga", callback_data=TplCb(a="open", s=callback_data.s))
    kb.adjust(2)
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(TplCb.filter(F.a == "getv"))
async def tp_get_version(cb: CallbackQuery, callback_data: TplCb) -> None:
    v = next((x for x in await central.template_versions(callback_data.s) if x["id"] == callback_data.v), None)
    await cb.answer()
    if v and (templates.TPL_DIR / v["stored"]).exists():
        await cb.message.answer_document(FSInputFile(templates.TPL_DIR / v["stored"], filename=v["file_name"]),
                                         caption=f"v{v['version']} · {fmt_dt(v['uploaded_at'])}")


@router.callback_query(TplCb.filter(F.a == "restore"))
async def tp_restore(cb: CallbackQuery, callback_data: TplCb) -> None:
    row = await central.activate_template(callback_data.v)
    await cb.answer(f"v{row['version']} tiklandi — kurs koordinatorlari endi shu versiyani oladi." if row else "Topilmadi",
                    show_alert=True)
    log.info("Shablon versiyasi tiklandi: %s v%s", callback_data.s, row["version"] if row else "?")
    text, kb = await _card(callback_data.s)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(TplCb.filter(F.a == "reset"))
async def tp_reset(cb: CallbackQuery, callback_data: TplCb) -> None:
    await central.deactivate_slot(callback_data.s)
    await cb.answer("Asl shablon tiklandi. Yuklangan versiyalar tarixda saqlanadi.", show_alert=True)
    log.info("Asl shablon tiklandi: %s", callback_data.s)
    text, kb = await _card(callback_data.s)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(TplCb.filter(F.a.in_({"hide", "show"})))
async def tp_hide(cb: CallbackQuery, callback_data: TplCb) -> None:
    await central.set_template_meta(callback_data.s, hidden=1 if callback_data.a == "hide" else 0)
    await cb.answer("Kurs koordinatorlariga ko'rinmaydi." if callback_data.a == "hide" else "Kurs koordinatorlariga ko'rinadi.")
    text, kb = await _card(callback_data.s)
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(TplCb.filter(F.a == "del"))
async def tp_delete(cb: CallbackQuery, callback_data: TplCb) -> None:
    await cb.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Ha, o'chirish", callback_data=TplCb(a="del_ok", s=callback_data.s))
    kb.button(text="« Yo'q", callback_data=TplCb(a="open", s=callback_data.s))
    await cb.message.edit_text("Shablon kurs koordinatorlari ro'yxatidan olib tashlanadi (fayllari tarixda qoladi). "
                               "O'chirasizmi?", reply_markup=kb.as_markup())


@router.callback_query(TplCb.filter(F.a == "del_ok"))
async def tp_delete_ok(cb: CallbackQuery, callback_data: TplCb) -> None:
    await central.deactivate_slot(callback_data.s)
    log.info("Shablon o'chirildi: %s", callback_data.s)
    await cb.answer("O'chirildi.")
    await _templates_list(cb.message, edit=True)
