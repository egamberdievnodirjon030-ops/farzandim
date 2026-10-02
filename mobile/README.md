# Telefon ilovasi — Android va iOS

Ilova ([Capacitor](https://capacitorjs.com) qobig'i) serverdagi Web App ni ochadi — Telegram ichidagi ilova bilan bir xil
ekranlar. Yangi funksiya serverga qo'yilishi bilan telefonda ham paydo bo'ladi: ilovani qayta o'rnatish shart emas.

**Telegram'da qoladigan narsalar:**
- **ro'yxatdan o'tish** — telefon raqami Telegram tugmasi orqali botda tasdiqlanadi;
- **ilovaga kirish** — ilova «Telegram orqali kirish» ni bosganda 2 xonali raqam ko'rsatadi va botni ochadi; botda shu
  raqam tanlanadi (boshqa odam yuborgan havola orqali akkauntga kirib bo'lmaydi). Parol yo'q;
- **bildirishnomalar** — avvalgidek bot chatiga keladi.

Botda: `/ilova` — yuklab olish, `/qurilmalar` — ilovaga kirgan qurilmalar va ulardan chiqarish. Foydalanuvchi talaba deb
bloklansa, uning barcha qurilmalari avtomatik chiqariladi.

## 1. Bir martalik sozlash (GitHub)

Repo → **Settings → Secrets and variables → Actions**:

| Qayerda | Nomi | Qiymati |
|---|---|---|
| Variables | `APP_SERVER_URL` | botdagi `WEBAPP_URL` bilan bir xil, masalan `https://ilova.example.uz` |
| Secrets | `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` | `bash mobile/scripts/make-keystore.sh` chiqargan qiymatlar |

Imzo kaliti **bir marta** yaratiladi va saqlab qo'yiladi. Kalitsiz ham APK yig'iladi (debug), lekin keyingi versiyalar
uning ustiga o'rnatilmaydi — haqiqiy foydalanish uchun kalit shart.

## 2. Android: yig'ish va tarqatish

1. GitHub → **Actions → «Mobil ilova» → Run workflow** (yoki `mobile/` dagi har bir o'zgarishda o'zi ishlaydi).
2. Tayyor APK — ish natijasidagi *Artifacts* da yoki **Releases** da (`android-1.0.N`).
3. APK ni **super-admin** sifatida botga yuboring (izohiga versiyani yozish mumkin: `1.0.5`). Shu zahoti:
   - ota-onalar botda `/ilova` yoki «📲 Telefon ilovasini yuklab olish» tugmasi orqali faylni oladi;
   - `https://<server>/ilova` sahifasidan ham yuklab olinadi.

Yangi versiya ham xuddi shunday: APK ni botga qayta yuborasiz. (Ko'pincha yangi APK kerak ham emas — ekranlar serverdan
keladi. APK faqat ilova belgisi, nomi yoki qobiq o'zgarganda yangilanadi.)

## 3. iPhone (iOS)

Apple iPhone'ga ilovani fayl sifatida o'rnatishga ruxsat bermaydi — faqat **App Store** yoki **TestFlight** orqali.
Shuning uchun:

- **Hozirdan:** ota-ona `https://<server>/` ni Safari'da ochadi → «Ulashish» → «Bosh ekranga qo'shish». Ekranda ilova
  belgisi paydo bo'ladi, kirish ham Telegram orqali. Bot `/ilova` da shu yo'riqnomani beradi.
- **App Store / TestFlight:** Apple Developer Program a'zoligi kerak (yiliga $99). App Store Connect'da `uz.jidu.otaona`
  identifikatorli ilova yarating, so'ng Secrets ga qo'shing: `IOS_CERT_P12_BASE64`, `IOS_CERT_PASSWORD` (Apple
  Distribution sertifikati), `IOS_PROFILE_BASE64` (App Store provisioning profile), `IOS_TEAM_ID`, va TestFlight'ga
  avtomatik yuklash uchun `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8_BASE64` (App Store Connect API kaliti). Workflow
  imzolangan `.ipa` ni yig'ib TestFlight'ga yuklaydi. Havolani botga kiriting: `/ilova_ios https://testflight.apple.com/join/...`
  (yoki App Store havolasi) — `/ilova` endi shu tugmani ko'rsatadi.

Eslatma: Apple sof «veb-sayt qobig'i» ilovalarini ba'zan rad etadi (4.2-qoida). Bu ilovada o'z kirish tizimi, real vaqt
yangilanishlari va telefon uchun moslashgan ekranlar bor, lekin tekshiruvdan o'tish kafolatlanmaydi — TestFlight
(10 000 tagacha foydalanuvchi, App Store tekshiruvisiz ichki sinov) yoki Safari yo'li har doim ishlaydi.

## Kompyuterda yig'ish (ixtiyoriy)

Node 22+, Java 21, Android Studio (Android uchun) yoki Xcode (iOS uchun, faqat Mac):

```bash
cd mobile
npm ci
APP_SERVER_URL=https://ilova.example.uz npm run android   # yoki: npm run ios
npx cap open android                                       # Android Studio'da ochiladi
```

## Tuzilishi

- `scripts/configure.mjs` — `capacitor.config.json` ni server manzili bilan yaratadi (`APP_SERVER_URL`)
- `assets/` — ilova belgisi va ochilish ekrani (har ikki platforma uchun avtomatik o'lchamlarga keltiriladi)
- `www/offline.html` — internet bo'lmaganda ko'rinadigan sahifa
- `android/`, `ios/` — yig'ish paytida yaratiladi (repoda saqlanmaydi)
- Server tomoni: `appauth.py` (kirish va seanslar), `handlers/mobileapp.py` (bot: `/ilova`, kirishni tasdiqlash,
  `/qurilmalar`), `webapi.py` (`/api/app/login…`), `webapp/app.js` (Telegram'siz rejim)
