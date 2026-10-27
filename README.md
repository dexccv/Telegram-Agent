# Gemini Terminal Agent

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Indonesiaku--Lang](https://img.shields.io/badge/Language-Indonesiaku--Lang-FF0000?style=flat-square)](https://github.com/teguh02/Indonesiaku-Lang)
[![Groq Cloud LPU](https://img.shields.io/badge/Groq-Ultra--Fast%20LPU-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![Google GenAI](https://img.shields.io/badge/Google-GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Telegram Gateway](https://img.shields.io/badge/Telegram-Remote%20Control-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Gemini Terminal Agent** adalah asisten AI otonom workstation dan terminal cerdas yang dibangun menggunakan Python dan bahasa pemrograman **Indonesiaku-Lang** (`.idk`).

Dilengkapi antarmuka visual **Textual TUI**, dukungan **Multi-Provider AI** (*Groq Cloud LPU*, *Google Gemini*, *Local Ollama*, dan *Omniroute*), kemampuan eksekusi perkakas otonom (*Autonomous Function Calling*) untuk kontrol sistem laptop, serta **Telegram Mobile Gateway** yang memungkinkan Anda mengendalikan seluruh fungsi laptop dari smartphone kapan pun dan di mana pun.

---

## 📑 Daftar Isi
1. [Ringkasan Fitur Unggulan](#-ringkasan-fitur-unggulan)
2. [Perbandingan Multi-Provider AI](#-perbandingan-multi-provider-ai)
3. [Daftar Lengkap Perintah Telegram Bot](#-daftar-lengkap-perintah-telegram-bot)
4. [Daftar Perkakas Sistem (Autonomous Tools)](#-daftar-perkakas-sistem-autonomous-tools)
5. [Daftar Pintasan Keyboard & Hotkey Global](#-daftar-pintasan-keyboard--hotkey-global)
6. [Bahasa Pemrograman: Indonesiaku-Lang](#-bahasa-pemrograman-indonesiaku-lang-idk)
7. [Struktur Berkas Repositori](#-struktur-berkas-repositori)
8. [Panduan Instalasi & Menjalankan](#-panduan-instalasi--menjalankan)
9. [Panduan Konfigurasi (.env)](#-panduan-konfigurasi-env)
10. [Keamanan & Privasi](#-keamanan--privasi)

---

## 🌟 Ringkasan Fitur Unggulan

Berikut adalah rangkuman kapabilitas utama Gemini Terminal Agent yang disajikan dalam bentuk tabel ringkas:

| Kategori Fitur | Deskripsi Fungsional | Cara Penggunaan / Akses |
| :--- | :--- | :--- |
| **Pencegahan Limit Token (Anti-413)** | Pemotongan cerdas (*Smart Truncation*) otomatis maksimal 1.500 karakter untuk output terminal besar (`tasklist`, `dir /s`, dll.) sehingga bebas dari galat HTTP 413 TPM limit Groq. | Otomatis di seluruh provider |
| **Remote Clipboard Sync** | Sinkronisasi papan klip instan dua arah antara smartphone dan laptop. Baca clipboard laptop dari HP atau kirim teks dari HP langsung ke clipboard laptop siap di-paste. | Perintah `/clip` dan `/copy <teks>` |
| **Kunci Layar Workstation Cepat** | Kunci layar laptop seketika saat ditinggal keluar via Telegram atau dengan shortcut global hardware keyboard. | `/lock`, `/kunci`, atau **Ctrl + L** |
| **Kontrol Audio & Pemutar Musik** | Atur volume master speaker Windows (0-100%, +/-10%, Mute/Unmute) serta simulasi tombol keyboard media (*Play/Pause*, *Next*, *Prev*, *Stop*). | `/volume`, `/play`, `/next`, `/prev` |
| **Pencarian & Pemutaran YouTube** | Cari video YouTube secara real-time, dapatkan daftar hasil teratas beserta tautan dan durasi, lalu putar otomatis di browser Chrome. | `/cari youtube <judul_lagu>` |
| **Inspeksi & Kontrol Tab Browser** | Pindai seluruh tab/jendela Google Chrome & Edge yang aktif, bawa tab ke layar depan (*focus*), atau tutup tab dari HP. | `/tabs` atau `/tab` |
| **Peluncur Aplikasi Desktop** | Buka aplikasi desktop Windows (Chrome, Spotify, VS Code, Notepad, File Explorer, Terminal, Kalkulator) dengan tombol hub interaktif. | `/buka` atau `/buka <nama_app>` |
| **Tangkapan Layar & Kamera Webcam** | Ambil tangkapan layar resolusi penuh display laptop atau ambil foto live dari webcam laptop dan kirimkan langsung ke chat Telegram. | `/capture`, `/ss`, atau `/kamera` |
| **Penjelajah Berkas & Pembuat PDF** | Jelajahi direktori laptop dan unduh berkas apa pun langsung ke HP, atau minta AI membuat berkas PDF dokumen profesional. | `/get`, `/baca`, atau via chat AI |
| **Monitoring Sistem Real-Time** | Pantau status baterai & charger, koneksi Wi-Fi (SSID, sinyal, IP), jendela fokus aktif di layar, serta beban CPU dan pemakaian RAM. | `/status` atau `/laptop` |
| **Keamanan Whitelist & Mutex Lock** | Gateway Telegram dikunci privat hanya untuk pemilik sah laptop dengan proteksi `asyncio.Lock` agar bebas dari *race condition*. | Otomatis via whitelist ID |

---

## 🤖 Perbandingan Multi-Provider AI

Aplikasi mendukung perpindahan provider AI secara dinamis melalui perintah `/provider <nama>` di antarmuka TUI maupun chat Telegram:

| Provider | Backend Mesin | Latensi Rata-rata | Keunggulan & Karakteristik |
| :--- | :--- | :---: | :--- |
| **Groq LPU** ⚡ *(Rekomendasi)* | Groq Cloud LPU | **~0.3s - 0.8s** | Model `openai/gpt-oss-120b` (120B reasoning) & `openai/gpt-oss-20b`, kuota gratis 14.400 req/hari, ultra-fast token streaming. |
| **Google Gemini** | Google GenAI SDK | **~1.5s - 3.0s** | Model resmi Google (`gemini-2.5-flash`, `gemini-3-flash-preview`), penalaran multimodal kaya konteks. |
| **Ollama Local** | Local Offline Engine | Hardware-dependent | 100% offline, hemat kuota internet, bebas privasi, auto-start daemon, model tersimpan di `D:\.ollama\models`. |
| **Omniroute** | OpenAI-Compatible Proxy | Bervariasi | Mendukung integrasi upstream model kustom atau server inferensi lokal privat. |

---

## 📱 Daftar Lengkap Perintah Telegram Bot

Berikut adalah daftar perintah interaktif yang dapat Anda gunakan di bot Telegram:

| Perintah Bot | Parameter | Deskripsi & Contoh Penggunaan |
| :--- | :--- | :--- |
| `/status` | *(tanpa argumen)* | Dashboard monitoring real-time laptop (Baterai, Wi-Fi, Window aktif, RAM, CPU). |
| `/clip` | *(tanpa argumen)* | Mengambil dan membaca teks yang sedang ada di clipboard laptop saat ini. |
| `/copy` | `<teks>` | Menyalin teks dari pesan Telegram langsung masuk ke clipboard laptop Windows (**Ctrl + V**). |
| `/lock` / `/kunci` | *(tanpa argumen)* | Mengunci workstation laptop Windows seketika (Lock Screen). |
| `/cari` | `<app> <query>` | Mencari konten di YouTube, Google, atau Spotify. Contoh: `/cari youtube the jansen`. |
| `/buka` | `[nama_aplikasi]` | Membuka menu peluncur aplikasi interaktif atau langsung membuka aplikasi (contoh: `/buka chrome`). |
| `/tabs` | *(tanpa argumen)* | Menampilkan seluruh jendela/tab browser yang sedang terbuka di laptop. |
| `/volume` | `[level / mute]` | Membuka panel tombol volume laptop (contoh: `/volume 50`, `/volume mute`, `/volume +10`). |
| `/play` / `/pause` | *(tanpa argumen)* | Memutar atau menjeda pemutar lagu/video di YouTube atau Spotify laptop (`F10`). |
| `/next` / `/prev` | *(tanpa argumen)* | Memutar lagu berikutnya (`F11`) atau lagu sebelumnya (`F9`). |
| `/mute` / `/unmute` | *(tanpa argumen)* | Mematikan atau menyalakan suara speaker laptop secara instan. |
| `/capture` / `/ss` | *(tanpa argumen)* | Mengambil screenshot display laptop dan mengirimkan fotonya ke Telegram. |
| `/kamera` | *(tanpa argumen)* | Mengambil foto live dari kamera webcam laptop dan mengirimkannya ke chat. |
| `/tutup` | `<nama_app>` | Menutup aplikasi desktop tertentu yang sedang berjalan (contoh: `/tutup notepad`). |
| `/get` | `[nama_berkas]` | Membuka File Picker interaktif atau mengunduh berkas tertentu dari laptop ke HP. |
| `/baca` | `<nama_berkas>` | Membaca isi teks berkas lokal di laptop secara langsung. |
| `/speed` | *(tanpa argumen)* | Uji kecepatan respons AI dan roundtrip transmisi Telegram. |
| `/provider` | `[nama_provider]` | Melihat atau beralih provider aktif (`groq`, `gemini`, `ollama`, `omniroute`). |
| `/models` / `/model` | `[nama_model]` | Memindai daftar model AI yang tersedia atau mengganti model aktif. |
| `/new` | `[judul_sesi]` | Memulai sesi percakapan baru dengan riwayat bersih. |
| `/sessions` | *(tanpa argumen)* | Menampilkan daftar riwayat sesi percakapan yang tersimpan di laptop. |
| `/load` | `<nomor_atau_id>` | Beralih ke sesi percakapan tertentu berdasarkan nomor atau ID sesi. |
| `/memory` | *(tanpa argumen)* | Melihat seluruh catatan memori jangka panjang persisten pengguna. |
| `/help` | *(tanpa argumen)* | Menampilkan panduan lengkap fitur dan petunjuk penggunaan. |

---

## 🛠️ Daftar Perkakas Sistem (Autonomous Tools)

Seluruh perkakas berikut dipanggil secara otomatis oleh AI Agent saat Anda memberikan perintah dalam bahasa sehari-hari:

| Nama Fungsi Perkakas | Deskripsi Fungsionalitas | Parameter Input |
| :--- | :--- | :--- |
| `set_volume` | Mengatur volume suara speaker master laptop atau status mute. | `level: str` |
| `media_control` | Menekan tombol keyboard multimedia (Play/Pause, Next, Prev, Stop). | `action: str` |
| `lock_laptop` | Mengunci workstation layar Windows seketika (`LockWorkStation`). | *(tanpa parameter)* |
| `open_application` | Membuka aplikasi desktop (Chrome, Spotify, dll) atau URL web di laptop. | `app_or_query: str, query: str` |
| `close_application` | Menutup atau menghentikan proses aplikasi desktop yang sedang berjalan. | `app_name_or_pid: str` |
| `search_youtube_videos` | Mencari video di YouTube dan mengembalikan daftar judul, durasi, dan URL. | `query: str, limit: int` |
| `play_youtube_video` | Membuka browser Chrome dan memutar video YouTube secara otomatis. | `video_id_or_url: str` |
| `get_open_browser_tabs` | Memindai seluruh jendela & tab browser yang sedang berjalan di laptop. | *(tanpa parameter)* |
| `focus_window` | Membawa jendela aplikasi atau tab browser tertentu ke layar paling depan. | `hwnd: int` |
| `close_window_tab` | Menutup jendela atau tab tertentu berdasarkan ID handle HWND. | `hwnd: int` |
| `capture_screen` | Mengambil tangkapan layar (screenshot) display laptop beresolusi penuh. | `output_path: str` |
| `capture_camera` | Mengambil foto live dari kamera webcam laptop menggunakan OpenCV. | `output_path: str` |
| `create_pdf` | Membuat dokumen berkas PDF profesional dengan judul dan konten teks. | `output_path: str, title: str, content: str` |
| `send_file_to_user` | Menandai berkas lokal di laptop agar otomatis dikirim ke chat Telegram. | `file_path: str` |
| `get_system_status` | Membaca metrik CPU, pemakaian RAM, sisa baterai, dan kapasitas disk drive. | *(tanpa parameter)* |
| `run_command` | Menjalankan perintah terminal/shell secara aman dengan filter keamanan. | `command: str` |
| `create_folder` | Membuat direktori/folder baru pada sistem penyimpanan file laptop. | `path: str` |
| `list_files` | Mendaftar seluruh berkas dan folder di dalam suatu direktori kerja. | `path: str` |
| `read_file` | Membaca isi teks berkas lokal pada sistem laptop. | `path: str` |
| `write_file` | Menulis teks ke berkas baru atau menimpa berkas yang ada. | `path: str, content: str` |
| `save_memory` | Menyimpan preferensi pengguna ke memori jangka panjang persisten. | `key: str, value: str` |

---

## ⌨️ Daftar Pintasan Keyboard & Hotkey Global

| Pintasan Keyboard | Cakupan Lingkup | Fungsi Teknis |
| :--- | :--- | :--- |
| **Ctrl + L** | **Global Windows (OS-Wide)** | Mengunci workstation laptop Windows seketika dan mengirim notifikasi instan ke Telegram Anda. |
| **Enter** | Terminal TUI | Mengirim pesan instruksi prompt ke AI Agent. |
| **Ctrl + X** / **Escape** | Terminal TUI | Menghentikan respon agen atau eksekusi perkakas seketika (*Interrupt*). |
| **Ctrl + S** | Terminal TUI | Membuka dialog pemulihan dan manajemen sesi percakapan. |
| **Ctrl + M** | Terminal TUI | Membuka dialog pemilihan & pemindaian model AI. |
| **Ctrl + T** | Terminal TUI | Mengganti tema warna antarmuka TUI (Default, Emerald, Crimson, Amber, Purple). |
| **Ctrl + R** | Terminal TUI | Memulai ulang (*restart*) proses aplikasi terminal secara bersih. |
| **Ctrl + C** | Terminal / Launcher | Menutup aplikasi terminal atau daemon gateway Telegram. |

---

## 🇮🇩 Bahasa Pemrograman: Indonesiaku-Lang (.idk)

Seluruh logika inti agen, pengelola sesi, memori, perkakas, antarmuka visual TUI, dan konfigurasi ditulis menggunakan bahasa pemrograman **Indonesiaku-Lang** (`.idk`).

Transpilasi dieksekusi secara *on-the-fly* oleh engine [penerjemah_idk.py](file:///d:/PROJECT/gemini-terminal-agent/penerjemah_idk.py) via `sys.meta_path` import hook yang menerjemahkan sintaks Bahasa Indonesia ke Python AST saat runtime tanpa jeda kompilasi manual.

```idk
# Contoh cuplikan kode Indonesiaku-Lang (.idk)
fungsi apakah_siap_membantu(status) {
    jika status == "aktif" {
        cetak("Agen siap menjalankan instruksi Anda!")
        kembalikan benar
    } selain {
        kembalikan salah
    }
}
```

---

## 📦 Struktur Berkas Repositori

| Nama Berkas / Modul | Tipe Bahasa | Peran & Deskripsi Fungsional |
| :--- | :---: | :--- |
| `bot_telegram.py` | Python 3 | Gateway Telegram remote control bot dengan proteksi whitelist dan async lock. |
| `agen.idk` / `agent.py` | Indonesiaku / Python | Logika inti AI Agent, loop tool calling multi-provider, dan context management. |
| `perkakas.idk` / `tools.py` | Indonesiaku / Python | Kumpulan perkakas sistem (Volume Win32, Webcam CV2, Screen Pillow, App Launcher). |
| `penerjemah_idk.py` | Python 3 | Transpiler dan runtime import hook untuk Bahasa Pemrograman Indonesiaku. |
| `aplikasi.idk` / `app_legacy.py` | Indonesiaku / Python | Antarmuka grafis terminal TUI berbasis framework Textual & Rich. |
| `konfigurasi.idk` / `config.py` | Indonesiaku / Python | Pengelola konfigurasi kredensial `.env` di direktori `~/.gemini-agent/.env`. |
| `pengelola_sesi.idk` | Indonesiaku | Penyimpanan riwayat obrolan persisten multi-turn dengan penulisan atomik. |
| `memori.idk` | Indonesiaku | Penyimpanan memori jangka panjang persisten pengguna lintas sesi. |
| `requirements.txt` | Teks | Daftar spesifikasi pustaka dependensi runtime Python. |
| `run_bot.bat` / `run_bot.sh` | Shell Script | Skrip peluncur cepat dedicated background daemon Telegram bot. |
| `run.bat` / `run.sh` | Shell Script | Skrip peluncur cepat antarmuka Terminal TUI interaktif. |

---

## 🚀 Panduan Instalasi & Menjalankan

### 1. Kloning Repositori
```bash
git clone https://github.com/dexccv/gemini-cli.git
cd gemini-cli
```

### 2. Buat Virtual Environment & Instal Dependensi
```bash
python -m venv .venv
# Aktifkan di Windows:
.venv\Scripts\activate
# Instal pustaka lengkap:
pip install -r requirements.txt
```

### 3. Konfigurasi Kredensial (.env)
Buka atau buat berkas di direktori profil pengguna Anda (`~/.gemini-agent/.env`):
```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=openai/gpt-oss-120b
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_ALLOWED_USER_ID=987654321
```

> **Tips Cepat Mendapatkan Kredensial:**
> - **Groq API Key**: Buka [console.groq.com/keys](https://console.groq.com/keys) (Gratis kuota 14.400 request/hari).
> - **Telegram Bot Token**: Buat bot baru di Telegram melalui `@BotFather` via perintah `/newbot`.
> - **User ID Telegram**: Cari tahu ID akun angka Anda via `@userinfobot` di Telegram.

### 4. Menjalankan Aplikasi

* **Opsi A: Menjalankan Bot Telegram (Remote Control Smartphone)**:
  ```bash
  python bot_telegram.py
  # atau klik dua kali:
  run_bot.bat
  ```
* **Opsi B: Menjalankan Antarmuka Terminal TUI**:
  ```bash
  python app.py
  # atau klik dua kali:
  run.bat
  ```

---

## 🛡️ Keamanan & Privasi

| Mekanisme Keamanan | Implementasi & Manfaat |
| :--- | :--- |
| **Strict Whitelist Lock** | Gateway Telegram hanya menerima perintah dari ID pemilik sah (`TELEGRAM_ALLOWED_USER_ID`). Jika whitelist belum disetel, seluruh akses dikunci total. |
| **Async Mutex Session Lock** | Mencegah *race condition* antar thread saat pengguna mengirim beberapa instruksi secara cepat. |
| **Smart Token Truncation** | Memotong output perintah terminal berukuran besar maksimal 1.500 karakter untuk mencegah galat limit token model AI. |
| **Sandbox Workspace Boundary** | Operasi berkas AI dibatasi di lingkungan proyek dan direktori aman pengguna, melindungi berkas sistem Windows inti. |
| **Blacklist Perintah Berbahaya** | Filter pola perintah shell destruktif (format disk, shutdown liar, penghapusan root paksa). |
| **Penyimpanan Kredensial Terisolasi** | Seluruh API key dan token bot tersimpan di direktori lokal pengguna (`~/.gemini-agent/.env`) dan tidak pernah masuk ke version control Git. |

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi resmi [MIT License](LICENSE).
