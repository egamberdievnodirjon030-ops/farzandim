"""Admin web-panel: bot bilan bitta jarayonda ishlaydi (aiohttp).

* Shu kompyuterda: http://localhost:8080
* Internet orqali (Cloudflare tunnel, HTTPS): https://<ilova-manzili>/admin/ — ADMIN_PANEL_PUBLIC=true bo'lsa
Kirish — parol bilan (ADMIN_PANEL_PASSWORD yoki data/admin_panel_password.txt). Panel internetga ochiq
bo'lgani uchun: har kirishga alohida sessiya, HTTPS'da Secure cookie, parolni terib topishdan himoya.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web

from ..db.models import DriverStatus
from ..services.taxi import TaxiService

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
COOKIE = "taxi_admin"
PASSWORD_FILE = Path("data") / "admin_panel_password.txt"
SESSION_TTL = 7 * 24 * 3600
MAX_SESSIONS = 50
FAIL_WINDOW = 15 * 60
FAILS_PER_IP = 5  # 15 daqiqada bitta manzildan
FAILS_TOTAL = 30  # 15 daqiqada jami (manzilni almashtirib terishga qarshi)


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
    password = secrets.token_urlsafe(12)
    try:
        PASSWORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        PASSWORD_FILE.write_text(password + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        log.warning("Panel paroli saqlanmadi: %s", exc)
    return password, True


def tile_sources(tile_url: str) -> str:
    """CSP uchun xarita plitkalari manbasi (TILE_URL dan; {s} — subdomenlar)."""
    host = urlparse(tile_url.replace("{s}", "a")).netloc
    if not host:
        return ""
    src = f"https://{host}"
    if "{s}" in tile_url:
        src += f" https://*.{host.split('.', 1)[-1]}"
    return src


LOGIN_PAGE = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><title>Kirish — {company}</title>
<link rel="stylesheet" href="{base}static/app.css"></head>
<body class="login-body"><main class="login-wrap"><form class="login-card" method="post" action="{base}login">
<div class="login-logo" aria-hidden="true">🚕</div><h1>{company}</h1><p class="muted">Boshqaruv paneli</p>
{error}<label for="pw">Parol</label>
<input id="pw" type="password" name="password" autocomplete="current-password" autofocus required>
<button type="submit" class="btn primary block">Kirish</button>
<p class="muted small">Parol: .env dagi ADMIN_PANEL_PASSWORD yoki data/admin_panel_password.txt
(bot ishga tushganda oynada ham ko'rsatiladi).</p>
</form></main></body></html>"""


class AdminPanel:
    def __init__(self, svc: TaxiService, password: str, host: str = "127.0.0.1", port: int = 8080) -> None:
        self.svc = svc
        self.password = password
        self.host = host
        self.port = port
        self._sessions: dict[str, float] = {}  # token -> amal qilish muddati (unix vaqt)
        self._fails: dict[str, list[float]] = {}
        self._runner: web.AppRunner | None = None
        self.csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            f"img-src 'self' data: {tile_sources(svc.settings.tile_url)}; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )

    # ------------------------------------------------------------------ autentifikatsiya
    def _new_session(self) -> str:
        now = time.time()
        self._sessions = {t: exp for t, exp in self._sessions.items() if exp > now}
        while len(self._sessions) >= MAX_SESSIONS:
            self._sessions.pop(min(self._sessions, key=self._sessions.__getitem__))
        token = secrets.token_urlsafe(32)
        self._sessions[token] = now + SESSION_TTL
        return token

    def _authed(self, request: web.Request) -> bool:
        token = request.cookies.get(COOKIE, "")
        exp = self._sessions.get(token) if token else None
        return exp is not None and exp > time.time()

    @staticmethod
    def _client_ip(request: web.Request) -> str:
        # Cloudflare tunnel orqali kelganda haqiqiy manzil shu sarlavhada
        return request.headers.get("CF-Connecting-IP") or request.remote or "?"

    @staticmethod
    def _https(request: web.Request) -> bool:
        return (
            request.secure
            or request.headers.get("X-Forwarded-Proto", "").lower() == "https"
            or '"https"' in request.headers.get("Cf-Visitor", "")
        )

    def _locked(self, ip: str) -> bool:
        now = time.time()
        for key in list(self._fails):
            self._fails[key] = [t for t in self._fails[key] if now - t < FAIL_WINDOW]
            if not self._fails[key]:
                del self._fails[key]
        total = sum(len(v) for v in self._fails.values())
        return len(self._fails.get(ip, [])) >= FAILS_PER_IP or total >= FAILS_TOTAL

    def _make_security(self, prefix: str):
        @web.middleware
        async def security(request: web.Request, handler):
            path = request.path[len(prefix):] or "/"
            if not (path.startswith("/static/") or path == "/login"):
                if not self._authed(request):
                    if path.startswith("/api/"):
                        return web.json_response({"error": "unauthorized"}, status=401)
                    raise web.HTTPFound(f"{prefix}/login")
                # CSRF himoyasi: boshqa saytdan bu sarlavha bilan so'rov yuborib bo'lmaydi
                if request.method != "GET" and request.headers.get("X-Panel") != "1":
                    return web.json_response({"error": "forbidden"}, status=403)
            response = await handler(request)
            response.headers.setdefault("Content-Security-Policy", self.csp)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            # Xarita serverlari (OpenStreetMap) Referer'siz so'rovlarni bloklaydi — faqat sayt manzili yuboriladi
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("X-Frame-Options", "DENY")
            if path.startswith("/api/") or path in ("/", "/login"):
                response.headers.setdefault("Cache-Control", "no-store")
            return response

        return security

    async def login_page(self, request: web.Request, error: str = "", status: int = 200) -> web.Response:
        base = request.app[BASE]
        if self._authed(request):
            raise web.HTTPFound(base)
        html = LOGIN_PAGE.format(
            company=escape(self.svc.settings.company_name, quote=False),
            base=base,
            error=f'<p class="error" role="alert">{escape(error, quote=False)}</p>' if error else "",
        )
        return web.Response(text=html, content_type="text/html", status=status)

    async def login(self, request: web.Request) -> web.Response:
        ip = self._client_ip(request)
        if self._locked(ip):
            return await self.login_page(request, "Urinishlar ko'p. 15 daqiqadan so'ng qayta urinib ko'ring.", 429)
        data = await request.post()
        given = str(data.get("password", ""))
        if not secrets.compare_digest(given.encode(), self.password.encode()):
            self._fails.setdefault(ip, []).append(time.time())
            log.warning("Admin panel: noto'g'ri parol (%s)", ip)
            await asyncio.sleep(1.0)  # parolni terib topishni sekinlashtirish
            return await self.login_page(request, "Parol noto'g'ri")
        self._fails.pop(ip, None)
        base = request.app[BASE]
        response = web.HTTPFound(base)
        response.set_cookie(
            COOKIE, self._new_session(), httponly=True, samesite="Strict", max_age=SESSION_TTL,
            secure=self._https(request), path=base,
        )
        raise response

    async def logout(self, request: web.Request) -> web.Response:
        self._sessions.pop(request.cookies.get(COOKIE, ""), None)
        base = request.app[BASE]
        response = web.HTTPFound(f"{base}login")
        response.del_cookie(COOKIE, path=base)
        raise response

    async def index(self, request: web.Request) -> web.Response:
        s = self.svc.settings
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        html = (
            html.replace("{{COMPANY}}", escape(s.company_name, quote=True))
            .replace("{{TILE_URL}}", escape(s.tile_url, quote=True))
            .replace("{{TILE_ATTR}}", escape(s.tile_attribution, quote=True))
        )
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
    def build_app(self, prefix: str = "") -> web.Application:
        """`prefix` — boshqa ilova ichiga ulanganda (masalan "/admin"); sahifadagi havolalar nisbiy."""
        app = web.Application(middlewares=[self._make_security(prefix)], client_max_size=64 * 1024)
        app[BASE] = f"{prefix}/"
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


BASE = web.AppKey("base", str)


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
