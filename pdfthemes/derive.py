"""Themes worked out from the author's colours, and checked.

Once a document's colours are organised into palettes (merge with
organise=True), each further theme is a new version of each palette, plus new
versions of any gradients and colour values. This module works those out for
a standard set of themes, checks each one's text contrast by drawing it, and
keeps only the themes that pass.

The standard set, chosen from research on reading comfort and accessibility:

  Dark                   for light sensitivity and some low vision
  Light, more contrast   for low vision
  Dark, more contrast    for low vision with light sensitivity
  Cream, Peach, Yellow, Turquoise
                         tinted backgrounds, which many readers with dyslexia
                         or visual stress prefer; people differ, so a range

Each theme carries a standard label (ColorScheme, Contrast, Tint) so a
reader can remember a person's choice from one document to the next.
"""

from __future__ import annotations

import datetime
import io
import math
import re
import zlib

import pikepdf
from pikepdf import Array, Dictionary, Name, String

from . import colour as C
from .contrast import check, summary
from .core import THEMES_KEY, apply, paint_paper

TINTS = {  # OKLCH paper colours: soft pastels, light enough for dark text
    "Cream": (0.965, 0.035, 92),
    "Peach": (0.945, 0.045, 58),
    "Yellow": (0.965, 0.075, 102),
    "Turquoise": (0.95, 0.04, 190),
}
DARK_BLEND = {"/Multiply": "/Screen", "/Darken": "/Lighten", "/ColorBurn": "/ColorDodge"}
BACKGROUND_AREA = 0.02   # a fill covering 2% of the page or more is a background
SURFACE_AREA = 0.003     # a smaller fill down to 0.3% is a surface: a box, a highlight, a swatch
# A grey scan in a theme: greys up to the first number are ink, from the
# second up are paper, and those between are mixed. 0.92 takes in a scan's
# off-white paper; more contrast also makes faint, grey print solid.
SCAN_STRETCH = {None: (0.0, 0.92), "More": (0.25, 0.85)}


class Spec:
    def __init__(self, name, scheme, contrast=None, tint=None, source="light"):
        self.name, self.scheme, self.contrast, self.tint, self.source = name, scheme, contrast, tint, source
        self.text_target = 7.0 if contrast == "More" else 4.5
        self.graphic_target = 3.0

    # How one colour changes in this theme ---------------------------------
    def background(self, rgb):
        L, Ch, h = C.srgb_to_oklch(rgb)
        if self.tint:
            pL, pC, ph = TINTS[self.tint]
            if L >= 0.85 and Ch <= 0.05:  # white and near-white surfaces take the tint
                return C.oklch_to_srgb(pL - (1 - L), pC, ph)
            return rgb
        if self.scheme == "Light" and self.contrast == "More":
            if L >= 0.85 and Ch <= 0.05:
                return C.oklch_to_srgb(1 - (1 - L) * 1.6, Ch, h)
            return rgb
        if self.scheme == "Dark" and self.source == "derive":
            return C.oklch_to_srgb(_invert(L), Ch * 0.8, h)
        if self.scheme == "Dark" and self.contrast == "More":
            if L <= 0.35 and Ch <= 0.06:
                return C.oklch_to_srgb(L * 0.45, Ch * 0.5, h)
            return rgb
        return rgb

    def foreground(self, rgb):
        if self.scheme == "Dark" and self.source == "derive":
            L, Ch, h = C.srgb_to_oklch(rgb)
            flipped = _invert(L)
            if Ch > 0.04:
                # A colour rather than a grey: dark themes use light accents,
                # so a light one stays light and a dark one comes up.
                flipped = max(flipped, min(L, 0.9))
            return C.oklch_to_srgb(flipped, Ch * 0.9, h)
        return rgb

    def paper(self, light_paper, dark_paper):
        if self.tint:
            return C.oklch_to_srgb(*TINTS[self.tint])
        if self.scheme == "Light":
            return (1.0, 1.0, 1.0) if self.contrast == "More" else light_paper
        if self.source == "derive":
            return self.background(light_paper)
        if self.contrast == "More":
            return (0.0, 0.0, 0.0)
        return dark_paper


def _invert(L):
    """Lightness for a dark theme: light surfaces go dark, dark text goes light."""
    return min(0.97, max(0.13, 1.06 - L))


def standard_specs(author_dark: bool):
    specs = []
    if not author_dark:
        specs.append(Spec("Dark", "Dark", source="derive"))
    specs.append(Spec("Light, more contrast", "Light", contrast="More"))
    specs.append(Spec("Dark, more contrast", "Dark", contrast="More", source="dark" if author_dark else "derived-dark"))
    for tint in TINTS:
        specs.append(Spec(tint, "Light", tint=tint))
    return specs


# ── Enforcing contrast ───────────────────────────────────────────────────────

def enforce(rgb, backgrounds, target):
    """Move a colour's lightness away from its backgrounds until it reaches
    the target contrast against each of them, keeping its hue."""
    if not backgrounds or min(C.contrast(rgb, b) for b in backgrounds) >= target:
        return rgb
    mean_bg = sum(C.luminance(b) for b in backgrounds) / len(backgrounds)
    darker = C.luminance(rgb) <= mean_bg
    L, Ch, h = C.srgb_to_oklch(rgb)
    for _ in range(100):
        L = L - 0.01 if darker else L + 0.01
        Ch *= 0.985
        cand = C.oklch_to_srgb(L, Ch, h)
        if min(C.contrast(cand, b) for b in backgrounds) >= target:
            return cand
        if L <= 0 or L >= 1:
            break
    return (0.0, 0.0, 0.0) if darker else (1.0, 1.0, 1.0)


# ── Working out one theme ────────────────────────────────────────────────────

SRGB_PRIMARIES = {b"rXYZ": (0.4361, 0.2225, 0.0139), b"gXYZ": (0.3851, 0.7169, 0.0971),
                  b"bXYZ": (0.1431, 0.0606, 0.7141)}  # D50-adapted, as ICC profiles store them


def _icc_xyz(data, signature):
    count = int.from_bytes(data[128:132], "big")
    for k in range(min(count, 100)):
        entry = 132 + 12 * k
        if data[entry:entry + 4] == signature:
            start = int.from_bytes(data[entry + 4:entry + 8], "big")
            return [int.from_bytes(data[start + 8 + 4 * i:start + 12 + 4 * i], "big", signed=True) / 65536
                    for i in range(3)]
    return None


def is_srgb_profile(data: bytes) -> bool:
    """An RGB ICC profile with the sRGB primaries."""
    if len(data) < 132 or data[36:40] != b"acsp" or data[16:20] != b"RGB ":
        return False
    for signature, want in SRGB_PRIMARIES.items():
        got = _icc_xyz(data, signature)
        if got is None or any(abs(a - b) > 0.01 for a, b in zip(got, want)):
            return False
    return True


def _srgb_space(pdf):
    """An sRGB ICC profile the file already holds, or DeviceRGB. Reusing the
    file's own profile keeps a PDF/A file within its rules."""
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Stream) and obj.get("/N") == 3 and "/Width" not in obj and "/Subtype" not in obj:
            try:
                data = obj.read_bytes()
            except pikepdf.PdfError:
                continue
            if is_srgb_profile(data):
                return Array([Name.ICCBased, obj])
    return Name.DeviceRGB


def _indirect(pdf, obj):
    return obj if getattr(obj, "is_indirect", False) else pdf.make_indirect(obj)


class Deriver:
    def __init__(self, merger, light_paper=(1.0, 1.0, 1.0), dark_paper=(0.0, 0.0, 0.0)):
        self.m = merger
        self.pdf = merger.pdf
        self.light_paper, self.dark_paper = tuple(light_paper), tuple(dark_paper)
        self.rgb_space = _srgb_space(self.pdf)
        self.author_dark = {b.objgen: a for b, a in merger.replace}
        self.has_author_dark = bool(merger.replace) and merger.dark is not merger.pdf

    # Source colours ----------------------------------------------------------
    def entry_rgb(self, pal, i, source):
        if source in ("dark",) and pal.alt is not None:
            return C.to_srgb(pal.space_d, pal.dark_values(i))
        return C.to_srgb(pal.space_l, pal.light_values(i))

    def kind(self, pal, i, rgb):
        """text, background, surface or graphic. Text and graphics (lines,
        marks, small shapes) are held to contrast minimums; backgrounds and
        surfaces are what they are measured against, so they keep their
        colours apart from the theme's own change."""
        if pal.context == "paint":
            roles = pal.roles[i]
            if roles["text"]:
                return "text"
            if roles["fill"] and pal.area[i] >= BACKGROUND_AREA:
                return "background"
            if roles["fill"] and pal.area[i] >= SURFACE_AREA:
                return "surface"
            return "graphic"
        L, Ch, _ = C.srgb_to_oklch(rgb)
        return "background" if L >= 0.9 and Ch <= 0.05 else "graphic"

    # Palettes ------------------------------------------------------------------
    def theme_palettes(self, spec, overrides, pushes=()):
        """New colours for every palette entry, as {palette name: [rgb, ...]}."""
        source = spec.source
        base_spec = spec
        derived_dark = None
        if source == "derived-dark":
            derived_dark = Spec("Dark", "Dark", source="derive")
            source = "light"
        out, kinds = {}, {}
        for pal in self.m.palette_list:
            if pal.context == "mask":
                continue
            colours, ks = [], []
            for i in range(len(pal.entries)):
                rgb = self.entry_rgb(pal, i, source)
                k = self.kind(pal, i, rgb)
                behind = k in ("background", "surface")
                if derived_dark is not None:
                    rgb = derived_dark.background(rgb) if behind else derived_dark.foreground(rgb)
                rgb = base_spec.background(rgb) if behind else base_spec.foreground(rgb)
                colours.append(rgb)
                ks.append(k)
            out[pal.name] = colours
            kinds[pal.name] = ks
        # Fills that text could not reach enough contrast against, in an
        # earlier round, move away from that text: a pill or a box behind a
        # label is a surface whatever its size.
        for name, cs in out.items():
            pal = next(p for p in self.m.palette_list if p.name == name)
            for i, k in enumerate(kinds[name]):
                if pal.context == "paint" and k != "text" and pal.roles[i]["fill"]:
                    cs[i] = _pushed([cs[i]], pushes)[0]
        # Contrast: text against the theme's backgrounds (the paper and large
        # fills; not the colours inside images), graphics more gently.
        paper = spec.paper(self.light_paper, self.dark_paper)
        contexts = {p.name: p.context for p in self.m.palette_list}
        backgrounds = [paper] + [c for name, cs in out.items() if contexts[name] == "paint"
                                 for c, k in zip(cs, kinds[name]) if k == "background"]
        for name, cs in out.items():
            pal = next(p for p in self.m.palette_list if p.name == name)
            for i, (c, k) in enumerate(zip(cs, kinds[name])):
                if (name, i) in overrides:
                    cs[i] = overrides[(name, i)]
                    continue
                if pal.context != "paint" or k in ("background", "surface"):
                    continue
                lum = C.luminance(c)
                lighter = [b for b in backgrounds if C.luminance(b) > lum]
                darker = [b for b in backgrounds if C.luminance(b) < lum]
                behind = lighter if len(lighter) >= len(darker) else darker  # the side most surfaces are on
                target = spec.text_target if k == "text" else spec.graphic_target
                if k == "graphic" and spec.contrast != "More":
                    continue  # graphics keep the author's colours unless more contrast is asked for
                cs[i] = enforce(c, behind, target)
        return out, kinds

    def palette_array(self, pal, colours):
        lookup = b"".join(bytes(round(min(max(v, 0.0), 1.0) * 255) for v in rgb) for rgb in colours)
        return self.pdf.make_indirect(Array([Name.Indexed, self.rgb_space, max(len(colours) - 1, 0), String(lookup)]))

    # Gradients and values ----------------------------------------------------
    def transform_rgb(self, spec, rgb, kind="graphic"):
        if spec.source == "derived-dark":
            d = Spec("Dark", "Dark", source="derive")
            rgb = d.background(rgb) if kind == "background" else d.foreground(rgb)
        return spec.background(rgb) if kind == "background" else spec.foreground(rgb)

    def sampled(self, spec, function, space, domain, n_in, pushes=()):
        """A type 0 function in sRGB that follows `function`, recoloured."""
        steps = 64 if n_in == 1 else 16
        grid = [[domain[0][0] + (domain[0][1] - domain[0][0]) * k / (steps - 1)] for k in range(steps)] \
            if n_in == 1 else [[domain[0][0] + (domain[0][1] - domain[0][0]) * x / (steps - 1),
                                domain[1][0] + (domain[1][1] - domain[1][0]) * y / (steps - 1)]
                               for y in range(steps) for x in range(steps)]
        olds, news = [], []
        for point in grid:
            rgb = C.to_srgb(space, C.eval_function(function, point))
            L, Ch, _ = C.srgb_to_oklch(rgb)
            olds.append(rgb)
            news.append(self.transform_rgb(spec, rgb, "background" if L >= 0.9 and Ch <= 0.05 else "graphic"))
        news = _pushed(news, pushes)
        if not any(abs(a - b) > 1 / 255 for o, n in zip(olds, news) for a, b in zip(o, n)):
            return None
        samples = b"".join(bytes(round(min(max(v, 0.0), 1.0) * 255) for v in n) for n in news)
        fn = pikepdf.Stream(self.pdf, zlib.compress(samples, 9))
        fn.FunctionType = 0
        fn.Domain = Array([v for pair in domain for v in pair])
        fn.Range = Array([0, 1, 0, 1, 0, 1])
        fn.Size = Array([steps] * n_in)
        fn.BitsPerSample = 8
        fn.Filter = Name.FlateDecode
        return self.pdf.make_indirect(fn)

    def transform_shading(self, spec, shading, pushes=()):
        st = int(shading.ShadingType)
        space = shading.ColorSpace
        new = pikepdf.Stream(self.pdf, shading.read_raw_bytes()) if isinstance(shading, pikepdf.Stream) \
            else Dictionary()
        for k, v in shading.items():
            if k != "/Length":
                new[k] = v
        if "/Function" in shading:
            if st == 1:
                domain = [(float(a), float(b)) for a, b in zip(*[iter(shading.get("/Domain", [0, 1, 0, 1]))] * 2)]
                n_in = 2
            elif st in (2, 3):
                domain = [tuple(float(v) for v in shading.get("/Domain", [0, 1]))]
                n_in = 1
            else:
                fn = shading.Function
                first = fn[0] if isinstance(fn, pikepdf.Array) else fn
                domain = [tuple(float(v) for v in first.Domain)]
                n_in = 1
            fn = self.sampled(spec, shading.Function, space, domain, n_in, pushes)
            if fn is None and "/Background" not in shading:
                return None
            if fn is not None:
                new["/Function"] = fn
                new["/ColorSpace"] = self.rgb_space
        elif st in (4, 5, 6, 7):
            return self.transform_mesh(spec, shading)
        if "/Background" in shading:
            new["/Background"] = Array(self.transform_rgb(spec, C.to_srgb(space, [float(v) for v in shading.Background]),
                                                          "background"))
        return _indirect(self.pdf, new)

    def transform_mesh(self, spec, shading):
        """A mesh shading (types 4 to 7) whose vertices carry colours,
        rewritten with each colour recoloured, in sRGB at 8 bits."""
        st = int(shading.ShadingType)
        space = shading.ColorSpace
        n = C.components(space)
        b_coord, b_comp = int(shading.BitsPerCoordinate), int(shading.BitsPerComponent)
        b_flag = int(shading.get("/BitsPerFlag", 8)) if st != 5 else 0
        decode = [float(v) for v in shading.Decode]
        ranges = list(zip(decode[4::2], decode[5::2]))
        top = (1 << b_comp) - 1
        reader, writer = _Bits(shading.read_bytes()), _Bits()
        changed = False

        def colour():
            nonlocal changed
            vals = [lo + reader.read(b_comp) * (hi - lo) / top for lo, hi in ranges[:n]]
            rgb = C.to_srgb(space, vals)
            L, Ch, _ = C.srgb_to_oklch(rgb)
            new = self.transform_rgb(spec, rgb, "background" if L >= 0.9 and Ch <= 0.05 else "graphic")
            changed |= any(abs(a - b) > 1 / 255 for a, b in zip(rgb, new))
            for v in new:
                writer.write(round(min(max(v, 0.0), 1.0) * 255), 8)

        if st in (4, 5):
            while reader.left() >= b_flag + 2 * b_coord + n * b_comp:
                if b_flag:
                    writer.write(reader.read(b_flag), b_flag)
                for _ in range(2):
                    writer.write(reader.read(b_coord), b_coord)
                colour()
                reader.align()
                writer.align()
        else:
            points = 12 if st == 6 else 16
            while reader.left() >= b_flag:
                flag = reader.read(b_flag)
                count, corners = (points, 4) if flag == 0 else (points - 4, 2)
                if reader.left() < count * 2 * b_coord + corners * n * b_comp:
                    break
                writer.write(flag, b_flag)
                for _ in range(count * 2):
                    writer.write(reader.read(b_coord), b_coord)
                for _ in range(corners):
                    colour()
                reader.align()
                writer.align()
        if not changed:
            return None
        new = pikepdf.Stream(self.pdf, zlib.compress(writer.data(), 9))
        for k, v in shading.items():
            if k not in ("/Length", "/Filter", "/DecodeParms"):
                new[k] = v
        new.Filter = Name.FlateDecode
        new.ColorSpace = self.rgb_space
        new.BitsPerComponent = 8
        new.Decode = Array(decode[:4] + [0, 1, 0, 1, 0, 1])
        return self.pdf.make_indirect(new)

    def shading_pair(self, spec, entry, pushes=()):
        src = entry["alt"] if spec.source == "dark" and entry["alt"] is not None else entry["base"]
        if entry["shape"] == "pattern":
            shading = self.transform_shading(spec, src.Shading, pushes)
            if shading is None:
                return None
            new = Dictionary({k: v for k, v in src.items()})
            new["/Shading"] = shading
            return self.pdf.make_indirect(new)
        return self.transform_shading(spec, src, pushes)

    def recolour_array(self, spec, arr, kind, paper):
        """A colour array ([], [g], [r g b] or [c m y k], or an array of them,
        as BorderColor has one per side) in this theme. None if unchanged."""
        if not isinstance(arr, pikepdf.Array) or len(arr) == 0:
            return None
        if all(isinstance(v, pikepdf.Array) for v in arr):
            parts = [self.recolour_array(spec, v, kind, paper) for v in arr]
            if all(p is None for p in parts):
                return None
            return Array([p if p is not None else v for p, v in zip(parts, arr)])
        vals = [float(v) for v in arr]
        space = {1: Name.DeviceGray, 3: Name.DeviceRGB, 4: Name.DeviceCMYK}.get(len(vals))
        if space is None:
            return None
        rgb = C.to_srgb(space, vals)
        if kind == "outline":
            rgb = self.transform_rgb(spec, rgb, "graphic")
            rgb = enforce(rgb, [(1.0, 1.0, 1.0)] if spec.scheme == "Light" else [(0.1, 0.1, 0.1)], 4.5)
        elif kind == "text":
            rgb = enforce(self.transform_rgb(spec, rgb, "text"), [paper], spec.text_target)
        else:
            L, Ch, _ = C.srgb_to_oklch(rgb)
            rgb = self.transform_rgb(spec, rgb, "background" if L >= 0.9 and Ch <= 0.05 else "graphic")
        return Array([round(v, 4) for v in rgb])

    def value_pair(self, spec, entry, paper):
        if entry.get("context") == "mask":
            return None  # a soft mask's backdrop is a shape, not a colour
        src = entry["alt"] if spec.source == "dark" and entry["alt"] is not None else entry["base"]
        kind = entry["value"]
        text_colour = lambda rgb: enforce(self.transform_rgb(spec, rgb, "text"), [paper], spec.text_target)
        if kind in ("colour", "outline", "text"):
            new = self.recolour_array(spec, src, kind, paper)
            return None if new is None else self.pdf.make_indirect(new)
        if kind == "da":
            text = bytes(src).decode("latin-1")
            return self.pdf.make_indirect(String(_recolour_da(text, text_colour)))
        if kind == "style":
            raw = bytes(src)
            utf16 = raw.startswith(b"\xfe\xff")
            text = raw[2:].decode("utf-16-be") if utf16 else raw.decode("latin-1")
            new = _recolour_css(text, text_colour)
            data = (b"\xfe\xff" + new.encode("utf-16-be")) if utf16 else new.encode("latin-1")
            return self.pdf.make_indirect(String(data))
        if spec.source == "dark" and entry["alt"] is not None:
            return self.m.fresh(entry["alt"])
        return None

    def indexed_image_pair(self, spec, entry):
        src = entry["alt"] if spec.source == "dark" and entry["alt"] is not None else entry["base"]
        base_space = src[1]
        n = C.components(base_space)
        lookup = C.indexed_lookup(src)
        rng = C.ranges(base_space)
        colours = []
        for i in range(int(src[2]) + 1):
            vals = C.dequantise(lookup[i * n:(i + 1) * n], rng)
            rgb = C.to_srgb(base_space, vals)
            L, Ch, _ = C.srgb_to_oklch(rgb)
            colours.append(self.transform_rgb(spec, rgb, "background" if L >= 0.9 and Ch <= 0.05 else "graphic"))
        data = b"".join(bytes(round(min(max(v, 0.0), 1.0) * 255) for v in rgb) for rgb in colours)
        return self.pdf.make_indirect(Array([Name.Indexed, self.rgb_space, int(src[2]), String(data)]))

    def scan_pair(self, spec, entry, paper):
        """A grey scan's palette in this theme: each grey becomes a mix of
        the theme's ink and its paper, so the scanned page's white is the
        theme's paper. Greys at or above a scan's usual off-white count as
        paper; more contrast also pulls dark greys to the ink."""
        if spec.source == "dark":
            return None  # the author's dark design shows its scans as they are
        ink = self.transform_rgb(spec, (0.0, 0.0, 0.0), "text")
        lo, hi = SCAN_STRETCH[spec.contrast]
        hival = entry["hival"]
        colours = []
        for k in range(hival + 1):
            t = min(max((k / hival - lo) / (hi - lo), 0.0), 1.0)
            colours.append(tuple(i + (p - i) * t for i, p in zip(ink, paper)))
        data = b"".join(bytes(round(min(max(v, 0.0), 1.0) * 255) for v in rgb) for rgb in colours)
        return self.pdf.make_indirect(Array([Name.Indexed, self.rgb_space, hival, String(data)]))

    def blend_pair(self, spec, entry):
        """In a dark theme worked out from the light one, a blend mode that
        darkens (Multiply, for a highlighter) becomes the one that lightens."""
        if spec.scheme != "Dark" or spec.source not in ("derive", "derived-dark"):
            return None
        base = entry["base"]
        new = Dictionary({k: v for k, v in base.items()})
        new["/BM"] = Name(DARK_BLEND[str(base["/BM"])])
        return self.pdf.make_indirect(new)

    # One theme ---------------------------------------------------------------
    def build(self, spec, overrides=None, pushes=()):
        overrides = overrides or {}
        pairs = {}
        if spec.source == "dark":
            for b, a in self.m.replace:
                pairs[b.objgen] = (b, a)
        colours, kinds = self.theme_palettes(spec, overrides, pushes)
        for pal in self.m.palette_list:
            if pal.name in colours:
                pairs[pal.base.objgen] = (pal.base, self.palette_array(pal, colours[pal.name]))
        paper = spec.paper(self.light_paper, self.dark_paper)
        for entry in self.m.registry:
            if entry.get("context") == "mask":
                continue  # soft masks set shape and opacity, which no theme changes
            if entry["kind"] == "shading":
                new = self.shading_pair(spec, entry, pushes)
            elif entry["kind"] == "value":
                new = self.value_pair(spec, entry, paper)
            elif entry["kind"] == "indexed-image":
                new = self.indexed_image_pair(spec, entry)
            elif entry["kind"] == "scan":
                new = self.scan_pair(spec, entry, paper)
            elif entry["kind"] == "blend":
                new = self.blend_pair(spec, entry)
            else:
                new = None
            if new is not None:
                pairs[entry["base"].objgen] = (entry["base"], new)
        return list(pairs.values()), colours, paper

    def info(self, spec, paper, checked=None):
        d = {"/Name": String(spec.name), "/ColorScheme": Name("/" + spec.scheme), "/Paper": Array([round(v, 4) for v in paper])}
        if spec.contrast:
            d["/Contrast"] = Name("/" + spec.contrast)
        if spec.tint:
            d["/Tint"] = Name("/" + spec.tint)
        if checked is not None:
            d["/Checked"] = checked
        return d

    def verify(self, default_info, info, pairs, paper, enhanced=False, drawn=None):
        """Draw one theme as a reader would and check its text contrast.
        drawn: as for contrast.check, a list that gets each page's fingerprint."""
        return verify(self.pdf, default_info, info, pairs, paper, enhanced, drawn)

    def derive(self, default_info, specs, checked_fn, rounds=4, default_drawn=None):
        """Work out each theme, check it, and fix colours that fall short.
        Returns [(info, pairs, report)] for the themes that pass and change
        something; a theme that draws every page exactly as the default does
        (default_drawn, the default's page fingerprints) is left out. A theme
        is marked as checked only if some of its text was measured."""
        results = []
        for spec in specs:
            overrides, pushes, failed_before = {}, [], set()
            report, drawn = None, []
            for _ in range(rounds):
                pairs, colours, paper = self.build(spec, overrides, pushes)
                drawn = []
                found = self.verify(default_info, self.info(spec, paper), pairs, paper, spec.contrast == "More",
                                    drawn=drawn)
                report = summary(found)
                if not report["failures"]:
                    break
                changed = False
                for fail in report["failures"]:
                    bg = C.hex_rgb(fail.get("behind") or fail["background"])  # the lightest or darkest part behind it
                    target = fail["needs"] + 0.3
                    text = C.hex_rgb(fail["colour"])
                    for name, cs in colours.items():
                        for i, c in enumerate(cs):
                            if C.rgb_hex(c) == fail["colour"]:
                                fixed = enforce(c, [bg], target)
                                if C.rgb_hex(fixed) != fail["colour"]:
                                    overrides[(name, i)] = fixed
                                    changed = True
                                text = fixed
                    seen = (fail["page"], fail["text"])
                    again = seen in failed_before
                    failed_before.add(seen)
                    if C.contrast(text, bg) < target or again:
                        # The text is as light or as dark as it can go, or a
                        # fix didn't hold: move what is behind it instead,
                        # further each round it still falls short.
                        for k, (t, b, x) in enumerate(pushes):
                            if t == tuple(text) and _distance(b, bg) < NEAR:
                                pushes[k] = (t, b, x * fail["needs"] / max(fail["ratio"], 1.0) + 0.1)
                                break
                        else:
                            pushes.append((tuple(text), tuple(bg), target))
                        changed = True
                if not changed:
                    break
            passed = report is not None and not report["failures"]
            if passed and default_drawn is not None and drawn == default_drawn:
                results.append((None, None, dict(report, name=spec.name, reason="unchanged")))
            elif passed:
                pairs, colours, paper = self.build(spec, overrides, pushes)
                checked = checked_fn(spec.contrast == "More") if report["runs"] else None
                results.append((self.info(spec, paper, checked), pairs, report))
            else:
                results.append((None, None, dict(report or {}, name=spec.name, reason="failed")))
        return results


NEAR = 0.1  # OKLab distance within which a colour counts as the one measured behind some text


def _distance(a, b):
    return math.dist(C.srgb_to_oklab(a), C.srgb_to_oklab(b))


def _pushed(colours, pushes):
    """Colours behind text that fell short, moved until the text reaches
    its target. A set of colours (a gradient's samples) moves together if
    any of them is the colour that was measured."""
    for text, behind, target in pushes:
        if colours and min(_distance(c, behind) for c in colours) < NEAR:
            colours = [enforce(c, [text], target) if C.contrast(c, text) < target else c for c in colours]
    return colours


CSS_COLOUR = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])|rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")


def _recolour_css(text, fn):
    """Recolour the CSS colours in a default style string or rich text."""
    def sub(m):
        if m.group(1):
            h = m.group(1) if len(m.group(1)) == 6 else "".join(ch * 2 for ch in m.group(1))
            rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        else:
            rgb = tuple(min(int(m.group(k)), 255) / 255 for k in (2, 3, 4))
        return C.rgb_hex(fn(rgb))
    return CSS_COLOUR.sub(sub, text)


class _Bits:
    """Reads and writes values of any bit width, most significant bit first."""

    def __init__(self, data=b""):
        self.buf, self.pos, self.out, self.acc, self.n = data, 0, bytearray(), 0, 0

    def left(self):
        return len(self.buf) * 8 - self.pos

    def read(self, width):
        v = 0
        for _ in range(width):
            byte = self.buf[self.pos >> 3]
            v = (v << 1) | ((byte >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def align(self):
        if self.buf:
            self.pos = (self.pos + 7) & ~7
        if self.n:
            self.out.append((self.acc << (8 - self.n)) & 0xFF)
            self.acc, self.n = 0, 0

    def write(self, value, width):
        for k in range(width - 1, -1, -1):
            self.acc = (self.acc << 1) | ((int(value) >> k) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc, self.n = 0, 0

    def data(self):
        return bytes(self.out)


def _recolour_da(text, fn):
    """Recolour the colour operators in a default appearance string."""
    tokens = text.split()
    out, stack = [], []
    for t in tokens:
        if t in ("g", "rg", "k"):
            n = {"g": 1, "rg": 3, "k": 4}[t]
            vals = [float(v) for v in stack[-n:]]
            space = {"g": Name.DeviceGray, "rg": Name.DeviceRGB, "k": Name.DeviceCMYK}[t]
            rgb = fn(C.to_srgb(space, vals))
            out = out[:-n] + [f"{v:.3f}" for v in rgb] + ["rg"]
            stack = []
        else:
            out.append(t)
            stack.append(t)
    return " ".join(out)


def checked_now(enhanced=False):
    """The Checked entry for a theme that has just passed."""
    criterion, level = ("1.4.6 Contrast (Enhanced)", "/AAA") if enhanced else ("1.4.3 Contrast (Minimum)", "/AA")
    return Dictionary({"/Standard": String("WCAG 2.2"), "/Criterion": String(criterion),
                       "/Level": Name(level), "/Date": String("D:" + datetime.date.today().strftime("%Y%m%d"))})


def verify(pdf, default_info, info, pairs, paper, enhanced=False, drawn=None):
    """Draw one theme as a reader would and check its text contrast.
    drawn: as for contrast.check, a list that gets each page's fingerprint."""
    write_themes(pdf, default_info, [(info, pairs)] if pairs is not None else [])
    buf = io.BytesIO()
    pdf.save(buf, fix_metadata_version=False)  # pikepdf would otherwise rewrite the file's XMP in place
    with pikepdf.open(io.BytesIO(buf.getvalue())) as copy:
        apply(copy, str(info["/Name"]))
        paint_paper(copy, paper)
        out = io.BytesIO()
        copy.save(out)
    return check(out.getvalue(), paper=paper, enhanced=enhanced, drawn=drawn)


def _report(name, kind, report, kept):
    lowest = report.get("lowest") if report else None
    return {"name": name, "kind": kind, "kept": kept,
            "passed": bool(report) and report.get("runs", 0) > 0 and not report["failures"],
            "reason": None if kept else report.get("reason", "failed"),
            "runs": report.get("runs", 0) if report else 0,
            "unmeasured": report.get("unmeasured", 0) if report else 0,
            "lowest": lowest["ratio"] if lowest else None,
            "lowest_text": lowest["text"] if lowest else None,
            "failures": [{k: f[k] for k in ("page", "text", "colour", "background", "ratio", "needs")}
                         for f in (report.get("failures", []) if report else [])[:8]]}


def add_authored_themes(merger, themes):
    """Write the themes an author built, one per build: `themes[0]` describes
    the default and the rest the alternates, in the order of the builds. Each
    is drawn and its text contrast measured. A theme that passes carries a
    Checked entry. One that fails is still written, without it, and nothing
    about it is changed: fixing it is for the author, in the source."""
    names = [t.name for t in themes]
    if len(themes) != 1 + len(merger.replaces):
        raise ValueError(f"{len(themes)} themes for {1 + len(merger.replaces)} builds")
    for name in names:
        if names.count(name) > 1:
            raise ValueError(f"two themes are called {name}")
    reports = []

    def checked(theme, info, pairs, kind):
        report = summary(verify(merger.pdf, default, info, pairs, tuple(theme.paper), theme.enhanced))
        if report["runs"] > 0 and not report["failures"]:
            info["/Checked"] = checked_now(theme.enhanced)
        reports.append(_report(theme.name, kind, report, True))

    default = themes[0].info()
    checked(themes[0], default, None, "default")
    alternates = []
    for theme, pairs in zip(themes[1:], merger.replaces):
        info = theme.info()
        checked(theme, info, pairs, "author")
        alternates.append((info, pairs))
    write_themes(merger.pdf, default, alternates)
    return reports


def add_themes(merger, light_paper=(1.0, 1.0, 1.0), dark_paper=(0.0, 0.0, 0.0), derived=True):
    """Give an organised document its themes. Given a list of Theme (from
    pdfthemes.themes) in place of the papers, it writes those, one per build:
    see add_authored_themes.

    Otherwise: the light build as the default, the dark build (if there was
    one) as Dark, and the standard derived themes that pass their contrast
    check. Every theme is checked; only those whose text was measured and
    passed carry a Checked entry. Derived themes that fail, or that draw
    every page exactly like the default, are left out. Returns one report
    per theme; a theme left out has a reason, "failed" or "unchanged"."""
    if isinstance(light_paper, list):
        return add_authored_themes(merger, light_paper)
    d = Deriver(merger, light_paper, dark_paper)
    reports = []

    def note(name, kind, report, kept):
        reports.append(_report(name, kind, report, kept))

    def passed(report):
        return report["runs"] > 0 and not report["failures"]

    default = {"/Name": String("Light"), "/ColorScheme": Name("/Light"),
               "/Paper": Array([round(v, 4) for v in light_paper])}
    default_drawn = []
    report = summary(d.verify(default, default, None, tuple(light_paper), drawn=default_drawn))
    if passed(report):
        default["/Checked"] = checked_now()
    note("Light", "default", report, True)
    alternates = []
    if d.has_author_dark:
        info = {"/Name": String("Dark"), "/ColorScheme": Name("/Dark"),
                "/Paper": Array([round(v, 4) for v in dark_paper])}
        report = summary(d.verify(default, info, merger.replace, tuple(dark_paper)))
        if passed(report):
            info["/Checked"] = checked_now()
        alternates.append((info, merger.replace))
        note("Dark", "author", report, True)
    if derived:
        for info, pairs, report in d.derive(default, standard_specs(d.has_author_dark), checked_now,
                                            default_drawn=default_drawn):
            if info is None:
                note(report.get("name"), "derived", report, False)
            else:
                alternates.append((info, pairs))
                note(str(info["/Name"]), "derived", report, True)
    write_themes(merger.pdf, default, alternates)
    return reports


def write_themes(pdf, default: dict, alternates):
    """Write the themes dictionary: the default theme, then each alternate
    as (info, [(base, replacement), ...])."""
    alts = Array()
    for info, pairs in alternates:
        rep = Array()
        for base, alt in pairs:
            rep.append(base)
            rep.append(alt)
        alts.append(Dictionary({"/Type": Name("/Theme"), **info, "/Replace": rep}))
    pdf.Root[THEMES_KEY] = Dictionary({"/Default": Dictionary({"/Type": Name("/Theme"), **default}),
                                       "/Alternates": alts})
