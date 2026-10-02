"""Tarjimalar jadvali: kursdagi barcha fan, fakultet, nazorat turi va xona nomlari — ruscha va inglizcha tarjimasi
bilan. Kurs koordinatori /tarjimalar orqali Excel oladi, bo'shlarini to'ldirib /import → «🌐 Tarjimalar» bilan
qaytaradi; tarjimalar umumiy ro'yxatda (central.db) saqlanadi va barcha kurslarda ishlaydi.
"""
from __future__ import annotations

import io
import re

import loc
from database import db

KINDS = (("Fan", "SELECT DISTINCT subject AS v FROM grades"),
         ("Fan", "SELECT DISTINCT subject AS v FROM schedule"),
         ("Fan", "SELECT DISTINCT subject AS v FROM elective_schedule"),
         ("Fan", "SELECT DISTINCT subject AS v FROM student_subjects"),
         ("Fan", "SELECT DISTINCT subject AS v FROM attendance"),
         ("Fakultet", "SELECT DISTINCT faculty AS v FROM students"),
         ("Nazorat turi", "SELECT DISTINCT control_type AS v FROM grades"),
         ("Xona", "SELECT DISTINCT room AS v FROM schedule"),
         ("Xona", "SELECT DISTINCT room AS v FROM elective_schedule"))


async def collect() -> list[dict]:
    """Kursdagi nomlar (takrorlanmasdan), har birining tarjima holati bilan."""
    seen: dict[str, dict] = {}
    for kind, sql in KINDS:
        for r in await db.fetchall(sql):
            v = " ".join(str(r["v"] or "").split())
            if not v or re.fullmatch(r"[\d\s\-./]+", v):  # «402», «2-bino» kabi raqamlar tarjima qilinmaydi
                continue
            key = loc.term_key(v)
            if key and key not in seen:
                seen[key] = {"kind": kind, "uz": loc._split(v)[0], "key": key}
    out = []
    for item in sorted(seen.values(), key=lambda x: (x["kind"], x["uz"])):
        custom = loc._CUSTOM.get(item["key"]) or {}
        builtin = loc._BUILTIN.get(item["key"])
        ru = custom.get("ru") or (builtin[0] if builtin else "")
        en = custom.get("en") or (builtin[1] if builtin else "")
        state = "kiritilgan" if custom.get("ru") or custom.get("en") else "lug'atda" if builtin else "TARJIMA KERAK"
        out.append({**item, "ru": ru, "en": en, "state": state})
    return out


def missing(values, lang: str = "ru") -> list[str]:
    """Rus (yoki ingliz) tiliga tarjimasi yo'q nomlar — import natijasi uchun."""
    out = {}
    for v in values:
        v = " ".join(str(v or "").split())
        if v and not re.fullmatch(r"[\d\s\-./]+", v) and not loc.known(v, lang):
            out.setdefault(loc.term_key(v), loc._split(v)[0])
    return sorted(out.values())


def build_xlsx(items: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    F = "Arial"
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    fill_in = PatternFill("solid", start_color="FFFF00")    # to'ldirilishi kerak bo'lgan katak
    wb = Workbook()
    ws = wb.active
    ws.title = "Tarjimalar"
    cols = (("Turi", 14), ("O'zbekcha", 40), ("Ruscha", 44), ("Inglizcha", 40), ("Holati", 16))
    for j, (t, w) in enumerate(cols, start=1):
        c = ws.cell(row=1, column=j, value=t)
        c.font = Font(name=F, bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", start_color="1F4E78")
        c.border = border
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[chr(64 + j)].width = w
    ws.cell(row=1, column=3).comment = Comment("Rasmiy ruscha nomi, kirill alifbosida (masalan: «Международные "
                                               "отношения»). Rim raqamlari (I, II, III) yozilmaydi — bot o'zi qo'shadi.",
                                               "Bot")
    for i, it in enumerate(items, start=2):
        for j, v in enumerate((it["kind"], it["uz"], it["ru"], it["en"], it["state"]), start=1):
            c = ws.cell(row=i, column=j, value=v or None)
            c.font = Font(name=F, size=10, bold=(j == 5 and it["state"] == "TARJIMA KERAK"),
                          color="C00000" if j == 5 and it["state"] == "TARJIMA KERAK" else "000000")
            c.border = border
            if j in (3, 4) and not v:
                c.fill = fill_in
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:E{max(len(items) + 1, 2)}"
    g = wb.create_sheet("Ko'rsatma")
    notes = [
        "Rus va ingliz tilini tanlagan ota-onalarga fan, fakultet va boshqa nomlar shu jadvaldagi tarjimada ko'rsatiladi.",
        "Sariq kataklarni to'ldiring: «Ruscha» — rasmiy ruscha nomi kirill alifbosida, «Inglizcha» — rasmiy inglizcha nomi.",
        "«Holati»: «lug'atda» — botning ichki lug'atidagi tarjima (o'zgartirish mumkin); «kiritilgan» — oldin siz kiritgan; "
        "«TARJIMA KERAK» — hozircha rus tilida kirill harflarida (asl o'zbekcha nom) ko'rsatiladi.",
        "Rim raqamlari va «(c)» kabi belgilar yozilmaydi: «Fransuz tili I» uchun «Французский язык» kiritiladi, "
        "bot «Французский язык I» deb ko'rsatadi.",
        "To'ldirilgan faylni botga yuboring: /import → «🌐 Tarjimalar». Tarjimalar barcha kurslar uchun umumiy.",
    ]
    g["A1"] = "Qanday to'ldiriladi"
    g["A1"].font = Font(name=F, bold=True, size=12)
    for r, n in enumerate(notes, start=2):
        g.cell(row=r, column=1, value=f"{r - 1}. {n}").font = Font(name=F, size=10)
    g.column_dimensions["A"].width = 130
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
