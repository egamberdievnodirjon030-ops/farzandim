"""Admin buyruqlari: haydovchilarni tasdiqlash, balans, bloklash, statistika."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from ..db.models import Driver, DriverStatus
from ..services.pricing import money
from ..services.taxi import TaxiService
from ..ui.kit import DANGER, SUCCESS, ACb, View, btn, h, inline
from ..ui.messenger import Role
from .common import IsAdmin

ADMIN_HELP = (
    "\n\n<b>Buyruqlar:</b>\n"
    "/pending — tasdiq kutayotgan haydovchilar\n"
    "/driver <code>ID</code> — haydovchi ma'lumoti\n"
    "/topup <code>ID</code> <code>summa</code> — balansni to'ldirish (manfiy — yechish)\n"
    "/block <code>ID</code> · /unblock <code>ID</code>"
)


def _driver_info(d: Driver, svc: TaxiService) -> str:
    status = {
        DriverStatus.PENDING: "⏳ kutilmoqda",
        DriverStatus.APPROVED: "✅ tasdiqlangan",
        DriverStatus.REJECTED: "❌ rad etilgan",
        DriverStatus.BLOCKED: "⛔️ bloklangan",
    }.get(DriverStatus(d.status), d.status)
    return (
        f"🚕 <b>Haydovchi #{d.id}</b> ({status})\n"
        f"👤 {h(d.full_name)} · 📱 <code>{h(d.phone or '—')}</code>\n"
        f"🚘 {h(d.car_color)} {h(d.car_model)} · {h(d.car_plate)}\n"
        f"💳 Balans: <b>{h(money(d.balance, svc.settings.currency))}</b>\n"
        f"⭐ {d.rating:.2f} ({d.rating_count} baho) · Safarlar: {d.trips_count} · Bekor: {d.cancel_count}\n"
        f"Holat: {'🟢 liniyada' if d.is_online else '🔴 liniyada emas'}"
        + (f" · buyurtma #{d.current_order_id}" if d.current_order_id else "")
    )


def build_admin_router() -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())

    @router.message(Command("admin"))
    async def panel(message: Message, svc: TaxiService) -> None:
        st = await svc.admin_stats()
        cur = svc.settings.currency
        await message.answer(
            "🛠 <b>Boshqaruv paneli</b>\n\n"
            f"🟢 Liniyada: <b>{st['online']}</b> (bo'sh: {st['free']})\n"
            f"🚕 Faol buyurtmalar: <b>{st['active']}</b>\n"
            f"✅ Bugun yakunlangan: <b>{st['today_done']}</b>\n"
            f"💰 Bugungi aylanma: <b>{h(money(st['today_turnover'], cur))}</b>\n"
            f"🧾 Bugungi komissiya: <b>{h(money(st['today_commission'], cur))}</b>\n"
            f"😔 Haydovchi topilmagan: {st['today_no_drivers']}\n"
            f"⏳ Tasdiq kutayotgan haydovchilar: {st['pending_drivers']}" + ADMIN_HELP
        )

    @router.message(Command("pending"))
    async def pending(message: Message, svc: TaxiService) -> None:
        async with svc.db.session() as s:
            drivers = (
                await s.scalars(select(Driver).where(Driver.status == DriverStatus.PENDING).limit(20))
            ).all()
        if not drivers:
            await message.answer("Tasdiq kutayotgan haydovchilar yo'q.")
            return
        for d in drivers:
            await message.answer(
                _driver_info(d, svc),
                reply_markup=inline(
                    [
                        btn("✅ Tasdiqlash", cb=ACb(action="ok", id=d.id), style=SUCCESS),
                        btn("❌ Rad etish", cb=ACb(action="no", id=d.id), style=DANGER),
                    ]
                ),
            )

    @router.message(Command("driver"))
    async def driver_info(message: Message, command: CommandObject, svc: TaxiService) -> None:
        if not command.args or not command.args.strip().isdigit():
            await message.answer("Foydalanish: /driver <code>ID</code>")
            return
        d = await svc.find_driver(int(command.args.strip()))
        await message.answer(_driver_info(d, svc) if d else "Haydovchi topilmadi.")

    @router.message(Command("topup"))
    async def topup(message: Message, command: CommandObject, svc: TaxiService) -> None:
        parts = (command.args or "").split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
            await message.answer("Foydalanish: /topup <code>ID</code> <code>50000</code>")
            return
        d = await svc.find_driver(int(parts[0]))
        if d is None:
            await message.answer("Haydovchi topilmadi.")
            return
        amount = int(parts[1])
        d = await svc.adjust_balance(
            d.id, amount, "topup" if amount > 0 else "adjust", note=f"admin {message.from_user.id}"  # type: ignore[union-attr]
        )
        await message.answer(
            f"✅ #{d.id} balansi: <b>{h(money(d.balance, svc.settings.currency))}</b>"  # type: ignore[union-attr]
        )

    async def _set_status(message: Message, command: CommandObject, svc: TaxiService, status: DriverStatus) -> None:
        if not command.args or not command.args.strip().isdigit():
            await message.answer(f"Foydalanish: /{command.command} <code>ID</code>")
            return
        d = await svc.find_driver(int(command.args.strip()))
        if d is None:
            await message.answer("Haydovchi topilmadi.")
            return
        d = await svc.set_driver_status(d.id, status)
        await message.answer(_driver_info(d, svc))  # type: ignore[arg-type]
        text = "⛔️ Hisobingiz bloklandi." if status == DriverStatus.BLOCKED else "✅ Hisobingiz faollashtirildi."
        await svc.msg.send(Role.DRIVER, d.tg_id, View.plain(text, svc.views.driver_menu(False)))  # type: ignore[union-attr]

    @router.message(Command("block"))
    async def block(message: Message, command: CommandObject, svc: TaxiService) -> None:
        await _set_status(message, command, svc, DriverStatus.BLOCKED)

    @router.message(Command("unblock"))
    async def unblock(message: Message, command: CommandObject, svc: TaxiService) -> None:
        await _set_status(message, command, svc, DriverStatus.APPROVED)

    @router.callback_query(ACb.filter(F.action.in_({"ok", "no"})))
    async def decide(callback: CallbackQuery, callback_data: ACb, svc: TaxiService) -> None:
        approve = callback_data.action == "ok"
        d = await svc.get_driver(callback_data.id)
        if d is None or d.status != DriverStatus.PENDING:
            await callback.answer("Ariza allaqachon ko'rib chiqilgan.", show_alert=True)
            return
        d = await svc.set_driver_status(d.id, DriverStatus.APPROVED if approve else DriverStatus.REJECTED)
        await callback.answer("✅ Tasdiqlandi" if approve else "❌ Rad etildi")
        if isinstance(callback.message, Message):
            verdict = "✅ Tasdiqlandi" if approve else "❌ Rad etildi"
            await callback.message.edit_text(
                _driver_info(d, svc) + f"\n\n<b>{verdict}</b> — {h(callback.from_user.full_name)}",  # type: ignore[arg-type]
                reply_markup=None,
            )
        if approve:
            text = (
                "🎉 <b>Tabriklaymiz! Arizangiz tasdiqlandi.</b>\n\n"
                f"💳 Balans: {h(money(d.balance, svc.settings.currency))}\n"  # type: ignore[union-attr]
                "Buyurtma olish uchun <b>🟢 Liniyaga chiqish</b> tugmasini bosing."
            )
        else:
            text = "❌ Afsuski, arizangiz rad etildi. Batafsil ma'lumot uchun operatorga murojaat qiling."
        await svc.msg.send(Role.DRIVER, d.tg_id, View.plain(text, svc.views.driver_menu(False)))  # type: ignore[union-attr]

    return router
