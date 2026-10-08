"""Pages for paths, colour spaces, shadings, patterns, fonts and text effects."""
import math
import struct

from pikepdf import Array, Dictionary, Name, String

from .core import MARGIN, H, W, Page, circle_path, n, poly_path, rect_path, round_rect_path, star_path
from .palette import HUES, fmt


def pentagram(cx, cy, r):
    pts = [(cx + r * math.cos(math.radians(90 + k * 144)), cy + r * math.sin(math.radians(90 + k * 144)))
           for k in range(5)]
    return poly_path(pts, close=True)


def caption(p, x, y, s, size=5.5, align="center"):
    p.text(x, y, s, size=size, role="muted", tag="Caption", align=align)


def swatches(p, inner, fills, strokes=None, labels=None, size=None):
    x, y, w, h = inner
    k = len(fills)
    gap = 4
    s = size or min((w - gap * (k - 1)) / k, h - (9 if labels else 0))
    total = k * s + gap * (k - 1)
    x0 = x + (w - total) / 2
    y0 = y + (h - s) / 2 + (4 if labels else 0)
    body = []
    for i, f in enumerate(fills):
        bx = x0 + i * (s + gap)
        body.append("%s %s f" % (f, round_rect_path(bx, y0, s, s, 2.5)))
        if strokes:
            body.append("1.6 w %s %s S" % (strokes[i], round_rect_path(bx + 3, y0 + 3, s - 6, s - 6, 2)))
    return body, [(x0 + i * (s + gap) + s / 2, y0 - 7) for i in range(k)]


def draw_swatches(p, inner, fills, strokes, alt, labels=None):
    body, pos = swatches(p, inner, fills, strokes, labels)
    p.figure("\n".join(body), alt)
    if labels:
        for (cx, cy), lab in zip(pos, labels):
            caption(p, cx, cy, lab, size=4.8)


# -- 2. Paths and painting -----------------------------------------------------------------

def page_paths(doc, res):
    p = Page(doc, "Paths and painting",
             "Every way to build and paint a path. The theme changes only the paint, so every shape "
             "should keep its geometry and take the dark design's colours.")
    t = p.grid(3, 4)
    ink, acc = p.fill("ink"), p.fill("accent")

    x, y, w, h = p.tile(t[0], "Fill rules: f and f*", "T59", "swaps")
    cy = y + h / 2
    rr = min(h * 0.46, w * 0.22)
    p.figure("%s %s f %s %s f*" % (acc, pentagram(x + w * 0.27, cy, rr),
                                   p.fill("green"), pentagram(x + w * 0.73, cy, rr)),
             "Two pentagrams: nonzero fill is solid, even-odd fill leaves the centre empty.")
    caption(p, x + w * 0.27, y - 2, "f nonzero")
    caption(p, x + w * 0.73, y - 2, "f* even-odd")

    x, y, w, h = p.tile(t[1], "Line widths", "T56, T51", "swaps")
    body = [p.stroke("ink")]
    for i, lw in enumerate([0, 0.25, 0.5, 1, 2, 4, 7]):
        yy = y + h - 4 - i * (h - 8) / 6
        body.append("%s w %s %s m %s %s l S" % (n(lw), n(x + 26), n(yy), n(x + w - 4), n(yy)))
    p.figure("\n".join(body), "Seven horizontal lines from width 0 (thinnest) to 7 points.")
    for i, lw in enumerate([0, 0.25, 0.5, 1, 2, 4, 7]):
        caption(p, x + 2, y + h - 6 - i * (h - 8) / 6, "%g" % lw, align="left")

    x, y, w, h = p.tile(t[2], "Line caps: J 0, 1, 2", "T53", "swaps")
    body = []
    for i in range(3):
        yy = y + h - 12 - i * (h - 18) / 2
        body.append("%s 9 w %d J %s %s m %s %s l S" % (p.stroke("accent"), i, n(x + 24), n(yy), n(x + w - 24), n(yy)))
    body.append("%s 0.5 w 0 J %s %s m %s %s l %s %s m %s %s l S" % (
        p.stroke("ink"), n(x + 24), n(y), n(x + 24), n(y + h), n(x + w - 24), n(y), n(x + w - 24), n(y + h)))
    p.figure("\n".join(body), "Butt, round and square line caps against guide lines.")

    x, y, w, h = p.tile(t[3], "Line joins and miter limit", "T54, T56", "swaps")
    body = []
    for i, (j, ml) in enumerate([(0, 10), (1, 10), (2, 10), (0, 1.2)]):
        bx = x + 4 + i * (w - 8) / 4
        pts = [(bx + 2, y + 10), (bx + (w - 8) / 8, y + h - 10), (bx + (w - 8) / 4 - 6, y + 10)]
        body.append("%s 7 w %d j %s M %s S" % (p.stroke("purple"), j, n(ml), poly_path(pts)))
    p.figure("\n".join(body), "Miter, round and bevel joins, and a miter join cut off by a low miter limit.")
    for i, lab in enumerate(["j 0", "j 1", "j 2", "M 1.2"]):
        caption(p, x + 4 + (i + 0.5) * (w - 8) / 4, y - 2, lab)

    x, y, w, h = p.tile(t[4], "Dash patterns", "T55, T56", "swaps")
    body = [p.stroke("ink"), "1.5 w"]
    pats = ["[] 0", "[6 3] 0", "[2 2] 1", "[8 3 1 3] 0", "[0 4] 0"]
    for i, d in enumerate(pats):
        yy = y + h - 6 - i * (h - 10) / 4
        cap = "1 J 2.5 w" if d == "[0 4] 0" else "0 J 1.5 w"
        body.append("%s %s d %s %s m %s %s l S" % (cap, d, n(x + 40), n(yy), n(x + w - 4), n(yy)))
    p.figure("\n".join(body), "Solid, dashed, dotted and dash-dot lines.")
    for i, d in enumerate(pats):
        caption(p, x + 2, y + h - 8 - i * (h - 10) / 4, d, align="left", size=5)

    x, y, w, h = p.tile(t[5], "Curves: c, v and y", "T58", "swaps")
    body = ["%s 1.6 w" % p.stroke("teal")]
    guides = ["%s 0.4 w" % p.stroke("rule")]
    for i, op in enumerate(["c", "v", "y"]):
        bx = x + i * w / 3
        x0_, x3 = bx + 6, bx + w / 3 - 6
        c1, c2 = (bx + 10, y + h - 4), (bx + w / 3 - 10, y + h - 4)
        if op == "c":
            seg = "%s %s m %s %s %s %s %s %s c" % (n(x0_), n(y + 8), n(c1[0]), n(c1[1]), n(c2[0]), n(c2[1]), n(x3), n(y + 8))
        elif op == "v":
            seg = "%s %s m %s %s %s %s v" % (n(x0_), n(y + 8), n(c2[0]), n(c2[1]), n(x3), n(y + 8))
        else:
            seg = "%s %s m %s %s %s %s y" % (n(x0_), n(y + 8), n(c1[0]), n(c1[1]), n(x3), n(y + 8))
        body.append(seg + " S")
        guides.append("%s %s m %s %s l %s %s m %s %s l S" % (n(x0_), n(y + 8), n(c1[0]), n(c1[1]), n(x3), n(y + 8), n(c2[0]), n(c2[1])))
    p.figure("\n".join(guides + body), "Bezier curves drawn with the c, v and y operators and their control lines.")

    x, y, w, h = p.tile(t[6], "Fill and stroke: B, B*, b, b*, s", "T59", "swaps")
    body = ["2 w %s %s" % (p.fill("yellow"), p.stroke("ink"))]
    ops = ["B", "B*", "b", "b*", "s"]
    for i, op in enumerate(ops):
        bx = x + i * w / 5 + 3
        bw = w / 5 - 6
        if op in ("B*", "b*"):
            path = pentagram(bx + bw / 2, y + h / 2, bw / 2)
            if op == "b*":
                path = path[:-2]  # leave it open, b* closes it
        else:
            pts = [(bx, y + 8), (bx + bw / 2, y + h - 6), (bx + bw, y + 8)]
            path = poly_path(pts, close=(op == "B"))
        body.append("%s %s" % (path, op))
    p.figure("\n".join(body), "Shapes filled and stroked with each combined painting operator.")
    for i, op in enumerate(ops):
        caption(p, x + (i + 0.5) * w / 5, y - 2, op)

    x, y, w, h = p.tile(t[7], "Clipping: W and W*", "T60", "swaps")
    stripes = " ".join("%s %s %s %s re" % (n(x + i * 6), n(y), 3, n(h)) for i in range(int(w / 6) + 1))
    rr = min(h * 0.46, w * 0.23)
    p.figure("q %s W n %s %s f Q q %s %s W* n %s %s f Q" % (
        circle_path(x + w * 0.27, y + h / 2, rr), p.fill("orange"), stripes,
        circle_path(x + w * 0.73, y + h / 2, rr), circle_path(x + w * 0.73, y + h / 2, rr * 0.48),
        p.fill("blue"), stripes), "Stripes clipped to a disc, and to a ring with the even-odd clip.")

    x, y, w, h = p.tile(t[8], "Rectangles, hairlines and dots", "T58, T51", "swaps")
    p.figure("%s %s F %s 0 w %s %s m %s %s l S 1 J 6 w %s %s m %s %s l S" % (
        p.fill("green"), rect_path(x + 4, y + 8, w * 0.4, h - 16), p.stroke("ink"),
        n(x + w * 0.5), n(y + 8), n(x + w - 6), n(y + h - 8), n(x + w * 0.75), n(y + 14), n(x + w * 0.75), n(y + 14)),
             "A filled rectangle, a zero-width hairline and a zero-length line with round caps, which draws a dot.")

    x, y, w, h = p.tile(t[9], "Graphics state: q, Q, cm and gs", "T56, T57", "swaps")
    body = []
    sq = rect_path(-10, -10, 20, 20)
    for i, (a, s) in enumerate([(0, 1), (20, 1.1), (45, 0.8), (70, 1.3)]):
        cx, cy = x + 18 + i * (w - 36) / 3, y + h / 2
        ca, sa = math.cos(math.radians(a)) * s, math.sin(math.radians(a)) * s
        body.append("q %s %s %s %s %s %s cm %s %s f Q" % (n(ca), n(sa), n(-sa), n(ca), n(cx), n(cy),
                                                          p.fill(HUES[i * 2]), sq))
    gsall = p.use("ExtGState", "GSLine", res.gstate(LW=3, LC=1, LJ=1, ML=4, D=Array([Array([5, 3]), 0]),
                                                    RI=Name.Perceptual, Font=Array([doc.fonts.get("Sans").obj, 7])))
    body.append("q %s gs %s %s %s m %s %s l S BT %s %s %s Td %s Tj ET Q" % (
        gsall, p.stroke("ink"), n(x + 6), n(y + 8), n(x + w - 6), n(y + 8), p.fill("muted"), n(x + 6), n(y + 14),
        doc.fonts.get("Sans").enc("LW, LC, LJ, ML, D, RI and Font from one ExtGState")))
    p.figure("\n".join(body), "One square drawn four times under different rotations and scales.")

    x, y, w, h = p.tile(t[10], "Stroke adjustment and flatness", "T57", "viewer",
                        note="SA and flatness are rendering hints")
    sa_on = p.use("ExtGState", "GSSAon", res.gstate(SA=True, FL=0.2))
    sa_off = p.use("ExtGState", "GSSAoff", res.gstate(SA=False, FL=20))
    body = [p.stroke("ink"), "0.3 w"]
    for i in range(6):
        body.append("q %s gs %s %s m %s %s l S Q" % (sa_on, n(x + 6 + i * 4.3), n(y + 4), n(x + 6 + i * 4.3), n(y + h - 4)))
        body.append("q %s gs %s %s m %s %s l S Q" % (sa_off, n(x + w / 2 + 6 + i * 4.3), n(y + 4), n(x + w / 2 + 6 + i * 4.3), n(y + h - 4)))
    body.append("q %s gs 20 i %s 1 w %s S Q" % (sa_off, p.stroke("accent"), circle_path(x + w - 20, y + h / 2, h / 2 - 4)))
    p.figure("\n".join(body), "Hairlines with stroke adjustment on and off, and a circle with coarse flatness.")

    x, y, w, h = p.tile(t[11], "Strokes under a scaled CTM", "T56", "swaps")
    p.figure("q %s 0 0 %s %s %s cm %s 4 w %s S Q" % (
        n(w / 40), n(h / 40 * 0.5), n(x + w / 2), n(y + h / 2), p.stroke("pink"), circle_path(0, 0, 18)),
             "A circle stroked after a non-uniform scale, so its line is thicker at the sides.")
    return p


# -- 3. Colour spaces -------------------------------------------------------------------------

def page_colour(doc, res):
    p = Page(doc, "Colour spaces",
             "All eleven colour space families, fill and stroke. Each swatch is a fill with a stroked "
             "inner square. The dark build gives each space its own dark values.")
    pal = p.pal
    t = p.grid(3, 5)
    hues = ["red", "orange", "green", "blue", "purple"]

    x, y, w, h = inner = p.tile(t[0], "DeviceGray: g, G", "T61, T73", "swaps")
    roles = ["ink", "muted", "rule", "accent", "paper"]
    draw_swatches(p, inner, ["%s g" % fmt([pal.gray(r)]) for r in roles],
                  ["%s G" % fmt([pal.gray(r)]) for r in roles[::-1]], "Grey swatches.")

    inner = p.tile(t[1], "DeviceRGB: rg, RG", "T61, T73", "swaps")
    draw_swatches(p, inner, [pal.rg(r) for r in hues], [pal.RG("ink")] * 5, "RGB swatches.")

    inner = p.tile(t[2], "DeviceCMYK: k, K", "T61, T73", "swaps")
    draw_swatches(p, inner, ["%s k" % fmt(pal.cmyk(r)) for r in hues],
                  ["%s K" % fmt(pal.cmyk("paper"))] * 5, "CMYK swatches.")

    def named(cs, key, vals_fill, vals_stroke):
        nm = p.use("ColorSpace", key, cs)
        return (["%s cs %s sc" % (nm, fmt(v)) for v in vals_fill],
                ["%s CS %s SC" % (nm, fmt(v)) for v in vals_stroke])

    inner = p.tile(t[3], "CalGray", "T62", "swaps")
    f, s = named(res.calgray(), "CSCalGray", [[pal.gray(r)] for r in roles], [[pal.gray(r)] for r in roles[::-1]])
    draw_swatches(p, inner, f, s, "CalGray swatches.")

    inner = p.tile(t[4], "CalRGB", "T63", "swaps")
    f, s = named(res.calrgb(), "CSCalRGB", [pal.rgb(r) for r in hues], [pal.rgb("ink")] * 5)
    draw_swatches(p, inner, f, s, "CalRGB swatches.")

    inner = p.tile(t[5], "Lab", "T64", "swaps")
    f, s = named(res.lab(), "CSLab", [pal.lab(r) for r in hues], [pal.lab("ink")] * 5)
    draw_swatches(p, inner, f, s, "CIE Lab swatches.")

    inner = p.tile(t[6], "ICCBased: sRGB", "T65, T66", "swaps")
    f, s = named(res.icc("srgb"), "CSsRGB", [pal.rgb(r) for r in hues], [pal.rgb("ink")] * 5)
    draw_swatches(p, inner, f, s, "ICC sRGB swatches.")

    inner = p.tile(t[7], "ICCBased: Display P3", "T65, T67", "swaps")
    f, s = named(res.icc("p3"), "CSP3", [pal.p3(r) for r in hues], [pal.p3("ink")] * 5)
    draw_swatches(p, inner, f, s, "Display P3 swatches.")

    inner = p.tile(t[8], "ICCBased: CMYK (FOGRA39)", "T65, T68", "swaps")
    f, s = named(res.icc("cmyk"), "CSCMYKicc", [pal.cmyk(r) for r in hues], [pal.cmyk("ink")] * 5)
    draw_swatches(p, inner, f, s, "ICC CMYK swatches.")

    inner = p.tile(t[9], "Indexed over RGB, Lab and ICC", "T61", "swaps")
    nm1 = p.use("ColorSpace", "CSIdx", res.indexed("rgb"))
    nm2 = p.use("ColorSpace", "CSIdxLab", res.indexed("lab"))
    nm3 = p.use("ColorSpace", "CSIdxICC", res.indexed("icc"))
    fills = ["%s cs %d sc" % (nm, res.role_index(r)) for nm, r in
             [(nm1, "red"), (nm1, "green"), (nm2, "orange"), (nm2, "blue"), (nm3, "purple")]]
    draw_swatches(p, inner, fills, ["%s CS %d SC" % (nm1, res.role_index("ink"))] * 5,
                  "Indexed colour swatches.", labels=["RGB", "RGB", "Lab", "Lab", "ICC"])

    inner = p.tile(t[10], "Separation: spot, All, None", "T61", "swaps",
                   note="All = registration colour; None never marks")
    sep = p.use("ColorSpace", "CSSep", res.separation("teal"))
    sall = p.use("ColorSpace", "CSAll", res.separation("all"))
    snone = p.use("ColorSpace", "CSNone", res.separation("none"))
    fills = ["%s cs %s sc" % (sep, v) for v in ("0.25", "0.5", "1")] + ["%s cs 1 sc" % sall, "%s cs 1 sc" % snone]
    draw_swatches(p, inner, fills, ["%s CS 1 SC" % sep] * 5, "Spot colour tints, the All colourant and None.",
                  labels=["25%", "50%", "100%", "All", "None"])

    inner = p.tile(t[11], "DeviceN and NChannel", "T70, T71", "swaps")
    dn = p.use("ColorSpace", "CSDevN", res.devicen())
    nc = p.use("ColorSpace", "CSNCh", res.nchannel())
    fills = ["%s cs 1 0 sc" % dn, "%s cs 0 1 sc" % dn, "%s cs 0.6 0.6 sc" % dn,
             "%s cs 0.4 0 0.8 sc" % nc, "%s cs 0 0.5 1 sc" % nc]
    draw_swatches(p, inner, fills, ["%s CS 0.3 0.3 SC" % dn] * 5, "Two spot inks mixed, and an NChannel space.",
                  labels=["teal", "orange", "mix", "C+spot", "M+spot"])

    inner = p.tile(t[12], "Rendering intents: ri", "T69", "viewer", note="Intents change ICC conversion only")
    srgb = p.use("ColorSpace", "CSCMYKicc", res.icc("cmyk"))
    intents = ["AbsoluteColorimetric", "RelativeColorimetric", "Saturation", "Perceptual"]
    fills = ["/%s ri %s cs %s sc" % (it, srgb, fmt(pal.cmyk("blue"))) for it in intents]
    draw_swatches(p, inner, fills, None, "One CMYK colour under each rendering intent.",
                  labels=["Abs", "Rel", "Sat", "Perc"])

    x, y, w, h = p.tile(t[13], "Default colour spaces in a form", "T34, T61", "swaps",
                        note="DefaultCMYK, DefaultRGB and DefaultGray remap k, rg and g")
    body, _ = swatches(p, (0, 0, w, h), ["%s k" % fmt(pal.cmyk(r)) for r in hues[:2]] + [pal.rg("green")] +
                       ["%s g" % fmt([pal.gray(r)]) for r in ("ink", "muted")])
    form = doc.form("\n".join(body), [0, 0, w, h], Dictionary(ColorSpace=Dictionary(
        DefaultCMYK=res.icc("cmyk"), DefaultRGB=res.icc("srgb"), DefaultGray=res.calgray())))
    p.use("XObject", "FmDefaultCS", form)
    p.figure("q 1 0 0 1 %s %s cm /FmDefaultCS Do Q" % (n(x), n(y)), "CMYK and grey swatches drawn through default colour spaces.")

    x, y, w, h = p.tile(t[14], "Overprint: OP, op and OPM", "T57, T146", "viewer",
                        note="Seen only with overprint preview")
    op = p.use("ExtGState", "GSOP", res.gstate(OP=True, op=True, OPM=1))
    cm = pal.cmyk("teal")
    p.figure("%s k %s f q %s gs 0 %s 0 0 k %s f Q" % (
        fmt([cm[0], 0, 0, 0]), rect_path(x + 10, y + 6, w * 0.5, h - 12), op, fmt([0.8]),
        rect_path(x + w * 0.4, y + 10, w * 0.5, h - 20)),
             "Cyan and magenta rectangles; the magenta one overprints, so preview shows blue where they overlap.")
    return p


# -- 4. Shadings and functions -----------------------------------------------------------------

def _q16(v, lo, hi):
    return max(0, min(65535, int(round((v - lo) / (hi - lo) * 65535))))


def _col8(c):
    return bytes(max(0, min(255, int(round(v * 255)))) for v in c)


def mesh_decode(x, y, w, h, ncomp=3):
    return Array([x, x + w, y, y + h] + [0, 1] * ncomp)


def page_shadings(doc, res):
    p = Page(doc, "Shadings and functions",
             "All seven shading types, drawn with the sh operator, and all four function types. "
             "Mesh shadings carry colour at every vertex, so the dark build changes the mesh data.")
    pal = p.pal
    t = p.grid(3, 4)

    def shade(rect, key, sh, alt):
        x, y, w, h = rect
        nm = p.use("Shading", key, doc.pdf.make_indirect(sh) if isinstance(sh, Dictionary) else sh)
        p.figure("q %s W n %s sh Q" % (rect_path(x, y, w, h), nm), alt)

    r = p.tile(t[0], "Type 1: function-based", "T78, T42", "swaps", note="Type 4 PostScript function")
    x, y, w, h = r
    shade(r, "Sh1", Dictionary(ShadingType=1, ColorSpace=Name.DeviceRGB, Domain=Array([0, 1, 0, 1]),
                               Matrix=Array([w, 0, 0, h, x, y]),
                               Function=res.fn_postscript_xy("accent", "pink", "yellow")),
          "A colour field blending three colours across x and y.")

    r = p.tile(t[1], "Type 2: axial", "T79, T40", "swaps", note="Type 2 exponential function, Extend")
    x, y, w, h = r
    shade(r, "Sh2", Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB,
                               Coords=Array([x + w * 0.2, y, x + w * 0.8, y]),
                               Function=res.fn_exp("blue", "green"), Extend=Array([True, True])),
          "A left to right gradient from blue to green.")

    r = p.tile(t[2], "Type 3: radial", "T80, T41", "swaps", note="Type 3 stitching function")
    x, y, w, h = r
    shade(r, "Sh3", Dictionary(ShadingType=3, ColorSpace=Name.DeviceRGB,
                               Coords=Array([x + w / 2, y + h / 2, 2, x + w / 2, y + h / 2, h * 0.7]),
                               Function=res.fn_stitch(["yellow", "orange", "red", "paper"]),
                               Extend=Array([True, True])),
          "A radial gradient through yellow, orange and red.")

    r = p.tile(t[3], "Axial with a sampled function", "T79, T39", "swaps", note="Type 0 sampled function")
    x, y, w, h = r
    shade(r, "Sh2s", Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, y, x + w, y]),
                                Function=res.fn_sampled(HUES)),
          "A rainbow gradient from a sampled function.")

    # Type 4: free-form triangle mesh
    r = p.tile(t[4], "Type 4: free-form triangle mesh", "T81", "swaps")
    x, y, w, h = r
    verts = [(0, x, y, "red"), (0, x + w, y, "blue"), (0, x + w / 2, y + h, "yellow"),
             (2, x, y + h, "green")]
    data = b"".join(bytes([f]) + struct.pack(">HH", _q16(vx, x, x + w), _q16(vy, y, y + h)) + _col8(pal.rgb(c))
                    for f, vx, vy, c in verts)
    sh4 = doc.stream(data, ShadingType=4, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16, BitsPerComponent=8,
                     BitsPerFlag=8, Decode=mesh_decode(x, y, w, h))
    shade(r, "Sh4", sh4, "Two triangles with a colour at each corner.")

    r = p.tile(t[5], "Type 5: lattice-form mesh", "T82", "swaps")
    x, y, w, h = r
    cols, rows = 4, 3
    data = b""
    for j in range(rows):
        for i in range(cols):
            role = HUES[(i + j * 2) % len(HUES)]
            vx = x + w * i / (cols - 1)
            vy = y + h * j / (rows - 1) + (4 * math.sin(i * 1.7) if 0 < j < rows - 1 else 0)
            data += struct.pack(">HH", _q16(vx, x, x + w), _q16(vy, y, y + h)) + _col8(pal.rgb(role))
    sh5 = doc.stream(data, ShadingType=5, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16, BitsPerComponent=8,
                     VerticesPerRow=cols, Decode=mesh_decode(x, y, w, h))
    shade(r, "Sh5", sh5, "A 4 by 3 lattice of coloured vertices.")

    def patch_points(x, y, w, h, bulge):
        A, B, C, D = (x + 4, y + 4), (x + 4, y + h - 4), (x + w - 4, y + h - 4), (x + w - 4, y + 4)
        return [A, (x - bulge, y + h / 3), (x - bulge, y + 2 * h / 3), B,
                (x + w / 3, y + h + bulge), (x + 2 * w / 3, y + h - bulge * 2), C,
                (x + w + bulge, y + 2 * h / 3), (x + w - bulge, y + h / 3), D,
                (x + 2 * w / 3, y - bulge), (x + w / 3, y + bulge)]

    for idx, (stype, label, tab) in enumerate([(6, "Type 6: Coons patch mesh", "T83, T84"),
                                                (7, "Type 7: tensor-product patch mesh", "T83, T85")]):
        r = p.tile(t[6 + idx], label, tab, "swaps")
        x, y, w, h = r
        pts = patch_points(x + 6, y + 4, w - 12, h - 8, 8)
        if stype == 7:
            pts += [(x + w / 3, y + h / 3), (x + w / 3, y + 2 * h / 3 + 10),
                    (x + 2 * w / 3, y + 2 * h / 3), (x + 2 * w / 3, y + h / 3 - 10)]
        rec = bytes([0]) + b"".join(struct.pack(">HH", _q16(px, x, x + w), _q16(py, y, y + h)) for px, py in pts)
        rec += b"".join(_col8(pal.rgb(c)) for c in ["teal", "purple", "orange", "accent"])
        sh = doc.stream(rec, ShadingType=stype, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16, BitsPerComponent=8,
                        BitsPerFlag=8, Decode=mesh_decode(x, y, w, h))
        shade(r, "Sh%d" % stype, sh, "One curved patch with a colour at each corner.")

    r = p.tile(t[8], "Mesh with a function", "T81", "swaps", note="Vertices carry t; a function maps t to colour")
    x, y, w, h = r
    verts = [(0, x, y, 0.0), (0, x + w, y, 0.5), (0, x + w / 2, y + h, 1.0), (2, x, y + h, 0.25),
             (1, x + w, y + h, 0.75)]
    data = b"".join(bytes([f]) + struct.pack(">HH", _q16(vx, x, x + w), _q16(vy, y, y + h)) + bytes([int(tv * 255)])
                    for f, vx, vy, tv in verts)
    shf = doc.stream(data, ShadingType=4, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16, BitsPerComponent=8,
                     BitsPerFlag=8, Decode=Array([x, x + w, y, y + h, 0, 1]),
                     Function=res.fn_stitch(["purple", "pink", "yellow"]))
    shade(r, "Sh4f", shf, "Triangles shaded through a function of t.")

    r = p.tile(t[9], "Axial shading in Lab", "T79, T64", "swaps")
    x, y, w, h = r
    shade(r, "ShLab", Dictionary(ShadingType=2, ColorSpace=res.lab(), Coords=Array([x, y, x + w, y + h]),
                                 Function=Dictionary(FunctionType=2, Domain=Array([0, 1]),
                                                     C0=Array([round(v, 3) for v in pal.lab("teal")]),
                                                     C1=Array([round(v, 3) for v in pal.lab("pink")]), N=1)),
          "A diagonal gradient computed in Lab.")

    r = p.tile(t[10], "Axial shading in DeviceN", "T79, T70", "swaps")
    x, y, w, h = r
    shade(r, "ShDN", Dictionary(ShadingType=2, ColorSpace=res.devicen(), Coords=Array([x, y, x + w, y]),
                                Function=Dictionary(FunctionType=2, Domain=Array([0, 1]), C0=Array([1, 0]),
                                                    C1=Array([0, 1]), N=1)),
          "A gradient from the teal spot ink to the orange spot ink.")

    r = p.tile(t[11], "Background, BBox and AntiAlias", "T77", "swaps",
               note="sh ignores Background; a pattern fill uses it")
    x, y, w, h = r
    shd = Dictionary(ShadingType=3, ColorSpace=Name.DeviceRGB, AntiAlias=True,
                     Background=Array([round(v, 4) for v in pal.rgb("rule")]),
                     BBox=Array([x + 4, y + 4, x + w / 2 - 4, y + h - 4]),
                     Coords=Array([x + w / 4, y + h / 2, 0, x + w / 4, y + h / 2, h * 0.35]),
                     Function=res.fn_exp("accent", "teal"))
    shd = doc.pdf.make_indirect(shd)
    p.use("Shading", "ShBG", shd)
    shd2 = shd.copy()
    shd2.BBox = Array([x + w / 2 + 4, y + 4, x + w - 4, y + h - 4])
    shd2.Coords = Array([x + 3 * w / 4, y + h / 2, 0, x + 3 * w / 4, y + h / 2, h * 0.35])
    pat = doc.pdf.make_indirect(Dictionary(Type=Name.Pattern, PatternType=2, Shading=doc.pdf.make_indirect(shd2)))
    p.use("Pattern", "PBG", pat)
    p.figure("q %s W n /ShBG sh Q q /Pattern cs /PBG scn %s f Q" % (
        rect_path(x, y, w / 2, h), rect_path(x + w / 2, y, w / 2, h)),
             "A radial shading drawn with sh, then the same shading as a pattern, which paints its background.")
    return p


# -- 5. Patterns --------------------------------------------------------------------------------

def page_patterns(doc, res):
    p = Page(doc, "Patterns",
             "Tiling patterns, coloured and uncoloured, and shading patterns for fills, strokes and text. "
             "A coloured pattern carries its colours inside; an uncoloured one takes them where it is used.")
    pal = p.pal
    t = p.grid(3, 3)

    def tiling(key, body, paint, tiling_type=1, step=10, matrix=None, resources=None):
        s = doc.stream(body, Type=Name.Pattern, PatternType=1, PaintType=paint, TilingType=tiling_type,
                       BBox=Array([0, 0, step, step]), XStep=step, YStep=step,
                       Resources=resources if resources is not None else Dictionary())
        if matrix:
            s.Matrix = Array(matrix)
        p.use("Pattern", key, s)
        return s

    x, y, w, h = p.tile(t[0], "Tiling, coloured (PaintType 1)", "T74", "swaps")
    tiling("PChk", "%s 0 0 5 5 re 5 5 5 5 re f %s 5 0 5 5 re 0 5 5 5 re f" % (pal.rg("accent"), pal.rg("yellow")), 1)
    p.figure("/Pattern cs /PChk scn %s f" % round_rect_path(x, y, w, h, 3), "A blue and yellow checkerboard pattern.")

    x, y, w, h = p.tile(t[1], "Tiling, uncoloured (PaintType 2)", "T74", "swaps",
                        note="Colour given at use: [/Pattern /DeviceRGB]")
    tiling("PHatch", "1.2 w 0 0 m 8 8 l S", 2, step=8)
    pcs = p.use("ColorSpace", "CSPatRGB", res.pattern_space("rgb"))
    p.figure("%s cs %s /PHatch scn %s f %s cs %s /PHatch scn %s f" % (
        pcs, fmt(pal.rgb("red")), rect_path(x, y, w / 2 - 3, h), pcs, fmt(pal.rgb("teal")),
        rect_path(x + w / 2 + 3, y, w / 2 - 3, h)), "One hatch pattern painted in red and in teal.")

    x, y, w, h = p.tile(t[2], "Tiling types 1, 2, 3 and a Matrix", "T74", "swaps")
    for i, tt in enumerate([1, 2, 3]):
        tiling("PT%d" % tt, "%s 2 2 4 4 re f" % pal.rg(HUES[i * 2 + 1]), 1, tiling_type=tt, step=8,
               matrix=[0.9, 0.5, -0.5, 0.9, 0, 0] if tt == 3 else None)
    p.figure(" ".join("/Pattern cs /PT%d scn %s f" % (tt, rect_path(x + i * w / 3 + 2, y, w / 3 - 4, h))
                      for i, tt in enumerate([1, 2, 3])),
             "Dots tiled with constant spacing, no distortion, faster tiling and a rotated matrix.")

    sh = doc.pdf.make_indirect(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([0, 0, W, 0]),
                                          Function=res.fn_stitch(["purple", "pink", "orange"]),
                                          Extend=Array([True, True])))
    shpat = doc.pdf.make_indirect(Dictionary(Type=Name.Pattern, PatternType=2, Shading=sh))
    p.use("Pattern", "PGrad", shpat)

    x, y, w, h = p.tile(t[3], "Shading pattern: fill", "T75", "swaps")
    p.figure("/Pattern cs /PGrad scn %s f" % circle_path(x + w / 2, y + h / 2, min(w, h) / 2),
             "A disc filled with a gradient.")

    x, y, w, h = p.tile(t[4], "Shading pattern: stroke", "T75", "swaps")
    p.figure("/Pattern CS /PGrad SCN 7 w 1 J %s S" % poly_path(
        [(x + 6, y + 6), (x + w * 0.3, y + h - 6), (x + w * 0.6, y + 10), (x + w - 6, y + h - 8)]),
             "A thick zigzag stroked with a gradient.")

    x, y, w, h = p.tile(t[5], "Shading pattern: text", "T75, T104", "swaps")
    f = p.font("SansBold")
    p.figure("BT /Pattern cs /PGrad scn /SansBold 30 Tf %s %s Td %s Tj ET" % (n(x + 2), n(y + h / 2 - 10), f.enc("Pattern")),
             "The word Pattern filled with a gradient.")

    x, y, w, h = p.tile(t[6], "Pattern inside a pattern", "T74", "swaps")
    inner_pat = doc.stream("%s 1 1 2 2 re f" % pal.rg("ink"), Type=Name.Pattern, PatternType=1, PaintType=1,
                           TilingType=1, BBox=Array([0, 0, 4, 4]), XStep=4, YStep=4, Resources=Dictionary())
    tiling("PNest", "%s 0 0 16 16 re f /Pattern cs /PIn scn 2 2 12 12 re f" % pal.rg("green"), 1, step=16,
           resources=Dictionary(Pattern=Dictionary(PIn=inner_pat)))
    p.figure("/Pattern cs /PNest scn %s f" % rect_path(x, y, w, h), "Green tiles each filled with a fine dot pattern.")

    x, y, w, h = p.tile(t[7], "Shading pattern with ExtGState", "T75, T57", "swaps", note="Pattern's own ca 0.5")
    gpat = doc.pdf.make_indirect(Dictionary(Type=Name.Pattern, PatternType=2, Shading=sh,
                                            ExtGState=Dictionary(Type=Name.ExtGState, ca=0.5)))
    p.use("Pattern", "PGradGS", gpat)
    p.figure("%s %s f /Pattern cs /PGradGS scn %s f" % (
        pal.rg("ink"), " ".join(rect_path(x + i * 14, y, 7, h) for i in range(int(w / 14) + 1)),
        circle_path(x + w / 2, y + h / 2, min(w, h) / 2)), "A half-transparent gradient disc over stripes.")

    x, y, w, h = p.tile(t[8], "Uncoloured pattern over a spot colour", "T74, T61", "swaps",
                        note="[/Pattern /Separation ...]")
    tiling("PDots", "%s 0 0 m 6 3 l 0 6 l h f" % "", 2, step=6)
    scs = p.use("ColorSpace", "CSPatSep", res.pattern_space("sep"))
    p.figure("%s cs 1 /PDots scn %s f" % (scs, rect_path(x, y, w, h)), "Small triangles in the teal spot ink.")
    return p


# -- 6. Fonts -----------------------------------------------------------------------------------

STD14 = ["Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic", "Helvetica", "Helvetica-Bold",
         "Helvetica-Oblique", "Helvetica-BoldOblique", "Courier", "Courier-Bold", "Courier-Oblique",
         "Courier-BoldOblique", "Symbol", "ZapfDingbats"]


def page_fonts(doc, res):
    p = Page(doc, "Fonts",
             "Every font type PDF defines: the standard 14 by reference, and embedded Type 1, TrueType, "
             "bare CFF, OpenType, two kinds of composite font and vertical writing. Text colour should follow "
             "the theme whatever the font type.")
    t = p.grid(2, 5, heights=[150, 118, 118, 118, 118])
    pal = p.pal

    x, y, w, h = p.tile(t[0], "Standard 14 fonts, not embedded", "T108, T109", "swaps",
                        note="The viewer supplies these fonts")
    for i, base in enumerate(STD14):
        col, row = i // 7, i % 7
        f = p.std(base)
        sample = {"Symbol": "abgdpW", "ZapfDingbats": "3456nH"}.get(base, base)
        p.tagged("Span", p.text_op(x + col * w / 2, y + h - 8 - row * 14, sample, 8.5, f,
                                   "ink" if i % 2 == 0 else "accent"),
                 actual=None if base not in ("Symbol", "ZapfDingbats") else
                 ("αβγδπΩ" if base == "Symbol" else "✓✔✕✖■★"))

    samples = [("T1", "Type 1, embedded (FontFile)", "T109, T124", "Bitstream Charter: The quick brown fox jumps."),
               ("Serif", "TrueType, embedded (FontFile2)", "T109, T124", "DejaVu Serif: The quick brown fox jumps."),
               ("CFF", "Bare CFF (FontFile3 /Type1C)", "T124, T125", "Inter as CFF: The quick brown fox jumps."),
               ("OTF", "OpenType CFF (FontFile3 /OpenType)", "T124, T125", "Inter Bold OpenType: quick brown fox."),
               ("CID2", "Type 0 with CIDFontType2, Identity-H", "T115, T119", FontSetText.TYPE0),
               ("CID0", "Type 0 with CIDFontType0 (CFF CIDs)", "T115, T119", FontSetText.CJK)]
    for i, (key, title, tab, s) in enumerate(samples):
        x, y, w, h = p.tile(t[1 + i], title, tab, "swaps")
        f = p.font(key)
        size = 13
        while f.width(s, size) > w and size > 6:
            size -= 0.5
        p.tagged("P", p.text_op(x, y + h - size, s, size, f, "ink"))
        p.tagged("P", p.text_op(x, y + h - size * 2.4, s[:max(10, len(s) // 2)], size * 0.8, f, ["accent", "red", "green", "purple", "teal", "orange"][i]))

    x, y, w, h = p.tile(t[7], "Vertical writing: Identity-V", "T115, T116", "swaps", note="W2 and DW2 vertical metrics")
    f = p.font("CID0V")
    s = FontSetText.CJK[:7]
    p.tagged("P", "BT /CID0V 10 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + w * 0.3), n(y + h - 2), f.enc(s)))
    p.tagged("P", "BT /CID0V 10 Tf %s %s %s Td %s Tj ET" % (pal.rg("accent"), n(x + w * 0.6), n(y + h - 2), f.enc(FontSetText.CJK[7:14])))

    x, y, w, h = p.tile(t[8], "Text state: Tc, Tw, Tz, Ts, TL, TJ", "T103, T106, T107", "swaps")
    f = p.font("Sans")
    body = ["BT /Sans 8.5 Tf %s 11 TL %s %s Td" % (pal.rg("ink"), n(x), n(y + h - 9)),
            "2 Tc %s Tj" % f.enc("Tc spacing"), "0 Tc 6 Tw %s ' 0 Tw" % f.enc("Tw word spacing here"),
            "150 Tz %s ' 100 Tz" % f.enc("Tz 150"),
            "%s ' 4 Ts %s Tj 0 Ts %s Tj" % (f.enc("Rise: x"), f.enc("2"), f.enc(" and TJ:")),
            "[%s -400 %s 200 %s] TJ" % (f.enc("A"), f.enc("V"), f.enc("A kerned")),
            "0 -11 TD %s Tj" % f.enc("TD moves and sets the leading"),
            "1 2 %s \"" % f.enc("the \" operator sets Tw and Tc"), "ET"]
    p.tagged("P", "\n".join(body))

    x, y, w, h = p.tile(t[9], "Text matrix: Tm", "T106", "swaps")
    f = p.font("SansBold")
    body = []
    for i, a in enumerate([0, 15, 30, 45]):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        body.append("BT /SansBold 9 Tf %s %s %s %s %s %s %s Tm %s Tj ET" % (
            pal.rg(HUES[i * 2]), n(ca), n(sa), n(-sa), n(ca), n(x + 4 + i * 30), n(y + 6), f.enc("Tm %d" % a)))
    p.tagged("P", "\n".join(body))
    return p


class FontSetText:
    TYPE0 = "Ελληνικά αβγδε, Кириллица абвгд"
    CJK = "縦書きの日本語テキスト。横書きの文字列、字体見本。"


# -- 7. Type 3 fonts and text effects ---------------------------------------------------------------

def page_text_effects(doc, res):
    p = Page(doc, "Type 3 fonts and text effects",
             "Type 3 glyphs that take the fill colour, glyphs that set their own colours, and a bitmap glyph; "
             "every text rendering mode, clipping to text, knockout and invisible text.")
    pal = p.pal
    t = p.grid(3, 3)
    t3 = p.add_font(res.type3())

    x, y, w, h = p.tile(t[0], "Type 3, uncoloured glyphs (d1)", "T110, T111", "swaps")
    body = []
    for i, role in enumerate(["ink", "accent", "red"]):
        body.append("BT /T3 22 Tf %s %s %s Td %s Tj ET" % (pal.rg(role), n(x), n(y + h - 22 - i * 28), t3.enc("star heart check arrow")))
    p.figure("\n".join(body), "Star, heart, check and arrow glyphs in three colours.")

    x, y, w, h = p.tile(t[1], "Type 3, coloured glyphs (d0)", "T110, T111", "swaps",
                        note="Colours live inside the glyph procedures")
    p.figure("BT /T3 34 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + 4), n(y + 14), t3.enc("badge flag badge")),
             "An information badge and a three-colour flag drawn by the glyphs themselves.")

    x, y, w, h = p.tile(t[2], "Type 3 glyph with a bitmap", "T110", "stays", note="An emoji image: it stays")
    p.figure("BT /T3 40 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + w / 2 - 20), n(y + 12), t3.enc("emoji")),
             "A colour emoji of an artist's palette.")

    f = p.font("SansBold")
    x, y, w, h = p.tile(t[3], "Rendering modes 0 to 3: Tr", "T104", "swaps", note="3 is invisible")
    body = ["%s %s 0.8 w" % (pal.rg("accent"), pal.RG("ink"))]
    for i in range(4):
        body.append("BT /SansBold 19 Tf %d Tr %s %s Td %s Tj ET" % (i, n(x + i * w / 4), n(y + h / 2 - 6), f.enc("Aa")))
    p.figure("\n".join(body), "The letters Aa filled, stroked, filled and stroked, and invisible.")
    for i in range(4):
        caption(p, x + (i + 0.35) * w / 4, y - 2, "Tr %d" % i)

    x, y, w, h = p.tile(t[4], "Rendering modes 4 to 7: clip", "T104", "swaps")
    stripes = lambda bx: " ".join(rect_path(bx + k * 3, y, 1.5, h) for k in range(10))
    body = []
    for i, mode in enumerate([4, 5, 6, 7]):
        bx = x + i * w / 4
        body.append("q %s %s 0.6 w BT /SansBold 21 Tf %d Tr %s %s Td %s Tj ET %s %s f Q" % (
            pal.rg("green"), pal.RG("ink"), mode, n(bx), n(y + h / 2 - 7), f.enc("Aa"), pal.rg("red"), stripes(bx)))
    p.figure("\n".join(body), "Letters used as a clip, with red stripes painted through them.")
    for i in range(4):
        caption(p, x + (i + 0.35) * w / 4, y - 2, "Tr %d" % (i + 4))

    x, y, w, h = p.tile(t[5], "Text knockout: TK", "T57", "swaps")
    tk_on = p.use("ExtGState", "GSTKon", res.gstate(TK=True, ca=0.6))
    tk_off = p.use("ExtGState", "GSTKoff", res.gstate(TK=False, ca=0.6))
    body = []
    for i, gs in enumerate([tk_off, tk_on]):
        body.append("q %s gs BT /SansBold 30 Tf %s -12 Tc %s %s Td %s Tj ET Q" % (
            gs, pal.rg("purple"), n(x + 4 + i * w / 2), n(y + h / 2 - 10), f.enc("AV")))
    p.figure("\n".join(body), "Overlapping translucent letters; with knockout off the overlap is darker.")
    caption(p, x + w / 4, y - 2, "TK false")
    caption(p, x + 3 * w / 4, y - 2, "TK true")

    x, y, w, h = p.tile(t[6], "Invisible text over a scan", "T104", "stays", note="Photo stays; Tr 3 text is invisible")
    from .images import photo
    im = photo(160, 90)
    img = doc.stream(im.tobytes(), Type=Name.XObject, Subtype=Name.Image, Width=im.width, Height=im.height,
                     ColorSpace=Name.DeviceRGB, BitsPerComponent=8)
    p.use("XObject", "ImScan", img)
    p.figure("q %s 0 0 %s %s %s cm /ImScan Do Q" % (n(w), n(h), n(x), n(y)), "A landscape photo.")
    fs = p.font("Sans")
    p.tagged("P", "BT 3 Tr /Sans 12 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + 6), n(y + h / 2), fs.enc("Searchable hidden text")))

    x, y, w, h = p.tile(t[7], "Fill, stroke and pattern together", "T104, T75", "swaps")
    sh = doc.pdf.make_indirect(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, y, x, y + h]),
                                          Function=res.fn_exp("yellow", "red")))
    p.use("Pattern", "PText", doc.pdf.make_indirect(Dictionary(Type=Name.Pattern, PatternType=2, Shading=sh)))
    p.figure("BT /SansBold 34 Tf 2 Tr 1.2 w /Pattern cs /PText scn %s %s %s Td %s Tj ET" % (
        pal.RG("ink"), n(x + 4), n(y + 10), f.enc("Glow")), "The word Glow with a gradient fill and a dark outline.")

    x, y, w, h = p.tile(t[8], "Tiny, huge and scaled text", "T103", "swaps")
    p.tagged("P", "BT /Sans 3 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x), n(y + h - 6), fs.enc("3 point text, still a colour")))
    p.tagged("P", "BT /SansBold 48 Tf %s %s %s Td %s Tj ET" % (pal.rg("accent"), n(x), n(y + 6), f.enc("Big")))
    p.tagged("P", "BT /Sans 9 Tf 60 Tz %s %s %s Td %s Tj ET" % (pal.rg("teal"), n(x + w * 0.55), n(y + 20), fs.enc("Tz 60 narrow")))
    return p
