"""Render PDFs in Poppler, MuPDF, PDFium and pdf.js, and make side-by-side sheets.

    python3 tools/render.py out/objects-light.pdf out/objects-dark.pdf --dpi 60 --pages 1-6
"""
import argparse
import os
import subprocess
import sys

import numpy as np
import pymupdf
import pypdfium2 as pdfium
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINES = ["poppler", "mupdf", "pdfium", "pdfjs"]


def render_poppler(path, outdir, dpi, pages):
    prefix = os.path.join(outdir, "p")
    for pg in pages:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(pg), "-l", str(pg), "-singlefile",
                        path, "%s%03d" % (prefix, pg)], check=True, capture_output=True)
    return {pg: Image.open("%s%03d.png" % (prefix, pg)).convert("RGB") for pg in pages}


def render_mupdf(path, dpi, pages):
    doc = pymupdf.open(path)
    out = {}
    for pg in pages:
        pix = doc[pg - 1].get_pixmap(dpi=dpi, annots=True)
        out[pg] = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return out


def render_pdfium(path, dpi, pages):
    doc = pdfium.PdfDocument(path)
    try:
        doc.init_forms()
    except Exception:
        pass
    out = {}
    for pg in pages:
        page = doc[pg - 1]
        out[pg] = page.render(scale=dpi / 72, may_draw_forms=True, draw_annots=True).to_pil().convert("RGB")
    return out


def render_pdfjs(path, outdir, dpi, pages):
    env = dict(os.environ)
    if "PDFJS_NODE_MODULES" not in env and os.path.isdir("/opt/npm-tools/node_modules/pdfjs-dist"):
        env["PDFJS_NODE_MODULES"] = "/opt/npm-tools/node_modules"
    subprocess.run(["node", os.path.join(HERE, "render_pdfjs.mjs"), path, outdir, str(dpi / 72),
                    ",".join(map(str, pages))], check=True, capture_output=True, text=True, env=env)
    return {pg: Image.open(os.path.join(outdir, "j%03d.png" % pg)).convert("RGB") for pg in pages}


def render_all(path, dpi, pages, workdir):
    os.makedirs(workdir, exist_ok=True)
    res = {}
    errors = {}
    for eng in ENGINES:
        try:
            if eng == "poppler":
                res[eng] = render_poppler(path, workdir, dpi, pages)
            elif eng == "mupdf":
                res[eng] = render_mupdf(path, dpi, pages)
            elif eng == "pdfium":
                res[eng] = render_pdfium(path, dpi, pages)
            else:
                res[eng] = render_pdfjs(path, workdir, dpi, pages)
        except subprocess.CalledProcessError as e:
            errors[eng] = (e.stderr or "")[-2000:]
        except Exception as e:  # keep going, report at the end
            errors[eng] = repr(e)
    return res, errors


def sheet(images, labels, path):
    w = sum(im.width for im in images) + 6 * (len(images) - 1)
    h = max(im.height for im in images) + 14
    out = Image.new("RGB", (w, h), (128, 128, 128))
    d = ImageDraw.Draw(out)
    x = 0
    for im, lab in zip(images, labels):
        out.paste(im, (x, 14))
        d.text((x + 2, 1), lab, fill=(255, 255, 255))
        x += im.width + 6
    out.save(path)


def parse_pages(spec, count):
    if not spec:
        return list(range(1, count + 1))
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in out if 1 <= p <= count]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--dpi", type=int, default=60)
    ap.add_argument("--pages")
    ap.add_argument("--out", default="renders")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for path in args.pdfs:
        name = os.path.splitext(os.path.basename(path))[0]
        count = pymupdf.open(path).page_count
        pages = parse_pages(args.pages, count)
        res, errors = render_all(path, args.dpi, pages, os.path.join(args.out, name + "-work"))
        for eng, err in errors.items():
            print("[%s] %s failed: %s" % (name, eng, err.strip()[:600]))
        engines = [e for e in ENGINES if e in res]
        for pg in pages:
            ims = [res[e][pg] for e in engines]
            sheet(ims, engines, os.path.join(args.out, "%s-p%02d.png" % (name, pg)))
            # how different are the engines from each other? (mean abs diff vs MuPDF)
            base = np.asarray(res["mupdf"][pg].resize((200, 283))).astype(int) if "mupdf" in res else None
            diffs = []
            for e in engines:
                a = np.asarray(res[e][pg].resize((200, 283))).astype(int)
                diffs.append("%s %.1f" % (e, np.abs(a - base).mean() if base is not None else 0))
            print("%s p%02d  %s" % (name, pg, "  ".join(diffs)))


if __name__ == "__main__":
    main()
