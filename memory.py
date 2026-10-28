"""Modul manajemen memori jangka panjang untuk Gemini Terminal Agent.

Menyimpan fakta penting, instruksi pengguna, dan preferensi kerja secara persisten
pada file ~/.gemini-agent/memory.json, sehingga agen tidak melupakan konteks
meskipun berganti sesi atau aplikasi dimulai ulang.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from config import config_manager
from logger import agent_logger


class MemoryManager:
    """Mengelola penyimpanan key-value memori persisten untuk agent."""

    def __init__(self, memory_file: Optional[Path] = None) -> None:
        self.memory_file: Path = memory_file or (config_manager.app_dir / "memory.json")
        self._ensure_file()

    def _atomic_write(self, content: str) -> None:
        """Menulis konten ke file memori secara atomic menggunakan file temporer."""
        temp_path = self.memory_file.with_suffix(".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(self.memory_file)

    def _ensure_file(self) -> None:
        """Memastikan file memory.json tersedia."""
        try:
            if not self.memory_file.exists():
                self._atomic_write("{}")
        except Exception as exc:
            agent_logger.log_error("memory.ensure_file", f"Gagal membuat file memori: {exc}")

    def get_all(self) -> dict[str, str]:
        """Mengambil seluruh data memori yang tersimpan."""
        try:
            if self.memory_file.exists():
                raw = self.memory_file.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:
            agent_logger.log_error("memory.get_all", f"Gagal membaca data memori: {exc}")
        return {}

    def get(self, key: str) -> Optional[str]:
        """Mengambil nilai memori untuk kunci tertentu."""
        memories = self.get_all()
        return memories.get(key.strip())

    def set(self, key: str, value: str) -> None:
        """Menyimpan atau memperbarui pasangan key-value memori secara atomic."""
        clean_key = key.strip()
        clean_val = value.strip()
        if not clean_key:
            return

        memories = self.get_all()
        memories[clean_key] = clean_val

        try:
            self._atomic_write(json.dumps(memories, indent=2, ensure_ascii=False))
            agent_logger.log_info("memory.set", f"Memori disimpan (atomic): '{clean_key}' -> '{clean_val}'")
        except Exception as exc:
            agent_logger.log_error("memory.set", f"Gagal menulis memori: {exc}")

    def delete(self, key: str) -> bool:
        """Menghapus kunci memori tertentu. Mengembalikan True jika berhasil dihapus."""
        clean_key = key.strip()
        memories = self.get_all()
        if clean_key in memories:
            del memories[clean_key]
            try:
                self._atomic_write(json.dumps(memories, indent=2, ensure_ascii=False))
                agent_logger.log_info("memory.delete", f"Memori dihapus (atomic): '{clean_key}'")
                return True
            except Exception as exc:
                agent_logger.log_error("memory.delete", f"Gagal menghapus memori: {exc}")
        return False

    def clear(self) -> None:
        """Mengosongkan seluruh memori jangka panjang secara atomic."""
        try:
            self._atomic_write("{}")
            agent_logger.log_info("memory.clear", "Seluruh memori persisten dikosongkan (atomic).")
        except Exception as exc:
            agent_logger.log_error("memory.clear", f"Gagal mengosongkan memori: {exc}")

    def format_for_system_instruction(self) -> str:
        """Memformat seluruh memori ke dalam string instruksi sistem untuk model."""
        memories = self.get_all()
        if not memories:
            return ""

        lines = [
            "\n[MEMORI PERSISTEN JANGKA PANJANG (FAKTA & PREFERENSI PENGGUNA)]:",
            "Informasi berikut harus selalu Anda ingat dan terapkan dalam setiap keputusan:",
        ]
        for k, v in memories.items():
            lines.append(f"- {k}: {v}")
        lines.append("────────────────────────────────────────────────────────────")
        return "\n".join(lines)


memory_manager = MemoryManager()
