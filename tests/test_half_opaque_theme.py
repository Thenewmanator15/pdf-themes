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
