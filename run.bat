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
echo        Gemini Terminal Agent - Workstation Assistant
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
for /f "tokens=*" %%i in ('python --version') do set "PYTHON_VERSION=%%i"
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

:: 3. Pemilihan Mode Eksekusi
echo.
echo Pilih mode eksekusi:
echo   1. Mode Normal [Langsung TUI app.py]
echo   2. Mode Self-Healing [Rekomendasi - Otomatis perbaiki crash]
echo   3. Mode Bot Telegram [Gateway Mobile - bot_telegram.py]
echo.
set "choice=2"
set /p "choice=Pilih 1, 2, atau 3 (default: 2): "

if "%choice%"=="1" (
    echo [*] Menjalankan Gemini Terminal Agent mode Normal...
    python app.py
) else (
    if "%choice%"=="3" (
        echo [*] Menjalankan Telegram Mobile Gateway...
        python bot_telegram.py
    ) else (
        echo [*] Menjalankan Gemini Terminal Agent mode Self-Healing...
        python run_with_healing.py tui
    )
)

if errorlevel 1 (
    echo.
    echo [!] Aplikasi berhenti dengan kode status: %errorlevel%
)

echo.
echo ========================================================
echo Sesi selesai. Tekan sembarang tombol untuk menutup jendela...
pause >nul
