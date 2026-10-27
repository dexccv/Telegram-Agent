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
echo Memulai server Ollama di latar belakang...
echo Biarkan jendela ini terbuka jika Anda ingin memantau log Ollama.
echo Tekan Ctrl+C untuk mematikan server.
echo ========================================================
echo.

ollama serve

pause
