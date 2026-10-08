"""Fonts of every kind PDF has, built from fonts installed on the machine.

Each kind is made once per build, and the font programs are identical in both
builds, so only the colours differ between them. `FontSet.get(key)` returns a
`Font` with the PDF dictionary and a way to measure and encode text.
"""
import hashlib
import io
import os
import string

import pikepdf
from fontTools import subset
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name, String
from reportlab.pdfbase import _fontdata, pdfmetrics

FONT_DIRS = ["/usr/share/fonts", "/usr/share/texlive/texmf-dist/fonts", "/usr/local/share/fonts"]


def find_font(*names):
    for root in FONT_DIRS:
        for dirpath, _, files in os.walk(root):
            for n in names:
                if n in files:
                    return os.path.join(dirpath, n)
    raise FileNotFoundError("none of %s installed" % (names,))


WINANSI = _fontdata.encodings["WinAnsiEncoding"]
WINANSI_CHARS = "".join(chr(c) for c in range(32, 127)) + "".join(
    bytes([c]).decode("cp1252") for c in range(160, 256))
WINANSI_CHARS += "".join(bytes([c]).decode("cp1252", errors="ignore") for c in range(128, 160))

_cache = {}


def _tag(*parts):
    h = hashlib.sha1("|".join(parts).encode()).digest()
    return "".join(string.ascii_uppercase[b % 26] for b in h[:6])


def _subset(path, unicodes, *, index=0, retain_gids=False, names=False):
    key = ("subset", path, index, tuple(sorted(unicodes)), retain_gids, names)
    if key in _cache:
        return _cache[key]
    font = TTFont(path, fontNumber=index)
    opts = subset.Options()
    opts.retain_gids = retain_gids
    opts.notdef_outline = True
    opts.glyph_names = names
    opts.hinting = False
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.desubroutinize = True
    opts.drop_tables += ["GSUB", "GPOS", "GDEF", "DSIG", "kern", "BASE", "JSTF", "MATH"]
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=sorted(unicodes))
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    out = (data, TTFont(io.BytesIO(data)))
    _cache[key] = out
    return out


def _escape(raw: bytes) -> str:
    out = []
    for b in raw:
        c = chr(b)
        if c in "()\\":
            out.append("\\" + c)
        elif 32 <= b < 127:
            out.append(c)
        else:
            out.append("\\%03o" % b)
    return "(" + "".join(out) + ")"


def to_unicode_cmap(mapping, two_byte):
    """mapping: code -> unicode string"""
    width = 4 if two_byte else 2
    lo, hi = ("0000", "FFFF") if two_byte else ("00", "FF")
    lines = [
        "/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
        "1 begincodespacerange", "<%s> <%s>" % (lo, hi), "endcodespacerange",
    ]
    items = sorted(mapping.items())
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        lines.append("%d beginbfchar" % len(chunk))
        for code, uni in chunk:
            u16 = uni.encode("utf-16-be").hex().upper()
            lines.append("<%0*X> <%s>" % (width, code, u16))
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(lines).encode("ascii")


class Font:
    """A font as used in content: a resource name, a PDF dict, and helpers."""

    def __init__(self, key, obj, widths, encode, kind, two_byte=False, vertical=False):
        self.key = key          # resource name used on every page, e.g. 'Sans'
        self.obj = obj
        self._widths = widths   # function: text -> width in 1/1000 em
        self._encode = encode   # function: text -> PDF string token
        self.kind = kind        # human description for labels
        self.two_byte = two_byte
        self.vertical = vertical

    def width(self, text, size):
        return self._widths(text) * size / 1000.0

    def enc(self, text):
        return self._encode(text)


def _winansi_encode(text):
    return _escape(text.encode("cp1252"))


def _descriptor_from_ttf(pdf, tt, name, flags, filekey, filestream):
    upm = tt["head"].unitsPerEm
    sc = 1000.0 / upm
    head, hhea = tt["head"], tt["hhea"]
    os2 = tt["OS/2"] if "OS/2" in tt else None
    cap = getattr(os2, "sCapHeight", 0) if os2 is not None else 0
    if not cap:
        cap = int(hhea.ascent * 0.7)
    d = Dictionary(
        Type=Name.FontDescriptor, FontName=Name("/" + name), Flags=flags,
        FontBBox=Array([int(head.xMin * sc), int(head.yMin * sc), int(head.xMax * sc), int(head.yMax * sc)]),
        ItalicAngle=float(tt["post"].italicAngle) if "post" in tt else 0,
        Ascent=int(hhea.ascent * sc), Descent=int(hhea.descent * sc), CapHeight=int(cap * sc),
        StemV=80 if (os2 is None or os2.usWeightClass < 600) else 140,
    )
    d[Name("/" + filekey)] = filestream
    return pdf.make_indirect(d)


class FontSet:
    def __init__(self, pdf):
        self.pdf = pdf
        self.fonts = {}

    def get(self, key):
        if key not in self.fonts:
            self.fonts[key] = getattr(self, "_make_" + key.lower())()
        return self.fonts[key]

    # -- Simple TrueType (FontFile2), WinAnsi ----------------------------------
    def _truetype(self, key, filename, flags, kind):
        path = find_font(filename)
        data, tt = _subset(path, [ord(c) for c in WINANSI_CHARS])
        psname = tt["name"].getDebugName(6) or os.path.splitext(filename)[0]
        name = _tag(path, "winansi") + "+" + psname
        upm = tt["head"].unitsPerEm
        cmap = tt.getBestCmap()
        hmtx = tt["hmtx"]
        widths = []
        for code in range(32, 256):
            glyph = WINANSI[code]
            ch = bytes([code]).decode("cp1252", errors="ignore")
            g = cmap.get(ord(ch)) if ch else None
            widths.append(int(round(hmtx[g][0] * 1000 / upm)) if g and glyph else 0)
        ff = pikepdf.Stream(self.pdf, data)
        ff.Length1 = len(data)
        desc = _descriptor_from_ttf(self.pdf, tt, name, flags, "FontFile2", ff)
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.TrueType, BaseFont=Name("/" + name),
            FirstChar=32, LastChar=255, Widths=Array(widths), Encoding=Name.WinAnsiEncoding,
            FontDescriptor=desc))

        def w(text):
            return sum(widths[b - 32] if b >= 32 else 0 for b in text.encode("cp1252"))

        return Font(key, obj, w, _winansi_encode, kind)

    def _make_sans(self):
        return self._truetype("Sans", "DejaVuSans.ttf", 32, "TrueType (FontFile2), WinAnsi")

    def _make_sansbold(self):
        return self._truetype("SansBold", "DejaVuSans-Bold.ttf", 32 | (1 << 18), "TrueType bold")

    def _make_mono(self):
        return self._truetype("Mono", "DejaVuSansMono.ttf", 32 | 1, "TrueType monospaced")

    def _make_serif(self):
        return self._truetype("Serif", "DejaVuSerif.ttf", 32 | 2, "TrueType (FontFile2)")

    # -- Standard 14, not embedded ---------------------------------------------
    # Font descriptor values for the standard 14, from the Adobe Core 14 AFM files (as shipped
    # with reportlab): flags, bounding box, italic angle, ascent, descent, cap height, stem.
    STD_DESC = {
        "Times": (34, [-168, -218, 1000, 898], 683, -217, 662, 84),
        "Helvetica": (32, [-166, -225, 1000, 931], 718, -207, 718, 88),
        "Courier": (33, [-23, -250, 715, 805], 629, -157, 562, 51),
        "Symbol": (4, [-180, -293, 1090, 1010], 1010, -293, 1010, 85),
        "ZapfDingbats": (4, [-1, -143, 981, 820], 820, -143, 820, 90),
    }

    def standard(self, base, bare=False):
        """A standard 14 font, not embedded. PDF 2.0 requires Widths and a FontDescriptor even
        for these (Table 109); bare=True leaves them out, as PDF 1.x files often do."""
        key = "Std" + base.replace("-", "") + ("Bare" if bare else "")
        if key in self.fonts:
            return self.fonts[key]
        d = Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/" + base))
        symbolic = base in ("Symbol", "ZapfDingbats")
        if not symbolic:
            d.Encoding = Name.WinAnsiEncoding
        if not bare:
            enc = _fontdata.encodings["SymbolEncoding" if base == "Symbol" else "ZapfDingbatsEncoding"] if symbolic else WINANSI
            glyphs = _fontdata.widthsByFontGlyph[base]
            widths = [glyphs.get(enc[c], 0) if enc[c] else 0 for c in range(32, 256)]
            family = base.split("-")[0]
            flags, bbox, asc, desc_, cap, stem = self.STD_DESC[family]
            if "Oblique" in base or "Italic" in base:
                flags |= 64
            d.FirstChar, d.LastChar, d.Widths = 32, 255, Array(widths)
            d.FontDescriptor = self.pdf.make_indirect(Dictionary(
                Type=Name.FontDescriptor, FontName=Name("/" + base), Flags=flags, FontBBox=Array(bbox),
                ItalicAngle=-12 if flags & 64 else 0, Ascent=asc, Descent=desc_, CapHeight=cap, StemV=stem))
        obj = self.pdf.make_indirect(d)

        def w(text):
            return pdfmetrics.stringWidth(text, base, 1000)

        def e(text):
            return _escape(text.encode("latin-1")) if symbolic else _winansi_encode(text)

        f = Font(key, obj, w, e, "Standard 14: " + base)
        self.fonts[key] = f
        return f

    # -- Type 1 embedded (FontFile) ----------------------------------------------
    def _make_t1(self):
        pfb = find_font("bchr8a.pfb")
        afm = os.path.splitext(pfb)[0] + ".afm"
        raw = open(pfb, "rb").read()
        segs, i = [], 0
        while i < len(raw):
            assert raw[i] == 0x80
            t = raw[i + 1]
            if t == 3:
                break
            n = int.from_bytes(raw[i + 2:i + 6], "little")
            if segs and segs[-1][0] == t:
                segs[-1] = (t, segs[-1][1] + raw[i + 6:i + 6 + n])
            else:
                segs.append((t, raw[i + 6:i + 6 + n]))
            i += 6 + n
        parts = [d for _, d in segs]
        prog = b"".join(parts)
        metrics, info = {}, {}
        for line in open(afm, encoding="latin-1"):
            if line.startswith("C "):
                fields = dict(p.strip().split(" ", 1) for p in line.split(";") if p.strip() and " " in p.strip())
                metrics[fields["N"]] = int(float(fields["WX"]))
            else:
                k, _, v = line.partition(" ")
                info[k] = v.strip()
        widths = [metrics.get(WINANSI[c] or "", 0) for c in range(32, 256)]
        ff = pikepdf.Stream(self.pdf, prog)
        ff.Length1, ff.Length2, ff.Length3 = len(parts[0]), len(parts[1]), len(parts[2]) if len(parts) > 2 else 0
        bbox = [int(float(v)) for v in info["FontBBox"].split()]
        name = info["FontName"]
        desc = self.pdf.make_indirect(Dictionary(
            Type=Name.FontDescriptor, FontName=Name("/" + name), Flags=34, FontBBox=Array(bbox),
            ItalicAngle=float(info.get("ItalicAngle", 0)), Ascent=int(float(info.get("Ascender", 700))),
            Descent=int(float(info.get("Descender", -200))), CapHeight=int(float(info.get("CapHeight", 650))),
            StemV=int(float(info.get("StdVW", 85))), FontFile=ff))
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/" + name), FirstChar=32, LastChar=255,
            Widths=Array(widths), Encoding=Name.WinAnsiEncoding, FontDescriptor=desc))

        def w(text):
            return sum(widths[b - 32] for b in text.encode("cp1252") if b >= 32)

        return Font("T1", obj, w, _winansi_encode, "Type 1 (FontFile), Bitstream Charter")

    # -- CFF: bare (Type1C) and OpenType (FontFile3) -------------------------------
    def _cff_simple(self, key, filename, subtype, kind):
        path = find_font(filename)
        data, tt = _subset(path, [ord(c) for c in WINANSI_CHARS], names=True)
        psname = tt["name"].getDebugName(6)
        name = _tag(path, subtype) + "+" + psname
        program = tt.getTableData("CFF ") if subtype == "Type1C" else data
        upm = tt["head"].unitsPerEm
        cmap, hmtx = tt.getBestCmap(), tt["hmtx"]
        widths = []
        for code in range(32, 256):
            ch = bytes([code]).decode("cp1252", errors="ignore")
            g = cmap.get(ord(ch)) if ch and WINANSI[code] else None
            widths.append(int(round(hmtx[g][0] * 1000 / upm)) if g else 0)
        ff = pikepdf.Stream(self.pdf, program)
        ff.Subtype = Name("/" + subtype)
        desc = _descriptor_from_ttf(self.pdf, tt, name, 32, "FontFile3", ff)
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/" + name), FirstChar=32, LastChar=255,
            Widths=Array(widths), Encoding=Name.WinAnsiEncoding, FontDescriptor=desc))

        def w(text):
            return sum(widths[b - 32] for b in text.encode("cp1252") if b >= 32)

        return Font(key, obj, w, _winansi_encode, kind)

    def _make_cff(self):
        return self._cff_simple("CFF", "Inter-Regular.otf", "Type1C", "Type1C (FontFile3), Inter")

    def _make_otf(self):
        return self._cff_simple("OTF", "Inter-Bold.otf", "OpenType", "OpenType CFF (FontFile3), Inter Bold")

    # -- Type 0 composite fonts ---------------------------------------------------
    TYPE0_TEXT = ("Ελληνικά Кириллица Ünïcödé "
                  "αβγδε ΑΒΓΔΕ абвгд АБВГД 0123456789 composite Identity-H CIDFontType2 Type 0")

    def _make_cid2(self):
        """Type 0 + CIDFontType2 (TrueType), Identity-H, CID = GID."""
        path = find_font("DejaVuSans.ttf")
        chars = set(self.TYPE0_TEXT) | set(string.printable[:95])
        data, tt = _subset(path, [ord(c) for c in chars], retain_gids=True)
        upm = tt["head"].unitsPerEm
        cmap, order, hmtx = tt.getBestCmap(), tt.getGlyphOrder(), tt["hmtx"]
        gid = {ch: order.index(cmap[ord(ch)]) for ch in chars if ord(ch) in cmap}
        name = _tag(path, "cid2") + "+DejaVuSans"
        ff = pikepdf.Stream(self.pdf, data)
        ff.Length1 = len(data)
        desc = _descriptor_from_ttf(self.pdf, tt, name, 32, "FontFile2", ff)
        wmap = {g: int(round(hmtx[order[g]][0] * 1000 / upm)) for g in gid.values()}
        W = Array()
        for g in sorted(wmap):
            W.append(g)
            W.append(Array([wmap[g]]))
        cid = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.CIDFontType2, BaseFont=Name("/" + name),
            CIDSystemInfo=Dictionary(Registry=String("Adobe"), Ordering=String("Identity"), Supplement=0),
            FontDescriptor=desc, DW=1000, W=W, CIDToGIDMap=Name.Identity))
        tu = pikepdf.Stream(self.pdf, to_unicode_cmap({g: ch for ch, g in gid.items()}, True))
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.Type0, BaseFont=Name("/" + name), Encoding=Name("/Identity-H"),
            DescendantFonts=Array([cid]), ToUnicode=tu))

        def w(text):
            return sum(wmap.get(gid.get(c, 0), 1000) for c in text)

        def e(text):
            return "<" + "".join("%04X" % gid.get(c, 0) for c in text) + ">"

        return Font("CID2", obj, w, e, "Type 0 + CIDFontType2, Identity-H", two_byte=True)

    CJK_TEXT = "縦書きの日本語テキスト。横書きの文字列、字体見本。色テーマ漢かんじにほんご割注（）"

    def _cid0(self, key, vertical):
        """Type 0 + CIDFontType0 (CID-keyed CFF from Noto Sans CJK), Identity-H or -V."""
        path = find_font("NotoSansCJK-Regular.ttc")
        chars = set(self.CJK_TEXT)
        data, tt = _subset(path, [ord(c) for c in chars], index=0, names=True)
        cmap, hmtx = tt.getBestCmap(), tt["hmtx"]
        upm = tt["head"].unitsPerEm
        cidof = {ch: int(cmap[ord(ch)][3:]) for ch in chars if ord(ch) in cmap}
        name = _tag(path, "cid0") + "+NotoSansCJKjp-Regular"
        ffkey = ("cid0prog", path)
        if ffkey not in self.fonts:
            ff = pikepdf.Stream(self.pdf, tt.getTableData("CFF "))
            ff.Subtype = Name.CIDFontType0C
            self.fonts[ffkey] = _descriptor_from_ttf(self.pdf, tt, name, 4, "FontFile3", ff)
        desc = self.fonts[ffkey]
        wmap = {c: int(round(hmtx[cmap[ord(ch)]][0] * 1000 / upm)) for ch, c in cidof.items()}
        W = Array()
        for c in sorted(wmap):
            W.append(c)
            W.append(Array([wmap[c]]))
        cid = Dictionary(
            Type=Name.Font, Subtype=Name.CIDFontType0, BaseFont=Name("/" + name),
            CIDSystemInfo=Dictionary(Registry=String("Adobe"), Ordering=String("Identity"), Supplement=0),
            FontDescriptor=desc, DW=1000, W=W)
        if vertical:
            vm = tt["vmtx"] if "vmtx" in tt else None
            W2 = Array()
            for ch, c in sorted(cidof.items(), key=lambda kv: kv[1]):
                g = cmap[ord(ch)]
                adv = vm[g][0] * 1000 / upm if vm else 1000
                W2.append(c)
                W2.append(c)
                W2.extend([-int(round(adv)), int(round(wmap[c] / 2)), 880])
            cid.DW2 = Array([880, -1000])
            cid.W2 = W2
        cid = self.pdf.make_indirect(cid)
        tu = pikepdf.Stream(self.pdf, to_unicode_cmap({c: ch for ch, c in cidof.items()}, True))
        obj = self.pdf.make_indirect(Dictionary(
            Type=Name.Font, Subtype=Name.Type0, BaseFont=Name("/" + name + ("-Identity-V" if vertical else "-Identity-H")),
            Encoding=Name("/Identity-V" if vertical else "/Identity-H"), DescendantFonts=Array([cid]), ToUnicode=tu))

        def w(text):
            return sum(1000 if vertical else wmap.get(cidof.get(c, 0), 1000) for c in text)

        def e(text):
            return "<" + "".join("%04X" % cidof.get(c, 0) for c in text) + ">"

        kind = "Type 0 + CIDFontType0 (CFF), Identity-" + ("V, vertical" if vertical else "H")
        return Font(key, obj, w, e, kind, two_byte=True, vertical=vertical)

    def _make_cid0(self):
        return self._cid0("CID0", False)

    def _make_cid0v(self):
        return self._cid0("CID0V", True)
