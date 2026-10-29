"""Tashrif moduli — kurs koordinatorining ijara xonadonlari, madaniy tashriflar va tadbirlarini rejalashtirish.

Alohida «tashrif-py» loyihasining asosiy qismlari shu botga modul sifatida joylashtirilgan:

  yol.py, tuman.py, malumot/ — manzilga qanday boriladi: joy, bekatlar, avtobuslar, metro; tuman chegaralari
                               (tashrif-py dan deyarli o'zgarishsiz; tarmoq so'rovlari Python'ning o'z vositalarida);
  geodb.py                   — manzillar joyi va bekatlari keshi (barcha kurslar uchun umumiy: data/tashrif/geo.db);
  sozlama.py, util.py        — modul sozlamalari (.env) va yordamchilar.

Rejalar, talaba va dekan o'rinbosari tasdig'i, dalolatnoma — visits.py (kurs bazalarida), bot oqimlari —
handlers/visits.py, boshqaruv paneli — webapp/desk.js («Tashriflar» bo'limi).
"""
