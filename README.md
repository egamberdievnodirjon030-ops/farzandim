# Yangi Özbek Lotin klaviaturasi

Eski lotin yozuvida qanday yozgan bölsangiz, şunday yozavering. Matn yangi (2026) özbek alifbosida çiqadi.

| Siz yozasiz | Çiqadi | Misol |
|---|---|---|
| `sh` | **ş** | Sherzod → Şerzod |
| `ch` | **ç** | choy → çoy |
| `o'` (yoki `o‘`, `` o` ``) | **ö** | O'zbekiston → Özbekiston |
| `g'` (yoki `g‘`, `` g` ``) | **ğ** | tog' → toğ |
| harf + `'` | **ʼ** (tutuq belgisi) | ma'no → maʼno |

Katta harflar ham işlaydi: `SH` / `Sh` → Ş, `O'` → Ö. `ng` özgarmaydi.

## Nimalar bor

- **[`dist/yangi_ozbek.kmp`](https://github.com/egamberdievnodirjon030-ops/farzandim/raw/ccr-b8bea070-9rcpnz/dist/yangi_ozbek.kmp)**: klaviatura. Bepul [Keyman](https://keyman.com/downloads/) dasturi orqali Windows, macOS, Linux, Android va iPhone/iPad'da işlaydi. Word, Telegram, brauzer va boşqa har qanday dasturda yozasiz.
- **`web/`**: brauzerda işlaydigan sahifa, heç narsa örnatiş şart emas. Yozganingiz darhol ögiriladi, eski yozuvdagi matnni joylab (Ctrl+V) ham ögiriş mumkin.
- **`keyman/yangi_ozbek/`**: klaviatura manba kodi. Qoidalar `source/yangi_ozbek.kmn` faylida, telefon tugmalari `source/yangi_ozbek.keyman-touch-layout` faylida.

## Örnatiş

**Windows, macOS, Linux**

1. [keyman.com/downloads](https://keyman.com/downloads/) saytidan Keyman'ni örnating.
2. `yangi_ozbek.kmp` faylini ikki marta bosing va «Install»ni tanlang.
3. Windows'da klaviaturani `Win` + `Space` bilan almaştiring.

**Android**

1. Play Market'dan «Keyman» ilovasini örnating va uni tizim klaviaturasi sifatida yoqing.
2. Keyman'da: Settings → Install Keyboard or Dictionary → Install from local file → `yangi_ozbek.kmp`.
3. Yozayotganda globus tugmasi bilan «Yangi Özbek Lotin»ni tanlang.

**iPhone, iPad**

1. App Store'dan «Keyman» ilovasini örnating.
2. `yangi_ozbek.kmp` faylini Fayllar ilovasida oçing → Ulaşiş → Keyman.
3. Sozlamalar → Umumiy → Klaviatura → Klaviaturalar → Keyman'ni qöşing.

## Qöşimça imkoniyatlar

| | Kompyuter | Telefon |
|---|---|---|
| Yangi harfni bitta tugma bilan | `AltGr` + `S` `C` `O` `G` (Shift bilan: Ş Ç Ö Ğ) | yuqori qatordagi Ö Ğ Ş Ç tugmalari |
| Ögirmasdan «sh» / «ch» (email, havola) | `s`, keyin `AltGr` + `H` | `s` yoki `c`ni bosib turing → «sh» / «ch» |
| Oddiy apostrof `'` | `AltGr` + `'` | `ʼ` tugmasini bosib turing → `'` |

`AltGr`: klaviaturadagi öng `Alt` tugmasi (Mac'da öng `Option`).

## Dasturçilar uçun

```sh
npm install
npm test   # klaviaturani yiğadi (dist/yangi_ozbek.kmp) va testlarni işga tuşiradi
```

`tests/keyboard.test.mjs` kompilyatsiya qilingan klaviaturaga tugma bosişlarini yuborib tekşiradi, `tests/converter.test.mjs` esa veb-sahifadagi ögirgiçni tekşiradi.

Alifbo qoidalari 2026-yil 21-oktabrda imzolangan qonun asosida (Oʻ → Ö, Gʻ → Ğ, Sh → Ş, Ch → Ç).
