"""Raqobatdagi ustunliklar: sevimli haydovchi, "Uyga" rejimi, saqlangan manzillar va boshqalar."""

from __future__ import annotations

import asyncio

from taxi_bot.db.models import Driver, OrderStatus
from taxi_bot.ui.messenger import Role

from .conftest import offset
from .test_flow import (
    PASSENGER_TG,
    _has_offer,
    add_driver,
    add_passenger,
    at_destination,
    offers,
    order_now,
    wait_for,
)


async def _set(svc, driver_id, **values):
    async with svc.db.session() as s:
        d = await s.get(Driver, driver_id)
        for k, v in values.items():
            setattr(d, k, v)


async def _accepted(svc, center, tg=2001, **kw):
    d = await add_driver(svc, tg, *offset(*center, kw.pop("north", 900), 0))
    await add_passenger(svc)
    order = await order_now(svc, center, dest=kw.pop("dest", offset(*center, 3000, 0)))
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert (await svc.accept_offer(tg, order.id)).ok
    return d, await svc.get_order(order.id)


# ---------------------------------------------------------------- ❤️ sevimli haydovchi
async def test_favorite_driver_sees_order_first(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0, favorite_headstart_sec=0.4)
    near = await add_driver(svc, 3201, *offset(*center, 200, 0), rating=5.0)
    fav, order = await _accepted(svc, center, tg=3202, north=2500)
    # 1-safarni yakunlab, haydovchini sevimlilarga qo'shamiz
    assert await svc.driver_start(3202, order.id)
    await at_destination(svc, 3202, order.id)
    assert await svc.driver_finish(3202, order.id) == "ok"
    assert await svc.rate(PASSENGER_TG, order.id, 5)
    assert await svc.add_favorite(PASSENGER_TG, order.id)
    await svc.update_driver_location(3202, *offset(*center, 2500, 0), accuracy=5, is_live=True)

    second = await order_now(svc, center)
    assert await wait_for(lambda: _has_offer(svc, second.id, fav.id), timeout=1)
    rows = await offers(svc, second.id)
    assert rows[0].driver_id == fav.id and rows[0].wave == -1
    assert not await _has_offer(svc, second.id, near.id)  # yaqinroq, lekin sevimli emas — keyinroq
    assert await wait_for(lambda: _has_offer(svc, second.id, near.id), timeout=1.5)
    offer_text = [m for m in _fake(svc).to(Role.DRIVER, 3202)][-1].view.text
    assert "sevimli" in offer_text
    assert await svc.remove_favorite(PASSENGER_TG, fav.id)
    assert await svc.list_favorites((await svc.get_passenger_by_tg(PASSENGER_TG)).id) == []


def _fake(svc):
    return svc.msg


# ---------------------------------------------------------------- 🏡 "Uyga" rejimi
async def test_home_mode_only_receives_orders_towards_home(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0, search_timeout_sec=0.8)
    d = await add_driver(svc, 3301, *offset(*center, 300, 0))
    home = offset(*center, 8000, 0)  # uyi shimolda
    await svc.set_home(3301, *home)
    assert (await svc.toggle_home_mode(3301)).home_mode
    await add_passenger(svc)

    south = await order_now(svc, center, dest=offset(*center, -4000, 0))
    await asyncio.sleep(0.3)
    assert not await _has_offer(svc, south.id, d.id)
    await svc.passenger_cancel(PASSENGER_TG, south.id, confirmed=True)

    no_dest = await order_now(svc, center)
    await asyncio.sleep(0.3)
    assert not await _has_offer(svc, no_dest.id, d.id)
    await svc.passenger_cancel(PASSENGER_TG, no_dest.id, confirmed=True)

    north = await order_now(svc, center, dest=offset(*center, 6000, 0))
    assert await wait_for(lambda: _has_offer(svc, north.id, d.id), timeout=1)
    assert "Uyingiz tomonga" in fake.to(Role.DRIVER, 3301)[-1].view.text


# ---------------------------------------------------------------- 📍 yaqinlashish va avto "yetib keldim"
async def test_near_alert_once_and_auto_arrival(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    _d, order = await _accepted(svc, center, tg=3401, north=1500)
    assert not order.near_notified
    await svc.update_driver_location(3401, *offset(*center, 300, 0), accuracy=5, is_live=True)
    await svc.update_driver_location(3401, *offset(*center, 250, 0), accuracy=5, is_live=True)
    alerts = [m for m in fake.to(Role.PASSENGER, PASSENGER_TG) if "yaqinlashmoqda" in m.view.text]
    assert len(alerts) == 1 and "01A3401" in alerts[0].view.text
    await svc.update_driver_location(3401, *offset(*center, 40, 0), accuracy=5, is_live=True)
    o = await svc.get_order(order.id)
    assert o.status == OrderStatus.ARRIVED
    assert "yetib keldi" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text
    assert any("avtomatik" in m.view.text for m in fake.to(Role.DRIVER, 3401))


async def test_inaccurate_gps_does_not_auto_arrive(make_service, center):
    svc, _ = await make_service(priority_headstart_sec=0)
    _, order = await _accepted(svc, center, tg=3501, north=1500)
    await svc.update_driver_location(3501, *offset(*center, 30, 0), accuracy=120, is_live=True)
    assert (await svc.get_order(order.id)).status == OrderStatus.ACCEPTED


# ---------------------------------------------------------------- 🏠 saqlangan manzillar
async def test_saved_places_show_in_destination_prompt(make_service, center):
    svc, _ = await make_service()
    await add_passenger(svc)
    home = await svc.save_place(PASSENGER_TG, "home", *offset(*center, 3000, 0))
    work = await svc.save_place(PASSENGER_TG, "work", *offset(*center, -2000, 0))
    home2 = await svc.save_place(PASSENGER_TG, "home", *offset(*center, 3500, 0))  # Uy almashtiriladi
    for _ in range(5):
        assert await svc.save_place(PASSENGER_TG, "other", *offset(*center, 1000, 1000), "Bozor")
    assert await svc.save_place(PASSENGER_TG, "other", *center) is None  # chegara
    p = await svc.get_passenger_by_tg(PASSENGER_TG)
    places = await svc.list_places(p.id)
    assert [x.kind for x in places][:2] == ["home", "work"] and len(places) == 7
    assert home.id not in {x.id for x in places} and home2.id in {x.id for x in places}
    view = svc.views.destination_prompt(10, center, places, [])
    data = [b.callback_data for row in view.markup.inline_keyboard for b in row]
    assert f"p:place:{home2.id}:0" in data and f"p:place:{work.id}:0" in data
    assert "p:nodest:0:0" in data
    assert await svc.delete_place(PASSENGER_TG, work.id)
    assert not await svc.delete_place(424242, home2.id)  # begona yo'lovchi o'chira olmaydi


# ---------------------------------------------------------------- 👤 boshqa odam uchun
async def test_order_for_someone_else_routes_calls_to_rider(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 3801, *offset(*center, 300, 0))
    await add_passenger(svc)
    q = await svc.build_quote(*center, 10, *offset(*center, 2000, 0), None, None)
    q.rider_phone = "+998901117788"
    order = await svc.create_order(PASSENGER_TG, q)
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    assert "Boshqa odam" in fake.to(Role.DRIVER, 3801)[-1].view.text
    assert (await svc.accept_offer(3801, order.id)).ok
    await svc.request_call(3801, order.id, Role.DRIVER)
    alert = fake.admin[-1].text
    assert "+998901117788" in alert and "buyurtmachi" in alert
    driver_texts = " ".join(m.view.text for m in fake.to(Role.DRIVER, 3801))
    assert "+998901117788" not in driver_texts


async def test_offer_shows_trip_direction_and_no_penalty(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 3901, *offset(*center, 300, 0))
    await add_passenger(svc)
    order = await order_now(svc, center, dest=offset(*center, 3000, 3000))
    assert await wait_for(lambda: _has_offer(svc, order.id, d.id))
    text = fake.to(Role.DRIVER, 3901)[-1].view.text
    assert "shimoli-sharqqa" in text and "jarima yo'q" in text


async def test_migration_adds_new_columns_to_old_database(tmp_path):
    import sqlite3

    from taxi_bot.db import Database

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE drivers (id INTEGER PRIMARY KEY, tg_id BIGINT, full_name VARCHAR(128))")
    con.execute("INSERT INTO drivers VALUES (1, 5, 'Ali')")
    con.commit()
    con.close()
    db = Database(f"sqlite+aiosqlite:///{path}")
    await db.create_all()
    await db.create_all()
    await db.close()
    con = sqlite3.connect(path)
    assert con.execute("SELECT full_name, home_mode, home_lat FROM drivers").fetchall() == [("Ali", 0, None)]
