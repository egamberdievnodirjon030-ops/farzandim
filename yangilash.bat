@echo off
rem Botni qayta o'rnatmasdan yangilash: GitHub'dan yangi kod - .env, data, venv, logs ga tegmaydi.
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0yangilash.ps1"
pause
