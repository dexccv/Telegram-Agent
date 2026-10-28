"""Kumpulan fungsi tools untuk eksekusi operasi file dan perintah sistem oleh Agent.

Menyediakan fungsi create_folder, list_files, read_file, write_file, serta
run_command yang dilengkapi filter keamanan perintah berbahaya (blacklist).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

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

# Daftar pola path yang SELALU diblokir terlepas dari konfigurasi
_ALWAYS_BLOCKED_PATTERNS = [
    ".ssh",
    ".gemini-agent/.env",
    "windows/system32",
    "windows/syswow64",
    "/etc/passwd",
    "/etc/shadow",
]


def validate_sandbox_path(path: str, allow_outside_workspace: bool = False) -> tuple[bool, str]:
    """Memvalidasi apakah path aman untuk diakses oleh agent.

    Mengembalikan (True, "") jika aman, atau (False, alasan) jika diblokir.
    """
    try:
        target = Path(path).expanduser().resolve()
    except Exception as exc:
        return False, f"Path tidak valid: {exc}"

    target_str = str(target).lower().replace("\\", "/")

    # 1. Blokir pola berbahaya absolut
    for pattern in _ALWAYS_BLOCKED_PATTERNS:
        if pattern in target_str:
            return False, f"Akses ke '{pattern}' selalu diblokir demi keamanan sistem."

    # 2. Blokir file .env di mana saja untuk melindungi kredensial API
    if target.name == ".env" or target.name.endswith(".env") or target.suffix == ".env":
        return False, "Akses ke file .env diblokir untuk melindungi kredensial API."

    # 3. Jika tidak diizinkan di luar workspace, cek batas direktori
    if not allow_outside_workspace:
        workspace = Path.cwd().resolve()
        try:
            target.relative_to(workspace)
        except ValueError:
            # Izinkan akses ke folder home agent (~/.gemini-agent) selain file .env
            agent_dir = (Path.home() / ".gemini-agent").resolve()
            try:
                target.relative_to(agent_dir)
            except ValueError:
                return False, (
                    f"Akses ke '{target}' diblokir. Path berada di luar direktori kerja "
                    f"('{workspace}'). Gunakan path relatif atau minta izin eksplisit."
                )

    return True, ""


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
    is_safe, reason = validate_sandbox_path(path)
    if not is_safe:
        agent_logger.log_warning("tools.create_folder", f"Path diblokir: {path} - {reason}")
        return f"[DIBLOKIR KEAMANAN] {reason}"

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
    is_safe, reason = validate_sandbox_path(path)
    if not is_safe:
        agent_logger.log_warning("tools.list_files", f"Path diblokir: {path} - {reason}")
        return f"[DIBLOKIR KEAMANAN] {reason}"

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
    is_safe, reason = validate_sandbox_path(path)
    if not is_safe:
        agent_logger.log_warning("tools.read_file", f"Path diblokir: {path} - {reason}")
        return f"[DIBLOKIR KEAMANAN] {reason}"

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
    is_safe, reason = validate_sandbox_path(path)
    if not is_safe:
        agent_logger.log_warning("tools.write_file", f"Path diblokir: {path} - {reason}")
        return f"[DIBLOKIR KEAMANAN] {reason}"

    try:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        temp_path = target.with_suffix(target.suffix + ".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(target)
        msg = f"[SUKSES] Berhasil menulis {len(content)} karakter ke file: {target}"
        agent_logger.log_info("tools.write_file", msg)
        return msg
    except Exception as exc:
        agent_logger.log_error("tools.write_file", f"Gagal menulis file {path}: {exc}")
        return f"[GAGAL] Gagal menulis ke file '{path}': {exc}"


def edit_file(path: str, target_text: str, replacement_text: str) -> str:
    """Mengganti blok teks spesifik dalam file tanpa menimpa seluruh konten.

    Lebih efisien dari write_file karena hanya memodifikasi bagian yang diperlukan,
    menghemat kuota output token model AI secara signifikan.

    Args:
        path: Path file yang akan diedit.
        target_text: Teks yang akan dicari dan diganti (harus unik dalam file).
        replacement_text: Teks pengganti.

    Returns:
        Pesan status keberhasilan atau kegagalan.
    """
    is_safe, reason = validate_sandbox_path(path)
    if not is_safe:
        agent_logger.log_warning("tools.edit_file", f"Path diblokir: {path} - {reason}")
        return f"[DIBLOKIR KEAMANAN] {reason}"

    try:
        target = Path(path).expanduser().resolve()
        if not target.exists():
            return f"[GAGAL] File tidak ditemukan: {target}"
        if not target.is_file():
            return f"[GAGAL] Path bukan sebuah file: {target}"

        content = target.read_text(encoding="utf-8", errors="replace")
        occurrences = content.count(target_text)

        if occurrences == 0:
            return f"[GAGAL] Teks target tidak ditemukan dalam file '{path}'. Pastikan teks target identik persis."
        if occurrences > 1:
            return (
                f"[PERINGATAN] Teks target ditemukan {occurrences} kali. "
                f"Hanya penggantian pertama yang akan dilakukan. "
                f"Gunakan target_text yang lebih spesifik untuk penggantian tepat."
            )

        new_content = content.replace(target_text, replacement_text, 1)

        # Atomic write
        temp_path = target.with_suffix(target.suffix + ".tmp")
        temp_path.write_text(new_content, encoding="utf-8")
        temp_path.replace(target)

        lines_changed = abs(replacement_text.count("\n") - target_text.count("\n"))
        msg = f"[SUKSES] File '{path}' berhasil diedit. {lines_changed} baris diubah."
        agent_logger.log_info("tools.edit_file", msg)
        return msg
    except Exception as exc:
        agent_logger.log_error("tools.edit_file", f"Gagal mengedit file {path}: {exc}")
        return f"[GAGAL] Kesalahan saat mengedit file '{path}': {exc}"


DANGEROUS_COMMANDS = [
    "format",
    "del /f /s /q c:\\",
    "del /s /q c:\\",
    "rmdir /s /q c:\\",
    "diskpart",
    "bcdedit",
    "shutdown",
    "reg delete",
    "mkfs",
    "rm -rf /",
    ":(){ :|:& };:",
]


def run_sandboxed_command(
    command: str,
    workspace_root: Optional[Path] = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Menjalankan perintah terminal dalam lingkungan sandbox terisolasi dengan proteksi perintah berbahaya.

    Args:
        command: Perintah shell yang akan dijalankan.
        workspace_root: Direktori kerja eksekusi (default: Path.cwd()).
        timeout: Batas waktu eksekusi dalam detik (default: 60).

    Returns:
        Dictionary berisikan success (bool), stdout (str), stderr (str), returncode (int).
    """
    root = (workspace_root or Path.cwd()).resolve()
    cmd_lower = command.strip().lower()

    # 1. Pengecekan daftar hitam perintah destruktif
    is_safe, reason = is_command_safe(command)
    if not is_safe:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"[SANDBOX BLOCKED] Perintah ditolak demi keamanan sistem: {reason}",
            "returncode": -1,
        }

    for bad in DANGEROUS_COMMANDS:
        if bad in cmd_lower:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"[SANDBOX BLOCKED] Perintah '{command}' ditolak karena mengandung pola terlarang '{bad}'.",
                "returncode": -1,
            }

    # 2. Injeksi lingkungan .venv otomatis jika tersedia di workspace
    env = os.environ.copy()
    venv_dir = root / ".venv"
    venv_scripts = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    if venv_scripts.exists():
        env["VIRTUAL_ENV"] = str(venv_dir)
        env["PATH"] = f"{venv_scripts}{os.pathsep}{env.get('PATH', '')}"

    try:
        agent_logger.log_info("tools.sandboxed_command", f"Menjalankan di '{root}': {command}")
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout[:6000],
            "stderr": proc.stderr[:3000],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        agent_logger.log_error("tools.sandboxed_command", f"Timeout {timeout}s: {command}")
        return {
            "success": False,
            "stdout": "",
            "stderr": f"[SANDBOX TIMEOUT] Perintah melebihi batas waktu {timeout} detik.",
            "returncode": -1,
        }
    except Exception as exc:
        agent_logger.log_error("tools.sandboxed_command", f"Kesalahan eksekusi '{command}': {exc}")
        return {
            "success": False,
            "stdout": "",
            "stderr": f"[SANDBOX ERROR] Gagal mengeksekusi perintah: {exc}",
            "returncode": -1,
        }


def run_command(command: str) -> str:
    """Menjalankan perintah terminal/shell secara aman dengan proteksi sandboxing.

    Args:
        command: String perintah shell yang akan dieksekusi.

    Returns:
        Output stdout dan stderr dari hasil eksekusi perintah terminal.
    """
    res = run_sandboxed_command(command)
    code = res["returncode"]
    stdout = res["stdout"].strip()
    stderr = res["stderr"].strip()

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
    "edit_file": edit_file,
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
    edit_file,
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
            "name": "edit_file",
            "description": "Mengganti blok teks spesifik di dalam file teks tanpa menimpa seluruh file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Jalur file yang akan diedit"},
                    "target_text": {"type": "string", "description": "Teks eksak yang akan dicari dan diganti"},
                    "replacement_text": {"type": "string", "description": "Teks baru pengganti"},
                },
                "required": ["path", "target_text", "replacement_text"],
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

# Muat seluruh perkakas sistem lengkap dari perkakas.idk jika tersedia
try:
    from penerjemah_idk import aktifkan_hook_idk
    aktifkan_hook_idk()
    import perkakas
    p_tools = getattr(perkakas, "ALAT_TERSEDIA", getattr(perkakas, "AVAILABLE_TOOLS", None))
    if p_tools:
        AVAILABLE_TOOLS.update(p_tools)
        existing_names = {getattr(f, "__name__", "") for f in TOOL_CALLABLES}
        p_callables = getattr(perkakas, "DAFTAR_PANGGILAN_ALAT", getattr(perkakas, "TOOL_CALLABLES", []))
        for fn in p_callables:
            fn_name = getattr(fn, "__name__", "")
            if fn_name and fn_name not in existing_names:
                TOOL_CALLABLES.append(fn)
                existing_names.add(fn_name)

        p_schemas = getattr(perkakas, "SKEMA_ALAT_OPENAI", getattr(perkakas, "OPENAI_TOOLS_SCHEMA", []))
        existing_schema_names = {
            s.get("function", {}).get("name") for s in OPENAI_TOOLS_SCHEMA if isinstance(s, dict)
        }
        for s in p_schemas:
            s_name = s.get("function", {}).get("name") if isinstance(s, dict) else None
            if s_name and s_name not in existing_schema_names:
                OPENAI_TOOLS_SCHEMA.append(s)
                existing_schema_names.add(s_name)

        for _name, _func in AVAILABLE_TOOLS.items():
            if _name not in globals():
                globals()[_name] = _func
except Exception as _exc:
    agent_logger.log_warning("tools.load_perkakas", f"Gagal sinkronisasi perkakas.idk: {_exc}")

