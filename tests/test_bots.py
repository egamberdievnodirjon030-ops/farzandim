"""Botlarning to'liq end-to-end sinovi: Telegram server o'rniga soxta sessiya."""

from __future__ import annotations

import asyncio
import itertools
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    Contact,
    Location,
    Message,
    Update,
    User,
)

from taxi_bot.app import build_dispatcher
from taxi_bot.db import Database
from taxi_bot.db.models import Driver, OrderStatus
from taxi_bot.services.taxi import TaxiService
from taxi_bot.ui.messenger import Messenger, Role

from .conftest import make_settings, offset

PASSENGER = User(id=7001, is_bot=False, first_name="Jasur")
DRIVER = User(id=7002, is_bot=False, first_name="Bekzod", last_name="Karimov")
ADMIN = User(id=999, is_bot=False, first_name="Admin")
PASSENGER_PHONE = "+998935556677"
DRIVER_PHONE = "+998901112233"


def _j(method: TelegramMethod) -> str:
    return json.dumps(method.model_dump(exclude_none=True), ensure_ascii=False, default=str)


class MockSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[int, TelegramMethod]] = []
        self._ids = itertools.count(1000)

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.requests.append((bot.id, method))
        name = type(method).__name__
        if name.startswith(("Send",)) and name != "SendChatAction":
            chat_id = getattr(method, "chat_id", 0)
            return Message(
                message_id=next(self._ids),
                date=datetime.now(UTC),
                chat=Chat(id=chat_id, type="private"),
                text=getattr(method, "text", None),
            )
        if name == "GetMe":
            return User(id=bot.id, is_bot=True, first_name="bot")
        if name.startswith("Edit"):
            return True
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def close(self) -> None:
        pass

    # yordamchilar
    def calls(self, bot_id: int | None = None, name: str | None = None) -> list[TelegramMethod]:
        return [
            m
            for b, m in self.requests
            if (bot_id is None or b == bot_id) and (name is None or type(m).__name__ == name)
        ]

    def dump(self, bot_id: int, chat_id: int | None = None) -> str:
        out = []
        for b, m in self.requests:
            if b != bot_id:
                continue
            if chat_id is not None and getattr(m, "chat_id", None) != chat_id:
                continue
            out.append(_j(m))
        return "\n".join(out)


class Harness:
    def __init__(self, svc: TaxiService, dp, passenger_bot: Bot, driver_bot: Bot, session: MockSession):
        self.svc, self.dp, self.pbot, self.dbot, self.session = svc, dp, passenger_bot, driver_bot, session
        self._uid = itertools.count(1)
        self._mid = itertools.count(1)

    def _msg(self, user: User, **kwargs) -> Message:
        return Message(
            message_id=next(self._mid),
            date=datetime.now(UTC),
            chat=Chat(id=user.id, type="private"),
            from_user=user,
            **kwargs,
        )

    async def send(self, bot: Bot, user: User, **kwargs) -> None:
        await self.dp.feed_update(bot, Update(update_id=next(self._uid), message=self._msg(user, **kwargs)))

    async def edit(self, bot: Bot, user: User, **kwargs) -> None:
        msg = self._msg(user, edit_date=int(datetime.now(UTC).timestamp()), **kwargs)
        await self.dp.feed_update(bot, Update(update_id=next(self._uid), edited_message=msg))

    async def press(self, bot: Bot, user: User, data: str, message_id: int = 1) -> None:
        msg = Message(
            message_id=message_id,
            date=datetime.now(UTC),
            chat=Chat(id=user.id, type="private"),
            from_user=User(id=bot.id, is_bot=True, first_name="bot"),
            text="card",
        )
        cq = CallbackQuery(id=str(next(self._uid)), from_user=user, chat_instance="x", data=data, message=msg)
        await self.dp.feed_update(bot, Update(update_id=next(self._uid), callback_query=cq))

    def last_text(self, bot: Bot, chat_id: int) -> str:
        for m in reversed(self.session.calls(bot.id)):
            if getattr(m, "chat_id", None) == chat_id and hasattr(m, "text") and getattr(m, "text", None):
                return m.text  # type: ignore[attr-defined]
            if getattr(m, "chat_id", None) == chat_id and type(m).__name__ == "SendRichMessage":
                return _j(m)
        return ""

    def callbacks(self, bot: Bot, chat_id: int) -> list[str]:
        """Shu chatga yuborilgan barcha inline tugmalar callback_data'lari."""
        result = []
        for m in self.session.calls(bot.id):
            if getattr(m, "chat_id", None) != chat_id:
                continue
            markup = getattr(m, "reply_markup", None)
            for row in getattr(markup, "inline_keyboard", None) or []:
                for b in row:
                    if b.callback_data:
                        result.append(b.callback_data)
        return result


@pytest.fixture(autouse=True)
def no_logged_errors(caplog):
    """Xato handler istisnolarni yutib yuboradi — shuning uchun loglarda xato yo'qligini tekshiramiz."""
    yield
    errors = [r for r in caplog.records if r.levelno >= 30 and r.name.startswith(("taxi_bot", "aiogram"))]
    assert not errors, [r.getMessage() for r in errors]


@pytest.fixture
async def harness(tmp_path):
    async def factory(single: bool = False, **overrides) -> Harness:
        settings = make_settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/bot{'1' if single else '2'}.db",
            passenger_bot_token="111:AAA",
            driver_bot_token="" if single else "222:BBB",
            require_live_location=True,
            priority_headstart_sec=0,
            **overrides,
        )
        session = MockSession()
        defaults = DefaultBotProperties(parse_mode="HTML")
        pbot = Bot("111:AAA", session=session, default=defaults)
        dbot = pbot if single else Bot("222:BBB", session=session, default=defaults)
        db = Database(settings.database_url)
        await db.create_all()
        messenger = Messenger({Role.PASSENGER: pbot, Role.DRIVER: dbot}, admin_chat_ids=[ADMIN.id])
        svc = TaxiService(settings, db, messenger)
        roles = None if single else {pbot.id: Role.PASSENGER, dbot.id: Role.DRIVER}
        dp = build_dispatcher(svc, MemoryStorage(), roles)
        h = Harness(svc, dp, pbot, dbot, session)
        made.append((svc, db))
        return h

    made: list = []
    yield factory
    for svc, db in made:
        await svc.close()
        await db.close()


async def register_and_approve_driver(h: Harness, location):
    dbot = h.dbot
    await h.send(dbot, DRIVER, text="/start")
    assert "telefon raqamingizni" in h.last_text(dbot, DRIVER.id)
    await h.send(dbot, DRIVER, contact=Contact(phone_number=DRIVER_PHONE[1:], first_name="B", user_id=DRIVER.id))
    await h.send(dbot, DRIVER, text="Bekzod Karimov")
    await h.send(dbot, DRIVER, text="Cobalt")
    await h.send(dbot, DRIVER, text="Oq")
    await h.send(dbot, DRIVER, text="01a777bc")
    assert "01 A 777 BC" in h.last_text(dbot, DRIVER.id)
    await h.press(dbot, DRIVER, "d:regok:0:0")
    driver = await h.svc.get_driver_by_tg(DRIVER.id)
    assert driver is not None and driver.status == "pending"
    # Admin arizani ko'radi va tasdiqlaydi
    admin_cb = [c for c in h.callbacks(dbot, ADMIN.id) if c.startswith("a:ok")]
    assert admin_cb
    await h.press(dbot, ADMIN, admin_cb[-1])
    assert "tasdiqlandi" in h.last_text(dbot, DRIVER.id)
    async with h.svc.db.session() as s:
        (await s.get(Driver, driver.id)).balance = 30_000
    # Oddiy nuqta qabul qilinmaydi — jonli joylashuv kerak
    await h.send(dbot, DRIVER, location=Location(latitude=location[0], longitude=location[1]))
    assert "Jonli joylashuvni ulashish" in h.last_text(dbot, DRIVER.id)
    await h.send(
        dbot,
        DRIVER,
        location=Location(latitude=location[0], longitude=location[1], live_period=0x7FFFFFFF, horizontal_accuracy=5),
    )
    assert "liniyadasiz" in h.last_text(dbot, DRIVER.id)
    return await h.svc.get_driver_by_tg(DRIVER.id)


async def test_end_to_end_two_bots(harness, center):
    h = await harness()
    pbot, dbot = h.pbot, h.dbot
    driver = await register_and_approve_driver(h, offset(*center, 300, 200))
    assert driver.is_online

    # --- Yo'lovchi: /start -> raqam -> joylashuv -> manzil -> tasdiq
    await h.send(pbot, PASSENGER, text="/start")
    assert "telefon raqamingizni" in h.last_text(pbot, PASSENGER.id)
    await h.send(pbot, PASSENGER, contact=Contact(phone_number=PASSENGER_PHONE, first_name="J", user_id=PASSENGER.id))
    assert "Taksi chaqirish" in h.last_text(pbot, PASSENGER.id)
    await h.send(pbot, PASSENGER, location=Location(latitude=center[0], longitude=center[1], horizontal_accuracy=12))
    assert "Qayerga borasiz" in h.last_text(pbot, PASSENGER.id)
    dest = offset(*center, 3000, 1000)
    await h.send(pbot, PASSENGER, location=Location(latitude=dest[0], longitude=dest[1]))
    quote = h.last_text(pbot, PASSENGER.id)
    assert "Buyurtmani tasdiqlang" in quote and '"type": "map"' in quote  # Rich Message + xarita bloki
    await h.send(pbot, PASSENGER, text="Oq darvoza oldida")  # izoh
    await h.press(pbot, PASSENGER, "p:confirm:0:0")

    # --- Haydovchiga taklif keladi (yangi dizayn: rangli tugmalar)
    order = await h.svc.active_order((await h.svc.get_passenger_by_tg(PASSENGER.id)).id)
    assert order is not None and order.comment == "Oq darvoza oldida"
    for _ in range(100):
        if f"d:acc:{order.id}:0" in h.callbacks(dbot, DRIVER.id):
            break
        await asyncio.sleep(0.02)
    offer = [m for m in h.session.calls(dbot.id, "SendRichMessage") if m.chat_id == DRIVER.id][-1]
    styles = {b.style for row in offer.reply_markup.inline_keyboard for b in row}
    assert "success" in styles
    assert "Oq darvoza oldida" in _j(offer)

    # --- Qabul -> 2 asosiy tugma: manzil (navigatsiya) va aloqa
    await h.press(dbot, DRIVER, f"d:acc:{order.id}:0", message_id=await offer_message_id(h, order.id))
    order = await h.svc.get_order(order.id)
    assert order.status == OrderStatus.ACCEPTED
    card = [m for m in h.session.calls(dbot.id, "EditMessageText") if m.chat_id == DRIVER.id][-1]
    first, second = card.reply_markup.inline_keyboard[0][0], card.reply_markup.inline_keyboard[1][0]
    assert "manzili" in first.text and "yandex" in first.url and "rtt=auto" in first.url  # Yandex navigatsiya
    assert "aloqa" in second.text and second.callback_data == f"d:call:{order.id}:0"
    assert "Haydovchi topildi" in h.last_text(pbot, PASSENGER.id)
    assert h.session.calls(pbot.id, "SendLocation")  # yo'lovchiga mashinaning jonli xaritasi

    # Aloqa — faqat kompaniya raqami va kod (shaxsiy raqamlar hech kimga ko'rinmaydi)
    await h.press(dbot, DRIVER, f"d:call:{order.id}:0")
    answer = h.session.calls(dbot.id, "AnswerCallbackQuery")[-1]
    assert "kompaniya" in answer.text.lower() and PASSENGER_PHONE not in answer.text
    card = h.last_text(dbot, DRIVER.id)
    code = (await h.svc.get_order(order.id)).call_code_d
    assert "Kompaniya raqami" in card and code in card and PASSENGER_PHONE.lstrip("+") not in card

    # Anonim chat
    await h.send(dbot, DRIVER, text="2 daqiqada yetib boraman")
    assert "2 daqiqada" in h.last_text(pbot, PASSENGER.id)

    # 📡 Yo'lovchi chatda jonli joylashuvni ulashadi («Men o'chirmagunimcha») — haydovchiga ko'rinadi
    here = offset(*center, 40, -30)
    await h.send(pbot, PASSENGER, location=Location(latitude=here[0], longitude=here[1], live_period=0x7FFFFFFF))
    assert "haydovchiga ko'rinib turadi" in h.last_text(pbot, PASSENGER.id)
    moved = offset(*center, 20, -10)
    await h.edit(pbot, PASSENGER, location=Location(latitude=moved[0], longitude=moved[1], live_period=0x7FFFFFFF))
    shared = await h.svc.get_order(order.id)
    assert (shared.pax_lat, shared.pax_lon) == moved

    # Haydovchi harakati -> yo'lovchidagi xarita yangilanadi
    await h.edit(
        dbot,
        DRIVER,
        location=Location(latitude=center[0], longitude=center[1], live_period=0x7FFFFFFF, horizontal_accuracy=5),
    )
    assert h.session.calls(pbot.id, "EditMessageLiveLocation")

    await h.press(dbot, DRIVER, f"d:arr:{order.id}:0")
    assert "yetib keldi" in h.last_text(pbot, PASSENGER.id)
    await h.press(dbot, DRIVER, f"d:start:{order.id}:0")
    before = (await h.svc.get_driver(driver.id)).balance
    # Manzilga yetmasdan yakunlab bo'lmaydi
    await h.press(dbot, DRIVER, f"d:fin:{order.id}:0")
    refused = h.session.calls(dbot.id, "AnswerCallbackQuery")[-1]
    assert refused.show_alert and "Manzilgacha" in refused.text
    assert (await h.svc.get_order(order.id)).status == OrderStatus.IN_PROGRESS
    # Manzilga yetib keldi → yakunlash (yo'lovchi tasdig'i kutilmaydi)
    await h.edit(
        dbot, DRIVER,
        location=Location(latitude=dest[0], longitude=dest[1], live_period=0x7FFFFFFF, horizontal_accuracy=5),
    )
    await h.press(dbot, DRIVER, f"d:fin:{order.id}:0")
    assert "Safar yakunlandi" in h.last_text(pbot, PASSENGER.id)
    order = await h.svc.get_order(order.id)
    after = (await h.svc.get_driver(driver.id)).balance
    assert order.status == OrderStatus.COMPLETED
    assert before - after == round(order.final_price * 0.1)
    done = [m for m in h.session.calls(pbot.id, "SendRichMessage") if m.chat_id == PASSENGER.id][-1]
    assert done.message_effect_id  # 🎉 effekt
    await h.press(pbot, PASSENGER, f"p:rate:{order.id}:5")
    assert (await h.svc.get_order(order.id)).rating == 5

    # --- MAXFIYLIK: hech bir tomon boshqasining raqami/ismini ko'rmaydi
    to_passenger = h.session.dump(pbot.id, PASSENGER.id)
    to_driver = h.session.dump(dbot.id, DRIVER.id)
    assert DRIVER_PHONE not in to_passenger and DRIVER_PHONE[1:] not in to_passenger
    assert "Bekzod" not in to_passenger and "Karimov" not in to_passenger
    assert PASSENGER_PHONE not in to_driver and PASSENGER_PHONE[1:] not in to_driver
    assert "Jasur" not in to_driver
    # Yo'lovchi boti hech qachon haydovchiga, haydovchi boti yo'lovchiga yozmaydi
    assert all(getattr(m, "chat_id", PASSENGER.id) != DRIVER.id for m in h.session.calls(pbot.id))
    assert all(getattr(m, "chat_id", DRIVER.id) != PASSENGER.id for m in h.session.calls(dbot.id))


async def offer_message_id(h: Harness, order_id: int) -> int:
    from sqlalchemy import select

    from taxi_bot.db.models import OrderOffer

    for _ in range(100):  # xabar yuborilgach, uning ID si bazaga biroz keyin yoziladi
        async with h.svc.db.session() as s:
            mid = await s.scalar(select(OrderOffer.message_id).where(OrderOffer.order_id == order_id))
        if mid:
            return mid
        await asyncio.sleep(0.01)
    raise AssertionError("taklif xabari topilmadi")


async def test_chat_written_destination_goes_to_taximeter(harness, center):
    h = await harness()
    pbot = h.pbot
    await h.send(pbot, PASSENGER, text="/start")
    await h.send(pbot, PASSENGER, contact=Contact(phone_number=PASSENGER_PHONE, first_name="J", user_id=PASSENGER.id))
    await h.send(pbot, PASSENGER, location=Location(latitude=center[0], longitude=center[1], horizontal_accuracy=10))
    assert "manzil nomini yozing" in h.last_text(pbot, PASSENGER.id)
    await h.send(pbot, PASSENGER, text="Chorsu bozori")  # ✍️ xaritasiz manzil
    quote = h.last_text(pbot, PASSENGER.id)
    assert "Chorsu bozori" in quote and "taksometr" in quote.lower()
    await h.send(pbot, PASSENGER, text="Oq darvoza")  # endi — izoh
    await h.press(pbot, PASSENGER, "p:confirm:0:0")
    order = await h.svc.active_order((await h.svc.get_passenger_by_tg(PASSENGER.id)).id)
    assert order.dest_title == "Chorsu bozori" and not order.has_destination and order.comment == "Oq darvoza"


async def test_single_bot_asks_role_first(harness, center):
    h = await harness(single=True)
    bot = h.pbot
    await h.send(bot, PASSENGER, text="/start")
    assert "Siz kimsiz" in h.last_text(bot, PASSENGER.id)
    assert "role:passenger" in h.callbacks(bot, PASSENGER.id)
    await h.press(bot, PASSENGER, "role:passenger")
    assert "telefon raqamingizni" in h.last_text(bot, PASSENGER.id)
    await h.send(bot, DRIVER, text="/start")
    await h.press(bot, DRIVER, "role:driver")
    assert "haydovchilar uchun bot" in h.last_text(bot, DRIVER.id)


async def test_single_bot_driver_on_trip_cannot_switch_to_passenger(harness, center):
    from taxi_bot.db.models import Driver

    h = await harness(single=True)
    bot = h.pbot
    await h.send(bot, DRIVER, text="/start")
    await h.press(bot, DRIVER, "role:driver")
    d = await h.svc.register_driver(DRIVER.id, "Ali", "+998901112233", "Cobalt", "Oq", "01A111AA")
    async with h.svc.db.session() as s:
        (await s.get(Driver, d.id)).current_order_id = 777  # safarda
    await h.send(bot, DRIVER, text="/role")
    await h.press(bot, DRIVER, "role:passenger")
    ans = h.session.calls(bot.id, "AnswerCallbackQuery")[-1]
    assert ans.show_alert and "safarni yakunlang" in ans.text
    assert await h.svc.get_user_role(DRIVER.id) == Role.DRIVER


async def test_stale_button_and_foreign_order_are_rejected(harness, center):
    h = await harness()
    await h.press(h.dbot, DRIVER, "d:acc:12345:0")
    ans = h.session.calls(h.dbot.id, "AnswerCallbackQuery")[-1]
    assert ans.show_alert
    await h.press(h.pbot, PASSENGER, "p:cancel:12345:0")
    assert "topilmadi" in h.session.calls(h.pbot.id, "AnswerCallbackQuery")[-1].text


async def test_competitive_features_end_to_end(harness, center):
    """Saqlangan manzil → 3 bosishda buyurtma, boshqa odam uchun, sevimli haydovchi, "Uyga" rejimi."""
    from taxi_bot.db.models import FavoriteDriver, Order

    h = await harness()
    pbot, dbot = h.pbot, h.dbot
    driver = await register_and_approve_driver(h, offset(*center, 300, 200))

    await h.send(pbot, PASSENGER, text="/start")
    await h.send(pbot, PASSENGER, contact=Contact(phone_number=PASSENGER_PHONE, first_name="J", user_id=PASSENGER.id))

    # 🏠 Uy manzilini saqlash
    await h.send(pbot, PASSENGER, text="📍 Manzillarim")
    assert "p:addplace:0:0" in h.callbacks(pbot, PASSENGER.id)
    await h.press(pbot, PASSENGER, "p:addplace:0:0")
    home = offset(*center, 2500, 1500)
    await h.send(pbot, PASSENGER, location=Location(latitude=home[0], longitude=home[1]))
    assert "Manzil saqlandi" in "".join(m.text or "" for m in h.session.calls(pbot.id, "SendMessage"))
    p = await h.svc.get_passenger_by_tg(PASSENGER.id)
    place = (await h.svc.list_places(p.id))[0]

    # 1) Taksi chaqirish → 2) 🏠 Uy → 3) Buyurtma berish
    await h.send(pbot, PASSENGER, location=Location(latitude=center[0], longitude=center[1], horizontal_accuracy=10))
    assert f"p:place:{place.id}:0" in h.callbacks(pbot, PASSENGER.id)
    await h.press(pbot, PASSENGER, f"p:place:{place.id}:0")
    assert "Buyurtmani tasdiqlang" in h.last_text(pbot, PASSENGER.id)
    # 👤 boshqa odam uchun
    await h.press(pbot, PASSENGER, "p:rider:0:0")
    await h.send(pbot, PASSENGER, text="93 444 55 66")
    assert "boshqa odam" in h.last_text(pbot, PASSENGER.id)
    await h.press(pbot, PASSENGER, "p:confirm:0:0")
    order = await h.svc.active_order(p.id)
    assert order.rider_phone == "+998934445566"
    assert abs(order.dest_lat - home[0]) < 1e-9 and abs(order.dest_lon - home[1]) < 1e-9

    for _ in range(100):
        if f"d:acc:{order.id}:0" in h.callbacks(dbot, DRIVER.id):
            break
        await asyncio.sleep(0.02)
    await h.press(dbot, DRIVER, f"d:acc:{order.id}:0", message_id=await offer_message_id(h, order.id))
    order = await h.svc.get_order(order.id)
    assert order.status == OrderStatus.ACCEPTED

    # ⚙️ Haydovchi sozlamalari: uy manzili va "Uyga" rejimi
    await h.send(dbot, DRIVER, text="⚙️ Sozlamalar")
    assert "d:sethome:0:0" in h.callbacks(dbot, DRIVER.id)
    await h.press(dbot, DRIVER, "d:sethome:0:0")
    await h.send(dbot, DRIVER, location=Location(latitude=home[0], longitude=home[1]))
    await h.press(dbot, DRIVER, "d:home:0:0")
    d = await h.svc.get_driver(driver.id)
    assert d.home_mode and abs(d.home_lat - home[0]) < 1e-9

    await h.press(dbot, DRIVER, f"d:start:{order.id}:0")
    await h.edit(
        dbot, DRIVER,
        location=Location(latitude=home[0], longitude=home[1], live_period=0x7FFFFFFF, horizontal_accuracy=5),
    )
    await h.press(dbot, DRIVER, f"d:fin:{order.id}:0")

    # ⭐ baho → ❤️ sevimli → 💾 Ish manzili
    await h.press(pbot, PASSENGER, f"p:rate:{order.id}:5")
    assert f"p:fav:{order.id}:0" in h.callbacks(pbot, PASSENGER.id)
    await h.press(pbot, PASSENGER, f"p:fav:{order.id}:0")
    await h.press(pbot, PASSENGER, f"p:savedest:{order.id}:1")
    async with h.svc.db.session() as s:
        from sqlalchemy import select

        assert await s.scalar(select(FavoriteDriver.driver_id)) == driver.id
        assert (await s.get(Order, order.id)).status == OrderStatus.COMPLETED
    kinds = {pl.kind for pl in await h.svc.list_places(p.id)}
    assert kinds == {"home", "work"}

    # Maxfiylik: boshqa odamning raqami ham haydovchiga ko'rinmaydi
    to_driver = h.session.dump(dbot.id, DRIVER.id)
    assert "934445566" not in to_driver and PASSENGER_PHONE[1:] not in to_driver
