import ast
import pytest
from penerjemah_idk import terjemahkan_idk_ke_python, _scan_triple_quote_state


def test_transpiler_basic_constructs():
    idk_code = """
fungsi hitung_total(a, b) {
    jika a > b {
        kembalikan a - b
    } jika_lain a == b {
        kembalikan 0
    } selain {
        kembalikan b - a
    }
}
"""
    py_code = terjemahkan_idk_ke_python(idk_code)
    parsed = ast.parse(py_code)
    assert parsed is not None
    assert "def hitung_total(a, b):" in py_code
    assert "if a > b:" in py_code
    assert "elif a == b:" in py_code
    assert "else:" in py_code
    assert "return" in py_code


def test_transpiler_triple_quote_bug02_protection():
    # Menguji kasus docstring multi-baris yang mengandung kutipan bersarang
    idk_code = '''
fungsi cetak_info() {
    """Fungsi ini melakukan pencetakan.
    Contoh dalam teks: 'kata' dan \'\'\'quote\'\'\'
    Semua harus aman dan tidak merusak parsing.
    """
    x = benar
    y = salah
    kembalikan x
}
'''
    py_code = terjemahkan_idk_ke_python(idk_code)
    parsed = ast.parse(py_code)
    assert parsed is not None
    assert "x = True" in py_code
    assert "y = False" in py_code
    assert "return x" in py_code


def test_scan_triple_quote_scanner():
    # Test state scanner mandiri
    in_t, q = _scan_triple_quote_state('"""docstring satu baris"""', False, "")
    assert in_t is False
    assert q == ""

    in_t, q = _scan_triple_quote_state('doc = """buka multi baris', False, "")
    assert in_t is True
    assert q == '"""'

    in_t, q = _scan_triple_quote_state('tutup multi baris"""', in_t, q)
    assert in_t is False
    assert q == ""

