@echo off
title TeleAgent - Telegram Mobile Gateway
cd /d "%~dp0"

chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
)

python bot_telegram.py

