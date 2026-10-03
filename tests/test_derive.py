"""Rules for derived themes that don't depend on any one document: a theme
that draws exactly like the default is left out, and a theme is marked as
checked only when some text was measured."""

import io

import pikepdf
from PIL import Image

from pdfthemes import merge, themes
from pdfthemes.derive import add_themes

WIDTH, HEIGHT = 400, 300


def one_page(path, content: bytes, xobjects=None):
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(WIDTH, HEIGHT))
    page.obj.Contents = pdf.make_stream(content)
    if xobjects:
        page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(xobjects))
    pdf.save(path)
    return path


def photo(pdf_path):
    """A page covered by a colourful photo-like JPEG: no text, no white."""
    w, h = 200, 150
    img = Image.new("RGB", (w, h))
    img.putdata([(40 + x, 60 + (x * y) % 120, 200 - y) for y in range(h) for x in range(w)])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    pdf = pikepdf.new()
    image = pikepdf.Stream(pdf, buf.getvalue(), Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                           Width=w, Height=h, ColorSpace=pikepdf.Name.DeviceRGB, BitsPerComponent=8,
                           Filter=pikepdf.Name.DCTDecode)
    page = pdf.add_blank_page(page_size=(WIDTH, HEIGHT))
    page.obj.Contents = pdf.make_stream(f"q {WIDTH} 0 0 {HEIGHT} 0 0 cm /Im0 Do Q".encode())
    page.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    pdf.save(pdf_path)
    return pdf_path


def theme_info(path):
    with pikepdf.open(path) as pdf:
        t = pdf.Root["/XXThemes"]
        out = {str(t.Default.Name): "/Checked" in t.Default}
        for a in t.Alternates:
            out[str(a.Name)] = "/Checked" in a
        return out


def themed(src, dst):
    m = merge(src)
    reports = add_themes(m, (1.0, 1.0, 1.0), (0x1C / 255, 0x1C / 255, 0x1E / 255))
    m.pdf.save(dst)
    return {r["name"]: r for r in reports}


def test_themes_that_draw_like_the_default_are_left_out(tmp_path):
    reports = themed(photo(tmp_path / "photo.pdf"), tmp_path / "out.pdf")
    with pikepdf.open(tmp_path / "out.pdf") as pdf:
        assert themes(pdf) == ["Light"]
    assert reports["Cream"]["kept"] is False
    assert reports["Cream"]["reason"] == "unchanged"


def test_a_theme_with_no_text_is_kept_but_not_marked_checked(tmp_path):
    # a black bar on white paper: Dark changes it, but there is no text to measure
    page = one_page(tmp_path / "bar.pdf", b"0 g 50 120 300 60 re f")
    reports = themed(page, tmp_path / "out.pdf")
    assert reports["Dark"]["kept"] is True
    assert reports["Dark"]["passed"] is False
    info = theme_info(tmp_path / "out.pdf")
    assert "Dark" in info
    assert not any(info.values()), info  # no theme claims a contrast check


def test_more_contrast_is_left_out_when_the_page_is_already_black_on_white(tmp_path):
    page = one_page(tmp_path / "bar.pdf", b"0 g 50 120 300 60 re f")
    reports = themed(page, tmp_path / "out.pdf")
    assert reports["Light, more contrast"]["kept"] is False
    assert reports["Light, more contrast"]["reason"] == "unchanged"
    assert reports["Cream"]["kept"] is True  # the paper shows, so a tint does change the page
