"""Ota-ona interfeysining rus va ingliz tilidagi tarjimalari. Kalit — koddagi o'zbekcha matn.

Yangi matn qo'shilganda: kodda tr("...") yoki N_("...") bilan o'rang va shu yerga tarjimasini qo'shing.
Tarjimasi yo'q matn o'zbekcha ko'rsatiladi. {nomli} o'rinlar va HTML teglar tarjimada ham bo'lishi shart.
"""

TR: dict[str, dict[str, str]] = {
    # HEMIS akademik qarzdorlar ro'yxati
    "HEMIS ro'yxati": {'ru': 'список HEMIS', 'en': 'HEMIS list'},
    "HEMIS akademik qarzdorlar ro'yxatiga ko'ra farzandingizda quyidagi fanlardan akademik qarz bor:": {
        'ru': 'Согласно списку академических задолженностей HEMIS, у вашего ребёнка есть академическая задолженность по следующим предметам:',
        'en': 'According to the HEMIS academic debt list, your child has academic debt in the following subjects:'},
    "Quyidagi fanlardan akademik qarzdorlik yopildi (HEMIS ro'yxatida endi yo'q):": {
        'ru': 'Академическая задолженность по следующим предметам закрыта (в списке HEMIS их больше нет):',
        'en': 'Academic debt has been cleared in the following subjects (no longer in the HEMIS list):'},
    "Jami akademik qarz: {n} ta fan. Qayta topshirish tartibi bo'yicha kurs koordinatoriga murojaat qiling.": {
        'ru': 'Всего академических задолженностей: {n}. По порядку пересдачи обращайтесь к куратору курса.',
        'en': 'Total academic debt: {n} subject(s). Please contact the course coordinator about retakes.'},
    "{n} kredit": {'ru': '{n} кредит(а)', 'en': '{n} credits'},
    # ilova rejimi: qisqa bildirishnomalar
    "📋 {name}: davomatda o'zgarish bo'ldi.": {'ru': '📋 {name}: изменения в посещаемости.', 'en': '📋 {name}: attendance has changed.'},
    "⚠️ {name}: dars qoldirish bo'yicha ogohlantirish.": {'ru': '⚠️ {name}: предупреждение по пропускам занятий.', 'en': '⚠️ {name}: absence warning.'},
    "✅ {name}: davomatda ijobiy o'zgarish.": {'ru': '✅ {name}: положительные изменения в посещаемости.', 'en': '✅ {name}: attendance has improved.'},
    "📝 {name}: baholarda yangilanish bo'ldi.": {'ru': '📝 {name}: обновление оценок.', 'en': '📝 {name}: grades have been updated.'},
    "❗ {name}: akademik qarzdorlik bo'yicha xabar.": {'ru': '❗ {name}: сообщение об академической задолженности.', 'en': '❗ {name}: academic debt notice.'},
    "💰 {name}: to'lov ma'lumotlarida o'zgarish.": {'ru': '💰 {name}: изменения в данных об оплате.', 'en': '💰 {name}: payment information has changed.'},
    "💰 {name}: to'lov muddati yaqinlashmoqda.": {'ru': '💰 {name}: приближается срок оплаты.', 'en': '💰 {name}: payment deadline is approaching.'},
    "📄 {name}: yangi hujjat — «{title}».": {'ru': '📄 {name}: новый документ — «{title}».', 'en': '📄 {name}: new document — “{title}”.'},
    "📢 Kurs koordinatoridan yangi e'lon.": {'ru': '📢 Новое объявление от куратора курса.', 'en': '📢 New announcement from the course coordinator.'},
    "💬 Kurs koordinatoridan javob keldi.": {'ru': '💬 Пришёл ответ от куратора курса.', 'en': '💬 The course coordinator has replied.'},
    "🌙 Kunlik xulosa tayyor.": {'ru': '🌙 Ежедневная сводка готова.', 'en': '🌙 Your daily summary is ready.'},
    "✅ Farzandingiz ma'lumotlari ilovada.": {'ru': '✅ Данные вашего ребёнка — в приложении.', 'en': '✅ Your child’s information is in the app.'},
    "✅ Kurs koordinatori so'rovingizni tasdiqladi: {name}.": {'ru': '✅ Куратор курса подтвердил ваш запрос: {name}.', 'en': '✅ The course coordinator approved your request: {name}.'},
    "❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Kurs koordinatori bilan bevosita bog'laning.": {'ru': '❌ Ваш запрос на привязку ребёнка не подтверждён. Свяжитесь с куратором курса напрямую.', 'en': '❌ Your request to link your child was not approved. Please contact the course coordinator directly.'},
    "Assalomu alaykum! Farzandingizning davomati, baholari, to'lovlari va hujjatlari — ilovada. Bildirishnomalar shu chatga keladi.": {'ru': 'Здравствуйте! Посещаемость, оценки, оплата и документы вашего ребёнка — в приложении. Уведомления будут приходить в этот чат.', 'en': 'Hello! Your child’s attendance, grades, payments and documents are in the app. Notifications will arrive in this chat.'},
    "Ro'yxatdan o'tish uchun ilovani oching — telefon raqamingiz Telegram orqali tasdiqlanadi.": {'ru': 'Чтобы зарегистрироваться, откройте приложение — номер телефона подтверждается через Telegram.', 'en': 'Open the app to register — your phone number is confirmed through Telegram.'},
    "Barcha ma'lumotlar va amallar — ilovada 👇": {'ru': 'Все данные и действия — в приложении 👇', 'en': 'All information and actions are in the app 👇'},
    "✅ Raqamingiz tasdiqlandi ({phone}). Farzandingiz ma'lumotlari — ilovada.": {'ru': '✅ Ваш номер подтверждён ({phone}). Данные вашего ребёнка — в приложении.', 'en': '✅ Your number is confirmed ({phone}). Your child’s information is in the app.'},
    "Raqamingiz ({phone}) universitet bazasida topilmadi. Ilovada farzandingiz ma'lumotlarini kiriting — kurs koordinatori tasdiqlaydi.": {'ru': 'Ваш номер ({phone}) не найден в базе университета. Укажите данные ребёнка в приложении — куратор курса подтвердит.', 'en': 'Your number ({phone}) was not found in the university database. Enter your child’s details in the app — the course coordinator will confirm.'},
    # farzandni bog'lash so'roviga javob (bot va kompyuter versiyasi)
    "✅ Kurs koordinatori so'rovingizni tasdiqladi. Endi <b>{name}</b> ma'lumotlarini ko'rishingiz mumkin: «👨‍🎓 Farzandim» bo'limini oching.": {
        'ru': '✅ Куратор курса подтвердил ваш запрос. Теперь вам доступны данные <b>{name}</b>: откройте раздел «👨‍🎓 Мой ребёнок».',
        'en': '✅ The course coordinator has approved your request. You can now view the data of <b>{name}</b>: open «👨‍🎓 My child».'},
    "❌ Farzandni bog'lash so'rovingiz tasdiqlanmadi. Iltimos, kurs koordinatori bilan bevosita bog'laning.": {
        'ru': '❌ Ваш запрос на привязку ребёнка не подтверждён. Пожалуйста, свяжитесь с куратором курса напрямую.',
        'en': '❌ Your request to link your child was not approved. Please contact the course coordinator directly.'},
    # Telegram Web App tugmalari
    '📱 Ilovada ochish': {
        'ru': '📱 Открыть в приложении',
        'en': '📱 Open in the app'},
    '📱 Ilovani ochish': {
        'ru': '📱 Открыть приложение',
        'en': '📱 Open the app'},
    'qoldirilgan (sababli bilan birga)': {
        'ru': 'пропущено (включая по уважительной причине)',
        'en': 'missed (including excused)'},
    'sababsiz qoldirilgan': {
        'ru': 'пропущено без уважительной причины',
        'en': 'missed without excuse'},
    "HEMIS ma'lumoti, {d} holatiga": {
        'ru': 'данные HEMIS на {d}',
        'en': 'HEMIS data as of {d}'},
    "kunlik davomat bo'yicha": {
        'ru': 'по ежедневной посещаемости',
        'en': 'based on daily attendance'},
    '📏 <b>Dars qoldirish chegaralari</b> (semestr davomida barcha qoldirilgan soatlar):': {
        'ru': '📏 <b>Пороги пропусков занятий</b> (за семестр, все пропущенные часы):',
        'en': '📏 <b>Absence thresholds</b> (per semester, all missed hours):'},
    '📏 <b>Dars qoldirish chegaralari</b> (semestr davomida sababsiz qoldirilgan soatlar):': {
        'ru': '📏 <b>Пороги пропусков занятий</b> (за семестр, часы без уважительной причины):',
        'en': '📏 <b>Absence thresholds</b> (per semester, unexcused hours):'},
    "GPA — o'rtacha o'zlashtirish ko'rsatkichi: fanlar bo'yicha 5 baholik baholarning o'rtachasi (kreditlar bo'lsa — kreditlar bo'yicha tortilgan).": {
        'ru': 'GPA — средний показатель успеваемости: среднее оценок по 5-балльной шкале по всем предметам (если указаны кредиты — взвешенное по кредитам).',
        'en': 'GPA — grade point average: the mean of 5-point grades across subjects (weighted by credits when credits are available).'},
    'Baholash: 90–100 ball — «5», 70–89 — «4», 60–69 — «3», 0–59 — «2» (akademik qarz). Ball 0,5 dan boshlab yuqoriga yaxlitlanadi (69,5 → 70 → «4»).': {
        'ru': 'Оценивание: 90–100 баллов — «5», 70–89 — «4», 60–69 — «3», 0–59 — «2» (академическая задолженность). Баллы от 0,5 округляются вверх (69,5 → 70 → «4»).',
        'en': 'Grading: 90–100 points — “5”, 70–89 — “4”, 60–69 — “3”, 0–59 — “2” (academic debt). Scores of .5 and above are rounded up (69.5 → 70 → “4”).'},
    'Bekor qilindi.': {
        'ru': 'Отменено.',
        'en': 'Cancelled.'},
    "Iltimos, o'zingizning raqamingizni pastdagi tugma orqali yuboring.": {
        'ru': 'Пожалуйста, отправьте свой номер с помощью кнопки ниже.',
        'en': 'Please send your own number using the button below.'},
    "Telefon raqamni o'qib bo'lmadi. Qaytadan urinib ko'ring.": {
        'ru': 'Не удалось прочитать номер телефона. Попробуйте ещё раз.',
        'en': 'Could not read the phone number. Please try again.'},
    "✅ Raqamingiz tasdiqlandi ({phone}).\n\nSizga bog'langan farzand(lar):\n{names}\n\nEndi menyudan bo'lim tanlang yoki farzandingiz ism-familiyasini yozib yuboring.": {
        'ru': '✅ Ваш номер подтверждён ({phone}).\n\nПривязанные к Вам дети:\n{names}\n\nТеперь выберите раздел в меню или напишите имя и фамилию ребёнка.',
        'en': "✅ Your number is confirmed ({phone}).\n\nChildren linked to you:\n{names}\n\nNow choose a section in the menu or type your child's name."},
    'Farzandni tanlang:': {
        'ru': 'Выберите ребёнка:',
        'en': 'Choose a child:'},
    "Raqamingiz ({phone}) universitet bazasida farzandingizga biriktirilmagan ekan.\nUni qo'lda bog'lash mumkin: ma'lumotlarni tekshirib, kurs koordinatori tasdiqlaydi.": {
        'ru': 'Ваш номер ({phone}) в базе университета не привязан к Вашему ребёнку.\nЕго можно привязать вручную: куратор курса проверит данные и подтвердит.',
        'en': 'Your number ({phone}) is not linked to your child in the university database.\nYou can link it manually: the course coordinator will check the details and confirm.'},
    "✍️ Farzandingizning <b>familiyasi va ismini</b> to'liq yozing.\nMasalan: <i>Aliyev Vali</i>\n\nBekor qilish: /bekor": {
        'ru': '✍️ Напишите полностью <b>фамилию и имя</b> ребёнка.\nНапример: <i>Aliyev Vali</i>\n\nОтмена: /bekor',
        'en': "✍️ Type your child's <b>surname and first name</b> in full.\nFor example: <i>Aliyev Vali</i>\n\nCancel: /bekor"},
    'Avval telefon raqamingizni tasdiqlang.': {
        'ru': 'Сначала подтвердите свой номер телефона.',
        'en': 'Please confirm your phone number first.'},
    "Iltimos, familiya va ismni birga yozing (kamida ikki so'z).": {
        'ru': 'Пожалуйста, напишите фамилию и имя вместе (не менее двух слов).',
        'en': 'Please type the surname and first name together (at least two words).'},
    "Endi tasdiqlash uchun farzandingizning <b>tug'ilgan sanasini</b> (masalan <code>05.03.2007</code>) yoki <b>talaba ID raqamini</b> (HEMIS) yozing.": {
        'ru': 'Теперь для подтверждения напишите <b>дату рождения</b> ребёнка (например <code>05.03.2007</code>) или <b>ID студента</b> (HEMIS).',
        'en': "Now, to confirm, type your child's <b>date of birth</b> (e.g. <code>05.03.2007</code>) or <b>student ID</b> (HEMIS)."},
    "Bu talabaning tug'ilgan sanasi universitet bazasida yo'q, shuning uchun sana bo'yicha tekshirib bo'lmaydi. Iltimos, farzandingizning <b>talaba ID raqamini</b> (HEMIS ID — 12 xonali raqam) yozing. Uni farzandingizdan so'rashingiz mumkin.": {
        'ru': 'Даты рождения этого студента нет в базе университета, поэтому проверить по дате нельзя. Пожалуйста, напишите <b>ID студента</b> (HEMIS ID — 12 цифр). Его можно узнать у ребёнка.',
        'en': "This student's date of birth is not in the university database, so it cannot be checked by date. Please type the <b>student ID</b> (HEMIS ID — 12 digits). You can ask your child for it."},
    "Kiritilgan ma'lumotlar bazadagi yozuv bilan mos kelmadi. Iltimos, kurs koordinatori bilan bevosita bog'laning — u raqamingizni farzandingizga biriktirib qo'yadi.": {
        'ru': 'Введённые данные не совпали с записью в базе. Пожалуйста, свяжитесь с куратором курса напрямую — он привяжет Ваш номер к ребёнку.',
        'en': 'The details you entered do not match the database record. Please contact the course coordinator directly — they will link your number to your child.'},
    "Ma'lumotlar mos kelmadi ({n}/3). Familiya va ismni hujjatdagidek qaytadan yozing:": {
        'ru': 'Данные не совпали ({n}/3). Напишите фамилию и имя ещё раз, как в документах:',
        'en': 'The details did not match ({n}/3). Type the surname and first name again as in the documents:'},
    "Bu farzand sizga allaqachon bog'langan.": {
        'ru': 'Этот ребёнок уже привязан к Вам.',
        'en': 'This child is already linked to you.'},
    "Bu farzand bo'yicha so'rovingiz kurs koordinatorida ko'rib chiqilmoqda.": {
        'ru': 'Ваш запрос по этому ребёнку рассматривается куратором курса.',
        'en': 'Your request for this child is being reviewed by the course coordinator.'},
    "Sizda ko'rib chiqilmagan so'rovlar ko'p. Iltimos, javobni kuting.": {
        'ru': 'У Вас много нерассмотренных запросов. Пожалуйста, дождитесь ответа.',
        'en': 'You have too many pending requests. Please wait for a reply.'},
    "✅ So'rovingiz kurs koordinatoriga yuborildi. Tasdiqlangach, sizga shu yerda xabar keladi.": {
        'ru': '✅ Ваш запрос отправлен куратору курса. После подтверждения Вы получите сообщение здесь.',
        'en': '✅ Your request has been sent to the course coordinator. You will be notified here once it is confirmed.'},
    'Iltimos, pastdagi «📱 Telefon raqamni yuborish» tugmasini bosing.': {
        'ru': 'Пожалуйста, нажмите кнопку «📱 Отправить номер телефона» ниже.',
        'en': 'Please press the “📱 Share phone number” button below.'},
    "Assalomu alaykum! 👋\n\n<b>{uni}</b> ota-onalar botiga xush kelibsiz.\n\nBu yerda farzandingiz qaysi kunlarda, qaysi fanlardan darsga qatnashgani yoki qoldirganini, dars jadvali va baholarini ko'rishingiz, kurs koordinatoriga savol yuborishingiz mumkin.\n\n🔐 Farzandingiz ma'lumotlari faqat sizga ko'rinishi uchun avval telefon raqamingizni tasdiqlang — pastdagi tugmani bosing.\n\nℹ️ Bot faqat ota-onalar uchun: talabalar ro'yxatdan o'ta olmaydi.": {
        'ru': 'Здравствуйте! 👋\n\nДобро пожаловать в бот для родителей <b>{uni}</b>.\n\nЗдесь Вы можете видеть, в какие дни и по каким предметам Ваш ребёнок посещал или пропускал занятия, смотреть расписание и оценки, а также задавать вопросы куратору курса.\n\n🔐 Чтобы данные ребёнка были видны только Вам, сначала подтвердите свой номер телефона — нажмите кнопку ниже.\n\nℹ️ Бот только для родителей: студенты не могут зарегистрироваться.',
        'en': "Hello! 👋\n\nWelcome to the <b>{uni}</b> parents' bot.\n\nHere you can see on which days and in which subjects your child attended or missed classes, view the timetable and grades, and send questions to the course coordinator.\n\n🔐 To make sure your child's data is visible only to you, please confirm your phone number first — press the button below.\n\nℹ️ This bot is for parents only: students cannot register."},
    "ℹ️ <b>Botdan foydalanish</b>\n\n• Farzandingiz <b>ism yoki familiyasini</b> yozib yuboring — bot uning sahifasini ochadi.\n• «📊 Davomat» — bugun, hafta, oy, semestr, fanlar kesimida yoki tanlangan sana bo'yicha.\n• «📅 Dars jadvali» — bugungi, ertangi va haftalik darslar.\n• «📝 Baholar» — joriy, oraliq va yakuniy nazorat natijalari.\n• «⚙️ Bildirishnomalar» — dars qoldirilganda darhol xabar, kunlik xulosa va ogohlantirishlar.\n• «✉️ Kurs koordinatoriga savol» — savolingiz kurs koordinatoriga yetkaziladi, javob shu yerga keladi.\n• «📄 Hujjatlar» (farzand sahifasida) — kurs koordinatori yuborgan tushuntirish xatlari, dekan ogohlantirishlari va hayfsanlar (PDF). Yangi hujjat yuborilganda u sizga darhol keladi.\n\n/start — bosh menyu, /bekor — joriy amalni bekor qilish": {
        'ru': 'ℹ️ <b>Как пользоваться ботом</b>\n\n• Напишите <b>имя или фамилию</b> ребёнка — бот откроет его страницу.\n• «📊 Посещаемость» — за сегодня, неделю, месяц, семестр, по предметам или за выбранную дату.\n• «📅 Расписание» — занятия на сегодня, завтра и неделю.\n• «📝 Оценки» — результаты текущего, промежуточного и итогового контроля.\n• «⚙️ Уведомления» — мгновенное сообщение о пропуске, ежедневная сводка и предупреждения.\n• «✉️ Вопрос куратору курса» — Ваш вопрос будет передан куратору, ответ придёт сюда.\n• «📄 Документы» (на странице ребёнка) — объяснительные, предупреждения декана и выговоры (PDF), отправленные куратором. Новый документ приходит Вам сразу.\n\n/start — главное меню, /bekor — отменить текущее действие',
        'en': "ℹ️ <b>How to use the bot</b>\n\n• Type your child's <b>first name or surname</b> — the bot will open their page.\n• “📊 Attendance” — for today, the week, month, semester, by subject or for a chosen date.\n• “📅 Timetable” — classes for today, tomorrow and the week.\n• “📝 Grades” — results of current, midterm and final assessments.\n• “⚙️ Notifications” — instant absence alerts, daily summary and warnings.\n• “✉️ Ask the coordinator” — your question is forwarded to the course coordinator and the reply comes here.\n• “📄 Documents” (on your child's page) — explanatory notes, dean's warnings and reprimands (PDF) sent by the coordinator. New documents are delivered to you immediately.\n\n/start — main menu, /bekor — cancel the current action"},
    "Assalomu alaykum, {name}! Bosh menyu 👇\nFarzandingiz ism-familiyasini yozib yuborsangiz ham bo'ladi.": {
        'ru': 'Здравствуйте, {name}! Главное меню 👇\nМожно также просто написать имя и фамилию ребёнка.',
        'en': "Hello, {name}! Main menu 👇\nYou can also just type your child's name."},
    '👨\u200d🎓 Farzandim:': {
        'ru': '👨\u200d🎓 Мой ребёнок:',
        'en': '👨\u200d🎓 My child:'},
    '👨\u200d🎓 Farzandingizni tanlang:': {
        'ru': '👨\u200d🎓 Выберите ребёнка:',
        'en': '👨\u200d🎓 Choose your child:'},
    "Sizga hali farzand bog'lanmagan.": {
        'ru': 'К Вам пока не привязан ни один ребёнок.',
        'en': 'No child is linked to you yet.'},
    "✅ Til tanlandi: O'zbekcha": {
        'ru': '✅ Язык выбран: Русский',
        'en': '✅ Language set: English'},
    'Bosh menyu 👇': {
        'ru': 'Главное меню 👇',
        'en': 'Main menu 👇'},
    'Dushanba': {
        'ru': 'Понедельник',
        'en': 'Monday'},
    'Seshanba': {
        'ru': 'Вторник',
        'en': 'Tuesday'},
    'Chorshanba': {
        'ru': 'Среда',
        'en': 'Wednesday'},
    'Payshanba': {
        'ru': 'Четверг',
        'en': 'Thursday'},
    'Juma': {
        'ru': 'Пятница',
        'en': 'Friday'},
    'Shanba': {
        'ru': 'Суббота',
        'en': 'Saturday'},
    'Yakshanba': {
        'ru': 'Воскресенье',
        'en': 'Sunday'},
    'qatnashdi': {
        'ru': 'присутствовал(а)',
        'en': 'attended'},
    'sababsiz qoldirdi': {
        'ru': 'пропуск без уважительной причины',
        'en': 'unexcused absence'},
    'sababli qoldirdi': {
        'ru': 'пропуск по уважительной причине',
        'en': 'excused absence'},
    'kechikdi': {
        'ru': 'опоздание',
        'en': 'late'},
    'Tushuntirish xati': {
        'ru': 'Объяснительная записка',
        'en': 'Explanatory note'},
    'Dekan ogohlantirishi': {
        'ru': 'Предупреждение декана',
        'en': "Dean's warning"},
    'Hayfsan': {
        'ru': 'Выговор',
        'en': 'Reprimand'},
    'Rasmiy hujjat': {
        'ru': 'Официальный документ',
        'en': 'Official document'},
    'Dekan nomiga tushuntirish xati': {
        'ru': 'Объяснительная на имя декана',
        'en': 'Explanatory note to the dean'},
    'Talabalar safidan chetlatish': {
        'ru': 'Отчисление из числа студентов',
        'en': 'Expulsion from the university'},
    'Davlat granti': {
        'ru': 'Государственный грант',
        'en': 'State grant'},
    "To'lov-shartnoma": {
        'ru': 'Платный контракт',
        'en': 'Paid contract'},
    "⛔️ Kechirasiz, bu bot faqat <b>ota-onalar</b> uchun mo'ljallangan.\n\nSiz talaba sifatida aniqlandingiz, shuning uchun kirish rad etildi va bu haqda kurs koordinatoriga xabar berildi.\n\nAgar siz ota-ona bo'lsangiz va bu xatolik bo'lsa, kurs koordinatori bilan bog'laning — tekshirgach, kirishga ruxsat beradi.": {
        'ru': '⛔️ Извините, этот бот предназначен только для <b>родителей</b>.\n\nВы определены как студент, поэтому доступ отклонён, и об этом сообщено куратору курса.\n\nЕсли Вы родитель и это ошибка, свяжитесь с куратором курса — после проверки он откроет доступ.',
        'en': '⛔️ Sorry, this bot is intended for <b>parents</b> only.\n\nYou have been identified as a student, so access was denied and the course coordinator has been notified.\n\nIf you are a parent and this is a mistake, please contact the course coordinator — access will be granted after verification.'},
    "⛔️ Bu bot faqat ota-onalar uchun. Sizning kirishingiz yopilgan.\nXatolik bo'lsa, kurs koordinatori bilan bog'laning.": {
        'ru': '⛔️ Этот бот только для родителей. Ваш доступ закрыт.\nЕсли это ошибка, свяжитесь с куратором курса.',
        'en': '⛔️ This bot is for parents only. Your access has been closed.\nIf this is a mistake, please contact the course coordinator.'},
    '👨\u200d🎓 Farzandim': {
        'ru': '👨\u200d🎓 Мой ребёнок',
        'en': '👨\u200d🎓 My child'},
    '📊 Davomat': {
        'ru': '📊 Посещаемость',
        'en': '📊 Attendance'},
    '📅 Dars jadvali': {
        'ru': '📅 Расписание',
        'en': '📅 Timetable'},
    "➕ Farzand qo'shish": {
        'ru': '➕ Добавить ребёнка',
        'en': '➕ Add a child'},
    '📝 Baholar': {
        'ru': '📝 Оценки',
        'en': '📝 Grades'},
    "➕ Farzandni bog'lash": {
        'ru': '➕ Привязать ребёнка',
        'en': '➕ Link a child'},
    "📢 E'lonlar": {
        'ru': '📢 Объявления',
        'en': '📢 Announcements'},
    '📄 Hujjatlar': {
        'ru': '📄 Документы',
        'en': '📄 Documents'},
    '💰 Moliyaviy qarzdorlik': {
        'ru': '💰 Финансовая задолженность',
        'en': '💰 Financial debt'},
    '📚 Akademik qarzdorlik': {
        'ru': '📚 Академическая задолженность',
        'en': '📚 Academic debt'},
    '✉️ Kurs koordinatoriga yozish': {
        'ru': '✉️ Написать куратору курса',
        'en': '✉️ Write to the coordinator'},
    '✉️ Kurs koordinatoriga savol': {
        'ru': '✉️ Вопрос куратору курса',
        'en': '✉️ Ask the coordinator'},
    '💰 Kontraktdan qarzdorlik': {
        'ru': '💰 Задолженность по контракту',
        'en': '💰 Contract debt'},
    '💳 Trimestrdan qarzdorlik': {
        'ru': '💳 Задолженность по триместру',
        'en': '💳 Trimester debt'},
    '🏠 Farzand sahifasi': {
        'ru': '🏠 Страница ребёнка',
        'en': "🏠 Child's page"},
    '⚙️ Bildirishnomalar': {
        'ru': '⚙️ Уведомления',
        'en': '⚙️ Notifications'},
    'Bugun': {
        'ru': 'Сегодня',
        'en': 'Today'},
    'Kecha': {
        'ru': 'Вчера',
        'en': 'Yesterday'},
    'Shu hafta': {
        'ru': 'Эта неделя',
        'en': 'This week'},
    "O'tgan hafta": {
        'ru': 'Прошлая неделя',
        'en': 'Last week'},
    'Shu oy': {
        'ru': 'Этот месяц',
        'en': 'This month'},
    'Semestr boshidan': {
        'ru': 'С начала семестра',
        'en': 'Since semester start'},
    '📚 Fanlar kesimida': {
        'ru': '📚 По предметам',
        'en': '📚 By subject'},
    '❗ Qoldirilgan darslar': {
        'ru': '❗ Пропущенные занятия',
        'en': '❗ Missed classes'},
    '🗓 Sana yoki oraliq tanlash': {
        'ru': '🗓 Выбрать дату или период',
        'en': '🗓 Choose a date or period'},
    "ℹ️ Foydali ma'lumot": {
        'ru': 'ℹ️ Полезная информация',
        'en': 'ℹ️ Useful information'},
    '📊 HEMIS statistikasi va chegaralar': {
        'ru': '📊 Статистика HEMIS и пороги',
        'en': '📊 HEMIS statistics and thresholds'},
    '⬅️ Orqaga': {
        'ru': '⬅️ Назад',
        'en': '⬅️ Back'},
    '🌐 Til': {
        'ru': '🌐 Язык',
        'en': '🌐 Language'},
    'Ertaga': {
        'ru': 'Завтра',
        'en': 'Tomorrow'},
    'Keyingi hafta': {
        'ru': 'Следующая неделя',
        'en': 'Next week'},
    '⬅️ Davomat menyusi': {
        'ru': '⬅️ Меню посещаемости',
        'en': '⬅️ Attendance menu'},
    '⬅️ Jadval menyusi': {
        'ru': '⬅️ Меню расписания',
        'en': '⬅️ Timetable menu'},
    '⬅️ Moliyaviy qarzdorlik': {
        'ru': '⬅️ Финансовая задолженность',
        'en': '⬅️ Financial debt'},
    'Dars qoldirilganda darhol xabar': {
        'ru': 'Мгновенное сообщение о пропуске',
        'en': 'Instant absence alert'},
    'Har kuni kechqurun xulosa': {
        'ru': 'Ежедневная вечерняя сводка',
        'en': 'Daily evening summary'},
    'Muhim ogohlantirishlar: dars qoldirish chegaralari, akademik qarz': {
        'ru': 'Важные предупреждения: пороги пропусков, академическая задолженность',
        'en': 'Important warnings: absence thresholds, academic debt'},
    "Kontrakt va trimestr to'lovi: qarzdorlik va muddat eslatmalari": {
        'ru': 'Оплата контракта и триместра: задолженность и напоминания о сроках',
        'en': 'Contract and trimester payments: debts and deadline reminders'},
    'Farzandingiz ism-familiyasini yozing…': {
        'ru': 'Напишите имя и фамилию ребёнка…',
        'en': "Type your child's name…"},
    '📱 Telefon raqamni yuborish': {
        'ru': '📱 Отправить номер телефона',
        'en': '📱 Share phone number'},
    "Bundan oldingi chegara(lar) ham o'tilgan: {v}.": {
        'ru': 'Предыдущие пороги также превышены: {v}.',
        'en': 'Earlier thresholds have also been exceeded: {v}.'},
    '❗️ Bu eng oxirgi chegara.': {
        'ru': '❗️ Это последний порог.',
        'en': '❗️ This is the final threshold.'},
    '«{subj}» fanidan {n} ta darsning {k} tasi ({p}%) sababsiz qoldirilgan.': {
        'ru': 'По предмету «{subj}» пропущено без уважительной причины {k} из {n} занятий ({p}%).',
        'en': 'In “{subj}”, {k} of {n} classes ({p}%) were missed without excuse.'},
    "Iltimos, zudlik bilan kurs koordinatori bilan bog'laning.": {
        'ru': 'Пожалуйста, срочно свяжитесь с куратором курса.',
        'en': 'Please contact the course coordinator urgently.'},
    "Iltimos, farzandingiz bilan suhbatlashing. Savollar bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozing.": {
        'ru': 'Пожалуйста, поговорите с ребёнком. Если есть вопросы, напишите в раздел «✉️ Вопрос куратору курса».',
        'en': 'Please talk to your child. If you have questions, write via “✉️ Ask the coordinator”.'},
    "⚠️ <b>Dars qoldirish bo'yicha ogohlantirish</b>": {
        'ru': '⚠️ <b>Предупреждение о пропусках занятий</b>',
        'en': '⚠️ <b>Absence warning</b>'},
    '(HEMIS, {d} holatiga)': {
        'ru': '(HEMIS, на {d})',
        'en': '(HEMIS, as of {d})'},
    '📊 <b>Davomat yangilandi</b>': {
        'ru': '📊 <b>Посещаемость обновлена</b>',
        'en': '📊 <b>Attendance updated</b>'},
    'davomat {p}%': {
        'ru': 'посещаемость {p}%',
        'en': 'attendance {p}%'},
    'Kontrakt': {
        'ru': 'Контракт',
        'en': 'Contract'},
    'Trimestr': {
        'ru': 'Триместр',
        'en': 'Trimester'},
    "💰 <b>To'lov bo'yicha eslatma</b>": {
        'ru': '💰 <b>Напоминание об оплате</b>',
        'en': '💰 <b>Payment reminder</b>'},
    "{kind} bo'yicha <b>{sum}</b> qarzdorlik mavjud.": {
        'ru': '{kind}: задолженность <b>{sum}</b>.',
        'en': '{kind}: an outstanding debt of <b>{sum}</b>.'},
    " (muddat o'tgan)": {
        'ru': ' (срок истёк)',
        'en': ' (overdue)'},
    ' (bugun)': {
        'ru': ' (сегодня)',
        'en': ' (today)'},
    ' ({n} kun qoldi)': {
        'ru': ' (осталось дней: {n})',
        'en': ' ({n} days left)'},
    "To'lov muddati: <b>{d}</b>": {
        'ru': 'Срок оплаты: <b>{d}</b>',
        'en': 'Payment deadline: <b>{d}</b>'},
    "Shartnoma summasi: {c}, to'langan: {p}": {
        'ru': 'Сумма контракта: {c}, оплачено: {p}',
        'en': 'Contract amount: {c}, paid: {p}'},
    'kamaydi': {
        'ru': 'уменьшилась',
        'en': 'decreased'},
    'oshdi': {
        'ru': 'увеличилась',
        'en': 'increased'},
    "{d} dagi ma'lumotga nisbatan qarz {way}: {sum}": {
        'ru': 'По сравнению с данными на {d} задолженность {way}: {sum}',
        'en': 'Compared with the data as of {d}, the debt has {way}: {sum}'},
    "🕐 Ma'lumot {t} da yangilangan (buxgalteriya hisoboti {d} holatiga).": {
        'ru': '🕐 Данные обновлены {t} (отчёт бухгалтерии на {d}).',
        'en': '🕐 Data updated on {t} (accounting report as of {d}).'},
    "Batafsil: farzand sahifasi → «💰 Moliyaviy qarzdorlik». Savollar bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozing.": {
        'ru': 'Подробнее: страница ребёнка → «💰 Финансовая задолженность». Если есть вопросы, напишите в раздел «✉️ Вопрос куратору курса».',
        'en': "Details: child's page → “💰 Financial debt”. If you have questions, write via “✉️ Ask the coordinator”."},
    "✅ <b>{kind} to'lovi</b> <i>({d} holatiga)</i>": {
        'ru': '✅ <b>Оплата: {kind}</b> <i>(на {d})</i>',
        'en': '✅ <b>{kind} payment</b> <i>(as of {d})</i>'},
    "Bu bo'yicha qarzdorlik to'liq yopildi. Rahmat!": {
        'ru': 'Задолженность по этому платежу полностью погашена. Спасибо!',
        'en': 'This debt has been fully paid off. Thank you!'},
    '⚠️ <b>Muhim xabar</b>': {
        'ru': '⚠️ <b>Важное сообщение</b>',
        'en': '⚠️ <b>Important notice</b>'},
    'Farzandingiz «{subj}» fanidan 60 balldan past natija qayd etdi.': {
        'ru': 'Ваш ребёнок получил по предмету «{subj}» результат ниже 60 баллов.',
        'en': 'Your child scored below 60 points in “{subj}”.'},
    'Natija: <b>{score}/100 → «2»</b>': {
        'ru': 'Результат: <b>{score}/100 → «2»</b>',
        'en': 'Result: <b>{score}/100 → “2”</b>'},
    '❗ Akademik qarzdorlik yuzaga kelgan.': {
        'ru': '❗ Возникла академическая задолженность.',
        'en': '❗ An academic debt has arisen.'},
    '❗ {n} ta fandan akademik qarzdorlik yuzaga kelgan.': {
        'ru': '❗ Возникла академическая задолженность по предметам: {n}.',
        'en': '❗ Academic debt has arisen in {n} subjects.'},
    "Jami akademik qarz: {n} ta fan. Batafsil: farzand sahifasi → «📚 Akademik qarzdorlik». Qayta topshirish tartibi bo'yicha kurs koordinatoriga murojaat qiling.": {
        'ru': 'Всего академических задолженностей (предметов): {n}. Подробнее: страница ребёнка → «📚 Академическая задолженность». По порядку пересдачи обратитесь к куратору курса.',
        'en': "Total academic debts: {n} subject(s). Details: child's page → “📚 Academic debt”. Please contact the course coordinator about the retake procedure."},
    '✅ <b>Yaxshi xabar</b>': {
        'ru': '✅ <b>Хорошая новость</b>',
        'en': '✅ <b>Good news</b>'},
    '«{subj}» fanidan akademik qarzdorlik yopildi: {score}/100 → «{grade}».': {
        'ru': 'Академическая задолженность по предмету «{subj}» закрыта: {score}/100 → «{grade}».',
        'en': 'The academic debt in “{subj}” has been cleared: {score}/100 → “{grade}”.'},
    'Qolgan akademik qarz: {n} ta fan.': {
        'ru': 'Осталось академических задолженностей (предметов): {n}.',
        'en': 'Remaining academic debts: {n} subject(s).'},
    'Akademik qarzdorlik qolmadi.': {
        'ru': 'Академических задолженностей больше нет.',
        'en': 'No academic debts remain.'},
    '📝 <b>Yangi baholar</b>': {
        'ru': '📝 <b>Новые оценки</b>',
        'en': '📝 <b>New grades</b>'},
    '❗ akademik qarz': {
        'ru': '❗ академическая задолженность',
        'en': '❗ academic debt'},
    "… va yana {n} ta. To'liq ro'yxat «📝 Baholar» bo'limida.": {
        'ru': '… и ещё {n}. Полный список — в разделе «📝 Оценки».',
        'en': '… and {n} more. The full list is in “📝 Grades”.'},
    "🔗 Telefon raqamingiz universitet bazasida topildi va quyidagi farzand(lar)ingiz botga bog'landi:": {
        'ru': '🔗 Ваш номер телефона найден в базе университета, и к боту привязаны Ваши дети:',
        'en': '🔗 Your phone number was found in the university database, and the following children have been linked to the bot:'},
    'Endi ularning davomati va jadvalini kuzatishingiz mumkin.': {
        'ru': 'Теперь Вы можете следить за их посещаемостью и расписанием.',
        'en': 'You can now follow their attendance and timetable.'},
    '{n} ta darsdan {a} tasida qatnashdi': {
        'ru': 'посетил(а) {a} из {n} занятий',
        'en': 'attended {a} of {n} classes'},
    '{p}-juftlik': {
        'ru': '{p}-я пара',
        'en': 'period {p}'},
    '🌙 <b>Kunlik xulosa — {d}</b>': {
        'ru': '🌙 <b>Итоги дня — {d}</b>',
        'en': '🌙 <b>Daily summary — {d}</b>'},
    '🔔 <b>Davomat xabari</b>': {
        'ru': '🔔 <b>Сообщение о посещаемости</b>',
        'en': '🔔 <b>Attendance notice</b>'},
    "Savol bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozishingiz mumkin.": {
        'ru': 'Если есть вопросы, напишите в раздел «✉️ Вопрос куратору курса».',
        'en': 'If you have questions, you can write via “✉️ Ask the coordinator”.'},
    "Qaysi farzandingiz bo'yicha?": {
        'ru': 'По какому ребёнку?',
        'en': 'Which child is this about?'},
    "Hozircha kurs koordinatori bog'lanmagan. Keyinroq urinib ko'ring.": {
        'ru': 'Куратор курса пока не подключён. Попробуйте позже.',
        'en': 'No course coordinator is connected yet. Please try again later.'},
    "✉️ <b>{name}</b> bo'yicha savolingizni bitta xabarda yozing. Kurs koordinatori javobi shu yerga keladi.\n\nBekor qilish: /bekor": {
        'ru': '✉️ Напишите вопрос по <b>{name}</b> одним сообщением. Ответ куратора курса придёт сюда.\n\nОтмена: /bekor',
        'en': "✉️ Write your question about <b>{name}</b> in a single message. The coordinator's reply will come here.\n\nCancel: /bekor"},
    "⚙️ <b>Bildirishnomalar</b>\n\nQaysi xabarlarni olishni xohlaysiz? Tugmani bosib yoqing yoki o'chiring.": {
        'ru': '⚙️ <b>Уведомления</b>\n\nКакие сообщения Вы хотите получать? Нажмите кнопку, чтобы включить или выключить.',
        'en': '⚙️ <b>Notifications</b>\n\nWhich messages would you like to receive? Tap a button to turn it on or off.'},
    '🧑\u200d🏫 <b>Kurs koordinatorlari</b>': {
        'ru': '🧑\u200d🏫 <b>Кураторы курса</b>',
        'en': '🧑\u200d🏫 <b>Course coordinators</b>'},
    "Bu ma'lumot sizga bog'lanmagan.": {
        'ru': 'Эти данные не привязаны к Вам.',
        'en': 'This information is not linked to you.'},
    'Hujjat topilmadi yoki u sizga tegishli emas.': {
        'ru': 'Документ не найден или не относится к Вам.',
        'en': 'The document was not found or does not belong to you.'},
    "🗓 Sanani <b>KK.OO.YYYY</b> ko'rinishida yozing, masalan <code>15.09.2026</code>.\nOraliq uchun ikki sana: <code>01.09.2026 - 20.09.2026</code>\n\nBekor qilish: /bekor": {
        'ru': '🗓 Напишите дату в формате <b>ДД.ММ.ГГГГ</b>, например <code>15.09.2026</code>.\nДля периода — две даты: <code>01.09.2026 - 20.09.2026</code>\n\nОтмена: /bekor',
        'en': '🗓 Type the date as <b>DD.MM.YYYY</b>, e.g. <code>15.09.2026</code>.\nFor a period, two dates: <code>01.09.2026 - 20.09.2026</code>\n\nCancel: /bekor'},
    'Sana tushunilmadi. Masalan: <code>15.09.2026</code> yoki <code>01.09.2026 - 20.09.2026</code>': {
        'ru': 'Дата не распознана. Например: <code>15.09.2026</code> или <code>01.09.2026 - 20.09.2026</code>',
        'en': 'Date not recognised. For example: <code>15.09.2026</code> or <code>01.09.2026 - 20.09.2026</code>'},
    'Oraliq juda katta. Iltimos, 200 kundan oshmaydigan davrni kiriting.': {
        'ru': 'Период слишком большой. Пожалуйста, укажите период не более 200 дней.',
        'en': 'The period is too long. Please enter a period of no more than 200 days.'},
    'Farzand topilmadi. Qaytadan tanlang: «👨\u200d🎓 Farzandim».': {
        'ru': 'Ребёнок не найден. Выберите снова: «👨\u200d🎓 Мой ребёнок».',
        'en': 'Child not found. Choose again: “👨\u200d🎓 My child”.'},
    'Tanlangan davr': {
        'ru': 'Выбранный период',
        'en': 'Selected period'},
    "ℹ️ <b>Foydali ma'lumot</b>\n\nBu bot orqali farzandingizning darslarga qatnashishi, dars jadvali va baholarini kuzatib borishingiz mumkin. Ma'lumotlar universitetning HEMIS tizimidan kurs koordinatori tomonidan muntazam yuklab boriladi, shuning uchun eng so'nggi darslar bir necha soat kechikib ko'rinishi mumkin.\n\n<b>Belgilar:</b> ✅ qatnashdi, ❌ sababsiz qoldirdi, 🟡 sababli qoldirdi, ⏰ kechikdi, ⚪ ma'lumot hali kiritilmagan, 📘 rejadagi dars.\n\n<b>Qidiruv:</b> farzandingizning ism yoki familiyasini yozib yuborsangiz, bot uning sahifasini ochadi (lotin va kirill yozuvi ham qabul qilinadi).\n\nSavollaringiz bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limidan yozing.": {
        'ru': 'ℹ️ <b>Полезная информация</b>\n\nС помощью этого бота Вы можете следить за посещаемостью, расписанием и оценками ребёнка. Данные регулярно загружает куратор курса из системы HEMIS университета, поэтому самые последние занятия могут появляться с задержкой в несколько часов.\n\n<b>Обозначения:</b> ✅ присутствовал(а), ❌ пропуск без уважительной причины, 🟡 пропуск по уважительной причине, ⏰ опоздание, ⚪ данные ещё не внесены, 📘 запланированное занятие.\n\n<b>Поиск:</b> напишите имя или фамилию ребёнка — бот откроет его страницу (принимается латиница и кириллица).\n\nЕсли есть вопросы, напишите в раздел «✉️ Вопрос куратору курса».',
        'en': "ℹ️ <b>Useful information</b>\n\nWith this bot you can follow your child's class attendance, timetable and grades. The data is regularly uploaded by the course coordinator from the university's HEMIS system, so the most recent classes may appear with a delay of a few hours.\n\n<b>Symbols:</b> ✅ attended, ❌ unexcused absence, 🟡 excused absence, ⏰ late, ⚪ not yet recorded, 📘 scheduled class.\n\n<b>Search:</b> type your child's first name or surname and the bot will open their page (Latin and Cyrillic are both accepted).\n\nIf you have questions, write via “✉️ Ask the coordinator”."},
    "Avval /start orqali ro'yxatdan o'ting.": {
        'ru': 'Сначала зарегистрируйтесь через /start.',
        'en': 'Please register first via /start.'},
    'Yoqildi ✅': {
        'ru': 'Включено ✅',
        'en': 'Turned on ✅'},
    "O'chirildi": {
        'ru': 'Выключено',
        'en': 'Turned off'},
    "Farzand topilmadi. Qaytadan urinib ko'ring.": {
        'ru': 'Ребёнок не найден. Попробуйте ещё раз.',
        'en': 'Child not found. Please try again.'},
    "Sizda javob kutilayotgan savollar ko'p. Iltimos, avvalgilariga javobni kuting.": {
        'ru': 'У Вас много вопросов без ответа. Пожалуйста, дождитесь ответа на предыдущие.',
        'en': 'You have many unanswered questions. Please wait for replies to the earlier ones.'},
    '✅ Savolingiz kurs koordinatoriga yuborildi. Javob shu yerga keladi.': {
        'ru': '✅ Ваш вопрос отправлен куратору курса. Ответ придёт сюда.',
        'en': '✅ Your question has been sent to the course coordinator. The reply will come here.'},
    "Savol saqlandi, lekin hozir kurs koordinatoriga yetkazib bo'lmadi. Keyinroq ko'rib chiqiladi.": {
        'ru': 'Вопрос сохранён, но сейчас его не удалось доставить куратору курса. Он будет рассмотрен позже.',
        'en': 'Your question was saved but could not be delivered to the coordinator right now. It will be reviewed later.'},
    "Iltimos, savolingizni matn ko'rinishida yozing. Bekor qilish: /bekor": {
        'ru': 'Пожалуйста, напишите вопрос текстом. Отмена: /bekor',
        'en': 'Please write your question as text. Cancel: /bekor'},
    "Avval ro'yxatdan o'ting: /start": {
        'ru': 'Сначала зарегистрируйтесь: /start',
        'en': 'Please register first: /start'},
    '📊 <b>Davomat</b> — davrni tanlang:': {
        'ru': '📊 <b>Посещаемость</b> — выберите период:',
        'en': '📊 <b>Attendance</b> — choose a period:'},
    '📅 <b>Dars jadvali</b> — kunni tanlang:': {
        'ru': '📅 <b>Расписание</b> — выберите день:',
        'en': '📅 <b>Timetable</b> — choose a day:'},
    'talab qilinmaydi (davlat granti)': {
        'ru': 'не требуется (государственный грант)',
        'en': 'not required (state grant)'},
    'mavjud emas ✅': {
        'ru': 'отсутствует ✅',
        'en': 'none ✅'},
    "ma'lumot yo'q": {
        'ru': 'нет данных',
        'en': 'no data'},
    "🎓 O'zlashtirish ko'rsatkichi (GPA): <b>{v}</b> / 5": {
        'ru': '🎓 Показатель успеваемости (GPA): <b>{v}</b> / 5',
        'en': '🎓 Grade point average (GPA): <b>{v}</b> / 5'},
    "🎓 O'zlashtirish ko'rsatkichi (GPA): ma'lumot yo'q": {
        'ru': '🎓 Показатель успеваемости (GPA): нет данных',
        'en': '🎓 Grade point average (GPA): no data'},
    "⚠️ <b>E'tibor talab qiladigan masalalar: {n} ta</b>": {
        'ru': '⚠️ <b>Вопросы, требующие внимания: {n}</b>',
        'en': '⚠️ <b>Issues requiring attention: {n}</b>'},
    "✅ E'tibor talab qiladigan masala yo'q": {
        'ru': '✅ Вопросов, требующих внимания, нет',
        'en': '✅ No issues requiring attention'},
    '📍 <b>Bugun:</b> {n} ta darsdan {a} tasida qatnashgan': {
        'ru': '📍 <b>Сегодня:</b> посетил(а) {a} из {n} занятий',
        'en': '📍 <b>Today:</b> attended {a} of {n} classes'},
    "📄 Rasmiy hujjatlar: {n} ta — «📄 Hujjatlar» bo'limida": {
        'ru': '📄 Официальные документы: {n} — в разделе «📄 Документы»',
        'en': '📄 Official documents: {n} — in “📄 Documents”'},
    '🕐 Oxirgi yangilanish: {dt}': {
        'ru': '🕐 Последнее обновление: {dt}',
        'en': '🕐 Last updated: {dt}'},
    "Kerakli bo'limni tanlang 👇": {
        'ru': 'Выберите нужный раздел 👇',
        'en': 'Choose a section 👇'},
    'rejada': {
        'ru': 'по плану',
        'en': 'scheduled'},
    "ma'lumot hali kiritilmagan": {
        'ru': 'данные ещё не внесены',
        'en': 'not yet recorded'},
    "Bu davr uchun davomat ma'lumoti hali kiritilmagan.": {
        'ru': 'Данные о посещаемости за этот период ещё не внесены.',
        'en': 'Attendance data for this period has not been recorded yet.'},
    '📈 <b>Umumiy natija</b>': {
        'ru': '📈 <b>Общий итог</b>',
        'en': '📈 <b>Overall result</b>'},
    'Qayd etilgan darslar: {n}': {
        'ru': 'Учтено занятий: {n}',
        'en': 'Classes recorded: {n}'},
    '✅ Qatnashgan: {n} ({p})': {
        'ru': '✅ Присутствовал(а): {n} ({p})',
        'en': '✅ Attended: {n} ({p})'},
    ', shundan kechikkan: {n}': {
        'ru': ', из них опозданий: {n}',
        'en': ', of which late: {n}'},
    "✅ qatnashdi · ❌ sababsiz · 🟡 sababli · ⏰ kechikdi · ⚪ ma'lumot kiritilmagan": {
        'ru': '✅ присутствовал(а) · ❌ без уважительной причины · 🟡 по уважительной причине · ⏰ опоздание · ⚪ данные не внесены',
        'en': '✅ attended · ❌ unexcused · 🟡 excused · ⏰ late · ⚪ not recorded'},
    "Bu kunda dars yo'q yoki ma'lumot hali kiritilmagan.": {
        'ru': 'В этот день занятий нет или данные ещё не внесены.',
        'en': 'No classes on this day, or the data has not been recorded yet.'},
    "Bu davrda dars yoki davomat ma'lumoti topilmadi.": {
        'ru': 'За этот период занятия или данные о посещаемости не найдены.',
        'en': 'No classes or attendance data found for this period.'},
    '📚 <b>Fanlar kesimida</b>': {
        'ru': '📚 <b>По предметам</b>',
        'en': '📚 <b>By subject</b>'},
    '❗ <b>Qoldirilgan / kechikilgan darslar ({n} ta)</b>': {
        'ru': '❗ <b>Пропущенные занятия и опоздания ({n})</b>',
        'en': '❗ <b>Missed classes and late arrivals ({n})</b>'},
    '… va yana {n} ta (oldingi sanalar)': {
        'ru': '… и ещё {n} (более ранние даты)',
        'en': '… and {n} more (earlier dates)'},
    'guruh: {g}': {
        'ru': 'группа: {g}',
        'en': 'group: {g}'},
    "📚 <b>Fanlar bo'yicha davomat</b> ({d1} — {d2})": {
        'ru': '📚 <b>Посещаемость по предметам</b> ({d1} — {d2})',
        'en': '📚 <b>Attendance by subject</b> ({d1} — {d2})'},
    "Davomat ma'lumotlari hali yuklanmagan.": {
        'ru': 'Данные о посещаемости ещё не загружены.',
        'en': 'Attendance data has not been uploaded yet.'},
    '⚠️ — sababsiz qoldirilgan darslar ulushi {p}% dan oshgan fan': {
        'ru': '⚠️ — предмет, где доля пропусков без уважительной причины превышает {p}%',
        'en': '⚠️ — subject where the share of unexcused absences exceeds {p}%'},
    '🗓 Semestr boshidan ({d} dan)': {
        'ru': '🗓 С начала семестра (с {d})',
        'en': '🗓 Since the start of the semester (from {d})'},
    '✅ Qoldirilgan yoki kechikilgan dars qayd etilmagan.': {
        'ru': '✅ Пропусков и опозданий не зафиксировано.',
        'en': '✅ No absences or late arrivals recorded.'},
    '{n}-kurs': {
        'ru': '{n}-й курс',
        'en': 'year {n}'},
    "Talabaning guruhi bazada ko'rsatilmagan.": {
        'ru': 'Группа студента не указана в базе.',
        'en': "The student's group is not specified in the database."},
    '{s}-oqim': {
        'ru': 'поток {s}',
        'en': 'stream {s}'},
    "dars yo'q yoki jadval hali yuklanmagan.": {
        'ru': 'занятий нет или расписание ещё не загружено.',
        'en': 'no classes, or the timetable has not been uploaded yet.'},
    '🎯 — farzandingizning tanlov fani yoki ikkinchi chet tili (shaxsiy jadval). Qolganlari — guruhning asosiy fanlari.': {
        'ru': '🎯 — предмет по выбору или второй иностранный язык Вашего ребёнка (личное расписание). Остальные — основные предметы группы.',
        'en': "🎯 — your child's elective or second foreign language (personal timetable). The rest are the group's core subjects."},
    'Farzandingizga tanlov fanlari va ikkinchi chet tili hali biriktirilmagan — jadvalda faqat guruhning asosiy fanlari.': {
        'ru': 'Вашему ребёнку ещё не назначены предметы по выбору и второй иностранный язык — в расписании только основные предметы группы.',
        'en': "Electives and a second foreign language have not yet been assigned to your child — the timetable shows only the group's core subjects."},
    'Farzandingizga tanlov fanlari va ikkinchi chet tili hali biriktirilmagan — jadvalda guruhning barcha darslari (parallel darslar bilan).': {
        'ru': 'Вашему ребёнку ещё не назначены предметы по выбору и второй иностранный язык — в расписании все занятия группы (включая параллельные).',
        'en': "Electives and a second foreign language have not yet been assigned to your child — the timetable shows all of the group's classes (including parallel ones)."},
    '📝 <b>Baholar</b>': {
        'ru': '📝 <b>Оценки</b>',
        'en': '📝 <b>Grades</b>'},
    'Baholar hali yuklanmagan.': {
        'ru': 'Оценки ещё не загружены.',
        'en': 'Grades have not been uploaded yet.'},
    '{n}-semestr': {
        'ru': '{n}-й семестр',
        'en': 'semester {n}'},
    "📢 Hozircha e'lonlar yo'q.": {
        'ru': '📢 Объявлений пока нет.',
        'en': '📢 No announcements yet.'},
    "📢 <b>So'nggi e'lonlar</b>": {
        'ru': '📢 <b>Последние объявления</b>',
        'en': '📢 <b>Latest announcements</b>'},
    '🗓 Sana: {d}': {
        'ru': '🗓 Дата: {d}',
        'en': '🗓 Date: {d}'},
    "🔒 Hujjatdagi boshqa talabalarning ma'lumotlari maxfiylik uchun yopilgan.": {
        'ru': '🔒 Данные других студентов в документе скрыты в целях конфиденциальности.',
        'en': "🔒 Other students' details in the document have been hidden for privacy."},
    "Savollaringiz bo'lsa, «✉️ Kurs koordinatoriga savol» bo'limi orqali yozishingiz mumkin.": {
        'ru': 'Если есть вопросы, напишите в раздел «✉️ Вопрос куратору курса».',
        'en': 'If you have questions, you can write via “✉️ Ask the coordinator”.'},
    '📄 <b>Rasmiy hujjatlar</b>': {
        'ru': '📄 <b>Официальные документы</b>',
        'en': '📄 <b>Official documents</b>'},
    "Hozircha kurs koordinatori tomonidan yuborilgan hujjatlar yo'q.": {
        'ru': 'Куратор курса пока не отправлял документов.',
        'en': 'The course coordinator has not sent any documents yet.'},
    'Hujjatni ochish uchun pastdagi tugmani bosing.': {
        'ru': 'Чтобы открыть документ, нажмите кнопку ниже.',
        'en': 'Tap a button below to open a document.'},
    "HEMIS bo'yicha": {
        'ru': 'По данным HEMIS',
        'en': 'According to HEMIS'},
    '({d} holatiga):': {
        'ru': '(на {d}):',
        'en': '(as of {d}):'},
    '(sababli {n})': {
        'ru': '(по уважительной причине {n})',
        'en': '(excused {n})'},
    "HEMIS ma'lumoti hali yuklanmagan.": {
        'ru': 'Данные HEMIS ещё не загружены.',
        'en': 'HEMIS data has not been uploaded yet.'},
    '📊 <b>HEMIS davomat statistikasi</b>': {
        'ru': '📊 <b>Статистика посещаемости HEMIS</b>',
        'en': '📊 <b>HEMIS attendance statistics</b>'},
    'HEMIS davomat statistikasi': {
        'ru': 'Статистика посещаемости HEMIS',
        'en': 'HEMIS attendance statistics'},
    "HEMIS statistikasida kun va fanlar bo'yicha tafsilot yo'q — faqat jami ko'rsatkichlar.": {
        'ru': 'В статистике HEMIS нет детализации по дням и предметам — только общие показатели.',
        'en': 'HEMIS statistics have no breakdown by day or subject — only totals.'},
    'Kontraktdan qarzdorlik': {
        'ru': 'Задолженность по контракту',
        'en': 'Contract debt'},
    'Trimestrdan qarzdorlik': {
        'ru': 'Задолженность по триместру',
        'en': 'Trimester debt'},
    "To'lov shakli: <b>{v}</b>": {
        'ru': 'Форма оплаты: <b>{v}</b>',
        'en': 'Payment basis: <b>{v}</b>'},
    "To'lov shakli: ko'rsatilmagan": {
        'ru': 'Форма оплаты: не указана',
        'en': 'Payment basis: not specified'},
    '💰 <b>Moliyaviy qarzdorlik</b>': {
        'ru': '💰 <b>Финансовая задолженность</b>',
        'en': '💰 <b>Financial debt</b>'},
    "Davlat granti asosida o'qiydi — kontrakt to'lovi talab qilinmaydi.": {
        'ru': 'Обучается на основе государственного гранта — оплата контракта не требуется.',
        'en': 'Studies on a state grant — no contract payment is required.'},
    'muddat: {d}': {
        'ru': 'срок: {d}',
        'en': 'deadline: {d}'},
    'Leksiya': {
        'ru': 'Лекция',
        'en': 'Lecture'},
    'Seminar': {
        'ru': 'Семинар',
        'en': 'Seminar'},
    "Batafsil ma'lumot uchun turini tanlang 👇": {
        'ru': 'Выберите вид задолженности для подробностей 👇',
        'en': 'Choose a type for details 👇'},
    "✅ Qarzdorlik mavjud emas: farzandingiz oxirgi hisobotdagi qarzdorlar ro'yxatida yo'q.": {
        'ru': '✅ Задолженности нет: Вашего ребёнка нет в списке должников последнего отчёта.',
        'en': "✅ No debt: your child is not on the debtors' list in the latest report."},
    "🕐 Ma'lumot {dt} da yangilangan.": {
        'ru': '🕐 Данные обновлены {dt}.',
        'en': '🕐 Data updated on {dt}.'},
    "Bu bo'yicha ma'lumot hali yuklanmagan.": {
        'ru': 'Данные по этому разделу ещё не загружены.',
        'en': 'No data has been uploaded for this yet.'},
    "{d} holatiga ({y} o'quv yili):": {
        'ru': 'На {d} ({y} учебный год):',
        'en': 'As of {d} ({y} academic year):'},
    '{d} holatiga:': {
        'ru': 'На {d}:',
        'en': 'As of {d}:'},
    'Shartnoma summasi: {v}': {
        'ru': 'Сумма контракта: {v}',
        'en': 'Contract amount: {v}'},
    "To'langan: {v}": {
        'ru': 'Оплачено: {v}',
        'en': 'Paid: {v}'},
    '💰 <b>Qarzdorlik: {v}</b>': {
        'ru': '💰 <b>Задолженность: {v}</b>',
        'en': '💰 <b>Debt: {v}</b>'},
    "✅ Qarzdorlik yo'q": {
        'ru': '✅ Задолженности нет',
        'en': '✅ No debt'},
    "📅 To'lov muddati: <b>{d}</b>": {
        'ru': '📅 Срок оплаты: <b>{d}</b>',
        'en': '📅 Payment deadline: <b>{d}</b>'},
    "muddat o'tgan": {
        'ru': 'срок истёк',
        'en': 'overdue'},
    'bugun': {
        'ru': 'сегодня',
        'en': 'today'},
    '({n} kun qoldi)': {
        'ru': '(осталось дней: {n})',
        'en': '({n} days left)'},
    "Ortiqcha to'langan: {v}": {
        'ru': 'Переплата: {v}',
        'en': 'Overpaid: {v}'},
    'Izoh: {v}': {
        'ru': 'Примечание: {v}',
        'en': 'Note: {v}'},
    "📈 <b>Qarzdorlik o'zgarishi:</b>": {
        'ru': '📈 <b>Изменение задолженности:</b>',
        'en': '📈 <b>Debt history:</b>'},
    "Ma'lumot universitet buxgalteriyasi hisobotidan olingan. Aniqlik kiritish uchun buxgalteriyaga yoki kurs koordinatoriga murojaat qiling.": {
        'ru': 'Данные взяты из отчёта бухгалтерии университета. Для уточнения обратитесь в бухгалтерию или к куратору курса.',
        'en': 'The data comes from the university accounting report. For clarification, please contact the accounting office or the course coordinator.'},
    '📚 <b>Akademik qarzdorlik</b>': {
        'ru': '📚 <b>Академическая задолженность</b>',
        'en': '📚 <b>Academic debt</b>'},
    "Fanlar bo'yicha 100 ballik umumiy baholar hali yuklanmagan.": {
        'ru': 'Итоговые оценки по 100-балльной шкале ещё не загружены.',
        'en': 'Final 100-point grades have not been uploaded yet.'},
    '❗ Jami <b>{n} ta fandan</b> akademik qarzdor:': {
        'ru': '❗ Академическая задолженность по предметам: <b>{n}</b>',
        'en': '❗ Academic debt in <b>{n} subject(s)</b>:'},
    '{s} ball → «2»': {
        'ru': '{s} из 100 → «2»',
        'en': '{s} points → “2”'},
    "✅ Akademik qarzdorlik yo'q.": {
        'ru': '✅ Академической задолженности нет.',
        'en': '✅ No academic debt.'},
    "🎓 <b>O'zlashtirish ko'rsatkichi (GPA): {v} / 5</b>": {
        'ru': '🎓 <b>Показатель успеваемости (GPA): {v} / 5</b>',
        'en': '🎓 <b>Grade point average (GPA): {v} / 5</b>'},
    "(kreditlar bo'yicha)": {
        'ru': '(по кредитам)',
        'en': '(credit-weighted)'},
    '📊 <b>Baholar (5 baholik tizimda):</b>': {
        'ru': '📊 <b>Оценки (по 5-балльной шкале):</b>',
        'en': '📊 <b>Grades (5-point scale):</b>'},
    '👨\u200d🎓 <b>Farzandim:</b> {name}': {
        'ru': '👨\u200d🎓 <b>Мой ребёнок:</b> {name}',
        'en': '👨\u200d🎓 <b>My child:</b> {name}'},
    "🧾 To'lov shakli: <b>{v}</b>": {
        'ru': '🧾 Форма оплаты: <b>{v}</b>',
        'en': '🧾 Payment basis: <b>{v}</b>'},
    "🧾 To'lov shakli: ma'lumot yo'q": {
        'ru': '🧾 Форма оплаты: нет данных',
        'en': '🧾 Payment basis: no data'},
    '🧑\u200d🏫 Kurs koordinatori: {v}': {
        'ru': '🧑\u200d🏫 Куратор курса: {v}',
        'en': '🧑\u200d🏫 Course coordinator: {v}'},
    '📋 <b>Umumiy holat</b>': {
        'ru': '📋 <b>Общее состояние</b>',
        'en': '📋 <b>Overview</b>'},
    "⚪ Davomat: ma'lumot yo'q": {
        'ru': '⚪ Посещаемость: нет данных',
        'en': '⚪ Attendance: no data'},
    '📚 Akademik qarzdorlik: <b>{n} ta fan</b> — {names}': {
        'ru': '📚 Академическая задолженность: <b>{n}</b> — {names}',
        'en': '📚 Academic debt: <b>{n} subject(s)</b> — {names}'},
    "📚 Akademik qarzdorlik: yo'q ✅": {
        'ru': '📚 Академическая задолженность: нет ✅',
        'en': '📚 Academic debt: none ✅'},
    "📚 Akademik qarzdorlik: ma'lumot yo'q": {
        'ru': '📚 Академическая задолженность: нет данных',
        'en': '📚 Academic debt: no data'},
    'Kontrakt qarzdorligi': {
        'ru': 'Задолженность по контракту',
        'en': 'Contract debt'},
    'Trimestr qarzdorligi': {
        'ru': 'Задолженность по триместру',
        'en': 'Trimester debt'},
    'Bir nechta mos farzand topildi, tanlang:': {
        'ru': 'Найдено несколько подходящих детей, выберите:',
        'en': 'Several matching children were found, choose one:'},
    "Bu ism sizga bog'langan farzandlar orasida topilmadi.\nQuyidagilardan birini tanlang yoki yangi farzandni bog'lang:": {
        'ru': 'Такое имя не найдено среди привязанных к Вам детей.\nВыберите одного из них или привяжите нового ребёнка:',
        'en': 'This name was not found among the children linked to you.\nChoose one of them or link a new child:'},
    "Noma'lum buyruq. Bosh menyu: /start, yordam: /yordam": {
        'ru': 'Неизвестная команда. Главное меню: /start, помощь: /yordam',
        'en': 'Unknown command. Main menu: /start, help: /yordam'},
    "Bot faqat matnli xabarlar va menyu tugmalari bilan ishlaydi. Kurs koordinatoriga fayl yoki savol yubormoqchi bo'lsangiz, «✉️ Kurs koordinatoriga savol» bo'limidan foydalaning yoki kurs koordinatori bilan bevosita bog'laning.": {
        'ru': 'Бот работает только с текстовыми сообщениями и кнопками меню. Если Вы хотите отправить куратору файл или вопрос, воспользуйтесь разделом «✉️ Вопрос куратору курса» или свяжитесь с куратором напрямую.',
        'en': 'The bot works only with text messages and menu buttons. To send a file or a question to the coordinator, use “✉️ Ask the coordinator” or contact the coordinator directly.'},
    '📚 Akademik qarz: {n} ta fan ({names})': {
        'ru': '📚 Академическая задолженность, предметов: {n} ({names})',
        'en': '📚 Academic debt: {n} subject(s) ({names})'},
    'Kontrakt qarzi: {v}': {
        'ru': 'Долг по контракту: {v}',
        'en': 'Contract debt: {v}'},
    'Trimestr qarzi: {v}': {
        'ru': 'Долг по триместру: {v}',
        'en': 'Trimester debt: {v}'},
    "muddat ({d}) o'tgan": {
        'ru': 'срок ({d}) истёк',
        'en': 'deadline ({d}) has passed'},
    "so'm": {
        'ru': 'сум',
        'en': 'UZS'},
    '{n} chegarasi': {
        'ru': 'порог {n}',
        'en': '{n} threshold'},
    'Semestrda {label}: <b>{h}</b>': {
        'ru': 'За семестр {label}: <b>{h}</b>',
        'en': 'This semester {label}: <b>{h}</b>'},
    'Chegara: {n} — <b>{a}</b>': {
        'ru': 'Порог: {n} — <b>{a}</b>',
        'en': 'Threshold: {n} — <b>{a}</b>'},
    '{n} — {a}': {
        'ru': '{n} — {a}',
        'en': '{n} — {a}'},
    'Semestrda {h} dars qoldirilgan — {a}': {
        'ru': 'За семестр пропущено {h} — {a}',
        'en': '{h} missed this semester — {a}'},
    'Davomat: <b>{pct}</b> ({label}: {h})': {
        'ru': 'Посещаемость: <b>{pct}</b> ({label}: {h})',
        'en': 'Attendance: <b>{pct}</b> ({label}: {h})'},
    '❌ Sababsiz qoldirilgan: {h}': {
        'ru': '❌ Пропущено без уважительной причины: {h}',
        'en': '❌ Missed without excuse: {h}'},
    '🟡 Sababli qoldirilgan: {h}': {
        'ru': '🟡 Пропущено по уважительной причине: {h}',
        'en': '🟡 Missed with excuse: {h}'},
    'Jami sababsiz: {a}, sababli: {b}': {
        'ru': 'Всего без уважительной причины: {a}, по уважительной: {b}',
        'en': 'Total unexcused: {a}, excused: {b}'},
    'qatnashgan {a}, qoldirgan {b}': {
        'ru': 'присутствовал(а): {a}, пропустил(а): {b}',
        'en': 'attended {a}, missed {b}'},
    "📈 <b>O'zgarish</b> ({label}):": {
        'ru': '📈 <b>Изменения</b> ({label}):',
        'en': '📈 <b>Changes</b> ({label}):'},
    'Semestr boshidan buyon {label}: <b>{h}</b>': {
        'ru': 'С начала семестра {label}: <b>{h}</b>',
        'en': 'Since the start of the semester {label}: <b>{h}</b>'},
    "Universitet ichki tartibiga ko'ra {n} va undan ko'p dars qoldirilganda qo'llaniladigan chora: <b>{a}</b>.": {
        'ru': 'Согласно внутреннему распорядку университета, при пропуске {n} и более применяется мера: <b>{a}</b>.',
        'en': "Under the university's internal regulations, the measure applied for missing {n} or more is: <b>{a}</b>."},
    'Keyingi chegara: {n} — {a}.': {
        'ru': 'Следующий порог: {n} — {a}.',
        'en': 'Next threshold: {n} — {a}.'},
    '{d} dan beri yana <b>{h}</b> dars qoldirilgan.': {
        'ru': 'С {d} пропущено ещё <b>{h}</b>.',
        'en': 'Since {d}, another <b>{h}</b> have been missed.'},
    '{d} dan beri yana <b>{h}</b> dars sababsiz qoldirilgan.': {
        'ru': 'С {d} ещё <b>{h}</b> пропущено без уважительной причины.',
        'en': 'Since {d}, another <b>{h}</b> have been missed without excuse.'},
    'Semestr boshidan jami: {h}': {
        'ru': 'Всего с начала семестра: {h}',
        'en': 'Total since semester start: {h}'},
    'Keyingi chegara: {n} — {a}, qolgan: {left}': {
        'ru': 'Следующий порог: {n} — {a}, осталось: {left}',
        'en': 'Next threshold: {n} — {a}, remaining: {left}'},
    'Keyingi chegara: {n} — {a}, qolgan: {left}.': {
        'ru': 'Следующий порог: {n} — {a}, осталось: {left}.',
        'en': 'Next threshold: {n} — {a}, remaining: {left}.'},
    "✅ <b>Davomat o'zgardi</b>": {
        'ru': '✅ <b>Посещаемость изменилась</b>',
        'en': '✅ <b>Attendance updated</b>'},
    "Farzandingiz {n} va undan ko'p dars qoldirgani uchun «{a}» talab qilingan edi.": {
        'ru': 'Так как Ваш ребёнок пропустил {n} и более, требовалось: «{a}».',
        'en': 'Because your child had missed {n} or more, “{a}” was required.'},
    'Qoldirilgan darslarning {e} sababli deb topildi.': {
        'ru': 'Из пропущенных занятий {e} признаны пропущенными по уважительной причине.',
        'en': '{e} of the missed classes have been recognised as excused.'},
    "Davomat ma'lumotlari tuzatildi.": {
        'ru': 'Данные о посещаемости исправлены.',
        'en': 'The attendance data has been corrected.'},
    'Sababsiz qoldirilgan darslar: {old} → <b>{new}</b>.': {
        'ru': 'Пропущено без уважительной причины: {old} → <b>{new}</b>.',
        'en': 'Missed without excuse: {old} → <b>{new}</b>.'},
    'Endi bu hech qaysi chegaradan past — «{a}» talab qilinmaydi.': {
        'ru': 'Теперь это ниже всех порогов — «{a}» больше не требуется.',
        'en': 'This is now below every threshold — “{a}” is no longer required.'},
    'Endi amaldagi chegara: {n} — {a}.': {
        'ru': 'Теперь действует порог: {n} — {a}.',
        'en': 'The threshold now in effect: {n} — {a}.'},
    "Chegara o'zgarmadi: {n} — {a}.": {
        'ru': 'Порог не изменился: {n} — {a}.',
        'en': 'The threshold is unchanged: {n} — {a}.'},
    '📈 {name}: davomat va baholar dinamikasi': {
        'ru': '📈 {name}: динамика посещаемости и оценок',
        'en': '📈 {name}: attendance and grade trends'},
    '📈 Dinamika': {
        'ru': '📈 Динамика',
        'en': '📈 Trends'},
    'batafsil: «📈 Dinamika»': {
        'ru': 'подробнее: «📈 Динамика»',
        'en': 'details: “📈 Trends”'},
    '📊 <b>Davomat</b>': {
        'ru': '📊 <b>Посещаемость</b>',
        'en': '📊 <b>Attendance</b>'},
    'shu hafta': {
        'ru': 'эта неделя',
        'en': 'this week'},
    '{period}: <b>{p}%</b>, sababsiz qoldirilgan: {h}': {
        'ru': '{period}: <b>{p}%</b>, пропущено без уважительной причины: {h}',
        'en': '{period}: <b>{p}%</b>, missed without excuse: {h}'},
    "o'tgan haftaga nisbatan": {
        'ru': 'по сравнению с прошлой неделей',
        'en': 'compared with last week,'},
    'oldingi davrga nisbatan ({p})': {
        'ru': 'по сравнению с предыдущим периодом ({p})',
        'en': 'compared with the previous period ({p}),'},
    '📚 <b>Baholar</b>': {
        'ru': '📚 <b>Оценки</b>',
        'en': '📚 <b>Grades</b>'},
    'oxirgi oyda': {
        'ru': 'за последний месяц',
        'en': 'over the last month'},
    '{d} dan beri': {
        'ru': 'с {d}',
        'en': 'since {d}'},
    "Taqqoslash uchun hali oldingi davr ma'lumoti yo'q.": {
        'ru': 'Для сравнения пока нет данных за предыдущий период.',
        'en': 'There is no data for an earlier period to compare with yet.'},
    'Sababsiz qoldirilgan darslar: {old} → {new}.': {
        'ru': 'Пропущено без уважительной причины: {old} → {new}.',
        'en': 'Missed without excuse: {old} → {new}.'},
    "Taqqoslash uchun baholar tarixi hali yo'q — keyingi yuklashlardan so'ng ko'rinadi.": {
        'ru': 'Истории оценок для сравнения пока нет — она появится после следующих загрузок.',
        'en': 'There is no grade history to compare with yet — it will appear after the next uploads.'},
    "{when} fanlar bo'yicha ball o'zgarmadi.": {
        'ru': '{when} баллы по предметам не изменились.',
        'en': '{when}, subject scores have not changed.'},
    "❗ «{subj}» fanidan o'rtacha ball {when} tushib ketdi.": {
        'ru': '❗ Средний балл по предмету «{subj}» {when} снизился.',
        'en': '❗ The average score in “{subj}” has dropped {when}.'},
    "👍 «{subj}» fanidan ball {when} ko'tarildi.": {
        'ru': '👍 Балл по предмету «{subj}» {when} вырос.',
        'en': '👍 The score in “{subj}” has risen {when}.'},
    '🎓 GPA: {old} → <b>{new}</b> ({when}).': {
        'ru': '🎓 GPA: {old} → <b>{new}</b> ({when}).',
        'en': '🎓 GPA: {old} → <b>{new}</b> ({when}).'},
    '{n} ta fanda ball pasaydi': {
        'ru': 'балл снизился по предметам: {n}',
        'en': 'score dropped in {n} subject(s)'},
    'Dinamika: {v}': {
        'ru': 'Динамика: {v}',
        'en': 'Trends: {v}'},
    '60 — chegara': {
        'ru': '60 — порог',
        'en': '60 — pass mark'},
    "Fanlar bo'yicha ball (100 ballik)": {
        'ru': 'Баллы по предметам (из 100)',
        'en': 'Subject scores (out of 100)'},
    '{base} davomat {d}% ga yaxshilandi ({old}% → {new}%).': {
        'ru': '{base} посещаемость улучшилась на {d}% ({old}% → {new}%).',
        'en': '{base} attendance improved by {d}% ({old}% → {new}%).'},
    'davomat {sign}{d}%': {
        'ru': 'посещаемость {sign}{d}%',
        'en': 'attendance {sign}{d}%'},
    "Davomat, % (haftalar bo'yicha)": {
        'ru': 'Посещаемость, % (по неделям)',
        'en': 'Attendance, % (by week)'},
    'Davomat, % (yuklashlar orasidagi davrlar)': {
        'ru': 'Посещаемость, % (периоды между загрузками)',
        'en': 'Attendance, % (periods between uploads)'},
    'hozir': {
        'ru': 'сейчас',
        'en': 'now'},
    '{base} davomat {d}% ga pasaydi ({old}% → {new}%).': {
        'ru': '{base} посещаемость снизилась на {d}% ({old}% → {new}%).',
        'en': '{base} attendance dropped by {d}% ({old}% → {new}%).'},
    "{base} davomat deyarli o'zgarmadi ({new}%).": {
        'ru': '{base} посещаемость почти не изменилась ({new}%).',
        'en': '{base} attendance barely changed ({new}%).'},
    'bir oy oldin': {
        'ru': 'месяц назад',
        'en': 'a month ago'},
    "📈 <b>Dinamika</b> — o'qishdagi o'zgarishlar": {
        'ru': '📈 <b>Динамика</b> — изменения в учёбе',
        'en': "📈 <b>Trends</b> — changes in your child's studies"},
    "Kechirasiz, texnik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring.": {
        'ru': 'Приносим извинения, произошла техническая ошибка. Пожалуйста, повторите попытку немного позже.',
        'en': 'We apologise — a technical error occurred. Please try again a little later.'},
    'Bugun yakshanba — kelasi hafta jadvali.': {
        'ru': 'Сегодня воскресенье — расписание на следующую неделю.',
        'en': "Today is Sunday — next week's timetable."},
    # GPA chegarasi (kursdan kursga o'tish)
    "🎓 GPA {v} — {min} dan past: kursdan kursga o'tmaydi": {
        'ru': '🎓 GPA {v} — ниже {min}: не переводится на следующий курс',
        'en': '🎓 GPA {v} — below {min}: will not advance to the next year'},
    "🔴 GPA {min} dan past — talaba kursdan kursga o'tkazilmaydi.": {
        'ru': '🔴 GPA ниже {min} — студент не переводится на следующий курс.',
        'en': '🔴 GPA is below {min} — the student will not advance to the next year.'},
    "Umumiy GPA {min} dan past bo'lsa, talaba kursdan kursga o'tkazilmaydi (GPA yaxlitlanmaydi).": {
        'ru': 'Если общий GPA ниже {min}, студент не переводится на следующий курс (GPA не округляется).',
        'en': 'If the overall GPA is below {min}, the student does not advance to the next year (GPA is not rounded).'},
    # Qoldirilgan darslar — faqat HEMIS statistikasi bo'lsa
    "❗ <b>Qoldirilgan darslar — HEMIS ma'lumoti</b>": {
        'ru': '❗ <b>Пропущенные занятия — данные HEMIS</b>', 'en': '❗ <b>Missed classes — HEMIS data</b>'},
    "{a} — {b}": {'ru': '{a} — {b}', 'en': '{a} — {b}'},
    "{b} gacha": {'ru': 'до {b}', 'en': 'until {b}'},
    "sababsiz {a}": {'ru': 'без причины {a}', 'en': 'unexcused {a}'},
    "sababli {b}": {'ru': 'по уважительной причине {b}', 'en': 'excused {b}'},
    "ℹ️ HEMIS umumiy statistikasida har bir darsning sanasi va fani bo'lmaydi. Kurs koordinatori kunlik davomatni yuklasa, darslar sana va fan bo'yicha ko'rinadi.": {
        'ru': 'ℹ️ В общей статистике HEMIS нет даты и предмета каждого занятия. Когда координатор загрузит ежедневную посещаемость, занятия будут видны по датам и предметам.',
        'en': 'ℹ️ HEMIS summary statistics do not include the date and subject of each class. Once the coordinator uploads daily attendance, classes will be shown by date and subject.'},
}
