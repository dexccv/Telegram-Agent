import pytest
from pathlib import Path
from memory import MemoryManager
from agent import GeminiAgent


def test_memory_manager_lifecycle(tmp_path):
    # Buat instance memory manager dengan path terisolasi
    mem_mgr = MemoryManager()
    mem_mgr.memory_file = tmp_path / "test_memory.json"
    mem_mgr.memories = {}

    # 1. Simpan memori
    mem_mgr.set("kunci_uji", "Nilai preferensi pengguna untuk pengujian")
    assert mem_mgr.memory_file.exists()

    # 2. Ambil / get
    val = mem_mgr.get("kunci_uji")
    assert val == "Nilai preferensi pengguna untuk pengujian"

    # 3. Get all
    semua = mem_mgr.get_all()
    assert "kunci_uji" in semua

    # 4. Hapus
    mem_mgr.delete("kunci_uji")
    assert "kunci_uji" not in mem_mgr.get_all()


def test_agent_history_pruning():
    agent = GeminiAgent(api_key="dummy_key", model_name="gemini-2.5-flash")
    session = agent.session

    # Simulasikan riwayat percakapan lebih dari 30 turn
    session.history = []
    for i in range(35):
        session.history.append({"role": "user", "text": f"Pesan user ke-{i}"})
        session.history.append({"role": "model", "text": f"Jawaban model ke-{i}"})

    assert len(session.history) == 70

    # Jalankan pruning
    agent._prune_history_if_needed(max_turns=25, max_chars=100000)

    # Riwayat harus terpotong menjadi 2 pesan summary + 16 pesan (8 turn terakhir)
    assert len(session.history) < 70
    assert any("CATATAN SISTEM:" in m.get("text", "") for m in session.history)
