"""Organising a PDF for themes.

merge(light, dark) takes two builds of one document that draw the same
shapes and differ only in paint, and writes one file in which the content is
stored once. Wherever the builds differ in paint, the light build's value
becomes the default and the dark build's value becomes a replacement:

- solid colours in content streams, in any colour space, become entries in
  Indexed palettes (`/Th0 cs 15 sc`), one palette per pair of base spaces;
  a colour may even be in a different space in each build;
- gradients (shading patterns and the `sh` operator), graphics states
  (opacity and blend mode), soft masks and images are merged or swapped as
  whole objects, and images with few colours become one plane of palette
  indices;
- form XObjects, tiling patterns, Type 3 glyph procedures, annotation
  appearances and soft mask groups are merged recursively, so their colours
  join the palettes too;
- colour values outside content streams (annotation, form field, bookmark,
  structure attribute and portfolio colours) are moved into their own
  indirect objects so a theme can replace them.

With organise=True every colour goes into a palette even where the builds
agree. That is what lets derive.py add further themes (dark, more contrast,
tints) by computing new palettes. merge(pdf) organises a single PDF.

merge_builds([default, alternate, ...]) takes one build per theme. It merges
the first two as above, then merges each further build into the result: the
merged file is the light side, and wherever the new build differs from it the
new theme gets a replacement. The replacements of the themes already there
are carried across to any object that was copied on the way.
"""

from __future__ import annotations

import re
import zlib
from collections import Counter, defaultdict

import numpy as np
import pikepdf
from pikepdf import Array, Dictionary, Name, Operator, String

from . import colour as C
from .core import Grafter, MergeError, canon

PALETTE_SIZE = 256
DEVICE_OPS = {"g": ("/DeviceGray", False), "G": ("/DeviceGray", True), "rg": ("/DeviceRGB", False),
              "RG": ("/DeviceRGB", True), "k": ("/DeviceCMYK", False), "K": ("/DeviceCMYK", True)}
DEVICE_SPACES = ("/DeviceGray", "/DeviceRGB", "/DeviceCMYK", "/Pattern")
GS_PAINT = ("/CA", "/ca", "/BM")
DARKENING_BLENDS = ("/Multiply", "/Darken", "/ColorBurn")
GS_DEFAULT = {"/CA": 1.0, "/ca": 1.0, "/BM": Name.Normal}
TEXT_SHOW = {"Tj", "TJ", "'", '"'}
FILL_OPS = {"f", "F", "f*", "B", "B*", "b", "b*"}
STROKE_OPS = {"S", "s", "B", "B*", "b", "b*"}
PATH_OPS = {"m", "l", "c", "v", "y", "re", "h"}
RASTER_FILTERS = {"/DCTDecode", "/JPXDecode", "/JBIG2Decode", "/CCITTFaxDecode"}
RESOURCE_KINDS = ("/ColorSpace", "/ExtGState", "/Pattern", "/Shading", "/XObject", "/Font", "/Properties")

ANNOT_PAINT = ("/C", "/IC", "/CA", "/ca", "/BM", "/DA", "/DS", "/RC")
ANNOT_GEOMETRY = ("/Rect", "/QuadPoints", "/InkList", "/Vertices", "/L", "/BS", "/Border", "/RD", "/CL", "/LE",
                  "/Subtype", "/F")
MK_PAINT = ("/BG", "/BC")
LAYOUT_PAINT = {"/Color": "text", "/TextDecorationColor": "text", "/BackgroundColor": "colour",
                "/BorderColor": "colour"}
COLLECTION_PAINT = ("/Background", "/CardBackground", "/CardBorder", "/PrimaryText", "/SecondaryText")

# Diagrams, not photos: in a single build, an image is recoloured by derived
# themes only when it looks like a drawing on white: a white background over
# a quarter of it, and a few colours (anti-aliased edges aside) for the rest.
DIAGRAM_COLOURS = 64
DIAGRAM_COVER = 0.9
DIAGRAM_BACKGROUND = 0.25

# A grey scan of a page: at least half of it paper, and few mid-greys, which
# photos are full of. Such an image is themed through a palette of its own
# greys, so its data (often JPEG) is kept exactly as it is.
SCAN_PAPER = 0.5
SCAN_MIDTONES = 0.2


def _grey_space(space):
    """DeviceGray, CalGray or a one-channel ICC profile."""
    if isinstance(space, pikepdf.Name):
        return str(space) == "/DeviceGray"
    if isinstance(space, pikepdf.Array) and len(space) == 2:
        if str(space[0]) == "/CalGray":
            return True
        if str(space[0]) == "/ICCBased":
            return int(space[1].get("/N", 0)) == 1
    return False


def _num(x):
    return float(x)


def _filters(stream):
    f = stream.get("/Filter")
    if f is None:
        return []
    return [str(f)] if isinstance(f, pikepdf.Name) else [str(v) for v in f]


def _direct_copy(obj):
    """A shallow direct copy of a dictionary (values shared)."""
    return Dictionary({k: v for k, v in obj.items()})


def _is_number(value):
    return isinstance(value, (bool, int, float)) or type(value).__name__ == "Decimal"


def _scalar(pdf, value):
    """A value that can be made an indirect object."""
    if isinstance(value, bool):
        return pikepdf.Object.parse(b"true" if value else b"false")
    if isinstance(value, (int, float)) or type(value).__name__ == "Decimal":
        return pikepdf.Object.parse(repr(float(value)).encode())
    return value


def _space(resources, name):
    try:
        return C.resolve(resources, name)
    except KeyError as e:
        raise MergeError(str(e).strip("'\"")) from None


def initial_colour(space):
    """The colour `cs` sets before any `sc`, as PDF defines it."""
    f = C.family(space)
    if f == "/Pattern":
        return None  # paints nothing until a pattern is chosen
    if f in ("/Separation", "/DeviceN"):
        return [1.0] * C.components(space)
    if f == "/DeviceCMYK":
        return [0.0, 0.0, 0.0, 1.0]
    return [min(max(0.0, lo), hi) for lo, hi in C.ranges(space)]


def _diagram_like(colours, counts):
    """A white background covering a good share, and a few colours making up
    nearly all the rest: a chart or a drawing, which a theme can recolour,
    rather than a photo."""
    if len(colours) == 0:
        return False
    counts = np.asarray(counts)
    order = np.argsort(-counts)
    top = int(order[0])
    L, Ch, _ = C.srgb_to_oklch(colours[top])
    few = counts[order[:DIAGRAM_COLOURS]].sum() >= DIAGRAM_COVER * counts.sum()
    return few and counts[top] >= DIAGRAM_BACKGROUND * counts.sum() and L >= 0.9 and Ch <= 0.05


def _unpack(data, width, height, bpc, n=1):
    """Image samples (any bits per component) as an array of rows."""
    row = (width * n * bpc + 7) // 8
    raw = np.frombuffer(data[:row * height], dtype=np.uint8)
    if len(raw) < row * height:
        return None
    raw = raw.reshape(height, row)
    if bpc == 8:
        return raw[:, :width * n].reshape(height, width, n)
    bits = np.unpackbits(raw, axis=1)[:, :width * n * bpc].reshape(height, width * n, bpc)
    weights = (1 << np.arange(bpc - 1, -1, -1)).astype(np.uint16)
    return (bits * weights).sum(axis=2).astype(np.uint16).reshape(height, width, n)


def _palette_base(pdf, space):
    """The base space for a palette. A Lab space gets the full a* and b*
    range, -128 to 127: its colours keep their values, every reader maps the
    palette's bytes the same way (MuPDF ignores a narrower Range there), and
    whole numbers of a* and b* are stored exactly."""
    if C.family(space) != "/Lab":
        return space
    params = space[1]
    if [float(v) for v in params.get("/Range", [-100, 100, -100, 100])] == [-128.0, 127.0, -128.0, 127.0]:
        return space
    wide = Dictionary({k: v for k, v in params.items()})
    wide["/Range"] = Array([-128, 127, -128, 127])
    return Array([Name.Lab, pdf.make_indirect(wide)])


# ── Colour changes in content streams ────────────────────────────────────────

class Colour:
    """A change of fill or stroke colour, however the stream wrote it:
    `0.5 g`, `1 0 0 rg`, `/CS0 cs 0.2 sc`, or `/CS0 cs` alone, which sets
    the space's initial colour."""
    __slots__ = ("operator", "operands", "space", "op")

    def __init__(self, stroke, space, operands, op):
        self.operator = "STROKE" if stroke else "FILL"
        self.space = space
        self.operands = list(operands)
        self.op = op


def colour_events(ops, res):
    """A content stream's instructions, with each colour change as a Colour."""
    out = []
    spaces = [["/DeviceGray", "/DeviceGray"]]  # fill, stroke
    for k, ins in enumerate(ops):
        op = str(ins.operator)
        if op == "q":
            spaces.append(list(spaces[-1]))
        elif op == "Q" and len(spaces) > 1:
            spaces.pop()
        if op in ("cs", "CS"):
            stroke = op == "CS"
            name = str(ins.operands[0])
            spaces[-1][stroke] = name
            following = str(ops[k + 1].operator) if k + 1 < len(ops) else None
            if following not in (("SC", "SCN") if stroke else ("sc", "scn")):
                init = initial_colour(_space(res, name))
                if init is not None:
                    out.append(Colour(stroke, name, init, op))
            continue
        if op in ("sc", "scn", "SC", "SCN"):
            stroke = op.isupper()
            out.append(Colour(stroke, spaces[-1][stroke], ins.operands, op))
            continue
        if op in DEVICE_OPS:
            space, stroke = DEVICE_OPS[op]
            spaces[-1][stroke] = space
            out.append(Colour(stroke, space, ins.operands, op))
            continue
        out.append(ins)
    return out


# ── Palettes ─────────────────────────────────────────────────────────────────

class Palette:
    """An Indexed colour space shared by content streams. Each entry has a
    light value (the default) and a dark value, each in its own base space."""

    def __init__(self, merger, number, space_l, space_d, context, origin=None):
        self.name = f"/Th{number}"
        # A palette from an earlier merge that this one's entries were painted
        # through, and each entry's index in it.
        self.origin = origin
        self.origin_idx: list[int] = []
        space_l, space_d = _palette_base(merger.pdf, space_l), _palette_base(merger.pdf, space_d)
        self.space_l, self.space_d = space_l, space_d
        self.rng_l, self.rng_d = C.ranges(space_l), C.ranges(space_d)
        self.context = context  # "paint", "mask" or "image"
        self.base = merger.pdf.make_indirect(Array([]))  # filled in by finish()
        self.alt = None
        self.keys: dict[tuple, int] = {}
        self.entries: list[tuple[tuple, tuple]] = []
        self.roles: list[Counter] = []
        self.area: list[float] = []

    def index(self, vl, vd, role="graphic", origin_idx=None):
        """The entry for this pair of colours used this way. Text, fills and
        strokes get their own entries, so a theme can strengthen text and
        lines without touching a box or a highlight of the same colour. Two
        uses that came through different entries of an earlier palette stay
        apart too, because an earlier theme may tell them apart."""
        key = (C.quantise(vl, self.rng_l), C.quantise(vd, self.rng_d),
               role if role in ("text", "fill", "stroke") else "graphic", origin_idx)
        if key not in self.keys:
            if len(self.entries) >= PALETTE_SIZE:
                return None
            self.keys[key] = len(self.entries)
            self.entries.append(key[:2])
            self.origin_idx.append(origin_idx)
            self.roles.append(Counter())
            self.area.append(0.0)
        return self.keys[key]

    def light_values(self, i):
        return C.dequantise(self.entries[i][0], self.rng_l)

    def dark_values(self, i):
        return C.dequantise(self.entries[i][1], self.rng_d)


# ── Output resources for one merged content stream ───────────────────────────

class OutRes:
    def __init__(self, base):
        self.base = base if base is not None else Dictionary()
        self.added: dict[str, dict[str, object]] = defaultdict(dict)
        self.used: dict[str, set] = defaultdict(set)
        self.counter = Counter()

    def lookup(self, kind, name):
        group = self.base.get(kind)
        if group is None or name not in group:
            raise MergeError(f"{kind[1:]} resource {name} is missing")
        return group[name]

    def use(self, kind, name):
        self.used[kind].add(str(name))

    def add(self, kind, obj, prefix, name=None):
        if name is None:
            for n, o in self.added[kind].items():
                if o is obj or (getattr(o, "is_indirect", False) and getattr(obj, "is_indirect", False)
                                and o.objgen == obj.objgen):
                    self.use(kind, n)
                    return n
            existing = set(self.base.get(kind, {}).keys()) | set(self.added[kind])
            while True:
                name = f"/{prefix}{self.counter[prefix]}"
                self.counter[prefix] += 1
                if name not in existing:
                    break
        self.added[kind][name] = obj
        self.use(kind, name)
        return name

    def finish(self):
        out = Dictionary({k: v for k, v in self.base.items() if k not in RESOURCE_KINDS})
        for kind in RESOURCE_KINDS:
            group = Dictionary()
            for k, v in self.base.get(kind, {}).items():
                if k in self.used[kind]:
                    group[k] = v
            for k, v in self.added[kind].items():
                group[k] = v
            if len(group):
                out[kind] = group
        return out


# ── Graphics state while walking two content streams side by side ───────────

class Side:
    """One build's graphics state: the parts that paint."""
    __slots__ = ("gs", "colour")

    def __init__(self, inherit=False):
        self.gs = {"/CA": 1.0, "/ca": 1.0, "/BM": Name.Normal, "/SMask": Name("/None")}
        # A form or a glyph starts with its caller's colours, unknown here.
        self.colour = [None, None] if inherit else [Colour(False, "/DeviceGray", [0], "g"),
                                                     Colour(True, "/DeviceGray", [0], "G")]

    def copy(self):
        s = Side.__new__(Side)
        s.gs, s.colour = dict(self.gs), list(self.colour)
        return s


BLACK = ("raw", "/DeviceGray", (0.0,))


class Out:
    """What the merged stream has written so far."""
    __slots__ = ("emitted", "ctm", "tr")

    def __init__(self, inherit=False):
        self.emitted = [None, None] if inherit else [BLACK, BLACK]  # fill, stroke
        self.ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        self.tr = 0

    def copy(self):
        o = Out.__new__(Out)
        o.emitted, o.ctm, o.tr = list(self.emitted), self.ctm, self.tr
        return o


def _mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2,
            e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


# ── The merger ───────────────────────────────────────────────────────────────

class Merger:
    def __init__(self, light: pikepdf.Pdf, dark: pikepdf.Pdf, organise: bool = False, earlier=None):
        self.pdf = light
        self.dark = dark
        self.organise = organise
        # Merging a further build into a file that already has themes:
        # `earlier` is each of those themes' replacements, and stand_ins says
        # which new objects took the place of one of their base objects.
        self.earlier = {b.objgen for pairs in (earlier or []) for b, _ in pairs}
        self.stand_ins: dict[tuple, list] = defaultdict(list)
        self.palette_offset = _next_palette_number(light)
        self._replaces = None
        self.alts = [dark] if dark is not light else []
        self.graft = Grafter(light) if dark is not light else None
        self.palettes: dict[tuple, list[Palette]] = defaultdict(list)
        self.palette_list: list[Palette] = []
        self.replace: list[tuple] = []          # the dark build's replacements
        self.cache: dict = {}
        self.registry: list[dict] = []          # what derived themes can recolour
        self.stats = Counter()
        self.notes: list[str] = []              # differences kept from the light build
        self.page_area = 1.0

    # Objects from the dark build -----------------------------------------------
    def from_dark(self, obj):
        if self.graft is None:
            return obj
        return self.graft.copy(obj)

    @property
    def replaces(self):
        """Each alternate theme's replacements, in the order of the builds."""
        if self._replaces is not None:
            return self._replaces
        return [self.replace] if self.dark is not self.pdf else []

    def ident(self, obj):
        """The object number of a base object from an earlier merge, else None."""
        if self.earlier and getattr(obj, "is_indirect", False) and obj.objgen in self.earlier:
            return obj.objgen
        return None

    def stands_in(self, old, new):
        """Note that `new` now sits where `old`, an earlier theme's base, did."""
        ident = self.ident(old)
        if ident is not None:
            self.stand_ins[ident].append(new)
        return new

    def fresh(self, obj):
        """A new indirect object with the same content, for a theme to replace."""
        if isinstance(obj, pikepdf.Stream):
            s = pikepdf.Stream(self.pdf, obj.read_raw_bytes())
            for k, v in obj.items():
                if k != "/Length":
                    s[k] = v
            new = self.pdf.make_indirect(s)
        elif isinstance(obj, pikepdf.Dictionary):
            new = self.pdf.make_indirect(_direct_copy(obj))
        elif isinstance(obj, pikepdf.Array):
            new = self.pdf.make_indirect(Array(list(obj)))
        else:
            new = self.pdf.make_indirect(_scalar(self.pdf, obj))
        return self.stands_in(obj, new)

    def carried(self, earlier):
        """The earlier themes' replacements after this merge: what they had,
        plus a replacement for every object this merge put in a base's place."""
        out = []
        for pairs in earlier:
            by_base = {b.objgen: a for b, a in pairs}
            new = list(pairs)
            for pal in self.palette_list:
                old = by_base.get(pal.origin.objgen) if pal.origin is not None else None
                if old is not None:
                    n = C.components(old[1])
                    lookup = C.indexed_lookup(old)
                    data = b"".join(lookup[i * n:(i + 1) * n] for i in pal.origin_idx)
                    new.append((pal.base, self.pdf.make_indirect(
                        Array([Name.Indexed, old[1], max(len(pal.entries) - 1, 0), String(data)]))))
            for ident, copies in self.stand_ins.items():
                if ident in by_base:
                    new.extend((copy, by_base[ident]) for copy in copies)
            out.append(new)
        return out

    def swap(self, base, alt):
        self.replace.append((base, self.pdf.make_indirect(alt) if not alt.is_indirect else alt))

    # Palettes ----------------------------------------------------------------
    def palette(self, space_l, vl, space_d, vd, context, role="graphic", origin=None):
        """`origin`: the earlier palette and index the light side painted through."""
        key = (canon(space_l), canon(space_d), context)
        from_pal, from_idx = origin if origin is not None else (None, None)
        if from_pal is not None:
            key += (from_pal.objgen,)
        if context == "paint" and not self.organise and key[0] == key[1] and \
                C.quantise(vl, C.ranges(space_l)) == C.quantise(vd, C.ranges(space_d)):
            return None, None  # the same colour in both builds
        for pal in self.palettes[key]:
            i = pal.index(vl, vd, role, from_idx)
            if i is not None:
                return pal, i
        pal = Palette(self, self.palette_offset + len(self.palette_list), space_l, self.from_dark(space_d), context,
                      from_pal)
        self.palettes[key].append(pal)
        self.palette_list.append(pal)
        return pal, pal.index(vl, vd, role, from_idx)

    # Colour values outside content streams ------------------------------------
    def theme_value(self, owner, key, vl, vd, kind):
        """Move a value that differs between the builds into its own indirect
        object, so a theme can replace it. `kind` says how to recolour it.
        A number (an opacity) is themed with the dictionary that holds it,
        as graphics states are; this returns True when such a number differs."""
        if vl is None or vd is None:
            if (vl is None) != (vd is None):
                self.notes.append(f"{key[1:]} is set in one build only; kept the light build's")
            return False
        if _is_number(vl) or _is_number(vd):
            return canon(vl) != canon(vd)
        if canon(vl) == canon(vd) and not self.organise:
            return
        ck = ("value", canon(vl), canon(vd), kind, self.ident(vl))
        if ck not in self.cache:
            base = self.fresh(vl)
            alt = None
            if canon(vl) != canon(vd):
                alt = self.fresh(self.from_dark(vd))
                self.replace.append((base, alt))
            self.registry.append({"kind": "value", "value": kind, "base": base, "alt": alt,
                                  "context": "mask" if kind == "mask" else "paint"})
            self.stats[f"values ({kind})"] += 1
            self.cache[ck] = base
        owner[key] = self.cache[ck]
        return False

    # Content streams ---------------------------------------------------------
    def merge_ops(self, ops_l, ops_d, res_l, res_d, context="paint", out_res=None, page=False, inherit=False):
        """Walk two content streams side by side and write the merged one.
        A colour is written just before the operator that paints with it, so
        each palette entry knows whether it colours text or graphics.
        `inherit`: the stream starts with its caller's colours (a form or a
        glyph) rather than black."""
        R = out_res if out_res is not None else OutRes(res_l)
        ops_l, ops_d = colour_events(ops_l, res_l), colour_events(ops_d, res_d)
        out = []
        st_l, st_d = [Side(inherit)], [Side(inherit)]
        os_ = [Out(inherit)]
        path, pending = [], []  # pending: a path waiting for the operator that paints it
        resolved = {}
        i = j = 0

        def emit(operands, op):
            out.append((operands, Operator(op)))

        def record(entry, role, area=0.0):
            if entry is not None:
                pal, idx = entry
                pal.roles[idx][role] += 1
                pal.area[idx] = max(pal.area[idx], area)

        def path_area():
            if not path:
                return 0.0
            xs, ys = [], []
            m = os_[-1].ctm
            for (x, y) in path:
                xs.append(m[0] * x + m[2] * y + m[4])
                ys.append(m[1] * x + m[3] * y + m[5])
            # As a share of the page, in the stream's own units: exact on the
            # page, close enough in forms, which are mostly drawn unscaled.
            return (max(xs) - min(xs)) * (max(ys) - min(ys)) / self.page_area

        def gs_dict(res, name):
            group = res.get("/ExtGState") if res is not None else None
            if group is None or str(name) not in group:
                raise MergeError(f"graphics state {name} is missing")
            return group[str(name)]

        def synthetic(side, other):
            d = Dictionary({"/Type": Name.ExtGState})
            for k in other.keys():
                if k == "/Type":
                    continue
                if k in GS_PAINT or k == "/SMask":
                    d[k] = side.gs.get(k, GS_DEFAULT.get(k, Name("/None")))
                else:
                    raise MergeError(f"graphics state {k} is set in one build only")
            return d

        def do_gs(dl, dd, name_l):
            for side, d in ((st_l[-1], dl), (st_d[-1], dd)):
                for k in GS_PAINT + ("/SMask",):
                    if k in d:
                        side.gs[k] = d[k]
            name = self.merge_gs(dl, dd, name_l, R, context)
            if name is not None:
                emit([Name(name)], "gs")

        def colour_of(res, space_name, operands):
            space = _space(res, space_name)
            fam = C.family(space)
            if fam == "/Pattern":
                comps = tuple(_num(v) for v in operands[:-1])
                base = space[1] if isinstance(space, pikepdf.Array) and len(space) > 1 else None
                return ("pattern", str(operands[-1]), comps, base)
            if fam == "/Indexed":
                base, vals = C.indexed_resolve(space, operands[0])
                return ("colour", base, vals, space)
            return ("colour", space, tuple(_num(v) for v in operands), space)

        def resolve(stroke, role):
            """How to write the current fill or stroke colour for this use:
            (what it is, the operators that set it, its palette entry)."""
            el, ed = st_l[-1].colour[stroke], st_d[-1].colour[stroke]
            if el is None and ed is None:
                return None  # the caller's colour, already in effect
            if el is None or ed is None:
                raise MergeError("one build sets a colour where the other uses its caller's")
            key = (id(el), id(ed), stroke, role)
            if key in resolved:
                return resolved[key]
            cl, cd = colour_of(res_l, el.space, el.operands), colour_of(res_d, ed.space, ed.operands)
            cs_op, sc_op = ("CS", "SCN") if stroke else ("cs", "scn")
            # The light side may paint through a palette an earlier merge made.
            origin = None
            through = cl[3] if cl[0] == "pattern" else cl[3] if C.family(cl[3]) == "/Indexed" else None
            if through is not None and self.ident(through) is not None:
                origin = (through, int(round(float(el.operands[0]))))
            if cl[0] == "pattern" and cd[0] == "pattern" and origin is not None:
                name = self.merge_pattern(cl[1], cd[1], res_l, res_d, R, context)
                if cd[3] is None:
                    raise MergeError("a pattern is coloured in one build and uncoloured in the other")
                base_l, vals_l = C.indexed_resolve(through, origin[1])
                pal, idx = self.palette(base_l, vals_l, cd[3], cd[2], context, role, origin=origin)
                if pal is None:  # the colour it already has: write it as it was
                    R.use("/ColorSpace", el.space)
                    result = (("pattern", name, cl[2], el.space),
                              [([Name(el.space)], cs_op), ([*el.operands[:-1], Name(name)], sc_op)], None)
                else:
                    space = self.cache.setdefault(("pattern-space", pal.name), Array([Name.Pattern, pal.base]))
                    space_name = R.add("/ColorSpace", space, "TPs")
                    result = (("pattern", name, pal.name, idx),
                              [([Name(space_name)], cs_op), ([idx, Name(name)], sc_op)], (pal, idx))
            elif cl[0] == "pattern" and cd[0] == "pattern":
                name = self.merge_pattern(cl[1], cd[1], res_l, res_d, R, context)
                if cl[2] == cd[2] and canon(cl[3]) == canon(cd[3]) and not (self.organise and cl[2]):
                    if cl[3] is None:
                        ops = [([Name.Pattern], cs_op)]
                    else:
                        R.use("/ColorSpace", el.space)
                        ops = [([Name(el.space)], cs_op)]
                    ops.append(([*el.operands[:-1], Name(name)], sc_op))
                    result = (("pattern", name, cl[2], el.space), ops, None)
                else:  # an uncoloured tiling pattern painted in colours that differ
                    if cl[3] is None or cd[3] is None:
                        raise MergeError("a pattern is coloured in one build and uncoloured in the other")
                    pal, idx = self.palette(cl[3], cl[2], cd[3], cd[2], context, role)
                    space = self.cache.setdefault(("pattern-space", pal.name), Array([Name.Pattern, pal.base]))
                    space_name = R.add("/ColorSpace", space, "TPs")
                    result = (("pattern", name, pal.name, idx),
                              [([Name(space_name)], cs_op), ([idx, Name(name)], sc_op)], (pal, idx))
            elif "pattern" in (cl[0], cd[0]):
                raise MergeError("a pattern in one build is a solid colour in the other")
            else:
                pal, idx = self.palette(cl[1], cl[2], cd[1], cd[2], context, role, origin=origin)
                if pal is None:  # the same colour in both builds: write it as it was
                    if el.op in DEVICE_OPS:
                        ops = [(list(el.operands), el.op)]
                    else:
                        if el.space not in DEVICE_SPACES:
                            R.use("/ColorSpace", el.space)
                        ops = [([Name(el.space)], cs_op), (list(el.operands), sc_op)]
                    result = (("raw", el.space, tuple(round(_num(v), 6) for v in el.operands)), ops, None)
                else:
                    R.add("/ColorSpace", pal.base, "Th", name=pal.name)
                    result = (("palette", pal.name, idx),
                              [([Name(pal.name)], cs_op), ([idx], "SC" if stroke else "sc")], (pal, idx))
            resolved[key] = result
            return result

        def ensure(stroke, role, area=0.0):
            """Write the current colour, for this use, if it isn't in effect."""
            r = resolve(stroke, role)
            if r is None:
                return
            what, ops, entry = r
            o = os_[-1]
            if o.emitted[stroke] != what:
                for operands, op in ops:
                    emit(operands, op)
                o.emitted[stroke] = what
            record(entry, role, area)

        def flush():
            for operands, op in pending:
                emit(operands, op)
            pending.clear()

        while i < len(ops_l) or j < len(ops_d):
            a = ops_l[i] if i < len(ops_l) else None
            b = ops_d[j] if j < len(ops_d) else None
            na = str(a.operator) if a is not None else None
            nb = str(b.operator) if b is not None else None
            if na != nb:
                # Paint set in one build only: a graphics state or a colour
                # change. The other build keeps what it had.
                # A colour change first: the builds may set colours at
                # different points around a graphics state they both set.
                if na in ("FILL", "STROKE"):
                    st_l[-1].colour[na == "STROKE"] = a
                    i += 1
                    continue
                if nb in ("FILL", "STROKE"):
                    st_d[-1].colour[nb == "STROKE"] = b
                    j += 1
                    continue
                if na == "gs":
                    dl = gs_dict(res_l, a.operands[0])
                    do_gs(dl, synthetic(st_d[-1], dl), str(a.operands[0]))
                    i += 1
                    continue
                if nb == "gs":
                    dd = gs_dict(res_d, b.operands[0])
                    do_gs(synthetic(st_l[-1], dd), dd, None)
                    j += 1
                    continue
                if na == "Do" and nb == "INLINE IMAGE":
                    # An earlier merge made this inline image an image object.
                    xl = R.lookup("/XObject", str(a.operands[0]))
                    if xl.get("/Subtype") == Name.Image and not xl.get("/ImageMask"):
                        flush()
                        merged = self.merge_image(xl, self.inline_to_xobject(b.iimage, res_d, dark=True), context)
                        if merged is xl:
                            R.use("/XObject", str(a.operands[0]))
                            emit([a.operands[0]], "Do")
                        else:
                            emit([Name(R.add("/XObject", merged, "TI"))], "Do")
                        i += 1
                        j += 1
                        continue
                raise MergeError(f"the builds draw differently at operator {i} ({na}) and {j} ({nb})")
            i += 1
            j += 1
            if na in ("FILL", "STROKE"):
                stroke = na == "STROKE"
                st_l[-1].colour[stroke], st_d[-1].colour[stroke] = a, b
                continue
            A, B = list(a.operands), list(b.operands)
            if na in PATH_OPS or na in ("W", "W*"):
                if canon(Array(A)) != canon(Array(B)):
                    raise MergeError(f"the builds draw different shapes at operator {i - 1} ({na})")
                if na == "re":
                    x, y, w, h = (_num(v) for v in A)
                    path.extend([(x, y), (x + w, y + h)])
                elif na in ("m", "l", "c", "v", "y"):
                    vals = [_num(v) for v in A]
                    path.extend(zip(vals[0::2], vals[1::2]))
                pending.append((A, na))
                continue
            if na in FILL_OPS or na in STROKE_OPS or na == "n":
                if na in FILL_OPS:
                    ensure(False, "fill", path_area())
                if na in STROKE_OPS:
                    ensure(True, "stroke")
                flush()
                path.clear()
                emit(A, na)
                continue
            flush()  # a path left without a painting operator: written as it was
            if na == "q":
                st_l.append(st_l[-1].copy())
                st_d.append(st_d[-1].copy())
                os_.append(os_[-1].copy())
                emit([], "q")
            elif na == "Q":
                if len(st_l) > 1:
                    st_l.pop()
                    st_d.pop()
                    os_.pop()
                emit([], "Q")
            elif na == "cm":
                if canon(Array(A)) != canon(Array(B)):
                    raise MergeError(f"the builds place things differently at operator {i - 1} (cm)")
                os_[-1].ctm = _mul(tuple(_num(v) for v in A), os_[-1].ctm)
                emit(A, "cm")
            elif na == "gs":
                do_gs(gs_dict(res_l, A[0]), gs_dict(res_d, B[0]), str(A[0]))
            elif na == "Tr":
                os_[-1].tr = int(A[0])
                emit(A, na)
            elif na in TEXT_SHOW:
                if canon(Array(A)) != canon(Array(B)):
                    raise MergeError(f"the builds show different text at operator {i - 1}")
                tr = os_[-1].tr
                if tr in (0, 2, 4, 6):
                    ensure(False, "text")
                if tr in (1, 2, 5, 6):
                    ensure(True, "text")
                emit(A, na)
            elif na == "Do":
                xl = R.lookup("/XObject", str(A[0]))
                if xl.get("/Subtype") == Name.Form:  # it may paint in the colours set here
                    ensure(False, "fill")
                    ensure(True, "stroke")
                elif xl.get("/ImageMask"):  # a stencil, painted in the fill colour
                    ensure(False, "fill")
                emit([Name(self.merge_xobject(str(A[0]), str(B[0]), res_l, res_d, R, context))], "Do")
            elif na == "sh":
                emit([Name(self.merge_shading(str(A[0]), str(B[0]), res_l, res_d, R, context))], "sh")
            elif na == "INLINE IMAGE":
                if a.iimage.image_mask:
                    ensure(False, "fill")
                self.merge_inline(a, b, R, res_d, context, out)
            elif na == "Tf":
                emit([Name(self.merge_font(str(A[0]), str(B[0]), res_l, res_d, R)), A[1]], "Tf")
                if canon(A[1]) != canon(B[1]):
                    raise MergeError(f"text set at different sizes at operator {i - 1}")
            elif na in ("BDC", "DP") and isinstance(A[1], pikepdf.Name):
                pl = R.lookup("/Properties", str(A[1]))
                group_d = res_d.get("/Properties") if res_d is not None else None
                pd = group_d[str(B[1])] if group_d is not None and str(B[1]) in group_d else None
                if pd is None or canon(pl) != canon(pd):
                    raise MergeError(f"marked content properties differ at operator {i - 1}")
                R.use("/Properties", str(A[1]))
                emit(A, na)
            else:
                if canon(Array(A)) != canon(Array(B)):
                    raise MergeError(f"the builds differ at operator {i - 1} ({na}): {A!r} vs {B!r}")
                emit(A, na)
        flush()
        return out, R

    # Graphics states -----------------------------------------------------------
    def merge_gs(self, dl, dd, name_l, R, context):
        for k in (set(dl.keys()) | set(dd.keys())) - {"/Type", "/SMask"} - set(GS_PAINT):
            if canon(dl.get(k)) != canon(dd.get(k)):
                raise MergeError(f"graphics state {k} differs between the builds")
        sm_l, sm_d = dl.get("/SMask", Name("/None")), dd.get("/SMask", Name("/None"))
        smask = sm_l
        if canon(sm_l) != canon(sm_d):
            if not (isinstance(sm_l, pikepdf.Dictionary) and isinstance(sm_d, pikepdf.Dictionary)):
                raise MergeError("a soft mask is used in one build only")
            smask = self.merge_smask(sm_l, sm_d)
        paint_differs = any(canon(dl.get(k, GS_DEFAULT[k])) != canon(dd.get(k, GS_DEFAULT[k])) for k in GS_PAINT)
        darkens = self.organise and context == "paint" and str(dl.get("/BM", "")) in DARKENING_BLENDS
        if not paint_differs and smask is sm_l and not darkens:
            if name_l is not None:
                R.use("/ExtGState", name_l)
            return name_l
        key = ("gs", canon(dl), canon(dd), self.ident(dl))
        if key not in self.cache:
            base = _direct_copy(dl)
            if isinstance(smask, pikepdf.Dictionary) or "/SMask" in dl:
                base["/SMask"] = smask
            base = self.stands_in(dl, self.pdf.make_indirect(base))
            if paint_differs:
                alt = _direct_copy(base)
                for k in GS_PAINT:
                    if k in dd or k in dl:
                        alt[k] = dd.get(k, GS_DEFAULT[k])
                self.swap(base, alt)
                self.stats["opacities and blend modes"] += 1
            if darkens:  # a derived dark theme turns it into its lightening twin
                self.registry.append({"kind": "blend", "base": base, "context": context})
            self.cache[key] = base
        return R.add("/ExtGState", self.cache[key], "TG")

    def merge_smask(self, sl, sd):
        key = ("smask", canon(sl), canon(sd))
        if key in self.cache:
            return self.cache[key]
        for k in (set(sl.keys()) | set(sd.keys())) - {"/G", "/BC", "/Type"}:
            if canon(sl.get(k)) != canon(sd.get(k)):
                raise MergeError(f"soft mask {k} differs between the builds")
        new = _direct_copy(sl)
        new["/G"] = self.merge_form(sl.G, sd.G, "mask")
        if "/BC" in sl or "/BC" in sd:
            self.theme_value(new, "/BC", sl.get("/BC"), sd.get("/BC"), "mask")
        new = self.pdf.make_indirect(new)
        self.stats["soft masks"] += 1
        self.cache[key] = new
        return new

    # Forms, patterns, shadings, images, fonts ---------------------------------
    def merge_form(self, xl, xd, context, parent_l=None, parent_d=None, inherit=True):
        key = ("form", xl.objgen, xd.objgen, context, inherit)
        if key in self.cache:
            return self.cache[key]
        if canon(xl) == canon(xd) and not (self.organise and context == "paint"):
            self.cache[key] = xl
            return xl
        for k in ("/BBox", "/Matrix", "/Group", "/OC"):
            if canon(xl.get(k)) != canon(xd.get(k)):
                raise MergeError(f"a form's {k[1:]} differs between the builds")
        res_l = xl.get("/Resources", parent_l)
        res_d = xd.get("/Resources", parent_d)
        out, R = self.merge_ops(pikepdf.parse_content_stream(xl), pikepdf.parse_content_stream(xd),
                                res_l, res_d, context, inherit=inherit)
        new = self.pdf.make_stream(pikepdf.unparse_content_stream(out))
        for k, v in xl.items():
            if k not in ("/Length", "/Filter", "/DecodeParms", "/Resources"):
                new[k] = v
        new["/Resources"] = R.finish()
        new = self.pdf.make_indirect(new)
        self.stats["forms merged"] += 1
        self.cache[key] = new
        return new

    def merge_xobject(self, name_l, name_d, res_l, res_d, R, context):
        xl = R.lookup("/XObject", name_l)
        group_d = res_d.get("/XObject") if res_d is not None else None
        if group_d is None or name_d not in group_d:
            raise MergeError(f"XObject {name_d} is missing from the dark build")
        xd = group_d[name_d]
        sub_l, sub_d = str(xl.get("/Subtype")), str(xd.get("/Subtype"))
        if sub_l != sub_d:
            raise MergeError("an XObject is a form in one build and an image in the other")
        if sub_l == "/Form":
            merged = self.merge_form(xl, xd, context, res_l, res_d)
        else:
            merged = self.merge_image(xl, xd, context)
        if merged is xl:
            R.use("/XObject", name_l)
            return name_l
        return R.add("/XObject", merged, "TX" if sub_l == "/Form" else "TI")

    def merge_pattern(self, name_l, name_d, res_l, res_d, R, context):
        pl = R.lookup("/Pattern", name_l)
        group_d = res_d.get("/Pattern") if res_d is not None else None
        if group_d is None or name_d not in group_d:
            raise MergeError(f"pattern {name_d} is missing from the dark build")
        pd = group_d[name_d]
        if int(pl.PatternType) != int(pd.PatternType):
            raise MergeError("a pattern is tiled in one build and shaded in the other")
        if int(pl.PatternType) == 1:
            key = ("tiling", pl.objgen, pd.objgen, context)
            if key not in self.cache:
                if canon(pl) == canon(pd) and not (self.organise and context == "paint"):
                    self.cache[key] = pl
                else:
                    for k in ("/BBox", "/XStep", "/YStep", "/Matrix", "/PaintType", "/TilingType"):
                        if canon(pl.get(k)) != canon(pd.get(k)):
                            raise MergeError(f"a tiling pattern's {k[1:]} differs between the builds")
                    out, PR = self.merge_ops(pikepdf.parse_content_stream(pl), pikepdf.parse_content_stream(pd),
                                             pl.get("/Resources"), pd.get("/Resources"), context,
                                             inherit=int(pl.PaintType) == 2)
                    new = self.pdf.make_stream(pikepdf.unparse_content_stream(out))
                    for k, v in pl.items():
                        if k not in ("/Length", "/Filter", "/DecodeParms", "/Resources"):
                            new[k] = v
                    new["/Resources"] = PR.finish()
                    self.cache[key] = self.pdf.make_indirect(new)
                    self.stats["tiling patterns merged"] += 1
            merged = self.cache[key]
            if merged is pl:
                R.use("/Pattern", name_l)
                return name_l
            return R.add("/Pattern", merged, "TPat")
        # A shading pattern: swapped whole when it differs.
        base = self.themed_shading(pl, pd, "pattern", context)
        if base is pl:
            R.use("/Pattern", name_l)
            return name_l
        return R.add("/Pattern", base, "TPat")

    def themed_shading(self, sl, sd, kind, context="paint"):
        key = (kind, canon(sl), canon(sd), context, self.ident(sl))
        if key in self.cache:
            return self.cache[key]
        differs = canon(sl) != canon(sd)
        if not differs and not (self.organise and context == "paint"):
            self.cache[key] = sl
            return sl
        if differs:
            shading_l = sl.Shading if kind == "pattern" else sl
            shading_d = sd.Shading if kind == "pattern" else sd
            for k in ("/ShadingType", "/Coords", "/Extend", "/Domain", "/Matrix", "/BBox"):
                if canon(shading_l.get(k)) != canon(shading_d.get(k)):
                    raise MergeError(f"a gradient's {k[1:]} differs between the builds")
            if kind == "pattern" and canon(sl.get("/Matrix")) != canon(sd.get("/Matrix")):
                raise MergeError("a gradient's Matrix differs between the builds")
        base = self.fresh(sl)
        alt = None
        if differs:
            alt = self.fresh(self.from_dark(sd))
            self.replace.append((base, alt))
            self.stats["gradients"] += 1
        self.registry.append({"kind": "shading", "shape": kind, "base": base, "alt": alt, "context": context})
        self.cache[key] = base
        return base

    def merge_shading(self, name_l, name_d, res_l, res_d, R, context="paint"):
        sl = R.lookup("/Shading", name_l)
        group_d = res_d.get("/Shading") if res_d is not None else None
        if group_d is None or name_d not in group_d:
            raise MergeError(f"shading {name_d} is missing from the dark build")
        base = self.themed_shading(sl, group_d[name_d], "shading", context)
        if base is sl:
            R.use("/Shading", name_l)
            return name_l
        return R.add("/Shading", base, "TSh")

    def image_samples(self, x):
        """An image's samples as (height, width, components) values, with its
        colour space, or None when the image can't be read that way."""
        if x.get("/ImageMask") or "/Decode" in x:
            return None
        if any(f in RASTER_FILTERS for f in _filters(x)):
            return None
        space = x.get("/ColorSpace")
        if space is None:
            return None
        bpc = int(x.get("/BitsPerComponent", 8))
        if bpc not in (1, 2, 4, 8):
            return None
        try:
            # Specialised, so qpdf decodes RunLengthDecode as well.
            data = x.read_bytes(decode_level=pikepdf.StreamDecodeLevel.specialized)
        except pikepdf.PdfError:
            return None
        samples = _unpack(data, int(x.Width), int(x.Height), bpc, C.components(space))
        return None if samples is None else (samples, space, bpc)

    def merge_image(self, xl, xd, context="paint"):
        key = ("image", xl.objgen, xd.objgen, context)
        if key in self.cache:
            return self.cache[key]
        same = canon(xl) == canon(xd)
        if xl.get("/ImageMask") or xd.get("/ImageMask"):
            if not same:
                raise MergeError("an image mask differs between the builds")
            result = xl  # its colour is the fill colour, already themed
        elif same and not self.organise:
            result = xl
        else:
            result = self.palette_image(xl, xd, same, context)
        self.cache[key] = result
        return result

    def swap_image(self, xl, xd):
        base = self.fresh(xl)
        self.replace.append((base, self.fresh(self.from_dark(xd))))
        self.stats["images swapped whole"] += 1
        return base

    def palette_image(self, xl, xd, same, context):
        """An image with the same shapes in both builds becomes one plane of
        indices with a palette per theme. Otherwise the theme swaps in the
        whole dark image. In a single build, only drawings get a palette."""
        if (int(xl.Width), int(xl.Height)) != (int(xd.Width), int(xd.Height)):
            raise MergeError("an image's size differs between the builds")
        masks_differ = canon(xl.get("/SMask")) != canon(xd.get("/SMask")) or \
            canon(xl.get("/Mask")) != canon(xd.get("/Mask"))
        if masks_differ or isinstance(xl.get("/Mask"), pikepdf.Array):
            # Colour-key masking is written in the image's own colour values,
            # so such an image keeps them.
            return xl if same else self.swap_image(xl, xd)
        pal_context = "mask" if context == "mask" else "image"
        if same and context != "mask":
            scan = self.grey_scan(xl)
            if scan is not None:
                return scan
        sl, sd = self.image_samples(xl), self.image_samples(xd)
        if sl is None or sd is None:
            return xl if same else self.swap_image(xl, xd)
        (al, space_l, bpc_l), (ad, space_d, bpc_d) = sl, sd
        indexed = C.family(space_l) == "/Indexed", C.family(space_d) == "/Indexed"
        if all(indexed) and bpc_l == bpc_d and np.array_equal(al, ad):
            if same:
                n = C.components(space_l[1])
                lookup = C.indexed_lookup(space_l)
                rng = C.ranges(space_l[1])
                used, counts = np.unique(al.reshape(-1), return_counts=True)
                colours = [C.to_srgb(space_l[1], C.dequantise(lookup[int(k) * n:(int(k) + 1) * n], rng))
                           for k in used]
                if not _diagram_like(colours, counts):
                    return xl
            base_space = self.fresh(space_l)
            img = self.fresh(xl)
            img["/ColorSpace"] = base_space
            alt = None
            if canon(space_l) != canon(space_d):
                alt = self.fresh(self.from_dark(space_d))
                self.replace.append((base_space, alt))
                self.stats["image palettes"] += 1
            self.registry.append({"kind": "indexed-image", "base": base_space, "alt": alt, "context": pal_context})
            return img
        if any(indexed) or bpc_l != 8 or bpc_d != 8:
            return xl if same else self.swap_image(xl, xd)
        h, w = al.shape[:2]
        n_l = al.shape[2]
        both = np.concatenate([al.reshape(h * w, -1), ad.reshape(h * w, -1)], axis=1).astype(np.uint8)
        pairs, inverse, counts = np.unique(both, axis=0, return_inverse=True, return_counts=True)
        if len(pairs) > PALETTE_SIZE:
            return xl if same else self.swap_image(xl, xd)
        rng_l = C.ranges(space_l)
        if same:
            colours = [C.to_srgb(space_l, C.dequantise(tuple(int(v) for v in row[:n_l]), rng_l)) for row in pairs]
            if not _diagram_like(colours, counts):
                return xl
        pal = Palette(self, self.palette_offset + len(self.palette_list), space_l, self.from_dark(space_d),
                      pal_context)
        for row in pairs:
            entry = (tuple(int(v) for v in row[:n_l]), tuple(int(v) for v in row[n_l:]))
            pal.keys[entry] = len(pal.entries)
            pal.entries.append(entry)
            pal.roles.append(Counter())
            pal.area.append(0.0)
        self.palette_list.append(pal)
        n = len(pairs)
        bpc = 8 if n > 16 else 4 if n > 4 else 2 if n > 2 else 1
        idx = inverse.reshape(h, w).astype(np.uint8)
        if bpc < 8:
            bits = np.unpackbits(idx[:, :, None], axis=2)[:, :, 8 - bpc:].reshape(h, w * bpc)
            plane = np.packbits(bits, axis=1).tobytes()
        else:
            plane = idx.tobytes()
        img = pikepdf.Stream(self.pdf, zlib.compress(plane, 9))
        img.Type, img.Subtype = Name.XObject, Name.Image
        img.Width, img.Height, img.BitsPerComponent = w, h, bpc
        img.ColorSpace, img.Filter = pal.base, Name.FlateDecode
        for k in ("/SMask", "/Interpolate", "/Intent", "/Mask", "/OC", "/Metadata", "/StructParent"):
            if k in xl:
                img[k] = xl[k]
        self.stats["images stored as palette indices"] += 1
        return self.stands_in(xl, self.pdf.make_indirect(img))

    def grey_scan(self, x):
        """A grey image of a page, with dark marks on light paper, gets an
        Indexed colour space over its own grey in which each index is its
        own grey. It draws exactly as before, its data is untouched, and a
        theme swaps the palette for one running from the theme's ink to its
        paper. None if the image isn't one."""
        space = x.get("/ColorSpace")
        bpc = int(x.get("/BitsPerComponent", 8))
        if x.get("/ImageMask") or space is None or not _grey_space(space) or bpc not in (1, 2, 4, 8):
            return None
        if "/Decode" in x and [float(v) for v in x.Decode] != [0.0, 1.0]:
            return None
        if "/JPXDecode" in _filters(x) or isinstance(x.get("/Mask"), pikepdf.Array):
            return None  # JPEG 2000 can carry its own colour space; colour-key masks
        try:
            grey = np.asarray(pikepdf.PdfImage(x).as_pil_image().convert("L"))
        except Exception:  # a filter this machine can't decode, such as JBIG2 without jbig2dec
            return None
        if (grey >= 192).mean() < SCAN_PAPER or ((grey > 64) & (grey < 192)).mean() > SCAN_MIDTONES:
            return None
        hival = (1 << bpc) - 1
        key = ("scan palette", canon(space), hival)  # one palette for every scan of its kind
        palette = self.cache.get(key)
        if palette is None:
            lookup = bytes(round(k * 255 / hival) for k in range(hival + 1))
            palette = self.cache[key] = self.pdf.make_indirect(Array([Name.Indexed, space, hival, String(lookup)]))
            self.registry.append({"kind": "scan", "base": palette, "hival": hival, "context": "image"})
        img = self.fresh(x)
        img["/ColorSpace"] = palette
        if "/Decode" in img:
            del img["/Decode"]  # [0 1] is the default for grey; for indices it would mean only two
        self.stats["grey scans given a palette"] += 1
        return img

    def merge_inline(self, a, b, R, res_d, context, out):
        il, idd = a.iimage, b.iimage
        same = il.unparse() == idd.unparse()
        cs = il.obj.get("/ColorSpace")
        if same and isinstance(cs, pikepdf.Name) and str(cs) not in DEVICE_SPACES:
            # A named space lives in the resources, so it can differ between
            # the builds while the image itself reads the same.
            try:
                same = canon(C.resolve(R.base, str(cs))) == canon(C.resolve(res_d, str(cs)))
            except KeyError:
                pass
        if same and (not self.organise or il.image_mask):
            self.keep_inline(a, R, out)
            return
        if il.image_mask or idd.image_mask:
            raise MergeError("an inline image mask differs between the builds")
        xl = self.inline_to_xobject(il, R.base, dark=False)
        xd = self.inline_to_xobject(idd, res_d, dark=True)
        result = self.merge_image(xl, xd, context)
        if result is xl:  # nothing to theme: leave the inline image as it was
            self.keep_inline(a, R, out)
            return
        name = R.add("/XObject", result, "TI")
        out.append(([Name(name)], Operator("Do")))
        self.stats["inline images made into image objects"] += 1

    @staticmethod
    def keep_inline(a, R, out):
        out.append(a)
        cs = a.iimage.obj.get("/ColorSpace")
        if isinstance(cs, pikepdf.Name) and str(cs) not in DEVICE_SPACES:
            R.use("/ColorSpace", str(cs))

    def inline_to_xobject(self, ii, res, dark):
        """An inline image as an image XObject with the same samples and
        colour space, so it can be themed like any other image."""
        d = ii.obj
        data = ii._data._inline_image_raw_bytes()
        cs = space = d.get("/ColorSpace")
        if isinstance(cs, pikepdf.Name) and str(cs) not in DEVICE_SPACES:
            space = _space(res, str(cs))
        if "/Filter" not in d and space is not None:
            # Unfiltered samples end where the image does; drop the space before EI.
            row = (int(d.Width) * C.components(space) * int(d.get("/BitsPerComponent", 8)) + 7) // 8
            data = data[:row * int(d.Height)]
        x = pikepdf.Stream(self.pdf, data)
        for k, v in d.items():
            if k != "/Length":
                x[k] = v
        x.Type, x.Subtype = Name.XObject, Name.Image
        if space is not cs:
            x.ColorSpace = self.from_dark(space) if dark else space
        return self.pdf.make_indirect(x)

    def merge_font(self, name_l, name_d, res_l, res_d, R):
        fl = R.lookup("/Font", name_l)
        group_d = res_d.get("/Font") if res_d is not None else None
        if group_d is None or name_d not in group_d:
            raise MergeError(f"font {name_d} is missing from the dark build")
        fd = group_d[name_d]
        if str(fl.get("/Subtype")) == "/Type3" and (canon(fl) != canon(fd) or self.organise):
            key = ("type3", fl.objgen, fd.objgen)
            if key not in self.cache:
                self.cache[key] = self.merge_type3(fl, fd, res_l, res_d)
            return R.add("/Font", self.cache[key], "TF")
        if str(fl.get("/BaseFont")) != str(fd.get("/BaseFont")):
            raise MergeError("text is set in different fonts in the two builds")
        R.use("/Font", name_l)
        return name_l

    def merge_type3(self, fl, fd, res_l, res_d):
        for k in (set(fl.keys()) | set(fd.keys())) - {"/CharProcs", "/Resources"}:
            if canon(fl.get(k)) != canon(fd.get(k)):
                raise MergeError(f"a Type 3 font's {k[1:]} differs between the builds")
        rl = fl.get("/Resources", res_l)
        rd = fd.get("/Resources", res_d)
        R = OutRes(rl)
        procs = Dictionary()
        for glyph, sl in fl.CharProcs.items():
            sd = fd.CharProcs.get(glyph)
            if sd is None:
                raise MergeError(f"glyph {glyph} is missing from the dark build's Type 3 font")
            out, _ = self.merge_ops(pikepdf.parse_content_stream(sl), pikepdf.parse_content_stream(sd),
                                    rl, rd, "paint", out_res=R, inherit=True)
            procs[glyph] = self.pdf.make_indirect(self.pdf.make_stream(pikepdf.unparse_content_stream(out)))
        new = _direct_copy(fl)
        new["/CharProcs"] = procs
        new["/Resources"] = R.finish()
        self.stats["Type 3 fonts merged"] += 1
        return self.pdf.make_indirect(new)

    # Pages and the rest of the document ---------------------------------------
    def merge_page(self, pl, pd):
        for k in ("/MediaBox", "/CropBox", "/Rotate", "/UserUnit"):
            if canon(pl.obj.get(k)) != canon(pd.obj.get(k)):
                raise MergeError(f"page {k[1:]} differs between the builds")
        x0, y0, x1, y1 = (float(v) for v in pl.mediabox)
        self.page_area = max((x1 - x0) * (y1 - y0), 1.0)
        res_l, res_d = pl.resources, pd.resources
        out, R = self.merge_ops(pikepdf.parse_content_stream(pl), pikepdf.parse_content_stream(pd),
                                res_l, res_d, "paint", page=True)
        pl.obj.Contents = self.pdf.make_stream(pikepdf.unparse_content_stream(out))
        pl.obj.Resources = R.finish()
        if "/Thumb" in pl.obj and "/Thumb" in pd.obj and canon(pl.obj.Thumb) != canon(pd.obj.Thumb):
            base = self.fresh(pl.obj.Thumb)
            self.replace.append((base, self.fresh(self.from_dark(pd.obj.Thumb))))
            pl.obj.Thumb = base
            self.stats["thumbnails"] += 1
        boxes_l, boxes_d = pl.obj.get("/BoxColorInfo"), pd.obj.get("/BoxColorInfo")
        if isinstance(boxes_l, pikepdf.Dictionary) and isinstance(boxes_d, pikepdf.Dictionary):
            for box, info in boxes_l.items():
                if box in boxes_d and "/C" in info:
                    self.theme_value(info, "/C", info.get("/C"), boxes_d[box].get("/C"), "colour")
        self.merge_annots(pl, pd)

    def merge_annots(self, pl, pd):
        al, ad = pl.obj.get("/Annots"), pd.obj.get("/Annots")
        if al is None and ad is None:
            return
        if al is None or ad is None or len(al) != len(ad):
            raise MergeError("a page has different annotations in the two builds")
        for x, y in zip(al, ad):
            self.merge_annot(x, y)

    def merge_annot(self, x, y):
        key = ("annot", x.objgen if x.is_indirect else id(x))
        if key in self.cache:
            return
        self.cache[key] = True
        for k in ANNOT_GEOMETRY:
            if canon(x.get(k)) != canon(y.get(k)):
                raise MergeError(f"an annotation's {k[1:]} differs between the builds")
        numbers = []
        for k in ANNOT_PAINT:
            if k in x or k in y:
                kind = {"/DA": "da", "/DS": "style", "/RC": "style", "/BM": "blend"}.get(
                    k, "opacity" if k in ("/CA", "/ca") else "colour")
                if self.theme_value(x, k, x.get(k), y.get(k), kind):
                    numbers.append(k)
        mk_l, mk_d = x.get("/MK"), y.get("/MK")
        if isinstance(mk_l, pikepdf.Dictionary) and isinstance(mk_d, pikepdf.Dictionary):
            for k in MK_PAINT:
                if k in mk_l or k in mk_d:
                    self.theme_value(mk_l, k, mk_l.get(k), mk_d.get(k), "colour")
        ap_l, ap_d = x.get("/AP"), y.get("/AP")
        if isinstance(ap_l, pikepdf.Dictionary) and isinstance(ap_d, pikepdf.Dictionary):
            for which in ("/N", "/R", "/D"):
                vl, vd = ap_l.get(which), ap_d.get(which)
                if vl is None or vd is None:
                    continue
                if isinstance(vl, pikepdf.Stream):  # appearances start from the default state
                    ap_l[which] = self.merge_form(vl, vd, "paint", inherit=False)
                else:
                    for state, sl in list(vl.items()):
                        if state in vd and isinstance(sl, pikepdf.Stream):
                            vl[state] = self.merge_form(sl, vd[state], "paint", inherit=False)
            self.stats["annotations"] += 1
        if "/Popup" in x and "/Popup" in y:
            self.merge_annot(x.Popup, y.Popup)
        if numbers:  # an opacity differs: the theme replaces the annotation's dictionary
            if not x.is_indirect:
                raise MergeError("an annotation's opacity differs but the annotation is not an indirect object")
            alt = _direct_copy(x)
            for k in numbers:
                alt[k] = y[k]
            self.swap(x, alt)
            self.stats["annotations with their own opacity"] += 1

    def merge_outlines(self, item_l, item_d):
        seen = set()
        while item_l is not None and item_d is not None:
            if item_l.objgen in seen:
                break
            seen.add(item_l.objgen)
            if canon(item_l.get("/Title")) != canon(item_d.get("/Title")):
                self.notes.append("a bookmark title differs between the builds; kept the light build's")
            if "/C" in item_l or "/C" in item_d:
                self.theme_value(item_l, "/C", item_l.get("/C", Array([0, 0, 0])), item_d.get("/C", Array([0, 0, 0])),
                                 "outline")
                self.stats["bookmark colours"] += 1
            if "/First" in item_l and "/First" in item_d:
                self.merge_outlines(item_l.First, item_d.First)
            item_l, item_d = item_l.get("/Next"), item_d.get("/Next")

    def merge_fields(self, fields_l, fields_d):
        for fl, fd in zip(fields_l, fields_d):
            if "/DA" in fl or "/DA" in fd:
                self.theme_value(fl, "/DA", fl.get("/DA"), fd.get("/DA"), "da")
            if "/Kids" in fl and "/Kids" in fd:
                self.merge_fields(fl.Kids, fd.Kids)

    def merge_attributes(self, attrs_l, attrs_d):
        listed_l = list(attrs_l) if isinstance(attrs_l, pikepdf.Array) else [attrs_l]
        listed_d = list(attrs_d) if isinstance(attrs_d, pikepdf.Array) else [attrs_d]
        for a, b in zip(listed_l, listed_d):
            if isinstance(a, pikepdf.Dictionary) and isinstance(b, pikepdf.Dictionary):
                for k, kind in LAYOUT_PAINT.items():
                    if k in a or k in b:
                        self.theme_value(a, k, a.get(k), b.get(k), kind)
                        self.stats["structure colours"] += 1

    def merge_structure(self, el, ed, seen):
        if not isinstance(el, pikepdf.Dictionary) or not isinstance(ed, pikepdf.Dictionary):
            return
        ident = el.objgen if el.is_indirect else None
        if ident is not None:
            if ident in seen:
                return
            seen.add(ident)
        attrs_l, attrs_d = el.get("/A"), ed.get("/A")
        if attrs_l is not None and attrs_d is not None:
            self.merge_attributes(attrs_l, attrs_d)
        kids_l, kids_d = el.get("/K"), ed.get("/K")
        if isinstance(kids_l, pikepdf.Array) and isinstance(kids_d, pikepdf.Array):
            for a, b in zip(kids_l, kids_d):
                if isinstance(a, pikepdf.Dictionary) and "/S" in a:
                    self.merge_structure(a, b, seen)
        elif isinstance(kids_l, pikepdf.Dictionary) and "/S" in kids_l:
            self.merge_structure(kids_l, kids_d, seen)

    def merge_document(self):
        root_l, root_d = self.pdf.Root, self.dark.Root
        if "/Outlines" in root_l and "/Outlines" in root_d and "/First" in root_l.Outlines \
                and "/First" in root_d.Outlines:
            self.merge_outlines(root_l.Outlines.First, root_d.Outlines.First)
        form_l, form_d = root_l.get("/AcroForm"), root_d.get("/AcroForm")
        if isinstance(form_l, pikepdf.Dictionary) and isinstance(form_d, pikepdf.Dictionary):
            if "/DA" in form_l or "/DA" in form_d:
                self.theme_value(form_l, "/DA", form_l.get("/DA"), form_d.get("/DA"), "da")
            if "/Fields" in form_l and "/Fields" in form_d:
                self.merge_fields(form_l.Fields, form_d.Fields)
        st_l, st_d = root_l.get("/StructTreeRoot"), root_d.get("/StructTreeRoot")
        if isinstance(st_l, pikepdf.Dictionary) and isinstance(st_d, pikepdf.Dictionary):
            seen = set()
            kids_l, kids_d = st_l.get("/K"), st_d.get("/K")
            if isinstance(kids_l, pikepdf.Array) and isinstance(kids_d, pikepdf.Array):
                for a, b in zip(kids_l, kids_d):
                    self.merge_structure(a, b, seen)
            elif kids_l is not None and kids_d is not None:
                self.merge_structure(kids_l, kids_d, seen)
            cm_l, cm_d = st_l.get("/ClassMap"), st_d.get("/ClassMap")
            if isinstance(cm_l, pikepdf.Dictionary) and isinstance(cm_d, pikepdf.Dictionary):
                for name, a in cm_l.items():
                    b = cm_d.get(name)
                    if b is not None:
                        self.merge_attributes(a, b)
        coll_l, coll_d = root_l.get("/Collection"), root_d.get("/Collection")
        if isinstance(coll_l, pikepdf.Dictionary) and isinstance(coll_d, pikepdf.Dictionary):
            colours_l, colours_d = coll_l.get("/Colors"), coll_d.get("/Colors")
            if isinstance(colours_l, pikepdf.Dictionary) and isinstance(colours_d, pikepdf.Dictionary):
                for k in COLLECTION_PAINT:
                    if k in colours_l or k in colours_d:
                        self.theme_value(colours_l, k, colours_l.get(k), colours_d.get(k),
                                         "text" if "Text" in k else "colour")

    # Writing the palettes ------------------------------------------------------
    def finish(self):
        for pal in self.palette_list:
            light = b"".join(bytes(e[0]) for e in pal.entries)
            dark = b"".join(bytes(e[1]) for e in pal.entries)
            hival = max(len(pal.entries) - 1, 0)
            pal.base.extend([Name.Indexed, pal.space_l, hival, String(light)])
            if light != dark or canon(pal.space_l) != canon(pal.space_d):
                pal.alt = self.pdf.make_indirect(Array([Name.Indexed, pal.space_d, hival, String(dark)]))
                self.replace.insert(0, (pal.base, pal.alt))
        return self.pdf


def merge(light, dark=None, *, organise=False):
    """Merge two builds (paths or open Pdfs) into one organised Pdf. With no
    dark build, organises a single document's colours into palettes."""
    light_pdf = light if isinstance(light, pikepdf.Pdf) else pikepdf.open(light)
    if dark is None:
        dark_pdf = light_pdf
        organise = True
    else:
        dark_pdf = dark if isinstance(dark, pikepdf.Pdf) else pikepdf.open(dark)
    if len(light_pdf.pages) != len(dark_pdf.pages):
        raise MergeError("the builds have different page counts")
    m = Merger(light_pdf, dark_pdf, organise=organise)
    pages_d = list(dark_pdf.pages) if dark_pdf is not light_pdf else None
    for n, pl in enumerate(light_pdf.pages):
        pd = pages_d[n] if pages_d is not None else pl
        m.merge_page(pl, pd)
    m.merge_document()
    m.finish()
    return m


def _next_palette_number(pdf):
    """One past the highest /ThN colour space name already in the file."""
    highest = -1
    for obj in pdf.objects:
        if not isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
            continue
        res = obj.get("/Resources")
        for holder in (obj, res if isinstance(res, pikepdf.Dictionary) else None):
            spaces = holder.get("/ColorSpace") if holder is not None else None
            if isinstance(spaces, pikepdf.Dictionary):
                for name in spaces.keys():
                    found = re.fullmatch(r"/Th(\d+)", name)
                    if found:
                        highest = max(highest, int(found.group(1)))
    return highest + 1


def _reach(obj, seen):
    """Add every indirect object reachable from `obj` to `seen`."""
    stack = [obj]
    while stack:
        o = stack.pop()
        if getattr(o, "is_indirect", False):  # a string can be a base object too (DA, DS, RC)
            if o.objgen in seen:
                continue
            seen.add(o.objgen)
        if not isinstance(o, (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)):
            continue
        stack.extend(o if isinstance(o, pikepdf.Array) else [v for _, v in o.items()])


def _in_use(pdf, replaces):
    """Each theme's replacements without those whose base object nothing
    draws any more: later merges copy objects, and the copies carry on."""
    live = set()
    _reach(pdf.Root, live)
    grown = True
    followed = set()
    while grown:  # a replacement can itself lead to base objects (an annotation's appearance)
        grown = False
        for pairs in replaces:
            for base, alt in pairs:
                if base.objgen in live and alt.objgen not in followed:
                    followed.add(alt.objgen)
                    before = len(live)
                    _reach(alt, live)
                    grown = grown or len(live) > before
    return [[(b, a) for b, a in pairs if b.objgen in live] for pairs in replaces]


def merge_builds(builds, *, organise=False):
    """Merge one build per theme (paths or open Pdfs). The first build is
    the default; each of the others becomes an alternate theme, and
    `replaces` on the result holds their replacements in the same order."""
    pdfs = [b if isinstance(b, pikepdf.Pdf) else pikepdf.open(b) for b in builds]
    if len(pdfs) < 2:
        raise MergeError("merging needs at least two builds")
    if organise and len(pdfs) > 2:
        raise MergeError("working themes out isn't supported with more than two builds")
    default = pdfs[0]
    for k, alt in enumerate(pdfs[1:], start=2):
        if len(alt.pages) != len(default.pages):
            raise MergeError(f"theme {k} has {len(alt.pages)} pages, the default has {len(default.pages)}")
    replaces, palettes, stats, notes = [], [], Counter(), []
    m = None
    for k, alt in enumerate(pdfs[1:], start=2):
        m = Merger(default, alt, organise=organise, earlier=replaces)
        pages = list(alt.pages)
        for n, page in enumerate(default.pages):
            try:
                m.merge_page(page, pages[n])
            except MergeError as e:
                raise MergeError(f"theme {k}, page {n + 1}: {e}") from None
        try:
            m.merge_document()
        except MergeError as e:
            raise MergeError(f"theme {k}: {e}") from None
        m.finish()
        replaces = m.carried(replaces) + [m.replace]
        palettes += m.palette_list
        stats.update(m.stats)
        notes += [note for note in m.notes if note not in notes]
    m._replaces = _in_use(default, replaces) if len(pdfs) > 2 else replaces
    m.palette_list, m.stats, m.notes, m.alts = palettes, stats, notes, pdfs[1:]
    return m
