@echo off
title Gemini Agent - Telegram Mobile Gateway
cd /d "%~dp0"
set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================
echo  Telegram Bot - Self-Healing Mode
echo ========================================
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

echo Pilih mode jalankan:
echo   1. Mode Normal (tanpa self-healing)
echo   2. Mode Self-Healing (otomatis perbaiki crash)
echo.
set /p choice="Pilih [1/2] (default: 2): "
if "%choice%"=="1" (
    python bot_telegram.py
) else (
    python run_with_healing.py bot
)
pause
