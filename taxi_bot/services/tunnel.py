"""Kompyuterda ishlaganda Telegram Mini App uchun HTTPS manzil — bepul tunnel orqali.

1. Cloudflare "quick tunnel" (`cloudflared`; Windows'da start.bat/run.py o'zi yuklab oladi) — asosiy;
2. Cloudflare "DNS'siz" — tarmoq DNS'i trycloudflare/argotunnel manzillarini bloklasa: tunnel API manzili
   DNS-over-HTTPS (to'g'ridan-to'g'ri 1.1.1.1 / 8.8.8.8 IP'lari) orqali topiladi, cloudflared esa Cloudflare
   hujjatidagi doimiy server IP'lariga (`--edge`) ulanadi — tizim DNS'i umuman kerak bo'lmaydi;
3. localhost.run — zaxira: Windows 10/11 ga o'rnatilgan `ssh` orqali, hech narsa yuklab olinmaydi.

`Tunnel.start()` fonda ishlaydi: bot darhol ishga tushadi, tunnel ochilgach menyu tugmasi yangilanadi.
Tunnel uzilsa — qayta ochiladi; ochilmasa — tugma o'chiriladi (buzuq havola qolmaydi).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import re
import shutil
import socket
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult

log = logging.getLogger(__name__)
MIN_SIZE = 5_000_000  # haqiqiy cloudflared ~30–60 MB; kichik fayl — to'liq yuklanmagan yoki HTML sahifa

# Faqat haqiqiy tunnel manzili: "so'z-so'z-so'z.trycloudflare.com". `api.trycloudflare.com` — Cloudflare'ning
# xizmat manzili, u faqat xato matnlarida uchraydi va ilova manzili EMAS.
CLOUDFLARE_URL_RE = re.compile(r"https://(?!api\.)[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com")
LOCALHOST_RUN_URL_RE = re.compile(r"https://[a-z0-9-]+\.lhr\.life")
ERROR_RE = re.compile(r"\bERR\b|error|failed|denied|refused|timed out|could not|ssh:", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT\S+\s+(?:(?:INF|ERR|WRN|DBG)\s+)?")
DNS_ERROR_RE = re.compile(
    r"lookup |getaddrinfo|no such host|name or service not known|could not resolve|no data of the requested type",
    re.IGNORECASE,
)
BLOCKED_RE = re.compile(
    r"timed out|timeout|no recent network activity|refused|unreachable|connection reset|javob bermadi", re.IGNORECASE
)
CLOUDFLARE_READY_RE = re.compile(r"Registered tunnel connection")

# Cloudflare tunnel serverlarining doimiy IP manzillari (region1/region2.v2.argotunnel.com, port 7844).
# Manba: developers.cloudflare.com — Cloudflare Tunnel > Tunnel with firewall > Required ports.
CLOUDFLARE_EDGE_IPS = (
    "198.41.192.167", "198.41.192.67", "198.41.192.57", "198.41.192.107",
    "198.41.200.13", "198.41.200.193", "198.41.200.33", "198.41.200.233",
)
# DNS-over-HTTPS: IP manzil bilan, ya'ni tarmoqning DNS serveriga murojaat qilinmaydi
DOH_SERVERS = ("https://1.1.1.1/dns-query", "https://8.8.8.8/resolve")
QUICK_TUNNEL_HOST = "api.trycloudflare.com"
QUICK_TUNNEL_API = f"https://{QUICK_TUNNEL_HOST}/tunnel"

DNS_HINT = """\
   ℹ️ Sabab: kompyuter ulangan tarmoq (ofis yoki provayder) DNS'i tunnel manzilini bloklayapti.
      Muammo faqat shu kompyuter tarmog'ida (telefonlar 4G orqali bu manzillarni ochadi). Yechimlardan biri:
      1) Windows DNS'ini 1.1.1.1 / 8.8.8.8 ga o'zgartiring: Sozlamalar > Tarmoq va Internet > (Wi-Fi yoki Ethernet)
         > Apparat xususiyatlari > DNS-server tayinlash > O'zgartirish > Qo'lda > IPv4: 1.1.1.1 va 8.8.8.8
      2) yoki kompyuterni boshqa internetga ulang (masalan, telefondagi hotspot / uy Wi-Fi).
      Tarmoq tuzalgach botni qayta ishga tushirish shart emas — tunnel o'zi qayta urinadi."""
BLOCKED_HINT = """\
   ℹ️ Sabab: tarmoq (ko'pincha ofis firewall'i) tunnel ulanishini to'smoqda.
      Kompyuterni boshqa internetga ulang (telefon hotspoti / uy Wi-Fi) — tunnel o'zi qayta urinadi."""


def hint_for(reason: str) -> str | None:
    if DNS_ERROR_RE.search(reason):
        return DNS_HINT
    if BLOCKED_RE.search(reason):
        return BLOCKED_HINT
    return None


OnChange = Callable[[str | None], Awaitable[None]]
Prepare = Callable[[], Awaitable[tuple[str, dict[str, str]]]]


def is_valid_binary(path: str | Path) -> bool:
    """Fayl haqiqiy dastur ekanini tekshiradi (Windows'da "MZ" sarlavha, hajm)."""
    p = Path(path)
    try:
        if p.stat().st_size < MIN_SIZE:
            return False
        with p.open("rb") as f:
            head = f.read(4)
    except OSError:
        return False
    if os.name == "nt":
        return head[:2] == b"MZ"
    return head[:4] == b"\x7fELF" or head[:2] == b"MZ" or head[:4] in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


def find_cloudflared() -> str | None:
    """Yaroqli cloudflared ni topadi. Loyiha papkasidagi buzilgan fayl o'chiriladi (start.bat qayta yuklaydi)."""
    for candidate in ("cloudflared.exe", "cloudflared"):
        local = Path(candidate)
        if local.is_file():
            if is_valid_binary(local):
                return str(local.resolve())
            size = local.stat().st_size
            log.warning(
                "%s buzilgan yoki to'liq yuklanmagan (%s bayt) — o'chirildi. start.bat uni qayta yuklab oladi.",
                candidate, size,
            )
            print(f"⚠️ {candidate} buzilgan ({size} bayt) — o'chirildi, keyingi ishga tushirishda qayta yuklanadi.")
            try:
                local.unlink()
            except OSError:
                pass
    for candidate in ("cloudflared", "cloudflared.exe"):
        found = shutil.which(candidate)
        if found and is_valid_binary(found):
            return found
    return None


@dataclass(frozen=True)
class Provider:
    name: str
    argv: tuple[str, ...]
    url_re: re.Pattern[str]
    # Manzil oldindan ma'lum bo'lsa: prepare() -> (url, qo'shimcha muhit o'zgaruvchilari);
    # tayyorlik esa jarayon chiqishidagi `ready_re` qatori bilan aniqlanadi.
    prepare: Prepare | None = None
    ready_re: re.Pattern[str] | None = None
    timeout: float | None = None


async def doh_resolve(host: str) -> list[str]:
    """Manzilni DNS-over-HTTPS orqali topadi (tizim DNS'iga murojaat qilmasdan)."""
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for server in DOH_SERVERS:
            try:
                async with session.get(
                    server, params={"name": host, "type": "A"}, headers={"accept": "application/dns-json"}
                ) as resp:
                    data = await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                log.debug("DoH %s: %s", server, exc)
                continue
            ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1 and a.get("data")]
            if ips:
                return ips
    return []


class PinnedResolver(AbstractResolver):
    """Berilgan host'larni oldindan topilgan IP'larga yo'naltiradi (TLS tekshiruvi host nomi bo'yicha qoladi)."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self.mapping = mapping

    async def resolve(self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET) -> list[ResolveResult]:
        ips = self.mapping.get(host)
        if not ips:
            raise OSError(f"{host}: IP manzil ma'lum emas")
        return [
            ResolveResult(hostname=host, host=ip, port=port, family=socket.AF_INET, proto=0, flags=socket.AI_NUMERICHOST)
            for ip in ips
        ]

    async def close(self) -> None:
        return None


async def request_quick_tunnel(user_agent: str = "cloudflared") -> tuple[str, str]:
    """Cloudflare'dan yangi quick tunnel oladi (DNS'siz). Qaytaradi: (https manzil, cloudflared uchun token)."""
    ips = await doh_resolve(QUICK_TUNNEL_HOST)
    if not ips:
        raise OSError("DNS-over-HTTPS (1.1.1.1, 8.8.8.8) ham javob bermadi")
    connector = aiohttp.TCPConnector(resolver=PinnedResolver({QUICK_TUNNEL_HOST: ips}), use_dns_cache=False)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
        try:
            async with session.post(
                QUICK_TUNNEL_API, headers={"Content-Type": "application/json", "User-Agent": user_agent}
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise OSError(f"{QUICK_TUNNEL_HOST} javob bermadi ({exc.__class__.__name__}: {exc})") from exc
    result = data.get("result") or {}
    if not data.get("success") or not result.get("hostname") or not result.get("secret"):
        raise OSError(f"Cloudflare tunnel bermadi: {data.get('errors') or data}"[:200])
    token = {"a": result["account_tag"], "s": result["secret"], "t": result["id"]}
    hostname = result["hostname"]
    url = hostname if hostname.startswith("https://") else f"https://{hostname}"
    return url, base64.b64encode(json.dumps(token).encode()).decode()


async def cloudflared_user_agent(binary: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        out, _ = await asyncio.wait_for(proc.communicate(), 10)
        match = re.search(r"version (\S+)", out.decode(errors="replace"))
        if match:
            return f"cloudflared/{match.group(1)}"
    except (OSError, TimeoutError):
        pass
    return "cloudflared"


def detect_providers(port: int) -> list[Provider]:
    providers: list[Provider] = []
    target = f"http://127.0.0.1:{port}"
    cloudflared = find_cloudflared()
    if cloudflared:
        providers.append(
            Provider("Cloudflare", (cloudflared, "tunnel", "--no-autoupdate", "--url", target), CLOUDFLARE_URL_RE)
        )

        async def prepare() -> tuple[str, dict[str, str]]:
            url, token = await request_quick_tunnel(await cloudflared_user_agent(cloudflared))
            return url, {"TUNNEL_TOKEN": token}  # token buyruq qatorida ko'rinmasligi uchun muhit orqali

        edges = tuple(arg for ip in CLOUDFLARE_EDGE_IPS for arg in ("--edge", f"{ip}:7844"))
        providers.append(
            Provider(
                "Cloudflare (DNS'siz)",
                (cloudflared, "tunnel", "--no-autoupdate", "--ha-connections", "2", *edges, "--url", target, "run"),
                CLOUDFLARE_URL_RE,
                prepare=prepare,
                ready_re=CLOUDFLARE_READY_RE,
                timeout=90.0,
            )
        )
    ssh = shutil.which("ssh")
    if ssh:
        known = Path("data") / "tunnel_known_hosts"
        with contextlib.suppress(OSError):
            known.parent.mkdir(exist_ok=True)
        providers.append(
            Provider(
                "localhost.run",
                (
                    ssh, "-T",
                    "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", f'UserKnownHostsFile="{known.resolve().as_posix()}"',
                    "-o", "ConnectTimeout=15",
                    "-o", "ServerAliveInterval=20",
                    "-o", "ServerAliveCountMax=3",
                    "-o", "ExitOnForwardFailure=yes",
                    "-o", "LogLevel=ERROR",
                    "-R", f"80:127.0.0.1:{port}",
                    "nokey@localhost.run",
                ),
                LOCALHOST_RUN_URL_RE,
            )
        )
    return providers


def _clean(line: str) -> str:
    return TIMESTAMP_RE.sub("", line.strip()).replace('\\"', '"')[:220]


async def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), 5)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        await proc.wait()


class Tunnel:
    """Tunnelni fonda ochadi, kuzatadi va uzilsa qayta ochadi. Har o'zgarishda `on_change(url | None)`."""

    def __init__(
        self,
        port: int,
        on_change: OnChange | None = None,
        providers: list[Provider] | None = None,
        open_timeout: float = 40.0,
        retry_delay: float = 15.0,
        max_delay: float = 120.0,
    ) -> None:
        self.port = port
        self.on_change = on_change
        self.providers = providers if providers is not None else detect_providers(port)
        self.open_timeout = open_timeout
        self.retry_delay = retry_delay
        self.max_delay = max_delay
        self.process: asyncio.subprocess.Process | None = None
        self.provider: Provider | None = None
        self.url: str | None = None
        self._task: asyncio.Task | None = None
        self._notified: object = object()  # hali hech narsa xabar qilinmagan
        self._hints: set[str] = set()  # har bir maslahat bir marta chiqariladi
        self._last_reason: dict[str, str] = {}  # bir xil xato har urinishda qaytarilmasin

    @property
    def available(self) -> bool:
        return bool(self.providers)

    def start(self) -> None:
        if self.available and not self._task:
            self._task = asyncio.create_task(self._run(), name="https-tunnel")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self.process:
            await _kill(self.process)

    async def open(self) -> str | None:
        """Provayderlarni navbat bilan sinaydi; birinchi ishlagan manzilni qaytaradi."""
        hints: list[str] = []
        for provider in self.providers:
            url, reason = await self._try(provider)
            if url:
                self.provider, self.url = provider, url
                self._last_reason.clear()
                return url
            hint = hint_for(reason)
            if hint and hint not in hints and hint not in self._hints:
                hints.append(hint)
            if self._last_reason.get(provider.name) == reason:
                log.debug("%s tunnel hali ham ochilmadi: %s", provider.name, reason)
                continue
            self._last_reason[provider.name] = reason
            log.debug("%s tunnel ochilmadi: %s", provider.name, reason)
            print(f"⚠️ {provider.name} tunnel ochilmadi: {reason}")
        for hint in hints:  # maslahat faqat hech bir usul ishlamaganda (va bir marta) chiqadi
            self._hints.add(hint)
            print(hint)
        return None

    async def _try(self, provider: Provider) -> tuple[str | None, str]:
        known_url, env = None, None
        if provider.prepare:
            try:
                known_url, extra = await asyncio.wait_for(provider.prepare(), 45)
            except TimeoutError:
                return None, "Cloudflare API 45 soniyada javob bermadi"
            except Exception as exc:  # noqa: BLE001 - tarmoq/javob xatolari: keyingi usulga o'tamiz
                return None, _clean(str(exc)) or exc.__class__.__name__
            env = {**os.environ, **extra}
        try:
            proc = await asyncio.create_subprocess_exec(
                *provider.argv,
                stdin=asyncio.subprocess.PIPE,  # ssh uchun: stdin yopilsa sessiya ham yopiladi
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        except OSError as exc:  # masalan WinError 193: fayl Windows dasturi emas
            return None, f"dastur ishga tushmadi ({exc})"
        lines: deque[str] = deque(maxlen=6)

        async def read_url() -> str | None:
            assert proc.stdout
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    return None
                line = raw.decode(errors="replace")
                if known_url and provider.ready_re:
                    if provider.ready_re.search(line):
                        return known_url
                else:
                    match = provider.url_re.search(line)
                    if match:
                        return match.group(0)
                if line.strip():
                    lines.append(_clean(line))

        timeout = provider.timeout or self.open_timeout
        try:
            url = await asyncio.wait_for(read_url(), timeout)
        except TimeoutError:
            url = None
            lines.append(f"{timeout:.0f} soniyada ulanib bo'lmadi")
        if url:
            self.process = proc
            return url, ""
        await _kill(proc)
        reason = next((x for x in reversed(lines) if ERROR_RE.search(x)), lines[-1] if lines else "noma'lum sabab")
        return None, reason

    async def _follow(self) -> None:
        """Jarayon chiqishini o'qib turadi (bufer to'lmasligi uchun) va manzil o'zgarsa xabar beradi."""
        proc, provider = self.process, self.provider
        assert proc and proc.stdout and provider
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            match = provider.url_re.search(raw.decode(errors="replace"))
            if match and match.group(0) != self.url:
                self.url = match.group(0)
                await self._notify(self.url)
        await proc.wait()

    async def _notify(self, url: str | None) -> None:
        if url == self._notified:
            return
        self._notified = url
        if self.on_change:
            try:
                await self.on_change(url)
            except Exception:
                log.exception("Tunnel manzili o'zgarishini qayta ishlashda xato")

    async def _run(self) -> None:
        delay = self.retry_delay
        announced_down = False
        while True:
            url = await self.open()
            if url:
                delay = self.retry_delay
                print(f"🔒 HTTPS tunnel ochildi ({self.provider.name if self.provider else '?'}): {url}")
                await self._notify(url)
                await self._follow()
                log.warning("HTTPS tunnel uzildi — qayta ochilmoqda")
                print("⚠️ HTTPS tunnel uzildi — qayta ochilmoqda...")
                self.url = None
                announced_down = False
                continue
            await self._notify(None)  # buzuq havola menyuda qolmasin
            if "no-ssh" not in self._hints and not any(p.name == "localhost.run" for p in self.providers):
                self._hints.add("no-ssh")
                print("   ℹ️ Zaxira tunnel uchun ssh topilmadi (Windows: Sozlamalar > Tizim > Qo'shimcha imkoniyatlar"
                      " > OpenSSH Client).")
            if not announced_down:
                announced_down = True
                print(
                    "   📵 Ilova tugmasi vaqtincha yashirildi, bot chat rejimida ishlayveradi. Tunnel fonda qayta"
                    " sinab ko'riladi (har 15 soniya – 2 daqiqada) va ochilishi bilan tugma o'zi qaytadi."
                )
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.max_delay)
