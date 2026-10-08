"""Shared resources: colour spaces of all eleven families, functions of all four
types, ICC profiles and the Type 3 font. Anything that carries a colour takes it
from the build's palette, so the light and dark builds differ only there."""
import io
import math
import struct

import numpy as np
import pikepdf
from fontTools.ttLib import TTFont
from PIL import Image
from pikepdf import Array, Dictionary, Name, String

from .fonts import Font, find_font, to_unicode_cmap
from .palette import D50, HUES, fmt

TEXLIVE_ICC = "/usr/share/texlive/texmf-dist/tex/generic/colorprofiles/"
D65 = [0.9505, 1.0, 1.089]


def _s15(v):
    return struct.pack(">i", int(round(v * 65536)))


def display_p3_icc():
    """A small ICC v2 display profile for Display P3 (D65 primaries adapted to D50, sRGB curve)."""
    bradford = ((1.0478112, 0.0228866, -0.0501270), (0.0295424, 0.9904844, -0.0170491),
                (-0.0092345, 0.0150436, 0.7521316))
    prim = [(0.4865709, 0.2289746, 0.0), (0.2656677, 0.6917385, 0.0451134), (0.1982173, 0.0792869, 1.0439444)]
    adapted = [tuple(sum(bradford[i][j] * p[j] for j in range(3)) for i in range(3)) for p in prim]

    def xyz(v):
        return b"XYZ " + b"\0" * 4 + b"".join(_s15(c) for c in v)

    curve = [0] * 1024
    for i in range(1024):
        c = i / 1023
        lin = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        curve[i] = int(round(lin * 65535))
    curv = b"curv" + b"\0" * 4 + struct.pack(">I", 1024) + b"".join(struct.pack(">H", v) for v in curve)
    desc_txt = b"Display P3 (pdf-themes test)\0"
    desc = (b"desc" + b"\0" * 4 + struct.pack(">I", len(desc_txt)) + desc_txt
            + b"\0" * 4 + b"\0" * 4 + b"\0" * 2 + b"\0" + b"\0" * 67)
    cprt = b"text" + b"\0" * 4 + b"No copyright, use freely\0"
    tags = [(b"desc", desc), (b"cprt", cprt), (b"wtpt", xyz(D50)),
            (b"rXYZ", xyz(adapted[0])), (b"gXYZ", xyz(adapted[1])), (b"bXYZ", xyz(adapted[2])),
            (b"rTRC", curv), (b"gTRC", curv), (b"bTRC", curv)]
    table_len = 4 + 12 * len(tags)
    offset = 128 + table_len
    entries, blobs = [], b""
    shared = {}
    for sig, data in tags:
        if data in shared:
            entries.append((sig, shared[data], len(data)))
            continue
        while (offset + len(blobs)) % 4:
            blobs += b"\0"
        pos = offset + len(blobs)
        shared[data] = pos
        entries.append((sig, pos, len(data)))
        blobs += data
    table = struct.pack(">I", len(tags)) + b"".join(s + struct.pack(">II", o, l) for s, o, l in entries)
    size = 128 + len(table) + len(blobs)
    header = (struct.pack(">I", size) + b"none" + struct.pack(">I", 0x02100000) + b"mntrRGB XYZ "
              + struct.pack(">6H", 2026, 1, 1, 0, 0, 0) + b"acsp" + b"APPL" + struct.pack(">I", 0)
              + b"none" + b"none" + b"\0" * 8 + struct.pack(">I", 0) + b"".join(_s15(c) for c in D50)
              + b"none" + b"\0" * 16 + b"\0" * 28)
    assert len(header) == 128, len(header)
    return header + table + blobs


def devicen_code(t, o):
    """Type 4 code for {teal orange} -> C M Y K, each channel o*O + t*T."""
    parts = []
    for i in range(3):
        parts.append("2 copy %s mul exch %s mul add 3 1 roll" % (fmt([o[i]]), fmt([t[i]])))
    parts.append("%s mul exch %s mul add" % (fmt([o[3]]), fmt([t[3]])))
    return "{ %s }" % " ".join(parts)


def nchannel_code(t):
    """Type 4 code for {Cyan Magenta SpotTeal} -> C M Y K."""
    return ("{ dup %s mul 4 -1 roll add 3 1 roll dup %s mul 3 -1 roll add exch dup %s mul exch %s mul }"
            % (fmt([t[0]]), fmt([t[1]]), fmt([t[2]]), fmt([t[3]])))


def xy_mix_code(A, B, C):
    """Type 4 code for (x, y) -> RGB: (A(1-x) + Bx)(1-y) + Cy, channel by channel."""
    parts = []
    for i in range(3):
        parts.append("2 copy exch dup %s mul exch 1 exch sub %s mul add exch dup %s mul 3 1 roll "
                     "1 exch sub mul add 3 1 roll" % (fmt([B[i]]), fmt([A[i]]), fmt([C[i]])))
    parts.append("pop pop")
    return "{ %s }" % " ".join(parts)


def run_type4(code, *args):
    """A small PostScript calculator, enough to check the functions above."""
    toks = code.replace("{", " ").replace("}", " ").split()
    st = list(args)
    for t in toks:
        if t == "dup":
            st.append(st[-1])
        elif t == "pop":
            st.pop()
        elif t == "exch":
            st[-1], st[-2] = st[-2], st[-1]
        elif t == "copy":
            k = int(st.pop())
            st.extend(st[-k:])
        elif t == "index":
            k = int(st.pop())
            st.append(st[-1 - k])
        elif t == "roll":
            j, k = int(st.pop()), int(st.pop())
            grp = st[-k:]
            j %= k
            st[-k:] = grp[-j:] + grp[:-j] if j else grp
        elif t in ("add", "sub", "mul"):
            b, a = st.pop(), st.pop()
            st.append(a + b if t == "add" else a - b if t == "sub" else a * b)
        else:
            st.append(float(t))
    return st


def function2(c0, c1, n=1.0):
    return Dictionary(FunctionType=2, Domain=Array([0, 1]), C0=Array([round(v, 4) for v in c0]),
                      C1=Array([round(v, 4) for v in c1]), N=n)


class Res:
    """Per-build shared resources, made on first use."""

    def __init__(self, doc):
        self.doc, self.pal, self.pdf = doc, doc.pal, doc.pdf

    def _once(self, key, make):
        return self.doc.once(key, make)

    # -- ICC --------------------------------------------------------------------------
    def icc(self, which):
        def make():
            if which == "srgb":
                data, n, alt = open(TEXLIVE_ICC + "sRGB.icc", "rb").read(), 3, Name.DeviceRGB
            elif which == "cmyk":
                data, n, alt = open(TEXLIVE_ICC + "FOGRA39L_coated.icc", "rb").read(), 4, Name.DeviceCMYK
            elif which == "p3":
                data, n, alt = display_p3_icc(), 3, Name.DeviceRGB
            else:
                raise KeyError(which)
            s = self.doc.stream(data, N=n, Alternate=alt)
            return self.pdf.make_indirect(Array([Name.ICCBased, s]))
        return self._once(("icc", which), make)

    def icc_stream(self, which):
        return self.icc(which)[1]

    # -- the eleven colour space families --------------------------------------------------
    def calgray(self):
        return self._once("calgray", lambda: self.pdf.make_indirect(
            Array([Name.CalGray, Dictionary(WhitePoint=Array(D65), Gamma=2.2)])))

    def calrgb(self):
        return self._once("calrgb", lambda: self.pdf.make_indirect(Array([Name.CalRGB, Dictionary(
            WhitePoint=Array(D65), Gamma=Array([2.2, 2.2, 2.2]),
            Matrix=Array([0.4124, 0.2126, 0.0193, 0.3576, 0.7152, 0.1192, 0.1805, 0.0722, 0.9505]))])))

    def lab(self):
        return self._once("lab", lambda: self.pdf.make_indirect(Array([Name.Lab, Dictionary(
            WhitePoint=Array(list(D50)), Range=Array([-128, 127, -128, 127]))])))

    def indexed_roles(self):
        return ["paper", "ink", "rule"] + HUES

    def indexed(self, base="rgb"):
        """Indexed over DeviceRGB, Lab or ICC sRGB, one entry per role."""
        def make():
            roles = self.indexed_roles()
            if base == "rgb":
                b, vals = Name.DeviceRGB, [self.pal.rgb(r) for r in roles]
                lookup = bytes(int(round(c * 255)) for v in vals for c in v)
            elif base == "icc":
                b = self.icc("srgb")
                lookup = bytes(int(round(c * 255)) for r in roles for c in self.pal.rgb(r))
            elif base == "lab":
                b = self.lab()
                # bytes scale to the Range: L 0..100, a and b -128..127
                out = []
                for r in roles:
                    L, a, bb = self.pal.lab(r)
                    out += [int(round(L / 100 * 255)), int(round(a + 128)), int(round(bb + 128))]
                lookup = bytes(max(0, min(255, v)) for v in out)
            return self.pdf.make_indirect(Array([Name.Indexed, b, len(roles) - 1, String(lookup)]))
        return self._once(("indexed", base), make)

    def role_index(self, role):
        return self.indexed_roles().index(role)

    def separation(self, which="teal"):
        def make():
            if which == "all":
                return Array([Name.Separation, Name.All, Name.DeviceCMYK,
                              function2([0, 0, 0, 0], [1, 1, 1, 1])])
            if which == "none":
                return Array([Name.Separation, Name("/None"), Name.DeviceCMYK,
                              function2([0, 0, 0, 0], [0, 0, 0, 0])])
            role = {"teal": "teal", "orange": "orange"}[which]
            name = {"teal": "/SpotTeal", "orange": "/SpotOrange"}[which]
            return self.pdf.make_indirect(Array([Name.Separation, Name(name), Name.DeviceCMYK,
                                                 function2([0, 0, 0, 0], self.pal.cmyk(role))]))
        return self._once(("sep", which), make)

    def _devicen_fn(self):
        """{teal orange} -> CMYK: each ink adds its own CMYK; Range clips the sum to 1."""
        code = devicen_code(self.pal.cmyk("teal"), self.pal.cmyk("orange"))
        return self.doc.stream(code.encode(), FunctionType=4, Domain=Array([0, 1, 0, 1]),
                               Range=Array([0, 1, 0, 1, 0, 1, 0, 1]))

    def devicen(self):
        def make():
            attrs = Dictionary(Colorants=Dictionary(SpotTeal=self.separation("teal"),
                                                    SpotOrange=self.separation("orange")))
            return self.pdf.make_indirect(Array([Name.DeviceN, Array([Name("/SpotTeal"), Name("/SpotOrange")]),
                                                 Name.DeviceCMYK, self._devicen_fn(), attrs]))
        return self._once("devicen", make)

    def nchannel(self):
        def make():
            code = nchannel_code(self.pal.cmyk("teal")).encode()
            fn = self.doc.stream(code, FunctionType=4, Domain=Array([0, 1, 0, 1, 0, 1]),
                                 Range=Array([0, 1, 0, 1, 0, 1, 0, 1]))
            attrs = Dictionary(Subtype=Name.NChannel,
                               Colorants=Dictionary(SpotTeal=self.separation("teal")),
                               Process=Dictionary(ColorSpace=Name.DeviceCMYK,
                                                  Components=Array([Name.Cyan, Name.Magenta, Name.Yellow, Name.Black])))
            return self.pdf.make_indirect(Array([Name.DeviceN, Array([Name.Cyan, Name.Magenta, Name("/SpotTeal")]),
                                                 Name.DeviceCMYK, fn, attrs]))
        return self._once("nchannel", make)

    def pattern_space(self, base="rgb"):
        def make():
            b = {"rgb": Name.DeviceRGB, "sep": self.separation("teal")}[base]
            return Array([Name.Pattern, b])
        return self._once(("patcs", base), make)

    # -- functions of all four types -----------------------------------------------------
    def fn_exp(self, a, b):
        return function2(self.pal.rgb(a), self.pal.rgb(b))

    def fn_sampled(self, roles):
        def make():
            samples = bytes(int(round(c * 255)) for r in roles for c in self.pal.rgb(r))
            return self.doc.stream(samples, FunctionType=0, Domain=Array([0, 1]), Range=Array([0, 1, 0, 1, 0, 1]),
                                   Size=Array([len(roles)]), BitsPerSample=8, Order=1)
        return self._once(("fn0", tuple(roles)), make)

    def fn_stitch(self, roles):
        fns = Array([self.fn_exp(a, b) for a, b in zip(roles, roles[1:])])
        k = len(roles) - 1
        return Dictionary(FunctionType=3, Domain=Array([0, 1]), Functions=fns,
                          Bounds=Array([round((i + 1) / k, 4) for i in range(k - 1)]),
                          Encode=Array([0, 1] * k))

    def fn_postscript_xy(self, a, b, c):
        """2-in, 3-out type 4 function: mixes three role colours over x and y."""
        code = xy_mix_code(self.pal.rgb(a), self.pal.rgb(b), self.pal.rgb(c))
        return self.doc.stream(code.encode(), FunctionType=4, Domain=Array([0, 1, 0, 1]),
                               Range=Array([0, 1, 0, 1, 0, 1]))

    # -- graphics states -----------------------------------------------------------------------
    def gstate(self, **entries):
        key = ("gs",) + tuple(sorted((k, repr(v)) for k, v in entries.items()))

        def make():
            d = Dictionary(Type=Name.ExtGState)
            for k, v in entries.items():
                d[Name("/" + k)] = v
            return self.pdf.make_indirect(d)
        return self._once(key, make)

    # -- Type 3 font ----------------------------------------------------------------------------
    def type3(self):
        return self._once("type3", self._make_type3)

    def _make_type3(self):
        pal, doc = self.pal, self.doc

        def path(points):
            return " ".join(("%g %g m" if i == 0 else "%g %g l") % p for i, p in enumerate(points)) + " h"

        star = []
        for i in range(10):
            r = 420 if i % 2 == 0 else 170
            a = math.radians(90 + i * 36)
            star.append((round(500 + r * math.cos(a)), round(420 + r * math.sin(a))))
        procs = {
            # uncoloured glyphs (d1): painted in the current fill colour
            "star": "1000 0 70 0 930 860 d1 %s f" % path(star),
            "heart": ("1000 0 80 0 920 800 d1 500 80 m 140 380 120 620 300 720 c 400 776 470 720 500 640 c "
                      "530 720 600 776 700 720 c 880 620 860 380 500 80 c h f"),
            "check": "1000 0 80 0 920 800 d1 %s f" % path([(100, 420), (220, 520), (400, 330), (800, 760), (900, 660), (400, 120)]),
            "arrow": "1000 0 60 60 940 760 d1 %s f" % path([(80, 330), (560, 330), (560, 140), (920, 410), (560, 680), (560, 490), (80, 490)]),
            # coloured glyphs (d0): the glyph sets its own colours
            "badge": ("1000 0 d0 %s 500 400 m 860 400 l 860 600 700 760 500 760 c 300 760 140 600 140 400 c "
                      "140 200 300 40 500 40 c 700 40 860 200 860 400 c h f %s 470 160 60 380 re f "
                      "500 640 m 545 640 580 605 580 560 c 580 515 545 480 500 480 c 455 480 420 515 420 560 c "
                      "420 605 455 640 500 640 c h f" % (pal.rg("accent"), pal.rg("paper"))),
            "flag": ("1000 0 d0 %s 100 560 800 200 re f %s 100 360 800 200 re f %s 100 160 800 200 re f "
                     "%s 12 w 100 160 800 600 re S" % (pal.rg("red"), pal.rg("yellow"), pal.rg("green"), pal.RG("ink"))),
            "emoji": "1000 0 d0 q 860 0 0 860 70 -60 cm /Em Do Q",
        }
        order = ["star", "heart", "check", "arrow", "badge", "flag", "emoji"]
        uni = {"star": "★", "heart": "♥", "check": "✓", "arrow": "➔", "badge": "ⓘ", "flag": "⚑", "emoji": "🎨"}
        charprocs = Dictionary()
        for name in order:
            charprocs[Name("/" + name)] = doc.stream(procs[name])
        # The emoji glyph draws a colour bitmap taken from Noto Color Emoji: an image, so it stays.
        em_img, em_alpha = emoji_bitmap("🎨")
        smask = doc.stream(em_alpha, Type=Name.XObject, Subtype=Name.Image, Width=em_img.width,
                           Height=em_img.height, ColorSpace=Name.DeviceGray, BitsPerComponent=8)
        em = doc.stream(em_img.tobytes(), Type=Name.XObject, Subtype=Name.Image, Width=em_img.width,
                        Height=em_img.height, ColorSpace=Name.DeviceRGB, BitsPerComponent=8, SMask=smask)
        diffs = Array([65] + [Name("/" + n) for n in order])
        tu = doc.stream(to_unicode_cmap({65 + i: uni[n] for i, n in enumerate(order)}, False))
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.Type3, FontBBox=Array([0, -100, 1000, 900]),
            FontMatrix=Array([0.001, 0, 0, 0.001, 0, 0]), CharProcs=charprocs,
            Encoding=Dictionary(Type=Name.Encoding, Differences=diffs), FirstChar=65, LastChar=65 + len(order) - 1,
            Widths=Array([1000] * len(order)), Resources=Dictionary(XObject=Dictionary(Em=em)), ToUnicode=tu,
            FontDescriptor=self.pdf.make_indirect(Dictionary(
                Type=Name.FontDescriptor, FontName=Name("/PdfThemesGlyphs"), Flags=4,
                FontBBox=Array([0, -100, 1000, 900]), ItalicAngle=0, Ascent=900, Descent=-100,
                CapHeight=700, StemV=80))))

        def w(text):
            return 1000 * len(text)

        def e(text):
            return "(" + "".join(chr(65 + order.index(t)) for t in text.split()) + ")"

        return Font("T3", obj, w, e, "Type 3")


def emoji_bitmap(ch):
    path = find_font("NotoColorEmoji.ttf")
    tt = TTFont(path)
    gname = tt.getBestCmap()[ord(ch)]
    strike = tt["CBDT"].strikeData[0]
    png = strike[gname].imageData
    im = Image.open(io.BytesIO(png)).convert("RGBA").resize((64, 64), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    alpha = a[..., 3:4] / 255
    rgb = (a[..., :3] * alpha + 255 * (1 - alpha))  # matte white for viewers that ignore SMask
    return Image.fromarray(rgb.astype("uint8"), "RGB"), im.split()[3].tobytes()
