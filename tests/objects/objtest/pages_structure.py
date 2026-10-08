"""Tagged structure: tables, lists, notes, formulas, ruby, and the structure attributes
that carry colour (BackgroundColor, BorderColor, Color, TextDecorationColor)."""
from pikepdf import Array, Dictionary, Name, String

from .core import Page, n, rect_path, round_rect_path

PDF2_NS = "http://iso.org/pdf2/ssn"
MATHML_NS = "http://www.w3.org/1998/Math/MathML"


def layout(doc, **entries):
    d = Dictionary(O=Name.Layout)
    for k, v in entries.items():
        d[Name("/" + k)] = v
    return d


def page_structure(doc, res):
    p = Page(doc, "Tagged structure and colour attributes",
             "Reflow, read-aloud and PDF-to-HTML tools use the structure tree, not the page. Its Layout attributes "
             "carry colours of their own, which a theme has to swap with the page.")
    pal = p.pal
    t = p.grid(2, 4)
    sans, bold = p.font("Sans"), p.font("SansBold")
    pdf2 = doc.namespace(PDF2_NS)

    # 1 Table with colour attributes
    x, y, w, h = p.tile(t[0], "Table with Layout colours", "T371, T377, T378, T384", "swaps",
                        note="TH BackgroundColor and Color, table BorderColor")
    cols, rows = 3, 4
    cw, rh = (w - 8) / cols, min(16, (h - 6) / rows)
    data = [["Theme", "Paper", "Ink"], ["Light", "#FFFFFF", "#1B1D21"], ["Dark", "#18191C", "#E8EAED"],
            ["Tinted", "#FDF6E3", "#1B1D21"]]
    p.begin("Table", attrs=Array([layout(doc, BorderColor=doc.rgb("rule"), BorderThickness=0.5,
                                        BorderStyle=Name.Solid),
                                 Dictionary(O=Name.Table, Summary=String("Paper and ink for three themes"))]))
    for r_ in range(rows):
        p.begin("THead" if r_ == 0 else "TBody") if r_ in (0, 1) else None
        p.begin("TR")
        for c in range(cols):
            cx, cy = x + 4 + c * cw, y + h - 4 - (r_ + 1) * rh
            head = r_ == 0
            fill = "accent" if head else ("tile" if r_ % 2 else "paper")
            p.artifact("%s %s f %s 0.5 w %s S" % (pal.rg(fill), rect_path(cx, cy, cw, rh), pal.RG("rule"), rect_path(cx, cy, cw, rh)))
            attrs = layout(doc, BackgroundColor=doc.rgb(fill), Color=doc.rgb("paper" if head else "ink"))
            if r_ == rows - 1 and c == 0:
                # BorderColor can give each side its own colour: before, after, start, end.
                attrs.BorderColor = Array([doc.rgb("rule"), doc.rgb("accent"), doc.rgb("rule"), doc.rgb("rule")])
            if head:
                attrs = Array([attrs, Dictionary(O=Name.Table, Scope=Name.Column)])
            p.tagged("TH" if head else "TD", p.text_op(cx + 4, cy + rh / 2 - 3, data[r_][c], 7, bold if head else sans,
                                                       "paper" if head else "ink"), attrs=attrs)
        p.end()
        if r_ == 0 or r_ == rows - 1:
            p.end()
    p.end()

    # 2 List
    x, y, w, h = p.tile(t[1], "List with numbering", "T370, T382", "swaps", note="Lbl Color differs from LBody")
    p.begin("L", attrs=Dictionary(O=Name.List, ListNumbering=Name.Decimal))
    for i, item in enumerate(["Swap palettes", "Paint the paper", "Draw as usual"]):
        yy = y + h - 14 - i * 16
        p.begin("LI")
        p.tagged("Lbl", p.text_op(x + 8, yy, "%d." % (i + 1), 8, bold, "accent"), attrs=layout(doc, Color=doc.rgb("accent")))
        p.tagged("LBody", p.text_op(x + 22, yy, item, 8, sans, "ink"))
        p.end()
    p.end()

    # 3 Text decoration colour
    x, y, w, h = p.tile(t[2], "Underline with TextDecorationColor", "T380", "swaps")
    tw = sans.width("A decorated phrase", 9)
    p.tagged("Span", "%s %s %s 0.8 w %s %s m %s %s l S" % (
        p.text_op(x + 6, y + h / 2, "A decorated phrase", 9, sans, "ink"), "", pal.RG("red"), n(x + 6), n(y + h / 2 - 2),
        n(x + 6 + tw), n(y + h / 2 - 2)),
        attrs=layout(doc, TextDecorationType=Name.Underline, TextDecorationColor=doc.rgb("red"),
                     TextDecorationThickness=0.8))

    # 4 Class map
    x, y, w, h = p.tile(t[3], "Attribute class: ClassMap and C", "T354, T355, T360", "swaps", note="Class 'Warning' sets two colours")
    doc.catalog_extra["ClassMap"] = Dictionary(Warning=layout(doc, BackgroundColor=doc.rgb("yellow"), Color=doc.rgb("ink"),
                                                              BorderColor=doc.rgb("orange")))
    p.artifact("%s %s f %s 1 w %s S" % (pal.rg("yellow"), round_rect_path(x + 4, y + h / 2 - 10, w - 8, 24, 4), pal.RG("orange"),
                                        round_rect_path(x + 4, y + h / 2 - 10, w - 8, 24, 4)))
    p.tagged("P", p.text_op(x + 10, y + h / 2 - 1, "Warning: the colours here come from a class.", 7.5, sans, "ink"), cls="Warning")

    # 5 Footnote (PDF 2.0 FENote), expansion and language
    x, y, w, h = p.tile(t[4], "FENote, E and Lang (PDF 2.0 namespace)", "T355, T356, T366, T368", "swaps")
    p.begin("P", ns=pdf2)
    p.tagged("Span", p.text_op(x + 6, y + h - 16, "PDF", 8, bold, "ink"), expansion="Portable Document Format", ns=pdf2)
    p.tagged("Span", p.text_op(x + 6 + bold.width("PDF ", 8), y + h - 16, "themes need a note", 8, sans, "ink"), ns=pdf2)
    p.tagged("Lbl", p.text_op(x + 6 + bold.width("PDF ", 8) + sans.width("themes need a note", 8), y + h - 12, "1", 5.5, sans,
                              "accent"), ns=pdf2)
    p.end()
    p.tagged("P", p.text_op(x + 6, y + h - 32, "Le mode sombre, en français.", 8, sans, "ink"), lang="fr-FR", ns=pdf2)
    p.begin("FENote", ns=pdf2, sid="note1")
    p.tagged("Lbl", p.text_op(x + 6, y + 8, "1", 6, sans, "accent"), ns=pdf2)
    p.tagged("P", p.text_op(x + 12, y + 8, "Footnote text, also themed.", 6, sans, "muted"), ns=pdf2)
    p.end()

    # 6 Formula with MathML associated file
    x, y, w, h = p.tile(t[5], "Formula with a MathML file", "T374, T43", "swaps", note="Alt text and AF: Supplement")
    mathml = (b'<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>L</mi><mo>=</mo><mn>0.2126</mn><mi>R</mi>'
              b'<mo>+</mo><mn>0.7152</mn><mi>G</mi><mo>+</mo><mn>0.0722</mn><mi>B</mi></math>')
    af = doc.embed_file("luminance.mml", mathml, "application/mathml+xml", "Relative luminance", rel="Supplement")
    el = p.tagged("Formula", p.text_op(x + 8, y + h / 2, "L = 0.2126 R + 0.7152 G + 0.0722 B", 8.5, sans, "ink"),
                  alt="L equals 0.2126 R plus 0.7152 G plus 0.0722 B")
    el.af = af

    # 7 Ruby and Warichu
    x, y, w, h = p.tile(t[6], "Ruby and Warichu", "T369", "swaps", note="Readings drawn above the base text")
    cjk = p.font("CID0")
    p.begin("Ruby")
    p.tagged("RB", p.text_op(x + 10, y + h / 2 - 8, "漢字", 16, cjk, "ink"))
    p.tagged("RT", p.text_op(x + 12, y + h / 2 + 12, "かんじ", 7, cjk, "accent"))
    p.end()
    p.begin("Warichu")
    p.tagged("WP", p.text_op(x + 70, y + h / 2 - 8, "（", 12, cjk, "muted"))
    p.tagged("WT", p.text_op(x + 82, y + h / 2 - 2, "割注", 6, cjk, "teal"))
    p.tagged("WT", p.text_op(x + 82, y + h / 2 - 9, "にほんご", 6, cjk, "teal"))
    p.tagged("WP", p.text_op(x + 108, y + h / 2 - 8, "）", 12, cjk, "muted"))
    p.end()

    # 8 Figure with BBox, Caption, TOC
    x, y, w, h = p.tile(t[7], "Figure with BBox and Caption", "T373, T372, T379", "swaps")
    bb = (x + 8, y + 22, w * 0.4, h - 40)
    p.begin("Figure", alt="Three coloured bars", attrs=layout(doc, BBox=Array([bb[0], bb[1], bb[0] + bb[2], bb[1] + bb[3]])))
    p.tagged("Span", " ".join("%s %s f" % (pal.rg(c), rect_path(bb[0] + i * bb[2] / 3, bb[1], bb[2] / 3 - 4, bb[3] * (0.5 + 0.2 * i)))
                              for i, c in enumerate(["red", "green", "blue"])))
    p.tagged("Caption", p.text_op(x + 8, y + 10, "Figure 1: three bars", 6.5, sans, "muted"))
    p.end()
    p.begin("TOC")
    for i, (txt, pg) in enumerate([("Colour spaces", 1), ("Images", 6), ("Annotations", 13)]):
        p.begin("TOCI")
        p.tagged("Reference", p.text_op(x + w * 0.55, y + h - 14 - i * 14, "%s, p%d" % (txt, pg + 1), 7, sans, "accent"))
        p.end()
    p.end()
    return p
