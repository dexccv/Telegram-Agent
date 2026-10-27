"""Gateway Telegram Bot untuk Gemini Terminal Agent.

Memungkinkan pengguna mengendalikan AI Agent di laptop secara penuh dari handphone
kapan pun dan di mana pun melalui aplikasi Telegram dengan perlindungan keamanan whitelist.
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import sys
from pathlib import Path

# Aktifkan runtime loader Indonesiaku-Lang
from penerjemah_idk import aktifkan_hook_idk

aktifkan_hook_idk()

import telegram.error
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
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
        msg = (
            f"Halo **{user_name}**! 👋\n\n"
            f"⌬ **Terminal Laptop Agent Siap Melayani**\n"
            f"• **Status Laptop**: ONLINE\n"
            f"• **Provider AI**: `{prov}`\n"
            f"• **Model AI**: `{self.agent.model_name}`\n"
            f"• **Sesi Aktif**: `{self.agent.session.title}`\n"
            f"• **Direktori Kerja**: `{Path.cwd().name}`\n\n"
            "Ketik instruksi apa saja (misal: *'buatkan file script.py dan jalankan'*), "
            "atau ketik `/help` untuk daftar perintah lengkap."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        help_text = (
            "📋 **Panduan Perintah Telegram Gateway**\n\n"
            "• **Kirim Pesan Biasa**: Instruksi langsung ke AI Agent untuk manipulasi berkas, shell, atau komputasi di laptop.\n"
            "• `/provider [gemini/omniroute]` : Cek atau ganti provider AI aktif.\n"
            "• `/models` : Pindai & tampilkan daftar model AI yang tersedia.\n"
            "• `/model <nama_model>` : Ganti model aktif (misal: `/model auto` atau `/model auto/best-fast`).\n"
            "• `/status` : Informasi hardware laptop (baterai, OS, memori, token).\n"
            "• `/get <nama_berkas>` : Unduh berkas dari laptop langsung ke Telegram HP Anda.\n"
            "• `/new [judul]` : Mulai sesi percakapan baru yang bersih.\n"
            "• `/sessions` : Lihat daftar sesi yang tersimpan di laptop.\n"
            "• `/load <no/id>` : Beralih ke sesi percakapan lama.\n"
            "• `/memory` : Lihat fakta memori jangka panjang agent.\n"
            "• `/stop` : Batalkan respon agen yang sedang berjalan.\n"
            "• **Kirim File/Foto**: Kirim berkas dari HP ke Telegram bot, dan agen akan langsung menyimpannya ke laptop."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def status_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.is_authorized(update):
            await self.unauthorized_handler(update)
            return

        os_name = platform.system()
        node_name = platform.node()
        tokens = self.agent.last_usage_metadata.get("total_tokens", 0)

        # Cek baterai jika ada
        battery_info = "Tidak terdeteksi"
        try:
            if os_name == "Windows":
                out = subprocess.check_output(
                    "powershell -Command \"Get-WmiObject -Class Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining\"",
                    shell=True,
                    text=True,
                    timeout=5,
                ).strip()
                if out:
                    battery_info = f"{out}%"
        except Exception:
            pass

        info_text = (
            f"💻 **Status Sistem Laptop**\n"
            f"• **Nama Device**: `{node_name}`\n"
            f"• **Sistem Operasi**: {os_name} ({platform.release()})\n"
            f"• **Baterai Laptop**: {battery_info}\n"
            f"• **Model AI**: `{self.agent.model_name}`\n"
            f"• **Sesi Aktif**: `{self.agent.session.title}`\n"
            f"• **Penggunaan Token**: `{tokens:,} tokens`\n"
            f"• **Waktu Server**: `{Path.cwd()}`"
        )
        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN)

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

        def _on_tool_call(tool_name: str, args: dict) -> None:
            brief = ", ".join([f"{k}={v}" for k, v in args.items()])[:50]
            try:
                loop.create_task(
                    context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚙️ `[Alat]` Menjalankan **{tool_name}**({brief})...",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                )
            except Exception:
                pass

        def _run_agent() -> str:
            return self.agent.send_message(
                message=user_text,
                on_tool_call=_on_tool_call,
            )

        try:
            # Jalankan di background worker thread agar event loop Telegram tidak terblokir
            response_text = await asyncio.to_thread(_run_agent)
            await status_msg.delete()

            # Kirim balasan respon (pecah jika panjang)
            chunks = split_message(response_text)
            for idx, chunk in enumerate(chunks):
                try:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    # Fallback ke plain text jika Markdown mengandung karakter unescaped
                    await update.message.reply_text(chunk)

        except Exception as exc:
            err_msg = f"❌ Terjadi kesalahan saat memproses di laptop: {exc}"
            agent_logger.log_error("telegram_gateway", str(exc))
            try:
                await status_msg.edit_text(err_msg)
            except Exception:
                await update.message.reply_text(err_msg)

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

        app = Application.builder().token(self.bot_token).build()

        app.add_handler(CommandHandler("start", self.start_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("provider", self.provider_cmd))
        app.add_handler(CommandHandler("models", self.models_cmd))
        app.add_handler(CommandHandler("model", self.model_cmd))
        app.add_handler(CommandHandler("status", self.status_cmd))
        app.add_handler(CommandHandler("get", self.get_file_cmd))
        app.add_handler(CommandHandler("new", self.new_session_cmd))
        app.add_handler(CommandHandler("sessions", self.list_sessions_cmd))
        app.add_handler(CommandHandler("load", self.load_session_cmd))
        app.add_handler(CommandHandler("memory", self.memory_cmd))

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
