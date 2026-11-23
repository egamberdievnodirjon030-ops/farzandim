"""Admin web-panel: bot bilan bitta jarayonda ishlaydi (aiohttp).

Standart holatda faqat shu kompyuterdan ochiladi: http://localhost:8080
Kirish — parol bilan (ADMIN_PANEL_PASSWORD yoki data/admin_panel_password.txt).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from html import escape
from pathlib import Path

from aiohttp import web

from ..db.models import DriverStatus
from ..services.taxi import TaxiService

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
COOKIE = "taxi_admin"
PASSWORD_FILE = Path("data") / "admin_panel_password.txt"

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)


def resolve_password(configured: str | None) -> tuple[str, bool]:
    """(parol, yangi yaratildimi). .env da bo'lmasa — faylda saqlanadigan tasodifiy parol."""
    if configured:
        return configured, False
    try:
        existing = PASSWORD_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing, False
    except OSError:
        pass
    password = secrets.token_urlsafe(9)
    try:
        PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        PASSWORD_FILE.write_text(password + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        log.warning("Panel paroli saqlanmadi: %s", exc)
    return password, True


LOGIN_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kirish — {company}</title><link rel="stylesheet" href="/static/app.css"></head>
<body class="login-body"><form class="login-card" method="post" action="/login">
<div class="login-logo">🚕</div><h1>{company}</h1><p class="muted">Boshqaruv paneli</p>
{error}<label for="pw">Parol</label>
<input id="pw" type="password" name="password" autocomplete="current-password" autofocus required>
<button type="submit" class="btn primary wide">Kirish</button>
<p class="muted small">Parol: .env dagi ADMIN_PANEL_PASSWORD yoki data/admin_panel_password.txt</p>
</form></body></html>"""


class AdminPanel:
    def __init__(self, svc: TaxiService, password: str, host: str = "127.0.0.1", port: int = 8080) -> None:
        self.svc = svc
        self.password = password
        self.host = host
        self.port = port
        self._key = secrets.token_bytes(32)
        self._runner: web.AppRunner | None = None

    # ------------------------------------------------------------------ autentifikatsiya
    def _token(self) -> str:
        return hmac.new(self._key, b"admin-session", hashlib.sha256).hexdigest()

    def _authed(self, request: web.Request) -> bool:
        return hmac.compare_digest(request.cookies.get(COOKIE, ""), self._token())

    @web.middleware
    async def _security(self, request: web.Request, handler):
        path = request.path
        if not (path.startswith("/static/") or path == "/login"):
            if not self._authed(request):
                if path.startswith("/api/"):
                    return web.json_response({"error": "unauthorized"}, status=401)
                raise web.HTTPFound("/login")
            # CSRF himoyasi: boshqa saytdan bu sarlavha bilan so'rov yuborib bo'lmaydi
            if request.method != "GET" and request.headers.get("X-Panel") != "1":
                return web.json_response({"error": "forbidden"}, status=403)
        response = await handler(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    async def login_page(self, request: web.Request, error: str = "") -> web.Response:
        if self._authed(request):
            raise web.HTTPFound("/")
        html = LOGIN_PAGE.format(
            company=escape(self.svc.settings.company_name, quote=False),
            error=f'<p class="error">{escape(error, quote=False)}</p>' if error else "",
        )
        return web.Response(text=html, content_type="text/html")

    async def login(self, request: web.Request) -> web.Response:
        data = await request.post()
        given = str(data.get("password", ""))
        if not hmac.compare_digest(given.encode(), self.password.encode()):
            await asyncio.sleep(1.0)  # parolni terib topishni sekinlashtirish
            return await self.login_page(request, "Parol noto'g'ri")
        response = web.HTTPFound("/")
        response.set_cookie(COOKIE, self._token(), httponly=True, samesite="Strict", max_age=7 * 24 * 3600)
        raise response

    async def logout(self, request: web.Request) -> web.Response:
        response = web.HTTPFound("/login")
        response.del_cookie(COOKIE)
        raise response

    async def index(self, request: web.Request) -> web.Response:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        html = html.replace("{{COMPANY}}", escape(self.svc.settings.company_name, quote=False))
        return web.Response(text=html, content_type="text/html")

    # ------------------------------------------------------------------ API: o'qish
    async def api_summary(self, request: web.Request) -> web.Response:
        return web.json_response(await self.svc.admin_summary())

    async def api_map(self, request: web.Request) -> web.Response:
        return web.json_response(await self.svc.admin_map())

    async def api_orders(self, request: web.Request) -> web.Response:
        scope = request.query.get("scope", "active")
        return web.json_response(await self.svc.admin_orders(scope, _int(request.query.get("limit"), 200)))

    async def api_drivers(self, request: web.Request) -> web.Response:
        status = request.query.get("status") or None
        if status and status not in {s.value for s in DriverStatus}:
            raise web.HTTPBadRequest(text="status")
        return web.json_response(await self.svc.admin_drivers(status))

    async def api_passengers(self, request: web.Request) -> web.Response:
        return web.json_response(await self.svc.admin_passengers())

    async def api_finance(self, request: web.Request) -> web.Response:
        return web.json_response(await self.svc.admin_finance(_int(request.query.get("days"), 14)))

    async def api_transactions(self, request: web.Request) -> web.Response:
        return web.json_response(await self.svc.admin_transactions(_int(request.query.get("limit"), 100)))

    # ------------------------------------------------------------------ API: amallar
    async def api_driver_action(self, request: web.Request) -> web.Response:
        driver_id = _int(request.match_info["id"], 0)
        action = request.match_info["action"]
        statuses = {
            "approve": DriverStatus.APPROVED,
            "unblock": DriverStatus.APPROVED,
            "reject": DriverStatus.REJECTED,
            "block": DriverStatus.BLOCKED,
        }
        if action == "topup":
            body = await _json(request)
            amount = _int(body.get("amount"), 0)
            if not amount or abs(amount) > 100_000_000:
                return web.json_response({"error": "Summa noto'g'ri"}, status=400)
            d = await self.svc.adjust_balance(
                driver_id, amount, "topup" if amount > 0 else "adjust", note="web-panel"
            )
        elif action in statuses:
            d = await self.svc.admin_set_driver_status(driver_id, statuses[action])
        else:
            raise web.HTTPNotFound()
        if d is None:
            return web.json_response({"error": "Haydovchi topilmadi"}, status=404)
        return web.json_response({"ok": True, "balance": d.balance, "status": d.status})

    async def api_order_cancel(self, request: web.Request) -> web.Response:
        ok = await self.svc.admin_cancel_order(_int(request.match_info["id"], 0), by="web-panel")
        if not ok:
            return web.json_response({"error": "Buyurtma faol emas yoki topilmadi"}, status=409)
        return web.json_response({"ok": True})

    async def api_passenger_action(self, request: web.Request) -> web.Response:
        action = request.match_info["action"]
        if action not in ("block", "unblock"):
            raise web.HTTPNotFound()
        ok = await self.svc.set_passenger_blocked(_int(request.match_info["id"], 0), action == "block")
        if not ok:
            return web.json_response({"error": "Yo'lovchi topilmadi"}, status=404)
        return web.json_response({"ok": True})

    # ------------------------------------------------------------------ ilova
    def build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._security], client_max_size=64 * 1024)
        app.add_routes(
            [
                web.get("/", self.index),
                web.get("/login", self.login_page),
                web.post("/login", self.login),
                web.post("/logout", self.logout),
                web.get("/api/summary", self.api_summary),
                web.get("/api/map", self.api_map),
                web.get("/api/orders", self.api_orders),
                web.get("/api/drivers", self.api_drivers),
                web.get("/api/passengers", self.api_passengers),
                web.get("/api/finance", self.api_finance),
                web.get("/api/transactions", self.api_transactions),
                web.post(r"/api/drivers/{id:\d+}/{action}", self.api_driver_action),
                web.post(r"/api/orders/{id:\d+}/cancel", self.api_order_cancel),
                web.post(r"/api/passengers/{id:\d+}/{action}", self.api_passenger_action),
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


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _json(request: web.Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
