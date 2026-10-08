"""theme-lab (tests/theme-lab): Lilaq plots built once per theme, eight
themes in all, each with its colours set in the source. Merged into one file,
every theme has to draw like the build it came from."""

import io
import pathlib

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


@pytest.mark.parametrize("mode", MODES)
def test_each_theme_draws_like_its_own_build(merged, mode):
    with pikepdf.open(io.BytesIO(merged[0])) as pdf:
        apply(pdf, MODES[mode][0])
        shown = pages(saved(pdf))
    built = pages((OUT / f"{mode}.pdf").read_bytes())
    assert max(int(np.abs(a - b).max()) for a, b in zip(shown, built)) == 0


def test_eight_themes_cost_less_than_two_builds(merged):
    light = (OUT / "light.pdf").stat().st_size
    assert len(merged[0]) < 2 * light
