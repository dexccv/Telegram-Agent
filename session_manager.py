"""Modul manajemen sesi percakapan persisten untuk Gemini Terminal Agent.

Menyimpan riwayat obrolan lengkap (termasuk function calling dan hasil tool)
ke file JSON di direktori ~/.gemini-agent/sessions/, memungkinkan pemulihan sesi,
beralih antar sesi percakapan, dan menjaga konteks penuh antar restart aplikasi.
"""

from __future__ import annotations

import datetime
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from config import config_manager
from logger import agent_logger


@dataclass
class SessionMessage:
    """Representasi satu pesan visual di antarmuka terminal."""
    msg_type: str  # "user", "agent", "tool", "system"
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_preview: str = ""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        return cls(
            msg_type=data.get("msg_type", "user"),
            text=data.get("text", ""),
            tool_name=data.get("tool_name", ""),
            tool_args=data.get("tool_args") or {},
            tool_preview=data.get("tool_preview", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class Session:
    """Data struktur lengkap untuk satu sesi percakapan."""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    model_name: str
    history: list[dict[str, Any]] = field(default_factory=list)  # Serialized types.Content
    ui_messages: list[SessionMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model_name": self.model_name,
            "history": self.history,
            "ui_messages": [m.to_dict() for m in self.ui_messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            session_id=data["session_id"],
            title=data.get("title", "Sesi Percakapan"),
            created_at=data.get("created_at", datetime.datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.datetime.now().isoformat()),
            model_name=data.get("model_name", "gemini-2.5-flash"),
            history=data.get("history", []) or [],
            ui_messages=[SessionMessage.from_dict(m) for m in data.get("ui_messages", [])],
        )


class SessionManager:
    """Mengelola file sesi percakapan di ~/.gemini-agent/sessions/."""

    def __init__(self) -> None:
        self.sessions_dir: Path = config_manager.sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return self.sessions_dir / f"{safe_id}.json"

    def generate_session_id(self) -> str:
        """Menghasilkan ID unik untuk sesi baru."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_suffix = uuid.uuid4().hex[:6]
        return f"sess_{timestamp}_{rand_suffix}"

    def list_sessions(self) -> list[dict[str, Any]]:
        """Mendaftar semua sesi tersimpan, diurutkan dari yang paling baru diperbarui."""
        sessions_summary: list[dict[str, Any]] = []
        if not self.sessions_dir.exists():
            return sessions_summary

        for filepath in self.sessions_dir.glob("*.json"):
            try:
                raw_text = filepath.read_text(encoding="utf-8")
                if not raw_text.strip():
                    continue
                data = json.loads(raw_text)
                sessions_summary.append({
                    "session_id": data.get("session_id", filepath.stem),
                    "title": data.get("title", "Sesi Tanpa Judul"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "model_name": data.get("model_name", "-"),
                    "message_count": len(data.get("ui_messages", [])),
                    "turn_count": len(data.get("history", [])),
                })
            except Exception as exc:
                agent_logger.log_error("session.list_sessions", f"Error membaca sesi {filepath.name}: {exc}")

        # Urutkan berdasarkan updated_at descending (terbaru di atas)
        sessions_summary.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions_summary

    def get_session(self, session_id: str) -> Optional[Session]:
        """Memuat sesi berdasarkan session_id."""
        path = self._get_session_path(session_id)
        if not path.exists():
            return None

        try:
            raw_text = path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
            return Session.from_dict(data)
        except Exception as exc:
            agent_logger.log_error("session.get_session", f"Gagal membaca sesi {session_id}: {exc}")
            return None

    def save_session(self, session: Session) -> None:
        """Menyimpan sesi ke disk secara persisten."""
        path = self._get_session_path(session.session_id)
        session.updated_at = datetime.datetime.now().isoformat()
        try:
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_path.replace(path)
            agent_logger.log_info(
                "session.save_session",
                f"Sesi '{session.session_id}' ({session.title}) berhasil disimpan. Total pesan: {len(session.ui_messages)}",
            )
        except Exception as exc:
            agent_logger.log_error("session.save_session", f"Gagal menyimpan sesi {session.session_id}: {exc}")

    def create_session(
        self,
        title: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Session:
        """Membuat sesi percakapan baru."""
        now_iso = datetime.datetime.now().isoformat()
        sess_id = self.generate_session_id()
        sess_title = title.strip() if title and title.strip() else f"Sesi {datetime.datetime.now().strftime('%d %b %H:%M')}"
        model = model_name or config_manager.get_model() or "gemini-2.5-flash"

        session = Session(
            session_id=sess_id,
            title=sess_title,
            created_at=now_iso,
            updated_at=now_iso,
            model_name=model,
            history=[],
            ui_messages=[],
        )
        self.save_session(session)
        self.set_active_session_id(sess_id)
        agent_logger.log_info("session.create_session", f"Sesi baru dibuat: {sess_id} ('{sess_title}')")
        return session

    def delete_session(self, session_id: str) -> bool:
        """Menghapus file sesi dari disk."""
        path = self._get_session_path(session_id)
        if path.exists():
            try:
                path.unlink()
                agent_logger.log_info("session.delete_session", f"Sesi '{session_id}' dihapus.")
                # Jika yang dihapus adalah sesi aktif, reset penunjuk aktif
                if self.get_active_session_id() == session_id:
                    self.set_active_session_id("")
                return True
            except Exception as exc:
                agent_logger.log_error("session.delete_session", f"Gagal menghapus sesi {session_id}: {exc}")
        return False

    def get_active_session_id(self) -> Optional[str]:
        """Mengambil ID sesi aktif terakhir dari config."""
        return config_manager.get_active_session_id()

    def set_active_session_id(self, session_id: str) -> None:
        """Menyimpan ID sesi aktif terakhir ke config."""
        config_manager.save_active_session_id(session_id)

    def get_or_create_active_session(self, model_name: Optional[str] = None) -> Session:
        """Mengembalikan sesi aktif terakhir, atau sesi terbaru, atau membuat baru jika belum ada."""
        active_id = self.get_active_session_id()
        if active_id:
            sess = self.get_session(active_id)
            if sess:
                agent_logger.log_info("session.get_or_create", f"Memulihkan sesi aktif: {active_id}")
                return sess

        # Cek apakah ada sesi lain yang tersimpan
        all_sessions = self.list_sessions()
        if all_sessions:
            most_recent_id = all_sessions[0]["session_id"]
            sess = self.get_session(most_recent_id)
            if sess:
                self.set_active_session_id(most_recent_id)
                agent_logger.log_info("session.get_or_create", f"Memulihkan sesi terbaru: {most_recent_id}")
                return sess

        # Jika sama sekali belum ada sesi, buat sesi awal
        return self.create_session(title="Sesi Perdana", model_name=model_name)

    def export_to_markdown(self, session: Session, target_path: Optional[str] = None) -> Path:
        """Mengekspor percakapan sesi ke format file Markdown."""
        if not target_path or not str(target_path).strip():
            clean_title = re.sub(r"[^\w\-_]", "_", session.title.lower())[:30].strip("_") or "percakapan"
            short_id = session.session_id[:8]
            target_path = f"ekspor_{clean_title}_{short_id}.md"

        jalur = Path(target_path)
        if not jalur.suffix:
            jalur = jalur.with_suffix(".md")

        baris = [
            f"# Ekspor Percakapan: {session.title}",
            f"- **ID Sesi**: `{session.session_id}`",
            f"- **Model**: `{session.model_name}`",
            f"- **Waktu Pembuatan**: {session.created_at[:19].replace('T', ' ')}",
            f"- **Terakhir Diperbarui**: {session.updated_at[:19].replace('T', ' ')}",
            "",
            "---",
            "",
        ]

        if session.ui_messages:
            for m in session.ui_messages:
                if m.msg_type == "user":
                    baris.append(f"### ❯ Anda\n\n{m.text}\n")
                elif m.msg_type == "agent":
                    baris.append(f"### ⌬ Agen AI\n\n{m.text}\n")
                elif m.msg_type == "tool":
                    baris.append(f"> ⚙ **[Tool]** `{m.tool_name}`: {m.tool_preview}\n")
                elif m.msg_type in ("error", "system"):
                    baris.append(f"> ℹ **[{m.msg_type.upper()}]** {m.text}\n")
        elif session.history:
            for h in session.history:
                role = "❯ Anda" if h.get("role") == "user" else "⌬ Agen AI"
                baris.append(f"### {role}\n\n{h.get('text', '')}\n")

        jalur.write_text("\n".join(baris), encoding="utf-8")
        agent_logger.log_info("session.export", f"Sesi '{session.session_id}' diekspor ke: {jalur.resolve()}")
        return jalur.resolve()


session_manager = SessionManager()
