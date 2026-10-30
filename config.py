"""Konfigurasi dan manajemen file lingkungan untuk TeleAgent.

Modul ini bertanggung jawab untuk membuat direktori konfigurasi lokal di ~/.gemini-agent,
membaca serta menyimpan GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, dan TELEGRAM_USER_ID.
"""

from __future__ import annotations

import os
import time
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
        self._failed_gemini_keys: set[str] = set()
        self._last_reload_time: float = 0.0
        self._reload_interval: float = 2.0
        self.ensure_directories()
        self.reload(force=True)

    def ensure_directories(self) -> None:
        """Membuat direktori kerja, log, dan sesi jika belum ada."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if not self.env_path.exists():
            self.env_path.touch(mode=0o600, exist_ok=True)

    def reload(self, force: bool = False) -> None:
        """Muat ulang environment variables dari file .env jika interval terlewati atau dipaksa."""
        now = time.time()
        if not force and (now - self._last_reload_time < self._reload_interval):
            return

        if self.env_path.exists():
            load_dotenv(dotenv_path=self.env_path, override=True)
        if not os.environ.get("OLLAMA_MODELS"):
            os.environ["OLLAMA_MODELS"] = r"D:\.ollama\models"
        self._last_reload_time = now

    def get_provider(self) -> str:
        """Mengambil provider AI aktif ('gemini', 'omniroute', 'ollama', atau 'groq')."""
        self.reload()
        prov = os.environ.get("AI_PROVIDER", "").strip().lower()
        if prov in ["gemini", "omniroute", "ollama", "groq"]:
            return prov
        if os.environ.get("GROQ_API_KEY"):
            return "groq"
        if os.environ.get("OMNI_API_KEY"):
            return "omniroute"
        return "gemini"

    def save_provider(self, provider: str) -> None:
        """Menyimpan provider AI aktif ke file .env."""
        clean = provider.strip().lower()
        set_key(str(self.env_path), "AI_PROVIDER", clean)
        os.environ["AI_PROVIDER"] = clean

    def get_gemini_key_pool(self) -> list[str]:
        """Mengambil seluruh daftar API key Gemini dari GEMINI_API_KEY dan GEMINI_API_KEYS."""
        self.reload()
        keys: list[str] = []
        primary = os.environ.get("GEMINI_API_KEY", "").strip()
        if primary:
            keys.append(primary)
        pool_raw = os.environ.get("GEMINI_API_KEYS", "").strip()
        if pool_raw:
            for item in pool_raw.split(","):
                clean_item = item.strip()
                if clean_item and clean_item not in keys:
                    keys.append(clean_item)
        return keys

    def get_next_valid_gemini_key(self) -> Optional[str]:
        """Mengambil kunci Gemini berikutnya dari pool yang belum ditandai gagal/exhausted."""
        pool = self.get_gemini_key_pool()
        for k in pool:
            if k not in self._failed_gemini_keys:
                return k
        return None

    def mark_key_failed(self, key: str) -> None:
        """Menandai kunci tertentu sebagai tidak valid atau habis kuota untuk sesi ini."""
        if key:
            self._failed_gemini_keys.add(key.strip())

    def reset_failed_keys(self) -> None:
        """Mereset status blacklist kunci yang gagal."""
        self._failed_gemini_keys.clear()

    def get_gemini_api_key(self) -> Optional[str]:
        """Mengambil API key resmi Gemini yang aktif dan valid."""
        self.reload()
        k = os.environ.get("GEMINI_API_KEY", "").strip()
        if k and k not in self._failed_gemini_keys:
            return k
        # Coba ambil kunci berikutnya dari pool cadangan jika kunci utama gagal
        fallback = self.get_next_valid_gemini_key()
        if fallback:
            return fallback
        return k or None

    def save_gemini_api_key(self, api_key: str) -> None:
        """Menyimpan API key resmi Gemini dan mereset status kegagalan kunci ini."""
        clean = api_key.strip()
        set_key(str(self.env_path), "GEMINI_API_KEY", clean)
        os.environ["GEMINI_API_KEY"] = clean
        self._failed_gemini_keys.discard(clean)

    def add_gemini_api_key(self, api_key: str) -> None:
        """Menambahkan API key baru ke dalam pool GEMINI_API_KEYS dan menjadikannya kunci aktif."""
        clean = api_key.strip()
        if not clean:
            return
        pool = self.get_gemini_key_pool()
        if clean not in pool:
            pool.append(clean)
        pool_str = ",".join(pool)
        set_key(str(self.env_path), "GEMINI_API_KEYS", pool_str)
        os.environ["GEMINI_API_KEYS"] = pool_str
        self.save_gemini_api_key(clean)

    def get_gemini_model(self) -> str:
        """Mengambil nama model Gemini aktif (default: gemini-2.5-flash)."""
        self.reload()
        m = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
        if not m or "/" in m or m == "auto":
            return "gemini-2.5-flash"
        return m

    def save_gemini_model(self, model_name: str) -> None:
        """Menyimpan nama model Gemini."""
        clean = model_name.strip()
        set_key(str(self.env_path), "GEMINI_MODEL", clean)
        os.environ["GEMINI_MODEL"] = clean

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

    def get_omni_model(self) -> str:
        """Mengambil nama model Omni aktif (default: auto)."""
        self.reload()
        return os.environ.get("OMNI_MODEL", "auto").strip() or "auto"

    def save_omni_model(self, model_name: str) -> None:
        """Menyimpan nama model Omni."""
        clean = model_name.strip()
        set_key(str(self.env_path), "OMNI_MODEL", clean)
        os.environ["OMNI_MODEL"] = clean

    def get_ollama_base_url(self) -> str:
        """Mengambil Base URL Ollama (default: http://localhost:11434/v1)."""
        self.reload()
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()

    def save_ollama_base_url(self, base_url: str) -> None:
        """Menyimpan Base URL Ollama."""
        clean = base_url.strip()
        set_key(str(self.env_path), "OLLAMA_BASE_URL", clean)
        os.environ["OLLAMA_BASE_URL"] = clean

    def get_ollama_models_path(self) -> str:
        r"""Mengambil path direktori penyimpanan model Ollama (default: D:\.ollama\models)."""
        self.reload()
        return os.environ.get("OLLAMA_MODELS", r"D:\.ollama\models").strip() or r"D:\.ollama\models"

    def save_ollama_models_path(self, path: str) -> None:
        """Menyimpan path direktori penyimpanan model Ollama."""
        clean = path.strip()
        set_key(str(self.env_path), "OLLAMA_MODELS", clean)
        os.environ["OLLAMA_MODELS"] = clean

    def get_ollama_model(self) -> str:
        """Mengambil nama model Ollama (default: llama3.2:3b)."""
        self.reload()
        m = os.environ.get("OLLAMA_MODEL", "llama3.2:3b").strip()
        if not m or m.startswith("gemini-") or m == "auto":
            return "llama3.2:3b"
        return m

    def save_ollama_model(self, model_name: str) -> None:
        """Menyimpan nama model Ollama."""
        clean = model_name.strip()
        set_key(str(self.env_path), "OLLAMA_MODEL", clean)
        os.environ["OLLAMA_MODEL"] = clean

    def get_groq_api_key(self) -> Optional[str]:
        """Mengambil API key Groq."""
        self.reload()
        k = os.environ.get("GROQ_API_KEY", "").strip()
        return k or None

    def save_groq_api_key(self, api_key: str) -> None:
        """Menyimpan API key Groq."""
        clean = api_key.strip()
        set_key(str(self.env_path), "GROQ_API_KEY", clean)
        os.environ["GROQ_API_KEY"] = clean

    def get_groq_model(self) -> str:
        """Mengambil model Groq aktif (default: openai/gpt-oss-120b)."""
        self.reload()
        return os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"

    def save_groq_model(self, model_name: str) -> None:
        """Menyimpan nama model Groq."""
        clean = model_name.strip()
        set_key(str(self.env_path), "GROQ_MODEL", clean)
        os.environ["GROQ_MODEL"] = clean

    def get_api_key(self) -> Optional[str]:
        """Mengambil API key sesuai provider aktif."""
        prov = self.get_provider()
        if prov == "groq":
            return self.get_groq_api_key()
        elif prov == "omniroute":
            return self.get_omni_api_key() or self.get_gemini_api_key()
        elif prov == "ollama":
            return "ollama"
        return self.get_gemini_api_key() or self.get_omni_api_key()

    def save_api_key(self, api_key: str) -> None:
        """Menyimpan API key ke provider aktif."""
        prov = self.get_provider()
        if prov == "groq":
            self.save_groq_api_key(api_key)
        elif prov == "omniroute":
            self.save_omni_api_key(api_key)
        elif prov == "ollama":
            pass
        else:
            self.save_gemini_api_key(api_key)

    def get_base_url(self) -> Optional[str]:
        """Mengambil base URL sesuai provider aktif."""
        prov = self.get_provider()
        if prov == "groq":
            return "https://api.groq.com/openai/v1"
        elif prov == "omniroute":
            return self.get_omni_base_url()
        elif prov == "ollama":
            return self.get_ollama_base_url()
        return os.environ.get("GEMINI_BASE_URL")

    def save_base_url(self, base_url: str) -> None:
        clean_url = base_url.strip()
        prov = self.get_provider()
        if prov == "groq":
            pass
        elif prov == "omniroute":
            self.save_omni_base_url(clean_url)
        elif prov == "ollama":
            self.save_ollama_base_url(clean_url)
        else:
            set_key(str(self.env_path), "GEMINI_BASE_URL", clean_url)
            os.environ["GEMINI_BASE_URL"] = clean_url

    def get_model(self) -> Optional[str]:
        """Mengambil model terpilih untuk provider aktif."""
        self.reload()
        prov = self.get_provider()
        if prov == "groq":
            return self.get_groq_model()
        elif prov == "omniroute":
            return self.get_omni_model()
        elif prov == "ollama":
            return self.get_ollama_model()
        return self.get_gemini_model()

    def save_model(self, model_name: str) -> None:
        """Menyimpan model terpilih untuk provider aktif."""
        clean_model = model_name.strip()
        prov = self.get_provider()
        if prov == "groq":
            self.save_groq_model(clean_model)
        elif prov == "omniroute":
            self.save_omni_model(clean_model)
        elif prov == "ollama":
            self.save_ollama_model(clean_model)
        else:
            self.save_gemini_model(clean_model)

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
        self.reload()
        return os.environ.get("GEMINI_AGENT_DEBUG", "").strip().lower() in ("1", "true", "yes")

    def get_telegram_token(self) -> str:
        """Mengambil token bot Telegram dari environment variable."""
        self.reload()
        return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    def get_telegram_allowed_user_id(self) -> str:
        """Mengambil Telegram User ID yang diizinkan (whitelist)."""
        self.reload()
        return os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()

    # Alias kompatibilitas bahasa Indonesia
    ambil_provider = get_provider
    simpan_provider = save_provider
    ambil_gemini_api_key = get_gemini_api_key
    simpan_gemini_api_key = save_gemini_api_key
    ambil_gemini_model = get_gemini_model
    simpan_gemini_model = save_gemini_model
    ambil_omni_api_key = get_omni_api_key
    simpan_omni_api_key = save_omni_api_key
    ambil_omni_base_url = get_omni_base_url
    simpan_omni_base_url = save_omni_base_url
    ambil_omni_model = get_omni_model
    simpan_omni_model = save_omni_model
    ambil_groq_api_key = get_groq_api_key
    simpan_groq_api_key = save_groq_api_key
    ambil_groq_model = get_groq_model
    simpan_groq_model = save_groq_model
    ambil_ollama_base_url = get_ollama_base_url
    simpan_ollama_base_url = save_ollama_base_url
    ambil_ollama_models_path = get_ollama_models_path
    simpan_ollama_models_path = save_ollama_models_path
    ambil_ollama_model = get_ollama_model
    simpan_ollama_model = save_ollama_model
    ambil_api_key = get_api_key
    simpan_api_key = save_api_key
    ambil_base_url = get_base_url
    simpan_base_url = save_base_url
    ambil_model = get_model
    simpan_model = save_model
    ambil_tema = get_theme
    simpan_tema = save_theme
    ambil_sesi_aktif_id = get_active_session_id
    simpan_sesi_aktif_id = save_active_session_id
    apakah_mode_debug = is_debug
    ambil_telegram_token = get_telegram_token
    ambil_telegram_allowed_user_id = get_telegram_allowed_user_id


config_manager = ConfigManager()
