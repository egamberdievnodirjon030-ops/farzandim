"""Kompyuterda ishlaganda Telegram Mini App uchun HTTPS manzil — bepul tunnel orqali.

1. Cloudflare "quick tunnel" (`cloudflared`; Windows'da start.bat/run.py o'zi yuklab oladi) — asosiy;
2. localhost.run — zaxira: Windows 10/11 ga o'rnatilgan `ssh` orqali, hech narsa yuklab olinmaydi.

`Tunnel.start()` fonda ishlaydi: bot darhol ishga tushadi, tunnel ochilgach menyu tugmasi yangilanadi.
Tunnel uzilsa — qayta ochiladi; ochilmasa — tugma o'chiriladi (buzuq havola qolmaydi).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

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
BLOCKED_RE = re.compile(r"timed out|i/o timeout|refused|unreachable|connection reset", re.IGNORECASE)

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


def detect_providers(port: int) -> list[Provider]:
    providers: list[Provider] = []
    target = f"http://127.0.0.1:{port}"
    cloudflared = find_cloudflared()
    if cloudflared:
        providers.append(
            Provider("Cloudflare", (cloudflared, "tunnel", "--no-autoupdate", "--url", target), CLOUDFLARE_URL_RE)
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
        for provider in self.providers:
            url, reason = await self._try(provider)
            if url:
                self.provider, self.url = provider, url
                self._last_reason.clear()
                return url
            if self._last_reason.get(provider.name) == reason:
                log.debug("%s tunnel hali ham ochilmadi: %s", provider.name, reason)
                continue
            self._last_reason[provider.name] = reason
            log.debug("%s tunnel ochilmadi: %s", provider.name, reason)
            print(f"⚠️ {provider.name} tunnel ochilmadi: {reason}")
            hint = hint_for(reason)
            if hint and hint not in self._hints:
                self._hints.add(hint)
                print(hint)
        return None

    async def _try(self, provider: Provider) -> tuple[str | None, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *provider.argv,
                stdin=asyncio.subprocess.PIPE,  # ssh uchun: stdin yopilsa sessiya ham yopiladi
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
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
                match = provider.url_re.search(line)
                if match:
                    return match.group(0)
                if line.strip():
                    lines.append(_clean(line))

        try:
            url = await asyncio.wait_for(read_url(), self.open_timeout)
        except TimeoutError:
            url = None
            lines.append(f"{self.open_timeout:.0f} soniyada manzil berilmadi")
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
