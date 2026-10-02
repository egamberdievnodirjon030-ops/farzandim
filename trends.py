"""Dinamika: davomat va baholar qanday o'zgargani — ota-ona uchun taqqoslash va grafik.

Davomat:
  • kunlik davomat bo'lsa — haftalar bo'yicha foiz (oxirgi 6 hafta), shu hafta o'tgan hafta bilan solishtiriladi;
  • faqat HEMIS statistikasi bo'lsa — yuklashlar orasidagi davrlar: har bir davrda qatnashilgan ulush
    (jami ko'rsatkichlar ayirmasidan), oxirgi davr oldingisi bilan solishtiriladi.
Baholar: har bir fan bo'yicha 100 ballik umumiy ball va GPA hozir va bir oy oldin (baholar tarixidan; tarix bir oydan
qisqa bo'lsa — birinchi ma'lum qiymat bilan).
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import absence
import academic
import loc
from database import db
from i18n import tr
from utils import esc, fmt_date, fmt_gpa, fmt_num, fmt_pairs, normalize_text, now, semester_start, today, week_bounds

MIN_CHANGE = 1          # davomat: foiz punktdan kam o'zgarish — «o'zgarmadi»
MIN_SCORE_CHANGE = 1    # baho: balldan kam o'zgarish ko'rsatilmaydi
WEEKS = 6


# ---------------------------------------------------------------- davomat
async def attendance_periods(st: dict) -> tuple[str, list[dict]]:
    """Qaytaradi: (rejim: "weekly" | "hemis" | "", davrlar ro'yxati eskidan yangiga)."""
    t = today()
    since = semester_start()
    mon, _ = week_bounds(t)
    start = max(mon - timedelta(weeks=WEEKS - 1), since)
    rows = await db.attendance_rows(st["id"], start.isoformat(), t.isoformat())
    if rows:
        weeks: dict[date, dict] = {}
        for r in rows:
            d = date.fromisoformat(r["date"])
            w = weeks.setdefault(d - timedelta(days=d.weekday()), {"total": 0, "att": 0, "unexc": 0.0})
            w["total"] += 1
            w["att"] += r["status"] in ("keldi", "kechikdi")
            if r["status"] == "kelmadi":
                w["unexc"] += r["hours"] or 0
        periods = [{"start": k, "end": min(k + timedelta(days=6), t), "pct": 100 * v["att"] / v["total"],
                    "unexc": v["unexc"], "total": v["total"]} for k, v in sorted(weeks.items()) if v["total"]]
        return "weekly", periods
    hist = await db.att_stats_history(st["id"], since.isoformat(), limit=12)
    if not hist:
        return "", []
    periods, prev, prev_date = [], None, since
    for r in hist:
        cur = absence.stats_hours(r)
        att = cur["attended"] - (prev["attended"] if prev else 0)
        absn = cur["absent"] - (prev["absent"] if prev else 0)
        unexc = cur["counted"] - (prev["counted"] if prev else 0)
        end = date.fromisoformat(r["as_of"])
        if att + absn > 0:
            periods.append({"start": prev_date, "end": end, "pct": 100 * att / (att + absn), "unexc": max(unexc, 0),
                            "total": att + absn})
        prev, prev_date = cur, end
    return "hemis", periods


def _cap(text: str) -> str:
    """Gap boshidagi o'rin («shu hafta», «o'tgan haftaga nisbatan») — bosh harf bilan."""
    return text[:1].upper() + text[1:]


def _period_label(p: dict) -> str:
    return f"{p['start'].strftime('%d.%m')}–{p['end'].strftime('%d.%m')}"


def attendance_lines(mode: str, periods: list[dict]) -> list[str]:
    if not periods:
        return [tr("📊 <b>Davomat</b>"), tr("Davomat ma'lumotlari hali yuklanmagan.")]
    last = periods[-1]
    lines = [tr("📊 <b>Davomat</b>")]
    what = tr("shu hafta") if mode == "weekly" and last["end"] >= week_bounds(today())[0] else _period_label(last)
    lines.append(_cap(tr("{period}: <b>{p}%</b>, sababsiz qoldirilgan: {h}", period=what, p=round(last["pct"]),
                         h=fmt_pairs(last["unexc"]))))
    if len(periods) < 2:
        lines.append(tr("Taqqoslash uchun hali oldingi davr ma'lumoti yo'q."))
        return lines
    prev = periods[-2]
    diff = round(last["pct"]) - round(prev["pct"])
    base = tr("o'tgan haftaga nisbatan") if mode == "weekly" else tr("oldingi davrga nisbatan ({p})", p=_period_label(prev))
    if diff >= MIN_CHANGE:
        lines.append("📈 " + _cap(tr("{base} davomat {d}% ga yaxshilandi ({old}% → {new}%).", base=base, d=diff,
                                    old=round(prev["pct"]), new=round(last["pct"]))))
    elif diff <= -MIN_CHANGE:
        lines.append("📉 " + _cap(tr("{base} davomat {d}% ga pasaydi ({old}% → {new}%).", base=base, d=-diff,
                                    old=round(prev["pct"]), new=round(last["pct"]))))
    else:
        lines.append("➖ " + _cap(tr("{base} davomat deyarli o'zgarmadi ({new}%).", base=base, new=round(last["pct"]))))
    if abs(last["unexc"] - prev["unexc"]) >= 1:
        lines.append(tr("Sababsiz qoldirilgan darslar: {old} → {new}.", old=fmt_pairs(prev["unexc"]),
                        new=fmt_pairs(last["unexc"])))
    return lines


# ---------------------------------------------------------------- baholar
def _results_at(history: list[dict], when: str) -> list[dict]:
    """Baholar tarixidan berilgan vaqtdagi holat: har bir (fan, nazorat, semestr) uchun shu vaqtgacha oxirgi ball."""
    latest: dict[tuple, dict] = {}
    for h in history:
        if h["recorded_at"] <= when:
            latest[(h["subject"], h["control_type"], h["semester"])] = h
    return academic.subject_results(list(latest.values()))


async def grade_changes(st: dict) -> dict:
    history = await db.grade_history(st["id"])
    current = (await academic.summary(st["id"]))["results"]
    out = {"ref": None, "month": False, "items": [], "gpa_old": None, "gpa_new": academic.gpa(current)[0]}
    if not history or not current:
        return out
    month_ago = (now() - timedelta(days=30)).isoformat(timespec="seconds")
    first = history[0]["recorded_at"]
    ref = month_ago if first <= month_ago else first
    old = {(str(r["semester"]), normalize_text(r["subject"])): r for r in _results_at(history, ref)}
    items = []
    for r in current:
        o = old.get((str(r["semester"]), normalize_text(r["subject"])))
        if o and abs(r["score"] - o["score"]) >= MIN_SCORE_CHANGE:
            items.append({"subject": r["subject"], "old": o["score"], "new": r["score"], "delta": r["score"] - o["score"],
                          "old_grade": o["grade"], "new_grade": r["grade"]})
    out.update(ref=ref, month=ref == month_ago, items=sorted(items, key=lambda x: x["delta"]),
               gpa_old=academic.gpa(list(old.values()))[0] if old else None,
               compared=[(old.get((str(r["semester"]), normalize_text(r["subject"]))), r) for r in current])
    return out


def grade_lines(g: dict) -> list[str]:
    lines = [tr("📚 <b>Baholar</b>")]
    if g["ref"] is None:
        lines.append(tr("Taqqoslash uchun baholar tarixi hali yo'q — keyingi yuklashlardan so'ng ko'rinadi."))
        return lines
    when = tr("oxirgi oyda") if g["month"] else tr("{d} dan beri", d=fmt_date(g["ref"][:10], False))
    if not g["items"]:
        lines.append(_cap(tr("{when} fanlar bo'yicha ball o'zgarmadi.", when=when)))
    for it in g["items"]:
        icon = "📉" if it["delta"] < 0 else "📈"
        lines.append(f"{icon} {esc(loc.term(it['subject']))}: {fmt_num(it['old'])} → <b>{fmt_num(it['new'])}</b> "
                     f"({'+' if it['delta'] > 0 else '−'}{fmt_num(abs(it['delta']))})"
                     + (f" · «{it['old_grade']}» → «{it['new_grade']}»" if it["old_grade"] != it["new_grade"] else ""))
    drops = [it for it in g["items"] if it["delta"] < 0]
    if drops:
        worst = drops[0]
        lines.append(tr("❗ «{subj}» fanidan o'rtacha ball {when} tushib ketdi.", subj=esc(loc.term(worst["subject"])), when=when))
    rises = [it for it in g["items"] if it["delta"] > 0]
    if rises:
        best = rises[-1]
        lines.append(tr("👍 «{subj}» fanidan ball {when} ko'tarildi.", subj=esc(loc.term(best["subject"])), when=when))
    if g["gpa_old"] is not None and g["gpa_new"] is not None and abs(g["gpa_new"] - g["gpa_old"]) >= 0.01:
        lines.append(tr("🎓 GPA: {old} → <b>{new}</b> ({when}).", old=fmt_gpa(g["gpa_old"]), new=fmt_gpa(g["gpa_new"]),
                        when=when))
    return lines


# ---------------------------------------------------------------- umumiy
async def report(st: dict) -> tuple[str, bytes | None]:
    mode, periods = await attendance_periods(st)
    g = await grade_changes(st)
    text = "\n".join([tr("📈 <b>Dinamika</b> — o'qishdagi o'zgarishlar"), ""] + attendance_lines(mode, periods) + [""]
                     + grade_lines(g))
    return text, chart_png(mode, periods, g)


async def short_line(st: dict) -> str | None:
    """«Umumiy holat» uchun bitta qator: davomat o'zgarishi va ball tushgan fanlar."""
    mode, periods = await attendance_periods(st)
    parts = []
    if len(periods) >= 2:
        diff = round(periods[-1]["pct"]) - round(periods[-2]["pct"])
        if abs(diff) >= MIN_CHANGE:
            parts.append(tr("davomat {sign}{d}%", sign="↑" if diff > 0 else "↓", d=abs(diff)))
    g = await grade_changes(st)
    down = sum(1 for it in g["items"] if it["delta"] < 0)
    if down:
        parts.append(tr("{n} ta fanda ball pasaydi", n=down))
    return "📈 " + tr("Dinamika: {v}", v=", ".join(parts)) if parts else None


async def mini(st: dict) -> list[dict]:
    """Ota-ona bosh sahifasi uchun ixcham dinamika: har bir ko'rsatkich — oxirgi qiymat, oldingisiga nisbatan
    o'zgarish va kichik grafik nuqtalari. Ma'lumot bitta bo'lsa ham ko'rsatiladi (o'zgarishsiz)."""
    items = []

    def item(key, title, unit, points, better, caption):
        vals = [p["value"] for p in points]
        return {"key": key, "title": title, "unit": unit, "points": points, "value": vals[-1],
                "delta": round(vals[-1] - vals[-2], 2) if len(vals) > 1 else None, "better": better, "caption": caption}

    mode, periods = await attendance_periods(st)
    if periods:
        pts = [{"label": p["start"].strftime("%d.%m") if mode == "weekly" else p["end"].strftime("%d.%m"),
                "value": round(p["pct"], 1)} for p in periods[-WEEKS:]]
        items.append(item("att", tr("Davomat"), "%", pts, "up",
                          tr("o'tgan haftaga nisbatan") if mode == "weekly" else tr("oldingi HEMIS ma'lumotiga nisbatan")))
    g = await grade_changes(st)
    if g["gpa_new"] is not None:
        pts = ([{"label": date.fromisoformat(g["ref"][:10]).strftime("%d.%m"), "value": round(g["gpa_old"], 2)}]
               if g["gpa_old"] is not None and g["ref"] else []) + [{"label": tr("bugun"), "value": round(g["gpa_new"], 2)}]
        items.append(item("gpa", tr("GPA"), "gpa", pts, "up",
                          tr("bir oy oldingiga nisbatan") if g["month"] else tr("oldingi baholarga nisbatan")))
    if not (st.get("payment_form") or "").lower().startswith("davlat"):
        hist = await db.payment_history(st["id"], "kontrakt", limit=6)
        cur = await db.latest_payment(st["id"], "kontrakt")
        if cur and cur.get("absent"):
            hist = hist + [cur]  # keyingi hisobotda ro'yxatda yo'q — qarzdorlik mavjud emas
        if hist:
            pts = [{"label": date.fromisoformat(h["as_of"]).strftime("%d.%m"), "value": round(h["debt"] or 0)} for h in hist]
            items.append(item("kontrakt", tr("Kontrakt qarzi"), "money", pts, "down", tr("oldingi hisobotga nisbatan")))
    return items


def chart_png(mode: str, periods: list[dict], g: dict) -> bytes | None:
    pairs = [(o, r) for o, r in g.get("compared", []) if o]
    if len(periods) < 2 and not pairs:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = (len(periods) >= 2) + bool(pairs)
    fig, axes = plt.subplots(panels, 1, figsize=(8, 3.4 * panels), dpi=110)
    axes = [axes] if panels == 1 else list(axes)
    i = 0
    if len(periods) >= 2:
        ax = axes[i]
        i += 1
        labels = [_period_label(p) for p in periods]
        vals = [p["pct"] for p in periods]
        colors = ["#2e7d32" if v >= 90 else "#f9a825" if v >= 75 else "#c62828" for v in vals]
        bars = ax.bar(labels, vals, color=colors)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{round(v)}%", ha="center", fontsize=9)
        ax.set_ylim(0, 110)
        ax.set_title(tr("Davomat, % (haftalar bo'yicha)") if mode == "weekly" else tr("Davomat, % (yuklashlar orasidagi davrlar)"),
                     fontsize=11)
        ax.tick_params(axis="x", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    if pairs:
        ax = axes[i]
        names = [loc.term(r["subject"])[:28] for _, r in pairs]
        y = list(range(len(pairs)))
        old_bars = ax.barh([v + 0.2 for v in y], [o["score"] for o, _ in pairs], height=0.4, color="#b0bec5",
                           label=tr("bir oy oldin") if g["month"] else fmt_date(g["ref"][:10], False))
        new_bars = ax.barh([v - 0.2 for v in y], [r["score"] for _, r in pairs], height=0.4, color="#1565c0",
                           label=tr("hozir"))
        for bars in (old_bars, new_bars):
            for b in bars:
                ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2, fmt_num(b.get_width()), va="center",
                        fontsize=8)
        ax.axvline(60, color="#c62828", linestyle="--", linewidth=1)
        ax.text(60.5, -0.75, tr("60 — chegara"), color="#c62828", fontsize=8)
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=8)
        ax.set_xlim(0, 108)
        ax.set_ylim(len(pairs) - 0.4, -0.95)
        ax.set_title(tr("Fanlar bo'yicha ball (100 ballik)"), fontsize=11)
        ax.legend(fontsize=8, loc="lower right")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
