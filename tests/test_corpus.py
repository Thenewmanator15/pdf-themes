"""The test document that carries colour in every way PDF allows
(tools/corpus.py): merging two builds, or organising one, must leave each
build's look and colour values exactly as they were.

Pixels are compared in MuPDF, which matches on every page. (PDFium differs
on one swatch of the original light build, because it ignores the initial
colour that `cs` sets; tools/check_corpus.py reports all three engines.)"""

import pathlib
import sys

import numpy as np
import pikepdf
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import corpus  # noqa: E402
from check_corpus import colour_values, compare_values  # noqa: E402
from pdfthemes import apply, merge, paint_paper, themes  # noqa: E402
from pdfthemes.derive import add_themes  # noqa: E402

LIGHT_PAPER = (1.0, 1.0, 1.0)
DARK_PAPER = tuple(v / 255 for v in corpus.rgb255(corpus.DARK["paper"]))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("corpus")
    return corpus.write(d), d


def shown(src, dst, theme=None, paper=LIGHT_PAPER):
    with pikepdf.open(src) as pdf:
        if theme is not None:
            paper = apply(pdf, theme)
        paint_paper(pdf, paper)
        values = colour_values(pdf)
        pdf.save(dst)
    return values


def same_pixels(a, b):
    pymupdf = pytest.importorskip("pymupdf")
    da, db = pymupdf.open(str(a)), pymupdf.open(str(b))
    for pa, pb in zip(da, db):
        x = np.frombuffer(pa.get_pixmap().samples, dtype=np.uint8)
        y = np.frombuffer(pb.get_pixmap().samples, dtype=np.uint8)
        if not np.array_equal(x, y):
            return False
    return len(da) == len(db)


def test_two_builds_merge_exactly(built):
    paths, d = built
    m = merge(paths["light"], paths["dark"], organise=True)
    reports = add_themes(m, LIGHT_PAPER, DARK_PAPER, derived=False)
    themed = d / "themed.pdf"
    m.pdf.save(themed)
    assert all(r["passed"] for r in reports)
    for theme, build, paper in (("Light", paths["light"], LIGHT_PAPER), ("Dark", paths["dark"], DARK_PAPER)):
        values_build = shown(build, d / f"build-{theme}.pdf", None, paper)
        values_theme = shown(themed, d / f"themed-{theme}.pdf", theme)
        assert compare_values(values_build, values_theme)["differ"] == []
        assert same_pixels(d / f"build-{theme}.pdf", d / f"themed-{theme}.pdf")


def test_one_build_keeps_its_look_and_gains_every_standard_theme(built):
    paths, d = built
    m = merge(paths["light"])
    reports = add_themes(m, LIGHT_PAPER, DARK_PAPER)
    themed = d / "single.pdf"
    m.pdf.save(themed)
    assert all(r["kept"] and r["passed"] for r in reports), [r for r in reports if not r["passed"]]
    assert len(themes(pikepdf.open(themed))) == 8
    values_build = shown(paths["light"], d / "single-build.pdf")
    values_theme = shown(themed, d / "single-themed.pdf", "Light")
    assert compare_values(values_build, values_theme)["differ"] == []
    assert same_pixels(d / "single-build.pdf", d / "single-themed.pdf")
