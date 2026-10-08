"""Pictures for the image pages, and an encoder for every image filter PDF has.

Photos are made procedurally from a fixed seed, so they are identical in both
builds and need no licence. Diagrams are palette images whose colours come
from the theme's roles, so a theme swaps only their colour table.
"""
import base64
import io
import struct
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, TiffImagePlugin

# -- pictures ----------------------------------------------------------------------


def photo(w=240, h=160, seed=7):
    """A landscape: sky, sun, hills and water with grain. The same in every build."""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    sky_top, sky_bot = np.array([40, 92, 170]), np.array([240, 190, 140])
    img = (sky_top[None, None] * (1 - y[..., None]) + sky_bot[None, None] * y[..., None]) * np.ones((h, w, 1))
    sun = ((x - 0.72) ** 2 * (w / h) ** 2 + (y - 0.42) ** 2) < 0.012
    img[sun] = [255, 236, 170]
    for k, (base, col) in enumerate([(0.55, (70, 96, 120)), (0.62, (52, 82, 70)), (0.70, (38, 64, 46))]):
        ridge = base + 0.06 * np.sin(x * (6 + 3 * k) + k) + 0.03 * np.sin(x * 23 + 2 * k)
        img[(y > ridge)[..., None].repeat(3, 2)[..., 0]] = col
    water = y[:, 0] > 0.78
    img[water] = img[water] * 0.55 + np.array([30, 70, 110]) * 0.45
    img += rng.normal(0, 6, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB")


def photo_gray(w=200, h=140, seed=11):
    return photo(w, h, seed).convert("L")


def photo16(w=120, h=80):
    """16-bit RGB samples, big-endian, as PDF wants."""
    p = np.asarray(photo(w, h, 3)).astype(np.uint16) * 257
    return p.astype(">u2").tobytes()


def diagram_indices(w=96, h=64, kinds=6):
    """A small bar chart as palette indices: 0 paper, 1 ink, 2 rule, 3.. bars."""
    a = np.zeros((h, w), np.uint8)
    a[h - 6, 4:w - 4] = 1
    a[4:h - 6, 4] = 1
    for gy in range(10, h - 6, 12):
        a[gy, 6:w - 4] = 2
    heights = [0.8, 0.55, 0.9, 0.35, 0.7, 0.5]
    bw = (w - 16) // kinds
    for i in range(kinds):
        x0 = 8 + i * bw
        top = int((h - 8) - heights[i % len(heights)] * (h - 16))
        a[top:h - 6, x0:x0 + bw - 3] = 3 + (i % (kinds))
    return a


def pack_bits(a, bpc):
    """Pack an index array into rows of bpc bits each."""
    h, w = a.shape
    if bpc == 8:
        return a.astype(np.uint8).tobytes()
    per = 8 // bpc
    rowbytes = (w * bpc + 7) // 8
    out = bytearray()
    for row in a:
        buf = bytearray(rowbytes)
        for i, v in enumerate(row):
            buf[i // per] |= (int(v) & ((1 << bpc) - 1)) << (8 - bpc * (1 + i % per))
        out += buf
    return bytes(out)


def line_art(w=128, h=96):
    """1-bit line art (0 black, 1 white) for fax and JBIG2 tiles."""
    im = Image.new("1", (w, h), 1)
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, w - 3, h - 3], outline=0, width=2)
    for i in range(6):
        d.line([10, 14 + i * 12, w - 10, 14 + i * 12], fill=0, width=1)
    d.ellipse([w - 46, h - 46, w - 10, h - 10], outline=0, width=3)
    d.text((10, h - 22), "FAX", fill=0)
    return im


def stencil_shape(w=64, h=64):
    """A triangle with a round hole. 0 bits mark the shape, as a stencil mask paints 0s."""
    im = Image.new("L", (w * 4, h * 4), 255)
    d = ImageDraw.Draw(im)
    d.polygon([(w * 2, 8), (w * 4 - 8, h * 4 - 8), (8, h * 4 - 8)], fill=0)
    d.ellipse([w * 2 - w * 0.6, h * 2 - h * 0.15, w * 2 + w * 0.6, h * 2 + h * 1.05], fill=255)
    return im.resize((w, h)).point(lambda v: 255 if v > 127 else 0).convert("1")


def alpha_disc(w=96, h=96):
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (w / 2)
    return np.clip((1 - r) * 1.6, 0, 1)


# -- filters -------------------------------------------------------------------------


def flate_png(raw, w, colors, bpc=8):
    """Flate with PNG 'Up' predictor rows (Predictor 15)."""
    rowlen = (w * colors * bpc + 7) // 8
    rows = [raw[i:i + rowlen] for i in range(0, len(raw), rowlen)]
    out, prev = bytearray(), bytes(rowlen)
    for r in rows:
        out.append(2)
        out += bytes((a - b) & 0xFF for a, b in zip(r, prev))
        prev = r
    return zlib.compress(bytes(out), 9)


def lzw(data, early=1):
    """LZWDecode encoder, 9-12 bit codes, EarlyChange as given."""
    CLEAR, EOD = 256, 257
    out_bits, nbits_total = 0, 0
    buf = bytearray()

    def emit(code, width):
        nonlocal out_bits, nbits_total
        out_bits = (out_bits << width) | code
        nbits_total += width
        while nbits_total >= 8:
            nbits_total -= 8
            buf.append((out_bits >> nbits_total) & 0xFF)

    table = {bytes([i]): i for i in range(256)}
    nxt, width = 258, 9
    emit(CLEAR, width)
    w = b""
    for b in data:
        wc = w + bytes([b])
        if wc in table:
            w = wc
            continue
        emit(table[w], width)
        table[wc] = nxt
        nxt += 1
        if nxt + early > (1 << width):
            if width == 12:
                emit(CLEAR, width)
                table = {bytes([i]): i for i in range(256)}
                nxt, width = 258, 9
            else:
                width += 1
        w = bytes([b])
    if w:
        emit(table[w], width)
        nxt += 1
        if nxt + early > (1 << width) and width < 12:
            width += 1
    emit(EOD, width)
    if nbits_total:
        buf.append((out_bits << (8 - nbits_total)) & 0xFF)
    return bytes(buf)


def runlength(data):
    out, i = bytearray(), 0
    while i < len(data):
        j = i
        while j < len(data) and j - i < 128 and data[j] == data[i]:
            j += 1
        if j - i >= 3:
            out += bytes([257 - (j - i), data[i]])
            i = j
            continue
        j = i
        while j < len(data) and j - i < 128 and not (j + 2 < len(data) and data[j] == data[j + 1] == data[j + 2]):
            j += 1
        out.append(j - i - 1)
        out += data[i:j]
        i = j
    out.append(128)
    return bytes(out)


def ascii_hex(data):
    h = data.hex().upper()
    return ("\n".join(h[i:i + 64] for i in range(0, len(h), 64)) + ">").encode()


def ascii85(data):
    return base64.a85encode(data, wrapcol=72) + b"~>"


def jpeg(im, **kw):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=kw.pop("quality", 85), **kw)
    return buf.getvalue()


def jpx(im, **kw):
    buf = io.BytesIO()
    im.save(buf, "JPEG2000", irreversible=True, quality_mode="rates", quality_layers=[24], **kw)
    return buf.getvalue()


def ccitt(im, scheme):
    """CCITT fax data from libtiff: scheme 'group4' (K -1) or 'group3' (K 0)."""
    buf = io.BytesIO()
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[278] = im.height  # one strip
    im.save(buf, "TIFF", compression=scheme, tiffinfo=info)
    t = Image.open(io.BytesIO(buf.getvalue()))
    off, cnt = t.tag_v2[273], t.tag_v2[279]
    off = off[0] if isinstance(off, tuple) else off
    cnt = cnt[0] if isinstance(cnt, tuple) else cnt
    photometric = t.tag_v2.get(262)
    return buf.getvalue()[off:off + cnt], photometric


def jbig2_mmr(im):
    """An embedded JBIG2 stream: page information, one immediate lossless generic
    region coded with MMR (the T.6 code), and end of page. 1 bits are black."""
    g4, photometric = ccitt(im, "group4")
    w, h = im.size

    def seg(number, stype, page, data):
        return (struct.pack(">I", number) + bytes([stype & 0x3F, 0x00, page])
                + struct.pack(">I", len(data)) + data)

    pageinfo = struct.pack(">IIIIB", w, h, 0, 0, 0) + struct.pack(">H", 0)
    region = struct.pack(">IIIIB", w, h, 0, 0, 0) + bytes([0x01]) + g4
    return seg(0, 48, 1, pageinfo) + seg(1, 39, 1, region) + seg(2, 49, 1, b""), photometric
