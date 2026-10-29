"""Bridge Otomasi Antigravity IDE untuk Pengendalian Jarak Jauh via Telegram Gateway."""

from __future__ import annotations

import ctypes
import os
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

    def _focus_window(self, click: bool = True) -> bool:
        """Membawa jendela Antigravity ke Foreground via Win32 API, SetWindowPos TOPMOST, dan klik mouse nyata."""
        self._attach_desktop()

        hwnd = self._find_window_hwnd()
        if hwnd:
            try:
                user32 = ctypes.windll.user32
                from ctypes import wintypes

                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))

                # 1. Restore bila minimized, atau show normal
                if user32.IsIconic(hwnd):
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
                if win.IsIconic():
                    win.Restore()
                win.SetActive()
                win.SetTopmost(True)
                win.SetTopmost(False)
                return True
            except Exception as exc:
                agent_logger.log_warning("antigravity_bridge", f"Gagal fokus window via UIAutomation: {exc}")

        return False

    def launch_or_focus(self, workspace_path: Optional[str] = None, click: bool = True) -> bool:
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

        focused = self._focus_window(click=click)
        agent_logger.log_info("antigravity_bridge", f"launch_or_focus(workspace='{ws}', click={click}) -> {focused}")
        return focused

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

    def get_active_model(self) -> dict[str, str]:
        """Mengambil model Antigravity yang sedang aktif saat ini."""
        models = self.get_available_models()
        active_id = "gemini-3.8-flash-medium"
        if self.MODEL_CONFIG_PATH.exists():
            try:
                import json
                with open(self.MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    active_id = cfg.get("selected_model", active_id)
            except Exception:
                pass

        for m in models:
            if m["id"] == active_id:
                return m
        return models[0] if models else {"id": active_id, "name": active_id, "icon": "🧠"}

    def set_active_model(self, model_query: str) -> tuple[bool, dict[str, str]]:
        """Mengatur model aktif Antigravity dengan pencocokan nama / ID yang fleksibel."""
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

        # Simpan preferensi model ke file persist
        try:
            import json
            with open(self.MODEL_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"selected_model": target_model["id"], "model_name": target_model["name"]}, f, indent=2)
            agent_logger.log_info("antigravity_bridge", f"Model Antigravity aktif disetel ke: {target_model['id']} ({target_model['name']})")
            return True, target_model
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal menyimpan model config: {exc}")
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
        target = output_path or (Path.cwd() / "antigravity_screenshot.png")
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


antigravity_bridge = AntigravityBridge()

