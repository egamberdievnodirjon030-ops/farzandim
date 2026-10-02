#!/usr/bin/env bash
# Ota-onalar davomat boti: ilovani (Telegram Web App) VAQTINCHA sinash — Linux/macOS.
# Cloudflare Quick Tunnel orqali HTTPS manzil ochadi, .env ga yozadi va botni ishga tushiradi.
# Ishga tushirish:  bash ilova_sinov.sh      To'xtatish: Ctrl+C (tunnel yopiladi, .env tiklanadi)
# FAQAT SINOV UCHUN: manzil har safar o'zgaradi. Doimiy ishlatish — README, «Web App uchun HTTPS manzil».
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo ".env topilmadi: cp .env.example .env va BOT_TOKEN, ADMIN_IDS ni to'ldiring"; exit 1; }
sed -i.bak '1s/^\xEF\xBB\xBF//' .env && rm -f .env.bak          # BOM bo'lsa olib tashlanadi
grep -Eq '^[[:space:]]*BOT_TOKEN[[:space:]]*=[[:space:]]*[^[:space:]]+' .env || { echo "BOT_TOKEN to'ldirilmagan"; exit 1; }
PORT=$(grep -E '^[[:space:]]*WEBAPP_PORT[[:space:]]*=' .env | tail -1 | sed -E 's/.*=[[:space:]]*([0-9]+).*/\1/' || true)
PORT=${PORT:-8080}
[ "$PORT" != "0" ] || { echo "WEBAPP_PORT=0 — ilova serveri o'chiq"; exit 1; }
OLD_URL=$(grep -E '^[[:space:]]*WEBAPP_URL[[:space:]]*=' .env | tail -1 | sed -E 's/^[^=]*=//' || true)
PY=python3; [ -x venv/bin/python ] && PY=venv/bin/python

CF=$(command -v cloudflared || true)
if [ -z "$CF" ]; then
  CF=./cloudflared
  if [ ! -x "$CF" ]; then
    case "$(uname -s)-$(uname -m)" in
      Linux-x86_64) A=linux-amd64 ;; Linux-aarch64|Linux-arm64) A=linux-arm64 ;;
      Darwin-*) echo "macOS: brew install cloudflared — so'ng qayta ishga tushiring"; exit 1 ;;
      *) echo "Noma'lum tizim: cloudflared ni qo'lda o'rnating"; exit 1 ;;
    esac
    echo "cloudflared yuklab olinmoqda (rasmiy GitHub sahifasidan)..."
    curl -fsSL -o "$CF" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-$A"
    chmod +x "$CF"
  fi
fi

set_url() {  # .env dagi WEBAPP_URL qatorini almashtiradi (bo'lmasa qo'shadi)
  if grep -Eq '^[[:space:]]*WEBAPP_URL[[:space:]]*=' .env; then
    V="$1" awk '{ if ($0 ~ /^[ \t]*WEBAPP_URL[ \t]*=/) print "WEBAPP_URL=" ENVIRON["V"]; else print }' .env > .env.tmp && mv .env.tmp .env
  else printf '\nWEBAPP_URL=%s\n' "$1" >> .env; fi
}

LOG=$(mktemp -t ota_ona_cloudflared.XXXX)
echo "Tunnel ochilmoqda: https://...trycloudflare.com -> http://127.0.0.1:$PORT"
"$CF" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" 2>"$LOG" &
TPID=$!
cleanup() { kill "$TPID" 2>/dev/null || true; set_url "$OLD_URL"; echo; echo "Tunnel yopildi, .env tiklandi."; }
trap cleanup EXIT

URL=""
for _ in $(seq 1 90); do
  sleep 1
  kill -0 "$TPID" 2>/dev/null || break
  URL=$(grep -Eo 'https://[a-z0-9]+(-[a-z0-9]+)+\.trycloudflare\.com' "$LOG" | grep -v '^https://api\.' | head -1 || true)
  [ -n "$URL" ] && break
done
if [ -z "$URL" ]; then echo "Tunnel manzilini olib bo'lmadi. Jurnal oxiri:"; tail -12 "$LOG"; exit 1; fi

set_url "$URL"
echo
echo "  Ilova manzili:  $URL"
echo "  Telegram'da botni oching va /start bosing — chat pastida «Ilova» tugmasi paydo bo'ladi."
echo "  To'xtatish: Ctrl+C."
echo
"$PY" bot.py
