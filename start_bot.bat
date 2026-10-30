@echo off
title TeleAgent - Telegram Mobile Gateway
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "TELEAGENT_MANAGED_BOT=1"

if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
    .venv\Scripts\python.exe bot_telegram.py
) else (
    python bot_telegram.py
)

if errorlevel 1 (
    echo.
    echo [!] Bot Telegram berhenti dengan kode: %errorlevel%
    pause
)
