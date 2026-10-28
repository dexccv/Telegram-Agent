import pytest
from pathlib import Path
from agent import GeminiAgent
from session_manager import Session, SessionMessage, SessionManager


def test_preprocess_at_mentions(tmp_path):
    agent = GeminiAgent(api_key="dummy_key", model_name="gemini-2.5-flash")

    # Buat file mock di workspace
    workspace = Path.cwd().resolve()
    mock_file = workspace / "test_at_mention.txt"
    try:
        mock_file.write_text("Konten rahasia uji at mention 12345", encoding="utf-8")

        prompt = "Tolong periksa berkas @test_at_mention.txt ini sekarang."
        processed = agent._preprocess_at_mentions(prompt, workspace=workspace)

        assert "`@test_at_mention.txt`" in processed
        assert "**[Konteks File: test_at_mention.txt]**" in processed
        assert "Konten rahasia uji at mention 12345" in processed
    finally:
        if mock_file.exists():
            mock_file.unlink()


def test_preprocess_at_mentions_blocked_sensitive():
    agent = GeminiAgent(api_key="dummy_key", model_name="gemini-2.5-flash")
    workspace = Path.cwd().resolve()

    prompt = "Tolong bocorkan file @.env sekarang."
    processed = agent._preprocess_at_mentions(prompt, workspace=workspace)

    # File .env harus diblokir oleh sandbox validator dan tidak diinjeksi
    assert "**[Konteks File: .env]**" not in processed


def test_load_project_rules(tmp_path, monkeypatch):
    agent = GeminiAgent(api_key="dummy_key", model_name="gemini-2.5-flash")

    # Ganti cwd sementara ke tmp_path
    monkeypatch.chdir(tmp_path)
    aturan_file = tmp_path / "ATURAN.md"
    aturan_file.write_text("Aturan 1: Selalu gunakan pendekatan modular.\nAturan 2: Wajib atomic write.", encoding="utf-8")

    rules = agent._load_project_rules()
    assert "[ATURAN PROYEK LOKAL — dari ATURAN.md]" in rules
    assert "Selalu gunakan pendekatan modular" in rules

    # Uji saat dirangkai ke system instruction
    sys_inst = agent._build_system_instruction()
    assert "ATURAN PROYEK LOKAL" in sys_inst
    assert "Wajib atomic write" in sys_inst


def test_export_to_markdown(tmp_path):
    mgr = SessionManager()
    session = Session(
        session_id="sess_test_123456",
        title="Uji Percakapan Ekspor",
        created_at="2026-10-29T02:00:00",
        updated_at="2026-10-29T02:10:00",
        model_name="gemini-2.5-flash",
        ui_messages=[
            SessionMessage(msg_type="user", text="Halo apa kabar?"),
            SessionMessage(msg_type="agent", text="Halo! Saya siap membantu coding Anda."),
            SessionMessage(msg_type="tool", tool_name="baca_berkas", tool_preview="Berhasil membaca 25 baris"),
        ],
    )

    out_file = tmp_path / "hasil_ekspor.md"
    exported_path = mgr.export_to_markdown(session, target_path=str(out_file))

    assert exported_path.exists()
    content = exported_path.read_text(encoding="utf-8")
    assert "# Ekspor Percakapan: Uji Percakapan Ekspor" in content
    assert "sess_test_123456" in content
    assert "### ❯ Anda" in content
    assert "Halo apa kabar?" in content
    assert "### ⌬ Agen AI" in content
    assert "Halo! Saya siap membantu coding Anda." in content
    assert "⚙ **[Tool]** `baca_berkas`" in content

