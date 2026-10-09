"""PDF/A and PDF/UA: a themed file that says it follows them still passes
veraPDF, as it is stored and with each theme shown. The file is the proposal
itself (demo/proposal-themed.pdf), a tagged PDF/A-2a and PDF/UA-1 document
built once in each of the eight standard themes.

Skipped unless veraPDF can be run: have `verapdf` on the path or set VERAPDF
(see tools/verapdf.py)."""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import verapdf  # noqa: E402

PROPOSAL = ROOT / "demo" / "proposal-themed.pdf"


@pytest.fixture(scope="module")
def rows():
    if verapdf.command() is None:
        pytest.skip("veraPDF is not installed")
    return verapdf.validate(PROPOSAL.read_bytes())


def test_the_file_says_it_is_pdf_a_2a_and_pdf_ua_1():
    import pikepdf
    with pikepdf.open(PROPOSAL) as pdf:
        assert verapdf.claimed(pdf) == ["2a", "ua1"]


def test_it_is_validated_as_stored_and_in_each_of_its_themes(rows):
    shown = ["as stored", "Dark", "Light, more contrast", "Dark, more contrast", "Cream", "Peach", "Yellow",
             "Turquoise"]
    assert [r["theme"] for r in rows if r["profile"] == "PDF/A-2A"] == shown
    assert [r["theme"] for r in rows if r["profile"] == "PDF/UA-1"] == shown


def test_every_theme_passes_both_standards(rows):
    assert [(r["theme"], r["profile"], r["failed"]) for r in rows if not r["passed"]] == []
