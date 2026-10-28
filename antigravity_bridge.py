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


def _win32_copy_to_clipboard(text: str) -> None:
    """Menyalin teks ke clipboard menggunakan tool clip.exe bawaan Windows (zero-dependency)."""
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True, encoding="utf-8")
        proc.communicate(input=text)
    except Exception as exc:
        agent_logger.log_warning("antigravity_bridge", f"Gagal copy to clipboard: {exc}")


class AntigravityBridge:
    """Mengendalikan Google Antigravity IDE (buka workspace, injeksi prompt, dan capture jendela)."""

    EXE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe"
    CMD_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "antigravity-ide.cmd"

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

    def send_prompt(self, prompt_text: str, auto_submit: bool = True) -> bool:
        """Fokus ke chat Antigravity Agent, tempelkan teks prompt (clipboard), dan submit."""
        if not prompt_text or not prompt_text.strip():
            return False

        self.launch_or_focus()
        time.sleep(0.3)

        try:
            # 1. Salin teks prompt ke clipboard
            _win32_copy_to_clipboard(prompt_text)

            # 2. Buka / fokus ke panel input chat Antigravity Agent (Ctrl+L)
            _win32_send_hotkey("ctrl", "l")
            time.sleep(0.25)

            # 3. Tempelkan teks prompt (Ctrl+V)
            _win32_send_hotkey("ctrl", "v")
            time.sleep(0.2)

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

