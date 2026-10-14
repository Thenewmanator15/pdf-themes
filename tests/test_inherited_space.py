"""A form that sets a colour in its caller's colour space keeps that colour.

A form XObject starts with the graphics state of whatever draws it, the current colour
space included (ISO 32000-2, 8.10.1), and a soft mask's form starts with the state in
force when the mask was set (11.6.5.2). So a form may write `0.2 0.6 0.4 scn` with no
`cs` of its own. Read on its own, such a form looks as if it painted in DeviceGray, the
space a page starts with. And once its caller's colours go through a palette, the space
it would start with is the palette, where three numbers are two too many. Found in the
figures of an arXiv paper, whose colours came out grey in all three readers.
"""

import io
import subprocess
import sys

import numpy as np
import pikepdf
import pypdfium2 as pdfium
from pikepdf import Array, Dictionary, Name, String

from pdfthemes import apply, merge_builds
from pdfthemes.core import SAVE
from pdfthemes.derive import write_themes

W, H = 100, 60
GREEN = "0.2 0.6 0.4"            # (51, 153, 102): whole bytes, so a palette holds it exactly
COMPONENTS = {"/DeviceGray": 1, "/DeviceRGB": 3, "/DeviceCMYK": 4, "/Indexed": 1, "/Separation": 1, "/CalGray": 1,
              "/CalRGB": 3, "/Lab": 3}
DEVICE = {"g": "/DeviceGray", "rg": "/DeviceRGB", "k": "/DeviceCMYK"}


def form(pdf, content, bbox=(0, 0, W, H), **resources):
    f = pdf.make_stream(content.encode())
    f.Type, f.Subtype, f.BBox = Name.XObject, Name.Form, Array(list(bbox))
    f.Resources = Dictionary(**resources)
    return f


def one_page(pdf, outer):
    """A page that draws the form `outer` and nothing else."""
    page = pdf.add_blank_page(page_size=(W, H))
    page.Resources = Dictionary(XObject=Dictionary(Outer=outer))
    page.Contents = pdf.make_stream(b"/Outer Do")
    return pdf


def nested(background="1 1 1"):
    """Outer sets DeviceRGB and fills the page. Inner paints a green box with no `cs` of its own."""
    pdf = pikepdf.new()
    inner = form(pdf, f"{GREEN} scn 10 10 30 30 re f")
    outer = form(pdf, f"/DeviceRGB cs {background} scn 0 0 {W} {H} re f /Inner Do", XObject=Dictionary(Inner=inner))
    return one_page(pdf, outer)


def saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf, **SAVE)
    return buf.getvalue()


def add(pdf, tmp_path):
    src, out = tmp_path / "plain.pdf", tmp_path / "themed.pdf"
    pdf.save(src)
    subprocess.run([sys.executable, "-m", "pdfthemes", "add", str(src), "-o", str(out)], check=True, capture_output=True)
    return src.read_bytes(), out.read_bytes()


def drawn(data, scale=1, theme=None):
    if theme is not None:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            apply(pdf, theme)
            data = saved(pdf)
    doc = pdfium.PdfDocument(data)
    try:
        return np.asarray(doc[0].render(scale=scale).to_pil().convert("RGB"))
    finally:
        doc.close()


def at(picture, x, y):
    """The colour at a point given in page units, from the bottom left as PDF counts."""
    return picture[H - 1 - y, x].tolist()


def components(space):
    if isinstance(space, pikepdf.Name):
        return COMPONENTS.get(str(space))
    family = str(space[0])
    return int(space[1].N) if family == "/ICCBased" else COMPONENTS.get(family)


def wrong_operands(data):
    """How many colours on the first page are set with the wrong number of operands for the
    colour space in force, following that space into each form and each soft mask's form."""
    def walk(stream, fill):
        res = stream.get("/Resources") or Dictionary()
        spaces, xobjects, states = (res.get(k) or Dictionary() for k in ("/ColorSpace", "/XObject", "/ExtGState"))
        wrong, stack = 0, []
        for operands, operator in pikepdf.parse_content_stream(stream):
            op = str(operator)
            if op == "q":
                stack.append(fill)
            elif op == "Q" and stack:
                fill = stack.pop()
            elif op == "cs":
                fill = spaces.get(operands[0], operands[0])
            elif op in DEVICE:
                fill = Name(DEVICE[op])
            elif op in ("sc", "scn"):
                n = components(fill)
                wrong += n is not None and len([v for v in operands if not isinstance(v, pikepdf.Name)]) != n
            elif op == "Do" and xobjects[operands[0]].get("/Subtype") == Name.Form:
                wrong += walk(xobjects[operands[0]], fill)
            elif op == "gs" and isinstance(states[operands[0]].get("/SMask"), pikepdf.Dictionary):
                wrong += walk(states[operands[0]].SMask.G, fill)
        return wrong

    with pikepdf.open(io.BytesIO(data)) as pdf:
        return walk(pdf.pages[0].obj, Name.DeviceGray)


def test_a_form_that_sets_a_colour_in_its_callers_space_keeps_the_colour(tmp_path):
    plain, themed = add(nested(), tmp_path)
    assert at(drawn(themed), 20, 20) == [51, 153, 102]
    for scale in (1, 2):
        assert np.array_equal(drawn(plain, scale), drawn(themed, scale))
    assert wrong_operands(themed) == 0


def test_the_space_reaches_a_form_through_a_form_that_sets_nothing(tmp_path):
    pdf = pikepdf.new()
    inner = form(pdf, f"{GREEN} scn 0 0 30 30 re f")
    middle = form(pdf, "q 1 0 0 1 10 10 cm /Inner Do Q", XObject=Dictionary(Inner=inner))
    outer = form(pdf, f"/DeviceRGB cs 1 1 1 scn 0 0 {W} {H} re f /Middle Do", XObject=Dictionary(Middle=middle))
    one_page(pdf, outer)
    plain, themed = add(pdf, tmp_path)
    assert at(drawn(themed), 20, 20) == [51, 153, 102]
    for scale in (1, 2):
        assert np.array_equal(drawn(plain, scale), drawn(themed, scale))
    assert wrong_operands(themed) == 0


def test_one_form_drawn_under_two_colour_spaces_keeps_both_colours(tmp_path):
    """`1 scn` is white in DeviceGray and the second entry, blue, in the palette."""
    pdf = pikepdf.new()
    inner = form(pdf, "1 scn 5 5 30 30 re f", bbox=(0, 0, 40, 40))
    palette = Array([Name.Indexed, Name.DeviceRGB, 1, String(bytes([0, 255, 0, 0, 0, 255]))])
    outer = form(pdf, f"/DeviceGray cs 0.4 scn 0 0 {W} {H} re f /Inner Do /Pal cs q 1 0 0 1 50 0 cm /Inner Do Q",
                 ColorSpace=Dictionary(Pal=palette), XObject=Dictionary(Inner=inner))
    one_page(pdf, outer)
    plain, themed = add(pdf, tmp_path)
    assert at(drawn(themed), 20, 20) == [255, 255, 255]
    assert at(drawn(themed), 70, 20) == [0, 0, 255]
    for scale in (1, 2):
        assert np.array_equal(drawn(plain, scale), drawn(themed, scale))
    assert wrong_operands(themed) == 0


def test_a_soft_masks_form_keeps_the_right_number_of_operands(tmp_path):
    """The mask's form paints the left half white, so the red shows there and nowhere else.
    It isn't rewritten, so it has to stop leaning on a caller that now sets a palette."""
    pdf = pikepdf.new()
    mask = form(pdf, f"1 1 1 scn 0 0 {W // 2} {H} re f")
    mask.Group = Dictionary(S=Name.Transparency, CS=Name.DeviceRGB)
    state = Dictionary(Type=Name.ExtGState, SMask=Dictionary(Type=Name.Mask, S=Name.Luminosity, G=mask))
    outer = form(pdf, f"/DeviceRGB cs 1 1 1 scn 0 0 {W} {H} re f 0.8 0.2 0.2 scn /Masked gs 0 0 {W} {H} re f",
                 ExtGState=Dictionary(Masked=state))
    one_page(pdf, outer)
    plain, themed = add(pdf, tmp_path)
    assert wrong_operands(plain) == 0
    assert wrong_operands(themed) == 0
    assert at(drawn(themed), 20, 20) == [204, 51, 51]
    assert at(drawn(themed), 80, 20) == [255, 255, 255]
    for scale in (1, 2):
        assert np.array_equal(drawn(plain, scale), drawn(themed, scale))


def test_a_form_both_builds_share_under_a_colour_that_differs():
    """Merging two builds: the background differs, so it goes through a palette, and the
    form inside is the same in both, so it is kept as it is. It still has to paint green."""
    light, dark = saved(nested("1 1 1")), saved(nested("0.1 0.1 0.1"))
    m = merge_builds([nested("1 1 1"), nested("0.1 0.1 0.1")])

    def info(name):
        return {"/Name": String(name), "/ColorScheme": Name("/Light")}
    write_themes(m.pdf, info("Light"), [(info("Dark"), m.replaces[0])])
    merged = saved(m.pdf)
    assert wrong_operands(merged) == 0
    assert np.array_equal(drawn(merged), drawn(light))
    assert np.array_equal(drawn(merged, theme="Dark"), drawn(dark))
    assert at(drawn(merged, theme="Dark"), 20, 20) == [51, 153, 102]
