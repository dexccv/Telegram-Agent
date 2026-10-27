# Gemini Terminal Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Indonesiaku--Lang](https://img.shields.io/badge/Language-Indonesiaku--Lang-FF0000?style=flat-square)](https://github.com/teguh02/Indonesiaku-Lang)
[![Telegram Gateway](https://img.shields.io/badge/Telegram-Remote%20Control-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org)
[![Google GenAI](https://img.shields.io/badge/Google-GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Gemini Terminal Agent** adalah aplikasi asisten AI terminal modern, cerdas, dan interaktif yang dibangun di atas Python dan bahasa pemrograman **Indonesiaku-Lang** (`.idk`). 

Dilengkapi dengan antarmuka visual **Textual TUI**, dukungan multi-provider AI (*Google Gemini*, *Local Ollama*, dan *Omniroute*), kemampuan eksekusi perkakas mandiri (*function calling*), serta **Telegram Mobile Gateway** yang memungkinkan Anda memantau status perangkat keras laptop, mengontrol musik, membuka aplikasi, hingga mengunduh berkas langsung dari handphone.

---

## 📑 Daftar Isi
1. [Fitur Utama](#-fitur-utama)
2. [Bahasa Pemrograman: Indonesiaku-Lang](#-bahasa-pemrograman-indonesiaku-lang-idk)
3. [Struktur Berkas](#-struktur-berkas)
4. [Persyaratan Sistem](#-persyaratan-sistem)
5. [Panduan Instalasi & Menjalankan](#-panduan-instalasi--menjalankan)
6. [Panduan Setup Telegram Mobile Gateway](#-panduan-setup-telegram-mobile-gateway)
7. [Panduan Setup Local AI (Ollama)](#-panduan-setup-local-ai-ollama-opsional)
8. [Daftar Perintah Telegram Bot](#-daftar-perintah-telegram-bot)
9. [Daftar Pintasan Keyboard Terminal TUI](#-daftar-pintasan-keyboard-terminal-tui)
10. [Konfigurasi Lengkap (.env)](#-konfigurasi-lengkap-env)
11. [Keamanan & Privasi](#-keamanan--privasi)

---

## 🌟 Fitur Utama

### 🖥️ Antarmuka Terminal (TUI) Modern
- **Desain Dark Mode Estetik**: Dibangun menggunakan [Textual](https://textual.textualize.io/) & [Rich](https://rich.readthedocs.io/) dengan animasi ketik (*typing effect*), *loading spinner*, serta beragam tema warna (`default`, `emerald`, `crimson`, `amber`, `purple`).
- **Interupsi Cepat (*Interrupt*)**: Batalkan proses generate model atau loop perkakas secara instan dengan menekan `Ctrl + X` / `Escape` atau tombol **Hentikan ⏹**.
- **Konteks Berkas Cepat**: Sisipkan isi berkas lokal ke prompt hanya dengan mengetik `@nama_berkas` (contoh: `@app.py`).

### 📱 Telegram Remote Gateway (Kendalikan Laptop dari HP)
- **Monitoring Real-Time (`/status`)**: Pantau daya baterai & charger, koneksi Wi-Fi (SSID, sinyal, IP), jendela aplikasi aktif di layar, beban CPU, pemakaian RAM, dan penyimpanan disk.
- **Pencarian YouTube & Media Cepat (`/cari <aplikasi> <keyword>`)**: Cari lagu/video apa pun (misal: `/cari youtube the jansen` atau `/cari spotify feast`), bot menyajikan daftar video teratas lengkap dengan tautan link langsung serta tombol interaktif untuk langsung memutar (*autoplay*) di laptop.
- **Peluncur Aplikasi Desktop (`/buka`)**: Menu tombol cepat untuk membuka Chrome, Spotify, VS Code, Notepad, File Explorer, Kalkulator, Terminal, atau Edge.
- **Inspeksi & Kontrol Tab Browser (`/tabs`)**: Memantau seluruh tab dan jendela browser (Chrome/Edge) yang sedang aktif di laptop, membawa tab tertentu ke depan layar (*focus*), memutar/jeda musik di tab, atau menutup tab dari HP.
- **Penjelajah Berkas & Pengunduh Dokumen (`/get`)**: Jelajahi folder laptop (Project, Downloads, Documents, Desktop, Drive C/D) dengan tombol inline dan unduh berkas apa pun langsung ke HP dalam satu ketukan.
- **Kontrol Volume & Pemutar Musik (`/volume`, `/play`, `/next`, `/prev`)**: Tombol volume (+/-10%, Mute/Unmute, 20-100%) dan kontrol lagu (Play/Pause `F10`, Next `F11`, Prev `F9`) yang disimulasikan langsung ke keyboard laptop.
- **Tangkapan Layar Display (`/capture`, `/ss`)**: Mengambil screenshot layar laptop resolusi penuh secara instan dan mengirimkannya langsung sebagai foto ke chat Telegram.
- **Tangkapan Kamera Webcam (`/kamera`)**: Ambil foto live dari webcam laptop dan kirimkan ke chat Telegram.
- **Manajemen Aplikasi (`/tutup`)**: Menutup aplikasi desktop yang sedang berjalan di laptop.
- **Uji Kecepatan & Latensi (`/speed`)**: Benchmark latency respon AI dan roundtrip pengiriman Telegram.

### 🧠 Multi-Turn Sesi & Memori Persisten
- Riwayat percakapan otomatis tersimpan di `~/.gemini-agent/sessions/`.
- Memori jangka panjang pengguna tersimpan di `~/.gemini-agent/memory.json` dan otomatis diinjeksi ke sistem instruksi.

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
- **Koneksi Internet**: Untuk akses API Google Gemini dan polling Telegram Bot.
- **Kunci API**: Google Gemini API Key (gratis di [Google AI Studio](https://aistudio.google.com/)) atau instalasi Ollama lokal.

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

### Langkah 3: Konfigurasi Pertama Kali (First-Run Wizard)
Saat pertama kali dijalankan, aplikasi akan menampilkan wizard interaktif:
1. **Input API Key**: Masukkan `GEMINI_API_KEY` Anda (karakter disamarkan untuk privasi).
2. **Pilih Model AI**: Aplikasi akan otomatis memindai model yang tersedia (misal `gemini-2.5-flash`).
3. Seluruh konfigurasi akan otomatis tersimpan rapi di direktori `~/.gemini-agent/.env` di komputer Anda.

---

## 📲 Panduan Setup Telegram Mobile Gateway

Telegram Mobile Gateway memungkinkan Anda mengendalikan laptop dari jarak jauh melalui chat bot Telegram.

### 1. Buat Bot Telegram Sendiri
1. Buka aplikasi Telegram di HP atau desktop, cari akun **`@BotFather`**.
2. Kirim perintah `/newbot`.
3. Masukkan nama tampilan bot Anda (contoh: *Asisten Laptop Saya*).
4. Masukkan username bot (harus berakhiran `bot`, contoh: *asisten_laptop_pribadi_bot*).
5. **Simpan Token Bot**: BotFather akan memberikan token API berupa kombinasi angka dan huruf (contoh: `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### 2. Dapatkan User ID Telegram Anda
Untuk memastikan hanya Anda yang bisa mengendalikan laptop:
1. Di Telegram, cari akun bot pencari ID seperti **`@userinfobot`** atau **`@raw_data_bot`**.
2. Kirim pesan `/start`.
3. Bot akan menampilkan `Id` angka Anda (contoh: `987654321`). Simpan nomor ini.

### 3. Masukkan Konfigurasi ke Berkas `.env`
Buka berkas konfigurasi di folder pengguna Anda:
* Windows: `C:\Users\<Nama_User>\.gemini-agent\.env`
* Linux / macOS: `~/.gemini-agent/.env`

Tambahkan atau sesuaikan baris berikut:
```env
TELEGRAM_BOT_TOKEN=masukkan_token_botfather_di_sini
TELEGRAM_ALLOWED_USER_ID=masukkan_user_id_angka_anda_di_sini
```

### 4. Jalankan Bot
* **Otomatis**: Setiap kali Anda menjalankan `app.py` atau `run.bat`, bot Telegram akan otomatis menyala di background.
* **Manual / Dedicated**: Jika Anda hanya ingin menjalankan bot Telegram tanpa membuka jendela TUI:
  ```cmd
  run_bot.bat
  # atau
  python bot_telegram.py
  ```

Buka bot Anda di Telegram, lalu ketik `/start`. Menu interaktif dan seluruh tombol kendali laptop akan langsung aktif!

---

## 🦙 Panduan Setup Local AI (Ollama) [Opsional]

Jika Anda ingin menjalankan agen secara offline atau menggunakan model open-source lokal di laptop Anda:

1. Unduh dan instal Ollama dari [ollama.com](https://ollama.com).
2. Unduh model yang diinginkan melalui terminal:
   ```bash
   ollama run qwen2.5-coder:7b
   ```
3. Buka Terminal Agent Anda, lalu ganti provider ke Ollama:
   * Ketik `/provider ollama` di TUI Terminal atau di Bot Telegram.
   * Model aktif dapat diganti dengan `/model <nama_model>` (contoh: `/model qwen2.5-coder:7b`).

---

## 📋 Daftar Perintah Telegram Bot

| Perintah | Deskripsi |
| :--- | :--- |
| `/status` | Menampilkan dashboard monitoring laptop real-time (baterai, Wi-Fi, jendela aktif, RAM, CPU). |
| `/cari <aplikasi> <kata_kunci>` | Cari lagu/video di YouTube, Google, Spotify (contoh: `/cari youtube the jansen` atau `/cari spotify feast`). |
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
| `/provider` | Melihat atau mengganti provider AI aktif (`gemini`, `ollama`, `omniroute`). |
| `/models` / `/model` | Memindai dan mengganti model AI yang aktif digunakan. |
| `/new` / `/sessions` | Memulai sesi percakapan baru atau beralih sesi percakapan lama. |

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

Seluruh konfigurasi tersimpan di berkas `~/.gemini-agent/.env`. Berikut adalah daftar variabel yang dapat Anda atur:

```env
# Provider AI aktif: gemini / ollama / omniroute
AI_PROVIDER=gemini

# Pengaturan Google Gemini
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash

# Pengaturan Ollama Lokal (Opsional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
# OLLAMA_MODELS=D:\.ollama\models

# Pengaturan Telegram Mobile Gateway
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_ALLOWED_USER_ID=987654321

# Pengaturan Tampilan & Debug
GEMINI_THEME=default
GEMINI_AGENT_DEBUG=0
```

---

## 🛡️ Keamanan & Privasi

- **Whitelist User ID Ketat**: Gateway Telegram hanya menerima dan menjalankan instruksi dari ID Telegram pemilik sah (`TELEGRAM_ALLOWED_USER_ID`). Pesan dari user lain otomatis ditolak.
- **Proteksi Sandbox Workspace**: Operasi berkas AI secara default dibatasi di direktori kerja proyek guna mencegah modifikasi tak disengaja pada sistem operasi.
- **Filter Perintah Berbahaya**: Agen dilengkapi filter blacklist untuk menolak perintah shell destruktif seperti format disk, penghapusan root paksa, atau shutdown liar.
- **Privasi Token**: Seluruh token API dan kredensial tersimpan lokal di mesin Anda dan tidak pernah dipublikasikan ke Git.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi [MIT](LICENSE).
