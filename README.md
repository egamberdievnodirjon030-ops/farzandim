# 🚕 Shahar Taksi — Telegram botlar orqali avtomatlashtirilgan taksi xizmati

Shahar ichida taksi chaqirish va haydovchilarni boshqarish tizimi. Ikkita bot — **yo'lovchilar** va
**haydovchilar** uchun alohida (yoki bitta bot: kirishda "Yo'lovchi / Haydovchi" so'raladi).
Telegramning eng yangi bot imkoniyatlari ishlatilgan: rangli tugmalar, xarita bloki bilan Rich Message kartalari,
xabar effektlari, bosilmaydigan va nusxa oluvchi tugmalar.

![Taxminiy ko'rinish](skrinshotlar/0_umumiy.png)

*Taxminiy ko'rinish: matn, tugma va ranglar bot kodidan olingan; alohida ekranlar — `skrinshotlar/` papkasida.*

---

## 📱 Telegram ilovasi (Mini App) — yo'lovchi va haydovchi uchun

![Telegram ilovasi](skrinshotlar/ilova_umumiy.png)

Botdagi **«🚕 Taksi»** menyu tugmasi (yoki «Ilovani ochish») Telegram ichida to'liq ekranli xarita ilovasini ochadi.
Bot esa bildirishnomalar uchun qoladi (yangi buyurtma, haydovchi yetib keldi va h.k.).

**Yo'lovchi:**
* ilova ochilishi bilan **telefon joylashuvi avtomatik so'raladi** (Telegram LocationManager), olish joyi — xarita
  markazidagi nina, manzil nomi avtomatik aniqlanadi (ninani surib aniqlashtirish mumkin);
* **Manzilning ikki alohida usuli:**
  * **🏁 Xaritada** (🏠 Uy / 🏢 Ish / oxirgi manzil / qidiruv / «xaritada belgilash») → **marshrut chizig'i va qat'iy
    narx darhol**; safar faqat shu nuqtada yakunlanadi;
  * **✍️ Manzil nomini yozish** (xaritasiz, mahalliy nom: «Chorsu bozori, 5-maktab yonida») → haydovchiga aytiladi,
    narx safar oxirida **taksometr bo'yicha (km)**;
* qidiruvda **radar** va atrofdagi bo'sh mashinalar; haydovchi topilgach mashina xaritada **silliq harakatlanadi**,
  **mashina boradigan yo'l bo'yicha** qolgan vaqt va km ko'rinadi; davlat raqami, rangi, reytingi; bepul kutish taymeri;
* safar davomida: manzilgacha yo'l bo'yicha vaqt; oldinroq tushmoqchi bo'lsangiz — **«🛑 Shu yerda tushaman»**
  (manzil mashinaning joriy joyiga o'zgaradi, narx bosib o'tilgan yo'l bo'yicha);
* izoh, boshqa odam uchun buyurtma, baholash, sevimli haydovchi, manzilni saqlash.

**Ikkalasi uchun:**
* **📡 Jonli joylashuv** — ilova ochilishi bilan **avtomatik yoqiladi** va **o'zingiz o'chirmaguningizcha** ishlaydi
  (yuqoridagi «📡» tugmasi; tanlov saqlanadi). Har ~3 soniyada yangilanadi. Yo'lovchining joylashuvi faqat faol
  buyurtma paytida (qidiruv → haydovchi yo'lda → kutmoqda) yuboriladi va haydovchi xaritasida **«🙋»** bo'lib ko'rinadi;
  safar boshlangach ko'rsatilmaydi.
* **Marshrut ko'chalar bo'yicha** — eng qisqa yo'l burilishlari bilan chiziladi (OSRM), yo'ldan aniq nuqtagacha bo'lgan
  qism («kirish») punktir bilan. Mashina yurganda bosib o'tilgan qismi kesiladi; boshqa ko'chaga burilsa — marshrut
  qayta hisoblanadi. Narx ham shu yo'l uzunligi bo'yicha.

**Haydovchi:**
* ilovada ro'yxatdan o'tish (raqam Telegram orqali tasdiqlanadi), 🎁 tasdiqlangach **30 000 so'm bonus**;
* katta **«Liniyaga chiqish»** tugmasi — joylashuv avtomatik yoqiladi va ilova ochiq paytida uzluksiz yuboriladi;
* **taklif kartasi**: yo'lovchigacha **mashinada boriladigan yo'l bo'yicha** masofa va vaqt (yo'lning narigi tomoni
  to'g'ri chiziqda 150 m bo'lsa ham, aylanib o'tish hisobga olinadi), safar uzunligi va yo'nalishi, narx, izoh,
  taxminiy hudud (aniq manzil qabul qilingach ochiladi);
* **«🚀 Safarni boshlash»** bosilishi bilan **navigator o'zi ochiladi** (standart — Yandex; ⚙️ da Google/Waze),
  manzilgacha yo'l bilan;
* **safarni faqat yo'lovchi belgilagan manzilga yetib kelganda yakunlaydi** (Yandex Go kabi, `FINISH_RADIUS_M`,
  standart 200 m): ungacha tugma «🏁 Manzilgacha 2.3 km» bo'lib nofaol turadi. Yo'lovchi tasdig'i kutilmaydi —
  10% xizmat haqi darhol yechiladi. Manzil yozma (xaritasiz) yoki ko'rsatilmagan bo'lsa — istalgan joyda, taksometr;
* **📞 Aloqa**, **jonli taksometr**, balans va bugungi tushum.
* **Bekor qilish** — faqat safar boshlanmasdan oldin (yo'lovchi ham, haydovchi ham); boshlangach — faqat yakunlash.

**Bitta bot rejimida rol** birinchi ro'yxatdan o'tishda bir marta tanlanadi («🙋 Yo'lovchi» / «🚕 Haydovchi») va
ilova doim shu rejimda ochiladi — ilovada rolni almashtirish yo'q. (Admin yoki foydalanuvchi zarur bo'lsa chatda
`/role` bilan o'zgartirishi mumkin; safardagi haydovchi buni safar tugaguncha qila olmaydi.)

**Ishga tushirish:** Telegram ilovani faqat **HTTPS** manzildan ochadi.
* **Kompyuterda (Windows):** `start.bat` (`run.py`) rasmiy `cloudflared.exe` ni o'zi yuklab oladi va bepul
  `https://….trycloudflare.com` tunnelini **fonda** ochadi. Bot darhol ishlay boshlaydi, tunnel ochilgach menyudagi
  «🚕 Taksi» tugmasi o'zi yangilanadi (manzil har ishga tushganda o'zgaradi — bu normal).
  * Tarmoq DNS'i Cloudflare manzillarini bloklasa (ofis/provayder), **DNS'siz usul** o'zi ishga tushadi: tunnel
    manzili DNS-over-HTTPS (to'g'ridan-to'g'ri 1.1.1.1 / 8.8.8.8) orqali olinadi, `cloudflared` esa Cloudflare
    hujjatidagi doimiy server IP'lariga (`198.41.192.x`, `198.41.200.x`, port 7844) ulanadi.
  * Bu ham ishlamasa, **zaxira tunnel** — [localhost.run](https://localhost.run) — Windows 10/11 dagi o'rnatilgan
    `ssh` orqali o'zi sinab ko'riladi (`https://….lhr.life`).
  * Tunnel uzilsa — qayta ochiladi va tugma yangi manzilga o'tadi. Umuman ochilmasa — tugma olib tashlanadi
    (buzuq havola qolmaydi), bot **chat rejimida ishlayveradi** va sababi oynada yoziladi
    (`⚠️ Cloudflare tunnel ochilmadi: ...`).
  * Telegram'da tugma eski manzilni ochsa — bot chatini yopib qayta oching.
  * `lookup api.trycloudflare.com ... no data of the requested type` (yoki `no such host`) — kompyuter ulangan
    tarmoq DNS'i tunnelni bloklayapti; bot shundan keyin **DNS'siz usulni o'zi sinaydi** (`Cloudflare (DNS'siz)`).
    U ham ochilmasa (`no recent network activity`, `timeout`) — tarmoq firewall'i 7844-portni ham to'smoqda:
    kompyuterni boshqa internetga (telefon hotspoti, uy Wi-Fi) ulang yoki Windows DNS'ini `1.1.1.1` / `8.8.8.8` ga
    o'zgartiring. Bot o'chirilmasa ham bo'ladi — tunnel fonda qayta urinadi va «🚕 Taksi» tugmasi o'zi qaytadi.
  * Qo'lda o'rnatish: `winget install --id Cloudflare.cloudflared` yoki
    [GitHub'dan](https://github.com/cloudflare/cloudflared/releases/latest) `cloudflared-windows-amd64.exe` ni yuklab,
    nomini `cloudflared.exe` qilib loyiha papkasiga qo'ying (~60 MB bo'lishi kerak). Buzilgan fayl avtomatik o'chiriladi.
  * Ilovani butunlay o'chirish: `.env` da `WEBAPP_TUNNEL=none`. Mac/Linux: `brew install cloudflared` yoki
    [cloudflared'ni o'rnating](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
  * Bepul tunnellar sinov uchun. Doimiy ishlash uchun — pastdagi doimiy domen varianti.
* **Serverda (doimiy domen):** `.env` da `WEBAPP_URL=https://taxi.sizning-domen.uz`, `WEBAPP_HOST=0.0.0.0` va
  domenni reverse-proxy (masalan Caddy) orqali `8081`-portga yo'naltiring.

**Cheklovlar (halol):**
* Telegram ilovasi joylashuvni **faqat ilova ochiq (yoki yig'ilgan) paytida** yuboradi. Ilova yopiq bo'lsa ham ishlashi
  uchun chatda jonli joylashuv ulashiladi: 📎 → Joylashuv → Jonli joylashuv → **«Men o'chirmagunimcha»**.
  Telegram qoidasiga ko'ra bot buni **o'zi yoqa olmaydi** (chatdagi tugma faqat bir martalik joylashuv so'raydi) —
  bir marta o'zingiz tanlaysiz, keyin u siz o'chirmaguningizcha ishlaydi. Haydovchi ham, yo'lovchi ham ulasha oladi.
* Marshrut chizig'i bepul ommaviy OSRM serverlaridan olinadi (OpenStreetMap jamoasining FOSSGIS serveri, zaxira —
  OSRM demo): natijalar keshlanadi, so'rovlar sekundiga ko'pi bilan 1 ta. Kompyuter ularga yeta olmasa, ilova
  marshrutni telefon interneti orqali o'zi oladi. Yuklama oshsa — o'z OSRM serveringiz (pastda, `OSRM_URL`).
* Xarita tayllari va manzil qidiruvi — OpenStreetMap (bepul, adolatli foydalanish cheklovi bilan). Yuklama oshsa
  `TILE_URL` ga tijoriy provayder (masalan MapTiler) va o'z Nominatim/Photon serveringizni ulang.

## ✨ Asosiy imkoniyatlar

| | |
|---|---|
| 🙋 **Yo'lovchi** | 1 tugma — **🚕 Taksi chaqirish** (joylashuv avtomatik yuboriladi) → manzil (ixtiyoriy) → narx → **Buyurtma berish** |
| 🚕 **Haydovchi** | Buyurtmada 2 asosiy tugma: **📍 Yo'lovchini olish manzili** (navigatorda yo'l darhol ochiladi) va **📞 Yo'lovchi bilan aloqa** (kompaniya raqami orqali) |
| 🔒 **Maxfiylik** | Telefon raqamlari, ismlar, profillar bir-biriga **hech qachon** ko'rinmaydi. Yo'lovchi faqat mashina modeli, rangi, davlat raqami va reytingni ko'radi. Izoh va chatda yozilgan telefon raqam / @username avtomatik yashiriladi (`•••`) — kompaniyani chetlab o'tib kelishishning oldi olinadi |
| 🎯 **Aniq qidiruv** | Faqat bo'sh haydovchilar; masofa diapazonlari bo'yicha to'lqinlar; har bir to'lqin **1 daqiqa**; **reytingi yuqorilar birinchi** ko'radi |
| 💳 **Balans** | Haydovchi safarni **yo'lovchi manzilida** yakunlagach balansidan xizmat narxining **10%** yechiladi |
| 🗺 **Jonli xarita** | Yo'lovchi mashina yaqinlashishini Telegram jonli xaritasida kuzatadi |
| 🧮 **Taksometr** | Manzil ko'rsatilmasa, narx haydovchining jonli joylashuvi bo'yicha bosib o'tilgan yo'ldan hisoblanadi (GPS shovqini va sakrashlar filtrlanadi) |
| 💬 **Anonim chat** | Safar davomida yozilgan matn/ovozli xabarlar ikkinchi tomonga muallifi ko'rinmasdan yetkaziladi |

---

## 🏆 Raqobatdagi ustunliklar (yirik agregatorlarga qarshi)

Kuchli tomonimiz — Telegram ichida ishlash, mahalliy odatlarga moslik va haydovchilar uchun adolatli shartlar.

### Yo'lovchi uchun
| Imkoniyat | Nima beradi |
|---|---|
| 📲 **Ilova o'rnatish shart emas** | Telegram bor har kim darhol foydalanadi — ro'yxatdan o'tish 1 tugma (raqam) |
| 🏠 **Saqlangan manzillar (Uy / Ish / +5 ta)** | "Uyga taksi" — **3 bosish**: 🚕 Taksi chaqirish → 🏠 Uy → Buyurtma berish. Oxirgi manzillar ham shu yerda |
| 🔒 **Qat'iy narx** | Narx buyurtmadan oldin ko'rsatiladi va talab oshganda ham ko'tarilmaydi |
| ❤️ **Sevimli haydovchi** | Yoqqan haydovchini saqlang — u yaqin bo'lsa, buyurtmangizni **birinchi** bo'lib ko'radi |
| 👤 **Boshqa odam uchun buyurtma** | Ota-ona, bola yoki mehmon uchun: haydovchi aynan o'sha odam bilan kompaniya raqami orqali bog'lanadi |
| 📍 **"Haydovchi yaqinlashmoqda"** | ~400 m qolganda ogohlantirish — chiqishga tayyorlanasiz, bepul kutish vaqti tejaladi |

### Haydovchi uchun (haydovchi ko'p bo'lsa — mashina tez keladi)
| Imkoniyat | Nima beradi |
|---|---|
| 💸 **Past komissiya (10%)** | Faqat manzilda yakunlangan safardan |
| 🟢 **Safar tugashi bilan bo'sh** | Manzilda «Safarni yakunlash» bosilgach darhol yangi buyurtma oladi — tasdiq kutilmaydi |
| 🏡 **"Uyga" rejimi** | Ish oxirida faqat uy tomonga ketayotgan buyurtmalar (bo'sh qaytishning oldi olinadi) |
| 🧭 **Shaffof taklif** | Qabul qilishdan oldin masofa, safar uzunligi, **yo'nalishi** va narxi ko'rinadi |
| 🚫 **Jarimasiz** | Taklifni o'tkazib yuborish reyting yoki balansga ta'sir qilmaydi |
| 📍 **Avtomatik "Yetib keldim"** | GPS bo'yicha manzilga yetganda o'zi bosiladi — rul ortida telefon bilan ovora bo'lish kamayadi |

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

0. **❤️ Sevimli haydovchilar** — yo'lovchining sevimli haydovchisi `FAVORITE_RADIUS_KM` ichida bo'sh bo'lsa,
   buyurtmani `FAVORITE_HEADSTART_SEC` oldin ko'radi.
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
5. **🏡 "Uyga" rejimi** — bu rejimdagi haydovchiga faqat uy tomonga ketayotgan (manzili ma'lum) buyurtma chiqadi.
6. **Qabul qilish atomik** — `UPDATE … WHERE status='searching'`: bir vaqtda 10 kishi bossa ham faqat bittasi
   oladi, qolganlaridagi taklif darhol o'chiriladi.
7. Haydovchi bekor qilsa — buyurtma avtomatik qayta qidiruvga tushadi (bekor qilgan haydovchiga qayta chiqmaydi).
8. `SEARCH_TIMEOUT_SEC` ichida topilmasa — yo'lovchiga **🔄 Qayta qidirish** tugmasi.

### Narx

* Manzil xaritada — **belgilangan narx**: `BASE_FARE` (`BASE_KM` gacha) + `PER_KM` × qolgan km (yo'l bo'yicha).
* Manzil yozma (xaritasiz) yoki ko'rsatilmagan — **taksometr**: jonli joylashuv bo'yicha bosib o'tilgan haqiqiy yo'l (km).
* «🛑 Shu yerda tushaman» — qat'iy narx o'rniga bosib o'tilgan yo'l bo'yicha.
* Kutish: `FREE_WAIT_MIN` daqiqa bepul, keyin har to'liq daqiqa uchun `PER_WAIT_MIN`.
* Xizmat haqi: yakuniy narxning `COMMISSION_PERCENT` (10%) — haydovchi safarni manzilda yakunlashi bilan yechiladi.
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

## 💻 Kompyuterda ishga tushirish (eng oson yo'l)

### Windows
1. **Python o'rnating** (3.11 yoki yangiroq): [python.org/downloads](https://www.python.org/downloads/).
   O'rnatish oynasida **"Add python.exe to PATH"** belgisini albatta qo'ying.
2. **Loyihani yuklab oling:** GitHub'da shu branchni oching → **Code → Download ZIP** → arxivni
   masalan `C:\taxi` papkasiga oching (yoki `git clone`).
3. Papkadagi **`start.bat`** faylini ikki marta bosing. Birinchi marta:
   * kerakli kutubxonalar o'zi o'rnatiladi (internet kerak, 1–2 daqiqa);
   * **sozlash yordamchisi** bot tokenini so'raydi va Telegram orqali tekshiradi;
   * admin ID'ingizni **o'zi aniqlaydi** — botingizga istalgan xabar yuborasiz, xolos;
   * hammasi `.env` fayliga yoziladi va bot ishga tushadi.
4. Keyingi safar shunchaki `start.bat` ni bosing. To'xtatish — `Ctrl+C` yoki oynani yopish.

`start.bat` faqat Python'ni topib, `run.py` ni ishga tushiradi; qolgan hamma ishni (disk joyi, kutubxonalar,
cloudflared, sozlash) `run.py` bajaradi. Oyna **o'zicha yopilmaydi** — xato bo'lsa, matni oynada qoladi.
Agar `start.bat` ishlamasa, papkada manzil satriga `cmd` yozib Enter bosing va `py run.py` ni kiriting.

### Mac / Linux
```bash
bash start.sh
```

### Qo'lda (har qanday tizim)
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   |   source .venv/bin/activate  — Mac/Linux
pip install -r requirements.txt
python -m taxi_bot setup          # sozlash yordamchisi (.env yaratadi)
python -m taxi_bot                # ishga tushirish
```

### Bilish kerak
* Bot **kompyuter yoniq va dastur ochiq turgan paytda** ishlaydi. Windows'da uyqu rejimini o'chiring:
  *Sozlamalar → Tizim → Quvvat → Uyqu: Hech qachon*. Doimiy ishlashi uchun keyinchalik serverga (VPS) o'tkazing — pastda Docker bo'limi.
* Diskda kamida **~300 MB bo'sh joy** kerak (kutubxonalar ~70 MB, cloudflared ~60 MB). `run.py` buni o'zi tekshiradi;
  `No space left on device` xatosi — disk to'lgan: vaqtinchalik fayllar, Savat, loyihaning eski nusxasini tozalang.
* Bitta token bilan **faqat bitta nusxa** ishlashi mumkin. Loglarda `TelegramConflictError` chiqsa — bot boshqa joyda ham ishlab turibdi.
* Ma'lumotlar `data\taxi.db` faylida, loglar `data\bot.log` da. Zaxira uchun `data` papkasini nusxalang.
* Sozlamalarni o'zgartirish: `.env` faylini Bloknot bilan oching (tarif, komissiya, radiuslar), so'ng botni qayta ishga tushiring.
  Tokenni almashtirish: `python -m taxi_bot setup` (yoki `.env` ni o'chirib `start.bat` ni bosing).

---

## 🖥 Serverda (Docker bilan) ishga tushirish

### 1. Botlar
1. [@BotFather](https://t.me/BotFather) → `/newbot` — **yo'lovchilar boti** (masalan `ShaharTaksiBot`).
2. Xohlasangiz yana `/newbot` — **haydovchilar boti**. Bitta bot bo'lsa — `DRIVER_BOT_TOKEN` bo'sh qoladi
   va bot kirishda "Yo'lovchi / Haydovchi" deb so'raydi.

### 2. Sozlash
```bash
cp .env.example .env
nano .env    # PASSENGER_BOT_TOKEN, ADMIN_IDS, tarif, COMPANY_PHONE ...
```

### 3. Ishga tushirish
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

## 🏁 Birinchi qadamlar
1. **Haydovchi:** botda `/start` → **🚕 Haydovchi** (ikki bot rejimida — haydovchilar botida `/start`) →
   ro'yxatdan o'tish: raqam, ism, mashina, rang, davlat raqami.
2. **Admin (siz)** arizani **✅ Tasdiqlash** tugmasi bilan tasdiqlaysiz. Ariza kelishi uchun o'zingiz avval
   botda `/start` bosgan bo'lishingiz kerak (sozlash yordamchisi bu qadamni o'zi qildiradi).
3. Haydovchi balansini to'ldiring: `/topup ID 50000` (ID — arizadagi raqam).
4. Haydovchi **🟢 Liniyaga chiqish** → jonli joylashuvni ulashadi («Men o'chirmagunimcha»).
5. **Yo'lovchi:** `/start` → **🙋 Yo'lovchi** → **🚕 Taksi chaqirish** — tayyor!

Bitta odam ham haydovchi, ham yo'lovchi bo'lib sinab ko'rishi mumkin: rolni almashtirish — `/role`.
(O'zingizning buyurtmangiz o'zingizga haydovchi sifatida kelmaydi — sinash uchun ikkinchi telefon kerak.)

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

Standart holatda marshrut chizig'i va narx ommaviy OSRM serverlaridan olinadi (`ROUTE_URLS`, o'chirish:
`ROUTE_URLS=none`). O'z serveringiz bilan esa hamma hisob (haydovchilarni saralash ham) cheklovsiz va tez ishlaydi:

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

## 🖥 Admin web-panel

Bot ishga tushganda konsolda manzil va parol chiqadi: **http://localhost:8080** (faqat shu kompyuterdan ochiladi).

![Admin panel](skrinshotlar/admin_panel.png)

* **📊 Umumiy** — liniyadagi/bo'sh/band haydovchilar, faol buyurtmalar, bugungi aylanma va komissiya, arizalar;
  **jonli xarita** (bo'sh — yashil, band — sariq, joylashuvi eskirgan — kulrang, buyurtmalar — qizil);
  faol buyurtmalar ro'yxati va **majburan bekor qilish** (qotib qolgan holatlar uchun).
* **📋 Buyurtmalar** — faol / bugun / hammasi, qidiruv (#raqam, telefon, davlat raqami).
* **🚕 Haydovchilar** — arizalarni tasdiqlash/rad etish, bloklash, **balansni to'ldirish**.
* **🙋 Yo'lovchilar** — safar va bekor qilishlar soni, bloklash (yolg'on buyurtmalarga qarshi).
* **💰 Moliya** — 7/14/30 kunlik aylanma, komissiya, to'ldirishlar, kunlik grafik va tranzaksiyalar.

Sozlamalar: `ADMIN_PANEL_PORT`, `ADMIN_PANEL_PASSWORD` (bo'sh bo'lsa avtomatik yaratiladi va
`data/admin_panel_password.txt` da saqlanadi). Tarmoqdagi boshqa kompyuterdan ochish uchun
`ADMIN_PANEL_HOST=0.0.0.0` (faqat ishonchli tarmoqda!).

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
# PostgreSQL'da tekshirish (servis testlari):
TEST_DATABASE_URL=postgresql+asyncpg://taxi:taxi@localhost:5432/taxi pytest -q tests/test_flow.py tests/test_features.py tests/test_review_fixes.py
```
89 ta test: geolokatsiya, tarif, to'lqinlar va reyting ustuvorligi, bir vaqtda qabul qilish poygasi, taksometr,
avtomatik yakunlash, qayta qidiruv, to'lovlar idempotentligi, sevimli haydovchi, "Uyga" rejimi, saqlangan
manzillar, ikki marta bosishdan himoya, kontaktlarni yashirish, eski bazani yangilash va **ikkala botning to'liq
end-to-end sinovi**
(soxta Telegram server bilan) — jumladan, hech bir so'rovda boshqa tomonning raqami yoki ismi yo'qligini tekshirish.

## 📁 Tuzilma

```
taxi_bot/
├── app.py                 # yig'ish va ishga tushirish (botlar, admin panel, Mini App, tunnel)
├── miniapp/               # Telegram ilovasi: server (initData tekshiruvi, API) + static (xarita UI)
├── web/                   # admin web-panel (localhost:8080)
├── config.py              # .env sozlamalari
├── db/models.py           # Passenger, Driver, Order, OrderOffer, Transaction
├── services/
│   ├── taxi.py            # biznes-logika: buyurtma holatlari, komissiya, aloqa, chat
│   ├── features.py        # saqlangan manzillar, sevimli haydovchilar, "Uyga" rejimi
│   ├── privacy.py         # chat va izohdagi telefon raqam / username'larni yashirish
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

* Yangi versiyaga o'tganda baza avtomatik yangilanadi (yetishmayotgan ustun va jadvallar qo'shiladi, ma'lumot o'chmaydi).

* Bir nusxada (bitta jarayon) ishlash uchun mo'ljallangan. Katta yuklamada PostgreSQL (`DATABASE_URL`) va
  Redis (`REDIS_URL`, FSM uchun) ulang.
* Haydovchilar uchun jonli joylashuv majburiy (`REQUIRE_LIVE_LOCATION=true`) — bu qidiruv aniqligi va
  taksometr uchun muhim. Xohlasangiz `false` qilib, oddiy joylashuvga ham ruxsat bering.
