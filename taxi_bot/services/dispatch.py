"""Buyurtmani haydovchilarga tarqatish dvigateli (to'lqinlar bo'yicha).

Har bir qidirilayotgan buyurtma uchun alohida asyncio vazifasi ishlaydi:

    diapazon 1 (1 km)  -> ustuvor (yuqori reyting) haydovchilar -> 10 s -> qolganlar -> 60 s kutish
                          (kutish davomida shu radiusda yangi bo'shaganlar ham darhol taklif oladi)
    diapazon 2 (2 km)  -> yangi haydovchilar qo'shiladi (oldingilar ham ko'rishda davom etadi)
    ...
    diapazonlar tugasa -> eng katta radiusda har 15 s qayta skanerlash (yangi bo'shaganlar uchun)
    umumiy vaqt tugasa -> "haydovchi topilmadi"

Diapazonda hech kim bo'lmasa — kutilmaydi, darhol keyingisiga o'tiladi.
To'lqindagi hamma rad etsa — muddatidan oldin keyingi to'lqinga o'tiladi.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ..db.models import OrderStatus, utcnow
from .matching import select_wave

if TYPE_CHECKING:
    from .taxi import TaxiService

log = logging.getLogger(__name__)


class DispatchEngine:
    def __init__(self, svc: TaxiService) -> None:
        self.svc = svc
        self._tasks: dict[int, asyncio.Task] = {}
        self._events: dict[int, asyncio.Event] = {}

    # -- boshqaruv -----------------------------------------------------------------
    def start(self, order_id: int) -> None:
        task = self._tasks.get(order_id)
        if task and not task.done():
            self.wake(order_id)
            return
        self._events[order_id] = asyncio.Event()
        task = asyncio.create_task(self._run(order_id), name=f"dispatch-{order_id}")
        self._tasks[order_id] = task
        task.add_done_callback(lambda _t, oid=order_id: self._cleanup(oid, _t))

    def _cleanup(self, order_id: int, task: asyncio.Task) -> None:
        if self._tasks.get(order_id) is task:
            self._tasks.pop(order_id, None)
            self._events.pop(order_id, None)

    def wake(self, order_id: int) -> None:
        """Holat o'zgardi (qabul/rad/bekor) — kutayotgan sikl darhol tekshiradi."""
        event = self._events.get(order_id)
        if event:
            event.set()

    def is_running(self, order_id: int) -> bool:
        task = self._tasks.get(order_id)
        return bool(task and not task.done())

    async def stop_all(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_idle(self, order_id: int) -> None:
        """Testlar uchun: buyurtma qidiruvi tugashini kutish."""
        task = self._tasks.get(order_id)
        if task:
            await asyncio.gather(task, return_exceptions=True)

    # -- asosiy sikl -------------------------------------------------------------------
    async def _run(self, order_id: int) -> None:
        s = self.svc.settings
        loop = asyncio.get_running_loop()
        try:
            order = await self.svc.get_order(order_id)
            if order is None or order.status != OrderStatus.SEARCHING:
                return
            search_round = order.search_round
            elapsed = max(0.0, (utcnow() - order.search_started_at).total_seconds())
            deadline = loop.time() + max(0.0, s.search_timeout_sec - elapsed)
            radii = [r * 1000 for r in s.wave_radii_km]
            wave = 0

            while True:
                order = await self.svc.get_order(order_id)
                if (
                    order is None
                    or order.status != OrderStatus.SEARCHING
                    or order.search_round != search_round
                ):
                    return
                if loop.time() >= deadline:
                    await self.svc.on_search_failed(order_id, search_round)
                    return

                exhausted = wave >= len(radii)
                radius = radii[min(wave, len(radii) - 1)]
                candidates = await self.svc.find_candidates(order, radius)
                priority, rest = select_wave(candidates, radius, s.priority_rating)
                wave_driver_ids: list[int] = []

                if priority:
                    wave_driver_ids += await self.svc.send_offers(order, priority, wave)
                    if rest:
                        # Yuqori reytingli haydovchilarga qisqa ustunlik vaqti
                        headstart = min(s.priority_headstart_sec, deadline - loop.time())
                        if await self._sleep(order_id, search_round, headstart, None) == "stop":
                            return
                        order = await self.svc.get_order(order_id)
                        if order is None:
                            return
                if rest:
                    wave_driver_ids += await self.svc.send_offers(order, rest, wave)

                await self.svc.on_search_progress(order_id, wave, radius)

                if exhausted:
                    pause = s.rescan_interval_sec
                elif wave_driver_ids:
                    pause = s.wave_timeout_sec
                else:
                    pause = 0.0  # diapazon bo'sh — darhol kengaytiramiz
                wave_end = loop.time() + min(pause, max(0.0, deadline - loop.time()))
                while True:
                    remaining = wave_end - loop.time()
                    if remaining <= 0:
                        break
                    outcome = await self._sleep(
                        order_id,
                        search_round,
                        min(remaining, s.rescan_interval_sec),
                        wave_driver_ids or None,
                    )
                    if outcome == "stop":
                        return
                    if outcome == "declined":
                        break  # to'lqindagilarning hammasi rad etdi — kutmasdan kengaytiramiz
                    # To'lqin davomida shu radiusda yangi bo'shagan haydovchilar ham darhol oladi
                    order = await self.svc.get_order(order_id)
                    if order is None or order.status != OrderStatus.SEARCHING:
                        return
                    newcomers = await self.svc.find_candidates(order, radius)
                    priority, rest = select_wave(newcomers, radius, s.priority_rating)
                    if priority or rest:
                        wave_driver_ids += await self.svc.send_offers(order, priority + rest, wave)
                wave += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Dispatch xatosi (buyurtma #%s)", order_id)
            try:
                await self.svc.on_search_failed(order_id, None)
            except Exception:
                log.exception("on_search_failed xatosi")

    async def _sleep(
        self,
        order_id: int,
        search_round: int,
        seconds: float,
        wave_driver_ids: list[int] | None,
    ) -> str:
        """Kutadi. Natija: `stop` — qidiruv tugadi (olindi/bekor), `declined` — hamma rad etdi, `timeout`."""
        loop = asyncio.get_running_loop()
        end = loop.time() + max(0.0, seconds)
        event = self._events.setdefault(order_id, asyncio.Event())
        while True:
            event.clear()
            order = await self.svc.get_order(order_id)
            if (
                order is None
                or order.status != OrderStatus.SEARCHING
                or order.search_round != search_round
            ):
                return "stop"
            if wave_driver_ids and await self.svc.all_declined(order_id, search_round, wave_driver_ids):
                return "declined"
            remaining = end - loop.time()
            if remaining <= 0:
                return "timeout"
            try:
                await asyncio.wait_for(event.wait(), timeout=remaining)
            except TimeoutError:
                return "timeout"
