"""Birinchi sozlash yordamchisi: `python -m taxi_bot setup`.

Token Telegram orqali tekshiriladi, admin ID esa botga yozilgan xabardan avtomatik aniqlanadi —
@userinfobot qidirib o'tirish shart emas. Natija `.env` fayliga yoziladi.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
DETECT_ROUNDS = 6  # 6 x 20 s = 2 daqiqa


@dataclass
class BotInfo:
    username: str
    name: str


class TelegramProbe:
    """Telegram bilan ishlash (testlarda soxtasi bilan almashtiriladi)."""

    async def get_me(self, token: str) -> BotInfo:
        from aiogram import Bot

        bot = Bot(token)
        try:
            me = await bot.get_me()
            return BotInfo(username=me.username or "", name=me.first_name)
        finally:
            await bot.session.close()

    async def wait_for_user(self, token: str, timeout: int) -> tuple[int, str] | None:
        """Botga yozgan birinchi odamning (ID, ism) — `timeout` soniya kutadi."""
        from aiogram import Bot

        bot = Bot(token)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            updates = await bot.get_updates(timeout=timeout, allowed_updates=["message"])
            for update in updates:
                if update.message and update.message.from_user and not update.message.from_user.is_bot:
                    user = update.message.from_user
                    # Yangilanishni tasdiqlaymiz — bot ishga tushganda qayta ishlanmaydi
                    await bot.get_updates(offset=update.update_id + 1, timeout=0)
                    return user.id, user.full_name
            return None
        finally:
            await bot.session.close()


def _ask(prompt: str, input_fn: Callable[[str], str], default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input_fn(f"{prompt}{suffix}: ").strip()
    return value or default


def _yes(prompt: str, input_fn: Callable[[str], str]) -> bool:
    return _ask(prompt + " (ha/yo'q)", input_fn, "ha").lower() in ("ha", "h", "y", "yes", "1")


async def _ask_token(
    title: str, probe: TelegramProbe, input_fn, out, *, optional: bool = False
) -> tuple[str, BotInfo | None]:
    while True:
        token = _ask(title, input_fn)
        if not token and optional:
            return "", None
        if not TOKEN_RE.match(token):
            out("  ❌ Token noto'g'ri ko'rinishda. Masalan: 123456789:AAH...  (@BotFather beradi)")
            continue
        try:
            info = await probe.get_me(token)
        except Exception as exc:  # noqa: BLE001 - tarmoq yoki noto'g'ri token
            text = str(exc)
            if "Unauthorized" in text or "Not Found" in text:
                out("  ❌ Telegram bu tokenni tanimadi. @BotFather dan qayta nusxalang.")
                continue
            out(f"  ⚠️ Telegram'ga ulanib bo'lmadi ({text[:80]}). Internetni tekshiring.")
            if _yes("  Tokenni tekshirmasdan saqlaymizmi?", input_fn):
                return token, None
            continue
        out(f"  ✅ Bot topildi: @{info.username} ({info.name})")
        return token, info


async def _detect_admin(token: str, info: BotInfo | None, probe: TelegramProbe, input_fn, out) -> str:
    manual = _ask(
        "\nAdmin Telegram ID (bilsangiz kiriting, bilmasangiz Enter — avtomatik aniqlaymiz)", input_fn
    )
    if manual:
        return ",".join(x.strip() for x in manual.split(",") if x.strip().isdigit())
    name = f"@{info.username}" if info and info.username else "botingiz"
    out(f"\n👉 Telegram'da {name} ni oching va istalgan xabar yuboring (masalan /start).")
    out("   Kutyapman (2 daqiqagacha)...")
    for _ in range(DETECT_ROUNDS):
        try:
            found = await probe.wait_for_user(token, timeout=20)
        except Exception as exc:  # noqa: BLE001
            out(f"  ⚠️ Aniqlab bo'lmadi: {str(exc)[:80]}")
            break
        if found:
            user_id, full_name = found
            if _yes(f"  Topildi: {full_name} (ID {user_id}). Bu sizmisiz?", input_fn):
                return str(user_id)
            out("  Boshqa odam ekan. Iltimos, o'zingiz xabar yuboring...")
    manual = _ask("  ID ni qo'lda kiriting (bo'sh qoldirsangiz keyin .env da yozasiz)", input_fn)
    return manual if manual.isdigit() else ""


def render_env(template: str, values: dict[str, str]) -> str:
    """`.env.example` dagi kerakli qatorlarni to'ldiradi, qolganini saqlaydi."""
    lines = template.splitlines()
    done: set[str] = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in values:
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    for key, value in values.items():
        if key not in done:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


async def wizard(
    root: Path,
    *,
    input_fn: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
    probe: TelegramProbe | None = None,
) -> int:
    probe = probe or TelegramProbe()
    env_path = root / ".env"
    out("=" * 60)
    out("🚕  Taksi bot — birinchi sozlash")
    out("=" * 60)
    if env_path.exists() and not _yes(".env fayli bor. Qaytadan sozlaymizmi?", input_fn):
        out("O'zgartirilmadi.")
        return 0

    out("\n1) Bot tokeni — @BotFather → /mybots → botingiz → API Token")
    token, info = await _ask_token("Bot tokeni", probe, input_fn, out)

    out("\n2) Haydovchilar uchun ALOHIDA bot bormi? Bo'lmasa Enter bosing —")
    out("   bitta bot ishlaydi va kirishda 'Yo'lovchi / Haydovchi' deb so'raydi.")
    driver_token, driver_info = await _ask_token(
        "Haydovchilar boti tokeni (ixtiyoriy)", probe, input_fn, out, optional=True
    )
    if driver_token == token:
        driver_token, driver_info = "", None

    out("\n3) Admin — haydovchi arizalarini tasdiqlaydigan odam (siz).")
    # Arizalar admin'ga haydovchilar boti orqali keladi — shuning uchun o'sha botga yozish kerak
    admin_ids = await _detect_admin(
        driver_token or token, driver_info if driver_token else info, probe, input_fn, out
    )
    if not admin_ids:
        out("  ⚠️ Admin ko'rsatilmadi — keyin .env faylida ADMIN_IDS= qatoriga yozing.")

    out("\n4) Kompaniya ma'lumotlari")
    company = _ask("Kompaniya nomi", input_fn, info.name if info else "Shahar Taksi")
    phone = _ask("Kompaniya telefoni (ixtiyoriy, masalan +998712000000)", input_fn)

    template_path = root / ".env.example"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    values = {
        "PASSENGER_BOT_TOKEN": token,
        "DRIVER_BOT_TOKEN": driver_token,
        "ADMIN_IDS": admin_ids,
        "COMPANY_NAME": company,
        "COMPANY_PHONE": phone,
    }
    if env_path.exists():
        shutil.copy(env_path, root / ".env.bak")
        out("  (eski .env → .env.bak ga saqlandi)")
    env_path.write_text(render_env(template, values), encoding="utf-8")
    out("\n✅ Sozlash tugadi! .env fayli yaratildi.")
    out("   Qolgan sozlamalar (tarif, komissiya, radiuslar) .env faylida — Bloknot bilan ochib o'zgartirsa bo'ladi.")
    return 0


def run_wizard(root: Path | None = None) -> int:
    try:
        return asyncio.run(wizard(root or Path.cwd()))
    except (KeyboardInterrupt, EOFError):
        print("\nSozlash bekor qilindi.")
        return 1
