"""Word (.docx) shablonlarini to'ldirish — qo'shimcha kutubxonasiz (zip + XML matn sifatida).

Shablonda {{KALIT}} belgilari: matn ichida — oddiy qiymat, jadval satrida {{T_...}} — har bir talaba uchun shu satr
nusxalanadi ({{T_N}} — tartib raqami). Word belgini bir necha bo'lakka (run) bo'lib saqlagan bo'lsa ham topiladi.
Shakl (shrift, qalinlik) belgining birinchi bo'lagidagidek qoladi. Rasm, sarlavha, matn oynalari (text box) o'zgarmaydi.
"""
from __future__ import annotations

import html
import io
import re
import zipfile

_T = re.compile(r"<w:t(\s[^>]*)?>(.*?)</w:t>|<w:t(\s[^>]*)?/>", re.S)
_PH = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_PARTS = re.compile(r"word/(document|header\d*|footer\d*)\.xml$")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _texts(xml: str) -> list[tuple[int, int, str, str]]:
    """w:t elementlari: (boshi, oxiri, atributlar, matn)."""
    out = []
    for m in _T.finditer(xml):
        if m.group(2) is not None:
            out.append((m.start(), m.end(), m.group(1) or "", html.unescape(m.group(2))))
        else:
            out.append((m.start(), m.end(), m.group(3) or "", ""))
    return out


def _render(attrs: str, text: str) -> str:
    if "xml:space" not in attrs:
        attrs = (attrs + ' xml:space="preserve"') if attrs else ' xml:space="preserve"'
    return f"<w:t{attrs}>{_esc(text)}</w:t>"


def replace_text(xml: str, old: str, new: str, count: int = -1) -> tuple[str, int]:
    """Hujjat matnidagi `old` ni (bir necha w:t ga bo'lingan bo'lsa ham) `new` ga almashtiradi. Qaytaradi: (xml, soni)."""
    done = 0
    pos_from = 0  # birlashgan matndagi qidiruv boshi (almashtirilgan matn qayta ko'rilmasin)
    while count < 0 or done < count:
        ts = _texts(xml)
        full = "".join(t[3] for t in ts)
        i = full.find(old, pos_from)
        if i < 0 or not old:
            break
        j = i + len(old)
        # i va j qaysi elementlarga tushadi
        acc, first, last, o0, o1 = 0, None, None, 0, 0
        for k, (_, _, _, t) in enumerate(ts):
            if first is None and i < acc + len(t):
                first, o0 = k, i - acc
            if first is not None and j <= acc + len(t):
                last, o1 = k, j - acc
                break
            acc += len(t)
        if first is None or last is None:
            break
        pieces, prev = [], 0
        for k in range(first, last + 1):
            s, e, attrs, t = ts[k]
            if k == first and k == last:
                nt = t[:o0] + new + t[o1:]
            elif k == first:
                nt = t[:o0] + new
            elif k == last:
                nt = t[o1:]
            else:
                nt = ""
            pieces.append(xml[prev:s])
            pieces.append(_render(attrs, nt))
            prev = e
        pieces.append(xml[prev:])
        xml = "".join(pieces)
        pos_from = i + len(new)
        done += 1
    return xml, done


def normalize_placeholders(xml: str) -> str:
    """Bo'linib ketgan {{KALIT}} larni bitta w:t ga yig'adi (Word imlo tekshiruvi/tahrir izlari bo'lib yuboradi)."""
    full = "".join(t[3] for t in _texts(xml))
    for ph in dict.fromkeys(m.group(0) for m in _PH.finditer(full)):
        xml, _ = replace_text(xml, ph, "{{" + _PH.match(ph).group(1) + "}}")
    return xml


def _value_xml(v) -> str:
    """Qiymat → w:t ichidagi matn (qator ko'chirish — w:br)."""
    s = "" if v is None else str(v)
    parts = [_esc(p) for p in s.split("\n")]
    return '</w:t><w:br/><w:t xml:space="preserve">'.join(parts)


def _sub_scalars(xml: str, values: dict) -> str:
    def rep(m):
        key = m.group(1)
        return _value_xml(values.get(key, "")) if not key.startswith("T_") else m.group(0)
    # faqat w:t ichidagi belgilar almashtiriladi
    return _T.sub(lambda m: m.group(0) if m.group(2) is None else
                  (f"<w:t{m.group(1) or ''}>" + _PH.sub(rep, m.group(2)) + "</w:t>"), xml)


def _rows(xml: str, rows: list[dict]) -> str:
    """{{T_...}} bor jadval satrini har bir yozuv uchun nusxalaydi."""
    while True:
        k = xml.find("{{T_")
        if k < 0:
            return xml
        s = max(m.start() for m in re.finditer(r"<w:tr[\s>]", xml[:k])) if re.search(r"<w:tr[\s>]", xml[:k]) else -1
        e = xml.find("</w:tr>", k)
        if s < 0 or e < 0:  # jadvaldan tashqarida — oddiy qiymat sifatida o'chiriladi
            return _PH.sub(lambda m: "" if m.group(1).startswith("T_") else m.group(0), xml)
        e += len("</w:tr>")
        tpl = xml[s:e]
        out = []
        for n, r in enumerate(rows, 1):
            vals = {"T_N": n, **{("T_" + key if not key.startswith("T_") else key): v for key, v in r.items()}}
            out.append(_PH.sub(lambda m: _value_xml(vals.get(m.group(1), "")) if m.group(1).startswith("T_") else m.group(0), tpl))
        xml = xml[:s] + "".join(out) + xml[e:]


def placeholders(data: bytes) -> set[str]:
    """Shablondagi {{KALIT}} lar (yuklangan shablonni tekshirish uchun)."""
    found: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if _PARTS.search(name):
                xml = normalize_placeholders(z.read(name).decode("utf-8"))
                found |= {m.group(1) for m in _PH.finditer("".join(t[3] for t in _texts(xml)))}
    return found


def fill(data: bytes, values: dict, rows: list[dict] | None = None) -> bytes:
    """Shablonni to'ldiradi: values — {{KALIT}} lar, rows — jadval satrlari ({"FISH": …, "BOSQICH": …})."""
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            raw = src.read(item.filename)
            if _PARTS.search(item.filename):
                xml = normalize_placeholders(raw.decode("utf-8"))
                xml = _rows(xml, rows or [])
                xml = _sub_scalars(xml, values)
                raw = xml.encode("utf-8")
            dst.writestr(item, raw)
    return buf.getvalue()


def text_of(data: bytes) -> str:
    """Hujjat matni (tekshirish va testlar uchun): paragraflar — qatorlar, jadval kataklari — « | »."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = xml.replace("</w:p>", "\n").replace("</w:tc>", " | ").replace("<w:br/>", "\n")
    return html.unescape(re.sub(r"<[^>]+>", "", xml))
