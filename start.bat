@echo off
rem ================================================================
rem  Taksi bot - Windows'da ishga tushirish (ikki marta bosing)
rem ================================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem --- Python'ni topish (py launcher yoki python) ---
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :nopython

rem --- Diskda bosh joyni tekshirish: kutubxonalar ~70 MB, cloudflared ~60 MB, vaqtinchalik fayllar ---
set "NEED_MB=300"
if exist ".venv\Scripts\python.exe" set "NEED_MB=80"
%PY% -c "import shutil,sys,tempfile; f=min(shutil.disk_usage('.').free, shutil.disk_usage(tempfile.gettempdir()).free)//1048576; n=int(sys.argv[1]); sys.exit(0) if f>=n else (print(f'Diskda bosh joy: {f} MB, kerak: kamida {n} MB'), sys.exit(3))" %NEED_MB%
if errorlevel 3 goto :nospace

rem --- Virtual muhit (.venv) - faqat birinchi marta yaratiladi ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Virtual muhit yaratilmoqda...
    %PY% -m venv .venv
    if errorlevel 1 goto :nospace
echo.
echo [XATO] Diskda joy yetarli emas. Joy bo'shating va qayta ishga tushiring:
echo   1. Windows Sozlamalar - Tizim - Xotira - Vaqtinchalik fayllar - O'chirish
echo   2. Savatni - Recycle Bin - tozalang, Yuklanmalar papkasidagi keraksiz fayllarni o'chiring
echo   3. Loyihaning eski nusxasi bo'lsa: .env va data papkasini ko'chirib oling, eski papkani o'chiring
echo   4. Python keshini tozalash: py -m pip cache purge
goto :end

:venvfail
)
set "VPY=.venv\Scripts\python.exe"

echo [2/3] Kutubxonalar tekshirilmoqda...
"%VPY%" -m pip install --disable-pip-version-check --no-cache-dir -q -r requirements.txt
if errorlevel 1 goto :pipfail

rem --- Birinchi marta: sozlash yordamchisi ---
if not exist ".env" (
    "%VPY%" -m taxi_bot setup
    if errorlevel 1 goto :end
)

rem --- Telegram ilovasi uchun HTTPS tunnel dasturi (bir marta yuklab olinadi, ~60 MB) ---
if not exist "cloudflared.exe" (
    where cloudflared >nul 2>nul
    if errorlevel 1 (
        echo Telegram ilovasi uchun cloudflared yuklab olinmoqda - rasmiy Cloudflare GitHub sahifasidan...
        powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile cloudflared.exe; $f = Get-Item cloudflared.exe; $b = [IO.File]::ReadAllBytes($f.FullName)[0..1]; if ($f.Length -lt 5000000 -or $b[0] -ne 77 -or $b[1] -ne 90) { Remove-Item cloudflared.exe; exit 1 } } catch { if (Test-Path cloudflared.exe) { Remove-Item cloudflared.exe }; exit 1 }"
        if errorlevel 1 echo [!] cloudflared yuklanmadi yoki buzilgan - bot chat rejimida ishlaydi. Qo'lda o'rnatish: README, Telegram ilovasi bo'limi.
    )
)

echo [3/3] Bot ishga tushmoqda... To'xtatish uchun Ctrl+C bosing.
echo.
"%VPY%" -m taxi_bot
goto :end

:nopython
echo.
echo [XATO] Python 3.11 yoki yangiroq topilmadi.
echo   1. https://www.python.org/downloads/ dan Python'ni yuklab oling.
echo   2. O'rnatishda "Add python.exe to PATH" belgisini albatta qo'ying.
echo   3. Shu faylni qaytadan ishga tushiring.
goto :end

:nospace
echo.
echo [XATO] Diskda joy yetarli emas. Joy bo'shating va qayta ishga tushiring:
echo   1. Windows Sozlamalar - Tizim - Xotira - Vaqtinchalik fayllar - O'chirish
echo   2. Savatni - Recycle Bin - tozalang, Yuklanmalar papkasidagi keraksiz fayllarni o'chiring
echo   3. Loyihaning eski nusxasi bo'lsa: .env va data papkasini ko'chirib oling, eski papkani o'chiring
echo   4. Python keshini tozalash: py -m pip cache purge
goto :end

:venvfail
echo.
echo [XATO] Virtual muhit yaratilmadi. Papkani yozish huquqi borligini tekshiring.
goto :end

:pipfail
echo.
echo [XATO] Kutubxonalar o'rnatilmadi. Sabab odatda: diskda joy yetishmaydi yoki internet yo'q.
echo   Yuqoridagi xato matnini o'qing: "No space left on device" - diskda joy tugagan.
goto :end

:end
echo.
pause
