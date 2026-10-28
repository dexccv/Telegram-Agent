"""In-Session Recovery Healer untuk Gemini Terminal Agent.

Modul ini bertanggung jawab untuk mendeteksi, mendiagnosis, dan memulihkan
kesalahan runtime yang terjadi di dalam sesi aktif (Terminal & Telegram Gateway)
tanpa merusak percakapan, tanpa membuang konteks, dan tanpa restart aplikasi.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from config import config_manager
from logger import agent_logger


class HealingAction(str, Enum):
    """Kategori aksi pemulihan in-session."""
    RETRY = "retry"
    KEY_ROTATED = "key_rotated"
    MODEL_FALLBACK = "model_fallback"
    PROVIDER_FALLBACK = "provider_fallback"
    HISTORY_REPAIRED = "history_repaired"
    NEEDS_USER_INPUT = "needs_user_input"
    UNRECOVERABLE = "unrecoverable"


@dataclass
class HealingResult:
    """Hasil dari percobaan pemulihan error in-session."""
    action: HealingAction
    recovered: bool
    summary: str
    details: str = ""
    new_key: Optional[str] = None
    new_model: Optional[str] = None
    new_provider: Optional[str] = None
    retry_delay_seconds: float = 0.0


# Urutan cascade fallback untuk model Gemini
GEMINI_FALLBACK_CASCADE = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class InSessionHealer:
    """Engine pemulihan error runtime di dalam sesi aktif."""

    def __init__(self, max_auto_retries: int = 3) -> None:
        self.max_auto_retries = max_auto_retries
        self._retry_counts: dict[str, int] = {}

    def classify_error(self, exc: Exception, context: str = "") -> str:
        """Mengidentifikasi kategori teknis error untuk menentukan strategi healing."""
        msg = str(exc)
        lower_msg = msg.lower()
        err_type = type(exc).__name__

        # 1. API Key Auth Error
        if (
            "api_key" in lower_msg
            or "api key" in lower_msg
            or "permission_denied" in lower_msg
            or "api_key_invalid" in lower_msg
            or ("400" in msg and "key" in lower_msg)
            or ("401" in msg)
            or ("403" in msg)
        ):
            return "auth_key"

        # 2. Rate Limit / Resource Exhausted
        if (
            "429" in msg
            or "resource_exhausted" in lower_msg
            or "rate limit" in lower_msg
            or "quota" in lower_msg
        ):
            return "rate_limit"

        # 3. Model Not Found / Unsupported
        if (
            "404" in msg
            or "not_found" in lower_msg
            or "unsupported" in lower_msg
            or "model not found" in lower_msg
        ):
            return "model_unsupported"

        # 4. Turn order mismatch / history corrupt / context length
        if (
            "turn" in lower_msg
            or "role" in lower_msg
            or "content" in lower_msg
            or "context length" in lower_msg
            or "max tokens" in lower_msg
            or "invalid_argument" in lower_msg
        ):
            return "session_corrupt"

        # 5. Network Transient / Timeout / 503
        if (
            "503" in msg
            or "unavailable" in lower_msg
            or "timeout" in lower_msg
            or "connect" in lower_msg
            or "network" in lower_msg
            or "ssl" in lower_msg
            or "deadline_exceeded" in lower_msg
            or "remotedisconnected" in lower_msg
        ):
            return "network_transient"

        return "unknown"

    def attempt_heal(
        self,
        exc: Exception,
        agent: Any,
        session: Any,
        context: str = "send_message",
        attempt: int = 1,
    ) -> HealingResult:
        """Mencoba memulihkan error in-session berdasarkan klasifikasi error."""
        error_cat = self.classify_error(exc, context)
        agent_logger.log_info(
            "session_healer",
            f"Memulai in-session healing: kategori={error_cat}, percobaan={attempt}, model={getattr(agent, 'model_name', '-')}",
        )

        # -------------------------------------------------------------
        # Skenario 1: API Key Invalid / Expired
        # -------------------------------------------------------------
        if error_cat == "auth_key":
            current_key = config_manager.get_gemini_api_key() or ""
            if current_key:
                config_manager.mark_key_failed(current_key)

            # Cek apakah ada kunci berikutnya di pool
            next_key = config_manager.get_next_valid_gemini_key()
            if next_key and next_key != current_key:
                config_manager.save_gemini_api_key(next_key)
                # Re-inisialisasi client agent
                if hasattr(agent, "_init_client"):
                    agent._init_client()
                if hasattr(agent, "_init_chat_session"):
                    agent._init_chat_session()
                agent_logger.log_info(
                    "session_healer",
                    f"Kunci API utama bermasalah. Berhasil beralih ke kunci cadangan di pool: {next_key[:6]}***",
                )
                return HealingResult(
                    action=HealingAction.KEY_ROTATED,
                    recovered=True,
                    summary="Beralih ke Kunci API Cadangan",
                    details=f"Kunci API utama kedaluwarsa. Sistem otomatis merotasi ke kunci cadangan ({next_key[:6]}***).",
                    new_key=next_key,
                )

            # Jika pool habis, coba beralih ke provider lokal/alternatif jika tersedia
            fallback_prov = self._try_provider_fallback(agent)
            if fallback_prov:
                return fallback_prov

            # Jika tidak ada cadangan sama sekali, minta input pengguna
            return HealingResult(
                action=HealingAction.NEEDS_USER_INPUT,
                recovered=False,
                summary="API Key Gemini Tidak Valid / Kedaluwarsa",
                details=(
                    "Kunci API Gemini saat ini tidak valid dan tidak ada kunci cadangan di pool. "
                    "Silakan masukkan kunci API baru untuk melanjutkan sesi tanpa perlu restart."
                ),
            )

        # -------------------------------------------------------------
        # Skenario 2: Rate Limit / Kuota Habis (429)
        # -------------------------------------------------------------
        if error_cat == "rate_limit":
            # Coba kunci lain terlebih dahulu jika ada di pool
            current_key = config_manager.get_gemini_api_key() or ""
            if current_key:
                config_manager.mark_key_failed(current_key)
            next_key = config_manager.get_next_valid_gemini_key()
            if next_key and next_key != current_key:
                config_manager.save_gemini_api_key(next_key)
                if hasattr(agent, "_init_client"):
                    agent._init_client()
                if hasattr(agent, "_init_chat_session"):
                    agent._init_chat_session()
                return HealingResult(
                    action=HealingAction.KEY_ROTATED,
                    recovered=True,
                    summary="Rotasi Kunci karena Kuota Habis (Rate Limit)",
                    details=f"Kunci sebelumnya mencapai batas kuota. Beralih ke kunci cadangan ({next_key[:6]}***).",
                    new_key=next_key,
                )

            # Jika kunci tunggal, coba downgrade model ke yang kuotanya lebih besar atau cooldown
            if attempt < self.max_auto_retries:
                # Periksa apakah ada instruksi retry-after
                retry_match = re.search(r"retry[- ]after[:\s]+(\d+)", str(exc).lower())
                wait_sec = min(int(retry_match.group(1)), 15) if retry_match else (2.0 * attempt)
                time.sleep(wait_sec)
                return HealingResult(
                    action=HealingAction.RETRY,
                    recovered=True,
                    summary="Menunggu Cooldown Kuota",
                    details=f"Rate limit terdeteksi. Sistem menunggu {wait_sec:.1f} detik sebelum mencoba ulang.",
                    retry_delay_seconds=wait_sec,
                )

            # Jika tetap 429 setelah retry, coba cascade fallback model atau provider
            model_fall = self._try_model_fallback(agent)
            if model_fall:
                return model_fall

            prov_fall = self._try_provider_fallback(agent)
            if prov_fall:
                return prov_fall

            return HealingResult(
                action=HealingAction.NEEDS_USER_INPUT,
                recovered=False,
                summary="Kuota API Habis (Rate Limit)",
                details="Kuota API Gemini habis. Tunggu beberapa saat, beralih ke Ollama, atau masukkan kunci baru.",
            )

        # -------------------------------------------------------------
        # Skenario 3: Model Not Found / Unsupported (404)
        # -------------------------------------------------------------
        if error_cat == "model_unsupported":
            model_fall = self._try_model_fallback(agent)
            if model_fall:
                return model_fall

        # -------------------------------------------------------------
        # Skenario 4: Session / History Corrupt / Token Limit
        # -------------------------------------------------------------
        if error_cat == "session_corrupt":
            repaired = self.sanitize_session_history(agent, session)
            if repaired:
                return HealingResult(
                    action=HealingAction.HISTORY_REPAIRED,
                    recovered=True,
                    summary="Perbaikan Riwayat Sesi (History Sanitizer)",
                    details="Ditemukan desinkronisasi giliran percakapan atau batas token. Riwayat telah dibersihkan secara otomatis.",
                )

        # -------------------------------------------------------------
        # Skenario 5: Network Transient / 503 / Timeout
        # -------------------------------------------------------------
        if error_cat == "network_transient":
            if attempt <= self.max_auto_retries:
                backoff = 2.0 ** attempt  # 2s, 4s, 8s
                agent_logger.log_info(
                    "session_healer",
                    f"Koneksi jaringan terputus/timeout. Melakukan retry dalam {backoff} detik (Percobaan {attempt}/{self.max_auto_retries})",
                )
                time.sleep(backoff)
                return HealingResult(
                    action=HealingAction.RETRY,
                    recovered=True,
                    summary="Retry Koneksi Jaringan",
                    details=f"Gangguan jaringan sementara. Mencoba ulang otomatis setelah {backoff:.1f} detik.",
                    retry_delay_seconds=backoff,
                )

        # Error yang tidak dapat dipulihkan secara otomatis
        return HealingResult(
            action=HealingAction.UNRECOVERABLE,
            recovered=False,
            summary="Kesalahan Tidak Dapat Dipulihkan Otomatis",
            details=str(exc),
        )

    def _try_model_fallback(self, agent: Any) -> Optional[HealingResult]:
        """Mencoba mendowngrade model Gemini ke versi yang lebih stabil sesuai cascade."""
        curr = getattr(agent, "model_name", "")
        if curr in GEMINI_FALLBACK_CASCADE:
            idx = GEMINI_FALLBACK_CASCADE.index(curr)
            if idx + 1 < len(GEMINI_FALLBACK_CASCADE):
                next_model = GEMINI_FALLBACK_CASCADE[idx + 1]
                agent.model_name = next_model
                config_manager.save_gemini_model(next_model)
                if hasattr(agent, "_init_chat_session"):
                    agent._init_chat_session()
                agent_logger.log_info(
                    "session_healer",
                    f"Model fallback cascade: {curr} -> {next_model}",
                )
                return HealingResult(
                    action=HealingAction.MODEL_FALLBACK,
                    recovered=True,
                    summary=f"Model Diturunkan ke {next_model}",
                    details=f"Model '{curr}' bermasalah. Sistem otomatis beralih ke model cadangan '{next_model}'.",
                    new_model=next_model,
                )
        return None

    def _try_provider_fallback(self, agent: Any) -> Optional[HealingResult]:
        """Mencoba beralih ke provider lokal (Ollama) atau Groq Cloud jika Gemini gagal total."""
        # 1. Coba Ollama lokal terlebih dahulu jika server berjalan
        ollama_models = []
        if hasattr(agent, "_pindai_model_ollama"):
            try:
                ollama_models = agent._pindai_model_ollama()
            except Exception:
                pass

        if ollama_models:
            chosen = config_manager.get_ollama_model()
            if chosen not in ollama_models and ollama_models:
                chosen = ollama_models[0]
            config_manager.save_provider("ollama")
            config_manager.save_ollama_model(chosen)
            agent.provider = "ollama"
            agent.model_name = chosen
            agent_logger.log_info(
                "session_healer",
                f"Failover provider berhasil dialihkan ke Ollama lokal: {chosen}",
            )
            return HealingResult(
                action=HealingAction.PROVIDER_FALLBACK,
                recovered=True,
                summary="Dialihkan ke Provider Lokal (Ollama)",
                details=f"Gemini API tidak dapat diakses. Sistem otomatis beralih ke model lokal '{chosen}' via Ollama.",
                new_provider="ollama",
                new_model=chosen,
            )

        # 2. Coba Groq jika ada API key
        groq_key = config_manager.get_groq_api_key()
        if groq_key:
            groq_m = config_manager.get_groq_model()
            config_manager.save_provider("groq")
            agent.provider = "groq"
            agent.model_name = groq_m
            agent_logger.log_info(
                "session_healer",
                f"Failover provider dialihkan ke Groq Cloud: {groq_m}",
            )
            return HealingResult(
                action=HealingAction.PROVIDER_FALLBACK,
                recovered=True,
                summary="Dialihkan ke Groq Cloud",
                details=f"Gemini API gagal. Sistem beralih ke Groq Cloud ({groq_m}).",
                new_provider="groq",
                new_model=groq_m,
            )

        return None

    def sanitize_session_history(self, agent: Any, session: Any) -> bool:
        """Membersihkan dan memperbaiki urutan riwayat percakapan yang rusak."""
        if not session or not hasattr(session, "ui_messages"):
            return False

        # Pastikan tidak ada pesan kosong atau urutan yang melanggar user/model
        cleaned = []
        last_type = None
        for msg in session.ui_messages:
            m_type = getattr(msg, "msg_type", "")
            m_text = getattr(msg, "text", "")
            if not m_text and not getattr(msg, "tool_name", ""):
                continue
            if m_type == "user" and last_type == "user":
                # Gabungkan dua pesan user berturut-turut untuk menjaga turn sequence
                if cleaned:
                    cleaned[-1].text = f"{cleaned[-1].text}\n{m_text}"
                continue
            cleaned.append(msg)
            last_type = m_type

        # Pangkas jika terlalu panjang (lebih dari 40 percakapan)
        if len(cleaned) > 40:
            cleaned = cleaned[-25:]

        session.ui_messages = cleaned

        # Rebuild chat session instance in-memory
        if hasattr(agent, "_init_chat_session"):
            try:
                agent._init_chat_session()
                return True
            except Exception as exc:
                agent_logger.log_error("session_healer.sanitize", f"Gagal rebuild chat: {exc}")
                return False
        return True


# Global singleton instance
session_healer = InSessionHealer()

