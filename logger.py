"""Sistem logging terstruktur dan perincian penanganan error untuk Gemini Terminal Agent.

Menyediakan rotasi log harian di ~/.gemini-agent/logs/agent-YYYY-MM-DD.log
dan formatting error detail untuk antarmuka terminal/UI tanpa emoji.
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import config_manager


@dataclass
class FormattedError:
    """Representasi terstruktur dari insiden kesalahan sistem."""

    symbol: str
    category: str
    exception_type: str
    message: str
    context: str
    active_model: str
    http_status: Optional[int]
    error_code: Optional[str]
    mitigation: str
    traceback_lines: list[str]

    def to_cli_string(self) -> str:
        """Menghasilkan teks berformat untuk ditampilkan di antarmuka terminal."""
        lines = [
            f"{self.symbol} [{self.category.upper()}] - {self.exception_type}",
            f"  Konteks      : {self.context}",
            f"  Model Aktif  : {self.active_model or 'Belum dipilih'}",
        ]
        if self.http_status is not None or self.error_code:
            lines.append(
                f"  Status API   : HTTP {self.http_status or '-'} | Kode: {self.error_code or '-'}"
            )
        lines.append(f"  Pesan Asli   : {self.message}")
        lines.append(f"  Saran Aksi   : {self.mitigation}")

        if self.traceback_lines:
            lines.append("  Traceback    :")
            for tb in self.traceback_lines:
                lines.append(f"    │ {tb}")
        return "\n".join(lines)


class AgentLogger:
    """Pengelola logger terstruktur berbasis file rotasi harian dan penangkap error."""

    def __init__(self) -> None:
        self.logs_dir: Path = config_manager.logs_dir
        self.current_date: str = ""
        self.logger: logging.Logger = logging.getLogger("gemini_terminal_agent")
        self.logger.setLevel(logging.DEBUG)
        self.file_handler: Optional[logging.FileHandler] = None
        self._ensure_handler()

    def _ensure_handler(self) -> None:
        """Menyesuaikan file handler jika tanggal telah berganti."""
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if today != self.current_date:
            self.current_date = today
            if self.file_handler:
                self.logger.removeHandler(self.file_handler)
                self.file_handler.close()

            log_file = self.logs_dir / f"agent-{today}.log"
            handler = logging.FileHandler(log_file, encoding="utf-8")
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)
            self.file_handler = handler

    def log_info(self, module: str, message: str) -> None:
        """Mencatat informasi reguler ke file log."""
        self._ensure_handler()
        self.logger.info(f"[{module}] {message}")

    def log_warning(self, module: str, message: str) -> None:
        """Mencatat peringatan ke file log."""
        self._ensure_handler()
        self.logger.warning(f"[{module}] {message}")

    def log_error(self, module: str, message: str) -> None:
        """Mencatat kesalahan ke file log."""
        self._ensure_handler()
        self.logger.error(f"[{module}] {message}")

    def log_critical(self, module: str, message: str) -> None:
        """Mencatat insiden kritis ke file log."""
        self._ensure_handler()
        self.logger.critical(f"[{module}] {message}")

    def diagnose_and_format_error(
        self,
        exc: Exception,
        context: str,
        active_model: str = "",
    ) -> FormattedError:
        """Mendiagnosa exception, mengelompokkan kategori, dan menyusun saran aksi teknis."""
        self._ensure_handler()
        exc_type = exc.__class__.__name__
        msg = str(exc)

        # Ekstraksi status HTTP dan error code jika berasal dari Google API SDK
        http_status: Optional[int] = getattr(exc, "code", None)
        if http_status is None:
            status_match = re.search(r"\b(4\d\d|5\d\d)\b", msg)
            if status_match:
                try:
                    http_status = int(status_match.group(1))
                except ValueError:
                    http_status = None

        error_code: Optional[str] = None
        code_match = re.search(
            r"(API_KEY_INVALID|PERMISSION_DENIED|RESOURCE_EXHAUSTED|NOT_FOUND|UNAVAILABLE|DEADLINE_EXCEEDED|INVALID_ARGUMENT)",
            msg,
        )
        if code_match:
            error_code = code_match.group(1)

        # Klasifikasi kategori dan rekomendasi perbaikan teknis
        category = "Kesalahan Sistem"
        symbol = "[X]"
        mitigation = "Periksa kembali konfigurasi dan coba jalankan ulang operasi."

        lower_msg = msg.lower()

        if (
            http_status in (400, 401, 403)
            and ("api_key" in lower_msg or "key" in lower_msg or error_code in ("API_KEY_INVALID", "PERMISSION_DENIED"))
        ) or "api_key" in lower_msg:
            category = "API Key Tidak Valid / Kedaluwarsa"
            symbol = "[!]"
            mitigation = (
                "Kunci API Gemini tidak valid, expired, atau tidak memiliki izin akses. "
                "Perbarui kunci melalui layar konfigurasi atau edit file ~/.gemini-agent/.env"
            )

        elif (
            http_status == 429
            or "quota" in lower_msg
            or "rate limit" in lower_msg
            or error_code == "RESOURCE_EXHAUSTED"
        ):
            category = "Kuota Habis / Rate Limit"
            symbol = "!!"
            retry_match = re.search(r"retry[- ]after[:\s]+(\d+)", lower_msg)
            retry_val = retry_match.group(1) if retry_match else "beberapa detik"
            mitigation = (
                f"Batas permintaan API tercapai (Rate Limit). Tunggu sekitar {retry_val} "
                "sebelum mengirim pesan berikutnya, atau beralih ke model dengan kuota lebih besar."
            )

        elif (
            http_status == 404
            or "not found" in lower_msg
            or "unsupported" in lower_msg
            or error_code == "NOT_FOUND"
        ):
            category = "Model Tidak Ditemukan / Tidak Mendukung Fitur"
            symbol = "◆"
            mitigation = (
                f"Model '{active_model}' tidak ditemukan atau tidak mendukung tool calling/generateContent. "
                "Gunakan perintah /model untuk memilih model resmi yang kompatibel."
            )

        elif (
            "connection" in lower_msg
            or "timeout" in lower_msg
            or "connecterror" in lower_msg
            or "ssl" in lower_msg
            or "network" in lower_msg
            or error_code in ("UNAVAILABLE", "DEADLINE_EXCEEDED")
        ):
            category = "Gangguan Jaringan / Koneksi Timeout"
            symbol = "[!]"
            mitigation = (
                "Koneksi ke server Gemini API gagal atau mengalami batas waktu habis (timeout). "
                "Periksa koneksi internet, proxy, atau konfigurasi firewall Anda."
            )

        elif "tool" in context.lower() or "command" in context.lower():
            category = "Kesalahan Eksekusi Tool"
            symbol = "◆"
            mitigation = (
                "Perintah shell atau operasi file gagal dijalankan. "
                "Periksa izin akses direktori, eksistensi file, atau sintaks perintah yang dikirim."
            )

        elif "json" in lower_msg or "parse" in lower_msg or "decode" in lower_msg:
            category = "Kesalahan Parse Respons SDK"
            symbol = "[X]"
            mitigation = (
                "Gagal memproses struktur payload dari SDK. "
                "Pastikan versi library google-genai sesuai dengan spesifikasi di requirements.txt."
            )

        # Persiapan Traceback (Top 3 baris ringkas atau lengkap saat debug)
        tb_list = traceback.format_exception(type(exc), exc, exc.__traceback__)
        is_debug = config_manager.is_debug()

        if is_debug:
            clean_tb = [line.rstrip() for line in tb_list]
        else:
            # Ambil 3 baris teratas yang representatif dari traceback
            raw_lines = [line.strip() for line in "".join(tb_list).splitlines() if line.strip()]
            clean_tb = raw_lines[-3:] if len(raw_lines) >= 3 else raw_lines

        formatted = FormattedError(
            symbol=symbol,
            category=category,
            exception_type=exc_type,
            message=msg,
            context=context,
            active_model=active_model,
            http_status=http_status,
            error_code=error_code,
            mitigation=mitigation,
            traceback_lines=clean_tb,
        )

        # Catat detail lengkap ke file log
        self.logger.error(
            f"EXC_OCCURRED | Kategori: {category} | Tipe: {exc_type} | Konteks: {context} | Model: {active_model} | Detail: {msg}"
        )
        return formatted


agent_logger = AgentLogger()
