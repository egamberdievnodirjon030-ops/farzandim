"""Admin web-panel: kirish, xavfsizlik va amallar."""

from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from taxi_bot.db.models import DriverStatus, OrderStatus
from taxi_bot.ui.messenger import Role
from taxi_bot.web.server import AdminPanel, resolve_password

from .conftest import offset
from .test_flow import PASSENGER_TG, _has_offer, add_driver, add_passenger, order_now, wait_for

PASSWORD = "maxfiy-parol"
H = {"X-Panel": "1"}


async def panel_client(svc) -> TestClient:
    client = TestClient(TestServer(AdminPanel(svc, PASSWORD).build_app()))
    await client.start_server()
    return client


async def login(client: TestClient) -> None:
    resp = await client.post("/login", data={"password": PASSWORD}, allow_redirects=False)
    assert resp.status == 302 and resp.headers["Location"] == "/"


async def test_requires_login_and_csrf_header(make_service):
    svc, _ = await make_service()
    client = await panel_client(svc)
    try:
        assert (await client.get("/api/summary")).status == 401
        resp = await client.get("/", allow_redirects=False)
        assert resp.status == 302 and resp.headers["Location"] == "/login"
        bad = await client.post("/login", data={"password": "xato"}, allow_redirects=False)
        assert bad.status == 200 and "Parol noto'g'ri" in await bad.text()
        assert (await client.get("/api/summary")).status == 401

        await login(client)
        page = await client.get("/")
        assert page.status == 200 and "Boshqaruv paneli" in await page.text()
        assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
        assert (await client.post("/api/orders/1/cancel")).status == 403  # X-Panel sarlavhasisiz
        assert (await client.get("/static/leaflet/leaflet.js")).status == 200
        await client.post("/logout", headers=H, allow_redirects=False)
        client.session.cookie_jar.clear()
        assert (await client.get("/api/summary")).status == 401
    finally:
        await client.close()


async def test_driver_actions_from_panel(make_service, center):
    svc, fake = await make_service()
    pending = await svc.register_driver(6001, "Ali Valiyev", "+998901234567", "Nexia", "Oq", "01 B 123 CD")
    client = await panel_client(svc)
    try:
        await login(client)
        drivers = await (await client.get("/api/drivers?status=pending")).json()
        assert [d["id"] for d in drivers] == [pending.id] and drivers[0]["phone"] == "+998901234567"
        summary = await (await client.get("/api/summary")).json()
        assert summary["pending_drivers"] == 1

        assert (await client.post(f"/api/drivers/{pending.id}/approve", headers=H)).status == 200
        assert (await svc.get_driver(pending.id)).status == DriverStatus.APPROVED
        assert "tasdiqlandi" in fake.to(Role.DRIVER, 6001)[-1].view.text

        resp = await client.post(f"/api/drivers/{pending.id}/topup", headers=H, json={"amount": 30000})
        assert (await resp.json())["balance"] == 30000
        assert "to'ldirildi" in fake.to(Role.DRIVER, 6001)[-1].view.text
        bad = await client.post(f"/api/drivers/{pending.id}/topup", headers=H, json={"amount": "abc"})
        assert bad.status == 400

        assert (await client.post(f"/api/drivers/{pending.id}/block", headers=H)).status == 200
        assert (await svc.get_driver(pending.id)).status == DriverStatus.BLOCKED
        assert (await client.post("/api/drivers/999/approve", headers=H)).status == 404
        tx = await (await client.get("/api/transactions")).json()
        assert tx[0]["amount"] == 30000 and tx[0]["kind"] == "topup"
    finally:
        await client.close()


async def test_cancel_stuck_order_map_and_finance(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0)
    d = await add_driver(svc, 6101, *offset(*center, 300, 0))
    await add_passenger(svc)
    client = await panel_client(svc)
    try:
        await login(client)
        # 1) Yakunlangan safar moliyada ko'rinadi
        done = await order_now(svc, center, dest=offset(*center, 3000, 0))
        assert await wait_for(lambda: _has_offer(svc, done.id, d.id))
        assert (await svc.accept_offer(6101, done.id)).ok
        assert await svc.driver_start(6101, done.id)
        assert await svc.passenger_confirm_arrival(PASSENGER_TG, done.id)
        fin = await (await client.get("/api/finance?days=7")).json()
        commission = (await svc.get_order(done.id)).commission
        assert fin["totals"]["trips"] == 1 and fin["totals"]["commission"] == commission
        assert fin["days"][0]["commission"] == commission and len(fin["days"]) == 7

        # 2) Faol buyurtma xaritada va ro'yxatda, operator bekor qiladi
        stuck = await order_now(svc, center)
        assert await wait_for(lambda: _has_offer(svc, stuck.id, d.id))
        assert (await svc.accept_offer(6101, stuck.id)).ok
        data = await (await client.get("/api/map")).json()
        assert data["drivers"][0]["state"] == "busy" and data["orders"][0]["id"] == stuck.id
        active = await (await client.get("/api/orders?scope=active")).json()
        assert [o["id"] for o in active] == [stuck.id] and active[0]["driver"]["plate"] == "01A6101"

        assert (await client.post(f"/api/orders/{stuck.id}/cancel", headers=H)).status == 200
        o = await svc.get_order(stuck.id)
        assert o.status == OrderStatus.CANCELLED and o.cancelled_by == "admin"
        assert (await svc.get_driver(d.id)).current_order_id is None
        assert "operator tomonidan" in fake.to(Role.PASSENGER, PASSENGER_TG)[-1].view.text
        assert "operator tomonidan" in fake.to(Role.DRIVER, 6101)[-1].view.text
        again = await client.post(f"/api/orders/{stuck.id}/cancel", headers=H)
        assert again.status == 409
    finally:
        await client.close()


async def test_block_passenger_stops_new_orders(make_service, center):
    svc, _ = await make_service()
    await add_passenger(svc)
    p = await svc.get_passenger_by_tg(PASSENGER_TG)
    client = await panel_client(svc)
    try:
        await login(client)
        rows = await (await client.get("/api/passengers")).json()
        assert rows[0]["phone"] == "+998935556677" and not rows[0]["blocked"]
        assert (await client.post(f"/api/passengers/{p.id}/block", headers=H)).status == 200
        assert await svc.create_order(PASSENGER_TG, await svc.build_quote(*center, 10)) is None
        assert (await client.post(f"/api/passengers/{p.id}/unblock", headers=H)).status == 200
        assert await svc.create_order(PASSENGER_TG, await svc.build_quote(*center, 10)) is not None
    finally:
        await client.close()


def test_password_is_generated_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first, created = resolve_password(None)
    second, created_again = resolve_password(None)
    assert created and not created_again and first == second and len(first) >= 10
    assert resolve_password("o'zim") == ("o'zim", False)
