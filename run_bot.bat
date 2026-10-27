@echo off
title Gemini Agent - Telegram Mobile Gateway
cd /d "%~dp0"

echo ========================================================
echo   GEMINI AGENT - TELEGRAM MOBILE GATEWAY LAUNCHER
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv tidak ditemukan.
    echo Menjalankan setup...
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate
)

echo Memulai Gateway Telegram...
echo Biarkan jendela ini tetap terbuka agar laptop dapat menerima perintah dari HP.
echo Tekan Ctrl+C untuk mematikan.
echo.

python bot_telegram.py

pause
