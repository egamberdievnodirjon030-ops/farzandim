"""Rasmiy hujjatlarda (buyruq, ogohlantirish, hayfsan va h.k.) boshqa talabalar ma'lumotlarini yashirish.

Ota-onaga faqat o'z farzandiga oid qism ko'rinadi. Ro'yxat yoki jadvaldagi boshqa talabalarning F.I.Sh.,
guruhi, ID raqami va shu qatordagi boshqa ma'lumotlari qora to'rtburchak bilan yopiladi. Natija
rasmga aylantirilgan PDF bo'ladi, shuning uchun yopilgan matn faylning ichida ham qolmaydi.

Matnli PDF (Word'dan saqlangan) pdfplumber bilan o'qiladi, jadval qatorlari chegaralari bo'yicha aniqlanadi.
Skanerlangan PDF Tesseract o'rnatilgan bo'lsa OCR bilan o'qiladi; bo'lmasa avtomatik yashirib bo'lmaydi.

Talabalar uch yo'l bilan topiladi: botdagi talabalar ro'yxati bo'yicha (familiya + ism yoki initsial),
familiyaga xos qo'shimchalar bo'yicha (-ov, -ova, -ev, -eva, o'g'li, qizi — bazada yo'q talabalar uchun)
va ID raqamlari bo'yicha. Rahbarlar (dekan, prorektor, koordinator) ismlari yashirilmaydi.
"""
from __future__ import annotations

import io
import logging
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import pdfplumber
import pypdfium2 as pdfium
from PIL import ImageDraw

from utils import normalize_text

log = logging.getLogger(__name__)

MAX_PAGES = 30
RENDER_DPI = 170
OCR_DPI = 300
_OCR_LANGS = ("uzb", "uzb_cyrl", "rus", "eng")

# Familiya qo'shimchalari va otasining ismi belgilari (normallashtirilgan, lotin)
_SURNAME_ENDINGS = ("ov", "ova", "ev", "eva", "yev", "yeva", "iy", "iyeva")
_PATRONYM_MARKERS = {"ogli", "qizi", "ugli", "kizi"}
_NOT_NAMES = {"studentov", "prepodavateley", "uchastnikov", "chlenov", "rabotnikov", "dekabrov"}
# Bu so'zlar bor qator — rahbar/imzo qatori: undagi noma'lum ismlar yashirilmaydi
_OFFICIAL = {"dekan", "dekani", "dekanat", "prorektor", "prorektori", "rektor", "rektori", "mudir", "mudiri",
             "kotib", "kotibi", "rais", "raisi", "direktor", "direktori", "boshligi", "tasdiqlayman", "imzo",
             "koordinator", "koordinatori", "koordinatorining", "tyutor", "tyutori", "tyutorning", "ijrochi",
             "tayyorladi", "kelishildi", "zamdekan", "nachalnik", "zamestitel", "dekana", "rektora"}
# «Mas'ullar:» bo'limi — undagi ismlar xodimlarniki, hech narsa yopilmaydi. Faqat aniq so'z shakllari va faqat
# qator boshida yoki ikki nuqta bilan («Mas'ullar:») — «mas'uliyat choralari» kabi jumla belgi hisoblanmaydi.
_KEEP_TRIGGERS = {"masul", "masullar", "masullari", "masuli", "javobgar", "javobgarlar", "javobgarlari", "ijrochi",
                  "ijrochilar", "otvetstvennie", "otvetstvenniy", "otvetstvennye", "otvetstvennyy", "otvetstvennyi",
                  "ispolnitel", "ispolniteli"}
# Shu so'z bilan boshlangan qator — yangi bo'lim: «Mas'ullar» bo'lagi shu yerda tugaydi
_SECTION_WORDS = {"asos", "asoslar", "ilova", "ilovalar", "tasdiqlayman", "buyuraman", "qaror", "osnovanie",
                  "prilozhenie", "prikazyvayu"}
_UZ_CASES = ("larining", "laridan", "lariga", "ning", "dan", "ga", "ka", "qa", "ni", "da", "ta")
_NUMBERED = re.compile(r"^\s*[\(\[]?\d{1,3}\s*[.)\]]")


# ---------------------------------------------------------------- tuzilmalar
@dataclass
class Word:
    text: str
    toks: list[str]
    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Page:
    width: float
    height: float
    words: list[Word]
    tables: list[list[tuple]] = field(default_factory=list)  # jadval -> qatorlar bbox ro'yxati
    ocr: bool = False


@dataclass
class Analysis:
    pages: list[Page]
    mode: str                    # text | ocr | mixed | none
    mentioned: list[int]         # hujjatda uchragan bazadagi talabalar (birinchi uchrash tartibida)
    roster: "Roster | None" = None
    error: str | None = None

    @property
    def readable(self) -> bool:
        return self.mode != "none" and not self.error


@dataclass
class Result:
    pdf: bytes
    boxes: int
    target_found: bool
    ambiguous: bool


@dataclass
class Hit:
    kind: str                    # target | other | ambiguous
    widx: set[int]


# ---------------------------------------------------------------- ismlarni solishtirish
def _base(t: str) -> str:
    for suf in _UZ_CASES:
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


def _sim(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    a2 = _base(a)
    if a2 == b:
        return True
    return abs(len(a2) - len(b)) <= 1 and SequenceMatcher(None, a2, b).ratio() >= 0.86


class Roster:
    def __init__(self, students: list[dict]):
        self.people: dict[int, dict] = {}
        self.by_prefix: dict[str, list[int]] = defaultdict(list)
        self.by_hemis: dict[str, int] = {}
        for s in students:
            toks = normalize_text(s["full_name"]).split()
            if len(toks) < 2:
                continue
            sid = s["id"]
            self.people[sid] = {"sur": toks[0], "first": toks[1], "rest": toks[2:]}
            self.by_prefix[toks[0][:2]].append(sid)
            hid = normalize_text(s.get("hemis_id") or "").replace(" ", "")
            if hid:
                self.by_hemis[hid] = sid

    def surname_candidates(self, tok: str) -> list[int]:
        return [sid for sid in self.by_prefix.get(tok[:2], []) if _sim(tok, self.people[sid]["sur"])]


def _flat(words: list[Word], idxs: list[int]) -> list[tuple[str, int]]:
    return [(t, i) for i in idxs for t in words[i].toks]


def _roster_matches(seq: list[tuple[str, int]], roster: Roster) -> list[tuple[int, int, set[int]]]:
    """(sid, ball, so'z indekslari): familiya + to'liq ism (2) yoki familiya + initsial (1)."""
    toks = [t for t, _ in seq]
    out = []
    for i, t in enumerate(toks):
        if len(t) < 4:
            continue
        for sid in roster.surname_candidates(t):
            p = roster.people[sid]
            score, used = 0, {seq[i][1]}
            for j in range(max(0, i - 3), min(len(toks), i + 4)):
                if j == i:
                    continue
                u = toks[j]
                if len(u) >= 3 and _sim(u, p["first"]):
                    score = max(score, 2)
                    used.add(seq[j][1])
                elif len(u) == 1 and abs(j - i) <= 2 and u == p["first"][0]:
                    score = max(score, 1)
                    used.add(seq[j][1])
                elif p["rest"] and len(u) >= 4 and any(_sim(u, r) for r in p["rest"]):
                    used.add(seq[j][1])
                elif u in _PATRONYM_MARKERS:
                    used.add(seq[j][1])
            if score:
                # yonidagi initsiallarni ham qo'shamiz (J.A.)
                for j in range(max(0, i - 3), min(len(toks), i + 4)):
                    if len(toks[j]) == 1 and toks[j].isalpha():
                        used.add(seq[j][1])
                out.append((sid, score + (t == p["sur"]), used))
    return out


def _generic_spans(words: list[Word], idxs: list[int]) -> list[set[int]]:
    """Bazada yo'q odamlar: familiya qo'shimchasi yoki o'g'li/qizi bo'yicha."""
    spans = []
    for k, wi in enumerate(idxs):
        w = words[wi]
        raw = w.text.strip("«»\"'(),.;:")
        if not raw or not (raw[0].isupper()):
            continue
        toks = [_base(t) for t in w.toks if len(t) >= 4]
        is_sur = any(t.endswith(_SURNAME_ENDINGS) and t not in _NOT_NAMES and len(t) >= 5 for t in toks)
        nxt = [words[j] for j in idxs[k + 1:k + 4]]
        is_patr = any(set(n.toks) & _PATRONYM_MARKERS for n in nxt[:2])
        if not (is_sur or is_patr):
            continue
        span = {wi}
        # atrofdagi bosh harfli so'zlar va initsiallar (Ism, Otasining ismi, J.A.)
        for j in range(k + 1, min(len(idxs), k + 4)):
            n = words[idxs[j]]
            t = n.text.strip("«»\"'(),.;:")
            if t and (t[0].isupper() or set(n.toks) & _PATRONYM_MARKERS):
                span.add(idxs[j])
                if set(n.toks) & _PATRONYM_MARKERS:
                    break
            else:
                break
        for j in range(k - 1, max(-1, k - 3), -1):
            n = words[idxs[j]]
            if all(len(t) == 1 for t in n.toks) and n.toks:
                span.add(idxs[j])
            else:
                break
        spans.append(span)
    return spans


def _analyze_group(words: list[Word], idxs: list[int], roster: Roster, target: int | None,
                   target_hemis: str) -> tuple[list[Hit], bool]:
    """Bir qator (yoki jadval qatori) ichidagi odamlar va ID lar. Qaytaradi: (topilganlar, rasmiy_qator)."""
    seq = _flat(words, idxs)
    toks = {t for t, _ in seq}
    official = bool(toks & _OFFICIAL)
    hits: list[Hit] = []
    # bazadagi talabalar: bir-biriga tegib turgan mosliklardan eng yaxshisi
    matches = sorted(_roster_matches(seq, roster), key=lambda m: -m[1])
    taken: list[tuple[set[int], int, int]] = []  # (so'zlar, sid, ball)
    for sid, score, used in matches:
        clash = next((c for c in taken if c[0] & used), None)
        if clash is None:
            taken.append((set(used), sid, score))
        elif clash[2] == score and clash[1] != sid and target in (sid, clash[1]):
            # target va ismdoshi ism bo'yicha teng: qatordagi HEMIS ID hal qiladi (qaysi birining ID si yozilgan bo'lsa —
            # qator o'shaniki); ID bo'lmasa — noaniq (ehtiyot uchun yopiladi, kurs koordinatori ogohlantiriladi)
            other = clash[1] if sid == target else sid
            other_ids = {h for h, x in roster.by_hemis.items() if x == other}
            if target_hemis and normalize_text(target_hemis) in toks and not (other_ids & toks):
                winner = target
            elif other_ids & toks and not (target_hemis and normalize_text(target_hemis) in toks):
                winner = other
            else:
                winner = -1
            clash[0].update(used)
            taken[taken.index(clash)] = (clash[0], winner, score)
    for used, sid, _ in taken:
        kind = "ambiguous" if sid == -1 else ("target" if sid == target else "other")
        hits.append(Hit(kind, used))
    covered = set().union(*(h.widx for h in hits)) if hits else set()
    # bazada yo'q odamlar (rasmiy qatorlarda emas)
    if not official:
        for span in _generic_spans(words, idxs):
            if not span & covered:
                hits.append(Hit("other", span))
                covered |= span
    # ID raqamlar: bazadagi boshqa talabaning ID si yoki 9+ xonali raqam
    for wi in idxs:
        for t in words[wi].toks:
            sid = roster.by_hemis.get(t)
            if (sid is not None and sid != target) or (t.isdigit() and len(t) >= 9 and t != target_hemis):
                if wi not in covered:
                    hits.append(Hit("other", {wi}))
                    covered.add(wi)
    return hits, official


# ---------------------------------------------------------------- o'qish
def ocr_languages() -> str | None:
    if not shutil.which("tesseract"):
        return None
    try:
        import pytesseract
        have = set(pytesseract.get_languages(config=""))
    except Exception:
        return None
    langs = [l for l in _OCR_LANGS if l in have]
    return "+".join(langs) if langs else None


def _words_from_text(t: str) -> list[str]:
    return normalize_text(t).split()


def _read_text_page(pl_page) -> Page:
    words = []
    for w in pl_page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5):
        toks = _words_from_text(w["text"])
        if toks:
            words.append(Word(w["text"], toks, w["x0"], w["top"], w["x1"], w["bottom"]))
    tables = []
    try:
        for tb in pl_page.find_tables():
            rows = [r.bbox for r in tb.rows if r.bbox]
            if len(rows) >= 2:
                tables.append(rows)
    except Exception as e:  # jadval topilmasa ham ishlayveramiz
        log.debug("find_tables: %s", e)
    return Page(float(pl_page.width), float(pl_page.height), words, tables)


def _remove_lines(img):
    """Jadval chiziqlarini oq rangga bo'yaydi (OCR ularni ko'rib matnni tashlab ketmasligi uchun)."""
    import numpy as np
    a = np.array(img)
    bw = (a < 160).astype(np.int32)
    out = a.copy()
    for axis, length in ((1, max(80, a.shape[1] // 25)), (0, max(60, a.shape[0] // 40))):
        m = bw if axis == 1 else bw.T
        c = np.concatenate([np.zeros((m.shape[0], 1), np.int32), np.cumsum(m, axis=1)], axis=1)
        full = (c[:, length:] - c[:, :-length]) == length          # shu joydan boshlanib uzun chiziq bor
        cc = np.concatenate([np.zeros((m.shape[0], 1), np.int32), np.cumsum(full, axis=1)], axis=1)
        idx = np.arange(m.shape[1])
        lo = np.clip(idx - length + 1, 0, full.shape[1])
        hi = np.clip(idx + 1, 0, full.shape[1])
        covered = (cc[:, hi] - cc[:, lo]) > 0
        if axis == 1:
            out[covered] = 255
        else:
            out.T[covered] = 255
    from PIL import Image
    return Image.fromarray(out)


def _ocr_words(img, langs: str, psm: int, k: float) -> list[Word]:
    import pytesseract
    data = pytesseract.image_to_data(img, lang=langs, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    words = []
    for j, text in enumerate(data["text"]):
        text = (text or "").strip()
        if not text or float(data["conf"][j]) < 20:
            continue
        toks = _words_from_text(text)
        if toks:
            x, y, w, h = data["left"][j], data["top"][j], data["width"][j], data["height"][j]
            words.append(Word(text, toks, x * k, y * k, (x + w) * k, (y + h) * k))
    return words


def _overlap(a: Word, b: Word) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    area = max(1e-6, min((a.x1 - a.x0) * (a.bottom - a.top), (b.x1 - b.x0) * (b.bottom - b.top)))
    return ix * iy / area


def _read_ocr_page(pdf: pdfium.PdfDocument, i: int, langs: str) -> Page:
    """Skanerlangan sahifa: ikki xil o'qish natijasi birlashtiriladi — biror so'z o'tkazib yuborilmasligi uchun."""
    page = pdf[i]
    w_pt, h_pt = page.get_size()
    img = page.render(scale=OCR_DPI / 72).to_pil().convert("L")
    k = 72 / OCR_DPI
    words = _ocr_words(img, langs, 3, k)                 # sahifa tahlili (oddiy matn)
    for w in _ocr_words(_remove_lines(img), langs, 11, k):  # chiziqsiz, tarqoq matn (jadvallar)
        if not any(_overlap(w, v) > 0.5 for v in words):
            words.append(w)
    return Page(w_pt, h_pt, words, [], ocr=True)


def analyze(pdf_bytes: bytes, students: list[dict]) -> Analysis:
    """PDF ni o'qiydi va unda bazadagi qaysi talabalar uchrashini aniqlaydi (sinxron — thread'da chaqiring)."""
    roster = Roster(students)
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        n = len(pdf)
        if n > MAX_PAGES:
            return Analysis([], "none", [], roster, f"hujjat juda uzun ({n} sahifa, ko'pi bilan {MAX_PAGES})")
        pages: list[Page] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pl:
            for i, pl_page in enumerate(pl.pages):
                pages.append(_read_text_page(pl_page))
        langs = None
        for i, pg in enumerate(pages):
            if len(pg.words) < 5:  # matn qatlami yo'q — skanerlangan sahifa
                langs = langs or ocr_languages()
                if langs:
                    pages[i] = _read_ocr_page(pdf, i, langs)
        text_pages = sum(1 for p in pages if not p.ocr and len(p.words) >= 5)
        ocr_pages = sum(1 for p in pages if p.ocr)
        empty = sum(1 for p in pages if len(p.words) < 5)
        if empty == len(pages):
            mode = "none"
        elif ocr_pages and text_pages:
            mode = "mixed"
        else:
            mode = "ocr" if ocr_pages else "text"
    except Exception as e:
        log.warning("PDF ni o'qib bo'lmadi: %s", e)
        return Analysis([], "none", [], roster, "PDF faylni ochib bo'lmadi (fayl buzilgan yoki parol bilan himoyalangan)")

    mentioned: list[int] = []
    for pg in pages:
        for idxs in _groups(pg):
            for sid, score, _ in _roster_matches(_flat(pg.words, idxs), roster):
                if sid not in mentioned:
                    mentioned.append(sid)
            for wi in idxs:
                for t in pg.words[wi].toks:
                    sid = roster.by_hemis.get(t)
                    if sid is not None and sid not in mentioned:
                        mentioned.append(sid)
    return Analysis(pages, mode, mentioned, roster)


# ---------------------------------------------------------------- qatorlarga ajratish
def _in_box(w: Word, box: tuple) -> bool:
    x0, top, x1, bottom = box
    return x0 - 1 <= w.cx <= x1 + 1 and top - 1 <= w.cy <= bottom + 1


def _table_rows(pg: Page) -> list[tuple[list[tuple], list[list[int]]]]:
    out = []
    for rows in pg.tables:
        out.append((rows, [[i for i, w in enumerate(pg.words) if _in_box(w, r)] for r in rows]))
    return out


def _lines(pg: Page, exclude: set[int]) -> list[list[int]]:
    """Jadvaldan tashqaridagi so'zlarni qatorlarga ajratadi (vertikal markaz bo'yicha)."""
    idxs = sorted((i for i in range(len(pg.words)) if i not in exclude), key=lambda i: (pg.words[i].cy, pg.words[i].x0))
    lines: list[list[int]] = []
    for i in idxs:
        w = pg.words[i]
        h = max(w.bottom - w.top, 4)
        if lines:
            last = lines[-1]
            ref = sum(pg.words[j].cy for j in last) / len(last)
            if abs(w.cy - ref) <= h * 0.45:
                last.append(i)
                continue
        lines.append([i])
    for ln in lines:
        ln.sort(key=lambda j: pg.words[j].x0)
    return lines


def _groups(pg: Page) -> list[list[int]]:
    in_tables = set()
    groups = []
    for _, row_idxs in _table_rows(pg):
        for r in row_idxs:
            groups.append(r)
            in_tables.update(r)
    return groups + _lines(pg, in_tables)


def _keep_trigger(pg: Page, idxs: list[int]) -> bool:
    """Qator «Mas'ullar:» (yoki «Mas'ul», «Javobgar», «Ijrochi») bo'limini boshlaydimi."""
    for pos, wi in enumerate(idxs):
        w = pg.words[wi]
        if not set(w.toks) & _KEEP_TRIGGERS:
            continue
        if pos <= 1 or w.text.rstrip().endswith(":"):  # «3. Mas'ullar ...» yoki «... uchun mas'ullar:»
            return True
    return False


def _section_start(pg: Page, idxs: list[int]) -> bool:
    for wi in idxs[:2]:
        if set(pg.words[wi].toks) & _SECTION_WORDS:
            return True
    return False


def _is_record(pg: Page, idxs: list[int]) -> bool:
    """Ro'yxat bandi yoki jadval qatoriga o'xshash qator (raqam bilan boshlanadi yoki ichida bir nechta son bor)."""
    text = " ".join(pg.words[i].text for i in idxs)
    digits = sum(any(ch.isdigit() for ch in pg.words[i].text) for i in idxs)
    return bool(_NUMBERED.match(text)) or digits >= 2


def _bbox(pg: Page, idxs, pad: float = 1.5) -> tuple:
    ws = [pg.words[i] for i in idxs]
    return (min(w.x0 for w in ws) - pad, min(w.top for w in ws) - pad,
            max(w.x1 for w in ws) + pad, max(w.bottom for w in ws) + pad)


# ---------------------------------------------------------------- yashirish rejasi
def plan(an: Analysis, target_sid: int, target_hemis: str = "") -> tuple[list[list[tuple]], bool, bool]:
    """Har bir sahifa uchun qora to'rtburchaklar ro'yxati, talabaning o'zi topildimi, noaniqlik bormi."""
    thid = normalize_text(target_hemis).replace(" ", "")
    all_boxes, found, ambiguous = [], False, False
    for pg in an.pages:
        boxes: list[tuple] = []
        in_tables: set[int] = set()
        # 1) jadvallar: sarlavhadan keyingi, shu talabaga tegishli bo'lmagan qatorlar to'liq yopiladi
        for rows, row_idxs in _table_rows(pg):
            info = []
            keep_rows = {k for k, idxs in enumerate(row_idxs) if _keep_trigger(pg, idxs)}
            for r, idxs in zip(rows, row_idxs):
                in_tables.update(idxs)
                hits, official = _analyze_group(pg.words, idxs, an.roster, target_sid, thid)
                info.append((r, idxs, hits, official))
            if 0 in keep_rows:  # «Mas'ullar» jadvali — butunlay o'zgarishsiz
                continue
            person_rows = [k for k, (_, _, hits, _) in enumerate(info) if hits and k not in keep_rows]
            if not person_rows:
                continue
            first, last = person_rows[0], person_rows[-1]
            for k, (r, idxs, hits, official) in enumerate(info):
                kinds = {h.kind for h in hits}
                found |= "target" in kinds
                ambiguous |= "ambiguous" in kinds
                if k < first or k > last or k in keep_rows:
                    continue
                if kinds == {"target"} or (not hits and official):
                    continue
                if "target" in kinds and len(kinds) > 1:
                    # bitta katakda ikki odam — faqat boshqalarini yopamiz
                    boxes += [_bbox(pg, h.widx) for h in hits if h.kind != "target"]
                    continue
                boxes.append((r[0] + 0.5, r[1] + 0.5, r[2] - 0.5, r[3] - 0.5))
        # 2) jadvaldan tashqari qatorlar
        lines = _lines(pg, in_tables)
        # ro'yxat qatori yopilganda qora chiziq matnning butun kengligiga cho'ziladi:
        # skanerda OCR o'qiy olmagan kataklar (soat, sana va h.k.) ham ochiq qolmasin
        left = min((w.x0 for w in pg.words), default=0) - 2
        right = max((w.x1 for w in pg.words), default=pg.width) + 2

        def wide(idxs):
            x0, top, x1, bottom = _bbox(pg, idxs)
            return (min(x0, left), top, max(x1, right), bottom)

        heights = sorted(pg.words[ln[0]].bottom - pg.words[ln[0]].top for ln in lines) or [10]
        lh = heights[len(heights) // 2]
        block = False          # oldingi raqamli band yopildi — uning davomi ham yopiladi
        keep = False           # «Mas'ullar:» bo'limi ichidamiz — hech narsa yopilmaydi
        prev_punct, prev_bottom = True, None
        for ln in lines:
            text = " ".join(pg.words[i].text for i in ln).strip()
            top = min(pg.words[i].top for i in ln)
            if _keep_trigger(pg, ln):
                keep, block = True, False
            elif keep and (prev_bottom is None or top - prev_bottom > lh * 2.5 or _section_start(pg, ln)):
                keep = False
            if keep:
                prev_punct, prev_bottom = text.endswith((".", ";", ":", "!", "?")), max(pg.words[i].bottom for i in ln)
                continue
            close = prev_bottom is not None and top - prev_bottom < lh * 1.1
            numbered = bool(_NUMBERED.match(text))
            hits, official = _analyze_group(pg.words, ln, an.roster, target_sid, thid)
            kinds = {h.kind for h in hits}
            found |= "target" in kinds
            ambiguous |= "ambiguous" in kinds
            others = [h for h in hits if h.kind != "target"]
            if block and not numbered and not prev_punct and close and "target" not in kinds:
                boxes.append(wide(ln))                         # yopilgan bandning davomi
            else:
                block = False
                if others and "target" not in kinds and _is_record(pg, ln):
                    boxes.append(wide(ln))                     # butun ro'yxat bandi / jadval qatori
                    block = numbered
                else:
                    boxes += [_bbox(pg, h.widx) for h in others]   # matn ichidagi ismlar
            prev_punct = text.endswith((".", ";", ":", "!", "?"))
            prev_bottom = max(pg.words[i].bottom for i in ln)
        all_boxes.append(boxes)
    return all_boxes, found, ambiguous


def render(pdf_bytes: bytes, pages_boxes: list[list[tuple]], an: Analysis) -> bytes:
    """Sahifalarni rasmga aylantiradi, qora to'rtburchaklarni chizadi va yangi PDF yig'adi."""
    pdf = pdfium.PdfDocument(pdf_bytes)
    images = []
    for i in range(len(pdf)):
        page = pdf[i]
        img = page.render(scale=RENDER_DPI / 72).to_pil().convert("RGB")
        w_pt = an.pages[i].width if i < len(an.pages) else page.get_size()[0]
        h_pt = an.pages[i].height if i < len(an.pages) else page.get_size()[1]
        sx, sy = img.width / w_pt, img.height / h_pt
        draw = ImageDraw.Draw(img)
        for x0, top, x1, bottom in (pages_boxes[i] if i < len(pages_boxes) else []):
            draw.rectangle([x0 * sx, top * sy, x1 * sx, bottom * sy], fill="black")
        images.append(img)
    out = io.BytesIO()
    images[0].save(out, "PDF", save_all=True, append_images=images[1:], resolution=RENDER_DPI, quality=82)
    return out.getvalue()


def redact_for(pdf_bytes: bytes, an: Analysis, target_sid: int, target_hemis: str = "") -> Result:
    """Shu talabaning ota-onasi uchun nusxa. Yashiradigan joy bo'lmasa, asl fayl qaytadi."""
    boxes, found, ambiguous = plan(an, target_sid, target_hemis)
    n = sum(len(b) for b in boxes)
    return Result(render(pdf_bytes, boxes, an) if n else pdf_bytes, n, found, ambiguous)
