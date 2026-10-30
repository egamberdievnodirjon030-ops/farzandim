"""Talabalarning ijtimoiy toifalari: nogironligi borlar, ijtimoiy himoyaga muhtojlar (ijtimoiy himoya reestri, xotin-qizlar
reestri, ayollar daftari, temir daftar, yoshlar daftari, boshqa), chin yetimlar, mehribonlik uyi tarbiyalanuvchilari.

Toifa fayl bilan («Ijtimoiy toifalar» importi) yoki qo'lda (kurs holati kartasidan — bir nechta talabaga birdan, yoki
talaba kartasidan) beriladi. Bir talabada bir nechta toifa bo'lishi mumkin (masalan, chin yetim va mehribonlik uyi);
nogironlik — bitta yozuv (guruhi bilan). Ma'lumot kurs bazasida: student_categories.
"""
from __future__ import annotations

import re

from database import db
from utils import now_iso, normalize_text

CATS: dict[str, dict] = {
    "nogironlik": {"title": "Nogironligi bor", "short": "Nogironlik",
                   "subs": {"1": "I guruh", "2": "II guruh", "3": "III guruh"}},
    "ijtimoiy": {"title": "Ijtimoiy himoyaga muhtoj", "short": "Ijtimoiy himoya",
                 "subs": {"reestr": "Ijtimoiy himoya reestri", "xotin_qizlar": "Xotin-qizlar reestri",
                          "ayollar": "Ayollar daftari", "temir": "Temir daftar", "yoshlar": "Yoshlar daftari",
                          "boshqa": "Boshqa"}},
    "chin_yetim": {"title": "Chin yetim", "short": "Chin yetim", "subs": {}},
    "mehribonlik": {"title": "Mehribonlik uyi tarbiyalanuvchisi", "short": "Mehribonlik uyi", "subs": {}},
}
SOURCES = {"fayl": "fayldan", "qolda": "qo'lda"}


class SocialError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def label(cat: str, sub: str = "") -> str:
    c = CATS.get(cat, {})
    s = c.get("subs", {}).get(sub, "")
    return f"{c.get('title', cat)}" + (f" — {s}" if s else "")


# ---------------------------------------------------------------- matndan toifa (fayl ustunlari va qiymatlari)
_ROMAN = {"i": "1", "ii": "2", "iii": "3", "birinchi": "1", "ikkinchi": "2", "uchinchi": "3"}
_DIS_GROUP = re.compile(r"\b(1|2|3|iii|ii|i|birinchi|ikkinchi|uchinchi)\s*(?:chi\s*)?(?:guruh|gr)\b")
_SUBS = (("temir", ("temir daftar", "temir daftari", "temir")),
         ("ayollar", ("ayollar daftar", "ayollar daftari")),
         ("yoshlar", ("yoshlar daftar", "yoshlar daftari")),
         ("xotin_qizlar", ("xotin qizlar reestr", "xotin qizlar reestri", "xotin qizlar")),
         ("reestr", ("ijtimoiy himoya reestr", "ijtimoiy himoya yagona reestr", "yagona reestr", "ijtimoiy reestr",
                     "ijtimoiy himoya reestri", "reestr")))


def _phrase(k: str) -> str:
    """Ko'p so'zli ibora — qo'shimcha bilan ham («daftariga», «reestri»); bitta so'z — aniq («Temirov» toifa emas)."""
    return rf"\b{re.escape(k)}" + (r"\w{0,5}\b" if " " in k else r"i?\b")


def disability_group(text) -> str:
    """«II guruh», «2-guruh», «III» (alohida «Nogironlik guruhi» katagida), «2» → «1» | «2» | «3»; topilmasa — bo'sh."""
    m = _DIS_GROUP.search(normalize_text(text))
    if not m:
        n = normalize_text(text).strip()
        return n if n in ("1", "2", "3") else _ROMAN.get(n, "")
    g = m.group(1)
    return _ROMAN.get(g, g)


def parse_label(text) -> list[tuple[str, str]]:
    """«Temir daftar», «Nogironligi bor (II guruh)», «Chin yetim, mehribonlik uyi» → [(toifa, kichik toifa)].
    Faqat «yetim» (yarim yetim bo'lishi mumkin) yoki tanilmagan matn — bo'sh ro'yxat."""
    t = normalize_text(text)
    if not t:
        return []
    out: list[tuple[str, str]] = []
    if any(w in t for w in ("nogiron", "invalid", "imkoniyati cheklangan")):
        out.append(("nogironlik", disability_group(t)))
    for sub, keys in _SUBS:
        if any(re.search(_phrase(k), t) for k in keys):
            out.append(("ijtimoiy", sub))
            if sub == "xotin_qizlar":  # «xotin-qizlar reestri» — ijtimoiy himoya reestri emas
                t = re.sub(r"\breestri?\b", "", t)
    if not any(c == "ijtimoiy" for c, _ in out) and ("ijtimoiy himoya" in t or "kam taminlangan" in t
                                                     or "ijtimoiy himoyaga muhtoj" in t):
        out.append(("ijtimoiy", "boshqa"))
    if any(w in t for w in ("chin yetim", "toliq yetim", "ota onasiz", "ikkala ota onasi", "chin etim")):
        out.append(("chin_yetim", ""))
    if any(w in t for w in ("mehribonlik", "bolalar uyi", "bolalar shaharchasi", "mexribonlik")):
        out.append(("mehribonlik", ""))
    return list(dict.fromkeys(out))


_NO = {"", "yoq", "yo q", "0", "no", "net", "false", "-", "—", "x yoq", "mavjud emas"}


def truthy(value) -> bool:
    """Keng jadval katagi: «ha», «bor», «+», «1», «✓» yoki biror izoh — belgilangan; bo'sh, «yo'q», «-», «0» — yo'q."""
    raw = str(value if value is not None else "").strip()
    if raw in ("+", "✓", "✔", "√", "v", "V", "x", "X"):
        return True
    return normalize_text(raw) not in _NO


# ---------------------------------------------------------------- o'qish
async def summary(scope: set[str] | None) -> dict:
    """Kurs holati kartalari: har bir toifa va kichik toifa bo'yicha talabalar soni (ko'rinish doirasida)."""
    rows = await db.fetchall("SELECT sc.student_id, sc.category, sc.sub, s.group_key FROM student_categories sc "
                             "JOIN students s ON s.id = sc.student_id")
    rows = [r for r in rows if scope is None or (r["group_key"] or "") in scope]
    out = {}
    for cat, c in CATS.items():
        mine = [r for r in rows if r["category"] == cat]
        out[cat] = {"title": c["title"], "short": c["short"], "students": len({r["student_id"] for r in mine}),
                    "subs": {k: len({r["student_id"] for r in mine if r["sub"] == k}) for k in c["subs"]}}
        if c["subs"]:
            out[cat]["subs"][""] = len({r["student_id"] for r in mine if not r["sub"]})
    return {"cats": out, "students": len({r["student_id"] for r in rows})}


async def listing(scope: set[str] | None, cat: str) -> list[dict]:
    if cat not in CATS:
        raise SocialError("bad_category", "Toifa noto'g'ri")
    rows = await db.fetchall(
        """SELECT sc.*, s.full_name, s.group_name, s.group_key, s.course, s.hemis_id FROM student_categories sc
           JOIN students s ON s.id = sc.student_id WHERE sc.category = ? ORDER BY s.group_name, s.full_name, sc.sub""", (cat,))
    return [{**r, "label": label(r["category"], r["sub"]), "sub_title": CATS[cat]["subs"].get(r["sub"], "")}
            for r in rows if scope is None or (r["group_key"] or "") in scope]


async def of_student(sid: int) -> list[dict]:
    rows = await db.fetchall("SELECT * FROM student_categories WHERE student_id = ? ORDER BY category, sub", (sid,))
    return [{**r, "label": label(r["category"], r["sub"])} for r in rows]


# ---------------------------------------------------------------- yozish
def _check(cat: str, sub: str) -> str:
    if cat not in CATS:
        raise SocialError("bad_category", "Toifa noto'g'ri")
    subs = CATS[cat]["subs"]
    sub = (sub or "").strip()
    if cat == "ijtimoiy":
        sub = sub or "boshqa"
    if sub and sub not in subs:
        raise SocialError("bad_sub", "Kichik toifa noto'g'ri")
    return sub if subs else ""


async def add(sid: int, cat: str, sub: str = "", note: str = "", source: str = "qolda", uid: int | None = None) -> bool:
    """Toifa beriladi (bor bo'lsa — izohi yangilanadi). Nogironlik — bitta yozuv: guruhi o'zgarsa almashtiriladi.
    Qaytaradi: yangi qo'shildimi."""
    sub = _check(cat, sub)
    note = (note or "").strip()[:300] or None
    if cat == "nogironlik":  # bitta yozuv; guruhi ko'rsatilmagan yangi yozuv aniq guruhni o'chirmaydi
        old = await db.fetchone("SELECT sub, note FROM student_categories WHERE student_id = ? AND category = ?", (sid, cat))
        if old and sub and old["sub"] != sub:  # guruhi o'zgardi — eski izoh (asos hujjat) yangisi bo'lmasa saqlanadi
            note = note or old["note"]
            await db.execute("DELETE FROM student_categories WHERE student_id = ? AND category = ?", (sid, cat))
        elif old:
            sub = old["sub"]
    old = await db.fetchone("SELECT 1 FROM student_categories WHERE student_id = ? AND category = ? AND sub = ?",
                            (sid, cat, sub))
    if old:
        if note:
            await db.execute("UPDATE student_categories SET note = ? WHERE student_id = ? AND category = ? AND sub = ?",
                             (note, sid, cat, sub))
        return False
    await db.execute("INSERT INTO student_categories (student_id, category, sub, note, source, set_by, set_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (sid, cat, sub, note, source if source in SOURCES else "qolda", uid,
                                                      now_iso()))
    return True


async def remove(sid: int, cat: str, sub: str = "") -> bool:
    cur = await db.conn.execute("DELETE FROM student_categories WHERE student_id = ? AND category = ? AND sub = ?",
                                (sid, cat, sub or ""))
    await db.conn.commit()
    return cur.rowcount > 0
