"""What themes could break in a PDF/A or PDF/UA file, checked by comparing a
build with its themed version. It is not a validator: run veraPDF for that.
It checks the things theming touches:

  - the catalog entries PDF/A and PDF/UA rely on are still there, unchanged:
    the XMP metadata (and its PDF/A and PDF/UA identification), the output
    intent, MarkInfo, the structure tree, Lang and ViewerPreferences;
  - every palette, default and alternate, and every image uses a colour
    space the build already used, so no device colour space appears that
    the output intent doesn't cover;
  - no PostScript calculator functions and no transfer functions appear;
  - every page's marked content (tags and MCIDs, in order) is unchanged, so
    the structure tree still points at the same content.

Usage: python tools/conformance.py build.pdf themed.pdf
"""

from __future__ import annotations

import os
import re
import sys

import pikepdf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pdfthemes.core import canon  # noqa: E402

CATALOG = ("/Metadata", "/OutputIntents", "/MarkInfo", "/StructTreeRoot", "/Lang", "/ViewerPreferences")


def xmp_ids(pdf):
    meta = pdf.Root.get("/Metadata")
    if meta is None:
        return {}
    data = meta.read_bytes()
    found = {}
    for key in ("pdfaid:part", "pdfaid:conformance", "pdfuaid:part"):
        m = re.search(rb"<" + key.encode() + rb">([^<]+)<|" + key.encode() + rb"=\"([^\"]+)\"", data)
        if m:
            found[key] = (m.group(1) or m.group(2)).decode()
    return found


def space_kind(space):
    """A colour space as a short label: DeviceRGB, ICCBased(3), Indexed over ..."""
    if isinstance(space, pikepdf.Name):
        return str(space)[1:]
    if isinstance(space, pikepdf.Array) and len(space):
        family = str(space[0])[1:]
        if family == "ICCBased":
            return f"ICCBased({int(space[1].get('/N', 0))})"
        if family == "Indexed":
            return f"Indexed over {space_kind(space[1])}"
        return family
    return "?"


def colour_spaces(pdf):
    """Every colour space the file holds, by label: in resources, on images
    and shadings, and every palette (alternate themes' palettes included)."""
    seen = set()

    def note(space):
        label = space_kind(space)
        seen.add(label)
        if label.startswith("Indexed over "):
            seen.add(label[len("Indexed over "):])

    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Array) and len(obj) and obj[0] == pikepdf.Name.Indexed:
            note(obj)
        if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
            if "/ColorSpace" in obj:
                cs = obj.ColorSpace
                if isinstance(cs, pikepdf.Dictionary):  # a resources dictionary
                    for space in cs.values():
                        note(space)
                else:
                    note(cs)
    return seen


def functions_and_transfers(pdf):
    found = set()
    for obj in pdf.objects:
        if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
            if obj.get("/FunctionType") == 4:
                found.add("PostScript calculator function")
            for key in ("/TR", "/TR2"):
                if key in obj and obj[key] != pikepdf.Name.Default and obj.get("/Type") != pikepdf.Name.Mask:
                    found.add(f"transfer function ({key})")
    return found


def marked_content(page_or_form, seen=None):
    """The page's marked-content tags and MCIDs, in order, forms included."""
    seen = seen if seen is not None else set()
    out = []
    resources = page_or_form.get("/Resources", pikepdf.Dictionary())
    xobjects = resources.get("/XObject", pikepdf.Dictionary())
    for operands, op in pikepdf.parse_content_stream(page_or_form):
        name = str(op)
        if name == "BDC":
            props = operands[1]
            mcid = props.get("/MCID") if isinstance(props, pikepdf.Dictionary) else None
            out.append((str(operands[0]), int(mcid) if mcid is not None else None))
        elif name == "BMC":
            out.append((str(operands[0]), None))
        elif name == "Do":
            x = xobjects.get(str(operands[0]))
            if x is not None and x.get("/Subtype") == pikepdf.Name.Form and x.objgen not in seen:
                seen.add(x.objgen)
                out.append(("form", None))
                out.extend(marked_content(x, seen))
    return out


def struct_shape(pdf):
    """The structure tree as plain values: each element's type, attributes
    and text alternatives, and its content as MCIDs with page numbers, or as
    the kind of object it refers to. Page content itself is left out, since
    theming rewrites how colours are set."""
    pages = {p.objgen: n for n, p in enumerate(pdf.pages, 1)}

    def page_of(d):
        pg = d.get("/Pg")
        return pages.get(pg.objgen) if pg is not None else None

    def walk(el, inherited_page=None):
        if isinstance(el, int) or type(el).__name__ == "Decimal":
            return ("mcid", int(el), inherited_page)
        if not isinstance(el, pikepdf.Dictionary):
            return ("?",)
        t = el.get("/Type")
        if t == pikepdf.Name.MCR:
            return ("mcid", int(el.MCID), page_of(el) or inherited_page)
        if t == pikepdf.Name.OBJR:
            obj = el.Obj
            return ("object", str(obj.get("/Subtype", obj.get("/Type", "?"))), page_of(el) or inherited_page)
        page = page_of(el) or inherited_page
        kids = el.get("/K")
        kids = list(kids) if isinstance(kids, pikepdf.Array) else [kids] if kids is not None else []
        own = tuple((k, canon(el[k])) for k in ("/S", "/T", "/Lang", "/Alt", "/ActualText", "/E", "/A", "/C", "/ID")
                    if k in el)
        return ("element", own, tuple(walk(k, page) for k in kids))

    root = pdf.Root.get("/StructTreeRoot")
    if root is None:
        return None
    kids = root.get("/K")
    kids = list(kids) if isinstance(kids, pikepdf.Array) else [kids] if kids is not None else []
    return (canon(root.get("/RoleMap")), canon(root.get("/ClassMap")), tuple(walk(k) for k in kids))


def compare(build_path, themed_path):
    problems, notes = [], []
    with pikepdf.open(build_path) as build, pikepdf.open(themed_path) as themed:
        for key in CATALOG:
            if key in build.Root and key not in themed.Root:
                problems.append(f"catalog {key} was dropped")
            elif key == "/StructTreeRoot":
                if key in build.Root and struct_shape(build) != struct_shape(themed):
                    problems.append("the structure tree changed")
            elif key in build.Root and canon(build.Root[key]) != canon(themed.Root[key]):
                problems.append(f"catalog {key} changed")
        ids_b, ids_t = xmp_ids(build), xmp_ids(themed)
        if ids_b != ids_t:
            problems.append(f"XMP identification changed: {ids_b} -> {ids_t}")
        notes.append(f"XMP identification: {ids_t or 'none'}")
        spaces_b, spaces_t = colour_spaces(build), colour_spaces(themed)
        new = sorted(s for s in spaces_t - spaces_b if not s.startswith("Indexed over "))
        if new:
            problems.append(f"colour spaces the build didn't use: {new}")
        notes.append(f"colour spaces: {sorted(s for s in spaces_t if not s.startswith('Indexed'))}")
        extra = functions_and_transfers(themed) - functions_and_transfers(build)
        if extra:
            problems.append(f"new: {sorted(extra)}")
        for n, (pb, pt) in enumerate(zip(build.pages, themed.pages), 1):
            if marked_content(pb.obj) != marked_content(pt.obj):
                problems.append(f"page {n}: marked content differs")
            if pb.obj.get("/StructParents") != pt.obj.get("/StructParents"):
                problems.append(f"page {n}: StructParents changed")
        notes.append(f"pages: {len(themed.pages)}, marked-content items on page 1: {len(marked_content(themed.pages[0].obj))}")
    return problems, notes


if __name__ == "__main__":
    problems, notes = compare(sys.argv[1], sys.argv[2])
    for line in notes:
        print("  " + line)
    for line in problems:
        print("  PROBLEM: " + line)
    print("  no problems found" if not problems else f"  {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
