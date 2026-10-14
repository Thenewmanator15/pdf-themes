"""A text colour is held to contrast against the surfaces it sits on, the paper first.

A worked-out theme moves each text colour lighter or darker until it stands out from
the backgrounds on one side of it: the side with more background colours, counted one
each, and on a tie the lighter side. In a GOV.UK report one purple band and the paper
tied, the purple headings were held against the band, made black, and left black on the
dark paper of every dark theme, which then failed and was left out. A tie now goes to the
paper's side. Two bands still outvote the paper, as in a second report: which side text
is on can't be told from colours alone, and the test document's labels on white boxes
need the count to win there.
"""

import pikepdf
from pikepdf import Name

from pdfthemes import merge
from pdfthemes.derive import add_themes

PURPLE = "0.561 0.137 0.702"   # (143, 35, 179), the report's headings and its band


def report(*bands):
    """A heading and a line of body text on white, and coloured bands across the foot."""
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(400, 600))
    page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)))
    feet = "".join(f"{colour} rg 0 {20 * k} 400 20 re f " for k, colour in enumerate(bands))
    page.obj.Contents = pdf.make_stream(
        (f"{feet}{PURPLE} rg BT /F1 18 Tf 40 540 Td (A purple heading) Tj ET "
         "0 g BT /F1 11 Tf 40 500 Td (Body text in black, on the white page.) Tj ET").encode())
    return pdf


def theme_of(pdf, name):
    (theme,) = [r for r in add_themes(merge(pdf)) if r["name"] == name]
    return theme


def test_a_heading_in_the_colour_of_a_band_keeps_its_dark_theme():
    dark = theme_of(report(PURPLE), "Dark")
    assert dark["kept"] and dark["passed"], dark["failures"]

