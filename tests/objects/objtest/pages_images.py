"""Pages for images: colour spaces and depths, every filter, masks and inline images."""
import io

import numpy as np
from PIL import Image, ImageCms
from pikepdf import Array, Dictionary, Name, String

from . import images as I
from .core import Page, n, rect_path
from .palette import HUES, fmt
from .resources import display_p3_icc


def ximage(doc, data, w, h, cs=None, bpc=8, **extra):
    s = doc.stream(data, Type=Name.XObject, Subtype=Name.Image, Width=w, Height=h)
    if cs is not None:
        s.ColorSpace = cs
    if bpc is not None:
        s.BitsPerComponent = bpc
    for k, v in extra.items():
        s[Name("/" + k)] = v
    return s


def place(p, key, img, rect, alt, aspect=None, pad=0):
    x, y, w, h = rect
    if aspect:
        if w / h > aspect:
            nw = h * aspect
            x += (w - nw) / 2
            w = nw
        else:
            nh = w / aspect
            y += (h - nh) / 2
            h = nh
    nm = p.use("XObject", key, img)
    p.figure("%s 0 0 %s %s %s cm %s Do" % (n(w - 2 * pad), n(h - 2 * pad), n(x + pad), n(y + pad), nm), alt)
    return x, y, w, h


def split(rect, k, gap=6):
    x, y, w, h = rect
    cw = (w - gap * (k - 1)) / k
    return [(x + i * (cw + gap), y, cw, h) for i in range(k)]


def lab_bytes(im):
    a = np.asarray(im).astype(np.float64) / 255
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    brad = np.array([[1.0478112, 0.0228866, -0.0501270], [0.0295424, 0.9904844, -0.0170491],
                     [-0.0092345, 0.0150436, 0.7521316]])
    xyz = lin @ (brad @ m).T / np.array([0.9642, 1.0, 0.8249])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    A = 500 * (f[..., 0] - f[..., 1])
    B = 200 * (f[..., 1] - f[..., 2])
    out = np.stack([L / 100 * 255, A + 128, B + 128], -1)
    return np.clip(np.round(out), 0, 255).astype(np.uint8).tobytes()


def to_p3(im):
    p3 = ImageCms.ImageCmsProfile(io.BytesIO(display_p3_icc()))
    srgb = ImageCms.createProfile("sRGB")
    return ImageCms.profileToProfile(im, srgb, p3, outputMode="RGB")


def indexed_space(doc, pal, roles, base=Name.DeviceRGB):
    lookup = bytes(int(round(c * 255)) for r in roles for c in pal.rgb(r))
    return doc.pdf.make_indirect(Array([Name.Indexed, base, len(roles) - 1, String(lookup)]))


# -- 8. Images: colour spaces and bit depths ----------------------------------------------------

def page_image_spaces(doc, res):
    p = Page(doc, "Images: colour spaces and bit depths",
             "Photos stay the same in every theme. Diagrams stored as palette (Indexed) images swap only "
             "their colour table, so a dark theme recolours them without touching the pixels.")
    pal = p.pal
    t = p.grid(3, 4)
    photo = I.photo(160, 106)
    aspect = 160 / 106

    r = p.tile(t[0], "DeviceGray, 8-bit photo", "T87, T61", "stays")
    g = photo.convert("L")
    place(p, "ImGray8", ximage(doc, g.tobytes(), g.width, g.height, Name.DeviceGray), r, "A greyscale photo.", aspect)

    r = p.tile(t[1], "DeviceGray at 1, 2 and 4 bits", "T87, T88", "stays")
    small = photo.convert("L").resize((80, 53))
    for i, (bpc, rr) in enumerate(zip([1, 2, 4], split(r, 3))):
        levels = (1 << bpc) - 1
        q = np.round(np.asarray(small) / 255 * levels).astype(np.uint8)
        place(p, "ImGray%d" % bpc, ximage(doc, I.pack_bits(q, bpc), 80, 53, Name.DeviceGray, bpc), rr,
              "The photo at %d bits per sample." % bpc, 80 / 53)

    r = p.tile(t[2], "DeviceRGB, 8-bit photo", "T87", "stays")
    place(p, "ImRGB8", ximage(doc, photo.tobytes(), photo.width, photo.height, Name.DeviceRGB), r, "A colour photo.", aspect)

    r = p.tile(t[3], "DeviceRGB, 16-bit samples", "T87", "stays")
    place(p, "ImRGB16", ximage(doc, I.photo16(120, 80), 120, 80, Name.DeviceRGB, 16), r,
          "A colour photo with 16 bits per sample.", 1.5)

    r = p.tile(t[4], "DeviceCMYK photo", "T87, T61", "stays")
    cmyk = photo.convert("CMYK")
    place(p, "ImCMYK", ximage(doc, cmyk.tobytes(), cmyk.width, cmyk.height, Name.DeviceCMYK), r, "A CMYK photo.", aspect)

    r = p.tile(t[5], "Lab photo", "T87, T64", "stays")
    place(p, "ImLab", ximage(doc, lab_bytes(photo), photo.width, photo.height, res.lab()), r, "A photo in Lab.", aspect)

    r = p.tile(t[6], "ICCBased: sRGB and Display P3", "T87, T65", "stays")
    a, b = split(r, 2)
    place(p, "ImsRGB", ximage(doc, photo.tobytes(), photo.width, photo.height, res.icc("srgb")), a, "Photo in sRGB.", aspect)
    p3 = to_p3(photo)
    place(p, "ImP3", ximage(doc, p3.tobytes(), p3.width, p3.height, res.icc("p3")), b, "Photo in Display P3.", aspect)

    idx = I.diagram_indices(96, 64)
    r = p.tile(t[7], "Indexed, 8-bit diagram", "T87, T61", "swaps", note="Only the colour table changes")
    place(p, "ImIdx8", ximage(doc, idx.tobytes(), 96, 64, res.indexed("rgb")), r, "A bar chart stored as a palette image.", 1.5)

    r = p.tile(t[8], "Indexed at 1, 2 and 4 bits", "T87, T61", "swaps")
    tables = {1: ["paper", "ink"], 2: ["paper", "ink", "accent", "red"],
              4: ["paper", "ink", "rule"] + HUES}
    for bpc, rr in zip([1, 2, 4], split(r, 3)):
        roles = tables[bpc]
        q = np.minimum(idx, len(roles) - 1) if bpc == 4 else np.where(idx >= 3, (idx % (len(roles) - 1)) + 1, np.minimum(idx, 1))
        cs = indexed_space(doc, pal, roles)
        place(p, "ImIdx%d" % bpc, ximage(doc, I.pack_bits(q, bpc), 96, 64, cs, bpc), rr,
              "A bar chart in a %d-bit palette image." % bpc, 1.5)

    r = p.tile(t[9], "Indexed over Lab and ICC", "T87, T61", "swaps")
    a, b = split(r, 2)
    place(p, "ImIdxLab", ximage(doc, idx.tobytes(), 96, 64, res.indexed("lab")), a, "Bar chart, palette over Lab.", 1.5)
    place(p, "ImIdxICC", ximage(doc, idx.tobytes(), 96, 64, res.indexed("icc")), b, "Bar chart, palette over ICC sRGB.", 1.5)

    r = p.tile(t[10], "Separation image (spot ink)", "T87, T61", "swaps", note="Tints of the teal spot ink")
    tint = 255 - np.asarray(photo.convert("L"))
    place(p, "ImSep", ximage(doc, tint.astype(np.uint8).tobytes(), photo.width, photo.height, res.separation("teal")),
          r, "The photo printed in one spot ink.", aspect)

    r = p.tile(t[11], "DeviceN image (two spot inks)", "T87, T70", "swaps")
    gg = np.asarray(photo.convert("L")).astype(np.float64) / 255
    yy = np.linspace(0, 1, photo.height)[:, None] * np.ones((1, photo.width))
    two = np.stack([(1 - gg) * (1 - yy), (1 - gg) * yy], -1)
    place(p, "ImDevN", ximage(doc, np.round(two * 255).astype(np.uint8).tobytes(), photo.width, photo.height,
                              res.devicen()), r, "The photo split between teal and orange spot inks.", aspect)
    return p


# -- 9. Images: filters ------------------------------------------------------------------------------

def page_image_filters(doc, res):
    p = Page(doc, "Images: every filter",
             "The same pictures compressed every way PDF allows. Filters change how pixels are stored, not "
             "what they look like, so each tile should look the same in every theme except the palette diagrams.")
    pal = p.pal
    t = p.grid(3, 5)
    photo = I.photo(120, 80)
    raw = photo.tobytes()
    aspect = 1.5

    def rgb(key, data, rect, alt, **extra):
        return place(p, key, ximage(doc, data, 120, 80, Name.DeviceRGB, **extra), rect, alt, aspect)

    r = p.tile(t[0], "FlateDecode", "T6, T8", "stays")
    import zlib
    rgb("ImFl", zlib.compress(raw, 9), r, "Photo, Flate.", Filter=Name.FlateDecode)

    r = p.tile(t[1], "FlateDecode with PNG predictor", "T8, T9, T10", "stays")
    rgb("ImFlP", I.flate_png(raw, 120, 3), r, "Photo, Flate with PNG Up predictor.", Filter=Name.FlateDecode,
        DecodeParms=Dictionary(Predictor=15, Colors=3, BitsPerComponent=8, Columns=120))

    r = p.tile(t[2], "LZWDecode", "T6, T7, T8", "stays")
    rgb("ImLZW", I.lzw(raw), r, "Photo, LZW.", Filter=Name.LZWDecode)

    r = p.tile(t[3], "RunLengthDecode", "T6", "swaps", note="A palette diagram, so it swaps")
    idx = I.diagram_indices(96, 64)
    place(p, "ImRL", ximage(doc, I.runlength(idx.tobytes()), 96, 64, res.indexed("rgb"), Filter=Name.RunLengthDecode),
          r, "Bar chart, run-length encoded.", 1.5)

    r = p.tile(t[4], "ASCIIHexDecode then Flate", "T6", "stays", note="A filter chain")
    rgb("ImAHx", I.ascii_hex(zlib.compress(raw, 9)), r, "Photo, hex then Flate.",
        Filter=Array([Name.ASCIIHexDecode, Name.FlateDecode]))

    r = p.tile(t[5], "ASCII85Decode", "T6", "stays")
    rgb("ImA85", I.ascii85(raw), r, "Photo, ASCII85.", Filter=Name.ASCII85Decode)

    r = p.tile(t[6], "DCTDecode (JPEG), baseline", "T6, T13", "stays")
    rgb("ImDCT", I.jpeg(photo), r, "Photo, baseline JPEG.", Filter=Name.DCTDecode)

    r = p.tile(t[7], "DCTDecode, progressive greyscale", "T6, T13", "stays")
    g = photo.convert("L")
    place(p, "ImDCTg", ximage(doc, I.jpeg(g, progressive=True), 120, 80, Name.DeviceGray, Filter=Name.DCTDecode),
          r, "Photo, progressive greyscale JPEG.", aspect)

    r = p.tile(t[8], "DCTDecode, CMYK (Adobe)", "T6, T13, T88", "stays")
    place(p, "ImDCTk", ximage(doc, I.jpeg(photo.convert("CMYK")), 120, 80, Name.DeviceCMYK, Filter=Name.DCTDecode,
                              Decode=Array([1, 0, 1, 0, 1, 0, 1, 0])), r, "Photo, CMYK JPEG.", aspect)

    r = p.tile(t[9], "JPXDecode (JPEG 2000)", "T6", "stays", note="Colour space comes from the codestream")
    place(p, "ImJPX", ximage(doc, I.jpx(photo), 120, 80, None, None, Filter=Name.JPXDecode), r, "Photo, JPEG 2000.", aspect)

    art = I.line_art(128, 96)
    for i, (scheme, k, key, title) in enumerate([("group4", -1, "ImG4", "CCITTFaxDecode, Group 4"),
                                                  ("group3", 0, "ImG3", "CCITTFaxDecode, Group 3")]):
        r = p.tile(t[10 + i], title, "T6, T11", "stays")
        data, photometric = I.ccitt(art, scheme)
        parms = Dictionary(K=k, Columns=128, Rows=96, BlackIs1=(photometric == 1))
        if k == 0:
            parms.EndOfLine = False
            parms.EncodedByteAlign = False
        place(p, key, ximage(doc, data, 128, 96, Name.DeviceGray, 1, Filter=Name.CCITTFaxDecode, DecodeParms=parms),
              r, "Fax-coded line art.", 128 / 96)

    r = p.tile(t[12], "JBIG2Decode (generic region, MMR)", "T6, T12", "stays")
    data, photometric = I.jbig2_mmr(art)
    place(p, "ImJB2", ximage(doc, data, 128, 96, Name.DeviceGray, 1, Filter=Name.JBIG2Decode,
                             Decode=Array([1, 0]) if photometric == 1 else Array([0, 1])),
          r, "JBIG2-coded line art.", 128 / 96)

    r = p.tile(t[13], "Interpolate: false and true", "T87", "stays")
    tiny = photo.resize((12, 8), Image.NEAREST)
    a, b = split(r, 2)
    place(p, "ImNoInt", ximage(doc, tiny.tobytes(), 12, 8, Name.DeviceRGB, Interpolate=False), a, "A 12 by 8 image, blocky.", 1.5)
    place(p, "ImInt", ximage(doc, tiny.tobytes(), 12, 8, Name.DeviceRGB, Interpolate=True), b, "The same image, smoothed.", 1.5)

    r = p.tile(t[14], "Alternates and a Decode array", "T87, T89, T88", "stays",
                note="Left has a print alternate; right is inverted by Decode")
    a, b = split(r, 2)
    alt_img = ximage(doc, photo.convert("L").tobytes(), 120, 80, Name.DeviceGray)
    place(p, "ImAlt", ximage(doc, raw, 120, 80, Name.DeviceRGB,
                             Alternates=Array([Dictionary(Image=alt_img, DefaultForPrinting=True)])), a,
          "Photo with a greyscale alternate for printing.", aspect)
    place(p, "ImDec", ximage(doc, raw, 120, 80, Name.DeviceRGB, Decode=Array([1, 0, 1, 0, 1, 0])), b,
          "Photo inverted by its Decode array.", aspect)
    return p


# -- 10. Masks and inline images ------------------------------------------------------------------------

def page_masks(doc, res):
    p = Page(doc, "Masks and inline images",
             "Stencil masks take the fill colour, so they swap. Masked and soft-masked photos stay. Inline images "
             "live inside the content stream; an inline palette image swaps through its named colour space.")
    pal = p.pal
    t = p.grid(3, 3)
    photo = I.photo(120, 80)

    st = I.stencil_shape(64, 64)
    stencil = ximage(doc, st.tobytes(), 64, 64, None, 1, ImageMask=True)
    r = p.tile(t[0], "Stencil mask (ImageMask)", "T87, T88", "swaps", note="Painted in the current fill colour")
    x, y, w, h = r
    p.use("XObject", "ImStencil", stencil)
    s = min(w / 3, h) - 4
    p.figure(" ".join("q %s %s 0 0 %s %s %s cm /ImStencil Do Q" % (pal.rg(role), n(s), n(s), n(x + i * w / 3 + 2), n(y + (h - s) / 2))
                      for i, role in enumerate(["ink", "accent", "red"])), "A stencil shape painted in three colours.")

    r = p.tile(t[1], "Stencil mask with Decode [1 0]", "T88", "swaps", note="The same mask, inverted")
    x, y, w, h = r
    p.use("XObject", "ImStencilInv", ximage(doc, st.tobytes(), 64, 64, None, 1, ImageMask=True, Decode=Array([1, 0])))
    p.figure("%s %s 0 0 %s %s %s cm /ImStencilInv Do" % (pal.rg("green"), n(min(w, h)), n(min(w, h)), n(x + (w - min(w, h)) / 2), n(y)),
             "An inverted stencil painted green.")

    r = p.tile(t[2], "Explicit mask (Mask stream)", "T87", "stays")
    mask = I.stencil_shape(120, 80)
    mimg = ximage(doc, mask.tobytes(), 120, 80, None, 1, ImageMask=True)
    place(p, "ImMasked", ximage(doc, photo.tobytes(), 120, 80, Name.DeviceRGB, Mask=mimg), r,
          "A photo cut to a triangle by an explicit mask.", 1.5)

    r = p.tile(t[3], "Colour-key mask (Mask array)", "T87", "swaps", note="Index 0 (paper) is keyed out")
    idx = I.diagram_indices(96, 64)
    place(p, "ImKeyed", ximage(doc, idx.tobytes(), 96, 64, res.indexed("rgb"), Mask=Array([0, 0])), r,
          "A bar chart with a transparent background.", 1.5)

    yy, xx = np.mgrid[0:80, 0:120]
    a = np.clip(1.4 - np.sqrt(((xx - 60) / 60) ** 2 + ((yy - 40) / 40) ** 2), 0, 1)
    smask = ximage(doc, np.round(a * 255).astype(np.uint8).tobytes(), 120, 80, Name.DeviceGray)
    r = p.tile(t[4], "Soft mask (SMask)", "T87, T143", "stays")
    x, y, w, h = r
    p.use("XObject", "ImSoft", ximage(doc, photo.tobytes(), 120, 80, Name.DeviceRGB, SMask=smask))
    stripes = " ".join(rect_path(x + i * 8, y, 4, h) for i in range(int(w / 8) + 1))
    p.figure("%s %s f %s 0 0 %s %s %s cm /ImSoft Do" % (pal.rg("rule"), stripes, n(w), n(h), n(x), n(y)),
             "A photo fading out at the edges over stripes.")

    r = p.tile(t[5], "Soft mask with Matte", "T144", "stays", note="Colours premultiplied against white")
    x, y, w, h = r
    pa = np.asarray(photo).astype(np.float64)
    pre = 255 + a[..., None] * (pa - 255)
    matte = ximage(doc, np.round(a * 255).astype(np.uint8).tobytes(), 120, 80, Name.DeviceGray, Matte=Array([1, 1, 1]))
    p.use("XObject", "ImMatte", ximage(doc, np.clip(np.round(pre), 0, 255).astype(np.uint8).tobytes(), 120, 80,
                                       Name.DeviceRGB, SMask=matte))
    stripes = " ".join(rect_path(x + i * 8, y, 4, h) for i in range(int(w / 8) + 1))
    p.figure("%s %s f %s 0 0 %s %s %s cm /ImMatte Do" % (pal.rg("rule"), stripes, n(w), n(h), n(x), n(y)),
             "The faded photo, premultiplied.")

    r = p.tile(t[6], "JPEG 2000 with SMaskInData", "T87", "stays")
    x, y, w, h = r
    rgba = photo.copy()
    rgba.putalpha(Image.fromarray(np.round(a * 255).astype(np.uint8)))
    p.use("XObject", "ImJPXa", ximage(doc, I.jpx(rgba), 120, 80, None, None, Filter=Name.JPXDecode, SMaskInData=1))
    stripes = " ".join(rect_path(x + i * 8, y, 4, h) for i in range(int(w / 8) + 1))
    p.figure("%s %s f %s 0 0 %s %s %s cm /ImJPXa Do" % (pal.rg("rule"), stripes, n(w), n(h), n(x), n(y)),
             "A JPEG 2000 photo carrying its own alpha.")

    r = p.tile(t[7], "Inline images: grey, RGB, Indexed", "T90, T91, T92", "swaps",
               note="Indexed swaps through a named space; grey and RGB stay")
    x, y, w, h = r
    p.use("ColorSpace", "CSIdx", res.indexed("rgb"))
    g = photo.convert("L").resize((30, 20))
    rgbsmall = photo.resize((30, 20))
    di = I.diagram_indices(48, 32)
    cells = split(r, 3)
    body = []
    for (cx, cy, cw, ch), (hdr, data) in zip(cells, [
            ("/W 30 /H 20 /CS /G /BPC 8 /F /AHx", I.ascii_hex(g.tobytes()).decode()),
            ("/W 30 /H 20 /CS /RGB /BPC 8 /F /AHx", I.ascii_hex(rgbsmall.tobytes()).decode()),
            ("/W 48 /H 32 /CS /CSIdx /BPC 8 /F /AHx", I.ascii_hex(di.tobytes()).decode())]):
        hh = cw / 1.5
        body.append("q %s 0 0 %s %s %s cm BI %s ID\n%s\nEI Q" % (n(cw), n(hh), n(cx), n(cy + (ch - hh) / 2), hdr, data))
    p.figure("\n".join(body), "Three small inline images: grey, colour and a palette bar chart.")

    r = p.tile(t[8], "Inline stencil mask", "T91", "swaps")
    x, y, w, h = r
    small = I.stencil_shape(32, 32)
    data = I.ascii_hex(small.tobytes()).decode()
    s = min(w / 2, h) - 4
    p.figure(" ".join("q %s %s 0 0 %s %s %s cm BI /W 32 /H 32 /IM true /BPC 1 /F /AHx ID\n%s\nEI Q" % (
        pal.rg(role), n(s), n(s), n(x + i * w / 2 + 2), n(y + (h - s) / 2), data) for i, role in enumerate(["purple", "orange"])),
             "An inline stencil painted purple and orange.")
    return p
