"""theme-lab (tests/theme-lab): Lilaq plots built once per theme, eight
themes in all, each with its colours set in the source. Merged into one file,
every theme has to draw like the build it came from."""

import io
import pathlib
import shutil
import subprocess

import numpy as np
import pikepdf
import pytest

from pdfthemes import apply, merge_builds, themes
from pdfthemes.core import SAVE
from pdfthemes.derive import add_themes
from pdfthemes.theme import standard

OUT = pathlib.Path(__file__).resolve().parent / "theme-lab" / "out"
# Each mode, the standard theme it is, and its paper colour in theme-lab.typ.
MODES = {"light": ("Light", "FFFFFF"), "dark": ("Dark", "18191C"),
         "light-contrast": ("Light, more contrast", "FFFFFF"), "dark-contrast": ("Dark, more contrast", "000000"),
         "cream": ("Cream", "FDF6E3"), "peach": ("Peach", "FDE7DC"), "yellow": ("Yellow", "FFF7C2"),
         "turquoise": ("Turquoise", "E3EEFA")}


def paper(hex_):
    return tuple(int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4))


def pages(data):
    pdfium = pytest.importorskip("pypdfium2")
    doc = pdfium.PdfDocument(data)
    return [np.asarray(doc[n].render(scale=1).to_pil().convert("RGB")).astype(int) for n in range(len(doc))]


def saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf, **SAVE)
    return buf.getvalue()


@pytest.fixture(scope="module")
def merged():
    m = merge_builds([OUT / f"{mode}.pdf" for mode in MODES])
    reports = add_themes(m, [standard(name, paper(hex_)) for name, hex_ in MODES.values()])
    return saved(m.pdf), reports


def test_theme_lab_carries_the_eight_themes_its_author_built(merged):
    with pikepdf.open(io.BytesIO(merged[0])) as pdf:
        assert themes(pdf) == [name for name, _ in MODES.values()]
    assert all(r["kept"] for r in merged[1])


def drawn(data, engine, tmp_path):
    """Page 1 at 144 dpi, as each engine draws it."""
    if engine == "PDFium":
        pdfium = pytest.importorskip("pypdfium2")
        return np.asarray(pdfium.PdfDocument(data)[0].render(scale=2).to_pil().convert("RGB")).astype(int)
    if engine == "MuPDF":
        pymupdf = pytest.importorskip("pymupdf")
        pix = pymupdf.open(stream=data, filetype="pdf")[0].get_pixmap(matrix=pymupdf.Matrix(2, 2))
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm (Poppler) is not installed")
    Image = pytest.importorskip("PIL.Image")
    (tmp_path / "page.pdf").write_bytes(data)
    subprocess.run(["pdftoppm", "-r", "144", "-png", "-singlefile", str(tmp_path / "page.pdf"), str(tmp_path / "page")],
                   check=True)
    return np.asarray(Image.open(tmp_path / "page.png").convert("RGB")).astype(int)


@pytest.mark.parametrize("engine", ["PDFium", "MuPDF", "Poppler"])
@pytest.mark.parametrize("mode", MODES)
def test_each_theme_draws_like_its_own_build(merged, mode, engine, tmp_path):
    with pikepdf.open(io.BytesIO(merged[0])) as pdf:
        apply(pdf, MODES[mode][0])
        shown = drawn(saved(pdf), engine, tmp_path)
    built = drawn((OUT / f"{mode}.pdf").read_bytes(), engine, tmp_path)
    assert shown.shape == built.shape and int(np.abs(shown - built).max()) == 0


def test_eight_themes_cost_less_than_two_builds(merged):
    light = (OUT / "light.pdf").stat().st_size
    assert len(merged[0]) < 2 * light
