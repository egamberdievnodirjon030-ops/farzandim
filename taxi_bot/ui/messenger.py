"""Telegramga xabar yuborish qatlami (ikki bot uchun yagona interfeys).

Rich Message yoki xabar effekti qabul qilinmasa — avtomatik oddiy variantga o'tadi,
foydalanuvchi botni bloklagan bo'lsa — jim o'tib ketadi. Shu sabab biznes-logika
Telegram xatolaridan himoyalangan.
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup

from .kit import View

log = logging.getLogger(__name__)

# Xabar effektlari (faqat shaxsiy chatlarda)
EFFECT_PARTY = "5046509860389126442"  # 🎉
EFFECT_LIKE = "5107584321108051014"  # 👍
EFFECT_HEART = "5044134455711629726"  # ❤️

LIVE_PERIOD = 3 * 3600


class Role(StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"


class Messenger:
    def __init__(
        self,
        bots: dict[Role, Bot],
        *,
        rich_enabled: bool = True,
        effects_enabled: bool = True,
        admin_chat_ids: list[int] | None = None,
    ) -> None:
        self.bots = bots
        self.rich_enabled = rich_enabled
        self.effects_enabled = effects_enabled
        self.admin_chat_ids = admin_chat_ids or []
        self._rich_failures = 0

    def bot(self, role: Role) -> Bot:
        return self.bots[role]

    # -- ichki yordamchilar ------------------------------------------------------
    async def _call(self, coro_factory, *, what: str):
        """Telegram chaqiruvini xavfsiz bajaradi (RetryAfter'da bir marta qayta urinadi)."""
        for attempt in range(2):
            try:
                return await coro_factory()
            except TelegramRetryAfter as exc:
                if attempt:
                    raise
                await asyncio.sleep(min(exc.retry_after, 10))
            except TelegramForbiddenError:
                log.info("%s: foydalanuvchi botni bloklagan", what)
                return None
        return None

    def _rich_failed(self, exc: TelegramBadRequest) -> None:
        self._rich_failures += 1
        log.warning("Rich message rad etildi (%s): %s", self._rich_failures, exc.message)
        if self._rich_failures >= 3:
            log.warning("Rich Messages o'chirildi — oddiy kartalar ishlatiladi")
            self.rich_enabled = False

    # -- yuborish --------------------------------------------------------------------
    async def send(
        self,
        role: Role,
        chat_id: int,
        view: View,
        *,
        effect: str | None = None,
        silent: bool = False,
    ) -> int | None:
        bot = self.bot(role)
        effect = effect if self.effects_enabled else None
        attempts: list[tuple[bool, str | None]] = []
        if view.rich is not None and self.rich_enabled:
            attempts.append((True, effect))
        attempts.append((False, effect))
        if effect:
            attempts.append((False, None))

        for use_rich, eff in attempts:
            try:
                if use_rich:
                    msg = await self._call(
                        lambda eff=eff: bot.send_rich_message(
                            chat_id=chat_id,
                            rich_message=view.rich,
                            reply_markup=view.markup,
                            message_effect_id=eff,
                            disable_notification=silent,
                        ),
                        what="send_rich",
                    )
                    self._rich_failures = 0
                else:
                    msg = await self._call(
                        lambda eff=eff: bot.send_message(
                            chat_id=chat_id,
                            text=view.text,
                            reply_markup=view.markup,
                            message_effect_id=eff,
                            disable_notification=silent,
                        ),
                        what="send_message",
                    )
                return msg.message_id if msg else None
            except TelegramBadRequest as exc:
                if use_rich:
                    self._rich_failed(exc)
                elif eff and "effect" in exc.message.lower():
                    self.effects_enabled = False
                else:
                    log.warning("Xabar yuborilmadi (%s): %s", chat_id, exc.message)
                    if not eff:
                        return None
            except TelegramAPIError as exc:
                log.warning("Telegram xatosi (%s): %s", chat_id, exc)
                return None
        return None

    async def edit(self, role: Role, chat_id: int, message_id: int | None, view: View) -> bool:
        """Kartani joyida yangilaydi. Muvaffaqiyatsiz bo'lsa False (chaqiruvchi yangisini yuboradi)."""
        if not message_id:
            return False
        bot = self.bot(role)
        markup = view.markup if isinstance(view.markup, InlineKeyboardMarkup) else None
        variants = [True, False] if (view.rich is not None and self.rich_enabled) else [False]
        for use_rich in variants:
            try:
                if use_rich:
                    await self._call(
                        lambda: bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            rich_message=view.rich,
                            reply_markup=markup,
                        ),
                        what="edit_rich",
                    )
                else:
                    await self._call(
                        lambda: bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=view.text,
                            reply_markup=markup,
                        ),
                        what="edit_text",
                    )
                return True
            except TelegramBadRequest as exc:
                text = exc.message.lower()
                if "not modified" in text:
                    return True
                if "not found" in text or "can't be edited" in text:
                    return False
                if use_rich:
                    self._rich_failed(exc)
                    continue
                log.warning("Xabarni tahrirlab bo'lmadi: %s", exc.message)
                return False
            except TelegramAPIError as exc:
                log.warning("Tahrirlashda xato: %s", exc)
                return False
        return False

    async def replace(
        self,
        role: Role,
        chat_id: int,
        old_message_id: int | None,
        view: View,
        *,
        effect: str | None = None,
    ) -> int | None:
        """Eski kartani o'chirib, yangisini yuboradi — foydalanuvchiga bildirishnoma boradi."""
        new_id = await self.send(role, chat_id, view, effect=effect)
        if old_message_id and new_id:
            await self.delete(role, chat_id, old_message_id)
        return new_id or old_message_id

    async def delete(self, role: Role, chat_id: int, message_id: int | None) -> bool:
        if not message_id:
            return False
        try:
            return bool(
                await self._call(
                    lambda: self.bot(role).delete_message(chat_id=chat_id, message_id=message_id),
                    what="delete",
                )
            )
        except TelegramAPIError:
            return False

    async def notify_admins(self, view: View) -> None:
        for chat_id in self.admin_chat_ids:
            await self.send(Role.DRIVER, chat_id, view)

    # -- jonli joylashuv (yo'lovchiga mashina harakati) -----------------------------
    async def send_live_location(
        self, role: Role, chat_id: int, lat: float, lon: float, heading: int | None = None
    ) -> int | None:
        try:
            msg = await self._call(
                lambda: self.bot(role).send_location(
                    chat_id=chat_id,
                    latitude=lat,
                    longitude=lon,
                    live_period=LIVE_PERIOD,
                    heading=heading if heading and 1 <= heading <= 360 else None,
                    disable_notification=True,
                ),
                what="send_location",
            )
            return msg.message_id if msg else None
        except TelegramAPIError as exc:
            log.warning("Jonli joylashuv yuborilmadi: %s", exc)
            return None

    async def edit_live_location(
        self,
        role: Role,
        chat_id: int,
        message_id: int,
        lat: float,
        lon: float,
        heading: int | None = None,
    ) -> None:
        try:
            await self._call(
                lambda: self.bot(role).edit_message_live_location(
                    chat_id=chat_id,
                    message_id=message_id,
                    latitude=lat,
                    longitude=lon,
                    heading=heading if heading and 1 <= heading <= 360 else None,
                ),
                what="edit_live",
            )
        except TelegramAPIError:
            pass

    # -- anonim yozishmalar --------------------------------------------------------
    async def relay_voice(
        self, from_role: Role, file_id: str, to_role: Role, chat_id: int, caption: str
    ) -> bool:
        """Ovozli xabarni boshqa botga ko'chiradi (forward emas — muallif ko'rinmaydi)."""
        try:
            if self.bot(from_role) is self.bot(to_role):
                await self.bot(to_role).send_voice(chat_id=chat_id, voice=file_id, caption=caption)
                return True
            src = self.bot(from_role)
            file = await src.get_file(file_id)
            data = await src.download_file(file.file_path)
            if data is None:
                return False
            await self.bot(to_role).send_voice(
                chat_id=chat_id,
                voice=BufferedInputFile(data.read(), filename="voice.ogg"),
                caption=caption,
            )
            return True
        except TelegramAPIError as exc:
            log.warning("Ovozli xabar uzatilmadi: %s", exc)
            return False
