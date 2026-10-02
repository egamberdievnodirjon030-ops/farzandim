"""Ota-onaga ko'rsatiladigan hisobot matnlari (HTML formatida)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from config import GPA_MIN, SUBJECT_WARN_MIN_LESSONS, SUBJECT_WARN_PERCENT
import absence
import loc
import status
import trends
import academic
import individual
from database import db
from tenancy import current_course
from i18n import N_, tr
from utils import (fmt_pairs, GRANT, fmt_dt, fmt_gpa, fmt_limit, fmt_money, lesson_kind, STATUS_ICON, STATUS_TEXT, WEEKDAYS, doc_title, esc, fmt_date, fmt_num, fmt_phone, pair_time,
                   pct, semester_start, today)

LEGEND = N_("✅ qatnashdi · ❌ sababsiz · 🟡 sababli · ⏰ kechikdi · ⚪ ma'lumot kiritilmagan")


def student_header(st: dict) -> str:
    lines = [f"👨‍🎓 <b>{esc(loc.student_name(st))}</b>"]
    meta = []
    if st.get("group_name"):
        meta.append(tr("guruh: {g}", g=esc(st['group_name'])))
    if st.get("course"):
        meta.append(tr("{n}-kurs", n=st['course']))
    if meta:
        lines.append("👥 " + ", ".join(meta))
    if st.get("faculty"):
        lines.append(f"🏛 {esc(loc.term(st['faculty']))}")
    return "\n".join(lines)


def _sem_range() -> tuple[str, str]:
    t = today()
    s = min(semester_start(), t)
    return s.isoformat(), t.isoformat()


def lesson_label(lesson_type, subgroup=None) -> str:
    """«ma'ruza» → «Leksiya», «amaliy» + seminar raqami 2 → «Seminar 2»."""
    k = lesson_kind(lesson_type)
    label = tr("Leksiya") if k == "leksiya" else tr("Seminar") if k == "seminar" else esc(lesson_type or "")
    if subgroup and label:
        label += f" {esc(subgroup)}"
    return label


UPDATE_KEYS = {
    "fin_all": ("debts_k", "debts_t"),
    "att": ("attendance", "attendance_stats"), "sch": ("schedule", "elsched", "enroll"),
    "gr": ("grades",), "acad": ("grades",), "kontrakt": ("debts_k",), "trimestr": ("debts_t",),
    "all": ("attendance", "attendance_stats", "schedule", "elsched", "enroll", "grades", "debts_k", "debts_t",
            "students"),
}


async def last_update(*keys: str) -> str | None:
    vals = [v for v in [await db.get_setting(f"updated:{k}") for k in keys] if v]
    return max(vals) if vals else None


async def updated_note(section: str) -> str:
    ts = await last_update(*UPDATE_KEYS.get(section, (section,)))
    return "\n\n" + tr("🕐 Ma'lumot {dt} da yangilangan.", dt=fmt_dt(ts)) if ts else ""


async def student_card(st: dict) -> str:
    """«Umumiy holat» — farzandning barcha ko'rsatkichlari bir qarashda."""
    s = await status.student_status(st)
    head = student_header(st).split("\n")
    head[0] = tr("👨‍🎓 <b>Farzandim:</b> {name}", name=esc(loc.student_name(st)))
    head.append(tr("🧾 To'lov shakli: <b>{v}</b>", v=esc(tr(st['payment_form']))) if st.get("payment_form")
                else tr("🧾 To'lov shakli: ma'lumot yo'q"))
    parts = ["\n".join(head)]
    # talabalar fayli → guruh koordinatorining /koordinator i → kurs bo'yicha /koordinator
    tutor_name, tutor_phone = await db.coordinator_contact(st, current_course())
    if tutor_name or tutor_phone:
        parts.append(tr("🧑‍🏫 Kurs koordinatori: {v}",
                        v=f"{esc(loc.person(tutor_name))} {fmt_phone(tutor_phone)}".strip()))

    lines = ["\n" + tr("📋 <b>Umumiy holat</b>")]
    sm = s["attendance"]
    if sm:
        pct_txt = f"{round(sm['percent'])}%" if sm.get("percent") is not None else "—"
        lines.append(absence.level_icon(s['level']) + " " + tr(
            "Davomat: <b>{pct}</b> ({label}: {h})", pct=pct_txt, label=tr(absence.COUNTED_LABEL),
            h=fmt_pairs(sm['counted'])))
    else:
        lines.append(tr("⚪ Davomat: ma'lumot yo'q"))
    if s["results"]:
        lines.append(tr("📚 Akademik qarzdorlik: <b>{n} ta fan</b> — {names}", n=len(s['debts']),
                        names=esc(", ".join(loc.term(d["subject"]) for d in s["debts"]))) if s["debts"]
                     else tr("📚 Akademik qarzdorlik: yo'q ✅"))
    else:
        lines.append(tr("📚 Akademik qarzdorlik: ma'lumot yo'q"))
    for kind, icon, title in (("kontrakt", "💰", N_("Kontrakt qarzdorligi")), ("trimestr", "💳", N_("Trimestr qarzdorligi"))):
        p = s["pays"].get(kind)
        if p:
            state = f"<b>{fmt_money(p['debt'])}</b>" if p["debt"] > 0 else tr("mavjud emas ✅")
        elif kind == "kontrakt" and st.get("payment_form") == GRANT:
            state = tr("talab qilinmaydi (davlat granti)")
        elif await last_update(UPDATE_KEYS[kind][0]):
            state = tr("mavjud emas ✅")  # hisobot yuklangan, talaba qarzdorlar ro'yxatida yo'q
        else:
            state = tr("ma'lumot yo'q")
        lines.append(f"{icon} {tr(title)}: {state}")
    lines.append(tr("🎓 O'zlashtirish ko'rsatkichi (GPA): <b>{v}</b> / 5", v=fmt_gpa(s['gpa'])) if s["gpa"] is not None
                 else tr("🎓 O'zlashtirish ko'rsatkichi (GPA): ma'lumot yo'q"))
    if s["issues"]:
        lines.append("\n" + tr("⚠️ <b>E'tibor talab qiladigan masalalar: {n} ta</b>", n=len(s['issues'])))
        lines += [f"   • {esc(x)}" for x in s["issues"]]
    else:
        lines.append("\n" + tr("✅ E'tibor talab qiladigan masala yo'q"))
    parts.append("\n".join(lines))

    t = today()
    today_recs = await db.attendance_between(st["id"], t.isoformat(), t.isoformat())
    if today_recs:
        attended = sum(r["status"] in ("keldi", "kechikdi") for r in today_recs)
        parts.append("\n" + tr("📍 <b>Bugun:</b> {n} ta darsdan {a} tasida qatnashgan", n=len(today_recs), a=attended))
        for r in today_recs:
            if r["status"] in ("kelmadi", "sababli"):
                parts.append(f"   {STATUS_ICON[r['status']]} " + tr("{p}-juftlik", p=r['pair']) + f", {esc(loc.term(r['subject']))}")
    docs = await db.documents_for(st["id"])
    if docs:
        parts.append("\n" + tr("📄 Rasmiy hujjatlar: {n} ta — «📄 Hujjatlar» bo'limida", n=len(docs)))
    dyn = await trends.short_line(st)  # dinamika: davomat o'zgarishi va ball pasaygan fanlar
    if dyn:
        parts.append("\n" + dyn + " — " + tr("batafsil: «📈 Dinamika»"))
    ts = await last_update(*UPDATE_KEYS["all"])
    if ts:
        parts.append("\n" + tr("🕐 Oxirgi yangilanish: {dt}", dt=fmt_dt(ts)))
    parts.append("\n" + tr("Kerakli bo'limni tanlang 👇"))
    return "\n".join(parts)


async def _day_lines(st: dict, d: date, t: date) -> list[str]:
    recs = await db.attendance_between(st["id"], d.isoformat(), d.isoformat())
    by_pair = {r["pair"]: r for r in recs}
    sched = await individual.lessons_on(st, d)  # shaxsiy jadval: talaba o'qimaydigan tanlov/til darslarisiz
    sched_by_pair: dict[int, list[dict]] = {}
    for les in sched:
        sched_by_pair.setdefault(les["pair"], []).append(les)
    lines = []
    for p in sorted(set(by_pair) | set(sched_by_pair)):
        r, group = by_pair.get(p), sched_by_pair.get(p, [])
        s = group[0] if group else None
        src = r or s
        if r:
            icon, label = STATUS_ICON[r["status"]], tr(STATUS_TEXT[r["status"]])
        elif d > t:
            icon, label = "📘", tr("rejada")
        else:
            icon, label = "⚪", tr("ma'lumot hali kiritilmagan")
        tm = pair_time(p, s)
        lt = lesson_label(src.get("lesson_type"), (s or {}).get("subgroup"))  # «Leksiya» / «Seminar 2»
        kind = f" ({lt})" if lt else ""
        subj = (esc(loc.term(src["subject"])) if r or len(group) < 2
                else " / ".join(esc(loc.term(x["subject"])) for x in group))
        if s and s.get("_personal") and (not r or r["subject"] == s["subject"]):
            subj = "🎯 " + subj
        lines.append(f"{icon} " + tr("{p}-juftlik", p=p) + f"{' ' + tm if tm else ''} — {subj}{kind}: <i>{label}</i>")
    return lines


def _totals_block(tot: dict) -> str:
    if not tot["total"]:
        return tr("Bu davr uchun davomat ma'lumoti hali kiritilmagan.")
    attended = tot['keldi'] + tot['kechikdi']
    return (
        tr("📈 <b>Umumiy natija</b>") + "\n"
        + tr("Qayd etilgan darslar: {n}", n=tot['total']) + "\n"
        + tr("✅ Qatnashgan: {n} ({p})", n=attended, p=pct(attended, tot['total']))
        + (tr(", shundan kechikkan: {n}", n=tot['kechikdi']) if tot["kechikdi"] else "") + "\n"
        + tr("❌ Sababsiz qoldirilgan: {h}", h=fmt_pairs(tot['kelmadi_soat'])) + "\n"
        + tr("🟡 Sababli qoldirilgan: {h}", h=fmt_pairs(tot['sababli_soat']))
    )


async def day_report(st: dict, d: date) -> str:
    t = today()
    lines = await _day_lines(st, d, t)
    body = "\n".join(lines) if lines else tr("Bu kunda dars yo'q yoki ma'lumot hali kiritilmagan.")
    return f"{student_header(st)}\n\n📅 <b>{fmt_date(d)}</b>\n{body}\n\n<i>{tr(LEGEND)}</i>"


async def period_report(st: dict, d1: date, d2: date, title: str) -> str:
    t = today()
    d2 = min(d2, t) if d1 <= t else d2
    head = f"{student_header(st)}\n\n🗓 <b>{esc(title)}</b>: {fmt_date(d1, False)} — {fmt_date(d2, False)}"
    tot = await db.attendance_totals(st["id"], d1.isoformat(), d2.isoformat())

    if (d2 - d1).days <= 7:  # qisqa davr: har bir kun, har bir juftlik
        blocks = []
        d = d1
        while d <= d2:
            lines = await _day_lines(st, d, t)
            if lines:
                blocks.append(f"<b>{fmt_date(d)}</b>\n" + "\n".join(lines))
            d += timedelta(days=1)
        body = "\n\n".join(blocks) if blocks else tr("Bu davrda dars yoki davomat ma'lumoti topilmadi.")
        return f"{head}\n\n{body}\n\n{_totals_block(tot)}\n\n<i>{tr(LEGEND)}</i>"

    # uzun davr: umumiy natija + fanlar + qoldirilgan darslar
    parts = [head, _totals_block(tot)]
    subj = await db.subject_stats(st["id"], d1.isoformat(), d2.isoformat())
    if subj:
        parts.append(tr("📚 <b>Fanlar kesimida</b>") + "\n" + "\n".join(_subject_line(s) for s in subj))
    absences = await db.absences_between(st["id"], d1.isoformat(), d2.isoformat())
    if absences:
        parts.append(_absence_list(absences, limit=40))
    return "\n\n".join(parts)


def _subject_line(s: dict) -> str:
    attended = s["keldi"] + s["kechikdi"]
    warn = ""
    if s["total"] >= SUBJECT_WARN_MIN_LESSONS and 100 * s["kelmadi"] / s["total"] >= SUBJECT_WARN_PERCENT:
        warn = " ⚠️"
    return (f"• <b>{esc(loc.term(s['subject']))}</b>{warn}: {attended}/{s['total']} ({pct(attended, s['total'])})"
            + (f", ❌ {s['kelmadi']}" if s["kelmadi"] else "")
            + (f", 🟡 {s['sababli']}" if s["sababli"] else "")
            + (f", ⏰ {s['kechikdi']}" if s["kechikdi"] else ""))


def _absence_list(absences: list[dict], limit: int = 60) -> str:
    by_day = defaultdict(list)
    for a in absences:
        by_day[a["date"]].append(a)
    lines = [tr("❗ <b>Qoldirilgan / kechikilgan darslar ({n} ta)</b>", n=len(absences))]
    shown = 0
    for d in sorted(by_day, reverse=True):
        if shown >= limit:
            break
        lines.append(f"<b>{fmt_date(d)}</b>")
        for a in by_day[d]:
            lines.append(f"  {STATUS_ICON[a['status']]} " + tr("{p}-juftlik", p=a['pair'])
                         + f" — {esc(loc.term(a['subject']))}: {tr(STATUS_TEXT[a['status']])}")
            shown += 1
    if len(absences) > shown:
        lines.append(tr("… va yana {n} ta (oldingi sanalar)", n=len(absences) - shown))
    return "\n".join(lines)


async def subjects_report(st: dict) -> str:
    d1, d2 = _sem_range()
    subj = await db.subject_stats(st["id"], d1, d2)
    head = f"{student_header(st)}\n\n" + tr("📚 <b>Fanlar bo'yicha davomat</b> ({d1} — {d2})",
                                                d1=fmt_date(d1, False), d2=fmt_date(d2, False))
    if not subj:
        return f"{head}\n\n" + tr("Davomat ma'lumotlari hali yuklanmagan.")
    note = ("\n\n" + tr("⚠️ — sababsiz qoldirilgan darslar ulushi {p}% dan oshgan fan", p=fmt_num(SUBJECT_WARN_PERCENT))
            if any("⚠️" in _subject_line(s) for s in subj) else "")
    return f"{head}\n\n" + "\n".join(_subject_line(s) for s in subj) + note


async def absences_report(st: dict) -> str:
    d1, d2 = _sem_range()
    absences = await db.absences_between(st["id"], d1, d2)
    head = f"{student_header(st)}\n\n" + tr("🗓 Semestr boshidan ({d} dan)", d=fmt_date(d1, False))
    if not absences:
        # Kunlik davomat yo'q, lekin HEMIS statistikasida qoldirishlar bo'lishi mumkin — «qayd etilmagan» demaymiz
        periods = absence.hemis_periods(await db.att_stats_history(st["id"], d1, limit=12))
        if periods:
            lines = [tr("❗ <b>Qoldirilgan darslar — HEMIS ma'lumoti</b>")]
            for p in periods:
                when = (tr("{a} — {b}", a=fmt_date(p["from"], False), b=fmt_date(p["as_of"], False)) if p["from"]
                        else tr("{b} gacha", b=fmt_date(p["as_of"], False)))
                lines.append(f"• {when}: " + tr("sababsiz {a}", a=fmt_pairs(p["unexcused"]))
                             + (", " + tr("sababli {b}", b=fmt_pairs(p["excused"])) if p["excused"] else ""))
            lines.append("\n" + tr("ℹ️ HEMIS umumiy statistikasida har bir darsning sanasi va fani bo'lmaydi. Kurs "
                                   "koordinatori kunlik davomatni yuklasa, darslar sana va fan bo'yicha ko'rinadi."))
            return f"{head}\n\n" + "\n".join(lines)
        return f"{head}\n\n" + tr("✅ Qoldirilgan yoki kechikilgan dars qayd etilmagan.")
    tot = await db.attendance_totals(st["id"], d1, d2)
    return (f"{head}\n\n{_absence_list(absences)}\n\n"
            + tr("Jami sababsiz: {a}, sababli: {b}", a=fmt_pairs(tot['kelmadi_soat']), b=fmt_pairs(tot['sababli_soat'])))


async def schedule_report(st: dict, d1: date, d2: date) -> str:
    head = student_header(st)
    ctx = await individual.load(st)
    if not st.get("group_key") and not ctx.mine:
        return f"{head}\n\n" + tr("Talabaning guruhi bazada ko'rsatilmagan.")
    blocks = []
    personal_shown = False
    d = d1
    while d <= d2:
        rows = await individual.lessons_on(st, d, ctx)
        if rows:
            lines = [f"📅 <b>{fmt_date(d)}</b>"]
            for r in rows:
                tm = pair_time(r["pair"], r)
                extra = ", ".join(x for x in (lesson_label(r.get("lesson_type"), r.get("subgroup")),
                                              esc(loc.person(r.get("teacher")))) if x)
                room = f" · 🚪 {esc(loc.term(r['room']))}" if r.get("room") else ""
                sub = ""
                if r.get("_personal"):
                    personal_shown = True
                    sub = " · " + tr("{s}-oqim", s=esc(r['stream'])) if r.get("stream") else ""
                mark = "🎯 " if r.get("_personal") else ""
                lines.append(f"{r['pair']}. {tm + ' ' if tm else ''}{mark}<b>{esc(loc.term(r['subject']))}</b>"
                             + (f" ({extra})" if extra else "") + sub + room)
            blocks.append("\n".join(lines))
        d += timedelta(days=1)
    if not blocks:
        span = fmt_date(d1) if d1 == d2 else f"{fmt_date(d1, False)} — {fmt_date(d2, False)}"
        return f"{head}\n\n{span}: " + tr("dars yo'q yoki jadval hali yuklanmagan.")
    notes = []
    if personal_shown:
        notes.append(tr("🎯 — farzandingizning tanlov fani yoki ikkinchi chet tili (shaxsiy jadval). "
                        "Qolganlari — guruhning asosiy fanlari."))
    if not ctx.mine and (ctx.group_keys or await db.elective_subject_keys()):
        notes.append(tr("Farzandingizga tanlov fanlari va ikkinchi chet tili hali biriktirilmagan — "
                        "jadvalda faqat guruhning asosiy fanlari.") if ctx.status != "missing" else
                     tr("Farzandingizga tanlov fanlari va ikkinchi chet tili hali biriktirilmagan — "
                        "jadvalda guruhning barcha darslari (parallel darslar bilan)."))
    note = "\n\n" + "\n".join(f"<i>{n}</i>" for n in notes) if notes else ""
    return f"{head}\n\n" + "\n\n".join(blocks) + note


async def grades_report(st: dict) -> str:
    rows = await db.grades_for(st["id"])
    head = f"{student_header(st)}\n\n" + tr("📝 <b>Baholar</b>")
    if not rows:
        return f"{head}\n\n" + tr("Baholar hali yuklanmagan.")
    by_sem = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_sem[r["semester"]][r["subject"]].append(r)
    parts = [head]
    for sem in sorted(by_sem, reverse=True):
        if sem:
            parts.append("\n<b>" + (tr("{n}-semestr", n=esc(sem)) if sem.isdigit() else esc(sem)) + "</b>")
        for subject in sorted(by_sem[sem]):
            items = []
            for g in by_sem[sem][subject]:
                score = fmt_num(g["score"])
                if g.get("max_score"):
                    score += f"/{fmt_num(g['max_score'])}"
                if academic.is_total(g):
                    gr = academic.five_point(g["score"])
                    score += f" → «{gr}»" + (" ❗" if gr == 2 else "")
                items.append(f"{esc(loc.term(g['control_type']))}: <b>{score}</b>")
            parts.append(f"📚 {esc(loc.term(subject))}\n   " + " · ".join(items))
    return "\n".join(parts)


def announcements_text(items: list[dict]) -> str:
    if not items:
        return tr("📢 Hozircha e'lonlar yo'q.")
    parts = [tr("📢 <b>So'nggi e'lonlar</b>")]
    for a in items:
        body = loc.pick(a["text"])  # ota-ona tilidagi qism (---ru / ---en)
        text = body if len(body) <= 800 else body[:800] + "…"
        parts.append(f"🗓 <i>{fmt_date(a['created_at'][:10], False)}</i>\n{esc(text)}")
    return "\n\n".join(parts)


def weekday_name(n: int) -> str:
    return WEEKDAYS[n - 1]


def document_caption(doc: dict, st: dict) -> str:
    """Ota-onaga PDF bilan birga boradigan izoh (Telegram cheklovi: 1024 belgi)."""
    lines = [f"<b>{doc_title(doc['doc_type'])}</b>", "",
             f"👨‍🎓 {esc(loc.student_name(st))} ({esc(st.get('group_name') or '—')})",
             tr("🗓 Sana: {d}", d=fmt_date(doc['doc_date'] or doc['created_at'][:10], False))]
    if doc.get("comment"):
        comment = doc["comment"] if len(doc["comment"]) <= 500 else doc["comment"][:500] + "…"
        lines += ["", f"💬 {esc(comment)}"]
    if doc.get("redacted"):
        lines += ["", tr("🔒 Hujjatdagi boshqa talabalarning ma'lumotlari maxfiylik uchun yopilgan.")]
    lines += ["", tr("Savollaringiz bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozishingiz mumkin.")]
    return "\n".join(lines)


def documents_report(st: dict, docs: list[dict]) -> str:
    head = f"{student_header(st)}\n\n" + tr("📄 <b>Rasmiy hujjatlar</b>") + "\n"
    if not docs:
        return head + "\n" + tr("Hozircha kurs koordinatori tomonidan yuborilgan hujjatlar yo'q.")
    lines = []
    for i, d in enumerate(docs[:20], 1):
        lines.append(f"{i}. {doc_title(d['doc_type'])} — {fmt_date(d['doc_date'] or d['created_at'][:10], False)}")
        if d.get("comment"):
            c = d["comment"] if len(d["comment"]) <= 120 else d["comment"][:120] + "…"
            lines.append(f"   <i>{esc(c)}</i>")
    return head + "\n" + "\n".join(lines) + "\n\n" + tr("Hujjatni ochish uchun pastdagi tugmani bosing.")


def _hemis_block(row: dict, title: str = N_("HEMIS bo'yicha")) -> str:
    h = absence.stats_hours(row)
    return (f"📊 <b>{tr(title)}</b> " + tr("({d} holatiga):", d=fmt_date(row['as_of'], False)) + "\n"
            + tr("qatnashgan {a}, qoldirgan {b}", a=fmt_pairs(h['attended']), b=fmt_pairs(h['absent']))
            + (" " + tr("(sababli {n})", n=fmt_pairs(h['excused'])) if h["excused"] else "")
            + (", " + tr("davomat {p}%", p=round(h['percent'])) if h["percent"] is not None else ""))


async def hemis_report(st: dict) -> str:
    """HEMIS davomat statistikasi: oxirgi holat, yuklashlar bo'yicha o'zgarish va chegaralar."""
    since = semester_start().isoformat()
    rows = await db.att_stats_history(st["id"], since)
    parts = [student_header(st), ""]
    if not rows:
        parts.append(tr("📊 <b>HEMIS davomat statistikasi</b>") + "\n\n" + tr("HEMIS ma'lumoti hali yuklanmagan."))
    else:
        parts.append(_hemis_block(rows[-1], N_("HEMIS davomat statistikasi")))
        sm = await absence.summary(st["id"])
        if sm:
            parts.append("\n" + "\n".join(absence.status_lines(sm)))
        if len(rows) > 1:
            parts.append("\n" + tr("📈 <b>O'zgarish</b> ({label}):", label=tr(absence.COUNTED_LABEL)))
            prev = None
            for r in rows:
                c = absence.stats_hours(r)["counted"]
                diff = f", +{fmt_pairs(c - prev)}" if prev is not None and c > prev else ""
                parts.append(f"   {fmt_date(r['as_of'], False)} — {fmt_pairs(c)}{diff}")
                prev = c
    daily = await db.attendance_totals(st["id"], since, today().isoformat())
    if not daily["total"]:
        parts.append("\n<i>" + tr("HEMIS statistikasida kun va fanlar bo'yicha tafsilot yo'q — faqat jami ko'rsatkichlar.") + "</i>")
    parts.append("\n" + absence.rules_text())
    return "\n".join(parts)


PAY_KINDS = {"kontrakt": ("💰", N_("Kontraktdan qarzdorlik")), "trimestr": ("💳", N_("Trimestrdan qarzdorlik"))}


def _form_line(form: str | None) -> str:
    return (tr("To'lov shakli: <b>{v}</b>", v=esc(tr(form))) if form else tr("To'lov shakli: ko'rsatilmagan"))


async def finance_menu(st: dict) -> str:
    parts = [student_header(st), "", tr("💰 <b>Moliyaviy qarzdorlik</b>")]
    form = st.get("payment_form")
    parts.append(_form_line(form))
    if form == GRANT:
        parts.append(tr("Davlat granti asosida o'qiydi — kontrakt to'lovi talab qilinmaydi."))
    dl = await status.deadlines()
    for kind, (icon, title) in PAY_KINDS.items():
        p = await db.latest_payment(st["id"], kind)
        if p:
            state = (f"<b>{fmt_money(p['debt'])}</b>" + (", " + tr("muddat: {d}", d=fmt_date(dl[kind], False))
                                                         if dl[kind] else "")
                     if p["debt"] > 0 else tr("mavjud emas ✅"))
        elif await last_update(UPDATE_KEYS[kind][0]):
            state = tr("mavjud emas ✅")
        else:
            state = tr("ma'lumot yo'q")
        parts.append(f"{icon} {tr(title)}: {state}")
    parts.append("\n" + tr("Batafsil ma'lumot uchun turini tanlang 👇"))
    return "\n".join(parts) + await updated_note("fin_all")


async def payment_report(st: dict, kind: str = "kontrakt") -> str:
    icon, title = PAY_KINDS[kind]
    parts = [student_header(st), "", f"{icon} <b>{tr(title)}</b>"]
    form = st.get("payment_form")
    parts.append(_form_line(form))
    hist = await db.payment_history(st["id"], kind)
    report_ts = await last_update(UPDATE_KEYS[kind][0])
    if not hist:
        if form == GRANT and kind == "kontrakt":
            parts.append("\n" + tr("Davlat granti asosida o'qiydi — kontrakt to'lovi talab qilinmaydi."))
        elif report_ts:
            parts.append("\n" + tr("✅ Qarzdorlik mavjud emas: farzandingiz oxirgi hisobotdagi qarzdorlar ro'yxatida yo'q.")
                         + "\n" + tr("🕐 Ma'lumot {dt} da yangilangan.", dt=fmt_dt(report_ts)))
        else:
            parts.append("\n" + tr("Bu bo'yicha ma'lumot hali yuklanmagan."))
        return "\n".join(parts)
    p = hist[-1]
    parts.append("\n🗓 " + (tr("{d} holatiga ({y} o'quv yili):", d=fmt_date(p['as_of'], False), y=esc(p['year_label']))
                            if p.get("year_label") else tr("{d} holatiga:", d=fmt_date(p['as_of'], False))))
    if p.get("contract"):
        parts.append(tr("Shartnoma summasi: {v}", v=fmt_money(p['contract'])))
    parts.append(tr("To'langan: {v}", v=fmt_money(p['paid'])) + (f" ({p['percent']:g}%)" if p.get("percent") is not None else ""))
    parts.append(tr("💰 <b>Qarzdorlik: {v}</b>", v=fmt_money(p['debt'])) if p["debt"] > 0 else tr("✅ Qarzdorlik yo'q"))
    dl = (await status.deadlines())[kind]
    if dl and p["debt"] > 0:
        left = (dl - today()).days
        parts.append(tr("📅 To'lov muddati: <b>{d}</b>", d=fmt_date(dl, False))
                     + (" — " + tr("muddat o'tgan") if left < 0 else " — " + tr("bugun") if left == 0
                        else " " + tr("({n} kun qoldi)", n=left)))
    if p.get("overpaid"):
        parts.append(tr("Ortiqcha to'langan: {v}", v=fmt_money(p['overpaid'])))
    if p.get("note"):
        parts.append(tr("Izoh: {v}", v=esc(loc.term(p['note']))))
    if len(hist) > 1:
        parts.append("\n" + tr("📈 <b>Qarzdorlik o'zgarishi:</b>"))
        prev = None
        for h in hist:
            diff = ""
            if prev is not None and h["debt"] != prev:
                diff = f" ({'+' if h['debt'] > prev else '−'}{fmt_money(abs(h['debt'] - prev))})"
            parts.append(f"   {fmt_date(h['as_of'], False)} — {fmt_money(h['debt'])}{diff}")
            prev = h["debt"]
    parts.append("\n" + tr("🕐 Ma'lumot {dt} da yangilangan.", dt=fmt_dt(p.get('imported_at'))))
    parts.append("<i>" + tr("Ma'lumot universitet buxgalteriyasi hisobotidan olingan. Aniqlik kiritish uchun "
                            "buxgalteriyaga yoki kurs koordinatoriga murojaat qiling.") + "</i>")
    return "\n".join(parts)


async def academic_report(st: dict) -> str:
    parts = [student_header(st), "", tr("📚 <b>Akademik qarzdorlik</b>")]
    sm = await academic.summary(st["id"])
    if sm["debts"]:  # baholardan (0–59 → «2») va HEMIS «Akadem qarzdorlar» ro'yxatidan
        parts.append("\n" + tr("❗ Jami <b>{n} ta fandan</b> akademik qarzdor:", n=len(sm['debts'])))
        for d in sm["debts"]:
            info = []
            if d["semester"] and str(d["semester"]).isdigit():
                info.append(tr("{n}-semestr", n=esc(d['semester'])))
            if d.get("source") == "hemis":
                if d.get("credits"):
                    info.append(tr("{n} kredit", n=fmt_num(d["credits"])))
                info.append(tr("HEMIS ro'yxati"))
                parts.append(f"   • <b>{esc(loc.term(d['subject']))}</b> — " + ", ".join(info))
            else:
                parts.append(f"   • <b>{esc(loc.term(d['subject']))}</b> — " + tr("{s} ball → «2»", s=fmt_num(d['score']))
                             + ("".join(" · " + x for x in info)))
    elif sm["results"]:
        parts.append("\n" + tr("✅ Akademik qarzdorlik yo'q."))
    if not sm["results"]:
        parts.append("\n" + tr("Fanlar bo'yicha 100 ballik umumiy baholar hali yuklanmagan."))
        parts.append(f"\n<i>{tr(academic.RULES_TEXT)}</i>")
        return "\n".join(parts)
    total_gpa, weighted = academic.gpa(sm["results"])
    parts.append("\n" + tr("🎓 <b>O'zlashtirish ko'rsatkichi (GPA): {v} / 5</b>", v=fmt_gpa(total_gpa))
                 + (" " + tr("(kreditlar bo'yicha)") if weighted else ""))
    if academic.gpa_low(total_gpa):
        parts.append(tr("🔴 GPA {min} dan past — talaba kursdan kursga o'tkazilmaydi.", min=fmt_limit(GPA_MIN)))
    sem_gpa = academic.semester_gpa(sm["results"])
    parts.append("\n" + tr("📊 <b>Baholar (5 baholik tizimda):</b>"))
    for sem, items in sorted(academic.by_semester(sm["results"]).items(), reverse=True):
        if sem:
            parts.append("<b>" + (tr("{n}-semestr", n=esc(sem)) if str(sem).isdigit() else esc(sem)) + "</b>"
                         + f" — GPA {fmt_gpa(sem_gpa.get(sem))}")
        for r in items:
            mark = "❗" if r["debt"] else "▫️"
            parts.append(f"{mark} {esc(loc.term(r['subject']))} — {fmt_num(r['score'])} → «{r['grade']}»")
    parts.append(f"\n<i>{tr(academic.RULES_TEXT)} {tr(academic.GPA_TEXT)} "
                 f"{tr(academic.GPA_RULE, min=fmt_limit(GPA_MIN))}</i>")
    return "\n".join(parts) + await updated_note("acad")
