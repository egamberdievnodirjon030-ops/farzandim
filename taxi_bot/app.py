"""Ilovani yig'ish va ishga tushirish."""

from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .bots.admin import build_admin_router
from .bots.common import RoleMiddleware, build_fallback_router, build_role_router
from .bots.driver import build_driver_router
from .bots.passenger import build_passenger_router
from .config import Settings, get_settings
from .db import Database
from .services.taxi import TaxiService
from .ui import kit
from .ui.messenger import Messenger, Role

log = logging.getLogger("taxi_bot")


def build_dispatcher(svc: TaxiService, storage: BaseStorage, bot_roles: dict[int, Role] | None) -> Dispatcher:
    """`bot_roles=None` — bitta bot rejimi (rol foydalanuvchidan so'raladi)."""
    dp = Dispatcher(storage=storage, svc=svc)
    dp.update.outer_middleware(RoleMiddleware(svc, bot_roles))
    if bot_roles is None:
        dp.include_router(build_role_router())
    dp.include_router(build_admin_router())
    dp.include_router(build_passenger_router())
    dp.include_router(build_driver_router())
    dp.include_router(build_fallback_router())
    return dp


def build_bots(settings: Settings) -> tuple[Bot, Bot]:
    defaults = DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True)
    passenger = Bot(settings.passenger_bot_token.get_secret_value(), default=defaults)
    if settings.single_bot:
        return passenger, passenger
    driver = Bot(settings.driver_bot_token.get_secret_value(), default=defaults)  # type: ignore[union-attr]
    return passenger, driver


def build_storage(settings: Settings) -> BaseStorage:
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage

        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


async def setup_commands(settings: Settings, passenger: Bot, driver: Bot) -> None:
    try:
        if settings.single_bot:
            await passenger.set_my_commands(
                [
                    BotCommand(command="start", description="Boshlash"),
                    BotCommand(command="role", description="Rolni almashtirish (yo'lovchi/haydovchi)"),
                    BotCommand(command="help", description="Yordam"),
                ]
            )
            return
        await passenger.set_my_commands(
            [BotCommand(command="start", description="Taksi chaqirish"), BotCommand(command="help", description="Yordam")]
        )
        await driver.set_my_commands(
            [
                BotCommand(command="start", description="Boshlash"),
                BotCommand(command="balance", description="Balans"),
                BotCommand(command="help", description="Qo'llanma"),
            ]
        )
    except TelegramAPIError as exc:  # pragma: no cover - tarmoq
        log.warning("Bot buyruqlarini o'rnatib bo'lmadi: %s", exc)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    db = Database(settings.database_url)
    await db.create_all()

    passenger_bot, driver_bot = build_bots(settings)
    admin_chats = [settings.admin_chat_id] if settings.admin_chat_id else list(settings.admin_ids)
    if not admin_chats:
        log.warning(
            "ADMIN_IDS ham, ADMIN_CHAT_ID ham ko'rsatilmagan: haydovchi arizalari va aloqa so'rovlari "
            "hech kimga yuborilmaydi! .env faylida ADMIN_IDS ni to'ldiring."
        )
    messenger = Messenger(
        {Role.PASSENGER: passenger_bot, Role.DRIVER: driver_bot},
        rich_enabled=settings.rich_messages,
        effects_enabled=settings.message_effects,
        admin_chat_ids=admin_chats,
    )
    kit.configure(settings.button_emoji_ids)
    svc = TaxiService(settings, db, messenger)

    bot_roles = None if settings.single_bot else {passenger_bot.id: Role.PASSENGER, driver_bot.id: Role.DRIVER}
    dp = build_dispatcher(svc, build_storage(settings), bot_roles)
    bots = [passenger_bot] if settings.single_bot else [passenger_bot, driver_bot]

    panel = miniapp = tunnel = maintenance = None
    try:
        for bot in bots:  # avval webhook o'rnatilgan bo'lsa, polling ishlamaydi — o'chiramiz
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except TelegramAPIError as exc:
                log.warning("Webhook o'chirilmadi: %s", exc)
        await setup_commands(settings, passenger_bot, driver_bot)
        await svc.resume()
        panel = await start_admin_panel(settings, svc)
        try:  # ilova (Mini App) ishga tushmasa ham bot chat rejimida ishlayveradi
            miniapp, tunnel = await start_miniapp(settings, svc, passenger_bot, driver_bot)
        except Exception:
            log.exception("Telegram ilovasini ishga tushirib bo'lmadi — bot chat rejimida ishlaydi")
        maintenance = asyncio.create_task(svc.run_maintenance(), name="maintenance")
        log.info(
            "Taksi bot ishga tushdi: %s",
            "bitta bot rejimi (rol so'raladi)" if settings.single_bot else "ikki bot rejimi (yo'lovchi + haydovchi)",
        )
        await dp.start_polling(*bots, allowed_updates=dp.resolve_used_update_types())
    finally:
        if maintenance:
            maintenance.cancel()
        if panel:
            await panel.stop()
        if tunnel:
            await tunnel.stop()
        if miniapp:
            await miniapp.stop()
        await svc.close()
        for bot in {id(b): b for b in (passenger_bot, driver_bot)}.values():
            await bot.session.close()
        await db.close()


async def start_miniapp(settings: Settings, svc: TaxiService, passenger_bot: Bot, driver_bot: Bot):
    """Telegram Mini App: server + (kerak bo'lsa) fondagi HTTPS tunnel + bot menyusidagi "🚕 Taksi" tugmasi."""

    async def menu(url: str | None) -> None:
        await apply_menu(settings, svc, passenger_bot, driver_bot, url)

    if not settings.webapp_enabled:
        await menu(None)
        return None, None
    from .miniapp.server import MiniAppServer
    from .services.tunnel import Tunnel

    p_token = settings.passenger_bot_token.get_secret_value()
    if settings.single_bot:
        tokens = [(p_token, None)]
    else:
        tokens = [(p_token, Role.PASSENGER), (settings.driver_bot_token.get_secret_value(), Role.DRIVER)]  # type: ignore[union-attr]
    server = MiniAppServer(svc, tokens, settings.webapp_port, settings.webapp_host)
    try:
        await server.start()
    except OSError as exc:
        log.warning("Mini App serveri ishga tushmadi (%s-port band?): %s", settings.webapp_port, exc)
        await menu(None)
        return None, None
    if settings.webapp_url:
        await menu(settings.webapp_url)
        return server, None
    if settings.webapp_tunnel != "auto":
        await menu(None)
        return server, None
    tunnel = Tunnel(settings.webapp_port, on_change=menu)
    if not tunnel.available:
        await menu(None)
        print(
            "ℹ️ Telegram ilovasi (Mini App) uchun HTTPS manzil kerak, lekin cloudflared ham, ssh ham topilmadi."
            " README: «Telegram ilovasi» bo'limi. Hozircha bot oddiy chat rejimida ishlaydi."
        )
        return server, None
    await menu(None)  # oldingi ishga tushirishdan qolgan eski (endi ishlamaydigan) havolani darhol olib tashlaymiz
    print("⏳ Ilova uchun HTTPS tunnel fonda ochilmoqda — bot shu vaqtda ham ishlayveradi...")
    tunnel.start()
    return server, tunnel


async def apply_menu(settings: Settings, svc: TaxiService, passenger_bot: Bot, driver_bot: Bot, url: str | None) -> None:
    """Menyu tugmasini ilova manziliga yo'naltiradi; manzil yo'q bo'lsa — oddiy buyruqlar menyusiga qaytaradi."""
    from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo

    svc.webapp_url = url.rstrip("/") if url else None
    base = svc.webapp_url
    try:
        if not base:
            for bot in {id(b): b for b in (passenger_bot, driver_bot)}.values():
                await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            return
        if settings.single_bot:
            await passenger_bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🚕 Taksi", web_app=WebAppInfo(url=f"{base}/"))
            )
        else:
            await passenger_bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🚕 Taksi", web_app=WebAppInfo(url=f"{base}/?app=passenger"))
            )
            await driver_bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🚖 Ish", web_app=WebAppInfo(url=f"{base}/?app=driver"))
            )
    except TelegramAPIError as exc:
        log.warning("Menyu tugmasi o'rnatilmadi: %s", exc)
        return
    print(f"📱 Telegram ilovasi: {base}  (botdagi «🚕 Taksi» menyu tugmasi orqali ochiladi)")


async def start_admin_panel(settings: Settings, svc: TaxiService):
    """Admin web-panelni ishga tushiradi (brauzerda ochiladi). Xato bo'lsa bot baribir ishlayveradi."""
    if not settings.admin_panel_enabled:
        return None
    from .web.server import AdminPanel, resolve_password

    configured = settings.admin_panel_password.get_secret_value() if settings.admin_panel_password else None
    password, created = resolve_password(configured)
    panel = AdminPanel(svc, password, settings.admin_panel_host, settings.admin_panel_port)
    try:
        await panel.start()
    except OSError as exc:
        log.warning("Admin panel ishga tushmadi (%s-port band bo'lishi mumkin): %s", settings.admin_panel_port, exc)
        return None
    host = "localhost" if settings.admin_panel_host in ("127.0.0.1", "localhost") else "<kompyuter-IP>"
    print(f"\n🌐 Admin panel: http://{host}:{settings.admin_panel_port}")
    if configured:
        print("   Parol: .env dagi ADMIN_PANEL_PASSWORD")
    else:
        print(f"   Parol: {password}" + ("  (yangi yaratildi — data/admin_panel_password.txt)" if created else ""))
    print()
    return panel


def setup_logging(level: str) -> None:
    """Konsol + `data/bot.log` (1 MB x 3 fayl) — muammo bo'lsa log faylini ko'rish mumkin."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        Path("data").mkdir(exist_ok=True)
        handlers.append(RotatingFileHandler("data/bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    except OSError:
        pass
    for handler in handlers:
        handler.setFormatter(fmt)
    logging.basicConfig(level=level.upper(), handlers=handlers, force=True)


def run() -> None:
    from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
    from pydantic import ValidationError

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi.")
    except TelegramUnauthorizedError:
        print("\n❌ Telegram tokenni qabul qilmadi. Tokenni tekshiring: python -m taxi_bot setup")
        sys.exit(1)
    except TelegramNetworkError as exc:
        print(f"\n❌ Telegram'ga ulanib bo'lmadi: {exc}")
        print("   Internet ulanishini tekshiring va botni qayta ishga tushiring.")
        sys.exit(1)
    except ValidationError as exc:
        print("\n❌ .env faylida xato bor:")
        for err in exc.errors():
            print(f"   {'.'.join(str(x) for x in err['loc']).upper()}: {err['msg']}")
        print("   Qayta sozlash: python -m taxi_bot setup")
        sys.exit(1)
