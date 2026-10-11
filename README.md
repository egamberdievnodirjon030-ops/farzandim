# farzandim

## Claude Code sub-agentlari

Bu repoda Claude Code ichida ishlaydigan sub-agentlar bor. Ular `.claude/agents/`
papkasida joylashgan. Claude Code shu papkadagi agentlarni avtomatik yuklaydi.

| Agent | Vazifasi | Kodni o'zgartiradimi? |
|---|---|---|
| `code-reviewer` | O'zgarishlarni xatolar, xavfsizlik va o'qilishi bo'yicha tekshiradi | Yo'q |
| `debugger` | Xatoning asl sababini topadi va tuzatadi | Ha |
| `test-writer` | Testlar yozadi va ishga tushiradi | Ha (faqat testlarni) |
| `docs-writer` | README va boshqa hujjatlarni o'zbek tilida yozadi | Ha (faqat hujjatlarni) |
| `researcher` | Internetdan ma'lumot qidiradi va manbalar bilan xulosa beradi | Yo'q |

### Qanday ishlatiladi

Claude o'zi vazifaga mos agentni tanlaydi. Agentni nomi bilan ham chaqirish mumkin:

```
code-reviewer agentidan foydalanib oxirgi o'zgarishlarni tekshir
```

```
debugger agenti bilan shu xatoni tuzat: TypeError: Cannot read properties of undefined
```

Barcha agentlarni ko'rish va boshqarish uchun Claude Code ichida `/agents`
buyrug'ini yozing.

### Yangi agent qo'shish

`.claude/agents/` papkasida yangi `.md` fayl yarating:

```markdown
---
name: agent-nomi
description: Agent nima qiladi va qachon ishlatilishi kerak.
tools: Read, Grep, Glob
---

Agentga ko'rsatmalar (system prompt).
```

- `name` — faqat kichik lotin harflari va chiziqcha (`-`).
- `description` — Claude agentni qachon chaqirishni shu matnga qarab hal qiladi,
  shuning uchun aniq yozing.
- `tools` — agent foydalanishi mumkin bo'lgan vositalar. Yozilmasa, agent
  barcha vositalardan foydalanadi.
- `model` (ixtiyoriy) — `sonnet`, `opus`, `haiku` yoki `inherit`. Yozilmasa,
  asosiy sessiya modeli ishlatiladi.
