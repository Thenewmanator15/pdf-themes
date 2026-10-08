"""What a two-build merge writes, in a form that can be compared from one
version of the merge to the next: the themes and what each swaps, the merge's
counts, and a hash of every page as PDFium draws it in each theme.

    python tools/snapshot_two_build.py    # rewrite tests/snapshots/two-build.json
"""
import hashlib
import io
import json
import pathlib

import numpy as np
import pikepdf
import pypdfium2 as pdfium

from pdfthemes import apply, describe, merge, paint_paper
from pdfthemes.core import SAVE
from pdfthemes.derive import add_themes

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "objects" / "out"
SNAPSHOT = ROOT / "tests" / "snapshots" / "two-build.json"
DARK_PAPER = (0x18 / 255, 0x19 / 255, 0x1C / 255)
PAIRS = ["legacy", "portfolio", "figures/mpl-lines", "figures/mpl-heat_div", "figures/pgf_surface", "objects"]


def paths(pair):
    return OUT / f"{pair}-light.pdf", OUT / f"{pair}-dark.pdf"


def _pixels(data):
    doc = pdfium.PdfDocument(data)
    h = hashlib.sha256()
    for n in range(len(doc)):
        h.update(np.asarray(doc[n].render(scale=1).to_pil().convert("RGB")).tobytes())
    return h.hexdigest()


def _saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf, **SAVE)
    return buf.getvalue()


def _stable(value):
    """Without the check's date or object numbers, which may change freely."""
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k.lower() not in ("date", "base", "replacement")}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def snapshot(light, dark):
    m = merge(pikepdf.open(light), pikepdf.open(dark))
    add_themes(m, (1, 1, 1), DARK_PAPER, derived=False)
    themed = _saved(m.pdf)
    with pikepdf.open(io.BytesIO(themed)) as pdf:
        described = _stable(describe(pdf))
        paint_paper(pdf, apply(pdf, "Dark"))
        as_dark = _saved(pdf)
    return json.loads(json.dumps({"themes": described, "stats": dict(sorted(m.stats.items())),
                                  "notes": list(m.notes), "pixels_light": _pixels(themed),
                                  "pixels_dark": _pixels(as_dark)}))


if __name__ == "__main__":
    SNAPSHOT.write_text(json.dumps({pair: snapshot(*paths(pair)) for pair in PAIRS}, indent=1) + "\n")
