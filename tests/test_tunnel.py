"""HTTPS tunnel: noto'g'ri manzil olinmasligi, xatoda bot to'xtamasligi, uzilganda qayta ochilishi."""

from __future__ import annotations

import asyncio
import os
import stat
import sys

from taxi_bot.services import tunnel as tunnel_mod
from taxi_bot.services.tunnel import (
    CLOUDFLARE_URL_RE,
    LOCALHOST_RUN_URL_RE,
    Provider,
    Tunnel,
    find_cloudflared,
    is_valid_binary,
)

# Haqiqiy cloudflared xatosi (foydalanuvchida shunday bo'lgan): tunnel ochilmagan, matnda esa API manzili bor
CLOUDFLARED_FAILURE = """\
2026-11-23T09:30:00Z INF Thank you for trying Cloudflare Tunnel. ... (https://www.cloudflare.com/website-terms/) ...
2026-11-23T09:30:00Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-11-23T09:30:15Z ERR Error requesting quick Tunnel error="failed to request quick Tunnel: \
Post \\"https://api.trycloudflare.com/tunnel\\": dial tcp: lookup api.trycloudflare.com: no such host"
failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": dial tcp: i/o timeout
"""
CLOUDFLARED_SUCCESS = """\
2026-11-23T09:30:00Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-11-23T09:30:02Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-11-23T09:30:02Z INF |  https://brave-fox-river-lamp.trycloudflare.com                                           |
"""
LOCALHOST_RUN_SUCCESS = """\
Welcome to localhost.run! Docs: https://localhost.run/docs/ admin: https://admin.localhost.run/
authenticated as anonymous user
3f2a9c1d7b6e54.lhr.life tunneled with tls termination, https://3f2a9c1d7b6e54.lhr.life
"""


def fake(tmp_path, name: str, output: str, then: str = "time.sleep(30)") -> tuple[str, ...]:
    """Berilgan matnni chiqaradigan soxta tunnel dasturi."""
    text = tmp_path / f"{name}.txt"
    text.write_text(output)
    code = f"import sys,time; sys.stdout.write(open({str(text)!r}).read()); sys.stdout.flush(); {then}"
    return (sys.executable, "-c", code)


def test_api_host_from_error_text_is_never_taken_as_app_url():
    assert CLOUDFLARE_URL_RE.search(CLOUDFLARED_FAILURE) is None
    found = CLOUDFLARE_URL_RE.search(CLOUDFLARED_SUCCESS)
    assert found and found.group(0) == "https://brave-fox-river-lamp.trycloudflare.com"
    found = LOCALHOST_RUN_URL_RE.search(LOCALHOST_RUN_SUCCESS)
    assert found and found.group(0) == "https://3f2a9c1d7b6e54.lhr.life"


async def test_failed_cloudflare_falls_back_to_second_provider_and_reports_reason(tmp_path, capsys):
    providers = [
        Provider("Cloudflare", fake(tmp_path, "cf", CLOUDFLARED_FAILURE, "sys.exit(1)"), CLOUDFLARE_URL_RE),
        Provider("localhost.run", fake(tmp_path, "lr", LOCALHOST_RUN_SUCCESS), LOCALHOST_RUN_URL_RE),
    ]
    t = Tunnel(8081, providers=providers, open_timeout=5)
    assert await t.open() == "https://3f2a9c1d7b6e54.lhr.life"
    out = capsys.readouterr().out
    assert "Cloudflare tunnel ochilmadi" in out and "failed to request quick Tunnel" in out
    await t.stop()
    assert t.process and t.process.returncode is not None


async def test_no_url_resets_menu_and_tunnel_reopens_after_drop(tmp_path):
    changes: list[str | None] = []

    async def on_change(url):
        changes.append(url)

    # 1-urinish: muvaffaqiyatsiz; 2-urinish: manzil beradi va tez orada uziladi; 3-urinish: yangi manzil
    state = tmp_path / "n"
    code = (
        f"import pathlib,sys,time; p=pathlib.Path({str(state)!r}); n=int(p.read_text()) if p.exists() else 0; "
        "p.write_text(str(n+1)); "
        "sys.exit(1) if n==0 else None; "
        "print(f'INF |  https://run-{n}-ok.trycloudflare.com  |', flush=True); "
        "time.sleep(0.5 if n==1 else 30)"
    )
    provider = Provider("Cloudflare", (sys.executable, "-c", code), CLOUDFLARE_URL_RE)
    t = Tunnel(8081, on_change=on_change, providers=[provider], open_timeout=5, retry_delay=0.1)
    t.start()
    for _ in range(100):
        if len(changes) >= 3:
            break
        await asyncio.sleep(0.1)
    await t.stop()
    assert changes[:3] == [None, "https://run-1-ok.trycloudflare.com", "https://run-2-ok.trycloudflare.com"]


async def test_unrunnable_program_does_not_crash(tmp_path):
    """WinError 193 kabi holat: fayl bor, lekin ishga tushmaydi."""
    broken = tmp_path / "cloudflared"
    broken.write_bytes(b"\x7fELF" + b"\0" * 100)
    broken.chmod(broken.stat().st_mode | stat.S_IEXEC)
    t = Tunnel(8081, providers=[Provider("Cloudflare", (str(broken),), CLOUDFLARE_URL_RE)], open_timeout=3)
    assert await t.open() is None


def test_broken_download_is_detected_and_removed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tunnel_mod.shutil, "which", lambda _name: None)
    (tmp_path / "cloudflared.exe").write_text("<html>Access denied</html>")  # tarmoq HTML qaytargan
    assert find_cloudflared() is None
    assert not (tmp_path / "cloudflared.exe").exists()  # keyingi safar qayta yuklanadi


def test_binary_validation(tmp_path):
    good = tmp_path / "ok"
    good.write_bytes((b"MZ" if os.name == "nt" else b"\x7fELF") + b"\0" * 6_000_000)
    small = tmp_path / "small"
    small.write_bytes(b"MZ" + b"\0" * 100)
    assert is_valid_binary(good) and not is_valid_binary(small) and not is_valid_binary(tmp_path / "yoq")


def test_ssh_fallback_is_detected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tunnel_mod, "find_cloudflared", lambda: None)
    monkeypatch.setattr(tunnel_mod.shutil, "which", lambda name: "/usr/bin/ssh" if name == "ssh" else None)
    providers = tunnel_mod.detect_providers(8081)
    assert [p.name for p in providers] == ["localhost.run"]
    argv = providers[0].argv
    assert "80:127.0.0.1:8081" in argv and argv[-1] == "nokey@localhost.run" and "BatchMode=yes" in argv


class FakeBot:
    def __init__(self):
        self.menus = []

    async def set_chat_menu_button(self, menu_button):
        self.menus.append(menu_button)


async def test_app_menu_never_points_to_cloudflare_api(make_service, tmp_path, monkeypatch):
    """Foydalanuvchidagi xato: cloudflared ishlamaganda menyuga https://api.trycloudflare.com yozilgan edi."""
    from aiogram.types import MenuButtonCommands, MenuButtonWebApp

    from taxi_bot.app import start_miniapp

    providers = [
        Provider("Cloudflare", fake(tmp_path, "cf", CLOUDFLARED_FAILURE, "sys.exit(1)"), CLOUDFLARE_URL_RE),
        Provider("localhost.run", fake(tmp_path, "lr", LOCALHOST_RUN_SUCCESS), LOCALHOST_RUN_URL_RE),
    ]
    monkeypatch.setattr(tunnel_mod, "detect_providers", lambda _port: providers)
    svc, _ = await make_service(driver_bot_token=None, webapp_port=0)
    bot = FakeBot()
    server, tunnel = await start_miniapp(svc.settings, svc, bot, bot)  # type: ignore[arg-type]
    try:
        assert isinstance(bot.menus[0], MenuButtonCommands)  # eski havola darhol olib tashlanadi
        for _ in range(50):
            if svc.webapp_url:
                break
            await asyncio.sleep(0.1)
        assert svc.webapp_url == "https://3f2a9c1d7b6e54.lhr.life"
        assert isinstance(bot.menus[-1], MenuButtonWebApp)
        assert bot.menus[-1].web_app.url == "https://3f2a9c1d7b6e54.lhr.life/"
        assert not any("api.trycloudflare" in str(m) for m in bot.menus)
    finally:
        await tunnel.stop()
        await server.stop()


def test_user_dns_error_gets_actionable_hint():
    """Foydalanuvchidagi haqiqiy xato: tarmoq DNS'i api.trycloudflare.com ni bermayapti."""
    from taxi_bot.services.tunnel import BLOCKED_HINT, DNS_HINT, hint_for

    reason = (
        'failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": dial tcp: lookup '
        "api.trycloudflare.com: getaddrinfow: The requested name is valid, but no data of the requested type was found."
    )
    assert hint_for(reason) == DNS_HINT and "1.1.1.1" in DNS_HINT
    assert hint_for("ssh: connect to host localhost.run port 22: Connection timed out") == BLOCKED_HINT
    assert hint_for("something else") is None


async def test_quick_tunnel_is_requested_without_system_dns(monkeypatch):
    """Foydalanuvchi holati: tarmoq DNS'i api.trycloudflare.com ni bermaydi — DoH + IP orqali olinadi."""
    import base64
    import json
    import socket

    from aiohttp import web
    from aiohttp.test_utils import TestServer

    async def doh(request):
        assert request.query["name"] == "api.trycloudflare.com"
        return web.json_response({"Status": 0, "Answer": [{"name": "api.trycloudflare.com", "type": 1, "data": "127.0.0.1"}]})

    async def api(request):
        assert request.method == "POST" and request.host.startswith("api.trycloudflare.com")
        assert request.headers["User-Agent"] == "cloudflared/2026.11.1"
        return web.json_response({"success": True, "result": {
            "id": "9ce6e75d-1bd9-4608-8347-64cd76958233", "name": "qt", "hostname": "calm-sea-tree.trycloudflare.com",
            "account_tag": "acc123", "secret": "c2VjcmV0",
        }})

    app = web.Application()
    app.router.add_get("/dns-query", doh)
    app.router.add_post("/tunnel", api)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    monkeypatch.setattr(tunnel_mod, "DOH_SERVERS", (f"http://127.0.0.1:{server.port}/dns-query",))
    monkeypatch.setattr(tunnel_mod, "QUICK_TUNNEL_API", f"http://api.trycloudflare.com:{server.port}/tunnel")

    real_getaddrinfo = socket.getaddrinfo

    def blocked_dns(host, *args, **kwargs):  # ofis tarmog'idagi kabi: bu nom DNS'da topilmaydi
        if "trycloudflare" in str(host):
            raise socket.gaierror(11004, "The requested name is valid, but no data of the requested type was found")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", blocked_dns)
    try:
        url, token = await tunnel_mod.request_quick_tunnel("cloudflared/2026.11.1")
    finally:
        await server.close()
    assert url == "https://calm-sea-tree.trycloudflare.com"
    # cloudflared `tunnel run` kutadigan TUNNEL_TOKEN formati: base64(JSON {a, s, t})
    assert json.loads(base64.b64decode(token)) == {
        "a": "acc123", "s": "c2VjcmV0", "t": "9ce6e75d-1bd9-4608-8347-64cd76958233"
    }


async def test_doh_unreachable_gives_clear_reason(monkeypatch):
    monkeypatch.setattr(tunnel_mod, "DOH_SERVERS", ("http://127.0.0.1:9/dns-query",))  # yopiq port
    try:
        await tunnel_mod.request_quick_tunnel()
    except OSError as exc:
        assert "javob bermadi" in str(exc)
        assert tunnel_mod.hint_for(str(exc)) == tunnel_mod.BLOCKED_HINT
    else:
        raise AssertionError("xato kutilgan edi")


async def test_dns_free_provider_waits_for_registration_and_passes_token(tmp_path, capsys):
    async def prepare():
        return "https://calm-sea-tree.trycloudflare.com", {"TUNNEL_TOKEN": "tok-123"}

    code = (
        "import os,sys,time; print('INF Starting tunnel token=' + os.environ['TUNNEL_TOKEN'], flush=True); "
        "time.sleep(0.2); print('INF Registered tunnel connection connIndex=0 protocol=quic', flush=True); time.sleep(30)"
    )
    providers = [
        Provider("Cloudflare", fake(tmp_path, "cf", CLOUDFLARED_FAILURE, "sys.exit(1)"), CLOUDFLARE_URL_RE),
        Provider(
            "Cloudflare (DNS'siz)", (sys.executable, "-c", code), CLOUDFLARE_URL_RE,
            prepare=prepare, ready_re=tunnel_mod.CLOUDFLARE_READY_RE, timeout=5,
        ),
    ]
    t = Tunnel(8081, providers=providers, open_timeout=5)
    assert await t.open() == "https://calm-sea-tree.trycloudflare.com"
    out = capsys.readouterr().out
    assert "Cloudflare tunnel ochilmadi" in out
    assert "1.1.1.1 / 8.8.8.8" not in out  # boshqa usul ishladi — "DNS'ni o'zgartiring" maslahati keraksiz
    await t.stop()


def test_dns_free_provider_uses_static_edge_and_token_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tunnel_mod, "find_cloudflared", lambda: "/opt/cloudflared")
    monkeypatch.setattr(tunnel_mod.shutil, "which", lambda _name: None)
    providers = tunnel_mod.detect_providers(8081)
    assert [p.name for p in providers] == ["Cloudflare", "Cloudflare (DNS'siz)"]
    argv = providers[1].argv
    assert argv[-1] == "run" and "--edge" in argv and "198.41.192.167:7844" in argv and "198.41.200.13:7844" in argv
    assert not any("TUNNEL_TOKEN" in a or "token" in a for a in argv)  # token faqat muhit orqali
