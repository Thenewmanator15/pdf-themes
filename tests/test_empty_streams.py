"""Every compressed stream in a written file decompresses.

qpdf, compressing on save, writes a stream with no data as /FlateDecode with no bytes at
all, which isn't a Flate stream: it has no header. MuPDF says "premature end of data in
flate filter" for it. Found on an empty form in a LaTeX paper, written again by `add`.
"""

import subprocess
import sys
import zlib

import pikepdf
from pikepdf import Array, Dictionary, Name


def test_an_empty_form_is_written_as_a_whole_flate_stream(tmp_path):
    src, out = tmp_path / "empty.pdf", tmp_path / "themed.pdf"
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    empty = pdf.make_stream(b"")
    empty.Type, empty.Subtype, empty.BBox = Name.XObject, Name.Form, Array([0, 0, 1, 1])
    page.obj.Resources = Dictionary(XObject=Dictionary(Empty=empty))
    page.obj.Contents = pdf.make_stream(b"0 0 1 rg 10 10 50 50 re f /Empty Do")
    pdf.save(src)
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True, capture_output=True)
    with pikepdf.open(out) as themed:
        for obj in themed.objects:
            if isinstance(obj, pikepdf.Stream) and obj.get("/Filter") == Name.FlateDecode:
                d = zlib.decompressobj()
                d.decompress(obj.read_raw_bytes())
                assert d.eof, f"object {obj.objgen} is marked FlateDecode but isn't a whole Flate stream"
