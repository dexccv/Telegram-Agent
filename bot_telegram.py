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
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

# Aktifkan runtime loader Indonesiaku-Lang
from penerjemah_idk import aktifkan_hook_idk

aktifkan_hook_idk()

import telegram.error
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Modul logika ditulis dalam Indonesiaku-Lang (.idk) dan dimuat dinamis via hook penerjemah_idk
import agen  # type: ignore[import-not-found]
import konfigurasi  # type: ignore[import-not-found]
import memori  # type: ignore[import-not-found]
import pengelola_sesi  # type: ignore[import-not-found]
from logger import agent_logger

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

        print(f"[*] Menginisialisasi Terminal Agent [Provider: {self.provider.upper()}, Model: {self.model_name}]...")
        self.agent = agen.AgenGemini(api_key=self.api_key, model_name=self.model_name)
        print(f"[OK] Agen siap. Whitelist Telegram User ID: {self.allowed_user_id or 'Semua User (Hati-hati!)'}")

    def is_authorized(self, update: Update) -> bool:
        """Memeriksa apakah pengirim pesan adalah pemilik sah laptop."""
        if not self.allowed_user_id:
            return True
        user = update.effective_user
        if not user:
            return False
        return str(user.id) == str(self.allowed_user_id)

    async def unauthorized_handler(self, update: Update) -> None:
        if update.message:
            user = update.effective_user
            u_info = f"{user.id} (@{user.username})" if user else "Anonim"
            agent_logger.log_warning("telegram_gateway", f"Percobaan akses tidak dikenal dari {u_info}")
            await update.message.reply_text(
                "⛔ Akses Ditolak: Bot ini dikunci secara privat untuk pemilik laptop ini."
            )

    async def start_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

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
            "• `/buka <target>` : Buka aplikasi, link, atau cari lagu di YouTube (misal: `/buka youtube lagu hindia`).\n"
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
            ]
        )
        return text, keyboard

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

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

    async def open_app_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Membuka aplikasi desktop, link URL, atau mencari di YouTube / Google."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text(
                "⚠️ Masukkan nama aplikasi, link, atau pencarian YouTube. Contoh:\n"
                "• `/buka chrome`\n"
                "• `/buka youtube lagu hindia`\n"
                "• `/buka spotify`\n"
                "• `/buka https://google.com`"
            )
            return

        target_query = " ".join(context.args).strip()
        import perkakas
        fn_open = getattr(perkakas, "open_application", None)
        if fn_open:
            status_msg = await update.message.reply_text(f"⏳ Membuka `{target_query}` di laptop...")
            res = await asyncio.to_thread(fn_open, target_query)
            try:
                await status_msg.edit_text(f"🖥️ {res}")
            except Exception:
                await update.message.reply_text(f"🖥️ {res}")
        else:
            await update.message.reply_text("❌ Fungsi open_application tidak tersedia.")

    def _build_volume_markup(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
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
                    InlineKeyboardButton("🔄 Refresh Volume", callback_data="vol_status"),
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

    async def get_file_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mengirim berkas dari laptop ke HP pengguna via Telegram document."""
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        if not context.args:
            await update.message.reply_text("⚠️ Masukkan nama berkas. Contoh: `/get README.md`")
            return

        target_name = " ".join(context.args).strip()
        target_path = Path(target_name).resolve()

        if not target_path.exists() or not target_path.is_file():
            await update.message.reply_text(f"❌ Berkas `{target_name}` tidak ditemukan di laptop.")
            return

        file_size = target_path.stat().st_size
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Ukuran berkas melebihi batas 50 MB Telegram Bot.")
            return

        await update.message.reply_text(f"📤 Mengunggah berkas `{target_path.name}` ({file_size} byte)...")
        with open(target_path, "rb") as f:
            await update.message.reply_document(document=f, caption=f"Berkas dari laptop: `{target_path.name}`")

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

        self.config.simpan_provider(target)
        self.provider = target
        self.api_key = self.config.ambil_api_key()
        self.model_name = self.config.ambil_model()
        self.agent = agen.AgenGemini(api_key=self.api_key, model_name=self.model_name)
        await update.message.reply_text(
            f"✅ Provider AI berhasil dialihkan ke **{target.upper()}** (Model: `{self.model_name}`)",
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
            brief = ", ".join([f"{k}={v}" for k, v in args.items()])[:50]
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
            BotCommand("speed", "Uji kecepatan respon AI & kirim Telegram"),
            BotCommand("kamera", "Ambil foto dari webcam laptop"),
            BotCommand("buka", "Buka aplikasi/Chrome/YouTube (misal: /buka youtube lagu hindia)"),
            BotCommand("tutup", "Tutup aplikasi desktop (contoh: /tutup chrome)"),
            BotCommand("volume", "Atur volume laptop (0-100, +10, -10, mute, unmute)"),
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
            await application.bot.set_my_commands(commands)
        except Exception:
            pass

    def run(self) -> None:
        """Menjalankan bot Telegram polling daemon."""
        print("=" * 60)
        print("  TERMINAL LAPTOP AGENT - TELEGRAM MOBILE GATEWAY")
        print("=" * 60)
        print(f"* Provider Aktif: {self.provider.upper()} (Model: {self.model_name})")
        print(f"* Bot Token: {self.bot_token[:10]}... (Aman)")
        print(f"* Whitelist User ID: {self.allowed_user_id}")
        print("* Status: Sedang mendengarkan pesan dari HP Anda...")
        print("* Tekan Ctrl+C di terminal ini untuk berhenti.\n")

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
        app.add_handler(CommandHandler("tutup", self.close_app_cmd))
        app.add_handler(CommandHandler("close", self.close_app_cmd))
        app.add_handler(CommandHandler("buka", self.open_app_cmd))
        app.add_handler(CommandHandler("open", self.open_app_cmd))
        app.add_handler(CommandHandler("volume", self.volume_cmd))
        app.add_handler(CommandHandler("vol", self.volume_cmd))
        app.add_handler(CommandHandler("mute", self.mute_cmd))
        app.add_handler(CommandHandler("unmute", self.unmute_cmd))
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
