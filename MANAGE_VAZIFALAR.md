# Bot va panelni «Manage» bilan integratsiya qilish: vazifalar ro'yxati

Hujjat ikki jamoa uchun:
- **Manage jamoasi** — API beradi.
- **Bot jamoasi** — bot va boshqaruv paneli tomonini qiladi.

Ma'muriyat (dekanat, buxgalteriya, yuridik bo'lim) bajaradigan ishlar alohida belgilangan.

Ustuvorlik darajalari:
- 🔴 — birinchi navbatda;
- 🟡 — keyin;
- ⚪ — ixtiyoriy.

---

## 0. Hozirgi holat

| Ma'lumot | Hozir qayerdan keladi |
|---|---|
| Fanlar, kreditlar, o'tilgan darslar | Manage `student-subjects?hemisId=…&academicYearId=…`. Bot so'raydi (polling) |
| Shaxsiy dars jadvali | Manage `student-timetable/weekly?hemisId=…&monday=…` |
| **Davomat**: talaba darsda bo'lgan yoki bo'lmagani | ❌ Manage'da yo'q. Excel yoki HEMIS statistikasi qo'lda yuklanadi |
| Talabalar ro'yxati (kontingent), telefonlar, manzillar | Excel, qo'lda |
| Baholar, GPA, akademik qarzdorlar | HEMIS Excel, qo'lda |
| Kontrakt va trimestr qarzdorligi | Buxgalteriya Excel, qo'lda, yoki panelda chek bilan |
| Ijtimoiy toifalar | Excel, koordinator yoki talabaning o'zi (ilova) |
| Tanlov fanlari va 2-til | Excel, qo'lda |
| Koordinator va dekan panelga kirishi | Telegram bot orqali bir martalik havola |

Bot tomonida tayyor bo'lgan narsalar:
- polling;
- webhook qabul qilish: `POST /api/integration/attendance` va `/schedule`;
- maydonlarni nomiga qarab avtomatik tanish;
- integratsiya holati dekan va koordinator bosh sahifasida.

**Asosiy maqsad:** qo'lda Excel yuklashni bosqichma-bosqich to'xtatish.

---

## 1-bosqich. Davomat — eng muhim 🔴

Ota-onaga dars qoldirilgani haqidagi xabar shu ma'lumotdan ketadi. Hozir u Excel'ga bog'liq.

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 1.1 | `student-subjects` javobidagi har bir `subjectTypes` elementiga `attendedCount`, `absentCount`, `excusedCount` maydonlarini qo'shish (batafsil: `INTEGRATSIYA.md`) | Manage | Bitta talaba uchun javobda maydonlar bor. Qiymat o'qituvchi jurnaliga mos keladi |
| 1.2 | **Yoki** (afzalroq): dars bo'yicha haftalik davomat `student-attendance/weekly?hemisId=…&monday=…`. Har bir yozuvda sana, juftlik, fan, holat (keldi / kelmadi / sababli / kechikdi) bo'ladi | Manage | Ota-onaga «qaysi kun, qaysi juftlik» aniq boradi. Bot bu manzilni o'zi sinab topadi |
| 1.3 | Guruh yoki kurs bo'yicha **ommaviy** so'rov: `…?groupId=…` yoki sahifalangan barcha talabalar ro'yxati | Manage | 1 000+ talaba uchun 1 000 ta alohida so'rov kerak bo'lmaydi. Javob 5 soniyadan tez qaytadi |
| 1.4 | So'rov chegarasini (rate limit) va ruxsat etilgan chastotani yozma kelishib olish | Manage + Bot | Bot sozlamasi (`INTEGRATION_*_INTERVAL`, `INTEGRATION_CONCURRENCY`) shunga moslangan |
| 1.5 | ⚪ Real vaqt: davomat belgilanishi bilan Manage botga `POST /api/integration/attendance` yuboradi (`X-Integration-Token`) | Manage | Xabar ota-onaga bir necha soniyada boradi |
| 1.6 | Bot serverida ulanishni sinash va birinchi sinxronlashni jim o'tkazish (`INTEGRATION_FIRST_SILENT=1`, eski qoldirishlar uchun xabar ketmaydi) | Bot | `/integratsiya` buyrug'i «ishlayapti» ko'rsatadi. Bosh sahifada Manage yashil |
| 1.7 | Excel va Manage davomatini bir hafta parallel solishtirish, keyin davomat Excel'ini to'xtatish | Bot + dekanat | Farq 1% dan kam. Davomat endi faqat Manage'dan |
| 1.8 | O'qituvchi qoldirishni o'chirsa yoki «sababli» qilsa — keyingi so'rovda o'zgargan holat kelishi | Manage | Botda yozuv «keldi» yoki «sababli»ga o'zgaradi. Ota-onaga to'g'rilash ko'rinadi |

---

## 2-bosqich. Talabalar ro'yxati va ma'lumotnomalar 🔴

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 2.1 | Kontingent endpointi `GET /students?facultyId=…&course=…&page=…`. Maydonlar: HEMIS ID, F.I.Sh., guruh, kurs, fakultet, ta'lim shakli, to'lov turi (grant/kontrakt), holat (o'qiydi / akademik ta'til / chetlatilgan / ko'chgan), talaba telefoni | Manage | Bitta so'rovda fakultetning barcha talabalari (sahifalab) |
| 2.2 | Guruhlar ro'yxati: guruh, kurs, til, ⚪ tyutor | Manage | Guruh nomlari jadval va davomatdagi nomlar bilan bir xil |
| 2.3 | Tanlov fanlari va 2-til biriktirish: talaba → fan → kichik guruh | Manage | «Tanlov fanlari» Excel'i kerak bo'lmaydi |
| 2.4 | Botda yangi tur — `students`. Kunda 1 marta polling, natija Excel importi bilan bir xil yo'ldan o'tadi | Bot | Yangi talaba avtomatik qo'shiladi, guruh o'zgarishi yangilanadi |
| 2.5 | Manage'da yo'qolgan yoki chetlatilgan talabani **o'chirmaslik**: «faol emas» deb belgilash, ota-ona va tarix saqlanadi | Bot | Ma'lumot yo'qolmaydi. Ro'yxatda «faol emas» filtri bor |
| 2.6 | ⚪ Ota-ona telefoni va doimiy manzil — Manage'da bo'lsa | Manage | Ota-onani bot bilan bog'lash raqam orqali avtomatik |

---

## 3-bosqich. O'zlashtirish 🟡

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 3.1 | Baholar: `GET /student-grades?hemisId=…&semester=…` — fan, umumiy ball, baho, kredit | Manage | Talaba kartasi va ilovadagi «Baholar» Excel'siz to'ladi |
| 3.2 | GPA: semestr va umumiy | Manage | Dinamikadagi «O'rtacha GPA» va «GPA past» avtomatik |
| 3.3 | Akademik qarzdorlar: talaba, fan, semestr, holat (qayta topshirish sanasi) | Manage | «Akademik qarzdorlar» Excel'i kerak bo'lmaydi |
| 3.4 | ⚪ Guruh yoki kurs bo'yicha ommaviy variant (1.3 kabi) | Manage | — |
| 3.5 | Botda turlar: `grades`, `gpa`, `acad_debts`. Har kuni oqshom sinxronlash va snapshot (dinamika uchun) | Bot | Bosh sahifadagi akademik ko'rsatkichlar va dinamika yangilanadi |

---

## 4-bosqich. To'lovlar (kontrakt va trimestr) 🟡

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 4.1 | Moliya endpointi: shartnoma summasi, to'langan, qarz, muddat, trimestrlar kesimida. ⚪ To'lovlar tarixi (sana, summa) | Manage yoki buxgalteriya tizimi | «Kontrakt / trimestr qarzdorligi» Excel'i kerak bo'lmaydi |
| 4.2 | Panelda chek bilan yopilgan qarz va Manage ma'lumotini muvofiqlashtirish: Manage'da to'lov tushgach chek yozuvi «tasdiqlandi» bo'ladi | Bot | Chek va rasmiy to'lov ikki marta hisoblanmaydi |
| 4.3 | ⚪ Botdagi chekni (PDF/rasm) buxgalteriyaga Manage orqali yuborish: `POST /payments/receipt` | Manage + Bot | Buxgalter chekni Manage'da ko'radi |
| 4.4 | Ma'lumotni kim, qachon va qaysi chastotada yangilashini buxgalteriya bilan kelishish | Ma'muriyat | Yozma kelishuv |

---

## 5-bosqich. Botdan Manage'ga qaytarish ⚪

Bu bosqich yozish huquqini talab qiladi. Har bir oqim bo'yicha alohida ruxsat va yuridik kelishuv kerak.

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 5.1 | Faqat **koordinator tasdiqlagan** ijtimoiy toifalar → `POST /students/{hemisId}/social-category` | Manage + Bot | Tasdiqlanmagan (talaba o'zi kiritgan) yozuv yuborilmaydi |
| 5.2 | Intizomiy choralar (tushuntirish xati, ogohlantirish, hayfsan) va buyruq raqami → Manage | Manage + Bot | Chora Manage'dagi talaba profilida ko'rinadi |
| 5.3 | Sababli qoldirish hujjati (ma'lumotnoma) → Manage'da «sababli» belgisi uchun so'rov | Manage + Bot | O'qituvchi yoki dekanat bitta joyda tasdiqlaydi |
| 5.4 | Talaba yashash joyi: faqat tasdiqlangan **turi** (yotoqxona / ijara / uy). Aniq manzil, xaritadagi joy va xonadon toifasi (yashil / sariq / qizil) **yuborilmaydi** — ular faqat kurs koordinatorida qoladi | Bot | Yuboriladigan maydonlar ro'yxati ma'muriyat bilan tasdiqlangan |
| 5.5 | Ota-ona va talaba botga ulanganmi — statistika (son), shaxsiy ma'lumotsiz | Bot | Manage hisobotida «botga ulanganlar %» |
| 5.6 | Navbat va qayta urinish: Manage ishlamasa yozuvlar yo'qolmaydi. Jurnal: nima, qachon, kim yubordi | Bot | Manage o'chiq bo'lsa ham keyin hammasi yetib boradi |

---

## 6-bosqich. Kirish (SSO) va rollar 🟡

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 6.1 | Manage orqali kirish: OAuth2 / OpenID Connect yoki Manage imzolagan bir martalik havola | Manage | Koordinator Manage'dan bitta tugma bilan panelga kiradi, Telegram shart emas |
| 6.2 | Manage lavozimi → bot roli: dekan → super-admin, kurs koordinatori → kurs. Lavozimdan olinsa huquq darhol yo'qoladi | Manage + Bot | Rollar qo'lda `.env` da yozilmaydi |
| 6.3 | Manage menyusida «Ota-onalar boti» havolasi. ⚪ Panelni Manage ichiga joylash (iframe, `frame-ancestors`) | Manage + Bot | — |
| 6.4 | Telegram orqali kirish zaxira sifatida qoladi | Bot | — |

---

## 7-bosqich. Xavfsizlik, sinov va ishga tushirish 🔴

Bu bosqich barcha bosqichlarga taalluqli.

| № | Vazifa | Kim | Qabul mezoni |
|---|---|---|---|
| 7.1 | Alohida kalitlar: **faqat o'qish** (1–4-bosqichlar) va **yozish** (5-bosqich). Muddatli, almashtiriladigan | Manage | Kalit faqat bot serveridagi `.env` da. Chat, xat va repozitoriyda emas |
| 7.2 | Bot serveri IP manzilini Manage'da ruxsat etilganlar ro'yxatiga qo'shish. Faqat HTTPS | Manage | — |
| 7.3 | Webhook so'rovini HMAC imzo bilan tekshirish (`X-Signature`, vaqt belgisi) | Bot | Soxta yoki takroriy so'rov rad etiladi |
| 7.4 | Sinov muhiti (staging) va soxta namunaviy ma'lumot | Manage | Bot jamoasi real talabalarsiz sinaydi |
| 7.5 | Shaxsiy ma'lumotlar bo'yicha kelishuv: qaysi maydon, qaysi maqsad, saqlash muddati. Jurnallarda shaxsiy ma'lumot yo'q | Ma'muriyat + yuridik | Imzolangan hujjat |
| 7.6 | Monitoring: integratsiya xato bersa yoki 1 soatdan ortiq ma'lumot kelmasa — super-adminga xabar | Bot | Bosh sahifada «Manage» sariq yoki qizil bo'ladi va xabar keladi |
| 7.7 | Har bosqich oxirida tegishli Excel yuklamani o'chirish (fallback sifatida qoldirish) va `INTEGRATSIYA.md` ni yangilash | Bot | — |

---

## Manage jamoasi bilan birinchi uchrashuvda kelishiladigan savollar

1. Talabaning yagona identifikatori: **HEMIS ID**. Hamma endpointda shu bo'ladimi?
2. `academicYearId` va semestr qanday aniqlanadi? Har yil qo'lda o'zgartirilmasligi uchun joriy yilni beradigan endpoint kerak.
3. Davomat Manage'da dars bo'yicha saqlanadimi yoki faqat jami son? Bu 1.1 va 1.2 orasidagi tanlovni hal qiladi.
4. So'rov chegarasi, ish vaqti, texnik xizmat oynalari.
5. Moliya ma'lumoti Manage'da bormi yoki alohida buxgalteriya tizimidami?
6. Yozish (5-bosqich) uchun kim ruxsat beradi?
7. Muddatlar va har bosqich uchun mas'ul shaxslar.

## Taxminiy ketma-ketlik

1. **1-bosqich** (davomat) va **7.1–7.4** (xavfsizlik) — 2–3 hafta.
2. **2-bosqich** (kontingent) — 2 hafta.
3. **3-bosqich** (o'zlashtirish) va **6-bosqich** (SSO) — parallel, 3–4 hafta.
4. **4-bosqich** (to'lovlar) — buxgalteriya bilan kelishuvdan keyin.
5. **5-bosqich** (qaytarish) — yuridik kelishuvdan keyin.

Bot tomonidagi har bir bosqich Manage endpointi tayyor bo'lgach odatda 2–5 ish kunida ulanadi. Sababi: ma'lumot
Excel importi bilan bir xil yo'ldan o'tadi.
