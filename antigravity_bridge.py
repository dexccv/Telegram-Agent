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


class AntigravityBridge:
    """Mengendalikan Google Antigravity IDE (buka workspace, injeksi prompt, dan capture jendela)."""

    EXE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe"
    CMD_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "bin" / "antigravity-ide.cmd"

    def __init__(self) -> None:
        self._last_window: Any = None

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
        try:
            import uiautomation as auto

            root = auto.GetRootControl()
            # Cari jendela dengan judul Antigravity atau repositori aktif
            for win in root.GetChildren():
                name = win.Name or ""
                if "Antigravity" in name or "gemini-terminal-agent" in name:
                    self._last_window = win
                    return win
        except Exception as exc:
            agent_logger.log_warning("antigravity_bridge", f"Gagal mencari window via uiautomation: {exc}")
        return None

    def _focus_window(self) -> bool:
        """Membawa jendela Antigravity ke Foreground via UIAutomation dan Win32 API."""
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
                agent_logger.log_warning("antigravity_bridge", f"Gagal fokus window: {exc}")

        # Fallback via Win32 ctypes FindWindow
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            return hwnd != 0
        except Exception:
            return False

    def launch_or_focus(self, workspace_path: Optional[str] = None) -> bool:
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

        focused = self._focus_window()
        agent_logger.log_info("antigravity_bridge", f"launch_or_focus(workspace='{ws}') -> {focused}")
        return focused

    def send_prompt(self, prompt_text: str, auto_submit: bool = True) -> bool:
        """Fokus ke chat Antigravity Agent, tempelkan teks prompt (clipboard), dan submit."""
        if not prompt_text or not prompt_text.strip():
            return False

        self.launch_or_focus()
        time.sleep(0.4)

        try:
            import uiautomation as auto

            # Salin teks prompt ke Windows clipboard via subproses clip
            proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True, encoding="utf-8")
            proc.communicate(input=prompt_text)

            # Shortcut fokus kotak prompt Antigravity Agent (Ctrl+L)
            auto.SendKeys("{Ctrl}l")
            time.sleep(0.3)

            # Tempelkan teks prompt (Ctrl+V)
            auto.SendKeys("{Ctrl}v")
            time.sleep(0.2)

            if auto_submit:
                auto.SendKeys("{Enter}")

            agent_logger.log_info(
                "antigravity_bridge",
                f"Prompt dikirim ke Antigravity ({len(prompt_text)} karakter, auto_submit={auto_submit}).",
            )
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal mengirim prompt: {exc}")
            return False

    def trigger_proceed(self) -> bool:
        """Mencari tombol 'Proceed' / 'Allow' pada Antigravity IDE untuk menyetujui plan atau eksekusi tool."""
        self.launch_or_focus()
        time.sleep(0.3)

        try:
            import uiautomation as auto

            win = self._find_window()
            if win:
                # Cari tombol bertuliskan Proceed / Continue / Allow
                for name_target in ["Proceed", "Proceed (Enter)", "Allow", "Run", "Continue"]:
                    btn = win.ButtonControl(Name=name_target)
                    if btn.Exists(maxSearchSeconds=1):
                        btn.Click()
                        agent_logger.log_info("antigravity_bridge", f"Tombol '{name_target}' berhasil ditekan.")
                        return True

            # Fallback kirim Enter
            auto.SendKeys("{Enter}")
            agent_logger.log_info("antigravity_bridge", "Proceed dipicu via Enter fallback.")
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal trigger proceed: {exc}")
            return False

    def open_integrated_terminal_and_run(self, command: str) -> bool:
        """Membuka terminal terintegrasi Antigravity dan mengeksekusi perintah."""
        self.launch_or_focus()
        time.sleep(0.4)

        try:
            import uiautomation as auto

            # Buka/fokus terminal terintegrasi (Ctrl+`)
            auto.SendKeys("{Ctrl}`")
            time.sleep(0.4)

            # Salin perintah ke clipboard dan tempel
            proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, text=True, encoding="utf-8")
            proc.communicate(input=command)

            auto.SendKeys("{Ctrl}v")
            time.sleep(0.1)
            auto.SendKeys("{Enter}")
            agent_logger.log_info("antigravity_bridge", f"Perintah terminal dikirim: {command}")
            return True
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal kirim perintah terminal: {exc}")
            return False

    def capture_window_screenshot(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """Mengambil tangkapan layar jendela Antigravity (atau layar penuh jika jendela tidak ditemukan)."""
        target = output_path or (Path.cwd() / "antigravity_screenshot.png")
        try:
            win = self._find_window()
            if win and not win.IsIconic():
                rect = win.BoundingRectangle
                if rect and rect.width() > 100 and rect.height() > 100:
                    bbox = (rect.left, rect.top, rect.right, rect.bottom)
                    img = ImageGrab.grab(bbox=bbox)
                    img.save(str(target), format="PNG")
                    return target

            # Fallback ke fullscreen
            img = ImageGrab.grab()
            img.save(str(target), format="PNG")
            return target
        except Exception as exc:
            agent_logger.log_error("antigravity_bridge", f"Gagal capture screenshot: {exc}")
            return None


antigravity_bridge = AntigravityBridge()

