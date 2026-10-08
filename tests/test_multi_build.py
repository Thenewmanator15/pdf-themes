"""Merging more than two builds: one build per theme, the first the default.
Each theme, applied, has to draw like the build it came from."""

import io
import pathlib

import numpy as np
import pikepdf
import pytest
from pikepdf import Name, String

from pdfthemes import MergeError, apply, merge_builds
from pdfthemes.core import SAVE
from pdfthemes.derive import write_themes

OUT = pathlib.Path(__file__).resolve().parent / "objects" / "out"
RED, GREEN, BLUE = "1 0 0", "0 1 0", "0 0 1"


def page(content, pages=1):
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(10, 10))
        pdf.pages[-1].obj.Contents = pdf.make_stream(content.encode())
    return pdf


def filled(colour):
    return page(f"{colour} rg 0 0 10 10 re f")


def saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf, **SAVE)
    return buf.getvalue()


def themed(m, names):
    """The merged file with a bare themes dictionary, one theme per build."""
    def info(name):
        return {"/Name": String(name), "/ColorScheme": Name("/Light")}
    write_themes(m.pdf, info(names[0]), [(info(n), pairs) for n, pairs in zip(names[1:], m.replaces)])
    return saved(m.pdf)


def drawn(data, theme=None):
    pdfium = pytest.importorskip("pypdfium2")
    if theme is not None:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            apply(pdf, theme)
            data = saved(pdf)
    doc = pdfium.PdfDocument(data)
    return [np.asarray(doc[n].render(scale=1).to_pil().convert("RGB")).astype(int) for n in range(len(doc))]


def furthest(a, b):
    return max(int(np.abs(x - y).max()) for x, y in zip(a, b))


def test_three_builds_each_draw_like_their_own_build():
    m = merge_builds([filled(RED), filled(BLUE), filled(GREEN)])
    assert len(m.replaces) == 2
    file = themed(m, ["A", "B", "C"])
    assert drawn(file)[0][5, 5].tolist() == [255, 0, 0]
    assert drawn(file, "B")[0][5, 5].tolist() == [0, 0, 255]
    assert drawn(file, "C")[0][5, 5].tolist() == [0, 255, 0]


def test_a_theme_that_agrees_with_the_default_where_an_earlier_one_differs():
    m = merge_builds([filled(RED), filled(BLUE), filled(RED)])
    file = themed(m, ["A", "B", "C"])
    assert drawn(file, "B")[0][5, 5].tolist() == [0, 0, 255]
    assert drawn(file, "C")[0][5, 5].tolist() == [255, 0, 0]


def test_two_uses_that_only_a_later_theme_tells_apart():
    # Both boxes are red by default and blue in B. Only C gives them different colours.
    def boxes(left, right):
        return page(f"{left} rg 0 0 5 10 re f {right} rg 5 0 5 10 re f")
    m = merge_builds([boxes(RED, RED), boxes(BLUE, BLUE), boxes(GREEN, "1 1 0")])
    file = themed(m, ["A", "B", "C"])
    for theme, left, right in ((None, [255, 0, 0], [255, 0, 0]), ("B", [0, 0, 255], [0, 0, 255]),
                               ("C", [0, 255, 0], [255, 255, 0])):
        picture = drawn(file, theme)[0]
        assert picture[5, 2].tolist() == left and picture[5, 7].tolist() == right


def test_a_build_that_leaves_out_a_colour_operator_still_lines_up():
    # Matplotlib leaves out an operator that wouldn't change the colour.
    m = merge_builds([page("1 G 1 g 0 0 10 10 re f"), page("0 g 0 0 10 10 re f"),
                      page("0.5 G 0.5 g 0 0 10 10 re f")])
    file = themed(m, ["A", "B", "C"])
    assert drawn(file)[0][5, 5].tolist() == [255, 255, 255]
    assert drawn(file, "B")[0][5, 5].tolist() == [0, 0, 0]
    assert drawn(file, "C")[0][5, 5][0] in (127, 128)


def test_a_graphics_state_both_builds_set_isnt_taken_for_one_sided():
    # The merged file writes a colour just before the shape it paints, so the
    # next build meets the shared graphics state while it is still at a colour.
    def band(colour):
        return page(f"{colour} rg /G0 gs 0 0 10 10 re f", pages=1)
    builds = [band(RED), band(BLUE), band(BLUE)]
    for b in builds:
        b.pages[0].obj.Resources = pikepdf.Dictionary(ExtGState=pikepdf.Dictionary(G0=pikepdf.Dictionary(ca=0.5)))
    m = merge_builds(builds)
    file = themed(m, ["A", "B", "C"])
    assert drawn(file, "B")[0][5, 5].tolist() == drawn(file, "C")[0][5, 5].tolist() == [128, 128, 255]


def test_a_different_shape_names_the_theme_and_page():
    with pytest.raises(MergeError, match=r"theme 3.*page 1"):
        merge_builds([filled(RED), filled(BLUE), page(f"{GREEN} rg 0 0 5 5 re f")])


def test_builds_with_different_page_counts_name_the_theme():
    with pytest.raises(MergeError, match="theme 2 has 2 pages, the default has 1"):
        merge_builds([filled(RED), page(f"{BLUE} rg 0 0 10 10 re f", pages=2)])


def test_more_than_256_combinations_spill_into_further_palettes():
    def strips(shade):
        return page(" ".join(f"{k / 299:.4f} {shade} {1 - k / 299:.4f} rg {k / 30:.4f} 0 0.04 10 re f"
                             for k in range(300)))
    builds = [strips(0), strips(0.5), strips(1)]
    references = [drawn(saved(strips(0))), drawn(saved(strips(0.5))), drawn(saved(strips(1)))]
    m = merge_builds(builds)
    assert len(m.palette_list) >= 2
    file = themed(m, ["A", "B", "C"])
    for theme, reference in zip((None, "B", "C"), references):
        assert furthest(drawn(file, theme), reference) <= 1


def test_working_themes_out_is_refused_for_more_than_two_builds():
    with pytest.raises(MergeError, match="more than two builds"):
        merge_builds([filled(RED), filled(BLUE), filled(GREEN)], organise=True)


# Real files: the objects test's pairs, with one build used twice. Every kind of
# object a theme can swap has to survive a third build in each position.
PAIRS = ["legacy", "portfolio", "figures/mpl-heat_div", "figures/mpl-lines", "figures/mpl-gouraud",
         "figures/pgf_surface", "objects"]
ORDERS = ["LDD", "LLD", "LDL"]


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("pair", PAIRS)
def test_a_third_build_of_the_objects_test_draws_like_its_own(pair, order):
    if pair == "objects" and order != "LDD":
        pytest.skip("the 31-page pair runs once; the smaller pairs cover the other orders")
    paths = {"L": OUT / f"{pair}-light.pdf", "D": OUT / f"{pair}-dark.pdf"}
    m = merge_builds([pikepdf.open(paths[c]) for c in order])
    file = themed(m, ["A", "B", "C"])
    allowed = 4 if pair == "objects" else 0  # 8-bit palettes over calibrated spaces, as in test_objects.py
    for theme, c in zip((None, "B", "C"), order):
        assert furthest(drawn(file, theme), drawn(paths[c].read_bytes())) <= allowed, f"theme {theme or 'A'}"


# Objects a theme swaps whole.

def with_resources(pdf, **resources):
    pdf.pages[0].obj.Resources = pikepdf.Dictionary(**resources)
    return pdf


def gradient(start, end):
    pdf = page("/Sh0 sh")
    fn = pikepdf.Dictionary(FunctionType=2, Domain=[0, 1], N=1, C0=start, C1=end)
    return with_resources(pdf, Shading=pikepdf.Dictionary(Sh0=pdf.make_indirect(pikepdf.Dictionary(
        ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=[0, 0, 10, 0], Function=fn, Extend=[True, True]))))


def test_a_gradient_is_swapped_only_in_the_theme_that_changes_it():
    m = merge_builds([gradient([1, 0, 0], [1, 0, 0]), gradient([1, 0, 0], [1, 0, 0]), gradient([0, 0, 1], [0, 0, 1])])
    assert [len(r) for r in m.replaces] == [0, 1]
    file = themed(m, ["A", "B", "C"])
    assert drawn(file, "B")[0][5, 5].tolist() == [255, 0, 0]
    assert drawn(file, "C")[0][5, 5].tolist() == [0, 0, 255]


def test_a_gradient_that_differs_in_every_theme_keeps_each_version():
    m = merge_builds([gradient([1, 0, 0], [1, 0, 0]), gradient([0, 1, 0], [0, 1, 0]), gradient([0, 0, 1], [0, 0, 1])])
    file = themed(m, ["A", "B", "C"])
    assert [drawn(file, t)[0][5, 5].tolist() for t in (None, "B", "C")] == [[255, 0, 0], [0, 255, 0], [0, 0, 255]]


def test_opacity_follows_each_theme():
    def faded(ca):
        return with_resources(page("0 0 0 rg /G0 gs 0 0 10 10 re f"),
                              ExtGState=pikepdf.Dictionary(G0=pikepdf.Dictionary(ca=ca)))
    m = merge_builds([faded(1), faded(0.5), faded(0)])
    file = themed(m, ["A", "B", "C"])
    assert [int(drawn(file, t)[0][5, 5][0]) for t in (None, "B", "C")] == [0, 128, 255]


def test_an_annotation_colour_follows_each_theme():
    def noted(colour):
        pdf = page("")
        pdf.pages[0].obj.Annots = pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(
            Type=Name.Annot, Subtype=Name.Square, Rect=[1, 1, 9, 9], C=colour, IC=colour))])
        return pdf
    m = merge_builds([noted([1, 0, 0]), noted([0, 0, 1]), noted([0, 1, 0])])
    file = themed(m, ["A", "B", "C"])
    with pikepdf.open(io.BytesIO(file)) as pdf:
        apply(pdf, "C")
        assert [float(v) for v in pdf.pages[0].Annots[0].IC] == [0, 1, 0]
    with pikepdf.open(io.BytesIO(file)) as pdf:
        apply(pdf, "B")
        assert [float(v) for v in pdf.pages[0].Annots[0].IC] == [0, 0, 1]


def photo(pixels):
    pdf = page("q 10 0 0 10 0 0 cm /Im0 Do Q")
    image = pdf.make_stream(bytes(pixels), Type=Name.XObject, Subtype=Name.Image, Width=2, Height=2,
                            BitsPerComponent=8, ColorSpace=Name.DeviceGray)
    return with_resources(pdf, XObject=pikepdf.Dictionary(Im0=image))


def test_an_image_that_differs_in_one_theme_is_swapped_in_that_theme_only():
    m = merge_builds([photo([0, 60, 120, 180]), photo([0, 60, 120, 180]), photo([255, 200, 140, 80])])
    assert [len(r) for r in m.replaces] == [0, 1]


def test_an_image_follows_every_theme():
    builds = [photo([0, 60, 120, 180]), photo([10, 70, 130, 190]), photo([255, 200, 140, 80])]
    references = [drawn(saved(photo(p))) for p in ([0, 60, 120, 180], [10, 70, 130, 190], [255, 200, 140, 80])]
    file = themed(merge_builds(builds), ["A", "B", "C"])
    for theme, reference in zip((None, "B", "C"), references):
        assert furthest(drawn(file, theme), reference) == 0


def test_an_inline_image_follows_a_named_palette_in_every_theme():
    def inline(colour):
        pdf = page("q 10 0 0 10 0 0 cm BI /W 1 /H 1 /BPC 8 /CS /CSIdx ID \x00 EI Q")
        return with_resources(pdf, ColorSpace=pikepdf.Dictionary(
            CSIdx=pikepdf.Array([Name.Indexed, Name.DeviceRGB, 0, String(colour)])))
    m = merge_builds([inline(b"\xff\x00\x00"), inline(b"\x00\x00\xff"), inline(b"\x00\xff\x00")])
    file = themed(m, ["A", "B", "C"])
    assert [drawn(file, t)[0][5, 5].tolist() for t in (None, "B", "C")] == [[255, 0, 0], [0, 0, 255], [0, 255, 0]]
