"""Ishga tushirish: `python -m taxi_bot` (sozlash: `python -m taxi_bot setup`)."""

import os
import sys

if sys.version_info < (3, 11):  # noqa: UP036 - eski Python'da tushunarli xabar chiqishi uchun
    print("XATO: Python 3.11 yoki yangiroq kerak (sizda " + sys.version.split()[0] + ").")
    print("   Yuklab oling: https://www.python.org/downloads/")
    sys.exit(1)

from pathlib import Path


def main() -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows konsolida o'zbekcha matn buzilmasligi uchun
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:]
    if args and args[0] == "setup":
        from .setup_wizard import run_wizard

        sys.exit(run_wizard())
    if not Path(".env").exists() and not os.environ.get("PASSENGER_BOT_TOKEN"):
        print(".env fayli topilmadi — avval sozlaymiz.\n")
        from .setup_wizard import run_wizard

        if run_wizard() != 0 or not Path(".env").exists():
            sys.exit(1)
    from .app import run

    run()


if __name__ == "__main__":
    main()
