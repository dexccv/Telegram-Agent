@echo off
title TeleAgent
cd /d "%~dp0"

:: 0. Konfigurasi Code Page UTF-8 dan Environment
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================================
echo        TeleAgent - Workstation ^& Mobile Gateway
echo    Autonomous AI Terminal Agent ^& Desktop Controller
echo ========================================================
echo.

:: 1. Verifikasi instalasi Python
where python >nul 2>&1
if errorlevel 1 (
    echo [X] Python tidak ditemukan di PATH sistem!
    echo     Silakan unduh dan pasang Python 3.10+ dari:
    echo     https://www.python.org/
    echo     Pastikan mencentang "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

:: Deteksi versi Python
for /f "tokens=*" %%i in ('python --version 2^>nul') do set "PYTHON_VERSION=%%i"
echo [i] Python terdeteksi: %PYTHON_VERSION%

:: 2. Pembuatan dan aktivasi Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [*] Virtual environment belum ditemukan. Menyiapkan environment via setup.bat...
    call setup.bat
    if errorlevel 1 (
        echo [X] Setup awal belum selesai.
        pause
        exit /b 1
    )
) else (
    call .venv\Scripts\activate.bat
)

:: Pastikan code page tetap UTF-8 setelah aktivasi venv
chcp 65001 >nul

:: 2.5. First-Run Guard: Verifikasi keberadaan file .env
if not exist ".env" (
    echo.
    echo [!] File konfigurasi .env belum ditemukan!
    echo [*] Meluncurkan Setup Wizard untuk konfigurasi awal...
    call setup.bat
    if not exist ".env" (
        echo [X] Setup belum selesai. TeleAgent membutuhkan file .env untuk berjalan.
        pause
        exit /b 1
    )
)

:: Cek argumen khusus jika hanya ingin menjalankan salah satu
if /i "%1"=="--bot" goto run_bot_only
if /i "%1"=="--cli" goto run_cli_only

:: ========================================================
:: 3. Peluncuran Otomatis Keduanya (Dual-Window)
:: ========================================================
echo.
echo [*] Meluncurkan 2 Jendela Layanan TeleAgent Sekaligus:
echo     [Window 1] TeleAgent (CLI / TUI)
echo     [Window 2] TeleAgent - Telegram Mobile Gateway (Live Monitoring)
echo.

:: Luncurkan Window 2: Telegram Mobile Gateway di jendela CMD terpisah
start "TeleAgent - Telegram Mobile Gateway" cmd /k "title TeleAgent - Telegram Mobile Gateway && chcp 65001 >nul && cd /d "%~dp0" && call .venv\Scripts\activate.bat && python bot_telegram.py"

:: Jalankan Window 1: TeleAgent (TUI) di jendela saat ini
echo [*] Memulai TeleAgent di jendela ini...
python app.py
goto end

:run_bot_only
echo [*] Menjalankan TeleAgent - Telegram Mobile Gateway saja...
python bot_telegram.py
goto end

:run_cli_only
echo [*] Menjalankan TeleAgent CLI saja...
python app.py
goto end

:end
if errorlevel 1 (
    echo.
    echo [!] Aplikasi berhenti dengan kode status: %errorlevel%
)

echo.
