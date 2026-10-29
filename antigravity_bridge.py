"""Bridge Otomasi Antigravity IDE untuk Pengendalian Jarak Jauh via Telegram Gateway."""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

import psutil
from PIL import ImageGrab

from logger import agent_logger


def _win32_mouse_click(x: int, y: int) -> None:
    """Melakukan klik mouse fisik pada koordinat (x, y) menggunakan Win32 API murni (zero-dependency)."""
    try:
        user32 = ctypes.windll.user32
        from ctypes import wintypes

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        orig_x, orig_y = pt.x, pt.y

        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.04)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
        time.sleep(0.04)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
        time.sleep(0.04)
        user32.SetCursorPos(orig_x, orig_y)
    except Exception as exc:
        agent_logger.log_warning("antigravity_bridge", f"Gagal _win32_mouse_click: {exc}")


def _win32_send_hotkey(*keys: str) -> None:
    """Mengirim kombinasi tombol keyboard menggunakan Win32 keybd_event murni (zero-dependency)."""
    VK_MAP = {
        "ctrl": 0x11,
        "alt": 0x12,
        "shift": 0x10,
        "enter": 0x0D,
        "return": 0x0D,
        "l": ord("L"),
        "v": ord("V"),
        "`": 0xC0,  # VK_OEM_3 (backtick)
        "backtick": 0xC0,
    }
    KEYEVENTF_KEYUP = 0x0002
    user32 = ctypes.windll.user32

    vk_list = [VK_MAP.get(k.lower(), ord(k.upper()) if len(k) == 1 else 0) for k in keys]
    vk_list = [vk for vk in vk_list if vk != 0]

    for vk in vk_list:
        user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.04)
    for vk in reversed(vk_list):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.04)


def _win32_copy_to_clipboard(text: str) -> bool:
    """Menyalin teks ukuran berapa pun ke clipboard Windows (Unicode 16-bit) tanpa batasan buffer."""
    if not text:
        return False

    # 1. Gunakan Win32 Clipboard API murni via ctypes 64-bit lengkap
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool

        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = ctypes.c_bool

        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                raw_bytes = (text + "\0").encode("utf-16le")
                h_mem = kernel32.GlobalAlloc(0x0002, len(raw_bytes))  # GMEM_MOVEABLE
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    if ptr:
                        ctypes.memmove(ptr, raw_bytes, len(raw_bytes))
                        kernel32.GlobalUnlock(h_mem)
                        if user32.SetClipboardData(13, h_mem):  # CF_UNICODETEXT
                            return True
            finally:
                user32.CloseClipboard()
    except Exception as exc:
        agent_logger.log_warning("antigravity_bridge", f"Win32 clipboard ctypes: {exc}")

    # 2. Fallback andal: clip.exe bawaan Windows dengan biner UTF-16LE murni
    try:
        subprocess.run(["clip"], input=text.encode("utf-16le"), check=True, timeout=5)
        return True
    except Exception as exc:
        agent_logger.log_error("antigravity_bridge", f"Gagal fallback clip.exe: {exc}")
        return False


class AntigravityBridge:
    """Mengendalikan Google Antigravity IDE (buka workspace, injeksi prompt, dan capture jendela)."""

    EXE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe"
    CMD_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "antigravity-ide.cmd"
    AGY_BIN_PATH = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "bin" / "agy.exe"
    MODEL_CONFIG_PATH = Path.cwd() / ".antigravity_model.json"
    ANTIGRAVITY_STATE_PATH = Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "antigravity_state.pbtxt"

    INTERNAL_MODEL_MAP: dict[str, str] = {
        "model_placeholder_m319": "gemini-3.8-flash-medium",
        "m319": "gemini-3.8-flash-medium",
        "model_placeholder_m318": "gemini-3.8-flash-high",
        "m318": "gemini-3.8-flash-high",
        "model_placeholder_m320": "gemini-3.8-flash-low",
        "m320": "gemini-3.8-flash-low",
        "model_placeholder_m321": "claude-sonnet-4-6",
        "m321": "claude-sonnet-4-6",
        "model_placeholder_m322": "claude-opus-4-6-thinking",
        "m322": "claude-opus-4-6-thinking",
        "model_placeholder_m323": "gpt-oss-120b-medium",
        "m323": "gpt-oss-120b-medium",
    }

    REVERSE_MODEL_MAP: dict[str, str] = {
        "gemini-3.8-flash-medium": "MODEL_PLACEHOLDER_M319",
        "gemini-3.8-flash-high": "MODEL_PLACEHOLDER_M318",
        "gemini-3.8-flash-low": "MODEL_PLACEHOLDER_M320",
        "claude-sonnet-4-6": "MODEL_PLACEHOLDER_M321",
        "claude-opus-4-6-thinking": "MODEL_PLACEHOLDER_M322",
        "gpt-oss-120b-medium": "MODEL_PLACEHOLDER_M323",
    }

    DEFAULT_MODELS: list[dict[str, str]] = [
        {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)", "icon": "🧠"},
        {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)", "icon": "⚡"},
        {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low)", "icon": "🔋"},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)", "icon": "🎭"},
        {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)", "icon": "🧙"},
        {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B (Medium)", "icon": "🌐"},
    ]

    def __init__(self) -> None:
        self._last_window: Any = None

    @staticmethod
    def _attach_desktop() -> None:
        """Memastikan thread terikat ke Input Desktop aktif Windows agar BitBlt/screenshot diizinkan."""
        try:
            user32 = ctypes.windll.user32
            user32.OpenInputDesktop.restype = ctypes.c_void_p
            user32.OpenInputDesktop.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
            user32.SetThreadDesktop.restype = ctypes.c_bool
            user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]

            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

    def _find_window_hwnd(self) -> Optional[int]:
        """Mencari HWND jendela Antigravity IDE aktif menggunakan EnumWindows Win32 dan filter PID psutil."""
        self._attach_desktop()
        user32 = ctypes.windll.user32
        target_hwnd: list[int] = []

        def enum_cb(hwnd: int, extra: Any) -> bool:
            if user32.IsWindowVisible(hwnd):
                # 1. Cek nama proses pemilik jendela untuk presisi 100%
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    pname = psutil.Process(pid.value).name().lower()
                    if "antigravity" in pname:
                        target_hwnd.append(hwnd)
                        return False
                except Exception:
                    pass

                # 2. Cek judul jendela dengan mengabaikan explorer.exe
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if "antigravity" in title and "explorer" not in title:
                        target_hwnd.append(hwnd)
                        return False
            return True

        try:
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            # Coba EnumDesktopWindows terlebih dahulu untuk desktop session aktif
            try:
                hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hdesk:
                    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_cb), 0)
            except Exception:
                pass

            if not target_hwnd:
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        except Exception as exc:
            agent_logger.log_warning("antigravity_bridge", f"Gagal EnumWindows: {exc}")

        return target_hwnd[0] if target_hwnd else None

    def is_running(self) -> bool:
        """Memeriksa apakah proses Antigravity IDE sedang aktif."""
        for p in psutil.process_iter(["name"]):
            try:
                name = (p.info["name"] or "").lower()
                if "antigravity" in name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _find_window(self) -> Any:
        """Mencari jendela Antigravity IDE aktif menggunakan UIAutomation."""
        self._attach_desktop()
        hwnd = self._find_window_hwnd()
        if hwnd:
            try:
                import uiautomation as auto

                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl:
                    self._last_window = ctrl
                    return ctrl
            except Exception:
                pass

        try:
            import uiautomation as auto

            root = auto.GetRootControl()
            for win in root.GetChildren():
                name = win.Name or ""
                if "Antigravity" in name:
                    self._last_window = win
                    return win
        except Exception as exc:
            agent_logger.log_warning("antigravity_bridge", f"Gagal mencari window via uiautomation: {exc}")
        return None

    def _focus_window(self, click: bool = True, maximize: bool = True) -> bool:
        """Membawa jendela Antigravity ke Foreground via Win32 API, SetWindowPos TOPMOST, maximize bila diminta, dan klik mouse nyata."""
        self._attach_desktop()

        hwnd = self._find_window_hwnd()
        if hwnd:
            try:
                user32 = ctypes.windll.user32
                from ctypes import wintypes

                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))

                # 1. Maksimalkan jendela bila diminta agar memenuhi layar penuh, atau restore/show
                if maximize:
                    user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                elif user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                else:
                    user32.ShowWindow(hwnd, 5)  # SW_SHOW

                # 2. Paksa Z-order ke tumpukan paling atas dengan toggle HWND_TOPMOST -> HWND_NOTOPMOST
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

                # 3. Lepas proteksi lock foreground dengan event ALT key
                user32.keybd_event(0x12, 0, 0, 0)
                user32.keybd_event(0x12, 0, 2, 0)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)

                # 4. Klik mouse fisik pada area title bar Antigravity agar Windows 100% menempatkannya di paling depan
                if click:
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w > 100 and h > 100:
                        click_x = max(rect.left + 80, min(rect.right - 180, rect.left + w // 2))
                        click_y = max(10, rect.top + 20)
                        _win32_mouse_click(click_x, click_y)

                time.sleep(0.3)
                return True
            except Exception as exc:
                agent_logger.log_warning("antigravity_bridge", f"Gagal fokus window via HWND: {exc}")

        # Fallback via uiautomation
        win = self._find_window()
        if win:
            try:
                if maximize:
                    try:
                        win.Maximize()
                    except Exception:
                        pass
                elif win.IsIconic():
                    win.Restore()
                win.SetActive()
                win.SetTopmost(True)
                win.SetTopmost(False)
                return True
            except Exception as exc:
                agent_logger.log_warning("antigravity_bridge", f"Gagal fokus window via UIAutomation: {exc}")

        return False

    def launch_or_focus(self, workspace_path: Optional[str] = None, click: bool = True, maximize: bool = True) -> bool:
        """Membuka Antigravity IDE atau membawa jendelanya ke depan."""
        ws = str(Path(workspace_path).resolve()) if workspace_path else str(Path.cwd().resolve())

        if not self.is_running():
            if self.CMD_PATH.exists():
                subprocess.Popen([str(self.CMD_PATH), ws], shell=True)
            elif self.EXE_PATH.exists():
                subprocess.Popen([str(self.EXE_PATH), ws])
            else:
                agent_logger.log_warning(
                    "antigravity_bridge",
                    f"Executable Antigravity tidak ditemukan di jalur standar ({self.EXE_PATH}).",
                )
            time.sleep(2.5)

        focused = self._focus_window(click=click, maximize=maximize)
        agent_logger.log_info("antigravity_bridge", f"launch_or_focus(workspace='{ws}', click={click}, maximize={maximize}) -> {focused}")
        return focused

    def maximize_window(self) -> bool:
        """Memaksimalkan jendela Antigravity IDE ke ukuran layar penuh (SW_MAXIMIZE)."""
        return self._focus_window(click=True, maximize=True)

    def get_available_models(self) -> list[dict[str, str]]:
        """Membaca daftar model AI yang tersedia dari CLI agy atau daftar resmi Antigravity."""
        models: list[dict[str, str]] = []
        if self.AGY_BIN_PATH.exists():
            try:
                res = subprocess.run(
                    [str(self.AGY_BIN_PATH), "models"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if "\t" in line:
                        p_id, p_name = line.split("\t", 1)
                        p_id = p_id.strip()
                        p_name = p_name.strip()
                        icon = "🧠"
                        if "high" in p_id or "flash-high" in p_id:
                            icon = "⚡"
                        elif "low" in p_id:
                            icon = "🔋"
                        elif "sonnet" in p_id:
                            icon = "🎭"
                        elif "opus" in p_id:
                            icon = "🧙"
                        elif "gpt" in p_id or "oss" in p_id:
                            icon = "🌐"
                        models.append({"id": p_id, "name": p_name, "icon": icon})
            except Exception as exc:
                agent_logger.log_warning("antigravity_bridge", f"Gagal membaca models via CLI agy: {exc}")

        if not models:
            models = list(self.DEFAULT_MODELS)
        return models

    def detect_ide_active_model(self) -> Optional[str]:
        """Membaca model yang sedang aktif secara riil di dalam Antigravity IDE (via state protobuf IDE)."""
        if self.ANTIGRAVITY_STATE_PATH.exists():
            try:
                with open(self.ANTIGRAVITY_STATE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    match = re.search(r"last_selected_agent_model:\s*(\w+)", content, re.IGNORECASE)
                    if match:
                        raw_key = match.group(1).lower()
                        return self.INTERNAL_MODEL_MAP.get(raw_key, raw_key)
            except Exception as exc:
                agent_logger.log_warning("antigravity_bridge", f"Gagal membaca antigravity_state.pbtxt: {exc}")
        return None

    def get_active_model(self) -> dict[str, str]:
        """Mengambil model Antigravity yang sedang aktif saat ini (otomatis sinkron dengan Antigravity IDE)."""
        models = self.get_available_models()
        active_id: Optional[str] = None

        # 1. Cek langsung model riil dari internal state Antigravity IDE
        ide_model_id = self.detect_ide_active_model()

        # 2. Cek file preferensi lokal (.antigravity_model.json)
        local_model_id = None
        local_mtime = 0.0
        if self.MODEL_CONFIG_PATH.exists():
            try:
                import json
                local_mtime = self.MODEL_CONFIG_PATH.stat().st_mtime
                with open(self.MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    local_model_id = cfg.get("selected_model")
            except Exception:
                pass

        # 3. Sinkronkan: jika state IDE tersedia, prioritaskan state IDE agar akurat dengan UI laptop
        state_mtime = self.ANTIGRAVITY_STATE_PATH.stat().st_mtime if self.ANTIGRAVITY_STATE_PATH.exists() else 0.0
        if ide_model_id:
            # Gunakan state IDE jika tidak ada setting lokal atau state IDE lebih terkini
            if not local_model_id or state_mtime >= (local_mtime - 1.0):
                active_id = ide_model_id
            else:
                active_id = local_model_id
        else:
            active_id = local_model_id or "gemini-3.8-flash-medium"

        # Simpan kembali ke file persist lokal agar sinkron
        if active_id:
            try:
                import json
                found_name = next((m["name"] for m in models if m["id"] == active_id), active_id)
                with open(self.MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump({"selected_model": active_id, "model_name": found_name}, f, indent=2)
            except Exception:
                pass

        for m in models:
            if m["id"] == active_id:
                return m

        # Fallback default ke Gemini Medium
        for m in models:
            if "medium" in m["id"]:
                return m

        return models[0] if models else {"id": active_id or "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)", "icon": "🧠"}

    def set_active_model(self, model_query: str) -> tuple[bool, dict[str, str]]:
        """Mengatur model aktif Antigravity dengan pencocokan nama / ID yang fleksibel & sinkronisasi dua arah."""
        q = model_query.strip().lower()
        if not q:
            return False, {}

        models = self.get_available_models()
        target_model = None

        # 1. Exact ID match
        for m in models:
            if m["id"].lower() == q:
                target_model = m
                break

        # 2. Match berdasarkan alias umum (misal 'medium', 'gemini medium', 'claude', dsb.)
        if not target_model:
            alias_map = {
                "medium": "gemini-3.8-flash-medium",
                "gemini medium": "gemini-3.8-flash-medium",
                "flash medium": "gemini-3.8-flash-medium",
                "high": "gemini-3.8-flash-high",
                "gemini high": "gemini-3.8-flash-high",
                "flash high": "gemini-3.8-flash-high",
                "low": "gemini-3.8-flash-low",
                "gemini low": "gemini-3.8-flash-low",
                "sonnet": "claude-sonnet-4-6",
                "claude sonnet": "claude-sonnet-4-6",
                "claude": "claude-sonnet-4-6",
                "opus": "claude-opus-4-6-thinking",
                "claude opus": "claude-opus-4-6-thinking",
                "gpt": "gpt-oss-120b-medium",
                "oss": "gpt-oss-120b-medium",
                "gpt-oss": "gpt-oss-120b-medium",
            }
            if q in alias_map:
                mapped_id = alias_map[q]
                for m in models:
                    if m["id"] == mapped_id:
                        target_model = m
                        break

        # 3. Partial substring match
        if not target_model:
            for m in models:
                if q in m["id"].lower() or q in m["name"].lower():
                    target_model = m
                    break

        if not target_model:
            return False, {}

        # Simpan preferensi model ke file persist lokal
        try:
            import json
            with open(self.MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"selected_model": target_model["id"], "model_name": target_model["name"]}, f, indent=2)
            agent_logger.log_info("antigravity_bridge", f"Model Antigravity aktif disetel ke: {target_model['id']} ({target_model['name']})")
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal menyimpan model config: {exc}")

        # Sinkronkan kembali ke state IDE Antigravity (two-way sync)
        if target_model["id"] in self.REVERSE_MODEL_MAP and self.ANTIGRAVITY_STATE_PATH.exists():
            try:
                with open(self.ANTIGRAVITY_STATE_PATH, "r", encoding="utf-8", errors="ignore") as f:
                    st_content = f.read()
                new_placeholder = self.REVERSE_MODEL_MAP[target_model["id"]]
                if "last_selected_agent_model:" in st_content:
                    st_content = re.sub(r"last_selected_agent_model:\s*\w+", f"last_selected_agent_model:  {new_placeholder}", st_content)
                    with open(self.ANTIGRAVITY_STATE_PATH, "w", encoding="utf-8") as f:
                        f.write(st_content)
                    agent_logger.log_info("antigravity_bridge", f"State Antigravity IDE berhasil disinkronkan ke: {new_placeholder}")
            except Exception as exc_sync:
                agent_logger.log_warning("antigravity_bridge", f"Gagal sync state IDE: {exc_sync}")

        return True, target_model

    def send_prompt(self, prompt_text: str, auto_submit: bool = True) -> bool:
        """Fokus ke chat Antigravity Agent, tempelkan teks prompt (clipboard), dan submit (tahan prompt panjang)."""
        if not prompt_text or not prompt_text.strip():
            return False

        self.launch_or_focus()
        time.sleep(0.4)

        try:
            # 1. Salin teks prompt ukuran berapa pun ke clipboard (Win32 Unicode 16-bit)
            ok_clip = _win32_copy_to_clipboard(prompt_text)
            if not ok_clip:
                agent_logger.log_warning("antigravity_bridge", "Peringatan: Gagal menyalin prompt ke clipboard.")

            # 2. Buka / fokus ke panel input chat Antigravity Agent (Ctrl+L)
            _win32_send_hotkey("ctrl", "l")
            time.sleep(0.35)

            # 3. Tempelkan teks prompt (Ctrl+V)
            _win32_send_hotkey("ctrl", "v")
            # Jeda adaptif: teks besar (1000+ karakter) butuh waktu render Monaco/Electron
            wait_render = 0.35 if len(prompt_text) < 500 else 0.65
            time.sleep(wait_render)

            # 4. Kirim enter jika auto_submit
            if auto_submit:
                _win32_send_hotkey("enter")

            agent_logger.log_info(
                "antigravity_bridge",
                f"Prompt dikirim ke Antigravity ({len(prompt_text)} karakter, auto_submit={auto_submit}).",
            )
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal mengirim prompt: {exc}")
            return False

    def trigger_proceed(self) -> bool:
        """Mencari tombol 'Proceed' / 'Allow' pada Antigravity IDE atau mengirim Enter konfirmasi."""
        self.launch_or_focus()
        time.sleep(0.25)

        # Coba deteksi via UIAutomation tombol jika accessibility aktif
        try:
            import uiautomation as auto

            win = self._find_window()
            if win:
                for name_target in ["Proceed", "Proceed (Enter)", "Allow", "Run", "Continue"]:
                    btn = win.ButtonControl(Name=name_target)
                    if btn.Exists(maxSearchSeconds=0.5):
                        btn.Click()
                        agent_logger.log_info("antigravity_bridge", f"Tombol '{name_target}' berhasil ditekan.")
                        return True
        except Exception:
            pass

        # Fallback andal: Kirim tombol Enter langsung ke jendela aktif Antigravity via Win32 murni
        try:
            _win32_send_hotkey("enter")
            agent_logger.log_info("antigravity_bridge", "Proceed dipicu via Enter Win32 keybd_event.")
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal trigger proceed: {exc}")
            return False

    def _find_and_click_accept_all_button(self) -> bool:
        """Mendeteksi tombol fisik biru [Accept all] di layar via Computer Vision dan mengkliknya secara presisi."""
        self._attach_desktop()
        try:
            from PIL import ImageGrab

            img = ImageGrab.grab(all_screens=True)
            w, h = img.size

            # Tombol [Accept all] berada di panel kanan/bawah (area chat Antigravity)
            start_x = int(w * 0.4)
            end_x = int(w - 10)
            start_y = int(h * 0.25)
            end_y = int(h - 40)

            blue_pts: list[tuple[int, int]] = []
            for y in range(start_y, end_y, 2):
                for x in range(start_x, end_x, 2):
                    r, g, b = img.getpixel((x, y))[:3]
                    # Warna khas tombol biru Antigravity: R <= 35, 95 <= G <= 215, B >= 175, B > G > R
                    if r <= 35 and 95 <= g <= 215 and b >= 175 and b > g:
                        blue_pts.append((x, y))

            if not blue_pts:
                return False

            # Kelompokkan piksel berdekatan menjadi cluster
            clusters: list[list[tuple[int, int]]] = []
            for p in blue_pts:
                matched = False
                for c in clusters:
                    last_p = c[-1]
                    if abs(p[0] - last_p[0]) <= 14 and abs(p[1] - last_p[1]) <= 10:
                        c.append(p)
                        matched = True
                        break
                if not matched:
                    clusters.append([p])

            # Filter cluster yang memiliki karakteristik bentuk tombol
            candidates = []
            for c in clusters:
                if len(c) >= 20:
                    xs = [p[0] for p in c]
                    ys = [p[1] for p in c]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    bw = max_x - min_x
                    bh = max_y - min_y
                    if 30 <= bw <= 180 and 8 <= bh <= 50:
                        cx = (min_x + max_x) // 2
                        cy = (min_y + max_y) // 2
                        candidates.append((cx, cy, len(c), bw, bh))

            if candidates:
                # Pilih kandidat dengan piksel terbanyak di area paling bawah (terdekat ke input chat)
                candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
                target_cx, target_cy = candidates[0][0], candidates[0][1]

                agent_logger.log_info(
                    "antigravity_bridge",
                    f"Tombol biru [Accept all] terdeteksi di ({target_cx}, {target_cy}) w={candidates[0][3]} h={candidates[0][4]}! Mengklik mouse fisik...",
                )
                _win32_mouse_click(target_cx, target_cy)
                time.sleep(0.25)
                return True

            return False
        except Exception as exc:
            agent_logger.log_warning("antigravity_bridge", f"Gagal computer vision accept all button: {exc}")
            return False

    def trigger_accept_all(self) -> bool:
        """Menyetujui semua perubahan berkas (Accept all changes) di Antigravity IDE (Vision Click + Hotkey + Command Palette)."""
        self.launch_or_focus(click=True, maximize=True)
        time.sleep(0.35)

        # 1. Prioritas Utama: Computer Vision Click tombol biru [Accept all] langsung di layar IDE
        clicked_vision = self._find_and_click_accept_all_button()
        if clicked_vision:
            agent_logger.log_info("antigravity_bridge", "Tombol Accept all berhasil diklik melalui Computer Vision.")
            return True

        # 2. Coba deteksi elemen UI 'Accept all' via UIAutomation
        try:
            import uiautomation as auto

            win = self._find_window()
            if win:
                for name_target in ["Accept all", "Accept All", "Accept all changes", "Accept All Changes", "Accept"]:
                    for ctrl_type in [auto.ButtonControl, auto.TextControl, auto.HyperlinkControl]:
                        elem = ctrl_type(searchFromControl=win, searchDepth=14, Name=name_target)
                        if elem.Exists(maxSearchSeconds=0.2):
                            elem.Click()
                            agent_logger.log_info("antigravity_bridge", f"Elemen '{name_target}' berhasil diklik via UIAutomation.")
                            return True
        except Exception as exc_ui:
            agent_logger.log_warning("antigravity_bridge", f"UIAutomation accept all: {exc_ui}")

        # 3. Kirim kombinasi tombol resmi Antigravity IDE: Alt + Enter (antigravity.inlineDiff.acceptAll & acceptAgentStep)
        try:
            _win32_send_hotkey("alt", "enter")
            time.sleep(0.2)
            agent_logger.log_info("antigravity_bridge", "Accept all dipicu via Alt+Enter resmi Antigravity.")
        except Exception as exc_hotkey:
            agent_logger.log_warning("antigravity_bridge", f"Gagal Alt+Enter: {exc_hotkey}")

        # 4. Command Palette fallback: Ctrl+Shift+P -> 'Antigravity: Accept All Changes'
        try:
            time.sleep(0.15)
            _win32_send_hotkey("ctrl", "shift", "p")
            time.sleep(0.35)
            _win32_copy_to_clipboard("Antigravity: Accept All Changes")
            _win32_send_hotkey("ctrl", "v")
            time.sleep(0.35)
            _win32_send_hotkey("enter")
            agent_logger.log_info("antigravity_bridge", "Accept all dipicu via Command Palette Antigravity.")
        except Exception as exc_cmd:
            agent_logger.log_warning("antigravity_bridge", f"Gagal Command Palette accept all: {exc_cmd}")

        return True

    def open_integrated_terminal_and_run(self, command: str) -> bool:
        """Membuka terminal terintegrasi Antigravity dan mengeksekusi perintah."""
        self.launch_or_focus()
        time.sleep(0.3)

        try:
            # 1. Buka/fokus terminal terintegrasi (Ctrl+`)
            _win32_send_hotkey("ctrl", "`")
            time.sleep(0.35)

            # 2. Salin perintah ke clipboard
            _win32_copy_to_clipboard(command)

            # 3. Tempel dan eksekusi
            _win32_send_hotkey("ctrl", "v")
            time.sleep(0.15)
            _win32_send_hotkey("enter")

            agent_logger.log_info("antigravity_bridge", f"Perintah terminal dikirim: {command}")
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal kirim perintah terminal: {exc}")
            return False

    def capture_window_screenshot(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Mengambil tangkapan layar fullscreen layar dengan jendela Antigravity difokuskan dan diklik ke paling depan."""
        target = Path(output_path) if output_path else (Path.cwd() / "antigravity_screenshot.png")
        self._attach_desktop()

        # 1. Bawa jendela Antigravity ke Foreground terdepan dengan klik mouse nyata
        self.launch_or_focus(click=True)
        time.sleep(0.4)

        try:
            # 2. Ambil tangkapan layar Fullscreen penuh agar tampilan Antigravity tidak terpotong
            img = ImageGrab.grab(all_screens=True)
            img.save(str(target), format="PNG")
            if target.exists() and target.stat().st_size > 500:
                agent_logger.log_info(
                    "antigravity_bridge",
                    f"Fullscreen screenshot Antigravity berhasil disimpan: {target} ({img.size[0]}x{img.size[1]})",
                )
                return target

            return None
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal capture fullscreen screenshot: {exc}")
            return None

    def find_latest_transcript_file(self) -> Optional[Path]:
        """Mencari berkas transcript.jsonl percakapan Antigravity terbaru di sistem."""
        brain_dirs = [
            Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity-ide" / "brain",
            Path(os.environ.get("USERPROFILE", "")) / ".gemini" / "antigravity" / "brain",
        ]
        newest_file: Optional[Path] = None
        newest_mtime: float = 0.0

        for b_dir in brain_dirs:
            if b_dir.exists():
                try:
                    for d in b_dir.iterdir():
                        if d.is_dir():
                            t_file = d / ".system_generated" / "logs" / "transcript.jsonl"
                            if t_file.exists():
                                try:
                                    mtime = t_file.stat().st_mtime
                                    if mtime > newest_mtime:
                                        newest_mtime = mtime
                                        newest_file = t_file
                                except Exception:
                                    pass
                except Exception:
                    pass
        return newest_file

    def get_latest_completed_response(
        self, transcript_file: Optional[Path] = None, since_timestamp: Optional[float] = None
    ) -> Optional[dict[str, Any]]:
        """Mencari respon PLANNER_RESPONSE terakhir yang selesai (status: DONE) dan memiliki konten."""
        t_file = transcript_file or self.find_latest_transcript_file()
        if not t_file or not t_file.exists():
            return None

        try:
            import json
            with open(t_file, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                buffer_size = min(size, 131072)  # Baca 128 KB terakhir
                f.seek(size - buffer_size)
                lines = f.read().decode("utf-8", errors="ignore").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            if (
                                obj.get("type") == "PLANNER_RESPONSE"
                                and obj.get("status") == "DONE"
                                and obj.get("content")
                            ):
                                if since_timestamp:
                                    created_str = obj.get("created_at", "")
                                    # Cek apakah timestamp step lebih baru
                                    try:
                                        import datetime
                                        dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                                        if dt.timestamp() < since_timestamp - 5:
                                            continue
                                    except Exception:
                                        pass
                                return obj
                        except Exception:
                            continue
        except Exception as exc:
            agent_logger.log_warning("antigravity_bridge", f"Gagal membaca latest completed response: {exc}")
        return None


antigravity_bridge = AntigravityBridge()

