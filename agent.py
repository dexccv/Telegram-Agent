"""Modul logika Agent Gemini dan tool calling loop interaktif dengan memori & sesi persisten.

Menggunakan SDK resmi google-genai untuk auto-detect model yang tersedia,
menjalankan obrolan multi-turn dengan riwayat sesi tersimpan di disk,
menyimpan fakta ke memori jangka panjang, serta mengeksekusi function calling loop
dengan notifikasi event status ke antarmuka terminal.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional
from google import genai
from google.genai import types

from config import config_manager
from logger import agent_logger
from memory import memory_manager
from session_manager import Session, SessionMessage, session_manager
from tools import AVAILABLE_TOOLS, OPENAI_TOOLS_SCHEMA, TOOL_CALLABLES


def _build_http_options() -> Optional[types.HttpOptions]:
    """Membuat HttpOptions jika GEMINI_BASE_URL (misal: Omniroute) disetel."""
    base_url = config_manager.get_base_url()
    if base_url:
        clean_url = base_url.rstrip("/")
        if clean_url.endswith("/v1"):
            clean_url = clean_url[:-3]
        return types.HttpOptions(base_url=clean_url)
    return None


def fetch_omniroute_models(base_url: str, api_key: str) -> list[dict[str, Any]]:
    """Memindai model yang tersedia di Omniroute melalui endpoint /v1/models."""
    try:
        clean = base_url.rstrip("/")
        if clean.endswith("/v1"):
            clean = clean[:-3]
        url = clean + "/v1/models"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            models = [
                {
                    "id": "auto",
                    "raw_name": "auto",
                    "display_name": "Omniroute Auto (Rekomendasi)",
                    "description": "Otomatis memilih model terbaik di Omniroute.",
                    "input_token_limit": 1000000,
                    "output_token_limit": 65535,
                }
            ]
            for m in data.get("data", []):
                mid = m.get("id", "")
                if not mid or mid == "auto":
                    continue
                name = m.get("name") or mid
                desc = f"Provider: {m.get('owned_by', 'omniroute')}"
                models.append({
                    "id": mid,
                    "raw_name": mid,
                    "display_name": name,
                    "description": desc,
                    "input_token_limit": m.get("max_input_tokens") or 1000000,
                    "output_token_limit": m.get("max_output_tokens") or 65535,
                })
            return models
    except Exception as exc:
        agent_logger.log_error("agent.fetch_omniroute_models", f"Gagal memindai model Omniroute: {exc}")
        return [
            {
                "id": "auto",
                "raw_name": "auto",
                "display_name": "Omniroute Auto (Rekomendasi)",
                "description": "Otomatis memilih model terbaik di Omniroute.",
                "input_token_limit": 1000000,
                "output_token_limit": 65535,
            },
            {
                "id": "auto/best-coding",
                "raw_name": "auto/best-coding",
                "display_name": "Omniroute Best Coding",
                "description": "Rute model koding terbaik di Omniroute.",
                "input_token_limit": 1000000,
                "output_token_limit": 65535,
            },
            {
                "id": "auto/best-fast",
                "raw_name": "auto/best-fast",
                "display_name": "Omniroute Best Fast",
                "description": "Rute model cepat di Omniroute.",
                "input_token_limit": 1000000,
                "output_token_limit": 65535,
            },
        ]


def fetch_available_models(api_key: Optional[str] = None) -> list[dict[str, Any]]:
    """Mendapatkan daftar model yang kompatibel secara dinamis sesuai provider aktif."""
    provider = config_manager.get_provider()
    if provider == "omniroute":
        omni_key = api_key or config_manager.get_omni_api_key() or ""
        base_url = config_manager.get_omni_base_url()
        return fetch_omniroute_models(base_url, omni_key)

    if provider == "groq":
        return [
            {
                "id": "openai/gpt-oss-120b",
                "raw_name": "openai/gpt-oss-120b",
                "display_name": "OpenAI GPT OSS 120B (Terbesar & Cerdas ⚡)",
                "description": "Model 120B OpenAI generasi terbaru di Groq, sangat cerdas & respons ~0.8s.",
                "input_token_limit": 131072,
                "output_token_limit": 65536,
            },
            {
                "id": "openai/gpt-oss-20b",
                "raw_name": "openai/gpt-oss-20b",
                "display_name": "OpenAI GPT OSS 20B (Ultra Fast ~0.4s)",
                "description": "Model 20B OpenAI berkecepatan tinggi dan pintar di Groq LPU.",
                "input_token_limit": 131072,
                "output_token_limit": 65536,
            },
            {
                "id": "qwen/qwen3.8-27b",
                "raw_name": "qwen/qwen3.8-27b",
                "display_name": "Qwen 3.8 27B (Alibaba Cloud)",
                "description": "Model Qwen 27B handal untuk penalaran dan instruksi teks.",
                "input_token_limit": 131072,
                "output_token_limit": 16384,
            },
            {
                "id": "llama-3.3-70b-versatile",
                "raw_name": "llama-3.3-70b-versatile",
                "display_name": "Llama 3.3 70B Versatile",
                "description": "Model 70B Meta Llama 3.3 di Groq.",
                "input_token_limit": 128000,
                "output_token_limit": 32768,
            },
        ]

    clean_key = (api_key or config_manager.get_gemini_api_key() or "").strip()
    http_opts = _build_http_options()
    client = genai.Client(api_key=clean_key, http_options=http_opts) if http_opts else genai.Client(api_key=clean_key)
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

        if not filtered_models:
            filtered_models = [
                {
                    "id": "gemini-2.5-flash",
                    "raw_name": "gemini-2.5-flash",
                    "display_name": "Gemini 2.5 Flash",
                    "description": "Model cepat dan efisien bawaan Gemini.",
                    "input_token_limit": 1048576,
                    "output_token_limit": 8192,
                },
                {
                    "id": "gemini-3-flash-preview",
                    "raw_name": "gemini-3-flash-preview",
                    "display_name": "Gemini 3 Flash",
                    "description": "Model Gemini 3 generasi terbaru.",
                    "input_token_limit": 1048576,
                    "output_token_limit": 8192,
                },
                {
                    "id": "auto/gemini",
                    "raw_name": "auto/gemini",
                    "display_name": "Omniroute Auto Gemini",
                    "description": "Rute otomatis Gemini via Omniroute.",
                    "input_token_limit": 1000000,
                    "output_token_limit": 65535,
                },
            ]

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
        return [
            {
                "id": "gemini-2.5-flash",
                "raw_name": "gemini-2.5-flash",
                "display_name": "Gemini 2.5 Flash",
                "description": "Model cepat dan efisien bawaan Gemini.",
                "input_token_limit": 1048576,
                "output_token_limit": 8192,
            },
            {
                "id": "gemini-3-flash-preview",
                "raw_name": "gemini-3-flash-preview",
                "display_name": "Gemini 3 Flash",
                "description": "Model Gemini 3 generasi terbaru.",
                "input_token_limit": 1048576,
                "output_token_limit": 8192,
            },
            {
                "id": "auto/gemini",
                "raw_name": "auto/gemini",
                "display_name": "Omniroute Auto Gemini",
                "description": "Rute otomatis Gemini via Omniroute.",
                "input_token_limit": 1000000,
                "output_token_limit": 65535,
            },
        ]


def pindai_model_ollama(base_url: Optional[str] = None) -> list[str]:
    r"""Memindai daftar model lokal yang tersedia di server Ollama (dengan fallback disk D:\.ollama)."""
    url_base = (base_url or config_manager.get_ollama_base_url()).rstrip("/")
    url_native = url_base[:-3] if url_base.endswith("/v1") else url_base
    endpoint = f"{url_native}/api/tags"

    daftar = []
    try:
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Terminal-Agent"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            daftar = [m.get("name", "") for m in models if m.get("name")]
    except Exception as exc:
        agent_logger.log_error("agent.pindai_model_ollama", f"Gagal membaca model dari API Ollama: {exc}")

    if daftar:
        return daftar

    try:
        jalur_models = Path(config_manager.get_ollama_models_path())
        manifests_dir = jalur_models / "manifests"
        if manifests_dir.exists() and manifests_dir.is_dir():
            for root, dirs, files in os.walk(str(manifests_dir)):
                for f in files:
                    p = Path(root) / f
                    rel = p.relative_to(manifests_dir)
                    parts = rel.parts
                    if len(parts) >= 2:
                        model = parts[-2]
                        tag = parts[-1]
                        nama_m = f"{model}:{tag}"
                        if nama_m not in daftar:
                            daftar.append(nama_m)
    except Exception:
        pass

    return daftar if daftar else ["qwen2.5-coder:7b", "llama3.2"]


def ensure_ollama_running(base_url: str = "http://localhost:11434", timeout: float = 6.0) -> bool:
    """Memeriksa apakah server Ollama aktif; jika belum, otomatis menyalakan server Ollama di latar belakang."""
    check_url = base_url.replace("/v1", "").rstrip("/") + "/api/tags"
    try:
        req = urllib.request.Request(check_url, headers={"User-Agent": "Terminal-Agent/HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as _:
            return True
    except Exception:
        pass

    try:
        models_path = getattr(config_manager, "get_ollama_models_path", lambda: r"D:\.ollama\models")() or r"D:\.ollama\models"
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(models_path)
        env["OLLAMA_HOST"] = "127.0.0.1:11434"

        ollama_bin = "ollama"
        custom_bin = r"C:\Users\HP\AppData\Local\Programs\Ollama\ollama.exe"
        if os.path.exists(custom_bin):
            ollama_bin = custom_bin

        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200 | 0x08000000
        subprocess.Popen(
            [ollama_bin, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )

        t_start = time.time()
        while time.time() - t_start < timeout:
            try:
                req = urllib.request.Request(check_url, headers={"User-Agent": "Terminal-Agent/HealthCheck"})
                with urllib.request.urlopen(req, timeout=1.0) as _:
                    agent_logger.log_info("agent.ollama", f"Server Ollama berhasil dinyalakan otomatis ({round(time.time() - t_start, 2)}s).")
                    return True
            except Exception:
                time.sleep(0.5)
    except Exception as exc:
        agent_logger.log_error("agent.ollama", f"Gagal menjalankan server Ollama otomatis: {exc}")
    return False


class GeminiAgent:
    """Agent Gemini interaktif dengan loop tool calling otomatis, memori jangka panjang, dan sesi persisten."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> None:
        self.provider: str = config_manager.get_provider()
        self.api_key: str = (api_key or config_manager.get_api_key() or "").strip()
        self.model_name: str = (model_name or config_manager.get_model() or "auto").strip()
        self.session: Session = session or session_manager.get_or_create_active_session(
            model_name=self.model_name
        )
        if not self.session.model_name:
            self.session.model_name = self.model_name

        self.chat = None
        if self.provider == "gemini":
            http_opts = _build_http_options()
            self.client: Optional[genai.Client] = genai.Client(api_key=self.api_key, http_options=http_opts) if http_opts else genai.Client(api_key=self.api_key)
            self._init_chat_session()
        else:
            self.client = None

    def _init_chat_session(self) -> None:
        """Membuat instance chat session baru dengan deklarasi tools, system instruction, dan riwayat sesi."""
        if self.provider != "gemini":
            self.chat = None
            return

        if not self.client:
            gemini_key = config_manager.get_gemini_api_key() or self.api_key
            if not gemini_key:
                self.chat = None
                return
            http_opts = _build_http_options()
            self.client = genai.Client(api_key=gemini_key, http_options=http_opts) if http_opts else genai.Client(api_key=gemini_key)

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
        self.provider = config_manager.get_provider()
        if session.model_name:
            self.model_name = session.model_name
        if self.provider == "omniroute" and not (self.model_name.startswith("auto") or "/" in self.model_name):
            self.model_name = config_manager.get_omni_model() or "auto"
        elif self.provider == "gemini" and ("/" in self.model_name or self.model_name == "auto"):
            self.model_name = config_manager.get_gemini_model() or "gemini-2.5-flash"
        elif self.provider == "ollama" and (self.model_name.startswith("gemini-") or self.model_name == "auto"):
            self.model_name = config_manager.get_ollama_model() or "qwen2.5-coder:7b"
        session.model_name = self.model_name
        session_manager.set_active_session_id(session.session_id)
        self._init_chat_session()
        agent_logger.log_info(
            "agent.switch_session",
            f"Beralih ke sesi: {session.session_id} ('{session.title}') [Provider: {self.provider}, Model: {self.model_name}]",
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

        # Fast path intent detection untuk perintah kontrol laptop langsung (hanya jika bukan instruksi majemuk)
        msg_lower = message.strip().lower()
        kata_sambung = [" dan ", " lalu ", " serta ", " sambil ", " kemudian ", " setelah itu ", " terus ", "\n", ";"]
        is_compound = any(w in msg_lower for w in kata_sambung)
        if ("putar" in msg_lower or "play" in msg_lower) and ("volume" in msg_lower or "suara" in msg_lower):
            is_compound = True
        if "pdf" in msg_lower or "dokumen" in msg_lower:
            is_compound = True

        if not is_compound:
            # 1. Menutup aplikasi
            if msg_lower.startswith("tutup aplikasi ") or msg_lower.startswith("tutup ") or msg_lower.startswith("close "):
                parts = message.strip().split(maxsplit=2 if msg_lower.startswith("tutup aplikasi ") else 1)
                target_app = parts[-1].strip().strip('"').strip("'")
                if target_app:
                    fn_tutup = AVAILABLE_TOOLS.get("close_application")
                    if fn_tutup:
                        if on_tool_call:
                            on_tool_call("close_application", {"app_name_or_pid": target_app})
                        res = str(fn_tutup(target_app))
                        if on_tool_result:
                            on_tool_result("close_application", res)
                        self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                        session_manager.save_session(self.session)
                        return res

            # 2. Buka kamera webcam & foto
            if any(k in msg_lower for k in ["buka kamera", "ambil foto", "foto kamera", "capture kamera", "foto webcam", "kamera laptop"]):
                fn_cam = AVAILABLE_TOOLS.get("capture_camera")
                if fn_cam:
                    if on_tool_call:
                        on_tool_call("capture_camera", {"output_path": "kamera_capture.jpg"})
                    res = str(fn_cam("kamera_capture.jpg"))
                    if on_tool_result:
                        on_tool_result("capture_camera", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 3. Status sistem / hardware
            if any(k in msg_lower for k in ["status sistem", "persentase sistem", "persentase penyimpanan", "persentase baterai", "cek baterai", "cek penyimpanan", "cek ram", "cek cpu", "cek storage"]):
                fn_stat = AVAILABLE_TOOLS.get("get_system_status")
                if fn_stat:
                    if on_tool_call:
                        on_tool_call("get_system_status", {})
                    res = str(fn_stat())
                    if on_tool_result:
                        on_tool_result("get_system_status", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 4. Buka aplikasi desktop / YouTube / URL
            if (msg_lower.startswith("buka ") or msg_lower.startswith("open ") or "buka chrome" in msg_lower or "buka youtube" in msg_lower or (("putar " in msg_lower or "play " in msg_lower) and ("youtube" in msg_lower or "yt" in msg_lower))) and not ("kamera" in msg_lower or "webcam" in msg_lower):
                if ("youtube" in msg_lower or "yt" in msg_lower) and ("putar" in msg_lower or "play" in msg_lower):
                    fn_yt = AVAILABLE_TOOLS.get("play_youtube_video")
                    if fn_yt:
                        q_yt = message.strip()
                        for w in ["putar", "putarkan", "play", "lagu", "video", "musik", "di", "pada", "youtube", "yt", "tolong", "coba"]:
                            q_yt = re.sub(r"\b" + w + r"\b", "", q_yt, flags=re.IGNORECASE).strip()
                        if on_tool_call:
                            on_tool_call("play_youtube_video", {"video_id_or_url": q_yt})
                        res = str(fn_yt(q_yt))
                        if on_tool_result:
                            on_tool_result("play_youtube_video", res)
                        self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                        session_manager.save_session(self.session)
                        return res

                fn_open = AVAILABLE_TOOLS.get("open_application")
                if fn_open:
                    if on_tool_call:
                        on_tool_call("open_application", {"app_or_query": message.strip()})
                    res = str(fn_open(message.strip()))
                    if on_tool_result:
                        on_tool_result("open_application", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 5. Atur volume laptop
            if any(k in msg_lower for k in ["atur volume", "set volume", "ganti volume", "ubah volume", "volume laptop", "besarkan volume", "naikkan volume", "kecilkan volume", "turunkan volume", "mute", "unmute", "senyap"]):
                m_vol = re.search(r"(\+?\-?\d+%?|mute|unmute|senyap)", msg_lower)
                vol_arg = m_vol.group(1) if m_vol else "status"
                if "naik" in msg_lower or "besar" in msg_lower:
                    vol_arg = "+10"
                elif "turun" in msg_lower or "kecil" in msg_lower:
                    vol_arg = "-10"
                elif any(w in msg_lower for w in ["unmute", "nyalakan suara", "hidupkan suara"]):
                    vol_arg = "unmute"
                elif any(w in msg_lower for w in ["mute", "senyap", "matikan suara"]):
                    vol_arg = "mute"
                fn_vol = AVAILABLE_TOOLS.get("set_volume")
                if fn_vol:
                    if on_tool_call:
                        on_tool_call("set_volume", {"level": vol_arg})
                    res = str(fn_vol(vol_arg))
                    if on_tool_result:
                        on_tool_result("set_volume", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 6. Kontrol musik / pemutar lagu (Play, Pause, Next, Prev, Stop HANYA jika bukan query lagu spesifik)
            bukan_query_spesifik = not ("youtube" in msg_lower or "yt" in msg_lower or len(msg_lower.split()) > 3)
            if bukan_query_spesifik and any(k in msg_lower for k in ["pause lagu", "jeda lagu", "play lagu", "putar lagu", "lanjut lagu", "stop lagu", "berhenti lagu", "next lagu", "lagu berikutnya", "prev lagu", "lagu sebelumnya", "pause musik", "play musik"]):
                act_media = "play_pause"
                if "next" in msg_lower or "berikutnya" in msg_lower:
                    act_media = "next"
                elif "prev" in msg_lower or "sebelumnya" in msg_lower:
                    act_media = "prev"
                elif "stop" in msg_lower or "berhenti" in msg_lower:
                    act_media = "stop"
                elif "pause" in msg_lower or "jeda" in msg_lower:
                    act_media = "pause"
                elif "play" in msg_lower or "putar" in msg_lower or "lanjut" in msg_lower:
                    act_media = "play"
                fn_med = AVAILABLE_TOOLS.get("media_control")
                if fn_med:
                    if on_tool_call:
                        on_tool_call("media_control", {"action": act_media})
                    res = str(fn_med(act_media))
                    if on_tool_result:
                        on_tool_result("media_control", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 7. Screenshot
            if any(k in msg_lower for k in ["screenshot", "screen capture", "capture layar", "tangkapan layar", "foto layar", "ss laptop", "ss layar"]):
                fn_ss = AVAILABLE_TOOLS.get("capture_screen")
                if fn_ss:
                    if on_tool_call:
                        on_tool_call("capture_screen", {"output_path": "screen_capture.png"})
                    res = str(fn_ss("screen_capture.png"))
                    if on_tool_result:
                        on_tool_result("capture_screen", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

            # 8. Kunci Layar / Lock Laptop (Ctrl + L)
            if any(k in msg_lower for k in ["kunci laptop", "lock laptop", "kunci layar", "lock screen", "kunci pc", "lock pc", "ctrl + l", "ctrl+l"]):
                fn_lock = AVAILABLE_TOOLS.get("lock_laptop")
                if fn_lock:
                    if on_tool_call:
                        on_tool_call("lock_laptop", {})
                    res = str(fn_lock())
                    if on_tool_result:
                        on_tool_result("lock_laptop", res)
                    self.session.ui_messages.append(SessionMessage(msg_type="agent", text=res))
                    session_manager.save_session(self.session)
                    return res

        self.provider = config_manager.get_provider()
        if self.provider == "groq":
            return self._send_message_groq(message, on_tool_call, on_tool_result)
        elif self.provider == "omniroute":
            return self._send_message_omniroute(message, on_tool_call, on_tool_result)
        elif self.provider == "ollama":
            return self._send_message_ollama(message, on_tool_call, on_tool_result)

        if not self.chat:
            self._init_chat_session()

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

    def _send_message_openai_compatible(
        self,
        target_url: str,
        headers: dict[str, str],
        model_name: str,
        message: str,
        provider_label: str,
        timeout: int = 45,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        persistent_memory = memory_manager.format_for_system_instruction()
        system_instruction = (
            f"Anda adalah AI Agent terminal profesional dan cerdas bernama Terminal Agent (berbasis {provider_label}). "
            "Anda memiliki akses PENUH ke sistem laptop pengguna. "
            "Gunakan tool/fungsi yang tersedia untuk mengeksekusi perintah kontrol laptop pengguna seperti: "
            "mengatur volume (set_volume), kontrol musik/lagu/YouTube/Spotify (media_control), "
            "membuka aplikasi desktop atau browser (open_application), "
            "menutup aplikasi atau proses (close_application), "
            "mencari dan memutar video di YouTube (search_youtube_videos, play_youtube_video), "
            "mengambil screenshot layar laptop (capture_screen), mengambil foto webcam (capture_camera), "
            "melihat tab browser yang terbuka (get_open_browser_tabs), "
            "membaca status CPU/RAM/Baterai/Storage (get_system_status), "
            "membaca/menulis berkas, menjalankan perintah terminal aman (run_command), atau menyimpan memori. "
            "Berikan jawaban to-the-point, tepat sasaran, faktual, dan teknis.\n"
            f"{persistent_memory}"
        )

        messages = [{"role": "system", "content": system_instruction}]
        for m in self.session.ui_messages[-10:]:
            role = "user" if m.msg_type == "user" else "assistant"
            if m.text:
                messages.append({"role": role, "content": m.text})
        if not messages or messages[-1].get("content") != message:
            messages.append({"role": "user", "content": message})

        max_iterations = 10
        iteration = 0
        final_text = ""

        while iteration < max_iterations:
            iteration += 1
            payload = {
                "model": model_name,
                "messages": messages,
                "tools": OPENAI_TOOLS_SCHEMA,
                "tool_choice": "auto",
                "stream": False,
            }
            try:
                req = urllib.request.Request(
                    target_url,
                    headers=headers,
                    data=json.dumps(payload).encode("utf-8"),
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode())

                choices = data.get("choices", [])
                if not choices:
                    err = data.get("error", "Tidak ada respon.")
                    final_text = f"[Galat {provider_label}]: {err}"
                    break

                choice = choices[0]
                resp_msg = choice.get("message", {})
                tool_calls = resp_msg.get("tool_calls")

                if tool_calls:
                    messages.append(resp_msg)
                    for tc in tool_calls:
                        tc_id = tc.get("id", f"call_{iteration}")
                        fn_info = tc.get("function", {})
                        fn_name = fn_info.get("name", "")
                        raw_args = fn_info.get("arguments", "{}")
                        try:
                            fn_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except Exception:
                            fn_args = {}

                        agent_logger.log_info(f"agent.{provider_label.lower()}", f"Tool call: {fn_name} args={fn_args}")
                        if on_tool_call:
                            on_tool_call(fn_name, fn_args)

                        if fn_name in AVAILABLE_TOOLS:
                            try:
                                func = AVAILABLE_TOOLS[fn_name]
                                result_str = str(func(**fn_args))
                            except Exception as exc:
                                result_str = f"[GAGAL] Eksekusi {fn_name}: {exc}"
                        else:
                            result_str = f"[GAGAL] Tool '{fn_name}' tidak ditemukan."

                        preview = result_str[:120].replace("\n", " ") + "..." if len(result_str) > 120 else result_str.replace("\n", " ")
                        if on_tool_result:
                            on_tool_result(fn_name, preview)

                        self.session.ui_messages.append(
                            SessionMessage(
                                msg_type="tool",
                                tool_name=fn_name,
                                tool_args=fn_args,
                                tool_preview=preview,
                            )
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": result_str,
                        })
                    continue
                else:
                    final_text = resp_msg.get("content", "")
                    break
            except urllib.error.HTTPError as exc_http:
                detail_err = ""
                try:
                    body_str = exc_http.read().decode("utf-8", errors="ignore")
                    if body_str:
                        try:
                            body_json = json.loads(body_str)
                            detail_err = body_json.get("error", {}).get("message", body_str[:120])
                        except Exception:
                            detail_err = body_str[:120]
                except Exception:
                    detail_err = str(exc_http)

                if any(err_term in detail_err.lower() for err_term in ["tools", "tool_choice", "parsing failed", "failed_generation"]):
                    try:
                        fb_messages = []
                        for pmsg in messages:
                            if pmsg.get("role") == "tool":
                                fb_messages.append({"role": "user", "content": f"[Hasil Perkakas]: {pmsg.get('content')}"})
                            elif pmsg.get("role") == "assistant" and pmsg.get("tool_calls"):
                                fb_messages.append({"role": "assistant", "content": "Saya telah menjalankan perkakas yang diperlukan."})
                            else:
                                fb_messages.append(pmsg)
                        fallback_payload = {
                            "model": model_name,
                            "messages": fb_messages,
                            "stream": False,
                        }
                        req_fb = urllib.request.Request(
                            target_url,
                            headers=headers,
                            data=json.dumps(fallback_payload).encode("utf-8"),
                        )
                        with urllib.request.urlopen(req_fb, timeout=timeout) as resp_fb:
                            data_fb = json.loads(resp_fb.read().decode())
                            final_text = data_fb.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if final_text:
                                break
                    except Exception as fb_exc:
                        detail_err = f"{detail_err} | Fallback gagal: {fb_exc}"
                final_text = f"[Galat {provider_label} HTTP {getattr(exc_http, 'code', 'Error')}]: {detail_err or exc_http}"
                break
            except Exception as exc:
                final_text = f"[Galat {provider_label}]: {exc}"
                break

        if not final_text.strip():
            final_text = f"[Galat {provider_label}]: Tidak ada respon teks dari model '{model_name}'."

        self.session.ui_messages.append(SessionMessage(msg_type="agent", text=final_text))
        session_manager.save_session(self.session)
        return final_text

    def _send_message_groq(
        self,
        message: str,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        agent_logger.log_info(
            "agent.groq",
            f"Kirim prompt Groq: {message[:80]} (Model: {self.model_name})",
        )

        api_key = config_manager.get_groq_api_key() or self.api_key
        if not api_key:
            err = "[Galat Groq]: API Key Groq belum disetel. Dapatkan gratis di https://console.groq.com/keys lalu ketik: /provider groq <API_KEY>"
            self.session.ui_messages.append(SessionMessage(msg_type="agent", text=err))
            session_manager.save_session(self.session)
            return err

        target_url = "https://api.groq.com/openai/v1/chat/completions"
        model_name = self.model_name or "openai/gpt-oss-120b"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        return self._send_message_openai_compatible(
            target_url=target_url,
            headers=headers,
            model_name=model_name,
            message=message,
            provider_label="Groq",
            timeout=35,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )

    def _send_message_omniroute(
        self,
        message: str,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        agent_logger.log_info(
            "agent.omniroute",
            f"Kirim prompt Omniroute: {message[:80]} (Model: {self.model_name})",
        )

        base_url = config_manager.get_omni_base_url().rstrip("/")
        api_key = config_manager.get_omni_api_key() or self.api_key
        target_url = (base_url if base_url.endswith("/v1") else f"{base_url}/v1") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        return self._send_message_openai_compatible(
            target_url=target_url,
            headers=headers,
            model_name=self.model_name,
            message=message,
            provider_label="Omniroute",
            timeout=60,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )

    def _send_message_ollama(
        self,
        message: str,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        agent_logger.log_info(
            "agent.ollama",
            f"Kirim prompt Ollama: {message[:80]} (Model: {self.model_name})",
        )

        base_url = config_manager.get_ollama_base_url().rstrip("/")
        ensure_ollama_running(base_url)

        target_url = (base_url if base_url.endswith("/v1") else f"{base_url}/v1") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        return self._send_message_openai_compatible(
            target_url=target_url,
            headers=headers,
            model_name=self.model_name,
            message=message,
            provider_label="Ollama",
            timeout=120,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )


TerminalAgent = GeminiAgent

