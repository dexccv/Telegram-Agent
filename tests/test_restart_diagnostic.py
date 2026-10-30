"""Diagnostic Feedback Loop for TeleAgent System Restart.

Tests:
1. Port 11434 bind conflict guard (start_ollama.bat must never crash when port 11434 is active).
2. Ollama API tags response & model validation (llama3.2:3b).
3. Telegram Bot API token validation & getMe response.
4. Clean process inspection & non-blocking execution.
5. Delivery of checklist message formatting.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from penerjemah_idk import aktifkan_hook_idk
aktifkan_hook_idk()
import konfigurasi


class TestRestartDiagnostic(unittest.TestCase):
    def setUp(self):
        self.cfg = konfigurasi.pengelola_konfigurasi
        self.bot_token = self.cfg.ambil_telegram_token() or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.allowed_id = self.cfg.ambil_telegram_allowed_user_id() or os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
        self.model = self.cfg.ambil_model() or "llama3.2:3b"

    def test_01_ollama_service_online_and_model_available(self):
        """Pastikan server Ollama merespon HTTP 200 dan model llama3.2:3b terpasang."""
        tags_url = "http://127.0.0.1:11434/api/tags"
        try:
            resp = requests.get(tags_url, timeout=3.0)
            self.assertEqual(resp.status_code, 200, "Ollama Server harus merespon status 200")
            models = [m.get("name") for m in resp.json().get("models", [])]
            self.assertTrue(any("llama3.2:3b" in m for m in models), f"Model llama3.2:3b harus ada di Ollama. Model terpasang: {models}")
        except requests.exceptions.RequestException as e:
            self.fail(f"Ollama Server tidak dapat dihubungi di port 11434: {e}")

    def test_02_start_ollama_bat_guard_prevents_socket_bind_error(self):
        """Memverifikasi bahwa start_ollama.bat tidak crash saat port 11434 sudah aktif."""
        bat_file = BASE_DIR / "start_ollama.bat"
        self.assertTrue(bat_file.exists(), "File start_ollama.bat harus ada")

        # Jalankan start_ollama.bat saat port 11434 sedang aktif
        proc = subprocess.run(
            ["cmd.exe", "/c", str(bat_file)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"start_ollama.bat harus keluar dengan kode 0 saat port sudah aktif. Output:\n{proc.stdout}\n{proc.stderr}")
        self.assertNotIn("bind: Only one usage of each socket address", proc.stdout + proc.stderr, "Error socket bind tidak boleh muncul!")

    def test_03_telegram_api_connectivity_and_credentials(self):
        """Pastikan kredensial bot Telegram valid dan dapat melakukan handshake ke Telegram API."""
        self.assertTrue(bool(self.bot_token), "TELEGRAM_BOT_TOKEN harus terkonfigurasi")
        self.assertTrue(bool(self.allowed_id), "TELEGRAM_ALLOWED_USER_ID harus terkonfigurasi")

        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        resp = requests.get(url, timeout=5.0)
        self.assertEqual(resp.status_code, 200, f"Handshake ke Telegram API gagal: {resp.text}")
        data = resp.json()
        self.assertTrue(data.get("ok"), "Respon Telegram getMe harus ok=true")
        username = data.get("result", {}).get("username")
        self.assertIsNotNone(username, "Bot Telegram harus memiliki username valid")

    def test_04_system_restart_module_execution(self):
        """Verifikasi bahwa modul system_restart.py dapat diimpor dan dieksekusi tanpa syntax error."""
        import system_restart
        token, allowed_id, model = system_restart.ambil_konfigurasi()
        self.assertTrue(bool(token), "Token harus terbaca oleh system_restart")
        self.assertTrue(bool(allowed_id), "Allowed user ID harus terbaca oleh system_restart")
        self.assertEqual(model, "llama3.2:3b", "Model aktif harus llama3.2:3b")

    def test_05_bot_singleton_guard_prevents_duplicate_and_exit_code_15(self):
        """Memastikan instance kedua bot_telegram.py keluar bersih (code 0) dan bukan crash code 15."""
        import socket
        test_sock = None
        bot_script = BASE_DIR / "bot_telegram.py"

        # Cek apakah port 48123 sudah dipegang oleh gateway nyata
        is_port_in_use = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", 48123)) == 0:
                is_port_in_use = True

        try:
            if not is_port_in_use:
                # Simulasikan lock port 48123 sedang dipegang oleh gateway utama
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                test_sock.bind(("127.0.0.1", 48123))
                test_sock.listen(1)

            # Jalankan bot_telegram.py di subproses saat socket terkunci
            proc = subprocess.run(
                [sys.executable, str(bot_script)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            # Instance kedua harus keluar dengan kode 0 (bukan 15) dan memberi pesan ramah
            self.assertEqual(proc.returncode, 0, f"Instance kedua harus keluar dengan code 0. Output:\n{proc.stdout}\n{proc.stderr}")
            self.assertIn("sudah aktif", proc.stdout + proc.stderr, "Harus memberi tahu bahwa gateway sudah aktif")
        finally:
            if test_sock:
                test_sock.close()

    def test_06_app_py_managed_bot_guard(self):
        """Memastikan app.py tidak men-spawn bot ganda jika TELEAGENT_MANAGED_BOT disetel."""
        import app
        os.environ["TELEAGENT_MANAGED_BOT"] = "1"
        try:
            app._bot_process = None
            app.mulai_server_bot_telegram()
            self.assertIsNone(app._bot_process, "app.py tidak boleh men-spawn _bot_process saat TELEAGENT_MANAGED_BOT=1")
        finally:
            os.environ.pop("TELEAGENT_MANAGED_BOT", None)


if __name__ == "__main__":
    unittest.main()


