"""Aplikasi antarmuka terminal (TUI) modern untuk Gemini Terminal Agent menggunakan Textual.

Menyediakan antarmuka visual gelap beranimasi lengkap dengan:
- Alur first-run interaktif (input API key & deteksi model otomatis)
- Manajemen sesi percakapan & riwayat obrolan persisten (Ctrl+S / /session)
- Memori jangka panjang agent untuk fakta dan preferensi (/memory)
- Indikator loading spinner saat fetch model dan agen berpikir
- Typing effect pada respon agen & rendering instan untuk riwayat lampau
- Visualisasi tool calling interaktif
- Status bar live dengan status model, sesi, dan highlight transisi
- Dukungan perintah slash (/session, /memory, /model, /clear, /theme, /help, /quit)
"""

from __future__ import annotations

import asyncio
import datetime
import json
from typing import Any, Optional

from rich.markdown import Markdown
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, LoadingIndicator, Static

from agent import GeminiAgent, fetch_available_models
from config import config_manager
from logger import agent_logger
from memory import memory_manager
from session_manager import Session, SessionMessage, session_manager


# ==============================================================================
# TEMA & CSS DINAMIS
# ==============================================================================
THEMES = {
    "default": {
        "accent": "#388bfd",
        "accent_light": "#58a6ff",
        "success": "#238636",
        "success_light": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "bg": "#0d1117",
        "bg_panel": "#161b22",
    },
    "emerald": {
        "accent": "#2ea043",
        "accent_light": "#3fb950",
        "success": "#238636",
        "success_light": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "bg": "#0a100d",
        "bg_panel": "#121a16",
    },
    "crimson": {
        "accent": "#f85149",
        "accent_light": "#ff7b72",
        "success": "#238636",
        "success_light": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "bg": "#120d0d",
        "bg_panel": "#1a1414",
    },
    "amber": {
        "accent": "#d29922",
        "accent_light": "#e3b341",
        "success": "#238636",
        "success_light": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "bg": "#100e0a",
        "bg_panel": "#1a1712",
    },
    "purple": {
        "accent": "#8957e5",
        "accent_light": "#a371f7",
        "success": "#238636",
        "success_light": "#3fb950",
        "warning": "#d29922",
        "error": "#f85149",
        "bg": "#0d0d17",
        "bg_panel": "#14141f",
    },
}

BASE_CSS = """
Screen {
    background: #0d1117;
    color: #c9d1d9;
}

#app_header {
    height: 3;
    background: #161b22;
    border-bottom: heavy #388bfd;
    padding: 0 1;
}

#header_title {
    color: #58a6ff;
    text-style: bold;
    width: 60%;
}

#header_clock {
    color: #8b949e;
    text-align: right;
    width: 40%;
}

#chat_messages {
    height: 1fr;
    padding: 1 2;
    background: #0d1117;
    overflow-y: auto;
}

.msg-user-box {
    background: #161b22;
    border-left: thick #388bfd;
    border-top: none;
    border-right: none;
    border-bottom: none;
    padding: 1 2;
    margin: 1 0;
}

.msg-user-title {
    color: #58a6ff;
    text-style: bold;
    margin-bottom: 1;
}

.msg-agent-box {
    background: #11161d;
    border-left: thick #238636;
    border-top: none;
    border-right: none;
    border-bottom: none;
    padding: 1 2;
    margin: 1 0;
}

.msg-agent-title {
    color: #3fb950;
    text-style: bold;
    margin-bottom: 1;
}

.msg-system-box {
    background: #1c1917;
    border-left: thick #d29922;
    padding: 1 2;
    margin: 1 0;
}

.msg-error-box {
    background: #211315;
    border-left: thick #f85149;
    padding: 1 2;
    margin: 1 0;
    color: #ff7b72;
}

.tool-box {
    background: #161b22;
    border: round #388bfd;
    padding: 1;
    margin: 1 0;
}

.tool-title {
    color: #58a6ff;
    text-style: bold;
}

.tool-args {
    color: #8b949e;
}

.tool-status-running {
    color: #d29922;
    text-style: italic;
}

.tool-status-done {
    color: #3fb950;
}

.tool-preview {
    color: #c9d1d9;
    background: #0d1117;
    padding: 0 1;
    margin-top: 1;
}

#thinking_box {
    height: 3;
    padding: 0 2;
    background: #161b22;
    color: #d29922;
    margin: 1 0;
    border-left: thick #d29922;
}

#input_container {
    height: 4;
    background: #161b22;
    border-top: heavy #30363d;
    padding: 0 1;
}

#chat_input {
    width: 85%;
    border: round #388bfd;
    background: #0d1117;
    color: #f0f6fc;
}

#chat_input:focus {
    border: round #58a6ff;
}

#btn_send {
    width: 15%;
    border: none;
    background: #238636;
    color: #ffffff;
    text-style: bold;
}

#btn_send:hover {
    background: #2ea043;
}

#status_bar {
    height: 1;
    background: #161b22;
    color: #8b949e;
    padding: 0 2;
}

.status-model {
    color: #58a6ff;
    width: 25%;
}

.status-session {
    color: #e3b341;
    width: 25%;
    text-style: bold;
}

.status-state {
    color: #3fb950;
    width: 15%;
    text-align: center;
}

.status-hints {
    color: #8b949e;
    width: 35%;
    text-align: right;
}

.status-bar-highlight {
    background: #1f6feb !important;
    color: #ffffff !important;
}

.modal-dialog {
    width: 82;
    height: auto;
    max-height: 85%;
    background: #161b22;
    border: heavy #388bfd;
    padding: 1 2;
}

.modal-title {
    color: #58a6ff;
    text-style: bold;
    text-align: center;
    margin-bottom: 1;
}

.modal-desc {
    color: #8b949e;
    margin-bottom: 1;
}

.model-list-view, .session-list-view {
    height: 14;
    border: round #30363d;
    background: #0d1117;
    margin-bottom: 1;
}

.session-action-bar {
    height: 3;
    margin-bottom: 1;
}

.model-item-title, .session-item-title {
    color: #58a6ff;
    text-style: bold;
}

.session-active-title {
    color: #3fb950;
    text-style: bold;
}

.model-item-sub, .session-item-sub {
    color: #8b949e;
}

.model-item-desc {
    color: #c9d1d9;
}
"""


def generate_all_css() -> str:
    chunks = [BASE_CSS]
    for name, t in THEMES.items():
        theme_chunk = f"""
Screen.theme-{name} {{
    background: {t['bg']};
}}
Screen.theme-{name} #app_header {{
    background: {t['bg_panel']};
    border-bottom: heavy {t['accent']};
}}
Screen.theme-{name} #header_title {{
    color: {t['accent_light']};
}}
Screen.theme-{name} #chat_messages {{
    background: {t['bg']};
}}
Screen.theme-{name} .msg-user-box {{
    background: {t['bg_panel']};
    border-left: thick {t['accent']};
}}
Screen.theme-{name} .msg-user-title {{
    color: {t['accent_light']};
}}
Screen.theme-{name} .tool-box {{
    background: {t['bg_panel']};
    border: round {t['accent']};
}}
Screen.theme-{name} .tool-title {{
    color: {t['accent_light']};
}}
Screen.theme-{name} .tool-preview {{
    background: {t['bg']};
}}
Screen.theme-{name} #thinking_box {{
    background: {t['bg_panel']};
}}
Screen.theme-{name} #input_container {{
    background: {t['bg_panel']};
}}
Screen.theme-{name} #chat_input {{
    border: round {t['accent']};
    background: {t['bg']};
}}
Screen.theme-{name} #chat_input:focus {{
    border: round {t['accent_light']};
}}
Screen.theme-{name} #btn_send {{
    background: {t['success']};
}}
Screen.theme-{name} #btn_send:hover {{
    background: {t['success_light']};
}}
Screen.theme-{name} #status_bar {{
    background: {t['bg_panel']};
}}
Screen.theme-{name} .status-model {{
    color: {t['accent_light']};
}}
Screen.theme-{name} .status-session {{
    color: {t['warning']};
}}
Screen.theme-{name} .status-bar-highlight {{
    background: {t['accent']} !important;
}}
Screen.theme-{name} .modal-dialog {{
    background: {t['bg_panel']};
    border: heavy {t['accent']};
}}
Screen.theme-{name} .modal-title {{
    color: {t['accent_light']};
}}
Screen.theme-{name} .model-list-view, Screen.theme-{name} .session-list-view {{
    background: {t['bg']};
}}
Screen.theme-{name} .model-item-title, Screen.theme-{name} .session-item-title {{
    color: {t['accent_light']};
}}
Screen.theme-{name} .session-active-title {{
    color: {t['success_light']};
}}
"""
        chunks.append(theme_chunk)
    return "\n".join(chunks)


APP_CSS = generate_all_css()


# ==============================================================================
# MODAL SCREEN 1: Input API Key
# ==============================================================================
class ApiKeyModal(ModalScreen[str]):
    """Layar modal dialog untuk memasukkan API Key Gemini saat first-run."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("⌬ KONFIGURASI GEMINI API KEY", classes="modal-title")
            yield Label(
                "API Key belum terkonfigurasi. Kunci ini akan disimpan aman di ~/.gemini-agent/.env.",
                classes="modal-desc",
            )
            yield Input(
                placeholder="Masukkan API Key (AIzaSy...)",
                id="api_key_input",
                password=True,
            )
            with Horizontal():
                yield Button("Simpan & Lanjutkan ▶", variant="primary", id="btn_save_key")
                yield Button("Keluar", variant="error", id="btn_exit_key")

    def on_mount(self) -> None:
        if hasattr(self.app, "active_theme"):
            self.add_class(f"theme-{self.app.active_theme}")
        self.query_one("#api_key_input", Input).focus()

    @on(Button.Pressed, "#btn_save_key")
    @on(Input.Submitted, "#api_key_input")
    def handle_save(self) -> None:
        input_widget = self.query_one("#api_key_input", Input)
        val = input_widget.value.strip()
        if val:
            config_manager.save_api_key(val)
            self.dismiss(val)

    @on(Button.Pressed, "#btn_exit_key")
    def handle_exit(self) -> None:
        self.app.exit()


# ==============================================================================
# MODAL SCREEN 2: Seleksi Model Otomatis
# ==============================================================================
class ModelItem(ListItem):
    """Item tampilan untuk satu model di ListView."""

    def __init__(self, model_info: dict[str, Any]) -> None:
        super().__init__()
        self.model_info = model_info

    def compose(self) -> ComposeResult:
        name = self.model_info.get("display_name", "")
        m_id = self.model_info.get("id", "")
        in_limit = self.model_info.get("input_token_limit")
        out_limit = self.model_info.get("output_token_limit")
        limit_str = f"In: {in_limit:,} | Out: {out_limit:,}" if in_limit and out_limit else "Token limit: standar"
        desc = self.model_info.get("description", "")[:110]

        yield Label(f"▸ {name} ({m_id})", classes="model-item-title")
        yield Label(f"  Batas Token: {limit_str}", classes="model-item-sub")
        yield Label(f"  {desc}", classes="model-item-desc")


class ModelSelectModal(ModalScreen[str]):
    """Layar seleksi model otomatis berbasis API Gemini dengan opsi fallback manual."""

    def __init__(self, api_key: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.models_data: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("⌬ SELEKSI MODEL GEMINI (AUTO-DETECT)", classes="modal-title")
            yield Label(
                "Memindai model resmi yang mendukung generateContent & tool calling...",
                id="model_status_label",
                classes="modal-desc",
            )
            with Vertical(id="loading_container"):
                yield LoadingIndicator()
            yield ListView(id="model_list_view", classes="model-list-view")
            yield Label("Atau masukkan nama teknis model secara manual:", classes="modal-desc")
            with Horizontal():
                yield Input(
                    placeholder="Contoh: gemini-2.5-flash",
                    id="manual_model_input",
                )
                yield Button("Pilih Manual", id="btn_manual_select")
            with Horizontal():
                yield Button("Gunakan Model Terpilih ▶", variant="primary", id="btn_confirm_model")
                yield Button("Kembali", id="btn_back")

    def on_mount(self) -> None:
        if hasattr(self.app, "active_theme"):
            self.add_class(f"theme-{self.app.active_theme}")
        list_view = self.query_one("#model_list_view", ListView)
        list_view.display = False
        self.query_one("#btn_confirm_model", Button).disabled = True
        self.fetch_models_task()

    @work(thread=True)
    def fetch_models_task(self) -> None:
        """Memanggil API Gemini di background thread agar antarmuka tidak membeku."""
        try:
            models = fetch_available_models(self.api_key)
            self.app.call_from_thread(self._on_models_loaded, models)
        except Exception as exc:
            err = agent_logger.diagnose_and_format_error(exc, "fetch_available_models")
            self.app.call_from_thread(self._on_models_error, err.to_cli_string())

    def _on_models_loaded(self, models: list[dict[str, Any]]) -> None:
        self.models_data = models
        loading = self.query_one("#loading_container")
        loading.display = False

        status_lbl = self.query_one("#model_status_label", Label)
        list_view = self.query_one("#model_list_view", ListView)

        if not models:
            status_lbl.update("[!] Tidak ada model yang kompatibel ditemukan. Silakan masukkan manual.")
            return

        status_lbl.update(f"[●] Ditemukan {len(models)} model yang siap digunakan. Pilih salah satu:")
        list_view.clear()
        for m in models:
            list_view.append(ModelItem(m))

        list_view.display = True
        self.query_one("#btn_confirm_model", Button).disabled = False
        list_view.focus()

    def _on_models_error(self, error_details: str) -> None:
        loading = self.query_one("#loading_container")
        loading.display = False
        status_lbl = self.query_one("#model_status_label", Label)
        status_lbl.update("[X] Gagal memindai model dari API. Periksa rincian di bawah:")

        list_view = self.query_one("#model_list_view", ListView)
        list_view.display = True
        list_view.clear()
        list_view.append(ListItem(Label(error_details, classes="msg-error-box")))

        manual_input = self.query_one("#manual_model_input", Input)
        manual_input.value = "gemini-2.5-flash"
        manual_input.focus()

    @on(ListView.Selected, "#model_list_view")
    def handle_item_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, ModelItem):
            selected_id = event.item.model_info.get("id", "")
            if selected_id:
                config_manager.save_model(selected_id)
                self.dismiss(selected_id)

    @on(Button.Pressed, "#btn_confirm_model")
    def handle_confirm_button(self) -> None:
        list_view = self.query_one("#model_list_view", ListView)
        item = list_view.highlighted_child
        if isinstance(item, ModelItem):
            selected_id = item.model_info.get("id", "")
            if selected_id:
                config_manager.save_model(selected_id)
                self.dismiss(selected_id)

    @on(Button.Pressed, "#btn_manual_select")
    @on(Input.Submitted, "#manual_model_input")
    def handle_manual_submit(self) -> None:
        manual_input = self.query_one("#manual_model_input", Input)
        chosen = manual_input.value.strip()
        if chosen:
            config_manager.save_model(chosen)
            self.dismiss(chosen)

    @on(Button.Pressed, "#btn_back")
    def handle_back(self) -> None:
        current = config_manager.get_model()
        if current:
            self.dismiss(current)
        else:
            self.app.exit()


# ==============================================================================
# MODAL SCREEN 3: Manajemen Sesi Percakapan (Ctrl+S / /session)
# ==============================================================================
class SessionItem(ListItem):
    """Item tampilan untuk satu sesi di ListView."""

    def __init__(self, session_summary: dict[str, Any], is_active: bool = False) -> None:
        super().__init__()
        self.session_summary = session_summary
        self.is_active = is_active

    def compose(self) -> ComposeResult:
        s_id = self.session_summary.get("session_id", "")
        title = self.session_summary.get("title", "Sesi")
        msgs = self.session_summary.get("message_count", 0)
        raw_updated = self.session_summary.get("updated_at", "")
        updated = raw_updated[:19].replace("T", " ") if raw_updated else "-"
        model = self.session_summary.get("model_name", "-")

        badge = " [AKTIF]" if self.is_active else ""
        title_cls = "session-item-title session-active-title" if self.is_active else "session-item-title"
        yield Label(f"🗎 {title}{badge}", classes=title_cls)
        yield Label(f"  ID: {s_id} │ {msgs} Pesan │ Diperbarui: {updated} │ Model: {model}", classes="session-item-sub")


class SessionSelectModal(ModalScreen[Optional[str]]):
    """Layar manajemen sesi untuk melihat, memulihkan, membuat, atau menghapus sesi."""

    def __init__(self, current_session_id: str) -> None:
        super().__init__()
        self.current_session_id = current_session_id

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-dialog"):
            yield Label("🗎 MANAJEMEN SESI & PEMULIHAN KONTEKS", classes="modal-title")
            yield Label(
                "Pilih sesi sebelumnya untuk memulihkan percakapan atau buat sesi baru:",
                classes="modal-desc",
            )
            with Horizontal(classes="session-action-bar"):
                yield Button("+ Sesi Baru", variant="success", id="btn_new_session")
                yield Button("✕ Hapus Sesi", variant="error", id="btn_delete_session")
            yield ListView(id="session_list_view", classes="session-list-view")
            with Horizontal():
                yield Button("Buka / Pulihkan Sesi ▶", variant="primary", id="btn_confirm_session")
                yield Button("Tutup", id="btn_close_session")

    def on_mount(self) -> None:
        if hasattr(self.app, "active_theme"):
            self.add_class(f"theme-{self.app.active_theme}")
        self._refresh_sessions_list()

    def _refresh_sessions_list(self) -> None:
        list_view = self.query_one("#session_list_view", ListView)
        list_view.clear()
        sessions = session_manager.list_sessions()

        if not sessions:
            list_view.append(ListItem(Label("Belum ada riwayat sesi tersimpan.", classes="session-item-sub")))
            self.query_one("#btn_confirm_session", Button).disabled = True
            return

        self.query_one("#btn_confirm_session", Button).disabled = False
        target_idx = 0
        for idx, s in enumerate(sessions):
            is_active = (s["session_id"] == self.current_session_id)
            if is_active:
                target_idx = idx
            list_view.append(SessionItem(s, is_active=is_active))

        list_view.index = target_idx
        list_view.focus()

    def _get_highlighted_session_id(self) -> Optional[str]:
        list_view = self.query_one("#session_list_view", ListView)
        item = list_view.highlighted_child
        if isinstance(item, SessionItem):
            return item.session_summary.get("session_id")
        return None

    @on(ListView.Selected, "#session_list_view")
    def handle_item_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, SessionItem):
            sess_id = event.item.session_summary.get("session_id")
            if sess_id:
                self.dismiss(sess_id)

    @on(Button.Pressed, "#btn_confirm_session")
    def handle_confirm(self) -> None:
        sess_id = self._get_highlighted_session_id()
        if sess_id:
            self.dismiss(sess_id)

    @on(Button.Pressed, "#btn_new_session")
    def handle_new(self) -> None:
        self.dismiss("__NEW__")

    @on(Button.Pressed, "#btn_delete_session")
    def handle_delete(self) -> None:
        sess_id = self._get_highlighted_session_id()
        if sess_id:
            session_manager.delete_session(sess_id)
            self._refresh_sessions_list()

    @on(Button.Pressed, "#btn_close_session")
    def handle_close(self) -> None:
        self.dismiss(None)


# ==============================================================================
# WIDGET TOOL CALL DAN ANIMASI TYPING
# ==============================================================================
class ToolCallCard(Static):
    """Widget representasi eksekusi function calling dengan visualisasi status dinamis."""

    def __init__(
        self,
        tool_name: str,
        args: dict[str, Any],
        initial_preview: str = "",
    ) -> None:
        super().__init__(classes="tool-box")
        self.tool_name = tool_name
        self.args = args
        self.initial_preview = initial_preview

    def compose(self) -> ComposeResult:
        args_str = json.dumps(self.args, ensure_ascii=False)
        yield Label(f"┌─ ⌬ TOOL MEMANGGIL: {self.tool_name} ─", classes="tool-title")
        yield Label(f"│ Argumen: {args_str}", classes="tool-args")
        if self.initial_preview:
            yield Label("│ Status : [SUKSES] Selesai", id="status_label", classes="tool-status-done")
            yield Label(f"│ Hasil  : {self.initial_preview}", id="preview_label", classes="tool-preview")
        else:
            yield Label("│ Status : [▒▒▒▒] Menjalankan operasi...", id="status_label", classes="tool-status-running")
            yield Label("", id="preview_label", classes="tool-preview")

    def mark_completed(self, preview_text: str) -> None:
        """Memperbarui visual status tool setelah eksekusi selesai."""
        status_lbl = self.query_one("#status_label", Label)
        status_lbl.update("│ Status : [SUKSES] Selesai")
        status_lbl.remove_class("tool-status-running")
        status_lbl.add_class("tool-status-done")

        prev_lbl = self.query_one("#preview_label", Label)
        prev_lbl.update(f"│ Preview: {preview_text}")


class TypingMessageCard(Static):
    """Bubble respon agen dengan animasi efek mengetik atau render langsung untuk riwayat."""

    def __init__(self, full_text: str, animate: bool = True) -> None:
        super().__init__(classes="msg-agent-box")
        self.full_text = full_text
        self.animate = animate
        self.current_idx = 0
        self.chunk_size = 2

    def compose(self) -> ComposeResult:
        yield Label("⌬ AGENT (GEMINI):", classes="msg-agent-title")
        if self.animate:
            yield Static("", id="typed_content")
        else:
            yield Static(Markdown(self.full_text), id="typed_content")

    def on_mount(self) -> None:
        if self.animate:
            self.set_interval(0.015, self._stream_next_chars)
        else:
            scroll_area = self.app.query_one("#chat_messages", VerticalScroll)
            scroll_area.scroll_end(animate=False)

    def _stream_next_chars(self) -> None:
        """Mengalirkan potongan karakter respon untuk animasi typing effect."""
        content_widget = self.query_one("#typed_content", Static)
        if self.current_idx < len(self.full_text):
            self.current_idx += self.chunk_size
            curr_slice = self.full_text[: self.current_idx]
            content_widget.update(curr_slice)
            scroll_area = self.app.query_one("#chat_messages", VerticalScroll)
            scroll_area.scroll_end(animate=False)
        else:
            # Selesai mengetik: render sebagai Rich Markdown resmi
            content_widget.update(Markdown(self.full_text))
            scroll_area = self.app.query_one("#chat_messages", VerticalScroll)
            scroll_area.scroll_end(animate=True)


# ==============================================================================
# APLIKASI UTAMA (GEMINI TERMINAL AGENT)
# ==============================================================================
class GeminiTerminalAgentApp(App[None]):
    """Aplikasi TUI Textual utama untuk Gemini Terminal Agent dengan Memori & Sesi."""

    CSS = APP_CSS
    TITLE = "Gemini Terminal Agent"

    BINDINGS = [
        Binding("ctrl+s", "open_session_modal", "Sesi", show=True),
        Binding("ctrl+m", "open_model_select", "Pilih Model", show=True),
        Binding("ctrl+t", "cycle_theme", "Ganti Tema", show=True),
        Binding("ctrl+l", "clear_chat", "Bersihkan Chat", show=True),
        Binding("ctrl+c", "quit_app", "Keluar", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.agent: Optional[GeminiAgent] = None
        self.active_tool_card: Optional[ToolCallCard] = None
        self.active_theme: str = config_manager.get_theme()

    def compose(self) -> ComposeResult:
        # Header Atas
        with Horizontal(id="app_header"):
            yield Label("⌬ GEMINI TERMINAL AGENT ─ v1.2 (Memory & Sesi)", id="header_title")
            yield Label("LIVE CLOCK", id="header_clock")

        # Kontainer Pesan
        yield VerticalScroll(id="chat_messages")

        # Indikator Berpikir (disembunyikan saat idle)
        with Horizontal(id="thinking_box"):
            yield LoadingIndicator()
            yield Label("  [▒▒▒▒] Agen sedang menganalisis & memproses...")

        # Input Area
        with Horizontal(id="input_container"):
            yield Input(
                placeholder="Ketik instruksi, /session, /memory, atau /help...",
                id="chat_input",
            )
            yield Button("Kirim ⏵", id="btn_send")

        # Status Bar Bawah
        with Horizontal(id="status_bar"):
            yield Label("[⌬ MODEL: Inisialisasi...]", id="status_model", classes="status-model")
            yield Label("[🗎 SESI: Inisialisasi...]", id="status_session", classes="status-session")
            yield Label("[● READY]", id="status_state", classes="status-state")
            yield Label("[Ctrl+S: Sesi | Ctrl+M: Model | Ctrl+T: Tema | Ctrl+C: Quit]", classes="status-hints")

    def on_mount(self) -> None:
        """Inisialisasi clock live dan verifikasi alur first-run."""
        # Sembunyikan thinking box pada awal start
        self.query_one("#thinking_box").display = False

        # Terapkan tema aktif
        self.apply_theme(self.active_theme)

        # Live clock update tiap 1 detik
        self.update_live_clock()
        self.set_interval(1.0, self.update_live_clock)

        # Cek alur first-run
        self.check_first_run()

    def update_live_clock(self) -> None:
        """Memperbarui label jam di header."""
        now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        self.query_one("#header_clock", Label).update(f"│ {now}")

    def check_first_run(self) -> None:
        """Mengecek keberadaan API key dan model tersimpan."""
        api_key = config_manager.get_api_key()
        if not api_key:
            self.push_screen(ApiKeyModal(), self._on_key_configured)
            return

        model_name = config_manager.get_model()
        if not model_name:
            self.push_screen(ModelSelectModal(api_key), self._on_model_configured)
            return

        self._start_agent(api_key, model_name)

    def _on_key_configured(self, api_key: str) -> None:
        model_name = config_manager.get_model()
        if not model_name:
            self.push_screen(ModelSelectModal(api_key), self._on_model_configured)
        else:
            self._start_agent(api_key, model_name)

    def _on_model_configured(self, model_name: str) -> None:
        api_key = config_manager.get_api_key() or ""
        self._start_agent(api_key, model_name)
        self.flash_model_transition(model_name)

    def _start_agent(self, api_key: str, model_name: str) -> None:
        """Menginisialisasi instance agent dan memulihkan sesi aktif atau menyapa pengguna."""
        try:
            self.agent = GeminiAgent(api_key=api_key, model_name=model_name)
            self.update_status_bar(model_name, "ONLINE", self.agent.session.title)

            # Jika sesi aktif memiliki riwayat pesan sebelumnya, pulihkan tampilannya
            if self.agent.session.ui_messages:
                self.restore_session_ui(self.agent.session)
            else:
                welcome_text = (
                    f"Sistem aktif dengan model `{model_name}`.\n"
                    f"Tema saat ini: `{self.active_theme}`.\n"
                    f"Sesi aktif: `{self.agent.session.title}` (ID: `{self.agent.session.session_id}`).\n\n"
                    "Tool yang tersedia:\n"
                    "- Operasi File: `create_folder`, `list_files`, `read_file`, `write_file`\n"
                    "- Shell Sistem: `run_command`\n"
                    "- Memori Jangka Panjang: `save_memory`, `recall_memory`, `list_memories`\n\n"
                    "Fitur Baru:\n"
                    "- `Ctrl + S` : Buka jendela Manajemen Sesi (pulihkan atau buat sesi)\n"
                    "- `/session` : Perintah pengelolaan sesi (/session list, load, new, delete)\n"
                    "- `/memory` : Perintah pengelolaan ingatan jangka panjang\n\n"
                    "Ketik `/help` untuk panduan lengkap."
                )
                self.append_system_message(welcome_text)
        except Exception as exc:
            err = agent_logger.diagnose_and_format_error(exc, "init_agent", model_name)
            self.append_error_message(err.to_cli_string())

    def update_status_bar(
        self,
        model_name: str,
        state: str,
        session_title: Optional[str] = None,
    ) -> None:
        """Memperbarui teks pada status bar bagian bawah."""
        self.query_one("#status_model", Label).update(f"[⌬ {model_name}]")
        self.query_one("#status_state", Label).update(f"[● {state}]")
        if session_title is not None:
            short_title = session_title[:20] + "..." if len(session_title) > 20 else session_title
            self.query_one("#status_session", Label).update(f"[🗎 {short_title}]")

    def flash_model_transition(self, new_model: str) -> None:
        """Animasi highlight transisi saat berganti model."""
        bar = self.query_one("#status_bar")
        bar.add_class("status-bar-highlight")
        self.update_status_bar(new_model, "MODEL BERGANTI")

        def _remove_highlight() -> None:
            bar.remove_class("status-bar-highlight")
            curr_title = self.agent.session.title if self.agent else None
            self.update_status_bar(new_model, "READY", curr_title)

        self.set_timer(1.5, _remove_highlight)

    # --------------------------------------------------------------------------
    # Render Bubble Chat
    # --------------------------------------------------------------------------
    def append_user_message(self, text: str) -> None:
        scroll = self.query_one("#chat_messages", VerticalScroll)
        box = Vertical(
            Label("⌬ ANDA:", classes="msg-user-title"),
            Label(text),
            classes="msg-user-box",
        )
        scroll.mount(box)
        scroll.scroll_end(animate=True)

    def append_system_message(self, markdown_text: str) -> None:
        scroll = self.query_one("#chat_messages", VerticalScroll)
        box = Vertical(
            Label(Markdown(markdown_text)),
            classes="msg-system-box",
        )
        scroll.mount(box)
        scroll.scroll_end(animate=True)

    def append_error_message(self, formatted_error: str) -> None:
        scroll = self.query_one("#chat_messages", VerticalScroll)
        box = Vertical(
            Label(formatted_error),
            classes="msg-error-box",
        )
        scroll.mount(box)
        scroll.scroll_end(animate=True)

    def restore_session_ui(self, session: Session) -> None:
        """Memulihkan dan merender seluruh pesan visual dari sesi yang dipilih."""
        scroll = self.query_one("#chat_messages", VerticalScroll)
        for child in list(scroll.children):
            child.remove()

        for msg in session.ui_messages:
            if msg.msg_type == "user":
                box = Vertical(
                    Label("⌬ ANDA:", classes="msg-user-title"),
                    Label(msg.text),
                    classes="msg-user-box",
                )
                scroll.mount(box)
            elif msg.msg_type == "tool":
                card = ToolCallCard(
                    tool_name=msg.tool_name,
                    args=msg.tool_args,
                    initial_preview=msg.tool_preview,
                )
                scroll.mount(card)
            elif msg.msg_type == "agent":
                card = TypingMessageCard(full_text=msg.text, animate=False)
                scroll.mount(card)
            elif msg.msg_type == "system":
                box = Vertical(
                    Label(Markdown(msg.text)),
                    classes="msg-system-box",
                )
                scroll.mount(box)

        scroll.scroll_end(animate=False)
        self.update_status_bar(
            self.agent.model_name if self.agent else "-",
            "READY",
            session.title,
        )
        self.append_system_message(
            f"Sesi **{session.title}** ({len(session.ui_messages)} pesan) dipulihkan. Konteks percakapan siap dilanjutkan."
        )

    # --------------------------------------------------------------------------
    # Interaksi Pengguna & Perintah Slash
    # --------------------------------------------------------------------------
    @on(Button.Pressed, "#btn_send")
    @on(Input.Submitted, "#chat_input")
    def handle_submit(self) -> None:
        input_widget = self.query_one("#chat_input", Input)
        raw_msg = input_widget.value.strip()
        if not raw_msg:
            return

        input_widget.value = ""

        # Tangani perintah slash
        if raw_msg.startswith("/"):
            self.handle_slash_command(raw_msg)
            return

        # Kirim pesan percakapan biasa ke Agent
        self.append_user_message(raw_msg)
        self.dispatch_agent_message(raw_msg)

    def handle_slash_command(self, cmd_text: str) -> None:
        parts = cmd_text.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command == "/quit":
            self.action_quit_app()

        elif command == "/clear":
            self.action_clear_chat()

        elif command in ["/session", "/sessions"]:
            self._handle_session_command(arg)

        elif command == "/memory":
            self._handle_memory_command(arg)

        elif command == "/theme":
            if arg in THEMES:
                self.apply_theme(arg)
                self.append_system_message(f"Tema berhasil diubah ke: `{arg}`")
            else:
                themes_list = ", ".join([f"`{t}`" for t in THEMES.keys()])
                self.append_system_message(f"Tema `{arg}` tidak ditemukan. Pilihan: {themes_list}")

        elif command == "/model":
            if arg:
                config_manager.save_model(arg)
                if self.agent:
                    self.agent.change_model(arg)
                self.flash_model_transition(arg)
                self.append_system_message(f"Model aktif dialihkan secara langsung ke: `{arg}`")
            else:
                self.action_open_model_select()

        elif command == "/help":
            help_content = (
                "### Panduan Perintah Slash & Pintasan\n\n"
                "| Perintah | Fungsi |\n"
                "| :--- | :--- |\n"
                "| `/session` | Buka jendela modal manajemen & pemulihan sesi |\n"
                "| `/session list` | Tampilkan daftar semua sesi yang tersimpan |\n"
                "| `/session load <id/no>` | Pulihkan dan masuk ke sesi tertentu |\n"
                "| `/session new [judul]` | Mulai sesi percakapan baru yang segar |\n"
                "| `/session rename <judul>`| Beri nama baru untuk sesi aktif saat ini |\n"
                "| `/session delete <id/no>`| Hapus sesi percakapan dari disk |\n"
                "| `/session info` | Informasi detail tentang sesi aktif saat ini |\n"
                "| `/memory` | Tampilkan daftar memori jangka panjang agent |\n"
                "| `/memory set <key> <val>`| Simpan instruksi/fakta ke memori persisten |\n"
                "| `/memory delete <key>` | Hapus kunci memori tertentu |\n"
                "| `/memory clear` | Kosongkan seluruh memori jangka panjang |\n"
                "| `/model [nama]` | Buka seleksi model atau langsung ganti model |\n"
                "| `/theme <nama>` | Ganti tema UI (default, emerald, crimson, amber, purple) |\n"
                "| `/clear` | Mulai sesi baru & bersihkan layar chat |\n"
                "| `/quit` | Keluar dari aplikasi terminal agent |\n\n"
                "### Pintasan Keyboard\n"
                "- `Ctrl + S` : Buka Layar Manajemen Sesi\n"
                "- `Ctrl + M` : Buka Layar Pemilihan Model\n"
                "- `Ctrl + T` : Ganti tema secara berurutan\n"
                "- `Ctrl + L` : Bersihkan chat / mulai sesi baru\n"
                "- `Ctrl + C` : Keluar dari aplikasi\n"
            )
            self.append_system_message(help_content)
        else:
            self.append_system_message(f"[!] Perintah `{command}` tidak dikenal. Ketik `/help` untuk panduan.")

    def _handle_session_command(self, arg: str) -> None:
        """Menangani sub-perintah /session."""
        if not self.agent:
            self.append_error_message("[X] Agent belum diinisialisasi.")
            return

        if not arg or arg == "modal":
            self.action_open_session_modal()
            return

        subparts = arg.split(maxsplit=1)
        subcmd = subparts[0].lower()
        subarg = subparts[1].strip() if len(subparts) > 1 else ""

        if subcmd == "list":
            sessions = session_manager.list_sessions()
            if not sessions:
                self.append_system_message("Belum ada riwayat sesi tersimpan.")
                return

            lines = ["### Daftar Sesi Tersimpan\n"]
            lines.append("| No | Sesi | ID | Pesan | Model | Terakhir Diperbarui |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for idx, s in enumerate(sessions, 1):
                is_active = (s["session_id"] == self.agent.session.session_id)
                tag = " `[AKTIF]`" if is_active else ""
                title = s["title"] + tag
                updated = s["updated_at"][:19].replace("T", " ") if s["updated_at"] else "-"
                lines.append(f"| {idx} | {title} | `{s['session_id']}` | {s['message_count']} | `{s['model_name']}` | {updated} |")
            lines.append("\nKetik `/session load <nomor_atau_id>` untuk berpindah sesi.")
            self.append_system_message("\n".join(lines))

        elif subcmd == "load":
            if not subarg:
                self.append_system_message("[!] Tentukan nomor urut atau ID sesi. Contoh: `/session load 1`")
                return

            target_id = self._resolve_session_id(subarg)
            if not target_id:
                self.append_system_message(f"[!] Sesi '{subarg}' tidak ditemukan.")
                return

            target_sess = session_manager.get_session(target_id)
            if not target_sess:
                self.append_system_message(f"[!] Gagal memuat file sesi: {target_id}")
                return

            self.agent.switch_session(target_sess)
            self.restore_session_ui(target_sess)

        elif subcmd == "new":
            new_title = subarg if subarg else None
            new_sess = self.agent.create_new_session(title=new_title)
            self.restore_session_ui(new_sess)
            self.append_system_message(f"Sesi baru dimulai: **{new_sess.title}** (ID: `{new_sess.session_id}`).")

        elif subcmd in ["rename", "title"]:
            if not subarg:
                self.append_system_message("[!] Masukkan judul baru. Contoh: `/session rename Proyek Analisis Data`")
                return
            self.agent.session.title = subarg
            session_manager.save_session(self.agent.session)
            self.update_status_bar(self.agent.model_name, "READY", subarg)
            self.append_system_message(f"Judul sesi aktif diubah menjadi: **{subarg}**")

        elif subcmd == "delete":
            if not subarg:
                self.append_system_message("[!] Tentukan nomor urut atau ID sesi yang ingin dihapus.")
                return

            target_id = self._resolve_session_id(subarg)
            if not target_id:
                self.append_system_message(f"[!] Sesi '{subarg}' tidak ditemukan.")
                return

            if target_id == self.agent.session.session_id:
                self.append_system_message("[!] Tidak dapat menghapus sesi yang sedang aktif. Beralihlah ke sesi lain terlebih dahulu.")
                return

            session_manager.delete_session(target_id)
            self.append_system_message(f"Sesi `{target_id}` berhasil dihapus.")

        elif subcmd == "info":
            s = self.agent.session
            info_text = (
                f"### Informasi Sesi Aktif\n\n"
                f"- **Judul Sesi**: {s.title}\n"
                f"- **ID Sesi**: `{s.session_id}`\n"
                f"- **Model**: `{s.model_name}`\n"
                f"- **Jumlah Pesan**: {len(s.ui_messages)}\n"
                f"- **Jumlah Putaran Multi-Turn**: {len(s.history)}\n"
                f"- **Waktu Dibuat**: {s.created_at[:19].replace('T', ' ')}\n"
                f"- **Waktu Terakhir Diperbarui**: {s.updated_at[:19].replace('T', ' ')}\n"
            )
            self.append_system_message(info_text)

        else:
            self.append_system_message(f"[!] Perintah `/session {subcmd}` tidak dikenal. Ketik `/help` untuk panduan.")

    def _resolve_session_id(self, input_str: str) -> Optional[str]:
        """Menemukan ID sesi baik dari nomor urut (1-based index) maupun ID teks."""
        sessions = session_manager.list_sessions()
        if input_str.isdigit():
            idx = int(input_str) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]["session_id"]
        for s in sessions:
            if s["session_id"] == input_str or s["session_id"].startswith(input_str):
                return s["session_id"]
        return None

    def _handle_memory_command(self, arg: str) -> None:
        """Menangani sub-perintah /memory."""
        if not arg or arg == "list":
            mems = memory_manager.get_all()
            if not mems:
                self.append_system_message("Memori jangka panjang masih kosong. Gunakan `/memory set <kunci> <nilai>` untuk menambahkan fakta.")
                return

            lines = ["### Memori Jangka Panjang Persisten\n"]
            lines.append("Fakta berikut selalu diingat agen di semua sesi:\n")
            lines.append("| Kunci (Key) | Nilai (Value) |")
            lines.append("| :--- | :--- |")
            for k, v in mems.items():
                lines.append(f"| `{k}` | {v} |")
            self.append_system_message("\n".join(lines))

        elif arg.startswith("set "):
            rest = arg[4:].strip()
            parts = rest.split(maxsplit=1)
            if len(parts) < 2:
                self.append_system_message("[!] Format salah. Gunakan: `/memory set <kunci> <nilai>`")
                return
            k, v = parts[0], parts[1]
            memory_manager.set(k, v)
            if self.agent:
                self.agent._init_chat_session()
            self.append_system_message(f"Memori disimpan: `{k}` = **{v}**. Konteks agen diperbarui.")

        elif arg.startswith("delete "):
            k = arg[7:].strip()
            if memory_manager.delete(k):
                if self.agent:
                    self.agent._init_chat_session()
                self.append_system_message(f"Kunci memori `{k}` berhasil dihapus.")
            else:
                self.append_system_message(f"[!] Kunci memori `{k}` tidak ditemukan.")

        elif arg == "clear":
            memory_manager.clear()
            if self.agent:
                self.agent._init_chat_session()
            self.append_system_message("Seluruh memori jangka panjang telah dikosongkan.")

        else:
            self.append_system_message("[!] Sub-perintah `/memory` tidak dikenal. Pilihan: `/memory`, `/memory set <kunci> <nilai>`, `/memory delete <kunci>`, `/memory clear`")

    # --------------------------------------------------------------------------
    # Eksekusi Pemanggilan Agent di Background Worker Thread
    # --------------------------------------------------------------------------
    @work(thread=True)
    def dispatch_agent_message(self, message: str) -> None:
        if not self.agent:
            self.app.call_from_thread(
                self.append_error_message,
                "[X] Agen belum diinisialisasi. Periksa API Key dan Model.",
            )
            return

        self.app.call_from_thread(self._set_thinking_state, True)

        try:
            response_text = self.agent.send_message(
                message=message,
                on_tool_call=self._ui_tool_call_start,
                on_tool_result=self._ui_tool_call_finish,
            )
            self.app.call_from_thread(self._render_agent_response, response_text)
            self.app.call_from_thread(
                self.update_status_bar,
                self.agent.model_name,
                "READY",
                self.agent.session.title,
            )
        except Exception as exc:
            err = agent_logger.diagnose_and_format_error(
                exc=exc,
                context="generate: send_message",
                active_model=self.agent.model_name,
            )
            self.app.call_from_thread(self.append_error_message, err.to_cli_string())
        finally:
            self.app.call_from_thread(self._set_thinking_state, False)

    def _set_thinking_state(self, is_thinking: bool) -> None:
        self.query_one("#thinking_box").display = is_thinking
        status = "BERPIKIR..." if is_thinking else "READY"
        title = self.agent.session.title if self.agent else None
        self.update_status_bar(self.agent.model_name if self.agent else "-", status, title)

    def _ui_tool_call_start(self, tool_name: str, args: dict[str, Any]) -> None:
        def _add_card() -> None:
            scroll = self.query_one("#chat_messages", VerticalScroll)
            card = ToolCallCard(tool_name, args)
            self.active_tool_card = card
            scroll.mount(card)
            scroll.scroll_end(animate=True)

        self.call_from_thread(_add_card)

    def _ui_tool_call_finish(self, tool_name: str, preview: str) -> None:
        def _update_card() -> None:
            if self.active_tool_card:
                self.active_tool_card.mark_completed(preview)
                self.active_tool_card = None
            scroll = self.query_one("#chat_messages", VerticalScroll)
            scroll.scroll_end(animate=True)

        self.call_from_thread(_update_card)

    def _render_agent_response(self, full_text: str) -> None:
        scroll = self.query_one("#chat_messages", VerticalScroll)
        card = TypingMessageCard(full_text)
        scroll.mount(card)
        scroll.scroll_end(animate=True)

    # --------------------------------------------------------------------------
    # Action Bindings
    # --------------------------------------------------------------------------
    def action_quit_app(self) -> None:
        self.exit()

    def action_clear_chat(self) -> None:
        """Membuat sesi percakapan baru yang segar (riwayat lama tetap tersimpan di disk)."""
        if self.agent:
            new_sess = self.agent.create_new_session()
            self.restore_session_ui(new_sess)
            self.append_system_message(f"Sesi baru dimulai: **{new_sess.title}** (Riwayat sebelumnya tetap tersimpan di disk).")
        else:
            scroll = self.query_one("#chat_messages", VerticalScroll)
            for child in list(scroll.children):
                child.remove()

    def action_open_session_modal(self) -> None:
        """Membuka modal manajemen sesi untuk memulihkan atau membuat sesi."""
        curr_id = self.agent.session.session_id if self.agent else ""
        self.push_screen(SessionSelectModal(curr_id), self._on_session_selected)

    def _on_session_selected(self, selected_sess_id: Optional[str]) -> None:
        """Callback setelah pengguna memilih sesi dari SessionSelectModal."""
        if not selected_sess_id or not self.agent:
            return

        if selected_sess_id == "__NEW__":
            new_sess = self.agent.create_new_session()
            self.restore_session_ui(new_sess)
            self.append_system_message(f"Sesi baru berhasil dibuat: **{new_sess.title}**.")
        else:
            target_sess = session_manager.get_session(selected_sess_id)
            if target_sess:
                self.agent.switch_session(target_sess)
                self.restore_session_ui(target_sess)

    def action_open_model_select(self) -> None:
        api_key = config_manager.get_api_key()
        if not api_key:
            self.push_screen(ApiKeyModal(), self._on_key_configured)
        else:
            self.push_screen(ModelSelectModal(api_key), self._on_model_reselected)

    def _on_model_reselected(self, new_model: str) -> None:
        if self.agent:
            self.agent.change_model(new_model)
        self.flash_model_transition(new_model)
        self.append_system_message(f"Model berhasil diperbarui ke: `{new_model}` (konteks sesi tetap terjaga).")

    def apply_theme(self, theme_name: str) -> None:
        """Menerapkan tema visual baru pada antarmuka terminal."""
        if theme_name not in THEMES:
            theme_name = "default"
        self.active_theme = theme_name
        config_manager.save_theme(theme_name)
        for t in THEMES:
            self.screen.remove_class(f"theme-{t}")
        self.screen.add_class(f"theme-{theme_name}")

    def action_cycle_theme(self) -> None:
        """Beralih ke tema berikutnya secara melingkar (Ctrl+T)."""
        theme_names = list(THEMES.keys())
        try:
            curr_idx = theme_names.index(self.active_theme)
            next_idx = (curr_idx + 1) % len(theme_names)
        except ValueError:
            next_idx = 0
        new_theme = theme_names[next_idx]
        self.apply_theme(new_theme)
        self.append_system_message(f"Tema tampilan dialihkan ke: `{new_theme}`")


def main() -> None:
    """Entry point peluncuran aplikasi."""
    app = GeminiTerminalAgentApp()
    app.run()


if __name__ == "__main__":
    main()
