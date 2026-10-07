"""Kurs koordinatori (admin) buyruqlari: import, e'lon, statistika, so'rovlarni tasdiqlash, savollarga javob."""
from __future__ import annotations

import asyncio
import time
import secrets
import re
import logging
import shutil
import tempfile
import uuid
from collections import OrderedDict
from datetime import timedelta
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, InputMediaDocument, Message

import absence
import academic
import individual
from config import ADMIN_IDS, GPA_MIN, HEMIS_STATS_HOURS_PER_UNIT, PAY_REMIND_DAYS, HOURS_PER_PAIR, NOTIFY_MAX_AGE_DAYS
from database import db
from family import adopt_parents
from tenancy import (central, coordinator_groups, course_title, current_course, current_user, group_scope, in_scope,
                     scope_label, scope_students, viewer_scope)
from importer import (COMPATIBLE, KIND_TITLES, detect_kinds, load_rows, parse_rows, resolve_by_name, stats_subject,
                      resolve_students)
from guard import recheck_parents
import redact
from keyboards import (MENU_TEXTS, ExpCb, ImpOkCb, ImpPickCb, PanelCb, export_kb, imp_confirm_kb, imp_pick_kb, panel_kb, AnsCb, BcCb, DocActCb, DocPickCb, DocRevCb, DocStuCb, DocTypeCb, GroupCb, GuardCb,
                       ImpCb, LinkCb, broadcast_confirm_kb, broadcast_target_kb, doc_confirm_kb, doc_pick_kb,
                       doc_revoke_kb, doc_students_kb, doc_type_kb, guard_kb, import_kb)
from notifier import (academic_keys, check_thresholds, notify_absence_decrease, notify_academic, notify_grades, notify_links, notify_new_absences, notify_present_marks, check_subject_limits, notify_payments,
                      notify_stats_changes,
                      safe_send)
import chat
import export
import templates
import loc
import termsheet
import status
from reports import UPDATE_KEYS, last_update, schedule_report
from subject_limits import limit_pairs
from utils import (CONTRACT, credits_from_code, subject_key, GRANT, normalize_phone, fmt_pairs, fmt_dt, now_iso, detect_doc_type, fmt_money, doc_keywords, doc_title, esc, fmt_date, fmt_num, fmt_phone, fmt_size,
                   group_key, name_score, normalize_text, parse_course, parse_date, parse_user_dates, split_message,
                   today, fmt_gpa, fmt_limit,
                   week_bounds)

log = logging.getLogger(__name__)

from aiogram.filters.callback_data import CallbackData

router = Router(name="admin")
router.message.filter(F.chat.type == "private")  # guruhlarda faqat handlers/groups.py ishlaydi
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

NOT_CMD = (~F.text.in_(MENU_TEXTS)) & (~F.text.startswith("/"))


class Imp(StatesGroup):
    file = State()
    confirm = State()


class Bc(StatesGroup):
    groups = State()
    content = State()
    confirm = State()


class InfoEdit(StatesGroup):
    text = State()


class Ans(StatesGroup):
    text = State()


class DocSend(StatesGroup):
    pick = State()
    student = State()
    dtype = State()
    file = State()
    confirm = State()


ADMIN_HELP = (
    "🛠 <b>Kurs koordinatori buyruqlari</b>\n\n"
    "/import — Excel fayllarni yuklash: turini bir marta tanlab, bir nechta faylni birga yuborish mumkin; "
    "«🤖 Aralash» — har xil turdagi fayllar, turini bot aniqlaydi\n"
    "/tayyor — import sessiyasini yakunlash (bir nechta fayl yuklangach)\n"
    "/shablon — import uchun Excel namunalarini olish\n"
    "/toldir <code>01.09.2026 20.09.2026</code> — jadvaldagi, lekin davomatda yo'q darslarni «qatnashdi» deb "
    "belgilash (HEMIS faqat qoldirilgan darslarni bergan hollarda)\n"
    "/elon — ota-onalarga e'lon yuborish (barchaga yoki guruhlar bo'yicha)\n"
    "/talaba <code>familiya ism</code> — talabani qidirish\n"
    "/jadval <code>familiya ism</code> — talabaning shaxsiy dars jadvali (asosiy fanlar + tanlov/2-til)\n"
    "/hisobot — 📥 kurs holati hisoboti: Excel yoki PDF (dekanat yig'ilishi, rahbariyat uchun)\n"
    "/koordinator — ota-onalarga ko'rinadigan ismingiz va telefoningiz\n"
    "/tarjimalar — 🌐 fan va fakultet nomlarining ruscha va inglizcha tarjimalari (Excel)\n"
    "/panel — 📊 kurs holati: qarzdorlar, davomat muammolari, muammoli talabalar (masalan <code>/panel 3-kurs</code>)\n"
    "/muddat — kontrakt va trimestr to'lov muddatlari (eslatmalar shu asosda yuboriladi)\n"
    "/qarzdorlar — moliyaviy qarzdorlar: kontrakt va trimestr (masalan <code>/qarzdorlar trimestr 2-kurs</code>)\n"
    "/akademik — akademik qarzdorlar (dekanatning qarzdorlar ro'yxati bo'yicha)\n"
    f"/chegaralar — dars qoldirish chegaralariga yetgan talabalar ({'/'.join(fmt_num(x / HOURS_PER_PAIR) for x in absence.LEVELS)} para = "
    f"{'/'.join(map(str, absence.LEVELS))} soat)\n"
    "/hujjat — tushuntirish xati, dekan ogohlantirishi yoki hayfsanni (PDF) ota-onaga yuborish. "
    "PDF faylni botga shunchaki yuborsangiz ham bo'ladi\n"
    "/hujjatlar <code>familiya ism</code> — talabaga yuborilgan hujjatlar, qaytarib olish tugmasi bilan\n"
    "/stat — statistika\n"
    "/info — «Foydali ma'lumot» matnini o'zgartirish\n"
    "/bekor — joriy amalni bekor qilish\n\n"
    "<b>Talabalarni aniqlash</b> (bot faqat ota-onalar uchun)\n"
    "/guruhlar — bot qo'shilgan talabalar Telegram guruhlari\n"
    "/tekshir — ro'yxatdan o'tganlarning barchasini qayta tekshirish\n"
    "/bloklar — talaba deb bloklanganlar ro'yxati\n"
    "Guruhni akademik guruhga bog'lash: guruhning o'zida <code>/guruh IQ-21</code>\n\n"
    "💡 Import paytida fayl izohiga (caption) <code>jim</code> deb yozsangiz, ota-onalarga avtomatik xabar yuborilmaydi."
)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Kurs holati", callback_data=PanelCb(v="open"))
    await message.answer(await _course_line_full() + ADMIN_HELP, reply_markup=kb.as_markup())


def _course_line() -> str:
    """Ko'p kursli rejim: koordinator qaysi kurs bazasida ishlayotgani (har bir kursning ma'lumotlari alohida)."""
    key = current_course()
    return f"📁 Kurs: <b>{esc(course_title(key))}</b> · ma'lumotlar: <code>data/{esc(key)}/</code>\n\n" if key else ""


async def _course_line_full() -> str:
    """/admin uchun: kurs va ota-onalarga ko'rinadigan koordinator ismi (bo'lmasa — qanday kiritish)."""
    uid = current_user.get()
    mine = group_scope(uid) is not None
    name = (await db.get_setting(f"coordinator_name:{uid}") if mine else None) or await db.get_setting("coordinator_name")
    who = (f"🧑‍🏫 Ota-onalarga: <b>{esc(name)}</b>\n" if name else
           "🧑‍🏫 Ota-onalarga ko'rinadigan ismingiz kiritilmagan: <code>/koordinator N. Egamberdiyev +998 ...</code>\n")
    if mine:
        who += ("👥 Guruhlaringiz: <b>" + esc(", ".join(sorted(coordinator_groups(uid).values(), key=str.lower)))
                + "</b> — ro'yxatlar, hisobotlar va xabarlar faqat shu guruhlar bo'yicha\n")
    who += "\n"
    return _course_line().rstrip("\n") + "\n" + who if _course_line() else who


# ---------------------------------------------------------------- import
def _scope_note(user_id: int) -> str:
    groups = coordinator_groups(user_id) if group_scope(user_id) is not None else {}
    if not groups:
        return ""
    return ("\n\n👥 <b>Sizning guruhlaringiz:</b> " + esc(", ".join(sorted(groups.values(), key=str.lower)))
            + ". Fayllarda faqat shu guruhlar talabalari tanilinadi, boshqalari o'tkazib yuboriladi.")


@router.message(Command("import"))
async def cmd_import(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Qaysi ma'lumotni yuklaysiz? Bir marta tanlab, <b>bir nechta faylni</b> birga yuborish mumkin; "
        "har xil turdagi fayllar uchun — «🤖 Aralash».\n\n"
        "Tavsiya etilgan tartib: 1) talabalar → 2) dars jadvali → 3) davomat → 4) baholar.\n\n"
        "HEMIS eksport fayllarini o'zgartirmasdan yuborish mumkin:\n"
        "• <b>Talabalar</b> — «Talabalar kontingenti» (ota-ona telefoni ustunini qo'shing);\n"
        "• <b>Davomat</b> — «O'quvchilarni darslarga qatnashish statistikasi» yoki kunlik davomat;\n"
        "• <b>Baholar</b> — guruhning «O'rtacha ball» jadvali;\n"
        "• <b>Dars jadvali</b> — faqat guruhning asosiy fanlari;\n"
        "• <b>Tanlov/2-til: kim o'qiydi</b> — har bir talaba qaysi tanlov fani va ikkinchi tilni (qaysi oqimda) "
        "o'qishi. «O'rtacha ball» jadvalini ham yuborish mumkin: bahosi bor fan — talaba o'qiydigan fan;\n"
        "• <b>Tanlov/2-til: jadval</b> — bu fanlarning darslari (fan, oqim, kun, juftlik), guruhga bog'lanmagan. "
        "Ular faqat biriktirilgan talabalarning shaxsiy jadvalida ko'rinadi.\n"
        "• <b>Kontrakt qarzdorligi</b> — buxgalteriya hisoboti (kontrakt qarzdorlar ro'yxati yoki aylanma vedomost).\n"
        "«📱 Talaba telefonlari» — talabalarning o'z raqamlari (talaba ota-ona sifatida kira olmasligi uchun)."
        + _scope_note(message.from_user.id),
        reply_markup=import_kb(),
    )


@router.callback_query(ImpCb.filter())
async def cb_import_kind(cb: CallbackQuery, callback_data: ImpCb, state: FSMContext) -> None:
    await state.set_state(Imp.file)
    await state.update_data(kind=callback_data.kind, count=0, done=[], skipped=[], pending={}, silent_groups=[],
                            ts=time.time())
    if callback_data.kind == "auto":
        head = ("📎 Endi fayllarni yuboring — <b>har xil turdagi</b> fayllar bo'lishi mumkin (baholar, davomat, "
                "qarzdorlik…). Har birining turini bot o'zi aniqlaydi; aniqlay olmasa — sizdan so'raydi.")
    else:
        head = (f"📎 Endi <b>{KIND_TITLES[callback_data.kind]}</b> fayllarini (.xlsx) yuboring — bittalab yoki "
                "bir nechtasini birga (Telegram'da bir nechta faylni belgilab yuborish mumkin).\n"
                "Orasida boshqa turdagi fayl bo'lsa, o'sha fayl bo'yicha darhol xabar beraman.")
    await cb.message.edit_text(
        head + "\n\nMa'lumot birinchi varaqda, sarlavha qatori bilan bo'lishi kerak. Ota-onalarga xabar "
        "yubormaslik uchun izohga <code>jim</code> deb yozing (bir nechta fayl birga yuborilsa — birinchisining "
        "izohiga).\n\nTugatgach: /tayyor · Bekor qilish: /bekor")
    await cb.answer()


_import_locks: dict[int, asyncio.Lock] = {}
IMPORT_SESSION_IDLE = 30 * 60  # soniya: shuncha vaqt fayl kelmasa, import sessiyasi yopiladi


@router.message(Imp.file, F.document)
async def on_import_file(message: Message, state: FSMContext) -> None:
    doc = message.document
    name = doc.file_name or "fayl"
    if _is_pdf(doc):  # import ochiq paytda PDF — sessiyani yopib, rasmiy hujjat sifatida qabul qilamiz
        await _finish_session(message, state, note="PDF hujjat keldi — import sessiyasi yopildi.")
        await on_pdf(message, state)
        return
    if not name.lower().endswith((".xlsx", ".xlsm")):
        await message.answer(f"«{esc(name)}»: faqat .xlsx formatidagi fayl qabul qilinadi (Excel'da «Сохранить как → "
                             ".xlsx»). Boshqa fayllar yuklanishda davom etadi.")
        return
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer(f"«{esc(name)}» 20 MB dan katta — Telegram bot uni yuklab ololmaydi. Faylni qismlarga bo'ling.")
        return
    # bir nechta fayl birga yuborilganda ular navbat bilan — biri tugagach ikkinchisi — qayta ishlanadi
    async with _import_locks.setdefault(message.from_user.id, asyncio.Lock()):
        if await state.get_state() != Imp.file.state:
            return  # sessiya shu orada yopilgan
        data = await state.get_data()
        if time.time() - data.get("ts", 0) > IMPORT_SESSION_IDLE:  # uzoq vaqt fayl kelmagan — eski turda yuklanmasin
            await _finish_session(message, state, note="⌛️ Import sessiyasi 30 daqiqa ishlatilmagani uchun yopilgan.")
            await message.answer("Faylni yuklash uchun /import bilan turini qaytadan tanlang.")
            return
        n = data.get("count", 0) + 1
        silent_groups = list(data.get("silent_groups") or [])
        caption = message.caption or ""
        if message.media_group_id and "jim" in caption.lower():
            silent_groups.append(message.media_group_id)
        if message.media_group_id in silent_groups and "jim" not in caption.lower():
            caption = (caption + " jim").strip()  # guruhdagi birinchi faylning «jim» izohi — hammasiga
        await state.update_data(count=n, silent_groups=silent_groups, ts=time.time())
        progress = await message.answer(f"⏳ {n}-fayl «{esc(name)}» o'qilmoqda…")
        tmpdir = Path(tempfile.mkdtemp())
        path = tmpdir / "import.xlsx"
        try:
            await message.bot.download(doc, destination=path)
            rows = await asyncio.to_thread(load_rows, str(path))
        except Exception as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            log.exception("Import xatosi")
            await progress.edit_text(f"❌ {n}-fayl «{esc(name)}»: o'qib bo'lmadi: {esc(e)}")
            await _session_add(state, "skipped", name, None)
            return
        kind = data["kind"]
        detected = await asyncio.to_thread(detect_kinds, rows, name)
        pend = {"path": str(path), "tmpdir": str(tmpdir), "kind": kind, "caption": caption, "file_name": name, "n": n}
        if kind == "auto":
            if not detected:  # turini aniqlab bo'lmadi — kurs koordinatori tanlaydi
                tok = await _add_pending(state, pend)
                await progress.edit_text(f"❓ {n}-fayl «{esc(name)}»: turi aniqlanmadi. Bu qaysi fayl?",
                                         reply_markup=imp_pick_kb(tok))
                return
            kind = detected[0]
            await progress.edit_text(f"⏳ {n}-fayl «{esc(name)}» — <b>{KIND_TITLES[kind]}</b> sifatida yuklanmoqda…")
        elif detected and not (set(detected) & COMPATIBLE.get(kind, {kind})):
            # Ma'lumotlarni tekshirish: fayl tanlangan import turiga o'xshamaydi — darhol xabar, qolganlari davom etadi
            tok = await _add_pending(state, {**pend, "det": detected[0]})
            await progress.edit_text(
                f"⚠️ <b>Diqqat!</b> {n}-fayl «{esc(name)}»\n\nUshbu faylda <b>«{KIND_TITLES[detected[0]]}»</b> fayliga xos "
                f"ustunlar aniqlandi.\nSiz <b>«{KIND_TITLES[kind]}»</b> importini tanladingiz.\n\nBu fayl bilan nima qilamiz?"
                " (Qolgan fayllar yuklanishda davom etadi.)",
                reply_markup=imp_confirm_kb(KIND_TITLES[detected[0]], tok, KIND_TITLES[kind]))
            return
        shutil.rmtree(tmpdir, ignore_errors=True)
        ok = await _process_import(message.bot, progress, kind, rows, caption, name, n=n, user_id=message.from_user.id)
        await _session_add(state, "done" if ok else "skipped", name, kind)


async def _add_pending(state: FSMContext, item: dict) -> str:
    tok = secrets.token_hex(4)
    pending = dict((await state.get_data()).get("pending") or {})
    pending[tok] = item
    await state.update_data(pending=pending)
    return tok


async def _session_add(state: FSMContext, key: str, name: str, kind: str | None) -> None:
    if await state.get_state() != Imp.file.state:
        return
    data = await state.get_data()
    await state.update_data(**{key: list(data.get(key) or []) + [[name, kind]]})


async def _resolve_pending(cb: CallbackQuery, state: FSMContext, tok: str, kind: str | None) -> None:
    """Tasdiq kutayotgan fayl: kind — qaysi tur sifatida yuklanadi; None — o'tkazib yuboriladi."""
    async with _import_locks.setdefault(cb.from_user.id, asyncio.Lock()):
        data = await state.get_data()
        pending = dict(data.get("pending") or {})
        item = pending.pop(tok, None)
        if not item:
            await cb.answer("Bu amal eskirgan. Faylni /import bilan qaytadan yuboring.", show_alert=True)
            return
        await state.update_data(pending=pending)
        await cb.answer()
        if kind is None:
            shutil.rmtree(item["tmpdir"], ignore_errors=True)
            await cb.message.edit_text(f"⏭ {item['n']}-fayl «{esc(item['file_name'])}» o'tkazib yuborildi.")
            await _session_add(state, "skipped", item["file_name"], None)
            return
        try:
            rows = await asyncio.to_thread(load_rows, item["path"])
        finally:
            shutil.rmtree(item["tmpdir"], ignore_errors=True)
        await cb.message.edit_text(f"⏳ {item['n']}-fayl «{esc(item['file_name'])}» — <b>{KIND_TITLES[kind]}</b> sifatida "
                                   "yuklanmoqda…")
        ok = await _process_import(cb.bot, cb.message, kind, rows, item["caption"], item["file_name"], n=item["n"],
                                 user_id=cb.from_user.id)
        await _session_add(state, "done" if ok else "skipped", item["file_name"], kind)


@router.callback_query(ImpOkCb.filter())
async def cb_import_confirm(cb: CallbackQuery, callback_data: ImpOkCb, state: FSMContext) -> None:
    item = ((await state.get_data()).get("pending") or {}).get(callback_data.tok)
    if callback_data.act == "cancel" or not item:
        await _resolve_pending(cb, state, callback_data.tok, None)
        return
    await _resolve_pending(cb, state, callback_data.tok, item["det"] if callback_data.act == "switch" else item["kind"])


@router.callback_query(ImpPickCb.filter())
async def cb_import_pick(cb: CallbackQuery, callback_data: ImpPickCb, state: FSMContext) -> None:
    await _resolve_pending(cb, state, callback_data.tok, None if callback_data.kind == "skip" else callback_data.kind)


@router.message(Command("tayyor"))
async def cmd_import_done(message: Message, state: FSMContext) -> None:
    if await state.get_state() != Imp.file.state:
        await message.answer("Ochiq import yo'q. Fayl yuklash uchun: /import")
        return
    await _finish_session(message, state)


async def _finish_session(message: Message, state: FSMContext, note: str = "") -> None:
    """Import sessiyasi xulosasi: nechta fayl, qaysi turlar, o'tkazib yuborilganlar, javob kutayotganlar."""
    data = await state.get_data()
    await state.clear()
    done, skipped, pending = data.get("done") or [], data.get("skipped") or [], data.get("pending") or {}
    for item in pending.values():
        shutil.rmtree(item["tmpdir"], ignore_errors=True)
    by_kind: dict[str, int] = {}
    for _, kind in done:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    lines = ([note, ""] if note else []) + [f"✅ <b>Import yakunlandi</b>: {len(done)} ta fayl yuklandi"]
    lines += [f"   • {KIND_TITLES.get(k, k)}: {v} ta" for k, v in by_kind.items()]
    if skipped:
        lines.append(f"⏭ O'tkazib yuborildi yoki xato: {len(skipped)} ta — " + esc(", ".join(x[0] for x in skipped)))
    if pending:
        lines.append(f"⚠️ Javob berilmagani uchun yuklanmadi: {len(pending)} ta — "
                     + esc(", ".join(x["file_name"] for x in pending.values())) + ". Kerak bo'lsa, /import bilan qayta yuboring.")
    await message.answer("\n".join(lines))


# Guruhga bog'lanmagan import turlari: tarjimalar (umumiy) va tanlov/2-til jadvali (fan va oqim bo'yicha)
UNSCOPED_KINDS = {"translations", "elsched"}


async def _scope_rows(rows: list[dict], scope: set[str]) -> tuple[list[dict], int]:
    """Faqat kurs koordinatorining guruhlariga tegishli qatorlar: guruh ustuni bo'lsa — guruh bo'yicha, bo'lmasa
    (masalan, buxgalteriya hisoboti) — talaba shu guruhlarda bormi (HEMIS ID yoki F.I.Sh. bo'yicha).
    Qaytaradi: (qolgan qatorlar, o'tkazib yuborilganlar soni)."""
    own = await db.all_students_brief(scope)
    hemis = {normalize_text(r["hemis_id"]).replace(" ", "") for r in own}
    names = {r["name_norm"] for r in own}
    kept = []
    for r in rows:
        g = r.get("group_name")
        if g:
            mine = group_key(g) in scope
        else:
            h = normalize_text(r.get("hemis_id") or "").replace(" ", "")
            mine = (h and h in hemis) or normalize_text(r.get("full_name") or "") in names
        if mine:
            kept.append(r)
    return kept, len(rows) - len(kept)


async def _process_import(bot, progress: Message, kind: str, rows: list, caption: str, file_name: str,
                          n: int | None = None, user_id: int | None = None) -> bool:
    """Yuklangan fayl — «yuklangan fayllar» ro'yxatiga yoziladi; undan kelgan ma'lumot, bildirishnoma va xabarlar
    shu yozuvga bog'lanadi (keyin faylni o'chirish mumkin)."""
    import imports
    from tenancy import current_import
    imp_id = await imports.start(kind, file_name, user_id)
    token = current_import.set(imp_id)
    ok = False
    try:
        ok = await _process_import_body(bot, progress, kind, rows, caption, file_name, n, user_id)
    finally:
        current_import.reset(token)
        await imports.finish(imp_id, ok)
    return ok


async def _process_import_body(bot, progress: Message, kind: str, rows: list, caption: str, file_name: str,
                               n: int | None = None, user_id: int | None = None) -> bool:
    silent = "jim" in caption.lower()
    # Kurs koordinatoriga guruhlar biriktirilgan bo'lsa — faylda faqat uning guruhlari talabalari tanilinadi
    scope = group_scope(user_id) if kind not in UNSCOPED_KINDS else None
    tag = f"{n}-fayl «{esc(file_name)}» — " if n else ""
    try:
        result = await asyncio.to_thread(parse_rows, rows, kind)
    except Exception as e:
        log.exception("Import xatosi: %s, «%s»", KIND_TITLES.get(kind, kind), file_name)
        await progress.edit_text(f"❌ {tag}faylni o'qib bo'lmadi: {esc(e)}")
        return False

    if result.fatal:
        log.warning("Import: fayl formati mos emas — %s, «%s»: %s", KIND_TITLES.get(kind, kind), file_name, result.fatal)
        await progress.edit_text(f"❌ {tag}{esc(result.fatal)}")
        return False

    lines = [f"✅ {tag}<b>{KIND_TITLES.get(result.kind, KIND_TITLES[kind])}</b> importi yakunlandi"]
    stats_subj = (stats_subject(rows, file_name) if result.kind == "attendance_stats" else None)
    lines += [esc(n) for n in result.notes]
    errors = list(result.errors)
    pf = result.meta.get("payment_forms") if isinstance(result.meta, dict) else None
    if scope is not None:
        total = len(result.rows)
        result.rows, outside = await _scope_rows(result.rows, scope)
        if pf:
            pf, _ = await _scope_rows(pf, scope)
        real = await db.group_counts()  # qo'lda yozilgan nom o'rniga bazadagi asl yozuvi
        names = sorted((real[k]["name"] if k in real else v for k, v in coordinator_groups(user_id).items()), key=str.lower)
        lines.append(f"👥 Faqat sizning guruhlaringiz ({esc(', '.join(names))}) bo'yicha: {total - outside} ta qator"
                     + (f"; boshqa guruhlarga tegishli {outside} ta qator o'tkazib yuborildi" if outside else ""))
        if total and not result.rows:
            lines.append("⚠️ Faylda guruhlaringizga tegishli talaba topilmadi — hech narsa saqlanmadi. Guruhlar "
                         "noto'g'ri biriktirilgan bo'lsa, super-adminga murojaat qiling.")

    if kind in ("students", "phones"):
        cols = result.columns
        lines.append("Tanilgan ustunlar: " + ", ".join(
            f"{COLUMN_ROLES[f]} ← «{esc(h)}»" for f, h in cols.items() if f in COLUMN_ROLES))

    if kind == "students":
        # boshqa kursda ro'yxatdan o'tgan yoki farzandi topilmay kutib turgan ota-onalar — shu kursga ham
        adopted = await adopt_parents({p for r in result.rows for p in (r.get("phones") or [])})
        ins, upd, new_links = await db.upsert_students(result.rows)
        if adopted:
            lines.append(f"Botda avval ro'yxatdan o'tgan ota-onalar topildi: {adopted}")
        lines.append(f"Yangi talabalar: {ins}, yangilangan: {upd}")
        self_n = sum(bool(r.get("student_phones")) for r in result.rows)
        if self_n:
            lines.append(f"Talabaning o'z raqami yozilganlar: {self_n}")
        lines += await _after_phone_import(bot)
        new_links = [(pid, sid) for pid, sid in new_links if not await db.is_blocked(pid)]
        if new_links:
            n = 0 if silent else await notify_links(bot, new_links)
            lines.append(f"Avtomatik bog'langan ota-onalar: {len(new_links)} (xabar yuborildi: {n})")

    elif kind == "phones":
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        n = await db.set_self_phones(rows)
        lines.append(f"Talabalarning o'z raqamlari yangilandi: {n} ta talaba "
                     f"({sum(len(r['student_phones']) for r in rows)} ta raqam)")
        lines += await _after_phone_import(bot)

    elif kind == "attendance" and result.kind == "attendance_stats" and stats_subj:
        # HEMIS statistikasi BITTA FAN bo'yicha — fanlar kesimiga yoziladi, umumiy davomatga tegilmaydi
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        as_of = _stats_date(caption, file_name)
        before = {r["student_id"]: await absence.summary(r["student_id"]) for r in rows}
        changes = await db.upsert_subject_stats(rows, stats_subj, as_of)
        after = {sid: await absence.summary(sid) for sid in before}
        k = HEMIS_STATS_HOURS_PER_UNIT
        unexc = lambda r: max((r["absent"] or 0) - (r["excused"] or 0), 0)  # noqa: E731
        grew = [(sid, prev, new) for sid, prev, new in changes if prev and unexc(new) > unexc(prev) or not prev and unexc(new) > 0]
        n_subj = (await db.fetchone("SELECT COUNT(DISTINCT subject_key) n FROM subject_att_stats"))["n"]
        lines.append(f"📚 Fan: <b>{esc(stats_subject_title(stats_subj))}</b> — fanlar kesimiga yozildi va umumiy davomatga "
                     f"qo'shildi (umumiy davomat — yuklangan {n_subj} ta fan bo'yicha yig'indi)")
        lines.append(f"Talabalar: {len(rows)}, holat sanasi: {fmt_date(as_of, False)}; sababsiz qoldirganlar: "
                     f"{sum(1 for r in rows if unexc(r) > 0)} ta talaba")
        if silent:
            lines.append("🔕 Jim rejim: ota-onalarga xabar yuborilmadi.")
        else:
            if grew:
                from notifier import notify_subject_stats
                lines.append(f"Ota-onalarga xabar (fan bo'yicha yangi sababsiz qoldirish): "
                             f"{await notify_subject_stats(bot, stats_subj, grew, k)}")
            sl_sent, overs = await check_subject_limits(bot, set(before))
            lines += _subject_limit_lines(overs, sl_sent)
            warned, crossings = await check_thresholds(bot, set(before))  # umumiy chegaralar (18/36/54/74)
            if warned:
                lines.append(f"Chegara bo'yicha ogohlantirishlar: {warned}")
            lines += _crossings_lines(crossings)
        lines += await _levels_overview(set(before))
        dec_sent, drops = await notify_absence_decrease(bot, before, after, notify=not silent)
        lines += _drops_lines(drops, dec_sent, silent)

    elif kind == "attendance" and result.kind == "attendance_stats":
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        as_of = _stats_date(caption, file_name)
        before = {r["student_id"]: await absence.summary(r["student_id"]) for r in rows}
        changes = await db.upsert_att_stats(rows, as_of)
        after = {sid: await absence.summary(sid) for sid in before}
        sids = {sid for sid, _, _ in changes}
        lines.append(f"Talabalar: {len(rows)}, holat sanasi: {fmt_date(as_of, False)} "
                     + (f"(fayldagi sonlar — para, 1 para = {fmt_num(HEMIS_STATS_HOURS_PER_UNIT)} soat)"
                        if HEMIS_STATS_HOURS_PER_UNIT == HOURS_PER_PAIR else
                        f"(1 birlik = {fmt_num(HEMIS_STATS_HOURS_PER_UNIT)} soat)"))
        if rows and len(rows) >= 10:
            floor = min(r["absent"] for r in rows)
            if floor > 0:
                lines.append(f"ℹ️ Fayldagi <b>barcha</b> talabalarda kamida {fmt_pairs(floor * HEMIS_STATS_HOURS_PER_UNIT)} «qatnashmagan» bor. "
                             "Yo'qlama qilinmagan darslar hammaga «qatnashmagan» deb yozilgan bo'lishi mumkin — "
                             "bir-ikki talabani HEMIS'da tekshirib ko'ring.")
        lines += await _levels_overview(sids)
        if silent:
            lines.append("🔕 Jim rejim: ota-onalarga xabar yuborilmadi (chegara xabarlari keyingi importda ketadi).")
        else:
            warned, crossings = await check_thresholds(bot, sids)
            upd_msgs = await notify_stats_changes(bot, changes, {c["sid"] for c in crossings})
            lines.append(f"Ota-onalarga xabarlar: chegara bo'yicha {warned}, yangilanish bo'yicha {upd_msgs}")
            lines += _crossings_lines(crossings)
        dec_sent, drops = await notify_absence_decrease(bot, before, after, notify=not silent)
        lines += _drops_lines(drops, dec_sent, silent)

    elif kind == "attendance":
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        cutoff = (today() - timedelta(days=NOTIFY_MAX_AGE_DAYS)).isoformat()
        # real vaqtdagi manba (Manage integratsiyasi): «darsga keldi» belgilari ham ota-ona ilovasiga boradi;
        # Excel fayldagi yuzlab «keldi» qatorlari esa xabarsiz yoziladi
        realtime = "integ" in caption.lower().split()
        tuples = [
            (r["student_id"], r["date"], r["pair"], r["subject"], r["lesson_type"], r["teacher"], r["status"],
             r["hours"], 1 if (silent or r["date"] < cutoff or (r["status"] == "keldi" and not realtime)) else 0)
            for r in rows
        ]
        before = {sid: await absence.summary(sid) for sid in {r["student_id"] for r in rows}}
        affected = await db.upsert_attendance(tuples)
        after = {sid: await absence.summary(sid) for sid in before}
        absences = sum(r["status"] != "keldi" for r in rows)
        lines.append(f"Yozuvlar: {len(rows)} (shundan qoldirilgan/kechikkan: {absences}), talabalar: {len(affected)}")
        if rows:
            dates = sorted({r["date"] for r in rows})
            lines.append(f"Davr: {fmt_date(dates[0], False)} — {fmt_date(dates[-1], False)}")
        if silent:
            lines.append("🔕 Jim rejim: ota-onalarga xabar yuborilmadi.")
        else:
            sent = await notify_new_absences(bot)
            if realtime:
                sent += await notify_present_marks(bot)
            sl_sent, overs = await check_subject_limits(bot, affected)
            lines += _subject_limit_lines(overs, sl_sent)
            warned, crossings = await check_thresholds(bot, affected)
            lines.append(f"Darhol xabarlar: {sent}, ogohlantirishlar: {warned}")
            lines += _crossings_lines(crossings)
        dec_sent, drops = await notify_absence_decrease(bot, before, after, notify=not silent)
        lines += _drops_lines(drops, dec_sent, silent)

    elif kind == "schedule":
        n, groups = await db.replace_schedule(result.rows)
        lines.append(f"Darslar: {n}, guruhlar: {groups} (bu guruhlarning eski jadvali almashtirildi)")
        subs = sum(1 for r in result.rows if r.get("subgroup"))
        if subs:
            lines.append(f"Kichik guruhga tegishli darslar: {subs}")
        lines += _code_credit_lines(result.rows)

    elif kind == "elsched":
        n, subjects = await db.replace_elective_schedule(result.rows)
        streams = {}
        for r in result.rows:
            streams.setdefault(r["subject"], set()).add(r.get("stream") or "")
        lines.append(f"Darslar: {n}, fanlar: {len(subjects)} (fayldagi fanlarning eski darslari almashtirildi)")
        lines += _code_credit_lines(result.rows)
        lines.append("Fanlar: " + ", ".join(
            esc(sj) + (f" ({len([x for x in streams[sj] if x])} oqim)" if any(streams[sj]) else "") for sj in subjects))
        lines.append("Bu darslar guruhga bog'lanmagan: ular faqat shu fanga biriktirilgan talabalarning shaxsiy "
                     "jadvalida ko'rinadi.")
        idle = await individual.unassigned_subjects(result.rows)
        if idle:
            lines.append("⚠️ Hali hech bir talaba biriktirilmagan fanlar (ular hech kimga ko'rinmaydi — «🎯 Tanlov/2-til: "
                         "kim o'qiydi» faylini yuklang): " + esc(", ".join(idle)))

    elif kind == "enroll":
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        n_st, n_pairs = await db.replace_enrollment(rows)
        lines.append(f"Talabalar: {n_st}, shaxsiy fanlar (tanlov, 2-til): {n_pairs} ta yozuv")
        per_subject: dict[str, int] = {}
        for r in rows:
            per_subject[r["subject"]] = per_subject.get(r["subject"], 0) + 1
        if per_subject:
            lines.append("Fanlar bo'yicha: " + ", ".join(f"{esc(k)} — {v}" for k, v in sorted(per_subject.items())))
        miss = await individual.unmatched_subjects(rows)
        if miss:
            lines.append("⚠️ Jadvallarda (guruh jadvali yoki «Tanlov/2-til: jadval») darsi topilmagan fanlar — nomi "
                         "farq qilishi yoki jadval hali yuklanmagan bo'lishi mumkin: " + esc(", ".join(miss)))

    elif kind == "grades":
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        errors += unknown
        for r in rows:
            r.pop("_row", None)
        clean = [{**{k: r[k] for k in ("student_id", "subject", "control_type", "score", "max_score", "date", "semester")},
                  "credits": r.get("credits")} for r in rows]
        affected = {r["student_id"] for r in clean}
        before = {sid: academic_keys((await academic.summary(sid))["results"]) for sid in affected}
        changed = await db.upsert_grades(clean)
        after = {sid: academic_keys((await academic.summary(sid))["results"]) for sid in affected}
        lines.append(f"Baholar: {len(clean)}, yangi yoki o'zgargan: {len(changed)}")
        if changed and not silent:
            lines.append(f"Ota-onalarga xabar: {await notify_grades(bot, changed)}")
            alerts = await notify_academic(bot, before, after)
            if alerts:
                lines.append(f"⚠️ Akademik qarz bo'yicha xabarlar (yangi qarz yoki yopilgan qarz): {alerts}")
        n_st = n_subj = 0
        for sid in {r["student_id"] for r in clean}:
            d = (await academic.summary(sid))["debts"]
            if d:
                n_st, n_subj = n_st + 1, n_subj + len(d)
        lines.append(f"📚 Akademik qarzdorlar (qarzdorlar ro'yxati bo'yicha): {n_st} ta talaba, {n_subj} ta fan"
                     + (" — ro'yxat: /akademik" if n_st else ""))

    elif kind == "acad_debts":  # HEMIS «Akadem qarzdorlar»: talaba necha marta kelsa — shuncha qarzdor fan
        from notifier import hemis_debt_keys, notify_acad_list
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        missing = sorted({u.split("(")[-1].rstrip(")") for u in unknown if "(" in u})
        if not rows:
            lines.append("❌ Fayldagi talabalarning birortasi ham bu kurs bazasida topilmadi — ro'yxat saqlanmadi. "
                         "Fayl boshqa kursga tegishli emasligini va «Talabalar» fayli yuklanganini tekshiring.")
        else:
            groups = {group_key(r["group_name"]) for r in result.rows if r.get("group_name")}
            if scope is not None:  # koordinator — faqat o'z guruhlarining ro'yxati almashtiriladi
                groups = (groups & scope) or set(scope)
            everyone = await db.fetchall("SELECT id, group_key FROM students")
            in_scope = {x["id"] for x in everyone if not groups or x["group_key"] in groups}
            before = {sid: hemis_debt_keys(v) for sid, v in (await db.bulk_academic_debts()).items() if sid in in_scope}
            clean = [{"student_id": r["student_id"], "subject": r["subject"], "semester": r["semester"],
                      "credits": r["credits"], "year": r.get("year")} for r in rows]
            await db.replace_academic_debts(clean, in_scope if groups else None)
            after = {sid: hemis_debt_keys(v) for sid, v in (await db.bulk_academic_debts()).items() if sid in in_scope}
            n_new = sum(len([k for k in a if k not in before.get(sid, {})]) for sid, a in after.items())
            n_closed = sum(len([k for k in b if k not in after.get(sid, {})]) for sid, b in before.items())
            lines.append(f"📚 HEMIS akademik qarzdorlar ro'yxati: {len(after)} ta talaba, "
                         f"{sum(len(a) for a in after.values())} ta qarzdor fan")
            if groups:
                lines.append(f"Guruhlar: {len(groups)} ta (boshqa guruhlarning ro'yxatiga tegilmadi)")
            lines.append(f"Yangi qarzdor fanlar: {n_new}, yopilgan (ro'yxatdan chiqqan): {n_closed}")
            if not silent and (n_new or n_closed):
                lines.append(f"Ota-onalarga xabar: {await notify_acad_list(bot, before, after)}")
        if missing:
            lines.append(f"⚠️ Bazada topilmagan talabalar: {len(missing)} ta — "
                         + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else "")
                         + ". «Talabalar» (kontingent) faylini yangilang.")
        unknown = []

    elif kind == "gpa":  # HEMIS «Performance GPA» — rasmiy GPA (baholardan hisoblanmaydi)
        from config import GPA_MIN
        rows, unknown = resolve_students(result.rows, await db.student_lookup(scope))
        missing = sorted({u.split("(")[-1].rstrip(")") for u in unknown if "(" in u})
        if not rows:
            lines.append("❌ Fayldagi talabalarning birortasi ham bu kurs bazasida topilmadi — GPA saqlanmadi. "
                         "Fayl boshqa kursga tegishli emasligini va «Talabalar» fayli yuklanganini tekshiring.")
        else:
            clean = [{k: r.get(k) for k in ("student_id", "gpa", "subjects", "credits", "debts", "method", "year",
                                            "changed_at")} for r in rows]
            await db.add_gpa(clean)
            low = [r for r in clean if round(r["gpa"], 9) < GPA_MIN]
            lines.append(f"🎓 GPA (HEMIS): {len(clean)} ta talaba, o'rtacha {sum(r['gpa'] for r in clean) / len(clean):.2f}")
            lines.append(f"GPA {str(GPA_MIN).replace('.', ',')} dan past (kursdan o'tmaydi): {len(low)} ta talaba")
        if missing:
            lines.append(f"⚠️ Bazada topilmagan talabalar: {len(missing)} ta — "
                         + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else "")
                         + ". «Talabalar» (kontingent) faylini yangilang.")
        unknown = []

    elif kind in ("debts", "debts_t"):
        pay_kind = "trimestr" if kind == "debts_t" else "kontrakt"
        rows, unknown = resolve_by_name(result.rows, await db.all_students_brief(scope))
        errors += unknown
        cap_dates = parse_user_dates(caption or "")
        as_of = (cap_dates[0].isoformat() if cap_dates else result.meta.get("as_of")
                 or _stats_date(None, file_name))
        year = result.meta.get("year")
        changes = await db.upsert_payments(rows, as_of, year, pay_kind)
        # hisobot qamrovi: unda yo'q (qamrovdagi) talabalarning qarzdorligi — «mavjud emas»
        await db.add_payment_report(pay_kind, as_of, scope)
        # To'lov shakli faqat yillik kontrakt hisobotidan: trimestr (qayta o'qish) to'lovini grant talaba ham to'laydi
        to_contract = ({r["student_id"]: CONTRACT for r in rows if (r.get("contract") or 0) > 0}
                       if pay_kind == "kontrakt" else {})
        switched = []
        for sid in to_contract:
            st0 = await db.get_student(sid)
            if st0 and st0.get("payment_form") == GRANT:
                switched.append(st0["full_name"])
        await db.set_payment_forms(to_contract)
        debtors = sorted((r for r in rows if r["debt"] > 0), key=lambda r: -r["debt"])
        lines.append(f"Talabalar: {len(rows)}, holat sanasi: {fmt_date(as_of, False)}"
                     + (f", {esc(year)} o'quv yili" if year else ""))
        lines.append(f"Qarzdorlar: {len(debtors)}, jami qarz: <b>{fmt_money(sum(r['debt'] for r in debtors))}</b>"
                     + (f"; qarzdorligi mavjud emas: {len(rows) - len(debtors)}" if len(rows) > len(debtors) else ""))
        lines.append("ℹ️ Ro'yxatda bo'lmagan talabalar" + (" (guruhlaringizda)" if scope is not None else "")
                     + " — qarzdorlik mavjud emas deb ko'rsatiladi (avval qarzi bo'lganlar ham).")
        if debtors:
            lines.append("\n💰 <b>Eng katta qarzlar:</b>")
            for r in debtors[:10]:
                st = await db.get_student(r["student_id"])
                pct = f" ({r['percent']:g}%)" if r.get("percent") is not None else ""
                lines.append(f"   • {esc(st['full_name'])} · {esc(st.get('group_name') or '—')} — "
                             f"{fmt_money(r['debt'])}{pct}")
            lines.append(f"To'liq ro'yxat: /qarzdorlar {pay_kind}")
        if switched:
            lines.append(f"⚠️ Oldin «Davlat granti» deb yozilgan, lekin hisobotda kontrakt summasi bor — to'lov shakli "
                         f"«To'lov-shartnoma» ga o'zgartirildi: {len(switched)} ta ({esc(', '.join(switched[:5]))}"
                         + (", …" if len(switched) > 5 else "") + "). Tekshirib ko'ring.")
        lines.append("ℹ️ JSHSHIR botda saqlanmaydi — talabalar F.I.Sh. bo'yicha topildi.")
        if silent:
            lines.append("🔕 Jim rejim: ota-onalarga xabar yuborilmadi.")
        else:
            lines.append(f"Ota-onalarga xabar: {await notify_payments(bot, changes)}")

    if pf:  # «O'rtacha ball» jadvalidagi «To'lov shakli» ustuni
        ok_pf, _ = resolve_students(pf, await db.student_lookup(scope))
        forms = {r["student_id"]: r["payment_form"] for r in ok_pf}
        await db.set_payment_forms(forms)
        n_g = sum(1 for f in forms.values() if f == GRANT)
        lines.append(f"To'lov shakli yangilandi: {len(forms)} ta talaba (davlat granti: {n_g}, "
                     f"to'lov-shartnoma: {sum(1 for f in forms.values() if f == CONTRACT)})")

    if kind == "translations":
        rows = [{"term_key": loc.term_key(r["uz"]), "uz": loc._split(r["uz"])[0], "ru": r["ru"], "en": r["en"]}
                for r in result.rows if r.get("ru") or r.get("en")]
        await central.upsert_terms(rows)
        await loc.reload()
        left = [t for t in await termsheet.collect() if t["state"] == "TARJIMA KERAK"]
        lines.append(f"Saqlandi: {len(rows)} ta nom (ruscha: {sum(bool(r['ru']) for r in rows)}, inglizcha: "
                     f"{sum(bool(r['en']) for r in rows)}). Tarjimalar barcha kurslarda darhol ishlaydi.")
        lines.append("Kursingizda tarjimasi yo'q nomlar qolmadi ✅" if not left else
                     f"Kursingizda hali tarjimasi yo'q nomlar: {len(left)} ta — /tarjimalar")
    elif result.rows and kind in ("students", "grades", "schedule", "elsched", "enroll", "attendance"):
        miss = termsheet.missing([r.get(f) for r in result.rows for f in ("subject", "faculty", "control_type", "room")])
        if miss:
            lines.append(f"\n🌐 Rus tiliga tarjimasi yo'q nomlar: {len(miss)} ta ({esc(', '.join(miss[:5]))}"
                         + (", …" if len(miss) > 5 else "") + "). Hozircha rus tilidagi ota-onalarga kirill harflarida "
                         "ko'rinadi — /tarjimalar orqali to'ldiring.")

    upd_key = {"debts": "debts_k"}.get(kind, result.kind if result.kind == "attendance_stats" else kind)
    if result.rows:  # «oxirgi yangilanish» — ota-onaga har bir bo'limda ko'rsatiladi
        await db.set_setting(f"updated:{upd_key}", now_iso())

    if result.skipped:
        lines.append(f"Namuna qatorlari o'tkazib yuborildi: {result.skipped}")
    missing = [e for e in errors if "bazada topilmadi" in e]
    if missing:  # bitta umumiy qator: odatda bu talabalar hali kontingent orqali yuklanmagan
        errors = [e for e in errors if "bazada topilmadi" not in e]
        miss_refs = list(dict.fromkeys(e.split("(")[-1].rstrip(")") for e in missing))
        total = len({(normalize_text(r.get("hemis_id") or ""), normalize_text(r.get("full_name") or ""))
                     for r in result.rows}) or len(miss_refs)
        lines.append(f"\n⚠️ <b>{total} talabadan {len(miss_refs)} tasi bazadan topilmadi</b> "
                     f"(masalan: {esc(', '.join(miss_refs[:5]))}). Ular hali «Talabalar» fayli orqali yuklanmagan — "
                     "kontingentni yangilab, faylni qayta yuboring.")
    if errors:
        lines.append(f"\n⚠️ Xatoli qatorlar: {len(errors)}")
        lines.extend(esc(e) for e in errors[:15])
        if len(errors) > 15:
            lines.append(f"… va yana {len(errors) - 15} ta")
    if result.rows and kind not in ("translations", "schedule", "elsched"):
        # har bir yuklash — dinamika uchun yangi nuqta (faqat o'zgargan ko'rsatkichlar yoziladi)
        import snapshots
        try:
            await snapshots.capture()
        except Exception:
            log.exception("Dinamika nuqtalari yozilmadi")
    if user_id is not None and kind in ("attendance", "schedule"):
        import integration
        if integration.active(kind):
            lines.append(f"\nℹ️ {esc(KIND_TITLES[kind])} {esc(integration.INTEGRATION_NAME)} tizimidan avtomatik olinadi — "
                         "qo'lda yuklangan ma'lumot keyingi yangilanishda manbadagi bilan almashtirilishi mumkin.")
    parts = split_message("\n".join(lines))
    await progress.edit_text(parts[0])
    for extra in parts[1:]:
        await progress.answer(extra)
    return True


def _code_credit_lines(rows: list[dict]) -> list[str]:
    """Jadvaldagi fan kodlaridan aniqlangan kreditlar (fan bo'yicha sababsiz qoldirish chegarasi shundan)."""
    found: dict[str, int] = {}
    for r in rows:
        c = credits_from_code(r.get("code"))
        if c:
            found.setdefault(r["subject"], c)
    if not found:
        return []
    return [f"Fan kreditlari fan kodidan aniqlandi ({len(found)} ta fan): " + ", ".join(
        f"{esc(s)} — {c} kr. (chegara {limit_pairs(c)} para)" for s, c in sorted(found.items()))]


async def apply_subject_stats(bot, rows: list[dict], silent: bool = False, as_of: str | None = None,
                              source: str = "") -> list[str]:
    """Talaba × fan qatorlari (student_id, subject, credits, code, attended, absent, excused — para) — Manage'dan
    (student-subjects): kreditlar yoziladi, davomat fanlar kesimiga va umumiy davomatga qo'shiladi, sababsiz qoldirish
    ko'paygan bo'lsa ota-onaga xabar, so'ng 25% chegarasi va umumiy chegaralar tekshiriladi. Natija — hisobot qatorlari."""
    as_of = as_of or today().isoformat()
    k = HEMIS_STATS_HOURS_PER_UNIT
    lines = [f"✅ <b>Fanlar</b> ({esc(source or 'integratsiya')}) — {fmt_date(as_of, False)} holatiga"]
    creds: dict[str, dict[str, tuple]] = {"manage": {}, "code": {}}
    for r in rows:
        if r.get("credits"):
            creds["manage" if r.get("credits_src") == "manage" else "code"].setdefault(
                subject_key(r["subject"]) or normalize_text(r["subject"]), (r["subject"], r["credits"], r.get("code")))
    for src, found in creds.items():
        await db.upsert_subject_credits(found, source=src)
    creds = {**creds["code"], **creds["manage"]}
    pairs: dict[str, tuple] = {}
    for r in rows:
        if r.get("planned"):
            pairs.setdefault(subject_key(r["subject"]) or normalize_text(r["subject"]), (r["subject"], r["planned"], r.get("held_n")))
    if pairs:
        await db.set_subject_pairs(pairs)
        from subject_limits import limit_from_pairs
        lines.append(f"Fanlarga ajratilgan darslar ({len(pairs)} ta fan) va sababsiz qoldirish chegarasi (25%): " + ", ".join(
            f"{esc(s)} — {fmt_num(p)} para → {limit_from_pairs(p)} para" + (f" (o'tildi: {fmt_num(h)})" if h is not None else "")
            for s, p, h in sorted(pairs.values())[:20]) + (" …" if len(pairs) > 20 else ""))
    if creds:
        lines.append(f"Fan kreditlari: {len(creds)} ta fan — " + ", ".join(
            f"{esc(s)} {fmt_num(c)} kr. ({limit_pairs(c)} para)" for s, c, _ in sorted(creds.values())[:20])
            + (" …" if len(creds) > 20 else ""))
    stats = [r for r in rows if r.get("absent") is not None]
    if not stats:
        return lines
    by_subj: dict[str, list[dict]] = {}
    for r in stats:
        by_subj.setdefault(subject_key(r["subject"]) or normalize_text(r["subject"]), []).append(r)
    sids = {r["student_id"] for r in stats}
    before = {sid: await absence.summary(sid) for sid in sids}
    unexc = lambda r: max((r["absent"] or 0) - (r["excused"] or 0), 0)  # noqa: E731
    from notifier import notify_subject_stats
    sent = grew_n = 0
    for key, rs in by_subj.items():
        subject = rs[0]["subject"]
        # oldingi holat — shu fan bo'yicha oxirgi yozuv (shu kungisi ham): kun davomida qayta olinganda xabar takrorlanmaydi
        prev = {x["student_id"]: x for x in await db.fetchall(
            """SELECT student_id, attended, absent, excused FROM subject_att_stats x WHERE subject_key = ?
               AND as_of = (SELECT MAX(as_of) FROM subject_att_stats y WHERE y.student_id = x.student_id
                            AND y.subject_key = x.subject_key)""", (key,))}
        await db.upsert_subject_stats(rs, subject, as_of)
        grew = [(r["student_id"], prev.get(r["student_id"]), r) for r in rs
                if unexc(r) > (unexc(prev[r["student_id"]]) if r["student_id"] in prev else 0)]
        grew_n += len(grew)
        if grew and not silent:
            sent += await notify_subject_stats(bot, subject, grew, k)
    after = {sid: await absence.summary(sid) for sid in sids}
    lines.append(f"Fan bo'yicha davomat: {len(by_subj)} ta fan, {len(sids)} ta talaba — fanlar kesimiga yozildi va umumiy "
                 f"davomatga qo'shildi; sababsiz qoldirishi ko'payganlar: {grew_n}")
    if silent:
        lines.append("🔕 Birinchi olish — ota-onalarga xabar yuborilmadi (eski qoldirishlar «yangi» bo'lib ketmasligi uchun).")
    else:
        if sent:
            lines.append(f"Ota-onalarga xabar (fan bo'yicha yangi sababsiz qoldirish): {sent}")
        sl_sent, overs = await check_subject_limits(bot, sids)
        lines += _subject_limit_lines(overs, sl_sent)
        warned, crossings = await check_thresholds(bot, sids)
        if warned:
            lines.append(f"Chegara bo'yicha ogohlantirishlar: {warned}")
        lines += _crossings_lines(crossings)
    dec_sent, drops = await notify_absence_decrease(bot, before, after, notify=not silent)
    lines += _drops_lines(drops, dec_sent, silent)
    import snapshots
    try:
        await snapshots.capture()
    except Exception:
        log.exception("Dinamika nuqtalari yozilmadi")
    return lines


def _subject_limit_lines(overs: list[dict], sent: int) -> list[str]:
    """Kurs koordinatoriga: fan bo'yicha chegaraga (auditoriya soatining 25%) yetgan talabalar."""
    if not overs:
        return [f"Fan bo'yicha ogohlantirishlar: {sent}"] if sent else []
    out = [f"\n⛔ <b>Fan bo'yicha chegaraga yetganlar</b> (yakuniy nazoratga kiritilmaydi): {len(overs)} ta"
           + (f", ota-onalarga xabar: {sent}" if sent else "")]
    out += [f"• {esc(o['name'])} ({esc(o['group'])}) — {esc(o['subject'])}: {o['unexcused']} / {o['limit']} para"
            for o in overs[:15]]
    if len(overs) > 15:
        out.append(f"… va yana {len(overs) - 15} ta")
    return out


def stats_subject_title(name: str) -> str:
    return " ".join(str(name).split())


def _stats_date(caption: str | None, file_name: str | None) -> str:
    """HEMIS statistikasi qaysi sana holatiga: izohdagi sana → fayl nomidagi sana → bugun."""
    t = today()
    dates = parse_user_dates(caption or "")
    if not dates:
        m = re.search(r"(\d{1,2})[._-](\d{1,2})[._-](20\d{2})", file_name or "")
        d = parse_date(f"{m.group(1)}.{m.group(2)}.{m.group(3)}") if m else None
        if not d:  # HEMIS: «…_2026-10-06_15-33-30.xlsx»
            m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", file_name or "")
            d = parse_date(f"{m.group(3)}.{m.group(2)}.{m.group(1)}") if m else None
        dates = [d] if d else []
    d = dates[0] if dates else t
    return min(d, t).isoformat()


async def _levels_overview(sids) -> list[str]:
    """Import natijasi uchun: talabalar qaysi chegarada turgani (eng yuqori yetilgan chegara bo'yicha)."""
    counts = [0] * len(absence.LEVELS)
    for sid in sids:
        sm = await absence.summary(sid)
        i = absence.level_index(sm["counted"]) if sm else -1
        if i >= 0:
            counts[i] += 1
    if not any(counts):
        return ["Chegaraga yetgan talaba yo'q."]
    return ["\n📏 <b>Chegaralar holati</b> (semestr boshidan):"] + [
        f"{absence.level_icon(i)} {fmt_pairs(lvl)} va undan ko'p — {esc(absence.action_for(i))}: {counts[i]} ta"
        for i, lvl in enumerate(absence.LEVELS) if counts[i]] + ["Batafsil ro'yxat: /chegaralar"]


def _drops_lines(drops: list[dict], sent: int, silent: bool, limit: int = 30) -> list[str]:
    """Sababsiz qoldirishlari kamaygan (masalan, sababli deb topilgan) va avval chegaraga yetgan talabalar."""
    if not drops:
        return []
    out = [f"\n⬇️ <b>Sababsiz qoldirishlari kamayganlar</b> (avval chegaraga yetgan): {len(drops)} ta"
           + ("" if silent else f", ota-onalarga xabar: {sent}")]
    for d in sorted(drops, key=lambda x: x["new_level"] - x["old_level"])[:limit]:
        change = (f"{esc(absence.action_for(d['old_level']))} → "
                  + (esc(absence.action_for(d["new_level"])) if d["new_level"] >= 0 else "chegaradan past")
                  if d["new_level"] != d["old_level"] else "chegara o'zgarmadi")
        out.append(f"   • {esc(d['name'])} · {esc(d['group'])} — {fmt_pairs(d['old'])} → {fmt_pairs(d['new'])} "
                   f"({change})")
    if len(drops) > limit:
        out.append(f"… va yana {len(drops) - limit} ta")
    return out


def _crossings_lines(crossings: list[dict], limit: int = 30) -> list[str]:
    """Yangi chegaraga yetgan talabalar — kurs koordinatorining ish ro'yxati."""
    if not crossings:
        return []
    out = ["\n🆕 <b>Yangi chegaraga yetganlar</b> (choralarni ko'rish uchun):"]
    shown = 0
    for i in range(len(absence.LEVELS) - 1, -1, -1):
        group = sorted((c for c in crossings if c["level"] == i), key=lambda c: -c["hours"])
        if not group:
            continue
        out.append(f"{absence.level_icon(i)} <b>{esc(absence.action_for(i))}</b> ({fmt_pairs(absence.LEVELS[i])} va undan ko'p): "
                   f"{len(group)} ta")
        for c in group:
            if shown >= limit:
                break
            out.append(f"   • {esc(c['name'])} · {esc(c['group'])} — {fmt_pairs(c['hours'])}")
            shown += 1
    if len(crossings) > shown:
        out.append(f"… va yana {len(crossings) - shown} ta — to'liq ro'yxat: /chegaralar")
    return out


COLUMN_ROLES = {"hemis_id": "ID", "full_name": "F.I.Sh", "group_name": "guruh",
                "student_phones": "talabaning o'z raqami", "phones": "ota-ona raqami",
                "phones_father": "otasining raqami", "phones_mother": "onasining raqami"}


async def _after_phone_import(bot) -> list[str]:
    """Raqamlar yangilangach: ziddiyatlarni ko'rsatish va ro'yxatdan o'tganlarni qayta tekshirish."""
    out = []
    n_conf, conf = await db.phone_conflicts()
    if n_conf:
        out.append(f"\n⚠️ {n_conf} ta raqam bir vaqtda talabaning o'z raqami va ota-ona raqami sifatida yozilgan "
                   "(bunday raqam egasi ota-ona sifatida kira olmaydi, faqat siz ruxsat bersangiz):")
        out += [f"  {fmt_phone(c['phone'])}: talaba {esc(c['student'])} / ota-onasi: {esc(c['child'])}" for c in conf]
    res = await recheck_parents(bot)
    if res["found"]:
        out.append(f"\n🚫 Ro'yxatdan o'tganlar orasidan talaba deb topilib bloklanganlar: {res['found']}"
                   + (" (batafsil: /bloklar)" if res["found"] > res["notified"] else ""))
    return out


@router.message(Imp.file, NOT_CMD)
async def on_import_wrong(message: Message) -> None:
    await message.answer("Iltimos, .xlsx faylni hujjat (document) sifatida yuboring yoki /bekor.")


@router.message(Command("shablon"))
async def cmd_templates(message: Message) -> None:
    items = await templates.catalog()  # asl, super-admin o'zgartirgan (joriy versiya) va qo'shgan shablonlar
    if not items:
        await message.answer("Shablonlar yo'q.")
        return
    for t in items:
        caption = f"📑 <b>{esc(t['title'])}</b>"
        if t["version"]:
            caption += f" · {t['version']}-versiya, {fmt_date(t['updated'][:10], False)}"
        if not t["kind"]:
            caption += "\n<i>Hujjat namunasi</i>"
        if t["description"]:
            caption += f"\n{esc(t['description'])}"
        await message.answer_document(FSInputFile(t["path"], filename=t["file_name"]), caption=caption[:1024])
    await message.answer("Asl shablonlarning ikkinchi varag'ida ustunlar bo'yicha ko'rsatma bor. NAMUNA bilan "
                         "boshlangan qatorlar import paytida o'tkazib yuboriladi. Shablonlarni super-admin yangilaydi.")


@router.message(Command("toldir"))
async def cmd_fill(message: Message, command: CommandObject) -> None:
    dates = parse_user_dates(command.args or "")
    if not dates:
        await message.answer("Foydalanish: /toldir <code>15.09.2026 21.09.2026</code>")
        return
    d1, d2 = min(dates[:2]), min(max(dates[:2]), today())
    n = await individual.fill_attended(d1, d2, HOURS_PER_PAIR)
    await message.answer(
        f"✅ {fmt_date(d1, False)} — {fmt_date(d2, False)}: shaxsiy jadvallar bo'yicha {n} ta dars «qatnashdi» deb "
        "belgilandi.\nOldin kiritilgan qoldirilgan darslar o'zgarmadi. Talaba o'qimaydigan tanlov fani va boshqa "
        "til darslari unga yozilmadi."
    )


# ---------------------------------------------------------------- statistika va qidiruv
@router.message(Command("stat"))
async def cmd_stat(message: Message) -> None:
    s = await db.stats(viewer_scope())
    debt_k, debt_t = scope_students(await db.debtors("kontrakt")), scope_students(await db.debtors("trimestr"))
    cover = f"{round(100 * s['students_linked'] / s['students'])}%" if s["students"] else "—"
    await message.answer(
        await _course_line_full() + "📊 <b>Statistika</b>\n\n"
        f"Talabalar: {s['students']} (ota-ona raqami bor: {s['students_with_phone']})\n"
        f"Ro'yxatdan o'tgan ota-onalar: {s['parents']} (faol: {s['parents_active']})\n"
        f"Kamida bitta ota-onasi ulangan talabalar: {s['students_linked']} ({cover})\n"
        f"Davomat yozuvlari: {s['attendance']}"
        + (f", oxirgi sana: {fmt_date(s['attendance_last'], False)}" if s["attendance_last"] else "") + "\n"
        f"Jadvali yuklangan guruhlar: {s['schedule_groups']}\n"
        f"Baholar: {s['grades']}\n"
        f"Kutilayotgan bog'lash so'rovlari: {s['pending_requests']}\n"
        f"Javobsiz savollar: {s['open_questions']}\n\n"
        f"🛡 O'z raqami kiritilgan talabalar: {s['students_self_phone']}\n"
        f"Talabalar Telegram guruhlari: {s['tg_groups']} (bot admin: {s['tg_groups_admin']}), "
        f"ulardagi ma'lum a'zolar: {s['tg_members']}\n"
        f"Talaba deb bloklanganlar: {s['blocked']}\n"
        f"📄 Yuborilgan rasmiy hujjatlar: {s['documents']}\n\n"
        f"💳 To'lov shakli: davlat granti — {s['grant']}, to'lov-shartnoma — {s['contract']}\n"
        f"💰 Kontrakt qarzdorlari: {len(debt_k)}, jami qarz: {fmt_money(sum(r['debt'] for r in debt_k))}\n"
        f"🗓 Trimestr qarzdorlari: {len(debt_t)}, jami qarz: {fmt_money(sum(r['debt'] for r in debt_t))}\n"
        "📚 Akademik qarzdorlar: /akademik\n\n📥 Hisobotni yuklab olish (Excel yoki PDF):",
        reply_markup=export_kb("all"),
    )


@router.message(Command("talaba"))
async def cmd_find_student(message: Message, command: CommandObject) -> None:
    q = normalize_text(command.args or "")
    if not q:
        await message.answer("Foydalanish: /talaba <code>familiya ism</code>")
        return
    scored = sorted(((name_score(q, s["name_norm"]), s) for s in await db.all_students_brief(viewer_scope())),
                    key=lambda x: -x[0])
    found = [s for sc, s in scored if sc >= 0.8][:10]
    if not found:
        await message.answer("Topilmadi.")
        return
    lines = []
    for s in found:
        n = await db.student_parent_count(s["id"])
        docs = len(await db.documents_for(s["id"]))
        subj = await db.enrollment_for(s["id"])
        full = await db.get_student(s["id"])
        pay_txt = ""
        pays = {k: await db.latest_payment(s["id"], k) for k in ("kontrakt", "trimestr")}
        if full.get("payment_form") or any(pays.values()):
            pay_txt = "\n   💳 " + esc(full.get("payment_form") or "to'lov shakli ko'rsatilmagan")
            for k, p in pays.items():
                if p:
                    pay_txt += (f" · {k}: " + (fmt_money(p["debt"]) if p["debt"] > 0 else "mavjud emas")
                                + f" ({fmt_date(p['as_of'], False)})")
        ac = await academic.summary(s["id"])
        if ac["results"]:
            pay_txt += ("\n   📚 akademik qarz: " + (f"{len(ac['debts'])} ta fan — " + ", ".join(
                esc(d["subject"]) for d in ac["debts"]) if ac["debts"] else "mavjud emas"))
        lines.append(f"• <b>{esc(s['full_name'])}</b> · {esc(s['group_name'] or '')} · ID {esc(s['hemis_id'])} · "
                     f"ulangan ota-onalar: {n}" + (f" · hujjatlar: {docs}" if docs else "")
                     + ("\n   🎯 " + ", ".join(esc(x["subject"]) + (f" ({x['subgroup']}-oqim)" if x["subgroup"] else "")
                                         for x in subj) if subj else "") + pay_txt)
    await message.answer("\n".join(lines))


LANG_HINT = ("🌐 Rus va ingliz tilini tanlagan ota-onalar uchun matnga alohida qatordan <code>---ru</code> va "
             "<code>---en</code> yozib, ruscha va inglizcha qismni qo'shing — har bir ota-ona o'z tilidagi qismni oladi. "
             "Ruscha qism bo'lmasa, o'zbekcha matn kirill harflarida boradi.")


# ---------------------------------------------------------------- «Foydali ma'lumot» matni
@router.message(Command("info"))
async def cmd_info(message: Message, state: FSMContext) -> None:
    await state.set_state(InfoEdit.text)
    await message.answer("«ℹ️ Foydali ma'lumot» bo'limining yangi matnini yuboring (formatlash saqlanadi).\n\n"
                         + LANG_HINT + "\n\nBekor qilish: /bekor")


@router.message(InfoEdit.text, F.text, NOT_CMD)
async def on_info_text(message: Message, state: FSMContext) -> None:
    await db.set_setting("info_text", message.html_text)
    await state.clear()
    await message.answer("✅ Matn yangilandi.")


# ---------------------------------------------------------------- e'lon yuborish
@router.message(Command("elon"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("📢 E'lon kimlarga yuborilsin?", reply_markup=broadcast_target_kb())


@router.callback_query(BcCb.filter(F.act == "all"))
async def cb_bc_all(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Bc.content)
    scope = viewer_scope()
    await state.update_data(target=sorted(scope) if scope else [])  # koordinator — faqat o'z guruhlariga
    await cb.message.edit_text(("👥 E'lon guruhlaringiz ota-onalariga boradi.\n\n" if scope else "")
                               + "E'lon matnini yuboring (rasm, hujjat yoki video bilan ham bo'lishi mumkin).\n\n" + LANG_HINT)
    await cb.answer()


@router.callback_query(BcCb.filter(F.act == "groups"))
async def cb_bc_groups(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Bc.groups)
    await cb.message.edit_text("Guruh nomlarini vergul bilan yozing, masalan: <code>IQ-21, IQ-22, XM-11</code>")
    await cb.answer()


@router.message(Bc.groups, F.text, NOT_CMD)
async def on_bc_groups(message: Message, state: FSMContext) -> None:
    keys = [group_key(g) for g in message.text.replace(";", ",").split(",") if group_key(g)]
    if not keys:
        await message.answer("Guruh nomlari tushunilmadi, qaytadan yozing.")
        return
    known = {r["group_key"] for r in await db.fetchall("SELECT DISTINCT group_key FROM students")}
    scope = viewer_scope()
    if scope is not None:  # boshqa koordinatorning guruhlari — ro'yxatdan chiqariladi
        known &= scope
    unknown = [g.strip() for g in message.text.replace(";", ",").split(",")
               if group_key(g) and group_key(g) not in known]
    keys = [k for k in keys if k in known]
    if not keys:
        await message.answer("Bu guruhlar bazada topilmadi" + (" yoki sizga biriktirilmagan" if scope is not None else "")
                             + ". Guruh nomlarini tekshirib, qaytadan yozing.")
        return
    count = len(await db.parent_ids_for_groups(keys))
    await state.update_data(target=keys)
    await state.set_state(Bc.content)
    warn = (f"⚠️ Bazada topilmadi{' yoki sizga biriktirilmagan' if scope is not None else ''}: "
            f"{esc(', '.join(unknown))}\n" if unknown else "")
    await message.answer(f"{warn}Tanlangan guruhlarda faol ota-onalar: {count}. Endi e'lon matnini yuboring.\n\n"
                         + LANG_HINT)


@router.message(Bc.content, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def on_bc_content(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    recipients = await db.parent_ids_for_groups(data.get("target") or None)
    html = message.html_text if (message.text or message.caption) else ""
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id, html=html,
                            has_text=bool(message.text), text=message.text or message.caption or "(media)")
    await state.set_state(Bc.confirm)
    langs = {}
    for pid in recipients:
        lang = await central.get_lang(pid) or "uz"
        langs[lang] = langs.get(lang, 0) + 1
    sec = loc.sections(html)
    notes = []
    if langs.get("ru"):
        notes.append(f"🇷🇺 rus tilidagi ota-onalar: {langs['ru']} — " + ("ruscha qism bor ✅" if "ru" in sec else
                     "⚠️ ruscha qism yo'q: o'zbekcha matn kirill harflarida boradi (<code>---ru</code> qo'shing)"))
    if langs.get("en"):
        notes.append(f"🇬🇧 ingliz tilidagi ota-onalar: {langs['en']} — " + ("inglizcha qism bor ✅" if "en" in sec else
                     "⚠️ inglizcha qism yo'q: o'zbekcha matn boradi (<code>---en</code> qo'shing)"))
    await message.answer(f"Yuqoridagi xabar <b>{len(recipients)}</b> ta ota-onaga yuboriladi"
                         + ("\n" + "\n".join(notes) if notes else "") + ".\nTasdiqlaysizmi?",
                         reply_markup=broadcast_confirm_kb())


@router.callback_query(BcCb.filter(F.act == "send"), Bc.confirm)
async def cb_bc_send(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await cb.message.edit_text("⏳ Yuborilmoqda…")
    await cb.answer()
    recipients = await db.parent_ids_for_groups(data.get("target") or None)
    sent = 0
    multi = bool(data.get("html")) and len(loc.sections(data["html"])) > 1
    for pid in recipients:
        lang = await central.get_lang(pid) or "uz"
        for _ in range(2):
            try:
                if data.get("html") and (multi or lang != "uz"):  # har bir ota-onaga o'z tilidagi qism
                    body = loc.pick(data["html"], lang)
                    if data.get("has_text"):
                        await cb.bot.send_message(pid, body)
                    else:
                        await cb.bot.copy_message(pid, data["chat_id"], data["message_id"], caption=body)
                else:
                    await cb.bot.copy_message(pid, data["chat_id"], data["message_id"])
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                await db.set_parent_active(pid, False)
                break
            except TelegramBadRequest:
                break
        await asyncio.sleep(0.04)
    await db.add_announcement(data["text"], data.get("target") or [], cb.from_user.id, sent)
    await cb.message.edit_text(f"✅ E'lon yuborildi: {sent} / {len(recipients)}")


@router.callback_query(BcCb.filter(F.act == "cancel"))
async def cb_bc_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Bekor qilindi.")
    await cb.answer()


# ---------------------------------------------------------------- bog'lash so'rovlari
@router.callback_query(LinkCb.filter())
async def cb_link_request(cb: CallbackQuery, callback_data: LinkCb) -> None:
    from staffops import decide_link
    done, verdict = await decide_link(cb.bot, callback_data.rid, bool(callback_data.ok), cb.from_user.id)
    if not done:
        await cb.answer(verdict, show_alert=True)
        return
    try:
        await cb.message.edit_text(f"{cb.message.html_text}\n\n<b>{verdict}</b> — {esc(cb.from_user.full_name)}")
    except TelegramBadRequest:
        pass
    await cb.answer(verdict)


# ---------------------------------------------------------------- savollarga javob
@router.callback_query(AnsCb.filter())
async def cb_answer(cb: CallbackQuery, callback_data: AnsCb, state: FSMContext) -> None:
    q = await db.get_question(callback_data.qid)
    if not q:
        await cb.answer("Savol topilmadi.", show_alert=True)
        return
    if q["answer"]:
        await cb.answer("Bu savolga allaqachon javob berilgan.", show_alert=True)
        return
    if not await _student_visible(q["student_id"]):
        await cb.answer(NOT_YOURS, show_alert=True)
        return
    await state.set_state(Ans.text)
    await state.update_data(qid=q["id"])
    await cb.answer()
    await cb.message.answer(f"#{q['id']} savolga javobingizni yozing. Bekor qilish: /bekor")


@router.message(Ans.text, F.text, NOT_CMD)
async def on_answer_text(message: Message, state: FSMContext) -> None:
    qid = (await state.get_data())["qid"]
    await state.clear()
    q = await db.get_question(qid)
    if not q or q["answer"]:
        await message.answer("Bu savolga allaqachon javob berilgan.")
        return
    if not await _student_visible(q["student_id"]):
        await message.answer(NOT_YOURS)
        return
    if not q["student_id"]:  # oldingi versiyadagi farzandsiz savol — avvalgidek
        ok = await safe_send(message.bot, q["parent_id"], f"💬 <b>Kurs koordinatori javobi</b>\n\n{esc(message.text)}")
        await db.answer_question(qid, message.text, message.from_user.id)
        await message.answer("✅ Javob yuborildi." if ok else "⚠️ Javob saqlandi, lekin ota-onaga yetkazilmadi.")
        return
    res = await chat.staff_reply(message.bot, message.from_user.id, message.from_user.full_name, q["student_id"],
                                 q["parent_id"], message.text, await central.get_lang(q["parent_id"]))
    await message.answer("✅ Javob yuborildi." if res["delivered"] else "⚠️ Javob saqlandi, lekin ota-onaga yetkazilmadi "
                                                                   "(botni bloklagan bo'lishi mumkin).")


# ---------------------------------------------------------------- talaba deb aniqlanganlar
@router.callback_query(GuardCb.filter())
async def cb_guard(cb: CallbackQuery, callback_data: GuardCb) -> None:
    block = await db.get_block(callback_data.uid)
    if not block:
        await cb.answer("Yozuv topilmadi.", show_alert=True)
        return
    uid = callback_data.uid
    if callback_data.ok:
        await db.set_block_status(uid, "allowed", cb.from_user.id)
        if block["phone"]:
            parent = await db.get_parent(uid)
            await db.upsert_parent(uid, block["phone"], (parent or {}).get("tg_name") or block["name"] or "")
            for st in await db.students_by_phone(block["phone"]):
                await db.link_parent(uid, st["id"], "phone")
        await safe_send(cb.bot, uid, "✅ Kurs koordinatori sizni ota-ona sifatida tasdiqladi. Davom etish uchun /start bosing.")
        verdict = "✅ Ruxsat berildi"
    else:
        await db.set_block_status(uid, "blocked", cb.from_user.id)
        verdict = "🚫 Bloklangan qoldi"
    try:
        await cb.message.edit_text(f"{cb.message.html_text}\n\n<b>{verdict}</b> — {esc(cb.from_user.full_name)}")
    except TelegramBadRequest:
        pass
    await cb.answer(verdict)


@router.message(Command("bloklar"))
async def cmd_blocks(message: Message) -> None:
    items = await db.list_blocks("blocked", 20)
    if not items:
        await message.answer("Talaba deb bloklangan foydalanuvchi yo'q.")
        return
    await message.answer(f"🚫 <b>Talaba deb bloklanganlar</b> (oxirgi {len(items)} ta):")
    for b in items:
        who = esc(b["name"] or "—") + (f" (@{esc(b['username'])})" if b["username"] else "")
        await message.answer(
            f"👤 {who}, ID <code>{b['tg_id']}</code>\n📱 {fmt_phone(b['phone']) if b['phone'] else '—'}\n"
            f"🗓 {fmt_date(b['created_at'][:10], False)}\n{b['detail'] or ''}",
            reply_markup=guard_kb(b["tg_id"]),
        )


@router.message(Command("guruhlar"))
async def cmd_groups(message: Message) -> None:
    groups = await db.tg_groups()
    if not groups:
        await message.answer(
            "Hali birorta talabalar Telegram guruhi qo'shilmagan.\n\n"
            "Botni talabalar guruhiga a'zo sifatida qo'shing va <b>administrator</b> qiling (eng kam huquqlar "
            "yetarli). Shundan so'ng guruh a'zolari ota-ona sifatida ro'yxatdan o'ta olmaydi. Guruhni akademik "
            "guruhga bog'lash uchun guruhning o'zida <code>/guruh IQ-21</code> deb yozing."
        )
        return
    lines = [f"👥 <b>Talabalar Telegram guruhlari</b> ({len(groups)} ta)\n"]
    for g in groups:
        admin = "✅ admin" if g["bot_admin"] else "⚠️ admin emas — a'zolarni tekshira olmaydi"
        lines.append(f"• «{esc(g['title'] or g['chat_id'])}»"
                     + (f" → {esc(g['group_name'])}" if g["group_name"] else " → <i>guruh nomi bog'lanmagan</i>")
                     + f"\n   {admin}, ma'lum a'zolar: {g['members']}")
    await message.answer("\n".join(lines))


@router.callback_query(GroupCb.filter(F.act == "off"))
async def cb_group_off(cb: CallbackQuery, callback_data: GroupCb) -> None:
    await db.remove_tg_group(callback_data.cid)
    try:
        await cb.bot.leave_chat(callback_data.cid)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    try:
        await cb.message.edit_text(f"{cb.message.html_text}\n\n<b>❌ Talabalar guruhlari ro'yxatidan olib tashlandi, "
                                   "bot guruhdan chiqdi.</b>\nShu guruh sababli bloklangan ota-onalar bo'lsa, "
                                   "/bloklar orqali ruxsat bering.")
    except TelegramBadRequest:
        pass
    await cb.answer("Olib tashlandi")


_recheck_running = False
_bg_tasks: set[asyncio.Task] = set()


@router.message(Command("tekshir"))
async def cmd_recheck(message: Message) -> None:
    global _recheck_running
    if _recheck_running:
        await message.answer("Tekshiruv allaqachon ketmoqda, iltimos kuting.")
        return
    _recheck_running = True
    progress = await message.answer("⏳ Ro'yxatdan o'tganlar qayta tekshirilmoqda…")

    async def on_progress(i: int, total: int, found: int) -> None:
        try:
            await progress.edit_text(f"⏳ Tekshirilmoqda: {i}/{total}, talaba deb topilganlar: {found}")
        except TelegramBadRequest:
            pass

    async def run() -> None:
        global _recheck_running
        try:
            res = await recheck_parents(message.bot, live=True, progress=on_progress)
            text = (f"✅ Tekshiruv yakunlandi.\nTekshirilgan foydalanuvchilar: {res['checked']}\n"
                    f"Telegram orqali tekshirilgan guruhlar (bot admin): {res['groups']}\n"
                    f"Talaba deb topilib bloklanganlar: {res['found']}")
            if res["found"] > res["notified"]:
                text += "\nTo'liq ro'yxat: /bloklar"
            await progress.edit_text(text)
        except Exception:
            log.exception("Qayta tekshiruv xatosi")
            await progress.edit_text("❌ Tekshiruvda xatolik yuz berdi, loglarni ko'ring.")
        finally:
            _recheck_running = False

    task = asyncio.create_task(run())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# ---------------------------------------------------------------- rasmiy hujjatlar (PDF) yuborish
# Bitta buyruqda bir nechta talaba bo'lishi mumkin. Bot hujjatni o'qib, undagi talabalarni topadi va har bir
# talabaning ota-onasiga faqat shu talaba ko'rinadigan nusxani yuboradi: boshqa talabalarning F.I.Sh., guruhi,
# ID si va shu qatordagi ma'lumotlari qora rang bilan yopiladi (redact.py). Yuborishdan oldin har bir nusxa
# kurs koordinatoriga ko'rsatiladi.
DOC_ASK_STUDENT = "👨‍🎓 Hujjat qaysi talabaga tegishli? <b>Familiya-ismini</b> yoki <b>HEMIS ID</b> sini yozing."
_NAME_SKIP = {"pdf", "xat", "xati", "dekan", "dekanat", "dekani", "buyruq", "buyrugi", "nusxa", "nusxasi", "scan",
              "skan", "talaba", "talabasi", "hujjat", "fayl", "son", "sonli", "yil"}
DOC_FILE_NAMES = {"tushuntirish": "Tushuntirish_xati", "ogohlantirish": "Dekan_ogohlantirishi",
                  "hayfsan": "Hayfsan", "boshqa": "Rasmiy_hujjat"}
MAX_DOC_STUDENTS = 30
_PDF_CACHE: "OrderedDict[str, tuple[bytes, redact.Analysis]]" = OrderedDict()  # file_unique_id -> (fayl, tahlil)


def _cache_put(key: str, value) -> None:
    _PDF_CACHE[key] = value
    _PDF_CACHE.move_to_end(key)
    while len(_PDF_CACHE) > 8:
        _PDF_CACHE.popitem(last=False)


def _is_pdf(doc) -> bool:
    return doc.mime_type == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")


def _doc_date(comment: str | None) -> str:
    dates = parse_user_dates(comment or "")
    return (dates[0] if dates else today()).isoformat()


async def _find_students(q: str, limit: int = 8) -> list[dict]:
    """HEMIS ID bo'yicha aniq yoki F.I.Sh bo'yicha taxminiy qidiruv (koordinator — faqat o'z guruhlarida)."""
    rows = await db.all_students_brief(viewer_scope())
    key = normalize_text(q).replace(" ", "")
    exact = [s for s in rows if key and normalize_text(s["hemis_id"]).replace(" ", "") == key]
    if exact:
        return exact
    qn = normalize_text(q)
    if not qn:
        return []
    scored = sorted(((name_score(qn, s["name_norm"]), s) for s in rows), key=lambda x: -x[0])
    return [s for sc, s in scored if sc >= 0.8][:limit]


async def _guess_student(file_name: str, caption: str) -> tuple[dict | None, list[dict]]:
    """Fayl nomi/izohda HEMIS ID bo'lsa — aniq talaba; bo'lmasa fayl nomidagi ism bo'yicha takliflar."""
    rows = await db.all_students_brief(viewer_scope())
    by_id = {normalize_text(s["hemis_id"]).replace(" ", ""): s for s in rows}
    for t in normalize_text(f"{file_name.rsplit('.', 1)[0]} {caption}").split():
        if len(t) >= 4 and t in by_id:
            return by_id[t], []
    keys = doc_keywords()
    words = [t for t in normalize_text(file_name.rsplit(".", 1)[0]).split()
             if len(t) > 2 and t not in _NAME_SKIP and not any(ch.isdigit() for ch in t)
             and not any(t.startswith(k) for k in keys)]
    if not words:
        return None, []
    q = " ".join(words[:3])
    scored = sorted(((name_score(q, s["name_norm"]), s) for s in rows), key=lambda x: -x[0])
    return None, [s for sc, s in scored if sc >= 0.85][:6]


async def _students(ids) -> list[dict]:
    """Talabalar (id bo'yicha); koordinator — faqat o'z guruhlaridagilari."""
    scope = viewer_scope()
    return [st for st in [await db.get_student(i) for i in ids] if st and in_scope(st.get("group_name"), scope)]


NOT_YOURS = "Bu talaba sizga biriktirilgan guruhlarda emas."


async def _student_visible(sid: int | None) -> bool:
    """Talaba joriy koordinator guruhlarida (yoki koordinatorga guruh biriktirilmagan / super-admin)."""
    scope = viewer_scope()
    if scope is None:
        return True
    st = await db.get_student(sid) if sid else None
    return bool(st) and in_scope(st.get("group_name"), scope)


async def _read_pdf(bot, data: dict) -> tuple[str, dict]:
    """PDF ni yuklab olib o'qiydi. Qaytaradi: (kurs koordinatoriga qisqa xulosa, state uchun yangilanishlar)."""
    uid = data["file_uid"]
    if data.get("file_size") and data["file_size"] > 20 * 1024 * 1024:
        return ("⚠️ Fayl 20 MB dan katta — bot uni o'qiy olmaydi, shuning uchun boshqa talabalar ma'lumotlarini "
                "avtomatik yopib bo'lmaydi.", {"an_ok": False})
    try:
        if uid not in _PDF_CACHE:
            buf = await bot.download(data["file_id"])
            raw = buf.read()
            an = await asyncio.to_thread(redact.analyze, raw, await db.all_students_brief())
            _cache_put(uid, (raw, an))
        raw, an = _PDF_CACHE[uid]
    except Exception as e:
        log.exception("PDF ni o'qib bo'lmadi")
        return f"⚠️ Faylni o'qib bo'lmadi ({esc(e)}).", {"an_ok": False}
    if not an.readable:
        why = an.error or ("hujjat skanerlangan (rasm), OCR dasturi (Tesseract) esa serverda o'rnatilmagan"
                           if not redact.ocr_languages() else "hujjatdagi matnni tanib bo'lmadi")
        return (f"⚠️ Hujjat matnini o'qib bo'lmadi: {esc(why.rstrip('.'))}. Boshqa talabalar ma'lumotlarini avtomatik yopib "
                "bo'lmaydi.", {"an_ok": False})
    kind = {"text": "matnli PDF", "ocr": "skanerlangan, matn OCR orqali o'qildi",
            "mixed": "qisman skanerlangan, OCR ishlatildi"}[an.mode]
    # Yopish uchun butun kurs ro'yxati ishlatiladi (boshqa guruh talabalari ham yopiladi), tanlash uchun esa —
    # faqat koordinatorning o'z guruhlari talabalari
    visible = [st["id"] for st in await _students(an.mentioned)]
    found = visible[:MAX_DOC_STUDENTS]
    others = len(an.mentioned) - len(visible)
    text = (f"📄 Hujjat o'qildi ({kind}, {len(an.pages)} sahifa). "
            + (f"Unda bazadagi <b>{len(found)}</b> ta talaba topildi." if found else
               "Unda bazadagi talabalar topilmadi — talabani o'zingiz ko'rsating.")
            + (f" Boshqa guruhlardagi {others} ta talaba tanlanmaydi (ularning ma'lumotlari yopiladi)." if others else ""))
    return text, {"an_ok": True, "found": found}


def _preview_caption(st: dict, pv: dict) -> str:
    head = f"👁 {esc(st['full_name'])} ota-onasi ko'radigan nusxa"
    if not pv.get("checked"):
        return head + "\n⚠️ Hujjat tekshirilmadi — asl holida yuboriladi."
    notes = [f"🔒 Yopilgan joylar: {pv['boxes']}" if pv["boxes"] else "Yopiladigan boshqa talaba topilmadi"]
    if not pv["found"]:
        notes.append("⚠️ Talabaning o'zi hujjatda topilmadi")
    if pv["amb"]:
        notes.append("⚠️ Ismi o'xshash talaba bor — nusxani diqqat bilan tekshiring")
    return head + "\n" + "\n".join(notes)


async def _build_previews(msg: Message, state: FSMContext) -> None:
    """Har bir tanlangan talaba uchun alohida nusxa tayyorlab, kurs koordinatoriga ko'rsatadi (va Telegram'ga yuklaydi)."""
    data = await state.get_data()
    previews: dict = data.get("previews") or {}
    todo = [sid for sid in data["sids"] if str(sid) not in previews]
    if not todo:
        return
    cached = _PDF_CACHE.get(data["file_uid"]) if data.get("an_ok") else None
    if data.get("an_ok") and not cached:  # bot qayta ishga tushgan bo'lsa — faylni qayta o'qiymiz
        _, upd = await _read_pdf(msg.bot, data)
        await state.update_data(**upd)
        cached = _PDF_CACHE.get(data["file_uid"]) if upd.get("an_ok") else None
    wait = await msg.answer(f"⏳ Har bir talaba uchun alohida nusxa tayyorlanmoqda ({len(todo)} ta)…") if cached else None
    fname = f"{DOC_FILE_NAMES.get(data['dtype'], 'Rasmiy_hujjat')}.pdf"
    items = []
    for sid in todo:
        st = await db.get_student(sid)
        if not st:
            continue
        if cached:
            raw, an = cached
            r = await asyncio.to_thread(redact.redact_for, raw, an, sid, st["hemis_id"])
            pv = {"checked": True, "boxes": r.boxes, "found": r.target_found, "amb": r.ambiguous}
            items.append((st, pv, BufferedInputFile(r.pdf, filename=fname)))
        else:  # o'qib bo'lmagan hujjat — asl fayl
            pv = {"checked": False, "boxes": 0, "found": True, "amb": False,
                  "file_id": data["file_id"], "file_uid": data["file_uid"]}
            previews[str(sid)] = pv
    for k in range(0, len(items), 10):  # Telegram albomida ko'pi bilan 10 ta fayl
        chunk = items[k:k + 10]
        if len(chunk) == 1:
            st, pv, f = chunk[0]
            sent = [await msg.answer_document(f, caption=_preview_caption(st, pv))]
        else:
            sent = await msg.answer_media_group(
                [InputMediaDocument(media=f, caption=_preview_caption(st, pv)) for st, pv, f in chunk])
        for (st, pv, _), m in zip(chunk, sent):
            pv.update(file_id=m.document.file_id, file_uid=m.document.file_unique_id, size=m.document.file_size)
            previews[str(st["id"])] = pv
    await state.update_data(previews=previews)
    if wait:
        try:
            await wait.delete()
        except TelegramBadRequest:
            pass


async def _doc_confirm_text(data: dict) -> str:
    sts = await _students(data["sids"])
    previews = data.get("previews") or {}
    lines = [
        "📄 <b>Hujjatni tekshiring va tasdiqlang</b>\n",
        f"Turi: <b>{doc_title(data['dtype'])}</b>" + (" <i>(fayl nomidan aniqlandi)</i>" if data.get("dtype_guess") else ""),
        f"Asl fayl: {esc(data['file_name'])}" + (f" ({fmt_size(data.get('file_size'))})" if data.get("file_size") else ""),
        f"Sana: {fmt_date(_doc_date(data.get('comment')), False)}",
        f"Izoh: {esc(data['comment'])}" if data.get("comment") else "Izoh: —",
        f"\n👨‍🎓 <b>Kimga yuboriladi</b> ({len(sts)} ta talaba):",
    ]
    for st in sts:
        pv = previews.get(str(st["id"]), {})
        parents = len(await db.parents_of_student(st["id"]))
        extra = []
        if pv.get("checked"):
            extra.append(f"yopilgan joylar: {pv['boxes']}" if pv["boxes"] else "yopiladigan joy yo'q")
            if not pv["found"]:
                extra.append("⚠️ o'zi hujjatda topilmadi")
            if pv["amb"]:
                extra.append("⚠️ ismi o'xshash talaba bor")
        dup = await db.same_file_sent(st["id"], data.get("file_uid"))
        if dup:
            extra.append(f"⚠️ bu hujjat {fmt_date(dup['created_at'][:10], False)} da yuborilgan")
        lines.append(f"• {esc(st['full_name'])} · {esc(st['group_name'] or '—')} — ota-onalar: {parents}"
                     + (f"; {'; '.join(extra)}" if extra else ""))
    if data.get("an_ok"):
        lines.append("\n🔒 Har bir ota-onaga faqat o'z farzandi ko'rinadigan nusxa boradi: boshqa talabalarning "
                     "ma'lumotlari qora rang bilan yopilgan. Nusxalar yuqorida — yuborishdan oldin ko'zdan kechiring.")
    else:
        lines.append("\n⚠️ <b>Hujjat tekshirilmadi</b>, u asl holida yuboriladi. Hujjatda boshqa talabalarning "
                     "ma'lumotlari yo'qligiga ishonch hosil qiling. Aks holda har bir talaba uchun alohida nusxa "
                     "tayyorlab yuboring.")
    no_parents = [st for st in sts if not await db.parents_of_student(st["id"])]
    if no_parents:
        lines.append("Ota-onasi hali ulanmagan talabalar hujjatni ota-ona ulangach «📄 Hujjatlar» bo'limida ko'radi.")
    lines.append("\nIzohni o'zgartirish uchun yangi matn yozib yuboring (unda sana bo'lsa, hujjat sanasi shu bo'ladi).")
    return "\n".join(lines)


async def _doc_advance(msg: Message, state: FSMContext) -> None:
    """Yetishmayotgan ma'lumotni so'raydi: PDF → talaba(lar) → tur → nusxalar → tasdiqlash."""
    data = await state.get_data()
    if not data.get("file_id"):
        await state.set_state(DocSend.file)
        await msg.answer("📎 <b>PDF</b> faylni yuboring. Izohiga (caption) qisqa sharh va hujjat sanasini "
                         "yozishingiz mumkin, masalan: <i>22.09.2026 dagi 45-son buyruq</i>.\n\nBekor qilish: /bekor")
    elif data.get("picking"):
        await state.set_state(DocSend.pick)
        found = list(dict.fromkeys((data.get("found") or []) + (data.get("sids") or [])))
        await msg.answer("👨‍🎓 Hujjat qaysi talabalarning ota-onalariga yuborilsin? Belgini bosib tanlang yoki "
                         "olib tashlang. Har bir ota-ona faqat o'z farzandini ko'radi.",
                         reply_markup=doc_pick_kb(await _students(found), set(data.get("sids") or [])))
    elif not data.get("sids"):
        await state.set_state(DocSend.student)
        sugg = await _students(data.get("suggest", []))
        text = DOC_ASK_STUDENT + ("\n\nFayl nomiga qarab taxminiy variantlar (ro'yxatda yo'q bo'lsa, yozing):"
                                  if sugg else "") + "\n\nBekor qilish: /bekor"
        await msg.answer(text, reply_markup=doc_students_kb(sugg) if sugg else None)
    elif not data.get("dtype"):
        await state.set_state(DocSend.dtype)
        await msg.answer("🏷 Hujjat turini tanlang:", reply_markup=doc_type_kb())
    else:
        await _build_previews(msg, state)
        data = await state.get_data()
        await state.set_state(DocSend.confirm)
        await msg.answer(await _doc_confirm_text(data), reply_markup=doc_confirm_kb(bool(data.get("an_ok"))))


@router.message(Command("hujjat"))
async def cmd_document(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(DocSend.file)
    await message.answer(
        "📄 <b>Rasmiy hujjat yuborish</b>\n\nTushuntirish xati, dekan ogohlantirishi, hayfsan yoki boshqa rasmiy hujjat "
        "PDF ko'rinishida talabaning ota-onalariga yuboriladi va farzand sahifasidagi «📄 Hujjatlar» bo'limida "
        "saqlanadi. Hujjatda bir nechta talaba bo'lsa, har bir ota-ona faqat o'z farzandini ko'radi — boshqa "
        "talabalarning ma'lumotlari qora rang bilan yopiladi.\n\n📎 PDF faylni yuboring. Izohiga (caption) qisqa sharh "
        "va hujjat sanasini yozishingiz mumkin.\n\nBekor qilish: /bekor"
    )


@router.message(StateFilter(None, DocSend), F.document)
async def on_pdf(message: Message, state: FSMContext) -> None:
    doc = message.document
    in_flow = await state.get_state() is not None
    if not _is_pdf(doc):
        if not in_flow and (doc.file_name or "").lower().endswith((".xlsx", ".xlsm")):
            await message.answer("Excel faylni yuklash uchun avval /import buyrug'ini bering.")
        else:
            await message.answer("Rasmiy hujjat sifatida faqat <b>PDF</b> fayl qabul qilinadi.")
        return
    old = await state.get_data() if in_flow else {}
    await state.clear()
    caption = (message.caption or "").strip()
    data = {"file_id": doc.file_id, "file_uid": doc.file_unique_id, "file_name": doc.file_name or "hujjat.pdf",
            "file_size": doc.file_size, "comment": caption or old.get("comment"), "dtype": old.get("dtype"),
            "dtype_guess": old.get("dtype_guess"), "previews": {}}
    if not data["dtype"]:
        guess = detect_doc_type(doc.file_name, caption)
        if guess:
            data.update(dtype=guess, dtype_guess=True)
    wait = await message.answer("⏳ Hujjat o'qilmoqda va undagi talabalar aniqlanmoqda…")
    summary, upd = await _read_pdf(message.bot, data)
    data.update(upd)
    found = data.get("found") or []
    if found:
        data["sids"] = list(found)
        data["picking"] = len(found) > 1
    else:
        st, sugg = await _guess_student(doc.file_name or "", caption)
        data["sids"] = [st["id"]] if st else []
        data["suggest"] = [x["id"] for x in sugg]
    await state.update_data(**data)
    try:
        await wait.edit_text(summary)
    except TelegramBadRequest:
        await message.answer(summary)
    await _doc_advance(message, state)


@router.message(DocSend.student, F.text, NOT_CMD)
async def on_doc_student(message: Message, state: FSMContext) -> None:
    found = await _find_students(message.text)
    if not found:
        await message.answer("Topilmadi. Familiya-ismni tekshirib qaytadan yozing yoki HEMIS ID ni yuboring.")
        return
    if len(found) == 1:
        await _add_student(message, state, found[0]["id"])
        return
    await message.answer("Bir nechta talaba topildi, keraklisini tanlang:", reply_markup=doc_students_kb(found))


async def _add_student(msg: Message, state: FSMContext, sid: int) -> None:
    data = await state.get_data()
    sids = list(data.get("sids") or [])
    if sid not in sids:
        sids.append(sid)
    found = list(data.get("found") or [])
    await state.update_data(sids=sids, found=found + [sid] if sid not in found else found,
                            picking=bool(data.get("found")) or len(sids) > 1)
    await _doc_advance(msg, state)


@router.message(DocSend.dtype, NOT_CMD)
async def on_doc_type_text(message: Message) -> None:
    await message.answer("Hujjat turini yuqoridagi tugmalardan birini bosib tanlang.", reply_markup=doc_type_kb())


@router.message(DocSend.pick, NOT_CMD)
async def on_doc_pick_text(message: Message) -> None:
    await message.answer("Talabalarni yuqoridagi tugmalar bilan tanlang va «▶️ Davom etish» ni bosing.")


@router.message(DocSend.file, NOT_CMD)
async def on_doc_file_wrong(message: Message) -> None:
    await message.answer("Iltimos, PDF faylni hujjat (document) sifatida yuboring yoki /bekor.")


@router.message(DocSend.confirm, F.text, NOT_CMD)
async def on_doc_comment(message: Message, state: FSMContext) -> None:
    await state.update_data(comment=message.text.strip())
    data = await state.get_data()
    await message.answer(await _doc_confirm_text(data), reply_markup=doc_confirm_kb(bool(data.get("an_ok"))))


@router.callback_query(DocStuCb.filter(), StateFilter(DocSend))
async def cb_doc_student(cb: CallbackQuery, callback_data: DocStuCb, state: FSMContext) -> None:
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await _add_student(cb.message, state, callback_data.sid)


@router.callback_query(DocPickCb.filter(), DocSend.pick)
async def cb_doc_pick(cb: CallbackQuery, callback_data: DocPickCb, state: FSMContext) -> None:
    data = await state.get_data()
    sids = list(data.get("sids") or [])
    if callback_data.sid in sids:
        sids.remove(callback_data.sid)
    else:
        sids.append(callback_data.sid)
    await state.update_data(sids=sids)
    found = list(dict.fromkeys((data.get("found") or []) + sids))
    try:
        await cb.message.edit_reply_markup(reply_markup=doc_pick_kb(await _students(found), set(sids)))
    except TelegramBadRequest:
        pass
    await cb.answer()


@router.callback_query(DocActCb.filter(F.act == "picked"), DocSend.pick)
async def cb_doc_picked(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("sids"):
        await cb.answer("Kamida bitta talabani tanlang.", show_alert=True)
        return
    await state.update_data(picking=False)
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await _doc_advance(cb.message, state)


@router.callback_query(DocActCb.filter(F.act == "add"), DocSend.pick)
async def cb_doc_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DocSend.student)
    await cb.answer()
    await cb.message.answer(DOC_ASK_STUDENT + "\n\nBekor qilish: /bekor")


@router.callback_query(DocTypeCb.filter(), StateFilter(DocSend))
async def cb_doc_type(cb: CallbackQuery, callback_data: DocTypeCb, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("dtype") != callback_data.t:
        await state.update_data(previews={} if data.get("an_ok") else data.get("previews"))  # fayl nomi o'zgaradi
    await state.update_data(dtype=callback_data.t, dtype_guess=False)
    await cb.answer()
    try:
        await cb.message.edit_text(f"🏷 Tanlandi: <b>{doc_title(callback_data.t)}</b>")
    except TelegramBadRequest:
        pass
    await _doc_advance(cb.message, state)


@router.callback_query(DocActCb.filter(F.act == "cancel"))
async def cb_doc_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await cb.message.edit_text("✖️ Hujjat yuborish bekor qilindi.")
    except TelegramBadRequest:
        pass
    await cb.answer()


@router.callback_query(DocActCb.filter(F.act.in_({"student", "type"})), DocSend.confirm)
async def cb_doc_change(cb: CallbackQuery, callback_data: DocActCb, state: FSMContext) -> None:
    await state.update_data(**({"picking": True} if callback_data.act == "student"
                               else {"dtype": None, "dtype_guess": False}))
    await cb.answer()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await _doc_advance(cb.message, state)


@router.callback_query(DocActCb.filter(F.act == "send"), DocSend.confirm)
async def cb_doc_send(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()  # ikki marta bosilsa ikki marta yuborilmasin
    await cb.answer()
    try:
        await cb.message.edit_text("⏳ Yuborilmoqda…")
    except TelegramBadRequest:
        pass
    batch = uuid.uuid4().hex[:12]
    previews = data.get("previews") or {}
    lines, first_id, total_sent, total_parents = [], None, 0, 0
    for st in await _students(data["sids"]):
        pv = previews.get(str(st["id"])) or {"file_id": data["file_id"], "file_uid": data["file_uid"], "boxes": 0}
        did = await db.add_document(st["id"], data["dtype"], pv["file_id"], pv.get("file_uid"),
                                    f"{DOC_FILE_NAMES.get(data['dtype'], 'Rasmiy_hujjat')}.pdf",
                                    pv.get("size") or data.get("file_size"), _doc_date(data.get("comment")),
                                    data.get("comment"), cb.from_user.id, batch=batch, redacted=pv.get("boxes", 0),
                                    source_file_id=data.get("file_uid"))
        first_id = first_id or did
        from staffops import deliver_document
        sent, n_parents = await deliver_document(cb.bot, did, st)
        parents = range(n_parents)
        total_sent += sent
        total_parents += len(parents)
        state_txt = (f"ota-onalarga yuborildi: {sent}/{len(parents)}" if parents else
                     "ota-ona hali ulanmagan — ulangach «Hujjatlar» bo'limida ko'radi")
        lines.append(f"• {esc(st['full_name'])} — {state_txt}" + (f" (🔒 yopilgan: {pv['boxes']})" if pv.get("boxes") else ""))
    head = (f"✅ <b>{doc_title(data['dtype'])}</b> saqlandi va yuborildi\n📎 {esc(data['file_name'])}\n"
            f"Jami: {len(lines)} ta talaba, {total_sent}/{total_parents} ota-onaga yetkazildi\n\n")
    await cb.message.edit_text(head + "\n".join(lines), reply_markup=doc_revoke_kb(first_id, batch=len(lines) > 1)
                               if first_id else None)


@router.callback_query(DocStuCb.filter())
@router.callback_query(DocTypeCb.filter())
@router.callback_query(DocPickCb.filter())
@router.callback_query(DocActCb.filter())
async def cb_doc_expired(cb: CallbackQuery) -> None:
    await cb.answer("Bu amal eskirgan. Hujjat yuborishni /hujjat bilan qaytadan boshlang.", show_alert=True)


async def _append_note(cb: CallbackQuery, note: str, kb=None) -> None:
    text = f"{cb.message.html_text}\n\n{note}"
    try:
        if cb.message.document:
            await cb.message.edit_caption(caption=text[:1024], reply_markup=kb)
        else:
            await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        await cb.message.answer(note)


@router.callback_query(DocRevCb.filter())
async def cb_doc_revoke(cb: CallbackQuery, callback_data: DocRevCb) -> None:
    doc = await db.get_document(callback_data.did)
    docs = (await db.documents_in_batch(doc["batch"]) if doc and callback_data.b and doc.get("batch")
            else [doc] if doc and not doc["revoked"] else [])
    if not docs:
        await cb.answer("Bu hujjat allaqachon qaytarib olingan.", show_alert=True)
        return
    if callback_data.sure != 1:  # 0 — tasdiqlash so'raladi, 2 — kurs koordinatori fikridan qaytdi
        try:
            await cb.message.edit_reply_markup(reply_markup=doc_revoke_kb(doc["id"], sure=callback_data.sure == 0,
                                                                          batch=bool(callback_data.b)))
        except TelegramBadRequest:
            pass
        await cb.answer("Qaytarib olishni tasdiqlang" if callback_data.sure == 0 else "Hujjat o'z joyida qoldi")
        return
    deleted = failed = 0
    for d0 in docs:
        for d in await db.deliveries(d0["id"]):
            try:
                await cb.bot.delete_message(d["parent_id"], d["message_id"])
                deleted += 1
            except (TelegramBadRequest, TelegramForbiddenError):
                failed += 1
        await db.revoke_document(d0["id"], cb.from_user.id)
    note = (f"<b>🗑 Qaytarib olindi</b> — {esc(cb.from_user.full_name)}. Hujjat ota-onalar bo'limidan olib tashlandi"
            + (f" ({len(docs)} ta talaba)" if len(docs) > 1 else "")
            + (f", chatlaridan o'chirildi: {deleted}" if deleted else "") + ".")
    if failed:
        note += (f"\n⚠️ {failed} ta ota-onaning chatidan o'chirib bo'lmadi (Telegram faqat 48 soat ichida "
                 "o'chirishga ruxsat beradi yoki ota-ona botni o'chirgan). Ular bilan bevosita bog'laning.")
    await _append_note(cb, note)
    await cb.answer("Qaytarib olindi")


@router.message(Command("hujjatlar"))
async def cmd_documents(message: Message, command: CommandObject) -> None:
    q = (command.args or "").strip()
    if not q:
        await message.answer("Foydalanish: /hujjatlar <code>familiya ism</code> yoki <code>HEMIS ID</code>")
        return
    found = await _find_students(q)
    if not found:
        await message.answer("Talaba topilmadi.")
        return
    if len(found) > 1:
        names = "\n".join(f"• {esc(s['full_name'])} · {esc(s['group_name'] or '—')} · ID {esc(s['hemis_id'])}"
                          for s in found)
        await message.answer(f"Bir nechta talaba topildi, aniqroq yozing yoki HEMIS ID bering:\n{names}")
        return
    st = found[0]
    docs = await db.documents_for(st["id"])
    if not docs:
        await message.answer(f"{esc(st['full_name'])} ga hali hujjat yuborilmagan.")
        return
    await message.answer(f"📄 <b>{esc(st['full_name'])}</b> · {esc(st['group_name'] or '—')} — hujjatlar: {len(docs)}\n"
                         "Quyida ota-ona ko'rgan nusxalar.")
    for d in docs[:20]:
        n = len(await db.deliveries(d["id"]))
        cap = (f"<b>{doc_title(d['doc_type'])}</b> · {fmt_date(d['doc_date'] or d['created_at'][:10], False)}\n"
               + (f"💬 {esc(d['comment'][:300])}\n" if d.get("comment") else "")
               + (f"🔒 Boshqa talabalar yopilgan: {d['redacted']} joy\n" if d.get("redacted") else "")
               + f"Yuborilgan: {fmt_date(d['created_at'][:10], False)}, ota-onalarga yetkazilgan: {n}")
        await message.answer_document(d["file_id"], caption=cap, reply_markup=doc_revoke_kb(d["id"]))


# ---------------------------------------------------------------- dars qoldirish chegaralari
@router.message(Command("chegaralar"))
async def cmd_levels(message: Message) -> None:
    rows = scope_students(await db.fetchall("SELECT id, full_name, group_name FROM students ORDER BY group_name, full_name"))
    by_level: dict[int, list[tuple]] = {}
    for st in rows:
        sm = await absence.summary(st["id"])
        if not sm:
            continue
        i = absence.level_index(sm["counted"])
        if i >= 0:
            by_level.setdefault(i, []).append((sm["counted"], st, sm))
    if not by_level:
        await message.answer("Chegaraga yetgan talaba yo'q.\n\n" + absence.rules_text())
        return
    lines = [f"📏 <b>Dars qoldirish chegaralari</b> — semestr boshidan, {absence.COUNTED_LABEL} darslar", ""]
    for i in sorted(by_level, reverse=True):
        items = sorted(by_level[i], key=lambda x: -x[0])
        lines.append(f"{absence.level_icon(i)} <b>{esc(absence.action_for(i))}</b> "
                     f"({fmt_pairs(absence.LEVELS[i])} va undan ko'p): {len(items)} ta")
        for h, st, sm in items:
            src = f"HEMIS {fmt_date(sm['as_of'], False)[:5]}" if sm["source"] == "hemis" else "kunlik"
            lines.append(f"   • {esc(st['full_name'])} · {esc(st['group_name'] or '—')} — {fmt_pairs(h)} "
                         f"<i>({src})</i>")
        lines.append("")
    for part in split_message("\n".join(lines)):
        await message.answer(part)


# ---------------------------------------------------------------- talabaning shaxsiy jadvali
@router.message(Command("jadval"))
async def cmd_student_schedule(message: Message, command: CommandObject) -> None:
    q = (command.args or "").strip()
    if not q:
        await message.answer("Foydalanish: /jadval <code>familiya ism</code> yoki <code>HEMIS ID</code>")
        return
    found = await _find_students(q)
    if not found:
        await message.answer("Talaba topilmadi.")
        return
    if len(found) > 1:
        names = "\n".join(f"• {esc(s['full_name'])} · {esc(s['group_name'] or '—')} · ID {esc(s['hemis_id'])}"
                          for s in found)
        await message.answer(f"Bir nechta talaba topildi, aniqroq yozing yoki HEMIS ID bering:\n{names}")
        return
    st = await db.get_student(found[0]["id"])
    mon, sun = week_bounds(today())
    subj = await db.enrollment_for(st["id"])
    text = await schedule_report(st, mon, sun)
    if subj:
        text += "\n\n🎯 Biriktirilgan: " + ", ".join(
            esc(x["subject"]) + (f" ({x['subgroup']}-oqim)" if x["subgroup"] else "") for x in subj)
    for part in split_message(text):
        await message.answer(part)


# ---------------------------------------------------------------- kontrakt qarzdorlari
def _filter_students(rows: list[dict], arg: str) -> list[dict]:
    """«2-kurs» / «2» — kurs bo'yicha, boshqa matn — guruh nomi bo'yicha."""
    if not arg:
        return rows
    course = parse_course(arg) if ("kurs" in arg.lower() or arg.isdigit()) else None
    gk = group_key(arg)
    return [r for r in rows if (course and r.get("course") == course)
            or (not course and group_key(r.get("group_name")) == gk)]


@router.message(Command("qarzdorlar"))
async def cmd_debtors(message: Message, command: CommandObject) -> None:
    words = (command.args or "").split()
    kinds = [k for k in ("kontrakt", "trimestr") if k in [w.lower() for w in words]] or ["kontrakt", "trimestr"]
    arg = " ".join(w for w in words if w.lower() not in ("kontrakt", "trimestr"))
    lines = []
    for kind in kinds:
        rows = _filter_students(scope_students(await db.debtors(kind)), arg)
        title = "Kontrakt" if kind == "kontrakt" else "Trimestr"
        if not rows:
            lines.append(f"💰 <b>{title} qarzdorlari</b>{' — ' + esc(arg) if arg else ''}: mavjud emas\n")
            continue
        lines.append(f"💰 <b>{title} qarzdorlari</b>{' — ' + esc(arg) if arg else ''}: {len(rows)} ta, "
                     f"jami qarz: <b>{fmt_money(sum(r['debt'] for r in rows))}</b>")
        for r in rows:
            pct = f" ({r['percent']:g}%)" if r.get("percent") is not None else ""
            lines.append(f"• {esc(r['full_name'])} · {esc(r['group_name'] or '—')} — {fmt_money(r['debt'])}{pct} "
                         f"<i>{fmt_date(r['as_of'], False)[:5]}</i>")
        lines.append("")
    lines.append("Faqat bitta tur: <code>/qarzdorlar kontrakt</code> yoki <code>/qarzdorlar trimestr</code>; "
                 "guruh yoki kurs bo'yicha: <code>/qarzdorlar 2-kurs</code>.")
    for part in split_message("\n".join(lines)):
        await message.answer(part)


@router.message(Command("akademik"))
async def cmd_academic(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    rows = _filter_students(scope_students(await db.fetchall(
        "SELECT id, full_name, group_name, course FROM students WHERE id IN (SELECT DISTINCT student_id FROM grades) "
        "ORDER BY group_name, full_name")), arg)
    found = []
    for st in rows:
        sm = await academic.summary(st["id"])
        if sm["debts"]:
            found.append((st, sm["debts"]))
    if not found:
        await message.answer("Akademik qarzdor talaba yo'q" + (f" ({esc(arg)})" if arg else "") + ".\n\n"
                             + academic.RULES_TEXT)
        return
    found.sort(key=lambda x: -len(x[1]))
    total = sum(len(d) for _, d in found)
    lines = [f"📚 <b>Akademik qarzdorlar</b>{' — ' + esc(arg) if arg else ''}: {len(found)} ta talaba, "
             f"jami {total} ta fan", ""]
    for st, debts in found:
        subj = ", ".join(f"{esc(d['subject'])} ({fmt_num(d['score'])})" for d in debts)
        lines.append(f"• {esc(st['full_name'])} · {esc(st['group_name'] or '—')} — <b>{len(debts)} ta fan</b>: {subj}")
    lines += ["", f"<i>{academic.RULES_TEXT}</i>"]
    for part in split_message("\n".join(lines)):
        await message.answer(part)

# ---------------------------------------------------------------- to'lov muddatlari
@router.message(Command("muddat"))
async def cmd_deadline(message: Message, command: CommandObject) -> None:
    words = (command.args or "").split()
    titles = {"kontrakt": "Kontrakt", "trimestr": "Trimestr"}
    if words and words[0].lower() in titles:
        kind = words[0].lower()
        if len(words) > 1 and words[1].lower() in ("-", "yoq", "yo'q", "ochirish", "o'chirish"):
            await db.set_setting(f"deadline:{kind}", "")
            await message.answer(f"{titles[kind]} to'lov muddati o'chirildi.")
            return
        dates = parse_user_dates(" ".join(words[1:]))
        if not dates:
            await message.answer("Sana tushunilmadi. Masalan: <code>/muddat kontrakt 30.09.2026</code>")
            return
        await db.set_setting(f"deadline:{kind}", dates[0].isoformat())
        n = len(scope_students(await db.debtors(kind)))
        await message.answer(
            f"✅ {titles[kind]} to'lov muddati: <b>{fmt_date(dates[0], False)}</b>.\n"
            f"Muddat ota-onalarga qarzdorlik ma'lumoti bilan ko'rsatiladi. Qarzi bor talabalarning ({n} ta) "
            f"ota-onalariga muddatdan {', '.join(map(str, PAY_REMIND_DAYS))} kun oldin avtomatik eslatma boradi.")
        return
    lines = ["📅 <b>To'lov muddatlari</b>"]
    for kind, title in titles.items():
        d = parse_date(await db.get_setting(f"deadline:{kind}"))
        lines.append(f"{title}: " + (fmt_date(d, False) if d else "belgilanmagan"))
    lines.append("\nBelgilash: <code>/muddat kontrakt 30.09.2026</code> yoki <code>/muddat trimestr 15.10.2026</code>; "
                 "o'chirish: <code>/muddat kontrakt -</code>")
    await message.answer("\n".join(lines))


# ---------------------------------------------------------------- kurs holati (panel)
FLAG_ICON = {"att": "🚫", "acad": "📚", "gpa": "🎓", "kontrakt": "💰", "trimestr": "💳"}


async def _panel_students(f: str) -> list[dict]:
    rows = scope_students(await db.fetchall("SELECT * FROM students ORDER BY group_name, full_name"))
    if f:
        course = parse_course(f) if ("kurs" in f.lower() or f.strip().isdigit()) else None
        gk = group_key(f)
        rows = [r for r in rows if (course and r["course"] == course) or (not course and r["group_key"] == gk)]
    return rows


async def _panel_text(f: str) -> str:
    sts = await status.all_statuses(await _panel_students(f))
    who = esc(scope_label(current_user.get()))
    if not sts:
        return "Talabalar topilmadi" + (f" ({esc(f)})" if f else "") + ".\n" + who
    ids = {x["student"]["id"] for x in sts}
    linked = {r["student_id"] for r in await db.fetchall("""SELECT DISTINCT ps.student_id FROM parent_students ps
                  JOIN parents p ON p.tg_id = ps.parent_id WHERE p.active = 1""")} & ids
    parents = (await db.fetchone(f"""SELECT COUNT(DISTINCT ps.parent_id) n FROM parent_students ps JOIN parents p
                  ON p.tg_id = ps.parent_id WHERE p.active = 1 AND ps.student_id IN ({','.join(map(str, ids))})"""))["n"]
    cnt = {k: sum(1 for x in sts if x["flags"][k]) for k in FLAG_ICON}
    total = {k: sum(x["pays"][k]["debt"] for x in sts if x["flags"][k]) for k in ("kontrakt", "trimestr")}
    many = sum(1 for x in sts if sum(x["flags"].values()) >= 3)
    ts = await last_update(*UPDATE_KEYS["all"])
    return "\n".join([
        f"📊 <b>Kurs holati</b>{' — ' + esc(f) if f else ''}", who, "",
        f"👨‍🎓 Jami talabalar: <b>{len(sts)}</b>",
        f"👨‍👩‍👧 Ulangan ota-onalar: <b>{parents}</b> (ota-onasi ulangan talabalar: {len(linked)} — "
        f"{round(100 * len(linked) / len(sts))}%)",
        f"⚠️ Akademik qarzdorlar: <b>{cnt['acad']}</b>",
        f"🎓 GPA {fmt_limit(GPA_MIN)} dan past (kursdan kursga o'tmaydi): <b>{cnt['gpa']}</b>",
        f"💰 Kontrakt qarzdorlar: <b>{cnt['kontrakt']}</b>" + (f" (jami {fmt_money(total['kontrakt'])})" if cnt["kontrakt"] else ""),
        f"💳 Trimestr qarzdorlar: <b>{cnt['trimestr']}</b>" + (f" (jami {fmt_money(total['trimestr'])})" if cnt["trimestr"] else ""),
        f"🚫 Davomat muammosi borlar: <b>{cnt['att']}</b> ({fmt_pairs(absence.LEVELS[0])} va undan ko'p, {absence.COUNTED_LABEL})",
        f"🔴 3+ muammoli talabalar: <b>{many}</b>",
    ] + await _dynamics_lines(f) + ([f"\n🕐 Oxirgi yangilanish: {fmt_dt(ts)}"] if ts else []) + ["\nRo'yxatni ochish uchun tugmani bosing 👇"])


async def _dynamics_lines(f: str) -> list[str]:
    """Kurs holati ostida — dinamika (guruh/kurs filtri bo'lmaganda; koordinator — o'z guruhlari bo'yicha)."""
    if f:
        return []
    import course_trends
    items = await course_trends.course_dynamics(viewer_scope())
    return ["", "📈 <b>Dinamika</b>"] + course_trends.text_lines(items) if items else []


@router.message(Command("panel"))
async def cmd_panel(message: Message, command: CommandObject) -> None:
    f = (command.args or "").strip()
    wait = await message.answer("⏳ Kurs holati hisoblanmoqda…")
    await wait.edit_text(await _panel_text(f), reply_markup=panel_kb(f))


@router.callback_query(PanelCb.filter())
async def cb_panel(cb: CallbackQuery, callback_data: PanelCb) -> None:
    f, v = callback_data.f, callback_data.v
    await cb.answer()
    if v in ("home", "open"):
        text = await _panel_text(f)
        if v == "open":  # /admin xabaridan — yangi xabar
            await cb.message.answer(text, reply_markup=panel_kb(f))
            return
        try:
            await cb.message.edit_text(text, reply_markup=panel_kb(f))
        except TelegramBadRequest:
            pass
        return
    sts = await status.all_statuses(await _panel_students(f))
    if v == "prob":
        items = sorted((x for x in sts if any(x["flags"].values())),
                       key=lambda x: (-sum(x["flags"].values()), x["student"]["full_name"]))
        title = "🔴 Muammoli talabalar (muammolar soni bo'yicha)"
    else:
        items = [x for x in sts if x["flags"][v]]
        if v in ("kontrakt", "trimestr"):
            items.sort(key=lambda x: -x["pays"][v]["debt"])
        elif v == "att":
            items.sort(key=lambda x: -x["attendance"]["counted"])
        elif v == "acad":
            items.sort(key=lambda x: -len(x["debts"]))
        elif v == "gpa":
            items.sort(key=lambda x: x["gpa"])
        title = {"acad": "📚 Akademik qarzdorlar", "gpa": f"🎓 GPA {fmt_limit(GPA_MIN)} dan past (kursdan kursga o'tmaydi)",
                 "kontrakt": "💰 Kontrakt qarzdorlar",
                 "trimestr": "💳 Trimestr qarzdorlar", "att": "🚫 Davomat muammosi borlar"}[v]
    if not items:
        await cb.message.answer(f"{title}: yo'q ✅")
        return
    lines = [f"<b>{title}</b>{' — ' + esc(f) if f else ''}: {len(items)} ta", ""]
    for x in items:
        st, fl = x["student"], x["flags"]
        det = []
        if fl["att"]:
            det.append(f"🚫 {fmt_pairs(x['attendance']['counted'])}")
        if fl["acad"]:
            det.append(f"📚 {len(x['debts'])} fan" + (f" ({esc(', '.join(d['subject'] for d in x['debts'][:2]))}"
                                                      + (", …" if len(x["debts"]) > 2 else "") + ")"
                                                      if v == "acad" else ""))
        if fl["gpa"]:
            det.append(f"🎓 GPA {fmt_gpa(x['gpa'])}")
        for k in ("kontrakt", "trimestr"):
            if fl[k]:
                det.append(f"{FLAG_ICON[k]} {fmt_money(x['pays'][k]['debt'])}")
        badge = f"🔴 {sum(fl.values())} · " if v == "prob" and sum(fl.values()) >= 3 else ""
        lines.append(f"• {badge}<b>{esc(st['full_name'])}</b> · {esc(st.get('group_name') or '—')} — {'; '.join(det)}")
    parts = split_message("\n".join(lines) + "\n\n📥 Shu ro'yxatni hisobot sifatida yuklab olish:")
    for i, part in enumerate(parts):
        await cb.message.answer(part, reply_markup=export_kb(v, f) if i == len(parts) - 1 else None)


# ---------------------------------------------------------------- hisobot eksporti (Excel / PDF)
@router.message(Command("hisobot"))
async def cmd_report(message: Message, command: CommandObject) -> None:
    f = (command.args or "").strip()
    await message.answer(
        _course_line() + "📥 <b>Kurs holati hisoboti</b>" + (f" — {esc(f)}" if f else "") + "\n\n"
        "Umumiy ko'rsatkichlar, muammoli talabalar, davomati past talabalar, akademik qarzdorlar, kontrakt va "
        "trimestr qarzdorlari. Formatni tanlang:", reply_markup=export_kb("all", f))


@router.callback_query(ExpCb.filter())
async def cb_export(cb: CallbackQuery, callback_data: ExpCb) -> None:
    await cb.answer("Hisobot tayyorlanmoqda…")
    only = None if callback_data.s == "all" else callback_data.s
    data = await export.collect(callback_data.f)
    ext = "xlsx" if callback_data.fmt == "x" else "pdf"
    build = export.build_xlsx if ext == "xlsx" else export.build_pdf
    content = await asyncio.to_thread(build, data, only)
    title = export.SECTIONS.get(only, "Kurs holati") if only else "Kurs holati — to'liq hisobot"
    count = f" ({len(data[only])} ta)" if only else ""
    await cb.message.answer_document(
        BufferedInputFile(content, export.file_name(data, ext, only)),
        caption=f"{'📥' if ext == 'xlsx' else '📄'} {esc(title)}{count}\n{esc(export.title_line(data))} · "
                f"{fmt_dt(data['meta']['generated'])}")


# ---------------------------------------------------------------- fan va fakultet nomlarining tarjimalari
@router.message(Command("tarjimalar"))
async def cmd_terms(message: Message) -> None:
    items = await termsheet.collect()
    if not items:
        await message.answer("Kursda hali fan yoki fakultet nomlari yo'q — avval talabalar, jadval yoki baholarni yuklang.")
        return
    need = sum(1 for t in items if t["state"] == "TARJIMA KERAK")
    content = await asyncio.to_thread(termsheet.build_xlsx, items)
    await message.answer_document(
        BufferedInputFile(content, f"tarjimalar_{current_course() or 'kurs'}.xlsx"),
        caption=(f"🌐 <b>Fan va fakultet nomlarining tarjimalari</b>: {len(items)} ta nom\n"
                 f"Tarjimasi yo'q: <b>{need}</b> ta (sariq kataklar) — hozircha rus tilidagi ota-onalarga kirill "
                 "harflarida ko'rinadi.\n\nTo'ldirib, /import → «🌐 Tarjimalar» orqali qaytaring. Tarjimalar barcha "
                 "kurslar uchun umumiy."))


# ---------------------------------------------------------------- kurs koordinatorining ota-onalarga ko'rinadigan ismi
# ---------------------------------------------------------------- yuklangan fayllar: ro'yxat va o'chirish
class ImpDelCb(CallbackData, prefix="idl"):
    i: int
    ok: int = 0   # 0 — tasdiq so'raladi, 1 — o'chiriladi


@router.message(Command("yuklamalar"))
async def cmd_imports(message: Message) -> None:
    import imports
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from config import SUPERADMIN_IDS
    uid = message.from_user.id
    items = await imports.listing(uid, uid in SUPERADMIN_IDS, limit=15)
    if not items:
        await message.answer("Hali fayl yuklanmagan (yoki o'zingiz yuklagan fayl yo'q).")
        return
    kb = InlineKeyboardBuilder()
    lines = ["📂 <b>Yuklangan fayllar</b> — o'chirilsa, shu fayldan kelgan ma'lumotlar, ota-onalarga ketgan "
             "bildirishnoma va xabarlar ham o'chadi:", ""]
    for i, r in enumerate(items, 1):
        lines.append(f"{i}. {esc(r['file_name'] or '—')} · {esc(KIND_TITLES.get(r['kind'], r['kind']))} · "
                     f"{r['rows']} ta yozuv · {fmt_dt(r['uploaded_at'])}")
        if imports.can_delete(r, uid, uid in SUPERADMIN_IDS):
            kb.button(text=f"🗑 {i}. {(r['file_name'] or '')[:28]}", callback_data=ImpDelCb(i=r["id"]))
    kb.adjust(1)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(ImpDelCb.filter())
async def cb_import_delete(cb: CallbackQuery, callback_data: ImpDelCb) -> None:
    import imports
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from config import SUPERADMIN_IDS
    uid = cb.from_user.id
    r = await imports.get(callback_data.i)
    if not r or not imports.can_delete(r, uid, uid in SUPERADMIN_IDS):
        await cb.answer("Bu faylni o'chirib bo'lmaydi (allaqachon o'chirilgan yoki boshqa koordinator yuklagan).",
                        show_alert=True)
        return
    if not callback_data.ok:
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Ha, o'chirish", callback_data=ImpDelCb(i=r["id"], ok=1))
        await cb.answer()
        if r["kind"] == "students":
            im = await imports.students_impact(r)
            if not im["students"]:
                await cb.message.answer(f"«{esc(r['file_name'] or '—')}» dagi talabalarning hammasi keyingi fayllarda qayta "
                                        "kelgan — o'chiriladigan talaba yo'q. Faqat yuklamalar ro'yxatidan olib tashlanadi.",
                                        reply_markup=kb.as_markup())
                return
            await cb.message.answer(
                f"⚠️ «{esc(r['file_name'] or '—')}» — talabalar ro'yxati. O'chirilsa, shu fayl orqali kelgan "
                f"<b>{im['students']} ta talaba</b> va ularning barcha ma'lumotlari (davomat, baholar, to'lovlar, hujjatlar, "
                f"yozishmalar) o'chadi; <b>{im['parents']} ta ota-ona</b> ulardan uziladi. Keyingi fayllarda qayta kelgan "
                "talabalar qoladi. Buni qaytarib bo'lmaydi.", reply_markup=kb.as_markup())
            return
        await cb.message.answer(f"«{esc(r['file_name'] or '—')}» tizimdan o'chirilsinmi? {r['rows']} ta yozuv, ota-onalarga "
                                "ketgan bildirishnoma va xabarlar ham o'chadi. Buni qaytarib bo'lmaydi.",
                                reply_markup=kb.as_markup())
        return
    await cb.answer("O'chirilmoqda…")
    st = await imports.delete(cb.bot, r["id"], uid)
    await cb.message.edit_text(
        f"🗑 «{esc(r['file_name'] or '—')}» o'chirildi: " + (f"{st['students']} ta talaba, " if st.get("students") else "")
        + f"{st['rows']} ta yozuv, {st['notifications']} ta bildirishnoma, "
        f"Telegram'dan {st['messages']} ta xabar" + (f" ({st['messages_failed']} tasini Telegram o'chirishga ruxsat bermadi — "
                                                     "48 soatdan o'tgan)" if st["messages_failed"] else "") + ".")


@router.message(Command("koordinator"))
async def cmd_coordinator(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    # Guruhlari biriktirilgan koordinator — o'z ismi (faqat o'z guruhlari ota-onalariga); aks holda — kurs bo'yicha
    uid = message.from_user.id
    sfx = f":{uid}" if group_scope(uid) is not None else ""
    if not arg:
        name = await db.get_setting(f"coordinator_name{sfx}")
        phone = await db.get_setting(f"coordinator_phone{sfx}")
        await message.answer(
            "🧑‍🏫 <b>Ota-onalarga ko'rinadigan kurs koordinatori</b>"
            + (" (guruhlaringiz ota-onalariga)" if sfx else "") + "\n"
            + (f"Hozir: {esc(name or '—')} {fmt_phone(phone) if phone else ''}\n\n" if name or phone else "Hozir kiritilmagan.\n\n")
            + "O'zgartirish: <code>/koordinator N. Egamberdiyev +998 90 123 45 67</code>\n"
              "Telefon ixtiyoriy. Talabalar faylida «Kurs koordinatori» ustuni bo'lsa, o'sha talabalar uchun fayldagisi "
              "ko'rsatiladi.")
        return
    m = re.search(r"(\+?\d[\d\s\-()]{7,})$", arg)
    phone = normalize_phone(m.group(1)) if m else None
    name = (arg[:m.start()] if m else arg).strip(" ,;")
    if not name:
        await message.answer("Ism tushunilmadi. Masalan: <code>/koordinator N. Egamberdiyev +998 90 123 45 67</code>")
        return
    await db.set_setting(f"coordinator_name{sfx}", name)
    await db.set_setting(f"coordinator_phone{sfx}", phone or "")
    await message.answer(
        f"✅ Endi {'guruhlaringizdagi' if sfx else 'kursingizdagi'} ota-onalar farzand sahifasida va «Foydali ma'lumot» bo'limida shunday ko'radi:\n"
        f"🧑‍🏫 Kurs koordinatori: <b>{esc(name)}</b> {fmt_phone(phone) if phone else ''}\n\n"
        f"Rus tilidagi ota-onalarga kirillda: {esc(loc.translit_ru(name))}")
