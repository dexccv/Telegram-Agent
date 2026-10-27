# Gemini Terminal Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Indonesiaku--Lang](https://img.shields.io/badge/Language-Indonesiaku--Lang-FF0000?style=flat-square)](https://github.com/teguh02/Indonesiaku-Lang)
[![Groq Cloud LPU](https://img.shields.io/badge/Groq-Ultra--Fast%20LPU-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![Google GenAI](https://img.shields.io/badge/Google-GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Telegram Gateway](https://img.shields.io/badge/Telegram-Remote%20Control-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Gemini Terminal Agent** adalah asisten AI terminal modern, cerdas, dan interaktif yang dibangun menggunakan Python dan bahasa pemrograman **Indonesiaku-Lang** (`.idk`). 

Dilengkapi dengan antarmuka visual **Textual TUI**, dukungan **Multi-Provider AI** (*Groq Cloud LPU*, *Google Gemini*, *Local Ollama*, dan *Omniroute*), kemampuan eksekusi perkakas mandiri (*Autonomous Function Calling*) untuk kontrol sistem laptop, serta **Telegram Mobile Gateway** yang memungkinkan Anda mengendalikan seluruh fungsi laptop dari handphone kapan pun dan di mana pun.

---

## 📑 Daftar Isi
1. [Fitur Utama](#-fitur-utama)
2. [Multi-Provider AI](#-multi-provider-ai)
3. [Daftar Perkakas Sistem (Tool Calling)](#-daftar-perkakas-sistem-tool-calling)
4. [Bahasa Pemrograman: Indonesiaku-Lang](#-bahasa-pemrograman-indonesiaku-lang-idk)
5. [Struktur Berkas](#-struktur-berkas)
6. [Persyaratan Sistem](#-persyaratan-sistem)
7. [Panduan Instalasi & Menjalankan](#-panduan-instalasi--menjalankan)
8. [Panduan Setup Groq AI (Super Cepat ~0.5s)](#-panduan-setup-groq-ai-rekomendasi)
9. [Panduan Setup Telegram Mobile Gateway](#-panduan-setup-telegram-mobile-gateway)
10. [Panduan Setup Local AI (Ollama)](#-panduan-setup-local-ai-ollama-opsional)
11. [Daftar Perintah Telegram Bot](#-daftar-perintah-telegram-bot)
12. [Daftar Pintasan Keyboard Terminal TUI](#-daftar-pintasan-keyboard-terminal-tui)
13. [Konfigurasi Lengkap (.env)](#-konfigurasi-lengkap-env)
14. [Keamanan & Privasi](#-keamanan--privasi)

---

## 🌟 Fitur Utama

### 🧠 Otomasi Kontrol Sistem Laptop Penuh (Autonomous Tool Calling)
Seluruh model AI (Groq, Gemini, Ollama, dan Omniroute) dibekali akses eksekusi perkakas (*Function Calling*) mandiri secara dua arah. Agen dapat memahami bahasa alami untuk:
- Mengatur volume suara speaker laptop, mute/unmute, dan membaca level volume.
- Mengontrol pemutar musik (Play/Pause `F10`, Next `F11`, Prev `F9`, Stop) untuk YouTube, Spotify, atau media player.
- Membuka dan menutup aplikasi desktop (Chrome, Spotify, VS Code, Notepad, Kalkulator, File Explorer, Terminal).
- Mencari video di YouTube secara real-time dan langsung memutarnya otomatis di browser Chrome.
- Memantau tab dan jendela browser yang aktif, memfokuskan tab ke depan, atau menutup tab dari HP.
- Mengambil tangkapan layar display (*screenshot*) dan foto live kamera webcam laptop.
- Memeriksa kesehatan perangkat keras (Beban CPU, RAM, Sisa Baterai, Penyimpanan disk drive C & D).

### ⚡ Fast-Path Direct Execution (< 50ms)
Untuk perintah langsung yang umum (seperti *"play lagu"*, *"tutup chrome"*, *"naikkan volume 20"*, *"screenshot"*), agen mendeteksi intent secara lokal dan mengeksekusinya seketika tanpa perlu menunggu jeda koneksi internet.

### 📱 Telegram Remote Gateway (Kendalikan Laptop dari HP)
- **Monitoring Real-Time (`/status`)**: Pantau daya baterai & charger, koneksi Wi-Fi (SSID, sinyal, IP), jendela aplikasi aktif di layar, beban CPU, pemakaian RAM, dan penyimpanan disk.
- **Pencarian YouTube & Media Cepat (`/cari <aplikasi> <keyword>`)**: Cari lagu/video apa pun (misal: `/cari youtube the jansen`), bot menyajikan daftar video teratas lengkap dengan tautan link langsung serta tombol interaktif untuk langsung memutar (*autoplay*) di laptop.
- **Peluncur Aplikasi Desktop (`/buka`)**: Menu tombol cepat untuk membuka Chrome, Spotify, VS Code, Notepad, File Explorer, Kalkulator, Terminal, atau Edge.
- **Inspeksi & Kontrol Tab Browser (`/tabs`)**: Memantau seluruh tab dan jendela browser (Chrome/Edge) yang sedang aktif di laptop, membawa tab tertentu ke depan layar (*focus*), memutar/jeda musik di tab, atau menutup tab dari HP.
- **Penjelajah Berkas & Pengunduh Dokumen (`/get`)**: Jelajahi folder laptop (Project, Downloads, Documents, Desktop, Drive C/D) dengan tombol inline dan unduh berkas apa pun langsung ke HP dalam satu ketukan.
- **Kontrol Volume & Pemutar Musik (`/volume`, `/play`, `/next`, `/prev`)**: Tombol volume (+/-10%, Mute/Unmute, 20-100%) dan kontrol lagu yang disimulasikan langsung ke keyboard laptop.
- **Tangkapan Layar Display (`/capture`, `/ss`)**: Mengambil screenshot layar laptop resolusi penuh secara instan dan mengirimkannya langsung sebagai foto ke chat Telegram.
- **Tangkapan Kamera Webcam (`/kamera`)**: Ambil foto live dari webcam laptop dan kirimkan ke chat Telegram.
- **Manajemen Aplikasi (`/tutup`)**: Menutup aplikasi desktop yang sedang berjalan di laptop.
- **Uji Kecepatan & Latensi (`/speed`)**: Benchmark latency respon AI dan roundtrip pengiriman Telegram.

### 🖥️ Antarmuka Terminal (TUI) Modern
- **Desain Dark Mode Estetik**: Dibangun menggunakan [Textual](https://textual.textualize.io/) & [Rich](https://rich.readthedocs.io/) dengan animasi ketik (*typing effect*), *loading spinner*, serta beragam tema warna (`default`, `emerald`, `crimson`, `amber`, `purple`).
- **Interupsi Cepat (*Interrupt*)**: Batalkan proses generate model atau loop perkakas secara instan dengan menekan `Ctrl + X` / `Escape` atau tombol **Hentikan ⏹**.
- **Konteks Berkas Cepat**: Sisipkan isi berkas lokal ke prompt hanya dengan mengetik `@nama_berkas` (contoh: `@app.py`).

### 💾 Multi-Turn Sesi & Memori Persisten
- Riwayat percakapan otomatis tersimpan di `~/.gemini-agent/sessions/`.
- Memori jangka panjang pengguna tersimpan di `~/.gemini-agent/memory.json` dan otomatis diinjeksi ke sistem instruksi model.

---

## 🤖 Multi-Provider AI

Aplikasi mendukung perpindahan provider AI secara dinamis melalui perintah `/provider <nama>` di TUI maupun Telegram:

| Provider | Backend | Kecepatan | Fitur Unggulan |
| :--- | :--- | :--- | :--- |
| **Groq** ⚡ *(Rekomendasi)* | Groq Cloud LPU | **~0.3s - 0.8s** | Kuota gratis 14.400 req/hari, model OpenAI `openai/gpt-oss-120b` (120B reasoning) & `openai/gpt-oss-20b`, native function calling. |
| **Google Gemini** | Google GenAI SDK | **~1.5s - 3.0s** | Resmi dari Google (`gemini-2.5-flash`, `gemini-3-flash`), multimodal, integrasi Google Workspace. |
| **Ollama** | Local Offline Engine | Tergantung Hardware | 100% offline & privat, mendukung penyimpanan model di drive `D:\.ollama\models`, auto-start daemon otomatis. |
| **Omniroute** | OpenAI Compatible Proxy | Bervariasi | Mendukung routing upstream model kustom atau server lokal. |

---

## 🛠️ Daftar Perkakas Sistem (Tool Calling)

Seluruh perkakas berikut dapat dipanggil secara otomatis oleh AI Agent saat Anda memberikan instruksi dalam bahasa sehari-hari:

| Nama Fungsi | Deskripsi | Parameter |
| :--- | :--- | :--- |
| `set_volume` | Mengatur volume suara master laptop (0-100%, +10, -10, mute, unmute, status). | `level: str` |
| `media_control` | Mengendalikan playback pemutar musik (Play/Pause, Next, Prev, Stop). | `action: str` |
| `open_application` | Membuka aplikasi desktop (Chrome, Spotify, Notepad, dll) atau URL / Google Search. | `app_or_query: str` |
| `close_application` | Menghentikan atau menutup aplikasi desktop yang sedang berjalan. | `app_name_or_pid: str` |
| `search_youtube_videos` | Mencari video di YouTube dan mengembalikan daftar judul, durasi, channel, dan URL. | `query: str, limit: int` |
| `play_youtube_video` | Membuka browser Chrome dan langsung memutar video YouTube secara otomatis. | `video_id_or_url: str` |
| `get_open_browser_tabs` | Memindai seluruh tab dan jendela browser (Chrome/Edge) yang sedang aktif di laptop. | *(tanpa parameter)* |
| `focus_window` | Membawa jendela aplikasi atau tab browser tertentu ke layar depan. | `hwnd: int` |
| `close_window_tab` | Menutup jendela atau tab tertentu berdasarkan handle HWND. | `hwnd: int` |
| `control_browser_media` | Mengontrol pemutaran media pada jendela browser tertentu. | `hwnd: int, action: str` |
| `capture_screen` | Mengambil screenshot display layar laptop dan menyimpannya ke berkas gambar. | `output_path: str` |
| `capture_camera` | Mengambil foto live dari kamera webcam laptop. | `output_path: str` |
| `get_system_status` | Membaca metrik real-time beban CPU, RAM, baterai, dan sisa kapasitas penyimpanan disk. | *(tanpa parameter)* |
| `check_speed` | Menguji benchmark kecepatan respons agent dan jaringan. | *(tanpa parameter)* |
| `create_folder` | Membuat direktori/folder baru pada sistem file laptop. | `path: str` |
| `list_files` | Mendaftar berkas dan folder di dalam suatu direktori. | `path: str` |
| `read_file` | Membaca isi teks dari berkas lokal di sistem. | `path: str` |
| `write_file` | Menulis atau membuat berkas baru dengan isi teks tertentu. | `path: str, content: str` |
| `run_command` | Menjalankan perintah terminal/shell secara aman dengan filter blacklist. | `command: str` |
| `save_memory` | Menyimpan fakta preferensi pengguna ke memori jangka panjang persisten. | `key: str, value: str` |
| `recall_memory` | Mengingat kembali fakta tertentu dari memori jangka panjang. | `key: str` |
| `list_memories` | Menampilkan seluruh catatan fakta yang tersimpan dalam memori. | *(tanpa parameter)* |

---

## 🇮🇩 Bahasa Pemrograman: Indonesiaku-Lang (.idk)

Seluruh logika inti agen, modul memori, pengelola sesi, perkakas eksekusi, antarmuka visual TUI, dan pengelola konfigurasi ditulis menggunakan bahasa pemrograman **Indonesiaku-Lang** (`.idk`).

Runtime dieksekusi secara native oleh engine `penerjemah_idk.py` via `sys.meta_path` import hook yang menerjemahkan sintaks bahasa Indonesia ke Python AST saat runtime tanpa jeda kompilasi manual.

---

## 📁 Struktur Berkas

```text
gemini-terminal-agent/
├── app.py                 # Pintu masuk utama aplikasi & peluncur background bot
├── utama.py               # Launcher runtime alternatif Indonesiaku-Lang
├── bot_telegram.py        # Gateway Remote Control Telegram
├── agent.py               # Implementasi modul agen Python murni
├── tools.py               # Kumpulan fungsi perkakas Python murni
├── config.py              # Pengelola konfigurasi Python murni
│
├── aplikasi.idk           # Antarmuka TUI Textual (.idk)
├── agen.idk               # Mesin agen AI & direct actions (.idk)
├── perkakas.idk           # Kumpulan perkakas sistem, audio, launcher, shell (.idk)
├── konfigurasi.idk        # Pengelola konfigurasi direktori ~/.gemini-agent & .env (.idk)
├── pengelola_sesi.idk     # Pengelola riwayat percakapan sesi persisten (.idk)
├── memori.idk             # Pengelola memori jangka panjang (.idk)
├── penerjemah_idk.py      # Engine penerjemah & compiler Indonesiaku-Lang
│
├── logger.py              # Sistem logging terstruktur rotasi harian
├── requirements.txt       # Dependensi library Python
├── run.bat / run.sh       # Script launcher otomatis (Windows / Linux / macOS)
├── run_bot.bat / .sh      # Script dedicated launcher bot Telegram
└── README.md              # Dokumentasi panduan proyek
```

---

## 💻 Persyaratan Sistem

- **Python**: Versi `3.10` atau lebih baru.
- **Sistem Operasi**: Windows 10/11 (disarankan untuk kontrol volume audio & shortcut keyboard), Linux, atau macOS.
- **Koneksi Internet**: Untuk akses API Groq Cloud, Google Gemini, dan polling Telegram Bot.
- **Kunci API**: Groq API Key gratis di [Groq Console](https://console.groq.com/keys) atau Google Gemini API Key di [Google AI Studio](https://aistudio.google.com/).

---

## 🚀 Panduan Instalasi & Menjalankan

### Langkah 1: Kloning Repositori
Buka terminal / Command Prompt, lalu jalankan:
```bash
git clone https://github.com/dexccv/gemini-cli.git
cd gemini-cli
```

### Langkah 2: Menjalankan Aplikasi

#### Cara 1: Menggunakan Script Otomatis (Direkomendasikan)
Script launcher akan otomatis membuat virtual environment `.venv`, menginstal seluruh dependensi yang dibutuhkan, dan menjalankan aplikasi:

* **Pengguna Windows**:
  ```cmd
  run.bat
  ```
* **Pengguna Linux / macOS**:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```

#### Cara 2: Instalasi Manual
Jika Anda ingin menyiapkan lingkungan secara manual:
```bash
# 1. Buat virtual environment
python -m venv .venv

# 2. Aktifkan virtual environment
# Di Windows:
.venv\Scripts\activate
# Di Linux / macOS:
source .venv/bin/activate

# 3. Pasang paket dependensi
pip install -r requirements.txt

# 4. Jalankan Terminal Agent
python app.py
```

---

## ⚡ Panduan Setup Groq AI (Rekomendasi)

Groq LPU memberikan kecepatan generasi respons luar biasa (~0.5 detik) dengan kuota harian gratis hingga 14.400 request/hari.

1. Buka [console.groq.com/keys](https://console.groq.com/keys) lalu buat API Key gratis Anda.
2. Tambahkan API Key ke berkas `~/.gemini-agent/.env`:
   ```env
   AI_PROVIDER=groq
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
   GROQ_MODEL=openai/gpt-oss-120b
   ```
3. Atau cukup ganti langsung dari Telegram bot:
   ```text
   /provider groq gsk_xxxxxxxxxxxxxxxxxxxx
   ```

---

## 📲 Panduan Setup Telegram Mobile Gateway

Telegram Mobile Gateway memungkinkan Anda mengendalikan laptop dari jarak jauh melalui chat bot Telegram.

### 1. Buat Bot Telegram Sendiri
1. Buka aplikasi Telegram, cari akun **`@BotFather`**.
2. Kirim perintah `/newbot`.
3. Masukkan nama tampilan dan username bot (contoh: *asisten_laptop_pribadi_bot*).
4. **Simpan Token Bot**: Simpan token yang diberikan (contoh: `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### 2. Dapatkan User ID Telegram Anda
Untuk memastikan hanya Anda yang bisa mengendalikan laptop:
1. Di Telegram, cari akun **`@userinfobot`** atau **`@raw_data_bot`**.
2. Kirim pesan `/start`.
3. Catat `Id` angka Anda (contoh: `987654321`).

### 3. Masukkan Konfigurasi ke Berkas `.env`
Buka berkas konfigurasi di folder pengguna Anda (`~/.gemini-agent/.env`):
```env
TELEGRAM_BOT_TOKEN=masukkan_token_botfather_di_sini
TELEGRAM_ALLOWED_USER_ID=masukkan_user_id_angka_anda_di_sini
```

### 4. Jalankan Bot
* **Otomatis**: Setiap kali Anda menjalankan `app.py` atau `run.bat`, bot Telegram otomatis menyala di background.
* **Dedicated Launcher**: Jika Anda hanya ingin menjalankan bot Telegram tanpa antarmuka TUI:
  ```cmd
  run_bot.bat
  # atau
  python bot_telegram.py
  ```

Buka bot Anda di Telegram, lalu ketik `/start`. Menu interaktif dan seluruh tombol kendali laptop akan langsung aktif!

---

## 🦙 Panduan Setup Local AI (Ollama) [Opsional]

Jika Anda ingin menjalankan agen secara offline di laptop Anda:

1. Unduh dan instal Ollama dari [ollama.com](https://ollama.com).
2. Tentukan lokasi model di Drive D (opsional, hemat kapasitas Drive C):
   ```cmd
   setx OLLAMA_MODELS "D:\.ollama\models"
   ```
3. Unduh model yang diinginkan:
   ```bash
   ollama pull qwen2.5-coder:7b
   ```
4. Ganti provider di bot Telegram atau TUI:
   * Ketik `/provider ollama`
   * Ganti model dengan `/model qwen2.5-coder:7b`

---

## 📋 Daftar Perintah Telegram Bot

| Perintah | Deskripsi |
| :--- | :--- |
| `/status` | Menampilkan dashboard monitoring laptop real-time (baterai, Wi-Fi, jendela aktif, RAM, CPU). |
| `/cari <aplikasi> <kata_kunci>` | Cari lagu/video di YouTube, Google, Spotify (contoh: `/cari youtube the jansen`). |
| `/buka` | Membuka tombol pintasan Peluncur Aplikasi desktop (Chrome, Spotify, VS Code, Notepad, dll). |
| `/buka <nama>` | Membuka aplikasi desktop atau link URL tertentu di laptop (contoh: `/buka chrome` atau `/buka notepad`). |
| `/tabs` / `/tab` | Memantau seluruh tab/jendela browser (Chrome/Edge) aktif, fokuskan tab, atau tutup tab dari HP. |
| `/get` | Membuka Penjelajah Berkas (File Picker) interaktif untuk mengunduh dokumen laptop ke HP. |
| `/get <path>` | Mengunduh berkas tertentu langsung ke HP (bisa berkas di dalam maupun di luar project). |
| `/volume` | Membuka panel kontrol volume laptop & tombol kendali musik (Play/Pause, Next, Prev). |
| `/play` / `/pause` | Memutar atau menjeda lagu/video di YouTube atau Spotify (`F10`). |
| `/next` / `/prev` | Memutar lagu berikutnya (`F11`) atau lagu sebelumnya (`F9`). |
| `/mute` / `/unmute` | Mematikan atau menghidupkan kembali suara speaker laptop secara instan. |
| `/capture` / `/ss` | Mengambil screenshot layar laptop resolusi penuh dan mengirimkan fotonya ke Telegram. |
| `/kamera` | Mengambil foto live dari webcam laptop dan mengirimkannya ke chat. |
| `/tutup <nama>` | Menutup aplikasi desktop tertentu yang sedang berjalan di laptop (contoh: `/tutup chrome`). |
| `/speed` | Menguji latensi respons model AI dan kecepatan kirim jaringan Telegram. |
| `/baca <file>` | Membaca isi berkas teks lokal laptop langsung di Telegram. |
| `/provider [nama]` | Melihat atau beralih provider aktif (`groq`, `gemini`, `ollama`, `omniroute`). |
| `/models` / `/model` | Memindai dan mengganti model AI yang aktif digunakan. |
| `/new` / `/sessions` | Memulai sesi percakapan baru atau beralih sesi percakapan lama. |
| `/memory` | Melihat catatan memori jangka panjang persisten agen. |
| `/stop` | Membatalkan eksekusi jawaban agen yang sedang berjalan. |

---

## ⌨️ Daftar Pintasan Keyboard Terminal TUI

| Tombol Pintasan | Fungsi |
| :--- | :--- |
| `Enter` | Mengirim pesan prompt ke agen |
| `Ctrl + X` / `Escape` | Menghentikan respon agen seketika (*Interrupt*) |
| `Ctrl + S` | Membuka dialog manajemen & pemulihan sesi percakapan |
| `Ctrl + M` | Membuka dialog pemilihan & pemindaian model AI |
| `Ctrl + T` | Beralih tema warna antarmuka TUI |
| `Ctrl + R` | Memulai ulang aplikasi terminal (*Restart*) |
| `Ctrl + L` | Membersihkan riwayat obrolan di layar |
| `Ctrl + C` | Keluar dari aplikasi terminal |

---

## ⚙️ Konfigurasi Lengkap (.env)

Seluruh konfigurasi tersimpan rapi di berkas `~/.gemini-agent/.env`:

```env
# Provider AI aktif: groq / gemini / ollama / omniroute
AI_PROVIDER=groq

# Pengaturan Groq Cloud LPU (Rekomendasi Utama)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=openai/gpt-oss-120b

# Pengaturan Google Gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash

# Pengaturan Ollama Lokal (Opsional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_MODELS=D:\.ollama\models

# Pengaturan Omniroute (Opsional)
OMNI_BASE_URL=http://localhost:20128/v1
OMNI_API_KEY=sk-...
OMNI_MODEL=auto

# Pengaturan Telegram Mobile Gateway
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_ALLOWED_USER_ID=987654321

# Pengaturan Tampilan & Debug
GEMINI_THEME=default
GEMINI_AGENT_DEBUG=0
```

---

## 🛡️ Keamanan & Privasi

- **Whitelist User ID Ketat**: Gateway Telegram hanya menerima dan mengeksekusi instruksi dari ID Telegram pemilik sah (`TELEGRAM_ALLOWED_USER_ID`). Pesan dari akun lain otomatis ditolak.
- **Proteksi Sandbox Workspace**: Operasi berkas AI secara default dibatasi di direktori kerja proyek guna mencegah modifikasi tak disengaja pada berkas sistem operasi.
- **Filter Perintah Berbahaya**: Agen dilengkapi proteksi filter blacklist untuk memblokir perintah shell destruktif seperti format disk, penghapusan root paksa, atau shutdown liar.
- **Privasi Kredensial**: Seluruh API key dan token tersimpan lokal di mesin Anda dan tidak pernah dipublikasikan ke repositori Git.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi [MIT](LICENSE).
