"""Bir bosishda ishga tushirish (start.bat / start.sh shu faylni chaqiradi).

Faqat standart kutubxona ishlatiladi: disk joyini tekshiradi, .venv yaratadi, kutubxonalarni o'rnatadi,
Windows'da cloudflared'ni yuklab oladi va tekshiradi, birinchi marta sozlash yordamchisini ochadi,
so'ng botni ishga tushiradi. Har qanday xatoda tushunarli xabar chiqadi.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
MIN_BINARY = 5_000_000


def say(text: str) -> None:
    print(text, flush=True)


def fail(text: str) -> int:
    say(f"\n[XATO] {text}")
    return 1


def free_mb() -> int:
    paths = [ROOT, Path(tempfile.gettempdir())]
    return min(shutil.disk_usage(p).free for p in paths) // (1024 * 1024)


def disk_help(free: int, need: int) -> str:
    return (
        f"Diskda bo'sh joy yetarli emas: {free} MB bor, kamida {need} MB kerak.\n"
        "  1. Windows Sozlamalar > Tizim > Xotira > Vaqtinchalik fayllar > O'chirish\n"
        "  2. Savatni (Recycle Bin) tozalang, Yuklanmalar papkasidagi keraksiz fayllarni o'chiring\n"
        "  3. Loyihaning eski nusxasi bo'lsa: .env va data papkasini ko'chirib oling, eski papkani o'chiring\n"
        "  4. Python keshini tozalash: py -m pip cache purge"
    )


def valid_binary(path: Path) -> bool:
    try:
        if path.stat().st_size < MIN_BINARY:
            return False
        with path.open("rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def ensure_cloudflared() -> None:
    """Telegram ilovasi (HTTPS) uchun. Muvaffaqiyatsiz bo'lsa ham bot chat rejimida ishlaydi."""
    if os.name != "nt" or shutil.which("cloudflared"):
        return
    target = ROOT / "cloudflared.exe"
    if target.exists():
        if valid_binary(target):
            return
        say("  cloudflared.exe buzilgan - qayta yuklanadi")
        target.unlink(missing_ok=True)
    if free_mb() < 150:
        say("  [!] cloudflared uchun diskda joy yetarli emas - bot chat rejimida ishlaydi")
        return
    part = target.with_suffix(".part")
    say("  cloudflared yuklab olinmoqda (rasmiy Cloudflare, ~60 MB)...")
    try:
        with urllib.request.urlopen(CLOUDFLARED_URL, timeout=60) as resp, part.open("wb") as out:
            shutil.copyfileobj(resp, out, 1024 * 1024)
        if not valid_binary(part):
            raise OSError("yuklangan fayl dastur emas (tarmoq yoki antivirus to'sgan bo'lishi mumkin)")
        part.replace(target)
        say("  cloudflared tayyor")
    except Exception as exc:  # noqa: BLE001 - tunnelsiz ham ishlash kerak
        part.unlink(missing_ok=True)
        say(f"  [!] cloudflared yuklanmadi: {exc}")
        say("      Bot chat rejimida ishlaydi. Qo'lda: winget install --id Cloudflare.cloudflared")


def main() -> int:
    os.chdir(ROOT)
    if sys.version_info < (3, 11):  # noqa: UP036 - run.py istalgan Python bilan ochilishi mumkin
        return fail(f"Python 3.11 yoki yangiroq kerak (sizda {sys.version.split()[0]}): https://www.python.org/downloads/")

    need = 80 if VPY.exists() else 300
    free = free_mb()
    if free < need:
        return fail(disk_help(free, need))

    if not VPY.exists():
        say("[1/4] Virtual muhit yaratilmoqda...")
        try:
            venv.create(VENV, with_pip=True, clear=True)
        except Exception as exc:  # noqa: BLE001
            return fail(f"Virtual muhit yaratilmadi: {exc}\n  Papkaga yozish huquqi va diskdagi joyni tekshiring.")

    say("[2/4] Kutubxonalar tekshirilmoqda...")
    pip = subprocess.run(
        [str(VPY), "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "-q", "-r", "requirements.txt"],
        check=False,
    )
    if pip.returncode != 0:
        free = free_mb()
        reason = disk_help(free, 300) if free < 300 else "Internet ulanishini tekshiring va qayta urinib ko'ring."
        return fail("Kutubxonalar o'rnatilmadi.\n" + reason)

    say("[3/4] Telegram ilovasi uchun tunnel tekshirilmoqda...")
    ensure_cloudflared()

    if not (ROOT / ".env").exists():
        subprocess.run([str(VPY), "-m", "taxi_bot", "setup"], check=False)
        if not (ROOT / ".env").exists():
            return fail("Sozlash tugallanmadi (.env yaratilmadi). Qaytadan ishga tushiring.")

    say("[4/4] Bot ishga tushmoqda... To'xtatish uchun Ctrl+C bosing.\n")
    try:
        return subprocess.call([str(VPY), "-m", "taxi_bot"])
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        code = 0
    except Exception as exc:  # noqa: BLE001 - foydalanuvchi oynasi yopilib ketmasin
        print(f"\n[XATO] Kutilmagan xato: {exc!r}", flush=True)
        code = 1
    sys.exit(code)
