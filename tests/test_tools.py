import os
import pytest
from pathlib import Path
from tools import (
    validate_sandbox_path,
    create_folder,
    write_file,
    read_file,
    edit_file,
    list_files,
    run_command,
)


def test_sandbox_path_validation_safe(tmp_path):
    workspace = Path.cwd().resolve()
    target = workspace / "dummy_test_file.txt"
    is_safe, err = validate_sandbox_path(str(target))
    assert is_safe is True
    assert err == ""


def test_sandbox_path_validation_blocked_sensitive():
    workspace = Path.cwd().resolve()
    is_safe_env, err_env = validate_sandbox_path(str(workspace / ".env"))
    assert is_safe_env is False
    assert "diblokir" in err_env.lower()

    is_safe_ssh, err_ssh = validate_sandbox_path(str(workspace / ".ssh" / "id_rsa"))
    assert is_safe_ssh is False
    assert "diblokir" in err_ssh.lower()


def test_sandbox_path_validation_blocked_escape():
    is_safe_esc, err_esc = validate_sandbox_path("C:\\Windows\\System32\\calc.exe")
    assert is_safe_esc is False
    assert "diblokir" in err_esc.lower()


def test_tools_file_lifecycle():
    test_rel_path = "test_artifact_lifecycle.tmp"
    workspace = Path.cwd().resolve()
    test_abs = workspace / test_rel_path

    try:
        # 1. Tulis file
        res_write = write_file(test_rel_path, "Baris 1: Awal\nBaris 2: Target Edit\nBaris 3: Akhir")
        assert "sukses" in res_write.lower() or "berhasil" in res_write.lower()
        assert test_abs.exists()

        # 2. Baca file
        res_read = read_file(test_rel_path)
        assert "Baris 2: Target Edit" in res_read

        # 3. Edit file presisi
        res_edit = edit_file(test_rel_path, "Target Edit", "Berhasil Diubah")
        assert "sukses" in res_edit.lower() or "berhasil" in res_edit.lower()

        # 4. Verifikasi hasil edit
        res_read_after = read_file(test_rel_path)
        assert "Baris 2: Berhasil Diubah" in res_read_after
        assert "Target Edit" not in res_read_after

        # 5. List files
        files_json = list_files()
        assert test_rel_path in files_json
    finally:
        if test_abs.exists():
            test_abs.unlink()


def test_edit_file_target_not_found():
    test_rel_path = "test_artifact_not_found.tmp"
    workspace = Path.cwd().resolve()
    test_abs = workspace / test_rel_path

    try:
        write_file(test_rel_path, "Halo dunia")
        res_edit = edit_file(test_rel_path, "Teks Yang Tidak Ada", "Ganti")
        assert "gagal" in res_edit.lower() or "tidak ditemukan" in res_edit.lower()
    finally:
        if test_abs.exists():
            test_abs.unlink()
