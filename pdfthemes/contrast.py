"""Text contrast in a rendered PDF, measured the WCAG 2.2 way, using PDFium.

check(pdf) renders each page on the theme's paper, finds every run of
visible text with its colour and size, reads what is drawn behind it, and
returns the contrast ratio of each run with the minimum it needs: 4.5:1, or
3:1 for large text (at least 18 pt, or 14 pt bold).
"""

from __future__ import annotations

import ctypes
import hashlib

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from .colour import contrast

INVISIBLE = (3, 7)  # text render modes that draw nothing themselves (7 only clips)
STROKED = (1, 5)    # modes that draw the outline only, in the stroke colour
BOTH = (2, 6)       # modes that fill and outline
DRAWN = 40          # a run's colour must appear within this many levels, or it is not what is drawn


def _runs(textpage):
    """Visible text as runs of characters sharing a colour, size and line.
    Spaces join a run rather than end it, so a run is usually a phrase."""
    n = textpage.count_chars()
    raw = textpage.raw
    r, g, b, a = (ctypes.c_uint() for _ in range(4))
    left_, bottom_, right_, top_ = (ctypes.c_double() for _ in range(4))
    loose = pdfium_c.FS_RECTF()
    runs, current, space = [], None, False
    for i in range(n):
        ch = textpage.get_text_range(i, 1)
        if not ch or ch in "\r\n":
            current = None
            continue
        if ch.isspace():
            space = True
            continue
        obj = pdfium_c.FPDFText_GetTextObject(raw, i)
        mode = pdfium_c.FPDFTextObj_GetTextRenderMode(obj) if obj else 0
        if mode in INVISIBLE:
            current = None
            continue
        get_colour = pdfium_c.FPDFText_GetStrokeColor if mode in STROKED else pdfium_c.FPDFText_GetFillColor
        if not get_colour(raw, i, r, g, b, a):
            continue
        colour = (r.value, g.value, b.value)
        if mode in BOTH:  # filled and outlined: one colour only if the two match
            r2, g2, b2, a2 = (ctypes.c_uint() for _ in range(4))
            if pdfium_c.FPDFText_GetStrokeColor(raw, i, r2, g2, b2, a2) and \
                    max(abs(x - y) for x, y in zip(colour, (r2.value, g2.value, b2.value))) > DRAWN:
                colour = None
        alpha = a.value / 255
        size = round(pdfium_c.FPDFText_GetFontSize(raw, i), 1)
        weight = pdfium_c.FPDFText_GetFontWeight(raw, i)
        if pdfium_c.FPDFText_GetLooseCharBox(raw, i, loose):
            box = [loose.left, loose.bottom, loose.right, loose.top]
        else:
            box = list(textpage.get_charbox(i))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        key = (colour, alpha, size, weight, mode in BOTH)
        if current is not None and current["key"] == key and abs(current["bottom"] - box[1]) < size * 0.5 \
                and box[0] - current["box"][2] < size * 1.5:
            current["text"] += (" " if space else "") + ch
            current["box"] = [min(current["box"][0], box[0]), min(current["box"][1], box[1]),
                              max(current["box"][2], box[2]), max(current["box"][3], box[3])]
        else:
            current = {"key": key, "text": ch, "bottom": box[1], "box": box}
            runs.append(current)
        space = False
    out = []
    for run in runs:
        colour, alpha, size, weight, _ = run["key"]
        out.append({"text": run["text"], "colour": colour, "alpha": alpha, "size": size,
                    "bold": weight >= 600, "box": run["box"]})
    return out


def check(path_or_bytes, paper=(1.0, 1.0, 1.0), scale=3.0, enhanced=False, drawn=None):
    """Contrast of every run of text. Each result has the page number, the
    text, its colour and background, the ratio found and the ratio needed.
    Text whose colour is not what is drawn (a gradient fill, or Type 3 glyphs
    that carry their own colours) is listed with ratio None: unmeasured.
    enhanced: hold text to 7:1 and large text to 4.5:1 (WCAG 1.4.6, AAA)
    rather than 4.5:1 and 3:1 (1.4.3, AA).
    drawn: a list to which a fingerprint of each drawn page is added, so two
    themes can be compared without keeping their pages."""
    minimum, minimum_large = (7.0, 4.5) if enhanced else (4.5, 3.0)
    doc = pdfium.PdfDocument(path_or_bytes)
    fill = tuple(round(c * 255) for c in paper) + (255,)
    results = []
    for pno in range(len(doc)):
        page = doc[pno]
        width, height = page.get_size()
        pixels = np.asarray(page.render(scale=scale, fill_color=fill).to_pil().convert("RGB"))
        if drawn is not None:
            drawn.append(hashlib.blake2b(pixels.tobytes(), digest_size=16).hexdigest())
        img = pixels.astype(float)
        for run in _runs(page.get_textpage()):
            left, bottom, right, top = run["box"]
            x0, x1 = int(left * scale), int(np.ceil(right * scale))
            y0, y1 = int((height - top) * scale), int(np.ceil((height - bottom) * scale))
            region = img[max(y0, 0):y1, max(x0, 0):x1].reshape(-1, 3)
            if len(region) == 0:
                continue
            fg = np.array(run["colour"] if run["colour"] is not None else (0, 0, 0), dtype=float)
            dist = np.abs(region - fg).max(axis=1)
            if run["colour"] is None or dist.min() > DRAWN:
                results.append({"page": pno + 1, "text": run["text"][:40], "size": run["size"], "large": False,
                                "colour": "#%02X%02X%02X" % run["colour"] if run["colour"] else None,
                                "background": None, "ratio": None, "needs": None})
                continue
            # The background is the pixels least like the text: anti-aliased
            # edges, which blend the two, are left out.
            far = region[dist >= 0.9 * dist.max()] if dist.max() > 0 else region
            if len(far) > 600:
                far = far[np.linspace(0, len(far) - 1, 600).astype(int)]
            shown = np.clip(run["alpha"] * fg + (1 - run["alpha"]) * far, 0, 255)
            ratios = np.array([contrast(s / 255, f / 255) for s, f in zip(shown, far)])
            worst = float(np.percentile(ratios, 10)) if len(ratios) else 21.0
            behind = far[np.argsort(ratios)[int(0.1 * (len(ratios) - 1))]] if len(ratios) else far[0]
            large = run["size"] >= 18 or (run["size"] >= 14 and run["bold"])
            results.append({"page": pno + 1, "text": run["text"][:40], "size": run["size"], "large": large,
                            "colour": "#%02X%02X%02X" % run["colour"],
                            "background": "#%02X%02X%02X" % tuple(int(v) for v in np.median(far, axis=0)),
                            "behind": "#%02X%02X%02X" % tuple(int(v) for v in behind),
                            "ratio": round(worst, 2), "needs": minimum_large if large else minimum})
    return results


def summary(results):
    measured = [r for r in results if r["ratio"] is not None]
    fails = [r for r in measured if r["ratio"] < r["needs"]]
    lowest = min(measured, key=lambda r: r["ratio"]) if measured else None
    return {"runs": len(measured), "unmeasured": len(results) - len(measured), "failures": fails, "lowest": lowest}
