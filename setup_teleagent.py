"""Setup Wizard Interaktif untuk TeleAgent (Zero-Friction Onboarding).

Memandu pengguna baru mengonfigurasi Telegram Bot Token, mendeteksi Telegram User ID
secara otomatis, memvalidasi Gemini API Key, dan menghasilkan file .env siap pakai.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


BANNER = r"""
======================================================================
  _____    _      ___                    _   
 |_   _|__| |___ / _ \  __ _ ___ _ _  __| |_ 
   | |/ -_) / -_) /_\ |/ _` / -_) ' \/ _`  _|
   |_|\___|_\___/_/   \_\__, \___|_||_\__|\__|
                        |___/                 
  Autonomous AI Terminal Agent & Mobile Telegram Gateway
======================================================================
"""


def clear_screen() -> None:
    """Membersihkan layar terminal."""
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    """Menampilkan banner TeleAgent."""
    print(BANNER)


def validate_telegram_token(token: str) -> tuple[bool, str]:
    """Memvalidasi Bot Token Telegram langsung ke server Telegram API."""
    token = token.strip()
    if not token or ":" not in token:
        return False, "Format token tidak valid (harus mengandung karakter ':')."

    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TeleAgent-Setup/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                bot_user = data.get("result", {})
                first_name = bot_user.get("first_name", "Bot")
                username = bot_user.get("username", "")
                return True, f"{first_name} (@{username})"
            return False, data.get("description", "Token ditolak oleh Telegram.")
    except Exception as exc:
        return False, f"Gagal menghubungi server Telegram: {exc}"


def auto_detect_telegram_user_id(token: str, timeout_seconds: int = 45) -> tuple[bool, str, str]:
    """Mendeteksi Telegram User ID secara otomatis dengan memantau getUpdates.

    Pengguna cukup membuka bot yang baru dibuat dan mengirimkan pesan /start atau teks apa pun.
    """
    token = token.strip()
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    # 1. Bersihkan update lama terlebih dahulu (ambil offset terakhir)
    last_update_id = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TeleAgent-Setup/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok") and data.get("result"):
                last_update_id = data["result"][-1]["update_id"]
                # Acknowledge update lama
                ack_url = f"{url}?offset={last_update_id + 1}"
                with urllib.request.urlopen(urllib.request.Request(ack_url, headers={"User-Agent": "TeleAgent-Setup/1.0"}), timeout=5):
                    pass
    except Exception:
        pass

    print("\n" + "=" * 62)
    print("  DETEKSI OTOMATIS USER ID TELEGRAM")
    print("=" * 62)
    print("  1. Buka aplikasi Telegram di HP / Desktop Anda.")
    print("  2. Cari bot yang baru Anda buat dari token di atas.")
    print("  3. Tekan START atau kirim pesan apa saja (misal: halo) ke bot.")
    print(f"  Menunggu pesan masuk (Maksimal {timeout_seconds} detik)...")
    print("=" * 62)

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        remaining = int(timeout_seconds - (time.time() - start_time))
        sys.stdout.write(f"\r  [⏳] Menunggu interaksi dari HP... ({remaining:02d} detik tersisa)  ")
        sys.stdout.flush()

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TeleAgent-Setup/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("result"):
                    for upd in data["result"]:
                        msg = upd.get("message") or upd.get("callback_query", {}).get("message") or {}
                        sender = msg.get("from") or {}
                        u_id = sender.get("id")
                        if u_id:
                            username = sender.get("username", sender.get("first_name", "User"))
                            print(f"\n\n  [SUCCESS] Berhasil mendeteksi pengirim!")
                            print(f"  User ID   : {u_id}")
                            print(f"  Username  : @{username}")
                            return True, str(u_id), str(username)
        except Exception:
            pass

        time.sleep(1.5)

    print("\n  [!] Waktu deteksi habis.")
    return False, "", ""


def validate_gemini_api_key(api_key: str) -> tuple[bool, str]:
    """Memvalidasi Gemini API Key langsung ke Google Generative Language API."""
    api_key = api_key.strip()
    if not api_key:
        return False, "API Key kosong."

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TeleAgent-Setup/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "models" in data:
                count = len(data["models"])
                return True, f"Valid ({count} model tersedia)"
            return False, "Format respons API tidak dikenali."
    except Exception as exc:
        return False, f"Validasi API Key gagal: {exc}"


def build_env_content(
    bot_token: str,
    user_id: str,
    gemini_key: str,
    groq_key: str = "",
    default_model: str = "gemini-2.5-flash",
    default_provider: str = "gemini",
) -> str:
    """Menyusun isi file .env yang terstruktur rapi dan bersih."""
    return f"""# ======================================================================
# TeleAgent - File Konfigurasi Lingkungan (.env)
# Autonomous AI Terminal Agent & Mobile Telegram Gateway
# ======================================================================

# 1. Konfigurasi Gateway Telegram Bot
# Token bot dari @BotFather
TELEGRAM_BOT_TOKEN={bot_token}

# User ID Telegram pemilik akun (akses eksklusif & proteksi perintah sistem)
TELEGRAM_ALLOWED_USER_ID={user_id}

# 2. Konfigurasi AI Provider (Gemini / Groq / Ollama)
# Kunci API resmi dari Google AI Studio: https://aistudio.google.com/app/apikey
GEMINI_API_KEY={gemini_key}

# Kunci API Groq (Opsional, untuk Llama-3 / Mixtral): https://console.groq.com/keys
GROQ_API_KEY={groq_key}

# 3. Model Default Saat Pertama Kali Berjalan
DEFAULT_AI_PROVIDER={default_provider}
DEFAULT_MODEL_NAME={default_model}

# 4. Pengaturan Sistem & Keamanan Sandbox
ANTIGRAVITY_AUTO_MAXIMIZE=true
SECURITY_SANDBOX_STRICT=true
"""


def run_interactive_wizard(env_path: Path) -> bool:
    """Menjalankan wizard pengaturan interaktif."""
    clear_screen()
    print_banner()

    print("Selamat datang di Wizard Setup Cepat TeleAgent!")
    print("Panduan ini akan membantu Anda menyiapkan TeleAgent hanya dalam 2 menit.\n")

    # --- LANGKAH 1: TELEGRAM BOT TOKEN ---
    print("┌────────────────────────────────────────────────────────┐")
    print("│ LANGKAH 1: TELEGRAM BOT TOKEN                          │")
    print("└────────────────────────────────────────────────────────┘")
    print("• Buka aplikasi Telegram, lalu cari @BotFather")
    print("• Kirim perintah /newbot dan ikuti instruksi penamaannya.")
    print("• Salin token API yang diberikan oleh @BotFather.\n")

    bot_token = ""
    bot_identity = ""
    while True:
        token_input = input("Masukkan Telegram Bot Token: ").strip()
        if not token_input:
            print("  [!] Token tidak boleh kosong. Silakan coba lagi.\n")
            continue

        print("  [*] Memverifikasi token ke server Telegram...")
        ok, res = validate_telegram_token(token_input)
        if ok:
            bot_token = token_input
            bot_identity = res
            print(f"  [✓] Sukses terhubung ke bot: {bot_identity}\n")
            break
        else:
            print(f"  [X] Token ditolak: {res}")
            pilihan = input("  Apakah ingin mencoba lagi? (y/n, default: y): ").strip().lower()
            if pilihan == "n":
                print("  Setup dibatalkan oleh pengguna.")
                return False
            print()

    # --- LANGKAH 2: TELEGRAM USER ID ---
    print("┌────────────────────────────────────────────────────────┐")
    print("│ LANGKAH 2: TELEGRAM USER ID (HAK AKSES BOT)            │")
    print("└────────────────────────────────────────────────────────┘")
    print("TeleAgent hanya merespon perintah dari User ID pemilik demi keamanan laptop.\n")

    user_id = ""
    print("Pilihan metode pendeteksian User ID:")
    print("  [1] Deteksi Otomatis (Cukup kirim pesan ke bot dari HP) - Disarankan")
    print("  [2] Masukkan ID Secara Manual (Jika Anda sudah tahu ID Anda)")

    metode = input("\nPilih metode (1/2, default: 1): ").strip()
    if metode != "2":
        ok, detected_id, username = auto_detect_telegram_user_id(bot_token, timeout_seconds=45)
        if ok:
            user_id = detected_id
        else:
            print("\n  Pendeteksian otomatis tidak menerima pesan.")
            user_id = input("  Masukkan User ID Telegram Anda secara manual: ").strip()
    else:
        user_id = input("Masukkan User ID Telegram Anda: ").strip()

    while not user_id.isdigit():
        print("  [!] User ID harus berupa angka unik (misal: 123456789).")
        user_id = input("Masukkan User ID Telegram Anda: ").strip()

    print(f"  [✓] User ID tersimpan: {user_id}\n")

    # --- LANGKAH 3: GEMINI API KEY ---
    print("┌────────────────────────────────────────────────────────┐")
    print("│ LANGKAH 3: GOOGLE GEMINI API KEY                       │")
    print("└────────────────────────────────────────────────────────┘")
    print("• Dapatkan API Key gratis di Google AI Studio:")
    print("  https://aistudio.google.com/app/apikey\n")

    gemini_key = ""
    while True:
        key_input = input("Masukkan Gemini API Key: ").strip()
        if not key_input:
            print("  [!] Gemini API Key diperlukan untuk menjalankan kecerdasan agent.\n")
            continue

        print("  [*] Memvalidasi API Key ke server Google...")
        ok, res = validate_gemini_api_key(key_input)
        if ok:
            gemini_key = key_input
            print(f"  [✓] Gemini API Key berhasil diverifikasi: {res}\n")
            break
        else:
            print(f"  [!] Peringatan: {res}")
            lanjut = input("  Tetap gunakan key ini? (y/n, default: y): ").strip().lower()
            if lanjut != "n":
                gemini_key = key_input
                break
            print()

    # --- LANGKAH 4: GROQ API KEY (OPSIONAL) ---
    print("┌────────────────────────────────────────────────────────┐")
    print("│ LANGKAH 4: GROQ API KEY (OPSIONAL)                     │")
    print("└────────────────────────────────────────────────────────┘")
    print("• Digunakan untuk inferensi kilat Llama-3 / Mixtral.")
    print("• Kosongkan (tekan Enter) jika tidak ingin menggunakan Groq saat ini.\n")

    groq_key = input("Masukkan Groq API Key (Opsional, Enter untuk lewati): ").strip()

    # --- LANGKAH 5: MENULIS FILE .ENV ---
    print("\n[*] Menulis konfigurasi ke file .env...")
    env_content = build_env_content(
        bot_token=bot_token,
        user_id=user_id,
        gemini_key=gemini_key,
        groq_key=groq_key,
    )

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print(f"[✓] Berkas konfigurasi berhasil disimpan di: {env_path.resolve()}\n")
    except Exception as exc:
        print(f"[X] Gagal menyimpan file .env: {exc}")
        return False

    print("======================================================================")
    print("  🎉 KONFIGURASI TELEAGENT SELESAI & SIAP DIGUNAKAN! 🎉")
    print("======================================================================")
    print("  • Gateway Bot Telegram : Aktif")
    print(f"  • Pemilik Terdaftar    : User ID {user_id}")
    print("  • AI Engine Terhubung  : Google Gemini")
    print("======================================================================\n")

    tanya_run = input("Apakah Anda ingin langsung meluncurkan TeleAgent sekarang? (y/n, default: y): ").strip().lower()
    if tanya_run != "n":
        bat_file = env_path.parent / "run.bat"
        if bat_file.exists():
            print("\n[*] Meluncurkan TeleAgent Dual-Window Launcher...")
            os.system(f'start "" "{bat_file}"')
        else:
            print("\nSilakan jalankan run.bat untuk memulai TeleAgent.")

    return True


def main() -> None:
    """Fungsi utama setup wizard."""
    # Mode uji / automated test
    if "--test" in sys.argv:
        print("Test mode active.")
        test_env = Path.cwd() / "test_teleagent.env"
        content = build_env_content("123:dummy", "5467304452", "AIzaSyDummyKey")
        test_env.write_text(content, encoding="utf-8")
        assert test_env.exists()
        test_env.unlink()
        print("Test mode completed successfully.")
        sys.exit(0)

    target_env = Path.cwd() / ".env"
    if target_env.exists():
        print(f"[!] File .env sudah ada di: {target_env.resolve()}")
        pilihan = input("Apakah Anda ingin mengonfigurasi ulang? (y/n, default: n): ").strip().lower()
        if pilihan != "y":
            print("Pengaturan dibatalkan. Konfigurasi yang ada tetap dipertahankan.")
            sys.exit(0)

    success = run_interactive_wizard(target_env)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

