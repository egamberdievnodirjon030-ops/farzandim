"""Ota-onalar uchun davomat boti — ishga tushirish nuqtasi. STUDENT_BOT_TOKEN bo'lsa, shu jarayonda talabalar boti
ham ishlaydi (tashrif so'rovlari, tadbir e'lonlari, ota-onani tasdiqlash — botlar.py).

    python bot.py
"""
import asyncio
import logging
import shutil
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramUnauthorizedError
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

import botlar
from config import ADMIN_IDS, BOT_TOKEN, COURSES, DATA_DIR, DB_PATH, STUDENT_BOT_TOKEN, SUPERADMIN_IDS
from database import db
from handlers import admin, appgate, common, groups, mobileapp, parent, search, staff, studentconfirm, superadmin
from handlers import integration as integration_h
from handlers import visits as visits_h
from keyboards import AttCb, ChildCb, DocGetCb, SchCb
from middlewares import BlockedUserMiddleware, CourseMiddleware, LangMiddleware, register_parent_callbacks
from botcommands import setup_commands
from notifier import scheduler_loop
import loc
import webserver
import templates
from logsetup import alert_handler, setup_logging
from i18n import tr, use_lang
from tenancy import central, course_keys, course_title, is_staff, reload_registry, use_course

def build_dispatcher(separate: bool = False) -> Dispatcher:
    """Asosiy (ota-onalar) boti. separate — talabalar uchun alohida bot bor: talaba oqimlari o'sha botda, bu yerda
    faqat eski talaba havolalari va tugmalari yo'naltiriladi."""
    dp = Dispatcher(storage=MemoryStorage())
    # Birinchi: so'rov qaysi kurs bazasiga tegishli (kurs koordinatori — o'z kursi, ota-ona — farzandining kursi)
    register_parent_callbacks(ChildCb, AttCb, SchCb, DocGetCb)
    for observer in (dp.message, dp.callback_query, dp.my_chat_member, dp.chat_member):
        observer.outer_middleware(CourseMiddleware())
    # Talaba deb bloklanganlarning shaxsiy chatdagi har qanday so'rovi shu yerda to'xtatiladi
    dp.message.outer_middleware(LangMiddleware())
    dp.callback_query.outer_middleware(LangMiddleware())
    dp.message.outer_middleware(BlockedUserMiddleware())
    dp.callback_query.outer_middleware(BlockedUserMiddleware())
    # Tartib muhim: guruhlar -> super-admin -> kurs koordinatori menyusi -> ota-ona menyusi -> ro'yxatdan o'tish ->
    # admin buyruqlari -> ism bo'yicha qidiruv (oxirida)
    student = [visits_h.redirect_router] if separate else [studentconfirm.router, visits_h.router]
    dp.include_routers(groups.router, *student, visits_h.staff_router, mobileapp.router, integration_h.router,
                       superadmin.router, staff.router, appgate.router, parent.router, common.router, admin.router,
                       search.router)
    dp.errors.register(on_error)
    return dp


def build_student_dispatcher() -> Dispatcher:
    """Talabalar boti: ota-onani tasdiqlash, shaxsiy havola, tashrif javoblari, e'londa ro'yxatdan o'tish, /start
    (telefon bilan ulanish) va «Tadbirlarim». Ota-ona menyusi va bloklash yo'q."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(LangMiddleware())
    dp.callback_query.outer_middleware(LangMiddleware())
    dp.include_routers(studentconfirm.router, visits_h.router, visits_h.home_router)
    dp.errors.register(on_error)
    return dp


async def _student_bot() -> Bot | None:
    """STUDENT_BOT_TOKEN bo'yicha talabalar boti; token noto'g'ri bo'lsa — ogohlantirish, hammasi bitta botda."""
    if not STUDENT_BOT_TOKEN:
        return None
    if STUDENT_BOT_TOKEN == BOT_TOKEN:
        logging.error("STUDENT_BOT_TOKEN asosiy BOT_TOKEN bilan bir xil — talabalar uchun @BotFather da alohida bot "
                      "yarating. Hozircha hammasi bitta botda ishlaydi.")
        return None
    sbot = Bot(STUDENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        me = await sbot.get_me()
    except TelegramUnauthorizedError:
        await sbot.session.close()
        logging.error("Telegram STUDENT_BOT_TOKEN ni qabul qilmadi (Unauthorized) — @BotFather → /mybots → talabalar boti → "
                      "API Token. Hozircha talabaga tegishli hammasi asosiy botda ishlaydi.")
        return None
    logging.info("Talabalar boti: @%s (id %s)", me.username, me.id)
    try:
        from aiogram.types import BotCommand
        await sbot.set_my_commands([BotCommand(command="start", description="Boshlash / ulanish"),
                                    BotCommand(command="tadbirlar", description="Yaqin tashrif va tadbirlarim")])
    except Exception:  # noqa: BLE001  (buyruqlar menyusi — majburiy emas)
        logging.warning("Talabalar boti buyruqlari o'rnatilmadi")
    return sbot


async def on_error(event: ErrorEvent) -> bool:
    """Kutilmagan xato: jurnalga (kurs va foydalanuvchi bilan) va foydalanuvchiga xushmuomala javob."""
    exc = event.exception
    if isinstance(exc, TelegramBadRequest) and "not modified" in str(exc):
        return True  # zararsiz: xabar o'zgarmagan
    if isinstance(exc, TelegramForbiddenError):
        logging.getLogger("bot").warning("Foydalanuvchi botni bloklagan: %s", exc)
        return True
    if not getattr(exc, "_logged", False):
        logging.getLogger("bot").error("Kutilmagan xato: %s", exc, exc_info=exc)
    upd = event.update
    target = upd.message or (upd.callback_query.message if upd.callback_query else None)
    user = (upd.message.from_user if upd.message else upd.callback_query.from_user if upd.callback_query else None)
    if target is None or user is None or target.chat.type != "private":
        return True
    if is_staff(user.id):
        text = ("⚠️ Kutilmagan texnik xatolik yuz berdi — super-adminga xabar berildi. Iltimos, amalni birozdan so'ng "
                "qayta urinib ko'ring.")
    else:
        with use_lang(await central.get_lang(user.id) or "uz"):
            text = tr("Kechirasiz, texnik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring.")
    try:
        await target.answer(text)
    except Exception:
        pass
    return True


def _move_legacy_db(first: str) -> None:
    """Oldingi versiyadagi yagona baza (data/bot.db) — birinchi kursning bazasiga aylanadi (bir marta)."""
    legacy, target = Path(DB_PATH), Path(DATA_DIR) / first / "bot.db"
    if legacy.exists() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(legacy) + suffix)
            if src.exists():
                shutil.move(str(src), str(target) + suffix)
        logging.warning("Eski baza %s → %s ko'chirildi (kurs «%s»)", legacy, target, course_title(first))


async def open_storage() -> None:
    """Umumiy ro'yxat (central.db) → kurslar reyestri (.env — faqat boshlang'ich sozlama) → har bir kursning alohida
    bazasi: data/<kurs>/bot.db."""
    await central.connect(str(Path(DATA_DIR) / "central.db"))
    await central.seed_from_env()
    await reload_registry()
    raw = await central.get_meta("pair_times")  # super-admin ilovada kiritgan juftlik vaqtlari (.env dan ustun)
    if raw:
        import json
        from config import PAIR_TIMES
        PAIR_TIMES.clear()
        PAIR_TIMES.update({int(k): tuple(v) for k, v in json.loads(raw).items()})
    keys = course_keys()
    if not keys and not SUPERADMIN_IDS:
        raise SystemExit("Kurs ham, super-admin ham yo'q: .env faylida ADMIN_IDS (yoki KURSLAR) yoki SUPERADMIN_IDS ni "
                         "ko'rsating.")
    if keys:
        _move_legacy_db(keys[0])
    for key in keys:  # kurs nomi o'zgargan bo'lsa (KURSLAR qo'shildi) — koordinatorning eski papkasi yangi nomga
        target = Path(DATA_DIR) / key
        if (target / "bot.db").exists():
            continue
        for uid in COURSES[key]:
            old = Path(DATA_DIR) / f"koordinator_{uid}"
            if old != target and (old / "bot.db").exists():
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(old), str(target))
                await central.rename_course(old.name, key)
                logging.warning("Kurs papkasi %s → %s ko'chirildi (ma'lumotlar saqlandi)", old, target)
                break
    await db.open_courses(DATA_DIR, keys)
    n = await templates.load_aliases()  # super-admin shablon o'zgartirganda o'rgatgan ustun nomlari
    if n:
        logging.info("O'rgatilgan ustun nomlari: %s ta", n)
    for key in keys:  # oldingi versiyadan: til sozlamalari va Telegram guruhlar — umumiy ro'yxatga
        d = db.for_course(key)
        for r in await d.fetchall("SELECT tg_id, lang FROM user_prefs"):
            if not await central.get_lang(r["tg_id"]):
                await central.set_lang(r["tg_id"], r["lang"])
        for g in await d.fetchall("SELECT chat_id FROM tg_groups"):
            if not await central.group_course(g["chat_id"]):
                await central.set_group_course(g["chat_id"], key)
        logging.info("Kurs «%s»: %s — koordinatorlar %s", course_title(key), Path(DATA_DIR) / key,
                     ", ".join(map(str, COURSES[key])) or "yo'q")
        try:  # dinamika uchun boshlang'ich nuqta (keyingi yuklash bilan solishtiriladi; o'zgarmagan — yozilmaydi)
            import snapshots
            with use_course(key):
                await snapshots.capture()
        except Exception:
            logging.exception("Dinamika boshlang'ich nuqtasi yozilmadi: %s", key)
    if not SUPERADMIN_IDS:
        logging.warning("SUPERADMIN_IDS bo'sh — kurslarni bot ichidan boshqarish, zaxira nusxa va xatolar haqida "
                        "xabarlar ishlamaydi")


async def main() -> None:
    setup_logging()  # logs/bot.log, logs/errors.log; xatolar — super-adminga
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN ko'rsatilmagan. .env.example dan nusxa olib .env faylini to'ldiring.")
    if not ADMIN_IDS:
        logging.warning("ADMIN_IDS bo'sh — kurs koordinatori buyruqlari va savollar ishlamaydi.")
    await open_storage()
    await loc.reload()  # kurs koordinatori kiritgan fan/fakultet tarjimalari
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:  # token noto'g'ri yoki bekor qilingan bo'lsa — tushunarli xabar bilan to'xtaymiz
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        await bot.session.close()
        await db.close()
        await central.close()
        raise SystemExit(
            "\nTelegram BOT_TOKEN ni qabul qilmadi (Unauthorized).\n"
            "Sabablari: token noto'g'ri ko'chirilgan (bo'sh joy, qo'shtirnoq, yetishmayotgan belgi), "
            "@BotFather da token yangilangan (/revoke) yoki bot o'chirilgan.\n"
            "Yechim: @BotFather → /mybots → botingiz → API Token — tokenni nusxalab, .env dagi "
            "BOT_TOKEN= qatoriga qo'ying va botni qayta ishga tushiring.")
    logging.info("Bot: @%s (id %s)", me.username, me.id)
    alert_handler.attach(bot)
    sbot = await _student_bot()
    botlar.set_bots(bot, sbot)
    dp = build_dispatcher(separate=sbot is not None)
    await setup_commands(bot)
    scheduler = asyncio.create_task(scheduler_loop(bot))
    from handlers.mobileapp import apk_loop
    apk_task = asyncio.create_task(apk_loop())  # telefon ilovasining yangi versiyasi (GitHub Releases)
    import integration
    integ_task = asyncio.create_task(integration.loop(bot))  # «Manage»: davomat va dars jadvali avtomatik
    import visits
    visits_task = asyncio.create_task(visits.loop(bot))  # tashriflar: javob va tashrif eslatmalari
    try:
        visits.start_geo()  # manzillarni xaritadan aniqlash, bekatlar (fon oqimlari; YOL_MALUMOTI=yoq — o'chiq)
    except Exception:
        logging.exception("Yo'l moduli ishga tushmadi")
    web_runner = await webserver.start(bot)  # Telegram Web App (bot ichidagi ilova)
    sdp = build_student_dispatcher() if sbot else None
    student_task = asyncio.create_task(sdp.start_polling(sbot, handle_signals=False, allowed_updates=sdp.resolve_used_update_types())) \
        if sdp else None
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if student_task:
            try:
                await sdp.stop_polling()
            except (RuntimeError, LookupError):
                pass
            student_task.cancel()
        scheduler.cancel()
        apk_task.cancel()
        integ_task.cancel()
        visits_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await db.close()
        await central.close()
        await bot.session.close()
        if sbot:
            await sbot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
