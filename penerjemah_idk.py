"""Penerjemah dan runtime loader untuk Bahasa Pemrograman Indonesiaku (Indonesiaku-Lang).

Menerjemahkan berkas sumber berekstensi .idk ke Python bytecode secara langsung
sehingga seluruh basis kode dapat ditulis dalam sintaks dan kata kunci Bahasa Indonesia.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import re
import sys
from pathlib import Path


KATA_KUNCI_PETA = {
    "tidak kosong": "is not None",
    "adalah kosong": "is None",
    "fungsi": "def",
    "kembalikan": "return",
    "jika_lain": "elif",
    "jika": "if",
    "selain": "else",
    "selagi": "while",
    "untuk": "for",
    "dalam": "in",
    "kelas": "class",
    "diri": "self",
    "init": "__init__",
    "benar": "True",
    "salah": "False",
    "kosong": "None",
    "dan": "and",
    "atau": "or",
    "tidak": "not",
    "coba": "try",
    "kecuali": "except",
    "akhirnya": "finally",
    "naikkan": "raise",
    "pastikan": "assert",
    "lewati": "pass",
    "lanjut": "continue",
    "berhenti": "break",
    "buang": "del",
    "cetak": "print",
    "impor": "import",
    "dari": "from",
    "sebagai": "as",
    "dengan": "with",
}

BLOK_HEADER_REGEX = re.compile(
    r"^\s*(fungsi|jika_lain|jika|selain|selagi|untuk|kelas|coba|kecuali|akhirnya|dengan)\b"
)


def _terjemahkan_ekspresi_kata_kunci(teks: str) -> str:
    """Mengganti kata kunci Indonesiaku dalam fragmen kode."""
    t = re.sub(
        r"fungsi\s*\((.*?)\)\s*\{\s*kembalikan\s*(.*?)\s*\}",
        lambda m: f"lambda {m.group(1).strip()}: {m.group(2).strip()}" if m.group(1).strip() else f"lambda: {m.group(2).strip()}",
        teks,
    )
    for k_idk, k_py in KATA_KUNCI_PETA.items():
        t = re.sub(r"\b" + k_idk + r"\b", k_py, t)
    return t


def _terjemahkan_fstring(fstr: str) -> str:
    """Menerjemahkan variabel/ekspresi di dalam kurung kurawal f-string (misal: {diri.nama})."""
    m = re.match(r"^(f[r|b]?|r?f)('\"\"|\"\"\"|'''|\"|')(.*)", fstr, re.DOTALL)
    if not m:
        return fstr

    def _repl_expr(match):
        expr = match.group(1)
        return "{" + _terjemahkan_ekspresi_kata_kunci(expr) + "}"

    isi = re.sub(r"\{([^}]+)\}", _repl_expr, fstr)
    return isi


def _ganti_kata_kunci(baris: str) -> str:
    """Mengganti kata kunci Indonesiaku dengan Python secara aman tanpa merusak string."""
    pola_string = r'(?:f?r?b?"""[\s\S]*?"""|f?r?b?\'\'\'[\s\S]*?\'\'\'|f?r?b?"(?:\\.|[^"\\])*"|f?r?b?\'(?:\\.|[^\'\\])*\')'
    bagian = re.split(f"({pola_string})", baris)

    hasil = []
    for fragmen in bagian:
        if not fragmen:
            continue
        if fragmen.startswith(("f\"", "f'", "f\"\"\"", "f'''")):
            hasil.append(_terjemahkan_fstring(fragmen))
        elif fragmen.startswith(('"', "'", 'r"', "r'", 'b"', "b'", '"""', "'''")):
            hasil.append(fragmen)
        else:
            hasil.append(_terjemahkan_ekspresi_kata_kunci(fragmen))

    return "".join(hasil)


def terjemahkan_idk_ke_python(kode_idk: str) -> str:
    """Menerjemahkan kode sumber Indonesiaku-Lang (.idk) menjadi kode Python yang valid."""
    baris_mentah = kode_idk.splitlines()
    baris_hasil: list[str] = []
    level_indentasi = 0
    in_triple_quote = False
    quote_char = ""
    class_indent_stack: list[int] = []
    data_brace_depth = 0

    pola_string_strip = r'(?:f?r?b?"""[\s\S]*?"""|f?r?b?\'\'\'[\s\S]*?\'\'\'|f?r?b?"(?:\\.|[^"\\])*"|f?r?b?\'(?:\\.|[^\'\\])*\')'

    for nomor_baris, baris in enumerate(baris_mentah, 1):
        teks = baris.strip()

        # Baris kosong
        if not teks:
            baris_hasil.append("")
            continue

        # Penanganan string multi-baris (triple quote)
        if in_triple_quote:
            baris_hasil.append(baris)
            if quote_char in teks:
                in_triple_quote = False
            continue

        if '"""' in teks or "'''" in teks:
            q = '"""' if '"""' in teks else "'''"
            count = teks.count(q)
            if count % 2 != 0:
                in_triple_quote = True
                quote_char = q

        # Tangani komentar murni
        if teks.startswith("#"):
            baris_hasil.append(("    " * level_indentasi) + teks)
            continue

        # Kode tanpa string untuk analisis kurung kurawal
        kode_bersih = re.sub(pola_string_strip, '""', teks)

        # Penutupan blok '}' di awal baris (misal "} selain {" atau "} kecuali ... {")
        while kode_bersih.startswith("}") and data_brace_depth == 0 and not kode_bersih.endswith("}"):
            level_indentasi = max(0, level_indentasi - 1)
            if class_indent_stack and class_indent_stack[-1] == level_indentasi:
                class_indent_stack.pop()
            teks = teks[1:].strip()
            kode_bersih = kode_bersih[1:].strip()

        # Jika baris adalah penutup kurung murni "}"
        if teks == "}":
            if data_brace_depth > 0:
                data_brace_depth -= 1
                indent_str = "    " * level_indentasi
                baris_hasil.append(indent_str + "}")
                continue
            else:
                level_indentasi = max(0, level_indentasi - 1)
                if class_indent_stack and class_indent_stack[-1] == level_indentasi:
                    class_indent_stack.pop()
                continue

        # Penanganan blok satu baris: "fungsi foo() { kembalikan x }"
        m_oneline = re.match(r"^(.*?)\s*\{\s*(.*?)\s*\}$", teks)
        if m_oneline and any(m_oneline.group(1).strip().startswith(kw) for kw in ["fungsi ", "jika ", "jika_lain ", "selain", "kelas ", "coba", "kecuali"]):
            h_raw = m_oneline.group(1).strip()
            b_raw = m_oneline.group(2).strip()
            if class_indent_stack and level_indentasi == class_indent_stack[-1] + 1 and h_raw.startswith("fungsi "):
                m_fn = re.match(r"^fungsi\s+([a-zA-Z0-9_]+)\s*\((.*?)\)", h_raw)
                if m_fn:
                    fn_name, fn_args = m_fn.group(1), m_fn.group(2).strip()
                    if not fn_args.startswith(("diri", "self", "cls")):
                        new_args = "diri, " + fn_args if fn_args else "diri"
                        h_raw = f"fungsi {fn_name}({new_args})"
            h_tr = _ganti_kata_kunci(h_raw)
            b_tr = _ganti_kata_kunci(b_raw)
            indent_str = "    " * level_indentasi
            baris_hasil.append(f"{indent_str}{h_tr}: {b_tr}")
            continue

        # Cek apakah baris ini adalah header blok kontrol yang berakhiran '{'
        apakah_blok = False
        if teks.endswith("{"):
            if BLOK_HEADER_REGEX.match(teks):
                teks = teks[:-1].rstrip() + ":"
                kode_bersih = kode_bersih[:-1].rstrip() + ":"
                apakah_blok = True

        # Hitung perubahan data_brace_depth dari kode_bersih
        # (Semua { dan } di luar string dan bukan blok header adalah data brace)
        count_open = kode_bersih.count("{")
        count_close = kode_bersih.count("}")
        data_brace_depth += (count_open - count_close)
        if data_brace_depth < 0:
            data_brace_depth = 0

        # Deteksi awal kelas
        is_class_start = teks.startswith("kelas ")

        # Penanganan sintaks inheritance: kelas Nama < Induk:
        if is_class_start and "<" in teks:
            teks = re.sub(r"kelas\s+([a-zA-Z0-9_]+)\s*<\s*([a-zA-Z0-9_\.]+)", r"kelas \1(\2)", teks)

        # Penanganan method di dalam kelas: otomatis beri diri (self) jika belum ada
        if class_indent_stack and level_indentasi == class_indent_stack[-1] + 1 and teks.startswith("fungsi "):
            m = re.match(r"^fungsi\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*(->\s*[^:]+)?\s*:", teks)
            if m:
                fn_name = m.group(1)
                args_str = m.group(2).strip()
                ret_type = m.group(3) or ""
                if not args_str.startswith(("diri", "self", "cls")):
                    new_args = "diri, " + args_str if args_str else "diri"
                    teks = f"fungsi {fn_name}({new_args}){ret_type}:"

        # Penanganan kecuali tanpa tipe galat
        if teks == "kecuali:":
            teks = "kecuali Exception:"
        elif teks.startswith("kecuali ") and "sebagai " not in teks and ":" in teks:
            target_err = teks[len("kecuali "):-1].strip()
            if "." in target_err or target_err.endswith(("Error", "Exception")) or (target_err and target_err[0].isupper()):
                teks = f"kecuali {target_err}:"
            elif target_err and "(" not in target_err:
                teks = f"kecuali Exception as {target_err}:"

        # Pemetaan kata kunci di luar string literal
        teks_diterjemahkan = _ganti_kata_kunci(teks)

        indent_str = "    " * level_indentasi
        baris_hasil.append(indent_str + teks_diterjemahkan)

        if is_class_start and apakah_blok:
            class_indent_stack.append(level_indentasi)

        if apakah_blok:
            level_indentasi += 1

    return "\n".join(baris_hasil)


class IdkLoader(importlib.abc.Loader):
    """Loader yang mengompilasi berkas .idk menjadi modul Python di memori."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def create_module(self, spec: importlib.machinery.ModuleSpec):
        return None

    def exec_module(self, module):
        with open(self.filepath, "r", encoding="utf-8") as f:
            kode_idk = f.read()

        kode_python = terjemahkan_idk_ke_python(kode_idk)
        module.__file__ = self.filepath
        module.__loader__ = self

        compiled = compile(kode_python, self.filepath, "exec")
        exec(compiled, module.__dict__)


class IdkFinder(importlib.abc.MetaPathFinder):
    """Finder untuk mendeteksi import modul berekstensi .idk secara otomatis."""

    def find_spec(self, fullname: str, path=None, target=None):
        mod_name = fullname.split(".")[-1]
        search_dirs = [os.getcwd()]
        if path:
            search_dirs.extend(path)

        for d in search_dirs:
            target_file = os.path.join(d, f"{mod_name}.idk")
            if os.path.exists(target_file):
                return importlib.machinery.ModuleSpec(fullname, IdkLoader(target_file))

        return None


def aktifkan_hook_idk() -> None:
    """Mengaktifkan hook import agar interpreter dapat langsung memuat berkas .idk."""
    for finder in sys.meta_path:
        if isinstance(finder, IdkFinder):
            return
    sys.meta_path.insert(0, IdkFinder())


def jalankan_berkas_idk(filepath: str) -> None:
    """Mengeksekusi langsung berkas .idk utama."""
    aktifkan_hook_idk()
    path_obj = Path(filepath).resolve()
    if not path_obj.exists():
        print(f"[Galat] Berkas '{filepath}' tidak ditemukan.")
        sys.exit(1)

    file_dir = str(path_obj.parent)
    if file_dir not in sys.path:
        sys.path.insert(0, file_dir)

    with open(path_obj, "r", encoding="utf-8") as f:
        kode_idk = f.read()

    kode_python = terjemahkan_idk_ke_python(kode_idk)
    compiled = compile(kode_python, str(path_obj), "exec")

    global_scope = {
        "__name__": "__main__",
        "__file__": str(path_obj),
        "__builtins__": __builtins__,
    }
    exec(compiled, global_scope)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        jalankan_berkas_idk(sys.argv[1])
    else:
        print("Penggunaan: python penerjemah_idk.py <berkas.idk>")
