#!/usr/bin/env bash
# Taksi bot — Mac / Linux'da ishga tushirish:  bash start.sh
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1

PY=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PY="$candidate"; break
    fi
done
if [ -z "$PY" ]; then
    echo "[XATO] Python 3.11 yoki yangiroq topilmadi: https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] Virtual muhit yaratilmoqda..."
    "$PY" -m venv .venv
fi
echo "[2/3] Kutubxonalar tekshirilmoqda..."
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt

if [ ! -f ".env" ]; then
    .venv/bin/python -m taxi_bot setup
fi
echo "[3/3] Bot ishga tushmoqda... To'xtatish uchun Ctrl+C bosing."
exec .venv/bin/python -m taxi_bot
