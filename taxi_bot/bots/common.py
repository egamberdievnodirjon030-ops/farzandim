"""Umumiy filtrlar, middleware va bitta bot rejimidagi rol tanlash."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Router
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message, TelegramObject

from ..services.taxi import TaxiService
from ..ui.kit import PRIMARY, SUCCESS, RoleCb, btn, inline
from ..ui.messenger import Role

log = logging.getLogger(__name__)


class RoleIs(Filter):
    """Xabar qaysi rolga tegishli ekanini tekshiradi (ikki bot yoki tanlangan rol)."""

    def __init__(self, role: Role | None) -> None:
        self.role = role

    async def __call__(self, event: TelegramObject, role: Role | None = None) -> bool:
        return role == self.role


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, svc: TaxiService, event_from_user=None) -> bool:
        return bool(event_from_user and svc.settings.is_admin(event_from_user.id))


class RoleMiddleware(BaseMiddleware):
    """`role` ni handlerlarga uzatadi.

    Ikki bot rejimi: rol botning o'zidan aniqlanadi (yo'lovchi boti / haydovchi boti).
    Bitta bot rejimi: foydalanuvchi /start da tanlagan rol (bazada saqlanadi).
    """

    def __init__(self, svc: TaxiService, bot_roles: dict[int, Role] | None) -> None:
        self.svc = svc
        self.bot_roles = bot_roles

    async def get_role(self, tg_id: int) -> Role | None:
        return await self.svc.get_user_role(tg_id)

    async def set_role(self, tg_id: int, role: Role) -> None:
        await self.svc.set_user_role(tg_id, role)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        bot: Bot = data["bot"]
        if self.bot_roles is not None:
            data["role"] = self.bot_roles.get(bot.id)
        else:
            user = data.get("event_from_user")
            data["role"] = await self.get_role(user.id) if user else None
        data["role_mw"] = self
        return await handler(event, data)


def apply_role(router: Router, role: Role) -> Router:
    """Xabar turidagi hodisalarni faqat shu rol uchun o'tkazadi (callbacklar prefiks bo'yicha ajraladi)."""
    for observer in (router.message, router.edited_message):
        observer.filter(RoleIs(role))
    return router


def role_picker_text() -> str:
    return "👋 Xush kelibsiz!\n\n<b>Siz kimsiz?</b> Davom etish uchun tanlang:"


def role_picker_markup():
    return inline(
        [
            btn("🙋 Yo'lovchi", cb=RoleCb(role=Role.PASSENGER.value), style=SUCCESS),
            btn("🚕 Haydovchi", cb=RoleCb(role=Role.DRIVER.value), style=PRIMARY),
        ]
    )


def build_role_router() -> Router:
    """Faqat bitta bot rejimida ulanadi."""
    router = Router(name="role")

    @router.message(CommandStart(), RoleIs(None))  # type: ignore[arg-type]
    async def start_without_role(message: Message) -> None:
        await message.answer(role_picker_text(), reply_markup=role_picker_markup())

    @router.message(RoleIs(None))  # type: ignore[arg-type]
    async def any_without_role(message: Message) -> None:
        await message.answer(role_picker_text(), reply_markup=role_picker_markup())

    @router.message(Command("role"))
    async def change_role(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("🔄 Rolni tanlang:", reply_markup=role_picker_markup())

    @router.callback_query(RoleCb.filter())
    async def picked(
        callback: CallbackQuery,
        callback_data: RoleCb,
        svc: TaxiService,
        role_mw: RoleMiddleware,
        state: FSMContext,
    ) -> None:
        role = Role(callback_data.role)
        if role == Role.PASSENGER and await svc.driver_busy(callback.from_user.id):
            await callback.answer("Avval joriy safarni yakunlang — so'ng yo'lovchi rejimiga o'tasiz.", show_alert=True)
            return
        await state.clear()
        await role_mw.set_role(callback.from_user.id, role)
        if role == Role.PASSENGER:
            await svc.driver_offline(callback.from_user.id)
        await callback.answer("✅ Tanlandi")
        if callback.message:
            await callback.message.delete()
        from .driver import driver_start
        from .passenger import passenger_start

        if isinstance(callback.message, Message):
            if role == Role.PASSENGER:
                await passenger_start(callback.message, callback.from_user, svc)
            else:
                await driver_start(callback.message, callback.from_user, svc, state)

    return router


def build_fallback_router() -> Router:
    router = Router(name="fallback")

    @router.callback_query()
    async def unknown_callback(callback: CallbackQuery) -> None:
        await callback.answer("Bu tugma eskirgan.", show_alert=False)

    @router.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Handler xatosi: %s", event.exception, exc_info=event.exception)
        update = event.update
        try:
            if update.callback_query:
                await update.callback_query.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.", show_alert=True)
            elif update.message:
                await update.message.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.")
        except Exception:  # noqa: BLE001
            pass
        return True

    return router
