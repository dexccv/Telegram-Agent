@echo off
setlocal enabledelayedexpansion
title TeleAgent - Quick Setup Wizard
chcp 65001 >nul

echo ======================================================================
echo    TeleAgent - One-Click Quick Setup ^& Environment Installer
echo    Autonomous AI Terminal Agent ^& Mobile Telegram Gateway
echo ======================================================================
echo.

:: 1. Deteksi ketersediaan Python di sistem
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python tidak ditemukan di sistem Anda!
    echo     Silakan instal Python 3.10 atau versi lebih baru dari https://www.python.org/
    echo     Pastikan mencentang opsi "Add python.exe to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>nul') do set "PY_VER=%%v"
echo [*] Menggunakan %PY_VER%

:: 2. Siapkan Virtual Environment (.venv)
if not exist ".venv\Scripts\python.exe" (
    echo [*] Membuat virtual environment baru di .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [X] Gagal membuat virtual environment!
        pause
        exit /b 1
    )
    echo [✓] Virtual environment berhasil dibuat.
) else (
    echo [✓] Virtual environment .venv sudah tersedia.
)

:: 3. Mengaktifkan Virtual Environment
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [X] Gagal mengaktifkan virtual environment .venv!
    pause
    exit /b 1
)

:: 4. Install / Update Dependensi dari requirements.txt
echo [*] Memeriksa dan menginstal paket pustaka (requirements.txt)...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [!] Peringatan: Beberapa dependensi mungkin gagal diinstal via quiet mode.
    echo [*] Mengulangi instalasi dengan log terbuka...
    python -m pip install -r requirements.txt
)
echo [✓] Seluruh dependensi pustaka TeleAgent siap.
echo.

:: 5. Meluncurkan Wizard Konfigurasi Interaktif (.env)
python setup_teleagent.py

echo.
echo Setup TeleAgent selesai.
exit /b 0
