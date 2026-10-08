"""Pages for transparency, form XObjects and optional content."""
from pikepdf import Array, Dictionary, Name, String

from .core import MARGIN, W, Page, circle_path, n, poly_path, rect_path, round_rect_path
from .palette import HUES, fmt

BLEND_MODES = ["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "ColorDodge", "ColorBurn",
               "HardLight", "SoftLight", "Difference", "Exclusion", "Hue", "Saturation", "Color", "Luminosity"]


def stripes(x, y, w, h, step=8):
    return " ".join(rect_path(x + i * step, y, step / 2, h) for i in range(int(w / step) + 1))


def wide(rects, i, j):
    """Merge tiles i..j of one row into one rectangle."""
    a, b = rects[i], rects[j]
    return (a[0], a[1], b[0] + b[2] - a[0], a[3])


def caption(p, x, y, s, size=5.2):
    p.text(x, y, s, size=size, role="muted", tag="Caption", align="center")


# -- 11. Transparency: opacity and blend modes -------------------------------------------------

def page_blending(doc, res):
    p = Page(doc, "Transparency: opacity and blend modes",
             "Constant opacity and all sixteen blend modes. Blending mixes the theme's colours, so a mode "
             "that reads well on light paper, such as Multiply, can vanish on dark paper.",
             Group=Dictionary(Type=Name.Group, S=Name.Transparency, CS=Name.DeviceRGB))
    pal = p.pal
    t = p.grid(3, 3, heights=[150, 300, 150])

    x, y, w, h = p.tile(t[0], "Fill opacity: ca", "T57, T136", "swaps")
    body = ["%s %s f" % (pal.rg("ink"), stripes(x, y, w, h))]
    for i, a in enumerate([0.25, 0.5, 0.75]):
        g = p.use("ExtGState", "GSca%d" % int(a * 100), res.gstate(ca=a))
        body.append("q %s gs %s %s f Q" % (g, pal.rg("accent"), round_rect_path(x + 4 + i * w / 3, y + 10, w / 3 - 8, h - 20, 4)))
    p.figure("\n".join(body), "Blue panels at 25, 50 and 75 percent opacity over stripes.")

    x, y, w, h = p.tile(t[1], "Stroke opacity: CA", "T57", "swaps")
    body = ["%s %s f" % (pal.rg("ink"), stripes(x, y, w, h))]
    for i, a in enumerate([0.25, 0.5, 0.75]):
        g = p.use("ExtGState", "GSCA%d" % int(a * 100), res.gstate(CA=a))
        body.append("q %s gs %s 9 w %s %s m %s %s l S Q" % (g, pal.RG("red"), n(x + 4), n(y + 14 + i * (h - 28) / 2),
                                                             n(x + w - 4), n(y + 14 + i * (h - 28) / 2)))
    p.figure("\n".join(body), "Red strokes at three opacities over stripes.")

    x, y, w, h = p.tile(t[2], "Alpha is shape: AIS", "T57", "swaps", note="Left AIS false, right AIS true")
    body = ["%s %s f" % (pal.rg("ink"), stripes(x, y, w, h))]
    for i, ais in enumerate([False, True]):
        g = p.use("ExtGState", "GSAIS%d" % i, res.gstate(AIS=ais, ca=0.5, CA=0.5))
        body.append("q %s gs %s %s f Q" % (g, pal.rg("green"), circle_path(x + w * (0.27 + 0.46 * i), y + h / 2, min(h, w) * 0.3)))
    p.figure("\n".join(body), "Two half-opaque green discs, one treating alpha as shape.")

    x, y, w, h = p.tile(wide(t, 3, 5), "All sixteen blend modes: BM", "T134, T135", "swaps",
                        note="A blue disc blended over a two-colour gradient, one mode per cell")
    sh = doc.pdf.make_indirect(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([0, 0, 1, 0]),
                                          Function=res.fn_exp("yellow", "pink")))
    cols, rows = 8, 2
    cw, ch = w / cols, h / rows
    body = []
    for k, mode in enumerate(BLEND_MODES):
        cx, cy = x + (k % cols) * cw, y + h - (k // cols + 1) * ch
        g = p.use("ExtGState", "GSBM%s" % mode, res.gstate(BM=Name("/" + mode)))
        p.use("Shading", "ShBM", sh)
        body.append("q %s W n q %s 0 0 %s %s %s cm /ShBM sh Q %s gs %s %s f Q" % (
            rect_path(cx + 2, cy + 12, cw - 4, ch - 16), n(cw - 4), n(ch - 16), n(cx + 2), n(cy + 12), g,
            pal.rg("accent"), circle_path(cx + cw / 2, cy + ch / 2 + 4, min(cw, ch) * 0.32)))
    p.figure("\n".join(body), "Sixteen cells, each blending a blue disc into a yellow to pink gradient with one blend mode.")
    for k, mode in enumerate(BLEND_MODES):
        caption(p, x + (k % cols + 0.5) * cw, y + h - (k // cols + 1) * ch + 4, mode)

    x, y, w, h = p.tile(t[6], "Highlighter: Multiply, or Screen in dark", "T134", "swaps",
                        note="Multiply hides a highlight on dark paper, so the dark build swaps in Screen")
    g = p.use("ExtGState", "GSHilite", res.gstate(BM=Name.Screen if pal.dark else Name.Multiply))
    f = p.font("Sans")
    p.tagged("P", "BT /Sans 10 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + 4), n(y + h / 2 - 3), f.enc("Highlighted words")))
    p.figure("%s gs %s %s f" % (g, pal.rg("hl"), rect_path(x + 2, y + h / 2 - 6, f.width("Highlighted words", 10) + 4, 14)),
             "A yellow highlight multiplied over text.")

    x, y, w, h = p.tile(t[7], "Screen and Lighten on paper", "T134", "swaps")
    body = []
    for i, mode in enumerate(["Screen", "Lighten"]):
        g = p.use("ExtGState", "GSBM%s" % mode, res.gstate(BM=Name("/" + mode)))
        body.append("q %s gs %s %s f Q" % (g, pal.rg("teal"), circle_path(x + w * (0.27 + 0.46 * i), y + h / 2, min(h, w) * 0.32)))
    p.figure("\n".join(body), "Teal discs in Screen and Lighten modes over the tile.")

    x, y, w, h = p.tile(t[8], "Difference and Exclusion on text", "T134", "swaps")
    body = []
    for i, mode in enumerate(["Difference", "Exclusion"]):
        g = p.use("ExtGState", "GSBM%s" % mode, res.gstate(BM=Name("/" + mode)))
        body.append("q BT /Sans 9 Tf %s %s %s Td %s Tj ET %s gs %s %s f Q" % (
            pal.rg("ink"), n(x + 4), n(y + h - 16 - i * 24), f.enc(mode + " over text"), g, pal.rg("orange"),
            rect_path(x + 2, y + h - 22 - i * 24, w * 0.6, 14)))
    p.figure("\n".join(body), "Orange bars in Difference and Exclusion modes over text.")
    return p


# -- 12. Transparency: groups and soft masks ---------------------------------------------------

def page_groups(doc, res):
    p = Page(doc, "Transparency: groups and soft masks",
             "Isolated and knockout groups, a group colour space, and soft masks. A luminosity mask is made of "
             "greys that mean opacity, not colour, so the theme must leave the mask alone and swap only what it masks.",
             Group=Dictionary(Type=Name.Group, S=Name.Transparency, CS=Name.DeviceRGB, I=True))
    pal = p.pal
    t = p.grid(3, 3, heights=[210, 170, 170])

    x, y, w, h = p.tile(wide(t, 0, 2), "Isolated and knockout groups: I and K", "T94, T145", "swaps",
                        note="Three translucent discs in a group over stripes; each cell changes I and K")
    cw = w / 4
    body = []
    half = p.use("ExtGState", "GSca60", res.gstate(ca=0.6))
    for k, (iso, ko) in enumerate([(False, False), (True, False), (False, True), (True, True)]):
        gx = x + k * cw
        discs = " ".join("%s %s f" % (pal.rg(c), circle_path(gx + cw / 2 + dx, y + h / 2 + 6 + dy, h * 0.24))
                         for c, dx, dy in [("red", -14, 8), ("green", 14, 8), ("blue", 0, -14)])
        form = doc.form("/GSca60 gs " + discs, [gx, y, gx + cw, y + h],
                        Dictionary(ExtGState=Dictionary(GSca60=res.gstate(ca=0.6))),
                        Group=Dictionary(Type=Name.Group, S=Name.Transparency, I=iso, K=ko))
        nm = p.use("XObject", "FmGrp%d" % k, form)
        body.append("q %s %s f %s Do Q" % (pal.rg("ink"), stripes(gx + 4, y + 14, cw - 8, h - 18, 6), nm))
    p.figure("\n".join(body), "Four groups of three overlapping discs showing isolated and knockout behaviour.")
    for k, lab in enumerate(["I false, K false", "I true, K false", "I false, K true", "I true, K true"]):
        caption(p, x + (k + 0.5) * cw, y + 4, lab)

    x, y, w, h = p.tile(t[3], "Group colour space: CS", "T145", "swaps", note="Multiply blended in RGB, then in CMYK")
    body = []
    for k, cs in enumerate([Name.DeviceRGB, Name.DeviceCMYK]):
        gx = x + k * w / 2
        mul = res.gstate(BM=Name.Multiply)
        inner = "%s %s f /GSm gs %s %s f" % (pal.rg("yellow"), rect_path(gx + 6, y + 10, w / 2 - 26, h - 30),
                                             pal.rg("accent"), rect_path(gx + 20, y + 20, w / 2 - 26, h - 30))
        form = doc.form(inner, [gx, y, gx + w / 2, y + h], Dictionary(ExtGState=Dictionary(GSm=mul)),
                        Group=Dictionary(Type=Name.Group, S=Name.Transparency, CS=cs, I=True))
        body.append("%s Do" % p.use("XObject", "FmCS%d" % k, form))
    p.figure("\n".join(body), "Two pairs of overlapping squares multiplied in RGB and CMYK blending spaces.")

    # Luminosity soft mask: the mask's greys are the same in both builds.
    x, y, w, h = p.tile(t[4], "Luminosity soft mask with BC", "T142", "swaps",
                        note="Mask greys stay; the masked colour swaps; BC black outside the group")
    msh = doc.pdf.make_indirect(Dictionary(ShadingType=3, ColorSpace=Name.DeviceGray,
                                           Coords=Array([x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, min(w, h) / 2]),
                                           Function=Dictionary(FunctionType=2, Domain=Array([0, 1]), C0=Array([1]),
                                                               C1=Array([0]), N=1)))
    mform = doc.form("/ShM sh", [x, y, x + w, y + h], Dictionary(Shading=Dictionary(ShM=msh)),
                     Group=Dictionary(Type=Name.Group, S=Name.Transparency, CS=Name.DeviceGray))
    sm = res.gstate(SMask=Dictionary(Type=Name.Mask, S=Name.Luminosity, G=mform, BC=Array([0])))
    nm = p.use("ExtGState", "GSLum", sm)
    p.figure("%s %s f q %s gs %s %s f Q" % (pal.rg("ink"), stripes(x, y, w, h), nm, pal.rg("accent"), rect_path(x, y, w, h)),
             "A blue panel fading out from its centre through a luminosity mask.")

    x, y, w, h = p.tile(t[5], "Alpha soft mask", "T142", "swaps", note="Mask from a group's opacity")
    aform = doc.form("/GSa gs 0 g %s f" % circle_path(x + w / 2, y + h / 2, min(w, h) * 0.35), [x + 10, y, x + w - 10, y + h],
                     Dictionary(ExtGState=Dictionary(GSa=res.gstate(ca=0.7))),
                     Group=Dictionary(Type=Name.Group, S=Name.Transparency))
    am = p.use("ExtGState", "GSAlpha", res.gstate(SMask=Dictionary(Type=Name.Mask, S=Name.Alpha, G=aform)))
    p.figure("%s %s f q %s gs %s %s f Q" % (pal.rg("ink"), stripes(x, y, w, h), am, pal.rg("purple"), rect_path(x, y, w, h)),
             "A purple disc cut out by an alpha soft mask, at 70 percent opacity.")

    x, y, w, h = p.tile(t[6], "Soft mask with a transfer function", "T142", "swaps", note="TR inverts the mask")
    tr = doc.stream(b"{ 1 exch sub }", FunctionType=4, Domain=Array([0, 1]), Range=Array([0, 1]))
    msh2 = msh.copy()
    msh2.Coords = Array([x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, min(w, h) / 2])
    mform2 = doc.form("/ShM sh", [x, y, x + w, y + h], Dictionary(Shading=Dictionary(ShM=doc.pdf.make_indirect(msh2))),
                      Group=Dictionary(Type=Name.Group, S=Name.Transparency, CS=Name.DeviceGray))
    nm = p.use("ExtGState", "GSLumTR", res.gstate(SMask=Dictionary(Type=Name.Mask, S=Name.Luminosity, G=mform2,
                                                                   BC=Array([0]), TR=tr)))
    p.figure("%s %s f q %s gs %s %s f Q" % (pal.rg("ink"), stripes(x, y, w, h), nm, pal.rg("teal"), rect_path(x, y, w, h)),
             "A teal panel, transparent in the middle and solid at the edges.")

    x, y, w, h = p.tile(t[7], "SMask None resets the mask", "T57", "swaps")
    off = p.use("ExtGState", "GSNoMask", res.gstate(SMask=Name("/None")))
    lum = p.use("ExtGState", "GSLum", sm)
    p.figure("%s %s f q %s gs %s gs %s %s f Q" % (pal.rg("ink"), stripes(x, y, w, h), lum, off, pal.rg("orange"),
                                                  rect_path(x + 10, y + 10, w - 20, h - 20)),
             "An orange panel drawn after the mask is switched off, so it is solid.")

    x, y, w, h = p.tile(t[8], "Transparency group reused", "T94", "swaps", note="One group form drawn three times")
    discs = " ".join("%s %s f" % (pal.rg(c), circle_path(16 + dx, 16 + dy, 11)) for c, dx, dy in [("pink", -6, 4), ("yellow", 6, 4), ("teal", 0, -6)])
    gform = doc.form("/GSca60 gs " + discs, [0, 0, 32, 32], Dictionary(ExtGState=Dictionary(GSca60=res.gstate(ca=0.6))),
                     Group=Dictionary(Type=Name.Group, S=Name.Transparency, I=True))
    nm = p.use("XObject", "FmReuse", gform)
    p.figure(" ".join("q %s 0 0 %s %s %s cm %s Do Q" % (n(s), n(s), n(x + 4 + i * w / 3), n(y + (h - 32 * s) / 2), nm)
                      for i, s in enumerate([1.2, 1.5, 1.8])), "One group of translucent discs at three sizes.")
    return p


# -- 13. Form XObjects --------------------------------------------------------------------------

def page_forms(doc, res):
    p = Page(doc, "Form XObjects",
             "Reusable drawings: placed many times, nested, clipped by their BBox, and drawn in the colour of the "
             "page that calls them. A theme that swaps a form must swap it everywhere it is used.")
    pal = p.pal
    t = p.grid(3, 3)

    icon = doc.form("%s %s f %s %s f" % (pal.rg("accent"), round_rect_path(0, 0, 40, 40, 8), pal.rg("paper"),
                                          poly_path([(12, 10), (32, 20), (12, 30)], close=True)), [0, 0, 40, 40],
                    Dictionary())
    x, y, w, h = p.tile(t[0], "One form, placed four times", "T93, T86", "swaps")
    nm = p.use("XObject", "FmIcon", icon)
    p.figure(" ".join("q %s 0 0 %s %s %s cm %s Do Q" % (n(s), n(s), n(x + 4 + i * w / 4), n(y + h / 2 - 20 * s), nm)
                      for i, s in enumerate([0.6, 0.8, 1.0, 0.7])), "A play-button icon drawn four times.")

    x, y, w, h = p.tile(t[1], "Nested forms, three deep", "T93", "swaps")
    lvl3 = doc.form("%s %s f" % (pal.rg("yellow"), circle_path(10, 10, 8)), [0, 0, 20, 20], Dictionary())
    lvl2 = doc.form("%s %s f q 1 0 0 1 10 10 cm /L3 Do Q" % (pal.rg("green"), rect_path(0, 0, 40, 40)), [0, 0, 40, 40],
                    Dictionary(XObject=Dictionary(L3=lvl3)))
    lvl1 = doc.form("%s %s f q 1 0 0 1 10 10 cm /L2 Do Q" % (pal.rg("purple"), rect_path(0, 0, 60, 60)), [0, 0, 60, 60],
                    Dictionary(XObject=Dictionary(L2=lvl2)))
    nm = p.use("XObject", "FmNest", lvl1)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + w / 2 - 30), n(y + h / 2 - 30), nm), "Three squares nested inside each other.")

    x, y, w, h = p.tile(t[2], "Form drawn in the caller's colour", "T93", "swaps", note="No colour inside the form")
    glyph = doc.form(star := "%s f" % poly_path([(20, 38), (25, 25), (38, 25), (28, 16), (32, 2), (20, 10), (8, 2), (12, 16), (2, 25), (15, 25)], close=True),
                     [0, 0, 40, 40], Dictionary())
    nm = p.use("XObject", "FmStar", glyph)
    p.figure(" ".join("q %s 1 0 0 1 %s %s cm %s Do Q" % (pal.rg(c), n(x + 4 + i * w / 3), n(y + h / 2 - 20), nm)
                      for i, c in enumerate(["red", "teal", "ink"])), "One star form filled in three colours set by the page.")

    x, y, w, h = p.tile(t[3], "BBox clips and Matrix maps", "T93", "swaps", note="The circle is cut by the form's BBox")
    clipped = doc.form("%s %s f" % (pal.rg("orange"), circle_path(20, 20, 26)), [0, 0, 40, 40], Dictionary(),
                       Matrix=Array([1, 0.3, 0, 1, 0, 0]))
    nm = p.use("XObject", "FmClip", clipped)
    p.figure("q 1.6 0 0 1.6 %s %s cm %s Do Q" % (n(x + w / 2 - 32), n(y + h / 2 - 40), nm),
             "An orange circle clipped to a sheared square.")

    x, y, w, h = p.tile(t[4], "Form with Measure and PtData (PDF 2.0)", "T93, T266, T272", "swaps",
                        note="A scaled drawing: 1 pt in the form is 1 cm")
    f = p.font("SansBold")
    plan = doc.form("%s 1.5 w %s S %s %s f BT /SansBold 8 Tf %s 6 6 Td %s Tj ET" % (
        pal.RG("ink"), rect_path(2, 2, 116, 56), pal.rg("blue"), rect_path(70, 30, 40, 22), pal.rg("ink"),
        f.enc("Floor plan")), [0, 0, 120, 60], Dictionary(Font=Dictionary(SansBold=f.obj)),
        Measure=Dictionary(Type=Name.Measure, Subtype=Name.RL, R=String("1 pt = 1 cm"),
                           X=Array([Dictionary(Type=Name.NumberFormat, U=String("cm"), C=1, D=10)]),
                           D=Array([Dictionary(Type=Name.NumberFormat, U=String("cm"), C=1, D=10)]),
                           A=Array([Dictionary(Type=Name.NumberFormat, U=String("sq cm"), C=1, D=10)])),
        PtData=Dictionary(Type=Name.PtData, Subtype=Name.Cloud, Names=Array([Name.LAT, Name.LON]),
                          XPTS=Array([Array([51.45, -2.58])])))
    nm = p.use("XObject", "FmPlan", plan)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + (w - 120) / 2), n(y + h / 2 - 30), nm), "A small floor plan drawn to scale.")

    x, y, w, h = p.tile(t[5], "Reference XObject (Ref)", "T93, T95", "swaps", note="Viewers draw the proxy content")
    target = doc.embed_file("reference-target.pdf", tiny_pdf(), "application/pdf", "Page imported by reference")
    ref = doc.form("%s %s f %s 2 w %s S BT /SansBold 9 Tf %s 8 30 Td %s Tj ET" % (
        pal.rg("tile"), rect_path(0, 0, 120, 60), pal.RG("accent"), rect_path(1, 1, 118, 58), pal.rg("accent"),
        f.enc("Proxy for Ref")), [0, 0, 120, 60], Dictionary(Font=Dictionary(SansBold=f.obj)),
                   Ref=Dictionary(F=target, Page=0))
    nm = p.use("XObject", "FmRef", ref)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + (w - 120) / 2), n(y + h / 2 - 30), nm), "A box labelled Proxy for Ref.")

    x, y, w, h = p.tile(t[6], "Form in a tiling pattern cell", "T74, T93", "swaps")
    pat = doc.stream("q 0.3 0 0 0.3 0 0 cm /FmIcon Do Q", Type=Name.Pattern, PatternType=1, PaintType=1, TilingType=1,
                     BBox=Array([0, 0, 14, 14]), XStep=14, YStep=14, Resources=Dictionary(XObject=Dictionary(FmIcon=icon)))
    p.use("Pattern", "PIcon", pat)
    p.figure("/Pattern cs /PIcon scn %s f" % round_rect_path(x, y, w, h, 4), "A wallpaper of small icons.")

    x, y, w, h = p.tile(t[7], "Form with its own Group and Matrix", "T93, T94", "swaps")
    gform = doc.form("/GS5 gs %s %s f %s %s f" % (pal.rg("red"), circle_path(16, 20, 14), pal.rg("blue"), circle_path(30, 20, 14)),
                     [0, 0, 46, 40], Dictionary(ExtGState=Dictionary(GS5=res.gstate(ca=0.5))),
                     Group=Dictionary(Type=Name.Group, S=Name.Transparency, I=True, K=True),
                     Matrix=Array([2, 0, 0, 2, 0, 0]))
    nm = p.use("XObject", "FmGM", gform)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + w / 2 - 46), n(y + h / 2 - 40), nm),
             "Two translucent discs in a knockout group, scaled by the form matrix.")

    x, y, w, h = p.tile(t[8], "Image inside a form, reused", "T93, T87", "stays")
    from .images import photo
    im = photo(80, 54)
    img = doc.stream(im.tobytes(), Type=Name.XObject, Subtype=Name.Image, Width=80, Height=54,
                     ColorSpace=Name.DeviceRGB, BitsPerComponent=8)
    pf = doc.form("q 40 0 0 27 0 0 cm /Im Do Q", [0, 0, 40, 27], Dictionary(XObject=Dictionary(Im=img)))
    nm = p.use("XObject", "FmPhoto", pf)
    p.figure(" ".join("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + 4 + i * 46), n(y + h / 2 - 13 + (i % 2) * 8), nm)
                      for i in range(3)), "One photo form placed three times.")
    return p


def tiny_pdf():
    import io
    import pikepdf
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(120, 60))
    page.obj.Contents = pdf.make_stream(b"0.2 0.4 0.8 rg 10 10 100 40 re f")
    buf = io.BytesIO()
    pdf.save(buf, deterministic_id=True)
    return buf.getvalue()


# -- 14. Optional content ------------------------------------------------------------------------

def page_layers(doc, res):
    p = Page(doc, "Optional content (layers)",
             "Layers that are on, off, view-only, print-only, zoom-dependent, language-dependent, locked and in "
             "radio groups, plus a visibility expression. Click the labels to toggle layers in viewers that support "
             "SetOCGState. Content in a layer swaps like any other content.")
    pal = p.pal
    t = p.grid(3, 3)

    def ocg(name, **usage):
        if name in doc.ocgs:
            return doc.ocgs[name]
        d = Dictionary(Type=Name.OCG, Name=String(name), Intent=Name.View)
        if usage:
            d.Usage = Dictionary(**usage)
        o = doc.pdf.make_indirect(d)
        doc.ocgs[name] = o
        return o

    on = ocg("Shown by default")
    off = ocg("Hidden by default")
    view = ocg("Screen only", View=Dictionary(ViewState=Name.ON), Print=Dictionary(PrintState=Name.OFF, Subtype=Name.Print))
    prn = ocg("Print only", View=Dictionary(ViewState=Name.OFF), Print=Dictionary(PrintState=Name.ON, Subtype=Name.Print))
    zoom = ocg("Zoom 150% and up", Zoom=Dictionary(min=1.5))
    en = ocg("English", Language=Dictionary(Lang=String("en-GB"), Preferred=Name.ON))
    fr = ocg("Français", Language=Dictionary(Lang=String("fr-FR")))
    ra, rb, rc = ocg("Radio A"), ocg("Radio B"), ocg("Radio C")
    locked = ocg("Locked on")
    expr = doc.pdf.make_indirect(Dictionary(Type=Name.OCMD, OCGs=Array([on, off]),
                                            VE=Array([Name.And, on, Array([Name.Not, off])])))
    anyoff = doc.pdf.make_indirect(Dictionary(Type=Name.OCMD, OCGs=Array([ra, rb]), P=Name.AnyOff))
    doc.oc_config = dict(on=[on, view, en, ra, locked], off=[off, prn, zoom, fr, rb, rc],
                         order=[Array([String("Test layers"), on, off, view, prn, zoom]),
                                Array([String("Language"), en, fr]), Array([String("Radio group"), ra, rb, rc]), locked],
                         rbgroups=[[ra, rb, rc]], locked=[locked],
                         auto=[(Name.View, [view, prn], [Name.View]), (Name.Print, [view, prn], [Name.Print]),
                               (Name.View, [zoom], [Name.Zoom]), (Name.View, [en, fr], [Name.Language])])

    f = p.font("SansBold")

    def layer_tile(i, title, ref, layer, role, label, note=None):
        x, y, w, h = p.tile(t[i], title, ref, "swaps", note=note)
        key = "OC%d" % i
        p.use("Properties", key, layer)
        p.figure("/OC /%s BDC %s %s BT /SansBold 12 Tf %s %s %s Td %s Tj ET EMC" % (
            key, pal.rg(role), round_rect_path(x + 4, y + h / 2 - 16, w - 8, 32, 6) + " f", pal.rg("paper"),
            n(x + 12), n(y + h / 2 - 4), f.enc(label)), "A coloured panel in the layer " + label + ".")
        return x, y, w, h

    toggles = []
    for i, (title, ref, layer, role, label, note) in enumerate([
            ("Default on", "T96, T99", on, "accent", "Shown by default", None),
            ("Default off", "T96, T99", off, "red", "Hidden by default", "Off until toggled"),
            ("View and print usage", "T100, T101", view, "green", "Screen only", "AS sets it from Usage"),
            ("Print-only layer", "T100, T101", prn, "purple", "Print only", "Hidden on screen"),
            ("Zoom-dependent layer", "T100", zoom, "orange", "Zoom 150%+", "Shown at 150% zoom and above"),
            ("Language layers", "T100", en, "teal", "English", None)]):
        x, y, w, h = layer_tile(i, title, ref, layer, role, label, note)
        toggles.append((x, y, w, h, layer))
    # French alternative drawn in the same tile as English, underneath.
    x, y, w, h = toggles[5][:4]
    p.use("Properties", "OCfr", fr)
    p.figure("/OC /OCfr BDC %s %s f BT /SansBold 12 Tf %s %s %s Td %s Tj ET EMC" % (
        pal.rg("teal"), round_rect_path(x + 4, y + 2, w - 8, 26, 6), pal.rg("paper"), n(x + 12), n(y + 11), f.enc("Français")),
             "A panel in the French language layer.")

    x, y, w, h = p.tile(t[6], "Radio-button layers: RBGroups", "T99", "swaps", note="Only one of A, B, C at a time")
    body = []
    for k, (lay, role) in enumerate([(ra, "red"), (rb, "green"), (rc, "blue")]):
        key = "OCr%d" % k
        p.use("Properties", key, lay)
        body.append("/OC /%s BDC %s %s f BT /SansBold 16 Tf %s %s %s Td %s Tj ET EMC" % (
            key, pal.rg(role), circle_path(x + w / 2, y + h / 2, min(w, h) * 0.35), pal.rg("paper"),
            n(x + w / 2 - 5), n(y + h / 2 - 6), f.enc("ABC"[k])))
    p.figure("\n".join(body), "Three discs, A, B and C, of which one shows.")
    toggles.append((x, y, w, h, None))

    x, y, w, h = p.tile(t[7], "Visibility expression: OCMD VE", "T97", "swaps", note="Shown when on AND NOT off")
    p.use("Properties", "OCexpr", expr)
    p.use("Properties", "OCany", anyoff)
    p.figure("/OC /OCexpr BDC %s %s f EMC /OC /OCany BDC %s 3 w %s S EMC" % (
        pal.rg("pink"), round_rect_path(x + 8, y + 8, w - 16, h - 16, 8), pal.RG("ink"),
        round_rect_path(x + 4, y + 4, w - 8, h - 8, 10)),
             "A pink panel shown by a visibility expression, outlined when any radio layer is off.")

    x, y, w, h = p.tile(t[8], "Locked layer, layered annotation and form", "T99, T166, T93", "swaps",
                        note="The square annotation and the form both carry OC")
    p.use("Properties", "OClock", locked)
    p.figure("/OC /OClock BDC %s %s f EMC" % (pal.rg("yellow"), round_rect_path(x + 4, y + h / 2, w / 2 - 8, h / 2 - 4, 6)),
             "A yellow panel in a locked layer.")
    lf = doc.form("%s %s f" % (pal.rg("green"), circle_path(16, 16, 14)), [0, 0, 32, 32], Dictionary(), OC=on)
    nm = p.use("XObject", "FmOC", lf)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + w * 0.6), n(y + h / 2 + 4), nm), "A green disc form in the default-on layer.")
    sq = (x + 8, y + 6, x + w / 2, y + h / 2 - 6)
    ap = doc.form("%s %s 2 w %s B" % (pal.rg("tile"), pal.RG("red"), rect_path(1, 1, sq[2] - sq[0] - 2, sq[3] - sq[1] - 2)),
                  [0, 0, sq[2] - sq[0], sq[3] - sq[1]], Dictionary())
    p.annot(Dictionary(Type=Name.Annot, Subtype=Name.Square, Rect=Array(list(sq)), F=4, OC=off,
                       C=doc.rgb("red"), IC=doc.rgb("tile"), BS=Dictionary(W=2), Contents=String("Square annotation in the hidden-by-default layer"),
                       AP=Dictionary(N=ap)), tag="Annot", alt="Square annotation in a layer")

    # Toggle links on each tile's title area
    for x, y, w, h, layer in toggles:
        if layer is None:
            state = Array([Name.ON, ra, Name.OFF, rb, rc])
        else:
            state = Array([Name.Toggle, layer])
        p.annot(Dictionary(Type=Name.Annot, Subtype=Name.Link, Rect=Array([x, y, x + w, y + h]), Border=Array([0, 0, 0]),
                           Contents=String("Toggle layer"), A=Dictionary(S=Name.SetOCGState, State=state, PreserveRB=True)),
                tag="Link", alt="Toggle this layer")
    return p
