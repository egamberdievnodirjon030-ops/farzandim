@echo off
rem Manage'dan namuna ma'lumot yig'ish (kalit .env yoki bot orqali kiritilgan bo'lishi kerak). Natija: data\manage_namuna.json
chcp 65001 >nul
cd /d "%~dp0"
if exist venv\Scripts\python.exe (set PY=venv\Scripts\python.exe) else (set PY=python)
set /p GURUH="Guruh nomi (masalan 3-10c-24; bo'sh qoldirsangiz - birinchi guruh): "
if "%GURUH%"=="" (%PY% integration.py yigish) else (%PY% integration.py yigish --guruh=%GURUH%)
echo.
echo Endi data\manage_namuna.json faylini Claude'ga yuboring.
start "" explorer /select,"%~dp0data\manage_namuna.json"
pause
