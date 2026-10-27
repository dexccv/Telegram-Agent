# Gemini Terminal Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Indonesiaku--Lang](https://img.shields.io/badge/Language-Indonesiaku--Lang-FF0000?style=flat-square)](https://github.com/teguh02/Indonesiaku-Lang)
[![Telegram Gateway](https://img.shields.io/badge/Telegram-Remote%20Control-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org)
[![Google GenAI](https://img.shields.io/badge/Google-GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

Terminal AI Agent modern, interaktif, dan beranimasi yang dibangun di atas Python dan **Indonesiaku-Lang** (`.idk`). Dilengkapi dengan antarmuka **Textual TUI**, integrasi model AI ganda (*Google Gemini*, *Local Ollama*, dan *Omniroute*), eksekusi perkakas otonom (*tool calling*), serta **Telegram Mobile Gateway** untuk memantau dan mengendalikan laptop secara real-time langsung dari handphone.

---

## 🌟 Fitur Utama

### 🖥️ Antarmuka Terminal (TUI) Modern
- **Tampilan Dark Mode Berkelas**: Desain visual elegan berbasis [Textual](https://textual.textualize.io/) dan [Rich](https://rich.readthedocs.io/) dengan animasi *typing effect*, *loading spinner*, dan palet tema dinamis (`default`, `emerald`, `crimson`, `amber`, `purple`).
- **Interupsi Instan (Interrupt)**: Hentikan pemrosesan agen atau loop pemanggilan alat seketika dengan `Ctrl + X`, `Escape`, atau tombol **Hentikan ⏹**.
- **Penyuntingan Konteks Cepat**: Sisipkan isi berkas ke prompt secara langsung menggunakan sintaks `@nama_berkas` (misal: `@app.py`).

### 📱 Telegram Mobile Gateway (Remote Laptop Control)
Kendalikan dan pantau laptop Anda kapan pun dan di mana pun melalui aplikasi Telegram dengan perlindungan keamanan *whitelist*:
- **Dashboard Real-Time (`/status`)**: Pantau status daya baterai, pengisian charger, nama SSID & kekuatan sinyal Wi-Fi, jendela aktif di layar, beban CPU, penggunaan RAM, dan penyimpanan disk.
- **Peluncur Aplikasi Interaktif (`/buka`)**: Menu tombol inline untuk membuka aplikasi desktop seperti Google Chrome, YouTube, Spotify, VS Code, Notepad, Kalkulator, File Explorer, atau Terminal.
- **Pencarian YouTube & Browser Otomatis**: Perintah seperti `buka chrome lalu buka youtube dan cari lagu hindia` secara cerdas mengurai kata kunci dan memutar pencarian di browser.
- **Penjelajah Berkas & Pengunduh Berkas (`/get`)**: File picker interaktif dengan navigasi folder (Project, Downloads, Documents, Desktop, Drive C/D) untuk mengunduh berkas apa saja dari laptop ke Telegram ponsel dalam 1 ketukan.
- **Pengatur Suara Master (`/volume`, `/mute`, `/unmute`)**: Panel tombol inline untuk mengatur volume laptop (0–100%, +10%, -10%, Mute/Unmute) secara instan via Windows Core Audio.
- **Webcam Snapshot (`/kamera`)**: Ambil foto langsung dari kamera webcam laptop dan kirimkan secara aman ke Telegram.
- **Manajemen Proses (`/tutup`)**: Tutup aplikasi yang sedang berjalan dari jarak jauh (misal: `/tutup chrome`).
- **Benchmark Latensi & Kecepatan (`/speed`)**: Uji kecepatan roundtrip server Telegram dan kecepatan token/detik pemrosesan AI.

### 🧠 Multi-Turn Sesi & Memori Jangka Panjang
- **Sesi Persisten**: Riwayat percakapan disimpan dalam format JSON di `~/.gemini-agent/sessions/`. Anda dapat berpindah sesi, memulihkan sesi lama, atau mengekspor percakapan ke Markdown (`/session`, `/export`).
- **Memori Persisten**: Preferensi dan fakta penting disimpan di `~/.gemini-agent/memory.json` dan otomatis diinjeksi ke instruksi sistem di setiap sesi (`/memory`).

### 🤖 Multi-Provider AI
- **Google Gemini**: Integrasi SDK resmi `google-genai` dengan model seperti `gemini-2.5-flash`, `gemini-2.5-pro`, dan kapabilitas multimodal.
- **Local Ollama**: Dukungan eksekusi model lokal offline (seperti `qwen2.5-coder:7b`, `llama3.1`, `deepseek-r1`) dengan penyimpanan model yang dapat disesuaikan.
- **Omniroute / OpenAI-Compatible**: Dukungan gateway proksi AI dengan endpoint OpenAI-compatible.

---

## 🇮🇩 Bahasa Pemrograman: Indonesiaku-Lang (.idk)

Seluruh arsitektur inti logika agen, modul memori, pengelola sesi, perkakas eksekusi, antarmuka TUI, dan konfigurasi ditulis menggunakan bahasa pemrograman **Indonesiaku-Lang** (`.idk`) yang terinspirasi dari [teguh02/Indonesiaku-Lang](https://github.com/teguh02/Indonesiaku-Lang).

```idk
fungsi open_application(app_or_query: str) -> str {
    jika "youtube" dalam app_or_query.lower() {
        # Buka Chrome dan putar pencarian YouTube
        kembalikan "[SUKSES] Berhasil membuka YouTube di Chrome."
    }
}
```

Modul `.idk` dikompilasi dan dimuat secara dinamis saat runtime oleh engine `penerjemah_idk.py` melalui `sys.meta_path` import hook sehingga beroperasi sepenuhnya native tanpa jeda translasi manual.

---

## 📁 Struktur Repositori

```text
gemini-terminal-agent/
├── app.py                 # Pintu masuk utama aplikasi & peluncur background gateway
├── utama.py               # Launcher alternatif runtime Indonesiaku-Lang
├── bot_telegram.py        # Gateway Remote Control Telegram (Real-Time Monitor & Commands)
│
├── aplikasi.idk           # Antarmuka visual TUI Textual & modal dialog (.idk)
├── agen.idk               # Mesin agen AI, orchestration multi-turn, & function calls (.idk)
├── perkakas.idk           # Kumpulan alat eksekusi file, shell, volume, & launcher (.idk)
├── konfigurasi.idk        # Pengelola konfigurasi lingkungan & berkas .env (.idk)
├── pengelola_sesi.idk     # Pengelola riwayat sesi percakapan persisten (.idk)
├── memori.idk             # Pengelola memori jangka panjang pengguna (.idk)
├── penerjemah_idk.py      # Runtime loader & compiler AST Indonesiaku-Lang
│
├── logger.py              # Sistem logging terstruktur rotasi harian
├── requirements.txt       # Daftar dependensi library Python
├── run.bat / run.sh       # Script launcher 1-klik (Windows / Linux)
├── run_bot.bat / .sh      # Script launcher dedicated bot Telegram
└── README.md              # Dokumentasi teknis proyek
```

---

## 🚀 Panduan Instalasi & Menjalankan

### Persyaratan Sistem
- Python 3.10 atau versi yang lebih tinggi
- Akses internet untuk Gemini API / Telegram Bot, atau Ollama untuk mode lokal offline
- OS: Windows 10/11 (dukungan penuh kontrol audio & webcam), Linux, atau macOS

### 1. Kloning Repositori
```bash
git clone https://github.com/dexccv/gemini-cli.git
cd gemini-cli
```

### 2. Cara Cepat (Rekomendasi)
* **Pengguna Windows**:
  ```cmd
  run.bat
  ```
* **Pengguna Linux / macOS**:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
*Script launcher akan otomatis membuat virtual environment `.venv`, memasang dependensi, dan menyalakan aplikasi.*

### 3. Cara Manual
```bash
# Buat dan aktifkan virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# Pasang dependensi
pip install -r requirements.txt

# Jalankan Terminal Agent TUI
python app.py
```

---

## 📲 Panduan Telegram Mobile Gateway

Gateway Telegram memungkinkan Anda memantau dan memberikan perintah ke laptop dari smartphone kapan saja.

### Konfigurasi Awal
Tambahkan token bot dan ID Telegram Anda ke `~/.gemini-agent/.env`:
```env
TELEGRAM_BOT_TOKEN=token_bot_anda_dari_botfather
TELEGRAM_ALLOWED_USER_ID=user_id_angka_anda
```

> **Keamanan Whitelist**: Bot dilindungi dengan whitelist ID Telegram. Setiap pesan dari akun yang tidak terdaftar akan otomatis ditolak.

### Perintah Utama Telegram Bot
| Perintah | Deskripsi |
| :--- | :--- |
| `/status` | Menampilkan dashboard monitoring laptop real-time (baterai, Wi-Fi, jendela aktif, hardware). |
| `/buka` | Membuka panel tombol aplikasi laptop (Chrome, YouTube, Spotify, VS Code, Notepad, dll). |
| `/buka <target>` | Buka aplikasi, tautan URL, atau cari YouTube langsung (misal: `/buka youtube lagu hindia`). |
| `/get` | Membuka Penjelajah Berkas (File Picker) interaktif untuk mengunduh file laptop ke ponsel. |
| `/get <path>` | Mengunduh file tertentu dari laptop (mendukung path di dalam maupun di luar workspace). |
| `/volume` | Membuka panel tombol kontrol volume laptop (0–100%, +10%, -10%, Mute/Unmute). |
| `/mute` / `/unmute` | Mematikan atau menghidupkan kembali suara speaker laptop secara instan. |
| `/kamera` | Mengambil foto langsung dari webcam laptop dan mengirimkannya ke chat. |
| `/tutup <nama>` | Menutup aplikasi desktop tertentu yang sedang berjalan di laptop. |
| `/speed` | Menguji latensi respons model AI dan kecepatan kirim jaringan Telegram. |
| `/baca <file>` | Membaca isi berkas teks lokal laptop langsung di Telegram. |
| `/provider` | Melihat atau mengganti provider AI aktif (`gemini`, `ollama`, `omniroute`). |
| `/models` / `/model` | Memindai dan mengganti model AI yang aktif digunakan. |
| `/new` / `/sessions` | Memulai sesi percakapan baru atau beralih sesi percakapan lama. |

---

## ⌨️ Pintasan Keyboard Terminal TUI

| Tombol Pintasan | Fungsi |
| :--- | :--- |
| `Enter` | Mengirim pesan prompt ke agen |
| `Ctrl + X` / `Escape` | Menghentikan respon agen seketika (*Interrupt*) |
| `Ctrl + S` | Membuka jendela dialog manajemen dan pemulihan sesi |
| `Ctrl + M` | Membuka jendela dialog pemilihan model AI |
| `Ctrl + T` | Beralih tema warna antarmuka secara berurutan |
| `Ctrl + R` | Memulai ulang aplikasi terminal (*Restart*) |
| `Ctrl + L` | Membersihkan riwayat tampilan layar chat |
| `Ctrl + C` | Keluar dari aplikasi terminal |

---

## 🛡️ Keamanan & Perlindungan Sistem

Agen dilengkapi dengan perlindungan keamanan terintegrasi:
- **Sandbox Workspace**: Pembatasan akses baca dan tulis file untuk mencegah modifikasi tidak disengaja di luar folder kerja, kecuali diminta secara eksplisit melalui perintah bot terotentikasi.
- **Filter Perintah Shell**: Memblokir perintah berbahaya seperti format partisi, penghapusan root direktori paksa (`rm -rf /`), atau shutdown tak terduga.
- **Aturan Autentikasi Tunggal**: Gateway Telegram hanya merespons perintah dari ID pemilik sah yang tertera pada konfigurasi lokal.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi [MIT](LICENSE).
