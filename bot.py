"""Ota-onalar uchun davomat boti — ishga tushirish nuqtasi.

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

from config import ADMIN_IDS, BOT_TOKEN, COURSES, DATA_DIR, DB_PATH, SUPERADMIN_IDS
from database import db
from handlers import admin, appgate, common, groups, mobileapp, parent, search, staff, studentconfirm, superadmin
from handlers import integration as integration_h
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

def build_dispatcher() -> Dispatcher:
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
    dp.include_routers(groups.router, studentconfirm.router, mobileapp.router, integration_h.router, superadmin.router, staff.router, appgate.router, parent.router, common.router, admin.router,
                       search.router)
    dp.errors.register(on_error)
    return dp


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
    dp = build_dispatcher()
    await setup_commands(bot)
    scheduler = asyncio.create_task(scheduler_loop(bot))
    from handlers.mobileapp import apk_loop
    apk_task = asyncio.create_task(apk_loop())  # telefon ilovasining yangi versiyasi (GitHub Releases)
    import integration
    integ_task = asyncio.create_task(integration.loop(bot))  # «Manage»: davomat va dars jadvali avtomatik
    web_runner = await webserver.start(bot)  # Telegram Web App (bot ichidagi ilova)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.cancel()
        apk_task.cancel()
        integ_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await db.close()
        await central.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
