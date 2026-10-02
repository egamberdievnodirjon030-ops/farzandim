@echo off
rem Ota-onalar davomat boti: ilovani vaqtincha HTTPS orqali sinash (Cloudflare Quick Tunnel)
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ilova_sinov.ps1"
echo.
pause
