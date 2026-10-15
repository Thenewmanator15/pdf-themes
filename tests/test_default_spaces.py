"""A page's default colour spaces are kept, though nothing names them.

/DefaultGray, /DefaultRGB and /DefaultCMYK in a page's colour space resources stand in
for the device spaces wherever the page uses them (ISO 32000-2, 8.6.5.6). No operator
names them, so they looked unused and were dropped. Found in a veraPDF test file that
is PDF/A because its RGB is given a profile this way: without it, Poppler draws the
image 22 levels away, and a PDF/A file with device RGB and a CMYK output intent fails.
"""

import subprocess
import sys

import pikepdf
from pikepdf import Array, Dictionary, Name

CALRGB = Array([Name.CalRGB, Dictionary(WhitePoint=Array([0.9505, 1, 1.089]), Gamma=Array([1.8, 1.8, 1.8]))])


def test_a_default_colour_space_stays_in_the_page_resources(tmp_path):
    src, out = tmp_path / "default.pdf", tmp_path / "themed.pdf"
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    page.obj.Resources = Dictionary(ColorSpace=Dictionary(DefaultRGB=CALRGB))
    page.obj.Contents = pdf.make_stream(b"0.8 0.3 0.2 rg 10 10 80 80 re f")
    pdf.save(src)
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True, capture_output=True)
    with pikepdf.open(out) as themed:
        spaces = themed.pages[0].obj.Resources.get("/ColorSpace") or Dictionary()
        assert "/DefaultRGB" in spaces
        assert str(spaces.DefaultRGB[0]) == "/CalRGB"
