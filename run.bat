@echo off
setlocal enabledelayedexpansion
set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================
echo  Gemini Terminal Agent - Self-Healing Mode
echo ========================================
echo.

:: 1. Verifikasi instalasi Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python tidak ditemukan di PATH sistem.
    echo     Silakan unduh dan pasang Python 3.10+ dari https://www.python.org/
    echo     Pastikan mencentang opsi "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

:: Tampilkan versi Python
for /f "tokens=*" %%i in ('python --version 2^>&1') do set PYTHON_VERSION=%%i
echo [i] Python terdeteksi: !PYTHON_VERSION!

:: 2. Pembuatan dan aktivasi Virtual Environment (.venv)
if not exist ".venv" (
    echo [*] Membuat virtual environment baru di .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [X] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
    echo [i] Virtual environment berhasil dibuat.
)

:: Aktivasi venv
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [X] Gagal mengaktifkan virtual environment.
    pause
    exit /b 1
)

:: 3. Verifikasi dan instalasi dependensi
echo [*] Memeriksa dan menginstal dependensi dari requirements.txt...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [!] Gagal memasang beberapa paket dependensi. Mencoba instalasi verbose:
    pip install -r requirements.txt
)

echo.
echo Pilih mode jalankan:
echo   1. Mode Normal (tanpa self-healing)
echo   2. Mode Self-Healing (otomatis perbaiki crash)
echo.
set /p choice="Pilih [1/2] (default: 2): "
if "%choice%"=="1" (
    python app.py
) else (
    python run_with_healing.py tui
)
pause
