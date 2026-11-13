"""A PDF/A-1 file, or a PDF/X file older than PDF 1.5, is written without object
streams and keeps its version. Any other file older than 1.5 gets object streams.

Saving with object streams writes a cross-reference stream and moves the file to PDF
1.5. PDF/A-1 is built on PDF 1.4 and forbids cross-reference streams (ISO 19005-1,
6.1.4), so six veraPDF test files that pass as PDF/A-1 failed after theming, and
PDF/X-1a and X-3 are the same. From 15 October every file older than 1.5 was kept that
way, and a browser's print, which is PDF 1.4, grew by half again over the original
where it had grown by 1%. Only the files whose standard asks for it are kept old now.
"""

import subprocess
import sys

import pikepdf

PDFA1 = b"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
<pdfaid:part>1</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance></rdf:Description>
</rdf:RDF></x:xmpmeta><?xpacket end="w"?>"""


def old_file(path, pages=40, metadata=None, pdfx=False):
    """A PDF 1.4 file with many small objects, the way a browser's print has them."""
    pdf = pikepdf.new()
    for i in range(pages):
        page = pdf.add_blank_page(page_size=(100, 100))
        page.obj.Contents = pdf.make_stream(f"0.2 0.4 0.8 rg {i % 50} 10 30 30 re f".encode())
        page.obj.Annots = pdf.make_indirect(pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link, Rect=[0, 0, 10, 10], Border=[0, 0, 0],
            A=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String(f"https://example.org/{i}"))))]))
    if metadata:
        pdf.Root.Metadata = pdf.make_stream(metadata, Type=pikepdf.Name.Metadata, Subtype=pikepdf.Name.XML)
    if pdfx:
        pdf.docinfo["/GTS_PDFXVersion"] = "PDF/X-1:2001"
    pdf.save(path, min_version="1.4", force_version="1.4", object_stream_mode=pikepdf.ObjectStreamMode.disable)


def add(src, out):
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True,
                   capture_output=True)


def old_form(pdf):
    return not any(isinstance(o, pikepdf.Stream) and o.get("/Type") in ("/ObjStm", "/XRef") for o in pdf.objects)


def test_a_pdfa1_file_stays_1_4_without_object_streams(tmp_path):
    src, out = tmp_path / "pdfa1.pdf", tmp_path / "themed.pdf"
    old_file(src, metadata=PDFA1)
    add(src, out)
    with pikepdf.open(out) as themed:
        assert themed.pdf_version == "1.4"
        assert old_form(themed)


def test_a_pdfx_file_older_than_1_5_stays_as_it_is(tmp_path):
    src, out = tmp_path / "pdfx.pdf", tmp_path / "themed.pdf"
    old_file(src, pdfx=True)
    add(src, out)
    with pikepdf.open(out) as themed:
        assert themed.pdf_version == "1.4"
        assert old_form(themed)


def test_any_other_1_4_file_gets_object_streams_and_stays_small(tmp_path):
    src, out = tmp_path / "print.pdf", tmp_path / "themed.pdf"
    old_file(src)
    add(src, out)
    with pikepdf.open(out) as themed:
        assert themed.pdf_version >= "1.5"
        assert not old_form(themed)
        assert "/Metadata" not in themed.Root
    assert out.stat().st_size < src.stat().st_size * 1.1
