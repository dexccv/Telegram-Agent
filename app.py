"""Pintu masuk aplikasi Gemini Terminal Agent berbasis Indonesiaku-Lang (.idk).

Memanggil runtime penerjemah dan menjalankan aplikasi.idk secara langsung.
Untuk berkas legacy murni Python, lihat berkas app_legacy.py.
"""

from penerjemah_idk import jalankan_berkas_idk

if __name__ == "__main__":
    jalankan_berkas_idk("aplikasi.idk")
