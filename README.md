# Ota-onalar uchun davomat boti (JIDU)

Telegram bot ota-onalarga farzandining qaysi kunlarda, qaysi fanlardan darsga qatnashgani yoki qoldirganini, dars jadvali va baholarini ko'rsatadi, dars qoldirilganda darhol xabar beradi va kurs koordinatori bilan yozishma kanalini ochadi. Ma'lumotlar kurs koordinatori tomonidan Excel (.xlsx) fayllar orqali yuklanadi.

**Asosiy ish tartibi — ilova.** `WEBAPP_URL` (HTTPS manzil) sozlangan bo'lsa, barcha ish Telegram ilovasida (Web App) va kompyuter versiyasida bajariladi; bot esa faqat ilovani ochadi va qisqa bildirishnomalar yuboradi («Farzandingiz davomatida o'zgarish bo'ldi», «Yangi hujjat — «Hayfsan»»). Quyida sanalgan bot menyulari — ilova manzili sozlanmaganda (yoki `BOT_FULL_MENU=1`) ishlaydigan to'liq bot rejimi. Batafsil — «Telegram Web App» bo'limi.

## Imkoniyatlar

**Ota-ona uchun:**

- farzandning ism yoki familiyasini yozish orqali uning sahifasini ochish (faqat o'ziga bog'langan farzandlar orasida qidiriladi);
- davomat: bugun, kecha, shu hafta, o'tgan hafta, shu oy, semestr boshidan, ixtiyoriy sana yoki oraliq; har bir juftlik bo'yicha holat (✅ qatnashdi, ❌ sababsiz, 🟡 sababli, ⏰ kechikdi, ⚪ ma'lumot hali kiritilmagan);
- fanlar kesimidagi davomat foizi va sababsiz qoldirishlar ulushi yuqori bo'lgan fanlarni belgilash;
- dars jadvali — hafta kunlari bo'yicha (Dushanba — Shanba tugmalari; bugungi kun 📍 bilan belgilangan, yakshanba kuni — kelasi hafta; toq/juft haftalar hisobga olinadi) va baholar;
- avtomatik xabarlar: dars qoldirilganda darhol, har kuni kechqurun xulosa, sababsiz soatlar chegaradan oshganda ogohlantirish, yangi baho qo'yilganda xabar (har birini «⚙️ Bildirishnomalar»da o'chirish mumkin);
- «✉️ Kurs koordinatoriga savol» — savol kurs koordinatoriga boradi, javob botga qaytadi;
- «📄 Hujjatlar» — kurs koordinatori yuborgan tushuntirish xatlari, dekan ogohlantirishlari va hayfsanlar (PDF); hujjatda boshqa talabalar bo'lsa, ularning ma'lumotlari qora rang bilan yopilgan bo'ladi; yangi hujjat darhol keladi va farzand sahifasida saqlanib turadi;
- e'lonlar arxivi (ota-onalar yig'ilishi va boshqalar), foydali ma'lumot va kurs koordinatori kontakti;
- **uch til: o'zbek, rus, ingliz** — ota-ona birinchi kirishda tilni tanlaydi, keyin «🌐 Til» tugmasi yoki `/til` bilan o'zgartiradi.

**Telegram Web App (ilova):** bot havolasidan ochiladigan zamonaviy ilova — botdagi barcha imkoniyatlar bitta qulay interfeysda, JIDU ranglarida (to'q ko'k va bordo): farzandning umumiy holati, davomat va chegaralar, jadval, baholar, dinamika, to'lovlar, hujjatlar, kurs koordinatori bilan yozishma, bildirishnomalar markazi. Kurs koordinatori uchun — kurs holati paneli, talabalar, xabarlar, e'lon, fayl yuklash va hisobot. Batafsil — «Telegram Web App» bo'limi.

**Kompyuter versiyasi:** kurs koordinatori va super-admin uchun brauzerdagi boshqaruv paneli — butun kurs bitta jadvalda (saralash, filtrlar), xabarlar va suhbat yonma-yon, so'rovlar, e'lon (uch tildagi ko'rinishi bilan), fayllarni sudrab yuklash, hisobotni yuklab olish; super-admin — barcha kurslar, kurslar va koordinatorlar, zaxira nusxa va xatolar jurnali. Kirish — botdagi «💻 Kompyuter versiyasi» tugmasi (parolsiz). Batafsil — «Kompyuter versiyasi» bo'limi.

**Kurs koordinatori (admin) uchun:** Excel import, e'lon yuborish (hammaga yoki guruhlar bo'yicha, oldindan ko'rish bilan), bog'lash so'rovlarini tasdiqlash, savollarga javob, statistika, talaba qidirish, talaba bo'lib kirishga uringanlar haqida darhol xabar va ularni bloklash yoki xato bo'lsa ruxsat berish.

## Rollar: ota-ona, kurs koordinatori, super-admin

Har bir rol o'z menyusini ko'radi — kurs koordinatori va super-admin ota-ona menyusini ko'rmaydi va ulardan telefon raqami so'ralmaydi (interfeys o'zbek tilida).

- **Kurs koordinatori** — pastki menyu: «📥 Fayl yuklash», «📊 Kurs holati», «🔎 Talaba qidirish», «📈 Statistika», «📢 E'lon yuborish», «📄 Hujjat yuborish», «💰 Qarzdorlar», «📏 Chegaralar», «📥 Hisobot (Excel/PDF)», «🌐 Tarjimalar», «ℹ️ Barcha buyruqlar». Talabani topish uchun familiyasini shunchaki yozish kifoya.
- **Super-admin** (`.env` dagi `SUPERADMIN_IDS`) — «🏫 Kurslar va koordinatorlar», «📊 Umumiy holat» (barcha kurslar bo'yicha), «🔀 Kursga kirish» (tanlangan kursda kurs koordinatori vositalari bilan ishlash, qaytish — «🛡 Super-admin menyusi»), «➕ Yangi kurs», «💾 Zaxira nusxa», «🧾 Xatolar jurnali».

### Kurs va koordinatorlarni bot ichidan boshqarish

Serverga kirish va botni qayta ishga tushirish shart emas — o'zgarish darhol ishlaydi:
- **Yangi kurs**: «➕ Yangi kurs» → nomini yozing → alohida papka va baza yaratiladi.
- **Kurs koordinatorini qo'shish**: kurs kartasida «👤 Koordinator qo'shish» → «👤 Foydalanuvchini tanlash» tugmasi bilan Telegram kontaktlaringizdan tanlang (yoki Telegram ID sini yozing). Koordinatorga xabar boradi va uning menyusi darhol o'rnatiladi; u botni hali ochmagan bo'lsa — sizga aytiladi. Koordinatorni boshqa kursga o'tkazish ham shu yo'l bilan.
- **Olib tashlash**: kurs kartasida «🗑 …» → tasdiqlash. Kurs ma'lumotlari o'chmaydi; olib tashlangan koordinator admin buyruqlaridan foydalana olmaydi.
- **Kurs nomini o'zgartirish**: papka nomi o'zgarmaydi, ma'lumotlar joyida qoladi.

`.env` dagi `ADMIN_IDS` va `KURSLAR` — faqat boshlang'ich sozlama: bot birinchi ishga tushganda umumiy ro'yxatga (`central.db`) yoziladi, keyin hamma narsa bot ichidan boshqariladi. Bot ichidan olib tashlangan koordinator `.env` da qolib ketsa ham qayta qo'shilmaydi. Koordinatori yo'q kursning xabarlari (savollar, bog'lash so'rovlari) super-adminga boradi — boshqa kurslarning koordinatorlariga emas.

### Koordinatorlarga guruh biriktirish

Bitta kursda bir nechta kurs koordinatori bo'lsa, ma'lumotlar chalkashmasligi uchun har biriga o'z guruhlari biriktiriladi:
- **Bot**: kurs kartasida «👥 <koordinator>: guruhlar» → guruhlarni bosib belgilang (✅ — biriktirilgan, 🔒 — boshqa koordinatorniki) yoki «✍️ Guruh nomlarini yozish» (talabalar hali yuklanmagan bo'lsa: `XM-21, XM-22`).
- **Kompyuter versiyasi**: «Kurslar va koordinatorlar» → koordinator yonidagi «Guruhlar» tugmasi.
- Bitta guruh faqat bitta koordinatorga biriktiriladi.

Guruhlari bor koordinator fayl yuklaganda (talabalar, davomat, baholar, akademik qarzdorlar, **buxgalteriya hisoboti** va boshqalar) faqat o'z guruhlari talabalari tanilinadi: guruh ustuni bo'lsa — guruh bo'yicha, bo'lmasa (buxgalteriya) — talaba uning guruhlarida bormi, HEMIS ID yoki F.I.Sh. bo'yicha. Boshqa guruhlar qatorlari o'tkazib yuboriladi va natijada soni ko'rsatiladi; bir xil F.I.Sh. li talabalar boshqa guruhda bo'lsa ham to'g'ri topiladi. Guruh biriktirilmagan koordinator va super-admin — butun kurs bilan ishlaydi (avvalgidek). Tarjimalar va «Tanlov/2-til: jadval» guruhga bog'lanmagan — ular cheklanmaydi.

## Shablonlar: super-admin o'zgartiradi va qo'shadi

Kurs koordinatorlari `/shablon` (yoki «📑 Shablonlar» tugmasi) orqali oladigan import namunalarini super-admin bot ichidan boshqaradi — «📑 Shablonlar (import namunalari)» yoki `/shablonlar`. Shablonlar barcha kurslar uchun umumiy.

- **Shaklini o'zgartirish** — shablonni tanlab, «🔄 Yangi versiya yuklash». Bot faylni import bilan bir xil tekshiradi: tanilgan ustunlarni ko'rsatadi, **tanimagan ustun uchun qaysi ma'lumot ekanini so'raydi** (majburiylari ⭐ bilan yuqorida; «№» kabi tartib raqamlari so'ralmaydi; ahamiyatsizlarini «🚫 E'tiborsiz qoldirish»). Tanlangan nomni import ham o'rganadi: masalan, «Talaba ID» o'rniga «HEMIS raqami», «F.I.Sh.» o'rniga «Talabaning to'liq ismi» deb o'zgartirilsa, kurs koordinatorlari yangi shablonni to'ldirib yuklaganda ustunlar to'g'ri o'qiladi. Majburiy ustun (masalan, «Guruh») bo'lmasa, shablon qabul qilinmaydi va sababi aytiladi.
- **Saqlashda** — «✅ Saqlash va koordinatorlarga yuborish»: yangi shakl barcha kurs koordinatorlariga fayl bilan yuboriladi (yoki «Faqat saqlash» — /shablon orqali oladi).
- **Versiyalar** — har bir yuklangan versiya saqlanadi: «📜 Versiyalar» dan istalganini yuklab olish yoki tiklash; «↩️ Asl shablonga qaytarish» — bot bilan kelgan shablon.
- **Yangi shablon** — «➕ Yangi shablon qo'shish»: import turiga bog'langan (masalan, «Baholar — o'qituvchi jurnali», o'z ustun nomlari bilan) yoki **hujjat namunasi** (Word, PDF, Excel — import qilinmaydi, koordinatorlarga shunchaki tarqatiladi: bayonnoma, ariza shakli va h.k.).
- **Nomi va izohi** — izoh kurs koordinatorlariga fayl bilan birga ko'rinadi (masalan, HEMIS'ning qaysi bo'limidan eksport qilish). Keraksiz asl shablonni «🙈 Koordinatorlardan yashirish» mumkin.

Yuklangan shablonlar `data/templates/` da saqlanadi (bot kodi yangilanganda o'chmaydi) va tungi zaxira nusxaga kiradi; o'rgatilgan ustun nomlari `central.db` da — bot qayta ishga tushganda ham ishlaydi.

## Zaxira nusxa

Har kuni `BACKUP_TIME` da (standart — 03:00) barcha kurs bazalari va `central.db` bitta arxivga yig'iladi va super-adminga yuboriladi; «💾 Zaxira nusxa» tugmasi yoki `/zaxira` — istalgan paytda.
- SQLite'ning o'z zaxira usuli: bot ishlab turgan paytda ham buzilmagan nusxa; har bir baza yaxlitlikka tekshiriladi (`PRAGMA integrity_check`), muammo bo'lsa — xabarda ❌ va super-adminga ogohlantirish.
- `BACKUP_PASSWORD` berilsa — arxiv **AES-256** bilan shifrlanadi (tavsiya etiladi: arxivda talabalarning shaxsiy ma'lumotlari va qarzdorlik bor, u Telegram orqali yuboriladi). 7-Zip yoki WinRAR bilan shu parol orqali ochiladi.
- Serverda `backups/` papkasida oxirgi `BACKUP_KEEP_DAYS` (standart — 14) kunlik arxivlar saqlanadi. Telegram botlar 50 MB dan katta fayl yubora olmaydi — bunday holda super-adminga hisobot va arxivning serverdagi manzili boradi.
- Ilova va kompyuter versiyasidan yuborilgan rasmiy hujjatlar (`data/<kurs>/documents/`) ham arxivga kiradi.
- Xabarda har bir kurs bo'yicha qisqa hisobot: talabalar, ota-onalar, oxirgi import vaqti, so'nggi 24 soatdagi tizim xatolari soni — kunlik «sog'liq tekshiruvi».

**Tiklash:** botni to'xtating → arxivni oching → kerakli `<kurs>/bot.db` faylini `data/<kurs>/` papkasiga (umumiy ro'yxat kerak bo'lsa — `central.db` ni `data/` ga) qo'ying → botni ishga tushiring. Har bir kurs mustaqil — bitta kursni tiklash boshqalariga ta'sir qilmaydi.

## Loglar va xatolar

- `logs/bot.log` — barcha yozuvlar, `logs/errors.log` — faqat ogohlantirish va xatolar; har ikkisi aylanma (5 MB × 10 fayl — disk to'lib qolmaydi). Har bir yozuvda kurs va foydalanuvchi: `[3-kurs u=8634767200]` — qaysi kursda nima bo'lganini topish oson.
- **Tizim xatosi** (kutilmagan nosozlik) — super-adminga **darhol** xabar: kurs, foydalanuvchi, joy va xato matni. Bir xil xato haqida 10 daqiqada bir martadan ko'p xabar yuborilmaydi (soatiga ko'pi bilan 20 ta) — bitta nosozlik yuzlab xabarga aylanmaydi. Foydalanuvchiga esa xushmuomala javob: «Kechirasiz, texnik xatolik yuz berdi…» (ota-onaning tilida).
- **Fayl formati xatosi** (Excel noto'g'ri tuzilgan, kerakli ustun yo'q) — bu nosozlik emas: kurs koordinatoriga import natijasida aniq aytiladi, `errors.log` ga fayl nomi bilan yoziladi, super-admin bezovta qilinmaydi.
- «🧾 Xatolar jurnali» yoki `/xatolar` — oxirgi yozuvlar va to'liq `errors.log` fayli.

## Bir nechta kurs koordinatori: har biriga alohida baza

Bitta botga bir nechta kurs koordinatori ulanadi (Telegram user ID si orqali) va **har bir kursning ma'lumotlari alohida papkada, alohida bazada** saqlanadi:

```
data/
  3-kurs/bot.db        ← 3-kurs koordinatori(lar)ining talabalari, davomat, baholar, qarzdorlik, hujjatlar, savollar
  2-kurs/bot.db        ← 2-kurs
  central.db           ← faqat ro'yxat: foydalanuvchi tili, Telegram guruh qaysi kursga biriktirilgani
```

Sozlash — `.env` faylida: `KURSLAR=3-kurs:111111111;2-kurs:222222222,333333333` (bitta kursni bir necha koordinator birga yuritishi mumkin). `KURSLAR` ga yozilmagan `ADMIN_IDS` koordinatorlarining har biri avtomatik o'z kursini oladi (`data/koordinator_<ID>/`), shuning uchun faqat ID larni yozish ham yetarli. Yangi koordinator qo'shish: `.env` ga ID sini yozib, botni qayta ishga tushirish — uning papkasi va bazasi o'zi yaratiladi.

Bot har bir so'rovni tegishli kurs bazasiga yo'naltiradi:
- **kurs koordinatori** — faqat o'z kursi: import, statistika, panel, qarzdorlar, e'lonlar, hujjatlar, savollar va bog'lash so'rovlari; boshqa kurs talabalarini ko'rmaydi va topa olmaydi;
- **ota-ona** — telefon raqami barcha kurslardan qidiriladi; farzandi qaysi kursda bo'lsa, o'sha kurs bazasida ro'yxatga olinadi. Ikki farzandi ikki kursda o'qisa — ikkalasini ham ko'radi, har bir farzand o'z kursi bazasidan ochiladi. Savol, bog'lash so'rovi va xabarlar faqat farzand kursining koordinatorlariga boradi;
- **farzandi hali topilmagan ota-ona** hech qaysi kurs bazasiga yozilmaydi (umumiy «kutilmoqda» ro'yxatida turadi): qo'lda bog'lash so'rovini yuborsa — so'rov faqat topilgan farzandning kursiga boradi; kurs koordinatori uning raqami bor talabalar faylini yuklasa — avtomatik bog'lanadi;
- **talaba** o'z raqami bilan kirmoqchi bo'lsa — barcha kurslar bo'yicha tekshiriladi, ogohlantirish o'sha talaba kursining koordinatoriga boradi, blok esa barcha kurslarda amal qiladi;
- **Telegram guruh** botni qo'shgan yoki `/guruh` buyrug'ini bergan koordinatorning kursiga biriktiriladi;
- kunlik xulosa va to'lov eslatmalari har bir kurs uchun alohida yuboriladi.

`/admin` va `/stat` da koordinator qaysi kurs bazasida ishlayotgani ko'rsatiladi. Keyinroq `KURSLAR` qo'shilsa yoki kurs nomi o'zgarsa (masalan, `data/koordinator_8634767200/` → `KURSLAR=3-kurs:8634767200`), bot birinchi ishga tushganda koordinatorning eski papkasini yangi nomga o'zi ko'chiradi — ma'lumotlar saqlanadi. Kurs nomi faqat papka nomi va koordinatorning `/admin` sahifasida ko'rinadi; ota-onaga talabaning o'z o'quv kursi («3-kurs», talabalar faylidagi «Talaba kursi» ustunidan) ko'rsatiladi. Oldingi versiyadagi yagona baza (`data/bot.db`) bot birinchi ishga tushganda birinchi kurs papkasiga ko'chiriladi (til sozlamalari va Telegram guruhlar ham saqlanadi). Namunaviy ma'lumotlarni ma'lum kursga yozish: `python demo_seed.py 998901234567 --kurs 3-kurs`.

Cheklov: kurs koordinatori shaxsiy chatda doim o'z kursi bilan ishlaydi — agar u boshqa kursda o'qiydigan farzandning ota-onasi ham bo'lsa, bu farzandni bot orqali kuzatish uchun boshqa Telegram akkaunt kerak.

## Tillar: o'zbek, rus, ingliz

Ota-ona botga birinchi kirganda tilni tanlaydi (🇺🇿 O'zbekcha · 🇷🇺 Русский · 🇬🇧 English), keyin istalgan paytda «🌐 Til» tugmasi yoki `/til` buyrug'i bilan o'zgartiradi. Tanlangan tilda butun ota-ona interfeysi ishlaydi: menyu va tugmalar, ro'yxatdan o'tish, farzand sahifasi va barcha bo'limlar, sozlamalar hamda **avtomatik xabarlar** — dars qoldirish, chegaralar, akademik qarz, to'lov eslatmalari va kunlik xulosa har bir ota-onaga o'z tilida boradi. Sanalar, oylar, hafta kunlari, pul birligi (so'm / сум / UZS) va GPA ko'rinishi ham tilga moslanadi. Fan, guruh, fakultet nomlari va kurs koordinatori yozgan e'lon matni asl holida qoladi. Kurs koordinatori buyruqlari o'zbek tilida.

Tarjimalar `i18n_data.py` da: kalit — koddagi o'zbekcha matn. Yangi matn qo'shilganda uni kodda `tr("...")` bilan o'rab, shu faylga rus va ingliz tarjimasini qo'shish kerak (tarjimasi yo'q matn o'zbekcha chiqadi).

### Ma'lumotlar ham ota-ona tilida

Rus yoki ingliz tilini tanlagan ota-onaga faqat bot matnlari emas, **ma'lumotlarning o'zi** ham shu tilda ko'rsatiladi (Excel fayllar o'zbekcha yuklanadi — o'girish ko'rsatish paytida bo'ladi, bazadagi asl nomlar o'zgarmaydi):

- **Ismlar** (talaba, kurs koordinatori, o'qituvchi) — rus tilida kirill alifbosida, qoidalar bo'yicha: «Karimov Jasur Anvarovich» → «Каримов Жасур Анварович», «G‘anijonov Shaxriyor o‘g‘li» → «Ганижонов Шахриёр угли», «Egamberdiyev» → «Эгамбердиев». Rasmiy ruscha yozuv boshqacha bo'lsa (masalan, Qodirov → «Кадыров»), talabalar faylidagi «F.I.Sh. (kirill)» ustuniga yozing — bot o'shani ko'rsatadi. Ingliz tilida ismlar lotin yozuvida.
- **Fan, fakultet, nazorat turi, xona** — rasmiy tarjimada: «Xalqaro tashkilotlar» → «Международные организации», «Asosiy chet tili III» → «Основной иностранный язык III», «O'rtacha ball» → «Средний балл», universitet nomi → «Университет мировой экономики и дипломатии». Botda keng tarqalgan fanlar, tillar va fakultetlarning ichki lug'ati bor (`terms_data.py`).
- **Lug'atda yo'q nomlar** — kurs koordinatori `/tarjimalar` buyrug'i bilan kursdagi barcha nomlarni Excel jadval qilib oladi (tarjimasi yo'qlari sariq), ruscha va inglizcha nomlarni yozib, /import → «🌐 Tarjimalar» orqali qaytaradi. Tarjimalar barcha kurslar uchun umumiy va ichki lug'atdan ustun turadi. Tarjima kiritilmaguncha nom rus tilida kirill harflarida ko'rsatiladi (lotin harfi ko'rinmaydi); har bir importdan keyin kurs koordinatoriga «tarjimasi yo'q nomlar» ro'yxati chiqadi.
- **E'lonlar va «Foydali ma'lumot»** — kurs koordinatori matnga alohida qatordan `---ru` va `---en` yozib, ruscha va inglizcha qismni qo'shadi; har bir ota-ona o'z tilidagi qismni oladi. Ruscha qism bo'lmasa, o'zbekcha matn kirill harflarida boradi (yuborishdan oldin kurs koordinatori bu haqda ogohlantiriladi).
- **Ota-onaning savoli** kurs koordinatoriga uning tili bilan boradi («🌐 Ota-ona tili: rus»), javobni shu tilda yozish mumkin.

Ruscha matnlar rasmiy uslubda: murojaat «Вы / Ваш» bosh harf bilan. Kurs koordinatori interfeysi doim o'zbek tilida.

## Maxfiylik qanday ta'minlangan

Istalgan odam istalgan talabaning ismini yozib davomatini ko'ra olmasligi uchun ota-ona avval Telegram orqali **o'z telefon raqamini** tasdiqlaydi (bot faqat foydalanuvchining o'z kontaktini qabul qiladi). Raqam talabalar faylidagi ota-ona telefonlari bilan solishtiriladi va mos kelsa farzand avtomatik bog'lanadi. Raqam bazada bo'lmasa, ota-ona farzandning familiya-ismi va tug'ilgan sanasini (yoki HEMIS ID) kiritadi, so'rov kurs koordinatoriga boradi va kurs koordinatori tasdiqlagandan keyingina bog'lanadi. Ism bo'yicha qidiruv faqat shu ota-onaga bog'langan farzandlar ichida ishlaydi.

## Talabalar botga kira olmaydi

Bot faqat ota-onalar uchun. Talaba o'z raqami bilan ro'yxatdan o'tib, «ota-ona» bo'lib olmasligi uchun ikki usul birga ishlaydi.

**Talabalar raqamlari bazasi.** Talabalar faylida «Talaba telefoni» ustuni bo'lsa yoki alohida «📱 Talaba telefonlari» fayli yuklansa (`/shablon` dagi 5-namuna), bot bu raqamlarni eslab qoladi. Kimdir shu raqam bilan ro'yxatdan o'tmoqchi bo'lsa, rad etiladi. Qo'shimchasiz «Telefon» yoki «Telefon raqami» ustuni talabaning o'z raqami deb olinadi, chunki HEMIS ro'yxatlarida odatda shunday. Ota-ona raqamlari faqat aniq nom bilan olinadi: «Ota-ona telefoni», «Otasining telefoni», «Onasining telefoni» va h.k. Import natijasida qaysi ustun qanday tanilgani ko'rsatiladi — uni albatta tekshiring.

**Talabalar Telegram guruhlari.** Botni talabalar guruhiga qo'shing va **administrator** qiling (eng kam huquqlar yetarli). Bot guruhda hech narsa yozmaydi. U a'zolarni uch yo'l bilan aniqlaydi:
- guruhga yozgan yoki qo'shilgan har bir foydalanuvchini eslab qoladi;
- ro'yxatdan o'tayotgan har bir kishining shu guruhlardan birida a'zo ekanini Telegram orqali tekshiradi;
- guruhda keyinroq paydo bo'lgan, oldin ro'yxatdan o'tgan «ota-ona»ni ham aniqlaydi.

Guruhni akademik guruhga bog'lash uchun guruhning o'zida `/guruh IQ-21` deb yozing. Botni faqat `ADMIN_IDS` dagi kurs koordinatori qo'shsa, guruh talabalar guruhi sifatida qabul qilinadi. Begona odam botni boshqa guruhga qo'shsa, bot o'sha zahoti chiqib ketadi.

**Talaba aniqlanganda nima bo'ladi.** Talaba deb aniqlangan foydalanuvchiga «bot faqat ota-onalar uchun» degan javob beriladi. Keyingi har qanday so'rovi to'xtatiladi va unga xabarnomalar yuborilmaydi. Kurs koordinatorlariga esa darhol xabar keladi. Xabarda Telegram nomi, ID, raqam va aniqlash asosi (qaysi talabaning raqami yoki qaysi guruh) ko'rsatiladi. Xabarda ikki tugma bor: «✅ Ota-ona — ruxsat berish» va «🚫 Bloklangan qolsin». Xato aniqlangan holatlar uchun ruxsat tugmasi bor. Masalan, oilada umumiy raqam bo'lishi mumkin: HEMIS'da talaba raqami o'rniga onasining raqami yozilgan bo'lsa. Yoki ota-ona talabalar guruhida turgan bo'lishi mumkin. Ruxsat berilgan foydalanuvchi boshqa tekshirilmaydi. Bir raqam bir vaqtda talabaning o'z raqami va ota-ona raqami sifatida yozilgan bo'lsa, import natijasida ogohlantirish chiqadi.

`/tekshir` buyrug'i barcha ro'yxatdan o'tganlarni qayta tekshiradi. Uni botni guruhlarga qo'shgandan yoki talabalar raqamlarini yuklagandan keyin bir marta bajaring. Talabalar va talaba telefonlari importidan keyin raqamlar bo'yicha tekshiruv avtomatik o'tadi.

**Cheklov.** Bot faqat o'ziga ma'lum raqamlar va guruhlar bo'yicha aniqlay oladi. Talaba bazada yo'q boshqa raqamdagi akkaunt bilan kirsa va talabalar guruhlarida bo'lmasa, uni avtomatik ajratib bo'lmaydi. Bunday holatda farzand faqat qo'lda bog'lash so'rovi orqali ulanadi, uni esa kurs koordinatori tasdiqlaydi. So'rovni tasdiqlashdan oldin ota-ona bilan telefon orqali gaplashib olish tavsiya etiladi.

Ishga tushirishdan oldin «Shaxsga doir ma'lumotlar to'g'risida»gi Qonun talablari (jumladan, ma'lumotlarni saqlash joyi va ota-onalar roziligi) bo'yicha universitet ma'muriyati va IT bo'limi bilan kelishib olish tavsiya etiladi.

## Telegram Web App (ilova)

Bot bilan birga ilova ham ishlaydi: ota-ona uni bot chatidagi «📱 Ilova» tugmasi, bosh menyudagi «📱 Ilovani ochish» tugmasi yoki har bir bildirishnoma ostidagi «📱 Ilovada ochish» tugmasi orqali ochadi. Ilova Telegram ichida ochiladi, alohida o'rnatish yoki parol talab qilinmaydi. Bot va ilova bitta jarayonda, bitta ma'lumotlar bazasi bilan ishlaydi: ilovada ko'rilgan narsa botdagi bilan bir xil.

**Ota-ona ilovada:** bosh ekranda — talaba guvohnomasi ko'rinishidagi karta va bir jumlalik xulosa («Hammasi joyida» yoki «2 ta masala e'tibor talab qiladi»), davomat halqasi, GPA, akademik va moliyaviy qarz, bugungi darslar, dinamika va kurs koordinatori; davomat — sababsiz va sababli darslar, dars qoldirish chegaralari zinapoyasi (keyingi chegara ajratib ko'rsatiladi), haftalar bo'yicha grafik, qoldirilgan darslar va fanlar kesimi; hafta kunlari bo'yicha jadval; baholar va baholash shkalasi; dinamika grafigi; to'lovlar; hujjatlar (PDF ilovaning o'zida ochiladi, xohlasa — chatga ham); kurs koordinatori bilan yozishma; e'lonlar; bildirishnomalar sozlamasi va til. Bir nechta farzand bo'lsa — yuqoridagi tugmalar bilan almashtiriladi. Ilova o'zbek, rus va ingliz tilida; kunduzgi, tungi yoki avtomatik (Telegram mavzusiga mos) ko'rinish.

**Bildirishnomalar o'z vaqtida.** Telefonga xabarni bot yuboradi (Telegram ilovaning o'zi telefonga xabar chiqara olmaydi). Xabar qisqa va aniq: «📋 Karimov Jasur: davomatda o'zgarish bo'ldi», «📝 …baholarda yangilanish bo'ldi», «⚠️ …dars qoldirish bo'yicha ogohlantirish», «💰 …to'lov muddati yaqinlashmoqda», «📄 …yangi hujjat — «Hayfsan»», «💬 Kurs koordinatoridan javob keldi» — ota-onaning tilida; ostidagi «📱 Ilovada ochish» tugmasi aynan shu farzandning tegishli bo'limini ochadi, to'liq ma'lumot esa ilovada. Ilova ochiq bo'lsa, bildirishnoma **darhol** ko'rinadi: yuqoridan banner chiqadi, nishonlar yangilanadi, ochiq suhbat o'zi yangilanadi (real vaqt ulanishi — `/api/events`). Barcha xabarlar ilovadagi bildirishnomalar markazida ham saqlanadi.

**Ota-ona ↔ kurs koordinatori yozishmasi.** Ota-ona ilovada yoki botda yozadi — bitta suhbat; kurs koordinatori ilovadagi yoki kompyuter versiyasidagi «Xabarlar» bo'limida javob beradi (ilova rejimida botga «Yangi savol» xabari va «Ilovada javob berish» tugmasi keladi); ota-onaga «Kurs koordinatoridan javob keldi» xabari boradi, javobning o'zi ilovadagi suhbatda — ilova ochiq bo'lsa, darhol. Ota-ona rus yoki ingliz tilida bo'lsa, koordinatorga javobni qaysi tilda yozish kerakligi ko'rsatiladi.

**Kurs koordinatori ilovada:** kurs holati paneli (talabalar, davomat muammosi, akademik qarz, 3+ muammoli, kontrakt va trimestr qarzi — har biri ro'yxatga olib boradi), talabalar qidiruvi va filtrlari, talaba kartasi, xabarlar qutisi, bog'lash so'rovlarini tasdiqlash yoki rad etish, e'lon yuborish (`---ru` / `---en` qismlari bilan), rasmiy hujjat (PDF) yuborish, bir nechta Excel faylni bir yo'la yuklash (turini bot o'zi aniqlaydi) va Excel/PDF hisobot (chatga keladi). Super-admin — kurs tanlagichi orqali istalgan kursga kiradi, «Talabalar» da «Barcha kurslar» ni tanlab barcha kurs koordinatorlarining talabalarini muammolari bilan bitta ro'yxatda ko'radi.

**Xavfsizlik.** Ilovaning har bir so'rovi Telegram imzosi (initData, HMAC-SHA256, `BOT_TOKEN` asosida) bilan tekshiriladi: imzosiz, soxtalashtirilgan yoki muddati o'tgan (`WEBAPP_AUTH_TTL`) so'rov rad etiladi. Ota-ona faqat o'ziga bog'langan farzandlarning ma'lumotini oladi — boshqa talabaning manzilini qo'lda yozsa ham server ruxsat bermaydi. Kurs koordinatori faqat o'z kursini ko'radi. Bloklangan foydalanuvchi (talaba) ilovani ham ocha olmaydi. Veb-server faqat ichki manzilda (`127.0.0.1`) tinglaydi, tashqariga HTTPS proksi orqali chiqadi; sahifaga qat'iy xavfsizlik sarlavhalari (CSP) qo'yilgan: ilova fayllari va shriftlar serverning o'zidan beriladi, tashqaridan faqat Telegram'ning rasmiy `telegram-web-app.js` skripti yuklanadi, ilova esa faqat Telegram ichida ochiladi.

**Ilova rejimi — bot faqat ilovaga o'tish vositasi.** `WEBAPP_URL` sozlangan bo'lsa, botda menyu tugmalari bo'lmaydi: `/start` — qisqa salom va «📱 Ilovani ochish» (kurs koordinatori va super-admin — «💻 Kompyuter versiyasi» ham); ota-ona botga matn yozsa yoki eski xabardagi tugmani bossa — ilovaga yo'naltiriladi; buyruqlar menyusida faqat `/start` (xodimlarda `/kompyuter` ham). Ro'yxatdan o'tish ilovada: ilova telefon raqamini Telegram orqali so'raydi, bot uni tasdiqlaydi. Barcha amallar — ilovada va kompyuter versiyasida; kurs koordinatorining eski buyruqlari (`/panel`, fayl yuborish va h.k.) zaxira sifatida ishlayveradi. Botning to'liq menyulari kerak bo'lsa: `.env` da `BOT_FULL_MENU=1`.

**Rasmiy hujjatlar ilovada.** Kurs koordinatori va super-admin buyruq yoki xatni (PDF) ilovadan yoki kompyuter versiyasidan yuboradi: hujjatdagi talabalar avtomatik topiladi (ismdosh bo'lsa — hujjatda ID si yoki guruhi borligi tekshiriladi, dalilsiz ismdosh avtomatik tanlanmaydi), turi fayl nomi yoki hujjat matnidan aniqlanadi (tushuntirish xati / dekan ogohlantirishi / hayfsan), har bir talaba uchun boshqa talabalar yopilgan nusxa tayyorlanadi va yuborishdan oldin ko'rsatiladi. Ota-onaga qisqa xabar boradi, hujjat **ilovaning o'zida** ochiladi (sahifalar rasm ko'rinishida — Android'da ham ishlaydi); xohlasa — «Chatga yuborish». Ilovadan yuborilgan hujjatlar serverda `data/<kurs>/documents/` papkasida saqlanadi va tungi zaxira nusxaga kiradi.

**Juftlik vaqtlari.** Super-admin kompyuter versiyasidagi «Tizim» sahifasida har bir juftlikning boshlanish va tugash vaqtini kiritadi — dars jadvalida (ota-ona ilovasida ham) ko'rinadi. HEMIS jadvalida vaqt bo'lsa, u ustun turadi; `.env` dagi `PAIR_TIMES` — zaxira.

**Mavzu.** Ilovada (yuqori paneldagi tugma yoki «Sozlamalar») va kompyuter versiyasida (yon menyu pastida): avtomatik (Telegram / tizim mavzusi), kunduzgi yoki tungi.

**Ishga tushirish.** `.env` fayliga `WEBAPP_URL` (ochiq HTTPS manzil) yozing va botni qayta ishga tushiring — qolganini bot o'zi qiladi (menyu tugmasi, xabarlar ostidagi tugmalar). HTTPS manzil qanday olinishi — «Serverga joylashtirish» bo'limida. `WEBAPP_URL` bo'sh bo'lsa, ilova o'chiq va bot avvalgidek ishlaydi.

Ixtiyoriy: @BotFather → `/newapp` bilan ilovani ro'yxatdan o'tkazsangiz, `https://t.me/<bot_nomi>/<ilova_nomi>` ko'rinishidagi to'g'ridan-to'g'ri havola paydo bo'ladi — uni ota-onalar chatlariga yuborish mumkin.

## Kompyuter versiyasi (boshqaruv paneli)

Kurs koordinatori va super-admin uchun kompyuter brauzerida ishlaydigan to'liq boshqaruv paneli. U bot va ilova bilan bitta serverda, bitta ma'lumotlar bazasi bilan ishlaydi — panelda qilingan har bir amal (javob, e'lon, so'rovni tasdiqlash, fayl yuklash) botdagidek natija beradi va ota-onalarga bot orqali yetkaziladi.

**Kirish — parolsiz, bot orqali.** Botda «💻 Kompyuter versiyasi» tugmasini bosing yoki `/kompyuter` buyrug'ini yuboring (Telegram ichidagi ilovada — kurs holati sahifasi pastidagi «Kompyuter versiyasi» kartasi). Bot **10 daqiqa** amal qiladigan, **bir marta** ishlatiladigan havola yuboradi; uni kompyuterda (Telegram Desktop yoki web.telegram.org) bosing va ochilgan sahifada «Kirish» ni bosing. Seans **12 soat** davom etadi; umumiy kompyuterda ishlagandan so'ng chap pastdagi «Chiqish» tugmasini bosing.

**Kurs koordinatori uchun:**
- **Kurs holati** — asosiy ko'rsatkichlar (davomat muammosi, akademik qarz, 3+ masalali, kontrakt va trimestr qarzi — har biri ro'yxatga olib boradi), e'tibor talab qiladigan talabalar, yangi xabarlar, bog'lanish so'rovlari va bir tugmali hisobot;
- **Talabalar** — butun kurs bitta jadvalda: davomat foizi va sababsiz darslar, chora, akademik qarz, GPA, kontrakt, trimestr, masalalar soni; istalgan ustun bo'yicha saralash, filtrlar (muammoli, davomat, akademik, kontrakt, trimestr), guruh va qidiruv (familiya, ism, guruh yoki HEMIS ID; «/» tugmasi — qidiruvga o'tish). Qatorni bossangiz — yon panelda talaba kartasi: masalalar, chegaralar zinapoyasi, akademik qarzlar, to'lovlar, dinamika va ota-onalar (har biriga «Yozish»);
- **Xabarlar** — suhbatlar ro'yxati va suhbat yonma-yon; ota-ona rus yoki ingliz tilida bo'lsa, javobni qaysi tilda yozish ko'rsatiladi; Ctrl+Enter — yuborish;
- **So'rovlar** — telefon raqami bazada topilmagan ota-onalarning farzandni bog'lash so'rovlari: ota-ona yozgan ma'lumot so'ralgan talaba bilan yonma-yon; tasdiqlash yoki rad etish (ota-onaga o'z tilida xabar boradi);
- **Hujjat yuborish** — rasmiy hujjat (PDF): talabalar avtomatik topiladi, har bir nusxa ko'rsatiladi, ota-onaga qisqa xabar va hujjat ilovada;
- **E'lon yuborish** — butun kursga yoki tanlangan guruhlarga; o'ng tomonda ota-ona har uch tilda aynan nimani ko'rishi ko'rsatiladi (`---ru` / `---en` qismi yozilmagan bo'lsa — bu haqda ogohlantiriladi);
- **Ma'lumot va hisobot** — Excel fayllarni sichqoncha bilan tashlab yuklash (bir nechtasini birga, turini bot o'zi aniqlaydi, «jim» rejim bilan), hisobotni Excel yoki PDF qilib kompyuterga yuklab olish yoki Telegram chatiga yuborish.

**Super-admin uchun** (yuqoridagilarga qo'shimcha): «Talabalar» sahifasida **barcha kurslar talabalari bitta jadvalda** (kurs ustuni bilan; har bir kursga alohida kirish ham qoladi); **Barcha kurslar** — universitet bo'yicha jami ko'rsatkichlar va kurslar kesimidagi jadval («Kursga kirish» — o'sha kursning paneliga o'tish; yon menyudagi «Joriy kurs» ro'yxati ham shu vazifani bajaradi); **Kurslar va koordinatorlar** — yangi kurs yaratish, nomini o'zgartirish, kurs koordinatorini Telegram ID bo'yicha tayinlash (u bot orqali darhol xabardor qilinadi) va olib tashlash — botni qayta ishga tushirmasdan; **Tizim** — juftlik vaqtlari, oxirgi zaxira nusxa, «Hozir zaxira nusxa olish» (shifrlangan arxiv Telegram chatingizga keladi) va xatolar jurnali. Import shablonlarini o'zgartirish hozircha botda («📑 Shablonlar»).

**Xavfsizlik.** Seans imzolangan cookie'da saqlanadi (HttpOnly — sahifadagi skriptlar uni o'qiy olmaydi; HTTPS'da Secure; SameSite=Lax); har bir API so'rovi maxsus sarlavha bilan keladi — begona sayt sizning brauzeringiz nomidan so'rov yubora olmaydi. Havola faqat kurs koordinatori va super-admin uchun beriladi; huquq har bir so'rovda qayta tekshiriladi — super-admin koordinatorni olib tashlasa, uning ochiq seansi darhol kuchini yo'qotadi. Kurs koordinatori faqat o'z kursini, super-admin barcha kurslarni ko'radi.

**Ekran.** 1366 va undan keng ekranda to'liq ko'rinish; 1200 pikseldan tor ekranda yon menyu ixcham (belgilar) ko'rinishga o'tadi. Mavzu — yon menyu pastidagi tugma bilan: avtomatik (tizim mavzusi), kunduzgi yoki tungi. Yangi xabar yoki so'rov kelganda panel o'ng pastida darhol bildirishnoma chiqadi. Kompyuter versiyasi ham `WEBAPP_URL` (HTTPS manzil) sozlanganda ishlaydi — qo'shimcha sozlama talab qilinmaydi.

## O'rnatish

1. Python 3.10 yoki undan yangi versiyasini o'rnating (tavsiya: 3.12).
2. Telegramda **@BotFather** → `/newbot` → bot nomi va username bering → token oling.
3. O'z Telegram ID raqamingizni **@userinfobot** orqali bilib oling.
4. Loyiha papkasida:

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# Linux/macOS:  source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

5. `.env` faylini oching va kamida `BOT_TOKEN`, `ADMIN_IDS`, `SEMESTER_START` ni to'ldiring. Bir nechta kurs koordinatori bo'lsa ID lar vergul bilan yoziladi.
6. Ishga tushirish: `python bot.py`

Bot faqat dastur ishlab turganda javob beradi. Doimiy ishlashi uchun uni server (VPS) ga joylashtiring (pastda).

## Sinab ko'rish (namunaviy ma'lumotlar)

```bash
python demo_seed.py 998901234567
```

Bu buyruq to'qima «DEMO-101» guruhini (3 talaba, jadval, 3 haftalik davomat, baholar, e'lon) yaratadi va ko'rsatilgan raqamni 2 ta talabaning ota-onasi sifatida yozadi. Ikkinchi raqamni ham bersangiz (`python demo_seed.py 998901234567 998935556677`), u uchinchi talabaning o'z raqami sifatida yoziladi. Shu raqamli boshqa Telegram akkaunt bilan kirib, talaba rad etilishini va kurs koordinatoriga xabar kelishini sinab ko'rasiz. So'ng botni ishga tushirib, o'sha raqamli Telegram akkaunt bilan `/start` bosing. **Haqiqiy ishga tushirishdan oldin `data/bot.db` faylini o'chiring.**

## Ma'lumotlarni yuklash (kurs koordinatori)

**Bir nechta faylni bir yo'la yuklash.** `/import` da turini bir marta tanlab, bir nechta faylni yuborish mumkin — bittalab yoki hammasini birga (Telegram'da bir nechta faylni belgilab jo'natish). Bot fayllarni navbat bilan yuklaydi va har biri bo'yicha natija beradi. Tugatgach — `/tayyor`: nechta fayl yuklangani, qaysi turlar va o'tkazib yuborilganlar ko'rsatiladi (30 daqiqa fayl kelmasa, sessiya o'zi yopiladi).

- Tanlangan turdan **boshqa turdagi fayl** kelsa, o'sha fayl bo'yicha **darhol** xabar beriladi: «⚠️ Diqqat! 2-fayl «davomat.xlsx» — ushbu faylda «Davomat» fayliga xos ustunlar aniqlandi» — tugmalar: «⏭ O'tkazib yuborish», «✅ Baribir …», «🔄 … sifatida yuklash». Qolgan fayllar kutib turmaydi, yuklanishda davom etadi.
- **«🤖 Aralash fayllar»** — har xil turdagi fayllarni (baholar, davomat, qarzdorlik…) birga yuborish: har birining turini bot o'zi aniqlaydi, aniqlay olmasa — o'sha fayl uchun turini so'raydi.
- Bir nechta fayl birga yuborilganda birinchisining izohidagi `jim` hammasiga tatbiq etiladi.
- Import ochiq paytda PDF yuborilsa, sessiya yopiladi va hujjat odatdagidek qabul qilinadi.


Botga `/shablon` yozsangiz, o'n bitta Excel namunasi keladi (har birining ikkinchi varag'ida ustunlar bo'yicha ko'rsatma bor). `/import` → turini tanlang → .xlsx faylni hujjat sifatida yuboring. Tavsiya etilgan tartib:

Talabalar, davomat va baholar uchun **HEMIS eksport fayllarini o'zgartirmasdan yuborish mumkin** — bot ularning tuzilishini o'zi taniydi:

1. **Talabalar** — HEMIS «Talabalar kontingenti» fayli (Talaba ID, Full Name of student, Tug'ilgan sana, Telefon, Talaba kursi, Guruh, Fakultet; pasport, manzil kabi ustunlar e'tiborsiz qoldiriladi, ikki qatorli sarlavha ham tushuniladi). HEMIS faylida ota-ona telefoni yo'q — uni faylning oxiriga «Ota-ona telefoni» ustuni qilib qo'shing (kerak bo'lsa «Kurs koordinatori», «Kurs koordinatori telefoni» ham). Katta harflardagi ismlar chiroyli yozuvga o'tkaziladi («G‘ANIJONOV … O‘G‘LI» → «G‘anijonov … o‘g‘li»). HEMIS eksportida tug'ilgan sana va telefonlar `***` bilan yashirilgan bo'lsa, ular saqlanmaydi: talabaning raqami bo'yicha aniqlash uchun «Talaba telefonlari» faylini alohida yuklang, qo'lda bog'lashda esa ota-ona HEMIS ID ni kiritadi.
2. **Dars jadvali (asosiy fanlar)** — guruh, hafta kuni, juftlik, vaqt, fan, mashg'ulot turi, o'qituvchi, xona, hafta (har/toq/juft), seminar raqami. Mashg'ulot turi ota-onaga **«Leksiya»** yoki **«Seminar»** deb ko'rsatiladi: «ma'ruza», «лекция», «katta guruh» — leksiya; «amaliy», «laboratoriya», «kichik guruh» — seminar. «Kichik guruh» ustuni nomi eski fayllarda ham qabul qilinadi. Bu yerga faqat guruhning **asosiy fanlari** kiritiladi — ular guruhdagi barcha talabalarga ko'rsatiladi. Bir katakda bir nechta guruh vergul bilan yozilishi mumkin. Yuklangan guruhlarning eski jadvali almashtiriladi.
3. **Davomat** — bot formatni o'zi aniqlaydi:
   - HEMIS «O'quvchilarni darslarga qatnashish statistikasi» (FIO, Hemis ID, Guruh nomi, Qatnashganlar soni, Qatnashmaganlar soni, Sabablilar soni) — har bir talaba uchun jami ko'rsatkichlar. Har yuklash sana bilan saqlanadi: ota-ona jami soatlar, oldingi yuklashdan beri o'zgarish va chegaralarni ko'radi. Holat sanasi fayl izohidagi sanadan (masalan `24.09.2026`), bo'lmasa fayl nomidagi sanadan, bo'lmasa yuklash kunidan olinadi;
   - kunlik davomat (`6_davomat_kunlik` shabloni): talaba, sana, juftlik, fan, holat (keldi / kelmadi / sababli / kechikdi; «НБ», «+», «-» ham tushuniladi) — bunda ota-ona kun va fanlar bo'yicha ham ko'radi.
4. **Baholar** — HEMIS guruh bo'yicha «O'rtacha ball» jadvali: har bir fan alohida ustunda, jadval ustida «Guruh» va «Semestr» qatorlari; katakdagi «78 [1]» dan ball (78, 100 ballik) olinadi, talabalar guruh ichida F.I.Sh. bo'yicha topiladi. Oldingi ro'yxat formati (Talaba ID, Fan, Nazorat turi, Ball) ham ishlaydi.
5. **Ikkinchi til va tanlov fanlari — individual jadval.** Bu fanlar akademik guruhga bog'lanmagan (bir oqimda turli guruhlar talabalari o'qiydi), shuning uchun ikki fayl bilan kiritiladi:
   - **«🗓 Tanlov/2-til: jadval»** (`8_tanlov_2til_jadvali`) — fan, oqim, hafta kuni, juftlik, vaqt, o'qituvchi, xona. Guruh ustuni odatda bo'sh; ko'rsatilsa, dars faqat shu akademik guruh talabalari uchun. Fayldagi fanlarning eski darslari almashtiriladi;
   - **«🎯 Tanlov/2-til: kim o'qiydi»** (`7_tanlov_2til_biriktirish`) — talaba, fan, oqim (har bir fan — alohida qator). «Tanlov fanlari» / «Ikkinchi til» ustunlari (vergul bilan) yoki guruhning HEMIS «O'rtacha ball» jadvali ham qabul qilinadi (bahosi bor fan — talaba o'qiydigan fan).

   Har bir talabaning **shaxsiy jadvali** = guruhining asosiy fanlari + u biriktirilgan tanlov fani va ikkinchi til darslari (o'z oqimi bo'yicha). Tanlov va til darslarini **faqat shu talabaning ota-onasi** ko'radi, jadvalda ular 🎯 belgisi va oqim raqami bilan ajratilgan. Fan nomlari biroz farq qilsa ham topiladi («Fransuz tili» = «Fransuz tili I», «(c)» belgisi e'tiborsiz). Talabaga hali hech narsa biriktirilmagan bo'lsa, unga faqat asosiy fanlar izoh bilan ko'rsatiladi. `/toldir` ham shaxsiy jadval bo'yicha ishlaydi. Import natijasida jadvalda darsi yo'q fanlar va hech kim biriktirilmagan fanlar ko'rsatiladi. `/jadval familiya` — kurs koordinatori talabaning shaxsiy jadvalini tekshiradi.
6. **Talaba telefonlari** (ixtiyoriy, istalgan paytda) — talaba (ID yoki F.I.Sh.+guruh) va uning o'z raqami. Talabalar faylida bu ustun bo'lsa, alohida yuklash shart emas.
7. **Moliyaviy qarzdorlik** — buxgalteriya hisobotlari, ikki alohida import: «💰 Kontrakt qarzdorligi» (`9_kontrakt_qarzdorlar`) va «🗓 Trimestr qarzdorligi» (`10_trimestr_qarzdorligi`). Har biri ikkala formatni taniydi: «Kontrakt qarzdorlar» ro'yxati (kontrakt miqdori, to'langan, Jami, Qoldiq — manfiy son qarz) yoki aylanma vedomost (davr boshi / aylanma / davr oxiri, DT–KT). Batafsil — «To'lov shakli va qarzdorlik» bo'limida.
8. **Akademik qarzdorlar (HEMIS ro'yxati)** — HEMIS'dagi «Akadem qarzdorlar» hisoboti (`12_akademik_qarzdorlar`), o'zgartirmasdan: T/R, To'liq ismi, Semestr, Fanlar, Kredit, Kurs, Guruh, Mutaxassislik, O'quv yili. Har bir qator — talabaning **bitta** qarzdor fani: talaba ro'yxatda necha marta (necha xil fan bilan) kelsa, shuncha qarzdor fan hisoblanadi; bir fan bir semestrda ikki marta yozilgan bo'lsa — bir marta. Faylda HEMIS ID bo'lmagani uchun talaba F.I.Sh. bo'yicha topiladi (katta harflar, «O'G'LI»/«QIZI» va «XXX» kabi yashirilgan qismlar hisobga olinadi); ro'yxat o'tgan yilniki bo'lib, talaba keyin boshqa guruhga o'tgan bo'lsa ham topiladi. Bazada topilmagan talabalar (joriy kontingentda yo'q — chetlashtirilgan, akademik ta'tilda yoki boshqa fakultetga o'tgan) import hisobotida ismi bilan ko'rsatiladi. Yangi fayl faqat undagi guruhlarning ro'yxatini almashtiradi: ro'yxatdan chiqqan fan — «yopilgan», yangisi — «yangi qarz»; ikkalasi haqida ham ota-onaga xabar boradi. Ota-ona ilovada «Akademik qarz: N ta fan» kartasini ko'radi, bossa — fanlar nomi, semestri va krediti bilan ro'yxat; kurs koordinatori — talabalar jadvalida («Akademik qarz» filtri) va talaba kartasida. Baholardan aniqlangan qarz (0–59 ball) bilan bir fan ikki manbada bo'lsa — bir marta ko'rsatiladi.

Ustun nomlari o'zbek (lotin/kirill) yoki rus tilida bo'lishi mumkin, sarlavha birinchi 15 qatordan avtomatik topiladi, «NAMUNA» deb boshlangan qatorlar o'tkazib yuboriladi. Xatoli qatorlar import natijasida raqami bilan ko'rsatiladi.

**Jim rejim.** Fayl izohiga (caption) `jim` deb yozsangiz, ota-onalarga xabar yuborilmaydi. Semestr boshidagi katta hajmdagi birinchi yuklashni shu tarzda qilish tavsiya etiladi. Bundan tashqari, `NOTIFY_MAX_AGE_DAYS` (standart 3 kun) dan eski qoldirishlar uchun «darhol xabar» umuman yuborilmaydi.

**Faqat qoldirilgan darslar bo'lsa.** Agar eksport faylida faqat qoldirilgan darslar bo'lsa, qolgan darslar botda ⚪ «ma'lumot hali kiritilmagan» ko'rinadi. Shunday holatda davomatni yuklagandan keyin:

```
/toldir 15.09.2026 21.09.2026
```

buyrug'i shu oraliqda jadvalda bor, lekin davomat yozuvi yo'q darslarni «qatnashdi» deb belgilaydi. Oldin kiritilgan qoldirishlar o'zgarmaydi. Buni faqat o'sha kunlar bo'yicha qoldirishlar to'liq yuklangandan keyin bajaring.

## Farzand sahifasi: «👨‍🎓 Farzandim» — umumiy holat

Ota-ona «👨‍🎓 Farzandim» ni bosganda (yoki farzandining ismini yozganda) birinchi navbatda **umumiy holat** ekrani ochiladi — farzandning barcha ko'rsatkichlari bir qarashda:

```
👨‍🎓 Farzandim: Aliyev Vali
🧾 To'lov shakli: To'lov-shartnoma
📋 Umumiy holat
🟢 Davomat: 94% (sababsiz qoldirilgan: 6 soat)
📚 Akademik qarzdorlik: 1 ta fan — Xalqaro huquq
💰 Kontrakt qarzdorligi: 2 450 000 so'm
💳 Trimestr qarzdorligi: mavjud emas ✅
🎓 O'zlashtirish ko'rsatkichi (GPA): 3,67 / 5
⚠️ E'tibor talab qiladigan masalalar: 2 ta
   • 📚 Akademik qarz: 1 ta fan (Xalqaro huquq)
   • 💰 Kontrakt qarzi: 2 450 000 so'm
🕐 Oxirgi yangilanish: 24.09.2026 18:42
```

Davomat belgisi dars qoldirish chegarasiga qarab o'zgaradi (🟢 → 🟡 18+ → 🟠 36+ → 🔴 54+ → ⛔️ 74+ soat). Profil sarlavhasida talabaning **to'lov shakli** (davlat granti yoki to'lov-shartnoma) doim ko'rsatiladi; ma'lumot bo'lmasa — «ma'lumot yo'q». Akademik qarzdorlik qatorida qarzdor fanlar nomi bilan beriladi. **GPA** — o'rtacha o'zlashtirish ko'rsatkichi (quyida). «Mavjud emas» faqat shu turdagi buxgalteriya hisoboti yuklangan va talaba undagi qarzdorlar ro'yxatida bo'lmaganda yoziladi; hisobot yuklanmagan bo'lsa — «ma'lumot yo'q». Ostida bo'limlar: Davomat, Dars jadvali, Baholar, Hujjatlar, **💰 Moliyaviy qarzdorlik**, **📚 Akademik qarzdorlik**, Kurs koordinatoriga yozish.

**🕐 Oxirgi yangilanish.** Kurs koordinatori har bir turdagi faylni yuklagan vaqt saqlanadi va har bir bo'limda ko'rsatiladi: «🕐 Ma'lumot 24.09.2026 18:42 da yangilangan.» To'lov bo'limlarida — shu talabaning ma'lumoti yuklangan vaqt va buxgalteriya hisobotining sanasi.

## Dinamika: davomat va baholar qanday o'zgargani

Farzand sahifasidagi **«📈 Dinamika»** bo'limi faqat raqamlarni emas, taqqoslashni ko'rsatadi:

```
📊 Davomat
Shu hafta: 85%, sababsiz qoldirilgan: 2 para (4 soat)
📉 O'tgan haftaga nisbatan davomat 7% ga pasaydi (92% → 85%).

📚 Baholar
📉 Matematika: 70 → 52 (−18) · «4» → «2»
📈 Ingliz tili: 60 → 74 (+14) · «3» → «4»
❗ «Matematika» fanidan o'rtacha ball oxirgi oyda tushib ketdi.
🎓 GPA: 3,67 → 3,25 (oxirgi oyda).
```

Matn bilan birga **grafik** (rasm) keladi: haftalar bo'yicha davomat foizi va fanlar bo'yicha «bir oy oldin / hozir» ballari (60 ball chegarasi belgilangan). «Umumiy holat» ekranida esa bitta qator: «📈 Dinamika: davomat ↓7%, 1 ta fanda ball pasaydi».

- **Davomat:** kunlik davomat bo'lsa — oxirgi 6 hafta, shu hafta o'tgan hafta bilan solishtiriladi; faqat HEMIS statistikasi bo'lsa — yuklashlar orasidagi har bir davrda qatnashilgan ulush (jami ko'rsatkichlar ayirmasidan), oxirgi davr oldingisi bilan solishtiriladi.
- **Baholar:** har bir import paytida yangi yoki o'zgargan ball sanasi bilan saqlanadi (baholar tarixi). Fan bo'yicha 100 ballik umumiy ball va GPA hozir va bir oy oldin solishtiriladi; tarix bir oydan qisqa bo'lsa — birinchi ma'lum qiymat bilan. Oldingi versiyadan o'tgan bazada tarix yangilanish kunidan boshlanadi.

Matn va grafik ota-onaning tilida (o'zbek, rus, ingliz).

## Akademik qarzdorlik

Fan bo'yicha 100 ballik umumiy ball (HEMIS «O'rtacha ball», «Umumiy», «Jami» yoki 100 ballik «Yakuniy») 5 baholik tizimga o'tkaziladi: **90–100 → «5», 70–89 → «4», 60–69 → «3», 0–59 → «2»**. Ball 0,5 dan boshlab yuqoriga yaxlitlanadi: 69,5 → 70 → «4», 59,5 → 60 → «3». «2» olingan fan — **akademik qarz**. «Oraliq nazorat 25/30» kabi qism baholar akademik qarzni belgilamaydi. «📚 Akademik qarzdorlik» bo'limida: jami nechta fandan qarzdorligi va qaysi fanlar (ball, semestr), barcha fanlar 5 baholik tizimda. Qayta topshirilib 60+ olinsa, qarz avtomatik yopiladi. Kurs koordinatori uchun: `/akademik` — akademik qarzdorlar ro'yxati.


**GPA (o'rtacha o'zlashtirish ko'rsatkichi)** 5 baholik tizimda hisoblanadi: Σ(baho × kredit) / Σ kredit. Kreditlar baholar faylining «Kredit» ustunidan olinadi (ro'yxat formatida: Talaba ID, Fan, Nazorat turi, Ball, Kredit); kreditlar ko'rsatilmagan bo'lsa — fanlar bo'yicha baholarning oddiy o'rtachasi. «2» olingan fanlar ham hisobga kiradi. «Umumiy holat» da GPA barcha semestrlar bo'yicha, «📚 Akademik qarzdorlik» bo'limida esa har bir semestr alohida ko'rsatiladi. Misol: 4 kreditli fandan «4», 6 kreditli fandan «4» va 6 kreditli fandan «2» → (16 + 24 + 12) / 16 = 3,25.

## Aqlli ogohlantirishlar

Ota-ona botni doim tekshirib yurmaydi — muhim o'zgarishni botning o'zi aytadi:
- **akademik qarz yuzaga kelganda** — «⚠️ Muhim xabar: farzandingiz «Xalqaro huquq» fanidan 60 balldan past natija qayd etdi. Natija: 52/100 → «2». ❗ Akademik qarzdorlik yuzaga kelgan.»; qarz yopilganda — «✅ Yaxshi xabar»;
- **to'lov bo'yicha** — hisobot yuklanganda qarz paydo bo'lsa yoki o'zgarsa: «💰 To'lov bo'yicha eslatma: Kontrakt bo'yicha 2 450 000 so'm qarzdorlik mavjud. To'lov muddati: 30-sentabr.»; qarz yopilsa — tasdiq;
- **to'lov muddatidan oldin** — qarzi bor talabalarning ota-onalariga muddatdan 7, 3 va 1 kun oldin avtomatik eslatma (`PAY_REMIND_DAYS`, vaqti `PAY_REMIND_TIME`; har biri bir marta). Muddat `/muddat kontrakt 30.09.2026` va `/muddat trimestr 15.10.2026` bilan belgilanadi;
- **dars qoldirish chegaralari** (18/36/54/74 soat) va dars qoldirilganda darhol xabar — oldingidek.

Ota-ona xabar turlarini «⚙️ Bildirishnomalar» da yoqib-o'chiradi (akademik qarz — «Muhim ogohlantirishlar», to'lov — «Kontrakt va trimestr to'lovi»).

## Moliyaviy qarzdorlik: kontrakt va trimestr

**To'lov shakli** («Davlat granti» yoki «To'lov-shartnoma») uch manbadan olinadi: talabalar faylidagi «To'lov shakli» ustuni, HEMIS «O'rtacha ball» jadvalidagi «To'lov shakli» ustuni va buxgalteriya hisoboti (kontrakt summasi bor talaba — to'lov-shartnoma; grant deb yozilgan talaba hisobotda kontrakt bilan chiqsa, o'zgartiriladi va import natijasida ko'rsatiladi).

**Moliyaviy qarzdorlik** — farzand sahifasida «💰 Moliyaviy qarzdorlik» bo'limi: to'lov shakli va ikki tanlov — **«📄 Kontraktdan qarzdorlik»** (yillik kontrakt bo'yicha hisobot) va **«🗓 Trimestrdan qarzdorlik»** (trimestr bo'yicha hisobot). Tanlanganida: hisobot sanasi, o'quv yili, shartnoma summasi, to'langan summa va foiz, qarzdorlik, izoh va hisobotlar bo'yicha qarz o'zgarishi. Grant talabada «kontrakt to'lovi talab qilinmaydi».

Hisobotlar alohida yuklanadi (/import → «💰 Kontrakt qarzdorligi» yoki «🗓 Trimestr qarzdorligi»), har biri har bir sana bo'yicha saqlanadi. Qarz «Qoldiq» (manfiy — qarz) yoki «Davr oxiriga qoldiq DT-Qarz» ustunidan; hisobot sanasi sarlavhadagi sanadan (boshqa sanani fayl izohiga yozish mumkin); pastdagi «Jami» qatorlari o'tkazib yuboriladi. Hisobotlarda HEMIS ID yo'q — talabalar **F.I.Sh. bo'yicha** topiladi (bir xil ismlilar kurs bo'yicha ajratiladi, ajratib bo'lmasa — xato qatori). **JSHSHIR saqlanmaydi.** Qarz paydo bo'lsa yoki o'zgarsa — ota-onaga xabar (qaysi hisobot: kontrakt yoki trimestr), to'liq yopilsa — tasdiq; `jim` — xabarsiz; ota-ona «⚙️ Bildirishnomalar» da o'chirishi mumkin.

**Akademik qarzdorlik** — farzand sahifasida «📚 Akademik qarzdorlik» bo'limi. Fan bo'yicha 100 ballik umumiy ball (masalan, HEMIS «O'rtacha ball») 5 baholik tizimga o'tkaziladi:

| Ball | Baho |
|---|---|
| 90–100 | «5» |
| 70–89 | «4» |
| 60–69 | «3» |
| 0–59 | «2» — shu fandan **akademik qarzdor** |

Ball 0,5 dan boshlab yuqoriga yaxlitlanadi: 69,5 → 70 → «4»; 59,5 → 60 → «3». «Oraliq nazorat 25/30» kabi qism baholar akademik qarzni belgilamaydi. Bo'limda: **jami nechta fandan qarzdorligi va qaysi fanlar** (ball va semestr bilan), so'ng barcha fanlar 5 baholik bahosi bilan. «📝 Baholar» bo'limida ham 100 ballik ball yonida 5 baholik baho ko'rinadi; yangi baho haqidagi xabarda «2» olingan fanlar alohida ko'rsatiladi.

Kurs koordinatori uchun: `/qarzdorlar` — moliyaviy qarzdorlar (kontrakt va trimestr alohida; `/qarzdorlar trimestr 2-kurs`), `/akademik` — akademik qarzdorlar (nechta va qaysi fanlar), `/talaba` — talabaning to'lov shakli, ikkala qarzi va akademik qarzi, `/stat` — umumiy ko'rsatkichlar; import natijasida qarzdorlar soni, jami qarz, eng katta qarzlar va akademik qarzdorlar soni chiqadi.

## Dars qoldirish chegaralari

**Qoldirilgan darslar para va soatda.** HEMIS davomat statistikasidagi sonlar — juftlik (para): «Qatnashmaganlar soni» 5 bo'lsa, bu 5 para = 10 soat. Ota-onaga ham, kurs koordinatoriga ham hamma joyda ikkalasi ko'rsatiladi: «5 para (10 soat)» (rus tilida «5 пар (10 ч)», ingliz tilida «5 classes (10 h)»). Chegaralar soatda belgilanadi va xuddi shunday ko'rinadi: 18 soat = «9 para (18 soat)».

Semestr boshidan buyon sababsiz qoldirilgan soatlar bo'yicha universitet ichki tartibidagi choralar botda sozlangan:

| Chegara | Chora |
|---|---|
| 18 soat | Dekan nomiga tushuntirish xati |
| 36 soat | Dekan ogohlantirishi |
| 54 soat | Hayfsan |
| 74 soat | Talabalar safidan chetlatish |

Soatlar HEMIS statistikasidan (bo'lsa — u ustun turadi), bo'lmasa kunlik davomatdan hisoblanadi. Talaba yangi chegaraga yetganda ota-onasiga **bitta** xabar boradi: jami soat, qo'llaniladigan chora va keyingi chegara (bir nechta chegara birdan o'tilsa ham xabar bitta). Har bir chegara haqida semestrda bir marta xabar beriladi. Farzand sahifasida va «Davomat» bo'limida chegara holati va keyingi chegaragacha qolgan soat doim ko'rinib turadi, «Foydali ma'lumot» bo'limida esa chegaralar jadvali.

Kurs koordinatoriga har bir davomat importidan keyin chegaralar holati va **yangi chegaraga yetgan talabalar ro'yxati** (tushuntirish xati olish, ogohlantirish tayyorlash uchun) chiqadi. `/chegaralar` buyrug'i barcha talabalarni chegaralar bo'yicha guruhlab ko'rsatadi.

Sozlamalar (`.env`): `ABSENCE_WARN_LEVELS=18,36,54,74`, `ABSENCE_WARN_ACTIONS` (choralar nomlari, `|` bilan), `ABSENCE_COUNT_EXCUSED=0` (1 qilinsa, sababli soatlar ham hisoblanadi), `HEMIS_STATS_HOURS_PER_UNIT=2` (HEMIS statistikasidagi sonlar — juftlik (para), 1 para = 2 soat; sonlar soatda bo'lsa — 1).

**Muhim.** HEMIS statistikasida yo'qlama qilinmagan darslar «qatnashmagan» deb hisoblangan bo'lsa, bot ota-onalarga noto'g'ri ogohlantirish yuboradi. Bot fayldagi barcha talabalarda bir xil minimal «qatnashmagan» soni bo'lsa, import natijasida buni aytadi. Birinchi yuklashni `jim` bilan qilib, natijani `/chegaralar` orqali ko'rib chiqing va bir-ikki talabani HEMIS'da tekshiring.

**Qoldirishlar kamaysa ham xabar boradi.** Keyingi davomat faylida talabaning sababsiz qoldirishlari kamaysa (masalan, bir qismi sababli deb topilsa yoki ma'lumot tuzatilsa) va u avval biror chegaraga yetgan bo'lsa, ota-onaga xabar ketadi:

```
✅ Davomat o'zgardi (HEMIS ma'lumoti, 24.09.2026 holatiga)
Farzandingiz 9 para (18 soat) va undan ko'p dars qoldirgani uchun «Dekan nomiga tushuntirish xati» talab qilingan edi.
Qoldirilgan darslarning 3 para (6 soat) sababli deb topildi.
Sababsiz qoldirilgan darslar: 10 para (20 soat) → 7 para (14 soat).
Endi bu hech qaysi chegaradan past — «Dekan nomiga tushuntirish xati» talab qilinmaydi.
```

Yuqoriroq chegaradan pastroqqa tushsa — hozir amaldagi chegara aytiladi (masalan, «dekan ogohlantirishi» → «tushuntirish xati»). Xabar «Muhim ogohlantirishlar» sozlamasi bo'yicha, ota-onaning tilida boradi; avval hech qaysi chegaraga yetmagan talabalar uchun yuborilmaydi. Kurs koordinatoriga import natijasida «⬇️ Sababsiz qoldirishlari kamayganlar» ro'yxati (avval → endi) chiqadi. Chegaradan pastga tushgan talaba keyinroq yana oshsa, ota-ona qayta ogohlantiriladi. Kunlik davomatda ham xuddi shunday ishlaydi.

## Rasmiy hujjatlar (PDF)

Tushuntirish xati, dekan ogohlantirishi, hayfsan yoki boshqa rasmiy hujjat PDF ko'rinishida talabaning ota-onalariga yuboriladi va farzand sahifasidagi «📄 Hujjatlar» bo'limida saqlanadi.

**Yuborish.** PDF faylni botga shunchaki yuboring (yoki avval `/hujjat` bering). Fayl izohiga (caption) qisqa sharh va sana yozish mumkin, masalan «22.09.2026 dagi 45-son buyruq» — sharh ota-onaga boradi, sana hujjat sanasi bo'ladi. Bot faylni o'qib, unda bazadagi qaysi talabalar borligini aniqlaydi. Bir nechta talaba bo'lsa, ro'yxatni belgilash tugmalari bilan ko'rsatadi — keraksizini olib tashlash yoki boshqasini qo'shish mumkin. Keyin hujjat turi so'raladi (fayl nomidagi «hayfsan», «ogohlantirish», «tushuntirish» so'zlaridan avtomatik aniqlanadi).

**Boshqa talabalar ma'lumotlarini yopish.** Buyruq yoki ogohlantirishda bir nechta talaba bo'lsa, har bir talabaning ota-onasi faqat o'z farzandini ko'radi. Boshqa talabalarning F.I.Sh., guruhi, ID raqami va shu qatordagi boshqa ma'lumotlari (qoldirilgan soatlar, sana va h.k.) qora rang bilan yopiladi.
- **Jadvaldagi ro'yxat:** sarlavhadan keyingi, shu talabaga tegishli bo'lmagan har bir qator to'liq yopiladi.
- **Raqamlangan ro'yxat:** boshqa talabaga tegishli band davomi bilan birga yopiladi.
- **Oddiy matn:** matn ichida uchragan boshqa talabaning ismi yopiladi.
- **Kimlar aniqlanadi:** bazadagi talabalar ism-familiya yoki initsial bo'yicha topiladi. Bazada yo'q talabalar familiyadagi -ov, -ova, -ev, -eva qo'shimchalari va «o'g'li / qizi» so'zlari orqali, ID raqamlar esa ko'rinishi bo'yicha aniqlanadi.
- **Nima yopilmaydi:** dekan, prorektor va kurs koordinatori kabi rahbarlar ismlari, shuningdek **«Mas'ullar:»** (yoki «Mas'ul», «Javobgar», «Ijrochi») bo'limidagi barcha ismlar — ular keyingi qatorlarda, raqamlangan ro'yxatda yoki «Mas'ul shaxslar» jadvalida bo'lsa ham. Bo'lim katta bo'sh joy yoki «Asos», «Ilova» kabi yangi bo'lim bilan tugaydi. «Intizomiy mas'uliyat choralari» kabi jumla bo'limni boshlamaydi — talabalar ro'yxati baribir yopiladi.
- **Nusxa qanday tayyorlanadi:** nusxa rasmga aylantirilgan PDF bo'ladi, shuning uchun yopilgan matn faylning ichida ham qolmaydi.

**Yuborishdan oldin tekshirish.** Har bir talaba uchun tayyorlangan nusxa avval kurs koordinatoriga yuboriladi. Tasdiqlash oynasida quyidagilar ko'rsatiladi: kimlarga yuborilishi, har bir nusxada nechta joy yopilgani, ulangan ota-onalar soni va ogohlantirishlar. Ogohlantirishlar uch turda bo'ladi: talabaning o'zi hujjatda topilmadi; ismi o'xshash talaba bor (masalan, aka-uka «Karimov J.»); bu hujjat avval yuborilgan. Hujjat faqat «Ota-onalarga yuborish» bosilgandagina ketadi.

**Skanerlangan hujjatlar.** Skanerlangan (rasm ko'rinishidagi) PDF serverda Tesseract OCR o'rnatilgan bo'lsa o'qiladi (o'zbek lotin va kirill, rus tillari). Tesseract bo'lmasa yoki fayl 20 MB dan katta bo'lsa, hujjatni tekshirib bo'lmaydi. Bunda bot buni ochiq aytadi va yuborish tugmasi «Boshqa talabalar yo'q — yuborish» bo'ladi. Hujjat asl holida faqat kurs koordinatori shuni tasdiqlasa ketadi; aks holda har bir talaba uchun alohida nusxa tayyorlab yuboring. Skanerda matn sifatli bo'lishi muhim — xira skanerda ba'zi ismlar o'qilmasligi mumkin, shuning uchun nusxalarni albatta ko'zdan kechiring.

**Xato yuborilsa.** Natija xabaridagi «🗑 Qaytarib olish» tugmasi shu yuborishdagi barcha nusxalarni ota-onalar bo'limidan olib tashlaydi va ularning chatidan o'chiradi. Telegram buni 48 soat ichida qilishga ruxsat beradi; kechroq bo'lsa, bot nechta chatdan o'chirib bo'lmaganini aytadi. `/hujjatlar familiya` buyrug'i talabaga yuborilgan hujjatlarni (ota-ona ko'rgan nusxada) qaytarib olish tugmasi bilan ko'rsatadi.

Fayllar Telegram serverida saqlanadi, bot bazasida faqat ularning identifikatori, nechta joy yopilgani, kim va qachon yuborgani yoziladi. Hujjatlarning asl nusxasi dekanatda saqlanishi kerak. Intizomiy hujjatlarni ota-onaga yuborish tartibi (masalan, avval talabaning o'zi tanishtirilishi) universitet ichki tartibi bilan kelishilgan bo'lishi lozim.

## Kurs koordinatori paneli va ma'lumotlarni tekshirish

`/panel` (yoki /admin → «📊 Kurs holati») — kurs holati bir qarashda: jami talabalar, ulangan ota-onalar (va ota-onasi ulangan talabalar ulushi), akademik qarzdorlar, kontrakt va trimestr qarzdorlari (jami summa bilan), davomat muammosi borlar (18+ soat), **3 va undan ortiq muammosi bor talabalar**. Tugmalar: «🔴 Muammoli talabalar» (muammolar soni bo'yicha saralangan), akademik, kontrakt, trimestr va davomat bo'yicha ro'yxatlar. Kurs yoki guruh bo'yicha: `/panel 3-kurs`, `/panel 3-1a-24`.

**Import tekshiruvi.** Bot har bir fayl ustunlariga qarab uning qaysi turga tegishli ekanini aniqlaydi. Tanlangan tur bilan mos kelmasa, import to'xtaydi:

```
⚠️ Diqqat!
Ushbu faylda «Kontrakt qarzdorligi» fayliga xos ustunlar aniqlandi.
Siz «Trimestr qarzdorligi» importini tanladingiz.
Davom etasizmi?
[❌ Bekor qilish] [✅ Davom etish] [🔄 «Kontrakt qarzdorligi» sifatida yuklash]
```

Import natijasida bazadan topilmagan talabalar ham umumiy son bilan ko'rsatiladi: «⚠️ 263 talabadan 7 tasi bazadan topilmadi (masalan: …)».

## Hisobot eksporti: Excel va PDF

Kurs koordinatori dekanat yig'ilishi yoki rahbariyat uchun tayyor hisobotni bir tugma bilan oladi:
- **to'liq hisobot** — `/panel` ostidagi «📥 Excel hisobot» / «📄 PDF hisobot», `/stat` ostidagi tugmalar yoki `/hisobot` (kurs yoki guruh bo'yicha: `/hisobot 3-1a-24`);
- **bitta ro'yxat** — panelda «Muammoli talabalar», «Akademik qarzdorlar», «Kontrakt qarzdorlar», «Trimestr qarzdorlar», «Davomat muammosi» ro'yxatlari oxiridagi «📥 Excel» / «📄 PDF».

Hisobot bo'limlari: umumiy ko'rsatkichlar; muammoli talabalar (muammolar soni, sababsiz qoldirilgan para va soat, chora, akademik qarz fanlari, kontrakt va trimestr qarzi, ota-onasi botdami); davomati past talabalar (para, soat, davomat foizi, chora, manba); akademik qarzdorlar (fanlar, ball → baho, semestr); kontrakt va trimestr qarzdorlari (shartnoma, to'langan, foiz, qarz, hisobot sanasi, to'lov muddati).

**Excel:** har bir bo'lim — alohida varaq, sarlavha qatori qotirilgan, filtr qo'yilgan, chop etishga moslangan (albom holatida, bir sahifa eniga). Jami summalar va «Umumiy» varaqdagi sonlar **formulalar** bilan hisoblanadi — jadval tahrirlansa ham to'g'ri qoladi. **PDF:** albom holatidagi A4, jadvallar, sahifa raqamlari; o'zbek va kirill harflari uchun DejaVu shrifti (matplotlib bilan birga keladi — serverga alohida o'rnatish shart emas). Ko'p kursli rejimda hisobot faqat koordinatorning o'z kursi bo'yicha.

## Kurs koordinatori buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `/admin` | buyruqlar ro'yxati |
| `/import` | Excel fayl yuklash |
| `/shablon` | Excel namunalarini olish |
| `/toldir d1 d2` | jadvaldagi, yozuvi yo'q darslarni «qatnashdi» deb belgilash |
| `/hisobot` | 📥 kurs holati hisoboti: Excel yoki PDF (ixtiyoriy: kurs yoki guruh) |
| `/koordinator Ism Familiya +998...` | ota-onalarga ko'rinadigan kurs koordinatori ismi va telefoni (butun kurs uchun; talabalar faylidagi «Kurs koordinatori» ustunidan keyin qo'llanadi) |
| `/tarjimalar` | 🌐 fan va fakultet nomlarining ruscha va inglizcha tarjimalari (Excel: yuklab olish, to'ldirib qaytarish) |
| `/tayyor` | import sessiyasini yakunlash va xulosa (bir nechta fayl yuklangach) |
| `/super`, `/kurslar`, `/yangi_kurs`, `/umumiy`, `/kursga_kirish`, `/zaxira`, `/xatolar` | faqat super-admin (menyu tugmalari bilan bir xil) |
| `/panel` | 📊 kurs holati va muammoli talabalar (ixtiyoriy: kurs yoki guruh) |
| `/kompyuter` | 💻 kompyuter versiyasi — brauzerda ochiladigan boshqaruv paneli uchun bir martalik havola |
| `/muddat` | kontrakt va trimestr to'lov muddatlari (eslatmalar shu asosda) |
| `/qarzdorlar` | moliyaviy qarzdorlar: kontrakt va trimestr (ixtiyoriy: tur, guruh yoki kurs) |
| `/akademik` | akademik qarzdorlar: 0–59 ball («2») olgan fanlari bilan |
| `/chegaralar` | dars qoldirish chegaralariga (18/36/54/74 soat) yetgan talabalar, chegaralar bo'yicha guruhlab |
| `/elon` | e'lon yuborish (matn, rasm, fayl) — hammaga yoki guruhlarga |
| `/talaba familiya` | talabani va unga ulangan ota-onalar sonini topish |
| `/jadval familiya` | talabaning shaxsiy dars jadvali: asosiy fanlar + tanlov fani va ikkinchi til |
| `/hujjat` | tushuntirish xati, dekan ogohlantirishi, hayfsanni (PDF) ota-onaga yuborish; PDF ni shunchaki yuborsangiz ham bo'ladi |
| `/hujjatlar familiya` | talabaga yuborilgan hujjatlar, qaytarib olish tugmasi bilan |
| `/stat` | statistika (ulangan ota-onalar ulushi va boshqalar) |
| `/info` | «Foydali ma'lumot» bo'limi matnini o'zgartirish |
| `/guruhlar` | bot qo'shilgan talabalar Telegram guruhlari, bot admin ekanligi, ma'lum a'zolar soni |
| `/tekshir` | ro'yxatdan o'tganlarning barchasini talabalar raqamlari va guruhlari bo'yicha qayta tekshirish |
| `/bloklar` | talaba deb bloklanganlar (har biri ruxsat tugmasi bilan) |
| `/guruh IQ-21` | (talabalar guruhining o'zida) Telegram guruhni akademik guruhga bog'lash |
| `/bekor` | joriy amalni bekor qilish |

Bog'lash so'rovlari va ota-ona savollari kurs koordinatoriga tugmalar bilan keladi (✅ Tasdiqlash / ❌ Rad etish, 💬 Javob berish). Bog'lash so'rovini tasdiqlashdan oldin ota-ona bilan telefon orqali gaplashib olish tavsiya etiladi.

## Sozlamalar (.env)

`ABSENCE_WARN_LEVELS`, `ABSENCE_WARN_ACTIONS`, `ABSENCE_COUNT_EXCUSED`, `HEMIS_STATS_HOURS_PER_UNIT` — dars qoldirish chegaralari («Dars qoldirish chegaralari» bo'limi). `SUBJECT_WARN_PERCENT` (25%) — bitta fandan sababsiz qoldirishlar ulushi (faqat kunlik davomatda). `DAILY_DIGEST_TIME` — kunlik xulosa vaqti, `DIGEST_DAY_OFFSET=1` qilsangiz xulosa kechagi kun bo'yicha yuboriladi (davomat kechroq yuklanadigan bo'lsa qulay). `PAIR_TIMES` — jadval faylida vaqt ustuni bo'lmasa juftlik vaqtlari (rasmiy qo'ng'iroq jadvali bo'yicha to'ldiring). `HOURS_PER_PAIR` — «Soat» ustuni bo'lmasa bitta juftlik necha soat hisoblanishi.

`WEBAPP_URL`, `WEBAPP_HOST`, `WEBAPP_PORT`, `WEBAPP_AUTH_TTL` — Telegram Web App («Telegram Web App» bo'limi). `WEBAPP_DEV_USER` — faqat sinov uchun (ilovani brauzerda Telegram'siz ochish); serverda bo'sh qoldiring.

## Serverga joylashtirish (Linux, systemd)

Skanerlangan hujjatlardagi boshqa talabalar ma'lumotlarini yopish uchun serverga OCR dasturini o'rnating:

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-uzb tesseract-ocr-uzb-cyrl tesseract-ocr-rus
```


```ini
# /etc/systemd/system/ota-ona-bot.service
[Unit]
Description=Ota-onalar davomat boti
After=network-online.target

[Service]
WorkingDirectory=/opt/ota_ona_bot
ExecStart=/opt/ota_ona_bot/venv/bin/python bot.py
Restart=always
RestartSec=5
User=botuser

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ota-ona-bot
journalctl -u ota-ona-bot -f     # loglarni ko'rish
```

Har bir kurs bazasidan va umumiy ro'yxatdan muntazam zaxira nusxa oling, masalan har kuni (cron):

```bash
for f in /opt/ota_ona_bot/data/*/bot.db /opt/ota_ona_bot/data/central.db; do
  sqlite3 "$f" ".backup /opt/backup/$(basename $(dirname $f))-$(basename $f .db)-$(date +%F).db"
done
```

Har bir kursning papkasi mustaqil: kursni boshqa serverga ko'chirish yoki koordinatorga topshirish uchun uning `data/<kurs>/` papkasini nusxalash kifoya.

### Web App uchun HTTPS manzil

Telegram ilovani faqat HTTPS orqali ochadi. Bot ichidagi veb-server `127.0.0.1:8080` da tinglaydi (`WEBAPP_HOST`, `WEBAPP_PORT`); unga tashqaridan HTTPS ulashning uch yo'li bor. Qaysi biri bo'lsa ham, oxirida `.env` dagi `WEBAPP_URL` ga manzilni yozib, botni qayta ishga tushirasiz (`sudo systemctl restart ota-ona-bot`).

**1. Domen + Caddy (eng sodda, tavsiya etiladi).** Universitet IT bo'limidan subdomen oling (masalan `ilova.example.uz`) va uning DNS A-yozuvini server IP manziliga yo'naltiring; serverda 80 va 443 portlar ochiq bo'lishi kerak. Caddy SSL sertifikatni o'zi oladi va yangilab turadi:

```bash
sudo apt install -y caddy
```

```
# /etc/caddy/Caddyfile
ilova.example.uz {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
# .env: WEBAPP_URL=https://ilova.example.uz
```

**2. Domen + nginx + Let's Encrypt.** Serverda nginx allaqachon bo'lsa:

```nginx
server {
    server_name ilova.example.uz;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 25m;   # Excel fayllarni ilova orqali yuklash uchun
        proxy_buffering off;        # real vaqt bildirishnomalari (/api/events) kechikmasin
        proxy_read_timeout 1h;      # uzoq ulanish uzilmasin
    }
}
```

```bash
sudo certbot --nginx -d ilova.example.uz
```

Muhim: `proxy_buffering off` bo'lmasa, nginx real vaqt bildirishnomalarini to'plab, kechiktirib yuboradi. Caddy va Cloudflare Tunnel buni o'zi to'g'ri qiladi.

**3. Cloudflare Tunnel (ochiq port va ochiq IP kerak emas).** Server tashqi internetdan ko'rinmasa (masalan universitet ichki tarmog'ida) qulay. Doimiy manzil uchun Cloudflare akkaunt va Cloudflare'ga ulangan domen kerak:

```bash
cloudflared tunnel login
cloudflared tunnel create ota-ona-ilova
cloudflared tunnel route dns ota-ona-ilova ilova.example.uz
cloudflared tunnel run --url http://127.0.0.1:8080 ota-ona-ilova   # doimiy ishlashi uchun: cloudflared service install
```

#### Vaqtincha sinash — bir bosishda (domen kerak emas)

Ilovani domen va serversiz, o'z kompyuteringizda sinab ko'rish uchun loyihada tayyor skript bor. U Cloudflare'ning bepul vaqtinchalik tunneli (Quick Tunnel) orqali `https://….trycloudflare.com` manzil ochadi, uni `.env` ga yozadi va botni ishga tushiradi:

- **Windows:** `ilova_sinov.bat` faylini ikki marta bosing;
- **Linux / macOS:** `bash ilova_sinov.sh`.

Skript `cloudflared` dasturi kompyuterda bo'lmasa, uni rasmiy GitHub sahifasidan o'zi yuklab oladi (Windows'da loyiha papkasiga `cloudflared.exe` bo'lib tushadi). Oynada «Ilova manzili: https://…» chiqqach, Telegram'da botni oching va `/start` bosing — chat pastida «📱 Ilova» tugmasi paydo bo'ladi. To'xtatish — **Ctrl+C**: tunnel yopiladi va `.env` dagi `WEBAPP_URL` avvalgi holatiga qaytadi; botni keyin oddiy ishga tushirsangiz, eski manzilli tugma o'zi olib tashlanadi.

Ota-ona ko'rinishini sinash: `ADMIN_IDS` dagi akkaunt har doim kurs koordinatori sifatida kiradi va koordinator ekranlarini ko'radi. Ota-ona ekranlarini ko'rish uchun avval `python demo_seed.py <ikkinchi_telefon_raqam>` bilan namunaviy ma'lumot yarating va shu raqamli **boshqa** Telegram akkaunt bilan botga kiring (telefon raqamini ulashing).

Cheklovlar: vaqtinchalik manzil har ishga tushirishda o'zgaradi va Cloudflare uning ishlashiga kafolat bermaydi — bu faqat sinov uchun; ilova kompyuter yoqiq va skript ishlab turganda ochiladi. Oldingi manzil bilan yuborilgan xabarlar ostidagi «📱 Ilovada ochish» tugmalari keyingi safar ishlamaydi. Ba'zi ofis tarmoqlari Cloudflare tunnelini to'sadi — unda skript xatoni ko'rsatadi, uyda yoki mobil internet orqali sinab ko'ring.

Tekshirish: `curl https://ilova.example.uz/healthz` — `ok` qaytishi kerak. Keyin botda `/start` bosing: chat menyusida «📱 Ilova» tugmasi paydo bo'ladi.

## Cheklovlar va keyingi qadamlar

Telegram bot orqali yuklanadigan fayl hajmi 20 MB dan oshmasligi kerak (katta fayllarni bir necha qismga bo'ling). Ma'lumotlar kurs koordinatori yuklagan paytdagi holatni aks ettiradi, shuning uchun «bugun» bo'limida yuklanmagan darslar ⚪ bilan ko'rinadi. Keyinchalik universitet IT bo'limi ruxsati bilan HEMIS bilan to'g'ridan-to'g'ri integratsiya qilinsa, qo'lda import o'rniga avtomatik yangilash qo'shish mumkin — buning uchun faqat `importer.py` o'rniga ma'lumotni API dan oluvchi modul yoziladi, qolgan qismlar o'zgarmaydi.

## Fayllar tuzilishi

```
bot.py            — ishga tushirish, buyruqlar menyusi, rejalashtiruvchi
config.py         — .env sozlamalari
database.py       — SQLite jadvallari va so'rovlar
importer.py       — Excel fayllarni o'qish (ustunlarni avtomatik aniqlash)
reports.py        — ota-onaga ko'rsatiladigan hisobotlar matni
notifier.py       — darhol xabarlar, ogohlantirishlar, kunlik xulosa
absence.py        — dars qoldirish chegaralari (18/36/54/74 soat) va choralar
academic.py       — akademik qarzdorlik: 100 ballik → 5 baholik (0–59 → «2»), GPA
templates.py      — shablonlar: versiyalar, sarlavhalar tahlili, import o'rgangan ustun nomlari
trends.py         — dinamika: davomat va baholar taqqoslanishi, grafik (ota-ona uchun)
export.py         — kurs koordinatori uchun Excel va PDF hisobotlar
loc.py            — ma'lumotlarni ota-ona tilida ko'rsatish: ismlar kirillda, fan va fakultetlar tarjimada
terms_data.py     — ichki lug'at: fan, til, fakultet, nazorat turlarining ruscha va inglizcha nomlari
termsheet.py      — /tarjimalar: kursdagi nomlar jadvali (Excel) va tarjimasi yo'qlar
botcommands.py    — Telegram buyruqlar menyusi rol bo'yicha (ota-ona, kurs koordinatori, super-admin)
logsetup.py       — markazlashgan loglar (logs/), xatolar haqida super-adminga darhol xabar
backup.py         — tungi zaxira nusxa: barcha kurs bazalari, yaxlitlik tekshiruvi, AES shifrlash
handlers/superadmin.py — super-admin: kurslar, koordinatorlar, umumiy holat, zaxira, xatolar
handlers/staff.py — kurs koordinatori menyusi (pastki tugmalar)
tenancy.py        — ko'p kursli rejim: joriy kurs, kurs koordinatorlari, umumiy ro'yxat (central.db)
family.py         — ota-onaning barcha kurslardagi farzandlari, kurslar orasida ota-onani ro'yxatga olish
i18n.py           — ko'p tillilik: o'zbek, rus, ingliz (joriy til, tr())
i18n_data.py      — rus va ingliz tilidagi tarjimalar
status.py         — talabaning umumiy holati (ota-onaning bosh ekrani va kurs koordinatori paneli uchun)
academic.py       — akademik qarzdorlik: 100 ballik → 5 baholik tizim
individual.py     — har bir talabaning shaxsiy dars jadvali (asosiy fanlar + tanlov fani va 2-til oqimi)
guard.py          — talabalarni aniqlash (raqam va Telegram guruhlar bo'yicha), bloklash
redact.py         — rasmiy hujjatlarda boshqa talabalar ma'lumotlarini qora rang bilan yopish
middlewares.py    — bloklangan foydalanuvchi so'rovlarini to'xtatish
keyboards.py      — tugmalar
utils.py          — ism/telefon/sana bilan ishlash, kirill→lotin
handlers/         — ota-ona, ro'yxatdan o'tish, admin, qidiruv, talabalar guruhlari
webserver.py      — Telegram Web App uchun veb-server (bot bilan bitta jarayonda), menyu tugmasi
webapi.py         — ilova API: Telegram imzosini tekshirish, ota-ona va kurs koordinatori ma'lumotlari
chat.py           — ota-ona ↔ kurs koordinatori yozishmasi (bot va ilova uchun umumiy)
deskauth.py       — kompyuter versiyasiga kirish: bot yuboradigan bir martalik havola, imzolangan seans
staffops.py       — so'rovni tasdiqlash, koordinatorni tayinlash/olib tashlash (bot va kompyuter versiyasi uchun umumiy)
appmode.py        — ilova rejimi: bot faqat ilovaga o'tish vositasi, qisqa bildirishnomalar (uch tilda)
live.py           — real vaqt voqealari (Server-Sent Events): bildirishnoma, xabar, so'rov — ilova ochiq bo'lsa darhol
docstore.py       — rasmiy hujjatlar ombori va ilovada ko'rish (PDF sahifalari — rasm)
handlers/appgate.py — ilova rejimida ota-onaning botdagi matnlari va eski tugmalari — ilovaga yo'naltiriladi
webapp/           — ilovaning o'zi: index.html, app.js, app.css; kompyuter versiyasi: desk.html, desk.js, desk.css;
                    shriftlar (Golos Text, PT Serif)
ilova_sinov.bat   — Windows: ilovani vaqtincha HTTPS orqali sinash (ilova_sinov.ps1 ni ishga tushiradi)
ilova_sinov.sh    — Linux/macOS: xuddi shu (Cloudflare Quick Tunnel + bot)
shablonlar/       — Excel namunalari
demo_seed.py      — sinov uchun to'qima ma'lumotlar
```
