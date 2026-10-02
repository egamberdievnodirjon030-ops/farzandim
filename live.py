"""Real vaqtdagi voqealar (Server-Sent Events): bildirishnoma, yangi xabar, e'lon, hujjat — ilova ochiq bo'lsa darhol.

Ilova /api/events ga bitta uzoq ulanish ochadi (fetch orqali — Telegram imzosi sarlavhada uzatiladi, standart
EventSource esa sarlavha yubora olmaydi). Server voqeani foydalanuvchining barcha ochiq ulanishlariga yuboradi;
ulanish yo'q bo'lsa voqea shunchaki tashlab yuboriladi — ilova ochilganda ma'lumotni API dan oladi.
Har 25 soniyada «ping» — proksi va Cloudflare ulanishni uzib qo'ymasligi uchun.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from aiohttp import web

log = logging.getLogger("live")
PING = 25
_subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
_closing = False


def publish(uid: int, event: dict) -> int:
    """Voqeani foydalanuvchining ochiq ulanishlariga yuboradi. Qaytaradi: nechta ulanishga ketdi."""
    n = 0
    for q in list(_subs.get(uid, ())):
        try:
            q.put_nowait(event)
            n += 1
        except asyncio.QueueFull:  # juda sekin mijoz — voqealar to'planib qolmasin
            pass
    return n


def publish_many(uids, event: dict) -> int:
    return sum(publish(u, event) for u in set(uids))


def online(uid: int) -> bool:
    return bool(_subs.get(uid))


async def stream(request: web.Request) -> web.StreamResponse:
    uid = request["user"]["id"]
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache",
                                       "X-Accel-Buffering": "no", "Connection": "keep-alive"})
    await resp.prepare(request)
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subs[uid].add(q)
    try:
        await resp.write(b"retry: 5000\nevent: hello\ndata: {}\n\n")
        while not _closing:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=PING)
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")
                continue
            if ev is None:  # server to'xtamoqda
                break
            await resp.write(f"event: {ev.get('type', 'message')}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
    except (ConnectionResetError, asyncio.CancelledError, RuntimeError):
        pass
    finally:
        _subs[uid].discard(q)
        if not _subs[uid]:
            _subs.pop(uid, None)
    return resp


async def close_all(app=None) -> None:
    """Server to'xtaganda barcha ochiq ulanishlarni darhol yopadi (aks holda aiohttp ularni 60 soniya kutadi)."""
    global _closing
    _closing = True
    for qs in list(_subs.values()):
        for q in list(qs):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
