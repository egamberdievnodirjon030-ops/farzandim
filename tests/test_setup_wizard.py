"""Birinchi sozlash yordamchisi (`python -m taxi_bot setup`)."""

from __future__ import annotations

from pathlib import Path

from taxi_bot.config import Settings
from taxi_bot.setup_wizard import BotInfo, render_env, wizard

TOKEN = "9099981582:" + "A" * 35
ROOT = Path(__file__).resolve().parents[1]


class FakeProbe:
    def __init__(self, users=None, bad_tokens=()):
        self.users = list(users or [])
        self.bad = set(bad_tokens)
        self.waited_on: list[str] = []

    async def get_me(self, token):
        if token in self.bad:
            raise RuntimeError("Telegram server says - Unauthorized")
        return BotInfo(username="Arabalartaxi_bot", name="Arabalar Taxi")

    async def wait_for_user(self, token, timeout):
        self.waited_on.append(token)
        return self.users.pop(0) if self.users else None


def answers(*items):
    it = iter(items)
    return lambda _prompt: next(it)


async def test_wizard_detects_admin_and_writes_env(tmp_path):
    (tmp_path / ".env.example").write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    probe = FakeProbe(users=[(555, "Boshqa odam"), (777, "Nodir")], bad_tokens={"1234567:" + "B" * 35})
    out: list[str] = []
    code = await wizard(
        tmp_path,
        input_fn=answers(
            "noto'g'ri",  # format xato
            "1234567:" + "B" * 35,  # Telegram tanimadi
            TOKEN,  # to'g'ri
            "",  # ikkinchi bot yo'q
            "",  # admin ID ni avtomatik aniqlash
            "yo'q",  # birinchi topilgan — boshqa odam
            "ha",  # ikkinchisi — men
            "",  # kompaniya nomi: bot nomi
            "+998712000000",
        ),
        out=out.append,
        probe=probe,
    )
    assert code == 0
    text = "\n".join(out)
    assert "noto'g'ri ko'rinishda" in text and "tanimadi" in text and "@Arabalartaxi_bot" in text
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert f"PASSENGER_BOT_TOKEN={TOKEN}" in env and "ADMIN_IDS=777" in env
    assert "COMPANY_NAME=Arabalar Taxi" in env and "BASE_FARE=7000" in env  # qolgan sozlamalar saqlandi
    s = Settings(_env_file=tmp_path / ".env")
    assert s.single_bot and s.admin_ids == [777] and s.company_phone == "+998712000000"


async def test_wizard_two_bots_detects_admin_via_driver_bot(tmp_path):
    driver_token = "1111111111:" + "C" * 35
    probe = FakeProbe(users=[(42, "Admin")])
    code = await wizard(
        tmp_path,
        input_fn=answers(TOKEN, driver_token, "", "ha", "Shahar Taksi", ""),
        out=lambda _m: None,
        probe=probe,
    )
    assert code == 0
    assert probe.waited_on == [driver_token]  # arizalar haydovchi boti orqali keladi
    s = Settings(_env_file=tmp_path / ".env")
    assert not s.single_bot and s.admin_ids == [42]


async def test_wizard_keeps_existing_env_when_declined(tmp_path):
    (tmp_path / ".env").write_text("PASSENGER_BOT_TOKEN=x\n", encoding="utf-8")
    assert await wizard(tmp_path, input_fn=answers("yo'q"), out=lambda _m: None, probe=FakeProbe()) == 0
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "PASSENGER_BOT_TOKEN=x\n"


def test_render_env_replaces_only_given_keys():
    tpl = "# izoh\nA=1\n# B=eski\nB=\nC=3"
    assert render_env(tpl, {"B": "2", "D": "4"}) == "# izoh\nA=1\n# B=eski\nB=2\nC=3\nD=4\n"
