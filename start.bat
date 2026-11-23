@echo off
rem ================================================================
rem  Taksi bot - Windows: ikki marta bosing. Barcha ishni run.py bajaradi.
rem ================================================================
rem Oyna hech qachon o'zicha yopilmasligi uchun o'zini "cmd /k" ichida qayta ochadi
if /i not "%~1"=="--inner" (
    cmd /k ""%~f0" --inner"
    exit /b
)
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto checkver
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY goto nopython

:checkver
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto nopython

%PY% run.py
echo.
echo Oynani yopishingiz mumkin.
goto :eof

:nopython
echo.
echo [XATO] Python 3.11 yoki yangiroq topilmadi.
echo   1. https://www.python.org/downloads/ dan Python yuklab oling.
echo   2. O'rnatishda "Add python.exe to PATH" belgisini qo'ying.
echo   3. start.bat ni qayta ishga tushiring.
goto :eof
