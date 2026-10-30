@echo off
title Ollama Server - Models di D:\.ollama\models
cd /d "%~dp0"

set "OLLAMA_MODELS=D:\.ollama\models"
set "OLLAMA_HOST=127.0.0.1:11434"

echo ========================================================
echo   OLLAMA SERVER LAUNCHER (Models di D:\.ollama\models)
echo ========================================================
echo.
echo [i] Direktori Model : %OLLAMA_MODELS%
echo [i] Alamat Host     : http://%OLLAMA_HOST%
echo.

:: 1. Cek apakah server Ollama sudah aktif dan mendengarkan di port 11434
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference = 'SilentlyContinue'; try { $r = (Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1 -UseBasicParsing).StatusCode; if ($r -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto ollama_already_active
goto start_ollama_process

:ollama_already_active
echo [OK] Server Ollama sudah aktif dan berjalan di port 11434.
echo      Tidak perlu menjalankan instance ganda.
echo.
exit /b 0

:start_ollama_process
echo Memulai server Ollama di latar belakang...
echo Biarkan jendela ini terbuka jika Anda ingin memantau log Ollama.
echo Tekan Ctrl+C untuk mematikan server.
echo ========================================================
echo.

ollama serve

pause
