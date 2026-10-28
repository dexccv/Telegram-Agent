"""
Sistem Self-Healing untuk Gemini Terminal Agent.

Secara otomatis mendeteksi crash, mendiagnosis error menggunakan Gemini AI,
menghasilkan patch perbaikan kode, meminta konfirmasi pengguna, menerapkan fix,
dan mencatat seluruh proses dalam laporan terstruktur.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich import box

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CrashReport:
    """Menyimpan semua informasi tentang satu siklus crash + healing."""

    timestamp: str = ""
    program_name: str = ""
    exit_code: int = -1
    error_type: str = ""
    error_message: str = ""
    traceback_text: str = ""
    file_affected: str = ""
    line_number: int = 0
    ai_diagnosis: str = ""
    ai_fix_description: str = ""
    ai_patch: str = ""          # Raw JSON string dari AI
    fix_applied: bool = False
    attempt_number: int = 1
    healing_log_path: str = ""


# ---------------------------------------------------------------------------
# SelfHealer class
# ---------------------------------------------------------------------------

class SelfHealer:
    """Mendeteksi crash, menganalisis dengan Gemini AI, dan menerapkan perbaikan."""

    def __init__(self, program_name: str, max_attempts: int = 3) -> None:
        self.program_name = program_name
        self.max_attempts = max_attempts
        self.console = Console()

        # Baca konfigurasi — impor di dalam method agar tidak crash jika config rusak
        try:
            from config import config_manager  # type: ignore
            self.api_key: Optional[str] = config_manager.get_gemini_api_key()
            self.telegram_token: str = config_manager.get_telegram_token()
            self.telegram_user_id: str = config_manager.get_telegram_allowed_user_id()
        except Exception:
            self.api_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
            self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            self.telegram_user_id = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()

        # Direktori healing
        base_dir = Path.home() / ".gemini-agent"
        self.healing_logs_dir: Path = base_dir / "healing_logs"
        self.backup_dir: Path = base_dir / "healing_backups"
        self.healing_logs_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # parse_traceback
    # ------------------------------------------------------------------

    def parse_traceback(self, error_output: str) -> CrashReport:
        """Parse string traceback/stderr dan isi CrashReport."""
        report = CrashReport(
            timestamp=datetime.now().isoformat(),
            program_name=self.program_name,
            traceback_text=error_output,
        )

        # Cari semua pola  File "...", line N
        file_matches = re.findall(r'File "(.+?)", line (\d+)', error_output)
        if file_matches:
            # Ambil file terakhir (yang paling dekat dengan error)
            last_file, last_line = file_matches[-1]
            report.file_affected = last_file
            report.line_number = int(last_line)

        # Cari tipe error — baris terakhir yang mengandung "Error:" atau "Exception:"
        lines = error_output.strip().splitlines()
        for line in reversed(lines):
            stripped = line.strip()
            # Cocokkan pola ExceptionType: message
            match = re.match(r'^([A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt|Exit)[A-Za-z0-9_]*)\s*:\s*(.*)', stripped)
            if match:
                report.error_type = match.group(1)
                report.error_message = match.group(2).strip()
                break
            # Tangani baris hanya berisi tipe error tanpa pesan
            match2 = re.match(r'^([A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt|Exit)[A-Za-z0-9_]*)$', stripped)
            if match2:
                report.error_type = match2.group(1)
                report.error_message = ""
                break

        if not report.error_type:
            # Fallback: ambil baris terakhir non-kosong sebagai pesan error
            for line in reversed(lines):
                if line.strip():
                    report.error_type = "UnknownError"
                    report.error_message = line.strip()
                    break

        return report

    # ------------------------------------------------------------------
    # diagnose_with_ai
    # ------------------------------------------------------------------

    def diagnose_with_ai(self, report: CrashReport, file_content: str) -> CrashReport:
        """Kirim error ke Gemini REST API dan isi diagnosis dalam report."""
        if not self.api_key:
            report.ai_diagnosis = "Tidak ada GEMINI_API_KEY — diagnosis AI dilewati."
            report.ai_fix_description = "Perbaiki secara manual."
            report.ai_patch = json.dumps({"diagnosis": report.ai_diagnosis,
                                          "fix_description": report.ai_fix_description,
                                          "patches": []})
            return report

        prompt = f"""Kamu adalah AI engineer yang ahli dalam Python dan debugging.

Sebuah program Python bernama "{report.program_name}" mengalami crash dengan error berikut:

ERROR TYPE: {report.error_type}
ERROR MESSAGE: {report.error_message}

TRACEBACK:
{report.traceback_text}

KODE FILE YANG ERROR ({report.file_affected}):
{file_content}

Tugasmu:
1. Jelaskan MENGAPA error ini terjadi (dalam bahasa Indonesia, 2-3 kalimat)
2. Jelaskan APA yang harus diperbaiki (konkret, spesifik)
3. Berikan KODE PERBAIKAN dalam format JSON berikut:

{{
  "diagnosis": "penjelasan penyebab error",
  "fix_description": "apa yang diperbaiki",
  "patches": [
    {{
      "target_text": "kode asli yang harus diganti (PERSIS sama dengan kode di file)",
      "replacement_text": "kode pengganti yang sudah diperbaiki"
    }}
  ]
}}

PENTING:
- target_text harus PERSIS sama dengan teks di file (termasuk indentasi dan whitespace)
- Jika tidak bisa diperbaiki otomatis, isi patches dengan array kosong []
- Pastikan responsenya adalah JSON valid saja, tanpa markdown atau teks tambahan
"""

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={self.api_key}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            ai_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            # Bersihkan markdown code fence jika ada
            ai_text = re.sub(r"^```(?:json)?\s*", "", ai_text, flags=re.MULTILINE)
            ai_text = re.sub(r"\s*```$", "", ai_text, flags=re.MULTILINE)
            ai_text = ai_text.strip()

            parsed = json.loads(ai_text)
            report.ai_diagnosis = parsed.get("diagnosis", "")
            report.ai_fix_description = parsed.get("fix_description", "")
            report.ai_patch = ai_text  # Simpan JSON string mentah

        except urllib.error.URLError as exc:
            report.ai_diagnosis = f"Gagal menghubungi Gemini API: {exc}"
            report.ai_fix_description = "Tidak ada fix otomatis tersedia."
            report.ai_patch = json.dumps({"diagnosis": report.ai_diagnosis,
                                          "fix_description": report.ai_fix_description,
                                          "patches": []})
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            report.ai_diagnosis = f"Gagal mem-parse respons AI: {exc}"
            report.ai_fix_description = "Tidak ada fix otomatis tersedia."
            report.ai_patch = json.dumps({"diagnosis": report.ai_diagnosis,
                                          "fix_description": report.ai_fix_description,
                                          "patches": []})

        return report

    # ------------------------------------------------------------------
    # display_crash_report
    # ------------------------------------------------------------------

    def display_crash_report(self, report: CrashReport) -> None:
        """Tampilkan laporan crash di terminal dengan Rich formatting."""
        console = self.console

        console.print()
        console.print(Panel(
            f"[bold red]⚠  CRASH TERDETEKSI[/bold red]\n\n"
            f"[yellow]Timestamp :[/yellow] {report.timestamp}\n"
            f"[yellow]Program   :[/yellow] {report.program_name}\n"
            f"[yellow]Exit Code :[/yellow] {report.exit_code}\n"
            f"[yellow]Percobaan :[/yellow] {report.attempt_number} / {self.max_attempts}",
            title="[bold red]SELF-HEALING AKTIF[/bold red]",
            border_style="red",
        ))

        # Tabel error diagnosis
        tbl = Table(title="Detail Error", box=box.ROUNDED, border_style="yellow", expand=True)
        tbl.add_column("Field", style="cyan", no_wrap=True)
        tbl.add_column("Nilai", style="white")
        tbl.add_row("Tipe Error", report.error_type)
        tbl.add_row("Pesan Error", report.error_message)
        tbl.add_row("File Terdampak", report.file_affected)
        tbl.add_row("Nomor Baris", str(report.line_number) if report.line_number else "-")
        console.print(tbl)

        # Traceback (batasi 20 baris)
        tb_lines = report.traceback_text.strip().splitlines()
        if len(tb_lines) > 20:
            tb_lines = tb_lines[:20]
            tb_lines.append("... (dipotong, lihat log untuk traceback lengkap)")
        tb_text = "\n".join(tb_lines)
        console.print(Panel(
            Syntax(tb_text, "python", theme="monokai", line_numbers=False),
            title="[yellow]TRACEBACK[/yellow]",
            border_style="yellow",
        ))

        # AI Analysis
        if report.ai_diagnosis:
            console.print(Panel(
                f"[bold]📋 Diagnosis:[/bold]\n{report.ai_diagnosis}\n\n"
                f"[bold]🔧 Rencana Perbaikan:[/bold]\n{report.ai_fix_description}",
                title="[bold green]ANALISIS AI[/bold green]",
                border_style="green",
            ))

        # Proposed Patches
        if report.ai_patch:
            try:
                patch_data = json.loads(report.ai_patch)
                patches = patch_data.get("patches", [])
                if patches:
                    for idx, patch in enumerate(patches, 1):
                        console.print(Panel(
                            Syntax(patch.get("target_text", ""), "python", theme="monokai"),
                            title=f"[bold cyan]PATCH #{idx} — TARGET (kode asli)[/bold cyan]",
                            border_style="cyan",
                        ))
                        console.print(Panel(
                            Syntax(patch.get("replacement_text", ""), "python", theme="monokai"),
                            title=f"[bold cyan]PATCH #{idx} — PENGGANTI (kode baru)[/bold cyan]",
                            border_style="green",
                        ))
                else:
                    console.print(
                        Panel("[italic]AI tidak menghasilkan patch otomatis untuk error ini.[/italic]",
                              title="PATCH", border_style="dim")
                    )
            except (json.JSONDecodeError, Exception):
                console.print(
                    Panel(report.ai_patch[:500], title="RAW AI RESPONSE", border_style="dim")
                )

    # ------------------------------------------------------------------
    # backup_file
    # ------------------------------------------------------------------

    def backup_file(self, file_path: Path) -> Path:
        """Buat backup file ke healing_backups sebelum dimodifikasi."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}_{ts}.bak"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(file_path, backup_path)
        return backup_path

    # ------------------------------------------------------------------
    # apply_patches
    # ------------------------------------------------------------------

    def apply_patches(self, report: CrashReport) -> tuple[bool, str]:
        """Terapkan patch dari report.ai_patch ke file yang terpengaruh."""
        if not report.ai_patch:
            return False, "Tidak ada patch untuk diterapkan."

        try:
            patch_data = json.loads(report.ai_patch)
        except json.JSONDecodeError as exc:
            return False, f"Gagal mem-parse JSON patch: {exc}"

        patches = patch_data.get("patches", [])
        if not patches:
            return False, "AI tidak menghasilkan patch (daftar patches kosong)."

        target_file = Path(report.file_affected)
        if not target_file.exists():
            return False, f"File tidak ditemukan: {target_file}"

        try:
            original_content = target_file.read_text(encoding="utf-8")
        except OSError as exc:
            return False, f"Gagal membaca file: {exc}"

        # Backup sebelum modifikasi
        backup_path = self.backup_file(target_file)
        report.healing_log_path  # Pastikan field ada

        modified_content = original_content
        applied_count = 0
        failed_patches: list[str] = []

        for idx, patch in enumerate(patches, 1):
            target_text = patch.get("target_text", "")
            replacement_text = patch.get("replacement_text", "")
            if not target_text:
                failed_patches.append(f"Patch #{idx}: target_text kosong")
                continue
            if target_text in modified_content:
                modified_content = modified_content.replace(target_text, replacement_text, 1)
                applied_count += 1
            else:
                failed_patches.append(f"Patch #{idx}: target_text tidak ditemukan di file")

        if applied_count == 0:
            # Kembalikan backup karena tidak ada yang berubah
            return False, "Tidak ada patch yang berhasil diterapkan. " + "; ".join(failed_patches)

        # Atomic write: tulis ke tmp file lalu replace
        try:
            dir_ = target_file.parent
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=dir_, delete=False, suffix=".tmp"
            ) as tmp:
                tmp.write(modified_content)
                tmp_path = tmp.name
            os.replace(tmp_path, target_file)
        except OSError as exc:
            # Jika atomic write gagal, restore backup
            shutil.copy2(backup_path, target_file)
            return False, f"Gagal menulis file (backup sudah dibuat): {exc}"

        success_msg = (
            f"{applied_count}/{len(patches)} patch berhasil diterapkan. "
            f"Backup: {backup_path}"
        )
        if failed_patches:
            success_msg += " | Gagal: " + "; ".join(failed_patches)

        report.fix_applied = True
        return True, success_msg

    # ------------------------------------------------------------------
    # save_healing_log
    # ------------------------------------------------------------------

    def save_healing_log(self, report: CrashReport) -> Path:
        """Simpan laporan healing ke file Markdown."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^\w\-]", "_", report.program_name)
        log_file = self.healing_logs_dir / f"healing_{ts}_{safe_name}.md"

        # Parse patch info
        patches_section = ""
        try:
            patch_data = json.loads(report.ai_patch) if report.ai_patch else {}
            patches = patch_data.get("patches", [])
            if patches:
                for idx, p in enumerate(patches, 1):
                    patches_section += f"\n### Patch #{idx}\n\n"
                    patches_section += f"**Target (kode asli):**\n```python\n{p.get('target_text', '')}\n```\n\n"
                    patches_section += f"**Pengganti:**\n```python\n{p.get('replacement_text', '')}\n```\n"
            else:
                patches_section = "_Tidak ada patch otomatis._\n"
        except (json.JSONDecodeError, Exception):
            patches_section = f"```\n{report.ai_patch}\n```\n"

        status_emoji = "✅" if report.fix_applied else "❌"
        status_text = "BERHASIL DITERAPKAN" if report.fix_applied else "GAGAL / TIDAK DITERAPKAN"

        content = f"""# Laporan Self-Healing

## Metadata

| Field | Nilai |
|-------|-------|
| Timestamp | `{report.timestamp}` |
| Program | {report.program_name} |
| Percobaan | {report.attempt_number} / {self.max_attempts} |
| Exit Code | `{report.exit_code}` |

---

## Penyebab Error

- **Tipe Error:** `{report.error_type}`
- **Pesan:** {report.error_message}
- **File Terdampak:** `{report.file_affected}`
- **Nomor Baris:** {report.line_number}

### Traceback Lengkap

```
{report.traceback_text}
```

---

## Diagnosis AI

{report.ai_diagnosis}

**Rencana Perbaikan:**

{report.ai_fix_description}

---

## Patch yang Diterapkan
{patches_section}

---

## Status Fix

{status_emoji} **{status_text}**

---

## File Backup

Backup disimpan di direktori: `{self.backup_dir}`
"""

        log_file.write_text(content, encoding="utf-8")
        report.healing_log_path = str(log_file)
        return log_file

    # ------------------------------------------------------------------
    # send_telegram_notification
    # ------------------------------------------------------------------

    def send_telegram_notification(self, report: CrashReport) -> None:
        """Kirim ringkasan laporan healing ke Telegram jika token dikonfigurasi."""
        token = self.telegram_token
        user_id = self.telegram_user_id

        if not token or not user_id:
            return  # Tidak dikonfigurasi, lewati

        status_str = "✅ Berhasil diterapkan" if report.fix_applied else "❌ Gagal/Ditolak"

        # Escape karakter khusus MarkdownV2
        def esc(text: str) -> str:
            for ch in r"\_*[]()~`>#+-=|{}.!":
                text = text.replace(ch, f"\\{ch}")
            return text

        message = (
            "🔧 *SELF\\-HEALING AKTIF*\n\n"
            f"Program: `{esc(report.program_name)}`\n"
            f"Error: `{esc(report.error_type)}`\n"
            f"File: `{esc(report.file_affected)}` baris {report.line_number}\n\n"
            f"📋 *Diagnosis:*\n{esc(report.ai_diagnosis[:300])}\n\n"
            f"✅ *Status Fix:* {esc(status_str)}\n\n"
            f"📄 Log: `{esc(report.healing_log_path)}`"
        )

        payload = json.dumps({
            "chat_id": user_id,
            "text": message,
            "parse_mode": "MarkdownV2",
        }).encode("utf-8")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except Exception as exc:
            # Jangan crash hanya karena notifikasi Telegram gagal
            try:
                from logger import agent_logger  # type: ignore
                agent_logger.log_warning("self_healer", f"Gagal kirim notifikasi Telegram: {exc}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # run_healing_cycle
    # ------------------------------------------------------------------

    def run_healing_cycle(
        self,
        error_output: str,
        entry_point_file: str,
        attempt_number: int = 1,
    ) -> tuple[bool, CrashReport]:
        """Jalankan satu siklus penuh: parse → diagnose → display → confirm → patch → log → notify."""
        console = self.console

        # 1. Parse traceback
        report = self.parse_traceback(error_output)
        report.attempt_number = attempt_number

        # 2. Baca konten file yang error
        file_to_read = report.file_affected or entry_point_file
        try:
            file_content = Path(file_to_read).read_text(encoding="utf-8")
        except OSError:
            file_content = "(Konten file tidak dapat dibaca)"

        # 3. Diagnosis AI
        console.print("\n[bold cyan]🤖 Menganalisis error dengan Gemini AI...[/bold cyan]")
        report = self.diagnose_with_ai(report, file_content)

        # 4. Tampilkan laporan
        self.display_crash_report(report)

        # 5. Tanya konfirmasi user
        try:
            answer = input("\nTerapkan perbaikan ke kode? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

        if answer in ("y", "yes", ""):
            # 6. Terapkan patch
            console.print("\n[bold yellow]🔧 Menerapkan patch...[/bold yellow]")
            success, msg = self.apply_patches(report)
            if success:
                console.print(f"[bold green]✅ {msg}[/bold green]")
            else:
                console.print(f"[bold red]❌ {msg}[/bold red]")
                success = False
        else:
            console.print("[yellow]⏭  Patch tidak diterapkan atas permintaan pengguna.[/yellow]")
            success = False

        # 8. Simpan log
        log_path = self.save_healing_log(report)
        console.print(f"[dim]📄 Log tersimpan: {log_path}[/dim]")

        # 9. Notifikasi Telegram
        self.send_telegram_notification(report)

        # 10. Return
        return success, report


# ---------------------------------------------------------------------------
# Standalone function — dipanggil dari run_with_healing.py
# ---------------------------------------------------------------------------

def run_with_healing(
    entry_point_file: str,
    program_name: str,
    max_attempts: int = 3,
) -> None:
    """Jalankan entry_point_file sebagai subprocess dengan siklus self-healing otomatis."""
    console = Console()
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        console.print(
            f"\n[bold cyan]▶ Menjalankan {program_name} (Percobaan {attempt}/{max_attempts})...[/bold cyan]"
        )

        proc = subprocess.Popen(
            [sys.executable, entry_point_file],
            stdout=None,    # Biarkan stdout muncul langsung ke terminal
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Tunggu proses selesai, tangkap stderr
        _, stderr_output = proc.communicate()
        exit_code = proc.returncode

        if exit_code == 0:
            console.print(f"[bold green]✅ {program_name} selesai dengan sukses.[/bold green]")
            break

        # --- Crash terdeteksi ---
        console.print(
            f"\n[bold red]💥 Program crash terdeteksi! (exit code: {exit_code})[/bold red]"
        )
        console.print("[bold yellow]🔄 Menjalankan Self-Healing...[/bold yellow]")

        healer = SelfHealer(program_name, max_attempts)
        healer.console.print(
            f"[dim]Stderr output ({len(stderr_output)} karakter) diterima.[/dim]"
        )

        success, report = healer.run_healing_cycle(
            error_output=stderr_output or "(tidak ada output stderr)",
            entry_point_file=entry_point_file,
            attempt_number=attempt,
        )

        if success:
            # Tanya apakah mau restart
            try:
                restart = input("\nRestart program sekarang? [Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                restart = "n"

            if restart in ("y", "yes", ""):
                console.print("[bold cyan]🔄 Me-restart program...[/bold cyan]")
                continue  # Ulang loop
            else:
                console.print("[yellow]Program tidak di-restart. Keluar.[/yellow]")
                break
        else:
            if attempt < max_attempts:
                console.print(
                    f"[yellow]Percobaan {attempt} gagal. Akan coba lagi ({attempt + 1}/{max_attempts})...[/yellow]"
                )
                # Tanya apakah mau lanjut mencoba
                try:
                    cont = input("Lanjutkan ke percobaan berikutnya? [Y/n]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    cont = "n"
                if cont not in ("y", "yes", ""):
                    console.print("[yellow]Pengguna membatalkan. Keluar.[/yellow]")
                    break
            else:
                console.print(
                    Panel(
                        "[bold red]❌ Tidak dapat memperbaiki otomatis setelah "
                        f"{max_attempts} percobaan.[/bold red]\n\n"
                        "Silakan perbaiki secara manual. Log healing tersimpan di:\n"
                        f"[cyan]{Path.home() / '.gemini-agent' / 'healing_logs'}[/cyan]",
                        title="SELF-HEALING GAGAL",
                        border_style="red",
                    )
                )
