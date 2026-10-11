"""An image whose soft mask has a Matte entry keeps its colour values.

Matte says the image's colours were blended with a matte colour beforehand, and a
reader undoes that with arithmetic on the colour components (ISO 32000-2, 11.6.5.3).
The matte colour is written in the image's own colour space, so turning the image into
palette indices leaves a three-number Matte beside a one-component image, and the
arithmetic no longer means anything. Found on a scanned signature in a public PDF,
where PDFium, MuPDF and Poppler all drew the themed file differently.
"""

import subprocess
import sys
import zlib

import numpy as np
import pikepdf
import pypdfium2 as pdfium
from pikepdf import Array, Dictionary, Name

W, H = 60, 24


def build(path, matte):
    """A drawing on white, dark strokes with soft edges, the kind `add` gives a palette."""
    alpha = np.full((H, W), 255, np.uint8)
    rgb = np.full((H, W, 3), 255, np.uint8)
    rgb[8:16, 10:50] = (20, 30, 90)
    alpha[7, 10:50] = alpha[16, 10:50] = 128      # soft edges
    rgb[7, 10:50] = rgb[16, 10:50] = (20, 30, 90)
    alpha[:, :2] = 64                             # and a faint border, as a scan's edge has
    pre = (rgb.astype(float) * alpha[..., None] / 255).round().astype(np.uint8)  # blended with a black matte

    pdf = pikepdf.new()
    smask = pikepdf.Stream(pdf, zlib.compress(alpha.tobytes()))
    smask.Type, smask.Subtype, smask.Width, smask.Height = Name.XObject, Name.Image, W, H
    smask.ColorSpace, smask.BitsPerComponent, smask.Filter = Name.DeviceGray, 8, Name.FlateDecode
    if matte:
        smask.Matte = Array([0, 0, 0])
    image = pikepdf.Stream(pdf, zlib.compress((pre if matte else rgb).tobytes()))
    image.Type, image.Subtype, image.Width, image.Height = Name.XObject, Name.Image, W, H
    image.ColorSpace, image.BitsPerComponent, image.Filter = Name.DeviceRGB, 8, Name.FlateDecode
    image.SMask = pdf.make_indirect(smask)
    page = pdf.add_blank_page(page_size=(200, 100))
    page.Resources = Dictionary(XObject=Dictionary(Im0=pdf.make_indirect(image)))
    page.Contents = pdf.make_stream(b"1 1 1 rg 0 0 200 100 re f q 150.5 0 0 60.5 20.3 20.3 cm /Im0 Do Q")
    pdf.save(path)


def add(src, out):
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True,
                   capture_output=True)


def image_family(path):
    with pikepdf.open(path) as pdf:
        (x,) = [o for o in pdf.pages[0].Resources.XObject.values() if o.get("/Subtype") == "/Image"]
        space = x.ColorSpace
        return str(space[0]) if isinstance(space, pikepdf.Array) else str(space)


def render(path, scale):
    doc = pdfium.PdfDocument(str(path))
    try:
        return np.asarray(doc[0].render(scale=scale).to_pil().convert("RGB"))
    finally:
        doc.close()


def test_a_matted_image_keeps_its_colour_space_and_its_look(tmp_path):
    src, out = tmp_path / "matte.pdf", tmp_path / "themed.pdf"
    build(src, matte=True)
    add(src, out)
    assert image_family(out) == "/DeviceRGB"
    for scale in (1, 2):
        assert np.array_equal(render(src, scale), render(out, scale))


def test_the_same_image_without_a_matte_still_gets_a_palette(tmp_path):
    """The control: without Matte this is a drawing on white and is given a palette.

    Its two colours are packed one bit to an index, and PDFium draws a 1-bit image
    one level off where it resamples it (MuPDF and Poppler don't), so the look is
    held to one level here and not to the pixel."""
    src, out = tmp_path / "plain.pdf", tmp_path / "themed.pdf"
    build(src, matte=False)
    add(src, out)
    assert image_family(out) == "/Indexed"
    for scale in (1, 2):
        diff = np.abs(render(src, scale).astype(int) - render(out, scale).astype(int))
        assert diff.max() <= 1
