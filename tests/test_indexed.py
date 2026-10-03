"""PDF readers already draw text and shapes through an Indexed colour space,
and swapping only the palette object recolours the page. This is the one
thing the whole design rests on, so it is tested in every engine available."""

import shutil
import subprocess

import numpy as np
import pikepdf
import pytest
from PIL import Image

LIGHT = [(0xF5, 0xF5, 0xF7), (0x9A, 0x20, 0xB6), (0x1D, 0x1D, 0x1F), (0x6E, 0x6E, 0x73)]
DARK = [(0x00, 0x00, 0x00), (0xC4, 0x7B, 0xFF), (0xF2, 0xF2, 0xF7), (0x9A, 0x9A, 0xA2)]
# Points to sample (PDF units, y up) and the palette entry painted there.
POINTS = {"page": ((10, 190), 0), "box": ((70, 50), 1), "thick stroke": ((215, 30), 1), "thin stroke": ((215, 60), 3)}
SCALE = 2


def build(palette, path):
    pdf = pikepdf.new()
    lookup = bytes(c for rgb in palette for c in rgb)
    th0 = pdf.make_indirect(pikepdf.Array([pikepdf.Name.Indexed, pikepdf.Name.DeviceRGB, len(palette) - 1,
                                           pikepdf.String(lookup)]))
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica))
    content = b"""/Th0 cs 0 sc 0 0 300 200 re f
/Th0 cs 1 sc 20 20 100 60 re f
/Th0 CS 1 SC 6 w 150 30 m 280 30 l S
BT /F1 28 Tf /Th0 cs 2 sc 20 130 Td (Themed text) Tj ET
/Th0 CS 3 SC 2 w 150 60 m 280 60 l S
"""
    page = pikepdf.Dictionary(Type=pikepdf.Name.Page, MediaBox=[0, 0, 300, 200],
                              Resources=pikepdf.Dictionary(ColorSpace=pikepdf.Dictionary(Th0=th0),
                                                           Font=pikepdf.Dictionary(F1=font)),
                              Contents=pdf.make_stream(content))
    pdf.pages.append(pikepdf.Page(page))
    pdf.save(path)


def render_pdfium(path):
    pdfium = pytest.importorskip("pypdfium2")
    return pdfium.PdfDocument(str(path))[0].render(scale=SCALE).to_pil().convert("RGB")


def render_mupdf(path):
    pymupdf = pytest.importorskip("pymupdf")
    pix = pymupdf.open(str(path))[0].get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE))
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def render_poppler(path):
    if not shutil.which("pdftoppm"):
        pytest.skip("pdftoppm (Poppler) is not installed")
    out = path.with_suffix("")
    subprocess.run(["pdftoppm", "-r", str(72 * SCALE), "-png", "-singlefile", str(path), str(out)], check=True)
    return Image.open(str(out) + ".png").convert("RGB")


@pytest.mark.parametrize("render", [render_pdfium, render_mupdf, render_poppler], ids=["PDFium", "MuPDF", "Poppler"])
@pytest.mark.parametrize("name,palette", [("light", LIGHT), ("dark", DARK)])
def test_indexed_colours_paint_shapes_and_text(tmp_path, render, name, palette):
    path = tmp_path / f"indexed-{name}.pdf"
    build(palette, path)
    img = render(path)
    for label, ((x, y), idx) in POINTS.items():
        got = img.getpixel((x * SCALE, (200 - y) * SCALE))
        assert max(abs(a - b) for a, b in zip(got, palette[idx])) <= 2, f"{label}: {got} != {palette[idx]}"
    text = np.asarray(img.crop((20 * SCALE, 40 * SCALE, 200 * SCALE, 75 * SCALE))).astype(int)
    inked = int((np.abs(text - np.array(palette[2])).max(axis=2) <= 8).sum())
    assert inked > 1000, "the text was not drawn in its palette colour"
