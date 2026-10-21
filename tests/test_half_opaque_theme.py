"""A theme aims higher for text drawn at less than full opacity.

A theme moves a text colour until the colour stands out from its background, but text
drawn at opacity 0.6 is seen blended with what is behind it, and stands out less. Once the
check measured such text (it had been passed over), the digits on a plot in an arXiv
paper fell short in seven derived themes, which were left out.
"""

import pikepdf
from pikepdf import Dictionary, Name

from pdfthemes import merge
from pdfthemes.derive import add_themes


def plot_labels():
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    page.obj.Resources = Dictionary(
        Font=Dictionary(F1=Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)),
        ExtGState=Dictionary(Faint=Dictionary(Type=Name.ExtGState, ca=0.6)))
    page.obj.Contents = pdf.make_stream(
        b"0 g BT /F1 11 Tf 20 160 Td (A caption in black.) Tj ET "
        b"q /Faint gs 0.82 0.10 0.12 rg BT /F1 12 Tf 40 60 Td (4) Tj ET Q")
    return pdf


def test_half_opaque_red_digits_keep_the_dark_theme():
    (dark,) = [r for r in add_themes(merge(plot_labels())) if r["name"] == "Dark"]
    assert dark["kept"] and dark["passed"], dark["failures"]


def faint_black_digits():
    """As on page 16 of arxiv-2604-13237: black digits drawn at opacity 0.6, which read grey,
    about 5.7:1 on white, and beside them a band at opacity 0.3, a shape and not text."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    page.obj.Resources = Dictionary(
        Font=Dictionary(F1=Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)),
        ExtGState=Dictionary(Faint=Dictionary(Type=Name.ExtGState, ca=0.6),
                             Band=Dictionary(Type=Name.ExtGState, ca=0.3)))
    page.obj.Contents = pdf.make_stream(
        b"0 g BT /F1 11 Tf 20 160 Td (A caption in black.) Tj ET "
        b"q /Band gs 0.2 0.4 0.8 rg 20 20 260 20 re f Q "
        b"q /Faint gs 0 g BT /F1 12 Tf 40 80 Td (0.25 0.50 0.75) Tj ET Q")
    return pdf


def opacities(pdf, theme):
    """The fill opacity of each graphics state the page names, as the theme shows it."""
    from pdfthemes import apply
    apply(pdf, theme)
    out = {}
    for name, gs in pdf.pages[0].Resources.ExtGState.items():
        out[name] = float(gs.get("/ca", 1.0))
    return out


def test_more_contrast_lifts_faint_text_only_as_far_as_it_needs(tmp_path):
    """Black can't get darker, so the theme raises the digits' opacity: enough for 7:1 and
    no more. The default keeps the author's 0.6, and the band, which isn't text, keeps 0.3."""
    m = merge(faint_black_digits())
    reports = {r["name"]: r for r in add_themes(m)}
    assert reports["Light, more contrast"]["kept"], reports["Light, more contrast"]["failures"]
    m.pdf.save(tmp_path / "out.pdf")
    with pikepdf.open(tmp_path / "out.pdf") as pdf:
        default = sorted(float(gs.get("/ca", 1.0)) for gs in pdf.pages[0].Resources.ExtGState.values())
    assert default == [0.3, 0.6]
    with pikepdf.open(tmp_path / "out.pdf") as pdf:
        lifted = sorted(opacities(pdf, "Light, more contrast").values())
    assert lifted[0] == 0.3
    assert 0.6 < lifted[1] < 1.0  # 7:1 needs about 0.7, not full opacity
