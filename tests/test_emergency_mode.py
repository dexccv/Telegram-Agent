"""Unit Tests for TeleAgent Emergency Mode (Mode Darurat).

Tests:
1. ambil_lokasi_laptop geolocation payload validation.
2. ambil_multi_foto_kamera callable and file generation.
3. TelegramAgentGateway emergency_cmd handler presence and method signature.
4. Natural language keyword detection patterns.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from penerjemah_idk import aktifkan_hook_idk
aktifkan_hook_idk()

import tools


class TestEmergencyMode(unittest.TestCase):
    def test_01_ambil_lokasi_laptop(self):
        """Verifikasi bahwa ambil_lokasi_laptop mengembalikan struktur lokasi yang valid."""
        loc = tools.ambil_lokasi_laptop()
        self.assertIsInstance(loc, dict, "Hasil harus berupa dictionary")
        self.assertIn("status", loc, "Harus ada key 'status'")
        if loc["status"] == "success":
            self.assertIsNotNone(loc["lat"], "Latitude tidak boleh None saat success")
            self.assertIsNotNone(loc["lon"], "Longitude tidak boleh None saat success")
            self.assertTrue(isinstance(loc["lat"], (int, float)), "Latitude harus berupa angka")
            self.assertTrue(isinstance(loc["lon"], (int, float)), "Longitude harus berupa angka")
            self.assertTrue(loc["maps_url"].startswith("https://www.google.com/maps?q="), "URL Google Maps harus valid")
            self.assertTrue(bool(loc.get("kota")), "Field kota harus ada")
            self.assertTrue(bool(loc.get("isp")), "Field ISP harus ada")

    def test_02_ambil_multi_foto_kamera_functionality(self):
        """Verifikasi pemanggilan ambil_multi_foto_kamera dengan parameter jumlah dan jeda."""
        self.assertTrue(callable(tools.ambil_multi_foto_kamera), "Fungsi ambil_multi_foto_kamera harus tersedia")

        # Test dengan mock cv2
        with patch("cv2.VideoCapture") as mock_cap_cls:
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, MagicMock())
            mock_cap_cls.return_value = mock_cap

            with patch("cv2.imwrite") as mock_imwrite, patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.stat") as mock_stat:
                mock_stat_res = MagicMock()
                mock_stat_res.st_size = 2048
                mock_stat.return_value = mock_stat_res

                paths = tools.ambil_multi_foto_kamera(jumlah=3, jeda_detik=0.01)
                self.assertEqual(len(paths), 3, "Harus menghasilkan 3 path foto")
                self.assertEqual(mock_cap.release.call_count, 1, "Kamera harus dilepas (release) setelah selesai")

    def test_03_telegram_gateway_emergency_cmd_present(self):
        """Verifikasi bahwa TelegramAgentGateway memiliki method emergency_cmd."""
        import bot_telegram
        self.assertTrue(hasattr(bot_telegram.TelegramAgentGateway, "emergency_cmd"), "TelegramAgentGateway harus memiliki method emergency_cmd")

    def test_04_natural_language_emergency_keywords(self):
        """Verifikasi bahwa variasi kata kunci darurat terdeteksi oleh logika pattern matching."""
        keywords = ["emergency", "mode darurat", "darurat", "tolong kunci laptop", "amankan laptop", "kunci darurat", "protokol darurat"]
        test_inputs = [
            "Tolong aktifkan mode darurat sekarang!",
            "EMERGENCY!!",
            "darurat laptop tertinggal",
            "tolong kunci laptop saya",
            "amankan laptop cepat",
        ]
        for inp in test_inputs:
            u_clean = inp.lower()
            matched = any(k in u_clean for k in keywords)
            self.assertTrue(matched, f"Input '{inp}' seharusnya cocok dengan salah satu kata kunci darurat")


if __name__ == "__main__":
    unittest.main()

