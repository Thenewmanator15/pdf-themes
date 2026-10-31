"""Fault 15 in the contrast check: text is classed as large by the size it is
drawn at, not the size its font is set at. 20 pt text drawn at half size was
held to the 3:1 for large text where WCAG asks 4.5:1, and 1 pt text scaled up
to 20 pt to the 4.5:1 for normal text."""

import pikepdf
import pytest

from pdfthemes.contrast import check


def page(content):
    pdf = pikepdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica))
    pdf.pages.append(pikepdf.Page(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=[0, 0, 612, 792],
        Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)),
        Contents=pdf.make_stream(content))))
    return pdf


@pytest.fixture
def one(tmp_path):
    def one(content):
        path = tmp_path / "t.pdf"
        page(content).save(path)
        [r] = check(str(path))
        return r
    return one


def test_text_set_large_and_drawn_small_is_held_to_the_normal_minimum(one):
    r = one(b"q 0.5 0 0 0.5 72 500 cm 0.541 g BT /F1 20 Tf 0 0 Td (SCALED grey) Tj ET Q")
    assert r["size"] == pytest.approx(10, abs=0.2)
    assert not r["large"] and r["needs"] == 4.5
    assert r["ratio"] < r["needs"]


def test_text_set_small_and_scaled_up_by_its_text_matrix_is_large(one):
    r = one(b"0.541 g BT /F1 1 Tf 20 0 0 20 72 500 Tm (SCALED up) Tj ET")
    assert r["size"] == pytest.approx(20, abs=0.2)
    assert r["large"] and r["needs"] == 3.0


def test_text_scaled_up_by_the_current_matrix_is_measured_at_its_drawn_size(one):
    r = one(b"q 2 0 0 2 72 500 cm 0 g BT /F1 7 Tf 0 0 Td (DOUBLED) Tj ET Q")
    assert r["size"] == pytest.approx(14, abs=0.2)


def test_unscaled_text_keeps_its_size(one):
    r = one(b"0.541 g BT /F1 10 Tf 72 450 Td (TRUE grey) Tj ET")
    assert r["size"] == 10
    assert not r["large"]


def test_rotated_text_keeps_its_size(tmp_path):
    # 90 degrees: the upright stretch is the length of (c, d), not d alone. Turned
    # text comes out a run per letter, as it always has.
    path = tmp_path / "t.pdf"
    page(b"0 g BT /F1 12 Tf 0 1 -1 0 300 300 Tm (SIDEWAYS) Tj ET").save(path)
    sizes = [r["size"] for r in check(str(path))]
    assert sizes and all(s == pytest.approx(12, abs=0.2) for s in sizes)
