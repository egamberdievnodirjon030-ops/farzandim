#!/usr/bin/env bash
# Android imzo kalitini BIR MARTA yaratadi va GitHub Secrets ga qo'yiladigan qiymatlarni chiqaradi.
# Kalitni (jidu-release.jks) va parolni xavfsiz joyda saqlang: yo'qolsa, yangi versiyalar eski ilova ustiga
# o'rnatilmaydi (ota-onalar ilovani o'chirib, qayta o'rnatishi kerak bo'ladi).
# Talab: Java (keytool). Ishlatish:  bash scripts/make-keystore.sh
set -euo pipefail
OUT="${1:-jidu-release.jks}"
ALIAS="jidu"
PASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
keytool -genkeypair -v -keystore "$OUT" -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 36500 \
  -storepass "$PASS" -keypass "$PASS" -dname "CN=JIDU Ota-ona, O=JIDU, C=UZ" >/dev/null 2>&1
echo "Yaratildi: $OUT"
echo
echo "GitHub → Settings → Secrets and variables → Actions → New repository secret:"
echo "  ANDROID_KEY_ALIAS          = $ALIAS"
echo "  ANDROID_KEYSTORE_PASSWORD  = $PASS"
echo "  ANDROID_KEY_PASSWORD       = $PASS"
echo "  ANDROID_KEYSTORE_BASE64    = (quyidagi fayl ichidagi butun matn)"
base64 -w0 "$OUT" > "$OUT.base64.txt" 2>/dev/null || base64 -i "$OUT" -o "$OUT.base64.txt"
echo "                               $OUT.base64.txt"
