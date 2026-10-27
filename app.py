"""Pintu masuk aplikasi Gemini Terminal Agent berbasis Indonesiaku-Lang (.idk).

Secara otomatis menjalankan background service Telegram Mobile Gateway
sehingga laptop dapat dipantau dan dikendalikan secara real-time dari HP.
"""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
from pathlib import Path

from config import config_manager
from penerjemah_idk import jalankan_berkas_idk

_bot_process: subprocess.Popen | None = None


def mulai_server_bot_telegram() -> None:
    """Memulai bot Telegram di background jika token sudah dikonfigurasi."""
    global _bot_process
    token = config_manager.get_telegram_token() or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    bot_script = Path(__file__).parent / "bot_telegram.py"
    if not bot_script.exists():
        return

    try:
        _bot_process = subprocess.Popen(
            [sys.executable, str(bot_script)],
            cwd=str(Path(__file__).parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except Exception:
        pass


def hentikan_server_bot_telegram() -> None:
    """Menghentikan background bot Telegram saat aplikasi ditutup."""
    global _bot_process
    if _bot_process and _bot_process.poll() is None:
        try:
            _bot_process.terminate()
            _bot_process.wait(timeout=2)
        except Exception:
            try:
                _bot_process.kill()
            except Exception:
                pass


atexit.register(hentikan_server_bot_telegram)

if __name__ == "__main__":
    mulai_server_bot_telegram()
    try:
        jalankan_berkas_idk("aplikasi.idk")
    finally:
        hentikan_server_bot_telegram()
