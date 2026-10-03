"""A test document that carries colour in every way PDF allows.

build(LIGHT) and build(DARK) give two builds of one six-page document that
draw the same shapes and differ only in paint: the pair merge() takes. Each
page says what it covers, so a rendering can be checked by eye as well.

  1 Colour spaces   DeviceGray, DeviceRGB, DeviceCMYK, CalGray, CalRGB, Lab,
                    ICCBased, Indexed, Separation, DeviceN; a colour whose
                    space changes between builds; the initial colour `cs`
                    sets with no `sc`; stroke colours; text render modes
  2 Gradients       function-based, axial and radial shadings and all four
                    mesh types; type 0, 2, 3 and 4 functions and arrays of
                    functions; coloured and uncoloured tiling patterns;
                    shading patterns for fills, strokes and text
  3 Transparency    fill and stroke opacity, blend modes, luminosity and
                    alpha soft masks, a knockout group, a graphics state only
                    one build sets; forms nested, reused and inheriting the
                    caller's colour
  4 Images          Indexed at 1, 4 and 8 bits, Gray, RGB with few colours,
                    photos, a soft mask, a colour-key mask, stencil masks,
                    inline images, JPEG, a Decode array, 16-bit samples
  5 Annotations     Square, Circle, Line, Polygon, Ink, Highlight, FreeText,
                    Text with Popup, Link, a text field and a check box
  6 Type 3 fonts    coloured and uncoloured glyphs; optional content; marked
                    artifacts; structure attributes and a class map
  Document          AcroForm, coloured bookmarks, a page thumbnail and
                    BoxColorInfo

Run it to write out/corpus-light.pdf and out/corpus-dark.pdf.
"""

from __future__ import annotations

import io
import math
import os
import sys
import zlib

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name, String
from PIL import Image, ImageCms, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pdfthemes import colour as C  # noqa: E402

W, H = 595, 842
D65 = [0.9505, 1.0, 1.089]
SRGB_MATRIX = [0.4124, 0.2126, 0.0193, 0.3576, 0.7152, 0.1192, 0.1805, 0.0722, 0.9505]

LIGHT = {
    "mode": "light", "paper": "#FFFFFF",
    "heading": "#111114", "ink": "#1C1C21", "muted": "#5A5A66", "card": "#F1F1F5", "rule": "#C9C9D2",
    "accent": "#6B2AC0", "blue": "#0B6E99", "orange": "#B4501E", "green": "#2E7D32", "pink": "#C2185B",
    "yellow": "#F2C230", "white": "#FFFFFF",
    "tint": 1.0, "inks": (0.8, 0.2), "teal": (0.85, 0.1, 0.45, 0.2),
    "alpha": 0.6, "blend": "/Multiply", "highlight_blend": "/Multiply", "annot_alpha": 0.9,
}
DARK = {
    "mode": "dark", "paper": "#18181C",
    "heading": "#F4F4F7", "ink": "#E8E8EE", "muted": "#A6A6B3", "card": "#26262D", "rule": "#4B4B57",
    "accent": "#B38CFF", "blue": "#5CC2EE", "orange": "#FF9C66", "green": "#7FD483", "pink": "#FF7AAE",
    "yellow": "#4D3D00", "white": "#1C1C21",
    "tint": 0.55, "inks": (0.3, 0.9), "teal": (0.45, 0.0, 0.2, 0.0),
    "alpha": 0.75, "blend": "/Screen", "highlight_blend": "/Screen", "annot_alpha": 0.8,
}


# ── Numbers and colours, kept on the 8-bit grid an Indexed palette uses ──────

def num(v, digits=6):
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def rgb255(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def u8(k):
    """k/255, written so that reading it back never lands below step k:
    some engines truncate rather than round."""
    return num(math.ceil(k / 255 * 1e8) / 1e8, 8)


def rgb(h):
    return " ".join(u8(v) for v in rgb255(h))


def rgbf(h):
    return [math.ceil(v / 255 * 1e8) / 1e8 for v in rgb255(h)]


def gray(h):
    r, g, b = rgb255(h)
    return u8(round(0.2126 * r + 0.7152 * g + 0.0722 * b))


def cmyk(h):
    r, g, b = (v / 255 for v in rgb255(h))
    k = 1 - max(r, g, b)
    c, m, y = (0.0, 0.0, 0.0) if k >= 1 else ((1 - x - k) / (1 - k) for x in (r, g, b))
    return " ".join(u8(round(v * 255)) for v in (c, m, y, k))


def snap(v, lo, hi):
    v = min(max(v, lo), hi)
    return lo + round((v - lo) / (hi - lo) * 255) * (hi - lo) / 255


def lab(h):
    r, g, b = (C.srgb_to_linear(v / 255) for v in rgb255(h))
    X = 0.4124 * r + 0.3576 * g + 0.1805 * b
    Y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    Z = 0.0193 * r + 0.1192 * g + 0.9505 * b

    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(X / D65[0]), f(Y / D65[1]), f(Z / D65[2])
    L, a, bb = 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)
    L = math.ceil(round(L / 100 * 255) * 100 / 255 * 1e8) / 1e8
    return " ".join(num(v, 8) for v in (L, round(a), round(bb)))


def esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text(font, size, x, y, s, extra=""):
    return f"BT /{font} {size} Tf {extra}{num(x)} {num(y)} Td ({esc(s)}) Tj ET\n"


def circle(cx, cy, r):
    k = 0.5523 * r
    return (f"{num(cx + r)} {num(cy)} m {num(cx + r)} {num(cy + k)} {num(cx + k)} {num(cy + r)} {num(cx)} {num(cy + r)} c "
            f"{num(cx - k)} {num(cy + r)} {num(cx - r)} {num(cy + k)} {num(cx - r)} {num(cy)} c "
            f"{num(cx - r)} {num(cy - k)} {num(cx - k)} {num(cy - r)} {num(cx)} {num(cy - r)} c "
            f"{num(cx + k)} {num(cy - r)} {num(cx + r)} {num(cy - k)} {num(cx + r)} {num(cy)} c h ")


def star(cx, cy, r_out, r_in, points=5):
    pts = []
    for k in range(points * 2):
        r = r_out if k % 2 == 0 else r_in
        a = math.pi / 2 + k * math.pi / points
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return f"{num(pts[0][0])} {num(pts[0][1])} m " + " ".join(f"{num(x)} {num(y)} l" for x, y in pts[1:]) + " h "


def label(c, x, y, s, size=8):
    return f"{rgb(c['muted'])} rg " + text("F1", size, x, y, s)


def heading(c, number, title, subtitle):
    return (f"{gray(c['heading'])} g " + text("F2", 20, 50, 796, f"{number}  {title}") +
            f"{rgb(c['muted'])} rg " + text("F1", 9.5, 50, 778, subtitle))


def footer(c, n):
    return (f"/Artifact << /Type /Pagination >> BDC {rgb(c['muted'])} rg " +
            text("F1", 8, 50, 30, f"pdf-themes test document, page {n} of 6") + "EMC\n")


# ── Objects shared by the pages of one build ─────────────────────────────────

class Shared:
    def __init__(self, pdf, c):
        self.pdf, self.c = pdf, c
        self.helv = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica,
                                                 Encoding=Name.WinAnsiEncoding))
        self.bold = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1,
                                                 BaseFont=Name("/Helvetica-Bold"), Encoding=Name.WinAnsiEncoding))
        self.zadb = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.ZapfDingbats))
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        icc = pdf.make_stream(profile)
        icc.N, icc.Alternate = 3, Name.DeviceRGB
        self.icc = pdf.make_indirect(Array([Name.ICCBased, icc]))

    def fonts(self):
        return Dictionary({"/F1": self.helv, "/F2": self.bold})

    def stream(self, data, **keys):
        s = self.pdf.make_stream(data if isinstance(data, bytes) else data.encode("latin-1"))
        for k, v in keys.items():
            s[f"/{k}"] = v
        return self.pdf.make_indirect(s)

    def form(self, content, bbox, resources=None, **keys):
        return self.stream(content, Type=Name.XObject, Subtype=Name.Form, BBox=Array(bbox),
                           Resources=resources if resources is not None else Dictionary(), **keys)

    def image(self, data, width, height, space, bpc=8, compress=True, **keys):
        s = self.stream(zlib.compress(data, 9) if compress else data, Type=Name.XObject, Subtype=Name.Image,
                        Width=width, Height=height, BitsPerComponent=bpc, **keys)
        if space is not None:
            s.ColorSpace = space
        if compress:
            s.Filter = Name.FlateDecode
        return s


# ── Page 1: colour spaces and text ───────────────────────────────────────────

def type2(c0, c1, n=1):
    return Dictionary(FunctionType=2, Domain=Array([0, 1]), C0=Array(c0), C1=Array(c1), N=n)


def page_spaces(sh):
    c = sh.c
    teal = sh.c["teal"]
    spaces = Dictionary({
        "/CalG": Array([Name.CalGray, Dictionary(WhitePoint=Array(D65), Gamma=2.2)]),
        "/CalR": Array([Name.CalRGB, Dictionary(WhitePoint=Array(D65), Gamma=Array([2.2, 2.2, 2.2]),
                                                Matrix=Array(SRGB_MATRIX))]),
        "/Lab": Array([Name.Lab, Dictionary(WhitePoint=Array(D65), Range=Array([-100, 100, -100, 100]))]),
        "/ICC": sh.icc,
        "/Idx": Array([Name.Indexed, Name.DeviceRGB, 3,
                       String(bytes(v for h in ("white", "accent", "blue", "orange") for v in rgb255(c[h])))]),
        "/Spot": Array([Name.Separation, Name("/BrandPurple"), Name.DeviceCMYK,
                        type2([0, 0, 0, 0], [0.55, 0.85, 0, 0.1])]),
        "/Spot2": Array([Name.Separation, Name("/BrandTeal"), Name.DeviceCMYK, type2([0, 0, 0, 0], list(teal))]),
        "/DN": Array([Name.DeviceN, Array([Name.Cyan, Name("/Gold")]), Name.DeviceCMYK,
                      sh.stream("{ dup 0.25 mul exch dup 0.9 mul exch 0.05 mul }", FunctionType=4,
                                Domain=Array([0, 1, 0, 1]), Range=Array([0, 1, 0, 1, 0, 1, 0, 1]))]),
    })
    clip_shading = Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([440, 0, 540, 0]),
                              Function=type2(rgbf(c["accent"]), rgbf(c["blue"])), Extend=Array([True, True]))
    res = Dictionary(Font=sh.fonts(), ColorSpace=spaces, Shading=Dictionary({"/ShClip": clip_shading}))
    inks = " ".join(u8(round(v * 255)) for v in c["inks"])
    swatches = [
        (f"{gray(c['accent'])} g", "DeviceGray (g)"),
        (f"{rgb(c['accent'])} rg", "DeviceRGB (rg)"),
        (f"{cmyk(c['accent'])} k", "DeviceCMYK (k)"),
        (f"/CalG cs {gray(c['blue'])} sc", "CalGray"),
        (f"/CalR cs {rgb(c['blue'])} sc", "CalRGB"),
        (f"/Lab cs {lab(c['blue'])} sc", "Lab"),
        (f"/ICC cs {rgb(c['orange'])} scn", "ICCBased, sRGB profile"),
        ("/Idx cs 1 sc", "Indexed, entry 1"),
        (f"/Spot cs {u8(round(c['tint'] * 255))} scn", "Separation (a spot ink)"),
        (f"/DN cs {inks} scn", "DeviceN (two inks)"),
        (f"{cmyk(c['green'])} k" if c["mode"] == "light" else f"{rgb(c['green'])} rg",
         "CMYK; RGB in the dark build"),
        ("/Spot2 cs", "Initial colour (cs alone)"),
    ]
    out = heading(c, 1, "Colour spaces",
                  "Each box is filled in a different colour space. The label under each box names it.")
    out += f"{rgb(c['card'])} rg 40 420 515 350 re f\n"
    for k, (paint, name) in enumerate(swatches):
        col, row = k % 4, k // 4
        x, y = 58 + col * 124, 680 - row * 110
        out += f"q {paint} {x} {y} 104 60 re f Q\n" + label(c, x, y - 14, name)
    out += f"{rgb(c['ink'])} rg " + text("F2", 11, 50, 395, "Stroke colours")
    strokes = [(f"{gray(c['accent'])} G", "Gray (G)"), (f"{rgb(c['blue'])} RG", "RGB (RG)"),
               (f"{cmyk(c['orange'])} K", "CMYK (K)"), (f"/Lab CS {lab(c['green'])} SC", "Lab (SC)"),
               (f"/DN CS {inks} SCN", "DeviceN (SCN)")]
    for k, (paint, name) in enumerate(strokes):
        x = 75 + k * 104
        out += f"q 4 w {paint} {circle(x, 345, 22)}S Q\n" + label(c, x - 24, 310, name)
    out += f"{rgb(c['ink'])} rg " + text("F2", 11, 50, 275, "Text render modes")
    out += f"{rgb(c['ink'])} rg " + text("F2", 24, 50, 232, "Fill")
    out += f"q 0.8 w {rgb(c['accent'])} RG " + text("F2", 24, 140, 232, "Stroke", "1 Tr ") + "Q\n"
    out += f"q 0.8 w {rgb(c['accent'])} rg {rgb(c['yellow'])} RG " + text("F2", 24, 255, 232, "Both", "2 Tr ") + "Q\n"
    out += "q " + text("F2", 30, 440, 230, "Clip", "7 Tr ") + "/ShClip sh Q\n"
    for x, name in ((50, "Fill (0 Tr)"), (140, "Stroke (1 Tr)"), (255, "Fill and stroke (2 Tr)"),
                    (440, "Clip with a gradient (7 Tr)")):
        out += label(c, x, 214, name)
    out += f"{rgb(c['card'])} rg 50 150 495 40 re f\n"
    out += label(c, 60, 174, "Below is a line of invisible text (3 Tr), the way OCR software lays text over a scan:", 8.5)
    out += f"{rgb(c['ink'])} rg " + text("F1", 11, 60, 158, "This text is invisible but can be selected and searched.", "3 Tr ")
    out += footer(c, 1)
    thumb = Image.new("RGB", (30, 42), c["paper"])
    ImageDraw.Draw(thumb).rectangle([4, 6, 26, 20], fill=c["accent"])
    page = Dictionary(Thumb=sh.image(thumb.tobytes(), 30, 42, Name.DeviceRGB),
                      BoxColorInfo=Dictionary(CropBox=Dictionary(C=Array(rgbf(c["accent"])), W=1, S=Name.S)))
    return out, res, page


# ── Page 2: gradients and patterns ───────────────────────────────────────────

def bits(values_bits):
    """Pack (value, bit count) pairs into bytes, padding at the end."""
    acc, n, out = 0, 0, bytearray()
    for v, b in values_bits:
        acc = (acc << b) | (int(v) & ((1 << b) - 1))
        n += b
        while n >= 8:
            n -= 8
            out.append((acc >> n) & 0xFF)
    if n:
        out.append((acc << (8 - n)) & 0xFF)
    return bytes(out)


def coord(v, lo, hi, b=16):
    return round((v - lo) / (hi - lo) * ((1 << b) - 1))


def page_gradients(sh):
    c = sh.c
    tiles = [(50 + col * 126, 640 - row * 140) for row in range(3) for col in range(4)]
    tw, th = 110, 70
    shadings, patterns = Dictionary(), Dictionary()

    def pattern(shading, name):
        patterns[name] = Dictionary(PatternType=2, Shading=shading, Matrix=Array([1, 0, 0, 1, 0, 0]))

    # a: function-based, a PostScript function of x and y
    x, y = tiles[0]
    r0, g0, b0 = rgbf(c["accent"])
    r1, g1, _ = rgbf(c["blue"])
    ps = f"{{ exch {num(r1 - r0)} mul {num(r0)} add exch {num(g1 - g0)} mul {num(g0)} add {num(b0)} }}"
    shadings["/ShF"] = Dictionary(ShadingType=1, ColorSpace=Name.DeviceRGB, Domain=Array([0, 1, 0, 1]),
                                  Matrix=Array([tw, 0, 0, th, x, y]),
                                  Function=sh.stream(ps, FunctionType=4, Domain=Array([0, 1, 0, 1]),
                                                     Range=Array([0, 1, 0, 1, 0, 1])))
    # b: axial, exponential function
    x, y = tiles[1]
    shadings["/ShA"] = Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, 0, x + tw, 0]),
                                  Function=type2(rgbf(c["orange"]), rgbf(c["yellow"]), 1.4), Extend=Array([True, True]))
    # c: radial in a pattern, stitching function, a Background outside the circles
    x, y = tiles[2]
    stitch = Dictionary(FunctionType=3, Domain=Array([0, 1]), Bounds=Array([0.5]), Encode=Array([0, 1, 0, 1]),
                        Functions=Array([type2(rgbf(c["accent"]), rgbf(c["pink"])),
                                         type2(rgbf(c["pink"]), rgbf(c["yellow"]))]))
    pattern(Dictionary(ShadingType=3, ColorSpace=Name.DeviceRGB, Background=Array(rgbf(c["card"])),
                       Coords=Array([x + 55, y + 35, 0, x + 55, y + 35, 30]), Function=stitch,
                       Extend=Array([False, False])), "/PRad")
    # d: axial, sampled function
    x, y = tiles[3]
    samples = bytes(v for h in ("card", "blue", "green", "orange") for v in rgb255(c[h]))
    shadings["/ShS"] = Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, 0, x + tw, 0]),
                                  Function=sh.stream(samples, FunctionType=0, Domain=Array([0, 1]),
                                                     Range=Array([0, 1, 0, 1, 0, 1]), Size=Array([4]),
                                                     BitsPerSample=8))
    # e: free-form triangle mesh in a pattern, a colour per vertex
    x, y = tiles[4]
    box = [x, x + tw, y, y + th]
    corners = [(x, y, "accent"), (x + tw, y, "blue"), (x, y + th, "yellow"), (x + tw, y + th, "pink")]
    data = b""
    for k, (vx, vy, h) in enumerate(corners):
        flag = 0 if k < 3 else 1
        data += bits([(flag, 8), (coord(vx, *box[:2]), 16), (coord(vy, *box[2:]), 16)] +
                     [(v, 8) for v in rgb255(c[h])])
    mesh = sh.stream(data, ShadingType=4, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16, BitsPerComponent=8,
                     BitsPerFlag=8, Decode=Array(box + [0, 1, 0, 1, 0, 1]))
    patterns["/PMesh"] = Dictionary(PatternType=2, Shading=mesh)
    # f: lattice mesh, three vertices a row
    x, y = tiles[5]
    box = [x, x + tw, y, y + th]
    grid = [("green", "blue", "accent"), ("yellow", "card", "pink")]
    data = b""
    for r, row in enumerate(grid):
        for k, h in enumerate(row):
            data += bits([(coord(x + k * tw / 2, *box[:2]), 16), (coord(y + r * th, *box[2:]), 16)] +
                         [(v, 8) for v in rgb255(c[h])])
    shadings["/ShL"] = sh.stream(data, ShadingType=5, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16,
                                 BitsPerComponent=8, VerticesPerRow=3, Decode=Array(box + [0, 1, 0, 1, 0, 1]))
    # g: Coons patch, colours through a function
    x, y = tiles[6]
    box = [x - 10, x + tw + 10, y - 10, y + th + 10]
    p = [(x, y), (x - 8, y + th / 3), (x + 8, y + 2 * th / 3), (x, y + th), (x + tw / 3, y + th + 8),
         (x + 2 * tw / 3, y + th - 8), (x + tw, y + th), (x + tw + 8, y + 2 * th / 3), (x + tw - 8, y + th / 3),
         (x + tw, y), (x + 2 * tw / 3, y - 8), (x + tw / 3, y + 8)]
    data = bits([(0, 8)] + [v for px, py in p for v in ((coord(px, *box[:2]), 16), (coord(py, *box[2:]), 16))] +
                [(t, 8) for t in (0, 85, 255, 170)])
    shadings["/ShC"] = sh.stream(data, ShadingType=6, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16,
                                 BitsPerComponent=8, BitsPerFlag=8, Decode=Array(box + [0, 1]),
                                 Function=type2(rgbf(c["blue"]), rgbf(c["green"])))
    # h: tensor patch, a colour per corner
    x, y = tiles[7]
    box = [x - 10, x + tw + 10, y - 10, y + th + 10]
    p = [(x, y), (x, y + th / 3), (x, y + 2 * th / 3), (x, y + th), (x + tw / 3, y + th), (x + 2 * tw / 3, y + th),
         (x + tw, y + th), (x + tw, y + 2 * th / 3), (x + tw, y + th / 3), (x + tw, y), (x + 2 * tw / 3, y),
         (x + tw / 3, y), (x + tw / 3 + 15, y + th / 3), (x + tw / 3, y + 2 * th / 3 + 10),
         (x + 2 * tw / 3, y + 2 * th / 3), (x + 2 * tw / 3 - 15, y + th / 3)]
    data = bits([(0, 8)] + [v for px, py in p for v in ((coord(px, *box[:2]), 16), (coord(py, *box[2:]), 16))] +
                [(v, 8) for h in ("pink", "yellow", "blue", "accent") for v in rgb255(c[h])])
    shadings["/ShT"] = sh.stream(data, ShadingType=7, ColorSpace=Name.DeviceRGB, BitsPerCoordinate=16,
                                 BitsPerComponent=8, BitsPerFlag=8, Decode=Array(box + [0, 1, 0, 1, 0, 1]))
    # i: axial, an array of one-output functions
    x, y = tiles[8]
    lo, hi = rgbf(c["green"]), rgbf(c["accent"])
    shadings["/ShArr"] = Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, y, x + tw, y + th]),
                                    Function=Array([type2([a], [b]) for a, b in zip(lo, hi)]))
    # j: coloured tiling pattern
    x, y = tiles[9]
    patterns["/PChk"] = sh.stream(f"{rgb(c['card'])} rg 0 0 20 20 re f {rgb(c['accent'])} rg 0 0 10 10 re f "
                                  f"10 10 10 10 re f", PatternType=1, PaintType=1, TilingType=1,
                                  BBox=Array([0, 0, 20, 20]), XStep=20, YStep=20, Resources=Dictionary(),
                                  Matrix=Array([1, 0, 0, 1, x, y]))
    # k: uncoloured tiling pattern, its colour given where it is used
    x, y = tiles[10]
    patterns["/PHatch"] = sh.stream("1.5 w 0 0 m 10 10 l S -5 5 m 5 15 l S 5 -5 m 15 5 l S", PatternType=1,
                                    PaintType=2, TilingType=1, BBox=Array([0, 0, 10, 10]), XStep=10, YStep=10,
                                    Resources=Dictionary(), Matrix=Array([1, 0, 0, 1, x, y]))
    # l: a shading pattern as stroke paint; m: as text fill
    x, y = tiles[11]
    pattern(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, 0, x + tw, 0]),
                       Function=type2(rgbf(c["orange"]), rgbf(c["pink"])), Extend=Array([True, True])), "/PStroke")
    pattern(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([50, 0, 330, 0]),
                       Function=type2(rgbf(c["accent"]), rgbf(c["orange"])), Extend=Array([True, True])), "/PText")
    res = Dictionary(Font=sh.fonts(), Shading=shadings, Pattern=patterns,
                     ColorSpace=Dictionary({"/PatRGB": Array([Name.Pattern, Name.DeviceRGB])}))
    out = heading(c, 2, "Gradients and patterns",
                  "Every kind of shading, the function types that drive them, and tiling patterns.")
    names = ["Function-based (type 1)", "Axial, exponential", "Radial, stitched, Background",
             "Axial, sampled function", "Triangle mesh (type 4)", "Lattice mesh (type 5)",
             "Coons patch + function", "Tensor patch (type 7)", "Axial, function array",
             "Coloured tiling pattern", "Uncoloured tiling pattern", "Gradient as a stroke"]
    for k, ((x, y), name) in enumerate(zip(tiles, names)):
        rect = f"{x} {y} {tw} {th} re"
        if k == 0:
            out += f"q {rect} W n /ShF sh Q\n"
        elif k == 1:
            out += f"q {rect} W n /ShA sh Q\n"
        elif k == 2:
            out += f"q /Pattern cs /PRad scn {rect} f Q\n"
        elif k == 3:
            out += f"q {rect} W n /ShS sh Q\n"
        elif k == 4:
            out += f"q /Pattern cs /PMesh scn {rect} f Q\n"
        elif k == 5:
            out += "q /ShL sh Q\n"
        elif k == 6:
            out += "q /ShC sh Q\n"
        elif k == 7:
            out += "q /ShT sh Q\n"
        elif k == 8:
            out += f"q {rect} W n /ShArr sh Q\n"
        elif k == 9:
            out += f"q /Pattern cs /PChk scn {rect} f Q\n"
        elif k == 10:
            out += f"q /PatRGB cs {rgb(c['blue'])} /PHatch scn {rect} f Q\n"
        else:
            zig = f"{x + 5} {y + 10} m " + " ".join(f"{x + 5 + s * 20} {y + (60 if s % 2 else 10)} l" for s in range(1, 6))
            out += f"q /Pattern CS /PStroke SCN 7 w 1 j {zig} S Q\n"
        out += label(c, x, y - 14, name)
    out += "q /Pattern cs /PText scn " + text("F2", 40, 50, 160, "Gradient text") + "Q\n"
    out += label(c, 50, 142, "Text filled with a shading pattern")
    out += footer(c, 2)
    return out, res, Dictionary()


# ── Page 3: transparency and forms ───────────────────────────────────────────

def page_transparency(sh):
    c = sh.c
    gs = Dictionary({
        "/GSa": Dictionary(Type=Name.ExtGState, ca=c["alpha"]),
        "/GSm": Dictionary(Type=Name.ExtGState, BM=Name(c["blend"])),
        "/GSs": Dictionary(Type=Name.ExtGState, CA=0.5),
    })
    lum_group = sh.form("/ShM sh", [300, 560, 420, 640],
                        Dictionary(Shading=Dictionary({"/ShM": Dictionary(
                            ShadingType=2, ColorSpace=Name.DeviceGray, Coords=Array([300, 0, 420, 0]),
                            Function=type2([1], [0]))})),
                        Group=Dictionary(S=Name.Transparency, CS=Name.DeviceGray))
    gs["/GSlum"] = Dictionary(Type=Name.ExtGState,
                              SMask=Dictionary(Type=Name.Mask, S=Name.Luminosity, G=lum_group))
    alpha_group = sh.form(f"0 g {circle(490, 600, 40)}{circle(490, 600, 24)}f* /Half gs {circle(490, 600, 14)}f",
                          [440, 550, 540, 650], Dictionary(ExtGState=Dictionary({"/Half": Dictionary(ca=0.35)})),
                          Group=Dictionary(S=Name.Transparency))
    gs["/GSalpha"] = Dictionary(Type=Name.ExtGState, SMask=Dictionary(Type=Name.Mask, S=Name.Alpha, G=alpha_group))
    if c["mode"] == "dark":
        gs["/GSdim"] = Dictionary(Type=Name.ExtGState, ca=0.85)
    knockout = sh.form(f"/H gs {rgb(c['accent'])} rg {circle(40, 40, 30)}f {rgb(c['pink'])} rg {circle(75, 40, 30)}f",
                       [0, 0, 115, 80], Dictionary(ExtGState=Dictionary({"/H": Dictionary(ca=0.6)})),
                       Group=Dictionary(S=Name.Transparency, I=True, K=True))
    dot = sh.form(f"{rgb(c['accent'])} rg {circle(10, 10, 8)}f", [0, 0, 20, 20])
    badge = sh.form(f"{rgb(c['card'])} rg 0 0 130 40 re f 1 w {rgb(c['rule'])} RG 0.5 0.5 129 39 re S "
                    f"q 1 0 0 1 10 10 cm /Dot Do Q {rgb(c['ink'])} rg " + text("F2", 12, 38, 15, "Reused form"),
                    [0, 0, 130, 40], Dictionary(XObject=Dictionary({"/Dot": dot}), Font=sh.fonts()))
    shape = sh.form(star(25, 25, 24, 10) + "f", [0, 0, 50, 50])
    res = Dictionary(Font=sh.fonts(), ExtGState=gs,
                     XObject=Dictionary({"/Knock": knockout, "/Badge": badge, "/Shape": shape}))
    out = heading(c, 3, "Transparency and forms",
                  "Opacity, blend modes, soft masks and groups, then forms that are nested and reused.")
    out += f"q /GSa gs {rgb(c['accent'])} rg {circle(80, 610, 30)}f {rgb(c['blue'])} rg {circle(110, 610, 30)}f " \
           f"{rgb(c['orange'])} rg {circle(95, 585, 30)}f Q\n" + label(c, 50, 540, "Fill opacity (ca)")
    out += f"q {rgb(c['yellow'])} rg 170 570 70 60 re f /GSm gs {rgb(c['blue'])} rg 200 550 70 60 re f Q\n" + \
           label(c, 170, 540, "Blend mode")
    out += f"q /GSlum gs {rgb(c['accent'])} rg 300 560 120 80 re f Q\n" + label(c, 300, 540, "Luminosity soft mask")
    out += f"q /GSalpha gs {rgb(c['blue'])} rg 440 550 100 100 re f Q\n" + label(c, 440, 540, "Alpha soft mask")
    out += f"q /GSs gs 10 w 1 J {rgb(c['accent'])} RG 60 470 m 230 500 l S Q\n" + label(c, 50, 440, "Stroke opacity (CA)")
    out += "q 1 0 0 1 300 440 cm /Knock Do Q\n" + label(c, 300, 425, "Knockout group")
    dim = "/GSdim gs " if c["mode"] == "dark" else ""
    out += f"q {dim}{rgb(c['orange'])} rg 440 450 100 60 re f Q\n" + label(c, 440, 425, "Opacity in dark build only")
    out += f"{rgb(c['ink'])} rg " + text("F2", 11, 50, 380, "Forms")
    for k, (x, y, s) in enumerate(((50, 310, 1.0), (210, 314, 0.8), (340, 300, 1.25))):
        out += f"q {num(s)} 0 0 {num(s)} {x} {y} cm /Badge Do Q\n"
    out += label(c, 50, 285, "One form, drawn three times; it holds a nested form, the dot")
    out += f"q {rgb(c['green'])} rg 1 0 0 1 50 200 cm /Shape Do Q q {rgb(c['pink'])} rg 1 0 0 1 120 200 cm /Shape Do Q\n"
    out += label(c, 50, 185, "A form with no colour of its own: it takes the colour set before it is drawn")
    out += footer(c, 3)
    return out, res, Dictionary()


# ── Page 4: images ───────────────────────────────────────────────────────────

def chart_indices():
    idx = np.zeros((96, 192), dtype=np.uint8)
    idx[88:90, 8:184] = 1
    idx[8:90, 8:10] = 1
    for k, (h, colour) in enumerate(((50, 2), (70, 3), (35, 4), (60, 5), (78, 2), (44, 3))):
        idx[88 - h:88, 20 + k * 27:38 + k * 27] = colour
    return idx


def icon_indices():
    img = Image.new("P", (32, 32), 0)
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 29, 29], fill=1)
    d.ellipse([9, 9, 13, 13], fill=2)
    d.ellipse([18, 9, 22, 13], fill=2)
    d.arc([8, 10, 23, 24], 20, 160, fill=3, width=2)
    d.rectangle([0, 30, 31, 31], fill=4)
    d.point([(1, 1), (30, 1)], fill=5)
    return np.array(img, dtype=np.uint8)


def pack(indices, bpc):
    h, w = indices.shape
    b = np.unpackbits(indices[:, :, None], axis=2)[:, :, 8 - bpc:].reshape(h, w * bpc)
    return np.packbits(b, axis=1).tobytes()


def diagram(dark):
    img = Image.new("L", (640, 400), 255)
    d = ImageDraw.Draw(img)
    d.ellipse([60, 60, 340, 340], outline=0, width=14)
    d.line([360, 340, 600, 60], fill=60, width=14)
    d.rectangle([380, 220, 560, 330], outline=120, width=10)
    small = np.array(img.resize((160, 100), Image.LANCZOS))
    return (255 - small) if dark else small


def few_colours(c):
    img = Image.new("RGB", (192, 96), c["white"])
    d = ImageDraw.Draw(img)
    d.line([8, 88, 184, 88], fill=c["ink"], width=2)
    pts = [(10, 70), (40, 50), (70, 60), (100, 30), (130, 40), (160, 15), (184, 25)]
    d.line(pts, fill=c["accent"], width=3)
    d.line([(x, y + 25) for x, y in pts], fill=c["orange"], width=3)
    return img.tobytes()


def photo(seed, size=(160, 100), shift=0.0):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size[1], 0:size[0]] / max(size)
    r = 0.5 + 0.4 * np.sin(6 * xx + shift) * np.cos(4 * yy)
    g = 0.5 + 0.4 * np.sin(5 * yy + 1 + shift)
    b = 0.5 + 0.4 * np.cos(7 * xx * yy + 2)
    img = np.stack([r, g, b], axis=2) + rng.normal(0, 0.03, (size[1], size[0], 3))
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def page_images(sh):
    c = sh.c
    tiles = [(45 + col * 130, 640 - row * 132) for row in range(4) for col in range(4)]
    xo = Dictionary()
    pal = lambda names: String(bytes(v for h in names for v in rgb255(c[h])))
    xo["/Chart8"] = sh.image(chart_indices().tobytes(), 192, 96, Array([Name.Indexed, Name.DeviceRGB, 5, pal(
        ("white", "ink", "accent", "blue", "orange", "green"))]))
    xo["/Icon4"] = sh.image(pack(icon_indices(), 4), 32, 32, Array([Name.Indexed, Name.DeviceRGB, 5, pal(
        ("white", "yellow", "ink", "ink", "accent", "pink"))]), bpc=4)
    rng = np.random.default_rng(7)
    qr = (rng.random((25, 25)) > 0.5).astype(np.uint8)
    qr[0:7, 0:7] = qr[0:7, 18:25] = qr[18:25, 0:7] = 1
    qr[1:6, 1:6] = qr[1:6, 19:24] = qr[19:24, 1:6] = 0
    qr[2:5, 2:5] = qr[2:5, 20:23] = qr[20:23, 2:5] = 1
    xo["/Code1"] = sh.image(pack(qr, 1), 25, 25, Array([Name.Indexed, Name.DeviceRGB, 1, pal(("white", "ink"))]),
                            bpc=1)
    xo["/Gray"] = sh.image(diagram(c["mode"] == "dark").tobytes(), 160, 100, Name.DeviceGray)
    xo["/Few"] = sh.image(few_colours(c), 192, 96, Name.DeviceRGB)
    xo["/Photo"] = sh.image(photo(1).tobytes(), 160, 100, Name.DeviceRGB)
    xo["/Shot"] = sh.image(photo(2, shift=0.0 if c["mode"] == "light" else 2.5).tobytes(), 160, 100, Name.DeviceRGB)
    alpha = Image.new("L", (256, 256), 0)
    ImageDraw.Draw(alpha).ellipse([16, 16, 240, 240], fill=255)
    alpha = np.array(alpha.filter(ImageFilter.GaussianBlur(10)).resize((64, 64), Image.LANCZOS))
    logo = np.zeros((64, 64, 3), dtype=np.uint8) + np.array(rgb255(c["accent"]), dtype=np.uint8)
    logo[24:40, 24:40] = rgb255(c["yellow"])
    xo["/Logo"] = sh.image(logo.tobytes(), 64, 64, Name.DeviceRGB,
                           SMask=sh.image(alpha.tobytes(), 64, 64, Name.DeviceGray))
    keyed = np.full((48, 64, 3), 255, dtype=np.uint8)
    keyed[8:40, 8:56] = (40, 140, 90)
    keyed[16:32, 20:44] = (230, 180, 40)
    xo["/Keyed"] = sh.image(keyed.tobytes(), 64, 48, Name.DeviceRGB, Mask=Array([250, 255, 250, 255, 250, 255]))
    arrow = Image.new("1", (32, 32), 1)
    ImageDraw.Draw(arrow).polygon([(2, 12), (18, 12), (18, 4), (30, 16), (18, 28), (18, 20), (2, 20)], fill=0)
    xo["/Stencil"] = sh.image(arrow.tobytes(), 32, 32, None, bpc=1, ImageMask=True)
    jpeg = io.BytesIO()
    Image.fromarray(photo(3, (120, 80))).save(jpeg, "JPEG", quality=85)
    xo["/Jpeg"] = sh.image(jpeg.getvalue(), 120, 80, Name.DeviceRGB, compress=False, Filter=Name.DCTDecode)
    decode = {"Decode": Array([1, 0])} if c["mode"] == "dark" else {}
    xo["/Decoded"] = sh.image(diagram(False).tobytes(), 160, 100, Name.DeviceGray, **decode)
    deep = (photo(4, (64, 40)).astype(np.uint16) * 257).astype(">u2")
    xo["/Deep"] = sh.image(deep.tobytes(), 64, 40, Name.DeviceRGB, bpc=16)
    spaces = Dictionary({"/InlIdx": Array([Name.Indexed, Name.DeviceRGB, 2, pal(("white", "green", "pink"))])})
    res = Dictionary(Font=sh.fonts(), XObject=xo, ColorSpace=spaces)
    tiny = np.zeros((8, 8, 3), dtype=np.uint8) + np.array(rgb255(c["blue"]), dtype=np.uint8)
    tiny[2:6, 2:6] = rgb255(c["yellow"])
    inline_rgb = f"BI /W 8 /H 8 /CS /RGB /BPC 8 /F /AHx ID {tiny.tobytes().hex()}> EI"
    mask = Image.new("1", (16, 16), 1)
    ImageDraw.Draw(mask).ellipse([1, 1, 14, 14], fill=0)
    inline_mask = f"BI /W 16 /H 16 /IM true /BPC 1 /F /AHx ID {mask.tobytes().hex()}> EI"
    inl = np.array([[0, 1, 1, 0], [1, 2, 2, 1], [1, 2, 2, 1], [0, 1, 1, 0]], dtype=np.uint8)
    inline_named = f"BI /W 4 /H 4 /CS /InlIdx /BPC 8 /F /AHx ID {inl.tobytes().hex()}> EI"
    items = [
        ("", 110, 55, "/Chart8 Do", "Indexed, 8 bits"),
        ("", 64, 64, "/Icon4 Do", "Indexed, 4 bits"),
        ("", 64, 64, "/Code1 Do", "Indexed, 1 bit"),
        ("", 110, 69, "/Gray Do", "Gray; the dark build inverts it"),
        ("", 110, 55, "/Few Do", "RGB with few colours"),
        ("", 110, 69, "/Photo Do", "Photo, the same in both builds"),
        ("", 110, 69, "/Shot Do", "Photo that differs: swapped whole"),
        ("", 64, 64, "/Logo Do", "Soft mask (alpha channel)"),
        ("", 85, 64, "/Keyed Do", "Colour-key mask"),
        (f"{rgb(c['accent'])} rg ", 48, 48, "/Stencil Do", "Stencil mask in the fill colour"),
        ("", 48, 48, inline_rgb, "Inline image"),
        (f"{rgb(c['pink'])} rg ", 48, 48, inline_mask, "Inline stencil mask"),
        ("", 100, 67, "/Jpeg Do", "JPEG photo"),
        ("", 110, 69, "/Decoded Do", "Inverted by a Decode array"),
        ("", 96, 60, "/Deep Do", "16 bits per component"),
        ("", 48, 48, inline_named, "Inline, named Indexed space"),
    ]
    out = heading(c, 4, "Images", "Images of every common kind. Some change between the builds and some do not.")
    out += f"{rgb(c['card'])} rg 35 105 525 655 re f\n"
    for (x, y), (before, w, h, draw, name) in zip(tiles, items):
        out += f"{before}q {w} 0 0 {h} {x} {y + 12} cm {draw} Q\n" + label(c, x, y - 4, name)
    out += footer(c, 4)
    return out, res, Dictionary()


# ── Page 5: annotations and form fields ──────────────────────────────────────

def page_annotations(sh):
    c, pdf = sh.c, sh.pdf
    fonts = Dictionary({"/Helv": sh.helv, "/ZaDb": sh.zadb})
    annots = []

    def annot(subtype, rect, ap_content, ap_res=None, **keys):
        x0, y0, x1, y1 = rect
        ap = sh.form(ap_content, [0, 0, x1 - x0, y1 - y0], ap_res)
        d = Dictionary(Type=Name.Annot, Subtype=Name("/" + subtype), Rect=Array(rect), F=4, AP=Dictionary(N=ap),
                       **keys)
        d = pdf.make_indirect(d)
        annots.append(d)
        return d

    annot("Square", [50, 600, 170, 680], f"{rgb(c['yellow'])} rg {rgb(c['accent'])} RG 3 w 1.5 1.5 117 77 re B",
          C=Array(rgbf(c["accent"])), IC=Array(rgbf(c["yellow"])), BS=Dictionary(W=3), CA=c["annot_alpha"],
          Contents=String("Square"))
    annot("Circle", [200, 600, 320, 680], f"{rgb(c['card'])} rg {rgb(c['blue'])} RG 3 w " + circle(60, 40, 37) + "B",
          C=Array(rgbf(c["blue"])), IC=Array(rgbf(c["card"])), BS=Dictionary(W=3))
    annot("Line", [350, 600, 510, 680],
          f"{rgb(c['orange'])} RG {rgb(c['orange'])} rg 2 w 10 10 m 140 70 l S 150 75 m 132 72 l 140 62 l h B",
          L=Array([360, 610, 500, 675]), LE=Array([Name("/None"), Name.ClosedArrow]),
          C=Array(rgbf(c["orange"])), IC=Array(rgbf(c["orange"])), BS=Dictionary(W=2))
    annot("Polygon", [50, 470, 170, 560], f"{rgb(c['card'])} rg {rgb(c['green'])} RG 2 w 10 10 m 110 20 l 90 80 l 30 70 l h B",
          Vertices=Array([60, 480, 160, 490, 140, 550, 80, 540]), C=Array(rgbf(c["green"])),
          IC=Array(rgbf(c["card"])), BS=Dictionary(W=2))
    annot("Ink", [200, 470, 320, 560], f"{rgb(c['pink'])} RG 3 w 1 J 1 j 10 20 m 30 70 50 10 70 60 c 90 85 100 30 110 50 c S",
          InkList=Array([Array([210, 490, 230, 540, 250, 480, 270, 530])]), C=Array(rgbf(c["pink"])),
          BS=Dictionary(W=3))
    hl_gs = Dictionary(ExtGState=Dictionary({"/M": Dictionary(BM=Name(c["highlight_blend"]))}))
    annot("Highlight", [48, 397, 300, 413], f"/M gs {rgb(c['yellow'])} rg 0 0 252 16 re f", hl_gs,
          QuadPoints=Array([48, 413, 300, 413, 48, 397, 300, 397]), C=Array(rgbf(c["yellow"])))
    hexes = c["ink"]
    annot("FreeText", [350, 470, 545, 560],
          f"{rgb(c['card'])} rg 0 0 195 90 re f {rgb(c['accent'])} RG 1 w 0.5 0.5 194 89 re S {rgb(c['ink'])} rg "
          + text("Helv", 11, 8, 68, "Free text, with its") + text("Helv", 11, 8, 52, "default appearance,")
          + text("Helv", 11, 8, 36, "style and rich text."),
          Dictionary(Font=fonts),
          DA=String(f"/Helv 11 Tf {rgb(c['ink'])} rg"), DS=String(f"font: 11pt Helvetica; color:{hexes}"),
          RC=String(f'<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" '
                    f'style="color:{hexes}"><p>Free text, with its default appearance, style and rich text.</p></body>'),
          C=Array(rgbf(c["card"])), Contents=String("Free text, with its default appearance, style and rich text."))
    note = annot("Text", [50, 300, 72, 322], f"{rgb(c['yellow'])} rg {rgb(c['ink'])} RG 1 w 1 1 20 20 re B "
                 f"{rgb(c['ink'])} RG 5 15 m 17 15 l 5 11 m 17 11 l 5 7 m 13 7 l S",
                 C=Array(rgbf(c["yellow"])), Name=Name.Comment, Contents=String("A sticky note"), Open=False)
    popup = pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Popup, Rect=Array([80, 250, 280, 330]),
                                         Parent=note, Open=False, F=4))
    note.Popup = popup
    annots.append(popup)
    link = pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Link, Rect=Array([200, 300, 330, 318]),
                                        Border=Array([0, 0, 0]), C=Array(rgbf(c["blue"])),
                                        A=Dictionary(S=Name.URI, URI=String("https://www.iso.org/standard/75839.html"))))
    annots.append(link)
    field = annot("Widget", [350, 300, 545, 324],
                  f"{rgb(c['card'])} rg 0 0 195 24 re f {rgb(c['rule'])} RG 1 w 0.5 0.5 194 23 re S "
                  f"/Tx BMC q {rgb(c['ink'])} rg " + text("Helv", 12, 6, 7, "Ada Lovelace") + "Q EMC",
                  Dictionary(Font=fonts),
                  FT=Name.Tx, T=String("name"), V=String("Ada Lovelace"), DA=String(f"/Helv 12 Tf {rgb(c['ink'])} rg"),
                  MK=Dictionary(BG=Array(rgbf(c["card"])), BC=Array(rgbf(c["rule"]))))
    on = sh.form(f"{rgb(c['card'])} rg 0 0 24 24 re f {rgb(c['rule'])} RG 1 w 0.5 0.5 23 23 re S "
                 f"q {rgb(c['accent'])} rg BT /ZaDb 18 Tf 4 6 Td (4) Tj ET Q", [0, 0, 24, 24], Dictionary(Font=fonts))
    off = sh.form(f"{rgb(c['card'])} rg 0 0 24 24 re f {rgb(c['rule'])} RG 1 w 0.5 0.5 23 23 re S", [0, 0, 24, 24])
    box = pdf.make_indirect(Dictionary(
        Type=Name.Annot, Subtype=Name.Widget, Rect=Array([350, 250, 374, 274]), F=4, FT=Name.Btn, T=String("agree"),
        V=Name.Yes, AS=Name.Yes, AP=Dictionary(N=Dictionary(Yes=on, Off=off), D=Dictionary(Yes=on, Off=off)),
        DA=String(f"/ZaDb 0 Tf {rgb(c['accent'])} rg"),
        MK=Dictionary(BG=Array(rgbf(c["card"])), BC=Array(rgbf(c["rule"])), CA=String("4"))))
    annots.append(box)
    acroform = Dictionary(Fields=Array([field, box]), DA=String(f"/Helv 0 Tf {gray(c['ink'])} g"),
                          DR=Dictionary(Font=fonts))
    res = Dictionary(Font=sh.fonts())
    out = heading(c, 5, "Annotations and form fields",
                  "Each annotation has an appearance stream and the colour entries its type defines.")
    for x, y, name in ((50, 586, "Square: C, IC, CA"), (200, 586, "Circle: C, IC"), (350, 586, "Line: C, IC, arrow"),
                       (50, 456, "Polygon: C, IC"), (200, 456, "Ink: C"), (350, 456, "FreeText: DA, DS, RC, C")):
        out += label(c, x, y, name)
    out += f"{rgb(c['ink'])} rg " + text("F1", 12, 50, 401, "This sentence has a highlight annotation over it.")
    out += label(c, 50, 385, "Highlight: C, and a blend mode in its appearance")
    out += f"{rgb(c['blue'])} rg " + text("F1", 11, 200, 305, "A link (C, no border)")
    out += label(c, 50, 286, "Text note with a Popup")
    out += label(c, 350, 286, "Text field: DA, MK BG and BC")
    out += f"{rgb(c['ink'])} rg " + text("F1", 11, 382, 257, "Check box: DA, MK, two states")
    out += footer(c, 5)
    return out, res, Dictionary(Annots=Array(annots)), acroform


# ── Page 6: Type 3 fonts, layers and structure ───────────────────────────────

def page_type3(sh, ocgs):
    c, pdf = sh.c, sh.pdf
    glyph_res = Dictionary(ColorSpace=Dictionary({"/G": sh.icc}))
    coloured = pdf.make_indirect(Dictionary(
        Type=Name.Font, Subtype=Name.Type3, FontBBox=Array([0, 0, 1000, 1000]),
        FontMatrix=Array([0.001, 0, 0, 0.001, 0, 0]),
        CharProcs=Dictionary(
            dot=sh.stream(f"1000 0 d0 {rgb(c['accent'])} rg {circle(500, 500, 420)}f {rgb(c['white'])} rg "
                          f"{circle(500, 500, 160)}f"),
            sq=sh.stream(f"1000 0 d0 /G cs {rgb(c['blue'])} scn 80 80 840 840 re f /G cs {rgb(c['yellow'])} scn "
                         f"300 300 400 400 re f")),
        Encoding=Dictionary(Type=Name.Encoding, Differences=Array([65, Name.dot, Name.sq])),
        FirstChar=65, LastChar=66, Widths=Array([1000, 1000]), Resources=glyph_res))
    plain = pdf.make_indirect(Dictionary(
        Type=Name.Font, Subtype=Name.Type3, FontBBox=Array([0, 0, 1000, 1000]),
        FontMatrix=Array([0.001, 0, 0, 0.001, 0, 0]),
        CharProcs=Dictionary(star=sh.stream("1000 0 0 0 1000 1000 d1 " + star(500, 500, 480, 200) + "f")),
        Encoding=Dictionary(Type=Name.Encoding, Differences=Array([65, Name.star])),
        FirstChar=65, LastChar=65, Widths=Array([1000]), Resources=Dictionary()))
    diagram_form = sh.form(f"{rgb(c['green'])} rg 0 0 60 40 re f {rgb(c['blue'])} rg 70 0 60 60 re f "
                           f"{rgb(c['orange'])} rg 140 0 60 25 re f", [0, 0, 200, 60], OC=ocgs[1])
    fonts = sh.fonts()
    fonts["/T3c"], fonts["/T3u"] = coloured, plain
    res = Dictionary(Font=fonts, XObject=Dictionary({"/Diag": diagram_form}),
                     Properties=Dictionary({"/oc1": ocgs[0]}))
    out = heading(c, 6, "Type 3 fonts, layers and structure",
                  "Glyphs that carry their own colours, optional content, and tagged text with layout colours.")
    out += text("T3c", 36, 50, 680, "ABAB") + label(c, 50, 662, "Type 3 glyphs with their own colours (d0)")
    out += f"{rgb(c['pink'])} rg " + text("T3u", 36, 300, 680, "AAAA") + \
        label(c, 300, 662, "Type 3 glyphs in the text colour (d1)")
    out += f"/OC /oc1 BDC {rgb(c['card'])} rg 50 560 220 60 re f {rgb(c['orange'])} rg 50 560 6 60 re f " \
           f"{rgb(c['ink'])} rg " + text("F1", 11, 66, 594, "This box is in the layer Notes.") + "EMC\n"
    out += label(c, 50, 545, "Marked content in an optional content group")
    out += "q 1 0 0 1 300 560 cm /Diag Do Q\n" + label(c, 300, 545, "A form XObject in the layer Diagrams")
    out += f"/H1 << /MCID 0 >> BDC {gray(c['heading'])} g " + text("F2", 14, 50, 490, "Tagged heading") + "EMC\n"
    out += f"/P << /MCID 1 >> BDC {rgb(c['ink'])} rg " + \
        text("F1", 11, 50, 470, "This paragraph's structure element sets Color, BackgroundColor,") + "EMC\n"
    out += f"/P << /MCID 2 >> BDC {rgb(c['ink'])} rg " + \
        text("F1", 11, 50, 455, "BorderColor and TextDecorationColor, and a class map sets more.") + "EMC\n"
    out += label(c, 50, 430, "Bookmarks carry colours too (C), and page 1 has a thumbnail and BoxColorInfo.")
    out += footer(c, 6)
    return out, res, Dictionary(StructParents=0)


# ── The document ─────────────────────────────────────────────────────────────

def build(c) -> pikepdf.Pdf:
    pdf = pikepdf.new()
    sh = Shared(pdf, c)
    ocgs = [pdf.make_indirect(Dictionary(Type=Name.OCG, Name=String(n))) for n in ("Notes", "Diagrams")]
    pages = []
    acroform = None
    for maker in (page_spaces, page_gradients, page_transparency, page_images, page_annotations, page_type3):
        result = maker(sh, ocgs) if maker is page_type3 else maker(sh)
        content, res, extra = result[:3]
        if maker is page_annotations:
            acroform = result[3]
        page = pdf.add_blank_page(page_size=(W, H))
        page.obj.Contents = pdf.make_stream(content.encode("latin-1"))
        page.obj.Resources = res
        for k, v in extra.items():
            page.obj[k] = v
        pages.append(page)
    pdf.Root.AcroForm = acroform
    pdf.Root.OCProperties = Dictionary(OCGs=Array(ocgs), D=Dictionary(ON=Array(ocgs), Order=Array(ocgs)))
    # Bookmarks with colours
    titles = ["Colour spaces", "Gradients and patterns", "Transparency and forms", "Images",
              "Annotations and form fields", "Type 3 fonts, layers and structure"]
    colours = ["accent", "blue", "orange", "green", "pink", "ink"]
    outlines = pdf.make_indirect(Dictionary(Type=Name.Outlines, Count=len(titles)))
    items = [pdf.make_indirect(Dictionary(Title=String(t), Parent=outlines, Dest=Array([p.obj, Name.Fit]),
                                          C=Array(rgbf(c[h])), F=2 if k % 2 else 0))
             for k, (t, p, h) in enumerate(zip(titles, pages, colours))]
    for a, b in zip(items, items[1:]):
        a.Next, b.Prev = b, a
    outlines.First, outlines.Last = items[0], items[-1]
    pdf.Root.Outlines = outlines
    # Structure: a document with a heading and two paragraphs on page 6
    root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
    doc = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.Document, P=root))
    p6 = pages[5].obj
    h1 = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.H1, P=doc, Pg=p6, K=0,
                                      A=Dictionary(O=Name.Layout, Color=Array(rgbf(c["heading"])))))
    side = [rgbf(c["accent"]), rgbf(c["rule"]), rgbf(c["accent"]), rgbf(c["rule"])]
    para = pdf.make_indirect(Dictionary(
        Type=Name.StructElem, S=Name.P, P=doc, Pg=p6, K=1, C=Name.Note,
        A=Array([Dictionary(O=Name.Layout, Color=Array(rgbf(c["ink"])), BackgroundColor=Array(rgbf(c["card"])),
                            BorderColor=Array([Array(s) for s in side]),
                            TextDecorationColor=Array(rgbf(c["accent"])))])))
    para2 = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.P, P=doc, Pg=p6, K=2,
                                         A=Dictionary(O=Name.Layout, BorderColor=Array(rgbf(c["rule"])))))
    doc.K = Array([h1, para, para2])
    root.K = Array([doc])
    root.ParentTree = Dictionary(Nums=Array([0, Array([h1, para, para2])]))
    root.ClassMap = Dictionary(Note=Dictionary(O=Name.Layout, Color=Array(rgbf(c["blue"])),
                                               BackgroundColor=Array(rgbf(c["card"]))))
    pdf.Root.StructTreeRoot = root
    pdf.Root.MarkInfo = Dictionary(Marked=True)
    pdf.Root.Lang = String("en-GB")
    pdf.docinfo["/Title"] = String("pdf-themes test document")
    return pdf


def write(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for name, colours in (("light", LIGHT), ("dark", DARK)):
        path = os.path.join(out_dir, f"corpus-{name}.pdf")
        build(colours).save(path, deterministic_id=True)
        paths[name] = path
    return paths


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for name, path in write(os.path.join(here, "..", "out")).items():
        print(name, os.path.relpath(path), os.path.getsize(path))
