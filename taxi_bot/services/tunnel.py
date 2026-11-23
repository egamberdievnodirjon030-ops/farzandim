"""Kompyuterda ishlaganda Telegram Mini App uchun HTTPS manzil: Cloudflare "quick tunnel".

`cloudflared` o'rnatilgan bo'lsa (yoki loyiha papkasida cloudflared.exe turgan bo'lsa), bepul
https://xxxx.trycloudflare.com manzili avtomatik ochiladi va bot menyusiga yoziladi.
Tunnel ochilmasa ham bot ishlashda davom etadi — faqat ilova (Mini App) ochilmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
MIN_SIZE = 5_000_000  # haqiqiy cloudflared ~30–60 MB; kichik fayl — to'liq yuklanmagan yoki HTML sahifa


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


class QuickTunnel:
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: asyncio.subprocess.Process | None = None
        self.url: str | None = None

    async def start(self, timeout: float = 40.0) -> str | None:
        binary = find_cloudflared()
        if not binary:
            return None
        try:
            self.process = await asyncio.create_subprocess_exec(
                binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:  # masalan WinError 193: fayl Windows dasturi emas
            log.warning("cloudflared ishga tushmadi: %s", exc)
            print(f"⚠️ cloudflared ishga tushmadi ({exc}). Bot chat rejimida ishlaydi, ilova ochilmaydi.")
            return None
        try:
            self.url = await asyncio.wait_for(self._read_url(), timeout)
        except TimeoutError:
            log.warning("cloudflared manzil bermadi (%s s)", timeout)
        if not self.url:
            print("⚠️ HTTPS tunnel ochilmadi (internet yoki tarmoq cheklovi). Bot chat rejimida ishlaydi.")
            await self.stop()
            return None
        asyncio.create_task(self._drain(), name="cloudflared-log")
        return self.url

    async def _read_url(self) -> str | None:
        assert self.process and self.process.stderr
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return None
            match = URL_RE.search(line.decode(errors="replace"))
            if match:
                return match.group(0)

    async def _drain(self) -> None:
        if self.process and self.process.stderr:
            while await self.process.stderr.readline():
                pass

    async def stop(self) -> None:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
