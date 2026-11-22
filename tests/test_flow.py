from __future__ import annotations

import asyncio

from sqlalchemy import select

from taxi_bot.db.models import (
    Driver,
    DriverStatus,
    OfferStatus,
    Order,
    OrderOffer,
    OrderStatus,
    Transaction,
)
from taxi_bot.ui.messenger import Role

from .conftest import offset

PASSENGER_TG = 5001


async def add_driver(svc, tg_id, lat, lon, *, rating=4.7, balance=50_000, live=True):
    d = await svc.register_driver(tg_id, f"Haydovchi {tg_id}", "+998901234567", "Cobalt", "Oq", f"01A{tg_id}")
    await svc.set_driver_status(d.id, DriverStatus.APPROVED)
    async with svc.db.session() as s:
        row = await s.get(Driver, d.id)
        row.rating = rating
        row.balance = balance
    res = await svc.update_driver_location(tg_id, lat, lon, accuracy=8, is_live=live)
    assert res.went_online or balance < svc.settings.min_driver_balance, res
    return d


async def add_passenger(svc, tg_id=PASSENGER_TG):
    await svc.ensure_passenger(tg_id, "Jasur")
    await svc.set_passenger_phone(tg_id, "+998935556677")


async def order_now(svc, pickup, dest=None, comment=None):
    q = await svc.build_quote(pickup[0], pickup[1], 10, *(dest or (None, None)), None, comment)
    order = await svc.create_order(PASSENGER_TG, q)
    assert order is not None
    return order


async def offers(svc, order_id):
    async with svc.db.session() as s:
        return list(
            (await s.scalars(select(OrderOffer).where(OrderOffer.order_id == order_id).order_by(OrderOffer.id))).all()
        )


async def wait_for(predicate, timeout=4.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if await predicate():
            return True
        await asyncio.sleep(0.02)
    return False


async def test_full_ride_with_priority_and_commission(make_service, center):
    svc, fake = await make_service()
    a = await add_driver(svc, 101, *offset(*center, 500, 0), rating=4.95)  # yaqin, yuqori reyting
    b = await add_driver(svc, 102, *offset(*center, 0, 300), rating=4.5)  # eng yaqin, past reyting
    far = await add_driver(svc, 103, *offset(*center, 3000, 0), rating=5.0)  # uzoq
    await add_passenger(svc)

    order = await order_now(svc, center, dest=offset(*center, 4000, 0), comment="3-podyezd")
    assert order.est_price and order.est_price > 7000

    # 1) Avval yuqori reytingli A ko'radi, B esa ustunlik vaqtidan keyin
    assert await wait_for(lambda: _has_offer(svc, order.id, b.id))
    rows = await offers(svc, order.id)
    assert [r.driver_id for r in rows[:2]] == [a.id, b.id]
    assert all(r.driver_id != far.id for r in rows)  # 3 km — birinchi to'lqinda emas
    assert any("Yangi buyurtma" in m.view.text for m in fake.to(Role.DRIVER, 101))
    offer_text = fake.to(Role.DRIVER, 101)[-1].view.text
    assert "+998" not in offer_text and "Jasur" not in offer_text  # shaxsiy ma'lumot yo'q

    # 2) B qabul qiladi, A dagi taklif o'chiriladi
    res = await svc.accept_offer(102, order.id)
    assert res.ok
    res_a = await svc.accept_offer(101, order.id)
    assert not res_a.ok and res_a.reason == "taken"
    o = await svc.get_order(order.id)
    assert o.status == OrderStatus.ACCEPTED and o.driver_id == b.id
    assert (Role.DRIVER, 101, rows[0].message_id) in fake.deleted
    # Yo'lovchiga haydovchi topildi kartasi va jonli xarita
    found = fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view
    assert "Haydovchi topildi" in found.text and "01A102" in found.text
    assert "+998" not in found.text and "Haydovchi 102" not in found.text
    assert any(x[0] == "send" and x[2] == PASSENGER_TG for x in fake.live)
    # Haydovchi kartasi: manzil (navigatsiya) va aloqa tugmalari
    card = [v for r, c, _, v in fake.edits if r == Role.DRIVER and c == 102][-1]
    buttons = [btn for row in card.markup.inline_keyboard for btn in row]
    assert buttons[0].url and "dir_action=navigate" in buttons[0].url
    assert buttons[1].callback_data.startswith("d:call")
    assert "+998" not in card.text

    # 3) Yetib keldi -> safar -> yakunlash
    assert await svc.driver_arrived(102, order.id)
    assert await svc.driver_start(102, order.id)
    lat, lon = center
    for step in range(1, 9):
        await _age_track(svc, order.id)
        await svc.update_driver_location(102, *offset(lat, lon, step * 500, 0), accuracy=5, is_live=True)
    assert await svc.driver_finish(102, order.id)
    o = await svc.get_order(order.id)
    assert o.status == OrderStatus.FINISHING
    assert o.final_price == o.est_price  # belgilangan narx (kutish bepul)
    assert 3500 < o.trip_distance_m < 4500
    assert "Manzilga yetib keldingizmi" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text

    # 4) Faqat yo'lovchi tasdig'idan so'ng 10% yechiladi
    d_before = await svc.get_driver(b.id)
    assert d_before.balance == 50_000
    assert await svc.passenger_confirm_arrival(PASSENGER_TG, order.id)
    o = await svc.get_order(order.id)
    d_after = await svc.get_driver(b.id)
    assert o.status == OrderStatus.COMPLETED
    assert o.commission == round(o.final_price * 0.10)
    assert d_after.balance == 50_000 - o.commission
    assert d_after.current_order_id is None and d_after.trips_count == 1
    async with svc.db.session() as s:
        tx = (await s.scalars(select(Transaction).where(Transaction.driver_id == b.id))).all()
    assert len(tx) == 1 and tx[0].amount == -o.commission and tx[0].balance_after == d_after.balance
    last = fake.to(Role.PASSENGER, PASSENGER_TG)[-1]
    assert last.effect is not None and "Safar yakunlandi" in last.view.text
    # Takroriy tasdiq komissiyani ikki marta yechmaydi
    assert not await svc.passenger_confirm_arrival(PASSENGER_TG, order.id)
    assert (await svc.get_driver(b.id)).balance == d_after.balance

    # 5) Baholash reytingga ta'sir qiladi (bir marta)
    assert await svc.rate(PASSENGER_TG, order.id, 5)
    assert await svc.rate(PASSENGER_TG, order.id, 1) is None
    rated = await svc.get_driver(b.id)
    assert rated.rating_count == 1 and rated.rating > 4.5


async def _has_offer(svc, order_id, driver_id):
    return any(o.driver_id == driver_id and o.message_id for o in await offers(svc, order_id))


async def _age_track(svc, order_id, seconds=30):
    """Taksometr tezlik filtri uchun vaqtni sun'iy o'tkazish."""
    from datetime import timedelta

    async with svc.db.session() as s:
        o = await s.get(Order, order_id)
        if o.track_at:
            o.track_at = o.track_at - timedelta(seconds=seconds)


async def test_simultaneous_accept_only_one_wins(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0)
    drivers = [await add_driver(svc, 200 + i, *offset(*center, 100 * i, 50), rating=4.7) for i in range(5)]
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _all_offered(svc, order.id, len(drivers)))
    results = await asyncio.gather(*(svc.accept_offer(200 + i, order.id) for i in range(5)))
    assert sum(r.ok for r in results) == 1
    async with svc.db.session() as s:
        busy = (await s.scalars(select(Driver).where(Driver.current_order_id == order.id))).all()
    assert len(busy) == 1


async def _all_offered(svc, order_id, n):
    return len([o for o in await offers(svc, order_id) if o.message_id]) >= n


async def test_waves_expand_after_timeout_and_skip_empty_bands(make_service, center):
    svc, _ = await make_service(wave_timeout_sec=0.4)
    near = await add_driver(svc, 301, *offset(*center, 400, 0))
    far = await add_driver(svc, 302, *offset(*center, 3000, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)

    assert await wait_for(lambda: _has_offer(svc, order.id, near.id), timeout=1)
    await asyncio.sleep(0.2)
    assert not await _has_offer(svc, order.id, far.id)  # 1 daqiqa (bu yerda 0.4 s) hali o'tmadi
    # 1-to'lqin javobsiz -> 2 km diapazon bo'sh (kutmasdan o'tiladi) -> 3.5 km da uzoq haydovchi
    assert await wait_for(lambda: _has_offer(svc, order.id, far.id), timeout=1.5)
    rows = await offers(svc, order.id)
    assert {r.driver_id: r.wave for r in rows} == {near.id: 0, far.id: 2}
    # Oldingi haydovchi ham ko'rishda davom etadi va qabul qila oladi
    assert (await svc.accept_offer(301, order.id)).ok


async def test_decline_moves_to_next_wave_early(make_service, center):
    svc, _ = await make_service(wave_timeout_sec=30)
    near = await add_driver(svc, 401, *offset(*center, 300, 0))
    mid = await add_driver(svc, 402, *offset(*center, 1500, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, near.id), timeout=1)
    await svc.decline_offer(401, order.id)
    assert await wait_for(lambda: _has_offer(svc, order.id, mid.id), timeout=1)


async def test_busy_low_balance_stale_and_unapproved_drivers_are_skipped(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0, search_timeout_sec=1.0)
    ok = await add_driver(svc, 501, *offset(*center, 200, 0))
    poor = await add_driver(svc, 502, *offset(*center, 210, 0))
    stale = await add_driver(svc, 503, *offset(*center, 220, 0))
    pending = await svc.register_driver(504, "Yangi", "+998900000000", "Spark", "Qora", "01B504")
    from datetime import timedelta

    from taxi_bot.db.models import utcnow

    async with svc.db.session() as s:
        (await s.get(Driver, poor.id)).balance = 0
        (await s.get(Driver, stale.id)).loc_valid_until = utcnow() - timedelta(minutes=1)
        p = await s.get(Driver, pending.id)
        p.is_online, p.lat, p.lon, p.loc_valid_until = True, center[0], center[1], utcnow() + timedelta(hours=1)
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, ok.id))
    await asyncio.sleep(0.3)
    assert {o.driver_id for o in await offers(svc, order.id)} == {ok.id}


async def test_no_drivers_then_retry(make_service, center):
    svc, fake = await make_service(search_timeout_sec=0.5)
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _status(svc, order.id, OrderStatus.NO_DRIVERS), timeout=3)
    await svc.dispatch.wait_idle(order.id)
    assert "topilmadi" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text
    late = await add_driver(svc, 601, *offset(*center, 100, 100))
    assert await svc.retry_search(PASSENGER_TG, order.id)
    assert await wait_for(lambda: _has_offer(svc, order.id, late.id))


async def _status(svc, order_id, status):
    o = await svc.get_order(order_id)
    return o.status == status


async def test_driver_cancel_redispatches_to_others(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    first = await add_driver(svc, 701, *offset(*center, 100, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, first.id))
    assert (await svc.accept_offer(701, order.id)).ok
    second = await add_driver(svc, 702, *offset(*center, 150, 0))
    assert await svc.driver_cancel(701, order.id, no_show=False) == "ok"
    o = await svc.get_order(order.id)
    assert o.status == OrderStatus.SEARCHING and o.search_round == 2 and o.driver_id is None
    assert (await svc.get_driver(first.id)).current_order_id is None
    assert await wait_for(lambda: _has_offer(svc, order.id, second.id))
    rows = await offers(svc, order.id)
    assert [r.status for r in rows if r.driver_id == first.id] == [OfferStatus.DRIVER_CANCELLED]
    assert "bekor qildi" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text


async def test_passenger_cancel_frees_driver(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 801, *offset(*center, 100, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert (await svc.accept_offer(801, order.id)).ok
    assert await svc.passenger_cancel(PASSENGER_TG, order.id, confirmed=False) == "confirm"
    assert await svc.passenger_cancel(PASSENGER_TG, order.id, confirmed=True) == "cancelled"
    assert (await svc.get_driver(d.id)).current_order_id is None
    assert any("bekor qildi" in m.view.text for m in fake.to(Role.DRIVER, 801))
    # Yangi buyurtma berish mumkin
    assert await svc.create_order(PASSENGER_TG, await svc.build_quote(*center, 5)) is not None


async def test_taximeter_without_destination_and_waiting(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0)
    await add_driver(svc, 901, *center)
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _all_offered(svc, order.id, 1))
    assert (await svc.accept_offer(901, order.id)).ok
    assert await svc.driver_arrived(901, order.id)
    from datetime import timedelta

    async with svc.db.session() as s:  # yo'lovchi 6 daqiqa kechikdi
        o = await s.get(Order, order.id)
        o.arrived_at = o.arrived_at - timedelta(minutes=6)
    assert await svc.driver_start(901, order.id)
    for step in range(1, 13):  # ~6 km
        await _age_track(svc, order.id)
        await svc.update_driver_location(901, *offset(*center, step * 500, 0), accuracy=5, is_live=True)
    # GPS sakrashi (shahar tashqarisiga) hisoblanmaydi
    await svc.update_driver_location(901, *offset(*center, 80_000, 0), accuracy=5, is_live=True)
    await svc.update_driver_location(901, *offset(*center, 6000, 0), accuracy=5, is_live=True)
    assert await svc.driver_finish(901, order.id)
    o = await svc.get_order(order.id)
    assert 5800 < o.trip_distance_m < 6300
    expected_ride = svc.tariff.ride_price(o.trip_distance_m)
    assert o.wait_charge == 3 * 500  # 6 daq - 3 bepul
    assert o.final_price == expected_ride + o.wait_charge


async def test_auto_complete_when_passenger_silent(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0, finish_confirm_timeout_min=0.001)
    d = await add_driver(svc, 1001, *center)
    await add_passenger(svc)
    order = await order_now(svc, center, dest=offset(*center, 2000, 0))
    assert await wait_for(lambda: _all_offered(svc, order.id, 1))
    assert (await svc.accept_offer(1001, order.id)).ok
    assert await svc.driver_start(1001, order.id)
    assert await svc.driver_finish(1001, order.id)
    await asyncio.sleep(0.1)
    await svc.maintenance_tick()
    o = await svc.get_order(order.id)
    assert o.status == OrderStatus.COMPLETED and o.auto_completed
    assert (await svc.get_driver(d.id)).balance == 50_000 - o.commission


async def test_require_live_location_rejects_static_points(make_service, center):
    svc, _ = await make_service(require_live_location=True)
    d = await svc.register_driver(1101, "Ali", "+998901111111", "Nexia", "Oq", "01C1101")
    await svc.set_driver_status(d.id, DriverStatus.APPROVED)
    async with svc.db.session() as s:
        (await s.get(Driver, d.id)).balance = 10_000
    res = await svc.update_driver_location(1101, *center, is_live=False)
    assert res.ignored == "need_live"
    res = await svc.update_driver_location(1101, *center, is_live=True)
    assert res.went_online


async def test_call_masking_operator_mode_hides_numbers(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0, company_phone="+998712000000")
    await add_driver(svc, 1201, *center)
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _all_offered(svc, order.id, 1))
    assert (await svc.accept_offer(1201, order.id)).ok
    reply = await svc.request_call(1201, order.id, Role.DRIVER)
    assert "Operator" in reply and "+998935556677" not in reply
    assert "+998935556677" in fake.admin[-1].text  # raqamlarni faqat dispetcher ko'radi
    assert "kuting" in await svc.request_call(1201, order.id, Role.DRIVER)  # cooldown
    assert "topilmadi" in await svc.request_call(9999, order.id, Role.DRIVER)


async def test_relay_chat_is_anonymous(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    await add_driver(svc, 1301, *center)
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _all_offered(svc, order.id, 1))
    assert (await svc.accept_offer(1301, order.id)).ok
    assert await svc.relay_text(Role.PASSENGER, PASSENGER_TG, "Oq darvoza oldidaman")
    msg = fake.to(Role.DRIVER, 1301)[-1].view.text
    assert "Oq darvoza oldidaman" in msg and "+998" not in msg and "Yo'lovchi</b>" in msg
    assert await svc.relay_text(Role.DRIVER, 1301, "2 daqiqada boraman")
    assert "2 daqiqada" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text


async def test_topup_is_idempotent(make_service, center):
    svc, _ = await make_service()
    d = await add_driver(svc, 1401, *center, balance=0)
    await svc.adjust_balance(d.id, 50_000, "payment", external_id="tg-charge-1")
    await svc.adjust_balance(d.id, 50_000, "payment", external_id="tg-charge-1")
    assert (await svc.get_driver(d.id)).balance == 50_000


async def test_driver_freed_during_wave_gets_offer_without_waiting(make_service, center):
    svc, _ = await make_service(wave_timeout_sec=30, rescan_interval_sec=0.2, priority_headstart_sec=0)
    first = await add_driver(svc, 1501, *offset(*center, 300, 0))
    await add_passenger(svc)
    order = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, order.id, first.id), timeout=1)
    newcomer = await add_driver(svc, 1502, *offset(*center, 200, 0))  # 1-to'lqin davomida bo'shadi
    assert await wait_for(lambda: _has_offer(svc, order.id, newcomer.id), timeout=1)
