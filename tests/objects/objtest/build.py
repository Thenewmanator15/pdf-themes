"""Build the light and dark objects test files.

    python3 -m objtest.build [outdir]

writes objects-light.pdf and objects-dark.pdf: two builds of one document
that draw the same objects in the same order and differ only in colour.
"""
import os
import sys

import pikepdf

from .core import Doc
from .palette import build_palettes
from .resources import Res
from . import pages_content as C
from . import pages_images as IM
from . import pages_graphics2 as G2
from . import pages_annots as AN
from . import pages_interactive as IA
from . import pages_media as MD
from . import pages_document as DC
from . import pages_structure as ST
from . import pages_device as DV
from . import pages_appendix as AX
from . import scifigs as SC

PAGES = [
    C.page_paths,
    C.page_colour,
    C.page_shadings,
    C.page_patterns,
    C.page_fonts,
    C.page_text_effects,
    IM.page_image_spaces,
    IM.page_image_filters,
    IM.page_masks,
    G2.page_blending,
    G2.page_groups,
    G2.page_forms,
    G2.page_layers,
    AN.page_annot_shapes,
    AN.page_annot_more,
    IA.page_links,
    IA.page_fields_text,
    IA.page_fields_buttons,
    MD.page_media,
    DC.page_navigation,
    DC.page_rotated,
    DC.page_userunit,
    ST.page_structure,
    DV.page_device,
    SC.page_sci_plots,
    SC.page_sci_more,
    AX.page_appendix,
]


def build(pal, only=None):
    doc = Doc(pal)
    res = Res(doc)
    for maker in PAGES:
        if only and maker.__name__ not in only:
            continue
        maker(doc, res)
    return doc.finish()


def save(pdf, path, version="2.0"):
    """Flate-compress the streams that have no filter, then save without letting qpdf touch
    any other stream: with compress_streams on, qpdf would decode LZW, ASCII85, ASCIIHex and
    PNG predictors and recompress them as plain Flate, and the filter tests would vanish."""
    import zlib
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Stream) and "/Filter" not in obj and obj.get("/Type") != pikepdf.Name.Metadata:
            data = obj.read_bytes()
            obj.write(zlib.compress(data, 9), filter=pikepdf.Name.FlateDecode)
    pdf.save(path, force_version=version, object_stream_mode=pikepdf.ObjectStreamMode.generate, deterministic_id=True,
             stream_decode_level=pikepdf.StreamDecodeLevel.none, compress_streams=False)


def write_coverage(doc, outdir):
    import json
    rows = [dict((k, v) for k, v in c.items() if k != "rect") for c in doc.coverage]
    with open(os.path.join(outdir, "coverage.json"), "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    lines = ["# Coverage", "", "Every tile in the objects test, the ISO 32000-2 tables it exercises, and what a theme "
             "should do with it.", "", "| Page | Object | ISO 32000-2 tables | Theme |", "|---|---|---|---|"]
    for r in rows:
        if r["ref"]:
            lines.append("| %d | %s | %s | %s |" % (r["page"], r["object"], r["ref"].replace("T", ""), r["expect"]))
    with open(os.path.join(outdir, "COVERAGE.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def build_doc(pal, only=None):
    doc = Doc(pal)
    res = Res(doc)
    for maker in PAGES:
        if only and maker.__name__ not in only:
            continue
        maker(doc, res)
    return doc


def main(outdir="out", only=None):
    os.makedirs(outdir, exist_ok=True)
    for pal in build_palettes():
        doc = build_doc(pal, only)
        if pal.name == "light":
            write_coverage(doc, outdir)
        pdf = doc.finish()
        path = os.path.join(outdir, "objects-%s.pdf" % pal.name)
        save(pdf, path)
        print("wrote", path, os.path.getsize(path), "bytes,", len(pdf.pages), "pages")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["out"]))
