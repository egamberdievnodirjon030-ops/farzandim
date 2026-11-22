# 🚕 Shahar Taksi — Telegram botlar orqali avtomatlashtirilgan taksi xizmati

Shahar ichida taksi chaqirish va haydovchilarni boshqarish tizimi. Ikkita bot — **yo'lovchilar** va
**haydovchilar** uchun alohida (yoki bitta bot: kirishda "Yo'lovchi / Haydovchi" so'raladi).
Telegramning eng yangi bot imkoniyatlari ishlatilgan: rangli tugmalar, xarita bloki bilan Rich Message kartalari,
xabar effektlari, bosilmaydigan va nusxa oluvchi tugmalar.

![Taxminiy ko'rinish](skrinshotlar/0_umumiy.png)

*Taxminiy ko'rinish: matn, tugma va ranglar bot kodidan olingan; alohida ekranlar — `skrinshotlar/` papkasida.*

---

## ✨ Asosiy imkoniyatlar

| | |
|---|---|
| 🙋 **Yo'lovchi** | 1 tugma — **🚕 Taksi chaqirish** (joylashuv avtomatik yuboriladi) → manzil (ixtiyoriy) → narx → **Buyurtma berish** |
| 🚕 **Haydovchi** | Buyurtmada 2 asosiy tugma: **📍 Yo'lovchini olish manzili** (navigatorda yo'l darhol ochiladi) va **📞 Yo'lovchi bilan aloqa** (kompaniya raqami orqali) |
| 🔒 **Maxfiylik** | Telefon raqamlari, ismlar, profillar bir-biriga **hech qachon** ko'rinmaydi. Yo'lovchi faqat mashina modeli, rangi, davlat raqami va reytingni ko'radi |
| 🎯 **Aniq qidiruv** | Faqat bo'sh haydovchilar; masofa diapazonlari bo'yicha to'lqinlar; har bir to'lqin **1 daqiqa**; **reytingi yuqorilar birinchi** ko'radi |
| 💳 **Balans** | Yo'lovchi manzilga yetganini **tasdiqlagandan so'ng** haydovchi balansidan xizmat narxining **10%** yechiladi |
| 🗺 **Jonli xarita** | Yo'lovchi mashina yaqinlashishini Telegram jonli xaritasida kuzatadi |
| 🧮 **Taksometr** | Manzil ko'rsatilmasa, narx haydovchining jonli joylashuvi bo'yicha bosib o'tilgan yo'ldan hisoblanadi (GPS shovqini va sakrashlar filtrlanadi) |
| 💬 **Anonim chat** | Safar davomida yozilgan matn/ovozli xabarlar ikkinchi tomonga muallifi ko'rinmasdan yetkaziladi |

---

## 🔄 Jarayon

```
Yo'lovchi                      Tizim                                  Haydovchi
─────────                      ─────                                  ─────────
🚕 Taksi chaqirish ──────────▶ joylashuv + aniqlik (±m)
📍 manzil / ⏭ manzilsiz ─────▶ yo'l masofasi, narx, yaqin mashinalar
🚕 Buyurtma berish ──────────▶ 1-to'lqin (1 km): ⭐ yuqori reyting ──▶ 🔔 Yangi buyurtma
                               10 s keyin qolganlar ────────────────▶ 🔔 (masofa, yo'nalish, narx)
                               60 s javob yo'q → 2 km → 3.5 km → …
🚕 Haydovchi topildi ◀──────── atomik qabul (faqat 1 kishi oladi) ◀── ✅ Qabul qilish
   (mashina, raqam, ⭐, ETA)                                          📍 Yo'lovchini olish manzili
   + jonli xarita                                                     📞 Yo'lovchi bilan aloqa
🔔 Haydovchi yetib keldi ◀───────────────────────────────────────────── ✅ Yetib keldim
🚀 Safar boshlandi ◀──────────────────────────────────────────────────── 🚀 Safarni boshlash
🏁 Yetib keldingizmi? ◀───────────────────────────────────────────────── 🏁 Safarni yakunlash
✅ Ha, yetib keldim ─────────▶ COMPLETED, balansdan −10% ───────────▶ ✅ Yakunlandi, balans
⭐⭐⭐⭐⭐ baholash ──────────▶ reyting (Bayes o'rtachasi)
```

### Haydovchi qidirish algoritmi (`taxi_bot/services/dispatch.py`, `matching.py`)

1. **Nomzodlar** — faqat: tasdiqlangan, liniyada, **yo'lovchisi yo'q**, balansi yetarli, joylashuvi yangi
   (jonli joylashuv faol yoki oxirgi yangilanish muddati o'tmagan) haydovchilar. Avval SQL indeks bo'yicha
   kvadrat (bounding box), keyin Haversine formulasi bilan aniq masofa.
2. **Yo'l masofasi** — `OSRM_URL` berilsa, har bir haydovchidan yo'lovchigacha **haqiqiy yo'llar bo'yicha**
   masofa va vaqt (OSRM table API) hisoblanadi: daryo yoki temir yo'l ortidagi "yaqin" haydovchi uzoq hisoblanadi.
   OSRM bo'lmasa — to'g'ri chiziq × `ROAD_FACTOR`.
3. **To'lqinlar** — `WAVE_RADII_KM=1,2,3.5,5,8`. Har bir diapazon `WAVE_TIMEOUT_SEC=60` soniya kutadi.
   Oldingi to'lqindagilar ham buyurtmani ko'rishda davom etadi. Diapazonda hech kim bo'lmasa — kutmasdan
   kengaytiriladi; to'lqindagilarning hammasi rad etsa — muddatidan oldin keyingisiga o'tiladi.
   Kutish davomida shu radiusda **yangi bo'shagan** haydovchi ham darhol taklif oladi.
4. **Reyting ustuvorligi** — to'lqin ichida reytingi `PRIORITY_RATING` (4.8) dan yuqorilar
   `PRIORITY_HEADSTART_SEC` (10 s) oldin ko'radi; tartib: reyting ↓, yetib kelish vaqti ↑.
5. **Qabul qilish atomik** — `UPDATE … WHERE status='searching'`: bir vaqtda 10 kishi bossa ham faqat bittasi
   oladi, qolganlaridagi taklif darhol o'chiriladi.
6. Haydovchi bekor qilsa — buyurtma avtomatik qayta qidiruvga tushadi (bekor qilgan haydovchiga qayta chiqmaydi).
7. `SEARCH_TIMEOUT_SEC` ichida topilmasa — yo'lovchiga **🔄 Qayta qidirish** tugmasi.

### Narx

* Manzil ko'rsatilgan — **belgilangan narx**: `BASE_FARE` (`BASE_KM` gacha) + `PER_KM` × qolgan km.
* Manzilsiz — **taksometr**: jonli joylashuv bo'yicha haqiqiy yo'l.
* Kutish: `FREE_WAIT_MIN` daqiqa bepul, keyin har to'liq daqiqa uchun `PER_WAIT_MIN`.
* Xizmat haqi: yakuniy narxning `COMMISSION_PERCENT` (10%) — **faqat yo'lovchi tasdig'idan keyin** yechiladi
  (yo'lovchi `FINISH_CONFIRM_TIMEOUT_MIN` ichida javob bermasa — avtomatik yakunlanadi, `0` — o'chirish).
  Har bir harakat `transactions` jadvalida (ledger) saqlanadi.

---

## 🎨 Telegramning yangi imkoniyatlari

| Imkoniyat | Bot API | Qayerda |
|---|---|---|
| Rangli tugmalar (`style`: success / danger / primary) | 9.4 | Barcha tugmalar: ✅ yashil, ❌ qizil, 📞 ko'k; pastki menyu tugmalari ham |
| Tugmalarda custom emoji (`icon_custom_emoji_id`) | 9.4 | `BUTTON_EMOJI_IDS` (bot egasida Premium kerak) |
| **Rich Messages** — sarlavha, **xarita bloki**, jadval, footer | 10.x | Buyurtma kartalari: haydovchida yo'lovchini olish joyi xaritada |
| Xabar effektlari | 7.4 | Safar yakunida 🎉 |
| Bosilmaydigan tugma (`disabled`) | 10.x | "⏳ Tasdiq kutilmoqda…" |
| Nusxa olish tugmasi (`copy_text`) | 7.11 | Balans: "📋 ID ni nusxalash" |
| Jonli joylashuv | — | Haydovchi joylashuvi, yo'lovchiga mashina harakati |
| Reaksiyalar | 7.0 | Chat xabari yetkazilganda 👌 |

Rich Message qo'llab-quvvatlanmasa (eski ilova yoki xato), xuddi shu karta avtomatik oddiy HTML ko'rinishida
yuboriladi — foydalanuvchi hech narsani sezmaydi (`RICH_MESSAGES=false` bilan butunlay o'chirish mumkin).

---

## 🚀 O'rnatish

### 1. Botlar
1. [@BotFather](https://t.me/BotFather) → `/newbot` — **yo'lovchilar boti** (masalan `ShaharTaksiBot`).
2. Yana `/newbot` — **haydovchilar boti** (masalan `ShaharTaksiDriverBot`).
   *Bitta bot xohlasangiz — `DRIVER_BOT_TOKEN` ni bo'sh qoldiring.*
3. O'z Telegram ID'ingizni bilib oling (masalan [@userinfobot](https://t.me/userinfobot)) — `ADMIN_IDS` ga yozing.

### 2. Sozlash
```bash
cp .env.example .env
nano .env    # tokenlar, ADMIN_IDS, tarif, COMPANY_PHONE ...
```

### 3. Ishga tushirish

**Docker (tavsiya):**
```bash
docker compose up -d --build     # yig'ish va fonda ishga tushirish
docker compose logs -f bot       # loglar ("Run polling for bot @..." — bot ishlayapti)
```

| Amal | Buyruq |
|---|---|
| To'xtatish | `docker compose down` |
| Qayta ishga tushirish (`.env` o'zgargach) | `docker compose up -d` |
| Kodni yangilash | `git pull && docker compose up -d --build` |
| Bazani zaxiralash | `docker compose cp bot:/app/data/taxi.db ./taxi-backup.db` |

Baza `taxi-data` nomli Docker volume'da saqlanadi — konteyner qayta yaratilsa ham o'chmaydi
(`docker compose down -v` esa uni **o'chiradi**). Server qayta yoqilsa, bot o'zi ishga tushadi.

**Oddiy usul (Python 3.11+):**
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m taxi_bot
```

### 4. Birinchi qadamlar
1. Haydovchi botida `/start` → ro'yxatdan o'tish (raqam, ism, mashina, rang, davlat raqami).
2. Admin (siz) arizani **✅ Tasdiqlash** tugmasi bilan tasdiqlaysiz.
   *Muhim:* arizalar admin'ga **haydovchi boti** orqali keladi — avval haydovchi botida `/start` bosing
   (yoki `ADMIN_CHAT_ID` guruhiga haydovchi botini qo'shing), aks holda bot sizga yoza olmaydi.
3. Haydovchi balansini to'ldiring: `/topup ID 50000`.
4. Haydovchi **🟢 Liniyaga chiqish** → jonli joylashuvni ulashadi («Men o'chirmagunimcha»).
5. Yo'lovchi botida **🚕 Taksi chaqirish** — tayyor!

---

## 📞 Aloqa — kompaniya raqami orqali (`CALL_PROVIDER`)

Haydovchi **📞 Yo'lovchi bilan aloqa** ni bosganda raqamlar oshkor qilinmaydi:

| Qiymat | Qanday ishlaydi |
|---|---|
| `zadarma` | [Zadarma](https://zadarma.com) callback API: ATS kompaniya raqamidan avval tugmani bosganga, u javob bergach ikkinchi tomonga qo'ng'iroq qilib ulaydi. `ZADARMA_KEY`, `ZADARMA_SECRET`, `ZADARMA_SIP` (CallerID = kompaniya raqami) |
| `webhook` | O'z ATS'ingiz (Asterisk, OnlinePBX, …): `CALL_WEBHOOK_URL` ga `{"order_id", "first", "second"}` JSON POST, `X-Taxi-Secret` sarlavhasi bilan. ATS `first` → `second` callback qiladi |
| `operator` | Dispetcherlik guruhiga (`ADMIN_CHAT_ID`) ikkala raqam bilan so'rov boradi, operator kompaniya telefonidan ulaydi |
| `none` | O'chirilgan (faqat `COMPANY_PHONE` ko'rsatiladi) |

Spamdan himoya: bir buyurtmada `CALLS_PER_ORDER` ta qo'ng'iroq, har biri orasida `CALL_COOLDOWN_SEC`.

## 💳 Balansni to'ldirish

* **Admin:** `/topup ID summa` (manfiy summa — yechish).
* **Click / Payme orqali (avtomatik):** @BotFather → haydovchi boti → *Payments* → Click yoki Payme →
  olingan tokenni `PAYMENT_PROVIDER_TOKEN` ga yozing. Haydovchi **💰 Balans** → summani tanlaydi → to'laydi →
  balans avtomatik to'ldiriladi (takroriy to'lov ikki marta yozilmaydi).

## 🗺 OSRM — haqiqiy yo'llar bo'yicha aniq masofa (ixtiyoriy, tavsiya etiladi)

```bash
mkdir osrm && cd osrm
wget https://download.geofabrik.de/asia/uzbekistan-latest.osm.pbf
docker run -t -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/car.lua /data/uzbekistan-latest.osm.pbf
docker run -t -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-partition /data/uzbekistan-latest.osrm
docker run -t -v "$PWD:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-customize /data/uzbekistan-latest.osrm
```
So'ng `docker-compose.yml` dagi `osrm` xizmatini yoqing va `.env` ga `OSRM_URL=http://osrm:5000` yozing.
OSRM ishlamay qolsa, tizim avtomatik taxminiy hisobga o'tadi.

---

## 🛠 Admin buyruqlari (istalgan botda, faqat `ADMIN_IDS` uchun)

| Buyruq | |
|---|---|
| `/admin` | Panel: liniyadagi/bo'sh haydovchilar, faol buyurtmalar, bugungi aylanma va komissiya |
| `/pending` | Tasdiq kutayotgan haydovchilar (tasdiqlash/rad etish tugmalari bilan) |
| `/driver ID` | Haydovchi ma'lumoti (ID yoki Telegram ID) |
| `/topup ID summa` | Balansni to'ldirish |
| `/block ID`, `/unblock ID` | Bloklash / faollashtirish |

---

## 🧪 Testlar

```bash
pip install -r requirements.txt pytest pytest-asyncio
pytest -q
```
30 ta test: geolokatsiya, tarif, to'lqinlar va reyting ustuvorligi, bir vaqtda qabul qilish poygasi, taksometr,
avtomatik yakunlash, qayta qidiruv, to'lovlar idempotentligi va **ikkala botning to'liq end-to-end sinovi**
(soxta Telegram server bilan) — jumladan, hech bir so'rovda boshqa tomonning raqami yoki ismi yo'qligini tekshirish.

## 📁 Tuzilma

```
taxi_bot/
├── app.py                 # yig'ish va ishga tushirish (ikki bot / bitta bot)
├── config.py              # .env sozlamalari
├── db/models.py           # Passenger, Driver, Order, OrderOffer, Transaction
├── services/
│   ├── taxi.py            # biznes-logika: buyurtma holatlari, komissiya, aloqa, chat
│   ├── dispatch.py        # to'lqinli qidiruv dvigateli
│   ├── matching.py        # nomzodlarni saralash (masofa, reyting)
│   ├── geo.py, routing.py # Haversine, OSRM
│   ├── pricing.py         # tarif va komissiya
│   └── telephony.py       # kompaniya raqami orqali qo'ng'iroq
├── ui/
│   ├── kit.py             # rangli tugmalar, Rich Message kartalari
│   ├── views.py           # har bir holat uchun kartalar
│   └── messenger.py       # Telegram'ga yuborish (zaxira variantlar bilan)
└── bots/                  # passenger.py, driver.py, admin.py, common.py
```

## ⚠️ Eslatmalar

* Bir nusxada (bitta jarayon) ishlash uchun mo'ljallangan. Katta yuklamada PostgreSQL (`DATABASE_URL`) va
  Redis (`REDIS_URL`, FSM uchun) ulang.
* Haydovchilar uchun jonli joylashuv majburiy (`REQUIRE_LIVE_LOCATION=true`) — bu qidiruv aniqligi va
  taksometr uchun muhim. Xohlasangiz `false` qilib, oddiy joylashuvga ham ruxsat bering.
