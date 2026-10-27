"""Modul logika Agent Gemini dan tool calling loop interaktif dengan memori & sesi persisten.

Menggunakan SDK resmi google-genai untuk auto-detect model yang tersedia,
menjalankan obrolan multi-turn dengan riwayat sesi tersimpan di disk,
menyimpan fakta ke memori jangka panjang, serta mengeksekusi function calling loop
dengan notifikasi event status ke antarmuka terminal.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Optional
from google import genai
from google.genai import types

from logger import agent_logger
from memory import memory_manager
from session_manager import Session, SessionMessage, session_manager
from tools import AVAILABLE_TOOLS, TOOL_CALLABLES


def fetch_available_models(api_key: str) -> list[dict[str, Any]]:
    """Mendapatkan daftar model Gemini yang mendukung generateContent dan tool calling secara dinamis.

    Args:
        api_key: Kunci API Gemini untuk autentikasi.

    Returns:
        Daftar dictionary metadata model (id, display_name, description, token limit).

    Raises:
        Exception: Jika terjadi kesalahan autentikasi, jaringan, atau kuota.
    """
    clean_key = api_key.strip()
    client = genai.Client(api_key=clean_key)
    filtered_models: list[dict[str, Any]] = []

    try:
        model_list = client.models.list()
        for m in model_list:
            raw_name = getattr(m, "name", "")
            clean_id = raw_name.replace("models/", "") if raw_name.startswith("models/") else raw_name
            display_name = getattr(m, "display_name", "") or clean_id
            description = getattr(m, "description", "") or "Model resmi Gemini dari Google."
            actions = getattr(m, "supported_actions", []) or []

            # Filter model yang hanya mendukung generateContent dan bukan embedding/vision murni
            is_generate = False
            if actions:
                is_generate = any("generatecontent" in str(act).lower() for act in actions)
            else:
                is_generate = "gemini" in clean_id.lower()

            # Abaikan model embedding, aqa, atau model khusus yang tidak cocok untuk obrolan/tool
            ignored_keywords = ["embedding", "imagen", "aqa", "text-bison", "chat-bison"]
            if any(ign in clean_id.lower() for ign in ignored_keywords):
                continue

            if is_generate:
                filtered_models.append(
                    {
                        "id": clean_id,
                        "raw_name": raw_name,
                        "display_name": display_name,
                        "description": description.strip(),
                        "input_token_limit": getattr(m, "input_token_limit", None),
                        "output_token_limit": getattr(m, "output_token_limit", None),
                    }
                )

        # Urutkan model: prioritaskan seri terbaru (gemini-3) dan varian flash
        filtered_models.sort(
            key=lambda x: (
                0 if "3" in x["id"] and "flash" in x["id"].lower() else (
                    1 if "flash" in x["id"].lower() else (
                        2 if "3" in x["id"] else 3
                    )
                ),
                x["id"].lower(),
            )
        )
        agent_logger.log_info(
            "agent.fetch_available_models",
            f"Berhasil menemukan {len(filtered_models)} model yang kompatibel.",
        )
        return filtered_models
    except Exception as exc:
        agent_logger.log_error(
            "agent.fetch_available_models",
            f"Gagal mendeteksi model dari API: {exc}",
        )
        raise exc


class GeminiAgent:
    """Agent Gemini interaktif dengan loop tool calling otomatis, memori jangka panjang, dan sesi persisten."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        session: Optional[Session] = None,
    ) -> None:
        self.api_key: str = api_key.strip()
        self.model_name: str = model_name.strip()
        self.client: genai.Client = genai.Client(api_key=self.api_key)
        self.session: Session = session or session_manager.get_or_create_active_session(
            model_name=self.model_name
        )
        # Pastikan model di session selaras jika belum ada model
        if not self.session.model_name:
            self.session.model_name = self.model_name

        self.chat = None
        self._init_chat_session()

    def _init_chat_session(self) -> None:
        """Membuat instance chat session baru dengan deklarasi tools, system instruction, dan riwayat sesi."""
        persistent_memory = memory_manager.format_for_system_instruction()

        system_instruction = (
            "Anda adalah AI Agent terminal profesional dan cerdas bernama gemini-terminal-agent. "
            "Berikan jawaban to-the-point, tepat sasaran, faktual, dan teknis. "
            "Jangan gunakan salam berlebihan atau basa-basi generik. Dilarang keras menggunakan emoji apapun. "
            "Gunakan tool yang tersedia kapan pun pengguna meminta manipulasi berkas, direktori, shell, atau memori.\n"
            f"{persistent_memory}"
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=TOOL_CALLABLES,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2,
        )

        # Rekonstruksi objek Content dari riwayat sesi tersimpan
        validated_history: list[types.Content] = []
        if self.session and self.session.history:
            for item in self.session.history:
                try:
                    content_obj = types.Content.model_validate(item)
                    validated_history.append(content_obj)
                except Exception as exc:
                    agent_logger.log_error(
                        "agent.init_chat_session",
                        f"Gagal memvalidasi riwayat turn sebelumnya: {exc}",
                    )

        self.chat = self.client.chats.create(
            model=self.model_name,
            config=config,
            history=validated_history if validated_history else None,
        )
        agent_logger.log_info(
            "agent.init_chat_session",
            f"Sesi chat diinisialisasi (Sesi ID: {self.session.session_id}, Judul: '{self.session.title}', Turns: {len(validated_history)}, Model: {self.model_name})",
        )

    def change_model(self, new_model_name: str) -> None:
        """Mengganti model aktif dengan tetap mempertahankan riwayat percakapan sesi ini."""
        self.model_name = new_model_name.strip()
        self.session.model_name = self.model_name
        self._sync_history_from_chat()
        session_manager.save_session(self.session)
        self._init_chat_session()
        agent_logger.log_info("agent.change_model", f"Model aktif dialihkan ke: {self.model_name}")

    def switch_session(self, session: Session) -> None:
        """Beralih ke sesi percakapan lain dan memuat seluruh riwayat serta konteksnya."""
        self.session = session
        if session.model_name:
            self.model_name = session.model_name
        session_manager.set_active_session_id(session.session_id)
        self._init_chat_session()
        agent_logger.log_info(
            "agent.switch_session",
            f"Beralih ke sesi: {session.session_id} ('{session.title}')",
        )

    def create_new_session(self, title: Optional[str] = None) -> Session:
        """Membuat sesi percakapan baru dan mengalihkannya sebagai sesi aktif."""
        self._sync_history_from_chat()
        session_manager.save_session(self.session)
        new_sess = session_manager.create_session(title=title, model_name=self.model_name)
        self.switch_session(new_sess)
        return new_sess

    def reset_chat(self) -> None:
        """Membersihkan riwayat dan memulai sesi percakapan baru yang segar."""
        self.create_new_session()

    def _sync_history_from_chat(self) -> None:
        """Mengekstrak riwayat Content dari instance Chat dan menyimpannya ke session."""
        if not self.chat:
            return
        try:
            raw_history = self.chat.get_history()
            self.session.history = [
                c.model_dump(mode="json", exclude_none=True) for c in raw_history
            ]
            self.session.updated_at = datetime.datetime.now().isoformat()
        except Exception as exc:
            agent_logger.log_error("agent.sync_history", f"Gagal sinkronisasi riwayat: {exc}")

    def send_message(
        self,
        message: str,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Mengirim pesan ke Gemini dan menjalankan loop eksekusi tool hingga respon final selesai.

        Menyimpan percakapan, panggilan tool, dan riwayat obrolan secara persisten.

        Args:
            message: Pesan teks dari pengguna.
            on_tool_call: Callback yang dipanggil saat model meminta eksekusi tool (nama, args).
            on_tool_result: Callback yang dipanggil setelah tool selesai dieksekusi (nama, preview).

        Returns:
            Teks respon final dari agent.
        """
        agent_logger.log_info(
            "agent.send_message",
            f"Mengirim pesan user: {message[:80]} (Sesi: {self.session.session_id}, Model: {self.model_name})",
        )

        # Catat pesan user ke daftar pesan UI sesi
        self.session.ui_messages.append(SessionMessage(msg_type="user", text=message))

        # Auto-update judul sesi jika masih berupa judul default
        if (
            self.session.title.startswith("Sesi ")
            or self.session.title in ["Sesi Baru", "Sesi Perdana", "Percakapan Baru"]
        ) and len(self.session.ui_messages) <= 2:
            auto_title = message.strip().replace("\n", " ")[:36]
            if auto_title:
                self.session.title = auto_title

        response = self.chat.send_message(message)
        max_tool_iterations = 15
        iteration = 0

        while response.function_calls and iteration < max_tool_iterations:
            iteration += 1
            parts_responses = []

            for call in response.function_calls:
                tool_name = call.name
                tool_args = call.args if isinstance(call.args, dict) else dict(call.args or {})

                agent_logger.log_info(
                    "agent.tool_loop",
                    f"Panggilan tool diminta: {tool_name} dengan argumen {tool_args}",
                )

                if on_tool_call:
                    on_tool_call(tool_name, tool_args)

                # Eksekusi fungsi tool yang terdaftar
                if tool_name in AVAILABLE_TOOLS:
                    try:
                        func = AVAILABLE_TOOLS[tool_name]
                        result_str = str(func(**tool_args))
                    except Exception as exc:
                        result_str = f"[GAGAL] Eksekusi tool {tool_name} error: {exc}"
                        agent_logger.log_error(
                            "agent.tool_loop",
                            f"Kesalahan internal pada tool {tool_name}: {exc}",
                        )
                else:
                    result_str = f"[GAGAL] Tool '{tool_name}' tidak dikenal."

                # Buat preview singkat untuk callback UI dan rekaman pesan
                preview = (
                    result_str[:120].replace("\n", " ") + "..."
                    if len(result_str) > 120
                    else result_str.replace("\n", " ")
                )

                if on_tool_result:
                    on_tool_result(tool_name, preview)

                # Catat pemanggilan tool ke UI messages sesi
                self.session.ui_messages.append(
                    SessionMessage(
                        msg_type="tool",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_preview=preview,
                    )
                )

                part = types.Part.from_function_response(
                    name=tool_name,
                    response={"result": result_str},
                )
                parts_responses.append(part)

            # Kirim kembali hasil tool response ke obrolan model
            response = self.chat.send_message(parts_responses)

        final_text = response.text or "(Tidak ada teks dalam respon)"
        agent_logger.log_info(
            "agent.send_message",
            f"Respon akhir diterima ({len(final_text)} karakter)",
        )

        # Catat respon agen ke UI messages sesi
        self.session.ui_messages.append(SessionMessage(msg_type="agent", text=final_text))

        # Sinkronisasi riwayat obrolan lengkap dan simpan ke disk
        self._sync_history_from_chat()
        session_manager.save_session(self.session)

        return final_text
