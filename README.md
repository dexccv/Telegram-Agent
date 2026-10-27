# gemini-terminal-agent

AI Agent terminal modern, berwarna, dan beranimasi yang dibangun di atas Python, Textual TUI, dan SDK resmi `google-genai`.

---

## ⌬ Gambaran Umum

`gemini-terminal-agent` menyediakan pengalaman interaksi agen AI langsung di terminal dengan antarmuka visual gelap, performa tinggi, dan eksekusi function calling otomatis untuk berinteraksi dengan berkas lokal dan shell sistem.

### Fitur Utama:
- **UI Terminal Beranimasi**: Dibangun dengan Textual dan Rich tanpa menggunakan emoji. Efek mengetik (typing effect 15ms/karakter), indikator spinner saat agen memproses, dan highlight saat transisi model.
- **Tombol & Pintasan Interupsi (Interrupt)**: Hentikan pemrosesan agen, pemanggilan tool loop, atau animasi respon secara instan menggunakan tombol **Hentikan ⏹**, tombol keyboard `Ctrl + X` / `Escape`, atau perintah slash `/stop`.
- **Manajemen Sesi & Pemulihan Percakapan**: Riwayat multi-turn dan eksekusi tool disimpan secara persisten di `~/.gemini-agent/sessions/`. Pengguna dapat beralih antar sesi, memulihkan sesi sebelumnya, atau membuat sesi baru (`Ctrl + S` atau `/session`).
- **Memori Jangka Panjang Persisten**: Menyimpan preferensi, instruksi, dan fakta pengguna di `~/.gemini-agent/memory.json` yang diinjeksi ke sistem instruksi model secara otomatis di setiap sesi (`/memory`).
- **Auto-Detect Model API**: Daftar model tidak di-hardcode, melainkan dipindai secara dinamis langsung dari Gemini API dengan filter kapabilitas `generateContent` dan tool calling.
- **First-Run Terpandu**: Alur modal interaktif untuk konfigurasi API key (disembunyikan) dan pemilihan model otomatis saat pertama kali diluncurkan.
- **Tool Calling Dinamis**: Agen dapat membuat folder, mendaftar file, membaca file, menulis file, menjalankan perintah shell, dan menyimpan/mengingat informasi ke memori jangka panjang.
- **Filter Keamanan Shell (Blacklist)**: Mencegah eksekusi perintah destruktif seperti penghapusan root direktori, pemformatan partisi disk, atau shutdown paksa.
- **Sistem Logging Terstruktur**: Rotasi harian di `~/.gemini-agent/logs/agent-YYYY-MM-DD.log` dengan diagnosa kesalahan mendalam (kategori, kode API, saran mitigasi, dan ringkasan traceback).

---

## ⌬ Bahasa Pemrograman: Indonesiaku-Lang

Basis kode aplikasi ini ditulis menggunakan bahasa pemrograman **Indonesiaku-Lang** (`.idk`) yang terinspirasi dari [teguh02/Indonesiaku-Lang](https://github.com/teguh02/Indonesiaku-Lang). Seluruh logika inti program (agen, antarmuka TUI Textual, modul memori, pengelola sesi, perkakas eksekusi, dan konfigurasi) ditulis dalam sintaks berbahasa Indonesia dengan kurung kurawal `{ }` dan kata kunci khas:
- `fungsi` (def), `kembalikan` (return)
- `kelas` (class), `diri` (self), `init` (__init__)
- `jika` (if), `jika_lain` (elif), `selain` (else)
- `untuk` (for), `dalam` (in), `selagi` (while)
- `coba` (try), `kecuali` (except), `akhirnya` (finally)
- `benar` (True), `salah` (False), `kosong` (None)

Runtime dieksekusi secara native via `penerjemah_idk.py` yang menyediakan Import Hook `sys.meta_path` dan translasi ast/bytecode langsung di memori tanpa jeda kompilasi manual.

---

## ⌬ Struktur Proyek

```text
gemini-terminal-agent/
│
├── penerjemah_idk.py   # Engine penerjemah & import hook loader Indonesiaku-Lang (.idk)
├── utama.py            # Peluncur utama berbasis Indonesiaku-Lang (menjalankan aplikasi.idk)
│
├── aplikasi.idk        # Kode sumber utama TUI Textual, layar modal, dan reactive watcher (Indonesiaku-Lang)
├── agen.idk            # Logika Agent Gemini, chat loop, dan function call handler (Indonesiaku-Lang)
├── pengelola_sesi.idk  # Pengelola sesi persisten, multi-turn, dan riwayat obrolan (Indonesiaku-Lang)
├── memori.idk          # Pengelola memori jangka panjang pengguna (Indonesiaku-Lang)
├── perkakas.idk        # 16 Tool sistem file, shell command runner, dan memori (Indonesiaku-Lang)
├── konfigurasi.idk     # Pengelola direktori ~/.gemini-agent dan .env (Indonesiaku-Lang)
│
├── app.py              # Pintu masuk kompatibilitas (meneruskan ke aplikasi.idk)
├── logger.py           # Logger rotasi harian dan formatter diagnosa error detail
├── requirements.txt    # Dependensi library Python (textual, google-genai, dll.)
├── run.bat             # Script peluncur Windows (venv otomatis + install deps)
├── run.sh              # Script peluncur Linux/macOS
└── README.md           # Dokumentasi teknis proyek
```

---

## ⌬ Persyaratan Sistem

- Python 3.10 atau versi yang lebih tinggi
- Koneksi internet untuk mengakses Gemini API
- Kunci API Google Gemini (dapat diperoleh melalui [Google AI Studio](https://aistudio.google.com/))

---

## ⌬ Instalasi dan Menjalankan

### Cara Cepat (Rekomendasi)

#### Pengguna Windows:
Cukup klik ganda atau jalankan file batch:
```cmd
run.bat
```

#### Pengguna Linux / macOS:
Berikan izin eksekusi lalu jalankan:
```bash
chmod +x run.sh
./run.sh
```

Script launcher di atas secara otomatis akan:
1. Memverifikasi keberadaan Python di sistem.
2. Membuat virtual environment `.venv` jika belum ada.
3. Memasang dependensi dari `requirements.txt`.
4. Menjalankan aplikasi `app.py`.
5. Memberikan jeda di akhir eksekusi sebelum terminal ditutup.

---

### Cara Manual

1. Buat dan aktifkan virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Pasang dependensi:
   ```bash
   pip install -r requirements.txt
   ```

3. Jalankan aplikasi:
   ```bash
   python utama.py
   # atau
   python app.py
   ```

---

## ⌬ Alur First-Run

Saat aplikasi pertama kali dijalankan dan belum menemukan konfigurasi:
1. **Layar 1 — Input API Key**:
   - Meminta input `GEMINI_API_KEY` (karakter disembunyikan).
   - Disimpan secara otomatis ke `~/.gemini-agent/.env`.
2. **Layar 2 — Deteksi Model**:
   - Menghubungi API Gemini untuk memindai seluruh model resmi yang tersedia.
   - Menampilkan daftar interaktif berisi nama model, nama teknis, dan batas token.
   - Pilihan disimpan sebagai `GEMINI_MODEL` di file `.env`.
   - Tersedia input manual jika koneksi terbatas atau ingin menggunakan nama spesifik.
3. **Layar 3 — Antarmuka Chat Utama**:
   - Menampilkan chat box, live clock di header, dan status bar di bagian bawah.

---

## ⌬ Perintah Slash dan Pintasan Keyboard

### Perintah Slash (Ketik di kotak input chat):
| Perintah / Format | Deskripsi |
| :--- | :--- |
| `@nama_berkas` | Menyertakan isi berkas langsung ke dalam konteks prompt (misal `@app.py`) |
| `/export [nama.md]` | Mengekspor percakapan aktif ke format dokumen Markdown yang rapi |
| `/restart` | Memulai ulang aplikasi terminal agent secara bersih (alias: `/reload`, `/reboot`) |
| `/stop` | Menghentikan pemrosesan respon agen seketika (alias: `/batal`, `/cancel`) |
| `/session` | Membuka jendela modal manajemen & pemulihan sesi |
| `/session list` | Menampilkan seluruh daftar sesi yang tersimpan di disk |
| `/session load <id/no>` | Memulihkan percakapan dan konteks dari sesi tertentu |
| `/session new [judul]` | Memulai sesi percakapan baru yang segar |
| `/session rename <judul>` | Mengubah judul sesi aktif saat ini |
| `/session delete <id/no>` | Menghapus file sesi dari disk |
| `/session info` | Menampilkan rincian statistik sesi aktif (turns, pesan, waktu) |
| `/memory` | Menampilkan seluruh catatan memori jangka panjang agent |
| `/memory set <key> <val>` | Menyimpan instruksi/preferensi/fakta baru ke memori persisten |
| `/memory delete <key>` | Menghapus kunci memori tertentu |
| `/memory clear` | Mengosongkan seluruh memori jangka panjang |
| `/theme <nama>` | Mengganti tema warna UI (`default`, `emerald`, `crimson`, `amber`, `purple`) |
| `/model` | Membuka layar deteksi model untuk mengganti model aktif |
| `/model <nama>` | Mengganti model aktif secara instan |
| `/clear` | Memulai sesi baru dan membersihkan tampilan layar chat |
| `/help` | Menampilkan ringkasan panduan perintah slash dan tombol pintasan |
| `/quit` | Menutup dan keluar dari aplikasi terminal |

### Pintasan Keyboard:
- `Enter` : Kirim pesan prompt ke agen
- `Ctrl + R` : Memulai ulang aplikasi (Restart)
- `Ctrl + X` : Menghentikan respon agen (Interrupt / Stop)
- `Ctrl + S` : Membuka Layar Manajemen & Pemulihan Sesi
- `Ctrl + M` : Membuka Layar Pemilihan Model
- `Ctrl + T` : Beralih tema warna UI secara berurutan
- `Ctrl + L` : Membersihkan area pesan chat & mulai sesi baru
- `Ctrl + C` : Keluar dari aplikasi

---

## ⌬ Tool Calling dan Proteksi Keamanan

Agen dibekali tool native Python yang dieksekusi secara otonom ketika dibutuhkan:
1. `create_folder(path)`: Membuat folder baru bersarang di dalam proyek.
2. `list_files(path=".")`: Mendaftar isi file dan sub-folder beserta ukuran byte.
3. `read_file(path)`: Membaca isi file teks di dalam proyek (batas maksimum 1MB).
4. `write_file(path, content)`: Menulis konten teks ke file secara aman dan atomik.
5. `edit_file(path, target_text, replacement_text)`: Menyunting potongan teks tertentu secara presisi (diff replace).
6. `run_command(command)`: Menjalankan perintah terminal lokal.
7. `save_memory(key, value)`: Menyimpan fakta/preferensi ke memori jangka panjang agent.
8. `recall_memory(key)`: Mencari dan membaca informasi dari memori jangka panjang.
9. `list_memories()`: Menampilkan semua informasi di memori jangka panjang.

### Proteksi Keamanan (Sandbox Jail):
Operasi berkas dibatasi secara ketat (*workspace sandbox*):
- Operasi baca/tulis/sunting di luar direktori kerja proyek otomatis diblokir.
- Mencegah *path traversal* (`../`) dan akses ke berkas sensitif sistem operasi.
- Penulisan berkas sesi dan memori menggunakan mekanisme penulisan atomik (*tempfile + atomic rename*).

### Blacklist Perintah Shell:
Perintah berbahaya berikut otomatis diblokir oleh sistem:
- `rm -rf /`
- `format c:`
- `mkfs`
- `shutdown`
- `del /f /s /q c:\`
- Pola disk wipe, fork bomb, dan manipulasi partisi berbasis regex.

---

## ⌬ Sistem Diagnosa Kesalahan dan Mode Debug

Semua aktivitas dicatat ke:
```text
~/.gemini-agent/logs/agent-YYYY-MM-DD.log
```

Setiap kesalahan ditampilkan dalam format terstruktur:
- **Simbol**: `[X]` (Error), `[!]` (Peringatan), `!!` (Rate limit), `◆` (Tool issue)
- **Kategori**: API Key, Rate Limit, Model Not Found, Network Timeout, Tool Error, Parse Error.
- **Status API**: Kode status HTTP dan kode error SDK (jika ada).
- **Saran Aksi**: Solusi teknis yang dapat diambil pengguna.
- **Traceback**: 3 baris ringkas teratas secara default.

### Mengaktifkan Full Traceback:
Untuk melihat full traceback saat debugging:
```bash
# Windows (CMD)
set GEMINI_AGENT_DEBUG=1
python app.py

# Windows (PowerShell)
$env:GEMINI_AGENT_DEBUG="1"
python app.py

# Linux / macOS
export GEMINI_AGENT_DEBUG=1
python3 app.py
```
