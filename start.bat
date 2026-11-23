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

rem --- Virtual muhit (.venv) - faqat birinchi marta yaratiladi ---
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Virtual muhit yaratilmoqda...
    %PY% -m venv .venv
    if errorlevel 1 goto :venvfail
)
set "VPY=.venv\Scripts\python.exe"

echo [2/3] Kutubxonalar tekshirilmoqda...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :pipfail

rem --- Birinchi marta: sozlash yordamchisi ---
if not exist ".env" (
    "%VPY%" -m taxi_bot setup
    if errorlevel 1 goto :end
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

:venvfail
echo.
echo [XATO] Virtual muhit yaratilmadi. Papkani yozish huquqi borligini tekshiring.
goto :end

:pipfail
echo.
echo [XATO] Kutubxonalar o'rnatilmadi. Internet ulanishini tekshiring va qayta urinib ko'ring.
goto :end

:end
echo.
pause
