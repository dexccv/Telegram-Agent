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

