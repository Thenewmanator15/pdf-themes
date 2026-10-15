"""A file older than PDF 1.5 is written without object streams, and keeps its version.

Saving every file with object streams writes a cross-reference stream and moves the file
to PDF 1.5. PDF/A-1 is built on PDF 1.4 and forbids cross-reference streams (ISO 19005-1,
6.1.4), so six veraPDF test files that pass as PDF/A-1 failed after theming.
"""

import subprocess
import sys

import pikepdf


def test_a_pdf_1_4_file_stays_1_4_without_object_streams(tmp_path):
    src, out = tmp_path / "old.pdf", tmp_path / "themed.pdf"
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(100, 100)).obj.Contents = pdf.make_stream(b"0.2 0.4 0.8 rg 10 10 80 80 re f")
    pdf.save(src, min_version="1.4", force_version="1.4", object_stream_mode=pikepdf.ObjectStreamMode.disable)
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True, capture_output=True)
    with pikepdf.open(out) as themed:
        assert themed.pdf_version == "1.4"
        assert not any(isinstance(o, pikepdf.Stream) and o.get("/Type") in ("/ObjStm", "/XRef") for o in themed.objects)
