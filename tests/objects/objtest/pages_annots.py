"""Pages for annotations: every subtype, with and without appearance streams."""
import math

from pikepdf import Array, Dictionary, Name, String

from .core import Page, circle_path, n, poly_path, rect_path, round_rect_path
from .palette import HUES, fmt

DATE = String("D:20261003120000Z")


def ap_form(doc, w, h, body, fonts=(), gstates=None, xobjects=None):
    res = Dictionary()
    if fonts:
        res.Font = Dictionary({("/" + f.key): f.obj for f in fonts})
    if gstates:
        res.ExtGState = Dictionary(gstates)
    if xobjects:
        res.XObject = Dictionary(xobjects)
    return doc.form(body, [0, 0, w, h], res)


_counter = [0]


def markup(p, subtype, rect, contents, ap=None, tag="Annot", **entries):
    _counter[0] += 1
    d = Dictionary(Type=Name.Annot, Subtype=Name("/" + subtype), Rect=Array([round(v, 3) for v in rect]), F=4,
                   Contents=String(contents), NM=String("objtest-%s-%d" % (subtype, p.number * 100 + len(p.annots))),
                   M=DATE)
    if subtype not in ("Link", "Widget", "Popup", "Screen", "PrinterMark", "TrapNet", "Watermark", "Movie",
                       "RichMedia", "3D"):
        d.T = String("pdf-themes")
        d.CreationDate = DATE
        d.Subj = String(subtype)
    if ap is not None:
        d.AP = ap if isinstance(ap, Dictionary) and Name.N in ap else Dictionary(N=ap)
    for k, v in entries.items():
        d[Name("/" + k)] = v
    return p.annot(d, tag=tag, alt=contents)


def popup_for(p, parent, rect, open_=False):
    pop = p.pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Popup, Rect=Array(rect), Parent=parent,
                                         Open=open_, F=28))
    if Name.C in parent:
        pop.C = parent.C
    pop.P = p.obj
    p.annots.append(pop)
    parent.Popup = pop
    return pop


def ending(style, x, y, direction, s, pal, fill_role):
    """Path for a line ending at (x, y); direction +1 points right, -1 left."""
    d = direction
    if style == "Square":
        return "%s re b" % " ".join(n(v) for v in (x - s / 2, y - s / 2, s, s))
    if style == "Circle":
        return circle_path(x, y, s / 2) + " b"
    if style == "Diamond":
        return poly_path([(x, y + s / 2), (x + s / 2, y), (x, y - s / 2), (x - s / 2, y)], close=True) + " b"
    if style in ("OpenArrow", "ROpenArrow"):
        k = d if style == "OpenArrow" else -d
        return poly_path([(x - k * s, y + s / 2), (x, y), (x - k * s, y - s / 2)]) + " S"
    if style in ("ClosedArrow", "RClosedArrow"):
        k = d if style == "ClosedArrow" else -d
        return poly_path([(x - k * s, y + s / 2), (x, y), (x - k * s, y - s / 2)], close=True) + " b"
    if style == "Butt":
        return "%s %s m %s %s l S" % (n(x), n(y - s / 2), n(x), n(y + s / 2))
    if style == "Slash":
        return "%s %s m %s %s l S" % (n(x - s * 0.25), n(y - s / 2), n(x + s * 0.25), n(y + s / 2))
    return ""


def cloud_path(x, y, w, h, r):
    """Scalloped outline for a cloudy border, as a series of arcs."""
    pts = []
    per = max(1, int(w / (2 * r)))
    for i in range(per):
        pts.append((x + (i + 0.5) * w / per, y, 0))
    per_v = max(1, int(h / (2 * r)))
    for i in range(per_v):
        pts.append((x + w, y + (i + 0.5) * h / per_v, 1))
    for i in range(per):
        pts.append((x + w - (i + 0.5) * w / per, y + h, 2))
    for i in range(per_v):
        pts.append((x, y + h - (i + 0.5) * h / per_v, 3))
    out = []
    for k, (cx, cy, side) in enumerate(pts):
        ang0 = {0: 180, 1: 270, 2: 0, 3: 90}[side] + 0
        a0, a1 = math.radians(ang0), math.radians(ang0 + 180)
        rr = r * 1.15
        sx, sy = cx + rr * math.cos(a0), cy + rr * math.sin(a0)
        if k == 0:
            out.append("%s %s m" % (n(sx), n(sy)))
        else:
            out.append("%s %s l" % (n(sx), n(sy)))
        for j in range(2):
            b0, b1 = a0 + j * (a1 - a0) / 2, a0 + (j + 1) * (a1 - a0) / 2
            kk = 4 / 3 * math.tan((b1 - b0) / 4)
            p0 = (cx + rr * math.cos(b0), cy + rr * math.sin(b0))
            p3 = (cx + rr * math.cos(b1), cy + rr * math.sin(b1))
            c1 = (p0[0] - kk * rr * math.sin(b0), p0[1] + kk * rr * math.cos(b0))
            c2 = (p3[0] + kk * rr * math.sin(b1), p3[1] - kk * rr * math.cos(b1))
            out.append("%s %s %s %s %s %s c" % (n(c1[0]), n(c1[1]), n(c2[0]), n(c2[1]), n(p3[0]), n(p3[1])))
    out.append("h")
    return " ".join(out)


# -- 15. Annotations: notes, shapes and lines ---------------------------------------------------

def page_annot_shapes(doc, res):
    p = Page(doc, "Annotations: notes, shapes and lines",
             "Each annotation carries an appearance stream drawn in the theme's colours, and its colour entries "
             "(C, IC, DA, DS, RC) say the same thing, for viewers that redraw it. The tiles marked viewer have no "
             "appearance stream, so the viewer draws them from those entries.")
    pal = p.pal
    t = p.grid(3, 4)
    sans, bold = p.font("Sans"), p.font("SansBold")
    doc.acroform_extra["need_dr"] = True

    # 1 Text note with appearance stream and a popup
    x, y, w, h = p.tile(t[0], "Text (sticky note) with appearance", "T175, T186", "swaps", note="Has a closed popup")
    icon = ap_form(doc, 24, 24, "%s %s 1 w %s B %s 1.2 w 5 16 m 19 16 l 5 12 m 19 12 l 5 8 m 14 8 l S" % (
        pal.rg("yellow"), pal.RG("ink"), round_rect_path(1, 1, 22, 22, 3), pal.RG("ink")))
    a = markup(p, "Text", [x + 8, y + h - 34, x + 32, y + h - 10], "A sticky note with its own icon.", icon,
               C=doc.rgb("yellow"), Name=Name.Note, Open=False)
    popup_for(p, a, [x + 40, y + 6, x + w - 4, y + h - 10])

    # 2 Review state and a reply (markup threads)
    x, y, w, h = p.tile(t[1], "Review state and a reply: IRT, RT, State", "T172, T174, T175", "swaps",
                        note="A reply thread on the sticky note; the state is hidden")
    reply_icon = ap_form(doc, 20, 20, "%s %s 1 w %s B %s 1.2 w 4 13 m 16 13 l 4 9 m 12 9 l S" % (
        pal.rg("teal"), pal.RG("ink"), round_rect_path(1, 1, 18, 18, 3), pal.RG("ink")))
    reply = markup(p, "Text", [x + 8, y + h - 34, x + 28, y + h - 14], "A reply to the sticky note.", reply_icon,
                   C=doc.rgb("teal"), Name=Name.Comment, IRT=a, RT=Name.R)
    p.text(x + 34, y + h - 27, "Reply to the note", size=6.5, role="muted", tag="Caption")
    tick = ap_form(doc, 20, 20, "%s %s f %s 2 w 1 J 1 j 5 10 m 9 6 l 15 14 l S" % (
        pal.rg("green"), circle_path(10, 10, 9.5), pal.RG("paper")))
    markup(p, "Text", [x + 8, y + h - 62, x + 28, y + h - 42], "Accepted by pdf-themes", tick, C=doc.rgb("green"),
           Name=Name.Note, IRT=a, StateModel=String("Review"), State=String("Accepted"), F=4 | 32)
    p.text(x + 34, y + h - 55, "Review state: Accepted (NoView)", size=6.5, role="muted", tag="Caption")
    marked = ap_form(doc, 20, 20, "%s 1.4 w %s S" % (pal.RG("purple"), circle_path(10, 10, 8)))
    markup(p, "Text", [x + 8, y + h - 90, x + 28, y + h - 70], "Marked", marked, C=doc.rgb("purple"), Name=Name.Note,
           IRT=a, StateModel=String("Marked"), State=String("Marked"), F=4 | 32)
    p.text(x + 34, y + h - 83, "Marked state (NoView)", size=6.5, role="muted", tag="Caption")

    # 3 FreeText plain
    x, y, w, h = p.tile(t[2], "FreeText with DA, DS and RC", "T177", "swaps", note="Rich text colours in RC")
    fw, fh = w - 8, 44
    txt = "Free text, drawn in ink"
    apb = "%s %s 1 w %s B BT /Sans 9 Tf %s 6 26 Td %s Tj %s 0 -13 Td %s Tj ET" % (
        pal.rg("tile"), pal.RG("accent"), rect_path(0.5, 0.5, fw - 1, fh - 1), pal.rg("ink"), sans.enc(txt),
        pal.rg("red"), sans.enc("and one red phrase"))
    rc = ('<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/" '
          'xfa:APIVersion="Acrobat:23.0.0" xfa:spec="2.0.2" style="font-size:9pt;color:%s"><p>%s<br/>'
          '<span style="color:%s">and one red phrase</span></p></body>' % (pal.hexstr("ink"), txt, pal.hexstr("red")))
    markup(p, "FreeText", [x + 4, y + h / 2 - fh / 2, x + 4 + fw, y + h / 2 + fh / 2], txt + " and one red phrase",
           ap_form(doc, fw, fh, apb, [sans]), DA=String("%s /Helv 9 Tf" % pal.rg("ink")),
           DS=String("font: Helvetica,sans-serif 9.0pt; text-align:left; color:%s" % pal.hexstr("ink")),
           RC=String(rc), C=doc.rgb("accent"), BS=Dictionary(W=1), Q=0)

    # 4 FreeText callout
    x, y, w, h = p.tile(t[3], "FreeText callout: CL, LE, IT", "T177, T179", "swaps")
    bx, by, bw, bh = x + w * 0.35, y + h - 40, w * 0.62, 30
    tipx, tipy = x + 8, y + 10
    rect = [x + 2, y + 4, x + w - 2, y + h - 4]
    ox, oy = rect[0], rect[1]
    arrow = poly_path([(tipx - ox + 7, tipy - oy + 3.5), (tipx - ox, tipy - oy), (tipx - ox + 3.5, tipy - oy + 7)], close=True)
    apb = ("%s %s 1 w %s B %s %s S %s %s f BT /Sans 8 Tf %s %s %s Td %s Tj ET" % (
        pal.rg("tile"), pal.RG("orange"), rect_path(bx - ox, by - oy, bw, bh), pal.RG("orange"),
        poly_path([(tipx - ox, tipy - oy), (bx - ox - 16, by - oy + bh / 2), (bx - ox, by - oy + bh / 2)]),
        pal.rg("orange"), arrow, pal.rg("ink"), n(bx - ox + 5), n(by - oy + 11), sans.enc("Callout text")))
    markup(p, "FreeText", rect, "A callout pointing at the corner.", ap_form(doc, rect[2] - rect[0], rect[3] - rect[1], apb, [sans]),
           IT=Name.FreeTextCallout, CL=Array([tipx, tipy, bx - 16, by + bh / 2, bx, by + bh / 2]), LE=Name.ClosedArrow,
           RD=Array([bx - rect[0], by - rect[1], rect[2] - bx - bw, rect[3] - by - bh]),
           DA=String("%s /Helv 8 Tf" % pal.rg("ink")), C=doc.rgb("orange"), BS=Dictionary(W=1))

    # 5 FreeText typewriter
    x, y, w, h = p.tile(t[4], "FreeText typewriter", "T177", "swaps", note="No border, text only")
    apb = "BT /Sans 10 Tf %s 2 6 Td %s Tj ET" % (pal.rg("blue"), sans.enc("Typed on the page"))
    markup(p, "FreeText", [x + 4, y + h / 2 - 10, x + w - 4, y + h / 2 + 10], "Typed on the page",
           ap_form(doc, w - 8, 20, apb, [sans]), IT=Name.FreeTextTypeWriter,
           DA=String("%s /Helv 10 Tf" % pal.rg("blue")), BS=Dictionary(W=0))

    # 6 Line endings
    x, y, w, h = p.tile(t[5], "Line: all ten line endings", "T178, T179", "swaps", note="Closed endings filled with IC")
    pairs = [("Square", "Circle"), ("Diamond", "OpenArrow"), ("ClosedArrow", "None"), ("Butt", "ROpenArrow"),
             ("RClosedArrow", "Slash")]
    for i, (a_, b_) in enumerate(pairs):
        ly = y + h - 10 - i * (h - 16) / 4
        x1, x2 = x + 12, x + w - 12
        rect = [x + 2, ly - 7, x + w - 2, ly + 7]
        ox, oy = rect[0], rect[1]
        apb = "%s %s 1.5 w %s %s m %s %s l S %s %s" % (
            pal.RG("green"), pal.rg("yellow"), n(x1 - ox), n(ly - oy), n(x2 - ox), n(ly - oy),
            ending(a_, x1 - ox, ly - oy, -1, 7, pal, "yellow"), ending(b_, x2 - ox, ly - oy, 1, 7, pal, "yellow"))
        markup(p, "Line", rect, "Line with %s and %s endings" % (a_, b_), ap_form(doc, rect[2] - ox, 14, apb),
               L=Array([x1, ly, x2, ly]), LE=Array([Name("/" + a_), Name("/" + b_)]), C=doc.rgb("green"),
               IC=doc.rgb("yellow"), BS=Dictionary(W=1.5))

    # 7 Dimension line with measure
    x, y, w, h = p.tile(t[6], "Line dimension with Measure", "T178, T266, T267", "swaps", note="Leader lines and a caption")
    x1, x2, ly = x + 10, x + w - 10, y + h / 2
    rect = [x + 2, ly - 22, x + w - 2, ly + 22]
    ox, oy = rect[0], rect[1]
    cap = "120 mm"
    cw = sans.width(cap, 8)
    apb = ("%s 0.8 w %s %s m %s %s l %s %s m %s %s l %s %s m %s %s l S %s %s %s BT /Sans 8 Tf %s %s %s Td %s Tj ET" % (
        pal.RG("purple"), n(x1 - ox), n(ly - oy - 14), n(x1 - ox), n(ly - oy + 4), n(x2 - ox), n(ly - oy - 14), n(x2 - ox),
        n(ly - oy + 4), n(x1 - ox), n(ly - oy), n(x2 - ox), n(ly - oy), pal.rg("purple"),
        ending("ClosedArrow", x1 - ox, ly - oy, -1, 6, pal, "purple"), ending("ClosedArrow", x2 - ox, ly - oy, 1, 6, pal, "purple"),
        pal.rg("purple"), n((x1 + x2) / 2 - ox - cw / 2), n(ly - oy + 5), sans.enc(cap)))
    measure = Dictionary(Type=Name.Measure, Subtype=Name.RL, R=String("1 in = 30 mm"),
                         X=Array([Dictionary(Type=Name.NumberFormat, U=String("mm"), C=0.8333, D=1)]),
                         D=Array([Dictionary(Type=Name.NumberFormat, U=String("mm"), C=1, D=1)]),
                         A=Array([Dictionary(Type=Name.NumberFormat, U=String("sq mm"), C=1, D=1)]))
    markup(p, "Line", rect, "A dimension line reading 120 mm.", ap_form(doc, rect[2] - ox, 44, apb, [sans]),
           L=Array([x1, ly, x2, ly]), LE=Array([Name.ClosedArrow, Name.ClosedArrow]), IT=Name.LineDimension,
           LL=-14, LLE=4, Cap=True, CP=Name.Top, Measure=measure, C=doc.rgb("purple"),
           IC=doc.rgb("purple"), BS=Dictionary(W=0.8))

    # 8 Square and circle
    x, y, w, h = p.tile(t[7], "Square and Circle with IC", "T180, T168", "swaps", note="Dashed border style")
    sw = (w - 12) / 2
    for i, sub in enumerate(["Square", "Circle"]):
        rect = [x + 4 + i * (sw + 4), y + 6, x + 4 + i * (sw + 4) + sw, y + h - 6]
        rw, rh = rect[2] - rect[0], rect[3] - rect[1]
        shape = rect_path(1.5, 1.5, rw - 3, rh - 3) if sub == "Square" else \
            "q 1 0 0 %s %s %s cm %s" % (n(rh / rw), n(rw / 2), n(rh / 2), circle_path(0, 0, rw / 2 - 1.5))
        apb = "%s %s 2 w [4 2] 0 d %s B%s" % (pal.rg(["teal", "pink"][i]), pal.RG("ink"), shape,
                                               "" if sub == "Square" else " Q")
        markup(p, sub, rect, sub + " annotation with interior colour", ap_form(doc, rw, rh, apb),
               C=doc.rgb("ink"), IC=doc.rgb(["teal", "pink"][i]), BS=Dictionary(W=2, S=Name.D, D=Array([4, 2])))

    # 9 Cloudy border
    x, y, w, h = p.tile(t[8], "Cloudy border: BE", "T169", "swaps")
    rect = [x + 10, y + 10, x + w - 10, y + h - 10]
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    apb = "%s %s 1.2 w %s B" % (pal.rg("tile"), pal.RG("red"), cloud_path(8, 8, rw - 16, rh - 16, 6))
    markup(p, "Square", rect, "A square with a cloudy border", ap_form(doc, rw, rh, apb), C=doc.rgb("red"),
           IC=doc.rgb("tile"), BE=Dictionary(S=Name.C, I=1), RD=Array([8, 8, 8, 8]), BS=Dictionary(W=1.2))

    # 10 Polygon and polyline
    x, y, w, h = p.tile(t[9], "Polygon and PolyLine", "T181", "swaps", note="Cloud intent; open path with endings")
    verts = [(x + 8, y + 10), (x + w * 0.4, y + h - 8), (x + w * 0.45, y + 20)]
    rect = [x + 2, y + 2, x + w * 0.5, y + h - 2]
    ox, oy = rect[0], rect[1]
    apb = "%s %s 1.5 w %s b" % (pal.rg("yellow"), pal.RG("orange"), poly_path([(vx - ox, vy - oy) for vx, vy in verts], close=True))
    markup(p, "Polygon", rect, "A triangle polygon", ap_form(doc, rect[2] - ox, rect[3] - oy, apb),
           Vertices=Array([c for v in verts for c in v]), C=doc.rgb("orange"), IC=doc.rgb("yellow"),
           IT=Name.PolygonCloud, BS=Dictionary(W=1.5))
    verts = [(x + w * 0.55, y + 12), (x + w * 0.7, y + h - 12), (x + w * 0.82, y + 24), (x + w - 8, y + h - 20)]
    rect = [x + w * 0.52, y + 2, x + w - 2, y + h - 2]
    ox, oy = rect[0], rect[1]
    apb = "%s %s 1.5 w %s %s" % (pal.RG("blue"), pal.rg("blue"), poly_path([(vx - ox, vy - oy) for vx, vy in verts]) + " S",
                                 ending("OpenArrow", verts[-1][0] - ox, verts[-1][1] - oy, 1, 7, pal, "blue"))
    markup(p, "PolyLine", rect, "A zigzag polyline with an arrow", ap_form(doc, rect[2] - ox, rect[3] - oy, apb),
           Vertices=Array([c for v in verts for c in v]), C=doc.rgb("blue"), LE=Array([Name("/None"), Name.OpenArrow]),
           BS=Dictionary(W=1.5))

    # 11 Ink
    x, y, w, h = p.tile(t[10], "Ink: InkList", "T185", "swaps")
    strokes = []
    for k in range(2):
        pts = [(x + 8 + i * (w - 16) / 30, y + h / 2 + (k * 18 - 9) + 14 * math.sin(i / 3 + k)) for i in range(31)]
        strokes.append(pts)
    rect = [x + 2, y + 2, x + w - 2, y + h - 2]
    ox, oy = rect[0], rect[1]
    apb = "%s 2 w 1 J 1 j %s" % (pal.RG("purple"), " ".join(poly_path([(a - ox, b - oy) for a, b in s]) + " S" for s in strokes))
    markup(p, "Ink", rect, "Two freehand strokes", ap_form(doc, rect[2] - ox, rect[3] - oy, apb),
           InkList=Array([Array([c for pt in s for c in pt]) for s in strokes]), C=doc.rgb("purple"), BS=Dictionary(W=2))

    # 12 Colour arrays with 0, 1 and 4 components
    x, y, w, h = p.tile(t[11], "C and IC in grey, CMYK and none", "T166, T180", "swaps",
                        note="C [] is transparent: no border is drawn")
    q = (w - 12) / 3
    shapes = [("Square", [], [pal.gray("muted")], "rule", None, "No border (C []), grey interior"),
              ("Circle", [pal.gray("ink")], list(pal.cmyk("teal")), "teal", "ink", "Grey border, CMYK interior"),
              ("Square", list(pal.cmyk("red")), [], None, "red", "CMYK border, no interior")]
    for i, (sub, c, ic, fill_role, stroke_role, desc) in enumerate(shapes):
        r = [x + 2 + i * (q + 4), y + 10, x + 2 + i * (q + 4) + q, y + h - 10]
        rw, rh = r[2] - r[0], r[3] - r[1]
        if sub == "Square":
            pre, shape, post = "", rect_path(1.5, 1.5, rw - 3, rh - 3), ""
        else:
            pre, shape, post = ("q 1 0 0 %s %s %s cm " % (n(rh / rw), n(rw / 2), n(rh / 2)),
                                circle_path(0, 0, rw / 2 - 1.5), " Q")
        body = []
        if fill_role:
            body.append("%s%s %s f%s" % (pre, pal.rg(fill_role), shape, post))
        if stroke_role:
            body.append("%s%s 3 w %s S%s" % (pre, pal.RG(stroke_role), shape, post))
        markup(p, sub, r, desc, ap_form(doc, rw, rh, " ".join(body)), C=Array([round(v, 4) for v in c]),
               IC=Array([round(v, 4) for v in ic]), BS=Dictionary(W=3))
    return p


# -- 16. Annotations: marking up text, stamps and the rest --------------------------------------------

def page_annot_more(doc, res):
    p = Page(doc, "Annotations: text markup, stamps and the rest",
             "Text markup over real text, stamps, a popup, a redaction mark, attachments, a watermark, printer's "
             "marks and a trap network, plus the PDF 2.0 annotation blend mode and fill opacity.")
    pal = p.pal
    t = p.grid(3, 4)
    sans, bold = p.font("Sans"), p.font("SansBold")

    def line_of_text(x, y, s, size=9):
        p.text(x, y, s, size=size)
        return sans.width(s, size)

    def quad(x, y, w, h):
        return [x, y + h, x + w, y + h, x, y, x + w, y]

    # 1 Highlight
    x, y, w, h = p.tile(t[0], "Highlight", "T182", "swaps", note="Multiply in light; the dark build uses Screen")
    ty = y + h / 2
    tw = line_of_text(x + 4, ty, "Highlight this phrase")
    rect = [x + 2, ty - 4, x + 6 + tw, ty + 11]
    apb = "/GSmul gs %s %s f" % (pal.rg("hl"), rect_path(0, 0, rect[2] - rect[0], rect[3] - rect[1]))
    markup(p, "Highlight", rect, "Highlighted phrase", ap_form(doc, rect[2] - rect[0], rect[3] - rect[1], apb,
                                                            gstates={"/GSmul": res.gstate(BM=Name.Screen if pal.dark else Name.Multiply)}),
           QuadPoints=Array(quad(*rect[:2], rect[2] - rect[0], rect[3] - rect[1])), C=doc.rgb("hl"))

    # 2 Underline, squiggly, strikeout
    x, y, w, h = p.tile(t[1], "Underline, Squiggly, StrikeOut", "T182", "swaps")
    for i, (sub, role) in enumerate([("Underline", "green"), ("Squiggly", "red"), ("StrikeOut", "purple")]):
        ty = y + h - 18 - i * (h - 24) / 2
        tw = line_of_text(x + 4, ty, sub + " this text")
        rect = [x + 2, ty - 4, x + 6 + tw, ty + 11]
        rw, rh = rect[2] - rect[0], rect[3] - rect[1]
        if sub == "Underline":
            apb = "%s 1 w 2 2.5 m %s 2.5 l S" % (pal.RG(role), n(rw - 2))
        elif sub == "Squiggly":
            pts = [(2 + k * 2, 1.5 + (k % 2) * 2) for k in range(int((rw - 4) / 2))]
            apb = "%s 0.8 w %s S" % (pal.RG(role), poly_path(pts))
        else:
            apb = "%s 1 w 2 %s m %s %s l S" % (pal.RG(role), n(rh * 0.45), n(rw - 2), n(rh * 0.45))
        markup(p, sub, rect, sub + " markup", ap_form(doc, rw, rh, apb),
               QuadPoints=Array(quad(rect[0], rect[1], rw, rh)), C=doc.rgb(role))

    # 3 Caret
    x, y, w, h = p.tile(t[2], "Caret: Sy P and None", "T183", "swaps")
    tw = line_of_text(x + 4, y + h / 2, "Insert here and here")
    for i, (sy, cx) in enumerate([("P", x + 4 + sans.width("Insert", 9)), ("None", x + 4 + sans.width("Insert here and", 9))]):
        rect = [cx - 5, y + h / 2 - 9, cx + 5, y + h / 2 + 1]
        apb = "%s %s f" % (pal.rg("blue"), poly_path([(0, 0), (5, 10), (10, 0)], close=True))
        if sy == "P":
            apb += " BT /SansBold 7 Tf %s 2 -8 Td %s Tj ET" % (pal.rg("blue"), bold.enc("¶"))
        markup(p, "Caret", rect, "Insertion point", ap_form(doc, 10, 10, apb, [bold]), C=doc.rgb("blue"),
               Sy=Name("/" + sy), RD=Array([0, 0, 0, 0]))

    # 4 Stamp with custom appearance, and an image stamp
    x, y, w, h = p.tile(t[3], "Stamp: drawn and image", "T184", "swaps", note="The image stamp stays")
    rect = [x + 4, y + h / 2 - 2, x + w * 0.55, y + h / 2 + 30]
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    apb = "%s 2.5 w %s S BT /SansBold 10 Tf %s 7 10 Td %s Tj ET" % (
        pal.RG("green"), round_rect_path(2, 2, rw - 4, rh - 4, 5), pal.rg("green"), bold.enc("APPROVED"))
    markup(p, "Stamp", rect, "Approved stamp", ap_form(doc, rw, rh, apb, [bold]), Name=Name.Approved, C=doc.rgb("green"))
    from .images import photo
    im = photo(60, 40)
    img = doc.stream(im.tobytes(), Type=Name.XObject, Subtype=Name.Image, Width=60, Height=40,
                     ColorSpace=Name.DeviceRGB, BitsPerComponent=8)
    rect = [x + w * 0.6, y + 6, x + w - 4, y + 6 + (w * 0.4 - 4) / 1.5]
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    markup(p, "Stamp", rect, "Photo stamp", ap_form(doc, rw, rh, "q %s 0 0 %s 0 0 cm /Im Do Q" % (n(rw), n(rh)),
                                                    xobjects={"/Im": img}), Name=Name("/Image"), IT=Name.StampImage)

    # 5 Stamps with the standard names, each with an appearance
    x, y, w, h = p.tile(t[4], "Stamp names, with appearances", "T184", "swaps",
                        note="The legacy file has the same stamps without appearances")
    for i, (nm, label) in enumerate([("Draft", "DRAFT"), ("Confidential", "CONFIDENTIAL"), ("Final", "FINAL"),
                                     ("ForComment", "FOR COMMENT"), ("TopSecret", "TOP SECRET"), ("Expired", "EXPIRED")]):
        cx, cy = x + 2 + (i % 2) * w / 2, y + h - 22 - (i // 2) * (h - 8) / 3
        sw, sh = w / 2 - 6, 16
        size = 7
        while bold.width(label, size) > sw - 8:
            size -= 0.5
        apb = "%s 1.5 w %s S BT /SansBold %s Tf %s %s 5 Td %s Tj ET" % (
            pal.RG("red"), round_rect_path(1, 1, sw - 2, sh - 2, 3), n(size), pal.rg("red"),
            n((sw - bold.width(label, size)) / 2), bold.enc(label))
        markup(p, "Stamp", [cx, cy, cx + sw, cy + sh], "Stamp " + nm, ap_form(doc, sw, sh, apb, [bold]),
               Name=Name("/" + nm), C=doc.rgb("red"))

    # 6 Popup, open
    x, y, w, h = p.tile(t[5], "Popup, open", "T186", "viewer", note="Popups are drawn by the viewer")
    bubble = ap_form(doc, 20, 20, "%s %s f %s 3 3 m 7 7 l 10 3 l f" % (
        pal.rg("accent"), round_rect_path(1, 5, 18, 14, 3), pal.rg("accent")))
    parent = markup(p, "Text", [x + 4, y + h - 26, x + 24, y + h - 6], "This note's popup starts open.", bubble,
                    C=doc.rgb("accent"), Name=Name.Comment, Open=True)
    popup_for(p, parent, [x + 30, y + 10, x + w - 4, y + h - 6], open_=True)

    # 7 Redact
    x, y, w, h = p.tile(t[6], "Redact (marked, not applied)", "T195", "swaps", note="IC and OverlayText apply once redacted")
    ty = y + h / 2
    tw = line_of_text(x + 4, ty, "Account 1234 5678")
    rect = [x + 4 + sans.width("Account ", 9) - 1, ty - 3, x + 6 + tw, ty + 10]
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    ro = ap_form(doc, rw, rh, "%s %s f BT /SansBold 6 Tf %s 2 3 Td %s Tj ET" % (pal.rg("ink"), rect_path(0, 0, rw, rh),
                                                                              pal.rg("paper"), bold.enc("REDACTED")), [bold])
    markup(p, "Redact", rect, "Number marked for redaction", ap_form(doc, rw, rh, "%s 1 w %s S" % (pal.RG("red"), rect_path(0.5, 0.5, rw - 1, rh - 1))),
           QuadPoints=Array(quad(rect[0], rect[1], rw, rh)), IC=doc.rgb("ink"),
           OverlayText=String("REDACTED"), DA=String("%s /Helv 6 Tf" % pal.rg("paper")), Q=1, RO=ro, C=doc.rgb("red"))

    # 8 File attachments
    x, y, w, h = p.tile(t[7], "FileAttachment: six icon names", "T187, T43", "swaps",
                        note="Each has an appearance; the legacy file leaves them to the viewer")
    csv = doc.embed_file("chart-data.csv", b"category,value\nA,80\nB,55\nC,90\nD,35\nE,70\nF,50\n", "text/csv",
                         "Data behind the bar chart", rel="Data")
    clip = ap_form(doc, 16, 22, "%s 1.6 w 1 J %s S" % (pal.RG("ink"), "8 2 m 3 2 3 6 3 8 c 3 18 l 3 21 13 21 13 18 c 13 7 l 13 5 7 5 7 7 c 7 16 l"))
    markup(p, "FileAttachment", [x + 6, y + h - 30, x + 22, y + h - 8], "Attached CSV file", clip, FS=csv,
           Name=Name.Paperclip, C=doc.rgb("ink"))
    glyphs = {
        "GraphPushPin": "%s 2 2 3 8 re 7 2 3 12 re 12 2 3 16 re f %s 13 17 m 13 21 l S",
        "PaperclipTag": "%s 2 4 12 12 re f %s 1 w 4 10 m 12 10 l S",
        "Graph": "%s 2 2 3 6 re 7 2 3 10 re 12 2 3 14 re f %s 0.8 w 1 1 m 16 1 l S",
        "PushPin": "%s %s f %s 1.5 w 8 2 m 8 10 l S",
        "Tag": "%s 2 6 m 10 6 l 15 11 l 10 16 l 2 16 l h f %s 1 w 4 11 m 6 11 l S",
    }
    for i, nm in enumerate(["GraphPushPin", "PaperclipTag", "Graph", "PushPin", "Tag"]):
        cx = x + 30 + i * (w - 34) / 5
        role = HUES[i]
        g = glyphs[nm]
        if nm == "PushPin":
            body = g % (pal.rg(role), circle_path(8, 15, 5), pal.RG(role))
        else:
            body = g % (pal.rg(role), pal.RG("ink"))
        markup(p, "FileAttachment", [cx, y + h - 30, cx + 16, y + h - 8], "Attachment icon " + nm,
               ap_form(doc, 16, 22, body), FS=csv, Name=Name("/" + nm), C=doc.rgb(role))

    # 9 Watermark
    x, y, w, h = p.tile(t[8], "Watermark with FixedPrint", "T193, T194", "swaps")
    rect = [x + 2, y + 2, x + w - 2, y + h - 2]
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    apb = "/GSwm gs BT /SansBold 30 Tf %s 0.8 0.6 -0.6 0.8 %s %s Tm %s Tj ET" % (pal.rg("red"), n(rw * 0.12), n(rh * 0.15), bold.enc("DRAFT"))
    markup(p, "Watermark", rect, "Draft watermark", ap_form(doc, rw, rh, apb, [bold], gstates={"/GSwm": res.gstate(ca=0.25)}),
           FixedPrint=Dictionary(Type=Name.FixedPrint, Matrix=Array([1, 0, 0, 1, 0, 0]), H=0, V=0))

    # 10 Printer's marks
    x, y, w, h = p.tile(t[9], "PrinterMark: colour bar and target", "T398, T399", "stays",
                        note="Print production marks keep their true colours")
    bar_w = (w - 8) / 8
    cm = [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1), (1, 1, 0, 0), (0, 1, 1, 0), (1, 0, 1, 0), (0.5, 0.5, 0.5, 0.5)]
    apb = " ".join("%s k %s f" % (fmt(c), rect_path(i * bar_w, 0, bar_w, 18)) for i, c in enumerate(cm))
    form = ap_form(doc, w - 8, 18, apb)
    form.MarkStyle = String("Colour bar")
    form.Colorants = Dictionary()
    markup(p, "PrinterMark", [x + 4, y + h - 26, x + w - 4, y + h - 8], "CMYK colour bar", form, MN=Name.ColorBar, F=4)
    tgt = ap_form(doc, 30, 30, "0 0 0 1 K 0.6 w %s S 15 0 m 15 30 l 0 15 m 30 15 l S %s S" % (circle_path(15, 15, 10), circle_path(15, 15, 5)))
    tgt.MarkStyle = String("Registration target")
    markup(p, "PrinterMark", [x + w / 2 - 15, y + 10, x + w / 2 + 15, y + 40], "Registration target", tgt,
           MN=Name.RegistrationTarget, F=4)

    # 11 PDF 2.0 annotation extras: BM and ca, plus rollover and down appearances
    x, y, w, h = p.tile(t[10], "Annotation BM and ca (PDF 2.0), R and D", "T166, T170", "swaps",
                        note="Multiply square; half-opaque circle; hover and press change the third")
    q = (w - 12) / 3
    sq = [x + 2, y + 10, x + 2 + q, y + h - 10]
    rw, rh = sq[2] - sq[0], sq[3] - sq[1]
    markup(p, "Square", sq, "Square blended with Multiply", ap_form(doc, rw, rh, "%s %s f" % (pal.rg("orange"), rect_path(0, 0, rw, rh))),
           C=doc.rgb("orange"), IC=doc.rgb("orange"), BM=Name.Multiply)
    ci = [x + 6 + q, y + 10, x + 6 + 2 * q, y + h - 10]
    markup(p, "Circle", ci, "Half-opaque circle", ap_form(doc, rw, rh, "%s %s f" % (pal.rg("blue"), circle_path(rw / 2, rh / 2, min(rw, rh) / 2))),
           C=doc.rgb("blue"), IC=doc.rgb("blue"), ca=0.5, CA=1)
    rd = [x + 10 + 2 * q, y + 10, x + w - 2, y + h - 10]
    states = {r: ap_form(doc, rw, rh, "%s %s f" % (pal.rg(r), round_rect_path(0, 0, rw, rh, 6))) for r in ("green", "yellow", "red")}
    markup(p, "Square", rd, "Square with rollover and down appearances",
           Dictionary(N=states["green"], R=states["yellow"], D=states["red"]), C=doc.rgb("green"), IC=doc.rgb("green"))
    stripe = " ".join(rect_path(x + i * 8, y + 4, 4, h - 8) for i in range(int(w / 8)))
    p.figure("%s %s f" % (pal.rg("ink"), stripe), "Stripes behind the blended annotations.")

    # 12 Trap network (deprecated) — must be last in Annots
    x, y, w, h = p.tile(t[11], "TrapNet (deprecated in PDF 2.0)", "T403, T404", "stays", note="Print trapping; keeps its colours")
    p.figure("%s %s f %s %s f" % ("0 0.8 0.9 0 k", rect_path(x + 10, y + 10, w / 2, h - 20), "0.8 0 0 0 k",
                                   rect_path(x + w / 2, y + 20, w / 2 - 10, h - 40)), "Two process-colour panels that meet.")
    trap = ap_form(doc, w, h, "0.8 0.8 0.9 0 K 1.2 w %s %s m %s %s l S" % (n(w / 2), n(20), n(w / 2), n(h - 20)))
    trap.PCM = Name.DeviceCMYK
    # A trap network annotation must come last in the page's Annots array.
    p.annot(Dictionary(Type=Name.Annot, Subtype=Name.TrapNet, Rect=Array([x, y, x + w, y + h]), F=4,
                       LastModified=DATE, Contents=String("Trap network"), AP=Dictionary(N=Dictionary(Trap=trap)),
                       AS=Name("/Trap")),
            tag="Annot", alt="Trap network")
    return p
