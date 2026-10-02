"""Markazlashgan loglar va xatolar haqida darhol xabar.

  logs/bot.log     — barcha yozuvlar (INFO va yuqori), aylanma: 5 MB × 10 fayl
  logs/errors.log  — faqat ogohlantirish va xatolar (WARNING va yuqori), aylanma: 5 MB × 10 fayl
Har bir yozuvda kurs va foydalanuvchi: «[3-kurs u=8634767200]» — qaysi kurs bazasida nima bo'lganini topish oson.

Tizim xatolari (ERROR, CRITICAL) super-admin(lar)ga Telegram orqali darhol yuboriladi. Bir xil xato haqida
ALERT_COOLDOWN_MIN daqiqada bir martadan ko'p xabar yuborilmaydi, soatiga jami 20 tadan ko'p emas — bitta nosozlik
yuzlab xabarga aylanmasin. Fayl formati xatolari (Excel noto'g'ri tuzilgan) — WARNING: jurnalga yoziladi, kurs
koordinatoriga import natijasida aytiladi, lekin super-adminni bezovta qilmaydi.
"""
from __future__ import annotations

import asyncio
import html
import logging
import time
from logging.handlers import RotatingFileHandler

from config import ALERT_COOLDOWN_MIN, LOG_DIR, SUPERADMIN_IDS
from tenancy import current_course, current_user

FORMAT = "%(asctime)s %(levelname)s [%(course)s u=%(uid)s] %(name)s: %(message)s"


class ContextFilter(logging.Filter):
    """Har bir yozuvga joriy kurs va foydalanuvchini qo'shadi."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.course = current_course() or "-"
        record.uid = current_user.get() or "-"
        return True


class TelegramAlertHandler(logging.Handler):
    """ERROR va undan yuqori yozuvlarni super-adminga yuboradi (navbat orqali — logging sinxron, yuborish asinxron)."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.bot = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.queue: asyncio.Queue | None = None
        self._last: dict[str, float] = {}
        self._sent: list[float] = []

    def attach(self, bot) -> None:
        self.bot = bot
        self.loop = asyncio.get_running_loop()
        self.queue = asyncio.Queue()
        self.loop.create_task(self._worker())

    def emit(self, record: logging.LogRecord) -> None:
        if not self.bot or not self.loop or not SUPERADMIN_IDS or record.name.startswith("aiogram.event"):
            return
        key = f"{record.name}:{record.getMessage()[:120]}"
        now = time.time()
        if now - self._last.get(key, 0) < ALERT_COOLDOWN_MIN * 60:
            return  # bir xil xato — yaqinda xabar berilgan
        self._sent = [t for t in self._sent if now - t < 3600]
        if len(self._sent) >= 20:
            return  # soatiga ko'pi bilan 20 ta xabar
        self._last[key] = now
        self._sent.append(now)
        exc = ""
        if record.exc_info and record.exc_info[1] is not None:
            exc = f"{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
        text = (f"🚨 <b>Tizim xatosi</b> ({record.levelname})\n"
                f"Kurs: <code>{html.escape(str(getattr(record, 'course', '-')))}</code> · "
                f"foydalanuvchi: <code>{html.escape(str(getattr(record, 'uid', '-')))}</code>\n"
                f"Joy: <code>{html.escape(record.name)}</code>\n\n{html.escape(record.getMessage()[:700])}"
                + (f"\n<code>{html.escape(exc[:500])}</code>" if exc else "")
                + "\n\nBatafsil: /xatolar")
        try:
            if asyncio.get_running_loop() is self.loop:
                self.queue.put_nowait(text)
                return
        except RuntimeError:
            pass
        self.loop.call_soon_threadsafe(self.queue.put_nowait, text)  # boshqa oqimdan (masalan, asyncio.to_thread)

    async def _worker(self) -> None:
        while True:
            text = await self.queue.get()
            for uid in list(SUPERADMIN_IDS):
                try:
                    await self.bot.send_message(uid, text)
                except Exception:  # xabar yuborib bo'lmasa — jim (aks holda xato haqidagi xabar yana xato beradi)
                    pass


alert_handler = TelegramAlertHandler()


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(FORMAT)
    ctx = ContextFilter()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    console = logging.StreamHandler()
    main = RotatingFileHandler(LOG_DIR / "bot.log", maxBytes=5_000_000, backupCount=10, encoding="utf-8")
    errors = RotatingFileHandler(LOG_DIR / "errors.log", maxBytes=5_000_000, backupCount=10, encoding="utf-8")
    errors.setLevel(logging.WARNING)
    for h in (console, main, errors, alert_handler):
        h.addFilter(ctx)
        h.setFormatter(fmt)
        root.addHandler(h)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


def tail(path, lines: int = 40, course: str | None = None) -> str:
    """Log faylining oxirgi qatorlari (kurs bo'yicha filtr bilan)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = f.readlines()
    except FileNotFoundError:
        return ""
    if course:
        data = [x for x in data if f"[{course} " in x]
    return "".join(data[-lines:])


def errors_since(hours: int = 24) -> int:
    """So'nggi soatlardagi ERROR yozuvlari soni (kunlik hisobot uchun)."""
    from datetime import datetime, timedelta
    edge = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    n = 0
    for line in tail(LOG_DIR / "errors.log", 5000).splitlines():
        if line[:19] >= edge and (" ERROR " in line or " CRITICAL " in line):
            n += 1
    return n
