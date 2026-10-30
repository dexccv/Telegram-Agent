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
from session_healer import session_healer
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


def _groq_fallback_models() -> list[dict[str, Any]]:
    """Daftar model resmi Groq fallback jika koneksi atau fetch API gagal."""
    return [
        {
            "id": "llama-3.3-70b-versatile",
            "raw_name": "llama-3.3-70b-versatile",
            "display_name": "Llama 3.3 70B Versatile (Groq)",
            "description": "Model 70B Meta Llama 3.3 unggulan di Groq LPU.",
            "input_token_limit": 128000,
            "output_token_limit": 32768,
        },
        {
            "id": "llama-3.1-8b-instant",
            "raw_name": "llama-3.1-8b-instant",
            "display_name": "Llama 3.1 8B Instant (Groq)",
            "description": "Model ultra cepat Llama 8B di Groq LPU.",
            "input_token_limit": 128000,
            "output_token_limit": 8192,
        },
        {
            "id": "mixtral-8x7b-32768",
            "raw_name": "mixtral-8x7b-32768",
            "display_name": "Mixtral 8x7B (Groq)",
            "description": "Mixtral MoE 8x7B di Groq LPU.",
            "input_token_limit": 32768,
            "output_token_limit": 32768,
        },
    ]


def fetch_groq_models(api_key: str) -> list[dict[str, Any]]:
    """Mengambil model yang aktif di Groq secara dinamis via endpoint /v1/models."""
    if not api_key:
        return _groq_fallback_models()
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Terminal-Agent",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            raw_models = data.get("data", [])
            models = []
            for m in raw_models:
                mid = m.get("id", "")
                if not mid:
                    continue
                # Filter model chat / non-whisper
                if "whisper" in mid.lower():
                    continue
                models.append({
                    "id": mid,
                    "raw_name": mid,
                    "display_name": f"{mid} (Groq)",
                    "description": f"Model Groq aktif: {m.get('owned_by', 'groq')}",
                    "input_token_limit": m.get("context_window", 131072),
                    "output_token_limit": 32768,
                })
            return models if models else _groq_fallback_models()
    except Exception as exc:
        agent_logger.log_error("agent.fetch_groq_models", f"Gagal fetch model Groq: {exc}")
        return _groq_fallback_models()


def fetch_available_models(api_key: Optional[str] = None) -> list[dict[str, Any]]:
    """Mendapatkan daftar model yang kompatibel secara dinamis sesuai provider aktif."""
    provider = config_manager.get_provider()
    if provider == "omniroute":
        omni_key = api_key or config_manager.get_omni_api_key() or ""
        base_url = config_manager.get_omni_base_url()
        return fetch_omniroute_models(base_url, omni_key)

    if provider == "groq":
        groq_key = (api_key or config_manager.get_groq_api_key() or "").strip()
        return fetch_groq_models(groq_key)

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

    return daftar if daftar else ["llama3.2:3b", "qwen2.5-coder:7b"]


def ensure_ollama_running(base_url: str = "http://localhost:11434", timeout: float = 12.0) -> bool:
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

        if os.name == "nt":
            ps_cmd = (
                f"$env:OLLAMA_MODELS = '{models_path}'; "
                f"$env:OLLAMA_HOST = '127.0.0.1:11434'; "
                f"Start-Process -FilePath '{ollama_bin}' -ArgumentList 'serve' -WindowStyle Hidden"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
        else:
            subprocess.Popen(
                [ollama_bin, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
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


def warmup_ollama_model_async(model_name: Optional[str] = None, base_url: Optional[str] = None) -> None:
    """Melakukan pre-warming model Ollama di latar belakang agar model sudah siap di RAM/VRAM dengan keep_alive."""
    import threading

    def _worker() -> None:
        try:
            m = model_name or config_manager.get_ollama_model() or "llama3.2:3b"
            b = (base_url or config_manager.get_ollama_base_url()).replace("/v1", "").rstrip("/")
            url = f"{b}/api/generate"
            payload = {
                "model": m,
                "prompt": "",
                "keep_alive": "60m",
            }
            req = urllib.request.Request(
                url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload).encode("utf-8"),
            )
            with urllib.request.urlopen(req, timeout=30):
                pass
            agent_logger.log_info("agent.ollama", f"Pre-warming model '{m}' berhasil (keep_alive: 60m).")
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def pangkas_output_tool(output: str, max_chars: int = 1500) -> str:
    """Memotong output perkakas yang terlalu panjang agar tidak memicu galat TPM/HTTP 413 pada model AI."""
    if len(output) <= max_chars:
        return output
    total_len = len(output)
    total_lines = output.count("\n") + 1
    head_len = max_chars - 250
    head = output[:head_len]
    tail = output[-150:]
    return (
        f"{head}\n\n"
        f"[... OUTPUT DIPOTONG: Menampilkan {head_len + 150} dari {total_len} karakter "
        f"({total_lines} baris). Minta parameter atau filter yang lebih spesifik jika butuh baris lainnya ...]\n\n"
        f"{tail}"
    )


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

        self.last_usage_metadata: dict[str, int] = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

        self.chat = None
        if self.provider == "gemini":
            http_opts = _build_http_options()
            self.client: Optional[genai.Client] = genai.Client(api_key=self.api_key, http_options=http_opts) if http_opts else genai.Client(api_key=self.api_key)
            self._init_chat_session()
        else:
            self.client = None

    def _load_project_rules(self) -> str:
        """Muat aturan proyek dari AGENTS.md, ATURAN.md, .agentrules, atau CLAUDE.md jika ada."""
        rules_files = ["AGENTS.md", "ATURAN.md", ".agentrules", "CLAUDE.md"]
        for fname in rules_files:
            candidate = Path.cwd() / fname
            if candidate.exists() and candidate.is_file():
                try:
                    content = candidate.read_text(encoding="utf-8", errors="replace")
                    if content.strip():
                        agent_logger.log_info(
                            "agent.project_rules",
                            f"Memuat aturan proyek dari '{fname}' ({len(content)} karakter).",
                        )
                        return (
                            f"\n\n[ATURAN PROYEK LOKAL — dari {fname}]:\n"
                            f"Instruksi berikut adalah konvensi khusus repositori ini yang harus selalu dipatuhi:\n"
                            f"{content[:4000]}\n"
                            f"────────────────────────────────────────────────────────────\n"
                        )
                except Exception as exc:
                    agent_logger.log_warning("agent.project_rules", f"Gagal membaca '{fname}': {exc}")
        return ""

    def _build_system_instruction(self, provider_label: Optional[str] = None) -> str:
        """Menyusun system instruction lengkap dengan menyertakan memori persisten dan aturan proyek."""
        persistent_memory = memory_manager.format_for_system_instruction()
        project_rules = self._load_project_rules()

        if provider_label:
            header = (
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
                "membaca/menulis/edit berkas, menjalankan perintah terminal aman (run_command), atau menyimpan memori. "
                "Berikan jawaban to-the-point, tepat sasaran, faktual, dan teknis."
            )
        else:
            header = (
                "Anda adalah AI Agent terminal profesional dan cerdas bernama gemini-terminal-agent. "
                "Berikan jawaban to-the-point, tepat sasaran, faktual, dan teknis. "
                "Jangan gunakan salam berlebihan atau basa-basi generik. Dilarang keras menggunakan emoji apapun. "
                "Gunakan tool yang tersedia kapan pun pengguna meminta manipulasi berkas, direktori, shell, atau memori."
            )

        return f"{header}\n{persistent_memory}{project_rules}"

    def _preprocess_at_mentions(self, message: str, workspace: Optional[Path] = None) -> str:
        """Mendeteksi @filename dalam prompt dan menyisipkan isi file ke konteks."""
        if not message or "@" not in message:
            return message

        if workspace is None:
            workspace = Path.cwd()

        pattern = r'@([\w./\\-]+\.[\w]+)'
        matches = re.findall(pattern, message)
        if not matches:
            return message

        appended_contexts = []
        for filename in matches:
            candidates = [
                workspace / filename,
                Path(filename).expanduser(),
            ]
            found = next((p for p in candidates if p.exists() and p.is_file()), None)

            if found:
                try:
                    from tools import validate_sandbox_path
                    is_safe, err_msg = validate_sandbox_path(str(found))
                    if not is_safe:
                        agent_logger.log_warning("agent.at_mention", f"File '@{filename}' diblokir sandbox: {err_msg}")
                        continue

                    content = found.read_text(encoding="utf-8", errors="replace")
                    if len(content) > 8000:
                        content = content[:8000] + f"\n... (terpotong, total {len(content)} karakter)"
                    appended_contexts.append(
                        f"\n\n---\n**[Konteks File: {filename}]**\n```\n{content}\n```\n---"
                    )
                    message = message.replace(f"@{filename}", f"`@{filename}`")
                except Exception as exc:
                    agent_logger.log_warning("agent.at_mention", f"Gagal membaca '@{filename}': {exc}")
            else:
                agent_logger.log_warning("agent.at_mention", f"File '@{filename}' tidak ditemukan.")

        if appended_contexts:
            return message + "".join(appended_contexts)
        return message

    def export_session(self, filename: Optional[str] = None) -> Path:
        """Mengekspor sesi aktif saat ini ke berkas Markdown."""
        return session_manager.export_to_markdown(self.session, filename)

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

        system_instruction = self._build_system_instruction()

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

    def _prune_history_if_needed(self, max_turns: int = 25, max_chars: int = 80_000) -> None:
        """Pangkas riwayat percakapan jika melebihi batas untuk mencegah context overflow."""
        # 1. Pangkas history di self.session (berlaku untuk semua provider)
        if self.session and hasattr(self.session, "history"):
            sess_hist = self.session.history
            total_chars = sum(len(str(m.get("text", ""))) for m in sess_hist)
            if len(sess_hist) > max_turns * 2 or total_chars > max_chars:
                turns_to_keep = min(8 * 2, len(sess_hist))
                recent = sess_hist[-turns_to_keep:]
                pruned_count = (len(sess_hist) - len(recent)) // 2
                notice = {
                    "role": "user",
                    "text": f"[CATATAN SISTEM: {pruned_count} turn percakapan sebelumnya telah dipangkas otomatis demi efisiensi kuota konteks.]"
                }
                ack = {
                    "role": "model",
                    "text": "Dipahami. Saya melanjutkan percakapan berdasarkan riwayat konteks terkini."
                }
                self.session.history = [notice, ack] + recent
                session_manager.save_session(self.session)
                agent_logger.log_info(
                    "agent.prune_history",
                    f"Session history dipangkas: {pruned_count} turns lama dihapus, {len(recent)//2} turns terkini dipertahankan."
                )

        # 2. Pangkas chat SDK Gemini jika provider == 'gemini'
        if not self.chat or self.provider != "gemini":
            return
        try:
            history = self.chat.get_history()
            if not history:
                return

            total_chars = 0
            for content in history:
                for part in (getattr(content, "parts", None) or []):
                    total_chars += len(str(getattr(part, "text", "") or ""))

            needs_prune = (len(history) > max_turns * 2) or (total_chars > max_chars)
            if not needs_prune:
                return

            turns_to_keep = min(8 * 2, len(history))
            recent_history = history[-turns_to_keep:]
            pruned_count = len(history) - len(recent_history)

            summary_content = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=f"[CATATAN SISTEM: {pruned_count} turn percakapan sebelumnya telah dipangkas otomatis demi efisiensi kuota konteks. Riwayat terkini dilanjutkan pada pesan berikut.]"
                        )
                    ],
                ),
                types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text="Dipahami. Saya melanjutkan percakapan berdasarkan riwayat konteks terkini."
                        )
                    ],
                ),
            ]

            system_instruction = self._build_system_instruction()
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=TOOL_CALLABLES,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.2,
            )

            self.chat = self.client.chats.create(
                model=self.model_name,
                config=config,
                history=summary_content + list(recent_history),
            )
            agent_logger.log_info(
                "agent.prune_history",
                f"SDK chat history dipangkas: {pruned_count} turns lama dihapus, {len(recent_history)//2} turns terkini dipertahankan.",
            )
        except Exception as exc:
            agent_logger.log_error("agent.prune_history", f"Gagal memangkas SDK chat history: {exc}")

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
            self.model_name = config_manager.get_ollama_model() or "llama3.2:3b"
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

    def _execute_fast_path_and_sync(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        user_message: str,
        on_tool_call: Optional[Callable[[str, dict[str, Any]], None]] = None,
        on_tool_result: Optional[Callable[[str, str], None]] = None,
    ) -> str:
        """Eksekusi tool cepat dan sinkronkan ke riwayat chat AI agar konteks percakapan tetap utuh."""
        func = AVAILABLE_TOOLS.get(tool_name)
        if not func:
            try:
                import perkakas
                func = getattr(perkakas, tool_name, None)
            except Exception:
                func = None

        if not func:
            err = f"[GAGAL] Tool '{tool_name}' tidak tersedia di sistem."
            self.session.ui_messages.append(SessionMessage(msg_type="agent", text=err))
            session_manager.save_session(self.session)
            return err

        if on_tool_call:
            on_tool_call(tool_name, tool_args)

        try:
            result_str = str(func(**tool_args))
        except Exception as exc:
            result_str = f"[GAGAL] Eksekusi {tool_name}: {exc}"

        preview = (
            result_str[:120].replace("\n", " ") + "..."
            if len(result_str) > 120
            else result_str.replace("\n", " ")
        )
        if on_tool_result:
            on_tool_result(tool_name, preview)

        # Catat pemanggilan tool ke UI messages
        self.session.ui_messages.append(
            SessionMessage(
                msg_type="tool",
                tool_name=tool_name,
                tool_args=tool_args,
                tool_preview=preview,
            )
        )
        self.session.ui_messages.append(SessionMessage(msg_type="agent", text=result_str))

        # Sinkronkan ke chat Gemini jika aktif agar AI mengingat tindakan ini
        if self.chat and self.provider == "gemini":
            try:
                current_history = list(self.chat.get_history() or [])
                current_history.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
                )
                current_history.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part.from_text(
                                text=f"[Tindakan Langsung: Tool '{tool_name}' dieksekusi]\nHasil: {result_str[:800]}"
                            )
                        ],
                    )
                )

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
                self.chat = self.client.chats.create(
                    model=self.model_name,
                    config=config,
                    history=current_history,
                )
            except Exception as e:
                agent_logger.log_warning("agent.fast_path", f"Gagal sinkron riwayat fast-path: {e}")

        self._sync_history_from_chat()
        session_manager.save_session(self.session)
        return result_str

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
        # Preprocessing @filename context injection
        message = self._preprocess_at_mentions(message)

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

        # Kecerdasan NLU Intent Detection (Anti-Misleading untuk Perintah Laptop)
        try:
            from kecerdasan_ollama import KecerdasanOllama
            niat = KecerdasanOllama.analisis_perintah(message)
            if niat and niat.tool_name in AVAILABLE_TOOLS:
                agent_logger.log_info("agent.kecerdasan_ollama", f"Niat terdeteksi: {niat.deskripsi_konfirmasi} -> {niat.tool_name}({niat.tool_args})")
                return self._execute_fast_path_and_sync(
                    niat.tool_name,
                    niat.tool_args,
                    message,
                    on_tool_call,
                    on_tool_result,
                )
        except Exception as e_nlu:
            agent_logger.log_warning("agent.kecerdasan_ollama", f"Gagal evaluasi NLU: {e_nlu}")

        if not is_compound:
            # 1. Menutup aplikasi
            if msg_lower.startswith("tutup aplikasi ") or msg_lower.startswith("tutup ") or msg_lower.startswith("close "):
                parts = message.strip().split(maxsplit=2 if msg_lower.startswith("tutup aplikasi ") else 1)
                target_app = parts[-1].strip().strip('"').strip("'")
                if target_app:
                    return self._execute_fast_path_and_sync(
                        "close_application",
                        {"app_name_or_pid": target_app},
                        message,
                        on_tool_call,
                        on_tool_result,
                    )

            # 2. Buka kamera webcam & foto
            if any(k in msg_lower for k in ["buka kamera", "ambil foto", "foto kamera", "capture kamera", "foto webcam", "kamera laptop"]):
                return self._execute_fast_path_and_sync(
                    "capture_camera",
                    {"output_path": "kamera_capture.jpg"},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

            # 3. Status sistem / hardware
            if any(k in msg_lower for k in ["status sistem", "persentase sistem", "persentase penyimpanan", "persentase baterai", "cek baterai", "cek penyimpanan", "cek ram", "cek cpu", "cek storage"]):
                return self._execute_fast_path_and_sync(
                    "get_system_status",
                    {},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

            # 4. Buka aplikasi desktop / YouTube / URL
            if (msg_lower.startswith("buka ") or msg_lower.startswith("open ") or "buka chrome" in msg_lower or "buka youtube" in msg_lower or (("putar " in msg_lower or "play " in msg_lower) and ("youtube" in msg_lower or "yt" in msg_lower))) and not ("kamera" in msg_lower or "webcam" in msg_lower):
                if ("youtube" in msg_lower or "yt" in msg_lower) and ("putar" in msg_lower or "play" in msg_lower):
                    q_yt = message.strip()
                    for w in ["putar", "putarkan", "play", "lagu", "video", "musik", "di", "pada", "youtube", "yt", "tolong", "coba"]:
                        q_yt = re.sub(r"\b" + w + r"\b", "", q_yt, flags=re.IGNORECASE).strip()
                    return self._execute_fast_path_and_sync(
                        "play_youtube_video",
                        {"video_id_or_url": q_yt},
                        message,
                        on_tool_call,
                        on_tool_result,
                    )

                return self._execute_fast_path_and_sync(
                    "open_application",
                    {"app_or_query": message.strip()},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

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
                return self._execute_fast_path_and_sync(
                    "set_volume",
                    {"level": vol_arg},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

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
                return self._execute_fast_path_and_sync(
                    "media_control",
                    {"action": act_media},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

            # 7. Screenshot
            if any(k in msg_lower for k in ["screenshot", "screen capture", "capture layar", "tangkapan layar", "foto layar", "ss laptop", "ss layar"]):
                return self._execute_fast_path_and_sync(
                    "capture_screen",
                    {"output_path": "screen_capture.png"},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

            # 8. Kunci Layar / Lock Laptop (Ctrl + L)
            if any(k in msg_lower for k in ["kunci laptop", "lock laptop", "kunci layar", "lock screen", "kunci pc", "lock pc", "ctrl + l", "ctrl+l"]):
                return self._execute_fast_path_and_sync(
                    "lock_laptop",
                    {},
                    message,
                    on_tool_call,
                    on_tool_result,
                )

        max_heal_attempts = 3
        heal_attempt = 0
        last_error = None

        while heal_attempt < max_heal_attempts:
            try:
                self.provider = config_manager.get_provider()
                if self.provider == "groq":
                    return self._send_message_groq(message, on_tool_call, on_tool_result)
                elif self.provider == "omniroute":
                    return self._send_message_omniroute(message, on_tool_call, on_tool_result)
                elif self.provider == "ollama":
                    return self._send_message_ollama(message, on_tool_call, on_tool_result)

                if not self.chat:
                    self._init_chat_session()

                # Pangkas riwayat lama jika melebihi batas token / turns
                self._prune_history_if_needed()

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

                        safe_result = pangkas_output_tool(result_str)
                        part = types.Part.from_function_response(
                            name=tool_name,
                            response={"result": safe_result},
                        )
                        parts_responses.append(part)

                    # Kirim kembali hasil tool response ke obrolan model
                    response = self.chat.send_message(parts_responses)

                final_text = response.text or "(Tidak ada teks dalam respon)"

                # Simpan metadata penggunaan token aktual
                try:
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        self.last_usage_metadata = {
                            "total_tokens": getattr(response.usage_metadata, "total_token_count", 0) or 0,
                            "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                            "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                        }
                except Exception:
                    pass

                agent_logger.log_info(
                    "agent.send_message",
                    f"Respon akhir diterima ({len(final_text)} karakter, token: {self.last_usage_metadata.get('total_tokens', 0)})",
                )

                # Catat respon agen ke UI messages sesi
                self.session.ui_messages.append(SessionMessage(msg_type="agent", text=final_text))

                # Sinkronisasi riwayat obrolan lengkap dan simpan ke disk
                self._sync_history_from_chat()
                session_manager.save_session(self.session)

                return final_text

            except Exception as exc:
                heal_attempt += 1
                last_error = exc
                heal_res = session_healer.attempt_heal(
                    exc=exc,
                    agent=self,
                    session=self.session,
                    context="generate: send_message",
                    attempt=heal_attempt,
                )
                if heal_res.recovered:
                    agent_logger.log_info(
                        "agent.healing",
                        f"In-Session healing berhasil: {heal_res.summary} -> Mencoba ulang pengiriman pesan...",
                    )
                    continue
                else:
                    # Tidak dapat di-heal secara otonom, sertakan heal_res pada exception dan re-raise
                    setattr(exc, "healing_result", heal_res)
                    raise exc

        if last_error:
            raise last_error

def _filter_tools_for_query(message: str, provider_label: str) -> Optional[list[dict[str, Any]]]:
    """Menyaring tool secara pintar. Untuk Ollama lokal di CPU, hanya menyertakan tool jika ada intensi perintah sistem."""
    if str(provider_label).lower() != "ollama":
        return OPENAI_TOOLS_SCHEMA

    msg_low = str(message).lower()
    action_keywords = {
        "volume": ["set_volume", "get_volume"],
        "suara": ["set_volume", "get_volume"],
        "mute": ["set_volume", "media_control"],
        "unmute": ["set_volume", "media_control"],
        "lagu": ["media_control", "play_youtube_video", "search_youtube_videos"],
        "musik": ["media_control", "play_youtube_video", "search_youtube_videos"],
        "youtube": ["play_youtube_video", "search_youtube_videos"],
        "putar": ["play_youtube_video", "media_control"],
        "play": ["play_youtube_video", "media_control"],
        "pause": ["media_control"],
        "buka": ["open_application", "get_open_browser_tabs"],
        "tutup": ["close_application"],
        "kill": ["close_application"],
        "aplikasi": ["open_application", "close_application", "list_running_applications"],
        "program": ["open_application", "close_application", "list_running_applications"],
        "tab": ["get_open_browser_tabs"],
        "browser": ["get_open_browser_tabs", "open_application"],
        "screenshot": ["capture_screen"],
        "layar": ["capture_screen"],
        "tangkapan": ["capture_screen"],
        "kamera": ["capture_camera"],
        "foto": ["capture_camera"],
        "webcam": ["capture_camera"],
        "baterai": ["get_system_status"],
        "battery": ["get_system_status"],
        "ram": ["get_system_status"],
        "cpu": ["get_system_status"],
        "status": ["get_system_status"],
        "spesifikasi": ["get_system_status"],
        "file": ["read_file", "write_file", "list_directory", "create_folder"],
        "berkas": ["read_file", "write_file", "list_directory", "create_folder"],
        "folder": ["list_directory", "create_folder"],
        "direktori": ["list_directory", "create_folder"],
        "baca": ["read_file"],
        "tulis": ["write_file"],
        "cmd": ["run_command"],
        "terminal": ["run_command"],
        "perintah": ["run_command"],
        "command": ["run_command"],
        "kunci": ["lock_laptop"],
        "lock": ["lock_laptop"],
        "restart": ["restart_laptop"],
        "sleep": ["sleep_laptop"],
        "ingat": ["save_memory", "search_memory"],
        "memori": ["save_memory", "search_memory"],
    }
    needed = set()
    for kw, tlist in action_keywords.items():
        if kw in msg_low:
            needed.update(tlist)

    if not needed:
        return None

    res = [t for t in OPENAI_TOOLS_SCHEMA if t.get("function", {}).get("name") in needed]
    return res if res else None


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
        system_instruction = self._build_system_instruction(provider_label=provider_label)

        messages = [{"role": "system", "content": system_instruction}]
        # Filter hanya pesan user dan agent, abaikan log internal/tool di level ini
        history_entries = [
            m for m in self.session.ui_messages
            if m.msg_type in ("user", "agent") and (m.text or "").strip()
        ]
        for m in history_entries[-20:]:
            role = "user" if m.msg_type == "user" else "assistant"
            messages.append({"role": role, "content": m.text})

        # Pastikan pesan user saat ini berada di posisi paling akhir
        if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != message:
            messages.append({"role": "user", "content": message})

        max_iterations = 10
        iteration = 0
        final_text = ""

        active_tools = _filter_tools_for_query(message, provider_label)

        while iteration < max_iterations:
            iteration += 1
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
            }
            if active_tools:
                payload["tools"] = active_tools
                payload["tool_choice"] = "auto"
            if str(provider_label).lower() == "ollama":
                payload["keep_alive"] = "60m"
                payload["options"] = {
                    "num_ctx": 4096,
                    "num_thread": 4,
                    "temperature": 0.2,
                }
            try:
                req = urllib.request.Request(
                    target_url,
                    headers=headers,
                    data=json.dumps(payload).encode("utf-8"),
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode())

                usage = data.get("usage", {})
                if usage:
                    self.last_usage_metadata = {
                        "total_tokens": usage.get("total_tokens", 0) or 0,
                        "input_tokens": usage.get("prompt_tokens", 0) or 0,
                        "output_tokens": usage.get("completion_tokens", 0) or 0,
                    }

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
                        safe_result = pangkas_output_tool(result_str)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": safe_result,
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
                        if str(provider_label).lower() == "ollama":
                            fallback_payload["keep_alive"] = "60m"
                            fallback_payload["options"] = {
                                "num_ctx": 4096,
                                "num_thread": 4,
                                "temperature": 0.2,
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
                clean_detail = str(detail_err or exc_http).replace("<", "").replace(">", "").strip()
                final_text = f"❌ **Galat {provider_label} (HTTP {getattr(exc_http, 'code', 'Error')})**: `{clean_detail}`"
                break
            except Exception as exc:
                clean_exc = str(exc).replace("<", "").replace(">", "").strip()
                final_text = f"❌ **Galat {provider_label}**: `{clean_exc}`"
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
        server_ready = ensure_ollama_running(base_url)
        if not server_ready:
            err_msg = (
                f"❌ **Server Ollama Tidak Aktif (Port 11434)**\n\n"
                f"Gagal terhubung ke host lokal Ollama di `{base_url}`.\n"
                f"• Pastikan server Ollama sudah berjalan (`ollama serve` di command prompt).\n"
                f"• Atau beralih ke provider aktif lainnya dengan perintah:\n"
                f"  `/provider gemini` atau `/provider groq`"
            )
            self.session.ui_messages.append(SessionMessage(msg_type="agent", text=err_msg))
            session_manager.save_session(self.session)
            return err_msg

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

