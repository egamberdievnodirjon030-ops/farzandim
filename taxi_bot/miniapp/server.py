"""Telegram Mini App serveri (yo'lovchi va haydovchi ilovasi).

Har bir so'rov `Authorization: tma <initData>` sarlavhasi bilan keladi va bot tokeni bilan
HMAC orqali tekshiriladi — foydalanuvchini soxtalashtirib bo'lmaydi.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from aiogram.utils.web_app import check_webapp_signature, safe_parse_webapp_init_data
from aiohttp import web

from ..services.geo import Point
from ..services.taxi import TaxiService
from ..ui.messenger import Role

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
LEAFLET = Path(__file__).parent.parent / "web" / "static" / "leaflet"
NAVIGATORS = {"google", "yandex", "waze"}

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
TG_ID = web.RequestKey("tg_id", int)
FIRST_NAME = web.RequestKey("first_name", str)
APP = web.RequestKey("app", Role)
BOT_ROLE = web.RequestKey("bot_role", object)  # Role | None: ikki bot rejimida bot rolni o'zi belgilaydi


class MiniAppServer:
    def __init__(
        self, svc: TaxiService, tokens: list[tuple[str, Role | None]], port: int = 8081, host: str = "127.0.0.1"
    ) -> None:
        """`tokens`: [(bot_token, rol)] — ikki bot rejimida rol botdan, bitta botda None."""
        self.svc = svc
        self.tokens = tokens
        self.port = port
        self.host = host
        self.max_age = svc.settings.webapp_auth_max_age_h * 3600
        self._runner: web.AppRunner | None = None
        tile_host = urlparse(svc.settings.tile_url.replace("{s}", "a")).netloc
        tile_src = f"https://{tile_host}" if tile_host else ""
        if "{s}" in svc.settings.tile_url:
            tile_src += " " + f"https://*.{tile_host.split('.', 1)[-1]}"
        # Marshrut serverlari: server ularga yeta olmasa, ilova telefon interneti orqali to'g'ridan-to'g'ri so'raydi
        routers = " ".join(
            sorted({f"https://{urlparse(u).netloc}" for u in svc.settings.route_urls if u.startswith("https://")})
        )
        self.csp = (
            "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; "
            f"img-src 'self' data: {tile_src}; connect-src 'self' {routers}; base-uri 'none'; "
            "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"
        )

    # ------------------------------------------------------------------ autentifikatsiya
    def authenticate(self, init_data: str) -> tuple[int, str, Role | None] | None:
        for token, role in self.tokens:
            try:
                data = safe_parse_webapp_init_data(token, init_data)
            except ValueError:
                continue
            if data.user is None:
                return None
            if self.max_age and time.time() - data.auth_date.timestamp() > self.max_age:
                return None
            return data.user.id, data.user.first_name or "", role
        return None

    def contact_from_signed(self, response: str) -> str | None:
        """WebApp.requestContact() javobi — imzolangan bo'lsa telefon raqamini qaytaradi."""
        import json

        for token, _ in self.tokens:
            if check_webapp_signature(token, response):
                fields = dict(parse_qsl(response))
                try:
                    contact = json.loads(fields.get("contact", "{}"))
                except ValueError:
                    return None
                return contact.get("phone_number")
        return None

    @web.middleware
    async def _middleware(self, request: web.Request, handler: Handler) -> web.StreamResponse:
        if request.path.startswith("/api/"):
            auth = request.headers.get("Authorization", "")
            user = self.authenticate(auth[4:]) if auth.startswith("tma ") else None
            if user is None:
                return web.json_response({"error": "Telegram orqali oching"}, status=401)
            tg_id, first_name, bot_role = user
            app = request.headers.get("X-App")
            if app in ("driver", "passenger"):
                app_role = Role.DRIVER if app == "driver" else Role.PASSENGER
                if bot_role is not None and bot_role != app_role:
                    return web.json_response({"error": "Noto'g'ri bot"}, status=403)
            else:  # ilova hali rolni bilmaydi (masalan /api/role)
                app_role = bot_role or Role.PASSENGER
            request[TG_ID], request[FIRST_NAME], request[APP] = tg_id, first_name, app_role
            request[BOT_ROLE] = bot_role
        try:
            response = await handler(request)
        except ValueError as exc:
            return web.json_response({"error": str(exc) or "Noto'g'ri so'rov"}, status=400)
        response.headers.setdefault("Content-Security-Policy", self.csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.path.startswith("/api/") or request.path == "/":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # ------------------------------------------------------------------ yordamchilar
    @staticmethod
    async def body(request: web.Request) -> dict:
        try:
            data = await request.json()
        except ValueError as exc:
            raise ValueError("JSON kutilgan") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON obyekt kutilgan")
        return data

    @staticmethod
    def ok(**data) -> web.Response:
        return web.json_response({"ok": True, **data})

    @staticmethod
    def fail(message: str, status: int = 409) -> web.Response:
        return web.json_response({"ok": False, "error": message}, status=status)

    def need(self, request: web.Request, role: Role) -> None:
        if request[APP] != role:
            raise web.HTTPForbidden()

    # ------------------------------------------------------------------ umumiy
    async def index(self, request: web.Request) -> web.Response:
        return web.FileResponse(STATIC / "index.html")

    async def role(self, request: web.Request) -> web.Response:
        """Ilova qaysi rejimda ochilishi kerak: bot roli (ikki bot) yoki foydalanuvchi tanlagan rol (bitta bot)."""
        role = request[BOT_ROLE] or await self.svc.get_user_role(request[TG_ID])
        return web.json_response({"role": role.value if role else None, "single_bot": self.svc.settings.single_bot})

    async def me(self, request: web.Request) -> web.Response:
        tg_id, role = request[TG_ID], request[APP]
        if self.svc.settings.single_bot:
            current = await self.svc.get_user_role(tg_id)
            if current != role:
                if current == Role.DRIVER and await self.svc.driver_busy(tg_id):
                    return self.fail("Avval joriy safarni yakunlang — so'ng yo'lovchi rejimiga o'tasiz")
                await self.svc.set_user_role(tg_id, role)
        if role == Role.PASSENGER:
            await self.svc.ensure_passenger(tg_id, request[FIRST_NAME])
        return web.json_response({
            "config": self.svc.app_config(), "role": role.value, "first_name": request[FIRST_NAME],
            "live": await self.svc.live_share(tg_id),
        })

    async def live(self, request: web.Request) -> web.Response:
        """«📡 Jonli joylashuv» — yoqilgan bo'lsa, ilova ochilishi bilan avtomatik ishlaydi, o'zi o'chirmaguncha."""
        b = await self.body(request)
        on = bool(b.get("on"))
        await self.svc.set_live_share(request[TG_ID], on)
        return self.ok(live=on)

    async def geocode(self, request: web.Request) -> web.Response:
        q = request.query.get("q", "")[:120]
        near = None
        if "lat" in request.query and "lon" in request.query:
            near = (float(request.query["lat"]), float(request.query["lon"]))
        return web.json_response(await self.svc.geocoder.search(q, near))

    async def reverse(self, request: web.Request) -> web.Response:
        lat, lon = float(request.query["lat"]), float(request.query["lon"])
        return web.json_response(await self.svc.geocoder.reverse(lat, lon) or {})

    async def route(self, request: web.Request) -> web.Response:
        b = await self.body(request)
        (alat, alon), (blat, blon) = b["a"], b["b"]
        est, geometry = await self.svc.routing.route_geometry(Point(alat, alon), Point(blat, blon))
        return web.json_response(
            {"distance_m": est.distance_m, "duration_s": est.duration_s, "route": geometry, "precise": est.precise}
        )

    async def contact(self, request: web.Request) -> web.Response:
        b = await self.body(request)
        phone = self.contact_from_signed(str(b.get("response", "")))
        if not phone:
            return self.fail("Raqam tasdiqlanmadi", 400)
        await self.svc.save_verified_phone(request[TG_ID], phone)
        if request[APP] == Role.PASSENGER:
            await self.svc.ensure_passenger(request[TG_ID], request[FIRST_NAME])
            await self.svc.set_passenger_phone(request[TG_ID], phone)
        return self.ok()

    # ------------------------------------------------------------------ yo'lovchi
    async def p_state(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        return web.json_response(await self.svc.passenger_state(request[TG_ID]))

    async def p_nearby(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        lat, lon = float(request.query["lat"]), float(request.query["lon"])
        return web.json_response(await self.svc.nearby_cars(lat, lon))

    async def p_quote(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        b = await self.body(request)
        pickup = b["pickup"]
        return web.json_response(
            await self.svc.app_quote(float(pickup["lat"]), float(pickup["lon"]), pickup.get("accuracy"), b.get("dest"))
        )

    async def p_order(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        order, error = await self.svc.app_create_order(request[TG_ID], await self.body(request))
        return self.ok(order_id=order.id) if order else self.fail(error)

    async def p_action(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        tg, b = request[TG_ID], await self.body(request)
        oid, action = int(b.get("order_id", 0)), request.match_info["action"]
        svc = self.svc
        if action == "cancel":
            result = await svc.passenger_cancel(tg, oid, confirmed=bool(b.get("confirmed")))
            return self.ok(result=result) if result in ("cancelled", "confirm") else self.fail(
                "Safar boshlangan — manzilga yetgach tasdiqlang" if result == "too_late" else "Buyurtma topilmadi"
            )
        if action == "arrived":
            return self.ok() if await svc.passenger_confirm_arrival(tg, oid) else self.fail("Buyurtma yakunlangan")
        if action == "notyet":
            result = await svc.passenger_not_yet(tg, oid)
            return self.ok() if result == "ok" else self.fail(
                "Haydovchi boshqa buyurtmaga o'tgan" if result == "driver_busy" else "Buyurtma topilmadi"
            )
        if action == "rate":
            return self.ok() if await svc.rate(tg, oid, int(b.get("stars", 5))) else self.fail("Baho qo'yilgan")
        if action == "favorite":
            return self.ok() if await svc.add_favorite(tg, oid) else self.fail("Topilmadi")
        if action == "retry":
            return self.ok() if await svc.retry_search(tg, oid) else self.fail("Buyurtma eskirgan")
        if action == "call":
            return self.ok(message=await svc.request_call(tg, oid, Role.PASSENGER))
        raise web.HTTPNotFound()

    async def p_place_save(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        b = await self.body(request)
        place = await self.svc.save_place(
            request[TG_ID], str(b.get("kind", "other")), float(b["lat"]), float(b["lon"]), b.get("title")
        )
        return self.ok(id=place.id) if place else self.fail("Saqlab bo'lmadi (ko'pi bilan 5 ta qo'shimcha manzil)")

    async def p_place_delete(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        ok = await self.svc.delete_place(request[TG_ID], int(request.match_info["id"]))
        return self.ok() if ok else self.fail("Topilmadi", 404)

    # ------------------------------------------------------------------ haydovchi
    async def d_state(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        return web.json_response(await self.svc.driver_state(request[TG_ID]))

    async def d_register(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        driver, error = await self.svc.app_register_driver(request[TG_ID], await self.body(request))
        return self.ok(status=driver.status) if driver else self.fail(error, 400)

    async def d_online(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        tg, b = request[TG_ID], await self.body(request)
        if not b.get("online"):
            await self.svc.driver_offline(tg)
            return self.ok(online=False)
        if "lat" in b and "lon" in b:
            await self.svc.app_driver_location(tg, float(b["lat"]), float(b["lon"]), b.get("accuracy"), b.get("heading"))
        result = await self.svc.driver_go_online(tg)
        messages = {
            "need_location": "Joylashuv aniqlanmadi — joylashuvga ruxsat bering",
            "low_balance": "Balansingiz yetarli emas — to'ldiring",
            "not_approved": "Arizangiz hali tasdiqlanmagan",
            "not_driver": "Avval ro'yxatdan o'ting",
        }
        return self.ok(online=True) if result == "online" else self.fail(messages.get(result, result))

    async def p_location(self, request: web.Request) -> web.Response:
        self.need(request, Role.PASSENGER)
        b = await self.body(request)
        acc = b.get("accuracy")
        shared = await self.svc.passenger_live_location(
            request[TG_ID], float(b["lat"]), float(b["lon"]), float(acc) if isinstance(acc, int | float) else None
        )
        return self.ok(shared=shared)

    async def d_location(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        b = await self.body(request)
        result = await self.svc.app_driver_location(
            request[TG_ID], float(b["lat"]), float(b["lon"]), b.get("accuracy"), b.get("heading")
        )
        return self.ok(ignored=getattr(result, "ignored", None))

    async def d_offer(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        tg, oid, action = request[TG_ID], int(request.match_info["id"]), request.match_info["action"]
        if action == "decline":
            await self.svc.decline_offer(tg, oid)
            return self.ok()
        if action != "accept":
            raise web.HTTPNotFound()
        result = await self.svc.accept_offer(tg, oid)
        messages = {
            "taken": "Buyurtma allaqachon boshqa haydovchiga o'tdi",
            "busy": "Sizda faol buyurtma bor",
            "low_balance": "Balansingiz yetarli emas",
            "not_driver": "Hisobingiz faol emas",
        }
        return self.ok() if result.ok else self.fail(messages.get(result.reason, "Qabul qilib bo'lmadi"))

    async def d_order(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        tg, oid, action = request[TG_ID], int(request.match_info["id"]), request.match_info["action"]
        svc = self.svc
        simple = {"arrived": svc.driver_arrived, "start": svc.driver_start, "finish": svc.driver_finish}
        if action in simple:
            return self.ok() if await simple[action](tg, oid) else self.fail("Holat o'zgargan")
        if action in ("cancel", "noshow"):
            result = await svc.driver_cancel(tg, oid, no_show=action == "noshow")
            if result == "too_early":
                return self.fail(f"Yo'lovchini kamida {svc.settings.no_show_wait_min:g} daqiqa kuting")
            return self.ok() if result == "ok" else self.fail("Holat o'zgargan")
        if action == "call":
            return self.ok(message=await svc.request_call(tg, oid, Role.DRIVER))
        raise web.HTTPNotFound()

    async def d_settings(self, request: web.Request) -> web.Response:
        self.need(request, Role.DRIVER)
        tg, b = request[TG_ID], await self.body(request)
        if b.get("navigator") in NAVIGATORS:
            await self.svc.set_navigator(tg, b["navigator"])
        if "home" in b and isinstance(b["home"], dict):
            await self.svc.set_home(tg, float(b["home"]["lat"]), float(b["home"]["lon"]))
        if "home_mode" in b:
            d = await self.svc.get_driver_by_tg(tg)
            if d and bool(b["home_mode"]) != d.home_mode:
                await self.svc.toggle_home_mode(tg)
        return self.ok()

    # ------------------------------------------------------------------ ilova
    def build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._middleware], client_max_size=64 * 1024)
        app.add_routes(
            [
                web.get("/", self.index),
                web.get("/api/me", self.me),
                web.get("/api/role", self.role),
                web.get("/api/geocode", self.geocode),
                web.get("/api/reverse", self.reverse),
                web.post("/api/route", self.route),
                web.post("/api/contact", self.contact),
                web.post("/api/live", self.live),
                web.get("/api/p/state", self.p_state),
                web.get("/api/p/nearby", self.p_nearby),
                web.post("/api/p/quote", self.p_quote),
                web.post("/api/p/order", self.p_order),
                web.post("/api/p/places", self.p_place_save),
                web.post(r"/api/p/places/{id:\d+}/delete", self.p_place_delete),
                web.post("/api/p/location", self.p_location),
                web.post("/api/p/{action}", self.p_action),
                web.get("/api/d/state", self.d_state),
                web.post("/api/d/register", self.d_register),
                web.post("/api/d/online", self.d_online),
                web.post("/api/d/location", self.d_location),
                web.post("/api/d/settings", self.d_settings),
                web.post(r"/api/d/offers/{id:\d+}/{action}", self.d_offer),
                web.post(r"/api/d/orders/{id:\d+}/{action}", self.d_order),
                web.static("/static/leaflet", LEAFLET),
                web.static("/static", STATIC),
            ]
        )
        return app

    async def start(self) -> None:
        self._runner = web.AppRunner(self.build_app(), access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, self.host, self.port).start()

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

