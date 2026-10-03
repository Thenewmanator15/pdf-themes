"""Check the theme engine against the test document (tools/corpus.py).

1. Two builds. Merge corpus-light.pdf and corpus-dark.pdf, add the standard
   themes, and check that showing Light and Dark gives the same pixels as
   each build on its own in Poppler, MuPDF and PDFium, and the same colour
   values outside the page content (annotations, form fields, bookmarks,
   structure attributes, the thumbnail).
2. One build. Organise corpus-light.pdf alone, add the standard themes
   (including a derived Dark), and check that its default look and values
   haven't changed.
3. Every theme is contrast-checked; derived themes that fail are left out.

Writes out/corpus-themed.pdf, out/corpus-single-themed.pdf,
results/corpus.json and results/corpus-themes.png.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

import pikepdf
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import corpus  # noqa: E402
import measure  # noqa: E402
from pdfthemes import apply, merge, paint_paper, themes  # noqa: E402
from pdfthemes.core import SAVE, canon  # noqa: E402
from pdfthemes.derive import add_themes  # noqa: E402
from pdfthemes.merge import ANNOT_PAINT, LAYOUT_PAINT, MK_PAINT  # noqa: E402

OUT = os.path.join(ROOT, "out")
RESULTS = os.path.join(ROOT, "results")


def hex_paper(h):
    return tuple(v / 255 for v in corpus.rgb255(h))


LIGHT_PAPER, DARK_PAPER = hex_paper(corpus.LIGHT["paper"]), hex_paper(corpus.DARK["paper"])


# ── Colour values outside page content ───────────────────────────────────────

def colour_values(pdf):
    """Every colour value outside the page content, keyed by where it lives."""
    out = {}
    for n, page in enumerate(pdf.pages, 1):
        for k, a in enumerate(page.obj.get("/Annots", [])):
            for key in ANNOT_PAINT:
                if key in a:
                    out[f"page {n} annotation {k} ({a.Subtype}) {key}"] = canon(a[key])
            mk = a.get("/MK")
            if mk is not None:
                for key in MK_PAINT:
                    if key in mk:
                        out[f"page {n} annotation {k} MK {key}"] = canon(mk[key])
        boxes = page.obj.get("/BoxColorInfo")
        if boxes is not None:
            for box, info in boxes.items():
                out[f"page {n} BoxColorInfo {box}"] = canon(info.get("/C"))
        if "/Thumb" in page.obj:
            out[f"page {n} thumbnail"] = canon(page.obj.Thumb)
    item, k = pdf.Root.Outlines.get("/First") if "/Outlines" in pdf.Root else None, 0
    while item is not None:
        out[f"bookmark {k} C"] = canon(item.get("/C"))
        item, k = item.get("/Next"), k + 1
    form = pdf.Root.get("/AcroForm")
    if form is not None:
        out["AcroForm DA"] = canon(form.get("/DA"))
        for k, f in enumerate(form.Fields):
            out[f"field {k} DA"] = canon(f.get("/DA"))

    def walk(el, path):
        attrs = el.get("/A")
        listed = list(attrs) if isinstance(attrs, pikepdf.Array) else [attrs] if attrs is not None else []
        for j, a in enumerate(listed):
            for key in LAYOUT_PAINT:
                if key in a:
                    out[f"structure {path} A{j} {key}"] = canon(a[key])
        kids = el.get("/K")
        if isinstance(kids, pikepdf.Array):
            for j, kid in enumerate(kids):
                if isinstance(kid, pikepdf.Dictionary) and "/S" in kid:
                    walk(kid, f"{path}/{j}")

    root = pdf.Root.get("/StructTreeRoot")
    if root is not None:
        for j, kid in enumerate(root.K):
            walk(kid, str(j))
        for name, a in root.get("/ClassMap", {}).items():
            for key in LAYOUT_PAINT:
                if key in a:
                    out[f"class {name} {key}"] = canon(a[key])
    return out


def compare_values(a, b):
    keys = sorted(set(a) | set(b))
    differ = [k for k in keys if a.get(k) != b.get(k)]
    return {"values": len(keys), "same": len(keys) - len(differ), "differ": differ}


# ── Drawing ──────────────────────────────────────────────────────────────────

def shown(src, dst, theme=None, paper=(1.0, 1.0, 1.0)):
    """Write a copy of src as a reader shows it: theme applied, paper painted."""
    with pikepdf.open(src) as pdf:
        if theme is not None:
            paper = apply(pdf, theme)
        paint_paper(pdf, paper)
        values = colour_values(pdf)
        pdf.save(dst)
    return values


def compare_pixels(a, b, pages):
    result = {}
    for engine, render in measure.ENGINES.items():
        total = {"pixels": 0, "identical": 0, "differ_gt_2": 0, "max_diff": 0}
        for p in range(pages):
            c = measure.compare(render(a, p), render(b, p))
            if not c["same_size"]:
                raise AssertionError(f"{engine} page {p + 1}: sizes differ")
            for k in ("pixels", "identical", "differ_gt_2"):
                total[k] += c[k]
            total["max_diff"] = max(total["max_diff"], c["max_diff"])
        result[engine] = total
    return result


def contact_sheet(path, names, dst, scale=0.28):
    tiles = []
    for name in names:
        with tempfile.TemporaryDirectory() as tmp:
            f = os.path.join(tmp, "t.pdf")
            shown(path, f, name)
            tiles.append((name, [measure.render_pdfium(f, p, scale) for p in range(len(pikepdf.open(path).pages))]))
    h, w = tiles[0][1][0].shape[:2]
    cols = len(tiles[0][1])
    sheet = Image.new("RGB", (cols * (w + 8) + 150, len(tiles) * (h + 8)), (110, 110, 118))
    draw = ImageDraw.Draw(sheet)
    for r, (name, imgs) in enumerate(tiles):
        draw.text((8, r * (h + 8) + h // 2 - 6), name, fill=(255, 255, 255))
        for k, img in enumerate(imgs):
            sheet.paste(Image.fromarray(img), (150 + k * (w + 8), r * (h + 8)))
    sheet.save(dst)


# ── The checks ───────────────────────────────────────────────────────────────

def main():
    os.makedirs(RESULTS, exist_ok=True)
    paths = corpus.write(OUT)
    report = {"engines": measure.ENGINE_VERSIONS, "sizes": {}, "two_builds": {}, "one_build": {}}
    pages = len(pikepdf.open(paths["light"]).pages)
    sizes = report["sizes"]
    sizes["light build"] = os.path.getsize(paths["light"])
    sizes["dark build"] = os.path.getsize(paths["dark"])
    for name in ("light", "dark"):  # the builds saved the same way as the themed files
        with pikepdf.open(paths[name]) as pdf:
            f = os.path.join(OUT, f"corpus-{name}-saved.pdf")
            pdf.save(f, **SAVE)
            sizes[f"{name} build, compressed like the themed file"] = os.path.getsize(f)

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Two builds
        t = time.time()
        m = merge(paths["light"], paths["dark"])
        add_themes(m, LIGHT_PAPER, DARK_PAPER, derived=False)
        f = os.path.join(tmp, "two-dark-only.pdf")
        m.pdf.save(f, **SAVE)
        sizes["themed: Light and Dark only"] = os.path.getsize(f)

        m = merge(paths["light"], paths["dark"], organise=True)
        theme_reports = add_themes(m, LIGHT_PAPER, DARK_PAPER)
        themed = os.path.join(OUT, "corpus-themed.pdf")
        m.pdf.save(themed, **SAVE)
        sizes["themed: Light, Dark and the standard themes"] = os.path.getsize(themed)
        two = report["two_builds"]
        two["seconds"] = round(time.time() - t, 1)
        two["merge"] = {k: v for k, v in sorted(m.stats.items())}
        two["palettes"] = len(m.palette_list)
        two["palette entries"] = sum(len(p.entries) for p in m.palette_list)
        two["themes"] = theme_reports
        two["kept"] = themes(pikepdf.open(themed))
        for theme, build, paper in (("Light", paths["light"], LIGHT_PAPER), ("Dark", paths["dark"], DARK_PAPER)):
            a, b = os.path.join(tmp, f"build-{theme}.pdf"), os.path.join(tmp, f"themed-{theme}.pdf")
            values_build = shown(build, a, None, paper)
            values_theme = shown(themed, b, theme)
            two[theme] = {"pixels": compare_pixels(a, b, pages), "values": compare_values(values_build, values_theme)}
        contact_sheet(themed, two["kept"], os.path.join(RESULTS, "corpus-themes.png"))

        # 2. One build
        t = time.time()
        m = merge(paths["light"])
        theme_reports = add_themes(m, LIGHT_PAPER, DARK_PAPER)
        single = os.path.join(OUT, "corpus-single-themed.pdf")
        m.pdf.save(single, **SAVE)
        sizes["one build, organised, with the standard themes"] = os.path.getsize(single)
        one = report["one_build"]
        one["seconds"] = round(time.time() - t, 1)
        one["merge"] = {k: v for k, v in sorted(m.stats.items())}
        one["themes"] = theme_reports
        one["kept"] = themes(pikepdf.open(single))
        a, b = os.path.join(tmp, "single-build.pdf"), os.path.join(tmp, "single-themed.pdf")
        values_build = shown(paths["light"], a)
        values_theme = shown(single, b, "Light")
        one["Light"] = {"pixels": compare_pixels(a, b, pages), "values": compare_values(values_build, values_theme)}
        contact_sheet(single, one["kept"], os.path.join(RESULTS, "corpus-single-themes.png"))

    with open(os.path.join(RESULTS, "corpus.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    return report


def summarise(report):
    lines = []
    for label, part, names in (("Two builds", report["two_builds"], ("Light", "Dark")),
                               ("One build", report["one_build"], ("Light",))):
        lines.append(f"{label}: themes kept {part['kept']} ({part['seconds']} s)")
        for name in names:
            for engine, r in part[name]["pixels"].items():
                lines.append(f"  {name:5} {engine:7} identical {r['identical']}/{r['pixels']} "
                             f"(>2 levels: {r['differ_gt_2']}, max {r['max_diff']})")
            v = part[name]["values"]
            lines.append(f"  {name:5} values  {v['same']}/{v['values']} the same" +
                         (f"; differ: {v['differ'][:6]}" if v["differ"] else ""))
        for t in part["themes"]:
            lines.append(f"  theme {t['name']:22} kept={t['kept']!s:5} passed={t['passed']!s:5} lowest={t['lowest']} "
                         f"failures={len(t['failures'])}")
    for k, v in report["sizes"].items():
        lines.append(f"  size  {k}: {v:,}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarise(main()))
