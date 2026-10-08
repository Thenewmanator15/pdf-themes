"""Appendix: how to read the test, and the coverage table generated from every tile."""
from pikepdf import Array, Dictionary, Name, String

from .core import MARGIN, H, W, Page, n, rect_path, round_rect_path

EXCLUDED = [
    ("XFA forms", "Deprecated in PDF 2.0; most viewers no longer render them."),
    ("PostScript XObjects and the PS operator", "Removed in PDF 2.0."),
    ("Web Capture (SpiderInfo, IDS, URLS)", "Records where pages came from; draws nothing."),
    ("Alternate presentations (slide shows)", "Deprecated; no current viewer plays them."),
    ("JBIG2 symbol dictionaries and text regions", "Generic regions are tested; symbol coding needs an encoder we don't have."),
    ("Portable collections (portfolios)", "Change how the whole file opens, so they're a separate test pair."),
    ("Encryption and signatures", "Change how the file is stored, not what's drawn: separate variant files."),
    ("Annotations and fields without appearances", "Not allowed in PDF 2.0, but common: they're in the legacy pair."),
    ("3D PRC streams", "No PRC writer was available; the U3D stream carries the same PDF-side colours."),
]

LEGEND = [
    ("swaps", "The theme must change it. The dark build shows the intended result."),
    ("stays", "Photos, print-production marks and media keep their colours in every theme."),
    ("viewer", "Drawn by the viewer from entries in the file, so the viewer has to follow the theme."),
]


def page_appendix(doc, res):
    pal = doc.pal
    first = Page(doc, "Appendix: coverage",
                 "Every tile in this file, the ISO 32000-2 tables it exercises, and what a theme should do with it. "
                 "The table is generated from the same source as the pages.")
    doc.appendix_start = first.number - 1
    sans, bold = first.font("Sans"), first.font("SansBold")

    y = H - 110
    for chip, text in LEGEND:
        cw = bold.width(chip, 6) + 8
        first.artifact("%s %s f" % (pal.rg(chip), round_rect_path(MARGIN, y - 2, cw, 10, 5)))
        first.text(MARGIN + 4, y + 1, chip, size=6, font="SansBold", role="paper", tag="Span")
        first.text(MARGIN + cw + 6, y + 1, text, size=7.5)
        y -= 14
    y -= 6
    first.text(MARGIN, y, "Not included, and why", size=9, font="SansBold", tag="H2")
    y -= 14
    for name, why in EXCLUDED:
        first.text(MARGIN, y, name, size=7, font="SansBold")
        first.text(MARGIN + 190, y, why, size=7, role="muted")
        y -= 11
    y -= 10

    rows = [c for c in doc.coverage if c["ref"]]
    cols = [("Page", 30), ("Object", 220), ("ISO 32000-2 tables", 170), ("Theme", 50)]
    page = first
    row_h = 10.5

    def header(pg, yy):
        x = MARGIN
        pg.begin("TR")
        for name, cw in cols:
            pg.artifact("%s %s f" % (pal.rg("accent"), rect_path(x, yy - 3, cw, row_h)))
            pg.tagged("TH", pg.text_op(x + 3, yy, name, 6.5, bold, "paper"),
                      attrs=Dictionary(O=Name.Table, Scope=Name.Column))
            x += cw
        pg.end()
        return yy - row_h

    page.begin("Table")
    y = header(page, y)
    for i, r in enumerate(rows):
        if y < 50:
            page.end()
            page = Page(doc, "Appendix: coverage, continued", "")
            page.begin("Table")
            y = header(page, H - 90)
        x = MARGIN
        page.begin("TR")
        if i % 2:
            page.artifact("%s %s f" % (pal.rg("tile"), rect_path(MARGIN, y - 3, sum(c[1] for c in cols), row_h)))
        cells = [str(r["page"]), r["object"], r["ref"].replace("T", "").replace(" ", " "), r["expect"]]
        for (name, cw), val in zip(cols, cells):
            role = r["expect"] if name == "Theme" else "ink"
            f = bold if name == "Theme" else sans
            size = 6.5
            while f.width(val, size) > cw - 6 and size > 4.5:
                size -= 0.25
            page.tagged("TD", page.text_op(x + 3, y, val, size, f, role))
            x += cw
        page.end()
        y -= row_h
    page.end()
    return first
