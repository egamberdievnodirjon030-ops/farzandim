"""Ota-onalarga avtomatik xabarlar: darhol ogohlantirish, chegara ogohlantirishi, baholar, kunlik xulosa."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from config import (BACKUP_TIME, PAY_REMIND_DAYS, PAY_REMIND_TIME, DAILY_DIGEST_TIME, DIGEST_DAY_OFFSET, SEMESTER_START,
                    SUBJECT_WARN_MIN_LESSONS, SUBJECT_WARN_PERCENT)
import absence
import loc
import academic
from database import db
from keyboards import webapp_kb
from tenancy import current_course, central, use_course
from i18n import N_, tr, use_lang
from utils import (fmt_pairs, STATUS_ICON, STATUS_TEXT, esc, fmt_date, fmt_day_month, fmt_dt, fmt_money, fmt_num, normalize_text, now, now_iso,
                   parse_date, semester_start, today)

log = logging.getLogger(__name__)


async def _remember(chat_id: int, msg) -> None:
    """Fayl yuklash natijasida ketgan xabar — fayl o'chirilsa Telegram chatidan ham o'chirish uchun."""
    from tenancy import current_import
    imp = current_import.get()
    if imp is not None and getattr(msg, "message_id", None):
        await db.execute("INSERT INTO sent_messages (import_id, chat_id, message_id, sent_at) VALUES (?, ?, ?, ?)",
                         (imp, chat_id, msg.message_id, now_iso()))


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    """Xabar yuboradi; bot bloklangan bo'lsa ota-onani nofaol qiladi. Telegram limitiga rioya qiladi."""
    for attempt in range(2):
        try:
            msg = await bot.send_message(chat_id, text, **kwargs)
            await _remember(chat_id, msg)
            await asyncio.sleep(0.04)  # ~25 xabar/soniya — Telegram chegarasidan past
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            await db.set_parent_active(chat_id, False)
            return False
        except TelegramBadRequest as e:
            log.warning("Xabar yuborilmadi %s: %s", chat_id, e)
            return False
    return False


async def safe_send_document(bot: Bot, chat_id: int, file_id: str, caption: str):
    """Hujjat (file_id) yuboradi; yuborilgan xabarni yoki None qaytaradi."""
    for _ in range(2):
        try:
            msg = await bot.send_document(chat_id, file_id, caption=caption)
            await asyncio.sleep(0.05)
            return msg
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            await db.set_parent_active(chat_id, False)
            return None
        except TelegramBadRequest as e:
            log.warning("Hujjat yuborilmadi %s: %s", chat_id, e)
            return None
    return None


# ---------------------------------------------------------------- darhol xabar: dars qoldirildi
async def send_each(bot: Bot, pids, build, sid: int | None = None, kind: str | None = None,
                    sub: str | None = None) -> int:
    """Har bir ota-onaga o'z tilida: build() joriy tilda matn (yoki matnlar ro'yxati) qaytaradi.
    Bir xil tildagi ota-onalar uchun matn bir marta tuziladi. sid va kind berilsa, xabar ostidagi
    «📱 Ilovada ochish» tugmasi Web App'da aynan shu farzandning tegishli bo'limini ochadi.

    Ilova rejimida (appmode.APP_MODE) botga faqat qisqa xabar ketadi (sub — uning turi: «davomatda o'zgarish»,
    «baholarda yangilanish»…); to'liq matn ilovadagi bildirishnomalar markazida saqlanadi va ilova ochiq bo'lsa
    darhol ko'rinadi (live.publish)."""
    import appmode
    import live
    course = current_course() or "_"
    if kind and sid:
        route = f"/go/{kind}/{course}/{sid}"
    elif kind in ("digest", "link"):
        route = "/"
    else:
        route = "/notifications"
    short = appmode.APP_MODE and sub in appmode.SHORT
    st = await db.get_student(sid) if (short and sid) else None
    sent, cache = 0, {}
    for pid in pids:
        lang = await central.get_lang(pid) or "uz"
        if lang not in cache:
            with use_lang(lang):
                full = await build()
                cache[lang] = (full, appmode.short_text(sub, st) if short else None, webapp_kb(route))
        full, brief, kb = cache[lang]
        fulls = [full] if isinstance(full, str) else list(full)
        if not fulls:
            continue
        ok_any = False
        for t in ([brief] if brief else fulls):
            ok_any = await safe_send(bot, pid, t, reply_markup=kb) or ok_any
        if ok_any:
            sent += 1
            for t in fulls:
                await db.add_notification(pid, t, sid, kind)  # Web App'dagi bildirishnomalar markazi (to'liq matn)
            live.publish(pid, {"type": "notification", "kind": kind, "course": course, "student_id": sid,
                               "text": brief or fulls[0][:300], "route": route})
    return sent


async def notify_new_absences(bot: Bot) -> int:
    rows = await db.unnotified_absences()
    if not rows:
        return 0
    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in rows:
        grouped[(r["student_id"], r["date"])].append(r)
    sent = 0
    for (sid, d), items in grouped.items():
        parents = await db.parents_of_student(sid, "notify_instant")
        if not parents:
            continue
        first = items[0]

        async def build(first=first, d=d, items=items) -> str:
            lines = [tr("🔔 <b>Davomat xabari</b>") + f"\n\n👨‍🎓 {esc(loc.student_name(first))} ({esc(first['group_name'] or '')})",
                     f"📅 {fmt_date(d)}"]
            for a in items:
                lines.append(f"{STATUS_ICON[a['status']]} " + tr("{p}-juftlik", p=a['pair'])
                             + f" — {esc(loc.term(a['subject']))}: <b>{tr(STATUS_TEXT[a['status']])}</b>"
                             + ("\n     " + tr("O'qituvchi: {t}", t=esc(" ".join(a['teacher'].split())))
                                if a.get('teacher') else ""))
            lines.append("\n" + tr("Savol bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozishingiz mumkin."))
            return "\n".join(lines)
        sent += await send_each(bot, parents, build, sid, "att", "att_new")
    await db.mark_notified([r["id"] for r in rows])
    return sent


async def notify_subject_stats(bot: Bot, subject: str, changes: list, unit_hours: float) -> int:
    """Fan bo'yicha HEMIS statistikasi: sababsiz qoldirishlar ko'paygan talabalar ota-onalariga xabar."""
    sent = 0
    for sid, prev, new in changes:
        parents = await db.parents_of_student(sid, "notify_instant")
        if not parents:
            continue
        st = await db.get_student(sid)
        un = max(new["absent"] - new["excused"], 0)
        was = max(prev["absent"] - prev["excused"], 0) if prev else 0

        async def build(st=st, un=un, was=was, new=new) -> str:
            total = (new["attended"] or 0) + (new["absent"] or 0)
            pct = round(100 * (new["attended"] or 0) / total) if total else None
            return (tr("📚 <b>Fan bo'yicha davomat</b>") + f"\n\n👨‍🎓 {esc(loc.student_name(st))} ({esc(st['group_name'] or '')})\n"
                    + tr("Fan: {s}", s=esc(loc.term(subject))) + "\n"
                    + tr("Sababsiz qoldirilgan: {n}", n=fmt_pairs(un * unit_hours))
                    + (f" (+{fmt_pairs((un - was) * unit_hours)})" if was and un > was else "")
                    + (("\n" + tr("Fan bo'yicha davomat: {p}%", p=pct)) if pct is not None else ""))
        sent += await send_each(bot, parents, build, sid, "att", "att_new")
    return sent


async def notify_present_marks(bot: Bot) -> int:
    """Real vaqtdagi davomat (Manage integratsiyasi): o'qituvchi talabani «darsga keldi» deb belgiladi.
    Har bir dars — ota-ona ilovasidagi bildirishnomalar markazida alohida «Yo'qlama» kartochkasi (Manage talabaga
    ko'rsatadigan kabi). Telegram'ga yuborilmaydi — kuniga bir necha dars bo'ladi; qoldirilgan dars esa Telegram'ga
    ham boradi (notify_new_absences)."""
    import live
    rows = await db.fetchall(
        """SELECT a.*, s.full_name, s.full_name_cyr, s.group_name FROM attendance a JOIN students s ON s.id = a.student_id
           WHERE a.notified = 0 AND a.status = 'keldi' ORDER BY a.date, a.pair""")
    if not rows:
        return 0
    course = current_course() or "_"
    n = 0
    for r in rows:
        sid = r["student_id"]
        for pid in await db.parents_of_student(sid, "notify_instant"):
            with use_lang(await central.get_lang(pid) or "uz"):
                teacher = " ".join((r.get("teacher") or "").split())
                subj = esc(loc.term(r["subject"]))
                body = (tr("Professor-o'qituvchi {t} «{s}» fanidan {p}-juftlikda farzandingizni darsga keldi deb belgiladi.",
                           t=esc(teacher), s=subj, p=r["pair"]) if teacher else
                        tr("«{s}» fanidan {p}-juftlikda farzandingiz darsga keldi deb belgilandi.", s=subj, p=r["pair"]))
                text = (tr("✅ <b>Yo'qlama</b>") + f"\n\n👨‍🎓 {esc(loc.student_name(r))} ({esc(r['group_name'] or '')})\n"
                        + f"📅 {fmt_date(r['date'])}\n{body}")
            await db.add_notification(pid, text, sid, "present")
            live.publish(pid, {"type": "notification", "kind": "present", "course": course, "student_id": sid,
                               "text": text[:300], "route": f"/go/att/{course}/{sid}"})
            n += 1
    await db.mark_notified([r["id"] for r in rows])
    return n


# ---------------------------------------------------------------- chegara ogohlantirishlari
async def check_thresholds(bot: Bot, student_ids, notify: bool = True) -> tuple[int, list[dict]]:
    """Dars qoldirish chegaralari (18/36/54/74 soat) va fan bo'yicha ulush.
    Bir nechta chegara birdan o'tilsa, ota-onaga faqat eng yuqorisi haqida bitta xabar boradi.
    Qaytaradi: (yuborilgan xabarlar soni, yangi chegaraga yetgan talabalar ro'yxati — kurs koordinatori uchun).
    Hisob va belgilash bir marta bajariladi, matn esa har bir ota-onaning tilida tuziladi."""
    t = today()
    d1, d2 = min(semester_start(), t).isoformat(), t.isoformat()
    sent, crossings = 0, []
    for sid in student_ids:
        st = await db.get_student(sid)
        sm = await absence.summary(sid) if st else None
        if not sm:
            continue
        h = sm["counted"]
        reached = [i for i, lvl in enumerate(absence.LEVELS) if h >= lvl]
        new = [i for i in reached if not await db.warning_sent(sid, "total", f"{SEMESTER_START}:{absence.LEVELS[i]}")]
        if new:
            crossings.append({"sid": sid, "name": st["full_name"], "group": st.get("group_name") or "",
                              "hours": h, "level": max(new)})
            for i in reached:
                await db.mark_warning(sid, "total", f"{SEMESTER_START}:{absence.LEVELS[i]}")
        subj_warn = []  # fan bo'yicha ulush — faqat kunlik davomat yozuvlari bo'lsa
        for s in await db.subject_stats(sid, d1, d2):
            if s["total"] < SUBJECT_WARN_MIN_LESSONS:
                continue
            share = 100 * s["kelmadi"] / s["total"]
            key = f"{SEMESTER_START}:{s['subject']}"
            if share >= SUBJECT_WARN_PERCENT and not await db.warning_sent(sid, "subject", key):
                subj_warn.append((s, share))
                await db.mark_warning(sid, "subject", key)
        if not (new or subj_warn) or not notify:
            continue

        async def build(st=st, sm=sm, h=h, new=new, subj_warn=subj_warn) -> str:
            parts = []
            if new:
                top = max(new)
                parts.append(
                    tr("Semestr boshidan buyon {label}: <b>{h}</b>", label=tr(absence.COUNTED_LABEL), h=fmt_pairs(h))
                    + f" <i>({absence.source_note(sm)})</i>.\n\n"
                    + tr("Universitet ichki tartibiga ko'ra {n} va undan ko'p dars qoldirilganda "
                         "qo'llaniladigan chora: <b>{a}</b>.", n=fmt_pairs(absence.LEVELS[top]), a=esc(absence.action_for(top))))
                if len(new) > 1:
                    lower = ", ".join(tr("{n} — {a}", n=fmt_pairs(absence.LEVELS[i]), a=esc(absence.action_for(i)))
                                      for i in new if i != top)
                    parts.append(tr("Bundan oldingi chegara(lar) ham o'tilgan: {v}.", v=lower))
                if top + 1 < len(absence.LEVELS):
                    parts.append(tr("Keyingi chegara: {n} — {a}.", n=fmt_pairs(absence.LEVELS[top + 1]),
                                    a=esc(absence.action_for(top + 1))))
                else:
                    parts.append(tr("❗️ Bu eng oxirgi chegara."))
            for s, share in subj_warn:
                parts.append(tr("«{subj}» fanidan {n} ta darsning {k} tasi ({p}%) sababsiz qoldirilgan.",
                                subj=esc(loc.term(s['subject'])), n=s['total'], k=s['kelmadi'], p=round(share)))
            last = bool(new) and max(new) == len(absence.LEVELS) - 1
            closing = (tr("Iltimos, zudlik bilan kurs koordinatori bilan bog'laning.") if last else
                       tr("Iltimos, farzandingiz bilan suhbatlashing. Savollar bo'lsa, «✉️ Kurs koordinatoriga savol» "
                          "bo'limi orqali yozing."))
            return (tr("⚠️ <b>Dars qoldirish bo'yicha ogohlantirish</b>") + f"\n\n👨‍🎓 {esc(loc.student_name(st))} "
                    f"({esc(st.get('group_name') or '')})\n\n" + "\n\n".join(parts) + "\n\n" + closing)
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_warn"), build, sid, "att", "att_warn")
    return sent, crossings


async def notify_stats_changes(bot: Bot, changes: list[tuple[int, dict | None, dict]], skip: set[int]) -> int:
    """HEMIS statistikasi yangilanganda: oldingi holatdan beri qoldirilgan soatlar ko'paygan bo'lsa xabar."""
    sent = 0
    for sid, prev, new in changes:
        if sid in skip or not prev:
            continue
        a, b = absence.stats_hours(prev), absence.stats_hours(new)
        delta = b["counted"] - a["counted"]
        if delta <= 0:
            continue
        st = await db.get_student(sid)
        if not st:
            continue
        i = absence.level_index(b["counted"])

        async def build(st=st, prev=prev, new=new, b=b, delta=delta, i=i) -> str:
            lines = [tr("📊 <b>Davomat yangilandi</b>") + " <i>" + tr("(HEMIS, {d} holatiga)", d=fmt_date(new['as_of'], False))
                     + "</i>\n",
                     f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})\n",
                     (tr("{d} dan beri yana <b>{h}</b> dars qoldirilgan.", d=fmt_date(prev['as_of'], False), h=fmt_pairs(delta))
                      if absence.ABSENCE_COUNT_EXCUSED else
                      tr("{d} dan beri yana <b>{h}</b> dars sababsiz qoldirilgan.", d=fmt_date(prev['as_of'], False),
                         h=fmt_pairs(delta))),
                     tr("Semestr boshidan jami: {h}", h=fmt_pairs(b['counted']))
                     + (", " + tr("davomat {p}%", p=round(b['percent'])) if b["percent"] is not None else "") + "."]
            if i + 1 < len(absence.LEVELS):
                lines.append(tr("Keyingi chegara: {n} — {a}, qolgan: {left}.", n=fmt_pairs(absence.LEVELS[i + 1]),
                                a=esc(absence.action_for(i + 1)), left=fmt_pairs(absence.LEVELS[i + 1] - b['counted'])))
            return "\n".join(lines)
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_instant"), build, sid, "att", "att_change")
    return sent


# ---------------------------------------------------------------- sababsiz qoldirishlar kamaydi
async def notify_absence_decrease(bot: Bot, before: dict[int, dict | None], after: dict[int, dict | None],
                                  notify: bool = True) -> tuple[int, list[dict]]:
    """Yangi davomat faylida sababsiz qoldirishlar kamaygan bo'lsa (masalan, bir qismi sababli deb topilgan) va talaba
    avval biror chegaraga yetgan bo'lsa — ota-onaga xabar: avval nima talab qilingan edi, qancha sababli deb topildi,
    endi qancha va qaysi chegara amalda. Chegaradan pastga tushgan bo'lsa — keyin yana oshganda qayta ogohlantiriladi.
    Qaytaradi: (yuborilgan xabarlar, kurs koordinatori uchun ro'yxat)."""
    sent, drops = 0, []
    for sid, a in after.items():
        b = before.get(sid)
        if not a or not b or b["counted"] - a["counted"] < 1:
            continue
        lb, la = absence.level_index(b["counted"]), absence.level_index(a["counted"])
        for i in range(la + 1, len(absence.LEVELS)):  # pasaygan chegaralar — qayta oshsa yana xabar beriladi
            await db.unmark_warning(sid, "total", f"{SEMESTER_START}:{absence.LEVELS[i]}")
        if lb < 0:
            continue  # avval hech qaysi chegaraga yetmagan — xabar shart emas
        excused_up = max(0.0, (a.get("excused") or 0) - (b.get("excused") or 0))
        st = await db.get_student(sid)
        if not st:
            continue
        drops.append({"sid": sid, "name": st["full_name"], "group": st.get("group_name") or "", "old": b["counted"],
                      "new": a["counted"], "old_level": lb, "new_level": la, "excused": excused_up})
        if not notify:
            continue

        async def build(st=st, a=a, b=b, lb=lb, la=la, excused_up=excused_up):
            lines = [tr("✅ <b>Davomat o'zgardi</b>") + f" <i>({absence.source_note(a)})</i>\n",
                     f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})", ""]
            lines.append(tr("Farzandingiz {n} va undan ko'p dars qoldirgani uchun «{a}» talab qilingan edi.",
                            n=fmt_pairs(absence.LEVELS[lb]), a=esc(absence.action_for(lb))))
            if excused_up >= 1:
                lines.append(tr("Qoldirilgan darslarning {e} sababli deb topildi.",
                                e=fmt_pairs(min(excused_up, b["counted"] - a["counted"]))))
            else:
                lines.append(tr("Davomat ma'lumotlari tuzatildi."))
            lines.append(tr("Sababsiz qoldirilgan darslar: {old} → <b>{new}</b>.", old=fmt_pairs(b["counted"]),
                            new=fmt_pairs(a["counted"])))
            if la < 0:
                lines.append("\n" + tr("Endi bu hech qaysi chegaradan past — «{a}» talab qilinmaydi.",
                                       a=esc(absence.action_for(lb))))
            elif la < lb:
                lines.append("\n" + tr("Endi amaldagi chegara: {n} — {a}.", n=fmt_pairs(absence.LEVELS[la]),
                                       a=esc(absence.action_for(la))))
            else:
                lines.append("\n" + tr("Chegara o'zgarmadi: {n} — {a}.", n=fmt_pairs(absence.LEVELS[la]),
                                       a=esc(absence.action_for(la))))
            lines.append(tr("Savol bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozishingiz mumkin."))
            return "\n".join(lines)
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_warn"), build, sid, "att", "att_good")
    return sent, drops


# ---------------------------------------------------------------- kontrakt to'lovi
PAY_TITLES = {"kontrakt": N_("Kontrakt"), "trimestr": N_("Trimestr")}


async def _pay_text(st: dict, kind: str, new: dict, prev: dict | None, reminder_days: int | None = None) -> str:
    """«💰 To'lov bo'yicha eslatma»: qarz, muddat, o'zgarish, ma'lumot yangilangan vaqt (joriy tilda)."""
    dl = parse_date(await db.get_setting(f"deadline:{kind}"))
    lines = [tr("💰 <b>To'lov bo'yicha eslatma</b>") + "\n",
             f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})", ""]
    lines.append(tr("{kind} bo'yicha <b>{sum}</b> qarzdorlik mavjud.", kind=tr(PAY_TITLES[kind]), sum=fmt_money(new["debt"])))
    if dl:
        left = (dl - today()).days
        tail = (tr(" (muddat o'tgan)") if left < 0 else tr(" (bugun)") if left == 0 else
                tr(" ({n} kun qoldi)", n=left) if reminder_days is not None else "")
        lines.append(tr("To'lov muddati: <b>{d}</b>", d=fmt_day_month(dl)) + tail + ".")
    if new.get("contract"):
        lines.append(tr("Shartnoma summasi: {c}, to'langan: {p}", c=fmt_money(new["contract"]), p=fmt_money(new.get("paid")))
                     + (f" ({new['percent']:g}%)" if new.get("percent") is not None else ""))
    if prev and reminder_days is None:
        way = tr("kamaydi") if new["debt"] < prev["debt"] else tr("oshdi")
        lines.append(tr("{d} dagi ma'lumotga nisbatan qarz {way}: {sum}", d=fmt_date(prev["as_of"], False), way=way,
                        sum=fmt_money(abs(new["debt"] - prev["debt"]))))
    lines.append(tr("🕐 Ma'lumot {t} da yangilangan (buxgalteriya hisoboti {d} holatiga).",
                    t=fmt_dt(new.get("imported_at") or now_iso()), d=fmt_date(new["as_of"], False)))
    lines.append("\n" + tr("Batafsil: farzand sahifasi → «💰 Moliyaviy qarzdorlik». Savollar bo'lsa, «✉️ Kurs "
                           "koordinatoriga savol» bo'limi orqali yozing."))
    return "\n".join(lines)


async def notify_payments(bot: Bot, changes: list[tuple[int, dict | None, dict]]) -> int:
    """Qarz paydo bo'lsa yoki o'zgarsa — eslatma; qarz to'liq yopilsa — tasdiq. O'zgarmagan bo'lsa — xabar yo'q."""
    sent = 0
    for sid, prev, new in changes:
        kind = new.get("kind") or "kontrakt"
        old_debt = prev["debt"] if prev else None
        st = await db.get_student(sid)
        if not st:
            continue
        if new["debt"] > 0 and (old_debt is None or abs(new["debt"] - old_debt) >= 1):
            async def build(st=st, kind=kind, new=new, prev=prev):
                return await _pay_text(st, kind, new, prev)
        elif new["debt"] <= 0 and old_debt and old_debt > 0:
            async def build(st=st, kind=kind, new=new):
                return (tr("✅ <b>{kind} to'lovi</b> <i>({d} holatiga)</i>", kind=tr(PAY_TITLES[kind]),
                           d=fmt_date(new["as_of"], False))
                        + f"\n\n👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})\n\n"
                        + tr("Bu bo'yicha qarzdorlik to'liq yopildi. Rahmat!"))
        else:
            continue
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_pay"), build, sid, "pay", "pay")
    return sent


async def send_payment_reminders(bot: Bot, day: date) -> int:
    """To'lov muddatidan PAY_REMIND_DAYS kun oldin qarzdorlarning ota-onalariga eslatma (har biri bir marta)."""
    sent = 0
    for kind in PAY_TITLES:
        dl = parse_date(await db.get_setting(f"deadline:{kind}"))
        if not dl:
            continue
        left = (dl - day).days
        key = f"remind:{kind}:{dl.isoformat()}:{left}"
        if left not in PAY_REMIND_DAYS or await db.get_setting(key):
            continue
        await db.set_setting(key, now_iso())
        for sid, p in (await db.bulk_latest_payments(kind)).items():
            if p["debt"] <= 0:
                continue
            st = await db.get_student(sid)
            if not st:
                continue

            async def build(st=st, kind=kind, p=p, left=left):
                return await _pay_text(st, kind, {**p, "kind": kind}, None, reminder_days=left)
            sent += await send_each(bot, await db.parents_of_student(sid, "notify_pay"), build, sid, "pay", "pay_remind")
    return sent


# ---------------------------------------------------------------- akademik qarzdorlik («aqlli» ogohlantirish)
def academic_keys(results: list[dict]) -> dict[tuple, dict]:
    return {(str(r["semester"]), normalize_text(r["subject"])): r for r in results}


async def notify_academic(bot: Bot, before: dict[int, dict], after: dict[int, dict]) -> int:
    """Akademik qarzdorlar ro'yxati bo'yicha: yangi qarz — «Muhim xabar», yopilsa — «Yaxshi xabar»."""
    sent = 0
    for sid, now_map in after.items():
        old_map = before.get(sid, {})
        new_debts = [r for k, r in now_map.items() if r["debt"] and not (old_map.get(k) or {}).get("debt")]
        cleared = [r for k, r in now_map.items() if not r["debt"] and (old_map.get(k) or {}).get("debt")]
        if not new_debts and not cleared:
            continue
        st = await db.get_student(sid)
        total = sum(1 for r in now_map.values() if r["debt"])

        async def build(st=st, new_debts=new_debts, cleared=cleared, total=total):
            head = f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})"
            texts = []
            if new_debts:
                lines = [tr("⚠️ <b>Muhim xabar</b>") + "\n", head, ""]
                for r in new_debts:
                    lines.append(tr("Farzandingiz «{subj}» fanidan 60 balldan past natija qayd etdi.",
                                    subj=esc(loc.term(r["subject"]))) + "\n"
                                 + tr("Natija: <b>{score}/100 → «2»</b>", score=fmt_num(r["score"])))
                lines.append(tr("❗ Akademik qarzdorlik yuzaga kelgan.") if len(new_debts) == 1 else
                             tr("❗ {n} ta fandan akademik qarzdorlik yuzaga kelgan.", n=len(new_debts)))
                lines.append("\n" + tr("Jami akademik qarz: {n} ta fan. Batafsil: farzand sahifasi → «📚 Akademik "
                                       "qarzdorlik». Qayta topshirish tartibi bo'yicha kurs koordinatoriga murojaat qiling.",
                                       n=total))
                texts.append("\n".join(lines))
            if cleared:
                lines = [tr("✅ <b>Yaxshi xabar</b>") + "\n", head, ""]
                for r in cleared:
                    lines.append(tr("«{subj}» fanidan akademik qarzdorlik yopildi: {score}/100 → «{grade}».",
                                    subj=esc(loc.term(r["subject"])), score=fmt_num(r["score"]), grade=r["grade"]))
                lines.append("\n" + (tr("Qolgan akademik qarz: {n} ta fan.", n=total) if total
                                     else tr("Akademik qarzdorlik qolmadi.")))
                texts.append("\n".join(lines))
            return texts
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_warn"), build, sid, "acad", "acad")
    return sent


# ---------------------------------------------------------------- HEMIS akademik qarzdorlar ro'yxati
def hemis_debt_keys(rows: list[dict]) -> dict[tuple, dict]:
    return {(str(r.get("semester") or ""), normalize_text(r["subject"])): r for r in rows}


def debt_line(r: dict) -> str:
    """«• Asosiy chet tili III — 3-semestr, 4 kredit» (joriy tilda)."""
    parts = []
    if r.get("semester"):
        parts.append(tr("{n}-semestr", n=r["semester"]))
    if r.get("credits"):
        parts.append(tr("{n} kredit", n=fmt_num(r["credits"])))
    return f"• {esc(loc.term(r['subject']))}" + (f" — {', '.join(parts)}" if parts else "")


async def notify_acad_list(bot: Bot, before: dict[int, dict], after: dict[int, dict]) -> int:
    """HEMIS ro'yxati yangilanganda: yangi qarzdor fanlar — «Muhim xabar», ro'yxatdan chiqqan fanlar — «Yaxshi xabar»."""
    import academic
    sent = 0
    for sid in set(before) | set(after):
        old_map, now_map = before.get(sid, {}), after.get(sid, {})
        new_debts = [r for k, r in now_map.items() if k not in old_map]
        cleared = [r for k, r in old_map.items() if k not in now_map]
        if not new_debts and not cleared:
            continue
        st = await db.get_student(sid)
        if not st:
            continue
        total = len((await academic.summary(sid))["debts"])

        async def build(st=st, new_debts=new_debts, cleared=cleared, total=total):
            head = f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '')})"
            texts = []
            if new_debts:
                lines = [tr("⚠️ <b>Muhim xabar</b>") + "\n", head, "",
                         tr("HEMIS akademik qarzdorlar ro'yxatiga ko'ra farzandingizda quyidagi fanlardan akademik qarz bor:")]
                lines += [debt_line(r) for r in new_debts]
                lines.append("\n" + tr("Jami akademik qarz: {n} ta fan. Qayta topshirish tartibi bo'yicha kurs "
                                       "koordinatoriga murojaat qiling.", n=total))
                texts.append("\n".join(lines))
            if cleared:
                lines = [tr("✅ <b>Yaxshi xabar</b>") + "\n", head, "",
                         tr("Quyidagi fanlardan akademik qarzdorlik yopildi (HEMIS ro'yxatida endi yo'q):")]
                lines += [debt_line(r) for r in cleared]
                lines.append("\n" + (tr("Qolgan akademik qarz: {n} ta fan.", n=total) if total
                                     else tr("Akademik qarzdorlik qolmadi.")))
                texts.append("\n".join(lines))
            return texts
        sent += await send_each(bot, await db.parents_of_student(sid, "notify_warn"), build, sid, "acad", "acad")
    return sent


# ---------------------------------------------------------------- yangi baholar
async def notify_grades(bot: Bot, changed: list[dict]) -> int:
    by_student: dict[int, list[dict]] = defaultdict(list)
    for g in changed:
        by_student[g["student_id"]].append(g)
    sent = 0
    for sid, items in by_student.items():
        parents = await db.parents_of_student(sid, "notify_instant")
        if not parents:
            continue
        st = await db.get_student(sid)

        async def build(st=st, items=items):
            lines = [tr("📝 <b>Yangi baholar</b>") + f"\n\n👨‍🎓 {esc(loc.student_name(st))} ({esc(st['group_name'] or '')})"]
            for g in items[:25]:
                score = fmt_num(g["score"]) + (f"/{fmt_num(g['max_score'])}" if g.get("max_score") else "")
                if academic.is_total(g):
                    gr = academic.five_point(g["score"])
                    score += f" → «{gr}»"
                lines.append(f"📚 {esc(loc.term(g['subject']))} — {esc(loc.term(g['control_type']))}: <b>{score}</b>")
            if len(items) > 25:
                lines.append(tr("… va yana {n} ta. To'liq ro'yxat «📝 Baholar» bo'limida.", n=len(items) - 25))
            return "\n".join(lines)
        sent += await send_each(bot, parents, build, sid, "grade", "grade")
    return sent


# ---------------------------------------------------------------- yangi bog'lanishlar
async def notify_links(bot: Bot, pairs: list[tuple[int, int]]) -> int:
    by_parent: dict[int, list[int]] = defaultdict(list)
    for pid, sid in pairs:
        by_parent[pid].append(sid)
    sent = 0
    for pid, sids in by_parent.items():
        names = []
        for sid in sids:
            st = await db.get_student(sid)
            if st:
                names.append(f"• {esc(loc.student_name(st))} ({esc(st['group_name'] or '')})")

        async def build(names=names):
            return (tr("🔗 Telefon raqamingiz universitet bazasida topildi va quyidagi farzand(lar)ingiz botga bog'landi:")
                    + "\n" + "\n".join(names) + "\n\n"
                    + tr("Endi ularning davomati va jadvalini kuzatishingiz mumkin."))
        sent += await send_each(bot, [pid], build, kind="link", sub="link")
    return sent


# ---------------------------------------------------------------- kunlik xulosa
async def send_daily_digest(bot: Bot, d: date) -> int:
    sent = 0
    for pid in await db.parents_for_digest():
        children = []
        for st in await db.parent_children(pid):
            recs = await db.attendance_between(st["id"], d.isoformat(), d.isoformat())
            if recs:
                children.append((st, recs))
        if not children:
            continue

        async def build(children=children):
            blocks = []
            for st, recs in children:
                attended = sum(r["status"] in ("keldi", "kechikdi") for r in recs)
                lines = [f"👨‍🎓 <b>{esc(loc.student_name(st))}</b>: "
                         + tr("{n} ta darsdan {a} tasida qatnashdi", n=len(recs), a=attended)]
                for r in recs:
                    if r["status"] != "keldi":
                        lines.append(f"   {STATUS_ICON[r['status']]} " + tr("{p}-juftlik", p=r["pair"])
                                     + f", {esc(loc.term(r['subject']))} — {tr(STATUS_TEXT[r['status']])}")
                if attended == len(recs) and not any(r["status"] == "kechikdi" for r in recs):
                    lines[0] += " ✅"
                blocks.append("\n".join(lines))
            return tr("🌙 <b>Kunlik xulosa — {d}</b>", d=fmt_date(d)) + "\n\n" + "\n\n".join(blocks)
        sent += await send_each(bot, [pid], build, kind="digest", sub="digest")
    return sent


async def scheduler_loop(bot: Bot) -> None:
    """Har 30 soniyada tekshiradi; belgilangan vaqtdan keyin kuniga bir marta kunlik xulosani yuboradi."""
    hh, mm = (int(x) for x in DAILY_DIGEST_TIME.split(":"))
    while True:
        try:
            current = now()
            target = current.replace(hour=hh, minute=mm, second=0, microsecond=0)
            day = current.date().isoformat()
            bh, bm = (int(x) for x in BACKUP_TIME.split(":"))
            if (db.multi and current >= current.replace(hour=bh, minute=bm, second=0, microsecond=0)
                    and await central.get_meta("last_backup_day") != day):
                await central.set_meta("last_backup_day", day)  # kuniga bir marta
                try:
                    import backup
                    info = await backup.make_backup()
                    await backup.send(bot, info)
                except Exception:
                    log.exception("Tungi zaxira nusxa olinmadi")
            rh, rm = (int(x) for x in PAY_REMIND_TIME.split(":"))
            for key in db.keys():  # har bir kurs — o'z bazasi, o'z ota-onalari
                with use_course(key):
                    if target <= current < target + timedelta(hours=3) and await db.get_setting("last_digest") != day:
                        await db.set_setting("last_digest", day)
                        n = await send_daily_digest(bot, current.date() - timedelta(days=DIGEST_DAY_OFFSET))
                        log.info("[%s] Kunlik xulosa yuborildi: %s ta ota-onaga", key, n)
                    if current >= current.replace(hour=rh, minute=rm, second=0, microsecond=0):
                        n = await send_payment_reminders(bot, current.date())
                        if n:
                            log.info("[%s] To'lov eslatmalari yuborildi: %s ta", key, n)
        except Exception:  # sikl to'xtab qolmasligi kerak
            log.exception("Rejalashtiruvchida xatolik")
        await asyncio.sleep(30)
