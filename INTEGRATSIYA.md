# JIDU ota-onalar boti ↔ «Manage»: integratsiya bo'yicha qisqa talablar

Bu hujjat Manage tizimi dasturchilari uchun. Bot universitet tizimidan faqat **davomat** va **dars jadvalini**
oladi (faqat o'qish). Boshqa ma'lumotlar (baholar, to'lovlar va h.k.) so'ralmaydi.

Ma'lumot formati va maydon nomlari bo'yicha qat'iy talab yo'q: bot JSON, CSV yoki Excel'ni qabul qiladi,
yozuvlar ro'yxatini, sahifalashni va maydonlarni nomiga qarab o'zi taniydi. Quyidagilar faqat tavsiya.

## Bizga kerak

1. **API manzili** (masalan `https://manage.uwed.uz/api/v1`).
2. **Faqat o'qish huquqli API kaliti**: `Authorization: Bearer <kalit>`, `X-API-Key: <kalit>` kabi sarlavha,
   so'rov parametri yoki login:parol (HTTP Basic).
3. Ikkita endpoint (GET):

| Ma'lumot | Tavsiya etilgan so'rov | Har bir yozuvda bo'lishi kerak |
|---|---|---|
| Davomat | `GET /attendance?date_from=2026-10-01&date_to=2026-10-07&page=1` | talaba ID (HEMIS ID) yoki F.I.Sh. + guruh; sana; juftlik raqami (yoki boshlanish vaqti); fan; holat (keldi / sababsiz / sababli / kechikdi yoki true/false) |
| Dars jadvali | `GET /schedule?date_from=…&date_to=…` (yoki haftalik jadval) | guruh; hafta kuni (yoki dars sanasi); juftlik raqami (yoki boshlanish vaqti); fan |

Bo'lsa yaxshi (ixtiyoriy): mashg'ulot turi, o'qituvchi, xona, boshlanish/tugash vaqti, kichik guruh (seminar),
toq/juft hafta, qoldirilgan soat.

Davomat endpointi tanlangan oraliqdagi **barcha** belgilangan yozuvlarni (yoki hech bo'lmaganda barcha
qoldirishlarni) qaytarishi kerak. O'qituvchi qoldirishni o'chirib to'g'rilasa, keyingi so'rovda u yozuv
bo'lmaydi va bot uni «keldi» deb yangilaydi.

Namuna javob (har qanday shunga o'xshash tuzilma ham bo'ladi):

```json
{"data": {"items": [
  {"student": {"student_id_number": "350241100707", "name": "ALIYEV VALI"},
   "group": {"name": "3-1a-24"}, "subject": {"name": "Matematika"},
   "lesson_date": 1791140400, "lessonPair": {"code": "2", "start_time": "10:00"},
   "employee": {"name": "Karimov A."}, "trainingType": {"name": "Ma'ruza"},
   "absent_on": 2, "explicable": false}
 ], "pagination": {"page": 1, "pageCount": 4}}}
```

Bot davomatni har daqiqada, jadvalni har 15 daqiqada so'raydi (ikkalasi ham sozlanadi). Bir so'rov oxirgi
7 kunni, jadval esa joriy va keyingi haftani oladi.

## Ixtiyoriy: real vaqt (webhook)

Davomat belgilanishi bilan Manage o'zi yuborishi mumkin. Shunda ota-onaga xabar bir necha soniyada boradi.

```
POST https://<bot manzili>/api/integration/attendance     (jadval uchun: /api/integration/schedule)
X-Integration-Token: <biz beradigan maxfiy kalit>
Content-Type: application/json

[ { ...yuqoridagi kabi yozuv... }, ... ]
```

Javob `200 {"ok": true, "records": N, "changed": true}` bo'ladi. Noto'g'ri kalit bilan `401`, noma'lum tur
bilan `404` qaytadi. CSV yoki Excel faylni ham yuborish mumkin (tana sifatida yoki multipart).

## Xavfsizlik

- Kalit faqat bot serveridagi `.env` faylida saqlanadi. Jurnalga va xabarlarga yozilmaydi.
- Bot faqat GET so'rov yuboradi, Manage'dagi ma'lumotni o'zgartirmaydi.
- Webhook kaliti doimiy vaqtda solishtiriladi va noto'g'ri urinishlar jurnalga yoziladi.
