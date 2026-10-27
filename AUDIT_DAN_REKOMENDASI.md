# AUDIT PROYEK & LAPORAN REKOMENDASI ARSITEKTUR
**Proyek:** Gemini Terminal Agent (Indonesiaku-Lang & Textual TUI)  
**Tanggal Audit:** 27 Oktober 2026  
**Status Audit:** Lengkap / Menyeluruh  

---

## 1. Eksekutif Ringkasan (Executive Summary)

Proyek **Gemini Terminal Agent** adalah aplikasi AI Agent terminal berbasis antarmuka teks (TUI) interaktif yang memanfaatkan Textual dan Google GenAI SDK. Karakteristik paling unik dari proyek ini adalah implementasi **Indonesiaku-Lang** (`.idk`), sebuah lapisan transpiler kustom yang memungkinkan seluruh kode aplikasi ditulis menggunakan sintaks, kata kunci, dan paradigma Bahasa Indonesia secara penuh, yang kemudian ditranspilasi ke Python bytecode secara runtime.

Secara fungsionalitas, aplikasi ini sudah memiliki fitur inti yang kaya:
- Multi-turn conversation dengan persistence sesi (`pengelola_sesi.idk`).
- Memori jangka panjang persisten lintas sesi (`memori.idk`).
- Eksekusi alat otonom (function calling) untuk manajemen file, shell, dan memori (`perkakas.idk`).
- Deteksi model otomatis dan konfigurasi interaktif (`konfigurasi.idk`).
- Antarmuka visual Textual yang kaya dengan multi-tema warna dan interrupt button (`aplikasi.idk`).
- Perintah `/restart` dan pintasan `Ctrl + R` untuk re-eksekusi bersih proses terminal.

Namun, audit mendalam ini menemukan sejumlah **kelemahan struktural, risiko keamanan, keterbatasan performa, dan tantangan pemeliharaan** yang perlu ditangani sebelum sistem ini dapat dianggap siap pakai tingkat produksi (production-ready).

---

## 2. Analisis Kekurangan Berdasarkan Komponen

### A. Lapisan Transpiler & Bahasa (`penerjemah_idk.py`)
| Aspek | Temuan Masalah | Dampak Teknis |
| :--- | :--- | :--- |
| **Metode Parsing** | Menggunakan Regular Expression (Regex) baris-per-baris, bukan Abstract Syntax Tree (AST) atau Tokenizer formal. | Rentan terhadap kegagalan parsing pada ekspresi kurung kurawal bersarang, kamus (dictionary) dalam string multiline, atau struktur kontrol yang kompleks. |
| **Source Mapping** | Tidak ada pemetaan baris asli (`sourcemap`). Stack trace galat Python merujuk ke nomor baris kode Python virtual di memori, bukan ke nomor baris berkas `.idk` asal. | Proses debugging galat sintaks/runtime menjadi jauh lebih lambat karena developer harus merekonstruksi baris kode `.idk` manual. |
| **Duplikasi Basis Kode** | Terdapat file Python legacy (`agent.py`, `tools.py`, `config.py`, dll.) berdampingan dengan berkas `.idk` (`agen.idk`, `perkakas.idk`, dll.). | Menyebabkan kebingungan mengenai berkas mana yang menjadi sumber kebenaran (*single source of truth*) dan risiko desinkronisasi. |
| **Penanganan Method Scope** | Penginjeksian `diri` (*self*) pada method kelas dilakukan melalui inspeksi kedalaman indentasi string (`class_indent_stack`). | Berisiko salah menginjeksi argumen jika ada fungsi helper internal di dalam method atau decorator bertingkat. |

---

### B. Keamanan & Eksekusi Perintah Sistem (`perkakas.idk`)
| Aspek | Temuan Masalah | Dampak Teknis |
| :--- | :--- | :--- |
| **Filter Perintah Berbahaya** | Menggunakan pendekatan daftar hitam (*blacklist regex* string sederhana). | **Mudah di-bypass**. Perintah seperti `echo cm0gLXJmIC8= \| base64 -d \| bash`, `python -c "import shutil; shutil.rmtree('/')"`, atau enkapsulasi Powershell tidak terdeteksi oleh regex. |
| **Ketiadaan Sandbox Path** | `read_file`, `write_file`, dan `list_files` menggunakan `Path.resolve()` tanpa batasan direktori kerja (*jail/sandbox*). | AI Agent dapat diarahkan untuk membaca berkas rahasia (`~/.ssh/id_rsa`, `.env`, password database) atau menimpa berkas sistem di luar folder proyek. |
| **Penyimpanan Kredensial** | `GEMINI_API_KEY` disimpan dalam format teks polos (*plaintext*) pada berkas `~/.gemini-agent/.env`. | Siapa pun atau malware lokal dengan izin baca direktori pengguna dapat mengekstraksi API key tersebut secara langsung. |
| **Timeout Subprocess** | Perintah `run_command` memiliki batas waktu 60 detik, namun proses anak (*child process*) yang tidak membaca stdin dapat mengalami hanging atau spawn proses background yang tidak terkontrol. | Konsumsi memori/CPU berlebih jika agen menjalankan loop tak terbatas yang tidak menghasilkan output. |

---

### C. Manajemen Konteks, Token, & Sesi (`agen.idk` & `pengelola_sesi.idk`)
| Aspek | Temuan Masalah | Dampak Teknis |
| :--- | :--- | :--- |
| **Ketiadaan Strategi Token Pruning** | Seluruh turn percakapan (`history`) dipertahankan dan dikirim ulang pada setiap putaran tanpa batas akumulasi token. | Pada sesi panjang dengan output tool ratusan baris, biaya token membengkak cepat, latensi API meningkat drastis, dan dapat memicu galat `RESOURCE_EXHAUSTED` (429/Token Limit Exceeded). |
| **Pseudo-Streaming UI** | UI tidak melakukan *true streaming* token-demi-token dari API Gemini. Agen menunggu seluruh payload selesai via `send_message()` blocking, lalu merender animasi ketik per karakter di klien. | Pengguna menunggu lama dalam mode "Thinking" sebelum melihat teks pertama keluar, mengurangi impresi responsivitas real-time. |
| **Interupsi Thread Non-Preemptive** | Flag `diri.interrupted` hanya diperiksa sebelum dan sesudah panggilan API atau sebelum eksekusi tool. | Jika SDK Gemini sedang menunggu I/O socket jaringan (network latency), menekan tombol *Interrupt* tidak membatalkan request HTTP secara preemptif seketika. |
| **Atomic File Operations** | Penyimpanan sesi dan memori ke file `.json` menggunakan penulisan langsung `write_text()` tanpa mekanisme penulisan atomik (*tempfile + atomic rename*). | Jika proses mati mendadak atau terputus daya saat operasi tulis berlangsung, berkas `session.json` atau `memory.json` dapat menjadi korup (kosong/0 bytes). |

---

### D. Arsitektur Antarmuka Visual (`aplikasi.idk`)
| Aspek | Temuan Masalah | Dampak Teknis |
| :--- | :--- | :--- |
| **Berkas Monolitik** | Seluruh logika UI, komponen kartu, modal, CSS generator, event handler, dan loop restart bertumpuk dalam satu berkas tunggal sepanjang ~1600 baris. | Pelanggaran prinsip *Single Responsibility*. Kompleksitas tinggi dan menyulitkan kolaborasi multi-developer. |
| **I/O Disk Sinkron saat Navigasi** | Membuka modal sesi membaca seluruh metadata berkas sesi di disk secara sinkron pada main thread Textual. | Jika terdapat puluhan atau ratusan file sesi, UI Textual akan mengalami lag/freeze sesaat (*frame drop*). |
| **Adaptabilitas Layar Terminal Kecil** | Layout antarmuka berasumsi lebar konsol standar minimal 100 kolom. | Pada terminal split-screen atau konsol sempit (di bawah 80 kolom), status bar dan tombol input dapat mengalami pemotongan teks atau desakan visual. |

---

### E. Kualitas Kode, Pengujian, & Dependensi
| Aspek | Temuan Masalah | Dampak Teknis |
| :--- | :--- | :--- |
| **Ketiadaan Automated Test Suite** | Tidak ada direktori `tests/` atau konfigurasi `pytest`/`unittest` yang terintegrasi. Pengujian selama ini hanya bergantung pada skrip acak di folder scratch. | Rawan regresi fungsionalitas ketika ada modifikasi pada transpiler atau komponen inti. |
| **Spesifikasi Dependensi Longgar** | `requirements.txt` hanya mencantumkan nama library (`textual`, `google-genai`) tanpa batasan versi spesifik (*semantic version pinning*). | Instalasi di lingkungan baru berisiko rusak jika versi major baru dari Textual atau Google GenAI merilis breaking changes. |
| **Ketiadaan CI/CD Workflow** | Tidak ada konfigurasi GitHub Actions untuk menjalankan automated build & testing saat terjadi commit atau pull request. | Menurunkan jaminan keandalan repositori secara publik. |

---

## 3. Kritik Konstruktif

1. **Tentang Konsep Bahasa "Indonesiaku-Lang":**
   - *Kelebihan:* Sangat kreatif, edukatif, dan membuktikan bahwa konsep pemrograman tingkat tinggi dengan bahasa lokal dapat berjalan mulus di atas runtime Python.
   - *Kritik:* Karena dibangun menggunakan pendekatan translasi teks/regex ad-hoc, ia menanggung "utang teknis" (*technical debt*) yang tinggi. Semakin besar fitur bahasa yang ingin didukung (misalnya async/await generator, list comprehension bersarang, type annotations kompleks), semakin rapuh sistem parsing berbasis string replace ini.
2. **Tentang Keamanan Eksekusi Tool Terminal:**
   - *Kritik:* Memberikan AI Agent akses tak terbatas ke terminal lokal (`subprocess.run(shell=True)`) dengan filter blacklist adalah anti-pattern dalam keamanan sistem otonom. Model bahasa dapat sewaktu-waktu mengalami halusinasi dan merusak berkas lokal penting.
3. **Tentang Pengalaman Pengguna (UX Streaming):**
   - *Kritik:* Di era model LLM modern, pengguna mengharapkan token mengalir segera setelah diproduksi (Time to First Token < 1 detik). Menunggu respons selesai lalu "berpura-pura" mengetik memperlambat alur kerja produktif developer.

---

## 4. Rencana Rekomendasi & Panduan Perbaikan (Actionable Roadmap)

### Fase 1: Penguatan Keamanan & Keandalan Penyimpanan (Prioritas Tinggi)
1. **Implementasi Workspace Jail / Sandbox Path:**
   - Batasi operasi `read_file`, `write_file`, `create_folder`, dan `list_files` hanya di dalam direktori kerja proyek (atau path yang secara eksplisit disetujui pengguna).
   - Cegah akses ke path absolut di luar workspace dan cegah pola `../` traversal.
2. **Konfirmasi Pengguna untuk Perintah Berbahaya (Human-in-the-Loop):**
   - Alih-alih hanya bergantung pada regex blacklist, sediakan modal konfirmasi pada Textual: "Agen ingin mengeksekusi perintah: `[command]`. Izinkan? [Ya / Tidak]".
3. **Penyimpanan Berkas Atomik (Atomic File Writing):**
   - Perbarui `pengelola_sesi.idk` dan `memori.idk` agar menulis data ke file sementara (`.tmp`) terlebih dahulu, kemudian melakukan `os.replace` ke nama target untuk mencegah berkas korup akibat interupsi.

### Fase 2: Manajemen Konteks Cerdas & Streaming Nyata (Prioritas Menengah)
1. **Strategi Context Pruning / Sliding Window:**
   - Hitung perkiraan token pada `session.history`. Jika melebihi batas (misal 50.000 token), pangkas putaran percakapan lama secara elegan atau gunakan ringkasan otomatis (*summarization turn*), sembari tetap mempertahankan system instruction dan pesan terbaru.
2. **Native Response Streaming:**
   - Beralih dari `chat.send_message()` ke `chat.send_message_stream()`.
   - Sambungkan generator stream tersebut langsung ke widget chat Textual sehingga respons mulai tertulis di layar seketika token pertama tiba.
3. **Dukungan Preemptive Cancellation:**
   - Simpan reference ke task asyncio atau HTTP request SDK agar saat tombol Interrupt ditekan, request jaringan dapat di-abort seketika tanpa menunggu socket selesai.

### Fase 3: Modernisasi Transpiler & Pembersihan Basis Kode (Prioritas Menengah)
1. **Migrasi Transpiler ke AST / Tokenizer:**
   - Gunakan pustaka bawaan `tokenize` Python untuk memisahkan token kata kunci, string literal, komentar, dan tanda kurung. Ini akan mengeliminasi seluruh bug kurung kurawal bersarang dan menjaga integritas string f-string.
2. **Pembuatan Source Map Generator:**
   - Setiap baris `.idk` yang diterjemahkan harus memiliki tabel asosiasi baris sumber, sehingga traceback eksepsi dapat menampilkan nomor baris asli `.idk`.
3. **Pembersihan Berkas Legacy:**
   - Hapus atau pindahkan file Python lama (`agent.py`, `tools.py`, `memory.py`, dll.) ke subfolder `archive/` agar repositori bersih dan berfokus penuh pada `.idk`.

### Fase 4: Modularisasi UI & Automated Testing (Prioritas Fondasional)
1. **Pemecahan Modul UI (`aplikasi.idk`):**
   - Pecah menjadi berkas-berkas tematik:
     - `tampilan_tema.idk`: Definisi tema dan generator CSS.
     - `komponen_kartu.idk`: Message card, typing card, tool call card.
     - `layar_modal.idk`: Modal API key, modal ganti model, modal sesi.
     - `aplikasi.idk`: Entry point utama aplikasi.
2. **Penyusunan Test Suite Resmi (`tests/`):**
   - Buat unit test terotomatisasi untuk memvalidasi:
     - Kompilasi semua berkas `.idk`.
     - Validasi tool function calling schema.
     - Pengujian session persistence (create, load, switch, delete).
     - Pengujian alur interrupt dan restart.
3. **Penguncian Versi Dependensi (`requirements.txt`):**
   - Tentukan pin versi stabil, misalnya:
     ```text
     textual>=0.85.0,<1.0.0
     google-genai>=1.0.0,<2.0.0
     python-dotenv>=1.0.0
     ```

---

## 5. Kesimpulan Audit

Proyek ini telah berhasil membuktikan kelayakan implementasi konsep bahasa pemrograman Indonesia (*Indonesiaku-Lang*) pada aplikasi TUI berbasis agen modern. Arsitektur modular antara agen, perkakas, memori, dan sesi percakapan sudah berada di jalur yang benar. Dengan menerapkan perbaikan keamanan sandbox, migrasi ke native token streaming, context window management, dan penguatan parsing transpiler, proyek ini memiliki potensi luar biasa untuk menjadi rujukan utama AI Agent berbasis teks di ekosistem pengembang Indonesia.
