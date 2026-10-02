"""Ma'lumotlarni ota-onaning tilida ko'rsatish — faqat ko'rsatish paytida (bazadagi asl qiymatlar o'zgarmaydi,
chunki import va talabalarni moslash ular bilan ishlaydi).

  • Ismlar (talaba, kurs koordinatori, o'qituvchi): rus tilida — o'zbek lotinidan rus kirilliga qoidalar bo'yicha
    («Karimov Jasur» → «Каримов Жасур», «o‘g‘li» → «угли»); talabalar faylida «F.I.Sh. (kirill)» ustuni bo'lsa —
    o'sha rasmiy yozuv. Ingliz tilida — asl lotin yozuvi.
  • Atamalar (fan, fakultet, nazorat turi, xona, izoh): tarjima — avval kurs koordinatori kiritgan (/tarjimalar),
    keyin ichki lug'at (terms_data.py). Tarjimasi yo'q bo'lsa: rus tilida — kirill harflarida (lotin harfi
    ko'rinmasin), ingliz tilida — asl nomi.
"""
from __future__ import annotations

import re

from i18n import get_lang
from terms_data import TERMS
from utils import normalize_text

_APOS = "ʻ‘'`’ʼ"
_VOWELS = "aeiouáóúíıäöü"
_MAP = {
    "a": "а", "b": "б", "c": "с", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х", "i": "и", "j": "ж", "k": "к",
    "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "w": "в", "x": "х", "y": "й", "z": "з",
    # qoraqalpoq va boshqa harflar
    "á": "а", "ó": "о", "ú": "у", "í": "ы", "ı": "ы", "ń": "н", "ǵ": "г", "ş": "ш", "ç": "ч", "ö": "ё", "ü": "ю",
    "ä": "а",
}
_DIGRAPHS = {"sh": "ш", "ch": "ч", "ts": "ц", "yo": "ё", "yu": "ю", "ya": "я", "ye": "е"}
_WORD = re.compile(r"[A-Za-zÀ-ɏ" + _APOS + r"]+")


def _case(src: str, res: str) -> str:
    """Harfning katta-kichikligi manbadagidek (qisqartmalar ham: «BRMga» → «БРМга»)."""
    return res.upper() if src[:1].isupper() else res


def _translit_word(w: str) -> str:
    lw = w.lower()
    out, i = [], 0
    while i < len(lw):
        ch, nx = lw[i], lw[i + 1] if i + 1 < len(lw) else ""
        if ch in "og" and nx and nx in _APOS:          # o‘ → у, g‘ → г
            out.append(_case(w[i], "у" if ch == "o" else "г"))
            i += 2
            continue
        if ch in _APOS:                                  # tutuq belgisi: so'z ichida — ъ, chetida (qo'shtirnoq) — tashlanadi
            out.append("ъ" if 0 < i < len(lw) - 1 else "")
            i += 1
            continue
        two = lw[i:i + 2]
        if two in _DIGRAPHS:
            out.append(_case(w[i], _DIGRAPHS[two]))
            i += 2
            continue
        if ch == "e":
            prev = lw[i - 1] if i else ""
            # so'z boshida va unlidan keyin — э; lekin familiya qo'shimchasi «-aev/-oev» — ев (Кошкарбаев)
            e = "э" if (not prev or prev in _VOWELS or prev in _APOS) and nx != "v" else "е"
            out.append(_case(w[i], e))
        else:
            out.append(_case(w[i], _MAP.get(ch, ch)))
        i += 1
    res = "".join(out)
    if len(w) > 1 and w.isupper():
        return res.upper()
    return res


def translit_ru(text: str) -> str:
    """O'zbek lotinidan rus kirilliga: «Egamberdiyev Nodirbek» → «Эгамбердиев Нодирбек»."""
    return _WORD.sub(lambda m: _translit_word(m.group()), text or "")


# ---------------------------------------------------------------- atamalar (fan, fakultet, ...)
def _split(text: str) -> tuple[str, str]:
    """«Fransuz tili I» → («Fransuz tili», «I»); «Jahon adabiyoti (c)» → («Jahon adabiyoti», «(c)»)."""
    words = (text or "").split()
    tail = []
    while len(words) > 1 and re.fullmatch(r"[IVX]{1,4}|\d{1,2}|\(.{1,3}\)", words[-1]):
        tail.insert(0, words.pop())
    return " ".join(words), " ".join(tail)


def term_key(text: str) -> str:
    return normalize_text(_split(text)[0])


_BUILTIN: dict[str, tuple[str, str]] = {term_key(k): v for k, v in TERMS.items()}
_CUSTOM: dict[str, dict] = {}  # kurs koordinatori kiritgan tarjimalar (central.db) — ichki lug'atdan ustun


def set_custom(rows: list[dict]) -> None:
    _CUSTOM.clear()
    for r in rows:
        _CUSTOM[r["term_key"]] = r


def known(text: str, lang: str) -> bool:
    k = term_key(text)
    c = _CUSTOM.get(k)
    return bool(c and c.get(lang)) or k in _BUILTIN


def term(text: str | None, lang: str | None = None) -> str:
    """Fan, fakultet, nazorat turi, xona, izoh — ota-ona tilida."""
    lang = lang or get_lang()
    if not text or lang == "uz":
        return text or ""
    base, tail = _split(str(text).strip())
    k = normalize_text(base)
    c = _CUSTOM.get(k)
    if c and c.get(lang):
        res = c[lang]
    elif k in _BUILTIN:
        res = _BUILTIN[k][0 if lang == "ru" else 1]
    else:
        res = translit_ru(base) if lang == "ru" else base
    if tail:  # rim raqamlari (I, II, III) rus tilida ham lotinda qoladi; «(c)» kabi belgilar — kirillda
        res += " " + " ".join(t if re.fullmatch(r"[IVX]{1,4}|\d{1,2}", t) or lang != "ru" else translit_ru(t)
                              for t in tail.split())
    return res


def person(name: str | None, lang: str | None = None) -> str:
    """Kurs koordinatori, o'qituvchi — rus tilida kirillda."""
    lang = lang or get_lang()
    return translit_ru(name or "") if lang == "ru" else (name or "")


def student_name(st: dict, lang: str | None = None) -> str:
    """Talaba ismi: rus tilida — rasmiy kirill yozuvi (bo'lsa) yoki qoidalar bo'yicha kirill."""
    lang = lang or get_lang()
    if lang == "ru":
        return st.get("full_name_cyr") or translit_ru(st.get("full_name") or "")
    return st.get("full_name") or ""


async def reload() -> None:
    """Kurs koordinatori kiritgan tarjimalarni umumiy ro'yxatdan (central.db) o'qiydi."""
    from tenancy import central
    set_custom(await central.all_terms())


# ---------------------------------------------------------------- kurs koordinatori yozgan matnlar (e'lon, ma'lumot)
_SECTION = re.compile(r"^[ \t]*(?:-{2,}|#)[ \t]*(uz|ru|en)[ \t]*$|^[ \t]*(🇺🇿|🇷🇺|🇬🇧)[ \t]*$", re.M | re.I)
_FLAG = {"🇺🇿": "uz", "🇷🇺": "ru", "🇬🇧": "en"}
_TAG = re.compile(r"(<[^>]+>|&[a-z]+;|https?://\S+)")


def sections(text: str) -> dict[str, str]:
    """E'lon matni tillar bo'yicha: «---ru» / «---en» (yoki 🇷🇺 / 🇬🇧) qatoridan keyingi qism — o'sha tilda;
    birinchi belgigacha — o'zbekcha."""
    text = text or ""
    marks = list(_SECTION.finditer(text))
    if not marks:
        return {"uz": text.strip()}
    out = {"uz": text[:marks[0].start()].strip()}
    for i, m in enumerate(marks):
        lang = (m.group(1) or _FLAG.get(m.group(2), "uz")).lower()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out[lang] = text[m.end():end].strip()
    return {k: v for k, v in out.items() if v}


def translit_html(html: str) -> str:
    """HTML matnni kirillga o'giradi — teglar, havolalar va &-belgilarga tegmaydi."""
    return "".join(part if _TAG.fullmatch(part) else translit_ru(part) for part in _TAG.split(html or ""))


def pick(text: str, lang: str | None = None) -> str:
    """Ota-ona tilidagi qism; bo'lmasa — rus tilida o'zbekcha matn kirill harflarida, ingliz tilida — o'zbekcha."""
    lang = lang or get_lang()
    sec = sections(text)
    if sec.get(lang):
        return sec[lang]
    base = sec.get("uz") or next(iter(sec.values()), "")
    return translit_html(base) if lang == "ru" else base
