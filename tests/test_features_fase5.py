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


def test_antigravity_model_management():
    bridge = AntigravityBridge()
    models = bridge.get_available_models()
    assert isinstance(models, list)
    assert len(models) >= 1
    # Minimal mengandung model gemini
    assert any("gemini" in m["id"].lower() for m in models)

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


def test_antigravity_trigger_accept_all():
    bridge = AntigravityBridge()
    assert hasattr(bridge, "trigger_accept_all")
    # trigger_accept_all harus dapat dipanggil tanpa melempar exception fatal
    # Bila jendela tidak fokus/running, fallback Alt+Enter tetap aman
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

