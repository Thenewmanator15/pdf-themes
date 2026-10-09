"""Non-text contrast: the lines and shapes on a page, each measured against
the colour drawn beside it (WCAG 2.2, 1.4.11 Non-text Contrast, 3:1). It is
a report for the author, because a tool can't tell a plot line from a faint
grid that is meant to be faint."""

import io

import pikepdf
import pytest
from pikepdf import Name

from pdfthemes import merge_builds
from pdfthemes.cli import main
from pdfthemes.contrast import check_shapes, shapes_summary
from pdfthemes.derive import add_themes
from pdfthemes.theme import standard

pytest.importorskip("pypdfium2")

LINE = "{c} RG 2 w 20 50 m 180 50 l S"


def page(content, resources=None):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 100))
    pdf.pages[0].obj.Resources = resources if resources is not None else pikepdf.Dictionary()
    pdf.pages[0].obj.Contents = pdf.make_stream(content.encode())
    return pdf


def saved(pdf):
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def shapes(content, paper=(1.0, 1.0, 1.0), resources=None):
    return check_shapes(saved(page(content, resources)), paper=paper)


def test_a_dark_line_on_white_paper_has_plenty_of_contrast():
    [line] = shapes(LINE.format(c="0 0 0"))
    assert (line["page"], line["kind"], line["colour"], line["against"]) == (1, "line", "#000000", "#FFFFFF")
    assert line["ratio"] == 21.0 and line["needs"] == 3.0
    assert shapes_summary([line]) == {"colours": 1, "low": [], "lowest": line}


def test_a_pale_line_on_white_paper_is_listed_as_low():
    [line] = results = shapes(LINE.format(c="0.85 0.85 0.85"))
    assert line["colour"] == "#D9D9D9" and 1.3 < line["ratio"] < 1.5
    assert shapes_summary(results)["low"] == [line]


def test_a_line_is_measured_against_the_paper_it_is_shown_on():
    [line] = shapes(LINE.format(c="0.85 0.85 0.85"), paper=(0.1, 0.1, 0.1))
    assert line["against"] == "#1A1A1A" and line["ratio"] > 10


def test_a_thin_line_is_still_measured():
    [line] = shapes("0 0 0 RG 0.4 w 20 50.3 m 180 50.3 l S")
    assert line["colour"] == "#000000" and line["ratio"] == 21.0


def test_a_bar_is_measured_against_the_panel_behind_it_not_the_paper():
    results = shapes("0 0 0.4 rg 10 10 180 80 re f 0 0 0.6 rg 60 30 40 40 re f")
    bar = next(r for r in results if r["colour"] == "#000099")
    assert bar["kind"] == "fill" and bar["against"] == "#000066" and bar["ratio"] < 3
    panel = next(r for r in results if r["colour"] == "#000066")
    assert panel["against"] == "#FFFFFF" and panel["ratio"] > 3


def test_a_fill_that_covers_the_whole_page_has_nothing_beside_it():
    assert shapes("0.9 0.9 0.9 rg 0 0 200 100 re f") == []


def test_a_shape_the_same_colour_as_what_is_round_it_is_not_a_shape():
    assert shapes("1 1 1 rg 40 20 100 50 re f") == []


def test_a_shape_that_is_painted_over_is_not_measured():
    results = shapes("0.9 0.9 0.9 rg 50 30 20 20 re f 0 0 0 rg 40 20 100 50 re f")
    assert [r["colour"] for r in results] == ["#000000"]


def test_a_filled_and_outlined_shape_gives_a_fill_and_a_line():
    results = shapes("0.6 0.8 1 rg 0 0 0.5 RG 3 w 40 20 100 50 re B")
    kinds = {r["kind"]: r for r in results}
    assert kinds["line"]["colour"] == "#000080" and kinds["line"]["against"] in ("#FFFFFF", "#99CCFF")
    assert kinds["fill"]["colour"] == "#99CCFF" and kinds["fill"]["against"] == "#000080"


def test_text_is_not_a_shape():
    fonts = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)))
    assert shapes("0.8 0.8 0.8 rg BT /F1 24 Tf 20 40 Td (Hello) Tj ET", resources=fonts) == []


def test_a_line_inside_a_form_is_found_where_the_form_draws_it():
    pdf = page("q 1 0 0 1 100 0 cm /Fm0 Do Q")
    form = pdf.make_stream(b"0.85 0.85 0.85 RG 2 w 10 20 m 10 80 l S")
    form.Type, form.Subtype, form.BBox = Name.XObject, Name.Form, [0, 0, 100, 100]
    pdf.pages[0].obj.Resources = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm0=form))
    [line] = check_shapes(saved(pdf))
    assert line["colour"] == "#D9D9D9" and line["ratio"] < 3


def test_shapes_of_one_colour_on_one_background_are_counted_together():
    content = " ".join(f"0 0 0 RG 1 w 20 {y} m 180 {y} l S" for y in (20, 40, 60, 80))
    [lines] = shapes(content)
    assert lines["count"] == 4


def test_the_check_command_lists_low_lines_without_failing_for_them(tmp_path, capsys):
    path = tmp_path / "pale.pdf"
    page(LINE.format(c="0.85 0.85 0.85")).save(path)
    assert main(["check", str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 colour of lines and shapes measured" in out
    assert "page 1: line #D9D9D9 against #FFFFFF is 1.4:1" in out


def build(ink, paper, line):
    fonts = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)))
    return page(f"{paper} rg 0 0 200 100 re f {ink} rg BT /F1 10 Tf 20 70 Td (Hello world) Tj ET "
                + LINE.format(c=line), fonts)


def test_each_theme_reports_its_lines_and_stays_checked_on_its_text():
    m = merge_builds([build("0 0 0", "1 1 1", "0 0 0.6"), build("1 1 1", "0 0 0", "0 0 0.6")])
    light, dark = add_themes(m, [standard("Light"), standard("Dark")])
    assert light["passed"] and light["shapes"]["low"] == []
    assert dark["passed"], "a low line doesn't take the text's mark away"
    [low] = dark["shapes"]["low"]
    assert (low["kind"], low["colour"], low["against"]) == ("line", "#000099", "#000000") and low["ratio"] < 3
