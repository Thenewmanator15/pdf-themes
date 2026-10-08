"""The objects test (tests/objects): light and dark pairs that between them
hold every kind of object a PDF 2.0 file can contain. Merge each pair and
check that both themes draw like the builds they came from."""

import io
import pathlib

import numpy as np
import pikepdf
import pytest

from pdfthemes import apply, merge, paint_paper, themes
from pdfthemes.core import SAVE
from pdfthemes.derive import add_themes

OUT = pathlib.Path(__file__).resolve().parent / "objects" / "out"
DARK_PAPER = (0x18 / 255, 0x19 / 255, 0x1C / 255)
PAIRS = sorted(p for p in [*OUT.glob("*-light.pdf"), *OUT.glob("figures/*-light.pdf")])
# The main pair paints through 8-bit palettes, so a colour written as decimals
# in a CIE-based or ICC space can land a few levels away once it's converted.
LEVELS = {"objects-light.pdf": 4}


def pages(data):
    pdfium = pytest.importorskip("pypdfium2")
    doc = pdfium.PdfDocument(data)
    return [np.asarray(doc[n].render(scale=1).to_pil().convert("RGB")).astype(int) for n in range(len(doc))]


def saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf, **SAVE)
    return buf.getvalue()


def furthest(a, b):
    return max(int(np.abs(x - y).max()) for x, y in zip(a, b))


@pytest.mark.parametrize("light", PAIRS, ids=lambda p: p.name.replace("-light.pdf", ""))
def test_pair_merges_and_both_themes_draw_like_the_builds(light):
    dark = light.with_name(light.name.replace("-light", "-dark"))
    m = merge(pikepdf.open(light), pikepdf.open(dark))
    add_themes(m, (1, 1, 1), DARK_PAPER, derived=False)
    themed = saved(m.pdf)
    allowed = LEVELS.get(light.name, 0)
    assert furthest(pages(themed), pages(light.read_bytes())) <= allowed
    with pikepdf.open(io.BytesIO(themed)) as pdf:
        assert themes(pdf) == ["Light", "Dark"]
        paint_paper(pdf, apply(pdf, "Dark"))
        as_dark = saved(pdf)
    with pikepdf.open(dark) as pdf:
        paint_paper(pdf, DARK_PAPER)
        on_paper = saved(pdf)
    assert furthest(pages(as_dark), pages(on_paper)) <= allowed
