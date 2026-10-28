import time
import pytest
from pathlib import Path
from config import ConfigManager


def test_config_throttled_reload(tmp_path, monkeypatch):
    cfg = ConfigManager()
    cfg.app_dir = tmp_path
    cfg.env_path = tmp_path / ".env"
    cfg.env_path.write_text("TEST_KEY=INITIAL_VAL\n", encoding="utf-8")
    cfg._reload_interval = 1.0  # 1 detik

    # Panggilan awal force=True
    cfg.reload(force=True)
    t0 = cfg._last_reload_time

    # Ubah isi disk secara langsung
    cfg.env_path.write_text("TEST_KEY=UPDATED_VAL\n", encoding="utf-8")

    # Panggilan reload biasa sebelum interval 1 detik tidak boleh reload (throttled)
    cfg.reload(force=False)
    assert cfg._last_reload_time == t0

    # Panggilan force=True harus reload segera
    cfg.reload(force=True)
    assert cfg._last_reload_time > t0

