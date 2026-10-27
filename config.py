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

    def get_provider(self) -> str:
        """Mengambil provider AI aktif ('gemini' atau 'omniroute')."""
        self.reload()
        prov = os.environ.get("AI_PROVIDER", "").strip().lower()
        if prov in ["gemini", "omniroute"]:
            return prov
        if os.environ.get("OMNI_API_KEY"):
            return "omniroute"
        return "gemini"

    def save_provider(self, provider: str) -> None:
        """Menyimpan provider AI aktif ke file .env."""
        clean = provider.strip().lower()
        set_key(str(self.env_path), "AI_PROVIDER", clean)
        os.environ["AI_PROVIDER"] = clean

    def get_gemini_api_key(self) -> Optional[str]:
        """Mengambil API key resmi Gemini."""
        self.reload()
        k = os.environ.get("GEMINI_API_KEY", "").strip()
        return k or None

    def save_gemini_api_key(self, api_key: str) -> None:
        """Menyimpan API key resmi Gemini."""
        clean = api_key.strip()
        set_key(str(self.env_path), "GEMINI_API_KEY", clean)
        os.environ["GEMINI_API_KEY"] = clean

    def get_omni_api_key(self) -> Optional[str]:
        """Mengambil API key Omniroute."""
        self.reload()
        k = os.environ.get("OMNI_API_KEY", "").strip()
        return k or None

    def save_omni_api_key(self, api_key: str) -> None:
        """Menyimpan API key Omniroute."""
        clean = api_key.strip()
        set_key(str(self.env_path), "OMNI_API_KEY", clean)
        os.environ["OMNI_API_KEY"] = clean

    def get_omni_base_url(self) -> str:
        """Mengambil Base URL Omniroute."""
        self.reload()
        return os.environ.get("OMNI_BASE_URL", "http://localhost:20128/v1").strip()

    def save_omni_base_url(self, base_url: str) -> None:
        """Menyimpan Base URL Omniroute."""
        clean = base_url.strip()
        set_key(str(self.env_path), "OMNI_BASE_URL", clean)
        os.environ["OMNI_BASE_URL"] = clean

    def get_api_key(self) -> Optional[str]:
        """Mengambil API key sesuai provider aktif."""
        if self.get_provider() == "omniroute":
            return self.get_omni_api_key() or self.get_gemini_api_key()
        return self.get_gemini_api_key() or self.get_omni_api_key()

    def save_api_key(self, api_key: str) -> None:
        """Menyimpan API key ke provider aktif."""
        if self.get_provider() == "omniroute":
            self.save_omni_api_key(api_key)
        else:
            self.save_gemini_api_key(api_key)

    def get_base_url(self) -> Optional[str]:
        """Mengambil base URL sesuai provider aktif."""
        if self.get_provider() == "omniroute":
            return self.get_omni_base_url()
        return os.environ.get("GEMINI_BASE_URL")

    def save_base_url(self, base_url: str) -> None:
        clean_url = base_url.strip()
        if self.get_provider() == "omniroute":
            self.save_omni_base_url(clean_url)
        else:
            set_key(str(self.env_path), "GEMINI_BASE_URL", clean_url)
            os.environ["GEMINI_BASE_URL"] = clean_url

    def get_model(self) -> Optional[str]:
        """Mengambil model terpilih untuk provider aktif."""
        self.reload()
        if self.get_provider() == "omniroute":
            return os.environ.get("OMNI_MODEL", "auto").strip() or "auto"
        return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    def save_model(self, model_name: str) -> None:
        """Menyimpan model terpilih untuk provider aktif."""
        clean_model = model_name.strip()
        if self.get_provider() == "omniroute":
            set_key(str(self.env_path), "OMNI_MODEL", clean_model)
            os.environ["OMNI_MODEL"] = clean_model
        else:
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
