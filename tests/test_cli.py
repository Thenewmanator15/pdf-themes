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
                 "--dark-paper", "1C1C1E", "--derive"])
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
    if sys.platform == "win32":
        # Windows doesn't read the first line, so a batch file runs the script.
        script, fake = fake, tmp_path / "typst.cmd"
        fake.write_text(f'@"{sys.executable}" "{script}" %*\n')
    out = tmp_path / "themed.pdf"
    code = main(["typst", str(SAMPLE), "-o", str(out), "--typst", str(fake), "--font-path", str(FONTS),
                 "--ignore-system-fonts", "--input", "paper=a5", "--pdf-standard", "a-2b", "--derive"])
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


def test_text_the_console_cant_show_is_escaped(monkeypatch):
    # A Windows console or pipe is often cp1252, and a report quotes the
    # document's own text, which can be in any script.
    import io
    from pdfthemes import cli
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    monkeypatch.setattr(cli, "cmd_info", lambda args: print(chr(0x65E5)) or 0)
    assert main(["info", "any.pdf"]) == 0
    sys.stdout.flush()
    assert raw.getvalue().strip() == b"\\u65e5"


# A build per theme.

@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    d = tmp_path_factory.mktemp("pair")
    return build("light", d / "light.pdf"), build("dark", d / "dark.pdf")


def themes_of(path):
    with pikepdf.open(path) as pdf:
        return themes(pdf)


def test_merge_takes_a_build_per_theme(pair, tmp_path):
    light, dark = pair
    out = tmp_path / "themed.pdf"
    assert main(["merge", "--theme", f"Light={light}", "--theme", f"Dark={dark}", "--theme", f"Cream={dark}",
                 "-o", str(out)]) == 0
    assert themes_of(out) == ["Light", "Dark", "Cream"]


def test_a_custom_theme_carries_its_labels(pair, tmp_path):
    from pdfthemes import describe
    light, dark = pair
    out = tmp_path / "themed.pdf"
    assert main(["merge", "--theme", f"Light={light}", "--theme", f"Night={dark};scheme=Dark;paper=0B0C10",
                 "-o", str(out)]) == 0
    with pikepdf.open(out) as pdf:
        night = describe(pdf)["themes"][1]
    assert night["name"] == "Night" and night["color_scheme"] == "Dark"
    assert night["paper"] == pytest.approx([0x0B / 255, 0x0C / 255, 0x10 / 255], abs=1e-3)


def test_paper_sets_a_standard_themes_paper(pair, tmp_path):
    from pdfthemes import describe
    light, dark = pair
    out = tmp_path / "themed.pdf"
    assert main(["merge", "--theme", f"Light={light}", "--theme", f"Dark={dark}", "--paper", "Dark=1C1C1E",
                 "-o", str(out)]) == 0
    with pikepdf.open(out) as pdf:
        assert describe(pdf)["themes"][1]["paper"] == pytest.approx([0x1C / 255, 0x1C / 255, 0x1E / 255], abs=1e-3)


@pytest.mark.parametrize("args, message", [
    (["--theme", "Light=a.pdf", "--theme", "Light=b.pdf"], "two themes are called Light"),
    (["--theme", "Light=a.pdf", "--theme", "Night=b.pdf"],
     "Night isn't a standard theme, so it needs scheme=Light or scheme=Dark"),
    (["a.pdf", "b.pdf", "--theme", "Cream=c.pdf"], "give the builds either as two files or with --theme, not both"),
    (["--theme", "Light=a.pdf"], "merging needs at least two builds"),
    (["--theme", "Light=a.pdf", "--theme", "Dark=b.pdf", "--paper", "Cream=FFEEDD"], "--paper names Cream"),
    (["--theme", "Light=a.pdf", "--theme", "Dark=nowhere.pdf"], "no such file"),
])
def test_usage_errors_name_the_theme_and_write_nothing(args, message, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.pdf").write_bytes(b"")
    (tmp_path / "b.pdf").write_bytes(b"")
    with pytest.raises(SystemExit) as e:
        main(["merge", *args, "-o", str(tmp_path / "out.pdf")])
    assert e.value.code == 2 and message in capsys.readouterr().err
    assert not (tmp_path / "out.pdf").exists()


def test_merge_works_out_no_themes_unless_asked(pair, tmp_path):
    light, dark = pair
    out = tmp_path / "themed.pdf"
    assert main(["merge", str(light), str(dark), "-o", str(out)]) == 0
    assert themes_of(out) == ["Light", "Dark"]
    assert main(["merge", str(light), str(dark), "-o", str(out), "--derive"]) == 0
    assert themes_of(out) == STANDARD


def test_derive_needs_a_light_and_a_dark_build_and_nothing_else(pair, tmp_path, capsys):
    light, dark = pair
    with pytest.raises(SystemExit) as e:
        main(["merge", "--theme", f"Light={light}", "--theme", f"Dark={dark}", "--theme", f"Cream={dark}",
              "--derive", "-o", str(tmp_path / "out.pdf")])
    assert e.value.code == 2 and "--derive works from a Light and a Dark build only" in capsys.readouterr().err


def any_mode_typst(tmp_path, pair):
    """A stand-in for the typst program: logs its arguments and writes the
    light build for mode=light and the dark build for any other mode."""
    light, dark = pair
    log = tmp_path / "calls.jsonl"
    script = tmp_path / "typst"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, shutil, sys\n"
        "args = sys.argv[1:]\n"
        f"open({str(log)!r}, 'a').write(json.dumps(args) + '\\n')\n"
        "mode = [args[k + 1].split('=', 1)[1] for k, a in enumerate(args)\n"
        "        if a == '--input' and args[k + 1].startswith('mode=')][0]\n"
        f"shutil.copy({str(light)!r} if mode == 'light' else {str(dark)!r}, args[2])\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    program = script
    if sys.platform == "win32":
        program = tmp_path / "typst.cmd"
        program.write_text(f'@"{sys.executable}" "{script}" %*\n')
    return program, log


def test_typst_compiles_once_per_mode(pair, tmp_path):
    program, log = any_mode_typst(tmp_path, pair)
    out = tmp_path / "themed.pdf"
    assert main(["typst", str(SAMPLE), "-o", str(out), "--typst", str(program),
                 "--modes", "light,dark,cream,dark-contrast"]) == 0
    modes = [[a.split("=", 1)[1] for a in json.loads(line) if a.startswith("mode=")][0]
             for line in log.read_text().splitlines()]
    assert modes == ["light", "dark", "cream", "dark-contrast"]
    assert themes_of(out) == ["Light", "Dark", "Cream", "Dark, more contrast"]


def test_typst_refuses_a_mode_with_no_standard_theme(pair, tmp_path, capsys):
    program, _ = any_mode_typst(tmp_path, pair)
    with pytest.raises(SystemExit) as e:
        main(["typst", str(SAMPLE), "-o", str(tmp_path / "out.pdf"), "--typst", str(program), "--modes", "light,sepia"])
    assert e.value.code == 2 and "sepia" in capsys.readouterr().err
