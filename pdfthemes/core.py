"""Colour themes in PDF: proof of concept.

The reader side, and helpers shared by the writer (merge.py, derive.py).

apply(pdf, name)
    What a reader does to show a theme: replace each object named in the
    theme's Replace array, then draw the page as usual. Returns the theme's
    paper colour, which the reader paints before the page.

describe(pdf)
    The themes, palettes and replacements in a themed file, for people.

The theme dictionary sits under the catalog key /XXThemes. XX marks a
third-class (private) name in ISO 32000-2 Annex E, which is right for a proof
of concept. A standard version would use a first-class key such as /Themes.
"""

from __future__ import annotations

import decimal
import hashlib

import pikepdf
from pikepdf import Array, Dictionary, Name

THEMES_KEY = "/XXThemes"
ALPHA_KEYS = ("/CA", "/ca")

# How a themed file is saved: compressed object streams, so sizes compare
# fairly, and the author's XMP metadata kept byte for byte. pikepdf would
# otherwise rewrite the metadata, which a PDF/A file is better without.
SAVE = dict(compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate, deterministic_id=True,
            fix_metadata_version=False)


class MergeError(Exception):
    """The two builds draw different shapes, so they cannot share content."""


# ── Comparing objects ────────────────────────────────────────────────────────

def stream_data(stream) -> bytes:
    """A stream's decoded bytes, or its raw bytes where qpdf doesn't decode
    the filter (JPEG and JPEG 2000 images, for instance)."""
    try:
        return stream.read_bytes()
    except pikepdf.PdfError:
        return stream.read_raw_bytes()


def canon(obj, _seen=None):
    """A hashable value that is equal for objects with the same content,
    wherever they live. Streams compare by their decoded bytes."""
    if _seen is None:
        _seen = set()
    if isinstance(obj, (pikepdf.Stream, pikepdf.Dictionary, pikepdf.Array)) and obj.is_indirect:
        if obj.objgen in _seen:
            return ("cycle",)
        _seen = _seen | {obj.objgen}
    if isinstance(obj, pikepdf.Stream):
        items = tuple(sorted((k, canon(v, _seen)) for k, v in obj.items()
                             if k not in ("/Length", "/Filter", "/DecodeParms")))
        return ("stream", items, hashlib.sha256(stream_data(obj)).hexdigest())
    if isinstance(obj, pikepdf.Dictionary):
        return ("dict", tuple(sorted((k, canon(v, _seen)) for k, v in obj.items())))
    if isinstance(obj, pikepdf.Array):
        return ("array", tuple(canon(v, _seen) for v in obj))
    if isinstance(obj, pikepdf.Name):
        return ("name", str(obj))
    if isinstance(obj, pikepdf.String):
        return ("string", bytes(obj))
    if isinstance(obj, bool):
        return ("bool", obj)
    if isinstance(obj, (int, float, decimal.Decimal)):
        return ("num", round(float(obj), 5))
    if obj is None:
        return ("null",)
    if isinstance(obj, pikepdf.Object):
        try:
            return ("num", round(float(obj), 5))
        except (TypeError, ValueError):
            pass
    return ("other", repr(obj))


class Grafter:
    """Copies objects from another PDF, reusing streams the target already
    holds (an ICC profile or a font program is not copied twice)."""

    def __init__(self, target: pikepdf.Pdf):
        self.target = target
        self.memo: dict[tuple[int, int], object] = {}
        self.streams: dict[tuple, pikepdf.Stream] = {}
        for obj in target.objects:
            if isinstance(obj, pikepdf.Stream):
                self.streams.setdefault(self._stream_key(obj), obj)

    @staticmethod
    def _stream_key(s):
        return canon(s)  # the whole dictionary and the data: a gradient's function or an image's Decode counts

    def copy(self, obj):
        if not isinstance(obj, (pikepdf.Stream, pikepdf.Dictionary, pikepdf.Array)):
            return obj
        indirect = obj.is_indirect
        if indirect and obj.is_owned_by(self.target):
            return obj  # already in the target (an object made while merging)
        if indirect and obj.objgen in self.memo:
            return self.memo[obj.objgen]
        if isinstance(obj, pikepdf.Stream):
            result = self.streams.get(self._stream_key(obj))
            if result is None:
                result = self.target.copy_foreign(obj)
        elif isinstance(obj, pikepdf.Dictionary):
            result = Dictionary({k: self.copy(v) for k, v in obj.items()})
            if indirect:
                result = self.target.make_indirect(result)
        else:
            result = Array([self.copy(v) for v in obj])
            if indirect:
                result = self.target.make_indirect(result)
        if indirect:
            self.memo[obj.objgen] = result
        return result



# ── What a reader does ───────────────────────────────────────────────────────

def themes(pdf: pikepdf.Pdf) -> list[str]:
    t = pdf.Root.get(THEMES_KEY)
    if t is None:
        return []
    return [str(t.Default.Name)] + [str(a.Name) for a in t.Alternates]


def apply(pdf: pikepdf.Pdf, name: str):
    """Show the theme called `name`: swap each base object for its
    replacement. Returns the theme's paper colour (sRGB, 0 to 1)."""
    t = pdf.Root[THEMES_KEY]
    if str(t.Default.Name) == name:
        theme = t.Default
    else:
        matches = [a for a in t.Alternates if str(a.Name) == name]
        if not matches:
            raise KeyError(name)
        theme = matches[0]
        rep = theme.Replace
        for k in range(0, len(rep), 2):
            pdf._swap_objects(rep[k].objgen, rep[k + 1].objgen)
    paper = theme.get("/Paper")
    return tuple(float(v) for v in paper) if paper is not None else (1.0, 1.0, 1.0)


def paint_paper(pdf: pikepdf.Pdf, rgb):
    """Write the paper colour into each page, for viewers that always draw on
    white. A theme-aware reader paints it itself instead."""
    if rgb == (1.0, 1.0, 1.0):
        return
    for page in pdf.pages:
        x0, y0, x1, y1 = [float(v) for v in page.mediabox]
        under = pdf.make_stream(
            f"q {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} rg {x0} {y0} {x1 - x0} {y1 - y0} re f Q\n".encode())
        page.contents_add(under, prepend=True)


# ── For people: what a themed file contains ──────────────────────────────────

def _kind(obj):
    if isinstance(obj, pikepdf.Array) and len(obj) and obj[0] == Name.Indexed:
        return "palette"
    if isinstance(obj, pikepdf.Stream) and (obj.get("/Subtype") == Name.Image or "/Width" in obj):
        return "image"  # thumbnails have no Subtype
    if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
        if "/PatternType" in obj or "/ShadingType" in obj:
            return "gradient"
        if obj.get("/Type") == Name.ExtGState or any(k in obj for k in ("/CA", "/ca", "/BM", "/SMask")) \
                and "/Subtype" not in obj:
            return "graphics state"
        if obj.get("/Type") == Name.Annot:
            return "annotation"
    if isinstance(obj, pikepdf.Array):
        return "colour value"
    if isinstance(obj, pikepdf.String):
        return "text style"
    return "object"


def _palette(arr):
    from . import colour as C
    base = arr[1]
    n = C.components(base)
    data = C.indexed_lookup(arr)
    rng = C.ranges(base)
    out = []
    for i in range(int(arr[2]) + 1):
        rgb = C.to_srgb(base, C.dequantise(data[i * n:(i + 1) * n], rng))
        out.append(C.rgb_hex(rgb))
    return out


def _ref(obj):
    return f"{obj.objgen[0]} {obj.objgen[1]} R"


def describe(pdf: pikepdf.Pdf) -> dict | None:
    """The themes in a file, each alternate's replacements, and the colours
    of every palette it swaps. None when the file has no themes."""
    t = pdf.Root.get(THEMES_KEY)
    if t is None:
        return None

    def info(d, default):
        checked = d.get("/Checked")
        return {
            "name": str(d.Name),
            "default": default,
            "color_scheme": str(d.get("/ColorScheme", "")).lstrip("/"),
            "contrast": str(d.get("/Contrast", "")).lstrip("/"),
            "tint": str(d.get("/Tint", "")).lstrip("/"),
            "paper": [float(v) for v in d.get("/Paper", [1, 1, 1])],
            "checked": {k.lstrip("/"): str(v).lstrip("/") for k, v in checked.items()} if checked else None,
        }

    themes_out = [info(t.Default, True)]
    for alt in t.Alternates:
        entry = info(alt, False)
        rep, pairs = alt.Replace, []
        for k in range(0, len(rep), 2):
            base, new = rep[k], rep[k + 1]
            kind = _kind(base)
            item = {"kind": kind, "base": _ref(base), "replacement": _ref(new)}
            if kind == "palette":
                item["default_colours"], item["theme_colours"] = _palette(base), _palette(new)
            elif kind == "graphics state":
                item["default"] = {k.lstrip("/"): str(v) for k, v in base.items() if k in ALPHA_KEYS + ("/BM",)}
                item["theme"] = {k.lstrip("/"): str(v) for k, v in new.items() if k in ALPHA_KEYS + ("/BM",)}
            elif kind == "image":
                item["size"] = [int(base.Width), int(base.Height)]
            pairs.append(item)
        entry["replace"] = pairs
        themes_out.append(entry)
    return {"key": THEMES_KEY, "themes": themes_out}
