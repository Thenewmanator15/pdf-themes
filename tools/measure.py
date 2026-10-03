"""Rendering, comparison and checking helpers for the prototype."""

from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
import pikepdf
import pymupdf
import pypdfium2 as pdfium
from PIL import Image

SCALE = 2  # 144 dpi


def render_poppler(path, page, scale=SCALE):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", str(72 * scale), "-f", str(page + 1), "-l", str(page + 1),
                        "-png", "-singlefile", str(path), os.path.join(d, "p")], check=True)
        return np.asarray(Image.open(os.path.join(d, "p.png")).convert("RGB"))


def render_mupdf(path, page, scale=SCALE):
    pix = pymupdf.open(str(path))[page].get_pixmap(matrix=pymupdf.Matrix(scale, scale))
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()


def render_pdfium(path, page, scale=SCALE):
    source = path if isinstance(path, (bytes, bytearray)) else str(path)
    doc = pdfium.PdfDocument(source)
    doc.init_forms()  # so form fields are drawn, as in the other engines
    return np.asarray(doc[page].render(scale=scale, may_draw_forms=True).to_pil().convert("RGB"))


ENGINES = {"Poppler": render_poppler, "MuPDF": render_mupdf, "PDFium": render_pdfium}
ENGINE_VERSIONS = {
    "Poppler": subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True).stderr.split()[2],
    "MuPDF": pymupdf.VersionFitz,
    "PDFium": __import__("pypdfium2.version", fromlist=["PDFIUM_INFO"]).PDFIUM_INFO.__str__(),
}


def compare(a: np.ndarray, b: np.ndarray) -> dict:
    if a.shape != b.shape:
        return {"same_size": False}
    d = np.abs(a.astype(int) - b.astype(int)).max(axis=2)
    return {
        "same_size": True,
        "pixels": int(d.size),
        "identical": int((d == 0).sum()),
        "differ_gt_2": int((d > 2).sum()),
        "max_diff": int(d.max()),
    }


def page_count(path) -> int:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def text_of(path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout

