#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  GEMINI TERMINAL AGENT (Indonesiaku-Lang Engine)"
echo "========================================================"
echo ""

# 1. Verifikasi instalasi Python 3
if ! command -v python3 &> /dev/null; then
    echo "[X] python3 tidak ditemukan di sistem."
    echo "    Silakan pasang Python 3.10+ melalui package manager Anda."
    echo ""
    read -p "Tekan [Enter] untuk keluar..."
    exit 1
fi

PYTHON_VER=$(python3 --version 2>&1)
echo "[i] Python terdeteksi: $PYTHON_VER"

# 2. Pembuatan dan aktivasi Virtual Environment (.venv)
if [ ! -d ".venv" ]; then
    echo "[*] Membuat virtual environment baru di .venv..."
    python3 -m venv .venv
    echo "[i] Virtual environment berhasil dibuat."
fi

# Aktivasi venv
source .venv/bin/activate

# 3. Instalasi dependensi
echo "[*] Memeriksa dan menginstal dependensi dari requirements.txt..."
pip install -r requirements.txt --quiet || pip install -r requirements.txt

# 4. Jalankan aplikasi
echo ""
echo "[*] Meluncurkan Gemini Terminal Agent..."
echo ""
python3 app.py

# 5. Pause di akhir
echo ""
echo "========================================================"
echo "       Sesi Gemini Terminal Agent telah selesai."
echo "========================================================"
read -p "Tekan [Enter] untuk menutup launcher..."
