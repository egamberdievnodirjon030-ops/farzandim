"""Telegram Mini App API: initData tekshiruvi, rollar, to'liq buyurtma oqimi, maxfiylik."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from aiohttp.test_utils import TestClient, TestServer

from taxi_bot.db.models import Driver, DriverStatus, OrderStatus
from taxi_bot.miniapp.server import MiniAppServer
from taxi_bot.ui.messenger import Role

from .conftest import offset
from .test_flow import add_driver, wait_for

P_TOKEN = "1111111:" + "P" * 35
D_TOKEN = "2222222:" + "D" * 35
PASSENGER, DRIVER = 8001, 8002


def signed(token: str, fields: dict) -> str:
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    return urlencode({**fields, "hash": hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()})


def init_data(token: str, user_id: int, name: str = "Test", age: int = 0) -> str:
    user = json.dumps({"id": user_id, "first_name": name}, separators=(",", ":"))
    return signed(token, {"auth_date": str(int(time.time()) - age), "query_id": "AAH", "user": user})


class AppClient:
    def __init__(self, client: TestClient, token: str, user_id: int, app: str | None, name: str = "Test"):
        self.client, self.headers = client, {"Authorization": f"tma {init_data(token, user_id, name)}"}
        if app:
            self.headers["X-App"] = app

    async def get(self, path: str, status: int = 200):
        resp = await self.client.get(path, headers=self.headers)
        assert resp.status == status, (path, resp.status, await resp.text())
        return await resp.json()

    async def post(self, path: str, body: dict | None = None, status: int = 200):
        resp = await self.client.post(path, headers=self.headers, json=body or {})
        assert resp.status == status, (path, resp.status, await resp.text())
        return await resp.json()


class FakeGeocoder:
    async def search(self, q, near=None):
        return [{"title": f"{q} ko'chasi", "subtitle": "Markaz", "lat": 41.0, "lon": 71.6}]

    async def reverse(self, lat, lon):
        return {"title": "Navoiy ko'chasi 12", "subtitle": "Markaz", "lat": lat, "lon": lon}

    async def close(self):
        pass


async def start(svc, tokens) -> TestClient:
    svc.geocoder = FakeGeocoder()
    client = TestClient(TestServer(MiniAppServer(svc, tokens).build_app()))
    await client.start_server()
    return client


TWO_BOTS = [(P_TOKEN, Role.PASSENGER), (D_TOKEN, Role.DRIVER)]


async def test_init_data_is_verified(make_service):
    svc, _ = await make_service()
    client = await start(svc, TWO_BOTS)
    try:
        assert (await client.get("/api/me")).status == 401
        forged = init_data(P_TOKEN, PASSENGER).replace("query_id=AAH", "query_id=XXX")
        assert (await client.get("/api/me", headers={"Authorization": f"tma {forged}"})).status == 401
        other_bot = init_data("3333333:" + "X" * 35, PASSENGER)
        assert (await client.get("/api/me", headers={"Authorization": f"tma {other_bot}"})).status == 401
        old = init_data(P_TOKEN, PASSENGER, age=3 * 24 * 3600)
        assert (await client.get("/api/me", headers={"Authorization": f"tma {old}"})).status == 401
        # Yo'lovchi boti imzosi bilan haydovchi ilovasini ochib bo'lmaydi
        wrong = AppClient(client, P_TOKEN, PASSENGER, "driver")
        await wrong.get("/api/d/state", status=403)
        me = await AppClient(client, P_TOKEN, PASSENGER, "passenger", "Jasur").get("/api/me")
        assert me["role"] == "passenger" and me["config"]["currency"] == "so'm"
        page = await client.get("/")
        assert page.status == 200 and "telegram-web-app.js" in await page.text()
        assert "https://telegram.org" in page.headers["Content-Security-Policy"]
    finally:
        await client.close()


async def test_full_ride_through_the_app(make_service, center):
    svc, fake = await make_service(priority_headstart_sec=0, auto_arrive_radius_m=0)
    client = await start(svc, TWO_BOTS)
    p = AppClient(client, P_TOKEN, PASSENGER, "passenger", "Jasur")
    d = AppClient(client, D_TOKEN, DRIVER, "driver", "Bekzod")
    try:
        await p.get("/api/me")
        assert (await p.get("/api/p/state"))["registered"] is False
        # 📱 Raqamni ulashish (Telegram imzolagan javob)
        contact = json.dumps({"user_id": PASSENGER, "phone_number": "998935556677"})
        response = signed(P_TOKEN, {"contact": contact, "auth_date": str(int(time.time()))})
        await p.post("/api/contact", {"response": response})
        await p.post("/api/contact", {"response": response.replace("contact=", "contact=x")}, status=400)
        assert (await p.get("/api/p/state"))["registered"] is True

        driver = await add_driver(svc, DRIVER, *offset(*center, 400, 0), rating=4.9)
        await d.post("/api/d/location", {"lat": offset(*center, 400, 0)[0], "lon": center[1], "accuracy": 6})

        # 🗺 Manzil qidirish, narx va marshrut
        assert (await p.get("/api/geocode?q=Navoiy"))[0]["title"] == "Navoiy ko'chasi"
        assert (await p.get(f"/api/reverse?lat={center[0]}&lon={center[1]}"))["title"] == "Navoiy ko'chasi 12"
        dest = offset(*center, 3000, 1000)
        quote = await p.post("/api/p/quote", {"pickup": {"lat": center[0], "lon": center[1]},
                                              "dest": {"lat": dest[0], "lon": dest[1], "title": "Bozor"}})
        assert quote["price"] > 7000 and len(quote["route"]) >= 2 and quote["nearby"] == 1
        cars = await p.get(f"/api/p/nearby?lat={center[0]}&lon={center[1]}")
        assert len(cars) == 1 and set(cars[0]) == {"lat", "lon", "heading"}  # shaxsiy ma'lumotsiz

        res = await p.post("/api/p/order", {"pickup": {"lat": center[0], "lon": center[1], "accuracy": 8},
                                            "dest": {"lat": dest[0], "lon": dest[1], "title": "Bozor"},
                                            "comment": "Oq darvoza, tel 90 123 45 67"})
        order_id = res["order_id"]
        await p.post("/api/p/order", {"pickup": {"lat": center[0], "lon": center[1]}}, status=409)  # 2-buyurtma yo'q
        state = await p.get("/api/p/state")
        assert state["order"]["status"] == "searching" and state["order"]["search"]["radius_m"] == 1000

        # 🚖 Haydovchi ilovasida taklif (aniq joy ko'rinmaydi)
        async def has_offer():
            return bool((await d.get("/api/d/state"))["offers"])
        assert await wait_for(has_offer)
        offer = (await d.get("/api/d/state"))["offers"][0]
        assert offer["order_id"] == order_id and offer["price"] == quote["price"]
        assert offer["approx"] != [center[0], center[1]] and "123 45 67" not in json.dumps(offer)
        await d.post(f"/api/d/offers/{order_id}/accept")
        ds = await d.get("/api/d/state")
        assert ds["order"]["status"] == "accepted" and ds["order"]["pickup"]["lat"] == center[0]

        # Yo'lovchi xaritada mashinani ko'radi
        await d.post("/api/d/location", {"lat": offset(*center, 200, 0)[0], "lon": center[1], "accuracy": 5, "heading": 180})
        ps = (await p.get("/api/p/state"))["order"]
        assert ps["status"] == "accepted" and ps["driver"]["plate"] == f"01A{DRIVER}" and ps["eta_s"] > 0
        assert ps["driver"]["lat"] == offset(*center, 200, 0)[0] and ps["driver"]["heading"] == 180

        await d.post(f"/api/d/orders/{order_id}/arrived")
        assert (await p.get("/api/p/state"))["order"]["free_wait_left_s"] > 0
        await d.post(f"/api/d/orders/{order_id}/start")
        taximeter = (await d.get("/api/d/state"))["order"]["taximeter"]
        assert taximeter is not None and taximeter["price"] >= quote["price"]
        await d.post(f"/api/d/orders/{order_id}/finish")
        assert (await d.get("/api/d/state"))["order"]["status"] == "finishing"  # haydovchi bo'sh, tasdiq kutilmoqda
        assert (await p.get("/api/p/state"))["order"]["status"] == "finishing"
        await p.post("/api/p/arrived", {"order_id": order_id})
        rate = (await p.get("/api/p/state"))["rate_order"]
        assert rate["id"] == order_id and rate["status"] == "completed"
        await p.post("/api/p/favorite", {"order_id": order_id})
        await p.post("/api/p/rate", {"order_id": order_id, "stars": 5})
        assert (await p.get("/api/p/state"))["rate_order"] is None
        o = await svc.get_order(order_id)
        assert o.status == OrderStatus.COMPLETED and o.rating == 5
        assert (await svc.get_driver(driver.id)).balance == 50_000 - o.commission

        # 🔒 Maxfiylik: ilova javoblarida boshqa tomonning raqami va ismi yo'q
        all_p = json.dumps(await p.get("/api/p/state"))
        assert "+99890" not in all_p and "Haydovchi" not in all_p
        assert "998935556677" not in json.dumps(await d.get("/api/d/state")) and "Jasur" not in json.dumps(await d.get("/api/d/state"))
        assert fake.to(Role.PASSENGER, PASSENGER)  # bot orqali bildirishnomalar ham ketdi
    finally:
        await client.close()


async def test_driver_registers_from_app_and_goes_online(make_service, center):
    svc, _ = await make_service(welcome_bonus=30000)
    client = await start(svc, TWO_BOTS)
    d = AppClient(client, D_TOKEN, DRIVER, "driver", "Bekzod")
    try:
        st = await d.get("/api/d/state")
        assert st["registered"] is False and st["phone"] is False
        await d.post("/api/d/register", {"full_name": "Bekzod Karimov", "car_model": "Cobalt",
                                          "car_color": "Oq", "car_plate": "01a777bc"}, status=400)  # raqamsiz
        await svc.save_verified_phone(DRIVER, "+998901112233")  # bot orqali kelgan kontakt
        await d.post("/api/d/register", {"full_name": "Bekzod Karimov", "car_model": "Cobalt",
                                          "car_color": "Oq", "car_plate": "AB"}, status=400)
        await d.post("/api/d/register", {"full_name": "Bekzod Karimov", "car_model": "Cobalt",
                                          "car_color": "Oq", "car_plate": "01a777bc"})
        st = await d.get("/api/d/state")
        assert st["driver"]["status"] == "pending" and st["driver"]["plate"] == "01 A 777 BC"
        await svc.set_driver_status(st["driver"]["id"], DriverStatus.APPROVED)
        st = await d.get("/api/d/state")
        assert st["driver"]["balance"] == 30000  # 🎁 yangi haydovchi bonusi
        bad = await d.post("/api/d/online", {"online": True}, status=409)
        assert "Joylashuv" in bad["error"]
        await d.post("/api/d/online", {"online": True, "lat": center[0], "lon": center[1], "accuracy": 5})
        assert (await d.get("/api/d/state"))["driver"]["online"] is True
        await d.post("/api/d/settings", {"navigator": "yandex", "home": {"lat": 41.05, "lon": 71.7}, "home_mode": True})
        drv = (await d.get("/api/d/state"))["driver"]
        assert drv["navigator"] == "yandex" and drv["home_mode"] is True
        await d.post("/api/d/online", {"online": False})
        assert (await d.get("/api/d/state"))["driver"]["online"] is False
    finally:
        await client.close()


async def test_single_bot_app_sets_role(make_service):
    svc, _ = await make_service(driver_bot_token="")
    client = await start(svc, [(P_TOKEN, None)])
    try:
        await AppClient(client, P_TOKEN, 8101, "driver").get("/api/me")
        assert await svc.get_user_role(8101) == Role.DRIVER
        await AppClient(client, P_TOKEN, 8101, "passenger").get("/api/me")
        assert await svc.get_user_role(8101) == Role.PASSENGER
    finally:
        await client.close()


async def test_saved_places_from_app(make_service, center):
    svc, _ = await make_service()
    client = await start(svc, TWO_BOTS)
    p = AppClient(client, P_TOKEN, PASSENGER, "passenger")
    try:
        await p.get("/api/me")
        res = await p.post("/api/p/places", {"kind": "home", "lat": center[0], "lon": center[1]})
        places = (await p.get("/api/p/state"))["places"]
        assert places[0]["kind"] == "home" and places[0]["title"] == "Uy"
        await p.post(f"/api/p/places/{res['id']}/delete")
        assert (await p.get("/api/p/state"))["places"] == []
    finally:
        await client.close()


async def test_app_opens_in_role_chosen_in_chat(make_service):
    """Foydalanuvchi xatosi: chatda «Haydovchi» tanlansa ham ilova yo'lovchi bo'lib ochilardi."""
    svc, _ = await make_service(driver_bot_token="")
    client = await start(svc, [(P_TOKEN, None)])
    try:
        fresh = AppClient(client, P_TOKEN, 8201, None)
        assert (await fresh.get("/api/role"))["role"] is None  # hali tanlamagan — ilova so'raydi
        await svc.set_user_role(8201, Role.DRIVER)  # chatda «🚕 Haydovchi» bosildi
        assert (await fresh.get("/api/role")) == {"role": "driver", "single_bot": True}
        # ilova shu rolda ochiladi va rolni qayta yozib yubormaydi
        await AppClient(client, P_TOKEN, 8201, "driver").get("/api/me")
        assert await svc.get_user_role(8201) == Role.DRIVER
    finally:
        await client.close()


async def test_role_switch_in_app_and_busy_driver_guard(make_service, center):
    svc, _ = await make_service(driver_bot_token="")
    client = await start(svc, [(P_TOKEN, None)])
    try:
        d = await add_driver(svc, 8202, *center)
        await svc.set_user_role(8202, Role.DRIVER)
        async with svc.db.session() as s:
            (await s.get(Driver, d.id)).current_order_id = 999  # faol safar
        busy = await AppClient(client, P_TOKEN, 8202, "passenger").get("/api/me", status=409)
        assert "safarni yakunlang" in busy["error"]
        assert await svc.get_user_role(8202) == Role.DRIVER
        async with svc.db.session() as s:
            (await s.get(Driver, d.id)).current_order_id = None
        await AppClient(client, P_TOKEN, 8202, "passenger").get("/api/me")
        assert await svc.get_user_role(8202) == Role.PASSENGER
        assert (await AppClient(client, P_TOKEN, 8202, None).get("/api/role"))["role"] == "passenger"
    finally:
        await client.close()


async def test_two_bots_role_comes_from_bot(make_service):
    svc, _ = await make_service()
    client = await start(svc, TWO_BOTS)
    try:
        assert (await AppClient(client, D_TOKEN, 8203, None).get("/api/role"))["role"] == "driver"
        assert (await AppClient(client, P_TOKEN, 8203, None).get("/api/role"))["role"] == "passenger"
        await AppClient(client, D_TOKEN, 8203, "passenger").get("/api/me", status=403)  # boshqa bot roli — rad
    finally:
        await client.close()
