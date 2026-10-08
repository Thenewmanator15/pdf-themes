"""Pages for page-level and document-level objects: page boxes, thumbnails, transitions,
threads, viewports and measurement, navigation steps, document parts, a rotated page and a
page with a user unit."""
import math

import numpy as np
from pikepdf import Array, Dictionary, Name, String

from .core import MARGIN, H, W, Page, circle_path, n, poly_path, rect_path, round_rect_path
from .pages_annots import ap_form, markup
from .pages_interactive import label, link
from .palette import HUES

BLEED = 18


def island_path(cx, cy, r, seed=3):
    rng = np.random.default_rng(seed)
    pts = []
    k = 28
    bumps = rng.uniform(0.75, 1.15, k)
    for i in range(k):
        a = 2 * math.pi * i / k
        rr = r * bumps[i] * (1 + 0.15 * math.sin(3 * a))
        pts.append((cx + rr * math.cos(a), cy + rr * 0.7 * math.sin(a)))
    return poly_path(pts, close=True)


def thumbnail(doc, page_rects):
    """An Indexed thumbnail of the page: its colours come from the palette, so a theme swaps the table."""
    pal = doc.pal
    roles = ["paper", "tile", "rule", "ink", "accent"]
    tw, th = 60, 85
    a = np.zeros((th, tw), np.uint8)
    for (x, y, w, h) in page_rects:
        x0, x1 = int(x / W * tw), int((x + w) / W * tw)
        y0, y1 = int((H - y - h) / H * th), int((H - y) / H * th)
        a[y0:y1, x0:x1] = 1
        a[y0, x0:x1] = a[y1 - 1, x0:x1] = 2
        a[y0:y1, x0] = a[y0:y1, x1 - 1] = 2
    a[4:7, 5:35] = 3
    a[8:9, 5:50] = 2
    lookup = bytes(int(round(c * 255)) for r in roles for c in pal.rgb(r))
    return doc.stream(a.tobytes(), Width=tw, Height=th, BitsPerComponent=8,
                      ColorSpace=Array([Name.Indexed, Name.DeviceRGB, len(roles) - 1, String(lookup)]))


def page_navigation(doc, res):
    trim = (0, 0, W, H)
    media = (-BLEED, -BLEED, W + BLEED, H + BLEED)
    p = Page(doc, "Page boxes, thumbnails and navigation",
             "This page has a bleed: its MediaBox is 18 pt larger than its TrimBox on every side. Box guide colours "
             "(BoxColorInfo), the thumbnail, transitions, article threads, measurement viewports and navigation steps "
             "are all here; most show only in a viewer's own panels or modes.", mediabox=media)
    pal = p.pal
    t = p.grid(3, 4)
    p.obj.CropBox = Array(list(media))
    p.obj.BleedBox = Array(list(media))
    p.obj.TrimBox = Array(list(trim))
    p.obj.ArtBox = Array([MARGIN - 4, 40, W - MARGIN + 4, H - 40])
    style = lambda role, dash=None: Dictionary(C=doc.rgb(role), W=1, S=Name.D if dash else Name.S,
                                               **({"D": Array(dash)} if dash else {}))
    p.obj.BoxColorInfo = Dictionary(CropBox=style("ink"), BleedBox=style("red", [3, 2]), TrimBox=style("green"),
                                    ArtBox=style("accent", [1, 2]))
    # trim marks in the bleed, as page content
    marks = []
    for cx, cy in [(0, 0), (W, 0), (0, H), (W, H)]:
        dx = -1 if cx == 0 else 1
        dy = -1 if cy == 0 else 1
        marks.append("%s %s m %s %s l %s %s m %s %s l" % (n(cx + dx * 4), n(cy), n(cx + dx * 16), n(cy),
                                                        n(cx), n(cy + dy * 4), n(cx), n(cy + dy * 16)))
    p.artifact("%s 0.4 w %s S" % (pal.RG("ink"), " ".join(marks)), "Layout")

    x, y, w, h = p.tile(t[0], "Page boxes and BoxColorInfo", "T31, T396, T397", "viewer",
                        note="Box guide colours are viewer chrome")
    for i, (nm, role) in enumerate([("CropBox", "ink"), ("BleedBox", "red"), ("TrimBox", "green"), ("ArtBox", "accent")]):
        yy = y + h - 12 - i * 16
        p.figure("%s 1.2 w %s %s m %s %s l S" % (pal.RG(role), n(x + 6), n(yy + 2), n(x + 30), n(yy + 2)), nm + " guide colour")
        p.text(x + 36, yy, nm, size=7)

    x, y, w, h = p.tile(t[1], "Thumbnail: Thumb", "T31", "swaps", note="An Indexed image, so its table swaps")
    p.obj.Thumb = thumbnail(doc, t)
    th = h - 6
    tw_ = th * 60 / 85
    p.use("XObject", "ImThumb", doc.stream(p.obj.Thumb.read_raw_bytes(), Type=Name.XObject, Subtype=Name.Image,
                                           Width=60, Height=85, BitsPerComponent=8, ColorSpace=p.obj.Thumb.ColorSpace))
    p.figure("q %s 0 0 %s %s %s cm /ImThumb Do Q %s 0.5 w %s S" % (n(tw_), n(th), n(x + (w - tw_) / 2), n(y + 2), pal.RG("rule"),
                                                                    rect_path(x + (w - tw_) / 2, y + 2, tw_, th)),
             "The page's own thumbnail image.")

    x, y, w, h = p.tile(t[2], "Transition and display time", "T31, T164", "viewer", note="Seen in full-screen mode")
    p.obj.Trans = Dictionary(Type=Name.Trans, S=Name.Wipe, D=0.8, Di=90)
    p.obj.Dur = 30
    p.para(x + 2, y + h - 6, "Trans: Wipe, 0.8 s, from the bottom. Dur: 30 s before the next page in full-screen mode.",
           w - 4, size=6.8)

    x, y, w, h = p.tile(t[3], "Article thread: beads", "T162, T163", "viewer", note="Two beads here, two on the next page")
    doc.thread_rects.append((p, [x + 4, y + h / 2, x + w - 4, y + h - 4]))
    doc.thread_rects.append((p, [x + 4, y + 4, x + w - 4, y + h / 2 - 4]))
    p.para(x + 4, y + h - 10, "Bead one: an article starts here and continues below.", w - 8, size=6.8)
    p.para(x + 4, y + h / 2 - 10, "Bead two: then on to the rotated page.", w - 8, size=6.8)

    x, y, w, h = p.tile(t[4], "Viewport with a scale: Measure RL", "T265, T266, T267, T268", "swaps",
                        note="Measuring tools read 1 cm on the bar as 1 m")
    bar = (x + 8, y + h / 2 - 4, w - 16, 8)
    cm = 72 / 2.54
    body = ["%s %s f" % (pal.rg("ink" if i % 2 == 0 else "paper"), rect_path(bar[0] + i * cm, bar[1], cm, bar[3]))
            for i in range(int(bar[2] / cm))]
    body.append("%s 0.6 w %s S" % (pal.RG("ink"), rect_path(bar[0], bar[1], int(bar[2] / cm) * cm, bar[3])))
    p.figure(" ".join(body), "A scale bar in centimetre steps.")
    for i in range(int(bar[2] / cm) + 1):
        p.text(bar[0] + i * cm, bar[1] - 9, "%d m" % i, size=5.5, role="muted", tag="Caption", align="center")
    vp = [Dictionary(Type=Name.Viewport, BBox=Array([x, y, x + w, y + h]), Name=String("Scale bar"),
                     Measure=Dictionary(Type=Name.Measure, Subtype=Name.RL, R=String("1 cm = 1 m"),
                                        X=Array([Dictionary(Type=Name.NumberFormat, U=String("m"), C=round(2.54 / 72, 6), D=100)]),
                                        D=Array([Dictionary(Type=Name.NumberFormat, U=String("m"), C=1, D=100)]),
                                        A=Array([Dictionary(Type=Name.NumberFormat, U=String("sq m"), C=1, D=100)])))]

    x, y, w, h = p.tile(t[5], "Geospatial viewport: GEO, PROJCS, PtData", "T265, T269, T270, T271, T272", "swaps",
                        note="A made-up island at 50 N, 30 W; map colours swap")
    p.figure("%s %s f %s %s f %s 0.8 w %s S" % (pal.rg("blue"), rect_path(x + 4, y + 4, w - 8, h - 8), pal.rg("green"),
                                                 island_path(x + w / 2, y + h / 2, min(w, h) * 0.38), pal.RG("ink"),
                                                 island_path(x + w / 2, y + h / 2, min(w, h) * 0.38)),
             "A map of an island in the sea.")
    p.text(x + w - 8, y + 8, "50.0 N 30.0 W", size=5.5, role="paper", tag="Caption", align="right")
    vp.append(Dictionary(Type=Name.Viewport, BBox=Array([x + 4, y + 4, x + w - 4, y + h - 4]), Name=String("Island map"),
                         Measure=Dictionary(Type=Name.Measure, Subtype=Name.GEO,
                                            Bounds=Array([0, 0, 0, 1, 1, 1, 1, 0]),
                                            GCS=Dictionary(Type=Name.GEOGCS, EPSG=4326),
                                            GPTS=Array([50.0, -30.1, 50.1, -30.1, 50.1, -30.0, 50.0, -30.0]),
                                            LPTS=Array([0, 0, 0, 1, 1, 1, 1, 0]),
                                            PDU=Array([Name.KM, Name.SQKM, Name.DEG]),
                                            DCS=Dictionary(Type=Name.PROJCS, EPSG=32626)),
                         PtData=Dictionary(Type=Name.PtData, Subtype=Name.Cloud,
                                           Names=Array([Name.LAT, Name.LON, Name.ALT]),
                                           XPTS=Array([Array([50.05, -30.05, 120]), Array([50.07, -30.02, 35])]))))
    p.obj.VP = Array(vp)

    x, y, w, h = p.tile(t[6], "Navigation steps: PresSteps", "T165", "viewer", note="Arrow keys step through layers")
    hidden = doc.ocgs.get("Hidden by default")
    shown = doc.ocgs.get("Shown by default")
    step2 = doc.pdf.make_indirect(Dictionary(Type=Name.NavNode,
                                             PA=Dictionary(S=Name.SetOCGState, State=Array([Name.OFF, hidden]))))
    step1 = doc.pdf.make_indirect(Dictionary(Type=Name.NavNode, Next=step2,
                                             NA=Dictionary(S=Name.SetOCGState, State=Array([Name.ON, hidden]))))
    step2.Prev = step1
    p.obj.PresSteps = step1
    p.para(x + 2, y + h - 6, "Step one shows the hidden layer on page 13; step back hides it again.", w - 4, size=6.8)

    x, y, w, h = p.tile(t[7], "Document parts and GoToDp", "T206, T408, T409", "swaps",
                        note="Parts: content pages and appendix")
    doc.want_dparts = True
    ly = y + h / 2
    tw = label(p, x + 6, ly, "Go to the appendix part")
    doc.gotodp_links.append(link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.GoToDp),
                                 contents="Go to the appendix document part"))

    x, y, w, h = p.tile(t[8], "Associated file on a page: AF", "T31, T43, T45", "stays")
    data = ("tile,object\n" + "\n".join("%d,%s" % (i + 1, c["object"]) for i, c in enumerate(doc.coverage[-8:]))).encode()
    af = doc.embed_file("page-20-tiles.csv", data, "text/csv", "The tiles on this page", rel="Supplement")
    p.obj.AF = Array([af])
    p.para(x + 2, y + h - 6, "This page carries a CSV of its own tiles, with AFRelationship Supplement.", w - 4, size=6.8)

    x, y, w, h = p.tile(t[9], "Outlines with colour and style", "T151, T152", "swaps",
                        note="Bookmark colours are shown in the panel")
    for i, (txt, role, flags) in enumerate([("Plain", "ink", 0), ("Italic", "accent", 1), ("Bold", "red", 2),
                                            ("Bold italic", "green", 3)]):
        yy = y + h - 12 - i * 14
        font = "SansBold" if flags & 2 else "Sans"
        p.text(x + 8, yy, "› " + txt, size=7.5, role=role, font=font)

    x, y, w, h = p.tile(t[10], "Page labels", "T161", "viewer", note="Pages show as 1 to n, then A-1 on")
    p.para(x + 2, y + h - 6, "The appendix pages are labelled A-1, A-2 and so on. Viewers show the label in the page box.",
           w - 4, size=6.8)

    x, y, w, h = p.tile(t[11], "Page output intent, by reference", "T31, T401, T402", "stays",
                        note="PDF 2.0: a page names its own condition, here by profile reference")
    p.obj.OutputIntents = Array([Dictionary(Type=Name.OutputIntent, S=Name.GTS_PDFX,
                                            OutputCondition=String("Coated FOGRA39"),
                                            OutputConditionIdentifier=String("FOGRA39"),
                                            RegistryName=String("http://www.color.org"),
                                            DestOutputProfileRef=Dictionary(
                                                ProfileName=String("Coated FOGRA39 (ISO 12647-2:2004)"),
                                                ICCVersion=String("2.1"), ProfileCS=String("CMYK"),
                                                URLs=Array([Dictionary(FS=Name.URL, F=String(
                                                    "https://www.color.org/registry/Coated_Fogra39L_VIGC_300.xalter"))])))])
    p.para(x + 2, y + h - 6, "This page's output intent names FOGRA39 by reference instead of embedding the profile.",
           w - 4, size=6.8)
    return p


def page_rotated(doc, res):
    p = Page(doc, "Rotated page: Rotate 90",
             "The page is stored upright and turned a quarter turn by the viewer. Annotations with NoRotate stay "
             "upright, and NoZoom keeps their size.")
    pal = p.pal
    p.obj.Rotate = 90
    t = p.grid(2, 2, heights=[300, 300])
    x, y, w, h = p.tile(t[0], "Content on a rotated page", "T31", "swaps")
    p.figure("%s %s f %s %s f" % (pal.rg("accent"), poly_path([(x + 20, y + 20), (x + w - 20, y + h / 2), (x + 20, y + h - 20)], close=True),
                                  pal.rg("yellow"), circle_path(x + w * 0.35, y + h / 2, 18)), "A blue triangle with a yellow dot.")
    x, y, w, h = p.tile(t[1], "NoRotate and NoZoom flags", "T167", "viewer")
    icon = ap_form(doc, 24, 24, "%s %s 1 w %s B %s 1.2 w 5 16 m 19 16 l 5 12 m 19 12 l S" % (
        pal.rg("yellow"), pal.RG("ink"), round_rect_path(1, 1, 22, 22, 3), pal.RG("ink")))
    markup(p, "Text", [x + 20, y + h - 60, x + 44, y + h - 36], "Note with NoRotate", icon, C=doc.rgb("yellow"),
           Name=Name.Note, F=4 | 16)
    markup(p, "Text", [x + 80, y + h - 60, x + 104, y + h - 36], "Note with NoRotate and NoZoom", icon,
           C=doc.rgb("yellow"), Name=Name.Note, F=4 | 8 | 16)
    x, y, w, h = p.tile(t[2], "Article thread continues", "T163", "viewer")
    doc.thread_rects.append((p, [x + 4, y + 4, x + w - 4, y + h - 4]))
    p.para(x + 4, y + h - 10, "Bead three: the article continues on this rotated page and ends in the next box.", w - 8, size=7)
    x, y, w, h = p.tile(t[3], "Last bead", "T163", "viewer")
    doc.thread_rects.append((p, [x + 4, y + 4, x + w - 4, y + h - 4]))
    p.para(x + 4, y + h - 10, "Bead four: the end of the article.", w - 8, size=7)
    return p


def page_userunit(doc, res):
    p = Page(doc, "", "", mediabox=(0, 0, W / 2, H / 2))
    pal = p.pal
    p.obj.UserUnit = 2.0
    # Draw at half scale: everything in this page's units is twice as big on screen.
    f = p.font("SansBold")
    p.text(MARGIN / 2, H / 2 - 26, "%d  UserUnit 2" % p.number, size=8, font="SansBold", tag="H1")
    p.para(MARGIN / 2, H / 2 - 36, "This page's MediaBox is half of A4, and UserUnit 2 makes each unit 1/36 inch, "
           "so it shows at A4 size. Content, annotations and line widths all scale.", W / 2 - MARGIN, size=4,
           role="muted")
    x, y, w, h = MARGIN / 2, 60, W / 2 - MARGIN, H / 2 - 110
    doc.cover("UserUnit page", "T31", p.number, "swaps")
    p.artifact("%s %s 0.3 w %s B" % (pal.rg("tile"), pal.RG("rule"), round_rect_path(x, y, w, h, 2)))
    p.figure("%s %s f %s 0.5 w %s S" % (pal.rg("teal"), circle_path(x + w / 2, y + h / 2, h * 0.3), pal.RG("ink"),
                                        rect_path(x + 10, y + 10, w - 20, h - 20)), "A teal disc in a box.")
    markup(p, "Square", [x + 6, y + 6, x + 40, y + 30], "Square annotation on a UserUnit page",
           ap_form(doc, 34, 24, "%s 1 w %s S" % (pal.RG("red"), rect_path(0.5, 0.5, 33, 23))), C=doc.rgb("red"))
    return p
