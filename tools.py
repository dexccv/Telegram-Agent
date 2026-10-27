"""Kumpulan fungsi tools untuk eksekusi operasi file dan perintah sistem oleh Agent.

Menyediakan fungsi create_folder, list_files, read_file, write_file, serta
run_command yang dilengkapi filter keamanan perintah berbahaya (blacklist).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from logger import agent_logger

# Daftar pola perintah berbahaya yang diblokir untuk keamanan sistem
DANGEROUS_PATTERNS = [
    r"\brm\s+-(?:r[fv]|f[rv]|rf|fr)\s+(?:/|[a-zA-Z]:\\|\*)",
    r"\bformat\s+[a-zA-Z]:",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\bdel\s+(?:/[a-zA-Z\s]+)*[a-zA-Z]:\\",
    r"\brmdir\s+/[sS]\s+/[qQ]\s+[a-zA-Z]:\\",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # Fork bomb
    r"\bdd\s+if=.*of=/dev/[sh]d[a-z]",
]


def is_command_safe(command: str) -> tuple[bool, str]:
    """Memeriksa apakah perintah terminal masuk dalam daftar hitam perintah berbahaya."""
    clean_cmd = command.strip().lower()

    # Pengecekan kata kunci spesifik
    exact_blacklists = [
        "rm -rf /",
        "format c:",
        "mkfs",
        "shutdown",
        "del /f /s /q c:\\",
    ]
    for bl in exact_blacklists:
        if bl in clean_cmd:
            return False, f"Perintah terdeteksi dalam daftar terlarang: '{bl}'"

    # Pengecekan via regex pattern
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, clean_cmd, re.IGNORECASE):
            return False, f"Pola berbahaya terdeteksi oleh filter keamanan ({pattern})."

    return True, ""


def create_folder(path: str) -> str:
    """Membuat direktori baru pada path yang ditentukan.

    Args:
        path: Path direktori yang akan dibuat.

    Returns:
        Pesan status hasil pembuatan direktori.
    """
    try:
        target = Path(path).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        msg = f"[SUKSES] Direktori berhasil dibuat: {target}"
        agent_logger.log_info("tools.create_folder", msg)
        return msg
    except Exception as exc:
        agent_logger.log_error("tools.create_folder", f"Gagal membuat folder {path}: {exc}")
        return f"[GAGAL] Gagal membuat folder '{path}': {exc}"


def list_files(path: str = ".") -> str:
    """Mendaftar file dan direktori pada path yang diberikan.

    Args:
        path: Direktori yang ingin diperiksa (default: ".").

    Returns:
        Daftar item direktori beserta tipe dan ukurannya.
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"[GAGAL] Path tidak ditemukan: {target}"
        if not target.is_dir():
            return f"[GAGAL] Path bukan sebuah direktori: {target}"

        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"Isi dari direktori: {target}", "─" * 45]

        if not entries:
            lines.append("  (Direktori kosong)")
        else:
            for item in entries:
                if item.is_dir():
                    lines.append(f"  [DIR]   {item.name}/")
                else:
                    try:
                        size = item.stat().st_size
                        lines.append(f"  [FILE]  {item.name} ({size:,} bytes)")
                    except OSError:
                        lines.append(f"  [FILE]  {item.name}")

        msg = "\n".join(lines)
        agent_logger.log_info("tools.list_files", f"Mendaftar {len(entries)} item di {target}")
        return msg
    except Exception as exc:
        agent_logger.log_error("tools.list_files", f"Gagal mendaftar file di {path}: {exc}")
        return f"[GAGAL] Kesalahan saat membaca direktori '{path}': {exc}"


def read_file(path: str) -> str:
    """Membaca seluruh konten file teks dari path yang ditentukan.

    Args:
        path: Path file yang akan dibaca.

    Returns:
        Isi teks dari file atau pesan kesalahan jika gagal.
    """
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"[GAGAL] File tidak ditemukan: {target}"
        if not target.is_file():
            return f"[GAGAL] Path merujuk pada direktori, bukan file: {target}"

        # Cek batas ukuran untuk mencegah kehabisan memori konteks
        file_size = target.stat().st_size
        max_bytes = 1_000_000  # 1 MB
        if file_size > max_bytes:
            return f"[GAGAL] Ukuran file terlalu besar ({file_size} bytes). Batas maksimum pembacaan adalah 1MB."

        content = target.read_text(encoding="utf-8", errors="replace")
        agent_logger.log_info("tools.read_file", f"Membaca {file_size} bytes dari {target}")
        return content
    except Exception as exc:
        agent_logger.log_error("tools.read_file", f"Gagal membaca file {path}: {exc}")
        return f"[GAGAL] Tidak dapat membaca file '{path}': {exc}"


def write_file(path: str, content: str) -> str:
    """Menulis atau menimpa konten teks ke dalam file pada path tertentu.

    Args:
        path: Path file tujuan.
        content: Konten teks yang akan ditulis.

    Returns:
        Pesan status hasil penulisan file.
    """
    try:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        msg = f"[SUKSES] Berhasil menulis {len(content)} karakter ke file: {target}"
        agent_logger.log_info("tools.write_file", msg)
        return msg
    except Exception as exc:
        agent_logger.log_error("tools.write_file", f"Gagal menulis file {path}: {exc}")
        return f"[GAGAL] Gagal menulis ke file '{path}': {exc}"


def run_command(command: str) -> str:
    """Menjalankan perintah terminal/shell secara aman dengan proteksi blacklist.

    Args:
        command: String perintah shell yang akan dieksekusi.

    Returns:
        Output stdout dan stderr dari hasil eksekusi perintah terminal.
    """
    is_safe, reason = is_command_safe(command)
    if not is_safe:
        agent_logger.log_warning("tools.run_command", f"Perintah diblokir: {command} - Alasan: {reason}")
        return f"[BLOCKED] Perintah ditolak demi keamanan sistem: {reason}"

    try:
        agent_logger.log_info("tools.run_command", f"Menjalankan perintah: {command}")
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        code = process.returncode

        output_parts = [f"[KODE KELUAR: {code}]"]
        if stdout:
            output_parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            output_parts.append(f"STDERR:\n{stderr}")
        if not stdout and not stderr:
            output_parts.append("(Tidak ada output)")

        result = "\n\n".join(output_parts)
        agent_logger.log_info("tools.run_command", f"Selesai (kode {code}): {command[:60]}")
        return result
    except subprocess.TimeoutExpired:
        agent_logger.log_error("tools.run_command", f"Timeout 60 detik pada perintah: {command}")
        return "[TIMEOUT] Eksekusi perintah melebihi batas waktu 60 detik."
    except Exception as exc:
        agent_logger.log_error("tools.run_command", f"Kesalahan saat menjalankan '{command}': {exc}")
        return f"[GAGAL] Kesalahan saat menjalankan perintah: {exc}"


def save_memory(key: str, value: str) -> str:
    """Menyimpan informasi penting, fakta preferensi pengguna, atau konteks proyek ke memori jangka panjang agent.

    Args:
        key: Kata kunci atau label informasi (misal: 'preferensi_bahasa', 'tech_stack', 'aturan_proyek').
        value: Detail informasi atau fakta yang harus selalu diingat.

    Returns:
        Pesan status konfirmasi penyimpanan.
    """
    from memory import memory_manager
    try:
        memory_manager.set(key, value)
        return f"[SUKSES] Informasi '{key}' berhasil disimpan ke memori jangka panjang."
    except Exception as exc:
        return f"[GAGAL] Gagal menyimpan memori: {exc}"


def recall_memory(key: str) -> str:
    """Mengambil fakta atau informasi tertentu dari memori jangka panjang berdasarkan kunci.

    Args:
        key: Kunci memori yang ingin dicari.

    Returns:
        Nilai yang tersimpan atau pesan jika tidak ditemukan.
    """
    from memory import memory_manager
    val = memory_manager.get(key)
    if val is not None:
        return f"[DITEMUKAN] {key}: {val}"
    return f"[TIDAK DITEMUKAN] Tidak ada catatan untuk kunci: '{key}'"


def list_memories() -> str:
    """Melihat seluruh catatan dan informasi yang tersimpan dalam memori jangka panjang agent.

    Returns:
        Daftar seluruh key dan value memori persisten.
    """
    from memory import memory_manager
    mems = memory_manager.get_all()
    if not mems:
        return "Memori jangka panjang masih kosong."
    lines = ["Daftar Memori Jangka Panjang Persisten:", "─" * 45]
    for k, v in mems.items():
        lines.append(f"• {k}: {v}")
    return "\n".join(lines)


# Map fungsi tool untuk eksekusi dinamis
AVAILABLE_TOOLS: dict[str, Any] = {
    "create_folder": create_folder,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "save_memory": save_memory,
    "recall_memory": recall_memory,
    "list_memories": list_memories,
}

TOOL_CALLABLES = [
    create_folder,
    list_files,
    read_file,
    write_file,
    run_command,
    save_memory,
    recall_memory,
    list_memories,
]

OPENAI_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Membuat direktori/folder baru pada sistem.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Jalur folder yang akan dibuat"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Mendaftar berkas dan folder di dalam suatu direktori.",
            "parameters": {
                "type": "object",
                "properties": {"directory": {"type": "string", "description": "Jalur direktori (default: .)"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Membaca isi teks dari berkas lokal di sistem.",
            "parameters": {
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Jalur berkas yang akan dibaca"}},
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Menulis atau membuat berkas baru dengan isi teks tertentu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Jalur berkas yang akan ditulis"},
                    "content": {"type": "string", "description": "Isi teks yang akan ditulis ke berkas"},
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Menjalankan perintah shell/terminal di sistem pengguna secara aman.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Perintah shell/terminal yang akan dieksekusi"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Menyimpan fakta atau preferensi pengguna ke memori jangka panjang.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Kunci memori"},
                    "value": {"type": "string", "description": "Nilai atau isi memori yang disimpan"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Mengambil fakta dari memori jangka panjang berdasarkan kata kunci.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string", "description": "Kunci memori yang dicari"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "Melihat seluruh fakta yang tersimpan dalam memori jangka panjang.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

