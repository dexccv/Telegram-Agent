#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================"
echo "  GEMINI AGENT - TELEGRAM MOBILE GATEWAY LAUNCHER"
echo "========================================================"
echo ""

if [ ! -f ".venv/bin/python" ]; then
    echo "[INFO] Membuat virtual environment .venv..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "Memulai Gateway Telegram..."
echo "Biarkan proses ini berjalan agar laptop dapat menerima perintah dari HP."
echo "Tekan Ctrl+C untuk mematikan."
echo ""

python3 bot_telegram.py
