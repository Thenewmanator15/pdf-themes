"""A scanned page: the test page drawn at 150 dpi in grey, with a scanner's
off-white paper and a little noise, saved as a JPEG inside a PDF, then given
the standard themes with `pdf-themes add`. It has no text and no vector
colour, so its themes come from the scan alone.

Run from the project folder:
    python tools/scan.py

Writes out/scan.pdf (the scan), out/scan-themed.pdf, demo/scan-themed.pdf
and results/scan-themes.png (the page in every theme the file kept).
"""

from __future__ import annotations

import io
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402
import pikepdf  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
import typst  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import measure  # noqa: E402
from pdfthemes import apply, merge, paint_paper, themes  # noqa: E402
from pdfthemes.core import SAVE  # noqa: E402
from pdfthemes.derive import add_themes  # noqa: E402

OUT, RESULTS, DEMO = ROOT / "out", ROOT / "results", ROOT / "demo"
SOURCE = ROOT / "examples" / "sample" / "sample.typ"
FONTS = ROOT / "examples" / "fonts"
DARK_PAPER = (0x1C / 255, 0x1C / 255, 0x1E / 255)
DPI = 150


def scan(dst):
    data = typst.compile(str(SOURCE), root=str(SOURCE.parent), font_paths=[str(FONTS)], ignore_system_fonts=True,
                         sys_inputs={"mode": "light"}, pdf_standards=["2.0"])
    page = pdfium.PdfDocument(data)[0]
    width, height = page.get_size()
    grey = np.asarray(page.render(scale=DPI / 72).to_pil().convert("L")).astype(float)
    noise = np.random.default_rng(1).normal(0, 3, grey.shape)
    grey = np.clip(grey * 244 / 255 + 6 * (1 - grey / 255) + noise, 0, 255).astype(np.uint8)  # off-white paper
    buf = io.BytesIO()
    Image.fromarray(grey, "L").save(buf, "JPEG", quality=80)
    pdf = pikepdf.new()
    image = pikepdf.Stream(pdf, buf.getvalue(), Type=pikepdf.Name.XObject, Subtype=pikepdf.Name.Image,
                           Width=grey.shape[1], Height=grey.shape[0], ColorSpace=pikepdf.Name.DeviceGray,
                           BitsPerComponent=8, Filter=pikepdf.Name.DCTDecode)
    p = pdf.add_blank_page(page_size=(width, height))
    p.obj.Contents = pdf.make_stream(f"q {width:.3f} 0 0 {height:.3f} 0 0 cm /Im0 Do Q".encode())
    p.obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=image))
    pdf.save(dst, **SAVE)
    return dst


def contact_sheet(path, dst, scale=0.5):
    names = themes(pikepdf.open(path))
    tiles = []
    for name in names:
        tmp = OUT / "scan-shown.pdf"
        with pikepdf.open(path) as pdf:
            paint_paper(pdf, apply(pdf, name))
            pdf.save(tmp)
        tiles.append((name, measure.render_pdfium(tmp, 0, scale)))
        tmp.unlink()
    h, w = tiles[0][1].shape[:2]
    cols = 4
    sheet = Image.new("RGB", (cols * (w + 10) + 10, -(-len(tiles) // cols) * (h + 30) + 10), (110, 110, 118))
    draw = ImageDraw.Draw(sheet)
    for k, (name, img) in enumerate(tiles):
        x, y = 10 + (k % cols) * (w + 10), 10 + (k // cols) * (h + 30)
        draw.text((x, y), name, fill=(255, 255, 255))
        sheet.paste(Image.fromarray(img), (x, y + 16))
    sheet.save(dst)


def main():
    OUT.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    src = scan(OUT / "scan.pdf")
    m = merge(src)
    reports = add_themes(m, (1.0, 1.0, 1.0), DARK_PAPER)
    themed = OUT / "scan-themed.pdf"
    m.pdf.save(themed, **SAVE)
    shutil.copy(themed, DEMO / "scan-themed.pdf")
    contact_sheet(themed, RESULTS / "scan-themes.png")
    same = {engine: bool(np.array_equal(render(src, 0), render(themed, 0))) for engine, render in measure.ENGINES.items()}
    print(f"scan {src.stat().st_size:,} bytes, themed {themed.stat().st_size:,} bytes")
    print("default theme draws like the scan:", same)
    for r in reports:
        print(f"  {r['name']:22} {'kept' if r['kept'] else 'left out (' + str(r['reason']) + ')'}")


if __name__ == "__main__":
    main()
