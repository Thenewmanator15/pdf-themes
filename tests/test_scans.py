"""Scanned pages: a grey scan is given a palette without touching its data,
so the default theme draws it exactly as before, Dark shows light text on
dark paper, and a tint shows where the page was white. A grey photo is left
alone."""

import io
import pathlib
import zlib

import numpy as np
import pikepdf
import pytest
from PIL import Image, ImageDraw, ImageFont

from pdfthemes import apply, merge, paint_paper, themes
from pdfthemes.derive import add_themes

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "examples" / "fonts" / "Inter-Regular.otf"
DARK_PAPER = (0x1C / 255, 0x1C / 255, 0x1E / 255)
PAGE = (420, 595)  # A5 in points
LINES = ["Colour themes for PDF: one file, its content stored once,",
         "with light, dark, higher contrast and tinted themes.",
         "A scanned page has no text and no vector colour, only",
         "an image of the page, so its themes come from the scan."]


def scan_image(mode):
    w, h = 583, 827  # A5 at 100 dpi
    img = Image.new("L", (w, h), 247)  # a real scan's paper is rarely pure white
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT), 17)
    for k in range(24):
        draw.text((55, 60 + 30 * k), LINES[k % len(LINES)], fill=30, font=font)
    return img if mode == "L" else img.point(lambda v: 255 if v > 140 else 0, mode="1")


def write_page(path, image_stream_args, data):
    pdf = pikepdf.new()
    image = pikepdf.Stream(pdf, data, Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image, **image_stream_args)
    page = pdf.add_blank_page(page_size=PAGE)
    page.obj.Contents = pdf.make_stream(f"q {PAGE[0]} 0 0 {PAGE[1]} 0 0 cm /Im0 Do Q".encode())
    page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    pdf.save(path)
    return path


def scan_pdf(path, kind):
    """kind: 'jpeg' (8-bit grey, DCTDecode) or 'bilevel' (1-bit, FlateDecode)."""
    if kind == "jpeg":
        img = scan_image("L")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=75)
        args = dict(Width=img.width, Height=img.height, ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=8,
                    Filter=pikepdf.Name.DCTDecode)
        return write_page(path, args, buf.getvalue())
    img = scan_image("1")
    args = dict(Width=img.width, Height=img.height, ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=1,
                Filter=pikepdf.Name.FlateDecode)
    return write_page(path, args, zlib.compress(img.tobytes()))


def image_raw(path):
    with pikepdf.open(path) as pdf:
        return pdf.pages[0].Resources.XObject.Im0.read_raw_bytes() if "/Im0" in pdf.pages[0].Resources.XObject \
            else next(iter(pdf.pages[0].Resources.XObject.values())).read_raw_bytes()


def shown(src, dst, theme):
    with pikepdf.open(src) as pdf:
        paint_paper(pdf, apply(pdf, theme))
        pdf.save(dst)
    return dst


def pdfium_pixels(path, scale=1.0):
    import pypdfium2 as pdfium
    return np.asarray(pdfium.PdfDocument(str(path))[0].render(scale=scale).to_pil().convert("RGB")).astype(int)


def mupdf_pixels(path):
    pymupdf = pytest.importorskip("pymupdf")
    pix = pymupdf.open(str(path))[0].get_pixmap()
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)


@pytest.fixture(scope="module", params=["jpeg", "bilevel"])
def scan(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    src = scan_pdf(d / "scan.pdf", request.param)
    m = merge(src)
    reports = add_themes(m, (1.0, 1.0, 1.0), DARK_PAPER)
    out = d / "themed.pdf"
    m.pdf.save(out)
    return {"src": src, "themed": out, "dir": d, "kind": request.param, "reports": {r["name"]: r for r in reports}}


def test_default_theme_draws_exactly_like_the_scan(scan):
    assert np.array_equal(pdfium_pixels(scan["src"]), pdfium_pixels(scan["themed"]))
    assert np.array_equal(mupdf_pixels(scan["src"]), mupdf_pixels(scan["themed"]))


def test_the_scan_is_stored_as_it_was(scan):
    assert image_raw(scan["themed"]) == image_raw(scan["src"])


def test_every_standard_theme_that_changes_the_page_is_kept(scan):
    with pikepdf.open(scan["themed"]) as pdf:
        kept = themes(pdf)
    if scan["kind"] == "jpeg":
        assert len(kept) == 8
    else:  # pure black on white already: more contrast would draw it the same
        assert len(kept) == 7 and "Light, more contrast" not in kept


def test_dark_shows_light_text_on_dark_paper(scan):
    before = pdfium_pixels(scan["src"]).mean(axis=2)
    dark = pdfium_pixels(shown(scan["themed"], scan["dir"] / "dark.pdf", "Dark")).mean(axis=2)
    assert dark[before < 60].mean() > 170   # the ink is now light
    assert dark[before > 235].mean() < 40   # the paper is now dark


def test_a_tint_shows_where_the_page_was_white(scan):
    with pikepdf.open(scan["themed"]) as pdf:
        cream = next(a for a in pdf.Root["/XXThemes"].Alternates if str(a.Name) == "Cream")
        paper = np.array([float(v) * 255 for v in cream.Paper])
    before = pdfium_pixels(scan["src"]).mean(axis=2)
    tinted = pdfium_pixels(shown(scan["themed"], scan["dir"] / "cream.pdf", "Cream"))
    assert np.abs(tinted[before > 235].mean(axis=0) - paper).max() < 3
    assert tinted[before < 60].mean() < 60  # the ink stays dark


def test_scanned_pages_share_one_palette_per_theme(tmp_path):
    pdf = pikepdf.new()
    for shift in (0, 7, 14):  # three different pages
        img = Image.new("L", (300, 420), 247)
        ImageDraw.Draw(img).text((30 + shift, 40), LINES[0], fill=30, font=ImageFont.truetype(str(FONT), 12))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=75)
        image = pikepdf.Stream(pdf, buf.getvalue(), Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                               Width=300, Height=420, ColorSpace=pikepdf.Name.DeviceGray, BitsPerComponent=8,
                               Filter=pikepdf.Name.DCTDecode)
        page = pdf.add_blank_page(page_size=(300, 420))
        page.obj.Contents = pdf.make_stream(b"q 300 0 0 420 0 0 cm /Im0 Do Q")
        page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    pdf.save(tmp_path / "book.pdf")
    m = merge(tmp_path / "book.pdf")
    add_themes(m, (1.0, 1.0, 1.0), DARK_PAPER)
    m.pdf.save(tmp_path / "out.pdf")
    with pikepdf.open(tmp_path / "out.pdf") as out:
        dark = next(a for a in out.Root["/XXThemes"].Alternates if str(a.Name) == "Dark")
        assert len(dark.Replace) == 2  # one palette and its replacement, for all three pages


def test_a_grey_photo_is_not_recoloured(tmp_path):
    w, h = 300, 200
    y, x = np.mgrid[0:h, 0:w]
    photo = (128 + 90 * np.sin(x / 23.0) * np.cos(y / 17.0)).astype(np.uint8)  # all tones, no page of white
    buf = io.BytesIO()
    Image.fromarray(photo, "L").save(buf, "JPEG", quality=85)
    src = write_page(tmp_path / "photo.pdf", dict(Width=w, Height=h, ColorSpace=pikepdf.Name.DeviceGray,
                                                  BitsPerComponent=8, Filter=pikepdf.Name.DCTDecode), buf.getvalue())
    m = merge(src)
    add_themes(m, (1.0, 1.0, 1.0), DARK_PAPER)
    m.pdf.save(tmp_path / "out.pdf")
    with pikepdf.open(tmp_path / "out.pdf") as pdf:
        assert themes(pdf) == ["Light"]
