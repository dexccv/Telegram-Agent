"""
Launcher dengan Self-Healing untuk Gemini Terminal Agent.

Jalankan file ini sebagai pengganti app.py atau bot_telegram.py
agar program dapat memperbaiki dirinya sendiri saat terjadi crash.

Penggunaan:
    python run_with_healing.py [tui|bot]

Contoh:
    python run_with_healing.py tui   # Jalankan TUI dengan self-healing
    python run_with_healing.py bot   # Jalankan Telegram Bot dengan self-healing
"""
import sys
from pathlib import Path

# Pastikan encoding UTF-8 di Windows console
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "tui"

    if mode == "bot":
        entry_file = str(Path(__file__).parent / "bot_telegram.py")
        program_name = "Telegram Bot"
    else:
        entry_file = str(Path(__file__).parent / "app.py")
        program_name = "TUI Terminal"

    from self_healer import run_with_healing
    run_with_healing(
        entry_point_file=entry_file,
        program_name=program_name,
        max_attempts=3,
    )


if __name__ == "__main__":
    main()
