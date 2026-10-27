"""Konfigurasi dan manajemen file lingkungan untuk Gemini Terminal Agent.

Modul ini bertanggung jawab untuk membuat direktori konfigurasi lokal di ~/.gemini-agent,
membaca serta menyimpan GEMINI_API_KEY dan GEMINI_MODEL ke file .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key


class ConfigManager:
    """Mengelola konfigurasi aplikasi, direktori kerja, dan file .env lokal."""

    def __init__(self) -> None:
        self.app_dir: Path = Path.home() / ".gemini-agent"
        self.logs_dir: Path = self.app_dir / "logs"
        self.sessions_dir: Path = self.app_dir / "sessions"
        self.env_path: Path = self.app_dir / ".env"
        self.ensure_directories()
        self.reload()

    def ensure_directories(self) -> None:
        """Membuat direktori kerja, log, dan sesi jika belum ada."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not self.env_path.exists():
            self.env_path.touch(mode=0o600, exist_ok=True)

    def reload(self) -> None:
        """Muat ulang environment variables dari file .env."""
        if self.env_path.exists():
            load_dotenv(dotenv_path=self.env_path, override=True)

    def get_api_key(self) -> Optional[str]:
        """Mengambil Gemini API key dari env atau file .env."""
        self.reload()
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            stripped = key.strip()
            if stripped:
                return stripped
        return None

    def save_api_key(self, api_key: str) -> None:
        """Menyimpan Gemini API key ke file .env dan memperbarui environment aktif."""
        clean_key = api_key.strip()
        set_key(str(self.env_path), "GEMINI_API_KEY", clean_key)
        os.environ["GEMINI_API_KEY"] = clean_key

    def get_model(self) -> Optional[str]:
        """Mengambil model terpilih dari env atau file .env."""
        self.reload()
        model = os.environ.get("GEMINI_MODEL")
        if model:
            stripped = model.strip()
            if stripped:
                return stripped
        return None

    def save_model(self, model_name: str) -> None:
        """Menyimpan model terpilih ke file .env dan memperbarui environment aktif."""
        clean_model = model_name.strip()
        set_key(str(self.env_path), "GEMINI_MODEL", clean_model)
        os.environ["GEMINI_MODEL"] = clean_model

    def get_theme(self) -> str:
        """Mengambil tema terpilih dari env atau file .env. Default: 'default'."""
        self.reload()
        return os.environ.get("GEMINI_THEME", "default").strip()

    def save_theme(self, theme_name: str) -> None:
        """Menyimpan tema terpilih ke file .env dan memperbarui environment aktif."""
        clean_theme = theme_name.strip().lower()
        set_key(str(self.env_path), "GEMINI_THEME", clean_theme)
        os.environ["GEMINI_THEME"] = clean_theme

    def get_active_session_id(self) -> Optional[str]:
        """Mengambil ID sesi aktif terakhir dari env atau file .env."""
        self.reload()
        sess_id = os.environ.get("GEMINI_ACTIVE_SESSION")
        if sess_id:
            stripped = sess_id.strip()
            if stripped:
                return stripped
        return None

    def save_active_session_id(self, session_id: str) -> None:
        """Menyimpan ID sesi aktif terakhir ke file .env dan memperbarui environment aktif."""
        clean_id = session_id.strip()
        set_key(str(self.env_path), "GEMINI_ACTIVE_SESSION", clean_id)
        os.environ["GEMINI_ACTIVE_SESSION"] = clean_id

    def is_debug(self) -> bool:
        """Memeriksa apakah mode debug diaktifkan via GEMINI_AGENT_DEBUG."""
        return os.environ.get("GEMINI_AGENT_DEBUG", "0").strip() == "1"


config_manager = ConfigManager()
