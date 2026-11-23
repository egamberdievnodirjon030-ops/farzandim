#!/usr/bin/env bash
# Taksi bot - Mac / Linux: bash start.sh  (barcha ishni run.py bajaradi)
cd "$(dirname "$0")"
export PYTHONUTF8=1
for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        exec "$candidate" run.py
    fi
done
echo "[XATO] Python 3.11 yoki yangiroq topilmadi: https://www.python.org/downloads/"
exit 1
