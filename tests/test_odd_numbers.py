"""A number written oddly stays with the operator it belongs to.

Google's export writes some numbers as `0.00-10`, which isn't a number in PDF. Readers
take it for 0 with a warning. pikepdf takes it for an operator with no operands, so the
`m` after it seems to have one number. Kept in its place that does no harm, but a colour
written between the two cut the number off from its `m` or `l`, and Poppler then left
out the segment, a quarter of a million pixels on five slides of one deck.
"""

import subprocess
import sys

import numpy as np
import pikepdf
import pypdfium2 as pdfium

SHAPE = b"q 1 0 0 1 50 0 cm 0 0 1 rg\n0.00-10\n80 m\n0.00-10\n20 l\n40 20 l\n40 80 l\nh f Q\n"
COUNTS = {"m": 2, "l": 2, "c": 6, "v": 4, "y": 4, "re": 4}


def drawn(path):
    doc = pdfium.PdfDocument(str(path))
    try:
        return np.asarray(doc[0].render(scale=1).to_pil().convert("RGB"))
    finally:
        doc.close()


def test_an_odd_number_is_written_with_its_path_operator(tmp_path):
    src, out = tmp_path / "odd.pdf", tmp_path / "themed.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100)).obj.Contents = pdf.make_stream(SHAPE)
    pdf.save(src)
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True, capture_output=True)
    with pikepdf.open(out) as themed:
        ops = pikepdf.parse_content_stream(themed.pages[0].obj)
    assert [str(op) for _, op in ops if str(op)[:1].isdigit() or str(op)[:1] in "+-."] == []
    assert all(len(operands) == COUNTS[str(op)] for operands, op in ops if str(op) in COUNTS)
    assert np.array_equal(drawn(src), drawn(out))
