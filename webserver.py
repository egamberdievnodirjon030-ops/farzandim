"""Web App veb-serveri: ilova fayllari (webapp/) va API (webapi.py). Bot bilan bitta jarayonda ishlaydi."""
from __future__ import annotations

import html
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, WebAppInfo
from aiohttp import web

import deskauth
import live
import webapi
from config import ADMIN_COURSE, SUPERADMIN_IDS, WEBAPP_HOST, WEBAPP_PORT, WEBAPP_URL
from tenancy import course_title

log = logging.getLogger("webapp")
STATIC = Path(__file__).parent / "webapp"


@web.middleware
async def security_headers(request: web.Request, handler):
    resp = await handler(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    # Ilova faqat Telegram ichida ochiladi — begona saytlarga joylashtirilmaydi
    resp.headers.setdefault("Content-Security-Policy",
                            "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; "
                            "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors https://web.telegram.org "
                            "https://*.telegram.org; object-src 'none'; base-uri 'self'")
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def _version() -> str:
    """Ilova fayllari versiyasi (o'zgartirilgan vaqtlari bo'yicha): yangi kod o'rnatilganda o'zgaradi."""
    import hashlib
    stamp = "|".join(f"{f}:{(STATIC / f).stat().st_mtime_ns}" for f in ("app.js", "app.css", "desk.js", "desk.css", "tg.js")
                     if (STATIC / f).exists())
    return hashlib.sha1(stamp.encode()).hexdigest()[:10]


APP_VERSION = _version()


def _html(name: str) -> web.Response:
    """HTML sahifa — skript va uslublar versiya bilan (?v=…): Telegram eski nusxani keshdan olmaydi, ilovani
    qo'lda yangilash shart emas."""
    html = (STATIC / name).read_text(encoding="utf-8")
    for f in ("app.css", "app.js", "desk.css", "desk.js", "fonts.css", "tg.js"):
        html = html.replace(f"static/{f}\"", f"static/{f}?v={APP_VERSION}\"")
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def index(request: web.Request) -> web.Response:
    return _html("index.html")


# ---------------------------------------------------------------- telefon ilovasi: PWA va yuklab olish sahifasi
async def manifest(request: web.Request) -> web.Response:
    return web.json_response({
        "name": "JIDU — Ota-onalar", "short_name": "JIDU Ota-ona", "lang": "uz", "start_url": "/", "scope": "/",
        "display": "standalone", "background_color": "#0E2240", "theme_color": "#0E2240",
        "icons": [{"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/static/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]},
        content_type="application/manifest+json")


async def download_page(request: web.Request) -> web.Response:
    """Ilovani yuklab olish: Android — APK (super-admin botga yuklagan), iPhone — App Store/TestFlight yoki Safari."""
    from handlers.mobileapp import APK_NAME, apk_path
    from tenancy import central
    version = await central.get_meta("android_apk_version") or ""
    ios_url = await central.get_meta("ios_url") or ""
    try:
        bot_name = (await request.app["bot"].me()).username
    except Exception:
        bot_name = ""
    has_apk = apk_path().exists()
    android = (f'<a class="btn" href="/ilova/{APK_NAME}">🤖 Android uchun yuklab olish{f" ({html.escape(version)})" if version else ""}</a>'
               '<p class="hint">Faylni oching → «O\'rnatish». Telefon ruxsat so\'rasa — brauzer uchun «noma\'lum manbalar»ga '
               'bir marta ruxsat bering.</p>' if has_apk else
               f'<p class="hint">Android fayli botda: <b>/ilova</b> buyrug\'ini yuboring.</p>')
    ios = (f'<a class="btn" href="{html.escape(ios_url)}">🍏 iPhone uchun o\'rnatish</a>' if ios_url else
           '<p class="hint">🍏 <b>iPhone</b>: shu sahifani <b>Safari</b>da oching → «Ulashish» belgisi → '
           '«Bosh ekranga qo\'shish». So\'ng belgini bosib, <b>«Telegram orqali kirish»</b> ni tanlang.</p>'
           '<a class="btn ghost" href="/">Ilovani ochish</a>')
    bot = (f'<p class="hint">Kirish va bildirishnomalar — Telegram botda: '
           f'<a href="https://t.me/{html.escape(bot_name)}">@{html.escape(bot_name)}</a></p>' if bot_name else "")
    body = (f"<h1>Telefon ilovasi</h1><p>Farzandingizning davomati, baholari va to'lovlari — telefoningizda.</p>"
            f"{android}<hr>{ios}{bot}")
    page = _LOGIN_PAGE.format(body=body).replace(
        "</style>", ".btn{display:block;text-align:center;text-decoration:none;border-radius:14px;padding:14px 18px;"
        "font-weight:600;color:#fff;background:#0E2240;margin:8px 0}.btn.ghost{background:#F3F5F9;color:#0E2240}"
        ".hint{font-size:14px;color:#5B6781}hr{border:0;border-top:1px solid #E6EAF1;margin:18px 0}</style>"
        '<link rel="icon" href="/static/icon-192.png">').replace("<title>Kirish — Boshqaruv paneli</title>",
                                                               "<title>JIDU — Telefon ilovasi</title>")
    return web.Response(text=page, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def download_apk(request: web.Request) -> web.StreamResponse:
    from handlers.mobileapp import APK_NAME, apk_path
    p = apk_path()
    if not p.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(p, headers={"Content-Type": "application/vnd.android.package-archive",
                                        "Content-Disposition": f'attachment; filename="{APK_NAME}"',
                                        "Cache-Control": "no-cache"})


# ---------------------------------------------------------------- kompyuter versiyasi (boshqaruv paneli)
_LOGIN_PAGE = """<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kirish — Boshqaruv paneli</title><link rel="stylesheet" href="/static/fonts.css"><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;font:16px/1.5 'Golos Text',system-ui,sans-serif;
background:radial-gradient(1200px 600px at 80% -10%,#1B3A6B 0%,#0E2240 55%,#0A1830 100%);color:#16213A}}
.card{{width:min(440px,92vw);background:#fff;border-radius:22px;padding:36px 34px 30px;box-shadow:0 30px 80px rgba(0,0,0,.35);position:relative;overflow:hidden}}
.card:before{{content:"";position:absolute;inset:0 0 auto 0;height:6px;background:linear-gradient(90deg,#7D1D3F,#9E2A52)}}
.seal{{width:56px;height:56px;border-radius:50%;display:grid;place-items:center;background:#7D1D3F;color:#fff;font:700 24px 'PT Serif',Georgia,serif;margin-bottom:18px}}
h1{{font:700 24px/1.25 'PT Serif',Georgia,serif;margin:0 0 6px;color:#0E2240}}p{{margin:0 0 18px;color:#5B6781}}
.who{{background:#F3F5F9;border-radius:14px;padding:12px 14px;margin:0 0 20px;font-weight:600}}
button{{width:100%;border:0;border-radius:14px;padding:14px 18px;font:600 16px 'Golos Text',system-ui,sans-serif;color:#fff;background:#0E2240;cursor:pointer}}
button:hover{{background:#1B3A6B}}small{{display:block;margin-top:16px;color:#8A93A8;font-size:13px}}</style></head>
<body><main class="card"><div class="seal">J</div>{body}</main></body></html>"""


def _login_html(body: str, status: int = 200) -> web.Response:
    return web.Response(text=_LOGIN_PAGE.format(body=body), content_type="text/html", status=status,
                        headers={"Cache-Control": "no-store"})


_EXPIRED = ("<h1>Havola eskirgan</h1><p>Kirish havolasi 10 daqiqa amal qiladi va faqat bir marta ishlatiladi.</p>"
            "<p>Yangi havola olish uchun botda <b>«💻 Kompyuter versiyasi»</b> tugmasini bosing yoki "
            "<b>/kompyuter</b> buyrug'ini yuboring.</p>")


async def desk_login_page(request: web.Request) -> web.Response:
    token = request.query.get("t", "")
    uid = deskauth.peek(token)
    if uid is None:
        return _login_html(_EXPIRED, 410)
    role = "Super-admin" if uid in SUPERADMIN_IDS else "Kurs koordinatori"
    title = course_title(ADMIN_COURSE[uid]) if uid in ADMIN_COURSE and ADMIN_COURSE[uid] != "_" else ""
    who = html.escape(role + (f" · {title}" if title else ""))
    return _login_html(
        "<h1>Boshqaruv paneli</h1><p>Ota-onalar davomat boti — kompyuter versiyasi</p>"
        f'<div class="who">{who}<br><span style="font-weight:400;color:#5B6781">Telegram ID {uid}</span></div>'
        f'<form method="post" action="/desk/login"><input type="hidden" name="t" value="{html.escape(token)}">'
        '<button type="submit">Kirish</button></form>'
        "<small>Seans 12 soat amal qiladi. Umumiy kompyuterda ishlagandan so'ng «Chiqish» tugmasini bosing.</small>")


async def desk_login(request: web.Request) -> web.Response:
    form = await request.post()
    uid = deskauth.consume(str(form.get("t", "")))
    if uid is None or (uid not in ADMIN_COURSE and uid not in SUPERADMIN_IDS):
        return _login_html(_EXPIRED, 410)
    resp = web.HTTPSeeOther("/desk")
    resp.set_cookie(deskauth.COOKIE, deskauth.make_cookie(uid), max_age=deskauth.SESSION_TTL, path="/",
                    httponly=True, secure=deskauth.cookie_secure(), samesite="Lax")
    log.info("Kompyuter versiyasiga kirish: %s", uid)
    return resp


async def desk(request: web.Request) -> web.Response:
    return _html("desk.html")


def create_app(bot: Bot) -> web.Application:
    app = web.Application(middlewares=[security_headers, webapi.auth_middleware], client_max_size=25 * 1024 * 1024)
    app["bot"] = bot
    webapi.setup_routes(app)
    app.router.add_get("/", index)
    app.router.add_get("/healthz", lambda r: web.Response(text="ok"))
    app.on_shutdown.append(live.close_all)  # real vaqt ulanishlari server to'xtaganda darhol yopilsin
    app.router.add_get("/manifest.webmanifest", manifest)
    app.router.add_get("/ilova", download_page)
    app.router.add_get("/ilova/{name}", download_apk)
    app.router.add_get("/desk", desk)
    app.router.add_get("/desk/login", desk_login_page)
    app.router.add_post("/desk/login", desk_login)
    app.router.add_static("/static/", STATIC, show_index=False)
    return app


async def start(bot: Bot) -> web.AppRunner | None:
    """Veb-serverni ishga tushiradi va Telegram'dagi chat pastiga «📱 Ilova» tugmasini o'rnatadi.
    WEBAPP_URL bo'sh bo'lsa, tugma standart holatga qaytariladi — eski (masalan vaqtinchalik tunnel)
    manzili menyuda qolib ketmasin."""
    runner = None
    if WEBAPP_PORT:
        runner = web.AppRunner(create_app(bot), access_log=None)
        await runner.setup()
        await web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT).start()
        log.info("Web App serveri: http://%s:%s (ochiq manzil: %s)", WEBAPP_HOST, WEBAPP_PORT, WEBAPP_URL or "sozlanmagan")
    try:
        if WEBAPP_PORT and WEBAPP_URL:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="📱 Ilova", web_app=WebAppInfo(url=WEBAPP_URL + "/")))
        else:
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    except Exception as e:  # tarmoq xatosi botning ishiga to'sqinlik qilmasin
        log.warning("Menyu tugmasini o'rnatib bo'lmadi: %s", e)
    return runner
