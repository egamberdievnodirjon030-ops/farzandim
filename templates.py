"""Import shablonlari — super-admin o'zgartiradi va yangisini qo'shadi (barcha kurslar uchun umumiy).

  • Asl shablonlar — shablonlar/ papkasida (bot bilan keladi). Super-admin yuklagan versiyalar — data/templates/ da:
    bot kodi yangilanganda ham saqlanadi va zaxira nusxaga kiradi. Har bir shablonning versiyalari tarixda qoladi,
    istalgan versiyaga yoki asl shablonga qaytish mumkin.
  • Import turiga bog'langan shablon yuklanganda bot sarlavhalarni tahlil qiladi: majburiy ustunlar bo'lmasa —
    qabul qilinmaydi; tanimagan ustun uchun super-admin qaysi ma'lumot ekanini tanlaydi va bu nom **import paytida
    ham taniladi** — kurs koordinatorlari yangi shablonni to'ldirib yuklaganda ustunlar to'g'ri o'qiladi.
  • Oddiy hujjat namunasi (Word, PDF, Excel) — import qilinmaydi, kurs koordinatorlariga /shablon orqali tarqatiladi.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import importer
from config import DATA_DIR, TEMPLATES_DIR
from importer import ALIASES, KIND_TITLES, REQUIRED, load_rows, parse_rows
from tenancy import central
from utils import normalize_text

TPL_DIR = Path(DATA_DIR) / "templates"

# Asl shablonlar: fayl → (nomi, import turi)
BUILTIN: dict[str, tuple[str, str]] = {
    "1_talabalar.xlsx": ("Talabalar (kontingent)", "students"),
    "2_dars_jadvali.xlsx": ("Dars jadvali (asosiy fanlar)", "schedule"),
    "3_davomat.xlsx": ("Davomat — HEMIS statistikasi", "attendance"),
    "4_baholar.xlsx": ("Baholar", "grades"),
    "5_talaba_telefonlari.xlsx": ("Talaba telefonlari", "phones"),
    "6_davomat_kunlik.xlsx": ("Davomat — kunlik", "attendance"),
    "7_tanlov_2til_biriktirish.xlsx": ("Tanlov fanlari va 2-til: kim o'qiydi", "enroll"),
    "8_tanlov_2til_jadvali.xlsx": ("Tanlov fanlari va 2-til: jadval", "elsched"),
    "9_kontrakt_qarzdorlar.xlsx": ("Kontrakt qarzdorligi", "debts"),
    "10_trimestr_qarzdorligi.xlsx": ("Trimestr qarzdorligi", "debts_t"),
    "11_tarjimalar.xlsx": ("Tarjimalar (fan va fakultet nomlari)", "translations"),
    "12_akademik_qarzdorlar.xlsx": ("Akademik qarzdorlar (HEMIS ro'yxati)", "acad_debts"),
    "13_gpa_hemis.xlsx": ("GPA (HEMIS «Performance GPA»)", "gpa"),
}
# Yangi shablon qo'shishda tanlanadigan import turlari
NEW_KINDS = [("students", "👥 Talabalar"), ("attendance", "📊 Davomat"), ("schedule", "📅 Dars jadvali"),
             ("grades", "📝 Baholar"), ("enroll", "🎯 Tanlov/2-til: kim o'qiydi"), ("elsched", "🗓 Tanlov/2-til: jadval"),
             ("debts", "💰 Kontrakt qarzdorligi"), ("debts_t", "🗓 Trimestr qarzdorligi"),
             ("acad_debts", "📚 Akademik qarzdorlar"), ("gpa", "🎓 GPA (HEMIS)"),
             ("phones", "📱 Talaba telefonlari"), ("translations", "🌐 Tarjimalar")]

FIELD_LABELS = {
    "hemis_id": "Talaba ID (HEMIS)", "full_name": "F.I.Sh.", "group_name": "Guruh", "faculty": "Fakultet",
    "course": "Kurs", "full_name_cyr": "F.I.Sh. (kirill)", "payment_form": "To'lov shakli",
    "birth_date": "Tug'ilgan sana", "phones": "Ota-ona telefoni", "phones_father": "Otasining telefoni",
    "phones_mother": "Onasining telefoni", "student_phones": "Talabaning telefoni", "tutor_name": "Kurs koordinatori",
    "tutor_phone": "Kurs koordinatori telefoni", "attended": "Qatnashganlar soni", "absent": "Qatnashmaganlar soni",
    "excused": "Sabablilar soni", "self_marked": "O'zi belgilagan", "teacher_marked": "O'qituvchi belgilagan",
    "date": "Sana", "pair": "Juftlik", "subject": "Fan", "lesson_type": "Mashg'ulot turi", "teacher": "O'qituvchi",
    "status": "Holat (keldi/kelmadi)", "hours": "Soat", "weekday": "Hafta kuni", "start_time": "Boshlanish vaqti",
    "end_time": "Tugash vaqti", "time_range": "Vaqt oralig'i", "room": "Xona", "week_type": "Hafta turi (toq/juft)",
    "subgroup": "Kichik guruh", "stream": "Oqim", "lang2": "Ikkinchi chet tili", "control_type": "Nazorat turi",
    "score": "Ball", "max_score": "Maksimal ball", "semester": "Semestr", "credits": "Kredit",
    "term_type": "Turi", "uz": "O'zbekcha", "ru": "Ruscha", "en": "Inglizcha",
}


def kind_title(kind: str | None) -> str:
    return KIND_TITLES.get(kind, kind) if kind else "Hujjat namunasi (import qilinmaydi)"


def label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _order(slot: str) -> tuple:
    head = slot.split("_")[0]
    return (0, int(head), slot) if head.isdigit() else (1, 0, slot)


# ---------------------------------------------------------------- ro'yxat
async def catalog(include_hidden: bool = False) -> list[dict]:
    """Barcha shablonlar: asl, o'zgartirilgan (joriy versiya) va qo'shilgan — kurs koordinatoriga shu tartibda."""
    active = {r["slot"]: r for r in await central.active_templates()}
    meta = await central.template_meta()
    slots = list(BUILTIN) + sorted({*active, *meta} - set(BUILTIN), key=lambda s: (meta.get(s, {}).get("sort") or 0,
                                                                                   _order(s)))
    out = []
    for slot in slots:
        m, cur = meta.get(slot, {}), active.get(slot)
        builtin = BUILTIN.get(slot)
        if not builtin and not cur:
            continue  # qo'shilgan shablon o'chirilgan
        path = (TPL_DIR / cur["stored"]) if cur else (Path(TEMPLATES_DIR) / slot)
        if not path.exists():
            continue
        item = {"slot": slot, "title": m.get("title") or (builtin[0] if builtin else slot),
                "kind": (cur or {}).get("kind") if not builtin else builtin[1],
                "description": m.get("description") or "", "path": path,
                "file_name": cur["file_name"] if cur else slot, "version": cur["version"] if cur else 0,
                "updated": cur["uploaded_at"] if cur else None, "builtin": bool(builtin),
                "changed": bool(builtin and cur), "hidden": bool(m.get("hidden"))}
        if include_hidden or not item["hidden"]:
            out.append(item)
    return out


async def get(slot: str) -> dict | None:
    return next((t for t in await catalog(include_hidden=True) if t["slot"] == slot), None)


async def save_version(slot: str, kind: str | None, src: Path, file_name: str, by: int | None) -> int:
    """Yangi versiyani data/templates/<slot>/ ga saqlaydi va faollashtiradi."""
    safe = re.sub(r"[^\w.\-]+", "_", file_name, flags=re.UNICODE)[:80] or "shablon"
    versions = await central.template_versions(slot)
    v = (versions[0]["version"] + 1) if versions else 1
    rel = f"{slot}/v{v}_{safe}"
    (TPL_DIR / slot).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, TPL_DIR / rel)
    return await central.add_template_version(slot, kind, file_name, rel, by)


# ---------------------------------------------------------------- sarlavhalar tahlili
def alias_group(kind: str | None, rows: list) -> str | None:
    """Import turi → ustun nomlari to'plami (davomat — HEMIS statistikasi yoki kunlik, ustunlarga qarab)."""
    if kind in (None, "debts", "debts_t"):
        return None
    if kind == "attendance":
        stats, _ = importer._best_header(rows, ALIASES["attendance_stats"])
        daily, _ = importer._best_header(rows, ALIASES["attendance"])
        return "attendance_stats" if "absent" in stats and "date" not in daily else "attendance"
    return kind if kind in ALIASES else None


def analyze(path: Path, kind: str) -> dict:
    """Shablonni import bilan bir xil tekshiradi: tanilgan va tanilmagan ustunlar, majburiy ustunlar."""
    rows = load_rows(str(path))
    res = parse_rows(rows, kind)
    grp = alias_group(kind, rows)
    out = {"group": grp, "fatal": res.fatal, "known": [], "unknown": [], "wide": res.kind.endswith("_wide"),
           "required": [label(f) for f in REQUIRED.get(grp or "", [])], "kind": res.kind}
    if grp and not out["wide"]:
        colmap, hidx = importer._best_header(rows, ALIASES[grp])
        header = rows[hidx] if hidx >= 0 else (rows[0] if rows else ())
        by_idx = {i: f for f, i in colmap.items()}
        for i, cell in enumerate(header):
            text = " ".join(str(cell or "").split())
            if not text:
                continue
            if i in by_idx:
                out["known"].append({"col": i, "text": text, "field": by_idx[i]})
            else:
                out["unknown"].append({"col": i, "text": text})
    return out


def free_fields(grp: str, analysis: dict, chosen: dict) -> list[str]:
    """Hali hech bir ustunga biriktirilmagan maydonlar (tanlash tugmalari uchun)."""
    used = {k["field"] for k in analysis["known"]} | set(chosen.values())
    return [f for f in ALIASES[grp] if f not in used]


def _apply_alias(grp: str, alias: str, field: str) -> None:
    group = ALIASES.get(grp)
    if not group or field not in group:
        return
    for f in list(group):  # boshqa maydonda bo'lsa — olib tashlanadi (ro'yxat nusxasi: boshqa turlarga ta'sir qilmasin)
        if f != field and alias in group[f]:
            group[f] = [a for a in group[f] if a != alias]
    if alias not in group[field]:
        group[field] = [*group[field], alias]


async def learn(grp: str, header_text: str, field: str, by: int | None) -> str:
    alias = normalize_text(header_text)
    _apply_alias(grp, alias, field)
    await central.add_alias(grp, alias, field, by)
    return alias


async def load_aliases() -> int:
    """Bot ishga tushganda: super-admin o'rgatgan ustun nomlari importga qo'shiladi."""
    rows = await central.all_aliases()
    for r in rows:
        _apply_alias(r["grp"], r["alias"], r["field"])
    return len(rows)
