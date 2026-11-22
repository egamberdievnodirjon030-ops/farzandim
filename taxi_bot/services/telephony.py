"""Haydovchi va yo'lovchini kompaniya raqami orqali bog'lash (raqamlar yashirin).

Ishlash tartibi (callback / "click-to-call"):
  1. ATS (PBX) kompaniya raqamidan tugmani bosgan tomonga qo'ng'iroq qiladi;
  2. u javob bergach, ATS ikkinchi tomonga ham kompaniya raqamidan qo'ng'iroq qilib, ularni ulaydi.
Natijada hech kim boshqasining shaxsiy raqamini ko'rmaydi.

Provayderlar:
  * zadarma  — Zadarma API (/v1/request/callback/)
  * webhook  — o'zingizning ATS (Asterisk, OnlinePBX, ...) uchun JSON POST
  * operator — dispetcherga xabar boradi, u kompaniya telefonidan ulab beradi
  * none     — o'chirilgan
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlencode

import aiohttp

from ..config import Settings

log = logging.getLogger(__name__)


def normalize_phone(raw: str | None) -> str | None:
    """Raqamni +998XXXXXXXXX ko'rinishiga keltiradi."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:  # 90 123 45 67
        digits = "998" + digits
    if len(digits) < 10:
        return None
    return "+" + digits


@dataclass(frozen=True, slots=True)
class CallResult:
    ok: bool
    mode: str  # callback | operator | disabled | error
    detail: str = ""


class TelephonyService:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.provider = settings.call_provider
        self._timeout = aiohttp.ClientTimeout(total=8)

    async def connect(self, first: str, second: str, order_id: int) -> CallResult:
        """`first` — birinchi qo'ng'iroq qilinadigan (tugmani bosgan) tomon."""
        if self.provider == "zadarma":
            return await self._zadarma(first, second)
        if self.provider == "webhook":
            return await self._webhook(first, second, order_id)
        if self.provider == "operator":
            return CallResult(True, "operator")
        return CallResult(False, "disabled")

    # -- Zadarma -------------------------------------------------------------------
    @staticmethod
    def zadarma_signature(method: str, params: dict[str, str], key: str, secret: str) -> str:
        query = urlencode(sorted(params.items()))
        md5 = hashlib.md5(query.encode()).hexdigest()
        digest = hmac.new(secret.encode(), f"{method}{query}{md5}".encode(), hashlib.sha1).hexdigest()
        return f"{key}:{base64.b64encode(digest.encode()).decode()}"

    async def _zadarma(self, first: str, second: str) -> CallResult:
        if not (self.s.zadarma_key and self.s.zadarma_secret):
            return CallResult(False, "error", "Zadarma kalitlari sozlanmagan")
        method = "/v1/request/callback/"
        params = {"from": first.lstrip("+"), "to": second.lstrip("+")}
        if self.s.zadarma_sip:
            params["sip"] = self.s.zadarma_sip
        auth = self.zadarma_signature(
            method, params, self.s.zadarma_key, self.s.zadarma_secret.get_secret_value()
        )
        url = f"https://api.zadarma.com{method}?{urlencode(sorted(params.items()))}"
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, headers={"Authorization": auth}) as resp:
                    data = await resp.json(content_type=None)
            if data.get("status") == "success":
                return CallResult(True, "callback")
            return CallResult(False, "error", str(data.get("message", data)))
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            log.warning("Zadarma xatosi: %s", exc)
            return CallResult(False, "error", str(exc))

    # -- Webhook (o'z ATS) ----------------------------------------------------------
    async def _webhook(self, first: str, second: str, order_id: int) -> CallResult:
        if not self.s.call_webhook_url:
            return CallResult(False, "error", "CALL_WEBHOOK_URL sozlanmagan")
        payload = {"order_id": order_id, "first": first, "second": second}
        headers = {}
        if self.s.call_webhook_secret:
            headers["X-Taxi-Secret"] = self.s.call_webhook_secret.get_secret_value()
        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session, session.post(
                self.s.call_webhook_url, json=payload, headers=headers
            ) as resp:
                if 200 <= resp.status < 300:
                    return CallResult(True, "callback")
                return CallResult(False, "error", f"HTTP {resp.status}")
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.warning("Call webhook xatosi: %s", exc)
            return CallResult(False, "error", str(exc))
