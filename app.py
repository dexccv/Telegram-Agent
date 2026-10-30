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
    """Memulai bot Telegram di background jika token sudah dikonfigurasi dan belum aktif."""
    global _bot_process

    # 1. Jika gateway Telegram dikelola oleh launcher induk (run.bat / system_restart.py), jangan spawn ganda
    if os.environ.get("TELEAGENT_MANAGED_BOT") == "1":
        return

    token = config_manager.get_telegram_token() or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    # 2. Cek apakah Telegram Gateway sudah aktif via lock port 48123
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", 48123)) == 0:
                return  # Gateway sudah aktif di jendela / background lain
    except Exception:
        pass

    # 3. Robust process scan dengan perlindungan per-proses terhadap AccessDenied
    try:
        import psutil
        my_pid = os.getpid()
        for p in psutil.process_iter():
            try:
                if p.pid == my_pid:
                    continue
                cmd = " ".join(p.cmdline() or [])
                if "bot_telegram.py" in cmd:
                    return
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
    except Exception:
        pass

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


def mulai_server_ollama_jika_perlu() -> None:
    """Otomatis menyalakan server Ollama di latar belakang jika provider aktif adalah Ollama."""
    try:
        prov = config_manager.get_provider()
        if prov == "ollama":
            from agent import ensure_ollama_running, warmup_ollama_model_async
            base_url = config_manager.get_ollama_base_url()
            if ensure_ollama_running(base_url, timeout=3.0):
                warmup_ollama_model_async(base_url=base_url)
    except Exception:
        pass


atexit.register(hentikan_server_bot_telegram)

if __name__ == "__main__":
    mulai_server_bot_telegram()
    mulai_server_ollama_jika_perlu()
    try:
        jalankan_berkas_idk("aplikasi.idk")
    finally:
        hentikan_server_bot_telegram()
