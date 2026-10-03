"""`pdf-themes typst`: compile a Typst document in light and dark modes and
merge the two builds, in one command."""

import json
import pathlib
import shutil
import stat
import sys

import numpy as np
import pikepdf
import pytest

from pdfthemes import apply, paint_paper, themes
from pdfthemes.cli import main

typst = pytest.importorskip("typst")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample" / "sample.typ"
FONTS = ROOT / "examples" / "fonts"
STANDARD = ["Light", "Dark", "Light, more contrast", "Dark, more contrast", "Cream", "Peach", "Yellow", "Turquoise"]


def build(mode, path):
    path.write_bytes(typst.compile(str(SAMPLE), root=str(SAMPLE.parent), font_paths=[str(FONTS)],
                                   ignore_system_fonts=True, sys_inputs={"mode": mode}))
    return path


def pixels(path):
    import pypdfium2 as pdfium
    return np.asarray(pdfium.PdfDocument(str(path))[0].render(scale=1).to_pil().convert("RGB"))


def test_typst_command_merges_the_light_and_dark_builds(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)  # no typst program: the Python package compiles
    out = tmp_path / "themed.pdf"
    code = main(["typst", str(SAMPLE), "-o", str(out), "--font-path", str(FONTS), "--ignore-system-fonts",
                 "--dark-paper", "1C1C1E"])
    assert code == 0
    with pikepdf.open(out) as pdf:
        assert themes(pdf) == STANDARD
        paint_paper(pdf, apply(pdf, "Dark"))
        pdf.save(tmp_path / "as-dark.pdf")
    with pikepdf.open(build("dark", tmp_path / "dark.pdf")) as pdf:
        paint_paper(pdf, (0x1C / 255, 0x1C / 255, 0x1E / 255))
        pdf.save(tmp_path / "dark-on-paper.pdf")
    assert np.array_equal(pixels(tmp_path / "as-dark.pdf"), pixels(tmp_path / "dark-on-paper.pdf"))


def test_typst_command_runs_the_typst_program_once_per_mode(tmp_path):
    builds = {mode: build(mode, tmp_path / f"{mode}.pdf") for mode in ("light", "dark")}
    log = tmp_path / "calls.jsonl"
    fake = tmp_path / "typst"
    # A stand-in for the typst program: it logs its arguments and writes the
    # build for the mode it was given to the output path, the third argument.
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, shutil, sys\n"
        "args = sys.argv[1:]\n"
        f"open({str(log)!r}, 'a').write(json.dumps(args) + '\\n')\n"
        "mode = [args[k + 1].split('=', 1)[1] for k, a in enumerate(args)\n"
        "        if a == '--input' and args[k + 1].startswith('mode=')][0]\n"
        f"shutil.copy({{'light': {str(builds['light'])!r}, 'dark': {str(builds['dark'])!r}}}[mode], args[2])\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "themed.pdf"
    code = main(["typst", str(SAMPLE), "-o", str(out), "--typst", str(fake), "--font-path", str(FONTS),
                 "--ignore-system-fonts", "--input", "paper=a5", "--pdf-standard", "a-2b"])
    assert code == 0
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == 2
    for call, mode in zip(calls, ("light", "dark")):
        assert call[:2] == ["compile", str(SAMPLE)]
        pairs = list(zip(call, call[1:]))
        assert ("--input", f"mode={mode}") in pairs
        assert ("--input", "paper=a5") in pairs
        assert ("--font-path", str(FONTS)) in pairs
        assert ("--root", str(SAMPLE.parent)) in pairs
        assert ("--pdf-standard", "a-2b") in pairs
        assert "--ignore-system-fonts" in call
    with pikepdf.open(out) as pdf:
        assert themes(pdf) == STANDARD


def test_a_themed_pdfa_file_keeps_its_xmp_metadata_byte_for_byte(tmp_path):
    paths = {}
    for mode in ("light", "dark"):
        paths[mode] = tmp_path / f"{mode}.pdf"
        paths[mode].write_bytes(typst.compile(str(SAMPLE), root=str(SAMPLE.parent), font_paths=[str(FONTS)],
                                              ignore_system_fonts=True, sys_inputs={"mode": mode},
                                              pdf_standards=["a-2b"]))
    out = tmp_path / "themed.pdf"
    assert main(["merge", str(paths["light"]), str(paths["dark"]), "-o", str(out), "--only-dark"]) == 0
    with pikepdf.open(paths["light"]) as build, pikepdf.open(out) as themed:
        assert themed.Root.Metadata.read_bytes() == build.Root.Metadata.read_bytes()
        assert "/Filter" not in themed.Root.Metadata  # PDF/A wants the metadata stream uncompressed


def test_typst_command_reports_a_typst_error_without_a_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    broken = tmp_path / "broken.typ"
    broken.write_text("#let x = \n")
    code = main(["typst", str(broken), "-o", str(tmp_path / "out.pdf")])
    assert code == 1
    err = capsys.readouterr().err
    assert "Typst couldn't compile" in err and "Traceback" not in err
    assert not (tmp_path / "out.pdf").exists()
