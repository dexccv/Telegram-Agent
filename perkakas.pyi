"""Type stub untuk modul perkakas (perkakas.idk)."""
from typing import Any, Callable

ALAT_TERSEDIA: list[Any]
DAFTAR_PANGGILAN_ALAT: list[Any]
AVAILABLE_TOOLS: list[Any]
TOOL_CALLABLES: list[Any]

def apakah_perintah_aman(perintah: str) -> tuple[bool, str]: ...
def is_command_safe(perintah: str) -> tuple[bool, str]: ...
def validasi_jalur_sandbox(path: str) -> tuple[bool, str]: ...
