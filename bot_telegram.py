"""Gateway Telegram Bot untuk Gemini Terminal Agent.

Memungkinkan pengguna mengendalikan AI Agent di laptop secara penuh dari handphone
kapan pun dan di mana pun melalui aplikasi Telegram dengan perlindungan keamanan whitelist.
"""

from __future__ import annotations

import asyncio
import ctypes
import datetime
import os
import platform
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console(highlight=False)

import telegram.error
from telegram import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Aktifkan runtime loader Indonesiaku-Lang
from penerjemah_idk import aktifkan_hook_idk

aktifkan_hook_idk()

# Modul logika ditulis dalam Indonesiaku-Lang (.idk) dan dimuat dinamis via hook penerjemah_idk
import agen  # type: ignore[import-not-found]
import konfigurasi  # type: ignore[import-not-found]
import memori  # type: ignore[import-not-found]
import pengelola_sesi  # type: ignore[import-not-found]
from logger import agent_logger


def get_user_info(update: Update) -> str:
    """Mendapatkan identitas pengirim pesan Telegram secara ringkas."""
    user = update.effective_user
    if not user:
        return "Anonim"
    name = user.first_name or "Pengguna"
    if user.last_name:
        name += f" {user.last_name}"
    u_name = f"@{user.username}" if user.username else ""
    return f"{name} (ID: {user.id}{' | ' + u_name if u_name else ''})"


def log_terminal_box(category: str, title: str, details: list[tuple[str, str]], color: str = "bright_cyan") -> None:
    """Mencetak log peristiwa Telegram yang rapi, profesional, berwarna dengan garis box bersambung."""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    w = 70
    tag = f"[{now}] {category.upper()}: {title}"
    head = f"[{color}]┌─── {tag} "
    fill_len = max(2, w - len(tag) - 5)
    head += ("─" * fill_len) + f"[/{color}]"
    console.print(head)
    for k, v in details:
        clean_v = str(v).replace("\n", " ").strip()
        if len(clean_v) > 75:
            clean_v = clean_v[:72] + "..."
        console.print(f"[{color}]│[/{color}] [bold]{k:<11}[/bold]: {clean_v}")
    console.print(f"[{color}]└" + ("─" * (w - 1)) + f"[/{color}]\n")

GUI_PROCESSES: dict[str, str] = {
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave Browser",
    "notepad.exe": "Notepad",
    "notepad++.exe": "Notepad++",
    "telegram.exe": "Telegram Desktop",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "explorer.exe": "File Explorer",
    "cmd.exe": "Command Prompt",
    "powershell.exe": "PowerShell",
    "windowsterminal.exe": "Windows Terminal",
    "antigravity ide.exe": "Antigravity IDE",
    "cursor.exe": "Cursor IDE",
    "ollama.exe": "Ollama Service",
    "slack.exe": "Slack",
}


def ambil_metrik_realtime() -> dict[str, Any]:
    """Mengambil status real-time laptop: baterai, Wi-Fi, jendela aktif, CPU, RAM, Uptime."""
    # 1. Baterai
    battery = psutil.sensors_battery()
    bat_percent = 100
    bat_status = "Tidak ada baterai"
    bat_str = "Tidak terdeteksi"
    if battery:
        bat_percent = battery.percent
        if battery.power_plugged:
            bat_status = "⚡ Sedang Mengisi Daya (Colok Charger AC)"
        else:
            bat_status = "🔋 Menggunakan Daya Baterai"
        bat_str = f"{battery.percent}% ({bat_status})"

    # 2. Wi-Fi
    wifi_ssid = "Tidak terhubung / Kabel LAN"
    wifi_signal = ""
    wifi_state = "Disconnected"
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"], text=True, errors="ignore", timeout=3
        )
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("SSID") and not line.startswith("BSSID"):
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    wifi_ssid = parts[1].strip()
            elif line.startswith("State") or line.startswith("Status"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    wifi_state = parts[1].strip()
            elif line.startswith("Signal") or line.startswith("Sinyal"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    wifi_signal = parts[1].strip()
    except Exception:
        pass

    wifi_full = f"{wifi_ssid}" + (f" (Sinyal: {wifi_signal} 📶)" if wifi_signal else "")

    # 3. Uptime
    try:
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{hours} jam {minutes} menit"
    except Exception:
        uptime_str = "-"

    # 4. CPU, RAM & Disk
    try:
        cpu = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu = 0.0

    try:
        mem = psutil.virtual_memory()
        ram_str = f"{mem.percent}% ({mem.used // (1024**2):,} MB / {mem.total // (1024**2):,} MB)"
    except Exception:
        ram_str = "-"

    disk_str = "Tersedia"
    try:
        disk_d = psutil.disk_usage("D:\\")
        disk_str = f"Drive D: {disk_d.free // (1024**3):,} GB bebas / {disk_d.total // (1024**3):,} GB"
    except Exception:
        try:
            disk_c = psutil.disk_usage("C:\\")
            disk_str = f"Drive C: {disk_c.free // (1024**3):,} GB bebas / {disk_c.total // (1024**3):,} GB"
        except Exception:
            pass

    # 5. IP Address
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "127.0.0.1"

    # 6. Jendela Fokus & Aplikasi Terbuka
    active_win = ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                active_win = buff.value.strip()
    except Exception:
        pass

    running_apps = set()
    for p in psutil.process_iter(["name"]):
        try:
            n = (p.info["name"] or "").lower()
            if n in GUI_PROCESSES:
                running_apps.add(GUI_PROCESSES[n])
        except Exception:
            pass

    return {
        "status": "ONLINE 🟢",
        "ip": ip,
        "uptime": uptime_str,
        "wifi_ssid": wifi_ssid,
        "wifi_signal": wifi_signal or "-",
        "wifi_state": wifi_state,
        "wifi_full": wifi_full,
        "battery_str": bat_str,
        "battery_percent": bat_percent,
        "battery_status": bat_status,
        "active_window": active_win or "Desktop / Layar Siaga",
        "running_apps": sorted(list(running_apps)),
        "cpu": f"{cpu}%",
        "ram": ram_str,
        "disk": disk_str,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S WIB"),
    }


def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Memecah teks panjang menjadi beberapa potongan sesuai batas limit Telegram."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.splitlines(keepends=True)
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) <= max_length:
            current_chunk += line
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            if len(line) > max_length:
                # Pecah paksa jika satu baris sangat panjang
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
            else:
                current_chunk = line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


class TelegramAgentGateway:
    def __init__(self) -> None:
        self.config = konfigurasi.pengelola_konfigurasi
        self.bot_token = self.config.ambil_telegram_token()
        self.allowed_user_id = self.config.ambil_telegram_allowed_user_id()
        self.provider = self.config.ambil_provider()
        self.api_key = self.config.ambil_api_key()
        self.model_name = self.config.ambil_model() or ("auto" if self.provider == "omniroute" else "gemini-2.5-flash")

        if not self.bot_token:
            print("[Galat] TELEGRAM_BOT_TOKEN belum disetel di ~/.gemini-agent/.env")
            sys.exit(1)

        if not self.api_key:
            print(f"[Galat] API Key untuk provider '{self.provider}' belum disetel di ~/.gemini-agent/.env")
            sys.exit(1)

        console.print(f"[dim]• Menginisialisasi Agen ({self.provider.upper()} - {self.model_name})...[/dim]")
        self.agent = agen.AgenGemini(api_key=self.api_key, model_name=self.model_name)
        self.file_picker_state: dict[int, dict] = {}
        console.print("[dim green]✓ Agen AI & modul sistem siap.[/dim green]")

    def is_authorized(self, update: Update) -> bool:
        """Memeriksa apakah pengirim pesan adalah pemilik sah laptop."""
        if not self.allowed_user_id:
            return True
        user = update.effective_user
        if not user:
            return False
        return str(user.id) == str(self.allowed_user_id)

    async def unauthorized_handler(self, update: Update) -> None:
        u_info = get_user_info(update)
        agent_logger.log_warning("telegram_gateway", f"Percobaan akses tidak dikenal dari {u_info}")
        log_terminal_box(
            "Keamanan", "Akses Ditolak",
            [("Pengguna", u_info), ("Status", "Ditolak oleh sistem keamanan whitelist")],
            color="bright_red",
        )
        if update.message:
            await update.message.reply_text(
                "⛔ Akses Ditolak: Bot ini dikunci secara privat untuk pemilik laptop ini."
            )

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        u_info = get_user_info(update)
        log_terminal_box("Command", "/start", [("Pengguna", u_info), ("Aksi", "Mengirim menu awal & perkenalan")], color="bright_yellow")

        user_name = update.effective_user.first_name if update.effective_user else "Pengguna"
        prov = self.config.ambil_provider().upper()
        m = ambil_metrik_realtime()
        msg = (
            f"Halo **{user_name}**! 👋\n\n"
            f"⌬ **Terminal Laptop Agent Siap Melayani**\n"
            f"• **Status Laptop**: ONLINE 🟢\n"
            f"• **Jaringan Wi-Fi**: `{m['wifi_full']}`\n"
            f"• **Daya Baterai**: `{m['battery_str']}`\n"
            f"• **Jendela Aktif**: `{m['active_window']}`\n"
            f"• **Provider AI**: `{prov}` (Model: `{self.agent.model_name}`)\n"
            f"• **Sesi Aktif**: `{self.agent.session.title}`\n\n"
            "Ketik instruksi apa saja (misal: *'buatkan script otomatisasi'*), "
            "ketik `/status` untuk memantau laptop secara lengkap, atau ketik `/help` untuk panduan."
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        help_text = (
            "📋 **Panduan Perintah Telegram Gateway (Real-Time Monitor)**\n\n"
            "• **Kirim Pesan Biasa**: Instruksi langsung ke AI Agent untuk eksekusi perintah di laptop.\n"
            "• `/status` : Dashboard real-time laptop (baterai, wifi, jendela aktif, CPU, RAM).\n"
            "• `/speed` : Uji kecepatan respon agent AI & pengiriman Telegram (latency & token/s).\n"
            "• `/wifi` : Pantau SSID dan kekuatan sinyal Wi-Fi laptop secara instan.\n"
            "• `/baterai` : Pantau persentase baterai & status pengisian charger.\n"
            "• `/jendela` : Pantau jendela yang sedang dibuka di layar & daftar aplikasi aktif.\n"
            "• `/kamera` : Ambil foto langsung dari webcam laptop dan kirimkan ke sini.\n"
            "• `/capture` : Ambil tangkapan layar (screenshot) tampilan display laptop saat ini.\n"
            "• `/cari <aplikasi> <keyword>` : Cari lagu/video di YouTube, Google, Spotify, dsb (misal: `/cari youtube the jansen`).\n"
            "• `/buka [target]` : Buka aplikasi desktop atau pantau tab browser (misal: `/buka chrome` atau `/buka spotify`).\n"
            "• `/tutup <nama>` : Tutup aplikasi desktop tertentu (misal: `/tutup chrome` atau `/tutup notepad`).\n"
            "• `/volume [level]` : Atur volume master laptop (0-100, +10, -10, mute, unmute) atau buka panel volume.\n"
            "• `/mute` / `/unmute` : Matikan atau nyalakan suara speaker laptop.\n"
            "• `/baca <file>` : Baca isi file teks dari laptop langsung di Telegram.\n"
            "• `/get <nama_berkas>` : Unduh berkas dari laptop langsung ke Telegram HP Anda.\n"
            "• `/provider [gemini/omniroute/ollama]` : Cek atau ganti provider AI aktif.\n"
            "• `/models` : Pindai & tampilkan daftar model AI yang tersedia.\n"
            "• `/model <nama>` : Ganti model aktif (misal: `/model qwen2.5-coder:7b`).\n"
            "• `/new [judul]` : Mulai sesi percakapan baru yang bersih.\n"
            "• `/sessions` : Lihat daftar sesi yang tersimpan di laptop.\n"
            "• `/load <no/id>` : Beralih ke sesi percakapan lama.\n"
            "• `/memory` : Lihat fakta memori jangka panjang agent.\n"
            "• `/stop` : Batalkan respon agen yang sedang berjalan.\n"
            "• **Kirim File/Foto**: Kirim berkas dari HP ke Telegram bot untuk disimpan di laptop."
        )
        if update.message:
            await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    def _build_status_dashboard(self) -> tuple[str, InlineKeyboardMarkup]:
        """Menghasilkan teks dashboard status real-time laptop beserta tombol navigasi inline."""
        metrics = ambil_metrik_realtime()
        tokens = (
            self.agent.last_usage_metadata.get("total_tokens", 0)
            if hasattr(self.agent, "last_usage_metadata")
            else 0
        )
        app_list_str = (
            ", ".join([f"`{a}`" for a in metrics["running_apps"]])
            if metrics["running_apps"]
            else "Tidak ada aplikasi khusus terdeteksi"
        )

        text = (
            "📊 **MONITORING LAPTOP REAL-TIME**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 **Status Laptop**: `{metrics['status']}`\n"
            f"🌐 **IP Jaringan**: `{metrics['ip']}`\n"
            f"⏱ **Laptop Menyala**: `{metrics['uptime']}`\n\n"
            f"📶 **Koneksi Wi-Fi**:\n"
            f"• SSID: `{metrics['wifi_ssid']}`\n"
            f"• Sinyal: `{metrics['wifi_signal']}` (Status: {metrics['wifi_state']})\n\n"
            f"🔋 **Baterai Laptop**:\n"
            f"• Daya: `{metrics['battery_percent']}%`\n"
            f"• Kondisi: {metrics['battery_status']}\n\n"
            f"🪟 **Jendela & Aplikasi Aktif**:\n"
            f"• Jendela Fokus: `{metrics['active_window']}`\n"
            f"• Aplikasi Terbuka: {app_list_str}\n\n"
            f"⚡ **Performa Hardware**:\n"
            f"• Beban CPU: `{metrics['cpu']}`\n"
            f"• Memori RAM: `{metrics['ram']}`\n"
            f"• Penyimpanan: `{metrics['disk']}`\n\n"
            f"🤖 **Terminal AI Agent**:\n"
            f"• Provider: `{self.provider.upper()}`\n"
            f"• Model AI: `{self.agent.model_name}`\n"
            f"• Sesi Aktif: `{self.agent.session.title}`\n"
            f"• Token Sesi: `{tokens:,} tokens`\n"
            f"• Lokasi: `{Path.cwd().name}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"_Diperbarui pada: {metrics['timestamp']}_"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔄 Segarkan Status", callback_data="refresh_status"),
                    InlineKeyboardButton("🔋 Cek Baterai", callback_data="btn_battery"),
                ],
                [
                    InlineKeyboardButton("📶 Info Wi-Fi", callback_data="btn_wifi"),
                    InlineKeyboardButton("🪟 Jendela & Apps", callback_data="btn_window"),
                ],
                [
                    InlineKeyboardButton("⚡ Uji Kecepatan (Speed Test)", callback_data="btn_speed_test"),
                    InlineKeyboardButton("🔊 Atur Volume", callback_data="btn_volume_panel"),
                ],
                [
                    InlineKeyboardButton("📸 Foto Webcam", callback_data="btn_camera"),
                    InlineKeyboardButton("🖥️ Screenshot Layar", callback_data="btn_capture_screen"),
                ],
            ]
        )
        return text, keyboard

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        u_info = get_user_info(update)
        log_terminal_box("Command", "/status", [("Pengguna", u_info), ("Aksi", "Mengirim dashboard monitoring laptop real-time")], color="bright_yellow")

        text, markup = self._build_status_dashboard()
        if update.message:
            await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

    async def wifi_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        m = ambil_metrik_realtime()
        msg = (
            "📶 **DETAIL KONEKSI WI-FI REAL-TIME**\n\n"
            f"• **Nama SSID**: `{m['wifi_ssid']}`\n"
            f"• **Kekuatan Sinyal**: `{m['wifi_signal']}`\n"
            f"• **Status Hubungan**: `{m['wifi_state']}`\n"
            f"• **Alamat IP Laptop**: `{m['ip']}`\n\n"
            f"_Waktu periksa: {m['timestamp']}_"
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def battery_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        m = ambil_metrik_realtime()
        msg = (
            "🔋 **STATUS DAYA BATERAI LAPTOP**\n\n"
            f"• **Persentase Daya**: `{m['battery_percent']}%`\n"
            f"• **Status Pengisian**: {m['battery_status']}\n\n"
            f"_Waktu periksa: {m['timestamp']}_"
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def window_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        m = ambil_metrik_realtime()
        app_list = (
            "\n".join([f"• `{a}`" for a in m["running_apps"]])
            if m["running_apps"]
            else "• Tidak ada aplikasi desktop khusus terdeteksi"
        )
        msg = (
            "🪟 **JENDELA & APLIKASI AKTIF DI LAPTOP**\n\n"
            f"🎯 **Jendela yang Sedang Dibuka di Depan Layar**:\n"
            f"👉 `{m['active_window']}`\n\n"
            f"📱 **Aplikasi Desktop yang Terbuka**:\n"
            f"{app_list}\n\n"
            f"_Waktu periksa: {m['timestamp']}_"
        )
        if update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return

        await query.answer("Memperbarui data...")

        if not self.is_authorized(update):
            return

        data = query.data
        u_info = get_user_info(update)
        log_terminal_box("Tombol Interaktif", str(data)[:35], [("Pengguna", u_info), ("Data", str(data))], color="bright_magenta")
        if data == "refresh_status":
            text, markup = self._build_status_dashboard()
            try:
                await query.edit_message_text(
                    text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        elif data == "btn_battery":
            m = ambil_metrik_realtime()
            msg = (
                f"🔋 **BATERAI LAPTOP**: `{m['battery_percent']}%`\n"
                f"Status: {m['battery_status']}\n"
                f"Waktu: `{m['timestamp']}`"
            )
            if query.message:
                await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        elif data == "btn_wifi":
            m = ambil_metrik_realtime()
            msg = (
                f"📶 **WI-FI LAPTOP**: `{m['wifi_ssid']}`\n"
                f"Sinyal: `{m['wifi_signal']}` ({m['wifi_state']})\n"
                f"IP: `{m['ip']}`\n"
                f"Waktu: `{m['timestamp']}`"
            )
            if query.message:
                await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        elif data == "btn_window":
            m = ambil_metrik_realtime()
            app_list = ", ".join([f"`{a}`" for a in m["running_apps"]])
            msg = (
                f"🪟 **JENDELA FOKUS**: `{m['active_window']}`\n\n"
                f"Aplikasi Terbuka:\n{app_list}\n"
                f"Waktu: `{m['timestamp']}`"
            )
            if query.message:
                await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        elif data == "btn_speed_test":
            await query.answer("⚡ Menjalankan uji kecepatan...")
            await self.speed_cmd(update, context)
        elif data == "btn_camera":
            await query.answer("📸 Mengambil foto kamera...")
            await self.camera_cmd(update, context)
        elif data == "btn_capture_screen":
            await query.answer("🖥️ Mengambil screenshot layar...")
            await self.capture_screen_cmd(update, context)
        elif data == "btn_volume_panel":
            import perkakas
            fn_vol = getattr(perkakas, "set_volume", None)
            cur_status = fn_vol("status") if fn_vol else "Volume tidak tersedia"
            msg = (
                f"🎛️ **PENGATUR VOLUME LAPTOP**\n\n"
                f"{cur_status}\n\n"
                "Pilih tingkat volume atau kontrol suara:"
            )
            if query.message:
                await query.message.reply_text(
                    msg,
                    reply_markup=self._build_volume_markup(),
                    parse_mode=ParseMode.MARKDOWN,
                )
        elif data.startswith("vol_"):
            action = data.replace("vol_", "")
            import perkakas
            fn_vol = getattr(perkakas, "set_volume", None)
            if fn_vol:
                if action == "down_10":
                    msg_res = fn_vol("-10")
                elif action == "up_10":
                    msg_res = fn_vol("+10")
                elif action == "mute":
                    msg_res = fn_vol("mute")
                elif action == "unmute":
                    msg_res = fn_vol("unmute")
                elif action == "status":
                    msg_res = fn_vol("status")
                else:
                    msg_res = fn_vol(action)

                cur_status = fn_vol("status")
                new_text = (
                    f"🎛️ **PENGATUR VOLUME LAPTOP**\n\n"
                    f"👉 {msg_res}\n"
                    f"{cur_status}\n\n"
                    "Gunakan tombol di bawah untuk mengubah volume:"
                )
                try:
                    await query.edit_message_text(
                        text=new_text,
                        reply_markup=self._build_volume_markup(),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass
        elif data.startswith("media_"):
            action = data.replace("media_", "")
            import perkakas
            fn_media = getattr(perkakas, "media_control", None)
            if fn_media:
                msg_res = fn_media(action)
                await query.answer(msg_res[:45])
                fn_vol = getattr(perkakas, "set_volume", None)
                cur_status = fn_vol("status") if fn_vol else ""
                new_text = (
                    f"🎛️ **KONTROL SUARA & PEMUTAR MUSIK LAPTOP**\n\n"
                    f"👉 {msg_res}\n"
                    f"{cur_status}\n\n"
                    "Gunakan tombol di bawah untuk kontrol pemutar lagu & volume:"
                )
                try:
                    await query.edit_message_text(
                        text=new_text,
                        reply_markup=self._build_volume_markup(),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass
        elif data.startswith("open_app:"):
            target_key = data.split(":", 1)[1]
            mapping = {
                "chrome": "chrome",
                "youtube": "https://www.youtube.com",
                "yt_hindia": "buka chrome lalu buka youtube dan cari lagu hindia",
                "spotify": "spotify",
                "notepad": "notepad",
                "calc": "calc",
                "vscode": "code",
                "explorer": "explorer",
                "terminal": "terminal",
                "edge": "msedge",
            }
            target_query = mapping.get(target_key, target_key)
            await query.answer(f"Membuka {target_key[:25]}...")
            import perkakas
            fn_open = getattr(perkakas, "open_application", None)
            if fn_open:
                res = await asyncio.to_thread(fn_open, target_query)
                if query.message:
                    await query.message.reply_text(f"🖥️ {res}")
        elif data == "open_hub:main":
            import perkakas
            fn_tabs = getattr(perkakas, "get_open_browser_tabs", None)
            tabs = fn_tabs() if fn_tabs else []
            count_str = f"{len(tabs)} tab aktif" if tabs else "belum ada tab aktif"
            new_text = (
                "📱 **PELUNCUR APLIKASI LAPTOP**\n\n"
                f"• **Browser Tab**: `{count_str}`\n"
                "• Pilih aplikasi di bawah untuk langsung dibuka di laptop:\n\n"
                "💡 **Untuk mencari lagu/video/informasi:**\n"
                "Gunakan: `/cari <aplikasi> <keyword>`\n"
                "Contoh: `/cari youtube the jansen`"
            )
            try:
                await query.edit_message_text(
                    text=new_text,
                    reply_markup=self._build_open_hub_markup(len(tabs)),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass
        elif data == "open_hub:yt":
            yt_text = (
                "🔍 **PENCARIAN CEPAT YOUTUBE**\n\n"
                "Gunakan perintah praktis:\n"
                "• `/cari youtube <keyword>`\n"
                "• `/cari yt <keyword>`\n\n"
                "Contoh: `/cari youtube the jansen`"
            )
            try:
                await query.edit_message_text(
                    text=yt_text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Buka", callback_data="open_hub:main")]]),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass
        elif data == "open_hub:tabs":
            text, markup = self._build_browser_tabs_markup()
            try:
                await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                if query.message:
                    await query.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        elif data.startswith("yt_search:"):
            q_term = data.split(":", 1)[1]
            await query.answer(f"🔍 Mencari {q_term[:20]}...")
            if query.message:
                await self.search_and_send_youtube(query.message, q_term)
        elif data.startswith("yt_play:"):
            vid = data.split(":", 1)[1]
            await query.answer("▶️ Memutar di laptop...")
            import perkakas
            fn_play = getattr(perkakas, "play_youtube_video", None)
            if fn_play:
                res = await asyncio.to_thread(fn_play, vid)
                if query.message:
                    await query.message.reply_text(
                        f"▶️ **Memutar Video di Laptop:**\n{res}\n🔗 https://www.youtube.com/watch?v={vid}"
                    )
        elif data.startswith("tab_focus:"):
            hwnd_val = int(data.split(":", 1)[1])
            import perkakas
            fn_focus = getattr(perkakas, "focus_window", None)
            if fn_focus:
                res = fn_focus(hwnd_val)
                await query.answer("🎯 Tab/Jendela dibawa ke depan!")
                if query.message:
                    await query.message.reply_text(f"🖥️ {res}")
        elif data.startswith("tab_close:"):
            hwnd_val = int(data.split(":", 1)[1])
            import perkakas
            fn_close_tab = getattr(perkakas, "close_window_tab", None)
            if fn_close_tab:
                res = fn_close_tab(hwnd_val)
                await query.answer("❌ Perintah tutup dikirim!")
                await asyncio.sleep(0.5)
                text, markup = self._build_browser_tabs_markup()
                try:
                    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass
        elif data.startswith("tab_media:"):
            hwnd_val = int(data.split(":", 1)[1])
            import perkakas
            fn_ctrl = getattr(perkakas, "control_browser_media", None)
            if fn_ctrl:
                res = fn_ctrl(hwnd_val, "play_pause")
                await query.answer(f"⏸️ {res[:40]}")
        elif data.startswith("fb_"):
            parts = data.split(":", 1)
            action = parts[0]
            val = parts[1] if len(parts) > 1 else ""
            user_id = update.effective_user.id if update.effective_user else 0
            state = getattr(self, "file_picker_state", {}).get(user_id, {})
            cur_dir = state.get("dir", Path.cwd())

            if action == "fb_loc":
                await query.answer("Memuat direktori...")
                if val == "ws":
                    target_dir = Path.cwd()
                elif val == "dl":
                    target_dir = Path.home() / "Downloads"
                elif val == "docs":
                    target_dir = Path.home() / "Documents"
                elif val == "dt":
                    target_dir = (
                        Path.home() / "OneDrive" / "Desktop"
                        if (Path.home() / "OneDrive" / "Desktop").exists()
                        else Path.home() / "Desktop"
                    )
                else:
                    target_dir = Path.cwd()
                text, markup = self._build_file_browser(user_id, target_dir, page=0)
                try:
                    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

            elif action == "fb_nav" and val == "up":
                await query.answer("Ke folder atas...")
                parent_dir = cur_dir.parent
                text, markup = self._build_file_browser(user_id, parent_dir, page=0)
                try:
                    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

            elif action == "fb_p":
                await query.answer()
                target_page = int(val)
                text, markup = self._build_file_browser(user_id, cur_dir, page=target_page)
                try:
                    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    pass

            elif action == "fb_d":
                await query.answer("Membuka folder...")
                item_idx = int(val)
                items = state.get("items", [])
                if 0 <= item_idx < len(items):
                    next_dir = items[item_idx]
                    text, markup = self._build_file_browser(user_id, next_dir, page=0)
                    try:
                        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

            elif action == "fb_f":
                item_idx = int(val)
                items = state.get("items", [])
                if 0 <= item_idx < len(items):
                    file_to_send = items[item_idx]
                    if file_to_send.exists() and file_to_send.is_file():
                        file_sz = file_to_send.stat().st_size
                        if file_sz > 50 * 1024 * 1024:
                            await query.message.reply_text("❌ Ukuran berkas melebihi batas 50 MB Telegram Bot.")
                            return
                        await query.answer("Mengirim berkas...")
                        status_msg = await query.message.reply_text(f"📤 Mengunggah berkas `{file_to_send.name}`...")
                        try:
                            with open(file_to_send, "rb") as f:
                                await query.message.reply_document(
                                    document=f, caption=f"📥 Berkas dari laptop:\n`{file_to_send}`"
                                )
                            try:
                                await status_msg.delete()
                            except Exception:
                                pass
                        except Exception as exc:
                            await query.message.reply_text(f"❌ Gagal mengirim berkas: {exc}")

            elif action == "fb_noop":
                await query.answer()

    async def speed_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Menguji kecepatan pengiriman bot Telegram dan kecepatan respon model AI."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        import time as _time
        import urllib.request as _urllib_req
        import psutil as _psutil

        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if not msg_target:
            return

        t0 = _time.perf_counter()
        probe_msg = await msg_target.reply_text("⚡ *Menguji kecepatan pengiriman Telegram & respon AI...*", parse_mode=ParseMode.MARKDOWN)
        tg_roundtrip_ms = int((_time.perf_counter() - t0) * 1000)

        # 1. Tes latency HTTP Telegram Server
        t_net = _time.perf_counter()
        try:
            req_tg = _urllib_req.Request("https://api.telegram.org", headers={"User-Agent": "SpeedCheck/1.0"})
            with _urllib_req.urlopen(req_tg, timeout=5) as _:
                pass
            tg_server_ping = int((_time.perf_counter() - t_net) * 1000)
        except Exception:
            tg_server_ping = int((_time.perf_counter() - t_net) * 1000)

        # 2. Tes kecepatan respon Agent AI (benchmark probe)
        prov = self.config.ambil_provider().upper()
        model = self.agent.model_name
        t_ai_start = _time.perf_counter()

        def _probe_ai() -> str:
            return self.agent.send_message("Tes koneksi dan kecepatan agen.")

        ai_resp = await asyncio.to_thread(_probe_ai)
        ai_duration = _time.perf_counter() - t_ai_start
        ai_duration_sec = round(ai_duration, 2)

        # Hitung perkiraan tokens & tokens/sec
        word_count = len(ai_resp.split())
        est_tokens = max(1, int(word_count * 1.3))
        tokens_per_sec = round(est_tokens / ai_duration, 1) if ai_duration > 0 else 0

        # Metrik sistem hardware saat pengujian
        cpu_load = _psutil.cpu_percent(interval=0.1)
        ram = _psutil.virtual_memory()

        # Klasifikasi Kecepatan
        rating = "⚡ SANGAT CEPAT" if tg_roundtrip_ms < 600 else ("🟢 NORMAL" if tg_roundtrip_ms < 1500 else "🟡 CUKUP BAIK")

        speed_report = (
            "⚡ **LAPORAN KECEPATAN (SPEED & LATENCY TEST)**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 **Status Performa**: `{rating}`\n\n"
            f"📱 **Kecepatan Kirim Telegram**:\n"
            f"• Roundtrip Kirim Pesan: `{tg_roundtrip_ms} ms`\n"
            f"• Ping Server Telegram: `{tg_server_ping} ms`\n\n"
            f"🤖 **Kecepatan Respon Agent AI**:\n"
            f"• Provider: `{prov}` (Model: `{model}`)\n"
            f"• Waktu Respon Model: `{ai_duration_sec} detik`\n"
            f"• Kecepatan Generate: ~`{tokens_per_sec} token/detik`\n\n"
            f"💻 **Kondisi Hardware Laptop**:\n"
            f"• Beban CPU: `{cpu_load}%`\n"
            f"• Beban RAM: `{ram.percent}% ({ram.used // (1024*1024):,} MB)`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"_Waktu tes: {datetime.datetime.now().strftime('%H:%M:%S WIB')}_"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔄 Tes Ulang Speed", callback_data="btn_speed_test"),
                    InlineKeyboardButton("📊 Status Lengkap", callback_data="refresh_status"),
                ]
            ]
        )

        try:
            await probe_msg.edit_text(speed_report, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await msg_target.reply_text(speed_report, reply_markup=keyboard)

    async def camera_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengambil foto dari kamera webcam laptop dan langsung mengirimkannya ke Telegram."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        status_msg = await update.message.reply_text("📸 *Mengaktifkan kamera laptop & mengambil foto...*", parse_mode=ParseMode.MARKDOWN)

        def _take_photo() -> tuple[bool, str, Path | None]:
            try:
                import cv2
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    return False, "Kamera webcam laptop tidak dapat dibuka atau sedang dipakai aplikasi lain.", None

                ret = False
                frame = None
                for _ in range(5):
                    ret, frame = cap.read()
                cap.release()

                if ret and frame is not None:
                    out_path = Path("kamera_capture.jpg").resolve()
                    cv2.imwrite(str(out_path), frame)
                    return True, "Foto berhasil diambil.", out_path
                return False, "Sensor kamera tidak menghasilkan gambar.", None
            except Exception as e:
                return False, str(e), None

        sukses, pesan, out_path = await asyncio.to_thread(_take_photo)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if sukses and out_path and out_path.exists():
            with open(out_path, "rb") as pf:
                await update.message.reply_photo(
                    photo=pf,
                    caption=f"📸 **Foto Kamera Laptop**\nWaktu: `{datetime.datetime.now().strftime('%H:%M:%S WIB')}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
        else:
            await update.message.reply_text(f"❌ Gagal mengambil foto: {pesan}")

    async def capture_screen_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengambil screenshot layar display laptop dan langsung mengirimkannya ke Telegram."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if not msg_target:
            return

        status_msg = await msg_target.reply_text(
            "🖥️ *Mengambil tangkapan layar (screenshot) display laptop...*",
            parse_mode=ParseMode.MARKDOWN,
        )

        import perkakas
        fn_ss = getattr(perkakas, "capture_screen", None)
        if not fn_ss:
            await msg_target.reply_text("❌ Fungsi capture_screen tidak tersedia.")
            return

        out_name = "screen_capture.png"
        ss_path = Path(out_name).resolve()
        try:
            if ss_path.exists():
                ss_path.unlink()
        except Exception:
            pass

        res = await asyncio.to_thread(fn_ss, out_name)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if ss_path.exists() and ss_path.stat().st_size > 500:
            m = ambil_metrik_realtime()
            caption = (
                f"🖥️ **Tangkapan Layar (Screenshot) Laptop**\n"
                f"🎯 **Jendela Aktif**: `{m['active_window']}`\n"
                f"⏱ **Waktu**: `{datetime.datetime.now().strftime('%H:%M:%S WIB')}`"
            )
            with open(ss_path, "rb") as pf:
                await msg_target.reply_photo(
                    photo=pf,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
        else:
            await msg_target.reply_text(f"❌ {res}")

    async def close_app_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Menutup aplikasi tertentu di laptop (misal: /tutup chrome atau /tutup notepad)."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text(
                "⚠️ Masukkan nama aplikasi yang ingin ditutup. Contoh:\n• `/tutup chrome`\n• `/tutup notepad`\n• `/tutup msedge`"
            )
            return

        target_app = " ".join(context.args).strip()
        import perkakas
        fn_close = getattr(perkakas, "close_application", None)
        if fn_close:
            res = fn_close(target_app)
            await update.message.reply_text(f"🖥️ {res}")
        else:
            await update.message.reply_text("❌ Fungsi close_application tidak tersedia.")

    def _build_open_hub_markup(self, tab_count: int = 0) -> InlineKeyboardMarkup:
        """Membuat tombol peluncur aplikasi desktop dan tab browser laptop."""
        tab_label = f"📑 Tab Browser ({tab_count})" if tab_count > 0 else "📑 Tab Browser"
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🌐 Google Chrome", callback_data="open_app:chrome"),
                    InlineKeyboardButton("🎧 Spotify", callback_data="open_app:spotify"),
                ],
                [
                    InlineKeyboardButton("💻 VS Code", callback_data="open_app:vscode"),
                    InlineKeyboardButton("📁 File Explorer", callback_data="open_app:explorer"),
                ],
                [
                    InlineKeyboardButton("📝 Notepad", callback_data="open_app:notepad"),
                    InlineKeyboardButton("🧮 Kalkulator", callback_data="open_app:calc"),
                ],
                [
                    InlineKeyboardButton(tab_label, callback_data="open_hub:tabs"),
                    InlineKeyboardButton("⚡ Terminal / CMD", callback_data="open_app:terminal"),
                ],
            ]
        )

    def _build_browser_tabs_markup(self) -> tuple[str, InlineKeyboardMarkup]:
        """Membuat tampilan dan tombol kontrol interaktif untuk jendela & tab browser yang sedang berjalan."""
        import perkakas
        fn_tabs = getattr(perkakas, "get_open_browser_tabs", None)
        tabs = fn_tabs() if fn_tabs else []

        if not tabs:
            text = (
                "📑 **TAB & JENDELA BROWSER LAPTOP**\n\n"
                "ℹ️ Tidak ada jendela Google Chrome atau Microsoft Edge yang sedang terbuka di laptop saat ini.\n"
                "Gunakan tombol di bawah untuk membuka browser atau kembali ke menu:"
            )
            markup = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🌐 Buka Google Chrome", callback_data="open_app:chrome")],
                    [
                        InlineKeyboardButton("🔄 Segarkan (Refresh)", callback_data="open_hub:tabs"),
                        InlineKeyboardButton("🔙 Hub Buka", callback_data="open_hub:main"),
                    ],
                ]
            )
            return text, markup

        text_lines = [
            f"📑 **TAB & JENDELA BROWSER AKTIF ({len(tabs)} Ditemukan)**\n",
            "Berikut tab/jendela yang sedang aktif di laptop:\n",
        ]
        buttons = []
        for idx, t in enumerate(tabs, 1):
            icon = "🎬" if t.get("is_youtube") else ("🎧" if t.get("is_media") else "🌐")
            clean_title = t.get("clean_title", "Tab Browser")
            if len(clean_title) > 60:
                clean_title = clean_title[:57] + "..."
            proc = t.get("process_name", "browser")
            text_lines.append(f"{idx}. {icon} `{clean_title}` ({proc})")

            row = [
                InlineKeyboardButton(f"🎯 Fokus #{idx}", callback_data=f"tab_focus:{t['hwnd']}"),
            ]
            if t.get("is_media") or t.get("is_youtube"):
                row.append(InlineKeyboardButton("⏸️ Play/Pause", callback_data=f"tab_media:{t['hwnd']}"))
            row.append(InlineKeyboardButton("❌ Tutup", callback_data=f"tab_close:{t['hwnd']}"))
            buttons.append(row)

        buttons.append(
            [
                InlineKeyboardButton("🔄 Segarkan (Refresh)", callback_data="open_hub:tabs"),
                InlineKeyboardButton("🔙 Hub Buka", callback_data="open_hub:main"),
            ]
        )
        return "\n".join(text_lines), InlineKeyboardMarkup(buttons)

    async def search_and_send_youtube(self, msg_target, query: str) -> None:
        """Mencari video di YouTube, menampilkan judul & link langsung, serta tombol pilihan interaktif."""
        import urllib.parse
        import perkakas
        fn_search = getattr(perkakas, "search_youtube_videos", None)
        if not fn_search:
            fn_open = getattr(perkakas, "open_application", None)
            if fn_open:
                res = await asyncio.to_thread(fn_open, f"youtube {query}")
                await msg_target.reply_text(f"🖥️ {res}")
            return

        status_msg = await msg_target.reply_text(
            f"🔍 *Mencari di YouTube:* `{query}`...",
            parse_mode=ParseMode.MARKDOWN,
        )

        results = await asyncio.to_thread(fn_search, query, 4)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if not results:
            fn_open = getattr(perkakas, "open_application", None)
            if fn_open:
                res = await asyncio.to_thread(fn_open, f"youtube {query}")
                await msg_target.reply_text(f"🖥️ {res}")
            return

        lines = [
            f"🎬 **PILIHAN HASIL YOUTUBE: \"{query}\"**\n",
            "Berikut video teratas yang ditemukan:\n",
        ]
        buttons = []
        for idx, r in enumerate(results, 1):
            dur_str = f" `[{r['duration']}]`" if r.get("duration") else ""
            ch_str = f" • *{r['channel']}*" if r.get("channel") else ""
            v_title = r.get("title", "Video YouTube")
            v_url = r.get("url", f"https://www.youtube.com/watch?v={r['video_id']}")
            lines.append(f"{idx}️⃣ **[{v_title}]({v_url})**{dur_str}{ch_str}")
            lines.append(f"   🔗 `{v_url}`\n")

            btn_title = v_title[:38] + ".." if len(v_title) > 40 else v_title
            buttons.append([InlineKeyboardButton(f"▶️ {idx}. {btn_title}", callback_data=f"yt_play:{r['video_id']}")])

        lines.append("👇 *Tekan tombol di bawah untuk langsung memutar video di laptop:*")
        encoded_q = urllib.parse.quote_plus(query)
        buttons.append([
            InlineKeyboardButton("🌐 Buka Hasil di Browser", callback_data=f"open_app:https://www.youtube.com/results?search_query={encoded_q}"),
        ])

        await msg_target.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    async def tabs_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Menampilkan dan mengontrol seluruh tab & jendela browser yang sedang terbuka di laptop."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if not msg_target:
            return

        text, markup = self._build_browser_tabs_markup()
        await msg_target.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

    async def cari_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mencari konten/lagu/video/artikel berdasarkan aplikasi dan kata kunci (misal: /cari youtube the jansen)."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        u_info = get_user_info(update)
        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if not msg_target:
            return

        if not context.args:
            msg = (
                "🔍 **PANDUAN FITUR CARI CEPAT LAPTOP**\n\n"
                "Format: `/cari <aplikasi> <kata kunci>`\n\n"
                "📌 **Contoh Penggunaan:**\n"
                "• `/cari youtube the jansen` : Cari & putar lagu/video YouTube di laptop\n"
                "• `/cari yt the jansen` : Versi singkat untuk YouTube\n"
                "• `/cari google tutorial python` : Cari di Google via Chrome laptop\n"
                "• `/cari spotify feast` : Cari artis/lagu di Spotify\n"
                "• `/cari github gemini agent` : Cari repositori di GitHub\n"
                "• `/cari wikipedia kecerdasan buatan` : Cari artikel Wikipedia\n\n"
                "💡 *Tips:* Jika langsung mengetik `/cari the jansen`, otomatis mencari ke YouTube."
            )
            await msg_target.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
            return

        first_arg = context.args[0].lower().strip()
        remaining_args = context.args[1:]

        app_aliases = {
            "youtube": "youtube",
            "yt": "youtube",
            "ytb": "youtube",
            "google": "google",
            "gg": "google",
            "chrome": "google",
            "browser": "google",
            "web": "google",
            "spotify": "spotify",
            "sp": "spotify",
            "github": "github",
            "gh": "github",
            "wikipedia": "wikipedia",
            "wiki": "wikipedia",
            "bing": "bing",
        }

        if first_arg in app_aliases:
            target_app = app_aliases[first_arg]
            if not remaining_args:
                await msg_target.reply_text(
                    f"⚠️ Masukkan kata kunci yang ingin dicari di {target_app.upper()}.\nContoh: `/cari {first_arg} the jansen`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            query_term = " ".join(remaining_args).strip()
        else:
            # Default ke YouTube jika kata pertama bukan nama aplikasi
            target_app = "youtube"
            query_term = " ".join(context.args).strip()

        log_terminal_box(
            "Command", f"/cari {target_app}",
            [("Pengguna", u_info), ("Aplikasi", target_app.upper()), ("Query", query_term)],
            color="bright_cyan",
        )

        import urllib.parse
        import perkakas

        if target_app == "youtube":
            await self.search_and_send_youtube(msg_target, query_term)
            return

        encoded_q = urllib.parse.quote_plus(query_term)
        app_urls = {
            "google": f"https://www.google.com/search?q={encoded_q}",
            "spotify": f"https://open.spotify.com/search/{encoded_q}",
            "github": f"https://github.com/search?q={encoded_q}",
            "wikipedia": f"https://id.wikipedia.org/wiki/Special:Search?search={encoded_q}",
            "bing": f"https://www.bing.com/search?q={encoded_q}",
        }
        app_labels = {
            "google": "Google Search (Chrome)",
            "spotify": "Spotify",
            "github": "GitHub",
            "wikipedia": "Wikipedia Indonesia",
            "bing": "Bing Search",
        }
        target_url = app_urls.get(target_app, f"https://www.google.com/search?q={encoded_q}")
        app_label = app_labels.get(target_app, target_app.title())

        fn_open = getattr(perkakas, "open_application", None)
        if fn_open:
            status_msg = await msg_target.reply_text(f"⏳ Membuka pencarian {app_label} di laptop...")
            res = await asyncio.to_thread(fn_open, target_url)
            msg_reply = (
                f"🔍 **Pencarian {app_label}:**\n"
                f"• Kata Kunci: `{query_term}`\n"
                f"• Tautan URL: {target_url}\n\n"
                f"🖥️ Status Laptop: {res}"
            )
            buttons = [
                [
                    InlineKeyboardButton("🌐 Buka Tautan di Browser", callback_data=f"open_app:{target_url}"),
                ]
            ]
            try:
                await status_msg.edit_text(
                    msg_reply,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                )
            except Exception:
                await msg_target.reply_text(
                    msg_reply,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                )
        else:
            await msg_target.reply_text("❌ Fungsi open_application tidak tersedia.")

    async def open_app_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Membuka aplikasi desktop, link URL, atau tab browser."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        u_info = get_user_info(update)
        msg_target = update.message or (update.callback_query.message if update.callback_query else None)
        if not msg_target:
            return

        import perkakas
        if not context.args:
            fn_tabs = getattr(perkakas, "get_open_browser_tabs", None)
            tabs = fn_tabs() if fn_tabs else []
            count_str = f"{len(tabs)} tab aktif" if tabs else "belum ada tab aktif"
            msg = (
                "📱 **PELUNCUR APLIKASI LAPTOP**\n\n"
                f"• **Browser Tab**: `{count_str}`\n"
                "• Pilih aplikasi di bawah untuk langsung dibuka di laptop:\n\n"
                "💡 **Untuk mencari sesuatu di YouTube / Google / Spotify:**\n"
                "Gunakan perintah: `/cari <aplikasi> <keyword>`\n"
                "Contoh: `/cari youtube the jansen`"
            )
            await msg_target.reply_text(
                msg,
                reply_markup=self._build_open_hub_markup(len(tabs)),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        first_lower = context.args[0].lower().strip()
        # Jika pengguna mengetik "/buka youtube the jansen" atau sejenisnya, alirkan langsung ke cari_cmd
        if first_lower in ["youtube", "yt", "cari", "search", "spotify", "google"]:
            await self.cari_cmd(update, context)
            return

        target_query = " ".join(context.args).strip()
        log_terminal_box("Command", f"/buka {target_query}", [("Pengguna", u_info), ("Target", target_query)], color="bright_yellow")

        fn_open = getattr(perkakas, "open_application", None)
        if fn_open:
            status_msg = await msg_target.reply_text(f"⏳ Membuka `{target_query}` di laptop...")
            res = await asyncio.to_thread(fn_open, target_query)
            try:
                await status_msg.edit_text(f"🖥️ {res}")
            except Exception:
                await msg_target.reply_text(f"🖥️ {res}")
        else:
            await msg_target.reply_text("❌ Fungsi open_application tidak tersedia.")

    def _build_volume_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⏮️ Prev (F9)", callback_data="media_prev"),
                    InlineKeyboardButton("⏯️ Play/Pause (F10)", callback_data="media_play_pause"),
                    InlineKeyboardButton("⏭️ Next (F11)", callback_data="media_next"),
                ],
                [
                    InlineKeyboardButton("🔉 -10%", callback_data="vol_down_10"),
                    InlineKeyboardButton("🔊 +10%", callback_data="vol_up_10"),
                ],
                [
                    InlineKeyboardButton("🔇 Mute", callback_data="vol_mute"),
                    InlineKeyboardButton("🔈 Unmute", callback_data="vol_unmute"),
                ],
                [
                    InlineKeyboardButton("20%", callback_data="vol_20"),
                    InlineKeyboardButton("40%", callback_data="vol_40"),
                    InlineKeyboardButton("60%", callback_data="vol_60"),
                    InlineKeyboardButton("80%", callback_data="vol_80"),
                    InlineKeyboardButton("100%", callback_data="vol_100"),
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Status", callback_data="vol_status"),
                ],
            ]
        )

    async def volume_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengatur atau melihat volume master laptop."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        import perkakas
        fn_vol = getattr(perkakas, "set_volume", None)
        if not fn_vol:
            await update.message.reply_text("❌ Fungsi set_volume tidak tersedia.")
            return

        if context.args:
            arg = " ".join(context.args).strip()
            res = fn_vol(arg)
            await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())
        else:
            status_text = fn_vol("status")
            msg = (
                f"🎛️ **PENGATUR VOLUME LAPTOP**\n\n"
                f"{status_text}\n\n"
                "Gunakan tombol di bawah atau ketik:\n"
                "• `/volume 50` (set 50%)\n"
                "• `/volume +10` atau `/volume -10`\n"
                "• `/mute` atau `/unmute`"
            )
            await update.message.reply_text(
                msg,
                reply_markup=self._build_volume_markup(),
                parse_mode=ParseMode.MARKDOWN,
            )

    async def mute_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return
        import perkakas
        fn_vol = getattr(perkakas, "set_volume", None)
        res = fn_vol("mute") if fn_vol else "Fungsi tidak tersedia"
        await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())

    async def unmute_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return
        import perkakas
        fn_vol = getattr(perkakas, "set_volume", None)
        res = fn_vol("unmute") if fn_vol else "Fungsi tidak tersedia"
        await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())

    async def play_pause_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Memutar atau menjeda lagu/video di YouTube atau Spotify."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return
        import perkakas
        fn_media = getattr(perkakas, "media_control", None)
        res = fn_media("play_pause") if fn_media else "Fungsi media_control tidak tersedia"
        await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())

    async def next_track_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Memutar lagu berikutnya di YouTube atau Spotify."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return
        import perkakas
        fn_media = getattr(perkakas, "media_control", None)
        res = fn_media("next") if fn_media else "Fungsi media_control tidak tersedia"
        await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())

    async def prev_track_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Memutar lagu sebelumnya di YouTube atau Spotify."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return
        import perkakas
        fn_media = getattr(perkakas, "media_control", None)
        res = fn_media("prev") if fn_media else "Fungsi media_control tidak tersedia"
        await update.message.reply_text(f"{res}", reply_markup=self._build_volume_markup())

    async def read_file_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Membaca isi teks dari berkas lokal di laptop."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text("⚠️ Masukkan nama berkas. Contoh: `/baca README.md`")
            return

        file_path = " ".join(context.args).strip()
        import perkakas
        fn_read = getattr(perkakas, "read_file", None)
        if fn_read:
            res = fn_read(file_path)
            chunks = split_message(res)
            for c in chunks:
                await update.message.reply_text(c)
        else:
            await update.message.reply_text("❌ Fungsi read_file tidak tersedia.")

    def _build_file_browser(
        self, user_id: int, target_dir: Path | None = None, page: int = 0
    ) -> tuple[str, InlineKeyboardMarkup]:
        """Membangun penjelajah berkas interaktif laptop dengan navigasi folder & pagination."""
        if not hasattr(self, "file_picker_state"):
            self.file_picker_state = {}

        state = self.file_picker_state.get(user_id, {})
        cur_dir = target_dir or state.get("dir") or Path.cwd()
        try:
            cur_dir = Path(cur_dir).resolve()
            if not cur_dir.exists() or not cur_dir.is_dir():
                cur_dir = Path.cwd()
        except Exception:
            cur_dir = Path.cwd()

        dirs = []
        files = []
        try:
            for item in sorted(cur_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    dirs.append(item)
                elif item.is_file():
                    files.append(item)
        except Exception:
            pass

        all_items = dirs + files
        page_size = 6
        total_items = len(all_items)
        total_pages = max(1, (total_items + page_size - 1) // page_size)
        page = max(0, min(page, total_pages - 1))

        self.file_picker_state[user_id] = {
            "dir": cur_dir,
            "page": page,
            "items": all_items,
        }

        start_idx = page * page_size
        page_items = all_items[start_idx : start_idx + page_size]

        keyboard = []

        # Shortcut folder cepat
        keyboard.append([
            InlineKeyboardButton("📂 Project", callback_data="fb_loc:ws"),
            InlineKeyboardButton("📥 Downloads", callback_data="fb_loc:dl"),
            InlineKeyboardButton("📄 Docs", callback_data="fb_loc:docs"),
            InlineKeyboardButton("🖥️ Desktop", callback_data="fb_loc:dt"),
        ])

        # Tombol folder atas jika ada parent
        if cur_dir.parent != cur_dir:
            parent_name = cur_dir.parent.name or str(cur_dir.parent)
            keyboard.append([
                InlineKeyboardButton(f"⬆️ Ke Folder Atas ({parent_name})", callback_data="fb_nav:up")
            ])

        # Daftar item folder & berkas
        for idx_in_page, item in enumerate(page_items):
            global_idx = start_idx + idx_in_page
            if item.is_dir():
                btn_text = f"📁 {item.name[:28]}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"fb_d:{global_idx}")])
            else:
                try:
                    sz = item.stat().st_size
                except Exception:
                    sz = 0
                sz_str = f"{sz} B" if sz < 1024 else (f"{sz/1024:.1f} KB" if sz < 1024*1024 else f"{sz/(1024*1024):.1f} MB")
                btn_text = f"📥 {item.name[:22]} ({sz_str})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"fb_f:{global_idx}")])

        # Baris navigasi pagination
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"fb_p:{page - 1}"))
        nav_row.append(InlineKeyboardButton(f"📄 Hal {page + 1}/{total_pages}", callback_data="fb_noop"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"fb_p:{page + 1}"))
        if len(nav_row) > 1:
            keyboard.append(nav_row)

        text = (
            "📂 **PENJELAJAH BERKAS LAPTOP (FILE PICKER)**\n\n"
            f"📍 **Direktori**: `{cur_dir}`\n"
            f"📊 **Isi**: {len(dirs)} folder, {len(files)} berkas\n\n"
            "• Klik **📁 Folder** untuk masuk ke subdirektori.\n"
            "• Klik **📥 Berkas** untuk mengunduhnya langsung ke HP Anda.\n"
            "• Atau ketik: `/get <path_lengkap>` (bisa file mana saja di laptop)."
        )
        return text, InlineKeyboardMarkup(keyboard)

    async def get_file_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengirim berkas dari laptop ke HP pengguna via Telegram document."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        user_id = update.effective_user.id if update.effective_user else 0

        if not context.args:
            text, markup = self._build_file_browser(user_id, Path.cwd(), page=0)
            await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
            return

        target_name = " ".join(context.args).strip()
        target_path = Path(target_name).expanduser().resolve()

        if not target_path.exists() or not target_path.is_file():
            alt_path = (Path.cwd() / target_name).resolve()
            if alt_path.exists() and alt_path.is_file():
                target_path = alt_path
            else:
                await update.message.reply_text(
                    f"❌ Berkas `{target_name}` tidak ditemukan di laptop.\n"
                    "Gunakan `/get` tanpa argumen untuk membuka Penjelajah Berkas interaktif."
                )
                return

        file_size = target_path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Ukuran berkas melebihi batas 50 MB Telegram Bot.")
            return

        status_msg = await update.message.reply_text(f"📤 Mengunggah berkas `{target_path.name}` ({file_size:,} byte)...")
        try:
            with open(target_path, "rb") as f:
                await update.message.reply_document(
                    document=f, caption=f"📥 Berkas dari laptop:\n`{target_path}`"
                )
            try:
                await status_msg.delete()
            except Exception:
                pass
        except Exception as exc:
            await update.message.reply_text(f"❌ Gagal mengirim berkas: {exc}")

    async def new_session_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        title = " ".join(context.args) if context.args else None
        new_sess = self.agent.create_new_session(title=title)
        await update.message.reply_text(
            f"✨ Sesi baru berhasil dibuat: **{new_sess.title}** (ID: `{new_sess.session_id}`)",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def list_sessions_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        sessions = pengelola_sesi.pengelola_sesi.daftar_sesi()
        if not sessions:
            await update.message.reply_text("Belum ada riwayat sesi tersimpan.")
            return

        lines = ["📚 **Daftar Sesi Tersimpan di Laptop**:\n"]
        for idx, s in enumerate(sessions[:10], 1):
            is_active = s["session_id"] == self.agent.session.session_id
            tag = " `[AKTIF]`" if is_active else ""
            lines.append(f"{idx}. **{s['title']}**{tag}\n   `ID: {s['session_id']}` ({s['message_count']} pesan)")

        lines.append("\nKetik `/load <nomor_atau_id>` untuk beralih sesi.")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def load_session_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text("⚠️ Masukkan nomor urut atau ID sesi. Contoh: `/load 1`")
            return

        arg = context.args[0].strip()
        sessions = pengelola_sesi.pengelola_sesi.daftar_sesi()
        target_id = None

        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(sessions):
                target_id = sessions[idx]["session_id"]
        else:
            for s in sessions:
                if s["session_id"] == arg or s["session_id"].startswith(arg):
                    target_id = s["session_id"]
                    break

        if not target_id:
            await update.message.reply_text(f"❌ Sesi '{arg}' tidak ditemukan.")
            return

        target_sess = pengelola_sesi.pengelola_sesi.ambil_sesi(target_id)
        if target_sess:
            self.agent.switch_session(target_sess)
            await update.message.reply_text(
                f"✅ Berhasil beralih ke sesi: **{target_sess.title}** (`{target_id}`)",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text("❌ Gagal memuat data sesi.")

    async def memory_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        mems = memori.pengelola_memori.ambil_semua()
        if not mems:
            await update.message.reply_text("Memori jangka panjang masih kosong.")
            return

        lines = ["🧠 **Catatan Memori Persisten Laptop**:\n"]
        for k, v in mems.items():
            lines.append(f"• **{k}**: {v}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def provider_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Melihat atau beralih provider AI (gemini atau omniroute)."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            current = self.config.ambil_provider()
            model = self.config.ambil_model()
            msg = (
                f"⚙️ **Status Provider AI Aktif**:\n"
                f"• Provider: `{current.upper()}`\n"
                f"• Model Terpilih: `{model}`\n\n"
                "Untuk beralih provider, gunakan:\n"
                "• `/provider omniroute`\n"
                "• `/provider ollama`\n"
                "• `/provider gemini`"
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
            return

        target = context.args[0].strip().lower()
        if target not in ["gemini", "omniroute", "ollama"]:
            await update.message.reply_text("⚠️ Pilihan provider: `gemini`, `omniroute`, atau `ollama`.")
            return

        if target == "ollama":
            os.environ["OLLAMA_MODELS"] = r"D:\.ollama\models"
            os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"

        self.config.simpan_provider(target)
        self.provider = target
        self.api_key = self.config.ambil_api_key()
        self.model_name = self.config.ambil_model()
        self.agent = agen.AgenGemini(api_key=self.api_key, model_name=self.model_name)
        await update.message.reply_text(
            f"✅ Provider AI berhasil dialihkan ke **{target.upper()}** (Model: `{self.model_name}`)\n📁 Models: `{r'D:\.ollama\models' if target == 'ollama' else 'Cloud API'}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def models_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Memindai dan menampilkan daftar model yang tersedia untuk provider aktif."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        status_msg = await update.message.reply_text("🔍 Memindai model yang tersedia...")
        try:
            models = agen.pindai_model_tersedia()
            prov = self.config.ambil_provider().upper()
            lines = [f"📋 **Daftar Model {prov} (Total: {len(models)})**:\n"]
            for m in models[:15]:
                is_active = m["id"] == self.agent.model_name
                tag = " `[AKTIF]`" if is_active else ""
                lines.append(f"• `{m['id']}` - {m['display_name']}{tag}")
            if len(models) > 15:
                lines.append(f"\n...dan {len(models) - 15} model lainnya.")
            lines.append("\nGunakan `/model <nama_model>` untuk mengganti model.")
            await status_msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            await status_msg.edit_text(f"❌ Gagal memindai model: {exc}")

    async def model_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengganti model aktif untuk provider saat ini."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text(
                f"Model aktif saat ini: `{self.agent.model_name}`\nContoh ganti: `/model auto` atau `/model gemini-2.5-flash`"
            )
            return

        new_model = context.args[0].strip()
        self.config.simpan_model(new_model)
        self.model_name = new_model
        self.agent.ganti_model(new_model)
        await update.message.reply_text(f"✅ Model aktif diganti ke: `{new_model}`")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Menerima kiriman file dari HP pengguna dan menyimpannya di folder kerja laptop."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        doc = update.message.document
        if not doc:
            return

        file_name = doc.file_name or f"file_{doc.file_id[:8]}"
        target_path = Path.cwd() / file_name

        status_msg = await update.message.reply_text(f"📥 Menerima berkas `{file_name}` dari HP...")
        file_obj = await context.bot.get_file(doc.file_id)
        await file_obj.download_to_drive(str(target_path))

        await status_msg.edit_text(
            f"✅ Berkas **{file_name}** ({doc.file_size} byte) berhasil disimpan di laptop!\n"
            f"Jalur: `{target_path.resolve()}`"
        )

    async def handle_user_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        user_text = update.message.text.strip()
        if not user_text:
            return

        u_info = get_user_info(update)
        u_clean = user_text.lower().strip()

        # Deteksi langsung: Pertanyaan seputar tab browser
        if any(w in u_clean for w in ["berapa tab", "daftar tab", "list tab", "tab browser", "tab chrome", "tab edge", "buka tab"]):
            log_terminal_box("Pesan Masuk", "Cek Tab Browser", [("Pengguna", u_info), ("Pesan", f'"{user_text}"'), ("Aksi", "Mengirim daftar tab browser")], color="bright_blue")
            text, markup = self._build_browser_tabs_markup()
            await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
            return

        # Deteksi langsung: Pesan diawali kata "cari ..." (misal: "cari youtube the jansen")
        if u_clean.startswith("cari ") or u_clean.startswith("search "):
            parts = user_text.split()[1:]
            context.args = parts
            await self.cari_cmd(update, context)
            return

        # Deteksi langsung: Pencarian / Pemutaran YouTube otomatis
        if ("youtube" in u_clean or "yt" in u_clean or "lagu" in u_clean) and any(w in u_clean for w in ["cari", "putar", "play", "dengarkan", "stel", "setel"]):
            cleaned_query = re.sub(
                r"\b(buka|open|chrome|lalu|didalam|dan|youtube|yt|tolong|coba|cari|carikan|putar|putarkan|play|lagu|video|setel|musik)\b",
                "",
                user_text,
                flags=re.IGNORECASE,
            ).strip()
            if not cleaned_query:
                cleaned_query = user_text
            log_terminal_box("Pesan Masuk", "Pencarian YouTube", [("Pengguna", u_info), ("Pesan", f'"{user_text}"'), ("Query", cleaned_query)], color="bright_cyan")
            await self.search_and_send_youtube(update.message, cleaned_query)
            return

        log_terminal_box("Pesan Masuk", "Chat AI Agent", [("Pengguna", u_info), ("Pesan", f'"{user_text}"'), ("Status", "Memproses instruksi ke model AI...")], color="bright_cyan")

        status_msg = await update.message.reply_text("⏳ *Memproses instruksi di laptop...*", parse_mode=ParseMode.MARKDOWN)
        loop = asyncio.get_running_loop()

        # Sinkronkan sesi aktif dengan disk agar sinkron 100% dengan apa yang ada di laptop
        try:
            active_id = pengelola_sesi.pengelola_sesi.ambil_sesi_aktif_id()
            if active_id:
                if not self.agent.session or self.agent.session.session_id != active_id:
                    sess = pengelola_sesi.pengelola_sesi.ambil_sesi(active_id)
                    if sess:
                        self.agent.switch_session(sess)
                else:
                    disk_sess = pengelola_sesi.pengelola_sesi.ambil_sesi(active_id)
                    if disk_sess:
                        self.agent.session = disk_sess
        except Exception:
            pass

        def _on_tool_call(tool_name: str, args: dict) -> None:
            brief = ", ".join([f"{k}={v}" for k, v in args.items()])[:60]
            log_terminal_box("Eksekusi Perkakas", tool_name, [("Parameter", brief)], color="bright_blue")
            try:
                asyncio.run_coroutine_threadsafe(
                    context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚙️ `[Alat]` Menjalankan **{tool_name}**({brief})...",
                        parse_mode=ParseMode.MARKDOWN,
                    ),
                    loop,
                )
            except Exception:
                pass

        def _run_agent() -> str:
            return self.agent.send_message(
                message=user_text,
                on_tool_call=_on_tool_call,
            )

        try:
            import time as _time
            t_ai_start = _time.perf_counter()
            # Jalankan di background worker thread agar event loop Telegram tidak terblokir
            response_text = await asyncio.to_thread(_run_agent)
            ai_duration = _time.perf_counter() - t_ai_start

            try:
                await status_msg.delete()
            except Exception:
                pass

            if not response_text or not response_text.strip():
                response_text = "✅ Perintah telah diproses oleh Agen di laptop."

            log_terminal_box(
                "Respon AI Selesai", f"{self.agent.model_name} ({ai_duration:.2f}s)",
                [("Pengguna", u_info), ("Balasan", f'"{response_text[:75]}..."')],
                color="bright_green"
            )

            # Tambahkan footer indikator latency kecepatan eksekusi
            footer_latency = f"\n\n_⏱ Respon: {ai_duration:.2f}s_"
            response_with_footer = response_text + footer_latency

            # Kirim balasan respon (pecah jika panjang)
            chunks = split_message(response_with_footer)
            for idx, chunk in enumerate(chunks):
                try:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    # Fallback ke plain text jika Markdown mengandung karakter unescaped
                    await update.message.reply_text(chunk)

            # Cek apakah ada foto webcam baru yang dihasilkan dalam 45 detik terakhir
            for foto_name in ["kamera_capture.jpg", "capture_kamera.jpg"]:
                foto_path = Path(foto_name)
                if foto_path.exists():
                    try:
                        mtime = foto_path.stat().st_mtime
                        if (datetime.datetime.now().timestamp() - mtime) < 45:
                            with open(foto_path, "rb") as pf:
                                await update.message.reply_photo(
                                    photo=pf,
                                    caption="📸 *Foto Kamera Webcam Laptop*",
                                    parse_mode=ParseMode.MARKDOWN,
                                )
                            break
                    except Exception:
                        pass

            # Cek apakah ada tangkapan layar (screenshot) baru yang dihasilkan dalam 45 detik terakhir
            for ss_name in ["screen_capture.png", "screenshot.png"]:
                ss_path = Path(ss_name)
                if ss_path.exists():
                    try:
                        mtime = ss_path.stat().st_mtime
                        if (datetime.datetime.now().timestamp() - mtime) < 45:
                            m = ambil_metrik_realtime()
                            caption = (
                                f"🖥️ **Tangkapan Layar (Screenshot) Laptop**\n"
                                f"🎯 **Jendela Aktif**: `{m['active_window']}`\n"
                                f"⏱ **Waktu**: `{datetime.datetime.now().strftime('%H:%M:%S WIB')}`"
                            )
                            with open(ss_path, "rb") as pf:
                                await update.message.reply_photo(
                                    photo=pf,
                                    caption=caption,
                                    parse_mode=ParseMode.MARKDOWN,
                                )
                            break
                    except Exception:
                        pass

        except Exception as exc:
            err_msg = f"❌ Terjadi kesalahan saat memproses di laptop: {exc}"
            agent_logger.log_error("telegram_gateway", str(exc))
            try:
                await status_msg.edit_text(err_msg)
            except Exception:
                await update.message.reply_text(err_msg)

    async def post_init(self, application: Application) -> None:
        """Mendaftarkan menu tombol command interaktif di aplikasi Telegram."""
        commands = [
            BotCommand("status", "Dashboard monitoring laptop real-time"),
            BotCommand("capture", "Ambil tangkapan layar laptop (Screenshot)"),
            BotCommand("cari", "Cari konten di YouTube, Google, Spotify (misal: /cari youtube the jansen)"),
            BotCommand("speed", "Uji kecepatan respon AI & kirim Telegram"),
            BotCommand("kamera", "Ambil foto dari webcam laptop"),
            BotCommand("buka", "Peluncur aplikasi desktop & browser laptop"),
            BotCommand("tabs", "Pantau & kontrol tab browser terbuka di laptop"),
            BotCommand("tutup", "Tutup aplikasi desktop (contoh: /tutup chrome)"),
            BotCommand("volume", "Atur volume laptop & kontrol lagu"),
            BotCommand("play", "Putar/Jeda lagu atau video YouTube/Spotify"),
            BotCommand("next", "Putar lagu berikutnya (Next Track)"),
            BotCommand("prev", "Putar lagu sebelumnya (Prev Track)"),
            BotCommand("mute", "Matikan suara laptop (Mute)"),
            BotCommand("unmute", "Nyalakan suara laptop (Unmute)"),
            BotCommand("baterai", "Pantau daya baterai & charger"),
            BotCommand("wifi", "Cek koneksi Wi-Fi & kekuatan sinyal"),
            BotCommand("jendela", "Cek jendela aktif & aplikasi terbuka"),
            BotCommand("baca", "Baca isi file teks di laptop"),
            BotCommand("get", "Unduh berkas dari laptop ke HP"),
            BotCommand("help", "Panduan lengkap fitur & perintah"),
            BotCommand("new", "Mulai sesi percakapan baru"),
            BotCommand("sessions", "Daftar riwayat sesi di laptop"),
            BotCommand("load", "Beralih ke nomor/id sesi tertentu"),
            BotCommand("models", "Daftar model AI yang tersedia"),
            BotCommand("model", "Ganti model AI aktif"),
            BotCommand("provider", "Ganti provider (gemini/ollama)"),
        ]
        try:
            await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
            await application.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
            if self.allowed_user_id and str(self.allowed_user_id).isdigit():
                await application.bot.set_my_commands(
                    commands, scope=BotCommandScopeChat(chat_id=int(self.allowed_user_id))
                )
                await application.bot.set_chat_menu_button(
                    chat_id=int(self.allowed_user_id), menu_button=MenuButtonCommands()
                )
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception:
            pass

        # Kirim notifikasi pesan ke user bahwa bot sudah berhasil terhubung (Connected)
        if self.allowed_user_id and str(self.allowed_user_id).isdigit():
            chat_id = int(self.allowed_user_id)
            try:
                m = ambil_metrik_realtime()
                prov = self.config.ambil_provider().upper()
                waktu_now = datetime.datetime.now().strftime("%H:%M:%S WIB")
                conn_msg = (
                    "🟢 **LAPTOP AGENT CONNECTED** 🚀\n\n"
                    "⌬ **Terminal Agent Berhasil Terhubung ke Telegram!**\n"
                    f"• **Status**: ONLINE 🟢\n"
                    f"• **Waktu**: `{waktu_now}`\n"
                    f"• **Daya Baterai**: `{m['battery_str']}`\n"
                    f"• **Jaringan Wi-Fi**: `{m['wifi_full']}`\n"
                    f"• **Jendela Aktif**: `{m['active_window']}`\n"
                    f"• **Provider AI**: `{prov}` (Model: `{self.agent.model_name}`)\n\n"
                    "Perangkat laptop siap dikendalikan dari HP.\n"
                    "Ketik `/status` untuk membuka dashboard monitoring atau `/buka` untuk pusat media."
                )
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=conn_msg,
                    parse_mode=ParseMode.MARKDOWN,
                )
                print(f"[OK] Notifikasi koneksi berhasil dikirim ke Telegram User ID: {chat_id}")
            except Exception as exc:
                agent_logger.log_error("telegram_gateway.post_init", f"Gagal mengirim notifikasi koneksi: {exc}")

    def run(self) -> None:
        """Menjalankan bot Telegram polling daemon."""
        # Bersihkan instance bot_telegram.py lain jika ada untuk mencegah Conflict 409
        try:
            import psutil
            my_pid = os.getpid()
            for p in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if p.info["pid"] != my_pid:
                        cmd = " ".join(p.info.get("cmdline") or [])
                        if "bot_telegram.py" in cmd and "python -c" not in cmd:
                            p.terminate()
                except Exception:
                    pass
        except Exception:
            pass

        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold cyan", justify="right")
        table.add_column(style="white")

        table.add_row("Status Gateway", f": [bold green]ONLINE 🟢[/bold green] (Mendengarkan instruksi HP)")
        table.add_row("Provider AI", f": [bold yellow]{self.provider.upper()}[/bold yellow] (Model: [bold white]{self.model_name}[/bold white])")
        table.add_row("Whitelist User", f": [bold green]{self.allowed_user_id}[/bold green] (Akses privat terkunci)")
        table.add_row("Bot Token", f": [dim]{self.bot_token[:10]}... (Tervalidasi)[/dim]")
        table.add_row("Sistem Host", f": {platform.system()} {platform.release()} (Python {platform.python_version()})")
        table.add_row("", "")
        table.add_row("Petunjuk", ": [dim italic]Kirim chat atau perintah dari Telegram di HP Anda.[/dim italic]")
        table.add_row("Pintasan", ": [dim italic]Tekan Ctrl+C di terminal ini untuk mematikan gateway.[/dim italic]")

        p = Panel(
            table,
            title="[bold bright_cyan]⌬ GEMINI TERMINAL AGENT - TELEGRAM MOBILE GATEWAY[/bold bright_cyan]",
            border_style="bright_blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        console.print()
        console.print(p)
        console.print()

        app = Application.builder().token(self.bot_token).post_init(self.post_init).build()

        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("provider", self.provider_cmd))
        app.add_handler(CommandHandler("models", self.models_cmd))
        app.add_handler(CommandHandler("model", self.model_cmd))
        app.add_handler(CommandHandler("status", self.status_cmd))
        app.add_handler(CommandHandler("laptop", self.status_cmd))
        app.add_handler(CommandHandler("pantau", self.status_cmd))
        app.add_handler(CommandHandler("speed", self.speed_cmd))
        app.add_handler(CommandHandler("ping", self.speed_cmd))
        app.add_handler(CommandHandler("wifi", self.wifi_cmd))
        app.add_handler(CommandHandler("baterai", self.battery_cmd))
        app.add_handler(CommandHandler("battery", self.battery_cmd))
        app.add_handler(CommandHandler("jendela", self.window_cmd))
        app.add_handler(CommandHandler("window", self.window_cmd))
        app.add_handler(CommandHandler("apps", self.window_cmd))
        app.add_handler(CommandHandler("kamera", self.camera_cmd))
        app.add_handler(CommandHandler("foto", self.camera_cmd))
        app.add_handler(CommandHandler("webcam", self.camera_cmd))
        app.add_handler(CommandHandler("capture", self.capture_screen_cmd))
        app.add_handler(CommandHandler("screenshot", self.capture_screen_cmd))
        app.add_handler(CommandHandler("ss", self.capture_screen_cmd))
        app.add_handler(CommandHandler("tutup", self.close_app_cmd))
        app.add_handler(CommandHandler("close", self.close_app_cmd))
        app.add_handler(CommandHandler("cari", self.cari_cmd))
        app.add_handler(CommandHandler("search", self.cari_cmd))
        app.add_handler(CommandHandler("buka", self.open_app_cmd))
        app.add_handler(CommandHandler("open", self.open_app_cmd))
        app.add_handler(CommandHandler("tabs", self.tabs_cmd))
        app.add_handler(CommandHandler("tab", self.tabs_cmd))
        app.add_handler(CommandHandler("volume", self.volume_cmd))
        app.add_handler(CommandHandler("vol", self.volume_cmd))
        app.add_handler(CommandHandler("mute", self.mute_cmd))
        app.add_handler(CommandHandler("unmute", self.unmute_cmd))
        app.add_handler(CommandHandler("play", self.play_pause_cmd))
        app.add_handler(CommandHandler("pause", self.play_pause_cmd))
        app.add_handler(CommandHandler("next", self.next_track_cmd))
        app.add_handler(CommandHandler("prev", self.prev_track_cmd))
        app.add_handler(CommandHandler("baca", self.read_file_cmd))
        app.add_handler(CommandHandler("read", self.read_file_cmd))
        app.add_handler(CommandHandler("get", self.get_file_cmd))
        app.add_handler(CommandHandler("new", self.new_session_cmd))
        app.add_handler(CommandHandler("sessions", self.list_sessions_cmd))
        app.add_handler(CommandHandler("load", self.load_session_cmd))
        app.add_handler(CommandHandler("memory", self.memory_cmd))

        app.add_handler(CallbackQueryHandler(self.handle_callback_query))

        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_user_message))

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            agent_logger.log_error("telegram_error_handler", str(context.error))
            if isinstance(context.error, telegram.error.Conflict):
                print("\n[PERINGATAN] Terdeteksi bot instance lain yang sedang aktif dengan token yang sama.")
                print("[SOLUSI] Pastikan hanya satu terminal / proses bot_telegram.py yang berjalan.")

        app.add_error_handler(error_handler)
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    gateway = TelegramAgentGateway()
    gateway.run()
