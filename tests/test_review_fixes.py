"""Tanqidiy ko'rib chiqishda topilgan muammolar uchun testlar."""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from taxi_bot.db.models import Order, OrderStatus
from taxi_bot.services.privacy import mask_contacts
from taxi_bot.ui.messenger import Role

from .conftest import offset
from .test_flow import PASSENGER_TG, _has_offer, add_driver, add_passenger, order_now, wait_for


async def _orders_count(svc) -> int:
    async with svc.db.session() as s:
        return int(await s.scalar(select(func.count(Order.id))))


async def test_double_tap_creates_single_order(make_service, center):
    svc, _ = await make_service()
    await add_passenger(svc)
    q = await svc.build_quote(*center, 10)
    results = await asyncio.gather(*(svc.create_order(PASSENGER_TG, q) for _ in range(3)))
    assert sum(r is not None for r in results) == 1
    assert await _orders_count(svc) == 1


async def test_old_retry_button_cannot_create_second_active_order(make_service, center):
    svc, _ = await make_service(search_timeout_sec=0.3)
    await add_passenger(svc)
    first = await order_now(svc, center)
    assert await wait_for(lambda: _status(svc, first.id, OrderStatus.NO_DRIVERS), timeout=3)
    await svc.dispatch.wait_idle(first.id)
    second = await order_now(svc, center)  # yo'lovchi yangi buyurtma berdi
    assert not await svc.retry_search(PASSENGER_TG, first.id)  # eski "Qayta qidirish"
    assert (await svc.get_order(first.id)).status == OrderStatus.NO_DRIVERS
    assert (await svc.get_order(second.id)).status in (OrderStatus.SEARCHING, OrderStatus.NO_DRIVERS)


async def _status(svc, order_id, status):
    return (await svc.get_order(order_id)).status == status


async def _ride_to_finish(svc, center, tg):
    d = await add_driver(svc, tg, *offset(*center, 200, 0))
    await add_passenger(svc)
    order = await order_now(svc, center, dest=offset(*center, 2000, 0))
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert (await svc.accept_offer(tg, order.id)).ok
    assert await svc.driver_start(tg, order.id)
    assert await svc.driver_finish(tg, order.id)
    return d, order


async def test_driver_is_free_right_after_finish_commission_still_on_confirm(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d, first = await _ride_to_finish(svc, center, 4001)
    assert (await svc.get_driver(d.id)).current_order_id is None  # 10 daqiqa kutib turmaydi
    assert (await svc.get_driver(d.id)).balance == 50_000  # komissiya hali yechilmagan
    assert "bo'shsiz" in [v.text for r, c, _, v in fake.edits if c == 4001][-1]

    # Haydovchi darhol boshqa yo'lovchining buyurtmasini oladi
    await svc.ensure_passenger(5002, "Boshqa")
    await svc.set_passenger_phone(5002, "+998931234567")
    q = await svc.build_quote(*center, 10)
    second = await svc.create_order(5002, q)
    assert await wait_for(lambda: _has_offer(svc, second.id, d.id))
    assert (await svc.accept_offer(4001, second.id)).ok

    # Birinchi yo'lovchi endi tasdiqlaydi: komissiya yechiladi, yangi buyurtma bog'lanishi saqlanadi
    assert await svc.passenger_confirm_arrival(PASSENGER_TG, first.id)
    after = await svc.get_driver(d.id)
    done = await svc.get_order(first.id)
    assert done.status == OrderStatus.COMPLETED
    assert after.balance == 50_000 - done.commission
    assert after.current_order_id == second.id


async def test_not_yet_relinks_free_driver_or_reports_busy(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0)
    d, order = await _ride_to_finish(svc, center, 4101)
    assert await svc.passenger_not_yet(PASSENGER_TG, order.id) == "ok"
    assert (await svc.get_order(order.id)).status == OrderStatus.IN_PROGRESS
    assert (await svc.get_driver(d.id)).current_order_id == order.id

    assert await svc.driver_finish(4101, order.id)
    async with svc.db.session() as s:  # haydovchi allaqachon boshqa buyurtmada
        (await s.get(type(d), d.id)).current_order_id = 999
    assert await svc.passenger_not_yet(PASSENGER_TG, order.id) == "driver_busy"
    assert (await svc.get_order(order.id)).status == OrderStatus.FINISHING
    assert (await svc.get_driver(d.id)).current_order_id == 999


async def test_redispatch_resets_near_alert(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 4201, *offset(*center, 300, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert (await svc.accept_offer(4201, order.id)).ok
    assert (await svc.get_order(order.id)).near_notified  # 300 m — darhol yaqin
    assert await svc.driver_cancel(4201, order.id, no_show=False) == "ok"
    assert not (await svc.get_order(order.id)).near_notified


def test_mask_contacts():
    assert mask_contacts("Raqamim +998 90 123-45-67, qo'ng'iroq qiling") == (
        "Raqamim •••, qo'ng'iroq qiling",
        True,
    )
    assert mask_contacts("901234567 ga yozing")[0] == "••• ga yozing"
    assert mask_contacts("@aziza_taxi yoki t.me/aziza_taxi")[0] == "••• yoki •••"
    # Oddiy ma'lumotlar o'zgarmaydi
    for text in ("3-podyezd, 5-qavat", "15 000 so'm", "14:30 da chiqaman", "2 daqiqada boraman"):
        assert mask_contacts(text) == (text, False)


async def test_contacts_hidden_in_chat_and_comment(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 4301, *offset(*center, 300, 0))
    await add_passenger(svc)
    order = await order_now(svc, center, comment="Qo'ng'iroq qiling 90 555 44 33")
    assert "•••" in (await svc.get_order(order.id)).comment
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert "555 44 33" not in fake.to(Role.DRIVER, 4301)[-1].view.text
    assert (await svc.accept_offer(4301, order.id)).ok
    await svc.relay_text(Role.DRIVER, 4301, "Mening raqamim +998901112233, keyingi safar to'g'ridan-to'g'ri")
    msg = fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text
    assert "901112233" not in msg and "•••" in msg


async def test_welcome_bonus_once_and_limit(make_service):
    from taxi_bot.db.models import DriverStatus

    svc, fake = await make_service(welcome_bonus=30000, welcome_bonus_limit=2)
    ids = []
    for tg in (7101, 7102, 7103):
        d = await svc.register_driver(tg, "Ism", "+998901234567", "Cobalt", "Oq", f"01A{tg}")
        ids.append(d.id)
        await svc.set_driver_status(d.id, DriverStatus.APPROVED)
    balances = [(await svc.get_driver(i)).balance for i in ids]
    assert balances == [30000, 30000, 0]  # faqat birinchi 2 tasiga
    # Bloklab, qayta faollashtirilsa yoki qayta tasdiqlansa — bonus ikkinchi marta berilmaydi
    await svc.set_driver_status(ids[0], DriverStatus.BLOCKED)
    await svc.set_driver_status(ids[0], DriverStatus.APPROVED)
    assert (await svc.get_driver(ids[0])).balance == 30000
    assert any("30 000" in m.view.text for m in fake.to(Role.DRIVER, 7101))
