/* JIDU — Ota-onalar uchun davomat boti: Telegram Web App.
   Hech qanday tashqi kutubxonasiz: hash-router, uch tilli matnlar, ekranlar funksiyalar ko'rinishida. */
const JIDU_MAIN = () => {
'use strict';
// Telegram ichida (Mini App) — initData bor; aks holda telefon ilovasi (Android/iOS) yoki oddiy brauzer:
// kirish Telegram botda tasdiqlanadi va seans kaliti qurilmada saqlanadi (Authorization: Bearer)
const tg = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData ? window.Telegram.WebApp : null;
const DEV = new URLSearchParams(location.search).has('dev');
const NATIVE = /JiduApp/.test(navigator.userAgent);  // Android/iOS ilovasi (Capacitor) foydalanuvchi agentiga qo'shadi
const store = { get: k => { try { return localStorage.getItem(k); } catch (_) { return null; } },
  set: (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (_) { /* */ } } };
const $app = document.getElementById('app');
const S = { me: null, lang: 'uz', child: null, cache: {}, timer: null, staffCourse: localStorage.getItem('staffCourse') || '' };

/* ================================================================ matnlar */
const T = {
  uz: {
    home: 'Asosiy', schedule: 'Jadval', attendance: 'Davomat', grades: 'Baholar', messages: 'Xabarlar',
    menu: 'Menyu', subj_att: 'Davomat', subj_att_hint: 'Semestr boshidan shu fan bo‘yicha: {n} ta dars', unexc_n: '{n} ta sababsiz', notes_all: 'Barcha xabarlar', notes_unread: 'O‘qilmagan', notes_updated: 'Oxirgi yangilanish: {t}', note_new: 'Yangi', notes_read_all: 'Hammasi o‘qildi', notifications: 'Bildirishnomalar', finance: 'To‘lovlar', documents: 'Hujjatlar', trends: 'Dinamika',
    news: 'E’lonlar', settings: 'Sozlamalar', info: 'Foydali ma’lumot', group: 'Guruh', year: 'Kurs', faculty: 'Fakultet',
    yearN: '{n}-kurs', student: 'Talaba', ok_title: 'Hammasi joyida', ok_sub: 'Davomat, baholar va to‘lovlar bo‘yicha muammo yo‘q.',
    issues: '{n} ta masala e’tibor talab qiladi', gpa: 'GPA', of5: '5 dan', gpa_hint: 'o‘zlashtirish ko‘rsatkichi', acad: 'Akademik qarz', none: 'yo‘q',
    subjectsN: '{n} ta fan', mln_unit: 'mln so‘m', debt_clear_s: 'qarz yo‘q', kontrakt: 'Kontrakt', trimestr: 'Trimestr', no_debt: 'Mavjud emas', grant: 'Davlat granti',
    no_data: 'Ma’lumot yo‘q', unexcused: 'sababsiz', excused: 'sababli', today_lessons: 'Bugungi darslar', no_lessons_today: 'Bugun dars yo‘q',
    all: 'Hammasi', coordinator: 'Kurs koordinatori', write: 'Yozish', call: 'Qo‘ng‘iroq', updated: 'Yangilangan: {t}',
    since_start: 'Semestr boshidan', next_level: 'Keyingi chegara: {a} — yana {left}', max_level: 'Eng yuqori chegaraga yetgan',
    hemis_missed: 'HEMIS ma’lumoti bo‘yicha', hemis_missed_note: 'HEMIS umumiy statistikasida har bir darsning sanasi va fani bo‘lmaydi. Kurs koordinatori kunlik davomatni yuklasa, darslar sana va fan bo‘yicha shu yerda ko‘rinadi.', until: '{d} gacha', unexcused_n: 'Sababsiz: {a}', excused_n: 'sababli: {b}',
    gpa_low: '{min} dan past — kursdan kursga o‘tmaydi',
    back: 'Ortga',
    surveys: 'So‘rovnomalar', survey: 'So‘rovnoma', regs: 'Ichki nizomlar', regs_sub: 'Universitet ichki tartib qoidalari va nizomlari', answer_now: 'Javob berish', q_n: '{n} ta savol', closes: '{d} gacha', submit_survey: 'Yuborish', survey_thanks: 'Rahmat! Javobingiz qabul qilindi.', survey_closed: 'So‘rovnoma yopilgan', required_q: 'Iltimos, belgilangan savollarga javob bering', your_answer: 'Javobingiz…', answered: 'Javob berilgan', no_surveys: 'Hozircha so‘rovnoma yo‘q', no_regs: 'Nizomlar hali joylanmagan', edit_answer: 'Javobni o‘zgartirish', anon: 'Anonim: ismingiz va farzandingiz ko‘rsatilmaydi', scale_lo: 'yomon', scale_hi: 'a’lo', choose_many: 'bir nechtasini tanlash mumkin', waiting_you: 'Fikringizni kutyapmiz', open_link: 'Ochish', new_note: 'Yangi bildirishnoma', poll_done: 'Javob berganlar',
    dyn_first: 'birinchi ma’lumot', dyn_same: 'o‘zgarmadi', more: 'Batafsil',
    dyn_none: 'Oxirgi yuklashlarda o‘zgarish bo‘lmadi — o‘zgarish bo‘lsa, shu yerda ko‘rinadi.',
    by_upload: 'Yuklangan ma’lumotlar bo‘yicha', by_semester: 'Semestrlar bo‘yicha', avg_score: 'o‘rtacha ball',
    portal: 'Ota-onalar portali', my_children: 'Farzandlarim', sec_study: 'O‘qish', sec_contact: 'Aloqa', sec_uni: 'Universitet', subj_h: 'Fan', score_h: 'Ball', grade_h: 'Baho', credits_h: 'Kredit', week_view: 'Haftalik jadval', today_word: 'Bugun', no_lessons_short: 'Dars yo‘q', hero_title: 'Farzandingizning o‘qishi — bir oynada', hero_1: 'Davomat, baholar va to‘lovlar — har kuni yangilanadi', hero_2: 'Kurs koordinatori bilan to‘g‘ridan-to‘g‘ri yozishma', hero_3: 'Bildirishnomalar Telegram’ga darhol keladi', hero_secure: 'Parolsiz va xavfsiz: kirish har safar Telegram’da tasdiqlanadi', missed_list: 'Qoldirilgan darslar', date_h: 'Sana', status_h: 'Holat', pair_h: 'Juftlik',
    login_sub: 'Ilovaga kirish Telegram orqali tasdiqlanadi — parol kerak emas.', login_tg: 'Telegram orqali kirish', login_note: 'Bildirishnomalar Telegram’dagi botga keladi.', login_pin: 'Telegram’da botni oching va shu raqamni tanlang:', login_open_tg: 'Telegram’ni ochish', login_wait: 'Tasdiqlashingiz kutilmoqda…', login_expired: 'Kirish vaqti tugadi. Qaytadan urinib ko‘ring.', login_cancelled: 'Kirish bekor qilindi.', cancel: 'Bekor qilish', app_word: 'ilova', browser_word: 'brauzer', logout: 'Shu qurilmadan chiqish', logout_q: 'Ilovadan chiqasizmi? Qayta kirish Telegram orqali tasdiqlanadi.', devices_hint: 'Barcha qurilmalar ro‘yxati — botda /qurilmalar', step_phone: 'Telefon', step_child: 'Farzand', step_confirm: 'Tasdiqlash', phone_safe: 'Raqamingizni Telegram o‘zi tasdiqlaydi — uni qo‘lda yozish shart emas. Raqam universitet ro‘yxatida bo‘lsa, farzandingiz darhol ulanadi.', child_title: 'Farzandingizni toping', child_sub: 'Raqamingiz universitet ro‘yxatida topilmadi. Farzandingiz ma’lumotlarini hujjatdagidek kiriting.', birth_date: 'Tug‘ilgan sanasi', or_hemis: 'yoki talaba ID (HEMIS) bilan', hemis_id: 'Talaba ID (HEMIS)', find_child: 'Davom etish', confirm_title: 'Oxirgi qadam — tasdiqlash', confirm_student_sub: 'Havolani farzandingizga yuboring: u o‘z telefon raqami bilan sizni tasdiqlaydi, so‘ng kurs koordinatori yakuniy tasdiqlaydi. Shunda begona odam sizning farzandingizga ulana olmaydi.', send_to_child: 'Farzandimga yuborish', copy_link: 'Havolani nusxalash', link_copied: 'Havola nusxalandi', wait_coord: 'Farzandingiz tasdiqlagach, so‘rov kurs koordinatoriga boradi', no_phone_hint: 'Raqamni bilmasangiz — so‘rovni kurs koordinatori o‘zi tekshirib tasdiqlaydi.', child_phone: 'Farzandingizning telefon raqami', child_phone_sub: 'Farzandingiz raqami universitet bazasida yo‘q. Uning Telegram’dagi raqamini kiriting — keyin farzandingiz shu raqam bilan sizni tasdiqlaydi.', phone_err_bad_phone: 'Raqam noto‘g‘ri. Masalan: +998 90 123 45 67', phone_err_own_phone: 'Bu sizning raqamingiz. Farzandingizning o‘z raqamini kiriting.', phone_err_phone_taken: 'Bu raqam boshqa odamga tegishli. Farzandingizning o‘z raqamini kiriting.', phone_err_not_found: 'So‘rov topilmadi yoki allaqachon ko‘rib chiqilgan.', phone_err_has_phone: 'Farzandingiz raqami bazada bor — havolani yuboring.', student_ok_wait: 'Farzandingiz sizni tasdiqladi. Endi kurs koordinatorining yakuniy tasdig‘i kutilmoqda — tasdiqlangach, shu yerda ochiladi.', coord_only: 'So‘rovingizni kurs koordinatori tekshirib tasdiqlaydi — tasdiqlangach, shu yerda ochiladi.', add_child: 'Boshqa farzandni qo‘shish', too_many_tries: 'Urinishlar soni tugadi. Ertaga qayta urinib ko‘ring yoki kurs koordinatori bilan bog‘laning.', share_text: 'Assalomu alaykum! Ota-onalar botida sizni tasdiqlashim kerak — havolani oching va «Ha» ni bosing:', waiting: 'kutilmoqda', done_step: 'bajarildi',
    levels: 'Dars qoldirish chegaralari', missed: 'Qoldirilgan darslar', by_subject: 'Fanlar bo‘yicha', by_week: 'Haftalar bo‘yicha',
    keldi: 'Keldi', kelmadi: 'Kelmadi', sababli: 'Sababli', kechikdi: 'Kechikdi', nothing_missed: 'Qoldirilgan dars yo‘q',
    this_week: 'Shu hafta', prev: 'Oldingi', next: 'Keyingi', next_limit: 'Keyingi', toq: 'toq hafta', juft: 'juft hafta', no_lessons: 'Bu kuni dars yo‘q',
    pairN: '{n}-juftlik', semN: '{n}-semestr', credits: 'kredit', debt_subject: 'Akademik qarz', gpa_long: 'O‘zlashtirish ko‘rsatkichi',
    contract_pay: 'Kontrakt to‘lovi', trimester_pay: 'Trimestr to‘lovi', debt: 'Qarzdorlik', paid: 'To‘langan', contract: 'Shartnoma',
    deadline: 'To‘lov muddati', days_left: '{n} kun qoldi', overdue: 'Muddati o‘tgan', history: 'Tarix', grant_note: 'Davlat granti — kontrakt to‘lovi talab qilinmaydi',
    not_loaded: 'Hisobot hali yuklanmagan', send_chat: 'Chatga yuborish', sent_chat: 'Hujjat chatga yuborildi', no_docs: 'Hujjatlar yo‘q',
    no_docs_sub: 'Rasmiy hujjat chiqqanda shu yerda paydo bo‘ladi va Telegram’ga ham keladi.', month_ago: 'bir oy oldin', now: 'hozir',
    no_trends: 'Taqqoslash uchun ma’lumot hali yetarli emas', type_msg: 'Xabar yozing…', msg_sent: 'Xabar yuborildi',
    no_msgs: 'Hali xabar yo‘q', no_msgs_sub: 'Savolingizni yozing — javob shu yerda va Telegram’da keladi.', mark_read: 'Hammasini o‘qildi',
    nav_att: 'Davomat', nav_msg: 'Xabarlar', debts_title: 'Akademik qarzdorlik', from_hemis: 'HEMIS qarzdorlar ro‘yxati', debt_score: '{s} ball → «2»', sem_n: '{n}-semestr', credits_n: '{n} kredit', debts_help: 'Qayta topshirish tartibi bo‘yicha kurs koordinatoriga murojaat qiling.', ask_coord: 'Kurs koordinatoriga yozish', no_debts: 'Akademik qarzdorlik mavjud emas', open: 'Ochish', theme: 'Mavzu', th_auto: 'Avtomatik', th_light: 'Kunduzgi', th_dark: 'Tungi', pages: 'sahifa', open_doc: 'Ochish', doc_loading: 'Hujjat ochilmoqda…', tap_zoom: 'Kattalashtirish uchun sahifani bosing', no_notes: 'Bildirishnomalar yo‘q', no_notes_sub: 'Dars qoldirilganda, baho qo‘yilganda yoki to‘lov yaqinlashganda shu yerda paydo bo‘ladi.',
    no_news: 'E’lonlar yo‘q', lang: 'Til', flags: 'Qaysi xabarlar kelsin', notify_instant: 'Dars qoldirilganda — darhol',
    notify_daily: 'Kunlik xulosa — kechqurun', notify_warn: 'Muhim ogohlantirishlar', notify_pay: 'To‘lov eslatmalari',
    grade_scale: 'Baholash shkalasi', welcome: 'Assalomu alaykum!', welcome_sub: 'Farzandingizning davomati, baholari va to‘lovlari — bir joyda, o‘z vaqtida.',
    choose_lang: 'Tilni tanlang', confirm_phone: 'Telefon raqamni tasdiqlash', phone_why: 'Raqam farzandingizni universitet bazasidan topish uchun kerak.',
    confirming: 'Tasdiqlanmoqda…', open_in_tg: 'Ilovani Telegram’dagi bot orqali oching.', pending_title: 'Farzandingiz hali topilmadi',
    pending_sub: 'Ma’lumotlarni kiriting — kurs koordinatori tekshirib tasdiqlaydi.', full_name: 'Farzandingizning familiyasi va ismi',
    verify: 'Tug‘ilgan sanasi yoki HEMIS ID', send_request: 'So‘rov yuborish', requested: 'So‘rov kurs koordinatoriga yuborildi. Tasdiqlangach, Telegram’ga xabar keladi.',
    not_matched: 'Ma’lumot mos kelmadi. Familiya va ismni hujjatdagidek yozing.', blocked: 'Bu ilova faqat ota-onalar uchun.',
    error: 'Ulanishda xato yuz berdi.', retry: 'Qayta urinish', saved: 'Saqlandi', choose_child: 'Farzandni tanlang',
    call_tutor: 'Kurs koordinatoriga qo‘ng‘iroq qilish', attention: 'E’tibor talab qiladi', see_all: 'Barchasi', lessonsN: '{n} ta dars',
    percent_note: 'davomat', pairs: '{p} para ({h} soat)', money: '{n} so‘m', today: 'Bugun', yesterday: 'Kecha', you: 'Siz',
    too_many: 'Javob kutilayotgan xabarlar ko‘p. Iltimos, javobni kuting.', uni_student: 'talaba',
  },
  ru: {
    home: 'Главная', schedule: 'Расписание', attendance: 'Посещаемость', grades: 'Оценки', messages: 'Сообщения',
    menu: 'Меню', subj_att: 'Посещаемость', subj_att_hint: 'С начала семестра по этому предмету: занятий {n}', unexc_n: 'без ув. причины: {n}', notes_all: 'Все уведомления', notes_unread: 'Непрочитанные', notes_updated: 'Последнее обновление: {t}', note_new: 'Новое', notes_read_all: 'Все прочитаны', notifications: 'Уведомления', finance: 'Оплата', documents: 'Документы', trends: 'Динамика',
    news: 'Объявления', settings: 'Настройки', info: 'Полезная информация', group: 'Группа', year: 'Курс', faculty: 'Факультет',
    yearN: '{n} курс', student: 'Студент', ok_title: 'Всё в порядке', ok_sub: 'Проблем с посещаемостью, оценками и оплатой нет.',
    issues: 'Требуют внимания: {n}', gpa: 'GPA', of5: 'из 5', gpa_hint: 'средний балл', acad: 'Академ. задолженность', none: 'нет',
    subjectsN: 'предметов: {n}', mln_unit: 'млн сум', debt_clear_s: 'задолженности нет', kontrakt: 'Контракт', trimestr: 'Триместр', no_debt: 'Отсутствует', grant: 'Госгрант',
    no_data: 'Нет данных', unexcused: 'без уважит. причины', excused: 'по уважит. причине', today_lessons: 'Занятия сегодня', no_lessons_today: 'Сегодня занятий нет',
    all: 'Все', coordinator: 'Куратор курса', write: 'Написать', call: 'Позвонить', updated: 'Обновлено: {t}',
    since_start: 'С начала семестра', next_level: 'Следующий порог: {a} — ещё {left}', max_level: 'Достигнут высший порог',
    hemis_missed: 'По данным HEMIS', hemis_missed_note: 'В общей статистике HEMIS нет даты и предмета каждого занятия. Когда координатор загрузит ежедневную посещаемость, занятия появятся здесь по датам и предметам.', until: 'до {d}', unexcused_n: 'Без причины: {a}', excused_n: 'по уваж. причине: {b}',
    gpa_low: 'ниже {min} — не переводится на следующий курс',
    back: 'Назад',
    surveys: 'Опросы', survey: 'Опрос', regs: 'Внутренние положения', regs_sub: 'Правила внутреннего распорядка и положения университета', answer_now: 'Ответить', q_n: 'вопросов: {n}', closes: 'до {d}', submit_survey: 'Отправить', survey_thanks: 'Спасибо! Ваш ответ принят.', survey_closed: 'Опрос закрыт', required_q: 'Пожалуйста, ответьте на отмеченные вопросы', your_answer: 'Ваш ответ…', answered: 'Ответ отправлен', no_surveys: 'Пока опросов нет', no_regs: 'Положения ещё не размещены', edit_answer: 'Изменить ответ', anon: 'Анонимно: ваше имя и имя ребёнка не показываются', scale_lo: 'плохо', scale_hi: 'отлично', choose_many: 'можно выбрать несколько', waiting_you: 'Ждём вашего мнения', open_link: 'Открыть', new_note: 'Новое уведомление', poll_done: 'Ответили',
    dyn_first: 'первые данные', dyn_same: 'без изменений', more: 'Подробнее',
    dyn_none: 'В последних загрузках изменений не было — при изменениях они появятся здесь.',
    by_upload: 'По загруженным данным', by_semester: 'По семестрам', avg_score: 'средний балл',
    portal: 'Портал для родителей', my_children: 'Мои дети', sec_study: 'Учёба', sec_contact: 'Связь', sec_uni: 'Университет', subj_h: 'Предмет', score_h: 'Балл', grade_h: 'Оценка', credits_h: 'Кредиты', week_view: 'Расписание на неделю', today_word: 'Сегодня', no_lessons_short: 'Занятий нет', hero_title: 'Учёба вашего ребёнка — в одном окне', hero_1: 'Посещаемость, оценки и оплата — обновляются каждый день', hero_2: 'Прямая переписка с куратором курса', hero_3: 'Уведомления сразу приходят в Telegram', hero_secure: 'Без пароля и безопасно: вход каждый раз подтверждается в Telegram', missed_list: 'Пропущенные занятия', date_h: 'Дата', status_h: 'Статус', pair_h: 'Пара',
    login_sub: 'Вход в приложение подтверждается через Telegram — пароль не нужен.', login_tg: 'Войти через Telegram', login_note: 'Уведомления приходят в бот в Telegram.', login_pin: 'Откройте бота в Telegram и выберите это число:', login_open_tg: 'Открыть Telegram', login_wait: 'Ожидаем подтверждения…', login_expired: 'Время входа истекло. Попробуйте ещё раз.', login_cancelled: 'Вход отменён.', cancel: 'Отмена', app_word: 'приложение', browser_word: 'браузер', logout: 'Выйти на этом устройстве', logout_q: 'Выйти из приложения? Повторный вход подтверждается через Telegram.', devices_hint: 'Все устройства — в боте: /qurilmalar', step_phone: 'Телефон', step_child: 'Ребёнок', step_confirm: 'Подтверждение', phone_safe: 'Номер подтверждает сам Telegram — вводить вручную не нужно. Если номер есть в списке университета, ребёнок подключится сразу.', child_title: 'Найдите ребёнка', child_sub: 'Ваш номер не найден в списке университета. Введите данные ребёнка как в документе.', birth_date: 'Дата рождения', or_hemis: 'или по ID студента (HEMIS)', hemis_id: 'ID студента (HEMIS)', find_child: 'Продолжить', confirm_title: 'Последний шаг — подтверждение', confirm_student_sub: 'Отправьте ссылку ребёнку: он подтвердит вас своим номером телефона, затем координатор курса даст окончательное подтверждение. Так посторонний не сможет подключиться к вашему ребёнку.', send_to_child: 'Отправить ребёнку', copy_link: 'Скопировать ссылку', link_copied: 'Ссылка скопирована', wait_coord: 'После подтверждения ребёнка запрос уйдёт координатору курса', no_phone_hint: 'Если не знаете номер — координатор курса проверит запрос сам.', child_phone: 'Телефон ребёнка', child_phone_sub: 'Номера ребёнка нет в базе университета. Введите его номер в Telegram — затем ребёнок подтвердит вас с этого номера.', phone_err_bad_phone: 'Неверный номер. Например: +998 90 123 45 67', phone_err_own_phone: 'Это ваш номер. Введите собственный номер ребёнка.', phone_err_phone_taken: 'Этот номер принадлежит другому человеку. Введите номер ребёнка.', phone_err_not_found: 'Запрос не найден или уже рассмотрен.', phone_err_has_phone: 'Номер ребёнка уже есть в базе — отправьте ссылку.', student_ok_wait: 'Ребёнок подтвердил вас. Теперь ожидается окончательное подтверждение координатора курса — после этого всё откроется здесь.', coord_only: 'Запрос проверит и подтвердит координатор курса — после этого всё откроется здесь.', add_child: 'Добавить другого ребёнка', too_many_tries: 'Попытки закончились. Попробуйте завтра или свяжитесь с координатором.', share_text: 'Здравствуйте! Подтвердите меня в боте для родителей — откройте ссылку и нажмите «Да»:', waiting: 'ожидается', done_step: 'выполнено',
    levels: 'Пороги пропусков', missed: 'Пропущенные занятия', by_subject: 'По предметам', by_week: 'По неделям',
    keldi: 'Присутствовал(а)', kelmadi: 'Отсутствовал(а)', sababli: 'Уважительная причина', kechikdi: 'Опоздал(а)', nothing_missed: 'Пропусков нет',
    this_week: 'Эта неделя', prev: 'Назад', next: 'Вперёд', next_limit: 'Следующий', toq: 'нечётная неделя', juft: 'чётная неделя', no_lessons: 'В этот день занятий нет',
    pairN: '{n}-я пара', semN: '{n}-й семестр', credits: 'кредит.', debt_subject: 'Академ. задолженность', gpa_long: 'Средний балл успеваемости',
    contract_pay: 'Оплата контракта', trimester_pay: 'Оплата триместра', debt: 'Задолженность', paid: 'Оплачено', contract: 'По договору',
    deadline: 'Срок оплаты', days_left: 'Осталось дней: {n}', overdue: 'Срок истёк', history: 'История', grant_note: 'Госгрант — оплата контракта не требуется',
    not_loaded: 'Отчёт ещё не загружен', send_chat: 'Отправить в чат', sent_chat: 'Документ отправлен в чат', no_docs: 'Документов нет',
    no_docs_sub: 'Официальные документы появятся здесь и придут в Telegram.', month_ago: 'месяц назад', now: 'сейчас',
    no_trends: 'Пока недостаточно данных для сравнения', type_msg: 'Напишите сообщение…', msg_sent: 'Сообщение отправлено',
    no_msgs: 'Сообщений пока нет', no_msgs_sub: 'Напишите Ваш вопрос — ответ придёт сюда и в Telegram.', mark_read: 'Прочитать все',
    nav_att: 'Пропуски', nav_msg: 'Чат', debts_title: 'Академическая задолженность', from_hemis: 'список должников HEMIS', debt_score: '{s} баллов → «2»', sem_n: '{n}-й семестр', credits_n: '{n} кредит(а)', debts_help: 'По порядку пересдачи обращайтесь к куратору курса.', ask_coord: 'Написать куратору курса', no_debts: 'Академическая задолженность отсутствует', open: 'Открыть', theme: 'Тема', th_auto: 'Авто', th_light: 'Светлая', th_dark: 'Тёмная', pages: 'стр.', open_doc: 'Открыть', doc_loading: 'Документ открывается…', tap_zoom: 'Нажмите на страницу, чтобы увеличить', no_notes: 'Уведомлений нет', no_notes_sub: 'Здесь появятся сообщения о пропусках, оценках и сроках оплаты.',
    no_news: 'Объявлений нет', lang: 'Язык', flags: 'Какие уведомления получать', notify_instant: 'При пропуске — сразу',
    notify_daily: 'Ежедневная сводка — вечером', notify_warn: 'Важные предупреждения', notify_pay: 'Напоминания об оплате',
    grade_scale: 'Шкала оценок', welcome: 'Здравствуйте!', welcome_sub: 'Посещаемость, оценки и оплата Вашего ребёнка — в одном месте и вовремя.',
    choose_lang: 'Выберите язык', confirm_phone: 'Подтвердить номер телефона', phone_why: 'Номер нужен, чтобы найти Вашего ребёнка в базе университета.',
    confirming: 'Подтверждение…', open_in_tg: 'Откройте приложение через бота в Telegram.', pending_title: 'Ваш ребёнок пока не найден',
    pending_sub: 'Введите данные — куратор курса проверит и подтвердит.', full_name: 'Фамилия и имя ребёнка',
    verify: 'Дата рождения или HEMIS ID', send_request: 'Отправить запрос', requested: 'Запрос отправлен куратору курса. После подтверждения Вам придёт сообщение в Telegram.',
    not_matched: 'Данные не совпали. Напишите фамилию и имя как в документе.', blocked: 'Это приложение только для родителей.',
    error: 'Ошибка соединения.', retry: 'Повторить', saved: 'Сохранено', choose_child: 'Выберите ребёнка',
    call_tutor: 'Позвонить куратору курса', attention: 'Требует внимания', see_all: 'Все', lessonsN: 'занятий: {n}',
    percent_note: 'посещаемость', pairs: '{p} {w} ({h} ч)', money: '{n} сум', today: 'Сегодня', yesterday: 'Вчера', you: 'Вы',
    too_many: 'Много сообщений ждут ответа. Пожалуйста, дождитесь ответа.', uni_student: 'студент',
  },
  en: {
    home: 'Home', schedule: 'Timetable', attendance: 'Attendance', grades: 'Grades', messages: 'Messages',
    menu: 'Menu', subj_att: 'Attendance', subj_att_hint: 'Since the start of the semester in this subject: {n} classes', unexc_n: '{n} unexcused', notes_all: 'All notifications', notes_unread: 'Unread', notes_updated: 'Last update: {t}', note_new: 'New', notes_read_all: 'All read', notifications: 'Notifications', finance: 'Payments', documents: 'Documents', trends: 'Trends',
    news: 'Announcements', settings: 'Settings', info: 'Useful information', group: 'Group', year: 'Year', faculty: 'Faculty',
    yearN: 'Year {n}', student: 'Student', ok_title: 'All good', ok_sub: 'No problems with attendance, grades or payments.',
    issues: '{n} issue(s) need attention', gpa: 'GPA', of5: 'of 5', gpa_hint: 'grade point average', acad: 'Academic debt', none: 'none',
    subjectsN: '{n} subject(s)', mln_unit: 'M UZS', debt_clear_s: 'no debt', kontrakt: 'Tuition', trimestr: 'Trimester', no_debt: 'None', grant: 'State grant',
    no_data: 'No data', unexcused: 'unexcused', excused: 'excused', today_lessons: 'Today’s classes', no_lessons_today: 'No classes today',
    all: 'All', coordinator: 'Course coordinator', write: 'Write', call: 'Call', updated: 'Updated: {t}',
    since_start: 'Since the start of the semester', next_level: 'Next threshold: {a} — {left} more', max_level: 'Highest threshold reached',
    hemis_missed: 'According to HEMIS', hemis_missed_note: 'HEMIS summary statistics do not include the date and subject of each class. Once the coordinator uploads daily attendance, classes will appear here by date and subject.', until: 'until {d}', unexcused_n: 'Unexcused: {a}', excused_n: 'excused: {b}',
    gpa_low: 'below {min} — will not advance to the next year',
    back: 'Back',
    surveys: 'Surveys', survey: 'Survey', regs: 'University regulations', regs_sub: 'Internal rules and regulations of the university', answer_now: 'Answer', q_n: '{n} question(s)', closes: 'until {d}', submit_survey: 'Submit', survey_thanks: 'Thank you! Your answer has been received.', survey_closed: 'The survey is closed', required_q: 'Please answer the marked questions', your_answer: 'Your answer…', answered: 'Answered', no_surveys: 'No surveys yet', no_regs: 'No regulations published yet', edit_answer: 'Change answer', anon: 'Anonymous: your and your child’s names are not shown', scale_lo: 'poor', scale_hi: 'excellent', choose_many: 'you can choose several', waiting_you: 'We’d like your opinion', open_link: 'Open', new_note: 'New notification', poll_done: 'Answered',
    dyn_first: 'first data', dyn_same: 'no change', more: 'Details',
    dyn_none: 'No changes in the latest uploads — changes will appear here.',
    by_upload: 'By uploaded data', by_semester: 'By semester', avg_score: 'average score',
    portal: 'Parents’ portal', my_children: 'My children', sec_study: 'Study', sec_contact: 'Contact', sec_uni: 'University', subj_h: 'Subject', score_h: 'Score', grade_h: 'Grade', credits_h: 'Credits', week_view: 'Weekly timetable', today_word: 'Today', no_lessons_short: 'No classes', hero_title: 'Your child’s studies — in one window', hero_1: 'Attendance, grades and payments — updated daily', hero_2: 'Direct messaging with the course coordinator', hero_3: 'Notifications arrive in Telegram instantly', hero_secure: 'No password, secure: every sign-in is confirmed in Telegram', missed_list: 'Missed classes', date_h: 'Date', status_h: 'Status', pair_h: 'Pair',
    login_sub: 'Sign-in is confirmed via Telegram — no password needed.', login_tg: 'Sign in with Telegram', login_note: 'Notifications arrive in the Telegram bot.', login_pin: 'Open the bot in Telegram and choose this number:', login_open_tg: 'Open Telegram', login_wait: 'Waiting for your confirmation…', login_expired: 'Sign-in timed out. Please try again.', login_cancelled: 'Sign-in was cancelled.', cancel: 'Cancel', app_word: 'app', browser_word: 'browser', logout: 'Sign out on this device', logout_q: 'Sign out of the app? Signing in again is confirmed via Telegram.', devices_hint: 'All devices — in the bot: /qurilmalar', step_phone: 'Phone', step_child: 'Child', step_confirm: 'Confirm', phone_safe: 'Telegram itself confirms your number — no need to type it. If it is in the university list, your child is connected at once.', child_title: 'Find your child', child_sub: 'Your number was not found in the university list. Enter your child’s details as in official documents.', birth_date: 'Date of birth', or_hemis: 'or by student ID (HEMIS)', hemis_id: 'Student ID (HEMIS)', find_child: 'Continue', confirm_title: 'Last step — confirmation', confirm_student_sub: 'Send the link to your child: they confirm you with their own phone number, then the course coordinator gives final approval. This way a stranger cannot connect to your child.', send_to_child: 'Send to my child', copy_link: 'Copy link', link_copied: 'Link copied', wait_coord: 'After your child confirms, the request goes to the course coordinator', no_phone_hint: 'If you don’t know the number, the course coordinator will check the request.', child_phone: 'Your child’s phone number', child_phone_sub: 'Your child’s number is not in the university database. Enter their Telegram number — then your child confirms you from that number.', phone_err_bad_phone: 'Invalid number. Example: +998 90 123 45 67', phone_err_own_phone: 'This is your own number. Enter your child’s number.', phone_err_phone_taken: 'This number belongs to someone else. Enter your child’s number.', phone_err_not_found: 'Request not found or already reviewed.', phone_err_has_phone: 'Your child’s number is already on file — send the link.', student_ok_wait: 'Your child has confirmed you. Now waiting for the course coordinator’s final approval — then everything opens here.', coord_only: 'The course coordinator will check and approve your request — then everything opens here.', add_child: 'Add another child', too_many_tries: 'No attempts left. Try again tomorrow or contact the coordinator.', share_text: 'Hello! Please confirm me in the parents’ bot — open the link and tap “Yes”:', waiting: 'waiting', done_step: 'done',
    levels: 'Absence thresholds', missed: 'Missed classes', by_subject: 'By subject', by_week: 'By week',
    keldi: 'Present', kelmadi: 'Absent', sababli: 'Excused', kechikdi: 'Late', nothing_missed: 'No missed classes',
    this_week: 'This week', prev: 'Previous', next: 'Next', next_limit: 'Next', toq: 'odd week', juft: 'even week', no_lessons: 'No classes on this day',
    pairN: 'Class {n}', semN: 'Semester {n}', credits: 'credits', debt_subject: 'Academic debt', gpa_long: 'Grade point average',
    contract_pay: 'Tuition payment', trimester_pay: 'Trimester payment', debt: 'Outstanding', paid: 'Paid', contract: 'Contract',
    deadline: 'Due date', days_left: '{n} days left', overdue: 'Overdue', history: 'History', grant_note: 'State grant — no tuition payment required',
    not_loaded: 'Report not uploaded yet', send_chat: 'Send to chat', sent_chat: 'Document sent to your chat', no_docs: 'No documents',
    no_docs_sub: 'Official documents will appear here and in Telegram.', month_ago: 'a month ago', now: 'now',
    no_trends: 'Not enough data to compare yet', type_msg: 'Write a message…', msg_sent: 'Message sent',
    no_msgs: 'No messages yet', no_msgs_sub: 'Write your question — the reply comes here and in Telegram.', mark_read: 'Mark all read',
    nav_att: 'Attendance', nav_msg: 'Chat', debts_title: 'Academic debt', from_hemis: 'HEMIS debtor list', debt_score: '{s} points → “2”', sem_n: 'semester {n}', credits_n: '{n} credits', debts_help: 'Please contact the course coordinator about retakes.', ask_coord: 'Write to the course coordinator', no_debts: 'No outstanding academic debt', open: 'Open', theme: 'Theme', th_auto: 'Auto', th_light: 'Light', th_dark: 'Dark', pages: 'pages', open_doc: 'Open', doc_loading: 'Opening the document…', tap_zoom: 'Tap a page to zoom', no_notes: 'No notifications', no_notes_sub: 'Absences, new grades and payment deadlines will appear here.',
    no_news: 'No announcements', lang: 'Language', flags: 'Which notifications to receive', notify_instant: 'Absence — immediately',
    notify_daily: 'Daily summary — evening', notify_warn: 'Important warnings', notify_pay: 'Payment reminders',
    grade_scale: 'Grading scale', welcome: 'Welcome!', welcome_sub: 'Your child’s attendance, grades and payments — in one place, on time.',
    choose_lang: 'Choose language', confirm_phone: 'Confirm phone number', phone_why: 'We need it to find your child in the university database.',
    confirming: 'Confirming…', open_in_tg: 'Open the app via the bot in Telegram.', pending_title: 'Your child has not been found yet',
    pending_sub: 'Enter the details — the course coordinator will verify them.', full_name: 'Child’s surname and first name',
    verify: 'Date of birth or HEMIS ID', send_request: 'Send request', requested: 'Request sent to the course coordinator. You will get a Telegram message once confirmed.',
    not_matched: 'The details did not match. Write the name as in official documents.', blocked: 'This app is for parents only.',
    error: 'Connection error.', retry: 'Try again', saved: 'Saved', choose_child: 'Choose a child',
    call_tutor: 'Call the course coordinator', attention: 'Needs attention', see_all: 'All', lessonsN: '{n} class(es)',
    percent_note: 'attendance', pairs: '{p} {w} ({h} h)', money: '{n} UZS', today: 'Today', yesterday: 'Yesterday', you: 'You',
    too_many: 'Many messages are awaiting a reply. Please wait.', uni_student: 'student',
  },
};
const t = (k, v = {}) => {
  let s = (T[S.lang] && T[S.lang][k]) || T.uz[k] || k;
  for (const [a, b] of Object.entries(v)) s = s.replaceAll('{' + a + '}', b);
  return s;
};
const MONTHS = {
  uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
};
const SHORT_WD = { uz: ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh'], ru: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'], en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] };

/* ================================================================ yordamchilar */
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
/* GPA yaxlitlanmaydi: 2 xonagacha kesiladi (2,599 → 2,59 — 2,6 deb ko'rsatilsa, chegaradan o'tgandek ko'rinadi) */
const limNum = x => S.lang === 'en' ? String(x) : String(x).replace('.', ',');  // chegara aynan: 2.6 → 2,6
const gpaNum = x => { const s = (Math.floor(Number(x) * 100 + 1e-6) / 100).toFixed(2); return S.lang === 'en' ? s : s.replace('.', ','); };
const num = x => { const v = Math.round(Number(x || 0) * 10) / 10; return (Number.isInteger(v) ? String(v) : String(v).replace('.', S.lang === 'en' ? '.' : ',')); };
const money = x => t('money', { n: Math.round(Number(x || 0)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') }).replace(/ /g, '\u00a0');
function subjUnit(n) {  // «1 ta fan» / «1 предмет, 2 предмета, 5 предметов» / «1 subject»
  if (S.lang === 'ru') return (n % 10 === 1 && n % 100 !== 11) ? 'предмет' : ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) ? 'предмета' : 'предметов';
  if (S.lang === 'en') return n === 1 ? 'subject' : 'subjects';
  return 'ta fan';
}
function fmtPhone(p) {
  const d = String(p || '').replace(/\D/g, '');
  if (d.length === 12 && d.startsWith('998')) return `+998 ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`;
  return p ? (d.length > 9 && !String(p).startsWith('+') ? '+' + d : String(p)) : '';
}
function pairs(hours) {
  const h = Number(hours || 0), p = h / 2;
  if (S.lang === 'ru') {
    const n = Math.floor(p), w = p !== n ? 'пары' : (n % 10 === 1 && n % 100 !== 11) ? 'пара' : ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) ? 'пары' : 'пар';
    return t('pairs', { p: num(p), w, h: num(h) });
  }
  if (S.lang === 'en') return t('pairs', { p: num(p), w: p === 1 ? 'class' : 'classes', h: num(h) });
  return t('pairs', { p: num(p), h: num(h) });
}
function dateLabel(iso, withYear = false) {
  if (!iso) return '';
  const d = new Date(iso.length <= 10 ? iso + 'T00:00:00' : iso);
  const m = MONTHS[S.lang][d.getMonth()];
  if (S.lang === 'en') return `${d.getDate()} ${m}${withYear ? ' ' + d.getFullYear() : ''}`;
  if (S.lang === 'ru') return `${d.getDate()} ${m}${withYear ? ' ' + d.getFullYear() : ''}`;
  return `${d.getDate()}-${m}${withYear ? ', ' + d.getFullYear() : ''}`;
}
function when(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  const hm = d.toTimeString().slice(0, 5);
  const day = x => x.toDateString();
  if (day(d) === day(now)) return `${t('today')}, ${hm}`;
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (day(d) === day(y)) return `${t('yesterday')}, ${hm}`;
  return `${dateLabel(iso)}, ${hm}`;
}
const haptic = (k = 'light') => { try { tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred(k); } catch (e) { /* eski versiya */ } };
function toast(msg) {
  const el = document.createElement('div');
  el.className = 'toast'; el.role = 'status'; el.textContent = msg;
  document.body.appendChild(el); setTimeout(() => el.remove(), 2600);
}
/* Bot xabari (HTML) — faqat xavfsiz teglar qoladi */
function safeHtml(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = String(html || '').replace(/\n/g, '<br>');
  const walk = node => {
    [...node.childNodes].forEach(ch => {
      if (ch.nodeType === 1) {
        if (!['B', 'I', 'U', 'BR', 'A', 'CODE'].includes(ch.tagName)) { ch.replaceWith(...ch.childNodes); walk(node); return; }
        [...ch.attributes].forEach(a => { if (!(ch.tagName === 'A' && a.name === 'href' && /^https?:/.test(a.value))) ch.removeAttribute(a.name); });
        walk(ch);
      }
    });
  };
  walk(tmp);
  return tmp.innerHTML;
}

/* ================================================================ ikonalar (24×24, chiziqli) */
const P = {
  clock: 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18M12 7v5l3 2', checks: 'M2 12.5l4 4L15 7.5M10 16.5l1 1L22 6.5',
  dollar: 'M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 18V6',
  receipt: 'M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1zM15 8h-4.5a1.75 1.75 0 0 0 0 3.5h3a1.75 1.75 0 0 1 0 3.5H9M12 6.5v11',
  bookx: 'M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20M14.5 7l-5 5M9.5 7l5 5',
  calx: 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM16 2v4M8 2v4M3 10h18M14 14l-4 4M10 14l4 4',
  flame: 'M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4.1 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5z',
  sun: 'M8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  auto: 'M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 3v18M12 7h4.5M12 11h6M12 15h5.5',
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  cal: 'M7 3v3M17 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  att: 'M9 11l3 3 8-8M20 12v7a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h11',
  grade: 'M12 3 2 8l10 5 10-5-10-5zM6 10.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-5.5',
  chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0',
  menu: 'M4 7h16M4 12h16M4 17h16',
  chev: 'M9 6l6 6-6 6', left: 'M15 6l-6 6 6 6',
  poll: 'M9 3h6v3H9zM9 4.5H6a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5.5a1 1 0 0 0-1-1h-3M8.5 12l2 2 4-4M8.5 17h7',
  book: 'M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5zM4 19.5A1.5 1.5 0 0 0 5.5 21H20v-3M8 7h8M8 10.5h6',
  ok: 'M20 6 9 17l-5-5', alert: 'M12 8v5M12 16.5v.5M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  wallet: 'M3 7a2 2 0 0 1 2-2h13v4M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2zM16 14h.01',
  file: 'M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M9 13h6M9 17h6',
  trend: 'M3 17l6-6 4 4 8-8M14 7h7v7', mega: 'M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1zM16 8a5 5 0 0 1 0 8',
  info: 'M12 8h.01M11 12h1v5h1M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z', gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-2.9-1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3.2 14H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 10 3.2V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 20.8 10H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  phone: 'M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z',
  send: 'M22 2 11 13M22 2l-7 20-4-9-9-4z', users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8',
  upload: 'M12 16V4M7 9l5-5 5 5M4 20h16', search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3', panel: 'M4 13h6V4H4zM14 20h6v-9h-6zM14 4v4h6V4zM4 20h6v-4H4z',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18',
};
/* bo'lim sarlavhalari belgisi: kalit — tarjima kaliti yoki o'zbekcha sarlavha */
const HI = { today_lessons: ['cal', 'people'], levels: ['alert', 'risk'], by_week: ['trend', 'att'], by_subject: ['book', 'gpa'],
  trends: ['trend', 'people'], semN: ['grade', 'gpa'], missed: ['calx', 'att'], missed_list: ['calx', 'att'], grade_scale: ['grade', 'gpa'], flags: ['alert', 'risk'],
  coordinator: ['users', 'people'], by_upload: ['trend', 'msg'], by_semester: ['grade', 'gpa'], answered: ['ok', 'att'], theme: ['sun', 'people'],
  lang: ['chat', 'msg'], 'Dinamika': ['trend', 'people'], 'Muammoli talabalar': ['flame', 'risk'], 'Akademik qarzdorlik': ['bookx', 'acad'],
  'Talabalar': ['users', 'people'], 'Ota-onalar': ['users', 'people'], 'Hisobot': ['file', 'people'], 'Yuklangan fayllar': ['file', 'people'],
  'Hujjat turi': ['file', 'acad'], 'HEMIS': ['grade', 'gpa'] };
const hi = k => HI[k] ? `<span class="h-ic c-${HI[k][1]}" aria-hidden="true">${ic(HI[k][0])}</span>` : '';
/* ixcham summa: 5 500 000 → «5,5 mln so‘m» (to'liq summa — title da) */
const mShort = x => (x >= 1e6 ? `${(Math.floor(x / 1e5) / 10).toString().replace('.', S.lang === 'en' ? '.' : ',')}<small class="of"> ${esc(t('mln_unit'))}</small>`
  : esc(money(x)));
/* kartochka nomi belgisi bilan */
const tk = (label, icon, c) => `<span class="k"><span class="t-ic c-${c}" aria-hidden="true">${ic(icon)}</span>${label}</span>`;
const ic = (name, cls = '') => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${P[name]}"/></svg>`;

/* ================================================================ API */
async function api(path, opts = {}) {
  const headers = Object.assign({ 'X-Telegram-Init-Data': (tg && tg.initData) || '' }, opts.headers || {});
  if (DEV) headers['X-Dev-User'] = '1';
  if (!tg && store.get('appToken')) headers.Authorization = 'Bearer ' + store.get('appToken');
  if (S.staffCourse) headers['X-Course'] = S.staffCourse;
  if (opts.json !== undefined) { headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, { method: opts.method || (opts.body ? 'POST' : 'GET'), headers, body: opts.body });
  if (!r.ok) { const e = new Error('http ' + r.status); e.status = r.status; try { e.data = await r.json(); } catch (_) { /* */ } throw e; }
  return opts.raw ? r : r.json();
}
const childPath = (c, tail) => `/api/c/${encodeURIComponent(c.course)}/${c.id}/${tail}`;

/* ================================================================ tuzilma: yuqori panel, navigatsiya */
// Ortga: ilova ichida oldingi sahifa bo'lsa — unga, aks holda (havola orqali to'g'ridan-to'g'ri ochilgan) — mantiqiy ota sahifaga
function backTarget() {
  const h = location.hash;
  if (h.startsWith('#/staff/chat')) return '#/staff/inbox';
  if (h.startsWith('#/staff/')) return '#/staff';
  if (h.startsWith('#/doc/')) return '#/documents';
  return '#/';
}
function goBack() {
  if (S.navDepth > 0) { S.navDepth -= 2; history.back(); } else location.hash = backTarget();
}
window.addEventListener('hashchange', () => { S.navDepth = (S.navDepth || 0) + 1; });
function topbar(title, sub = '') {
  const unread = (S.me && S.me.unread) || {};
  const isStaff = S.me && (S.me.role === 'staff' || S.me.role === 'super');
  const courses = S.me && S.me.staff && S.me.staff.courses || [];
  return `<header class="topbar">
    <div class="brand">${S.chrome && S.chrome.noNav ? `<button class="icon-btn back" data-act="back" aria-label="${t('back')}" title="${t('back')}">${ic('left')}</button>` : '<div class="seal" aria-hidden="true">J</div>'}<div><h1>${esc(title)}</h1>${sub ? `<small>${esc(sub)}</small>` : ''}</div></div>
    ${courses.length ? `<select class="course-select" data-act="course" aria-label="Kurs">${courses.map(c => `<option value="${esc(c.key)}" ${c.key === (S.me.staff.course) ? 'selected' : ''}>${esc(c.title)}</option>`).join('')}</select>` : ''}
    <button class="icon-btn" data-act="theme" aria-label="${t('theme')}: ${t('th_' + themePref())}" title="${t('theme')}: ${t('th_' + themePref())}">${ic({ auto: 'auto', light: 'sun', dark: 'moon' }[themePref()])}</button>
    ${isStaff ? '' : `<a class="icon-btn" href="#/notifications" aria-label="${t('notifications')}">${ic('bell')}${unread.notifications ? `<span class="dot">${unread.notifications > 9 ? '9+' : unread.notifications}</span>` : ''}</a>
    <a class="icon-btn" href="#/menu" aria-label="${t('menu')}">${ic('menu')}</a>`}
  </header>`;
}
function nav(active) {
  const unread = (S.me && S.me.unread) || {};
  const staff = S.me && (S.me.role === 'staff' || S.me.role === 'super');
  const items = staff
    ? [['#/staff', 'panel', 'Panel'], ['#/staff/students', 'users', 'Talabalar'], ['#/staff/inbox', 'chat', 'Xabarlar'], ['#/staff/announce', 'mega', 'E’lon'], ['#/staff/files', 'upload', 'Fayllar']]
    : [['#/', 'home', t('home')], ['#/schedule', 'cal', t('schedule')], ['#/attendance', 'att', t('nav_att')], ['#/grades', 'grade', t('grades')], ['#/chat', 'chat', t('nav_msg')]];
  return `<nav class="nav" aria-label="Asosiy bo‘limlar">${items.map(([href, icon, label]) => {
    const badge = (href === '#/chat' && unread.messages) || (href === '#/staff/inbox' && S.staffUnread) || 0;
    return `<a href="${href}" ${href === active ? 'aria-current="page"' : ''}>${ic(icon)}<span>${esc(label)}</span>${badge ? `<span class="dot">${badge}</span>` : ''}</a>`;
  }).join('')}</nav>`;
}
function page({ title, sub, body, active, noNav, wide }) {
  S.chrome = { title, sub, active, noNav, wide };
  if (deskMode()) {  // kompyuter: yon menyu + sarlavha + keng ish maydoni
    $app.innerHTML = `<div class="dk">${deskSide()}<div class="dk-main">${deskHead(title, sub, noNav)}
      <main class="dk-body${wide ? ' wide' : ''}">${body}</main></div></div>`;
    window.scrollTo(0, 0);
    return;
  }
  $app.innerHTML = topbar(title, sub) + `<main class="${noNav ? 'no-nav' : ''}">${body}</main>` + (noNav ? '' : nav(active));
  window.scrollTo(0, 0);
}

/* ================================================================ kompyuter versiyasi (keng ekran, oddiy brauzer)
   Ota-ona uchun: chapda yon menyu (farzandlar va bo'limlar), yuqorida sarlavha, sahifalar ko'p ustunli.
   Kurs koordinatori kompyuterda — alohida boshqaruv paneliga (/desk) o'tadi. */
const DESK_MQ = matchMedia('(min-width: 1100px)');
const deskWide = () => !tg && !NATIVE && DESK_MQ.matches;
const deskMode = () => deskWide() && !!S.me && S.me.role === 'parent';
if (DESK_MQ.addEventListener) DESK_MQ.addEventListener('change', () => { if (S.me && !tg && !NATIVE) route(); });
function deskSide() {
  const u = S.me.unread || {}, cur = (location.hash.split('?')[0] || '#/').replace(/^#$/, '#/');
  const on = href => cur === href || (href !== '#/' && cur.startsWith(href + '/')) || (href === '#/debts' && cur === '#/debts');
  const item = (href, icon, label, badge) => `<a href="${href}" class="${on(href) ? 'on' : ''}"${on(href) ? ' aria-current="page"' : ''}>${ic(icon)}<span>${esc(label)}</span>${badge ? `<b class="cnt">${badge > 99 ? '99+' : badge}</b>` : ''}</a>`;
  const kids = S.me.children;
  return `<aside class="dk-side" aria-label="${t('menu')}">
    <a class="dk-brand" href="#/"><img src="static/jidu-seal.webp" alt="" width="40" height="40"><span><b>JIDU</b><small>${t('portal')}</small></span></a>
    ${kids.length ? `<div class="dk-kids"><h6>${t('my_children')}</h6>${kids.map(k => `<button class="dk-kid${S.child === k ? ' on' : ''}" data-act="child" data-key="${k.course}/${k.id}" aria-pressed="${S.child === k}">
      <span class="av">${esc(k.initials)}</span><span class="nm"><b>${esc(k.short)}</b><small>${esc([k.group, k.year ? t('yearN', { n: k.year }) : ''].filter(Boolean).join(' · '))}</small></span></button>`).join('')}</div>` : ''}
    <nav class="dk-nav">
      <h6>${t('sec_study')}</h6>
      ${item('#/', 'home', t('home'))}${item('#/schedule', 'cal', t('schedule'))}${item('#/attendance', 'att', t('attendance'))}${item('#/grades', 'grade', t('grades'))}
      ${item('#/finance', 'wallet', t('finance'))}${item('#/trends', 'trend', t('trends'))}${item('#/documents', 'file', t('documents'))}
      <h6>${t('sec_contact')}</h6>
      ${item('#/chat', 'chat', t('messages'), u.messages)}${item('#/notifications', 'bell', t('notifications'), u.notifications)}${item('#/news', 'mega', t('news'))}
      <h6>${t('sec_uni')}</h6>
      ${item('#/surveys', 'poll', t('surveys'), S.pendingSurveys)}${item('#/regulations', 'book', t('regs'))}${item('#/info', 'info', t('info'))}
    </nav>
    <div class="dk-me"><span class="av">${esc((S.me.user.name || '?').trim().charAt(0).toUpperCase())}</span>
      <span class="nm"><b>${esc(S.me.user.name || '')}</b><small>${t('portal')}</small></span>
      <a class="icon-btn" href="#/settings" title="${t('settings')}" aria-label="${t('settings')}">${ic('gear')}</a>
      ${S.me.app_session ? `<button class="icon-btn" data-act="logout" title="${t('logout')}" aria-label="${t('logout')}">${ic('logout')}</button>` : ''}</div>
  </aside>`;
}
function deskHead(title, sub, back) {
  const u = S.me.unread || {}, d = new Date();
  const today = `${d.getDate()} ${(MONTHS[S.lang] || MONTHS.uz)[d.getMonth()]}`;
  return `<header class="dk-head">
    ${back ? `<button class="icon-btn" data-act="back" aria-label="${t('back')}" title="${t('back')}">${ic('left')}</button>` : ''}
    <div class="dk-title"><h1>${esc(title)}</h1>${sub ? `<p>${esc(sub)}</p>` : ''}</div>
    <span class="dk-date">${ic('cal')}${esc(today)}</span>
    <a class="icon-btn" href="#/notifications" aria-label="${t('notifications')}" title="${t('notifications')}">${ic('bell')}${u.notifications ? `<span class="dot">${u.notifications > 9 ? '9+' : u.notifications}</span>` : ''}</a>
    <button class="icon-btn" data-act="theme" aria-label="${t('theme')}: ${t('th_' + themePref())}" title="${t('theme')}: ${t('th_' + themePref())}">${ic({ auto: 'auto', light: 'sun', dark: 'moon' }[themePref()])}</button>
  </header>`;
}
const loading = () => `<div class="skeleton" style="height:190px;margin-top:4px"></div><div class="grid2" style="margin-top:16px"><div class="skeleton" style="height:118px"></div><div class="skeleton" style="height:118px"></div></div><div class="skeleton" style="height:160px;margin-top:16px"></div>`;
const empty = (icon, title, sub = '') => `<div class="empty">${ic(icon)}<b>${esc(title)}</b>${esc(sub)}</div>`;
const errorBox = () => `<div class="empty">${ic('alert')}<b>${t('error')}</b><button class="btn ghost" data-act="reload" style="margin-top:12px">${t('retry')}</button></div>`;
function switcher() {
  const kids = S.me.children;
  if (kids.length < 2 || deskMode()) return '';  // kompyuterda farzand yon menyuda tanlanadi
  return `<div class="switcher${kids.length === 2 ? ' two' : ''}" role="group" aria-label="${t('choose_child')}">${kids.map(k =>
    `<button class="kid" data-act="child" data-key="${k.course}/${k.id}" aria-pressed="${S.child === k ? 'true' : 'false'}"><span class="av">${esc(k.initials)}</span><span class="nm">${esc(k.short)}</span></button>`).join('')}</div>`;
}
function ring(pct, size = 64, stroke = 8) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, pct || 0));
  const color = v >= 90 ? 'var(--ok)' : v >= 75 ? 'var(--warn)' : 'var(--bordo-500)';
  return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle class="bg" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke-width="${stroke}"/>
    <circle class="fg" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-offset="${c * (1 - v / 100)}"/></svg>`;
}
const animateRings = () => requestAnimationFrame(() => document.querySelectorAll('.ring .fg').forEach(el => { el.style.strokeDashoffset = el.dataset.offset; }));

/* ================================================================ ota-ona: asosiy */
function idCard(c) {
  const rows = [[t('group'), c.group], [t('year'), c.year ? t('yearN', { n: c.year }) : ''], [t('faculty'), c.faculty]].filter(r => r[1]);
  return `<section class="idcard" aria-label="${t('student')}">
    <picture class="stamp" aria-hidden="true"><source srcset="static/jidu-seal.webp" type="image/webp"><img src="static/jidu-seal.png" alt="" width="56" height="56" decoding="async"></picture>
    <p class="role">${esc(S.me.university)}</p>
    <h2 class="name">${esc(c.name)}</h2>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    <div class="foot">${c.hemis_id ? `<span class="tag">HEMIS ${esc(c.hemis_id)}</span>` : ''}${c.payment_form ? `<span class="tag">${esc(c.payment_form)}</span>` : ''}</div>
  </section>`;
}
function verdict(o) {
  const n = o.issues.length;
  if (!n) return `<div class="verdict ok">${ic('ok')}<div><b>${t('ok_title')}</b><p>${t('ok_sub')}</p></div></div>`;
  const tone = (o.attendance && o.attendance.level >= 1) || o.academic.count ? 'bad' : 'warn';
  const kind = s => /^📚/u.test(s) ? ['bookx', 'acad', '#/debts'] : /^💰/u.test(s) ? ['dollar', 'money', '#/finance']
    : /^💳/u.test(s) ? ['receipt', 'money2', '#/finance'] : /^🎓/u.test(s) ? ['grade', 'gpa', '#/grades'] : ['calx', 'att', '#/attendance'];
  const rows = o.issues.map(s => { const [i, c, h] = kind(s); return `<a class="issue" href="${h}"><span class="t-ic c-${c}" aria-hidden="true">${ic(i)}</span>
    <span class="tx">${esc(s.replace(/^[^\p{L}\p{N}]+/u, ''))}</span>${ic('chev', 'chev')}</a>`; }).join('');
  return `<div class="verdict ${tone}">${ic('alert')}<div style="flex:1;min-width:0"><b>${t('issues', { n })}</b><div class="issues">${rows}</div></div></div>`;
}
function payTile(kind, p) {
  const label = tk(t(kind), kind === 'trimestr' ? 'receipt' : 'dollar', kind === 'trimestr' ? 'money2' : 'money');
  if (!p || p.state === 'none') return `<a class="tile st-tile" href="#/finance">${label}<span class="v muted" style="font-size:18px">${t('no_data')}</span></a>`;
  if (p.state === 'grant') return `<a class="tile st-tile ok" href="#/finance">${label}<span class="v" style="font-size:19px">${t('grant')}</span><span class="s state ok">${ic('ok')}${t('no_debt')}</span></a>`;
  if (p.state === 'clear') return `<a class="tile st-tile ok" href="#/finance">${label}<span class="v" style="font-size:20px">${t('no_debt')}</span><span class="s state ok">${ic('ok')}${t('debt_clear_s')}</span></a>`;
  const late = p.days_left != null && p.days_left < 0;
  return `<a class="tile st-tile bad" href="#/finance" title="${esc(money(p.debt))}">${label}<span class="v num">${mShort(p.debt)}</span>
    <span class="s">${p.days_left != null ? (late ? t('overdue') : t('days_left', { n: p.days_left })) : t('debt')}</span></a>`;
}
/* darsdagi fan bo'yicha davomat (semestr boshidan): foiz, chiziq va sababsiz qoldirilganlar */
function lessonAtt(a) {
  if (!a || !a.total) return '';
  const tone = a.pct >= 90 ? 'ok' : a.pct >= 75 ? 'warn' : 'bad';
  return `<div class="latt ${tone}" title="${esc(t('subj_att_hint', { n: a.total }))}"><span>${t('subj_att')}</span><b class="num">${a.pct}%</b>
    <span class="lbar"><i style="width:${a.pct}%"></i></span>${a.kelmadi ? `<span class="lmiss">${t('unexc_n', { n: a.kelmadi })}</span>` : ''}</div>`;
}
function lessonRow(l) {
  const st = l.status ? `<span class="pill ${l.status === 'keldi' ? 'ok' : l.status === 'kelmadi' ? 'bordo' : 'warn'}">${t(l.status)}</span>` : '';
  const time = l.start ? `${esc(l.start)}<small>${esc(l.end || '')}</small>` : (l.pair ? `<span class="pairno">${esc(t('pairN', { n: l.pair }))}</span>` : '');
  return `<div class="lesson"><div class="time">${time}${l.start && l.pair ? `<small class="pairno-s">${esc(t('pairN', { n: l.pair }))}</small>` : ''}</div>
    <div><div class="subj">${esc(l.subject)}</div><div class="meta">${l.type ? `<span class="pill">${esc(l.type)}${l.subgroup ? ' ' + esc(l.subgroup) : ''}</span>` : ''}
    ${l.room ? `<span>${esc(l.room)}</span>` : ''}${l.teacher ? `<span>${esc(l.teacher)}</span>` : ''}${st}</div>${lessonAtt(l.att)}</div></div>`;
}
async function viewHome() {
  const c = S.child;
  page({ title: t('home'), sub: c ? c.short : '', active: '#/', body: switcher() + loading() });
  let o, sv = { pending: [] };
  try { [o, sv] = await Promise.all([api(childPath(c, 'overview')), api('/api/surveys').catch(() => ({ pending: [] }))]); }
  catch (e) { return page({ title: t('home'), active: '#/', body: errorBox() }); }
  S.pendingSurveys = sv.pending.length;
  const a = o.attendance;
  const attTile = a ? `<a class="tile st-tile ${a.percent >= 90 ? 'ok' : a.percent >= 75 ? 'warn' : 'bad'}" href="#/attendance">${tk(t('attendance'), 'att', 'att')}
      <div class="ring-wrap">${ring(a.percent, 54, 7)}<span class="v num">${a.percent != null ? a.percent + '%' : '—'}</span></div>
      <span class="s">${t('unexcused')}<br><b class="nowrap">${pairs(a.counted_hours)}</b></span></a>`
    : `<a class="tile st-tile" href="#/attendance">${tk(t('attendance'), 'att', 'att')}<span class="v muted" style="font-size:18px">${t('no_data')}</span></a>`;
  const gpaTile = `<a class="tile st-tile ${o.gpa_low ? 'bad' : ''}" href="#/grades">${tk(t('gpa'), 'grade', 'gpa')}<span class="v num">${o.gpa != null ? gpaNum(o.gpa) : '—'}<small class="of"> / 5</small></span><span class="s">${o.gpa_low ? t('gpa_low', { min: limNum(o.gpa_min) }) : t('gpa_hint')}</span></a>`;
  const acadTile = `<a class="tile st-tile ${o.academic.count ? 'bad' : 'ok'}" href="${o.academic.count ? '#/debts' : '#/grades'}">${tk(t('acad'), 'bookx', 'acad')}
      <span class="v" style="font-size:${o.academic.count ? 26 : 22}px">${o.academic.count ? `${o.academic.count}<small class="of"> ${esc(subjUnit(o.academic.count))}</small>` : t('no_debt')}</span>
      <span class="s clamp3">${o.academic.count ? esc(o.academic.debts.map(d => d.subject).join(', ')) : ''}</span></a>`;
  const tutor = c.tutor || {};
  if (deskMode()) {  // kompyuter: chapda — talaba va holat, o'ngda — bugungi darslar, so'rovnomalar, koordinator
    const kpis = `<div class="dk-kpis">${attTile}${gpaTile}${acadTile}${payTile('kontrakt', o.pays.kontrakt)}${o.pays.trimestr && o.pays.trimestr.state !== 'none' ? payTile('trimestr', o.pays.trimestr) : ''}</div>`;
    const tutorCard = tutor.name || tutor.phone ? `<section class="card dk-tutor"><h3 class="dk-h3">${hi('coordinator')}${t('coordinator')}</h3>
      <div class="chat-head" style="padding:0;box-shadow:none;background:none"><div class="av">${esc((tutor.name || '?').trim().charAt(0))}</div>
      <div><b>${esc(tutor.name || '')}</b><div class="muted small">${esc(fmtPhone(tutor.phone))}</div></div></div>
      <a class="btn block" href="#/chat" style="margin-top:14px">${ic('chat')}${t('write')}</a></section>` : '';
    const lessons = `<section class="section"><div class="section-head"><h2>${hi('today_lessons')}${t('today_lessons')}</h2><a href="#/schedule">${t('schedule')}</a></div>
      <div class="list">${o.today.length ? o.today.map(l => lessonRow(l)).join('') : `<div class="empty" style="padding:22px">${t('no_lessons_today')}</div>`}</div></section>`;
    // 1-qator: talaba kartasi | holat va koordinator; 2-qator: ko'rsatkichlar; 3-qator: dinamika | bugungi darslar
    page({ title: t('home'), sub: `${c.name}${c.group ? ' · ' + c.group : ''}`, active: '#/', wide: true, body: `
      <div class="dk-grid home">
        <div class="dk-col">${idCard(c)}</div>
        <div class="dk-col">${verdict(o)}${sv.pending.slice(0, 2).map(surveyCta).join('')}${tutorCard}</div>
      </div>
      ${kpis}
      <div class="dk-grid home">
        <div class="dk-col">${parentDyn(o.dynamics)}</div>
        <div class="dk-col">${lessons}${o.updated ? `<p class="muted small" style="text-align:center">${t('updated', { t: when(o.updated) })}</p>` : ''}</div>
      </div>` });
    animateRings();
    return;
  }
  // birinchi ekranda: talaba kartasi → javob kutayotgan so'rovnoma → so'rovnomalar va ichki nizomlar → holat
  const body = switcher() + idCard(c) + sv.pending.slice(0, 2).map(surveyCta).join('') + quickLinks(sv.pending.length) + verdict(o) + `
    <div class="grid2" style="margin-top:14px">${attTile}${gpaTile}${acadTile}${payTile('kontrakt', o.pays.kontrakt)}</div>
    ${o.pays.trimestr && o.pays.trimestr.state === 'debt' ? `<div style="margin-top:12px">${payTile('trimestr', o.pays.trimestr)}</div>` : ''}
    ${parentDyn(o.dynamics)}
    <section class="section"><div class="section-head"><h2>${hi('today_lessons')}${t('today_lessons')}</h2><a href="#/schedule">${t('schedule')}</a></div>
      <div class="list">${o.today.length ? o.today.map(l => lessonRow(l)).join('') : `<div class="empty" style="padding:22px">${t('no_lessons_today')}</div>`}</div></section>
    ${tutor.name || tutor.phone ? `<section class="section"><div class="section-head"><h2>${hi('coordinator')}${t('coordinator')}</h2></div>
      <div class="card" style="display:flex;align-items:center;gap:12px"><div class="chat-head" style="padding:0;box-shadow:none;flex:1;background:none">
      <div class="av">${esc((tutor.name || '?').trim().charAt(0))}</div><div><b>${esc(tutor.name || '')}</b><div class="muted small">${esc(fmtPhone(tutor.phone))}</div></div></div>
      ${tutor.phone ? `<a class="icon-btn" style="background:var(--tint-navy);color:var(--accent)" href="tel:+${esc(tutor.phone)}" aria-label="${t('call_tutor')}">${ic('phone')}</a>` : ''}
      <a class="btn" href="#/chat">${t('write')}</a></div></section>` : ''}
    ${o.updated ? `<p class="muted small" style="text-align:center;margin-top:18px">${t('updated', { t: when(o.updated) })}</p>` : ''}`;
  page({ title: t('home'), sub: c.short, active: '#/', body });
  animateRings();
}

/* ================================================================ davomat */
function ladder(a) {
  const max = a.levels[a.levels.length - 1].hours * 1.1;
  const pos = Math.min(100, (a.counted_hours / max) * 100);
  const short = h => pairs(h).replace(/\s*\(.*\)\s*$/, '');
  return `<div class="ladder"><div class="track"><div class="fill" style="width:${pos}%"></div>
    ${a.levels.map(l => `<div class="mark" style="left:${(l.hours / max) * 100}%"></div>`).join('')}
    <div class="now num" style="left:${Math.max(8, Math.min(92, pos))}%">${esc(short(a.counted_hours))}</div></div>
    <ol class="steps">${a.levels.map((l, i) => {
      const cls = i <= a.level ? 'hit' : i === a.level + 1 ? 'next' : '';
      return `<li class="${cls}"><span class="lvl-dot">${i <= a.level ? ic('ok') : i + 1}</span>
        <div class="lv"><b class="num">${esc(pairs(l.hours))}</b><span>${esc(l.action)}</span></div>
        ${cls === 'next' ? `<span class="tag">${t('next_limit')}</span>` : ''}</li>`;
    }).join('')}</ol></div>`;
}
function weekChart(weeks) {
  if (!weeks || weeks.length < 2) return '';
  const w = 320, h = 140, bw = Math.min(38, (w - 20) / weeks.length - 10);
  const bars = weeks.map((x, i) => {
    const bh = Math.max(4, (x.pct / 100) * (h - 36)), xx = 10 + i * ((w - 20) / weeks.length) + ((w - 20) / weeks.length - bw) / 2;
    const col = x.pct >= 90 ? 'var(--ok)' : x.pct >= 75 ? 'var(--warn)' : 'var(--bordo-500)';
    return `<rect x="${xx}" y="${h - 20 - bh}" width="${bw}" height="${bh}" rx="6" fill="${col}"/><text x="${xx + bw / 2}" y="${h - 24 - bh}" text-anchor="middle">${x.pct}%</text>
      <text x="${xx + bw / 2}" y="${h - 5}" text-anchor="middle">${esc((x.label || dateLabel(x.start)).split('–')[0])}</text>`;
  }).join('');
  return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${t('by_week')}">${bars}</svg>`;
}
async function viewAttendance() {
  const c = S.child;
  page({ title: t('attendance'), sub: c.short, active: '#/attendance', body: switcher() + loading() });
  let d;
  try { d = await api(childPath(c, 'attendance')); } catch (e) { return page({ title: t('attendance'), active: '#/attendance', body: errorBox() }); }
  const a = d.summary;
  if (!a) return page({ title: t('attendance'), sub: c.short, active: '#/attendance', body: switcher() + empty('att', t('no_data')) });
  const next = a.next ? t('next_level', { a: a.next.action, left: pairs(a.next.left_hours) }) : t('max_level');
  const byDate = {};
  d.absences.forEach(x => { (byDate[x.date] = byDate[x.date] || []).push(x); });
  const hp = d.absences.length ? [] : (d.hemis_periods || []);  // kunlik ro'yxat yo'q — HEMIS davrlari bo'yicha
  if (deskMode()) {
    const summary = `<div class="card dk-att-sum">${ring(a.percent, 120, 12)}<div><div class="bigstat"><b class="num">${a.percent != null ? a.percent + '%' : '—'}</b></div>
        <div class="muted">${t('since_start')}</div>
        <div class="kv" style="margin-top:12px"><span>${t('unexcused')}</span><b class="num">${pairs(a.counted_hours)}</b></div>
        <div class="kv"><span>${t('excused')}</span><b class="num">${pairs(a.excused_hours)}</b></div>
        <p class="small muted" style="margin:6px 0 0">${esc(a.note)}</p></div></div>`;
    const levels = `<div class="card"><h3 class="dk-h3">${hi('levels')}${t('levels')}</h3>${ladder(a)}<p style="margin:12px 0 0" class="${a.level >= 0 ? '' : 'muted'}">${esc(next)}</p></div>`;
    const weeks = d.weeks && d.weeks.length > 1 ? `<div class="card"><h3 class="dk-h3">${hi('by_week')}${t('by_week')}</h3>${weekChart(d.weeks)}</div>` : '';
    const subj = d.subjects.length ? `<div class="card"><h3 class="dk-h3">${hi('by_subject')}${t('by_subject')}</h3><div class="list flat">${d.subjects.map(s => {
      const pct = s.total ? Math.round(100 * (s.keldi + s.kechikdi) / s.total) : 0;
      return `<div class="subject"><div><div class="t" style="font-weight:600">${esc(s.subject)}</div><div class="small muted">${t('kelmadi')}: ${s.kelmadi} · ${t('sababli')}: ${s.sababli}</div></div>
        <b class="num">${pct}%</b><div class="meter"><i style="width:${pct}%"></i></div></div>`; }).join('')}</div></div>` : '';
    const missed = d.absences.length ? `<div class="card"><h3 class="dk-h3">${hi('missed_list')}${t('missed_list')}</h3><table class="dk-tbl"><thead><tr><th>${t('date_h')}</th><th>${t('pair_h')}</th><th>${t('subj_h')}</th><th class="r">${t('status_h')}</th></tr></thead>
        <tbody>${d.absences.slice(0, 60).map(x => `<tr><td>${esc(x.weekday)}, ${dateLabel(x.date)}</td><td class="num">${esc(t('pairN', { n: x.pair }))}</td><td>${esc(x.subject)}</td>
          <td class="r"><span class="pill ${x.status === 'kelmadi' ? 'bordo' : 'warn'}">${t(x.status)}</span></td></tr>`).join('')}</tbody></table></div>`
      : `<div class="card">${empty('ok', t('nothing_missed'))}</div>`;
    page({ title: t('attendance'), sub: c.name, active: '#/attendance', wide: true, body: `<div class="dk-grid att">
      <div class="dk-col">${summary}${levels}</div><div class="dk-col">${weeks}${subj}</div></div>${missed}` });
    animateRings();
    return;
  }
  const body = switcher() + `
    <div class="card"><div style="display:flex;gap:16px;align-items:center">${ring(a.percent, 96, 10)}
      <div><div class="bigstat"><b class="num">${a.percent != null ? a.percent + '%' : '—'}</b></div><div class="muted">${t('since_start')}</div></div></div>
      <div class="kv" style="margin-top:14px"><span>${t('unexcused')}</span><b class="num">${pairs(a.counted_hours)}</b></div>
      <div class="kv"><span>${t('excused')}</span><b class="num">${pairs(a.excused_hours)}</b></div>
      <p class="small muted" style="margin:8px 0 0">${esc(a.note)}</p></div>
    <section class="section"><div class="section-head"><h2>${hi('levels')}${t('levels')}</h2></div>
      <div class="card">${ladder(a)}<p style="margin:12px 0 0" class="${a.level >= 0 ? '' : 'muted'}">${esc(next)}</p></div></section>
    ${d.weeks && d.weeks.length > 1 ? `<section class="section"><div class="section-head"><h2>${hi('by_week')}${t('by_week')}</h2><a href="#/trends">${t('trends')}</a></div><div class="card">${weekChart(d.weeks)}</div></section>` : ''}
    <section class="section"><div class="section-head"><h2>${hi('missed')}${t('missed')}</h2></div>
      ${d.absences.length ? `<div class="list">${Object.entries(byDate).slice(0, 30).map(([day, items]) => `<div class="row" style="cursor:default;align-items:flex-start">
        <div class="body"><div class="t">${esc(items[0].weekday)}, ${dateLabel(day)}</div>${items.map(x => `<div class="d">${t('pairN', { n: x.pair })} — ${esc(x.subject)}</div>`).join('')}</div>
        <div class="end">${items.map(x => `<div><span class="pill ${x.status === 'kelmadi' ? 'bordo' : 'warn'}">${t(x.status)}</span></div>`).join('')}</div></div>`).join('')}</div>`
        : hp.length ? `<div class="list">${hp.map(p => `<div class="row" style="cursor:default"><div class="body">
            <div class="t">${p.from ? `${dateLabel(p.from)} — ${dateLabel(p.as_of)}` : t('until', { d: dateLabel(p.as_of) })}</div>
            <div class="d">${t('hemis_missed')}</div></div>
            <div class="end"><div><span class="pill ${p.unexcused ? 'bordo' : 'warn'}">${t('unexcused_n', { a: pairs(p.unexcused) })}</span></div>
              ${p.excused ? `<div class="small muted" style="margin-top:4px">${t('excused_n', { b: pairs(p.excused) })}</div>` : ''}</div></div>`).join('')}</div>
            <p class="small muted" style="margin:8px 4px 0">${t('hemis_missed_note')}</p>`
        : `<div class="list">${empty('ok', t('nothing_missed'))}</div>`}</section>
    ${d.subjects.length ? `<section class="section"><div class="section-head"><h2>${hi('by_subject')}${t('by_subject')}</h2></div><div class="list">${d.subjects.map(s => {
      const pct = s.total ? Math.round(100 * (s.keldi + s.kechikdi) / s.total) : 0;
      return `<div class="subject"><div><div class="t" style="font-weight:600">${esc(s.subject)}</div><div class="small muted">${t('kelmadi')}: ${s.kelmadi} · ${t('sababli')}: ${s.sababli}</div></div>
        <b class="num">${pct}%</b><div class="meter"><i style="width:${pct}%"></i></div></div>`;
    }).join('')}</div></section>` : ''}
    ${d.hemis.length ? `<section class="section"><div class="section-head"><h2>${hi('HEMIS')}HEMIS</h2></div><div class="list">${d.hemis.slice().reverse().map(h =>
      `<div class="row" style="cursor:default"><div class="body"><div class="t">${dateLabel(h.as_of, true)}</div><div class="d">${t('unexcused')}: ${pairs(h.counted)}</div></div></div>`).join('')}</div></section>` : ''}`;
  page({ title: t('attendance'), sub: c.short, active: '#/attendance', body });
  animateRings();
}

/* ================================================================ jadval */
async function viewSchedule(week) {
  const c = S.child;
  page({ title: t('schedule'), sub: c.short, active: '#/schedule', body: switcher() + loading() });
  let d;
  try { d = await api(childPath(c, 'schedule') + (week ? `?week=${week}` : '')); } catch (e) { return page({ title: t('schedule'), active: '#/schedule', body: errorBox() }); }
  S.cache.schedule = d;
  const todayIdx = d.days.findIndex(x => x.today);
  S.cache.day = S.cache.day != null && week ? S.cache.day : (todayIdx >= 0 ? todayIdx : 0);
  renderSchedule();
}
function renderSchedule() {
  const d = S.cache.schedule, i = S.cache.day, day = d.days[i], c = S.child;
  if (deskMode()) {  // kompyuter: butun hafta bir qarashda — kunlar ustunlar
    const nav = `<div class="dk-weeknav"><button class="btn ghost" data-act="week" data-week="${d.prev}">${ic('left')}${t('prev')}</button>
      <div><b>${dateLabel(d.days[0].date)} – ${dateLabel(d.days[d.days.length - 1].date)}</b><span class="muted small">${t(d.week_type)}</span></div>
      <button class="btn ghost" data-act="week" data-week="${d.next}">${t('next')}${ic('chev')}</button></div>`;
    const st = l => l.status ? `<span class="pill ${l.status === 'keldi' ? 'ok' : l.status === 'kelmadi' ? 'bordo' : 'warn'}">${t(l.status)}</span>` : '';
    const grid = `<div class="dk-week">${d.days.map(x => `<section class="dk-day${x.today ? ' today' : ''}">
      <header><b>${esc(x.weekday)}</b><span>${new Date(x.date + 'T00:00:00').getDate()}${x.today ? ` · ${t('today_word')}` : ''}</span></header>
      ${x.lessons.length ? x.lessons.map(l => `<article class="dk-lesson">
        <div class="tm num">${l.start ? `${esc(l.start)}–${esc(l.end || '')}` : esc(t('pairN', { n: l.pair }))}</div>
        <b>${esc(l.subject)}</b>
        <div class="meta">${l.type ? `<span class="pill">${esc(l.type)}${l.subgroup ? ' ' + esc(l.subgroup) : ''}</span>` : ''}${st(l)}</div>
        ${l.room || l.teacher ? `<small>${[l.room, l.teacher].filter(Boolean).map(esc).join(' · ')}</small>` : ''}${lessonAtt(l.att)}</article>`).join('')
        : `<div class="dk-free">${t('no_lessons_short')}</div>`}</section>`).join('')}</div>`;
    page({ title: t('schedule'), sub: c.name, active: '#/schedule', wide: true, body: nav + grid });
    return;
  }
  const body = switcher() + `
    <div class="weeknav"><button data-act="week" data-week="${d.prev}">${ic('left', 'chev')} ${t('prev')}</button>
      <div style="text-align:center"><b>${dateLabel(d.days[0].date)} – ${dateLabel(d.days[5].date)}</b><div class="small muted">${t(d.week_type)}</div></div>
      <button data-act="week" data-week="${d.next}">${t('next')} ${ic('chev', 'chev')}</button></div>
    <div class="seg" role="tablist">${d.days.map((x, k) => `<button role="tab" data-act="day" data-i="${k}" aria-pressed="${k === i}" class="${x.today ? 'today' : ''}">
      ${SHORT_WD[S.lang][k]}<small>${new Date(x.date + 'T00:00:00').getDate()}</small></button>`).join('')}</div>
    <section class="section"><div class="section-head"><h2>${esc(day.weekday)}, ${dateLabel(day.date)}</h2><span class="muted small">${day.lessons.length ? t('lessonsN', { n: day.lessons.length }) : ''}</span></div>
      <div class="list">${day.lessons.length ? day.lessons.map(l => lessonRow(l)).join('') : empty('cal', t('no_lessons'))}</div></section>`;
  page({ title: t('schedule'), sub: c.short, active: '#/schedule', body });
}

/* ================================================================ baholar */
async function viewGrades() {
  const c = S.child;
  page({ title: t('grades'), sub: c.short, active: '#/grades', body: switcher() + loading() });
  let d;
  try { d = await api(childPath(c, 'grades')); } catch (e) { return page({ title: t('grades'), active: '#/grades', body: errorBox() }); }
  if (!d.semesters.length) return page({ title: t('grades'), sub: c.short, active: '#/grades', body: switcher()
    + (d.debts ? `<a class="card desk-card" href="#/debts" style="margin-bottom:14px"><span class="ic-badge" style="color:var(--bordo-fg)">${ic('alert')}</span>
      <div style="flex:1;text-align:left"><b style="display:block">${t('acad')}: ${d.debts}</b><span class="muted small">${t('open')}</span></div>${ic('chev')}</a>` : '')
    + empty('grade', t('no_data')) });
  if (deskMode()) {
    const head = `<div class="dk-kpis">
      <div class="tile st-tile ${d.gpa_low ? 'bad' : ''}">${tk(t('gpa_long'), 'grade', 'gpa')}<span class="v num">${d.gpa != null ? gpaNum(d.gpa) : '—'}<small class="of"> / 5</small></span>
        <span class="s">${[d.gpa_as_of ? `HEMIS · ${dateLabel(d.gpa_as_of, true)}` : '', d.gpa_low ? t('gpa_low', { min: limNum(d.gpa_min) }) : (d.gpa_as_of ? '' : t('gpa_hint'))].filter(Boolean).join(' · ')}</span></div>
      <a class="tile st-tile ${d.debts ? 'bad' : 'ok'}" href="${d.debts ? '#/debts' : '#/grades'}">${tk(t('acad'), 'bookx', 'acad')}
        <span class="v">${d.debts ? `${d.debts}<small class="of"> ${esc(subjUnit(d.debts))}</small>` : t('no_debt')}</span><span class="s">${d.debts ? t('open') : ''}</span></a>
      <div class="tile st-tile">${tk(t('grade_scale'), 'grade', 'people')}<div class="dk-scale">${[['90–100', 5], ['70–89', 4], ['60–69', 3], ['0–59', 2]].map(([r, g]) =>
        `<span><i class="grade g${g}">${g}</i><small class="num">${r}</small></span>`).join('')}</div></div></div>`;
    const sems = d.semesters.map(sm => `<section class="card"><div class="section-head" style="margin:0 0 4px"><h2>${hi('semN')}${t('semN', { n: sm.semester })}</h2>${sm.gpa != null ? `<span class="muted num">GPA ${gpaNum(sm.gpa)}</span>` : ''}</div>
      <table class="dk-tbl"><thead><tr><th>${t('subj_h')}</th><th class="r">${t('credits_h')}</th><th style="width:38%">${t('score_h')}</th><th class="r">${t('grade_h')}</th></tr></thead><tbody>
      ${sm.subjects.map(g => `<tr class="${g.debt ? 'debt' : ''}"><td><b>${esc(g.subject)}</b>${g.debt ? `<div class="small" style="color:var(--bordo-fg)">${t('debt_subject')}</div>` : ''}</td>
        <td class="r num">${g.credits ? num(g.credits) : '—'}</td>
        <td><div class="dk-bar"><i style="width:${Math.min(100, g.score)}%"></i></div><span class="num small">${num(g.score)} / 100</span></td>
        <td class="r"><span class="grade g${g.grade}">${g.grade}</span></td></tr>`).join('')}</tbody></table></section>`).join('');
    return page({ title: t('grades'), sub: c.name, active: '#/grades', wide: true, body: head + sems });
  }
  const body = switcher() + `<div class="card" style="display:flex;justify-content:space-between;align-items:center">
      <div><div class="muted small">${t('gpa_long')}</div><div class="bigstat"><b class="num">${d.gpa != null ? gpaNum(d.gpa) : '—'}</b><span class="muted">/ 5</span></div>${d.gpa_as_of ? `<div class="small muted">HEMIS · ${dateLabel(d.gpa_as_of, true)}</div>` : ''}${d.gpa_low ? `<div class="small" style="color:var(--bordo-fg);font-weight:600;margin-top:2px">${t('gpa_low', { min: limNum(d.gpa_min) })}</div>` : ''}</div>
      ${d.debts ? `<a class="pill bordo" href="#/debts" style="font-size:14px;padding:8px 12px">${t('acad')}: ${d.debts} ${ic('chev')}</a>` : `<span class="pill ok" style="font-size:14px;padding:8px 12px">${t('acad')}: ${t('no_debt').toLowerCase()}</span>`}</div>
    ${d.semesters.map(s => `<section class="section"><div class="section-head"><h2>${hi('semN')}${t('semN', { n: s.semester })}</h2>${s.gpa != null ? `<span class="muted num">GPA ${gpaNum(s.gpa)}</span>` : ''}</div>
      <div class="list">${s.subjects.map(g => `<div class="subject ${g.debt ? 'debt' : ''}"><div><div style="font-weight:600">${esc(g.subject)}</div>
        <div class="small muted num">${num(g.score)} / 100${g.credits ? ' · ' + num(g.credits) + ' ' + t('credits') : ''}${g.debt ? ' · <span style="color:var(--bordo-fg)">' + t('debt_subject') + '</span>' : ''}</div></div>
        <div class="grade g${g.grade}">${g.grade}</div><div class="meter"><i style="width:${Math.min(100, g.score)}%"></i></div></div>`).join('')}</div></section>`).join('')}
    <section class="section"><div class="card"><div class="section-head" style="margin:0 0 8px"><h2>${hi('grade_scale')}${t('grade_scale')}</h2></div>
      <div class="grid2" style="grid-template-columns:repeat(4,1fr);gap:8px">${[['90–100', 5], ['70–89', 4], ['60–69', 3], ['0–59', 2]].map(([r, g]) =>
        `<div style="text-align:center"><div class="grade g${g}" style="margin:0 auto 4px">${g}</div><span class="small muted num">${r}</span></div>`).join('')}</div></div></section>`;
  page({ title: t('grades'), sub: c.short, active: '#/grades', body });
}

/* ================================================================ yozishma */
async function viewChat() {
  const c = S.child;
  page({ title: t('messages'), sub: c.short, active: '#/chat', body: switcher() + loading() });
  await refreshChat(true);
}
async function refreshChat(first) {
  const c = S.child;
  let d;
  try { d = await api(childPath(c, 'messages')); } catch (e) { if (first) page({ title: t('messages'), active: '#/chat', body: errorBox() }); return; }
  if (S.me.unread) { S.me.unread.messages = 0; }
  const tutor = d.tutor || {};
  const draft = document.querySelector('.composer textarea');
  const keep = draft ? draft.value : '';
  let lastDay = '';
  const msgs = d.messages.map(m => {
    const day = new Date(m.at).toDateString();
    const sep = day !== lastDay ? `<div class="daysep">${dateLabel(m.at)}</div>` : '';
    lastDay = day;
    return sep + `<div class="bubble ${m.sender === 'parent' ? 'me' : 'them'}">${m.sender === 'staff' && m.author ? `<div class="who">${esc(m.author)}</div>` : ''}${esc(m.text)}<time>${new Date(m.at).toTimeString().slice(0, 5)}</time></div>`;
  }).join('');
  const body = switcher() + `<div class="chat-head"><div class="av">${esc((tutor.name || '?').trim().charAt(0))}</div>
      <div style="flex:1"><b>${esc(tutor.name || t('coordinator'))}</b><div class="small muted">${t('coordinator')}</div></div>
      ${tutor.phone ? `<a class="icon-btn" style="background:var(--tint-navy);color:var(--accent)" href="tel:+${esc(tutor.phone)}" aria-label="${t('call_tutor')}">${ic('phone')}</a>` : ''}</div>
    <div class="msgs">${msgs || empty('chat', t('no_msgs'), t('no_msgs_sub'))}</div>
    <form class="composer" data-act="send"><textarea class="input" name="text" rows="1" placeholder="${t('type_msg')}" aria-label="${t('type_msg')}" maxlength="3000">${esc(keep)}</textarea>
      <button class="send" type="submit" aria-label="${t('write')}">${ic('send')}</button></form>`;
  if (deskMode()) {
    page({ title: t('messages'), sub: c.name, active: '#/chat', body: `<div class="dk-chat">${body}</div>` });
    const box = document.querySelector('.dk-chat .msgs'); if (box) box.scrollTop = box.scrollHeight;
  } else {
    page({ title: t('messages'), sub: c.short, active: '#/chat', body, noNav: true });
    window.scrollTo(0, document.body.scrollHeight);
  }
  clearInterval(S.timer);
  S.timer = setInterval(() => { if (location.hash.startsWith('#/chat') && !document.hidden) refreshChat(false); }, 15000);
}

/* ================================================================ bildirishnomalar, e'lonlar */
/* bildirishnoma turi → belgi, rang va ochiladigan bo'lim */
const NOTE_KIND = {
  present: { icon: 'ok', route: '/attendance', tone: 'ok' },
  att: { icon: 'att', route: '/attendance', tone: 'navy' }, pay: { icon: 'wallet', route: '/finance', tone: 'bordo' },
  grade: { icon: 'grade', route: '/grades', tone: 'navy' }, acad: { icon: 'grade', route: '/debts', tone: 'bordo' },
  doc: { icon: 'file', route: '/documents', tone: 'bordo' },
  news: { icon: 'mega', route: '/news', tone: 'navy' }, chat: { icon: 'chat', route: '/chat', tone: 'navy' },
  digest: { icon: 'cal', route: '/', tone: 'navy' }, link: { icon: 'users', route: '/', tone: 'ok' },
  survey: { icon: 'poll', route: '/surveys', tone: 'bordo' }, reg: { icon: 'book', route: '/regulations', tone: 'navy' },
};
const GO_ROUTE = Object.fromEntries(Object.entries(NOTE_KIND).map(([k, v]) => [k, v.route]));
const PICTO = /^[\p{Extended_Pictographic}\uFE0F\u200D\s]+/u;
/* turi yozilmagan (eski) bildirishnomalar — birinchi belgidan */
function guessKind(plain) {
  const e = (plain.trim().match(/^\p{Extended_Pictographic}/u) || [''])[0];
  if ('💰💳'.includes(e) && e) return 'pay';
  if ('📝❗📚'.includes(e) && e) return 'grade';
  if ('📊🔔📏⚠🚫'.includes(e) && e) return 'att';
  if (e === '✅') return /to[‘'’]lov|оплат|payment/i.test(plain) ? 'pay' : 'att';
  if (e === '🌙') return 'digest';
  if (e === '📄') return 'doc';
  if (e === '📢') return 'news';
  if (e === '🔗') return 'link';
  return '';
}
/* botdagi tugmalarga ishora qiluvchi gaplar ilovada kerak emas («… → «💰 …»», «… «✉️ …» bo‘limi …») */
const BOT_NAV = /→\s*[«“"]\s*\p{Extended_Pictographic}|[«“"]\s*(✉️|💰|📚|📝|📊|📅|📄|📈)/u;
function cleanBody(lines) {
  const out = [];
  for (const line of lines) {
    const kept = line.split(/(?<=[.!?])\s+/).filter(x => !BOT_NAV.test(x)).join(' ').trim();
    if (kept || (out.length && out[out.length - 1] !== '')) out.push(kept);
  }
  while (out.length && out[out.length - 1] === '') out.pop();
  return out;
}
function noteCard(n) {
  const plain = n.text.replace(/<[^>]+>/g, '');
  const kind = n.kind || guessKind(plain);
  const meta = kind === 'att' && /❌|sababsiz|прогул|unexcused/i.test(plain) ? { ...NOTE_KIND.att, icon: 'alert', tone: 'bordo' }
    : NOTE_KIND[kind] || { icon: 'bell', tone: 'navy' };
  const lines = n.text.split('\n');
  while (lines.length && !lines[0].replace(/<[^>]+>/g, '').trim()) lines.shift();
  const title = (lines.shift() || '').replace(/^((?:<[^>]+>)*)([\p{Extended_Pictographic}\uFE0F\u200D\s]+)/u, '$1');
  let child = '';
  const rest = [];
  for (const l of lines) {
    const pl = l.replace(/<[^>]+>/g, '').trim();
    if (!child && /^👨‍🎓/u.test(pl)) { child = pl.replace(PICTO, ''); continue; }
    rest.push(l);
  }
  const body = cleanBody(rest);
  const href = kind && n.student_id && n.course ? `#/go/${kind}/${encodeURIComponent(n.course)}/${n.student_id}` : (meta.route ? '#' + meta.route : '');
  return `<article class="ncard ${n.read ? '' : 'unread'}">${n.read ? '' : '<i class="ndot" aria-hidden="true"></i>'}
    <span class="nic ${meta.tone}">${ic(meta.icon)}</span>
    <div class="nbody"><div class="ntitle">${safeHtml(title)}</div>
      ${child ? `<div class="nchild">${esc(child)}</div>` : ''}
      ${body.length ? `<div class="ntext">${safeHtml(body.join('\n')).replace(/\n/g, '<br>')}</div>` : ''}
      <div class="nfoot"><time>${ic('clock')}${when(n.at)}</time>${!n.read ? `<span class="nnew">${t('note_new')}</span>` : href ? `<a class="nopen" href="${href}">${t('open')}${ic('chev')}</a>` : ''}</div>
    </div></article>`;
}
async function viewNotifications() {
  page({ title: t('notifications'), body: loading(), noNav: false, active: '' });
  let d;
  try { d = await api('/api/notifications'); } catch (e) { return page({ title: t('notifications'), body: errorBox() }); }
  const unread = d.items.filter(n => !n.read).length;
  const summary = `<section class="nsum" aria-label="${t('notifications')}">
    <div class="nsum-row"><div><span class="nsum-ic">${ic('bell')}</span><b class="num">${d.items.length}</b><span>${t('notes_all')}</span></div>
      <div><span class="nsum-ic">${ic('checks')}</span><b class="num">${unread}</b><span>${t('notes_unread')}</span></div></div>
    <div class="nsum-upd">${ic('clock')}${t('notes_updated', { t: d.items.length ? when(d.items[0].at) : '—' })}</div></section>`;
  const body = `<h2 class="screen-title">${t('notifications')}</h2>${summary}
    ${d.items.length ? `<div class="nlist">${d.items.map(noteCard).join('')}</div>`
      : `<div class="list">${empty('bell', t('no_notes'), t('no_notes_sub'))}</div>`}`;
  page({ title: t('notifications'), body, active: '' });
  if (d.items.some(n => !n.read)) { api('/api/notifications/read', { method: 'POST', json: {} }).then(() => { S.me.unread.notifications = 0; }).catch(() => {}); }
}
async function viewNews() {
  page({ title: t('news'), body: loading(), active: '' });
  let d;
  try { d = await api('/api/announcements'); } catch (e) { return page({ title: t('news'), body: errorBox() }); }
  page({ title: t('news'), active: '', body: `<h2 class="screen-title">${t('news')}</h2>${d.items.length
    ? d.items.map(a => `<article class="card"><div class="small muted">${when(a.at)}</div><div style="margin-top:6px;white-space:pre-wrap">${safeHtml(a.text)}</div></article>`).join('')
    : `<div class="list">${empty('mega', t('no_news'))}</div>`}` });
}

/* ================================================================ moliya, hujjatlar, dinamika */
function moneyCard(title, p, icon = 'dollar', c = 'money') {
  title = `<span class="mc-t"><span class="t-ic c-${c}" aria-hidden="true">${ic(icon)}</span>${title}</span>`;
  if (!p || p.state === 'none') return `<div class="card money"><div class="muted small">${title}</div><p class="muted">${t('not_loaded')}</p></div>`;
  if (p.state === 'grant') return `<div class="card money"><div class="muted small">${title}</div><p><span class="pill ok">${t('grant_note')}</span></p></div>`;
  const pct = p.percent != null ? Math.round(p.percent) : null;
  return `<div class="card money"><div class="muted small">${title}</div>
    <div class="amount num" style="color:${p.debt > 0 ? 'var(--bordo-fg)' : 'var(--ok)'}">${p.debt > 0 ? money(p.debt) : t('no_debt')}</div>
    ${pct != null ? `<div class="progress"><i style="width:${Math.min(100, pct)}%"></i></div><div class="small muted num">${t('paid')}: ${pct}%</div>` : ''}
    ${p.contract ? `<div class="kv" style="margin-top:10px"><span>${t('contract')}</span><b class="num">${money(p.contract)}</b></div>` : ''}
    ${p.paid != null ? `<div class="kv"><span>${t('paid')}</span><b class="num">${money(p.paid)}</b></div>` : ''}
    ${p.deadline ? `<div class="kv"><span>${t('deadline')}</span><b>${dateLabel(p.deadline, true)} ${p.debt > 0 ? `<span class="pill ${p.days_left < 0 ? 'bordo' : 'warn'}">${p.days_left < 0 ? t('overdue') : t('days_left', { n: p.days_left })}</span>` : ''}</b></div>` : ''}
    ${p.history && p.history.length > 1 ? `<div class="muted small" style="margin-top:12px">${t('history')}</div><ul class="hist">${p.history.map(h => `<li><span>${dateLabel(h.as_of, true)}</span><b class="num">${money(h.debt)}</b></li>`).join('')}</ul>` : ''}
    <div class="small muted" style="margin-top:10px">${p.as_of ? t('updated', { t: dateLabel(p.as_of, true) }) : ''}</div></div>`;
}
async function viewFinance() {
  const c = S.child;
  page({ title: t('finance'), sub: c.short, body: switcher() + loading(), active: '' });
  let d;
  try { d = await api(childPath(c, 'finance')); } catch (e) { return page({ title: t('finance'), body: errorBox() }); }
  page({ title: t('finance'), sub: deskMode() ? `${c.name}${d.payment_form ? ' · ' + d.payment_form : ''}` : c.short, active: '', wide: deskMode(),
    body: switcher() + `<h2 class="screen-title">${t('finance')}</h2>${d.payment_form && !deskMode() ? `<p class="screen-sub">${esc(d.payment_form)}</p>` : ''}
    <div class="dk-pair">${moneyCard(t('contract_pay'), d.kontrakt)}${moneyCard(t('trimester_pay'), d.trimestr, 'receipt', 'money2')}</div>` });
}
async function viewDocs() {
  const c = S.child;
  page({ title: t('documents'), sub: c.short, body: switcher() + loading(), active: '' });
  let d;
  try { d = await api(childPath(c, 'documents')); } catch (e) { return page({ title: t('documents'), body: errorBox() }); }
  page({ title: t('documents'), sub: c.short, active: '', body: switcher() + `<h2 class="screen-title">${t('documents')}</h2>${d.documents.length
    ? `<div class="list">${d.documents.map(x => `<div class="row" style="cursor:default"><div class="ic bordo">${ic('file')}</div><div class="body"><div class="t">${esc(x.title)}</div>
        <div class="d">${dateLabel(x.date, true)}${x.comment ? ' — ' + esc(x.comment) : ''}</div></div>
        <a class="btn" style="min-height:40px;padding:0 14px" href="#/doc/${x.id}">${t('open_doc')}</a></div>`).join('')}</div>`
    : `<div class="list">${empty('file', t('no_docs'), t('no_docs_sub'))}</div>`}` });
}
async function viewTrends() {
  const c = S.child;
  page({ title: t('trends'), sub: c.short, body: switcher() + loading(), active: '' });
  let d;
  try { d = await api(childPath(c, 'trends')); } catch (e) { return page({ title: t('trends'), body: errorBox() }); }
  const g = d.grades;
  const comp = g.items.length ? (g.compared || []).filter(x => x.old != null) : [];  // ball o'zgarmagan — grafik shart emas
  const cmpChart = comp.length ? `<svg class="chart" viewBox="0 0 320 ${comp.length * 46 + 10}" role="img" aria-label="${t('by_subject')}">${comp.map((x, i) => {
    const y = i * 46 + 6, wOld = x.old * 1.8, wNew = x.new * 1.8;
    return `<text x="0" y="${y + 10}">${esc(x.subject.slice(0, 34))}</text>
      <rect x="0" y="${y + 15}" width="${wOld}" height="9" rx="4" fill="var(--line)"/><text x="${wOld + 6}" y="${y + 23}">${num(x.old)}</text>
      <rect x="0" y="${y + 27}" width="${wNew}" height="9" rx="4" fill="${x.new < 60 ? 'var(--bordo-500)' : 'var(--navy-500)'}"/><text x="${wNew + 6}" y="${y + 35}">${num(x.new)}</text>`;
  }).join('')}<line x1="108" x2="108" y1="0" y2="${comp.length * 46 + 10}" stroke="var(--bordo-500)" stroke-dasharray="3 3"/></svg>
    <div class="chips small muted" style="margin-top:8px"><span><span class="pill" style="background:var(--line);color:var(--muted)">${g.month ? t('month_ago') : dateLabel(g.ref)}</span></span><span class="pill">${t('now')}</span><span class="small muted">60 — «3»</span></div>` : '';
  const ups = d.uploads || [], sems = (d.semesters || []).filter(x => x.avg != null);
  S.gpaMin = d.gpa_min;
  // yuklangan fayllar bo'yicha: har bir ko'rsatkich — qiymat, o'zgarish, grafik va barcha nuqtalar (sana: qiymat)
  const upHtml = ups.length ? `<section class="section"><div class="section-head"><h2>${hi('by_upload')}${t('by_upload')}</h2></div><div class="card dyn">${ups.map(it => { const dl = dynDelta(it); return `<div class="dyn-row">${dynIc(it)}
      <div class="body"><div class="t">${esc(it.title)}</div><div class="d">${it.points.map(p => `${esc(p.label)}: ${esc(dynVal(it, p.value))}`).join(' → ')}</div></div>
      ${spark(it.points, dl.cls)}<div class="val"><b class="num">${esc(dynVal(it, it.value))}</b><span class="${dl.cls}">${esc(dl.txt)}</span></div></div>`; }).join('')}</div></section>` : '';
  // semestrlar bo'yicha: GPA ustunlari va har bir semestr — oldingisiga nisbatan
  const semHtml = sems.length ? `<section class="section"><div class="section-head"><h2>${hi('by_semester')}${t('by_semester')}</h2></div><div class="card">
      ${sems.length > 1 ? `<div class="sem-bars">${sems.map(x => `<div class="sem-bar"><b class="num">${num(x.avg)}</b><i style="height:${Math.max(6, Math.round(x.avg / 100 * 90))}px" class="${x.avg < 60 ? 'low' : ''}"></i><span>${esc(semLabel(x.semester))}</span></div>`).join('')}</div>` : ''}
      ${sems.map((x, i) => { const p = sems[i - 1]; const dg = p ? Math.round((x.avg - p.avg) * 10) / 10 : null;
        return `<div class="kv" style="margin-top:${i ? 8 : 12}px"><span><b>${esc(semLabel(x.semester))}</b> · ${x.subjects} ${t('subj_h').toLowerCase()}</span>
          <b class="num">${t('avg_score')} ${num(x.avg)}${dg ? ` <span style="color:${dg > 0 ? 'var(--ok)' : 'var(--bordo-fg)'}">${dg > 0 ? '▲' : '▼'} ${num(Math.abs(dg))}</span>` : ''}</b></div>`; }).join('')}</div></section>` : '';
  page({ title: t('trends'), sub: c.short, active: '', body: switcher() + `<h2 class="screen-title">${t('trends')}</h2>
    ${upHtml}${semHtml}
    ${d.periods.length > 1 ? `<section class="section"><div class="section-head"><h2>${hi('by_week')}${t('by_week')}</h2></div><div class="card">${weekChart(d.periods)}</div></section>` : ''}
    ${g.items.length ? `<section class="section"><div class="section-head"><h2>${hi('by_subject')}${t('by_subject')}</h2>${g.gpa_old != null && g.gpa_new != null ? `<span class="muted num">GPA ${gpaNum(g.gpa_old)} → <b>${gpaNum(g.gpa_new)}</b></span>` : ''}</div>
      <div class="list">${g.items.map(x => `<div class="row" style="cursor:default"><div class="ic ${x.delta < 0 ? 'bordo' : ''}">${ic('trend')}</div><div class="body"><div class="t">${esc(x.subject)}</div>
        <div class="d num">${num(x.old)} → ${num(x.new)}${x.old_grade !== x.new_grade ? ` · «${x.old_grade}» → «${x.new_grade}»` : ''}</div></div>
        <b class="num" style="color:${x.delta < 0 ? 'var(--bordo-fg)' : 'var(--ok)'}">${x.delta > 0 ? '+' : '−'}${num(Math.abs(x.delta))}</b></div>`).join('')}</div></section>` : ''}
    ${cmpChart ? `<section class="section"><div class="card">${cmpChart}</div></section>` : ''}
    ${d.periods.length < 2 && !g.items.length && !ups.length && !sems.length ? `<div class="list">${empty('trend', t('no_trends'))}</div>` : ''}` });
}

/* ================================================================ menyu, sozlamalar, ma'lumot */
function viewMenu() {
  const items = [['#/surveys', 'poll', t('surveys')], ['#/regulations', 'book', t('regs')],
    ['#/finance', 'wallet', t('finance')], ['#/documents', 'file', t('documents')], ['#/trends', 'trend', t('trends')],
    ['#/news', 'mega', t('news')], ['#/info', 'info', t('info')], ['#/settings', 'gear', t('settings')]];
  page({ title: t('menu'), active: '', body: `<h2 class="screen-title">${t('menu')}</h2><div class="list">${items.map(([h, i, l]) =>
    `<a class="row" href="${h}"><div class="ic">${ic(i)}</div><div class="body"><div class="t">${esc(l)}</div></div>${ic('chev', 'chev')}</a>`).join('')}</div>` });
}
async function viewSettings() {
  page({ title: t('settings'), body: loading(), active: '' });
  let d;
  try { d = await api('/api/settings'); } catch (e) { return page({ title: t('settings'), body: errorBox() }); }
  const langs = [['uz', 'O‘zbekcha'], ['ru', 'Русский'], ['en', 'English']];
  page({ title: t('settings'), active: '', body: `<h2 class="screen-title">${t('settings')}</h2>
    <section class="section"><div class="section-head"><h2>${hi('lang')}${t('lang')}</h2></div><div class="seg">${langs.map(([k, l]) =>
      `<button data-act="lang" data-lang="${k}" aria-pressed="${S.lang === k}">${l}</button>`).join('')}</div></section>
    <section class="section"><div class="section-head"><h2>${hi('theme')}${t('theme')}</h2></div><div class="seg">${['auto', 'light', 'dark'].map(k =>
      `<button data-act="theme-set" data-v="${k}" aria-pressed="${themePref() === k}">${t('th_' + k)}</button>`).join('')}</div></section>
    <section class="section"><div class="section-head"><h2>${hi('flags')}${t('flags')}</h2></div><div class="list">${Object.entries(d.flags).map(([k, v]) =>
      `<label class="row"><div class="body"><div class="t">${t(k)}</div></div><span class="switch"><input type="checkbox" data-act="flag" data-key="${k}" ${v ? 'checked' : ''}><i></i></span></label>`).join('')}</div></section>
    ${logoutBlock()}` });
}
function logoutBlock() {  // telefon ilovasi / brauzer: shu qurilmadan chiqish (Telegram ichida kerak emas)
  return S.me && S.me.app_session ? `<section class="section"><button class="btn ghost block" data-act="logout">${t('logout')}</button>
    <p class="small muted" style="text-align:center">${t('devices_hint')}</p></section>` : '';
}
async function viewInfo() {
  page({ title: t('info'), body: loading(), active: '' });
  let d;
  try { d = await api('/api/info'); } catch (e) { return page({ title: t('info'), body: errorBox() }); }
  page({ title: t('info'), active: '', body: `<h2 class="screen-title">${t('info')}</h2>
    ${d.tutors.map(x => `<div class="card" style="display:flex;align-items:center;gap:12px"><div class="chat-head" style="padding:0;box-shadow:none;background:none;flex:1">
      <div class="av">${esc((x.name || '?').charAt(0))}</div><div><b>${esc(x.name || '')}</b><div class="small muted">${t('coordinator')} — ${esc(x.children.join(', '))}</div></div></div>
      ${x.phone ? `<a class="btn ghost" href="tel:+${esc(x.phone)}">${ic('phone')}${t('call')}</a>` : ''}</div>`).join('')}
    <section class="section"><div class="section-head"><h2>${hi('levels')}${t('levels')}</h2></div><div class="list">${d.levels.map((l, i) =>
      `<div class="row" style="cursor:default"><div class="ic ${i === d.levels.length - 1 ? 'bordo' : ''}"><b class="num">${i + 1}</b></div><div class="body"><div class="t num">${pairs(l.hours)}</div><div class="d">${esc(l.action)}</div></div></div>`).join('')}</div></section>
    <section class="section"><div class="section-head"><h2>${hi('grade_scale')}${t('grade_scale')}</h2></div><div class="list">${d.grades.map(g =>
      `<div class="row" style="cursor:default"><div class="grade g${g.grade}">${g.grade}</div><div class="body"><div class="t num">${g.range}</div></div></div>`).join('')}</div></section>
    ${d.texts.map(x => `<div class="card" style="margin-top:16px;white-space:pre-wrap">${safeHtml(x)}</div>`).join('')}` });
}

/* ================================================================ ro'yxatdan o'tish */
// Bog'lash — uch qadam: 1 telefon (Telegram tasdiqlaydi) → 2 farzand (topilmasa — F.I.Sh. + sana) → 3 tasdiqlash
function steps(n) {
  const L = [t('step_phone'), t('step_child'), t('step_confirm')];
  return `<ol class="wizard">${L.map((l, i) => `<li class="${i + 1 < n ? 'done' : i + 1 === n ? 'on' : ''}"><span>${i + 1 < n ? ic('ok') : i + 1}</span>${esc(l)}</li>`).join('')}</ol>`;
}
/* ================================================================ telefon ilovasi / brauzer: Telegram orqali kirish */
function openExternal(url) {
  if (tg && tg.openTelegramLink && /^https:\/\/t\.me\//.test(url)) return tg.openTelegramLink(url);
  if (NATIVE) { location.href = url; return; }  // ilova tashqi havolani Telegram'da (yoki brauzerda) ochadi
  if (!window.open(url, '_blank', 'noopener')) location.href = url;
}
function deviceName() {
  const ua = navigator.userAgent;
  const os = /iPhone|iPad|iPod/.test(ua) ? 'iPhone' : /Android/.test(ua) ? 'Android' : /Mac OS/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : 'Brauzer';
  return `${os} — ${NATIVE ? t('app_word') : t('browser_word')}`;
}
const LOGIN = { code: null, timer: null, until: 0 };
// Kirish jarayoni sahifa qayta yuklansa ham (masalan, telefon brauzeri Telegram'ga o'tib qaytganda) davom etadi
const loginSaved = { get() { try { const v = JSON.parse(sessionStorage.getItem('jiduLogin') || 'null'); return v && v.until > Date.now() ? v : null; } catch (_) { return null; } },
  set(v) { try { v ? sessionStorage.setItem('jiduLogin', JSON.stringify(v)) : sessionStorage.removeItem('jiduLogin'); } catch (_) { /* */ } } };
function viewLogin(msg) {
  clearTimeout(LOGIN.timer); LOGIN.code = null;
  S.lang = store.get('lang') || ((navigator.language || '').startsWith('ru') ? 'ru' : 'uz');
  document.documentElement.lang = S.lang;
  const langs = [['uz', 'O‘zbekcha'], ['ru', 'Русский'], ['en', 'English']];
  const form = `<div class="hero-center"><img class="hero-seal" src="static/jidu-seal.webp" alt="" width="72" height="72"><h2>${t('welcome')}</h2><p class="muted">${t('welcome_sub')}</p></div>
    <div class="seg" style="margin-bottom:16px">${langs.map(([k, l]) => `<button data-act="login-lang" data-lang="${k}" aria-pressed="${S.lang === k}">${l}</button>`).join('')}</div>
    <div class="card" id="login-box">${msg ? `<p class="small" style="margin-top:0;color:var(--bordo-fg)">${esc(msg)}</p>` : ''}<p style="margin-top:0">${t('login_sub')}</p>
      <button class="btn block" data-act="login">${ic('send')}${t('login_tg')}</button>
      <p class="small muted" style="margin-bottom:0">${t('login_note')}</p></div>`;
  $app.innerHTML = deskWide()  // kompyuter: chapda — tanishtiruv, o'ngda — kirish
    ? `<div class="dk-login"><section class="dk-hero"><div class="dk-hero-in"><img src="static/jidu-seal.webp" alt="" width="84" height="84">
        <p class="eyebrow">${t('portal')}</p><h1>${t('hero_title')}</h1>
        <ul>${['hero_1', 'hero_2', 'hero_3'].map((k, i) => `<li>${ic(['att', 'chat', 'bell'][i])}<span>${t(k)}</span></li>`).join('')}</ul>
        <p class="secure">${ic('ok')}${t('hero_secure')}</p></div></section>
      <main class="dk-form">${form}</main></div>`
    : `<main class="no-nav">${form}</main>`;
  const saved = !msg && loginSaved.get();
  if (saved) showPin(saved); else loginSaved.set(null);
}
function showPin(d) {
  LOGIN.code = d.code; LOGIN.until = d.until;
  // Brauzerda — oddiy havola (foydalanuvchi bosadi: telefon brauzerlari server javobidan keyin avtomatik ochilgan
  // oynani bloklaydi); ilovada (Android/iOS) — tugma, havola Telegram'da ochiladi
  const open = NATIVE ? `<button class="btn block" data-act="login-open" data-url="${esc(d.url)}">${ic('send')}${t('login_open_tg')}</button>`
    : `<a class="btn block" href="${esc(d.url)}" target="_blank" rel="noopener">${ic('send')}${t('login_open_tg')}</a>`;
  document.getElementById('login-box').innerHTML = `<p style="margin-top:0">${t('login_pin')}</p><div class="login-pin num">${d.pin}</div>
    ${open}
    <p class="small muted" style="text-align:center;margin-bottom:0">${t('login_wait')}</p>
    <p style="text-align:center;margin:12px 0 0"><a href="#" data-act="login-cancel" class="small">${t('cancel')}</a></p>`;
  pollLogin(d.code);
}
async function startLogin() {
  let d;
  try { d = await api('/api/app/login', { json: { device: deviceName() } }); }
  catch (e) { toast(e.status === 429 ? t('too_many_tries') : t('error')); return; }
  const saved = { code: d.code, pin: d.pin, url: d.url, until: Date.now() + d.expires_in * 1000 };
  loginSaved.set(saved);
  showPin(saved);
  if (NATIVE) openExternal(d.url);
}
async function pollLogin(code) {
  clearTimeout(LOGIN.timer);
  if (LOGIN.code !== code) return;
  const end = msg => { LOGIN.code = null; loginSaved.set(null); return viewLogin(msg); };
  if (Date.now() > LOGIN.until) return end(t('login_expired'));
  let r = { state: 'pending' };
  try { r = await api('/api/app/login/' + encodeURIComponent(code)); } catch (_) { /* tarmoq — qayta urinamiz */ }
  if (LOGIN.code !== code) return;
  if (r.state === 'approved') { LOGIN.code = null; loginSaved.set(null); store.set('appToken', r.token); haptic('success'); return boot(); }
  if (r.state === 'cancelled') return end(t('login_cancelled'));
  if (r.state === 'expired' || r.state === 'used') return end(t('login_expired'));
  LOGIN.timer = setTimeout(() => pollLogin(code), document.hidden ? 4000 : 1500);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && LOGIN.code) pollLogin(LOGIN.code); });
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="login"],[data-act="login-open"],[data-act="login-cancel"],[data-act="login-lang"],[data-act="logout"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const act = b.dataset.act;
  if (act === 'login') { b.disabled = true; await startLogin(); b.disabled = false; }
  else if (act === 'login-open') openExternal(b.dataset.url);
  else if (act === 'login-cancel') { loginSaved.set(null); viewLogin(); }
  else if (act === 'login-lang') { store.set('lang', b.dataset.lang); viewLogin(); }
  else if (act === 'logout') {
    if (!(await confirmSafe(t('logout_q')))) return;
    try { await api('/api/app/logout', { method: 'POST', json: {} }); } catch (_) { /* */ }
    store.set('appToken', null); S.me = null;
    if (LIVE.ctrl) { LIVE.ctrl.abort(); LIVE.ctrl = null; }  // qayta kirganda real vaqt ulanishi yangidan ochilsin
    history.replaceState(null, '', location.pathname + location.search); viewLogin();
  }
}, true);

function viewWelcome() {
  const langs = [['uz', 'O‘zbekcha'], ['ru', 'Русский'], ['en', 'English']];
  $app.innerHTML = `<main class="no-nav"><div class="hero-center"><img class="hero-seal" src="static/jidu-seal.webp" alt="" width="72" height="72"><h2>${t('welcome')}</h2><p class="muted">${esc(S.me.university)}</p></div>
    <div class="seg" style="margin-bottom:16px">${langs.map(([k, l]) => `<button data-act="lang" data-lang="${k}" aria-pressed="${S.lang === k}">${l}</button>`).join('')}</div>
    ${steps(1)}
    <div class="card"><p style="margin-top:0">${t('phone_safe')}</p>
      <button class="btn block" data-act="contact">${ic('phone')}${t('confirm_phone')}</button>
      ${tg || S.me.bot ? '' : `<p class="small muted" style="margin-bottom:0">${t('open_in_tg')}</p>`}</div></main>`;
}
async function viewPending(addMore = false) {
  let reqs = [];
  try { reqs = (await api('/api/link')).requests; } catch (_) { /* */ }
  const form = `<form class="card" data-act="link"><h3 style="margin:0 0 4px">${t('child_title')}</h3><p class="muted small" style="margin:0 0 10px">${t('child_sub')}</p>
    <label class="field"><span>${t('full_name')}</span><input class="input" name="name" required minlength="3" autocomplete="off" placeholder="Aliyev Vali"></label>
    <label class="field"><span>${t('birth_date')}</span><input class="input" name="verify" type="date" required max="${new Date().toISOString().slice(0, 10)}"></label>
    <details class="small muted"><summary>${t('or_hemis')}</summary><label class="field"><span>${t('hemis_id')}</span><input class="input" name="hemis" inputmode="numeric" autocomplete="off"></label></details>
    <button class="btn block" style="margin-top:16px">${t('find_child')}</button></form>`;
  const reqCard = r => `<div class="card req-link"><div class="t"><b>${esc(r.student)}</b> <span class="muted small">${esc(r.group)}</span></div>
    ${r.student_ok ? `<p class="small" style="margin:6px 0 0">${ic('ok')} ${t('student_ok_wait')}</p>` : r.student_can_confirm && r.confirm_url ? `<p class="small" style="margin:6px 0 12px">${t('confirm_student_sub')}</p>
      <button class="btn block" data-act="share-link" data-url="${esc(r.confirm_url)}">${ic('send')}${t('send_to_child')}</button>
      <button class="btn ghost block" style="margin-top:8px" data-act="copy-link" data-url="${esc(r.confirm_url)}">${t('copy_link')}</button>
      <p class="muted small" style="text-align:center;margin:10px 0 0">${t('wait_coord')}</p>`
      : r.needs_phone ? `<form data-act="child-phone" data-id="${r.id}" data-course="${esc(r.course)}"><p class="small" style="margin:6px 0 10px">${t('child_phone_sub')}</p>
        <label class="field"><span>${t('child_phone')}</span><input class="input" name="phone" type="tel" inputmode="tel" required autocomplete="off" placeholder="+998 90 123 45 67"></label>
        <button class="btn block" style="margin-top:12px">${t('find_child')}</button>
        <p class="muted small" style="text-align:center;margin:10px 0 0">${t('no_phone_hint')}</p></form>`
      : `<p class="small muted" style="margin:6px 0 0">${t('coord_only')}</p>`}</div>`;
  const body = reqs.length && !addMore
    ? `${steps(3)}<h2 class="screen-title" style="margin-top:4px">${t('confirm_title')}</h2>${reqs.map(reqCard).join('')}
       <p style="text-align:center;margin-top:16px"><a href="#" data-act="add-child" class="small">${t('add_child')}</a></p>`
    : `${steps(2)}${form}`;
  $app.innerHTML = topbar(t('home')) + `<main class="no-nav">${body}</main>`;
}
document.addEventListener('submit', async e => {
  const f = e.target.closest('form[data-act="child-phone"]');
  if (!f) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const btn = f.querySelector('button'); btn.disabled = true;
  try { await api('/api/link/phone', { json: { id: +f.dataset.id, course: f.dataset.course, phone: f.phone.value } }); haptic('success'); viewPending(); }
  catch (err) { haptic('error'); const code = 'phone_err_' + ((err.data && err.data.error) || ''); toast(T.uz[code] ? t(code) : t('error')); btn.disabled = false; }
}, true);
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="share-link"],[data-act="copy-link"],[data-act="add-child"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (b.dataset.act === 'add-child') return viewPending(true);
  const url = b.dataset.url;
  if (b.dataset.act === 'share-link') {
    const share = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(t('share_text'))}`;
    haptic('light');
    if (tg && tg.openTelegramLink) tg.openTelegramLink(share); else window.open(share, '_blank', 'noopener');
  } else {
    try { await navigator.clipboard.writeText(url); toast(t('link_copied')); } catch (_) { prompt('', url); }
  }
}, true);

/* ================================================================ kurs koordinatori */
function staffRow(r, withCourse = false) {
  const tags = [];
  if (r.flags.att) tags.push(`<span class="pill bordo">${esc(r.action || 'Davomat')}</span>`);
  if (r.flags.acad) tags.push(`<span class="pill bordo">Akademik: ${r.debts.length}</span>`);
  if (r.flags.gpa) tags.push(`<span class="pill bordo">GPA ${gpaNum(r.gpa)}</span>`);
  if (r.kontrakt) tags.push(`<span class="pill warn">Kontrakt: ${money(r.kontrakt)}</span>`);
  if (r.trimestr) tags.push(`<span class="pill warn">Trimestr: ${money(r.trimestr)}</span>`);
  return `<a class="row" href="#/staff/student/${r.id}${withCourse ? '?c=' + encodeURIComponent(r.course) : ''}"><div class="ic cnt ${r.problems >= 3 ? 'bordo' : ''}" title="${r.problems} ta masala" aria-label="${r.problems} ta masala"><b>${r.problems}</b><small>masala</small></div>
    <div class="body"><div class="t">${esc(r.name)}</div><div class="d">${withCourse ? `<b>${esc(r.course_title)}</b>, ` : ''}${esc(r.group)}${r.percent != null ? ' — davomat ' + r.percent + '%' : ''}</div>
    <div class="chips" style="gap:4px;margin-top:4px">${tags.join('')}</div></div>${ic('chev', 'chev')}</a>`;
}
/* Dinamika: kichik grafik (sparkline) — oxirgi nuqta ajratib ko'rsatiladi */
function spark(points, cls) {
  const v = points.map(p => p.value), W = 120, H = 34, P = 3;
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), span = hi - lo || 1;
  const xy = v.map((y, i) => [P + i * (W - 2 * P) / (v.length - 1), H - P - (y - lo) * (H - 2 * P) / span]);
  const d = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join('');
  const [lx, ly] = xy[xy.length - 1];
  return `<svg class="spark ${cls}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${points.map(p => p.label + ': ' + p.value).join(', ')}">
    <path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="${lx}" cy="${ly}" r="3" fill="currentColor"/></svg>`;
}
function dynVal(it, v) {
  if (v == null) return '—';
  if (it.unit === '%') return `${num(v)}%`;
  if (it.unit === 'gpa') return gpaNum(v);
  if (it.unit === 'pairs') return pairs(v);
  if (it.unit === 'subjects') return v ? t('subjectsN', { n: v }) : t('no_debt');
  if (it.unit === 'so\'m' || it.unit === 'money') return v ? (v >= 1e6 ? `${(Math.floor(v / 1e5) / 10).toString().replace('.', S.lang === 'en' ? '.' : ',')} ${t('mln_unit')}` : money(v)) : t('no_debt');
  return `${v} ta`;
}
function dynDelta(it) {
  const d = it.delta;
  if (d == null) return { cls: 'flat', txt: t('dyn_first') };
  if (!d) return { cls: 'flat', txt: t('dyn_same') };
  const good = (d > 0) === (it.better === 'up');
  const mag = it.unit === '%' ? `${num(Math.abs(d))} p.p.` : it.unit === 'gpa' ? gpaNum(Math.abs(d)) : it.unit === 'pairs' ? pairs(Math.abs(d)) : it.unit === 'subjects' ? t('subjectsN', { n: Math.abs(d) }) : it.unit === 'money' || it.unit === 'so\'m' ? dynVal(it, Math.abs(d)) : dynVal(it, Math.abs(d));
  return { cls: good ? 'good' : 'bad', txt: `${d > 0 ? '▲' : '▼'} ${mag}` };
}
const semLabel = s => /^\d+$/.test(String(s)) ? t('semN', { n: s }) : String(s || '—');
/* dinamika qatori belgisi: ko'rsatkich turi bo'yicha */
function dynIc(it) {
  const money = it.unit === "so'm" || it.unit === 'money', tri = /trimestr/i.test(it.key || '') || /trimestr|триместр|trimester/i.test(it.title);
  const [i, c] = it.unit === '%' ? ['att', 'att'] : money ? (tri ? ['receipt', 'money2'] : ['dollar', 'money']) : it.unit === 'gpa' ? ['grade', 'gpa']
    : it.unit === 'subjects' ? ['bookx', 'acad'] : it.unit === 'pairs' ? ['calx', 'risk'] : ['trend', 'people'];
  return `<span class="t-ic c-${c}" aria-hidden="true">${ic(i)}</span>`;
}
function parentDyn(items) {
  // ota-ona bosh sahifasi: davomat, GPA, kontrakt qarzi — qiymat, o'zgarish va kichik grafik; bosilsa — batafsil
  return `<section class="section"><div class="section-head"><h2>${hi('trends')}${t('trends')}</h2><a href="#/trends">${t('more')}</a></div>
    ${items && items.length ? `<a class="card dyn" href="#/trends" style="display:block;color:inherit;text-decoration:none">${items.map(it => { const dl = dynDelta(it); return `<div class="dyn-row">${dynIc(it)}
      <div class="body"><div class="t">${esc(it.title)}</div><div class="d">${esc(it.caption)}</div></div>
      ${spark(it.points, dl.cls)}<div class="val"><b class="num">${esc(dynVal(it, it.value))}</b><span class="${dl.cls}">${esc(dl.txt)}</span></div></div>`; }).join('')}</a>`
      : `<div class="card muted small">${t('dyn_none')}</div>`}</section>`;
}
function dynCard(items) {
  if (!items || !items.length) return '';
  return `<section class="section"><div class="section-head"><h2>${hi('Dinamika')}Dinamika</h2></div><div class="card dyn">${items.map(it => { const dl = dynDelta(it); return `<div class="dyn-row">${dynIc(it)}
    <div class="body"><div class="t">${esc(it.title)}</div><div class="d">${esc(it.note || it.caption)}</div></div>
    ${spark(it.points, dl.cls)}<div class="val"><b class="num">${esc(dynVal(it, it.value))}</b><span class="${dl.cls}">${esc(dl.txt)}</span></div></div>`; }).join('')}</div></section>`;
}
async function viewStaff() {
  const title = S.me.staff && S.me.staff.title || 'Kurs koordinatori';
  const mine = (S.me.staff && S.me.staff.groups) || [];
  page({ title: 'Kurs holati', sub: title + (mine.length ? ' · ' + mine.join(', ') : ''), active: '#/staff', body: loading() });
  let d;
  try { d = await api('/api/staff/panel'); } catch (e) { return page({ title: 'Kurs holati', active: '#/staff', body: errorBox() }); }
  S.staffUnread = d.unread;
  const pctLinked = d.total ? Math.round(100 * d.linked / d.total) : 0;
  // har bir ko'rsatkich — o'z belgisi (ma'lumot turi rangida); summalar ixcham, to'liq summa — izohda
  const tile = (k, v, s, tone, href, icon, c) => `<a class="tile st-tile ${tone}" href="${href}"><span class="k"><span class="t-ic c-${c}" aria-hidden="true">${ic(icon)}</span>${k}</span><span class="v num">${v}</span><span class="s">${s}</span></a>`;
  const mshort = x => (x >= 1e6 ? `${(Math.round(x / 1e5) / 10).toString().replace('.', ',')}<small class="of"> mln so‘m</small>` : `${Math.round(x).toLocaleString('ru-RU')}<small class="of"> so‘m</small>`);
  const body = `${d.scope ? `<p class="small muted" style="margin:0 0 10px">${esc(d.scope)}</p>` : ''}${d.unread || d.link_requests ? `<div class="alert warn"><div class="bar"></div><div>${d.unread ? `<b>${d.unread} ta o‘qilmagan xabar</b> — <a href="#/staff/inbox">ochish</a><br>` : ''}${d.link_requests ? `<b>${d.link_requests} ta bog‘lash so‘rovi</b> — <a href="#/staff/requests">ko‘rib chiqish</a>` : ''}</div></div>` : ''}
    <div class="grid2" style="margin-top:12px">
      ${tile('Talabalar', d.total, `ota-onasi ulangan: ${pctLinked}%`, '', '#/staff/students', 'users', 'people')}
      ${tile('Davomat muammosi', d.att, 'chegaraga yetganlar', d.att ? 'bad' : 'ok', '#/staff/students?filter=att', 'calx', 'att')}
      ${tile('Akademik qarz', d.acad, 'qarzdorlar ro‘yxati bo‘yicha', d.acad ? 'bad' : 'ok', '#/staff/students?filter=acad', 'bookx', 'acad')}
      ${tile('3+ muammoli', d.multi, 'birinchi navbatda', d.multi ? 'bad' : 'ok', '#/staff/students?filter=prob', 'flame', 'risk')}
      ${tile('GPA past', d.gpa, `${limNum(d.gpa_min)} dan past — kursdan o‘tmaydi`, d.gpa ? 'bad' : 'ok', '#/staff/students?filter=gpa', 'grade', 'gpa')}
      ${tile('Kontrakt qarzi', mshort(d.kontrakt.sum), `${d.kontrakt.count} ta talaba`, d.kontrakt.count ? 'warn' : 'ok', '#/staff/students?filter=kontrakt', 'dollar', 'money')}
      ${tile('Trimestr qarzi', mshort(d.trimestr.sum), `${d.trimestr.count} ta talaba`, d.trimestr.count ? 'warn' : 'ok', '#/staff/students?filter=trimestr', 'receipt', 'money2')}
      ${tile('Xabarlar', d.unread, `bog‘lash so‘rovlari: ${d.link_requests}`, d.unread ? 'bad' : 'ok', '#/staff/inbox', 'chat', 'msg')}</div>
    ${dynCard(d.dynamics)}
    <section class="section"><div class="section-head"><h2>${hi('Muammoli talabalar')}Muammoli talabalar</h2><a href="#/staff/students?filter=prob">Barchasi</a></div>
      <div class="list">${d.top.length ? d.top.slice(0, 12).map(staffRow).join('') : empty('ok', 'Muammoli talaba yo‘q')}</div></section>
    <section class="section"><div class="list">
      <a class="row" href="#/staff/surveys"><div class="ic">${ic('poll')}</div><div class="body"><div class="t">So‘rovnomalar</div><div class="d">Ota-onalar fikri — tuzish va natijalar</div></div>${ic('chev', 'chev')}</a>
      <a class="row" href="#/staff/docs"><div class="ic bordo">${ic('file')}</div><div class="body"><div class="t">Rasmiy hujjat yuborish</div><div class="d">Buyruq yoki xat — har bir ota-onaga o‘z farzandining nusxasi</div></div>${ic('chev', 'chev')}</a>
      <a class="row" href="#/staff/requests"><div class="ic">${ic('users')}</div><div class="body"><div class="t">Bog‘lash so‘rovlari</div><div class="d">${d.link_requests ? d.link_requests + ' ta kutilmoqda' : 'Kutilayotgan so‘rov yo‘q'}</div></div>${d.link_requests ? `<span class="pill bordo">${d.link_requests}</span>` : ''}${ic('chev', 'chev')}</a>
    </div></section>
    <section class="section"><button class="card desk-card" type="button" data-act="desk"><span class="ic-badge">${ic('panel')}</span>
      <div style="flex:1;text-align:left"><b style="display:block">Kompyuter versiyasi</b><span class="muted small">Talabalar jadvali, xabarlar, e’lon va hisobotlar — kompyuter brauzerida</span></div>${ic('chev')}</button></section>
    ${d.updated ? `<p class="muted small" style="text-align:center;margin-top:18px">Yangilangan: ${when(d.updated)}</p>` : ''}${logoutBlock()}`;
  page({ title: 'Kurs holati', sub: title + (mine.length ? ' · ' + mine.join(', ') : ''), active: '#/staff', body });
}
async function viewStaffStudents(params) {
  const flt = params.get('filter') || '', q = params.get('q') || '';
  const all = S.me.role === 'super' && params.get('all') === '1';
  const qs = k => `#/staff/students?${new URLSearchParams(Object.assign({}, all ? { all: '1' } : {}, k ? { filter: k } : {}))}`;
  const filters = [['', 'Hammasi'], ['prob', 'Muammoli'], ['att', 'Davomat'], ['acad', 'Akademik'], ['gpa', 'GPA past'], ['kontrakt', 'Kontrakt'], ['trimestr', 'Trimestr']];
  const scope = S.me.role === 'super' ? `<div class="seg" style="margin-bottom:12px"><button data-act="scope" data-all="0" aria-pressed="${!all}">Joriy kurs</button><button data-act="scope" data-all="1" aria-pressed="${all}">Barcha kurslar</button></div>` : '';
  const head = scope + `<form data-act="search" style="display:flex;gap:8px">${all ? '<input type="hidden" name="all" value="1">' : ''}<input class="input" name="q" value="${esc(q)}" placeholder="Familiya, ism yoki HEMIS ID" aria-label="Qidirish"><button class="btn" aria-label="Qidirish">${ic('search')}</button></form>
    <div class="chips" style="margin:12px 0">${filters.map(([k, l]) => `<a class="chip" href="${qs(k)}" aria-pressed="${k === flt}">${l}</a>`).join('')}</div>`;
  page({ title: 'Talabalar', active: '#/staff/students', body: head + loading() });
  let d;
  try {
    if (all) {
      const r = await api('/api/super/students');
      const qq = q.toLowerCase();
      let items = r.items.filter(x => !qq || x.name.toLowerCase().includes(qq) || String(x.hemis_id || '').toLowerCase() === qq);
      if (flt === 'prob') items = items.filter(x => x.problems).sort((a, b) => b.problems - a.problems);
      else if (flt) items = items.filter(x => x.flags[flt]);
      d = { items: items.slice(0, 300), total: items.length };
    } else {
      d = await api(`/api/staff/students?filter=${flt}&q=${encodeURIComponent(q)}`);
    }
  } catch (e) { return page({ title: 'Talabalar', active: '#/staff/students', body: head + errorBox() }); }
  page({ title: 'Talabalar', sub: `${d.total} ta${all ? ', barcha kurslar' : ''}`, active: '#/staff/students', body: head + `<div class="list">${d.items.length ? d.items.map(r => staffRow(r, all)).join('') : empty('search', 'Hech kim topilmadi')}</div>` });
}
async function viewStaffStudent(sid) {
  page({ title: 'Talaba', active: '#/staff/students', body: loading() });
  let o;
  try { o = await api(`/api/staff/student/${sid}`); } catch (e) { return page({ title: 'Talaba', active: '#/staff/students', body: errorBox() }); }
  const c = o.child, a = o.attendance;
  const body = idCard(c) + verdict(o) + `<div class="grid2" style="margin-top:14px">
      <div class="tile"><span class="k">Davomat</span><span class="v num">${a && a.percent != null ? a.percent + '%' : '—'}</span><span class="s">${a ? `sababsiz<br><b class="nowrap">${pairs(a.counted_hours)}</b>` : ''}</span></div>
      <div class="tile"><span class="k">GPA</span><span class="v num">${o.gpa != null ? gpaNum(o.gpa) : '—'}<small class="of"> / 5</small></span><span class="s">${o.gpa_low ? `<b>${limNum(o.gpa_min)} dan past — kursdan kursga o‘tmaydi</b><br>` : ''}akademik qarz: ${o.academic.count ? o.academic.count + ' ta fan' : 'mavjud emas'}</span></div>
      ${payTile('kontrakt', o.pays.kontrakt)}${payTile('trimestr', o.pays.trimestr)}</div>
    ${o.academic.count ? `<section class="section"><div class="section-head"><h2>${hi('Akademik qarzdorlik')}Akademik qarzdorlik</h2><span class="muted small">${o.academic.count} ta fan</span></div>
      <div class="list">${o.academic.debts.map(debtRow).join('')}</div></section>` : ''}
    <section class="section"><div class="section-head"><h2>${hi('Ota-onalar')}Ota-onalar</h2></div><div class="list">${o.parents.length ? o.parents.map(p =>
      `<div class="row" style="cursor:default"><div class="ic">${ic('users')}</div><div class="body"><div class="t">${esc(p.tg_name || '')}</div><div class="d">${esc(fmtPhone(p.phone))} — ${p.lang.toUpperCase()}${p.active ? '' : ' — nofaol'}</div></div>
      <a class="icon-btn" style="color:var(--accent)" href="tel:+${esc(p.phone)}" aria-label="Qo‘ng‘iroq">${ic('phone')}</a>
      <a class="icon-btn" style="color:var(--accent)" href="#/staff/chat/${encodeURIComponent(c.course)}/${c.id}/${p.tg_id}" aria-label="Yozish">${ic('chat')}</a></div>`).join('') : empty('users', 'Ota-ona hali ulanmagan')}</div></section>`;
  page({ title: 'Talaba', sub: c.group, active: '#/staff/students', body });
}
async function viewStaffInbox() {
  page({ title: 'Xabarlar', active: '#/staff/inbox', body: loading() });
  let d;
  try { d = await api('/api/staff/inbox'); } catch (e) { return page({ title: 'Xabarlar', active: '#/staff/inbox', body: errorBox() }); }
  S.staffUnread = d.items.reduce((s, x) => s + x.unread, 0);
  const course = S.me.staff && S.me.staff.course || '_';
  page({ title: 'Xabarlar', active: '#/staff/inbox', body: `<div class="list">${d.items.length ? d.items.map(x =>
    `<a class="row" href="#/staff/chat/${encodeURIComponent(course)}/${x.sid}/${x.pid}"><div class="ic ${x.unread ? 'bordo' : ''}">${ic('chat')}</div>
      <div class="body"><div class="t">${esc(x.student)} <span class="muted small">${esc(x.group || '')}</span></div><div class="d">${esc(x.parent)}: ${esc((x.last || '').slice(0, 80))}</div></div>
      <div class="end">${x.unread ? `<span class="pill bordo">${x.unread}</span>` : `<span class="small muted">${when(x.at)}</span>`}</div></a>`).join('')
    : empty('chat', 'Xabarlar yo‘q', 'Ota-onalar yozganda shu yerda ko‘rinadi.')}</div>` });
}
async function viewStaffChat(sid, pid, first = true) {
  if (first) page({ title: 'Suhbat', active: '#/staff/inbox', body: loading(), noNav: true });
  let d;
  try { d = await api(`/api/staff/thread/${sid}/${pid}`); } catch (e) { return page({ title: 'Suhbat', body: errorBox(), noNav: true }); }
  let lastDay = '';
  const msgs = d.messages.map(m => {
    const day = new Date(m.at).toDateString(), sep = day !== lastDay ? `<div class="daysep">${dateLabel(m.at)}</div>` : '';
    lastDay = day;
    return sep + `<div class="bubble ${m.sender === 'staff' ? 'me' : 'them'}">${m.sender === 'parent' ? `<div class="who">${esc(d.parent)}</div>` : ''}${esc(m.text)}<time>${new Date(m.at).toTimeString().slice(0, 5)}</time></div>`;
  }).join('');
  const langHint = { ru: 'Ota-ona tili: rus — javobni rus tilida yozing', en: 'Ota-ona tili: ingliz — javobni ingliz tilida yozing' }[d.lang] || '';
  page({ title: d.student, sub: d.group, noNav: true, body: `<div class="chat-head"><div class="av">${esc((d.parent || '?').charAt(0))}</div>
      <div style="flex:1"><b>${esc(d.parent)}</b><div class="small muted">${esc(fmtPhone(d.phone))}${langHint ? ' — ' + langHint : ''}</div></div>
      ${d.phone ? `<a class="icon-btn" style="background:var(--tint-navy);color:var(--accent)" href="tel:+${esc(d.phone)}" aria-label="Qo‘ng‘iroq">${ic('phone')}</a>` : ''}</div>
    <div class="msgs">${msgs || empty('chat', 'Xabar yo‘q')}</div>
    <form class="composer" data-act="reply" data-sid="${sid}" data-pid="${pid}"><textarea class="input" name="text" rows="1" placeholder="Javob yozing…" aria-label="Javob"></textarea>
      <button class="send" type="submit" aria-label="Yuborish">${ic('send')}</button></form>` });
  window.scrollTo(0, document.body.scrollHeight);
}
function staffCourseTitle() {  // kurs koordinatori / super-admin hozir qaysi kurs bilan ishlayapti
  const st = S.me.staff || {};
  const c = (st.courses || []).find(x => x.key === (S.staffCourse || st.course));
  return (c && c.title) || st.title || 'Kurs';
}
/* Tasdiqlash oynasi: Telegram'ning o'zi — faqat qo'llab-quvvatlansa (versiya 6.2+, matn 256 belgigacha, boshqa oyna
   ochiq emas); aks holda yoki xato bo'lsa — brauzerning oynasi. Oyna hech qachon amalni (e'lon, hujjat) to'sib qo'ymasin. */
function confirmSafe(msg) {
  const tgOk = tg && typeof tg.showConfirm === 'function' && String(msg).length <= 256
    && (typeof tg.isVersionAtLeast !== 'function' || tg.isVersionAtLeast('6.2'));
  if (tgOk) {
    try {
      return new Promise((res, rej) => { try { tg.showConfirm(msg, ok => res(!!ok)); } catch (e) { rej(e); } })
        .catch(() => window.confirm(msg));
    } catch (_) { /* pastga */ }
  }
  return Promise.resolve(window.confirm(msg));
}
function confirmAsync(msg) { return confirmSafe(msg); }
/* ================================================================ kurs koordinatori: so'rovnomalar (telefonda) */
async function viewStaffSurveys() {
  page({ title: 'So‘rovnomalar', active: '', body: loading() });
  let d;
  try { d = await api('/api/staff/surveys'); } catch (e) { return page({ title: 'So‘rovnomalar', active: '', body: errorBox() }); }
  page({ title: 'So‘rovnomalar', active: '', body: `<h2 class="screen-title">So‘rovnomalar</h2>
    <a class="btn block" href="#/staff/surveys/new" style="margin-bottom:12px">${ic('poll')} Yangi so‘rovnoma</a>
    <div class="list">${d.items.length ? d.items.map(x => `<a class="row" href="#/staff/surveys/${x.id}"><div class="ic ${x.open ? '' : 'muted'}">${ic('poll')}</div>
      <div class="body"><div class="t">${esc(x.title)}</div><div class="d">${x.answered} / ${x.eligible} javob · ${x.open ? 'ochiq' : 'yopilgan'}${x.groups.length ? ' · ' + esc(x.groups.join(', ')) : ''}</div></div>${ic('chev', 'chev')}</a>`).join('')
      : empty('poll', 'Hali so‘rovnoma yo‘q')}</div>` });
}
async function viewStaffSurvey(id) {
  page({ title: 'So‘rovnoma', active: '', body: loading() });
  let d;
  try { d = await api(`/api/staff/surveys/${id}`); } catch (e) { return page({ title: 'So‘rovnoma', active: '', body: errorBox() }); }
  const pct = d.eligible ? Math.round(100 * d.answered / d.eligible) : 0;
  page({ title: 'So‘rovnoma', sub: `${d.answered} / ${d.eligible} javob`, active: '', body: `<h2 class="screen-title">${esc(d.title)}</h2>
    <div class="card"><div class="kv"><span>Javob berganlar</span><b class="num">${d.answered} / ${d.eligible} (${pct}%)</b></div><div class="progress"><i style="width:${pct}%"></i></div>
      <div class="kv" style="margin-top:8px"><span>Holat</span><b>${d.open ? 'ochiq' : 'yopilgan'}${d.anonymous ? ', anonim' : ''}</b></div></div>
    ${d.questions.map((q, i) => `<section class="section"><div class="section-head"><h2 style="font-size:16px">${i + 1}. ${esc(q.text)}</h2></div><div class="card">
      ${q.options ? (() => { const tot = q.options.reduce((a, o) => a + o.count, 0) || 1; return q.options.map(o => `<div class="kv"><span>${esc(o.label)}</span><b class="num">${o.count} · ${Math.round(100 * o.count / tot)}%</b></div><div class="progress" style="margin-bottom:8px"><i style="width:${Math.round(100 * o.count / tot)}%"></i></div>`).join('') + (q.average != null ? `<p class="small muted">O‘rtacha: <b>${num(q.average)}</b> / 5</p>` : ''); })()
        : q.texts.length ? q.texts.map(x => `<p style="margin:0 0 8px;white-space:pre-line">${esc(x.text)}${x.student ? `<br><span class="muted small">${esc(x.student)}, ${esc(x.group || '')}</span>` : ''}</p>`).join('') : '<p class="muted small">Hali javob yo‘q</p>'}</div></section>`).join('')}
    ${d.open ? `<button class="btn ghost block" data-act="st-sv-close" data-id="${d.id}" style="margin-top:14px">So‘rovnomani yopish</button>` : ''}` });
}
function viewStaffSurveyNew() {
  const kinds = [['single', 'Bitta javob'], ['multi', 'Bir nechta javob'], ['scale', 'Baho 1–5'], ['text', 'Erkin javob']];
  const qBlock = i => `<fieldset class="card q" data-i="${i}"><div class="q-t"><b>${i + 1}-savol</b></div>
    <select class="input" name="kind" style="margin-bottom:8px">${kinds.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select>
    <input class="input" name="text" placeholder="Savol matni" maxlength="500" style="margin-bottom:8px">
    <textarea class="input" name="options" rows="3" placeholder="Javob variantlari — har biri yangi qatorda (bitta / bir nechta javob uchun)"></textarea></fieldset>`;
  page({ title: 'Yangi so‘rovnoma', active: '', body: `<form id="stSurvey">
    <label class="field" style="margin-top:0"><span>Sarlavha</span><input class="input" name="title" required minlength="3" maxlength="200"></label>
    <label class="field"><span>Izoh (ixtiyoriy)</span><textarea class="input" name="description" rows="2" maxlength="2000"></textarea></label>
    <div id="stQs">${qBlock(0)}</div>
    <button class="btn ghost block" type="button" data-act="st-sv-addq">+ Savol qo‘shish</button>
    <label class="field"><span>Guruhlar (ixtiyoriy, vergul bilan; bo‘sh — ${(S.me.staff && S.me.staff.groups || []).length ? 'barcha guruhlaringiz' : 'butun kurs'})</span><input class="input" name="groups" placeholder="XM-21, XM-22"></label>
    <label class="field"><span>Yopilish sanasi (ixtiyoriy)</span><input class="input" type="date" name="closes_at"></label>
    <label class="row" style="margin-top:8px;cursor:pointer"><span class="switch"><input type="checkbox" name="anonymous"><i></i></span><div class="body"><div class="t">Anonim</div><div class="d">Natijada ismlar ko‘rinmaydi</div></div></label>
    <button class="btn block" style="margin-top:14px">${ic('send')} E’lon qilish</button></form>` });
  S.stQ = 1;
  document.querySelector('[data-act="st-sv-addq"]').onclick = () => { document.getElementById('stQs').insertAdjacentHTML('beforeend', qBlock(S.stQ++)); };
}
document.addEventListener('submit', async e => {
  if (e.target.id !== 'stSurvey') return;
  e.preventDefault(); e.stopImmediatePropagation();
  const f = e.target, fd = new FormData(f);
  const questions = [...f.querySelectorAll('fieldset.q')].map(fs => ({ kind: fs.querySelector('[name=kind]').value, text: fs.querySelector('[name=text]').value.trim(),
    options: fs.querySelector('[name=options]').value.split('\n').map(x => x.trim()).filter(Boolean), required: true })).filter(q => q.text);
  if (!questions.length) return toast('Kamida bitta savol yozing');
  const bad = questions.findIndex(q => (q.kind === 'single' || q.kind === 'multi') && q.options.length < 2);
  if (bad >= 0) return toast(`${bad + 1}-savolga kamida ikkita variant yozing`);
  if (!await confirmAsync('So‘rovnoma e’lon qilinadi va ota-onalarga yuboriladi. Davom etasizmi?')) return;
  const btn = f.querySelector('button:not([type=button])'); btn.disabled = true;
  try {
    const r = await api('/api/staff/surveys', { json: { title: fd.get('title'), description: fd.get('description'), questions,
      groups: String(fd.get('groups') || '').split(',').map(x => x.trim()).filter(Boolean), closes_at: fd.get('closes_at') || null, anonymous: !!fd.get('anonymous') } });
    toast(`E’lon qilindi: ${r.sent} / ${r.recipients}`); location.hash = `#/staff/surveys/${r.id}`;
  } catch (err) { toast('E’lon qilinmadi: ' + ((err.data && err.data.error) || '')); btn.disabled = false; }
}, true);
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="st-sv-close"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (!await confirmAsync('So‘rovnomani yopasizmi? Ota-onalar endi javob bera olmaydi.')) return;
  try { await api(`/api/staff/surveys/${b.dataset.id}/close`, { method: 'POST' }); route(); } catch (err) { toast(t('error')); }
}, true);
function viewStaffAnnounce() {
  page({ title: 'E’lon yuborish', active: '#/staff/announce', body: `<form class="card" data-act="announce">
    <label class="field" style="margin-top:0"><span>E’lon matni</span><textarea class="input" name="text" rows="7" required placeholder="Ota-onalar yig‘ilishi shanba kuni soat 10:00 da.&#10;---ru&#10;Родительское собрание в субботу в 10:00."></textarea></label>
    <p class="small muted">Rus va ingliz tilidagi ota-onalar uchun alohida qatordan <b>---ru</b> va <b>---en</b> yozib, tarjimani qo‘shing — har bir ota-ona o‘z tilidagi qismni oladi.</p>
    <label class="field"><span>Guruhlar (ixtiyoriy, vergul bilan; bo‘sh — ${(S.me.staff && S.me.staff.groups || []).length ? 'barcha guruhlaringiz: ' + esc(S.me.staff.groups.join(', ')) : 'butun kurs'})</span><input class="input" name="groups" placeholder="3-1a-24, 3-2a-24"></label>
    ${S.me.role === 'super' ? `<label class="row" style="margin-top:12px;cursor:pointer"><span class="switch"><input type="checkbox" name="all"><i></i></span>
      <div class="body"><div class="t">Barcha kurslarga yuborish</div><div class="d">Universitet miqyosidagi e’lon — har bir ota-onaga bir marta</div></div></label>` : ''}
    <p class="small muted" style="margin-top:12px">Kurs: <b>${esc(staffCourseTitle())}</b></p>
    <button class="btn block" style="margin-top:12px">${ic('send')}E’lonni yuborish</button></form><div id="result"></div>` });
}
function viewStaffFiles() {
  const kinds = [['auto', 'Turini bot aniqlasin'], ['students', 'Talabalar'], ['attendance', 'Davomat'], ['schedule', 'Dars jadvali'], ['grades', 'Baholar'],
    ['enroll', 'Tanlov/2-til: kim o‘qiydi'], ['elsched', 'Tanlov/2-til: jadval'], ['debts', 'Kontrakt qarzdorligi'], ['debts_t', 'Trimestr qarzdorligi'], ['acad_debts', 'Akademik qarzdorlar (HEMIS)'], ['phones', 'Talaba telefonlari'], ['translations', 'Tarjimalar']];
  page({ title: 'Fayllar', active: '#/staff/files', body: `<a class="card desk-card" href="#/staff/docs" style="margin-bottom:16px"><span class="ic-badge">${ic('file')}</span>
      <div style="flex:1;text-align:left"><b style="display:block">Rasmiy hujjat yuborish (PDF)</b><span class="muted small">Buyruq, ogohlantirish, hayfsan — ota-onalarga</span></div>${ic('chev')}</a>
    <h2 class="screen-title">Ma’lumot yuklash</h2>
    <form class="card" data-act="import"><label class="drop"><input type="file" name="file" accept=".xlsx,.xlsm" multiple>
      <span class="drop-ic">${ic('upload')}</span><span class="drop-t" id="fname">Excel faylni tanlang</span>
      <span class="drop-s">.xlsx · bir nechta faylni birga tanlash mumkin</span></label>
      <label class="field"><span>Fayl turi</span><select class="input" name="kind">${kinds.map(([k, l]) => `<option value="${k}">${l}</option>`).join('')}</select></label>
      <label class="row" style="padding:12px 0 0;min-height:0"><div class="body">Ota-onalarga xabar yubormaslik (jim)</div><span class="switch"><input type="checkbox" name="silent"><i></i></span></label>
      <button class="btn block" style="margin-top:16px">${ic('upload')}Yuklash</button></form><div id="result"></div>
    <section class="section"><div class="section-head"><h2>${hi('Hisobot')}Hisobot</h2></div><div class="card"><p class="muted small" style="margin-top:0">Hisobot Telegram chatingizga fayl bo‘lib keladi.</p>
      <div class="grid2"><button class="btn ghost" data-act="export" data-fmt="x">Excel</button><button class="btn ghost" data-act="export" data-fmt="p">PDF</button></div></div></section>
    <section class="section"><div class="section-head"><h2>${hi('Yuklangan fayllar')}Yuklangan fayllar</h2></div><div class="list" id="imports">${loading()}</div></section>` });
  loadImportsApp();
}
async function loadImportsApp() {
  const box = document.getElementById('imports'); if (!box) return;
  let d; try { d = await api('/api/staff/imports'); } catch (e) { box.innerHTML = errorBox(); return; }
  box.innerHTML = d.items.length ? d.items.slice(0, 30).map(x => `<div class="row" style="cursor:default"><div class="ic">${ic('upload')}</div>
    <div class="body"><div class="t">${esc(x.file_name || '—')}</div><div class="d">${esc(x.kind_title)}${x.deletable ? ` · ${x.rows} ta ${x.kind === 'students' ? 'talaba' : 'yozuv'}` : ''} · ${when(x.at)}${x.parents ? ` · ${x.parents} ota-onaga xabar` : ''}</div></div>
    ${x.deletable ? `<button class="icon-btn" style="color:var(--bordo-fg)" data-act="imp-del" data-id="${x.id}" data-name="${esc(x.file_name || '')}" data-kind="${esc(x.kind)}" data-rows="${x.rows}" data-linked="${x.linked_parents || 0}" aria-label="O‘chirish">${ic('x')}</button>` : ''}</div>`).join('')
    : empty('upload', 'Hali fayl yuklanmagan');
}
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-act="imp-del"]');
  if (!b) return;
  e.preventDefault(); e.stopImmediatePropagation();
  const q = b.dataset.kind === 'students'
    ? (Number(b.dataset.rows) ? `«${b.dataset.name}» — talabalar ro‘yxati. Shu fayl orqali kelgan ${b.dataset.rows} ta talaba va ularning barcha ma’lumotlari (davomat, baholar, to‘lovlar, yozishmalar) o‘chadi; ${b.dataset.linked} ta ota-ona ulardan uziladi. Keyingi fayllarda qayta kelgan talabalar qoladi. O‘chirilsinmi?`
      : `«${b.dataset.name}» dagi talabalar keyingi fayllarda qayta kelgan — o‘chiriladigan talaba yo‘q. Fayl ro‘yxatdan olib tashlansinmi?`)
    : `«${b.dataset.name}» tizimdan o‘chirilsinmi? Shu fayldan kelgan ma’lumotlar, ota-onalarga ketgan bildirishnoma va xabarlar ham o‘chadi.`;
  if (!await confirmAsync(q)) return;
  b.disabled = true;
  try { const r = await api(`/api/staff/imports/${b.dataset.id}`, { method: 'DELETE' }); toast(`O‘chirildi: ${r.students ? r.students + ' ta talaba, ' : ''}${r.rows} ta yozuv`); loadImportsApp(); }
  catch (err) { toast(err.status === 403 ? 'Faqat o‘zingiz yuklagan faylni o‘chira olasiz' : t('error')); b.disabled = false; }
}, true);
async function viewSuperCourses() {
  page({ title: 'Kurslar', active: '#/staff', body: loading() });
  const d = await api('/api/super/courses');
  page({ title: 'Kurslar', active: '#/staff', body: `<div class="list">${d.courses.map(c => `<button class="row" data-act="pickCourse" data-key="${esc(c.key)}"><div class="ic">${ic('grade')}</div>
    <div class="body"><div class="t">${esc(c.title)}</div><div class="d">talabalar: ${c.students} — ota-onalar: ${c.parents}</div></div>${ic('chev', 'chev')}</button>`).join('')}</div>` });
}

/* ================================================================ marshrutlash */
function pickChild(key) {
  const kids = S.me.children;
  S.child = kids.find(k => `${k.course}/${k.id}` === key) || S.child || kids[0];
  localStorage.setItem('child', `${S.child.course}/${S.child.id}`);
}

/* ================================================================ sahifa ramkasini yangilash (nishonlar, mavzu) */
function updateChrome() {
  const c = S.chrome; if (!c || !S.me) return;
  if (deskMode()) {
    const side = document.querySelector('.dk-side'); if (side) side.outerHTML = deskSide();
    const head = document.querySelector('.dk-head'); if (head) head.outerHTML = deskHead(c.title, c.sub, c.noNav);
    return;
  }
  const h = document.querySelector('header.topbar'); if (h) h.outerHTML = topbar(c.title, c.sub);
  const n = document.querySelector('nav.nav'); if (n && !c.noNav) n.outerHTML = nav(c.active);
}

/* ================================================================ real vaqt: bildirishnoma kelishi bilan */
const LIVE = { ctrl: null, retry: 2000 };
async function connectLive() {
  if (LIVE.ctrl || !S.me || S.me.role === 'blocked') return;
  const ctrl = new AbortController(); LIVE.ctrl = ctrl;
  try {
    const headers = { 'X-Telegram-Init-Data': (tg && tg.initData) || '' };
    if (DEV) headers['X-Dev-User'] = '1';
    if (!tg && store.get('appToken')) headers.Authorization = 'Bearer ' + store.get('appToken');
    const r = await fetch('/api/events', { headers, signal: ctrl.signal, cache: 'no-store' });
    if (!r.ok || !r.body) throw new Error('http ' + r.status);
    LIVE.retry = 2000;
    const reader = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) { liveChunk(buf.slice(0, i)); buf = buf.slice(i + 2); }
    }
  } catch (e) { if (ctrl.signal.aborted) return; }
  LIVE.ctrl = null;
  if (!document.hidden) setTimeout(connectLive, LIVE.retry);
  LIVE.retry = Math.min(LIVE.retry * 2, 30000);
}
function liveChunk(chunk) {
  let type = 'message', data = '';
  for (const l of chunk.split('\n')) { if (l.startsWith('event:')) type = l.slice(6).trim(); else if (l.startsWith('data:')) data += l.slice(5).trim(); }
  if (type === 'hello' || !data) return;
  try { onLive(JSON.parse(data)); } catch (_) { /* */ }
}
function onLive(ev) {
  LIVE.last = Date.now();
  if (ev.type === 'refresh') { if (S.me.role === 'parent') { S.me.unread = S.me.unread || {}; api('/api/pulse').then(p => { S.me.unread.notifications = p.notifications; route(); }).catch(() => route()); } return; }  // fayl o'chirildi
  const staff = S.me.role === 'staff' || S.me.role === 'super';
  if (ev.type === 'link') { haptic('success'); boot(true); return; }
  if (ev.type === 'link_progress') { haptic('success'); if (S.me.role === 'pending') viewPending(); return; }  // farzand tasdiqladi  // so'rov tasdiqlandi — farzand sahifasi
  S.me.unread = S.me.unread || {};
  if (!staff && (ev.type === 'notification' || ev.type === 'news')) S.me.unread.notifications = (S.me.unread.notifications || 0) + 1;
  if (!staff && ev.type === 'message') S.me.unread.messages = (S.me.unread.messages || 0) + 1;
  if (staff && ev.type === 'message') S.staffUnread = (S.staffUnread || 0) + 1;
  haptic('light');
  const h = location.hash || '#/';
  const here = (!staff && ev.type === 'message' && h.startsWith('#/chat')) || (!staff && h.startsWith('#/notifications'))
    || (staff && ev.type === 'message' && (h.startsWith('#/staff/inbox') || h.startsWith('#/staff/chat')))
    || (staff && ev.type === 'request' && h.startsWith('#/staff/requests'));
  if (here) { route(); return; }
  const top = (h.split('?')[0]);
  if (!staff && ['#/', '#', '#/surveys', '#/regulations'].includes(top)) route(); else updateChrome();  // yangilashsiz
  banner(ev);
}
function banner(ev) {
  document.querySelectorAll('.live-banner').forEach(x => x.remove());
  const icon = { att: 'att', grade: 'grade', acad: 'grade', pay: 'wallet', doc: 'file', news: 'mega', digest: 'cal', link: 'users', survey: 'poll', reg: 'book' }[ev.kind] || (ev.type === 'message' ? 'chat' : ev.type === 'request' ? 'users' : 'bell');
  const el = document.createElement('a');
  el.className = 'live-banner'; el.href = '#' + (ev.route || '/notifications');
  el.innerHTML = `<span class="ic-badge">${ic(icon)}</span><span class="lb-t">${esc(String(ev.text || '').replace(/<[^>]+>/g, '').slice(0, 160))}</span><b>${t('open')}</b>`;
  el.addEventListener('click', () => el.remove());
  document.body.append(el);
  requestAnimationFrame(() => el.classList.add('on'));
  setTimeout(() => { el.classList.remove('on'); setTimeout(() => el.remove(), 350); }, 7000);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && S.me && !LIVE.ctrl) connectLive(); });

/* ================================================================ so'rovnomalar va ichki nizomlar (ota-ona) */
function surveyCta(x) {
  return `<a class="survey-cta" href="#/survey/${encodeURIComponent(x.course)}/${x.id}"><span class="ic-badge">${ic('poll')}</span>
    <div class="body"><small>${t('waiting_you')}</small><b>${esc(x.title)}</b><span class="muted small">${t('q_n', { n: x.questions })}${x.closes_at ? ' · ' + t('closes', { d: dateLabel(x.closes_at) }) : ''}</span></div>
    <span class="go">${t('answer_now')}</span></a>`;
}
function quickLinks(pending) {
  return `<div class="quick"><a href="#/surveys">${ic('poll')}<span>${t('surveys')}</span>${pending ? `<span class="dot">${pending}</span>` : ''}</a>
    <a href="#/regulations">${ic('book')}<span>${t('regs')}</span></a></div>`;
}
async function viewSurveys() {
  page({ title: t('surveys'), active: '', body: loading() });
  let d;
  try { d = await api('/api/surveys'); } catch (e) { return page({ title: t('surveys'), active: '', body: errorBox() }); }
  const row = x => `<a class="row" href="#/survey/${encodeURIComponent(x.course)}/${x.id}"><div class="ic ${x.answered ? '' : 'bordo'}">${ic(x.answered ? 'ok' : 'poll')}</div>
    <div class="body"><div class="t">${esc(x.title)}</div><div class="d">${x.answered ? t('answered') : t('q_n', { n: x.questions })}${!x.open ? ' · ' + t('survey_closed') : x.closes_at ? ' · ' + t('closes', { d: dateLabel(x.closes_at) }) : ''}</div></div>${ic('chev', 'chev')}</a>`;
  page({ title: t('surveys'), active: '', body: `<h2 class="screen-title">${t('surveys')}</h2>
    ${d.pending.length ? d.pending.map(surveyCta).join('') : ''}
    ${d.done.length ? `<section class="section"><div class="section-head"><h2>${hi('answered')}${t('answered')}</h2></div><div class="list">${d.done.map(row).join('')}</div></section>` : ''}
    ${!d.pending.length && !d.done.length ? `<div class="list">${empty('poll', t('no_surveys'))}</div>` : ''}` });
}
async function viewSurvey(course, sid) {
  page({ title: t('survey'), active: '', body: loading() });
  let d;
  try { d = await api(`/api/surveys/${encodeURIComponent(decodeURIComponent(course))}/${sid}`); } catch (e) { return page({ title: t('survey'), active: '', body: errorBox() }); }
  const dis = d.open ? '' : 'disabled';
  const q = (x, i) => {
    const head = `<div class="q-t"><b>${i + 1}.</b> ${esc(x.text)}${x.required ? ' <span class="req">*</span>' : ''}${x.kind === 'multi' ? `<small class="muted"> — ${t('choose_many')}</small>` : ''}</div>`;
    let inp;
    if (x.kind === 'single' || x.kind === 'multi') {
      const ty = x.kind === 'single' ? 'radio' : 'checkbox', cur = [].concat(x.answer || []);
      inp = `<div class="opts">${x.options.map(o => `<label class="opt"><input type="${ty}" name="q${x.id}" value="${esc(o)}" ${cur.includes(o) ? 'checked' : ''} ${dis}><span>${esc(o)}</span></label>`).join('')}</div>`;
    } else if (x.kind === 'scale') {
      inp = `<div class="scale">${[1, 2, 3, 4, 5].map(n => `<label><input type="radio" name="q${x.id}" value="${n}" ${String(x.answer) === String(n) ? 'checked' : ''} ${dis}><span>${n}</span></label>`).join('')}</div>
        <div class="scale-ends muted small"><span>1 — ${t('scale_lo')}</span><span>5 — ${t('scale_hi')}</span></div>`;
    } else {
      inp = `<textarea class="input" name="q${x.id}" rows="3" maxlength="2000" placeholder="${t('your_answer')}" ${dis}>${esc(x.answer || '')}</textarea>`;
    }
    return `<fieldset class="card q" data-q="${x.id}" data-kind="${x.kind}" data-req="${x.required ? 1 : 0}">${head}${inp}</fieldset>`;
  };
  page({ title: t('survey'), active: '', body: `<h2 class="screen-title">${esc(d.title)}</h2>
    ${d.description ? `<p class="muted" style="margin:-4px 2px 12px;white-space:pre-line">${esc(d.description)}</p>` : ''}
    ${d.anonymous ? `<p class="small muted" style="margin:-4px 2px 12px">🔒 ${t('anon')}</p>` : ''}
    ${d.answered ? `<div class="verdict ok" style="margin-bottom:12px">${ic('ok')}<div><b>${t('survey_thanks')}</b>${d.open ? `<p>${t('edit_answer')} ↓</p>` : ''}</div></div>` : ''}
    ${!d.open ? `<div class="verdict warn" style="margin-bottom:12px">${ic('alert')}<div><b>${t('survey_closed')}</b></div></div>` : ''}
    <form id="surveyForm" data-course="${esc(d.course)}" data-sid="${d.id}">${d.questions.map(q).join('')}
      ${d.open ? `<button class="btn block" type="submit" style="margin-top:14px">${ic('send')} ${d.answered ? t('edit_answer') : t('submit_survey')}</button>` : ''}</form>` });
}
document.addEventListener('submit', async e => {
  const f = e.target;
  if (f.id !== 'surveyForm') return;
  e.preventDefault(); e.stopImmediatePropagation();
  const answers = {}, missing = [];
  f.querySelectorAll('fieldset.q').forEach(fs => {
    const id = fs.dataset.q, kind = fs.dataset.kind;
    let v;
    if (kind === 'multi') v = [...fs.querySelectorAll('input:checked')].map(x => x.value);
    else if (kind === 'text') v = fs.querySelector('textarea').value.trim();
    else v = (fs.querySelector('input:checked') || {}).value;
    const emptyV = v == null || v === '' || (Array.isArray(v) && !v.length);
    fs.classList.toggle('missing', emptyV && fs.dataset.req === '1');
    if (emptyV) { if (fs.dataset.req === '1') missing.push(fs); } else answers[id] = v;
  });
  if (missing.length) { toast(t('required_q')); missing[0].scrollIntoView({ behavior: 'smooth', block: 'center' }); haptic('rigid'); return; }
  const btn = f.querySelector('button[type="submit"]'); if (btn) btn.disabled = true;
  try {
    await api(`/api/surveys/${encodeURIComponent(f.dataset.course)}/${f.dataset.sid}`, { json: { answers } });
    haptic('success'); toast(t('survey_thanks'));
    S.pendingSurveys = Math.max(0, (S.pendingSurveys || 1) - 1);
    location.hash = '#/surveys';
  } catch (err) { toast(err.data && err.data.error === 'closed' ? t('survey_closed') : t('error')); if (btn) btn.disabled = false; }
}, true);

async function viewRegulations() {
  page({ title: t('regs'), active: '', body: loading() });
  let d;
  try { d = await api('/api/regulations'); } catch (e) { return page({ title: t('regs'), active: '', body: errorBox() }); }
  page({ title: t('regs'), active: '', body: `<h2 class="screen-title">${t('regs')}</h2><p class="muted small" style="margin:-4px 2px 12px">${t('regs_sub')}</p>
    <div class="list">${d.items.length ? d.items.map(r => `<a class="row" ${r.kind === 'pdf' ? `href="#/regulation/${r.id}"` : `href="${esc(r.url)}" data-act="reg-link" data-url="${esc(r.url)}"`}>
      <div class="ic">${ic('book')}</div><div class="body"><div class="t">${esc(r.title)}</div>${r.description ? `<div class="d">${esc(r.description)}</div>` : ''}</div>${ic('chev', 'chev')}</a>`).join('')
      : empty('book', t('no_regs'))}</div>` });
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-act="reg-link"]');
  if (!a) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (tg && tg.openLink) tg.openLink(a.dataset.url); else window.open(a.dataset.url, '_blank', 'noopener');
}, true);
async function viewRegulation(rid) {
  page({ title: t('regs'), noNav: true, body: `<div class="empty">${ic('book')}<b>${t('doc_loading')}</b></div>` });
  let d;
  try { d = await api(`/api/regulations/${rid}/pages`); } catch (e) { return page({ title: t('regs'), noNav: true, body: errorBox() }); }
  page({ title: d.title, sub: t('regs'), noNav: true, body: `<div class="doc-tools"><span class="muted small">${d.pages} ${t('pages')} · ${t('tap_zoom')}</span></div>
    <div class="doc-pages" id="docPages">${Array.from({ length: d.pages }, (_, i) => `<figure class="doc-page" data-n="${i}"><div class="skeleton"></div></figure>`).join('')}</div>` });
  const w = Math.min(1600, Math.round(window.innerWidth * Math.max(2, window.devicePixelRatio || 2)));
  for (let i = 0; i < d.pages; i++) {
    let url;
    try { url = URL.createObjectURL(await (await api(`/api/regulations/${rid}/page/${i}?w=${w}`, { raw: true })).blob()); } catch (e) { continue; }
    const fig = document.querySelector(`.doc-page[data-n="${i}"]`);
    if (!fig) return;
    fig.innerHTML = `<img src="${url}" alt="${i + 1}">`;
  }
  const box = document.getElementById('docPages');
  if (box) box.addEventListener('click', e => { if (e.target.tagName === 'IMG') { box.classList.toggle('zoom'); haptic('light'); } });
}

/* ================================================================ yangilashsiz: zaxira tekshiruv va ilova versiyasi */
// Jonli ulanish (SSE) Telegram ichida ba'zan uziladi — har 20 soniyada yengil /api/pulse: yangi bildirishnoma,
// xabar yoki so'rovnoma bo'lsa darhol ko'rsatiladi; server yangilangan bo'lsa ilova keyingi o'tishda o'zini yangilaydi.
const PULSE = { v: null, reload: false };
async function pulse() {
  if (document.hidden || !S.me || S.me.role !== 'parent') return;
  let p;
  try { p = await api('/api/pulse'); } catch (e) { return; }
  if (PULSE.v && p.v !== PULSE.v) PULSE.reload = true;
  PULSE.v = PULSE.v || p.v;
  const u = S.me.unread = S.me.unread || {};
  const moreNotes = p.notifications > (u.notifications || 0), moreMsgs = p.messages > (u.messages || 0);
  const surveysChanged = S.pendingSurveys != null && p.surveys !== S.pendingSurveys;
  u.notifications = p.notifications; u.messages = p.messages;
  if (!moreNotes && !moreMsgs && !surveysChanged) return;
  const h = (location.hash || '#/').split('?')[0];
  if (['#/', '#', '#/surveys', '#/notifications'].includes(h) || (moreMsgs && h.startsWith('#/chat'))) route(); else updateChrome();
  // jonli voqea kelmagan (ulanish uzilgan yoki «osilib» qolgan) — bildirishnomani shu yerda ko'rsatamiz
  if ((moreNotes || moreMsgs) && Date.now() - (LIVE.last || 0) > 25000) { haptic('light'); banner({ type: moreMsgs ? 'message' : 'notification', text: t('new_note'), route: moreMsgs ? '/chat' : '/notifications' }); }
}
setInterval(pulse, 20000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) { if (PULSE.reload) location.reload(); else pulse(); } });

/* ================================================================ hujjatni ilovada ko'rish */
async function viewDoc(did) {
  const c = S.child;
  page({ title: t('documents'), sub: c.short, noNav: true, body: `<div class="empty">${ic('file')}<b>${t('doc_loading')}</b></div>` });
  let d;
  try { d = await api(childPath(c, `documents/${did}/pages`)); } catch (e) { return page({ title: t('documents'), noNav: true, body: errorBox() }); }
  page({ title: d.title.replace(/^\S+\s/, ''), sub: c.short, noNav: true, body: `<div class="doc-tools">
      <span class="muted small">${d.pages} ${t('pages')} · ${t('tap_zoom')}</span>
      <button class="btn ghost" data-act="sendDoc" data-id="${did}">${ic('send')} ${t('send_chat')}</button></div>
    <div class="doc-pages" id="docPages">${Array.from({ length: d.pages }, (_, i) => `<figure class="doc-page" data-n="${i}"><div class="skeleton"></div></figure>`).join('')}</div>` });
  const w = Math.min(1600, Math.round(window.innerWidth * Math.max(2, window.devicePixelRatio || 2)));
  for (let i = 0; i < d.pages; i++) {
    let url;
    try { url = URL.createObjectURL(await (await api(childPath(c, `documents/${did}/page/${i}?w=${w}`), { raw: true })).blob()); } catch (e) { continue; }
    const fig = document.querySelector(`.doc-page[data-n="${i}"]`);
    if (!fig) return;  // foydalanuvchi boshqa sahifaga o'tdi
    fig.innerHTML = `<img src="${url}" alt="${i + 1}-sahifa">`;
  }
  const box = document.getElementById('docPages');
  if (box) box.addEventListener('click', e => { if (e.target.tagName === 'IMG') { box.classList.toggle('zoom'); haptic('light'); } });
}

/* ================================================================ kurs koordinatori: bog'lash so'rovlari */
function stuOk(r) {  // talaba tasdig'i — yakuniy qaror koordinatorda
  if (r.student_ok) return `<div class="alert ok" style="margin-top:10px"><div class="bar"></div><div class="small"><b>✅ Talabaning o‘zi tasdiqladi</b> (${esc(when(r.student_ok.at))})<br>Telegram: ${esc(r.student_ok.tg_name || '—')}<br>Raqami: ${esc(fmtPhone(r.student_ok.phone))} — ${r.student_ok.source === 'parent' ? '<b>⚠️ bazada yo‘q, raqamni ota-ona kiritgan.</b> Raqam haqiqatan talabaniki ekanini tekshiring' : 'bazadagi talaba raqami bilan mos'}</div></div>`;
  return `<div class="small muted" style="margin-top:8px">${r.student_can_confirm ? '⏳ Talaba hali tasdiqlamagan' + (r.claimed_phone ? ` (ota-ona kiritgan raqam: ${esc(fmtPhone(r.claimed_phone))})` : '') : 'Talaba raqami bazada yo‘q — o‘zi tasdiqlay olmaydi, ota-ona bilan telefonda gaplashib tekshiring'}</div>`;
}
async function viewStaffRequests() {
  page({ title: 'So‘rovlar', active: '', body: loading() });
  let d;
  try { d = await api('/api/staff/requests'); } catch (e) { return page({ title: 'So‘rovlar', active: '', body: errorBox() }); }
  const langs = { uz: 'o‘zbek', ru: 'rus', en: 'ingliz' };
  page({ title: 'So‘rovlar', sub: `${d.items.length} ta`, active: '', body: `<h2 class="screen-title">Bog‘lash so‘rovlari</h2>
    <p class="muted small" style="margin:-4px 0 12px">Talaba o‘zi tasdiqlagan so‘rovlar yuqorida. Yakuniy tasdiq — sizda: «Tasdiqlash» bosilgandagina ota-ona ulanadi.</p>
    ${d.items.length ? d.items.map(r => `<div class="card req">
      <div class="t"><b>${esc(r.parent_name || 'Ota-ona')}</b> <span class="muted small">${esc(fmtPhone(r.phone))}${r.lang !== 'uz' ? ', ' + langs[r.lang] + ' tilida' : ''}</span></div>
      <div class="small" style="margin-top:6px">So‘ralgan talaba: <b>${r.student ? esc(r.student.name) : '—'}</b>${r.student ? ` <span class="muted">(${esc(r.student.group)})</span>` : ''}</div>
      <div class="small muted" style="margin-top:4px">Ota-ona yozgan: ${esc(r.note)}</div>
      ${stuOk(r)}
      ${r.blocked ? '<div class="small" style="color:var(--bordo-fg);margin-top:6px">Talaba deb bloklangan — avval botda /bloklar orqali ruxsat bering</div>' : ''}
      <div class="grid2" style="margin-top:12px"><button class="btn" data-act="req" data-id="${r.id}" data-ok="1" ${r.blocked ? 'disabled' : ''}>Tasdiqlash</button>
        <button class="btn ghost" data-act="req" data-id="${r.id}" data-ok="0">Rad etish</button></div></div>`).join('')
      : `<div class="list">${empty('ok', 'Kutilayotgan so‘rov yo‘q')}</div>`}` });
}

/* ================================================================ kurs koordinatori: rasmiy hujjat yuborish */
const DOC_KINDS = [['tushuntirish', 'Tushuntirish xati'], ['ogohlantirish', 'Dekan ogohlantirishi'], ['hayfsan', 'Hayfsan'], ['boshqa', 'Rasmiy hujjat']];
function viewStaffDocs() {
  const j = S.docJob;
  if (!j) {
    page({ title: 'Hujjat yuborish', active: '', body: `<h2 class="screen-title">Rasmiy hujjat yuborish</h2>
      <form class="card" data-act="doc-upload"><label class="drop"><input type="file" name="file" accept="application/pdf,.pdf">
        <span class="drop-ic">${ic('file')}</span><span class="drop-t" id="fname">PDF faylni tanlang</span>
        <span class="drop-s">Buyruq yoki xat — ichidagi talabalar avtomatik topiladi</span></label>
        <button class="btn block" style="margin-top:14px">${ic('upload')} Yuklash va o‘qish</button></form>
      <p class="muted small" style="margin-top:12px">Har bir ota-onaga faqat o‘z farzandi ko‘rinadigan nusxa boradi: boshqa talabalarning ma’lumoti qora rang bilan yopiladi. Yuborishdan oldin har bir nusxani ko‘rasiz.</p>` });
    return;
  }
  const sel = j.found.filter(x => j.sel.has(x.id));
  page({ title: 'Hujjat yuborish', sub: j.file_name, active: '', body: `
    <div class="card"><b>📄 ${esc(j.file_name)}</b><div class="small muted" style="margin-top:4px">${j.readable
      ? `${j.pages} sahifa, hujjatda ${j.found.filter(x => x.auto).length} ta talaba topildi`
      : '⚠️ Hujjat matnini o‘qib bo‘lmadi — nusxalar asl holida yuboriladi (boshqa talabalar yopilmaydi)'}</div></div>
    <section class="section"><div class="section-head"><h2>${hi('Talabalar')}Talabalar</h2><span class="muted small">${sel.length} ta tanlandi</span></div>
      <div class="list">${j.found.length ? j.found.map(x => `<label class="row"><span class="switch"><input type="checkbox" data-act="doc-sel" data-id="${x.id}" ${j.sel.has(x.id) ? 'checked' : ''}><i></i></span>
        <div class="body"><div class="t">${esc(x.name)}</div><div class="d">${esc(x.group)}${x.hemis_id ? ', HEMIS ' + esc(x.hemis_id) : ''}</div>${x.note ? `<div class="d" style="color:var(--bordo-fg);font-weight:600">⚠️ ${esc(x.note)}</div>` : ''}</div>
        <button class="btn ghost" type="button" style="min-height:36px;padding:0 10px" data-act="doc-preview" data-id="${x.id}">Ko‘rish</button></label>`).join('')
        : empty('users', 'Talaba topilmadi', 'Pastdan qidirib qo‘shing')}</div>
      <form data-act="doc-find" style="display:flex;gap:8px;margin-top:10px"><input class="input" name="q" placeholder="Talabani qo‘shish: familiya yoki HEMIS ID"><button class="btn" aria-label="Qidirish">${ic('search')}</button></form>
      <div id="docFind"></div></section>
    <section class="section"><div class="section-head"><h2>${hi('Hujjat turi')}Hujjat turi</h2></div>
      <div class="seg wrap">${DOC_KINDS.map(([k, l]) => `<button data-act="doc-type" data-v="${k}" aria-pressed="${j.dtype === k}">${l}</button>`).join('')}</div>
      <input class="input" id="docComment" style="margin-top:10px" value="${esc(j.comment || '')}" placeholder="Izoh: buyruq raqami va sanasi (ixtiyoriy)"></section>
    <div id="docPreview"></div>
    <button class="btn block" data-act="doc-send" ${sel.length ? '' : 'disabled'} style="margin-top:16px">${ic('send')} Yuborish — ${sel.length} ta talaba</button>
    <button class="btn ghost block" data-act="doc-reset" style="margin-top:8px">Boshqa hujjat</button>` });
}
async function docPreview(sid) {
  const j = S.docJob, box = document.getElementById('docPreview'); if (!j || !box) return;
  const x = j.found.find(y => y.id === sid);
  box.innerHTML = `<section class="section"><div class="section-head"><h2>${esc(x ? x.name : '')} — nusxa</h2></div><div class="skeleton" style="height:240px"></div></section>`;
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  let info;
  try { info = await api(`/api/staff/docs/${j.token}/${sid}`); } catch (e) { box.innerHTML = empty('alert', e.status === 410 ? 'Hujjat seansi tugadi — qayta yuklang' : t('error')); return; }
  const notes = !info.checked ? ['⚠️ Hujjat tekshirilmadi — asl holida yuboriladi']
    : [info.boxes ? `🔒 Yopilgan joylar: ${info.boxes}` : 'Yopiladigan boshqa talaba yo‘q'].concat(info.found ? [] : ['⚠️ Talabaning o‘zi hujjatda topilmadi']).concat(info.ambiguous ? ['⚠️ Ismi o‘xshash talaba bor — diqqat bilan tekshiring'] : []);
  box.innerHTML = `<section class="section"><div class="section-head"><h2>${esc(x ? x.name : '')} — ota-onasi ko‘radigan nusxa</h2></div>
    <div class="small" style="margin-bottom:8px">${notes.join('<br>')}</div><div class="doc-pages">${Array.from({ length: info.pages }, (_, i) => `<figure class="doc-page" data-pn="${i}"><div class="skeleton"></div></figure>`).join('')}</div></section>`;
  for (let i = 0; i < info.pages; i++) {
    try {
      const url = URL.createObjectURL(await (await api(`/api/staff/docs/${j.token}/${sid}/page/${i}?w=1100`, { raw: true })).blob());
      const fig = box.querySelector(`[data-pn="${i}"]`); if (fig) fig.innerHTML = `<img src="${url}" alt="${i + 1}-sahifa">`;
    } catch (e) { /* */ }
  }
}


/* ================================================================ akademik qarzdorlik: fanlar nomi bilan */
function debtRow(x) {
  const info = [x.semester ? t('sem_n', { n: x.semester }) : '', x.credits ? t('credits_n', { n: num(x.credits) }) : '',
    x.source === 'hemis' ? t('from_hemis') : (x.score != null ? t('debt_score', { s: num(x.score) }) : '')].filter(Boolean).join(' · ');
  return `<div class="row" style="cursor:default"><div class="ic bordo">${ic('grade')}</div>
    <div class="body"><div class="t">${esc(x.subject)}</div><div class="d">${esc(info)}</div></div></div>`;
}
async function viewDebts() {
  const c = S.child;
  page({ title: t('debts_title'), sub: c.short, active: '', body: loading() });
  let d;
  try { d = await api(childPath(c, 'grades')); } catch (e) { return page({ title: t('debts_title'), sub: c.short, active: '', body: errorBox() }); }
  const L = d.debt_list || [];
  page({ title: t('debts_title'), sub: c.short, active: '', body: `<h2 class="screen-title">${t('debts_title')}</h2>
    ${L.length ? `<div class="verdict bad">${ic('alert')}<div><b>${L.length} ${esc(subjUnit(L.length))}</b><p>${esc(L.map(x => x.subject).join(', '))}</p></div></div>
      <div class="list" style="margin-top:14px">${L.map(debtRow).join('')}</div>
      <p class="muted small" style="margin-top:12px">${t('debts_help')}</p>
      <a class="btn block" href="#/chat" style="margin-top:8px">${ic('chat')} ${t('ask_coord')}</a>`
      : `<div class="verdict ok">${ic('ok')}<div><b>${t('no_debts')}</b></div></div>`}` });
}
async function route() {
  if (PULSE.reload) { location.reload(); return; }  // server yangilangan — yangi versiya (qo'lda yangilash shart emas)
  clearInterval(S.timer);
  if (!S.me) return;  // hali kirilmagan yoki chiqilgan (kirish ekrani)
  const [path, qs] = (location.hash.slice(1) || '/').split('?');
  const params = new URLSearchParams(qs || '');
  const parts = path.split('/').filter(Boolean);
  const role = S.me.role;
  if (tg && tg.BackButton) { (['', 'schedule', 'attendance', 'grades', 'staff'].includes(parts[0] || '') && parts.length <= 1) ? tg.BackButton.hide() : tg.BackButton.show(); }
  if (role === 'staff' || role === 'super') {
    if (parts[0] !== 'staff') return viewStaff();
    if (parts[1] === 'students') return viewStaffStudents(params);
    if (parts[1] === 'student') { if (params.get('c')) { S.staffCourse = params.get('c'); S.me.staff.course = S.staffCourse; } return viewStaffStudent(parts[2]); }
    if (parts[1] === 'inbox') return viewStaffInbox();
    if (parts[1] === 'chat') return viewStaffChat(parts[3], parts[4]);
    if (parts[1] === 'announce') return viewStaffAnnounce();
    if (parts[1] === 'files') return viewStaffFiles();
    if (parts[1] === 'courses') return viewSuperCourses();
    if (parts[1] === 'requests') return viewStaffRequests();
    if (parts[1] === 'docs') return viewStaffDocs();
    if (parts[1] === 'surveys') return parts[2] === 'new' ? viewStaffSurveyNew() : parts[2] ? viewStaffSurvey(parts[2]) : viewStaffSurveys();
    return viewStaff();
  }
  if (role === 'new') return viewWelcome();
  if (role === 'pending') return viewPending();
  if (role === 'blocked') { $app.innerHTML = `<main class="no-nav">${empty('alert', t('blocked'))}</main>`; return; }
  if (parts[0] === 'go') {  // Telegram xabaridagi «Ilovada ochish» tugmasi: kerakli farzand + bo'lim
    if (parts[2] && parts[3]) pickChild(`${decodeURIComponent(parts[2])}/${parts[3]}`);
    location.replace('#' + (GO_ROUTE[parts[1]] || '/notifications'));
    return;
  }
  if (parts[0] === 'chat' && parts[2]) pickChild(`${decodeURIComponent(parts[1])}/${parts[2]}`);
  switch (parts[0]) {
    case 'doc': return viewDoc(parts[1]);
    case 'debts': return viewDebts();
    case 'schedule': return viewSchedule(params.get('week'));
    case 'attendance': return viewAttendance();
    case 'grades': return viewGrades();
    case 'chat': return viewChat();
    case 'notifications': return viewNotifications();
    case 'news': return viewNews();
    case 'finance': return viewFinance();
    case 'documents': return viewDocs();
    case 'trends': return viewTrends();
    case 'menu': return viewMenu();
    case 'surveys': return viewSurveys();
    case 'survey': return viewSurvey(parts[1], parts[2]);
    case 'regulations': return viewRegulations();
    case 'regulation': return viewRegulation(parts[1]);
    case 'settings': return viewSettings();
    case 'info': return viewInfo();
    default: return viewHome();
  }
}

/* ================================================================ amallar */
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-act]');
  if (!el || el.tagName === 'FORM' || el.tagName === 'SELECT' || el.type === 'checkbox') return;
  const act = el.dataset.act;
  if (act === 'child') { haptic(); pickChild(el.dataset.key); route(); }
  else if (act === 'day') { haptic(); S.cache.day = Number(el.dataset.i); renderSchedule(); }
  else if (act === 'week') { haptic(); viewSchedule(el.dataset.week); }
  else if (act === 'reload') { route(); }
  else if (act === 'lang') {
    haptic(); S.lang = el.dataset.lang; document.documentElement.lang = S.lang;
    try { await api('/api/settings', { json: { lang: S.lang } }); await boot(true); } catch (_) { route(); }
  } else if (act === 'contact') {
    if (!tg || !tg.requestContact) { if (S.me.bot) openExternal(`https://t.me/${S.me.bot}?start`); else toast(t('open_in_tg')); return; }
    tg.requestContact(async okShared => {
      if (!okShared) return;
      el.disabled = true; el.textContent = t('confirming');
      for (let i = 0; i < 12; i++) { await new Promise(r => setTimeout(r, 1500)); await boot(true); if (S.me.role !== 'new') return; }
      el.disabled = false; el.textContent = t('confirm_phone');
    });
  } else if (act === 'sendDoc') {
    el.disabled = true;
    try { await api(childPath(S.child, `documents/${el.dataset.id}/send`), { method: 'POST', json: {} }); haptic('medium'); toast(t('sent_chat')); } catch (_) { toast(t('error')); }
    el.disabled = false;
  } else if (act === 'export') {
    el.disabled = true;
    try { await api(`/api/staff/export/send?fmt=${el.dataset.fmt}`, { method: 'POST', json: {} }); toast('Hisobot chatingizga yuborildi'); } catch (_) { toast('Xato yuz berdi'); }
    el.disabled = false;
  } else if (act === 'pickCourse') { S.staffCourse = el.dataset.key; localStorage.setItem('staffCourse', S.staffCourse); await boot(true); location.hash = '#/staff'; }
});
document.addEventListener('change', async e => {
  const el = e.target;
  if (el.dataset.act === 'flag') {
    haptic();
    try { await api('/api/settings', { json: { key: el.dataset.key, value: el.checked } }); toast(t('saved')); } catch (_) { el.checked = !el.checked; toast(t('error')); }
  } else if (el.dataset.act === 'course') { S.staffCourse = el.value; localStorage.setItem('staffCourse', el.value); await boot(true); }
});
document.addEventListener('input', e => {
  if (e.target.matches('.composer textarea')) { e.target.style.height = 'auto'; e.target.style.height = Math.min(140, e.target.scrollHeight) + 'px'; }
});
document.addEventListener('submit', async e => {
  const f = e.target, act = f.dataset.act;
  if (!act) return;
  e.preventDefault();
  const fd = new FormData(f);
  const btn = f.querySelector('button');
  if (btn) btn.disabled = true;
  try {
    if (act === 'send') {
      const text = String(fd.get('text') || '').trim();
      if (text) { await api(childPath(S.child, 'messages'), { json: { text } }); haptic('medium'); f.querySelector('textarea').value = ''; await refreshChat(false); }
    } else if (act === 'reply') {
      const text = String(fd.get('text') || '').trim();
      if (text) { await api(`/api/staff/thread/${f.dataset.sid}/${f.dataset.pid}`, { json: { text } }); haptic('medium'); await viewStaffChat(f.dataset.sid, f.dataset.pid, false); }
    } else if (act === 'link') {
      const hemis = String(fd.get('hemis') || '').trim(), d = String(fd.get('verify') || '');
      const verify = hemis || (d ? d.split('-').reverse().join('.') : '');  // 2008-05-05 → 05.05.2008
      const r = await api('/api/link', { json: { name: fd.get('name'), verify } });
      haptic('success');
      if (r.state === 'linked') await boot(true); else await viewPending();
    } else if (act === 'search') {
      location.hash = `#/staff/students?${fd.get('all') ? 'all=1&' : ''}q=${encodeURIComponent(fd.get('q') || '')}`;
    } else if (act === 'announce') {
      const all = fd.get('all') === 'on';
      const groups = String(fd.get('groups') || '').split(',').map(x => x.trim()).filter(Boolean);
      const course = staffCourseTitle();
      const msg = all ? 'E’lon BARCHA kurslarning ota-onalariga yuboriladi.'
        : groups.length ? `E’lon «${course}» kursining ${groups.join(', ')} guruhi ota-onalariga yuboriladi.`
        : (S.me.staff && S.me.staff.groups || []).length ? `E’lon ${S.me.staff.groups.join(', ')} guruhlari ota-onalariga yuboriladi.`
        : `E’lon «${course}» kursining butun ota-onalariga yuboriladi.`;
      if (!await confirmAsync(msg + ' Yuborilgan e’lonni qaytarib bo‘lmaydi.')) return;
      const r = all ? await api('/api/super/announce', { json: { text: fd.get('text') } })
        : await api('/api/staff/announce', { json: { text: fd.get('text'), groups } });
      document.getElementById('result').innerHTML = r.recipients
        ? `<div class="verdict ok" style="margin-top:14px">${ic('ok')}<div><b>E’lon yuborildi</b><p>${r.sent} / ${r.recipients} ota-onaga yetkazildi${all ? ' (barcha kurslar)' : ` («${esc(course)}»)`}.</p></div></div>`
        : `<div class="verdict warn" style="margin-top:14px">${ic('alert')}<div><b>Hech kimga yuborilmadi</b><p>${all ? 'Kurslarda' : `«${esc(course)}» kursida`} botga ulangan ota-ona yo‘q${groups.length ? ' (tanlangan guruhlarda)' : ''}.</p></div></div>`;
      f.reset();
    } else if (act === 'import') {
      const files = Array.from(f.querySelector('input[type=file]').files || []);
      const res = document.getElementById('result');
      if (!files.length) { toast('Avval Excel faylni tanlang'); return; }
      res.innerHTML = `<div class="skeleton" style="height:80px;margin-top:14px"></div>`;
      const out = [];
      for (const file of files) {
        const body = new FormData();
        body.append('file', file);
        body.append('kind', f.dataset.force || fd.get('kind'));
        if (f.dataset.force) body.append('force', '1');
        if (fd.get('silent')) body.append('caption', 'jim');
        const r = await api('/api/staff/import', { body });
        if ((r.state === 'confirm' || r.state === 'choose') && files.length > 1) {
          out.push(`<div class="alert warn" style="margin-top:14px"><div class="bar"></div><div><b>${esc(file.name)}</b> — ${r.state === 'confirm'
            ? `faylda «${esc(r.detected_title)}» ustunlari bor, siz «${esc(r.kind_title)}» ni tanladingiz.` : 'fayl turi aniqlanmadi.'} Bu faylni alohida yuklang.</div></div>`);
          continue;
        }
        if (r.state === 'confirm') {
          delete f.dataset.force;
          res.innerHTML = `<div class="alert warn" style="margin-top:14px"><div class="bar"></div><div><b>Diqqat!</b> Faylda «${esc(r.detected_title)}» fayliga xos ustunlar bor, siz «${esc(r.kind_title)}» ni tanladingiz.
            <div class="grid2" style="margin-top:10px"><button class="btn ghost" type="button" id="useDetected">«${esc(r.detected_title)}» sifatida</button><button class="btn ghost" type="button" id="forceKind">Baribir yuklash</button></div></div></div>`;
          document.getElementById('useDetected').onclick = () => { f.dataset.force = r.detected; f.requestSubmit(); };
          document.getElementById('forceKind').onclick = () => { f.dataset.force = fd.get('kind'); f.requestSubmit(); };
          return;
        }
        if (r.state === 'choose') {
          delete f.dataset.force;
          res.innerHTML = `<div class="alert warn" style="margin-top:14px"><div class="bar"></div><div>Fayl turi aniqlanmadi — ro‘yxatdan tanlang va qayta yuklang.</div></div>`;
          return;
        }
        out.push(`<div class="card report" style="margin-top:14px">${files.length > 1 ? `<b>📄 ${esc(file.name)}</b><br>` : ''}${safeHtml(r.report)}</div>`);
      }
      delete f.dataset.force;
      res.innerHTML = out.join('');
      loadImportsApp();
    }
  } catch (err) {
    const code = err.data && err.data.error;
    toast(code === 'too_many' ? t('too_many') : code === 'not_matched' ? t('not_matched') : code === 'too_many_attempts' ? t('too_many_tries') : t('error'));
  } finally { if (btn) btn.disabled = false; }
});
document.addEventListener('change', e => {  // fayl tanlanganda nomini ko'rsatish
  const inp = e.target.closest('.drop input[type=file]');
  if (!inp) return;
  const n = inp.files.length, el = document.getElementById('fname');
  if (el) el.textContent = !n ? 'Excel faylni tanlang' : n === 1 ? inp.files[0].name : `${n} ta fayl tanlandi`;
  inp.closest('.drop').classList.toggle('has', n > 0);
});
document.addEventListener('click', async e => {  // kurs koordinatori: kompyuter versiyasini brauzerda ochish
  const b = e.target.closest('[data-act="desk"]');
  if (!b) return;
  b.disabled = true;
  try {
    const r = await api('/api/desk/link', { method: 'POST', json: {} });
    if (tg && tg.openLink) tg.openLink(r.url); else window.open(r.url, '_blank', 'noopener');
    toast('Panel brauzerda ochildi. Havola 10 daqiqa amal qiladi');
  } catch (err) {
    toast(err.data && err.data.error === 'no_url' ? 'Ilova manzili sozlanmagan' : 'Havolani olib bo‘lmadi');
  }
  b.disabled = false;
});
/* ---- mavzu, so'rovlar, hujjat yuborish, super-admin qamrovi ---- */
function confirmAsk(text) { return confirmSafe(text); }
document.addEventListener('click', async e => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const act = el.dataset.act;
  const mine = ['back', 'theme', 'theme-set', 'req', 'doc-preview', 'doc-type', 'doc-send', 'doc-reset', 'doc-add', 'scope'];
  if (!mine.includes(act)) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (act === 'back') { goBack(); return; }
  if (act === 'theme') {
    const order = ['auto', 'light', 'dark'], next = order[(order.indexOf(themePref()) + 1) % 3];
    setTheme(next); haptic('light'); toast(`${t('theme')}: ${t('th_' + next)}`);
  } else if (act === 'theme-set') {
    setTheme(el.dataset.v); haptic('light');
    document.querySelectorAll('[data-act="theme-set"]').forEach(b => b.setAttribute('aria-pressed', String(b === el)));
  } else if (act === 'scope') {
    location.hash = el.dataset.all === '1' ? '#/staff/students?all=1' : '#/staff/students';
  } else if (act === 'req') {
    const approve = el.dataset.ok === '1';
    if (!approve && !await confirmAsk('So‘rovni rad etasizmi? Ota-onaga xabar boradi.')) return;
    el.disabled = true;
    try { const r = await api(`/api/staff/requests/${el.dataset.id}`, { json: { approve } }); haptic('success'); toast(r.message.replace(/^[✅❌]\s*/, '') + ' — ota-onaga xabar yuborildi'); }
    catch (err) { toast((err.data && err.data.error) || t('error')); }
    route();
  } else if (act === 'doc-preview') {
    docPreview(Number(el.dataset.id));
  } else if (act === 'doc-type') {
    if (!S.docJob) return;
    S.docJob.dtype = el.dataset.v;
    document.querySelectorAll('[data-act="doc-type"]').forEach(b => b.setAttribute('aria-pressed', String(b === el)));
  } else if (act === 'doc-add') {
    const j = S.docJob; if (!j) return;
    const x = JSON.parse(el.dataset.st);
    if (!j.found.some(y => y.id === x.id)) j.found.push({ ...x, auto: false });
    j.sel.add(x.id); j.comment = (document.getElementById('docComment') || {}).value || j.comment;
    viewStaffDocs();
  } else if (act === 'doc-reset') {
    S.docJob = null; viewStaffDocs();
  } else if (act === 'doc-send') {
    const j = S.docJob; if (!j) return;
    j.comment = (document.getElementById('docComment') || {}).value || '';
    const title = (DOC_KINDS.find(k => k[0] === j.dtype) || DOC_KINDS[3])[1];
    if (!await confirmAsk(`«${title}» ${j.sel.size} ta talabaning ota-onalariga yuboriladi. Davom etasizmi?`)) return;
    el.disabled = true; el.textContent = 'Yuborilmoqda…';
    try {
      const r = await api('/api/staff/docs/send', { json: { token: j.token, sids: [...j.sel], dtype: j.dtype, comment: j.comment } });
      S.docJob = null; haptic('success');
      page({ title: 'Hujjat yuborildi', active: '', body: `<h2 class="screen-title">${esc(r.title)} yuborildi</h2><div class="list">${r.items.map(x =>
        `<div class="row" style="cursor:default"><div class="ic ${x.sent ? '' : 'bordo'}">${ic(x.sent ? 'ok' : 'alert')}</div><div class="body"><div class="t">${esc(x.student)}</div>
        <div class="d">${x.parents ? `ota-onalarga yetkazildi: ${x.sent}/${x.parents}` : 'ota-ona hali ulanmagan — ulangach «Hujjatlar»da ko‘radi'}${x.boxes ? ` · 🔒 yopilgan: ${x.boxes}` : ''}</div></div></div>`).join('')}</div>
        <a class="btn block" href="#/staff/docs" style="margin-top:16px">Yana hujjat yuborish</a>` });
    } catch (err) {
      toast(err.status === 410 ? 'Hujjat seansi tugadi — faylni qayta yuklang' : t('error'));
      el.disabled = false; el.textContent = 'Yuborish';
    }
  }
}, true);
document.addEventListener('change', e => {
  const el = e.target;
  if (el.dataset && el.dataset.act === 'doc-sel' && S.docJob) {
    e.stopImmediatePropagation();
    const id = Number(el.dataset.id);
    el.checked ? S.docJob.sel.add(id) : S.docJob.sel.delete(id);
    const b = document.querySelector('[data-act="doc-send"]');
    if (b) { b.disabled = !S.docJob.sel.size; b.innerHTML = `${ic('send')} Yuborish — ${S.docJob.sel.size} ta talaba`; }
  } else if (el.closest && el.closest('form[data-act="doc-upload"]') && el.type === 'file') {
    const n = document.getElementById('fname'); if (n) n.textContent = el.files[0] ? el.files[0].name : 'PDF faylni tanlang';
  }
}, true);
document.addEventListener('submit', async e => {
  const f = e.target, act = f.dataset && f.dataset.act;
  if (act !== 'doc-upload' && act !== 'doc-find') return;
  e.preventDefault(); e.stopImmediatePropagation();
  const btn = f.querySelector('button');
  if (act === 'doc-upload') {
    const file = f.querySelector('input[type=file]').files[0];
    if (!file) { toast('Avval PDF faylni tanlang'); return; }
    const body = new FormData(); body.append('file', file);
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> O‘qilmoqda…';
    try {
      const d = await api('/api/staff/docs', { body });
      S.docJob = { token: d.token, file_name: d.file_name, pages: d.pages, readable: d.readable, dtype: d.dtype, comment: '',
        found: d.found.map(x => ({ ...x, auto: true })), sel: new Set(d.found.filter(x => x.select !== false).map(x => x.id)) };
      haptic('success'); viewStaffDocs();
    } catch (err) {
      toast(err.data && err.data.error === 'not_pdf' ? 'Bu PDF fayl emas' : err.data && err.data.error === 'too_big' ? 'Fayl 20 MB dan katta' : t('error'));
      btn.disabled = false; btn.innerHTML = `${ic('upload')} Yuklash va o‘qish`;
    }
  } else {
    const q = String(new FormData(f).get('q') || '').trim(); if (!q) return;
    const box = document.getElementById('docFind');
    try {
      const r = await api(`/api/staff/students?q=${encodeURIComponent(q)}&limit=8`);
      box.innerHTML = `<div class="list" style="margin-top:8px">${r.items.length ? r.items.map(x => `<div class="row" style="cursor:default"><div class="body"><div class="t">${esc(x.name)}</div><div class="d">${esc(x.group)}</div></div>
        <button class="btn ghost" style="min-height:36px;padding:0 12px" data-act="doc-add" data-st='${esc(JSON.stringify({ id: x.id, name: x.name, group: x.group, hemis_id: x.hemis_id }))}'>Qo‘shish</button></div>`).join('') : empty('search', 'Topilmadi')}</div>`;
    } catch (err) { toast(t('error')); }
  }
}, true);
window.addEventListener('hashchange', route);
document.addEventListener('visibilitychange', () => { if (!document.hidden && S.me) api('/api/me').then(me => { S.me.unread = me.unread; }).catch(() => {}); });

/* ================================================================ ishga tushirish */
function themePref() { try { return localStorage.getItem('theme') || 'auto'; } catch (_) { return 'auto'; } }
function setTheme(v) {
  try { localStorage.setItem('theme', v); } catch (_) { /* */ }
  applyTheme(); updateChrome();
}
function applyTheme() {
  const pref = themePref();
  const dark = pref === 'dark' || (pref === 'auto' && (tg ? tg.colorScheme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches));
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  try { tg && tg.setHeaderColor('#0E2240'); tg && tg.setBackgroundColor(dark ? '#0A1322' : '#F3F5F9'); } catch (_) { /* eski versiya */ }
}
async function boot(again) {
  try { S.me = await api('/api/me'); }
  catch (e) {
    if (e.status === 401 && !tg && !DEV) { store.set('appToken', null); return viewLogin(); }
    $app.innerHTML = `<main class="no-nav">${empty('alert', t('error'), e.status === 401 ? t('open_in_tg') : '')}${e.status === 401 ? '' : `<p style="text-align:center"><button class="btn ghost" data-act="reload-boot">${t('retry')}</button></p>`}</main>`;
    const b = document.querySelector('[data-act="reload-boot"]'); if (b) b.onclick = () => boot();
    return;
  }
  S.lang = S.me.lang || 'uz';
  document.documentElement.lang = S.lang;
  if (deskWide() && (S.me.role === 'staff' || S.me.role === 'super')) { location.replace('/desk' + (DEV ? '?dev' : '')); return; }
  if (S.me.staff && S.me.staff.course) S.staffCourse = S.me.staff.course;
  if (S.me.children.length) pickChild(localStorage.getItem('child') || '');
  const start = tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param;
  if (!again && start && !location.hash) location.hash = '#/' + start.replace(/_/g, '/');
  route();
  connectLive();
}
if (tg) {
  tg.ready(); tg.expand();
  try { if (tg.isVersionAtLeast && tg.isVersionAtLeast('7.7')) tg.disableVerticalSwipes(); } catch (_) { /* eski Telegram */ }
  tg.onEvent && tg.onEvent('themeChanged', applyTheme);
  tg.BackButton && tg.BackButton.onClick(goBack);
}
applyTheme();
boot();
};
// Telegram ichida — avval telegram-web-app.js yuklanadi (static/tg.js); oddiy brauzerda — darhol
(window.TG_LOADING || Promise.resolve()).then(JIDU_MAIN);
