"""Themes the author made: each is written with its labels, drawn and
checked, and never altered."""

import pikepdf
import pytest
from pikepdf import Name

from pdfthemes import THEMES_KEY, describe, merge_builds, themes
from pdfthemes.derive import add_themes
from pdfthemes.themes import STANDARD, Theme, standard

BLACK, WHITE = "0 0 0", "1 1 1"


def text_build(ink, paper):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 100))
    page = pdf.pages[0]
    page.obj.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
        Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica)))
    page.obj.Contents = pdf.make_stream(
        f"{paper} rg 0 0 200 100 re f {ink} rg BT /F1 10 Tf 20 40 Td (Hello world) Tj ET".encode())
    return pdf


def theme_dict(pdf, name):
    t = pdf.Root[THEMES_KEY]
    return next(d for d in [t.Default, *t.Alternates] if str(d.Name) == name)


def palette_bytes(m):
    return [bytes(obj[3]) for obj in m.pdf.objects
            if isinstance(obj, pikepdf.Array) and len(obj) == 4 and obj[0] == Name.Indexed]


def test_the_standard_set_is_the_eight_names():
    assert list(STANDARD) == ["Light", "Dark", "Light, more contrast", "Dark, more contrast",
                              "Cream", "Peach", "Yellow", "Turquoise"]
    assert standard("Dark").scheme == "Dark" and standard("Dark").paper == (0.0, 0.0, 0.0)
    assert standard("Dark, more contrast").contrast == "More"
    assert standard("Cream").tint == "Cream" and standard("Cream").scheme == "Light"
    assert standard("Dark", paper=(0.1, 0.1, 0.1)).paper == (0.1, 0.1, 0.1)
    with pytest.raises(KeyError):
        standard("Night")


def test_each_authored_theme_is_written_with_its_labels():
    m = merge_builds([text_build(BLACK, WHITE), text_build(WHITE, BLACK), text_build(BLACK, "0.99 0.95 0.86")])
    reports = add_themes(m, [standard("Light"), standard("Dark"), standard("Cream")])
    d = describe(m.pdf)
    assert [t["name"] for t in d["themes"]] == ["Light", "Dark", "Cream"]
    assert d["themes"][1]["color_scheme"] == "Dark" and d["themes"][2]["tint"] == "Cream"
    assert [r["kind"] for r in reports] == ["default", "author", "author"]
    assert all(r["kept"] and r["passed"] for r in reports)
    assert all("/Checked" in theme_dict(m.pdf, name) for name in ("Light", "Dark", "Cream"))


def test_a_theme_that_fails_is_kept_unmarked_and_its_colours_untouched():
    m = merge_builds([text_build(BLACK, WHITE), text_build("0.8 0.8 0.8", WHITE)])   # about 1.6:1
    before = palette_bytes(m)
    reports = add_themes(m, [standard("Light"), Theme("Faint", "Light")])
    assert reports[1]["kept"] and not reports[1]["passed"] and reports[1]["failures"]
    assert "/Checked" not in theme_dict(m.pdf, "Faint")
    assert palette_bytes(m) == before


def test_a_theme_that_draws_like_the_default_is_kept_with_nothing_to_swap():
    m = merge_builds([text_build(BLACK, WHITE), text_build(BLACK, WHITE)])
    add_themes(m, [standard("Light"), standard("Cream", paper=(1.0, 1.0, 1.0))])
    assert themes(m.pdf) == ["Light", "Cream"]
    assert len(theme_dict(m.pdf, "Cream").Replace) == 0


def test_an_enhanced_contrast_theme_is_held_to_seven_to_one():
    m = merge_builds([text_build(BLACK, WHITE), text_build("0.4 0.4 0.4", WHITE)])   # about 5.7:1
    reports = add_themes(m, [standard("Light"), standard("Light, more contrast")])
    assert reports[1]["kept"] and not reports[1]["passed"]
    assert "/Checked" not in theme_dict(m.pdf, "Light, more contrast")


def test_a_passing_enhanced_theme_is_marked_at_level_aaa():
    m = merge_builds([text_build("0.4 0.4 0.4", WHITE), text_build(BLACK, WHITE)])
    add_themes(m, [standard("Light"), standard("Light, more contrast")])
    checked = theme_dict(m.pdf, "Light, more contrast").Checked
    assert str(checked.Criterion) == "1.4.6 Contrast (Enhanced)" and checked.Level == Name.AAA


def test_no_themes_are_worked_out_unless_asked_for():
    m = merge_builds([text_build(BLACK, WHITE), text_build(WHITE, BLACK)])
    add_themes(m, [standard("Light"), standard("Dark")])
    assert themes(m.pdf) == ["Light", "Dark"]


def test_the_themes_must_match_the_builds():
    m = merge_builds([text_build(BLACK, WHITE), text_build(WHITE, BLACK)])
    with pytest.raises(ValueError, match="3 themes for 2 builds"):
        add_themes(m, [standard("Light"), standard("Dark"), standard("Cream")])
    with pytest.raises(ValueError, match="two themes are called Light"):
        add_themes(m, [standard("Light"), standard("Light")])
