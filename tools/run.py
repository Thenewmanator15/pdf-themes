"""Build Typst documents in both modes, merge each pair into one themed PDF
with the standard themes, and measure the result.

Run from the project folder:
    python tools/run.py                      # the test page in examples/sample
    python tools/run.py --cv path/to/cv.typ  # also a Typst CV that takes a mode input
Needs typst, pikepdf, pymupdf, pypdfium2, numpy, pillow, and poppler-utils
(pdftoppm, pdftotext) and qpdf on the path.

For each document, out/ gets:
  <doc>-light.pdf, <doc>-dark.pdf   the two builds, as Typst makes them
  <doc>-themed.pdf                  one file: light by default, the dark build's theme and the standard themes
  <doc>-themed-as-dark.pdf          what a reader draws after switching to Dark
  <doc>-two-layers.pdf              today's alternative: both builds as optional content layers
  <doc>-themes.png                  page 1 in every theme the file kept
and out/results.json holds every measurement. tools/check_corpus.py does the
same for the test document that covers every kind of PDF object.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import pikepdf  # noqa: E402
import typst  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import measure  # noqa: E402
from baseline import two_layers  # noqa: E402
from pdfthemes import apply, merge, paint_paper, themes  # noqa: E402
from pdfthemes.core import SAVE  # noqa: E402
from pdfthemes.derive import add_themes  # noqa: E402

OUT = ROOT / "out"

DOCS = {
    "sample": dict(source=ROOT / "examples" / "sample" / "sample.typ", fonts=ROOT / "examples" / "fonts",
                   paper={"Light": (1, 1, 1), "Dark": (0x1C / 255, 0x1C / 255, 0x1E / 255)}),
}


def build(doc, mode):
    src = DOCS[doc]["source"]
    data = typst.compile(str(src), root=str(src.parent), font_paths=[str(DOCS[doc]["fonts"])], ignore_system_fonts=True,
                         sys_inputs={"mode": mode}, pdf_standards=["2.0"])
    path = OUT / f"{doc}-{mode}.pdf"
    path.write_bytes(data)
    return path


def shown(src, target, theme=None, paper=(1.0, 1.0, 1.0)):
    """A copy of src as a reader shows it: theme applied, paper painted."""
    with pikepdf.open(src) as pdf:
        if theme is not None:
            paper = apply(pdf, theme)
        paint_paper(pdf, tuple(paper))
        pdf.save(target, **SAVE)
    return target


def resaved_size(path):
    with tempfile.TemporaryDirectory() as d, pikepdf.open(path) as pdf:
        target = pathlib.Path(d) / "x.pdf"
        pdf.save(target, **SAVE)
        return target.stat().st_size


def sheet(themed, target, scale=0.5):
    names = themes(pikepdf.open(themed))
    tiles = []
    with tempfile.TemporaryDirectory() as d:
        for name in names:
            f = pathlib.Path(d) / "t.pdf"
            shown(themed, f, name)
            tiles.append((name, measure.render_pdfium(f, 0, scale)))
    h, w = tiles[0][1].shape[:2]
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * (w + 12), rows * (h + 28)), (110, 110, 118))
    draw = ImageDraw.Draw(img)
    for k, (name, tile) in enumerate(tiles):
        x, y = (k % cols) * (w + 12), (k // cols) * (h + 28)
        draw.text((x + 4, y + 8), name, fill=(255, 255, 255))
        img.paste(Image.fromarray(tile), (x, y + 24))
    img.save(target)


def run(doc, tmp):
    paper = DOCS[doc]["paper"]
    r = {}
    light, dark = build(doc, "light"), build(doc, "dark")

    m = merge(light, dark)
    add_themes(m, paper["Light"], paper["Dark"], derived=False)
    dark_only = tmp / f"{doc}-dark-only.pdf"
    m.pdf.save(dark_only, **SAVE)

    m = merge(light, dark, organise=True)
    r["themes"] = add_themes(m, paper["Light"], paper["Dark"])
    themed = OUT / f"{doc}-themed.pdf"
    m.pdf.save(themed, **SAVE)
    r["merge"] = {"palettes": len(m.palette_list), "colours": sum(len(p.entries) for p in m.palette_list),
                  "replaced by Dark": len(m.replace), **dict(sorted(m.stats.items()))}

    as_dark = shown(themed, OUT / f"{doc}-themed-as-dark.pdf", "Dark")
    dark_on_paper = shown(dark, tmp / f"{doc}-dark-on-paper.pdf", None, paper["Dark"])
    layers = OUT / f"{doc}-two-layers.pdf"
    two_layers(light, dark).save(layers, **SAVE)

    r["sizes"] = {
        "light_as_typst_writes_it": light.stat().st_size,
        "dark_as_typst_writes_it": dark.stat().st_size,
        "light": resaved_size(light),
        "dark": resaved_size(dark),
        "themed_light_and_dark": dark_only.stat().st_size,
        "themed": themed.stat().st_size,
        "two_layers": layers.stat().st_size,
    }

    pixels = {}
    for engine, render in measure.ENGINES.items():
        for label, a, b in (("default theme vs light build", light, themed),
                            ("dark theme vs dark build", dark_on_paper, as_dark)):
            pixels.setdefault(engine, {})[label] = [measure.compare(render(a, n), render(b, n))
                                                    for n in range(measure.page_count(a))]
    r["pixels"] = pixels

    r["text_same_as_light_build"] = measure.text_of(light) == measure.text_of(themed)
    r["text_same_in_dark_theme"] = measure.text_of(themed) == measure.text_of(as_dark)
    with pikepdf.open(light) as a, pikepdf.open(themed) as b:
        mcids = lambda p: sum(1 for pg in p.pages for ins in pikepdf.parse_content_stream(pg)
                              if str(ins.operator) == "BDC" and isinstance(ins.operands[1], pikepdf.Dictionary)
                              and "/MCID" in ins.operands[1])
        r["tags"] = {"struct_tree_kept": "/StructTreeRoot" in b.Root,
                     "marked_content_light": mcids(a), "marked_content_themed": mcids(b)}
    q = subprocess.run(["qpdf", "--check", str(themed)], capture_output=True, text=True)
    r["qpdf_check"] = " ".join(q.stdout.split()[-17:]) if q.returncode == 0 else q.stdout + q.stderr
    sheet(themed, OUT / f"{doc}-themes.png")
    return r, themed, as_dark


def pair_picture(a_path, b_path, target, page=0, scale=1.25):
    a = measure.render_pdfium(a_path, page, scale=scale)
    b = measure.render_pdfium(b_path, page, scale=scale)
    gap = int(16 * scale)
    img = Image.new("RGB", (a.shape[1] * 2 + gap, a.shape[0]), (255, 255, 255))
    img.paste(Image.fromarray(a), (0, 0))
    img.paste(Image.fromarray(b), (a.shape[1] + gap, 0))
    img.save(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cv", type=pathlib.Path, help="a Typst CV that takes --input mode=light|dark")
    parser.add_argument("--cv-fonts", type=pathlib.Path, help="the CV's font folder (default: fonts/ beside it)")
    opts = parser.parse_args()
    if opts.cv:
        DOCS = {"cv": dict(source=opts.cv.resolve(), fonts=(opts.cv_fonts or opts.cv.resolve().parent / "fonts"),
                           paper={"Light": (1, 1, 1), "Dark": (0, 0, 0)}), **DOCS}
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*"):
        if old.name.split("-")[0] in DOCS or old.name == "results.json":
            old.unlink()
    results = {"date": datetime.date.today().isoformat(), "engines": measure.ENGINE_VERSIONS}
    with tempfile.TemporaryDirectory() as d:
        for doc in DOCS:
            results[doc], themed, as_dark = run(doc, pathlib.Path(d))
            pair_picture(themed, as_dark, OUT / f"{doc}-both-themes.png")
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))

    for doc in DOCS:
        r = results[doc]
        s = r["sizes"]
        print(f"\n== {doc}")
        print("merge:", r["merge"])
        print(f"sizes: light {s['light']}  dark {s['dark']}  "
              f"themed, Light and Dark {s['themed_light_and_dark']} "
              f"({100 * (s['themed_light_and_dark'] / s['light'] - 1):+.1f}%)  "
              f"themed, all themes {s['themed']} ({100 * (s['themed'] / s['light'] - 1):+.1f}%)  "
              f"two layers {s['two_layers']} ({100 * (s['two_layers'] / s['light'] - 1):+.1f}%)  "
              f"two files {s['light'] + s['dark']}")
        print("text same:", r["text_same_as_light_build"], r["text_same_in_dark_theme"], "tags:", r["tags"])
        print("qpdf:", r["qpdf_check"])
        for t in r["themes"]:
            print(f"  theme {t['name']:<22} kept={t['kept']} passed={t['passed']} lowest={t['lowest']} "
                  f"({t['lowest_text']!r})")
        for engine, comps in r["pixels"].items():
            for label, pages in comps.items():
                print(f"  {engine:8} {label:30}", "; ".join(
                    f"p{n + 1} {p['identical'] / p['pixels']:.4%} same, {p['differ_gt_2']} px >2, max {p['max_diff']}"
                    for n, p in enumerate(pages)))
