# TeleAgent 🤖📱

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Indonesiaku--Lang](https://img.shields.io/badge/Language-Indonesiaku--Lang-FF0000?style=flat-square)](https://github.com/teguh02/Indonesiaku-Lang)
[![Telegram Gateway](https://img.shields.io/badge/Telegram-Remote%20Control-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org)
[![Google GenAI](https://img.shields.io/badge/Google-GenAI%20SDK-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq Cloud LPU](https://img.shields.io/badge/Groq-Ultra--Fast%20LPU-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**TeleAgent** adalah asisten AI otonom workstation dan terminal cerdas yang menghubungkan laptop Anda secara langsung ke **Telegram di smartphone**. 

Dikembangkan dengan Python dan bahasa pemrograman **Indonesiaku-Lang** (`.idk`), TeleAgent memungkinkan Anda memantau status perangkat, menjalankan instruksi terminal, mengendalikan media & tab browser, hingga menyetujui perubahan kode Antigravity IDE dari mana saja melalui genggaman tangan.

---

## ⚡ Quick Start: Setup 3 Menit (Zero-Friction Setup)

Tidak perlu bingung mencari Telegram User ID secara manual atau mengedit file `.env` yang rumit! Cukup jalankan wizard otomatis satu-klik:

```cmd
setup.bat
```

Atau via command line Python:
```bash
python setup_teleagent.py
```

### Apa yang dilakukan Setup Wizard?
1. **Otomatisasi Virtual Environment**: Membuat dan mengaktifkan `.venv` serta menginstal pustaka yang dibutuhkan secara otomatis.
2. **Validasi Bot Token Telegram**: Menguji koneksi token ke Telegram Bot API (`getMe`) secara langsung.
3. **Auto-Detect Telegram User ID**: Anda cukup mengirim pesan apa saja ke bot Telegram Anda dari HP; wizard akan mendeteksi akun Anda secara instan dan mengunci akses (*Strict Whitelist*).
4. **Validasi API Key AI**: Memverifikasi Gemini API Key atau Groq API Key secara langsung sebelum menyimpannya ke `.env`.

---

## 📑 Daftar Isi
1. [Fitur Unggulan](#-fitur-unggulan)
2. [Antigravity IDE Live Bridge](#-antigravity-ide-live-bridge)
3. [Perbandingan Multi-Provider AI](#-perbandingan-multi-provider-ai)
4. [Daftar Perintah Telegram Bot](#-daftar-perintah-telegram-bot)
5. [Daftar Perkakas Otonom (Tools)](#-daftar-perkakas-otonom-tools)
6. [Struktur Berkas Repositori](#-struktur-berkas-repositori)
7. [Panduan Menjalankan](#-panduan-menjalankan)
8. [Keamanan & Privasi](#-keamanan--privasi)

---

## 🌟 Fitur Unggulan

| Kategori Fitur | Deskripsi Fungsional | Cara Penggunaan / Akses |
| :--- | :--- | :--- |
| **Interactive Setup Wizard** | Konfigurasi awal interaktif dengan auto-detect ID Telegram dan validasi kunci API instan. | `setup.bat` atau `python setup_teleagent.py` |
| **Antigravity IDE Remote Control** | Deteksi jendela Antigravity IDE, inspeksi proposal diff file, dan klik tombol *Accept All* / *Reject All* dari Telegram. | `/agy status`, `/agy diff`, `/agy accept`, `/agy reject` |
| **Pencegahan Limit Token (Anti-413)** | Pemotongan cerdas (*Smart Truncation*) otomatis maksimal 1.500 karakter untuk output terminal besar sehingga bebas galat TPM. | Otomatis di seluruh provider |
| **Remote Clipboard Sync** | Sinkronisasi papan klip dua arah antara smartphone dan laptop. Baca clipboard laptop dari HP atau kirim teks ke clipboard laptop. | Perintah `/clip` dan `/copy <teks>` |
| **Kunci Layar Workstation Cepat** | Kunci layar laptop seketika saat ditinggal keluar via Telegram atau shortcut hardware keyboard. | `/lock`, `/kunci`, atau **Ctrl + L** |
| **Kontrol Audio & Pemutar Musik** | Atur volume master speaker Windows (0-100%, +/-10%, Mute/Unmute) serta simulasi kontrol media (*Play/Pause*, *Next*, *Prev*). | `/volume`, `/play`, `/next`, `/prev` |
| **Pencarian & Pemutaran YouTube** | Cari video YouTube secara real-time dan putar otomatis di browser Chrome. | `/cari youtube <judul_lagu>` |
| **Inspeksi Tab Browser** | Pindai seluruh tab/jendela Google Chrome & Edge yang aktif, bawa tab ke layar depan (*focus*), atau tutup tab dari HP. | `/tabs` atau `/tab` |
| **Peluncur Aplikasi Desktop** | Buka aplikasi desktop Windows (Chrome, Spotify, VS Code, Notepad, File Explorer, Terminal) dengan tombol hub interaktif. | `/buka` atau `/buka <nama_app>` |
| **Tangkapan Layar & Kamera Webcam** | Ambil tangkapan layar resolusi display laptop atau ambil foto live dari webcam laptop dan kirimkan langsung ke Telegram. | `/capture`, `/ss`, atau `/kamera` |
| **Monitoring Sistem Real-Time** | Pantau status baterai & charger, Wi-Fi (SSID & sinyal), jendela fokus aktif di layar, serta beban CPU & RAM. | `/status` atau `/laptop` |
| **Keamanan Whitelist & Mutex Lock** | Gateway Telegram dikunci privat hanya untuk ID pemilik sah dengan proteksi `asyncio.Lock` anti race-condition. | Otomatis via whitelist ID |

---

## 🚀 Antigravity IDE Live Bridge

TeleAgent dilengkapi integrasi mendalam ke **Antigravity IDE** melalui jembatan Win32 API (`antigravity_bridge.py`):
- **Live Sync Model IDE**: TeleAgent mendeteksi model aktif yang sedang Anda pilih di Antigravity IDE (misal Gemini Flash Medium / Gemini Pro High) secara realtime via protobuf state.
- **Remote Code Review**: Saat Antigravity mengajukan modifikasi berkas, Anda dapat membaca daftar berkas yang diubah via `/agy diff` dari Telegram.
- **One-Tap Accept All**: Setujui seluruh perubahan kode langsung dari HP Anda dengan `/agy accept`, bot akan mengaktifkan jendela IDE dan mengeksekusi konfirmasi perubahan secara otomatis.

---

## 🤖 Perbandingan Multi-Provider AI

Aplikasi mendukung perpindahan provider AI secara dinamis melalui perintah `/provider <nama>` di antarmuka TUI maupun chat Telegram:

| Provider | Backend Mesin | Latensi Rata-rata | Keunggulan & Karakteristik |
| :--- | :--- | :---: | :--- |
| **Groq LPU** ⚡ *(Rekomendasi)* | Groq Cloud LPU | **~0.3s - 0.8s** | Model `openai/gpt-oss-120b` (120B reasoning) & `openai/gpt-oss-20b`, kuota gratis 14.400 req/hari, ultra-fast streaming. |
| **Google Gemini** | Google GenAI SDK | **~1.5s - 3.0s** | Model resmi Google (`gemini-2.5-flash`, `gemini-3-flash-preview`), penalaran multimodal dan kontekstual. |
| **Ollama Local** | Local Offline Engine | Hardware-dependent | 100% offline, hemat kuota, bebas privasi, auto-start daemon, model di `D:\.ollama\models`. |
| **Omniroute** | OpenAI-Compatible Proxy | Bervariasi | Integrasi upstream model kustom atau server inferensi lokal privat. |

---

## 📱 Daftar Perintah Telegram Bot

| Perintah Bot | Parameter | Deskripsi & Contoh Penggunaan |
| :--- | :--- | :--- |
| `/status` | *(tanpa argumen)* | Dashboard monitoring real-time laptop (Baterai, Wi-Fi, Window aktif, RAM, CPU). |
| `/agy` | `[status/diff/accept/reject]` | Manajemen integrasi remote Google Antigravity IDE. |
| `/clip` | *(tanpa argumen)* | Membaca isi clipboard laptop saat ini dari HP. |
| `/copy` | `<teks>` | Menyalin teks dari pesan Telegram langsung masuk ke clipboard laptop Windows. |
| `/lock` / `/kunci` | *(tanpa argumen)* | Mengunci workstation laptop Windows seketika (Lock Screen). |
| `/cari` | `<app> <query>` | Mencari konten di YouTube, Google, atau Spotify. Contoh: `/cari youtube the jansen`. |
| `/buka` | `[nama_aplikasi]` | Membuka menu peluncur aplikasi interaktif atau langsung membuka aplikasi. |
| `/tabs` | *(tanpa argumen)* | Menampilkan seluruh jendela/tab browser yang sedang terbuka di laptop. |
| `/volume` | `[level / mute]` | Membuka panel tombol volume laptop (contoh: `/volume 50`, `/volume mute`, `/volume +10`). |
| `/play` / `/pause` | *(tanpa argumen)* | Memutar atau menjeda pemutar lagu/video di YouTube atau Spotify laptop. |
| `/next` / `/prev` | *(tanpa argumen)* | Memutar lagu berikutnya atau lagu sebelumnya. |
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

## 🛠️ Daftar Perkakas Otonom (Tools)

Seluruh perkakas berikut dipanggil secara otomatis oleh AI Agent saat Anda memberikan perintah percakapan:

| Nama Perkakas | Deskripsi Fungsionalitas | Parameter Input |
| :--- | :--- | :--- |
| `antigravity_bridge` | Deteksi jendela IDE, pembacaan diff proposal kode, dan aksi Accept/Reject All. | `action: str, target: str` |
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

## 📦 Struktur Berkas Repositori

| Nama Berkas / Modul | Tipe Bahasa | Peran & Deskripsi Fungsional |
| :--- | :---: | :--- |
| `setup_teleagent.py` | Python 3 | Wizard konfigurasi interaktif dengan auto-detect ID Telegram & validasi token. |
| `setup.bat` | Batch Script | Launcher satu-klik untuk setup otomatis environment & wizard konfigurasi. |
| `bot_telegram.py` | Python 3 | Gateway Telegram remote control bot dengan proteksi whitelist dan async lock. |
| `antigravity_bridge.py`| Python 3 | Jembatan kontrol & deteksi jendela Antigravity IDE (Win32 API). |
| `agen.idk` / `agent.py` | Indonesiaku / Python | Logika inti AI Agent, loop tool calling multi-provider, dan context management. |
| `perkakas.idk` / `tools.py` | Indonesiaku / Python | Kumpulan perkakas sistem (Volume Win32, Webcam CV2, Screen Pillow, App Launcher). |
| `penerjemah_idk.py` | Python 3 | Transpiler dan runtime import hook untuk Bahasa Pemrograman Indonesiaku. |
| `aplikasi.idk` / `app_legacy.py` | Indonesiaku / Python | Antarmuka grafis terminal TUI berbasis framework Textual & Rich. |
| `konfigurasi.idk` / `config.py` | Indonesiaku / Python | Pengelola konfigurasi kredensial `.env` di direktori `~/.gemini-agent/.env`. |
| `pengelola_sesi.idk` | Indonesiaku | Penyimpanan riwayat obrolan persisten multi-turn dengan penulisan atomik. |
| `memori.idk` | Indonesiaku | Penyimpanan memori jangka panjang persisten pengguna lintas sesi. |
| `run_bot.bat` | Batch Script | Skrip peluncur cepat background daemon Telegram bot. |
| `run.bat` | Batch Script | Skrip peluncur cepat antarmuka Terminal TUI interaktif (dengan First-Run Guard). |

---

## 🚀 Panduan Menjalankan

### Menjalankan Gateway Telegram (Remote Control Smartphone)
```bash
run_bot.bat
# atau
python bot_telegram.py
```

### Menjalankan Antarmuka Terminal TUI
```bash
run.bat
# atau
python app.py
```

---

## 🛡️ Keamanan & Privasi

| Mekanisme Keamanan | Implementasi & Manfaat |
| :--- | :--- |
| **Strict Whitelist Lock** | Gateway Telegram hanya menerima perintah dari ID pemilik sah (`TELEGRAM_ALLOWED_USER_ID`). Jika whitelist belum disetel, seluruh akses dikunci total. |
| **Async Mutex Session Lock** | Mencegah *race condition* antar thread saat pengguna mengirim beberapa instruksi secara cepat. |
| **Smart Token Truncation** | Memotong output perintah terminal berukuran besar maksimal 1.500 karakter untuk mencegah galat limit token model AI. |
| **Sandbox Workspace Boundary** | Operasi berkas AI dibatasi di lingkungan proyek dan direktori aman pengguna, melindungi berkas sistem Windows inti. |
| **Penyimpanan Kredensial Terisolasi** | Seluruh API key dan token bot tersimpan di direktori lokal pengguna (`~/.gemini-agent/.env`) dan tidak pernah masuk ke version control Git. |

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi resmi [MIT License](LICENSE).
