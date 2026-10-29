"""Manzilga qanday boriladi: koordinata, eng yaqin bekatlar, avtobuslar, metro.

Talabaning ijara manzili matn ko'rinishida kiritiladi. Koordinator tashrifga
borayotganda unga amaliy narsa kerak: qaysi bekatda tushish, qaysi avtobus
boradi, metro yaqinmi. Shu modul manzilni xaritadagi nuqtaga aylantiradi va
atrofidagi jamoat transportini topadi.

Ma'lumot manbalari:

  joy     — Yandex Geocoder (`.env` da YANDEX_GEOCODER_KEY bo'lsa) yoki
            OpenStreetMap (kalit kerak emas). Manzil ichida koordinata yoki
            xarita havolasi bo'lsa — o'sha olinadi. Hech biri topa olmasa,
            koordinator botga joylashuvni o'zi yuboradi.
  hududlar — shahar mavze, daha va mahallalarining tayyor ro'yxati (dastur
            bilan keladi). «Uchtepa tumani, 14-kvartal» kabi mavze nomi
            yozilmagan manzil shu ro'yxat orqali topiladi.
  bekatlar — OpenStreetMap (Overpass): bekatlar, ulardan o'tadigan marshrut
            raqamlari, metro bekatlari.

Tashqi xizmatlar sekin va har doim ham javob bermaydi, shuning uchun:

  * so'rovlar fon oqimida bajariladi — sayt ham, bot ham kutib qolmaydi;
  * natija bazada saqlanadi (`address_geo`) — har bir manzil bir marta
    so'raladi, bot xabarlari esa faqat bazadan o'qiydi;
  * xato bo'lsa, tanaffus uzayib boradigan qayta urinish belgilanadi.

Natija faqat kurs koordinatoriga ko'rsatiladi; talabaga hech narsa bormaydi.
"""
from __future__ import annotations

import json
import math
import queue
import re
import threading
import time
from datetime import timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urljoin, urlsplit

import logging
import urllib.error
import urllib.parse
import urllib.request

from . import geodb as db
from .sozlama import sozlama
from .util import APOSTROFLAR, iso, oddiy_ism, utc_hozir

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
TESKARI = "https://nominatim.openstreetmap.org/reverse"
YANDEX = "https://geocode-maps.yandex.ru/1.x/"
DAVLAT = "uz"

BEKAT_RADIUSI = 800          # metr: bekat shu masofadan uzoq bo'lsa foydasi yo'q
METRO_RADIUSI = 3000
YANGILASH_KUN = 30           # marshrutlar o'zgarib turadi — bekatlar qayta olinadi
KOCHA_UZUNLIGI = 1500        # metr: bundan uzun ko'chaning «o'rtasi» hech narsa bermaydi
HUDUD_RADIUSI = 1200         # metr: mavze markazidan shu masofadagi uy o'sha mavzeniki
HUDUD_CHEGARASI = 3000       # metr: bundan uzoqdagi natija boshqa joy — qabul qilinmaydi
BIR_JOY = 1500               # metr: ro'yxatdagi bir xil nomli yozuvlar shu masofada — bitta hudud
NATIJALAR_SONI = 8           # xaritadan bitta so'rovga shuncha natija olinadi va mosi tanlanadi


class YolXato(Exception):
    """Xarita xizmatiga ulanib bo'lmadi yoki javobi yaroqsiz."""


# ------------------------------------------------------------------ tarmoq

_http: Callable | None = None       # testlarda haqiqiy tarmoq o'rniga qo'yiladi
_uxla = time.sleep


def http_qoy(fn: Callable | None) -> None:
    """Testlar uchun: fn(url, params, data) -> JSON."""
    global _http
    _http = fn


def _sorov(url: str, params: dict | None = None, data: dict | None = None,
           kutish: float = 30):
    if _http is not None:
        return _http(url, params or {}, data)
    sarlavha = {"User-Agent": "jidu-tashrif/1.0 (universitet tashrif moduli)",
                "Accept-Language": "uz,ru;q=0.8"}
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=sarlavha),
                                    timeout=kutish) as javob:
            matn = javob.read()
    except urllib.error.HTTPError as e:
        raise YolXato(f"xizmat {e.code} javob qaytardi") from None
    except (urllib.error.URLError, OSError) as e:
        # Xato matnida manzil, manzilda esa kalit bo'lishi mumkin — u yozilmaydi.
        raise YolXato(f"ulanib bo'lmadi ({type(e).__name__})") from None
    try:
        return json.loads(matn)
    except ValueError:
        raise YolXato("javobni o'qib bo'lmadi") from None


# ------------------------------------------------------------- yordamchilar

def masofa(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Ikki nuqta orasidagi masofa, metrda (to'g'ri chiziq bo'yicha)."""
    f1, f2 = math.radians(a[0]), math.radians(b[0])
    df, dl = f2 - f1, math.radians(b[1] - a[1])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def _hududdami(lat: float, lon: float) -> bool:
    """Nuqta sozlangan shahar atrofidami (chalkash yoki tasodifiy sonlar emasmi)."""
    m_lat, m_lon = sozlama.geo_markaz
    return abs(lat - m_lat) <= 5 and abs(lon - m_lon) <= 8


_SON = r"(-?\d{1,3}\.\d{3,})"
_JUFT = _SON + r"\s*[,;\s]\s*" + _SON
_KOORD = re.compile(_JUFT)
# Xarita havolasida bir nechta koordinata bo'ladi: xaritaning markazi va
# belgilangan nuqta. Kerakligi — nuqta; shuning uchun u birinchi qidiriladi.
_NUQTA_QOLIPLARI = [
    re.compile(r"!3d" + _SON + r"!4d" + _SON),                         # Google: tanlangan joy
    re.compile(r"(?:whatshere|poi)\[point\]=" + _JUFT),                # Yandex: belgilangan nuqta
    re.compile(r"mlat=" + _SON + r"&mlon=" + _SON),                    # OpenStreetMap
    re.compile(r"[?&](?:pt|q|query|destination|daddr|m)=" + _JUFT),     # «shu nuqta» parametrlari
    re.compile(r"rtext=[^&\s]*~" + _JUFT),                             # Yandex yo'l: boradigan joy
    re.compile(r"/@" + _JUFT),                                         # Google: xarita markazi
    _KOORD,
]


def koordinata_matndan(matn) -> tuple[float, float] | None:
    """Matn ichidagi koordinatani topadi: '41.3418, 69.2879' yoki xarita havolasi.

    Yandex havolalarida tartib teskari (uzunlik, kenglik) — qaysi biri
    kenglik ekani shahar joylashuviga qarab aniqlanadi.
    """
    matn = unquote(str(matn or ""))
    for qolip in _NUQTA_QOLIPLARI:
        for m in qolip.finditer(matn):
            a, b = float(m.group(1)), float(m.group(2))
            for lat, lon in ((a, b), (b, a)):
                if -90 <= lat <= 90 and _hududdami(lat, lon):
                    return lat, lon
    return None


# ---- qisqa xarita havolalari
#
# Xaritadan «ulashish» orqali olingan havola qisqa bo'ladi
# (yandex.uz/maps/-/XXXX, maps.app.goo.gl/XXXX) va unda koordinata yo'q —
# u haqiqiy manzilga yo'naltiradi. Shu yo'naltirishni server kuzatadi.
# Faqat ma'lum xarita saytlari va faqat https: foydalanuvchi kiritgan
# manzil orqali server ichki tarmoqqa so'rov yuborib qolmasligi kerak.

_HAVOLA = re.compile(r"https?://[^\s<>\"']+")
_XARITA_HOSTLARI = re.compile(
    r"(?:^|\.)(?:yandex\.[a-z.]{2,6}|ya\.ru|google\.[a-z.]{2,6}|goo\.gl|2gis\.[a-z.]{2,6}|"
    r"openstreetmap\.org|osm\.org)$")


def _havola_ol(url: str) -> tuple[int, str, str]:
    """Bitta so'rov, yo'naltirishga ergashmasdan: (holat, yo'naltirilgan manzil, sahifa matni)."""
    sorov = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept-Language": "uz,ru;q=0.8,en;q=0.6"})
    try:
        with _YONALTIRMASDAN.open(sorov, timeout=12) as javob:
            return javob.status, "", javob.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:   # 3xx ham shu yerga tushadi (yo'naltirishga ergashilmaydi)
        return e.code, e.headers.get("Location") or "", ""
    except (urllib.error.URLError, OSError) as e:
        raise YolXato(f"havolani ochib bo'lmadi ({type(e).__name__})") from None


class _Yonaltirmaslik(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_YONALTIRMASDAN = urllib.request.build_opener(_Yonaltirmaslik)


def havolani_och(matn) -> tuple[float, float] | None:
    """Matndagi xarita havolasini ochib, undagi joyni topadi. Tarmoqqa chiqadi."""
    topilgan = _HAVOLA.search(str(matn or ""))
    if not topilgan:
        return None
    url = topilgan.group(0).rstrip(".,;)")
    if url.startswith("http://"):
        url = "https://" + url[7:]          # xarita saytlari baribir https ga o'tkazadi
    for _ in range(6):
        qismlar = urlsplit(url)
        if qismlar.scheme != "https" or not _XARITA_HOSTLARI.search(qismlar.hostname or ""):
            return None
        try:
            holat, keyingi, sahifa = _havola_ol(url)
        except YolXato:
            return None
        if holat in (301, 302, 303, 307, 308) and keyingi:
            url = urljoin(url, keyingi)
            nuqta = koordinata_matndan(url)
            if nuqta:
                return nuqta
            continue
        if holat == 200:
            # Sahifa matnida tasodifiy sonlar ko'p — faqat aniq nuqta qoliplari olinadi.
            ochilgan = unquote(sahifa)
            for qolip in _NUQTA_QOLIPLARI[:-1]:
                for m in qolip.finditer(ochilgan):
                    a, b = float(m.group(1)), float(m.group(2))
                    for lat, lon in ((a, b), (b, a)):
                        if -90 <= lat <= 90 and _hududdami(lat, lon):
                            return lat, lon
        return None
    return None


def joyni_tani(matn) -> tuple[float, float] | None:
    """Kiritilgan matndan joylashuv: koordinata, xarita havolasi yoki qisqa havola."""
    return koordinata_matndan(matn) or havolani_och(matn)


_FAQAT_KOORD = re.compile(r"-?\d{1,3}\.\d+,\s*-?\d{1,3}\.\d+")


def nuqta_manzili(lat: float, lon: float) -> str:
    """Tayyor joylashuvning matn ko'rinishi — manzil o'rnida ishlatiladi.

    Shu tufayli yuborilgan joy ham yozilgan manzil bilan bir xil yo'ldan
    o'tadi: bekatlari aniqlanadi va natijasi bazada saqlanadi.
    """
    return f"{float(lat):.6f}, {float(lon):.6f}"


def _apostrof(s: str) -> str:
    for a in APOSTROFLAR:
        s = s.replace(a, "'")
    return s


def _lotin(s: str) -> bool:
    return bool(re.search(r"[a-z]", str(s or "").lower()))


def _sodda(s) -> str:
    """'Chilonzor 19', 'Chilonzor-19' va 'Chilonzor (19)' bir xil ko'rinishga keladi."""
    return re.sub(r"[\s\-()\"«»]+", "-", oddiy_ism(s)).strip("-")


UMUMIY_SOZLAR = {
    "kochasi", "kocha", "shoh", "tor", "berk", "yoli", "prospekti", "prospekt", "xiyoboni",
    "mavze", "mavzesi", "mahalla", "mahallasi", "tumani", "tuman", "shahri", "shahar",
    "toshkent", "kvartal", "massiv", "uy", "dom",
}


def _sozlar(s) -> set[str]:
    """Nomning ma'no tashuvchi so'zlari (umumiy so'zlarsiz)."""
    return {w for w in re.findall(r"[^\W\d_]{3,}", oddiy_ism(s)) if w not in UMUMIY_SOZLAR}


# ------------------------------------------------------- manzilni bo'laklash

# Uy raqami: «14», «25a», «2-v», «12 B», «7/2». Harf raqamdan chiziqcha yoki
# bo'shliq bilan ajratilgan bo'lishi mumkin («2-v-uy»), lekin u keyingi
# so'zning bosh harfi bo'lmasligi kerak («14 uy» dagi «u» — harf emas).
_UY_RAQAMI = r"\d+(?:\s?-?\s?[a-zа-я](?![^\W\d_]))?(?:/\d+)?"
_XONADON = re.compile(
    r"\b\d+\s*-?\s*(?:xonadon\w*|xon\b\.?|kv\b\.?|кв\b\.?|квартира|хонадон\w*)"
    r"|\b(?:xonadon|kv|кв|квартира|хонадон)\.?\s*\d+\b", re.I)
# Xonadon raqami xaritaga yuborilmaydi; u faqat bir xonadonda yashovchilarni
# birlashtirish uchun (dashboard) shu kompyuterning o'zida ishlatiladi.
_XONADON_RAQAMI = re.compile(
    r"\b(\d+)\s*-?\s*(?:xonadon\w*|xon\b\.?|kv\b\.?|кв\b\.?|квартира|хонадон\w*)"
    r"|\b(?:xonadon|kv|кв|квартира|хонадон)\.?\s*(\d+)\b", re.I)
_UY = re.compile(
    rf"\b({_UY_RAQAMI})\s*-?\s*(?:uy\b|уй\b|дом\b)"
    rf"|\b(?:uy|уй|дом|д\.)\s*({_UY_RAQAMI})\b", re.I)
_TUMAN = re.compile(r"\b(?:tumani?|тумани?|района?|р-н|r-n)(?![\w'])", re.I)
_MAVZE_SOZI = (r"(?:mavze(?:si)?|мавзе(?:си)?|kvartal[i]?|квартал[аи]?|massiv[i]?|"
               r"массив[аи]?|mikrorayon[i]?|микрорайон[аи]?|мкр\.?|da[hx]a(?:si)?|"
               r"kichik\s+nohiya)")
_MAVZE_RAQAMI = r"\d+(?:/\d+)?"                 # «19», «2/1» (Qoraqamish 2/1)
_MAVZE = re.compile(
    rf"^(?P<nom>.*?)[\s-]*(?P<raqam>{_MAVZE_RAQAMI})\s*-?\s*{_MAVZE_SOZI}(?![\w'])", re.I)
# «квартал 14», «массив Чиланзар 14», «массив Феруза» — so'z oldinda turgan yozilish
_MAVZE_OLDIDA = re.compile(
    rf"^{_MAVZE_SOZI}[\s.]+(?P<nom>[^\d,]*?)[\s-]*(?P<raqam>{_MAVZE_RAQAMI})?$", re.I)
# «Feruza dahasi», «Sebzor massivi» — raqamsiz, faqat nomi bor hudud
_MAVZE_NOMLI = re.compile(rf"^(?P<nom>[^\d,]+?)[\s-]+{_MAVZE_SOZI}$", re.I)
_MAHALLA = re.compile(
    r"(?<![^\W\d_])(?:mfy|m\.f\.y|ma[hx]al+a(?:si)?|мфй|махалл[яи]|маҳалла(?:си)?)(?![^\W\d_])\.?",
    re.I)
_QISQA = re.compile(r"^(?P<nom>[^\d,]+?)[\s-]+(?P<raqam>\d+)$")
_QISQA_KASR = re.compile(r"^(?P<nom>[^\d,]+?)[\s-]+(?P<raqam>\d+/\d+)$")
_QISQA_UY = re.compile(
    r"^(?P<nom>[^\d,]+?)\s+(?P<uy>\d+[a-zа-я]?)\s*[-/]\s*(?P<xonadon>\d+)$", re.I)
_KOCHA = re.compile(r"ko'?cha|кўча|куча|улиц|\bул\.|prospekt|проспект|\bshoh\b|\btor\b|"
                    r"\bberk\b|проезд|тупик|\bxiyoboni?\b|\byo'li\b", re.I)
_KOCHA_ANIQ = re.compile(r"ko'?cha|кўча|куча|улиц|\bул\.", re.I)
_OXIRGI_RAQAM = re.compile(rf"[\s,]+({_UY_RAQAMI})$", re.I)
# «3-tor ko'cha», «2-berk» — asosiy ko'chadan ajralgan tor ko'cha; uning uy
# raqamlari alohida, shuning uchun raqami natija bilan solishtiriladi.
_TOR = re.compile(r"(?<!\d)(?P<raqam>\d+)\s*-?\s*(?P<tur>tor|berk|тупик|проезд)(?![^\W\d_])", re.I)
_KOCHA_SOZI = re.compile(r"\s*\bko'?cha(?:si)?\b", re.I)


def _uy_toza(xom: str) -> str:
    """«2-v», «2 v» -> «2v»."""
    return re.sub(r"[\s-]+", "", xom)


def _shaharmi(qism: str) -> bool:
    n = oddiy_ism(qism)
    shahar = oddiy_ism(sozlama.geo_shahar)
    return n in (shahar, f"{shahar} shahri", f"{shahar} sh", "ташкент", "г ташкент", "tashkent")


def tahlil(manzil: str) -> dict:
    """Manzil matnini qismlarga ajratadi.

        'Yunusobod tumani, Bodomzor ko'chasi, 14-uy, 23-xonadon'
            -> tuman 'Yunusobod', kocha 'Bodomzor ko'chasi', uy '14'
        'Chilonzor tumani, 19-mavze, 42-uy'
            -> mavze 'Chilonzor', mavze_raqami '19', uy '42'
        'Uchtepa tumani, 14-kvartal, 2-v-uy'
            -> mavze 'Uchtepa' (nomsiz: tuman nomi olindi), mavze_raqami '14', uy '2v'
        'Olmazor tumani, Qoraqamish dahasi, 5, 12'
            -> mavze 'Qoraqamish', uy '5'

    Xonadon raqami tashlab yuboriladi: xaritaga uning keragi yo'q va uni
    hech qayerga yuborish ham shart emas.
    """
    asl = _apostrof(str(manzil or ""))
    xonadon = _XONADON_RAQAMI.search(asl)
    matn = _XONADON.sub(" ", asl)
    t = {"tuman": "", "kocha": "", "kocha_asosiy": "", "uy": "", "mavze": "", "mavze_raqami": "",
         "mahalla": "", "xonadon": (xonadon.group(1) or xonadon.group(2)) if xonadon else "",
         "qisqa": False, "taxmin": False, "nomsiz": False, "qolgan": []}

    for qism in re.split(r"[,;\n]", matn):
        qism = qism.strip(" .-")
        if not qism or _shaharmi(qism):
            continue

        m = _UY.search(qism)
        if m:
            t["uy"] = t["uy"] or _uy_toza(m.group(1) or m.group(2))
            qism = (qism[:m.start()] + " " + qism[m.end():]).strip(" .-")
            if not qism:
                continue

        if _TUMAN.search(qism):
            t["tuman"] = _TUMAN.sub("", qism).strip(" .-")
            continue

        m = _MAHALLA.search(qism)
        if m and not _KOCHA_ANIQ.search(qism):
            t["mahalla"] = " ".join((qism[:m.start()] + " " + qism[m.end():]).split()).strip(" .-")
            continue

        m = _MAVZE.match(qism) or _MAVZE_OLDIDA.match(qism)
        if m and (m["raqam"] or m["nom"].strip(" .-")):
            if m["raqam"] or not t["mavze"]:
                t["mavze"], t["mavze_raqami"] = m["nom"].strip(" .-"), m["raqam"] or ""
            continue

        m = _MAVZE_NOMLI.match(qism)
        if m and not t["mavze"]:
            t["mavze"] = m["nom"].strip(" .-")      # «Feruza dahasi»
            continue

        if _KOCHA.search(qism):
            m = _TOR.match(qism)
            if m and t["kocha"]:                    # «Bodomzor ko'chasi, 3-tor ko'cha»
                asosiy = _KOCHA_SOZI.sub("", t["kocha"]).strip(" .-")
                t["kocha_asosiy"] = t["kocha"]
                t["kocha"] = f"{asosiy} {m['raqam']}-{m['tur'].lower()} ko'chasi"
                continue
            m = _OXIRGI_RAQAM.search(qism)          # «Bodomzor ko'chasi 14»
            if m:
                t["uy"] = t["uy"] or _uy_toza(m.group(1))
                qism = qism[:m.start()].strip(" .-")
            t["kocha"] = qism
            continue

        if (t["kocha"] or t["mavze"] or t["mavze_raqami"]) and not t["uy"] \
                and re.fullmatch(_UY_RAQAMI, qism, re.I):
            t["uy"] = _uy_toza(qism)                # «ул. Бодомзор, 14»: raqamning o'zi
            continue

        if t["uy"] and not t["xonadon"] and re.fullmatch(r"\d+", qism):
            t["xonadon"] = qism                     # «Qoraqamish dahasi, 5, 12»: uy va xonadon
            continue

        m = _QISQA_KASR.match(qism)                 # «Qoraqamish 2/1» — shunday mavze bor
        if m and not t["mavze_raqami"] and _hudud_top(m["nom"], m["raqam"]):
            t["mavze"], t["mavze_raqami"] = m["nom"].strip(" .-"), m["raqam"]
            continue

        m = _QISQA_UY.match(qism)                   # «Bodomzor 14-23»: uy va xonadon
        if m and not t["kocha"]:
            t["kocha"], t["uy"] = m["nom"].strip(), t["uy"] or m["uy"]
            t["xonadon"] = t["xonadon"] or m["xonadon"]
            t["taxmin"] = True                      # «ko'cha» deb yozilmagan — bu bizning taxmin
            continue

        m = _QISQA.match(qism)                      # «Aviasozlar 2», «Qorasuv-3»
        if m and not t["mavze_raqami"]:
            t["mavze"], t["mavze_raqami"] = m["nom"].strip(" .-"), m["raqam"]
            t["qisqa"] = True                       # «Navoiy 12» — ko'cha va uy ham bo'lishi mumkin
            continue

        t["qolgan"].append(qism)

    if t["mavze_raqami"] and not t["mavze"]:
        # «Chilonzor tumani, 19-mavze»: mavzening nomi yozilmagan. Ko'pincha u
        # tuman nomi bilan ataladi, lekin har doim emas: Uchtepa tumanidagi
        # 14-kvartal — «Chilonzor-14». Haqiqiy nomi ro'yxatdan topiladi (`_royxatdan`).
        t["mavze"], t["nomsiz"] = t["tuman"], True
    return t


def xonadonsiz(manzil: str) -> str:
    """Manzilning xaritaga yuborsa bo'ladigan ko'rinishi (xonadon raqamisiz)."""
    toza = _XONADON.sub(" ", _apostrof(str(manzil or "")))
    toza = re.sub(r"\s*,(\s*,)+", ",", toza)
    return re.sub(r"\s{2,}", " ", toza).strip(" ,.-")


def manzilga_oxshaydimi(matn) -> bool:
    """Buyruqsiz yozilgan matn manzilmi (yoki ichida koordinata bormi).

    Bot har qanday matnni xaritaga yubormasligi kerak: «rahmat» yoki
    «ertaga boraman» — manzil emas. Manzil deb faqat ko'cha, mavze yoki
    uy raqami ajratib olingan matn hisoblanadi.
    """
    matn = str(matn or "").strip()
    if not 4 <= len(matn) <= 300:
        return False
    return koordinata_matndan(matn) is not None or bool(_nomzodlar(tahlil(matn)))


# ------------------------------------------- shahar hududlari ro'yxati
#
# Manzillar ko'pincha «Uchtepa tumani, 14-kvartal, 2-uy» ko'rinishida yoziladi:
# kvartalning nomi yo'q, faqat tuman va raqam. Xaritada esa u «Chilonzor-14»
# deb nomlangan — tuman nomi bilan qidirilsa, topilmaydi. Shuning uchun dastur
# bilan birga shahar mavze, daha va mahallalarining ro'yxati keladi
# (`tashrif/malumot/hududlar.json`): nomi, markazi va qaysi tumanda joylashgani.
# Ro'yxat OpenStreetMap ma'lumotidan tuzilgan; undan tarmoqsiz foydalaniladi.

_HUDUD_TURI = re.compile(
    r"(?<![^\W\d_])(?:mavze(?:si)?|da[hx]a(?:si)?|kvartal[i]?|massiv[i]?|mikrorayon[i]?|"
    r"kichik\s+nohiya|ma[hx]al+a(?:si)?|mfy|мавзе(?:си)?|квартал[аи]?|массив[аи]?|"
    r"микрорайон[аи]?|мкр|махалл[яи]|маҳалла(?:си)?|мфй)(?![^\W\d_])", re.I)
_TUMAN_SOZI = re.compile(
    r"(?<![^\W\d_])(?:tumani?|rayon[i]?|тумани?|района?|р-н)(?![^\W\d_])", re.I)
_BIR_XIL_HARFLAR = str.maketrans({"x": "h", "ё": "е", "ҳ": "х", "қ": "к", "ғ": "г", "ў": "у"})
_KALIT_RAQAMI = re.compile(r"(?P<asos>.*?)(?P<raqam>\d+(?:/\d+)?[a-zа-я]?)")

_hududlar: dict | None = None
_hududlar_ochildi = False
_hududlar_qulfi = threading.Lock()


def _hudud_fayli() -> Path:
    return Path(__file__).resolve().parent / "malumot" / "hududlar.json"


def _hudud_kaliti(nom) -> str:
    """«Chilonzor 14 mavzesi», «Chilonzor-14», «chilonzor 14-kvartal» — bitta kalit."""
    toza = _HUDUD_TURI.sub(" ", oddiy_ism(nom)).translate(_BIR_XIL_HARFLAR)
    return re.sub(r"[^\w/]|_", "", toza)


def _hududlarni_och() -> dict | None:
    """Ro'yxatni xotiraga oladi: {'kalit': nom -> hududlar, 'raqam': raqam -> (asos, hudud)}."""
    global _hududlar, _hududlar_ochildi
    if _hududlar_ochildi:
        return _hududlar
    with _hududlar_qulfi:
        if _hududlar_ochildi:
            return _hududlar
        try:
            xom = json.loads(_hudud_fayli().read_text(encoding="utf-8"))
            yaroqli = _ichidami(xom.get("hudud"), *sozlama.geo_markaz)   # shu shaharnikimi
            qatorlar = xom["hududlar"] if yaroqli else []
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            xom, qatorlar = {}, []
        kalit: dict[str, list[dict]] = {}
        raqam: dict[str, list[tuple[str, dict]]] = {}
        for q in qatorlar:
            try:
                nom, asos, soni, boshqa, lat, lon, tuman, tur = q
                h = {"nom": str(nom), "asos": str(asos), "raqam": str(soni), "lat": float(lat),
                     "lon": float(lon), "tuman": str(tuman or ""), "tur": str(tur)}
            except (TypeError, ValueError):
                continue
            for k in {_hudud_kaliti(n) for n in [nom, f"{asos} {soni}", *boshqa]} - {""}:
                kalit.setdefault(k, []).append(h)
                m = _KALIT_RAQAMI.fullmatch(k)
                if m and tur == "m":
                    raqam.setdefault(m["raqam"], []).append((m["asos"], h))
        _hududlar = {"kalit": kalit, "raqam": raqam, "tumanlar": xom.get("tumanlar") or {},
                     "qoshni": xom.get("qoshni") or {}} if kalit else None
        _hududlar_ochildi = True
    return _hududlar


def hududlarni_unut() -> None:
    """Xotiradagi ro'yxatni tashlaydi — keyingi murojaatda diskdan qayta o'qiladi."""
    global _hududlar, _hududlar_ochildi
    with _hududlar_qulfi:
        _hududlar, _hududlar_ochildi = None, False
    manzil_kaliti.cache_clear()


def _tuman_lotincha(tuman: str) -> str:
    """Tuman nomi lotinchada: «Учтепинский район» -> «Uchtepa». Tanilmasa — bo'sh."""
    nom = _TUMAN_SOZI.sub(" ", str(tuman or "")).strip(" .-")
    if not nom or _lotin(nom):
        return nom
    royxat = _hududlarni_och()
    sodda = oddiy_ism(nom).translate(_BIR_XIL_HARFLAR)
    for lotincha, ozaklar in ((royxat or {}).get("tumanlar") or {}).items():
        if any(o in sodda for o in ozaklar):
            return lotincha
    return ""


def _tuman_kaliti(tuman: str) -> str:
    return re.sub(r"[^a-z]", "", oddiy_ism(_tuman_lotincha(tuman)).replace("x", "h"))


def _oxshash(a: str, b: str, chegara: float = 0.85) -> bool:
    return bool(a and b) and (a == b or SequenceMatcher(None, a, b).ratio() >= chegara)


def _tuman_bir(a: str, b: str) -> bool:
    """Ikki yozuv bitta tumanmi («Shayxontohur» / «Shayhontohur», «M.Ulug'bek» / «Mirzo Ulug'bek»)."""
    ka, kb = _tuman_kaliti(a), _tuman_kaliti(b)
    if not ka or not kb:
        return False
    qisqa, uzun = sorted((ka, kb), key=len)
    return _oxshash(ka, kb, 0.75) or (len(qisqa) >= 6 and qisqa in uzun)


def _tuman_qoshni(a: str, b: str) -> bool:
    """Ikki tuman chegaradoshmi (ro'yxatdagi ma'lumot bo'yicha)."""
    royxat = _hududlarni_och()
    for nom, qoshnilar in ((royxat or {}).get("qoshni") or {}).items():
        if _tuman_bir(a, nom):
            return any(_tuman_bir(b, q) for q in qoshnilar)
    return False


def _bir_hudud(nomzodlar: list[dict]) -> dict | None:
    """Nomzodlar bitta joyni bildirsa — o'sha; har xil joy bo'lsa — None (taxmin qilinmaydi)."""
    if not nomzodlar:
        return None
    birinchi = nomzodlar[0]
    joyi = (birinchi["lat"], birinchi["lon"])
    if all(masofa(joyi, (h["lat"], h["lon"])) <= BIR_JOY for h in nomzodlar):
        return birinchi
    return None


def _hudud_top(nom: str, raqam: str = "", tuman: str = "", mahalla: bool = False) -> dict | None:
    """Nomi (va raqami) bo'yicha ro'yxatdagi hudud. Topilmasa yoki ikkilansa — None."""
    royxat = _hududlarni_och()
    asos, raqam = _hudud_kaliti(nom), _hudud_kaliti(raqam)
    if not royxat or not asos or len(asos + raqam) < 3:
        return None
    topilgan = list(royxat["kalit"].get(asos + raqam) or [])
    if not topilgan and raqam and _lotin(asos):
        # «Chilanzor 14», «Yunusabad 4» — yozilishdagi farq
        topilgan = [h for a, h in royxat["raqam"].get(raqam, []) if _oxshash(a, asos)]
    if not topilgan:
        return None
    turi = [h for h in topilgan if (h["tur"] == "h") == mahalla]
    topilgan = turi or topilgan
    if tuman:
        shu_tumanda = ([h for h in topilgan if _tuman_bir(tuman, h["tuman"])]
                       or [h for h in topilgan if _tuman_qoshni(tuman, h["tuman"])])
        # Raqamli mavze nomi shaharda bitta bo'ladi («Chilonzor-14») — tuman xato
        # yozilgan bo'lsa ham o'sha. Raqamsiz nom («Guliston», «Do'stlik») esa
        # bir necha tumanda uchraydi: o'sha yoki qo'shni tumanda bo'lmasa, olinmaydi.
        if shu_tumanda or not raqam:
            topilgan = shu_tumanda
    return _bir_hudud(topilgan)


def _nomsiz_hudud(raqam: str, tuman: str) -> dict | None:
    """«Uchtepa tumani, 14-kvartal» — shu tumandagi 14-raqamli mavze qaysi."""
    royxat = _hududlarni_och()
    raqam = _hudud_kaliti(raqam)
    if not royxat or not raqam or not tuman:
        return None
    nomzodlar = royxat["raqam"].get(raqam, [])
    tuman_kaliti = _tuman_kaliti(tuman)
    # Tuman nomi bilan atalgan mavze («Chilonzor tumani, 19-mavze» — «Chilonzor-19»)
    oz_nomi = [h for asos, h in nomzodlar if _oxshash(asos, tuman_kaliti)]
    if oz_nomi:
        return _bir_hudud(oz_nomi)
    return _bir_hudud([h for _, h in nomzodlar if _tuman_bir(tuman, h["tuman"])])


def _royxatdan(t: dict) -> dict | None:
    """Manzildagi mavze yoki daha — ro'yxatdagi yozuv (tarmoqsiz)."""
    if not t["mavze"] and not t["mavze_raqami"]:
        return None
    if not t["nomsiz"]:
        topilgan = _hudud_top(t["mavze"], t["mavze_raqami"], t["tuman"])
        if not topilgan and t["tuman"]:
            # «Chilonzor tumani, Ts-kvartal» — harf bilan atalgan mavze: «Chilonzor-Ts»
            tuman = _tuman_lotincha(t["tuman"])
            topilgan = _hudud_top(f"{tuman} {t['mavze']}", t["mavze_raqami"], t["tuman"])
        return topilgan
    for bolak in t["qolgan"]:                        # «Uchtepa tumani, Chilonzor, 14-kvartal»
        topilgan = _hudud_top(bolak, t["mavze_raqami"], t["tuman"])
        if topilgan:
            return topilgan
    return _nomsiz_hudud(t["mavze_raqami"], t["tuman"])


_KOCHA_TURI = re.compile(
    r"(?<![^\W\d_])(?:kochasi|kocha|shoh|prospekti?|xiyoboni?|улица|ул|проспект|кучаси|куча)"
    r"(?![^\W\d_])", re.I)


@lru_cache(maxsize=8192)
def manzil_kaliti(manzil: str) -> tuple[str, str]:
    """Manzil -> (bino kaliti, xonadon raqami). Tarmoqqa chiqmaydi.

    Bir xonadonda yashovchi talabalar manzilni har xil yozadi:

        'Toshkent shahri, Uchtepa tumani, 14-kvartal, 2-uy, 63-xonadon'
        'Uchtepa t., Chilonzor-14 mavzesi, 2 uy, 63 xon.'

    Ikkalasi ham ('chilonzor14||2', '63') ni beradi — shu juftlik bo'yicha
    ular bitta xonadonga birlashtiriladi. Tuman kalitga kirmaydi (uni hamma
    ham yozmaydi), mavze nomi esa ro'yxatdagi yagona ko'rinishga keltiriladi.
    Manzil tushunilmasa, matnning o'zi kalit bo'ladi.
    """
    matn = str(manzil or "").strip()
    if not matn or koordinata_matndan(matn):
        return "", ""
    t = tahlil(matn)
    hudud = _royxatdan(t)
    if hudud:
        mavze = f"{hudud['asos']} {hudud['raqam']}"
    elif t["mavze"] or t["mavze_raqami"]:
        mavze = f"{t['mavze']} {t['mavze_raqami']}"
    else:
        mavze = ""
    kocha = re.sub(r"[^\w]|_", "", _KOCHA_TURI.sub(" ", oddiy_ism(t["kocha"])))
    uy = re.sub(r"[\s-]+", "", t["uy"].lower()).translate(_HARF_LOTINCHA)
    if uy and (mavze or kocha):
        return f"{_hudud_kaliti(mavze)}|{kocha}|{uy}", t["xonadon"]
    # Uy raqami ajratilmadi — xonadonsiz matnning o'zi (bir xil yozilganlar birlashadi).
    return "m:" + re.sub(r"[^\w]|_", "", oddiy_ism(xonadonsiz(matn))), t["xonadon"]


# ---------------------------------------------------- joyni topish: OSM

def _nomzodlar(t: dict) -> list[tuple[str, str, dict]]:
    """Xaritadan so'raladigan variantlar — eng aniqidan boshlab.

    Har biri: (so'rov matni, turi, shu so'rov tekshiriladigan qismlar).
    """
    shahar = sozlama.geo_shahar
    n: list[tuple[str, str, dict]] = []
    # «2v» uy xaritada bo'lmasa, yonidagi «2» so'raladi: harfli uylar odatda
    # shu raqamli uyning yonida turadi. Bunday natija «taxminiy» deb beriladi.
    uylar = [t["uy"]] if t["uy"] else []
    raqami = re.match(r"\d+", t["uy"])
    if raqami and raqami.group() != t["uy"]:
        uylar.append(raqami.group())

    if t["kocha"]:
        for uy in uylar:
            n.append((f"{t['kocha']} {uy}, {shahar}", "uy_taxmin" if t["taxmin"] else "uy", t))
    if t["mavze"] and t["mavze_raqami"]:
        mavze = f"{t['mavze']}-{t['mavze_raqami']}"
        for uy in uylar:
            n.append((f"{uy}, {mavze}, {shahar}", "mavze_uy", t))
        n.append((f"{mavze}, {shahar}", "mavze", t))
        if t["qisqa"] and not t["kocha"] and not t["uy"]:
            # «Navoiy 12» mavze bo'lib chiqmadi — ko'cha va uy sifatida sinaladi.
            kocha_deb = {**t, "kocha": f"{t['mavze']} ko'chasi", "uy": t["mavze_raqami"]}
            n.append((f"{kocha_deb['kocha']} {kocha_deb['uy']}, {shahar}", "uy_taxmin", kocha_deb))
    elif t["mavze"]:
        for uy in uylar:                             # «Feruza dahasi, 12-uy»
            n.append((f"{uy}, {t['mavze']}, {shahar}", "hudud_uy", t))
        n.append((f"{t['mavze']}, {shahar}", "hudud", t))
    if t["kocha"]:
        n.append((f"{t['kocha']}, {shahar}", "kocha", t))
    if t["kocha_asosiy"]:
        # Tor ko'cha xaritada yo'q — asosiy ko'chaning o'zi (uy raqamisiz: u boshqa uy).
        n.append((f"{t['kocha_asosiy']}, {shahar}", "kocha", {**t, "kocha": t["kocha_asosiy"]}))
    return n


def _nominatim(sorov: str) -> list[dict]:
    """Xaritadagi mos joylar — eng o'xshashidan boshlab.

    Bitta emas, bir nechta natija olinadi: bir xil nomli ko'cha turli
    tumanlarda uchraydi va birinchi qaytgani ko'pincha boshqa tumandagisi.
    """
    lat, lon = sozlama.geo_markaz
    d = _sorov(NOMINATIM, {
        "q": sorov, "format": "jsonv2", "limit": NATIJALAR_SONI, "addressdetails": 1,
        "countrycodes": DAVLAT, "accept-language": "uz",
        "viewbox": f"{lon - 0.45},{lat + 0.30},{lon + 0.45},{lat - 0.30}",
    })
    return [r for r in d if isinstance(r, dict)] if isinstance(d, list) else []


# Uy harfi lotincha ham, kirillcha ham yoziladi: «2v» va «2В» — bitta uy.
_HARF_LOTINCHA = str.maketrans("абвгдежзиклмнопрстуфх", "abvgdejziklmnoprstufx")


def _uy_mos(sorilgan: str, topilgan: str) -> int:
    """2 — aynan shu uy; 1 — shu raqamli qo'shni bino ('3' va '3Б'); 0 — boshqa."""
    a = re.sub(r"[\s-]+", "", str(sorilgan or "").lower()).translate(_HARF_LOTINCHA)
    b = re.sub(r"[\s-]+", "", str(topilgan or "").lower()).translate(_HARF_LOTINCHA)
    if not a or not b:
        return 0
    if a == b:
        return 2
    ra, rb = re.match(r"\d+", a), re.match(r"\d+", b)
    return 1 if ra and rb and ra.group() == rb.group() else 0


_HUDUD_MAYDONLARI = ("residential", "quarter", "neighbourhood", "suburb", "city_block", "hamlet")


def _osm_baho(r: dict, tur: str, t: dict, hudud: dict | None = None,
              uzunlik: bool = True) -> str | None:
    """Xarita qaytargan natija so'ralgan manzilga mos keladimi.

    Xarita har doim «eng o'xshash»ini qaytaradi va u ko'pincha noto'g'ri:
    «Chilonzor 19-mavze» o'rniga «Chilonzor-5 dagi 19-uy», ko'cha o'rniga
    shu nomdagi oshxona. Koordinatorni boshqa joyga yuborgandan ko'ra
    «topilmadi» degan yaxshi — shuning uchun har bir natija tekshiriladi.

    `hudud` — manzildagi mavze ro'yxatdan topilgan bo'lsa, o'sha yozuv:
    natija uning yonida bo'lishi kerak. `uzunlik=False` — ko'chaning uzunligi
    tekshirilmaydi (bo'laklari `_osm` da birga o'lchanadi).
    """
    manzil = r.get("address") or {}
    qiymatlar = [str(v) for v in manzil.values()] + [str(r.get("name") or "")]
    toifa = r.get("category") or r.get("class") or ""
    uy = _uy_mos(t["uy"], manzil.get("house_number"))
    try:
        oraliq = masofa((float(r["lat"]), float(r["lon"])),
                        (hudud["lat"], hudud["lon"])) if hudud else 0.0
    except (KeyError, TypeError, ValueError):
        return None
    mavze_turi = tur in ("mavze_uy", "mavze", "hudud_uy", "hudud")

    def nom_mos(nom: str) -> bool:
        if not _lotin(nom):
            return True          # kirillcha yozilgan — lotincha natija bilan solishtirilmaydi
        sozlar = _sozlar(nom)
        return not sozlar or bool(sozlar & _sozlar(" ".join(qiymatlar)))

    def mavze_mos() -> bool:
        raqam = re.escape(t["mavze_raqami"])
        nom = re.escape(_sodda(t["mavze"])) if _lotin(t["mavze"]) else r"[^\W\d_]+"
        qolip = re.compile(rf"(?<![^\W_]){nom}-{raqam}(?![\d/])")
        if any(qolip.search(_sodda(v)) for v in qiymatlar):
            return True
        # Xaritada nom boshqacha yozilgan bo'lishi mumkin («Yo'ldosh (Sputnik) 14»).
        # Ro'yxatdagi mavzening yonida turgan va raqami to'g'ri kelgan natija — o'sha.
        return bool(hudud) and oraliq <= HUDUD_RADIUSI and any(
            re.search(rf"(?<![\d/]){raqam}(?![\d/])", str(manzil.get(k) or ""))
            for k in _HUDUD_MAYDONLARI)

    def hudud_nomi_mos(nomlar: list[str]) -> bool:
        """Raqamsiz daha: nomi natijadagi nomlardan birida to'liq bo'lishi kerak.

        So'zma-so'z emas, yaxlit solishtiriladi: «Chilonzor S» so'ralganda
        «Chilonzor 5» mos kelmasligi kerak.
        """
        kalit = _hudud_kaliti(t["mavze"])
        if not _lotin(t["mavze"]) or len(kalit) < 3:
            return False
        return any(kalit in _hudud_kaliti(n) for n in nomlar if n)

    def tor_mos() -> bool:
        """«3-tor» so'ralgan bo'lsa — aynan 3-tor; so'ralmagan bo'lsa — tor ko'cha emas."""
        yol_nomi = _apostrof(f"{manzil.get('road') or ''} {r.get('name') or ''}")
        sorilgan, topilgan = _TOR.search(t["kocha"]), _TOR.search(yol_nomi)
        return (sorilgan["raqam"] if sorilgan else "") == (topilgan["raqam"] if topilgan else "")

    def tuman_mos() -> int:
        """Topilgan joy manzilda yozilgan tumandami: 2 — ha, 1 — qo'shni tumanda, 0 — yo'q.

        Bir xil nomli ko'cha va bir xil raqamli uy turli tumanlarda uchraydi —
        noto'g'ri natijalarning asosiy manbai shu. Yozilishdagi mayda farq
        (Shayxontohur / Shayhontohur) xato hisoblanmaydi. Qo'shni tuman alohida
        ajratiladi: chegaradagi joyni odamlar ko'pincha eski yoki qo'shni tuman
        nomi bilan yozadi (Chilonzor mavzelarining bir qismi — Uchtepa tumanida).
        """
        tuman = _tuman_lotincha(t["tuman"])
        if not tuman:
            return 2                 # tuman yozilmagan yoki tanilmadi — tekshirib bo'lmaydi
        tumanlar = [v for v in qiymatlar if "tuman" in oddiy_ism(v)]
        topilgan = [w for v in tumanlar for w in _sozlar(v)]
        if not topilgan:
            return 2                 # natijada tuman ko'rsatilmagan — tekshirib bo'lmaydi
        if all(any(SequenceMatcher(None, soz, w).ratio() >= 0.8 for w in topilgan)
               for soz in _sozlar(tuman)):
            return 2
        return 1 if any(_tuman_qoshni(tuman, v) for v in tumanlar) else 0

    shu_tumanda = True
    if hudud and mavze_turi:
        # Mavzening o'rni ro'yxatdan ma'lum: tuman yozuvi emas, masofa tekshiriladi
        # («Chilonzor tumani, 14-kvartal» aslida Uchtepa tumanida joylashgan).
        if oraliq > HUDUD_CHEGARASI:
            return None
    else:
        tuman_bahosi = tuman_mos()
        # Ko'cha nomi takrorlanadi — qo'shni tumandagisi faqat uy raqami ham mos
        # kelsa olinadi. Mavze va daha nomi esa kam takrorlanadi.
        if not tuman_bahosi or (tuman_bahosi == 1 and tur == "kocha"):
            return None
        shu_tumanda = tuman_bahosi == 2

    if tur in ("uy", "uy_taxmin"):
        if not nom_mos(t["kocha"]) or not tor_mos() or not uy:
            return None
        # Ko'cha ekanini o'zimiz taxmin qilgan bo'lsak, natija «aniq» deb aytilmaydi.
        return "aniq" if uy == 2 and tur == "uy" and shu_tumanda else "taxminiy"

    if tur == "mavze_uy":
        # Uy topilmasa, shu so'rov mavzening o'zini qaytarishi mumkin — u `_osm` da
        # «mavze» sifatida alohida baholanadi.
        if not uy or not mavze_mos():
            return None
        return "aniq" if uy == 2 else "taxminiy"

    if tur == "mavze":
        return "taxminiy" if mavze_mos() and toifa in ("landuse", "place", "boundary") else None

    if tur == "hudud_uy":
        if not uy or not _lotin(t["mavze"]):
            return None
        # Katta massiv ichida bir necha daha bo'ladi va uy raqamlari takrorlanadi:
        # «Feruza dahasi, 12-uy» o'rniga qo'shni dahadagi 12-uy qaytishi mumkin.
        yaqin = [str(manzil[k]) for k in _HUDUD_MAYDONLARI if k != "suburb" and manzil.get(k)]
        if yaqin:
            if not hudud_nomi_mos(yaqin):
                return None
            raqamsiz = not re.search(r"\d", " ".join(yaqin))
            return "aniq" if uy == 2 and raqamsiz and shu_tumanda else "taxminiy"
        return "taxminiy" if hudud_nomi_mos([str(manzil.get("suburb") or "")]) else None

    if tur == "hudud":
        mos = (toifa in ("landuse", "place", "boundary") and hudud_nomi_mos(
            [str(r.get("name") or "")] + [str(manzil.get(k) or "") for k in _HUDUD_MAYDONLARI]))
        return "taxminiy" if mos else None

    if tur == "kocha":
        if toifa != "highway" or not nom_mos(t["kocha"]) or not tor_mos():
            return None
        return "taxminiy" if not uzunlik or _qamrov([r]) <= KOCHA_UZUNLIGI else None

    return None


def _qamrov(natijalar: list[dict]) -> float:
    """Natijalar egallagan joyning diagonali, metrda. O'lchab bo'lmasa — cheksiz."""
    try:
        chegaralar = [[float(x) for x in r["boundingbox"]] for r in natijalar]
    except (KeyError, TypeError, ValueError):
        return math.inf
    if not chegaralar or any(len(c) != 4 for c in chegaralar):
        return math.inf
    return masofa((min(c[0] for c in chegaralar), min(c[2] for c in chegaralar)),
                  (max(c[1] for c in chegaralar), max(c[3] for c in chegaralar)))


def _royxat_joyi(h: dict, izoh: str = "") -> dict:
    """Ro'yxatdagi hududning markazi — taxminiy joy sifatida."""
    nom = h["nom"] + (f", {h['tuman']} tumani" if h["tuman"] else "") + izoh
    return {"lat": h["lat"], "lon": h["lon"], "manba": "osm", "aniqlik": "taxminiy",
            "nom": nom[:200]}


def _osm(manzil: str) -> dict | None:
    t = tahlil(manzil)
    hudud = _royxatdan(t)
    if hudud:
        # Ro'yxat mavzening xaritadagi nomini biladi: «Uchtepa tumani, 14-kvartal» —
        # «Chilonzor-14». Uy shu nom bilan so'raladi.
        t = {**t, "mavze": hudud["asos"], "mavze_raqami": hudud["raqam"], "qisqa": False}

    def joy(r: dict, aniqlik: str) -> dict:
        return {"lat": float(r["lat"]), "lon": float(r["lon"]), "manba": "osm",
                "aniqlik": aniqlik, "nom": str(r.get("display_name") or "")[:200]}

    markaz = None                # uy topilmasa beriladigan joy: mavzening o'zi
    sorildi = False
    for sorov, tur, qismlar in _nomzodlar(t):
        if tur in ("mavze", "hudud"):
            if markaz:
                return markaz    # mavzening o'zi oldingi so'rovda qaytgan edi
            if hudud:
                continue         # markazi ro'yxatda bor — so'rash shart emas
        if sorildi:
            _uxla(1.1)           # Nominatim qoidasi: soniyasiga bittadan ko'p so'rov emas
        sorildi = True
        natijalar = _nominatim(sorov)
        if tur == "kocha":
            # Xaritada ko'cha bo'laklarga bo'lingan. Uzun ko'chaning qisqa bo'lagi
            # ham «ko'chaning o'rtasi» emas — hamma bo'laklari birga o'lchanadi.
            bolaklar = [r for r in natijalar if _osm_baho(r, tur, qismlar, hudud, uzunlik=False)]
            if _qamrov(bolaklar) > KOCHA_UZUNLIGI:
                continue
        mos = None
        for r in natijalar:
            aniqlik = _osm_baho(r, tur, qismlar, hudud)
            if aniqlik and (mos is None or aniqlik == "aniq"):
                mos = joy(r, aniqlik)
                if aniqlik == "aniq":
                    break
        if mos:
            return mos
        if tur in ("mavze_uy", "hudud_uy") and not markaz and not hudud:
            # Uy yo'q, lekin xarita mavzening o'zini qaytargan bo'lishi mumkin.
            markaz = next((joy(r, "taxminiy") for r in natijalar
                           if _osm_baho(r, tur[:-3], qismlar)), None)
    if markaz:
        return markaz
    if hudud:
        return _royxat_joyi(hudud)
    mahalla = _hudud_top(t["mahalla"], "", t["tuman"], mahalla=True) if t["mahalla"] else None
    if mahalla:
        # Ko'cha ham, uy ham topilmadi — hech bo'lmasa mahallaning o'rtasi.
        return _royxat_joyi(mahalla, " (mahalla markazi)")
    return None


def _muddatli(fn: Callable, soniya: float, *args):
    """fn(*args) natijasi — agar `soniya` ichida ulgursa; ulgurmasa None.

    Tarmoq kutubxonasining o'z vaqt chegarasi DNS qidiruvini qamramaydi —
    sekin tarmoqda bitta so'rov o'n soniyalab osilib turishi mumkin.
    """
    natija: list = []
    oqim = threading.Thread(target=lambda: natija.append(fn(*args)), daemon=True)
    oqim.start()
    oqim.join(soniya)
    return natija[0] if natija else None


def joy_nomi(lat: float, lon: float) -> str:
    """Nuqtaning xaritadagi nomi: «14, Bodomzor ko'chasi, Xiyobontepa mahalla».

    Yuborilgan joylashuv to'g'ri joyga tushganini ko'rish uchun. Topilmasa
    yoki xizmat javob bermasa — bo'sh qator: bu yo'l ma'lumotiga to'sqinlik qilmaydi.
    """
    try:
        d = _sorov(TESKARI, {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2",
                             "zoom": 18, "addressdetails": 1, "accept-language": "uz"})
    except YolXato:
        return ""
    manzil = d.get("address") if isinstance(d, dict) else None
    if not isinstance(manzil, dict):
        return ""
    # Faqat aniq narsa foydali: ko'cha va uy yoki mavze va uy. «Falon tuman,
    # falon mahalla» degan umumiy javob joyni tanitmaydi — u ko'rsatilmaydi.
    uy = str(manzil.get("house_number") or "").strip()
    kocha = str(manzil.get("road") or "").strip()
    mavze = str(manzil.get("residential") or manzil.get("quarter") or "").strip()
    if kocha:
        return (f"{kocha} {uy}".strip() + (f", {mavze}" if mavze else ""))[:120]
    if mavze and uy:
        return f"{uy}, {mavze}"[:120]
    return ""


def joy_tavsifi(lat: float, lon: float) -> str:
    """Nuqtani eng yaqin bekat orqali tanitadi: «Amir Temur skveri bekati yaqinida»."""
    nusxa = _shaharni_och()
    if not nusxa:
        return ""
    eng = None
    for b in nusxa["bekatlar"]:
        if not b["nom"] or abs(b["lat"] - lat) > 0.006 or abs(b["lon"] - lon) > 0.008:
            continue
        m = masofa((lat, lon), (b["lat"], b["lon"]))
        if m <= 500 and (eng is None or m < eng[0]):
            eng = (m, b["nom"])
    return f"«{eng[1]}» bekati yaqinida" if eng else ""


# ------------------------------------------------- joyni topish: Yandex

# Yandex shaharning o'zini yoki butun viloyatni qaytarsa — bu «topilmadi».
_YANDEX_DAGAL = {"country", "province", "area", "locality", "hydro", "vegetation",
                 "airport", "railway_station", "route", "other"}


def _yandex(manzil: str) -> dict | None:
    lat, lon = sozlama.geo_markaz
    toza = xonadonsiz(manzil)
    if oddiy_ism(sozlama.geo_shahar) not in oddiy_ism(toza):
        toza = f"{sozlama.geo_shahar}, {toza}"
    d = _sorov(YANDEX, {
        "apikey": sozlama.yandex_kalit, "geocode": toza, "format": "json",
        "results": 1, "lang": "ru_RU", "ll": f"{lon},{lat}", "spn": "0.9,0.6",
    })
    try:
        azolar = d["response"]["GeoObjectCollection"]["featureMember"]
        if not azolar:
            return None
        obyekt = azolar[0]["GeoObject"]
        uzunlik, kenglik = (float(x) for x in obyekt["Point"]["pos"].split())
        meta = obyekt["metaDataProperty"]["GeocoderMetaData"]
    except (KeyError, TypeError, ValueError, IndexError):
        raise YolXato("Yandex javobi kutilmagan ko'rinishda") from None

    tur = meta.get("kind")
    if tur in _YANDEX_DAGAL or not _hududdami(kenglik, uzunlik):
        return None
    aniq = tur == "house" and meta.get("precision") in ("exact", "number")
    return {"lat": kenglik, "lon": uzunlik, "manba": "yandex",
            "aniqlik": "aniq" if aniq else "taxminiy", "nom": str(meta.get("text") or "")[:200]}


_yandex_ogohlantirildi = False


def geokod(manzil: str) -> dict | None:
    """Manzil -> {lat, lon, manba, aniqlik, nom}. Topilmasa None."""
    global _yandex_ogohlantirildi

    nuqta = koordinata_matndan(manzil)
    if nuqta:
        return {"lat": nuqta[0], "lon": nuqta[1], "manba": "matn", "aniqlik": "aniq", "nom": ""}

    if sozlama.yandex_kalit:
        try:
            natija = _yandex(manzil)
            if natija:
                return natija
        except YolXato as e:
            if not _yandex_ogohlantirildi:
                _yandex_ogohlantirildi = True
                log.info(f"Yandex Geocoder: {e} — OpenStreetMap ishlatiladi "
                      "(kalit va kunlik chegarani tekshiring)")
    return _osm(manzil)


# ---------------------------------------------------- bekatlar va metro
#
# Bekatlar ikki yo'l bilan olinadi:
#
#   1. Shahar nusxasi — butun shahar bekatlari, marshrut raqamlari va metro
#      bitta so'rov bilan yuklab olinadi va `data/bekatlar.json` da saqlanadi.
#      Shundan keyin istalgan nuqta uchun javob shu kompyuterning o'zida, bir
#      zumda hisoblanadi — xarita serveri ishlamay tursa ham. Dastur bilan
#      birga tayyor nusxa ham keladi (`tashrif/malumot/bekatlar.json`), shuning
#      uchun birinchi ishga tushishdayoq ishlaydi.
#   2. Nuqta bo'yicha so'rov — nusxa yo'q yoki nuqta shahardan tashqarida
#      bo'lsa, faqat shu atrof xarita serveridan so'raladi.
#
# Bepul xarita serverlari tez-tez band bo'ladi. Har bir manzil uchun ularga
# qaram bo'lish «bekatlar hali olinmadi» degan javobning sababi edi.

SHAHAR_YARIM_OLCHAMI = (0.30, 0.45)   # markazdan har tomonga, gradusda (~33 x 37 km)
NUSXA_KUN = 14                        # shahar nusxasi shuncha kunda yangilanadi
NUSXA_TANAFFUSI = 1800                # soniya: muvaffaqiyatsiz yuklashdan keyingi tanaffus
MARSHRUT_TURLARI = "^(bus|trolleybus|minibus|share_taxi|tram)$"


def _overpass_sorovi(lat: float, lon: float) -> str:
    return f"""[out:json][timeout:25];
(
  node(around:{BEKAT_RADIUSI},{lat},{lon})[highway=bus_stop];
  node(around:{BEKAT_RADIUSI},{lat},{lon})[public_transport=platform];
)->.b;
.b out body;
node(around:{METRO_RADIUSI},{lat},{lon})[railway=station][station=subway];
out body;
foreach.b->.s(
  rel(bn.s)[type=route][route~"{MARSHRUT_TURLARI}"];
  make bekat_yoli ::id = s.u(id()), refs = set(t["ref"]);
  out;
);"""


def _shahar_sorovi(hudud: list[float]) -> str:
    """Butun shahar: bekatlar, metro va har bir marshrutning bekatlari — bitta so'rovda."""
    janub, garb, shimol, sharq = hudud
    return f"""[out:json][timeout:170][bbox:{janub},{garb},{shimol},{sharq}];
(
  node[highway=bus_stop];
  node[public_transport=platform];
);
out body;
node[railway=station][station=subway];
out body;
rel[type=route][route~"{MARSHRUT_TURLARI}"]->.r;
foreach.r->.x(
  node(r.x)->.m;
  make marshrut ref = x.u(t["ref"]), tugunlar = m.set(id());
  out;
);"""


def _raqam_tartibi(raqam: str):
    m = re.match(r"\d+", raqam)
    return (int(m.group()) if m else 10 ** 6, raqam)


def _xomdan(d) -> tuple[list[dict], list[dict]]:
    """Xarita javobi -> (bekatlar, metro bekatlari), ixcham ko'rinishda.

    Ikkala so'rovning javobini tushunadi: nuqta bo'yicha so'rovda har bir
    bekatning raqamlari keladi (`bekat_yoli`), shahar nusxasida esa har bir
    marshrutning bekatlari (`marshrut`).
    """
    elementlar = d.get("elements") if isinstance(d, dict) else None
    if not isinstance(elementlar, list):
        raise YolXato("xarita javobi kutilmagan ko'rinishda")

    raqamlar: dict[int, set[str]] = {}
    for e in elementlar:
        teglar = e.get("tags") or {}
        if e.get("type") == "bekat_yoli":
            raqamlar.setdefault(e.get("id"), set()).update(
                r.strip() for r in str(teglar.get("refs") or "").split(";") if r.strip())
        elif e.get("type") == "marshrut":
            raqam = str(teglar.get("ref") or "").strip()
            if not raqam:
                continue
            for tugun in str(teglar.get("tugunlar") or "").split(";"):
                if tugun.strip().isdigit():
                    raqamlar.setdefault(int(tugun), set()).add(raqam)

    bekat, metro = [], []
    for e in elementlar:
        if e.get("type") != "node" or "lat" not in e or "lon" not in e:
            continue
        teglar = e.get("tags") or {}
        nom = str(teglar.get("name:uz") or teglar.get("name") or "").strip()
        nuqta = {"lat": round(e["lat"], 6), "lon": round(e["lon"], 6), "nom": nom}
        if teglar.get("railway") == "station":
            if nom:
                metro.append(nuqta)
            continue
        bekat_raqamlari = raqamlar.get(e.get("id"), set())
        if nom or bekat_raqamlari:
            bekat.append({**nuqta, "raqamlar": sorted(bekat_raqamlari, key=_raqam_tartibi)})
    return bekat, metro


def _yaqinlar(bekat: list[dict], metro: list[dict], lat: float, lon: float) -> dict:
    """Nuqtaga yaqin bekatlar (nomi, masofa, marshrut raqamlari) va metro.

    Yo'lning ikki tomonidagi bir xil nomli bekatlar bittaga birlashtiriladi:
    koordinatorga «qaysi tomondagi» emas, «qaysi bekat va qaysi avtobus» kerak.
    """
    guruhlar: dict[str, dict] = {}
    for b in bekat:
        # Avval arzon saralash (~1,3 km), aniq masofa faqat yaqinlari uchun.
        if abs(b["lat"] - lat) > 0.012 or abs(b["lon"] - lon) > 0.016:
            continue
        m = masofa((lat, lon), (b["lat"], b["lon"]))
        if m > BEKAT_RADIUSI:
            continue
        g = guruhlar.setdefault(oddiy_ism(b["nom"]) or f"#{b['lat']},{b['lon']}",
                                {"nom": b["nom"], "masofa": m + 1, "raqamlar": set()})
        if m < g["masofa"]:              # guruhning nuqtasi — eng yaqin bekatniki
            g.update(masofa=m, lat=b["lat"], lon=b["lon"])
        g["raqamlar"] |= set(b.get("raqamlar") or [])

    yaqin_metro: dict[str, dict] = {}
    for bekat_ in metro:
        m = masofa((lat, lon), (bekat_["lat"], bekat_["lon"]))
        if m <= METRO_RADIUSI and (bekat_["nom"] not in yaqin_metro
                                   or m < yaqin_metro[bekat_["nom"]]["masofa"]):
            yaqin_metro[bekat_["nom"]] = {"nom": bekat_["nom"], "masofa": round(m),
                                          "lat": bekat_["lat"], "lon": bekat_["lon"]}

    eng_yaqin = sorted(guruhlar.values(), key=lambda g: g["masofa"])[:8]
    return {
        "bekatlar": [{"nom": g["nom"], "masofa": round(g["masofa"]),
                      "raqamlar": sorted(g["raqamlar"], key=_raqam_tartibi),
                      "lat": g["lat"], "lon": g["lon"]} for g in eng_yaqin],
        "metro": sorted(yaqin_metro.values(), key=lambda x: x["masofa"])[:2],
    }


# ---- shahar nusxasi

_shahar: dict | None = None
_shahar_ochildi = False
_shahar_qulfi = threading.Lock()
_nusxa_urinishi = 0.0           # oxirgi yuklash urinishi (time.monotonic)


def _nusxa_fayli() -> Path:
    """Dastur o'zi yuklab olgan, yangilanib turadigan nusxa."""
    return sozlama.malumot_papkasi / "bekatlar.json"


def _toplam_fayli() -> Path:
    """Dastur bilan birga keladigan tayyor nusxa (Toshkent)."""
    return Path(__file__).resolve().parent / "malumot" / "bekatlar.json"


def _hudud() -> list[float]:
    """Shahar atrofi: [janub, g'arb, shimol, sharq]."""
    lat, lon = sozlama.geo_markaz
    dy, dx = SHAHAR_YARIM_OLCHAMI
    return [round(lat - dy, 4), round(lon - dx, 4), round(lat + dy, 4), round(lon + dx, 4)]


def _ichidami(hudud, lat: float, lon: float, chet: float = 0.0) -> bool:
    try:
        janub, garb, shimol, sharq = (float(x) for x in hudud)
    except (TypeError, ValueError):
        return False
    return janub + chet <= lat <= shimol - chet and garb + chet <= lon <= sharq - chet


def _yaroqli(nusxa) -> bool:
    """Nusxa butunmi va sozlangan shaharga tegishlimi."""
    return (isinstance(nusxa, dict) and isinstance(nusxa.get("bekatlar"), list)
            and bool(nusxa["bekatlar"]) and isinstance(nusxa.get("metro"), list)
            and _ichidami(nusxa.get("hudud"), *sozlama.geo_markaz))


def _shaharni_och() -> dict | None:
    """Shahar nusxasini xotiraga oladi: avval yangilanadigani, bo'lmasa tayyor kelgani."""
    global _shahar, _shahar_ochildi
    if _shahar_ochildi:
        return _shahar
    with _shahar_qulfi:
        if not _shahar_ochildi:
            for manba in (_nusxa_fayli(), _toplam_fayli()):
                try:
                    nusxa = json.loads(manba.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if _yaroqli(nusxa):
                    _shahar = nusxa
                    break
            _shahar_ochildi = True
    return _shahar


def shahar_nusxasini_unut() -> None:
    """Xotiradagi nusxani tashlaydi — keyingi murojaatda diskdan qayta o'qiladi."""
    global _shahar, _shahar_ochildi
    with _shahar_qulfi:
        _shahar, _shahar_ochildi = None, False


def nusxa_matni(nusxa: dict) -> str:
    return json.dumps(nusxa, ensure_ascii=False, separators=(",", ":"))


def shaharni_yukla() -> dict:
    """Butun shahar bekatlarini xarita serveridan yuklab, diskka saqlaydi.

    Tarmoqqa chiqadi (odatda 5–30 soniya) — fon oqimida chaqiriladi. Yarim
    yoki bo'sh javob mavjud nusxani bosib ketmaydi.
    """
    global _shahar, _shahar_ochildi
    hudud = _hudud()
    oxirgi: Exception | None = None
    for server in sozlama.overpass:
        try:
            bekat, metro = _xomdan(_sorov(server, data={"data": _shahar_sorovi(hudud)},
                                          kutish=200))
        except YolXato as e:
            oxirgi = e
            continue
        if not bekat:
            oxirgi = YolXato("xarita bu hudud uchun bekat qaytarmadi")
            continue
        nusxa = {"olingan": db.hozir(), "hudud": hudud,
                 "manba": "OpenStreetMap ishtirokchilari (ODbL)",
                 "bekatlar": bekat, "metro": metro}
        try:
            nishon = _nusxa_fayli()
            nishon.parent.mkdir(parents=True, exist_ok=True)
            vaqtinchalik = nishon.with_suffix(".yozilmoqda")
            vaqtinchalik.write_text(nusxa_matni(nusxa), encoding="utf-8")
            vaqtinchalik.replace(nishon)
        except OSError as e:
            log.info(f"shahar nusxasini diskka yozib bo'lmadi: {e}")
        with _shahar_qulfi:
            _shahar, _shahar_ochildi = nusxa, True
        return nusxa
    raise oxirgi or YolXato("xarita serveri sozlanmagan")


def nusxa_eskirganmi() -> bool:
    """Yangilanadigan nusxa yo'qmi yoki eskirganmi (tayyor kelgani hisobga olinmaydi)."""
    try:
        olingan = json.loads(_nusxa_fayli().read_text(encoding="utf-8")).get("olingan") or ""
    except (OSError, ValueError, AttributeError):
        return True
    return olingan < iso(utc_hozir() - timedelta(days=NUSXA_KUN))


_nusxa_oqimi: threading.Thread | None = None


def _nusxani_fonda_yangila() -> None:
    """Shahar nusxasini alohida oqimda yangilaydi.

    Yuklash bir necha daqiqa osilib turishi mumkin; shu paytda koordinator
    yuborgan joylashuv yoki manzil navbat kutib qolmasligi kerak.
    """
    global _nusxa_oqimi
    if _nusxa_oqimi is not None and _nusxa_oqimi.is_alive():
        return
    _nusxa_oqimi = threading.Thread(target=_nusxani_yangila, name="shahar-nusxasi", daemon=True)
    _nusxa_oqimi.start()


def _nusxani_yangila() -> None:
    """Kerak bo'lsa shahar nusxasini yangilaydi. Xato bo'lsa — keyinroq qayta uriniladi."""
    global _nusxa_urinishi
    if not sozlama.yol_malumoti or not nusxa_eskirganmi():
        return
    if _nusxa_urinishi and time.monotonic() - _nusxa_urinishi < NUSXA_TANAFFUSI:
        return
    _nusxa_urinishi = time.monotonic()
    try:
        nusxa = shaharni_yukla()
        log.info(f"shahar bekatlari yangilandi: {len(nusxa['bekatlar'])} ta bekat, "
              f"{len(nusxa['metro'])} ta metro bekati")
    except YolXato as e:
        mavjud = _shaharni_och()
        log.info(f"shahar bekatlarini yangilab bo'lmadi ({e}) — "
              + ("mavjud nusxa ishlatiladi" if mavjud else "keyinroq qayta uriniladi"))


def _mahalliy(lat: float, lon: float) -> dict | None:
    """Shahar nusxasidan javob (tarmoqsiz). Nusxa yo'q yoki nuqta tashqarida bo'lsa None."""
    nusxa = _shaharni_och()
    # Chetdagi nuqta atrofidagi bekatlarning bir qismi nusxaga kirmagan bo'lishi mumkin.
    if not nusxa or not _ichidami(nusxa.get("hudud"), lat, lon, chet=0.02):
        return None
    return _yaqinlar(nusxa["bekatlar"], nusxa["metro"], lat, lon)


def bekatlar(lat: float, lon: float) -> dict:
    """Nuqta atrofidagi bekatlar va metro.

    Shahar nusxasi bo'lsa — undan, darhol va tarmoqsiz. Bo'lmasa xarita
    serverlaridan so'raladi (navbat bilan sinab ko'riladi).
    """
    mahalliy = _mahalliy(lat, lon)
    if mahalliy is not None:
        return mahalliy
    oxirgi: Exception | None = None
    for server in sozlama.overpass:
        try:
            javob = _sorov(server, data={"data": _overpass_sorovi(lat, lon)}, kutish=45)
            return _yaqinlar(*_xomdan(javob), lat, lon)
        except YolXato as e:
            oxirgi = e
    raise oxirgi or YolXato("xarita serveri sozlanmagan")


# ---------------------------------- yo'nalish: turgan joydan manzilgacha
#
# Koordinator GPS orqali turgan joyini yuboradi; dastur shahar nusxasidan
# hisoblaydi: qaysi bekatdan qaysi avtobusga chiqish va qayerda tushish.
# Hammasi shu kompyuterda, tarmoqsiz. Avtobusning qaysi tomonga ketishi va
# vaqti bu yerda ma'lum emas — buning uchun xabarda Yandex Xaritalar tugmasi bor.

YURISH_RADIUSI = 800          # metr: bekatgacha odatda shuncha yuriladi
KENG_RADIUS = 1500            # yaqinda bekat bo'lmasa
METRO_YURISH = 1500


def _atrofdagi_bekatlar(nusxa: dict, lat: float, lon: float) -> list[dict]:
    """Nuqta atrofidagi nomli bekatlar, yaqinidan boshlab: [{nom, masofa, raqamlar}]."""
    for radius in (YURISH_RADIUSI, KENG_RADIUS):
        guruhlar: dict[str, dict] = {}
        for b in nusxa["bekatlar"]:
            if not b["nom"] or abs(b["lat"] - lat) > 0.02 or abs(b["lon"] - lon) > 0.027:
                continue
            m = masofa((lat, lon), (b["lat"], b["lon"]))
            if m > radius:
                continue
            g = guruhlar.setdefault(oddiy_ism(b["nom"]),
                                    {"nom": b["nom"], "masofa": m + 1, "raqamlar": set()})
            if m < g["masofa"]:
                g.update(masofa=m, lat=b["lat"], lon=b["lon"])
            g["raqamlar"] |= set(b.get("raqamlar") or [])
        if guruhlar:
            return sorted(guruhlar.values(), key=lambda g: g["masofa"])
    return []


def _eng_yaqin_metro(nusxa: dict, lat: float, lon: float) -> dict | None:
    eng = None
    for bekat_ in nusxa["metro"]:
        m = masofa((lat, lon), (bekat_["lat"], bekat_["lon"]))
        if m <= METRO_YURISH and (eng is None or m < eng["masofa"]):
            eng = {"nom": bekat_["nom"], "masofa": round(m),
                   "lat": bekat_["lat"], "lon": bekat_["lon"]}
    return eng


def _raqam_bekatlari(nusxa: dict) -> dict[str, dict[str, tuple]]:
    """Marshrut raqami -> {bekat: (nomi, kenglik, uzunlik)}. Bir marta hisoblanadi."""
    indeks = nusxa.get("_indeks")
    if indeks is None:
        indeks = {}
        for b in nusxa["bekatlar"]:
            if not b["nom"]:
                continue
            for raqam in b.get("raqamlar") or []:
                indeks.setdefault(raqam, {}).setdefault(oddiy_ism(b["nom"]),
                                                        (b["nom"], b["lat"], b["lon"]))
        nusxa["_indeks"] = indeks
    return indeks


def _qisqa(bekat_: dict) -> dict:
    return {"nom": bekat_["nom"], "masofa": round(bekat_["masofa"]),
            "lat": bekat_["lat"], "lon": bekat_["lon"]}


def _almashishlar(nusxa: dict, boshi, oxiri, chiqish: list[dict], tushish: list[dict],
                  orasi: float) -> list[dict]:
    """To'g'ri avtobus bo'lmasa: bitta almashish bilan boriladigan variantlar.

    Ikki marshrut bir xil nomli bekatdan o'tsa, o'sha yerda almashish mumkin.
    Juda aylanma variantlar tashlab yuboriladi.
    """
    indeks = _raqam_bekatlari(nusxa)
    eng_yaxshi: dict[tuple, dict] = {}
    for c in chiqish:
        for birinchi in c["raqamlar"]:
            birinchi_bekatlari = indeks.get(birinchi, {})
            for t in tushish:
                for ikkinchi in t["raqamlar"]:
                    if ikkinchi == birinchi:
                        continue
                    for k in birinchi_bekatlari.keys() & indeks.get(ikkinchi, {}).keys():
                        if k in (oddiy_ism(c["nom"]), oddiy_ism(t["nom"])):
                            continue
                        nom, lat, lon = birinchi_bekatlari[k]
                        aylanma = masofa(boshi, (lat, lon)) + masofa((lat, lon), oxiri)
                        if aylanma > orasi * 1.8 + 1500:
                            continue
                        baho = aylanma + 4 * (c["masofa"] + t["masofa"])
                        eski = eng_yaxshi.get((birinchi, ikkinchi))
                        if eski is None or baho < eski["_baho"]:
                            eng_yaxshi[(birinchi, ikkinchi)] = {
                                "birinchi": birinchi, "ikkinchi": ikkinchi, "bekat": nom,
                                "bekat_joyi": [lat, lon],
                                "chiqish": _qisqa(c), "tushish": _qisqa(t), "_baho": baho}
    saralangan = sorted(eng_yaxshi.values(), key=lambda x: x["_baho"])[:2]
    return [{k: v for k, v in x.items() if k != "_baho"} for x in saralangan]


def yonalish(boshi: tuple[float, float], oxiri: tuple[float, float]) -> dict | None:
    """Jamoat transportida `boshi` nuqtadan `oxiri` nuqtaga qanday boriladi.

    Qaytaradi: {masofa, togri: [...], metro: {...} | None, almashish: [...]}.
    Shahar nusxasi yo'q yoki nuqtalardan biri shahardan tashqarida bo'lsa — None.
    """
    nusxa = _shaharni_och()
    if (not nusxa or not _ichidami(nusxa.get("hudud"), *boshi)
            or not _ichidami(nusxa.get("hudud"), *oxiri)):
        return None

    orasi = masofa(boshi, oxiri)
    chiqish = _atrofdagi_bekatlar(nusxa, *boshi)
    tushish = _atrofdagi_bekatlar(nusxa, *oxiri)

    # Ikkala tomondagi bekatlardan o'tadigan marshrutlar — almashishsiz boradi.
    chiqish_raqamlari = set().union(*(b["raqamlar"] for b in chiqish)) if chiqish else set()
    tushish_raqamlari = set().union(*(b["raqamlar"] for b in tushish)) if tushish else set()
    juftlar: dict[tuple, dict] = {}
    for raqam in chiqish_raqamlari & tushish_raqamlari:
        c = next(b for b in chiqish if raqam in b["raqamlar"])      # eng yaqini
        t = next(b for b in tushish if raqam in b["raqamlar"])
        if oddiy_ism(c["nom"]) == oddiy_ism(t["nom"]):
            continue
        juft = juftlar.setdefault((c["nom"], t["nom"]),
                                  {"chiqish": _qisqa(c), "tushish": _qisqa(t), "raqamlar": set()})
        juft["raqamlar"].add(raqam)
    togri = sorted(juftlar.values(),
                   key=lambda j: j["chiqish"]["masofa"] + j["tushish"]["masofa"])[:3]
    for juft in togri:
        juft["raqamlar"] = sorted(juft["raqamlar"], key=_raqam_tartibi)

    metro = None
    metro_boshi = _eng_yaqin_metro(nusxa, *boshi)
    metro_oxiri = _eng_yaqin_metro(nusxa, *oxiri)
    if metro_boshi and metro_oxiri and metro_boshi["nom"] != metro_oxiri["nom"]:
        metro = {"chiqish": metro_boshi, "tushish": metro_oxiri}

    almashish = ([] if togri else
                 _almashishlar(nusxa, boshi, oxiri, chiqish, tushish, orasi))
    return {"masofa": round(orasi), "togri": togri, "metro": metro, "almashish": almashish}


def yonalish_havolasi(boshi: tuple[float, float], oxiri: tuple[float, float]) -> str:
    """Yandex Xaritalar: aynan shu ikki nuqta orasida jamoat transportida yo'l."""
    return ("https://yandex.uz/maps/?rtext="
            f"{boshi[0]:.6f}%2C{boshi[1]:.6f}~{oxiri[0]:.6f}%2C{oxiri[1]:.6f}&rtt=mt")


# ------------------------------------------------------------ bazadagi nusxa

def kalit(manzil) -> str:
    return oddiy_ism(manzil)


def _qator(manzil: str) -> dict | None:
    return db.qator_dict(db.bitta("SELECT * FROM address_geo WHERE address_norm = ?",
                                  kalit(manzil)))


def _korinish(q: dict | None) -> dict | None:
    if not q:
        return None
    try:
        yol = json.loads(q["transit_json"]) if q["transit_json"] else {}
    except ValueError:
        yol = {}
    return {
        "holat": q["status"], "lat": q["lat"], "lon": q["lon"],
        "manba": q["source"], "aniqlik": q["precision"], "nom": q["found_name"] or "",
        "bekatlar": yol.get("bekatlar") or [], "metro": yol.get("metro") or [],
    }


def ol(manzil) -> dict | None:
    """Saqlangan yo'l ma'lumoti (tarmoqqa chiqmaydi). Hali aniqlanmagan bo'lsa None."""
    manzil = str(manzil or "").strip()
    return _korinish(_qator(manzil)) if manzil else None


def joylar() -> dict[str, dict]:
    """Saqlangan barcha joylar bitta so'rov bilan: kalit(manzil) -> {holat, lat, lon, aniqlik, nom}.

    Dashboard yuzlab talabani birga ko'rsatadi — har biri uchun alohida
    so'rov o'rniga hammasi bir marta o'qiladi. Tarmoqqa chiqmaydi.
    """
    return {r["address_norm"]: {"holat": r["status"], "lat": r["lat"], "lon": r["lon"],
                                "aniqlik": r["precision"], "nom": r["found_name"] or ""}
            for r in db.hammasi(
                "SELECT address_norm, status, lat, lon, precision, found_name FROM address_geo")}


def _saqla(manzil: str, holat: str, joy: dict | None = None, yol: dict | None = None,
           urinish: int = 0, tanaffus: timedelta | None = None) -> dict:
    hozir = db.hozir()
    joy = joy or {}
    db.bajar(
        """INSERT INTO address_geo (address_norm, address, status, lat, lon, source, precision,
             found_name, transit_json, transit_at, tries, next_try_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (address_norm) DO UPDATE SET
             address = excluded.address, status = excluded.status, lat = excluded.lat,
             lon = excluded.lon, source = excluded.source, precision = excluded.precision,
             found_name = excluded.found_name,
             transit_json = COALESCE(excluded.transit_json, address_geo.transit_json),
             transit_at = COALESCE(excluded.transit_at, address_geo.transit_at),
             tries = excluded.tries, next_try_at = excluded.next_try_at,
             updated_at = excluded.updated_at""",
        kalit(manzil), manzil, holat, joy.get("lat"), joy.get("lon"), joy.get("manba"),
        joy.get("aniqlik"), joy.get("nom"),
        json.dumps(yol, ensure_ascii=False) if yol is not None else None,
        hozir if yol is not None else None, urinish,
        iso(utc_hozir() + tanaffus) if tanaffus else None, hozir,
    )
    return _korinish(_qator(manzil))


def _tanaffus(urinish: int) -> timedelta:
    """5 daqiqa, 10, 20 … ko'pi bilan 12 soat."""
    return min(timedelta(hours=12), timedelta(minutes=5 * 2 ** min(urinish - 1, 8)))


def aniqla(manzil: str) -> dict | None:
    """Manzilning joyini va bekatlarini aniqlab, bazaga yozadi.

    Tarmoqqa chiqadi va bir necha soniya oladi — veb-so'rov yoki bot oqimi
    ichida emas, fon oqimida chaqiriladi (`fonda`, `boshla`).
    """
    manzil = str(manzil or "").strip()
    if not manzil or not sozlama.yol_malumoti:
        return None

    eski = _qator(manzil)
    urinish = (eski["tries"] if eski else 0) + 1

    if eski and eski["lat"] is not None:
        # Joy allaqachon ma'lum (yoki koordinator o'zi ko'rsatgan) — qayta
        # qidirilmaydi, faqat bekatlar yangilanadi.
        joy = {"lat": eski["lat"], "lon": eski["lon"], "manba": eski["source"],
               "aniqlik": eski["precision"], "nom": eski["found_name"]}
    else:
        try:
            joy = geokod(manzil)
        except YolXato as e:
            log.info(f"joyni aniqlab bo'lmadi: {e}")
            return _saqla(manzil, "xato", urinish=urinish, tanaffus=_tanaffus(urinish))
        if not joy:
            # Matn o'zgarmaguncha natija ham o'zgarmaydi — tez-tez so'rash foydasiz.
            return _saqla(manzil, "topilmadi", urinish=urinish, tanaffus=timedelta(days=7))
        if joy["manba"] == "matn" and not joy["nom"]:
            # Nom — qulaylik, xolos: sekin xizmat tufayli bekatlar kechikmasin.
            joy["nom"] = (_muddatli(joy_nomi, 4, joy["lat"], joy["lon"])
                          or joy_tavsifi(joy["lat"], joy["lon"]))

    try:
        yol = bekatlar(joy["lat"], joy["lon"])
    except YolXato as e:
        log.info(f"bekatlarni olib bo'lmadi: {e}")
        return _saqla(manzil, "bekatsiz", joy, urinish=urinish, tanaffus=_tanaffus(urinish))
    return _saqla(manzil, "ok", joy, yol)


def sorash_kerakmi(manzil: str) -> bool:
    """Odam so'raganda xaritaga chiqish kerakmi yoki saqlangani yetarlimi.

    Tayyor natija qayta so'ralmaydi (xarita serveri sekin). Topilmagan manzil
    ham matni o'zgarmaguncha qayta so'ralmaydi. Vaqtinchalik xato bo'lgan
    bo'lsa — odam kutib turgani uchun navbat kutilmaydi, darhol uriniladi.
    """
    q = _qator(str(manzil or "").strip())
    if not q:
        return True
    if q["status"] == "ok":
        return (q["transit_at"] or "") < iso(utc_hozir() - timedelta(days=YANGILASH_KUN))
    if q["status"] == "topilmadi":
        return (q["next_try_at"] or "") <= db.hozir()
    return True


def _toldir(manzil: str, yol: dict | None) -> dict | None:
    """Joyi ma'lum, bekati yo'q manzilni shahar nusxasidan to'ldiradi (tarmoqsiz).

    Xarita serveri javob bermagan paytda saqlangan manzillar shu tufayli
    «bekatlar hali olinmadi» holatida qolib ketmaydi.
    """
    if not yol or yol["holat"] != "bekatsiz" or yol["lat"] is None:
        return yol
    mahalliy = _mahalliy(yol["lat"], yol["lon"])
    if mahalliy is None:
        return yol
    return _saqla(manzil, "ok", {"lat": yol["lat"], "lon": yol["lon"], "manba": yol["manba"],
                                 "aniqlik": yol["aniqlik"], "nom": yol["nom"]}, mahalliy)


def joy_belgila(manzil: str, lat: float, lon: float, manba: str = "sayt") -> dict | None:
    """Manzilning joyi aniq ma'lum (talaba kartasida ko'rsatilgan) — shu nuqta ishlatiladi.

    Tarmoqqa chiqmaydi: bekatlar shahar nusxasidan to'ldiriladi, nusxa
    bo'lmasa — fon oqimi keyinroq oladi. Manzil matni bo'sh bo'lsa,
    koordinataning o'zi manzil o'rnida turadi.
    """
    if not sozlama.yol_malumoti or lat is None or lon is None:
        return None
    lat, lon = float(lat), float(lon)
    manzil = str(manzil or "").strip() or nuqta_manzili(lat, lon)
    eski = _qator(manzil)
    if (eski and eski["lat"] is not None and eski["precision"] == "aniq"
            and abs(eski["lat"] - lat) < 1e-6 and abs(eski["lon"] - lon) < 1e-6):
        return _toldir(manzil, _korinish(eski))
    _saqla(manzil, "bekatsiz", {"lat": lat, "lon": lon, "manba": manba,
                                "aniqlik": "aniq", "nom": ""})
    # Eski (boshqa nuqtaga tegishli) bekatlar ko'rsatilmasin.
    db.bajar("UPDATE address_geo SET transit_json = NULL, transit_at = NULL "
             "WHERE address_norm = ?", kalit(manzil))
    natija = _toldir(manzil, ol(manzil))
    if natija and natija["holat"] != "ok":
        uygot()
    return natija


def joyni_unut(manzil: str) -> None:
    """Qo'lda ko'rsatilgan joy olib tashlandi — manzil yana xaritadan qidiriladi."""
    manzil = str(manzil or "").strip()
    if manzil:
        db.bajar("DELETE FROM address_geo WHERE address_norm = ? AND source IN ('sayt', 'qolda')",
                 kalit(manzil))
        uygot()


def qolda_qoy(manzil: str, lat: float, lon: float) -> dict | None:
    """Koordinator joyni o'zi ko'rsatdi — shu nuqta ishlatiladi va bekatlar olinadi."""
    manzil = str(manzil or "").strip()
    if not manzil or not sozlama.yol_malumoti:
        return None
    _saqla(manzil, "bekatsiz", {"lat": float(lat), "lon": float(lon), "manba": "qolda",
                                "aniqlik": "aniq", "nom": ""})
    # Eski (boshqa nuqtaga tegishli) bekatlar ko'rsatilmasin.
    db.bajar("UPDATE address_geo SET transit_json = NULL, transit_at = NULL "
             "WHERE address_norm = ?", kalit(manzil))
    return aniqla(manzil)


# Aniqlanadigan manzillar manbai: talabalarning ijara manzillari va yaqin tashriflar manzillari
# (bot ishga tushganda tashrif moduli o'rnatadi — barcha kurs bazalaridan o'qiydi).
manzillar_manbai: Callable[[], list[str]] = lambda: []  # noqa: E731


def navbatdagilar(chegara: int = 40) -> list[str]:
    """Hali aniqlanmagan yoki qayta urinish vaqti kelgan manzillar."""
    if not sozlama.yol_malumoti:
        return []
    manzillar = [m for m in manzillar_manbai() if str(m or "").strip()]

    mavjud = {r["address_norm"]: r for r in db.hammasi(
        "SELECT address_norm, status, next_try_at, transit_at FROM address_geo")}
    hozir = db.hozir()
    eskirgan = iso(utc_hozir() - timedelta(days=YANGILASH_KUN))

    natija, korilgan = [], set()
    for manzil in manzillar:
        k = kalit(manzil)
        if not k or k in korilgan:
            continue
        korilgan.add(k)
        q = mavjud.get(k)
        if q is None:
            natija.append(manzil)
        elif q["status"] == "ok":
            if (q["transit_at"] or "") < eskirgan:
                natija.append(manzil)
        elif (q["next_try_at"] or "") <= hozir:
            natija.append(manzil)
    return natija[:chegara]


# ------------------------------------------- bot xabari uchun tayyor ma'lumot

def xarita_havolasi(lat: float, lon: float) -> str:
    """Yandex Xaritalar: hozirgi joydan shu nuqtagacha jamoat transportida yo'l."""
    return f"https://yandex.uz/maps/?rtext=~{lat:.6f}%2C{lon:.6f}&rtt=mt"


def taksi_havolasi(lat: float, lon: float, boshi: tuple[float, float] | None = None) -> str:
    """Yandex Go: shu nuqtaga taksi (ilova o'rnatilmagan bo'lsa — do'kon sahifasi)."""
    qayerdan = f"start-lat={boshi[0]:.6f}&start-lon={boshi[1]:.6f}&" if boshi else ""
    return ("https://3.redirect.appmetrica.yandex.com/route"
            f"?{qayerdan}end-lat={lat:.6f}&end-lon={lon:.6f}&ref=manage_tashrif"
            "&appmetrica_tracking_id=1178268795219780156")


def qidiruv_havolasi(manzil: str) -> str:
    """Joy aniqlanmagan bo'lsa: Yandex Xaritalarda shu manzilni qidirish."""
    return "https://yandex.uz/maps/?text=" + quote(f"{sozlama.geo_shahar}, {xonadonsiz(manzil)}")


def qator(ism: str, manzil: str, talaba_id=None, nom: str = "") -> dict:
    """Bitta manzil bo'yicha xabarga tushadigan hamma narsa.

    `nom` — sarlavha sifatida aynan shunday ko'rsatiladigan matn (masalan,
    «Yuborilgan joy»); berilmasa, talabaning ismi qisqartirib yoziladi.
    """
    manzil = str(manzil or "").strip()
    yol = _toldir(manzil, ol(manzil)) if manzil else None
    # Tayyor joylashuv yuborilgan bo'lsa, sonlar o'rniga xaritadagi nomi ko'rsatiladi.
    korinish = manzil
    if yol and yol["nom"] and _FAQAT_KOORD.fullmatch(manzil):
        korinish = yol["nom"]
    natija = {"talaba_id": talaba_id, "ism": ism, "nom": nom, "manzil": manzil,
              "korinish": korinish, "yol": yol,
              "xarita": "", "taksi": "", "qidiruv": qidiruv_havolasi(manzil) if manzil else ""}
    if yol and yol["lat"] is not None:
        natija["xarita"] = xarita_havolasi(yol["lat"], yol["lon"])
        natija["taksi"] = taksi_havolasi(yol["lat"], yol["lon"])
    return natija


def talaba_yoli(talaba: dict, turgan_joy: tuple[float, float] | None = None) -> dict:
    """Saytdagi «Qanday boriladi» oynasi uchun: bitta talaba bo'yicha hamma narsa.

    Bot xabaridagi ma'lumotning o'zi, lekin xaritada chizish uchun bekat va
    metro koordinatalari bilan. Tarmoqqa chiqmaydi: saqlangan natija va shahar
    nusxasidan olinadi; manzil hali aniqlanmagan bo'lsa, fon oqimi uyg'otiladi.
    """
    manzil = str(talaba.get("address") or "").strip()
    if talaba.get("lat") is not None and talaba.get("lon") is not None:
        manzil = manzil or nuqta_manzili(talaba["lat"], talaba["lon"])
        joy_belgila(manzil, talaba["lat"], talaba["lon"])
    q = qator(talaba["full_name"], manzil, talaba["id"])
    saqlangan = q["yol"]
    natija = {"id": talaba["id"], "ism": talaba["full_name"], "manzil": q["korinish"] or manzil,
              "joy": None, "holat": "manzil_yoq" if not manzil else "aniqlanmoqda",
              "bekatlar": [], "metro": [], "yonalish": None,
              "havolalar": {"xarita": q["xarita"], "taksi": q["taksi"], "qidiruv": q["qidiruv"]}}
    if not manzil:
        return natija
    if saqlangan is None:
        uygot()
        return natija
    if saqlangan["lat"] is None:
        natija["holat"] = "topilmadi"
        return natija

    nuqta = (saqlangan["lat"], saqlangan["lon"])
    atrof = _mahalliy(*nuqta) or saqlangan       # nusxadan — koordinatalari bilan
    natija.update(holat="ok", joy={"lat": nuqta[0], "lon": nuqta[1],
                                   "aniqlik": saqlangan["aniqlik"], "manba": saqlangan["manba"]},
                  bekatlar=atrof["bekatlar"], metro=atrof["metro"])
    if turgan_joy:
        natija["yonalish"] = yonalish(turgan_joy, nuqta)
        natija["havolalar"]["xarita"] = yonalish_havolasi(turgan_joy, nuqta)
        natija["havolalar"]["taksi"] = taksi_havolasi(*nuqta, boshi=turgan_joy)
    return natija


def reja_yoli(reja: dict) -> list[dict]:
    """Rejadagi har bir talaba manzili bo'yicha yo'l ma'lumoti.

    Talaba kartasida joylashuv ko'rsatilgan bo'lsa, aynan o'sha nuqta
    ishlatiladi — manzil matni xaritadan qanday topilishidan qat'i nazar.
    """
    natija = []
    for s in reja.get("talabalar") or []:
        manzil = str(s.get("address") or "").strip()
        if s.get("lat") is not None and s.get("lon") is not None:
            manzil = manzil or nuqta_manzili(s["lat"], s["lon"])
            joy_belgila(manzil, s["lat"], s["lon"])
        natija.append(qator(s["full_name"], manzil, s.get("student_id")))
    return natija


# ------------------------------------------------------------- fon oqimlari
#
# Ikkita oqim bor va ular bir-birini kutmaydi:
#
#   so'rovlar — koordinator hozir so'ragan narsa (joylashuv tashladi, manzil
#               yozdi). Darhol bajariladi.
#   navbat    — kiritilgan manzillarni birma-bir aniqlab chiqadi. Sekin
#               xarita xizmatida bitta manzil yarim daqiqa olishi mumkin;
#               shu paytda odam kutib qolmasligi kerak.

_ishlar: queue.Queue = queue.Queue()
_uygot_belgisi = threading.Event()
_toxta = threading.Event()
_oqim: threading.Thread | None = None           # navbat
_ish_oqimi: threading.Thread | None = None      # so'rovlar
_ulangan = False


def _yoqilganmi() -> bool:
    return _ish_oqimi is not None and _ish_oqimi.is_alive()


def uygot(**_) -> None:
    """Yangi manzil paydo bo'ldi — fon oqimi navbatni qayta ko'rib chiqadi."""
    _uygot_belgisi.set()


def fonda(fn: Callable, **malumot) -> None:
    """Tarmoqqa chiqadigan ishni fon oqimida bajaradi (yoqilmagan bo'lsa — darhol).

    Xabarlar navbatidan alohida: xarita so'rovi yarim daqiqa olishi mumkin,
    bu paytda boshqa xabarlar (kirish kodi, tasdiq so'rovi) kutib qolmasligi kerak.
    """
    if _yoqilganmi():
        _ishlar.put((fn, malumot))
    else:
        fn(**malumot)


def _ish_halqasi() -> None:
    while True:
        ish = _ishlar.get()
        if ish is None:
            return
        fn, malumot = ish
        try:
            fn(**malumot)
        except Exception as e:                       # noqa: BLE001
            log.info(f"so'rov bajarilmadi: {e}")


def _halqa() -> None:
    _toxta.wait(5)                   # dastur to'liq ishga tushib olsin
    while not _toxta.is_set():
        _nusxani_fonda_yangila()
        try:
            manzillar = navbatdagilar()
        except Exception as e:                       # noqa: BLE001
            log.info(f"navbatni o'qib bo'lmadi: {e}")
            manzillar = []
        for manzil in manzillar:
            if _toxta.is_set():
                return
            try:
                aniqla(manzil)
            except Exception as e:                   # noqa: BLE001
                log.info(f"manzilni aniqlashda xato: {e}")
            _toxta.wait(1.5)         # xizmatlarni band qilmaslik uchun
        _uygot_belgisi.wait(120)
        _uygot_belgisi.clear()
        _toxta.wait(3)               # bir yo'la kiritilgan manzillar yig'ilib olsin


def ulan() -> None:
    """Talaba manzili o'zgarganda fon oqimi o'zi uyg'onadi (tashrif moduli `uygot()` ni chaqiradi)."""
    global _ulangan
    _ulangan = True


def ulanishni_tiklash() -> None:
    """Testlar orasida obunani qaytadan ro'yxatdan o'tkazish uchun."""
    global _ulangan
    _ulangan = False


def boshla() -> threading.Thread | None:
    global _oqim, _ish_oqimi
    if sozlama.sinov or not sozlama.yol_malumoti or _yoqilganmi():
        return _oqim
    _toxta.clear()
    _ish_oqimi = threading.Thread(target=_ish_halqasi, name="yol-sorovlari", daemon=True)
    _ish_oqimi.start()
    _oqim = threading.Thread(target=_halqa, name="yol-navbati", daemon=True)
    _oqim.start()
    manba = "Yandex + OpenStreetMap" if sozlama.yandex_kalit else "OpenStreetMap"
    nusxa = _shaharni_och()
    bekatlar_ = (f"{len(nusxa['bekatlar'])} ta bekat kompyuterda saqlangan" if nusxa
                 else "bekatlar xarita serveridan so'raladi")
    log.info(f"manzillar bo'yicha bekat va avtobuslar aniqlanadi ({manba}; {bekatlar_})")
    return _oqim


def toxtat() -> None:
    global _oqim, _ish_oqimi
    oqim, _oqim = _oqim, None
    ish_oqimi, _ish_oqimi = _ish_oqimi, None
    _toxta.set()
    _uygot_belgisi.set()
    if ish_oqimi is not None and ish_oqimi.is_alive():
        _ishlar.put(None)
    for o in (oqim, ish_oqimi):
        if o is not None and o.is_alive():
            o.join(timeout=3)
