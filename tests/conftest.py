from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import pytest
import pytest_asyncio

from taxi_bot.config import Settings
from taxi_bot.db import Database
from taxi_bot.services.taxi import TaxiService
from taxi_bot.ui.kit import View
from taxi_bot.ui.messenger import Role


@dataclass
class Sent:
    role: Role
    chat_id: int
    view: View
    message_id: int
    effect: str | None = None


@dataclass
class FakeMessenger:
    """Telegram o'rniga barcha yuborilgan xabarlarni yozib boradi."""

    sent: list[Sent] = field(default_factory=list)
    edits: list[tuple[Role, int, int, View]] = field(default_factory=list)
    deleted: list[tuple[Role, int, int]] = field(default_factory=list)
    admin: list[View] = field(default_factory=list)
    live: list[tuple] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(100))

    async def send(self, role, chat_id, view, *, effect=None, silent=False):
        mid = next(self._ids)
        self.sent.append(Sent(role, chat_id, view, mid, effect))
        return mid

    async def edit(self, role, chat_id, message_id, view):
        if not message_id:
            return False
        self.edits.append((role, chat_id, message_id, view))
        return True

    async def replace(self, role, chat_id, old_message_id, view, *, effect=None):
        mid = await self.send(role, chat_id, view, effect=effect)
        if old_message_id:
            await self.delete(role, chat_id, old_message_id)
        return mid

    async def delete(self, role, chat_id, message_id):
        if message_id:
            self.deleted.append((role, chat_id, message_id))
        return True

    async def notify_admins(self, view):
        self.admin.append(view)

    async def send_live_location(self, role, chat_id, lat, lon, heading=None):
        mid = next(self._ids)
        self.live.append(("send", role, chat_id, mid, lat, lon))
        return mid

    async def edit_live_location(self, role, chat_id, message_id, lat, lon, heading=None):
        self.live.append(("edit", role, chat_id, message_id, lat, lon))

    async def relay_voice(self, from_role, file_id, to_role, chat_id, caption):
        self.sent.append(Sent(to_role, chat_id, View.plain(caption), next(self._ids)))
        return True

    # yordamchilar
    def to(self, role: Role, chat_id: int) -> list[Sent]:
        return [m for m in self.sent if m.role == role and m.chat_id == chat_id]

    def texts(self, role: Role, chat_id: int) -> list[str]:
        return [m.view.text for m in self.to(role, chat_id)] + [
            v.text for r, c, _, v in self.edits if r == role and c == chat_id
        ]


def make_settings(**overrides) -> Settings:
    base = dict(
        passenger_bot_token="1:passenger",
        driver_bot_token="2:driver",
        database_url="sqlite+aiosqlite:///:memory:",
        admin_ids=[999],
        wave_radii_km=[1.0, 2.0, 3.5],
        wave_timeout_sec=0.6,
        priority_headstart_sec=0.15,
        search_timeout_sec=5.0,
        rescan_interval_sec=0.2,
        min_driver_balance=1000,
        finish_confirm_timeout_min=10,
        call_provider="operator",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


@pytest_asyncio.fixture
async def make_service(tmp_path):
    created: list[tuple[TaxiService, Database]] = []

    async def factory(**overrides) -> tuple[TaxiService, FakeMessenger]:
        settings = make_settings(
            database_url=f"sqlite+aiosqlite:///{tmp_path}/t{len(created)}.db", **overrides
        )
        db = Database(settings.database_url)
        await db.create_all()
        fake = FakeMessenger()
        svc = TaxiService(settings, db, fake)  # type: ignore[arg-type]
        created.append((svc, db))
        return svc, fake

    yield factory
    for svc, db in created:
        await svc.close()
        await db.close()


# Namangan markazi atrofidagi nuqtalar
CENTER = (40.9983, 71.6726)


def offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    import math

    dlat = north_m / 111_320
    dlon = east_m / (111_320 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


@pytest.fixture
def center():
    return CENTER
