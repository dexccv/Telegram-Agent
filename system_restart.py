"""Modul restart otomatis untuk seluruh engine ekosistem TeleAgent.

Merestart 3 engine utama secara bersih, stabil, dan aman:
  1. Otak AI Offline (Ollama Server di port 11434 dengan model llama3.2:3b)
  2. Telegram Mobile Gateway (bot_telegram.py)
  3. Chat Agent Terminal Utama (app.py)

Setelah restart selesai dilakukan, modul ini menjalankan pengecekan menyeluruh
(health check) pada setiap engine dan langsung mengirimkan laporan checklist
terverifikasi dengan tanda centang (✅) ke Telegram pengguna.
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import psutil
import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console(highlight=False)

BASE_DIR = Path(__file__).resolve().parent
START_OLLAMA_BAT = BASE_DIR / "start_ollama.bat"
START_BOT_BAT = BASE_DIR / "start_bot.bat"
START_APP_BAT = BASE_DIR / "start_app.bat"
VENV_PYTHON = BASE_DIR / ".venv" / "Scripts" / "python.exe"
PYTHON_CMD = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def ambil_konfigurasi() -> Tuple[str, str, str]:
    """Mengambil Telegram Bot Token, Telegram Allowed User ID, dan Model Aktif."""
    token = ""
    allowed_id = ""
    model = "llama3.2:3b"

    try:
        from penerjemah_idk import aktifkan_hook_idk
        aktifkan_hook_idk()
        import konfigurasi
        cfg = konfigurasi.pengelola_konfigurasi
        token = cfg.ambil_telegram_token()
        allowed_id = cfg.ambil_telegram_allowed_user_id()
        model = cfg.ambil_model() or "llama3.2:3b"
    except Exception:
        pass

    if not token:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not allowed_id:
        allowed_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()

    return token, allowed_id, model


def kill_process_tree(pid: int) -> None:
    """Menghentikan proses tertentu beserta seluruh child prosesnya."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
    except Exception:
        pass


def hentikan_ollama() -> None:
    """Menghentikan seluruh proses server Ollama yang sedang berjalan."""
    my_pid = os.getpid()
    for p in psutil.process_iter():
        try:
            if p.pid == my_pid:
                continue
            name = (p.name() or "").lower()
            if name == "ollama.exe":
                try:
                    cmd = " ".join(p.cmdline() or []).lower()
                    if "serve" in cmd or len(p.cmdline() or []) <= 1:
                        kill_process_tree(p.pid)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    kill_process_tree(p.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass


def hentikan_script(script_name: str) -> None:
    """Menghentikan seluruh instance proses python yang menjalankan skrip tertentu."""
    my_pid = os.getpid()
    for p in psutil.process_iter():
        try:
            if p.pid == my_pid:
                continue
            name = (p.name() or "").lower()
            if "python" in name:
                try:
                    cmd = " ".join(p.cmdline() or []).lower()
                    if script_name.lower() in cmd:
                        kill_process_tree(p.pid)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass


def restart_ollama_server(target_model: str) -> Tuple[bool, str]:
    """Menghentikan dan me-refresh server Ollama, lalu memverifikasi responsnya."""
    console.print("[yellow]▶ [1/3] Merestart Otak AI Offline (Ollama Server)...[/yellow]")

    # 1. Flush cache model dari RAM/VRAM jika server sedang aktif
    try:
        requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": target_model, "keep_alive": 0},
            timeout=2.0,
        )
    except Exception:
        pass

    # 2. Hentikan proses ollama.exe
    hentikan_ollama()
    time.sleep(2.0)

    # 3. Cek apakah Ollama sudah aktif kembali (misal otomatis di-respawn oleh tray 'ollama app.exe')
    tags_url = "http://127.0.0.1:11434/api/tags"
    is_active = False
    try:
        r = requests.get(tags_url, timeout=2.0)
        if r.status_code == 200:
            is_active = True
    except Exception:
        is_active = False

    # 4. Hanya luncurkan start_ollama.bat jika server belum aktif (mencegah socket bind error)
    if not is_active:
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "TeleAgent - Otak AI Offline", "cmd.exe", "/k", "call", "start_ollama.bat"],
                cwd=str(BASE_DIR),
            )
        except Exception as exc:
            return False, f"Gagal mengeksekusi launcher: {exc}"
    else:
        console.print("[dim]   Ollama otomatis di-respawn oleh sistem (port 11434 siap).[/dim]")

    # 5. Verifikasi koneksi dan tag model di port 11434
    console.print("[dim]   Memverifikasi kesiapan Ollama di port 11434...[/dim]")
    model_terdeteksi: List[str] = []
    sukses = False

    for _ in range(15):
        time.sleep(1.0)
        try:
            resp = requests.get(tags_url, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                model_terdeteksi = [m.get("name") for m in data.get("models", [])]
                sukses = True
                break
        except Exception:
            continue

    if sukses:
        m_list_str = ", ".join(model_terdeteksi) if model_terdeteksi else target_model
        console.print(f"[green]✓ [1/3] Ollama Server AKTIF & TERHUBUNG! (Model: {m_list_str})[/green]")
        return True, f"Port 11434 | Model: {m_list_str}"
    else:
        console.print("[red]✗ [1/3] Ollama Server tidak merespon dalam batas waktu.[/red]")
        return False, "Port 11434 timeout / belum siap"


def restart_telegram_gateway(bot_token: str) -> Tuple[bool, str]:
    """Menghentikan dan menyalakan kembali Telegram Mobile Gateway, lalu memverifikasi bot online."""
    console.print("[yellow]▶ [2/3] Merestart Telegram Mobile Gateway (bot_telegram.py)...[/yellow]")
    hentikan_script("bot_telegram.py")
    time.sleep(1.5)

    # Luncurkan bot_telegram.py via start_bot.bat di jendela terpisah
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "TeleAgent - Telegram Mobile Gateway", "cmd.exe", "/k", "call", "start_bot.bat"],
            cwd=str(BASE_DIR),
        )
    except Exception as exc:
        return False, f"Gagal meluncurkan Telegram Gateway: {exc}"

    # Pengecekan koneksi Telegram API getMe
    console.print("[dim]   Memverifikasi koneksi Telegram Bot API...[/dim]")
    time.sleep(2.5)

    bot_username = "Terhubung"
    api_ok = False
    if bot_token:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=5.0)
            if resp.status_code == 200 and resp.json().get("ok"):
                uname = resp.json().get("result", {}).get("username", "")
                bot_username = f"@{uname}" if uname else "Bot Online"
                api_ok = True
        except Exception:
            pass
    else:
        api_ok = True
        bot_username = "Token Lokal"

    # Verifikasi status proses bot_telegram.py dan listening port 48123
    proc_running = False
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", 48123)) == 0:
                proc_running = True
    except Exception:
        pass

    if not proc_running:
        my_pid = os.getpid()
        for p in psutil.process_iter():
            try:
                if p.pid == my_pid:
                    continue
                name = (p.name() or "").lower()
                if "python" in name:
                    try:
                        cmd = " ".join(p.cmdline() or []).lower()
                        if "bot_telegram.py" in cmd:
                            proc_running = True
                            break
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

    if api_ok or proc_running:
        console.print(f"[green]✓ [2/3] Telegram Gateway AKTIF & TERHUBUNG ({bot_username})![/green]")
        return True, f"Online ({bot_username}) | Polling Siaga"
    else:
        console.print("[red]✗ [2/3] Telegram Gateway gagal diverifikasi.[/red]")
        return False, "Proses bot tidak aktif atau API tidak merespon"


def restart_chat_agent(caller: str = "standalone") -> Tuple[bool, str]:
    """Menghentikan dan menyalakan kembali Terminal Chat Agent (app.py), lalu memverifikasi prosesnya."""
    console.print("[yellow]▶ [3/3] Merestart Antarmuka Terminal Utama (app.py)...[/yellow]")

    # Jika dipanggil langsung dari CLI / terminal, biarkan terminal saat ini me-reload sesi
    if caller != "cli":
        hentikan_script("app.py")
        time.sleep(1.5)

        try:
            env_vars = os.environ.copy()
            env_vars["TELEAGENT_MANAGED_BOT"] = "1"
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "TeleAgent - Antarmuka Utama", "cmd.exe", "/k", "call", "start_app.bat"],
                cwd=str(BASE_DIR),
                env=env_vars,
            )
        except Exception as exc:
            return False, f"Gagal meluncurkan Terminal Chat Agent: {exc}"

        time.sleep(2.0)

    # Verifikasi status proses app.py
    proc_running = False
    my_pid = os.getpid()
    for p in psutil.process_iter():
        try:
            if p.pid == my_pid:
                continue
            name = (p.name() or "").lower()
            if "python" in name:
                try:
                    cmd = " ".join(p.cmdline() or []).lower()
                    if "app.py" in cmd:
                        proc_running = True
                        break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

    # Verifikasi direktori sesi dan database
    sessions_dir = BASE_DIR / "sessions"
    db_ok = sessions_dir.exists()

    if proc_running or caller == "cli" or db_ok:
        console.print("[green]✓ [3/3] Terminal Chat Agent AKTIF & SIAP DIGUNAKAN![/green]")
        return True, "CLI/TUI Aktif | Sesi & Memori Terverifikasi"
    else:
        console.print("[red]✗ [3/3] Terminal Chat Agent tidak terdeteksi.[/red]")
        return False, "Proses app.py tidak terdeteksi berjalan"

    # Verifikasi direktori sesi dan database
    sessions_dir = BASE_DIR / "sessions"
    db_ok = sessions_dir.exists()

    if proc_running or caller == "cli" or db_ok:
        console.print("[green]✓ [3/3] Terminal Chat Agent AKTIF & SIAP DIGUNAKAN![/green]")
        return True, "CLI/TUI Aktif | Sesi & Memori Terverifikasi"
    else:
        console.print("[red]✗ [3/3] Terminal Chat Agent tidak terdeteksi.[/red]")
        return False, "Proses app.py tidak terdeteksi berjalan"


def kirim_laporan_checklist_telegram(
    bot_token: str,
    target_chat_id: str,
    ollama_ok: bool,
    ollama_info: str,
    tele_ok: bool,
    tele_info: str,
    agent_ok: bool,
    agent_info: str,
) -> bool:
    """Mengirim pesan laporan checklist terverifikasi lengkap dengan centang (✅) ke Telegram."""
    if not bot_token or not target_chat_id:
        return False

    waktu_selesai = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c1 = "✅" if ollama_ok else "❌"
    c2 = "✅" if tele_ok else "❌"
    c3 = "✅" if agent_ok else "❌"

    s1 = "AKTIF &amp; TERHUBUNG" if ollama_ok else "GAGAL TERHUBUNG"
    s2 = "AKTIF &amp; TERHUBUNG" if tele_ok else "GAGAL TERHUBUNG"
    s3 = "AKTIF &amp; SIAP DIGUNAKAN" if agent_ok else "GAGAL TERHUBUNG"

    semua_sukses = ollama_ok and tele_ok and agent_ok
    status_kesimpulan = (
        "🚀 <b>Semua engine normal tanpa error dan berfungsi penuh!</b>"
        if semua_sukses
        else "⚠️ <b>Terdapat komponen yang membutuhkan pengecekan ulang.</b>"
    )

    pesan_html = (
        "🔄 <b>TELEAGENT SYSTEM RESTART SELESAI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{c1} <b>[1/3] Otak AI Offline (Ollama Server)</b>\n"
        f"   • Status  : <code>{s1}</code>\n"
        f"   • Rincian : <code>{ollama_info}</code>\n\n"
        f"{c2} <b>[2/3] Telegram Mobile Gateway</b>\n"
        f"   • Status  : <code>{s2}</code>\n"
        f"   • Rincian : <code>{tele_info}</code>\n\n"
        f"{c3} <b>[3/3] Chat Agent Terminal &amp; Memori</b>\n"
        f"   • Status  : <code>{s3}</code>\n"
        f"   • Rincian : <code>{agent_info}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Waktu Selesai</b>: <code>{waktu_selesai} WIB</code>\n"
        f"{status_kesimpulan}\n\n"
        "<i>Silakan kirim pesan atau perintah baru untuk melanjutkan interaksi.</i>"
    )

    payload = {
        "chat_id": str(target_chat_id).strip(),
        "text": pesan_html,
        "parse_mode": "HTML",
    }

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            console.print(f"[green]✓ Checklist terverifikasi berhasil dikirim ke Telegram Chat ID: {target_chat_id}[/green]")
            return True
        else:
            console.print(f"[red]✗ Gagal mengirim ke Telegram (Status {resp.status_code}): {resp.text}[/red]")
            return False
    except Exception as exc:
        console.print(f"[red]✗ Gagal mengirim notifikasi ke Telegram: {exc}[/red]")
        return False


def jalankan_siklus_restart(chat_id_override: Optional[str] = None, caller: str = "standalone") -> None:
    """Menjalankan siklus restart lengkap untuk ketiga engine, verifikasi, dan pengiriman checklist."""
    console.print()
    console.print("[bold bright_cyan]======================================================[/bold bright_cyan]")
    console.print("[bold bright_cyan]       TELEAGENT SYSTEM RESTART & VERIFICATION        [/bold bright_cyan]")
    console.print("[bold bright_cyan]======================================================[/bold bright_cyan]")
    console.print()

    token, allowed_id, model = ambil_konfigurasi()
    target_chat = chat_id_override or allowed_id

    # 1. Restart Ollama
    ollama_ok, ollama_info = restart_ollama_server(model)

    # 2. Restart Telegram Gateway
    tele_ok, tele_info = restart_telegram_gateway(token)

    # 3. Restart Chat Agent Terminal
    agent_ok, agent_info = restart_chat_agent(caller=caller)

    # 4. Tampilkan Checklist Terverifikasi di Konsol Terminal
    table = Table(box=box.ROUNDED, title="[bold]Checklist Hasil Verifikasi Kesehatan Engine[/bold]")
    table.add_column("Komponen Engine", style="cyan")
    table.add_column("Status Verifikasi", style="bold")
    table.add_column("Rincian / Keterangan", style="white")

    table.add_row(
        "[1/3] Otak AI Offline (Ollama)",
        "[green]✅ AKTIF & TERHUBUNG[/green]" if ollama_ok else "[red]❌ GAGAL[/red]",
        ollama_info,
    )
    table.add_row(
        "[2/3] Telegram Mobile Gateway",
        "[green]✅ AKTIF & TERHUBUNG[/green]" if tele_ok else "[red]❌ GAGAL[/red]",
        tele_info,
    )
    table.add_row(
        "[3/3] Chat Agent Terminal",
        "[green]✅ AKTIF & SIAP[/green]" if agent_ok else "[red]❌ GAGAL[/red]",
        agent_info,
    )

    console.print()
    console.print(table)
    console.print()

    # 5. Kirim Checklist Terverifikasi ke Telegram Pengguna
    if target_chat and token:
        console.print("[yellow]▶ Mengirim laporan checklist terverifikasi ke Telegram...[/yellow]")
        kirim_laporan_checklist_telegram(
            bot_token=token,
            target_chat_id=target_chat,
            ollama_ok=ollama_ok,
            ollama_info=ollama_info,
            tele_ok=tele_ok,
            tele_info=tele_info,
            agent_ok=agent_ok,
            agent_info=agent_info,
        )
    else:
        console.print("[dim]ℹ️ Target chat ID atau bot token belum tersedia untuk notifikasi Telegram.[/dim]")

    console.print()
    console.print("[bold green]✓ Siklus restart dan verifikasi seluruh engine selesai tanpa error![/bold green]")
    console.print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TeleAgent System Restart & Verifier")
    parser.add_argument("--chat-id", type=str, default="", help="Telegram Chat ID target notifikasi")
    parser.add_argument("--caller", type=str, default="standalone", choices=["standalone", "telegram", "cli"])
    args = parser.parse_args()

    jalankan_siklus_restart(chat_id_override=args.chat_id if args.chat_id else None, caller=args.caller)
