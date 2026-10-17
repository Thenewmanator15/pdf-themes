"""The text contrast check measures text that is seen, and only that.

Text drawn with a fill opacity of 0 is in the file, so PDFium lists it, but nothing of it
is drawn. Measured as if it were seen, its colour blended at opacity 0 is its background,
which gives 1.0:1, and every theme of the document failed on it. Found in a LaTeX paper
whose figure legend carries a copy of each label at opacity 0, and in two GOV.UK reports.
"""

import io

import pikepdf
from pikepdf import Dictionary, Name

from pdfthemes.contrast import check, summary


def page(content):
    pdf = pikepdf.new()
    p = pdf.add_blank_page(page_size=(300, 100))
    p.obj.Contents = pdf.make_stream(content.encode())
    p.obj.Resources = Dictionary(
        Font=Dictionary(F1=Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)),
        ExtGState=Dictionary(Clear=Dictionary(Type=Name.ExtGState, ca=0), Half=Dictionary(Type=Name.ExtGState, ca=0.5)))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_text_drawn_at_opacity_zero_is_not_measured():
    """As in the paper: an unseen copy of a label drawn just before the label itself.
    PDFium keeps the first of two copies of the same text in the same place, so the one it
    lists is the unseen copy, and the label's own black is there to be found in its box."""
    label = "BT /F1 20 Tf 10 40 Td (Label) Tj ET"
    results = check(page(f"q /Clear gs {label} Q {label}"))
    assert [r["ratio"] for r in results if r["ratio"] is not None and r["ratio"] < 21] == []
    assert summary(results)["failures"] == []


def test_text_at_half_opacity_is_measured():
    """Half-black on white is drawn mid-grey, about 3.9:1. Looked for as solid black it
    wasn't found, so it went unmeasured, and a theme could fail it unseen."""
    results = check(page("q /Half gs BT /F1 20 Tf 10 20 Td (Half) Tj ET Q"))
    (half,) = [r for r in results if r["text"] == "Half"]
    assert half["ratio"] is not None and 2.5 < half["ratio"] < 5.5


def type3_page(content, glyph):
    """A page whose font F3 is a Type 3 font with one glyph, 'a', drawn by `glyph`."""
    pdf = pikepdf.new()
    p = pdf.add_blank_page(page_size=(300, 100))
    p.obj.Contents = pdf.make_stream(content.encode())
    font = Dictionary(Type=Name.Font, Subtype=Name.Type3, FontBBox=[0, 0, 1, 1], FontMatrix=[1, 0, 0, 1, 0, 0],
                      FirstChar=97, LastChar=97, Widths=[0.6],
                      Encoding=Dictionary(Type=Name.Encoding, Differences=[97, Name.a]),
                      CharProcs=Dictionary(a=pdf.make_stream(glyph.encode())))
    p.obj.Resources = Dictionary(Font=Dictionary(F3=font))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_text_whose_glyphs_draw_nothing_is_measured_by_what_is_drawn_there():
    """As in a paper's figures (arxiv-2610-12449, pages 2 and 3): each label is drawn as
    filled outlines, with a copy as text over it in a Type 3 font whose glyphs draw nothing,
    for search and copying. The copy was measured in its own colour. In a dark theme the
    copy went white while the outlines stayed dark: the outlines were pushed away from the
    copy until they were black on the black paper, and the check passed."""
    outlines = "0 g 12 36 30 4 re 12 46 30 4 re f"  # strokes of the letters, inside the box
    unseen = "BT /F3 30 Tf 10 30 Td 1 g (aa) Tj ET"
    results = check(type3_page(f"{outlines} {unseen}", "0.6 0 0 0 0.6 1 d1"))
    (label,) = [r for r in results if r["text"] == "aa"]
    assert label["colour"] == "#000000" and label["ratio"] > 15


def test_outlines_too_faint_under_text_that_draws_nothing_fail():
    """Labels drawn in a pale grey on white, as page 2's labels were in the dark theme,
    with copies in black: the copies' black wasn't found in the box, so they went
    unmeasured, and the faint labels passed."""
    outlines = "0.9 g 12 36 30 4 re 12 46 30 4 re f"  # strokes of the letters, inside the box
    unseen = "BT /F3 30 Tf 10 30 Td 0 g (aa) Tj ET"
    results = check(type3_page(f"{outlines} {unseen}", "0.6 0 0 0 0.6 1 d1"))
    (label,) = [r for r in results if r["text"] == "aa"]
    assert label["colour"] == "#E6E6E6" and label["ratio"] < 1.5
    assert summary(results)["failures"] == [label]


def test_text_that_draws_nothing_over_nothing_is_not_measured():
    results = check(type3_page("BT /F3 30 Tf 10 30 Td 0.5 g (aa) Tj ET", "0.6 0 0 0 0.6 1 d1"))
    assert results == []


def test_type3_text_that_draws_is_measured_in_its_own_colour():
    inked = "0.6 0 0 0 0.6 1 d1 0 0 0.6 1 re f"
    results = check(type3_page("BT /F3 30 Tf 10 30 Td 0.5 g (aa) Tj ET", inked))
    assert [(r["text"], r["colour"]) for r in results] == [("aa", "#808080")]
