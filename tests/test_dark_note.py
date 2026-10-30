"""The report says when a themed file has no dark theme. SPEC.md section 7:
a themed file should carry Dark and Dark, more contrast, because a reader
who needs light text on dark otherwise has to invert the page."""

from pdfthemes.cli import print_reports


def report(name, kept=True, scheme=None, contrast=None):
    r = {"name": name, "kind": "derived", "kept": kept, "passed": kept, "reason": None if kept else "failed",
         "runs": 1, "unmeasured": 0, "lowest": 7.0, "lowest_text": "a", "failures": []}
    if scheme:
        r["scheme"], r["contrast"] = scheme, contrast
    return r


def test_no_note_when_both_dark_themes_are_kept(capsys):
    print_reports([report("Light"), report("Dark"), report("Dark, more contrast")])
    assert "note:" not in capsys.readouterr().out


def test_names_the_dark_themes_a_file_lacks(capsys):
    print_reports([report("Light"), report("Dark", kept=False), report("Cream")])
    out = capsys.readouterr().out
    assert "no Dark or Dark, more contrast theme" in out


def test_names_only_the_one_missing(capsys):
    print_reports([report("Light"), report("Dark"), report("Dark, more contrast", kept=False)])
    out = capsys.readouterr().out
    assert "no Dark, more contrast theme" in out
    assert "no Dark or" not in out


def test_an_authored_theme_counts_by_its_labels_not_its_name(capsys):
    print_reports([report("Day", scheme="Light"), report("Night", scheme="Dark"),
                   report("Night, high", scheme="Dark", contrast="More")])
    assert "note:" not in capsys.readouterr().out
