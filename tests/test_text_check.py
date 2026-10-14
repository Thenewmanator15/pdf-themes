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
