import pytest
from pathlib import Path
from tools import run_sandboxed_command, run_command
from antigravity_bridge import AntigravityBridge, antigravity_bridge


def test_antigravity_bridge_instantiation():
    bridge = AntigravityBridge()
    # is_running harus mengembalikan boolean tanpa crash
    running = bridge.is_running()
    assert isinstance(running, bool)
    assert hasattr(bridge, "launch_or_focus")
    assert hasattr(bridge, "send_prompt")
    assert hasattr(bridge, "trigger_proceed")
    assert hasattr(bridge, "capture_window_screenshot")


def test_run_sandboxed_command_safe():
    res = run_sandboxed_command('python -c "print(\'HELLO_SANDBOX_OK\')"')
    assert res["success"] is True
    assert res["returncode"] == 0
    assert "HELLO_SANDBOX_OK" in res["stdout"]


def test_run_sandboxed_command_blocked():
    # Perintah berbahaya harus diblokir seketika
    res_format = run_sandboxed_command("format C:")
    assert res_format["success"] is False
    assert res_format["returncode"] == -1
    assert "SANDBOX BLOCKED" in res_format["stderr"]

    res_del = run_sandboxed_command("del /f /s /q c:\\")
    assert res_del["success"] is False
    assert "SANDBOX BLOCKED" in res_del["stderr"]

    res_rm = run_sandboxed_command("rm -rf /")
    assert res_rm["success"] is False
    assert "SANDBOX BLOCKED" in res_rm["stderr"]


def test_run_command_wrapper_integration():
    output = run_command('python -c "print(\'WRAPPER_TEST_OK\')"')
    assert "[KODE KELUAR: 0]" in output
    assert "WRAPPER_TEST_OK" in output


def test_run_sandboxed_command_timeout():
    # Menguji timeout cepat (1 detik)
    res = run_sandboxed_command('python -c "import time; time.sleep(3)"', timeout=1)
    assert res["success"] is False
    assert "SANDBOX TIMEOUT" in res["stderr"]


def test_antigravity_capture_window_screenshot(tmp_path):
    bridge = AntigravityBridge()
    target_img = tmp_path / "test_capture.png"
    result = bridge.capture_window_screenshot(output_path=target_img)
    # Harus mengembalikan file gambar valid yang tersimpan di disk
    assert result is not None
    assert result.exists()
    assert result.stat().st_size > 500


def test_antigravity_model_management(tmp_path, monkeypatch):
    bridge = AntigravityBridge()
    models = bridge.get_available_models()
    assert isinstance(models, list)
    assert len(models) >= 1
    # Minimal mengandung model gemini
    assert any("gemini" in m["id"].lower() for m in models)

    # Uji deteksi model dari dummy state pbtxt
    fake_state = tmp_path / "antigravity_state.pbtxt"
    fake_state.write_text("last_selected_agent_model:  MODEL_PLACEHOLDER_M319\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "ANTIGRAVITY_STATE_PATH", fake_state)
    detected = bridge.detect_ide_active_model()
    assert detected == "gemini-3.8-flash-medium"

    # Uji set_active_model dengan alias 'medium'
    ok, m_info = bridge.set_active_model("medium")
    assert ok is True
    assert "medium" in m_info["id"]

    active = bridge.get_active_model()
    assert "medium" in active["id"]

    # Uji set_active_model dengan ID spesifik
    ok2, m_info2 = bridge.set_active_model("gemini-3.8-flash-high")
    assert ok2 is True
    assert "high" in m_info2["id"]


def test_win32_clipboard_long_text():
    from antigravity_bridge import _win32_copy_to_clipboard
    # Uji prompt panjang 8000 karakter multiline
    long_text = "Prompt testing multiline:\n" + ("def example_function():\n    return 42\n" * 250)
    ok = _win32_copy_to_clipboard(long_text)
    assert ok is True


def test_antigravity_trigger_accept_all(monkeypatch):
    bridge = AntigravityBridge()
    assert hasattr(bridge, "trigger_accept_all")
    assert hasattr(bridge, "_find_and_click_accept_all_button")

    # Uji visual button clicker dengan simulated canvas
    from PIL import Image
    fake_canvas = Image.new("RGB", (1000, 800), (30, 30, 30))
    # Buat tombol biru di x=600..660, y=500..525
    for y in range(500, 525):
        for x in range(600, 660):
            fake_canvas.putpixel((x, y), (0, 150, 230))

    monkeypatch.setattr("PIL.ImageGrab.grab", lambda **kwargs: fake_canvas)
    clicked = []
    monkeypatch.setattr("antigravity_bridge._win32_mouse_click", lambda x, y: clicked.append((x, y)))

    res_vision = bridge._find_and_click_accept_all_button()
    assert res_vision is True
    assert len(clicked) == 1
    # Koordinat klik harus berada di dalam bounding box tombol (630, 512)
    assert 595 <= clicked[0][0] <= 665
    assert 495 <= clicked[0][1] <= 530

    res = bridge.trigger_accept_all()
    assert isinstance(res, bool)


def test_antigravity_transcript_watcher(tmp_path):
    bridge = AntigravityBridge()
    # 1. Pastikan method find_latest_transcript_file ada dan mengembalikan Path atau None
    latest_tfile = bridge.find_latest_transcript_file()
    assert latest_tfile is None or isinstance(latest_tfile, Path)

    # 2. Uji parsing transcript buatan
    fake_log_dir = tmp_path / ".system_generated" / "logs"
    fake_log_dir.mkdir(parents=True)
    fake_tfile = fake_log_dir / "transcript.jsonl"
    
    import json
    with open(fake_tfile, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "USER_INPUT", "status": "DONE", "content": "Tolong buat fitur X"}) + "\n")
        f.write(json.dumps({"type": "PLANNER_RESPONSE", "status": "DONE", "content": "Fitur X berhasil dibuat"}) + "\n")

    res = bridge.get_latest_completed_response(fake_tfile)
    assert res is not None
    assert res["type"] == "PLANNER_RESPONSE"
    assert "Fitur X" in res["content"]


def test_maximize_window_support(monkeypatch):
    bridge = AntigravityBridge()
    monkeypatch.setattr(bridge, "_find_window_hwnd", lambda: 99999)
    
    called_show = []
    class FakeUser32:
        def ShowWindow(self, hwnd, cmd):
            called_show.append((hwnd, cmd))
            return 1
        def IsIconic(self, hwnd):
            return 0
        def SetWindowPos(self, *args):
            return 1
        def keybd_event(self, *args):
            pass
        def BringWindowToTop(self, *args):
            pass
        def SetForegroundWindow(self, *args):
            pass
        def GetWindowRect(self, *args):
            return 0

    monkeypatch.setattr("ctypes.windll.user32", FakeUser32())
    res = bridge.maximize_window()
    assert res is True
    # SW_MAXIMIZE cmd adalah 3
    assert (99999, 3) in called_show


