@echo off
title TeleAgent - Telegram Mobile Gateway
cd /d "%~dp0"

:: Konfigurasi Code Page UTF-8 & Environment
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================================
echo       TeleAgent - Telegram Mobile Gateway
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment .venv tidak ditemukan.
    echo [*] Menjalankan setup otomatis...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

chcp 65001 >nul

echo.
echo Pilih mode eksekusi:
echo   1. Mode Normal [Langsung bot_telegram.py]
echo   2. Mode Self-Healing [Rekomendasi - Otomatis perbaiki crash]
echo.
set "choice=2"
set /p "choice=Pilih 1 atau 2 (default: 2): "

if "%choice%"=="1" (
    echo [*] Menjalankan Bot Telegram mode Normal...
    python bot_telegram.py
) else (
    echo [*] Menjalankan Bot Telegram mode Self-Healing...
    python run_with_healing.py bot
)

if errorlevel 1 (
    echo.
    echo [!] Bot berhenti dengan kode status: %errorlevel%
)

echo.
echo Sesi selesai. Tekan sembarang tombol untuk keluar...
pause >nul
