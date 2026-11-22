"""Ilovani yig'ish va ishga tushirish."""

from __future__ import annotations

import asyncio
import logging

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
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    db = Database(settings.database_url)
    await db.create_all()

    passenger_bot, driver_bot = build_bots(settings)
    admin_chats = [settings.admin_chat_id] if settings.admin_chat_id else list(settings.admin_ids)
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

    await setup_commands(settings, passenger_bot, driver_bot)
    await svc.resume()
    maintenance = asyncio.create_task(svc.run_maintenance(), name="maintenance")
    log.info(
        "Taksi bot ishga tushdi: %s",
        "bitta bot rejimi (rol so'raladi)" if settings.single_bot else "ikki bot rejimi (yo'lovchi + haydovchi)",
    )
    try:
        await dp.start_polling(*bots, allowed_updates=dp.resolve_used_update_types())
    finally:
        maintenance.cancel()
        await svc.close()
        await db.close()


def run() -> None:
    asyncio.run(main())
