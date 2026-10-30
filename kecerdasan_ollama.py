"""Modul Kecerdasan dan Parser Niat untuk Model AI Lokal (Ollama / Llama).

Menganalisis, membersihkan kata basa-basi/filler (seperti 'coba', 'tolong', 'dong'),
mendeteksi intensi perintah kontrol laptop secara presisi tanpa salah tafsir (anti-misleading),
serta mengekstrak argumen yang tepat saat pengguna mengendalikan laptop dari Telegram maupun terminal.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# Daftar kata basa-basi, filler, dan permohonan dalam Bahasa Indonesia & Inggris
KATA_FILLER = {
    "coba", "cobain", "tolong", "silakan", "silahkan", "mohon", "harap",
    "bisa", "bisakah", "dapatkah", "tolonglah", "mau", "pengen", "ingin",
    "dong", "deh", "yuk", "cuy", "bang", "bro", "min", "gan", "kak", "mas",
    "ya", "yah", "nih", "tuh", "lah", "kah", "saja", "aja", "kali", "dulu",
    "sebentar", "bentar", "cepat", "segera", "sekarang", "langsung",
    "please", "pls", "can you", "could you", "help me", "try to", "just", "now",
    "didalam", "di", "pada", "ke", "dari", "dan", "lalu", "kemudian", "tersebut",
}

# Pemetaan aplikasi umum ke nama proses / executable Windows
APLIKASI_POPULER = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "notepad": "notepad",
    "catatan": "notepad",
    "kalkulator": "calc",
    "calculator": "calc",
    "calc": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "spotify": "spotify",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "settings": "ms-settings:",
    "pengaturan": "ms-settings:",
}

# Pemetaan website umum ke URL resmi
WEBSITE_POPULER = {
    "youtube": "https://www.youtube.com",
    "yt": "https://www.youtube.com",
    "google": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chatgpt.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "wa": "https://web.whatsapp.com",
    "web whatsapp": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "ig": "https://www.instagram.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "fb": "https://www.facebook.com",
    "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "tiktok": "https://www.tiktok.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
}


@dataclass
class NiatTerdeteksi:
    """Representasi terstruktur niat perintah pengguna."""
    kategori: str
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    deskripsi_konfirmasi: str = ""
    apakah_aksi_sistem: bool = True


class KecerdasanOllama:
    """Mesin pemroses bahasa alami cerdas untuk Ollama."""

    @staticmethod
    def bersihkan_kata_filler(teks: str) -> str:
        """Membersihkan kata-kata basa-basi yang sering membingungkan LLM kecil."""
        tokens = teks.strip().split()
        hasil = []
        for t in tokens:
            t_bersih = re.sub(r"[^\w\s]", "", t).lower()
            if t_bersih not in KATA_FILLER:
                hasil.append(t)
        return " ".join(hasil).strip()

    @classmethod
    def analisis_perintah(cls, pesan: str) -> Optional[NiatTerdeteksi]:
        """Menganalisis kalimat pengguna dan menentukan niat aksi yang tepat tanpa misleading.
        
        Mengembalikan NiatTerdeteksi jika cocok dengan perintah laptop, atau None jika chat biasa.
        """
        raw = pesan.strip()
        low = raw.lower()

        # -------------------------------------------------------------
        # Kasus 1: PENGATURAN VOLUME SUARA
        # -------------------------------------------------------------
        if any(k in low for k in ["volume", "suara laptop", "suara pc", "besarkan suara", "kecilkan suara", "mute", "unmute", "senyap"]):
            # Cek angka spesifik (misal: "volume 50", "set volume 80%", "naikkan 10")
            m_pct = re.search(r"(\d+)\s*%", low) or re.search(r"(?:ke|menjadi|jadi|\=)\s*(\d+)", low)
            if m_pct:
                val = m_pct.group(1)
                return NiatTerdeteksi(
                    kategori="volume",
                    tool_name="set_volume",
                    tool_args={"level": f"{val}%"},
                    deskripsi_konfirmasi=f"Mengatur volume speaker laptop ke {val}%.",
                )

            if "unmute" in low or "nyalakan suara" in low or "hidupkan suara" in low:
                return NiatTerdeteksi(
                    kategori="volume",
                    tool_name="set_volume",
                    tool_args={"level": "unmute"},
                    deskripsi_konfirmasi="Menyalakan kembali suara master laptop (Unmute).",
                )

            if "mute" in low or "senyap" in low or "matikan suara" in low or "hening" in low:
                return NiatTerdeteksi(
                    kategori="volume",
                    tool_name="set_volume",
                    tool_args={"level": "mute"},
                    deskripsi_konfirmasi="Mematikan suara master laptop (Mute).",
                )

            if any(k in low for k in ["naik", "tambah", "besar", "keras", "up"]):
                return NiatTerdeteksi(
                    kategori="volume",
                    tool_name="set_volume",
                    tool_args={"level": "+10"},
                    deskripsi_konfirmasi="Menaikkan volume laptop (+10%).",
                )

            if any(k in low for k in ["turun", "kurang", "kecil", "pelan", "down"]):
                return NiatTerdeteksi(
                    kategori="volume",
                    tool_name="set_volume",
                    tool_args={"level": "-10"},
                    deskripsi_konfirmasi="Menurunkan volume laptop (-10%).",
                )

            return NiatTerdeteksi(
                kategori="volume",
                tool_name="set_volume",
                tool_args={"level": "status"},
                deskripsi_konfirmasi="Mengecek status level volume laptop saat ini.",
            )

        # -------------------------------------------------------------
        # Kasus 2: KONTROL MEDIA PLAYBACK (YouTube / Spotify)
        # -------------------------------------------------------------
        if any(k in low for k in [
            "pause lagu", "jeda lagu", "play lagu", "putar lagu", "lanjut lagu",
            "stop lagu", "berhenti lagu", "next lagu", "lagu berikutnya", "prev lagu",
            "lagu sebelumnya", "next track", "prev track", "pause musik", "play musik",
            "jeda musik", "putar musik", "stop musik", "jeda video", "pause video",
            "lanjutkan video", "putar video", "pause youtube", "play youtube"
        ]):
            action = "play_pause"
            if any(k in low for k in ["next", "berikutnya", "selanjutnya"]):
                action = "next"
            elif any(k in low for k in ["prev", "sebelumnya", "kembali"]):
                action = "prev"
            elif any(k in low for k in ["stop", "berhenti"]):
                action = "stop"
            elif any(k in low for k in ["pause", "jeda"]):
                action = "pause"
            elif any(k in low for k in ["play", "putar", "lanjut"]):
                action = "play"

            return NiatTerdeteksi(
                kategori="media",
                tool_name="media_control",
                tool_args={"action": action},
                deskripsi_konfirmasi=f"Mengirim tombol kontrol media: {action.upper()}.",
            )

        # -------------------------------------------------------------
        # Kasus 3: MONITORING BATERAI, STATUS LAPTOP, & HARDWARE
        # -------------------------------------------------------------
        if any(k in low for k in [
            "cek baterai", "baterai", "battery", "status laptop", "status pc",
            "kondisi laptop", "cek ram", "cek cpu", "cek storage", "cek sistem",
            "spesifikasi", "spek laptop", "info laptop", "status sistem"
        ]):
            return NiatTerdeteksi(
                kategori="system_status",
                tool_name="get_system_status",
                tool_args={},
                deskripsi_konfirmasi="Membaca indikator baterai, RAM, CPU, dan storage laptop.",
            )

        # -------------------------------------------------------------
        # Kasus 4: MONITORING TAB & JENDELA BROWSER
        # -------------------------------------------------------------
        if any(k in low for k in [
            "tab browser", "tab chrome", "tab edge", "daftar tab", "list tab",
            "buka apa aja", "sedang buka apa", "tab aktif", "jendela aktif"
        ]):
            return NiatTerdeteksi(
                kategori="browser_tabs",
                tool_name="get_open_browser_tabs",
                tool_args={},
                deskripsi_konfirmasi="Memeriksa seluruh tab dan judul jendela browser yang aktif.",
            )

        # -------------------------------------------------------------
        # Kasus 5: TANGKAPAN LAYAR (SCREENSHOT) & KAMERA
        # -------------------------------------------------------------
        if any(k in low for k in ["screenshot", "screen capture", "tangkapan layar", "foto layar", "ss laptop", "ss layar", "capture screen"]):
            return NiatTerdeteksi(
                kategori="screenshot",
                tool_name="capture_screen",
                tool_args={"output_path": "screen_capture.png"},
                deskripsi_konfirmasi="Mengambil screenshot layar display laptop.",
            )

        if any(k in low for k in ["foto webcam", "kamera laptop", "foto kamera", "capture camera", "ambil foto saya", "jepret webcam"]):
            return NiatTerdeteksi(
                kategori="camera",
                tool_name="capture_camera",
                tool_args={"output_path": "kamera_capture.jpg"},
                deskripsi_konfirmasi="Mengambil foto melalui webcam laptop.",
            )

        # -------------------------------------------------------------
        # Kasus 6: PENGUNCIAN & DAYA LAPTOP (LOCK / SLEEP)
        # -------------------------------------------------------------
        if any(k in low for k in ["kunci laptop", "lock laptop", "kunci layar", "lock screen", "kunci pc", "lock pc"]):
            return NiatTerdeteksi(
                kategori="security",
                tool_name="lock_laptop",
                tool_args={},
                deskripsi_konfirmasi="Mengunci layar laptop (Windows + L).",
            )

        # -------------------------------------------------------------
        # Kasus 7: BUKA YOUTUBE / PENCARIAN LAGU / VIDEO DI YOUTUBE
        # (Masalah Utama: 'coba buka youtube' -> Buka homepage, BUKAN cari 'coba'!)
        # -------------------------------------------------------------
        if re.search(r"\b(youtube|yt)\b", low):
            # Pola 1: Hanya buka homepage YouTube (contoh: "coba buka youtube", "tolong buka yt dong")
            # Jika TIDAK mengandung kata kunci pencarian seperti 'cari', 'search', 'lagu', 'video', 'judul'
            ada_niat_cari = any(k in low for k in ["cari ", "search ", "lagu ", "video ", "tentang ", "judul "])

            if not ada_niat_cari:
                # Periksa apakah ada kata substantif selain kata kerja buka dan nama youtube
                bersih = cls.bersihkan_kata_filler(low)
                sisa_kata = [w for w in bersih.split() if w not in ["buka", "open", "youtube", "yt", "chrome", "di", "ke"]]
                if not sisa_kata:
                    # MURNI hanya membuka homepage YouTube!
                    return NiatTerdeteksi(
                        kategori="youtube_open",
                        tool_name="open_application",
                        tool_args={"app_or_query": "https://www.youtube.com"},
                        deskripsi_konfirmasi="Membuka homepage YouTube di browser.",
                    )

            # Pola 2: Ada niat pencarian atau pemutaran lagu/video spesifik di YouTube
            m_cari = re.search(r"(?:cari|search|lagu|video|putar|play)\s+(?:di\s+youtube|di\s+yt)?\s*(.+)", raw, re.IGNORECASE)
            search_query = ""
            if m_cari:
                search_query = m_cari.group(1).strip()
            else:
                # Bersihkan kata kerja & filler
                bersih_q = cls.bersihkan_kata_filler(raw)
                for w in ["buka", "open", "youtube", "yt", "chrome", "di", "ke"]:
                    bersih_q = re.sub(r"\b" + w + r"\b", "", bersih_q, flags=re.IGNORECASE).strip()
                search_query = bersih_q

            # Bersihkan sisa kata filler dari search query
            search_query = cls.bersihkan_kata_filler(search_query)

            if search_query and len(search_query) > 1:
                return NiatTerdeteksi(
                    kategori="youtube_search",
                    tool_name="play_youtube_video",
                    tool_args={"video_id_or_url": search_query},
                    deskripsi_konfirmasi=f"Mencari dan memutar video di YouTube: \"{search_query}\".",
                )
            else:
                return NiatTerdeteksi(
                    kategori="youtube_open",
                    tool_name="open_application",
                    tool_args={"app_or_query": "https://www.youtube.com"},
                    deskripsi_konfirmasi="Membuka homepage YouTube di browser.",
                )

        # -------------------------------------------------------------
        # Kasus 8: BUKA WEBSITE / URL UMUM
        # -------------------------------------------------------------
        # Cek apakah ada nama website populer setelah kata buka/open
        for web_key, web_url in WEBSITE_POPULER.items():
            if re.search(r"\b(buka|open)\s+" + re.escape(web_key) + r"\b", low) or low == web_key:
                return NiatTerdeteksi(
                    kategori="browser_url",
                    tool_name="open_application",
                    tool_args={"app_or_query": web_url},
                    deskripsi_konfirmasi=f"Membuka situs web {web_key.capitalize()} ({web_url}).",
                )

        # Cek URL langsung (http://, https://, atau domain .com, .id, dll)
        m_url = re.search(r"(https?://\S+|www\.\S+|\b[a-zA-Z0-9\-_]+\.(?:com|id|org|net|io|co|me|dev)\b)", raw)
        if m_url and ("buka" in low or "open" in low or "kunjungi" in low):
            target_url = m_url.group(1)
            if not target_url.startswith("http"):
                target_url = "https://" + target_url
            return NiatTerdeteksi(
                kategori="browser_url",
                tool_name="open_application",
                tool_args={"app_or_query": target_url},
                deskripsi_konfirmasi=f"Membuka URL di browser: {target_url}.",
            )

        # -------------------------------------------------------------
        # Kasus 9: BUKA APLIKASI DESKTOP
        # -------------------------------------------------------------
        if any(low.startswith(k) or f" {k}" in low for k in ["buka ", "open ", "jalankan ", "start "]):
            # Ekstrak nama aplikasi yang diminta
            bersih_app = cls.bersihkan_kata_filler(low)
            for w in ["buka", "open", "jalankan", "start", "aplikasi", "program"]:
                bersih_app = re.sub(r"\b" + w + r"\b", "", bersih_app, flags=re.IGNORECASE).strip()

            target_app = bersih_app.strip()
            # Cek kecocokan dengan kamus aplikasi populer
            if target_app in APLIKASI_POPULER:
                nama_exe = APLIKASI_POPULER[target_app]
                return NiatTerdeteksi(
                    kategori="app_open",
                    tool_name="open_application",
                    tool_args={"app_or_query": nama_exe},
                    deskripsi_konfirmasi=f"Membuka aplikasi desktop: {target_app.capitalize()}.",
                )
            elif target_app:
                return NiatTerdeteksi(
                    kategori="app_open",
                    tool_name="open_application",
                    tool_args={"app_or_query": target_app},
                    deskripsi_konfirmasi=f"Membuka aplikasi atau perintah: {target_app}.",
                )

        # -------------------------------------------------------------
        # Kasus 10: MENUTUP APLIKASI DESKTOP (CLOSE / KILL)
        # -------------------------------------------------------------
        if any(k in low for k in ["tutup ", "close ", "matikan ", "kill ", "hentikan "]):
            bersih_close = cls.bersihkan_kata_filler(low)
            for w in ["tutup", "close", "matikan", "kill", "hentikan", "aplikasi", "program"]:
                bersih_close = re.sub(r"\b" + w + r"\b", "", bersih_close, flags=re.IGNORECASE).strip()

            target_close = bersih_close.strip()
            if target_close in APLIKASI_POPULER:
                target_close = APLIKASI_POPULER[target_close]

            if target_close:
                return NiatTerdeteksi(
                    kategori="app_close",
                    tool_name="close_application",
                    tool_args={"process_name": target_close},
                    deskripsi_konfirmasi=f"Menutup aplikasi: {target_close}.",
                )

        # Tidak cocok dengan perintah kontrol laptop -> serahkan ke model Ollama sebagai percakapan/coding biasa
        return None
