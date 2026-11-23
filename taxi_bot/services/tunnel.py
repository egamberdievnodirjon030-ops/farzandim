"""Kompyuterda ishlaganda Telegram Mini App uchun HTTPS manzil: Cloudflare "quick tunnel".

`cloudflared` o'rnatilgan bo'lsa (yoki loyiha papkasida cloudflared.exe turgan bo'lsa), bepul
https://xxxx.trycloudflare.com manzili avtomatik ochiladi va bot menyusiga yoziladi.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_cloudflared() -> str | None:
    for candidate in ("cloudflared", "cloudflared.exe"):
        found = shutil.which(candidate)
        if found:
            return found
        local = Path(candidate)
        if local.exists():
            return str(local.resolve())
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
        self.process = await asyncio.create_subprocess_exec(
            binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        try:
            self.url = await asyncio.wait_for(self._read_url(), timeout)
        except TimeoutError:
            log.warning("cloudflared manzil bermadi (%s s)", timeout)
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
