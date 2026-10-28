@echo off
title Gemini Terminal Agent
cd /d "%~dp0"

:: 0. Konfigurasi Code Page UTF-8 dan Environment
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================================
echo        Gemini Terminal Agent - Workstation & Gateway
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
    echo [*] Virtual environment belum ditemukan. Membuat .venv baru...
    python -m venv .venv
    if errorlevel 1 (
        echo [X] Gagal membuat virtual environment .venv.
        echo     Pastikan izin akses direktori mencukupi.
        echo.
        pause
        exit /b 1
    )
    echo [i] Virtual environment berhasil dibuat.
    echo [*] Memasang dependensi awal dari requirements.txt...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

:: Pastikan code page tetap UTF-8 setelah aktivasi venv
chcp 65001 >nul

:: Cek argumen khusus jika hanya ingin menjalankan salah satu
if /i "%1"=="--bot" goto run_bot_only
if /i "%1"=="--cli" goto run_cli_only

:: ========================================================
:: 3. Peluncuran Otomatis Keduanya (Dual-Window)
:: ========================================================
echo.
echo [*] Meluncurkan 2 Jendela Layanan Sekaligus:
echo     [Window 1] Gemini Terminal Agent (CLI / TUI)
echo     [Window 2] Telegram Mobile Gateway (Live Monitoring)
echo.

:: Luncurkan Window 2: Telegram Mobile Gateway di jendela CMD terpisah
start "Gemini Agent - Telegram Mobile Gateway" cmd /k "title Gemini Agent - Telegram Mobile Gateway && chcp 65001 >nul && cd /d "%~dp0" && call .venv\Scripts\activate.bat && python bot_telegram.py"

:: Jalankan Window 1: Gemini Terminal Agent (TUI) di jendela saat ini
echo [*] Memulai Gemini Terminal Agent di jendela ini...
python app.py
goto end

:run_bot_only
echo [*] Menjalankan Telegram Mobile Gateway saja...
python bot_telegram.py
goto end

:run_cli_only
echo [*] Menjalankan Gemini Terminal Agent saja...
python app.py
goto end

:end
if errorlevel 1 (
    echo.
    echo [!] Aplikasi berhenti dengan kode status: %errorlevel%
)

echo.
echo ========================================================
echo Sesi selesai. Tekan sembarang tombol untuk menutup jendela...
pause >nul
