"""Build the test page in both modes, merge with the standard themes, show
the dark theme the way a reader would, and check it draws exactly like the
dark build."""

import pathlib

import numpy as np
import pikepdf
import pytest

from pdfthemes import apply, describe, merge, paint_paper, themes
from pdfthemes.derive import add_themes

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample" / "sample.typ"
FONTS = ROOT / "examples" / "fonts"
DARK_PAPER = (0x1C / 255, 0x1C / 255, 0x1E / 255)
STANDARD = ["Light", "Dark", "Light, more contrast", "Dark, more contrast", "Cream", "Peach", "Yellow", "Turquoise"]


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    typst = pytest.importorskip("typst")
    d = tmp_path_factory.mktemp("builds")
    paths = {}
    for mode in ("light", "dark"):
        data = typst.compile(str(SAMPLE), root=str(SAMPLE.parent), font_paths=[str(FONTS)],
                             ignore_system_fonts=True, sys_inputs={"mode": mode}, pdf_standards=["2.0"])
        paths[mode] = d / f"{mode}.pdf"
        paths[mode].write_bytes(data)
    m = merge(paths["light"], paths["dark"], organise=True)
    paths["reports"] = add_themes(m, (1, 1, 1), DARK_PAPER)
    paths["themed"] = d / "themed.pdf"
    m.pdf.save(paths["themed"])
    paths["merger"] = m
    return paths


def render(path):
    pdfium = pytest.importorskip("pypdfium2")
    return np.asarray(pdfium.PdfDocument(str(path))[0].render(scale=2).to_pil().convert("RGB")).astype(int)


def test_every_standard_theme_passes_and_is_kept(builds):
    with pikepdf.open(builds["themed"]) as pdf:
        assert themes(pdf) == STANDARD
    assert all(r["kept"] and r["passed"] for r in builds["reports"])


def test_dark_theme_swaps_palettes_only(builds):
    with pikepdf.open(builds["themed"]) as pdf:
        dark = next(t for t in describe(pdf)["themes"] if t["name"] == "Dark")
    assert {r["kind"] for r in dark["replace"]} == {"palette"}  # the page palette and the chart image's palette


def test_default_theme_draws_like_the_light_build(builds):
    assert np.array_equal(render(builds["light"]), render(builds["themed"]))


def test_dark_theme_draws_like_the_dark_build(builds, tmp_path):
    with pikepdf.open(builds["themed"]) as pdf:
        paint_paper(pdf, apply(pdf, "Dark"))
        pdf.save(tmp_path / "as-dark.pdf")
    with pikepdf.open(builds["dark"]) as pdf:
        paint_paper(pdf, DARK_PAPER)
        pdf.save(tmp_path / "dark-on-paper.pdf")
    assert np.array_equal(render(tmp_path / "dark-on-paper.pdf"), render(tmp_path / "as-dark.pdf"))


def test_chart_image_becomes_one_plane_of_palette_indices(builds):
    assert builds["merger"].stats["images stored as palette indices"] == 1


def test_text_and_tags_are_stored_once(builds):
    pymupdf = pytest.importorskip("pymupdf")
    text = lambda p: "".join(page.get_text() for page in pymupdf.open(str(p)))
    assert text(builds["light"]) == text(builds["themed"])
    with pikepdf.open(builds["themed"]) as pdf:
        assert "/StructTreeRoot" in pdf.Root
