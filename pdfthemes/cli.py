"""pdf-themes: make and inspect PDFs that carry colour themes.

  pdf-themes typst document.typ -o themed.pdf         compile with --input mode=light and mode=dark, then merge
  pdf-themes merge light.pdf dark.pdf -o themed.pdf   two builds: Light, Dark and the standard themes
  pdf-themes add document.pdf -o themed.pdf           one build: Light and the standard themes, Dark included
  pdf-themes apply themed.pdf --theme Dark -o out.pdf a theme as a plain PDF, for readers without themes
  pdf-themes info themed.pdf                          the themes in a file and what each one swaps
  pdf-themes check document.pdf                       the text contrast of a plain PDF

The standard themes are Dark (worked out from the light build when there is
no dark one), Light and Dark with more contrast, and Cream, Peach, Yellow and
Turquoise tints. Each is checked for text contrast by drawing it, and a
theme that fails is left out, so every theme in the file has passed. A theme
that would draw every page exactly like the default (a scan, say) is left
out too.
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pikepdf

from . import core
from .contrast import check, summary
from .derive import add_themes
from .merge import merge

SAVE = core.SAVE


def hex_colour(text: str) -> tuple[float, float, float]:
    text = text.lstrip("#")
    if len(text) != 6:
        raise argparse.ArgumentTypeError(f"{text!r} is not a colour like 1C1C1E")
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


def print_reports(reports):
    for r in reports:
        if r["kept"] and r["passed"]:
            state = "kept, checked"
        elif r["kept"] and r["failures"]:
            state = "kept, NOT checked: some text is below the minimum"
        elif r["kept"]:
            state = "kept, not checked: no text to measure"
        elif r["reason"] == "unchanged":
            state = "left out: draws exactly like Light"
        else:
            state = "left out: some text is below the minimum"
        lowest = f", lowest {r['lowest']}:1 ({r['lowest_text']!r})" if r["lowest"] is not None else ""
        print(f"  {r['name']:<22} {state}{lowest}")
        if not r["passed"]:
            for f in r["failures"]:
                print(f"      page {f['page']}: {f['text']!r} {f['colour']} on {f['background']} "
                      f"is {f['ratio']}:1, needs {f['needs']}:1")


def write(m, args, reports):
    m.pdf.save(args.output, **SAVE)
    size = pathlib.Path(args.output).stat().st_size
    scans = m.stats["grey scans given a palette"]
    print(f"Wrote {args.output} ({size:,} bytes): {len(m.palette_list)} palette(s), "
          f"{sum(len(p.entries) for p in m.palette_list)} colours"
          + (f", {scans} grey scan{'s' if scans > 1 else ''} themed through a palette of greys." if scans else "."))
    print_reports(reports)
    for note in m.notes:
        print(f"  note: {note}")


def cmd_merge(args) -> int:
    try:
        m = merge(args.light, args.dark, organise=not args.only_dark)
    except core.MergeError as e:
        print(f"Can't merge: {e}", file=sys.stderr)
        return 1
    reports = add_themes(m, args.light_paper, args.dark_paper, derived=not args.only_dark)
    write(m, args, reports)
    return 0


class TypstFailed(Exception):
    pass


def key_value(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"{text!r} is not an input like key=value")
    return key, value


def compile_typst(document, out, root, inputs, font_paths, ignore_system_fonts, standards, program):
    """One build: with the typst program when there is one, otherwise with
    the typst Python package."""
    if program:
        cmd = [program, "compile", str(document), str(out), "--root", str(root)]
        for key, value in inputs.items():
            cmd += ["--input", f"{key}={value}"]
        for path in font_paths:
            cmd += ["--font-path", str(path)]
        if ignore_system_fonts:
            cmd.append("--ignore-system-fonts")
        if standards:
            cmd += ["--pdf-standard", ",".join(standards)]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            raise TypstFailed(str(e)) from None
        if done.returncode != 0:
            raise TypstFailed(done.stderr.strip() or f"{program} stopped with exit code {done.returncode}")
        return
    try:
        import typst
    except ImportError:
        raise TypstFailed("Typst isn't installed: put the typst program on your path, or pip install typst") from None
    options = dict(root=str(root), ignore_system_fonts=ignore_system_fonts, sys_inputs=dict(inputs))
    if font_paths:
        options["font_paths"] = [str(p) for p in font_paths]
    if standards:
        options["pdf_standards"] = list(standards)
    try:
        data = typst.compile(str(document), **options)
    except typst.TypstError as e:
        raise TypstFailed(str(e)) from None
    pathlib.Path(out).write_bytes(data)


def cmd_typst(args) -> int:
    program = args.typst if args.typst is not None else shutil.which("typst")
    root = args.root or args.document.parent
    standards = [s for value in args.pdf_standard for s in value.split(",") if s]
    with tempfile.TemporaryDirectory() as tmp:
        builds = {}
        for mode, value in (("light", args.light), ("dark", args.dark)):
            builds[mode] = pathlib.Path(tmp) / f"{mode}.pdf"
            inputs = {**dict(args.input), args.input_name: value}
            try:
                compile_typst(args.document, builds[mode], root, inputs, args.font_path, args.ignore_system_fonts,
                              standards, program)
            except TypstFailed as e:
                print(f"Typst couldn't compile {args.document} with {args.input_name}={value}:\n{e}", file=sys.stderr)
                return 1
        # Read the builds into memory: an open file can't be deleted on Windows,
        # and the merged Pdf outlives the temporary directory.
        opened = {mode: pikepdf.open(io.BytesIO(path.read_bytes())) for mode, path in builds.items()}
        try:
            m = merge(opened["light"], opened["dark"], organise=not args.only_dark)
        except core.MergeError as e:
            print(f"Can't merge the two builds: {e}", file=sys.stderr)
            return 1
        reports = add_themes(m, args.light_paper, args.dark_paper, derived=not args.only_dark)
        write(m, args, reports)
    return 0


def cmd_add(args) -> int:
    try:
        m = merge(args.document)
    except core.MergeError as e:
        print(f"Can't organise this file: {e}", file=sys.stderr)
        return 1
    reports = add_themes(m, args.light_paper, args.dark_paper)
    write(m, args, reports)
    return 0


def cmd_apply(args) -> int:
    with pikepdf.open(args.themed) as pdf:
        try:
            paper = core.apply(pdf, args.theme)
        except KeyError:
            print(f"No theme called {args.theme!r}. This file has: {', '.join(core.themes(pdf)) or 'none'}",
                  file=sys.stderr)
            return 1
        if not args.no_paper:
            core.paint_paper(pdf, paper)
        pdf.save(args.output, **SAVE)
    print(f"Wrote {args.output}: the {args.theme} theme as a plain PDF that any reader shows.")
    return 0


def cmd_info(args) -> int:
    with pikepdf.open(args.themed) as pdf:
        d = core.describe(pdf)
    if d is None:
        print("This file has no themes.")
        return 1
    if args.json:
        print(json.dumps(d, indent=2))
        return 0
    for t in d["themes"]:
        labels = [t["color_scheme"] or "no colour scheme"]
        if t["contrast"]:
            labels.append(f"{t['contrast']} contrast")
        if t["tint"]:
            labels.append(f"{t['tint']} tint")
        paper = "#" + "".join(f"{round(v * 255):02X}" for v in t["paper"])
        checked = t["checked"]
        line = f"{t['name']} ({'default' if t['default'] else 'alternate'}; {', '.join(labels)}), paper {paper}"
        if checked:
            line += f", checked: {checked.get('Standard')} {checked.get('Criterion')} {checked.get('Level')}"
        print(line)
        kinds = {}
        for r in t.get("replace", []):
            kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        if kinds:
            print("  swaps " + ", ".join(f"{n} {k}{'s' if n > 1 else ''}" for k, n in sorted(kinds.items())))
        if args.colours:
            for r in t.get("replace", []):
                if r["kind"] == "palette":
                    print(f"  palette {r['base']}: " + " ".join(
                        f"{a}->{b}" for a, b in zip(r["default_colours"], r["theme_colours"])))
    return 0


def cmd_check(args) -> int:
    results = check(str(args.document), paper=args.paper, enhanced=args.enhanced)
    s = summary(results)
    lowest = s["lowest"]
    print(f"{s['runs']} runs of text measured ({s['unmeasured']} not measurable: gradient or self-coloured)"
          + (f", lowest {lowest['ratio']}:1 ({lowest['text']!r})" if lowest else ""))
    for f in s["failures"]:
        print(f"  page {f['page']}: {f['text']!r} {f['colour']} on {f['background']} "
              f"is {f['ratio']}:1, needs {f['needs']}:1")
    return 1 if s["failures"] else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pdf-themes", description="Colour themes in PDF (proof of concept).")
    sub = p.add_subparsers(dest="command", required=True)

    def papers(parser):
        parser.add_argument("--light-paper", type=hex_colour, default=hex_colour("FFFFFF"), metavar="RRGGBB",
                            help="the paper colour of the light design (default FFFFFF)")
        parser.add_argument("--dark-paper", type=hex_colour, default=hex_colour("000000"), metavar="RRGGBB",
                            help="the paper colour for dark themes (default 000000)")

    t = sub.add_parser("typst", help="compile a Typst document in light and dark modes and merge the two builds")
    t.add_argument("document", type=pathlib.Path)
    t.add_argument("-o", "--output", type=pathlib.Path, required=True)
    t.add_argument("--input-name", default="mode", metavar="KEY",
                   help="the sys.inputs key the document reads to pick its mode (default mode)")
    t.add_argument("--light", default="light", metavar="VALUE", help="its value for the light build (default light)")
    t.add_argument("--dark", default="dark", metavar="VALUE", help="its value for the dark build (default dark)")
    t.add_argument("--input", type=key_value, action="append", default=[], metavar="KEY=VALUE",
                   help="another input for both builds; give it again for more")
    t.add_argument("--root", type=pathlib.Path, help="the project root (default: the document's folder)")
    t.add_argument("--font-path", type=pathlib.Path, action="append", default=[], metavar="DIR")
    t.add_argument("--ignore-system-fonts", action="store_true")
    t.add_argument("--pdf-standard", action="append", default=[], metavar="STANDARD",
                   help="for example 2.0, a-2b or ua-1; give it again, or separate with commas, for more")
    t.add_argument("--typst", metavar="PROGRAM",
                   help="the typst program to run (default: typst on the path, otherwise the typst Python package)")
    papers(t)
    t.add_argument("--only-dark", action="store_true",
                   help="add the dark build's theme only, not the standard themes")
    t.set_defaults(func=cmd_typst)

    m = sub.add_parser("merge", help="merge a light and a dark build of one document into one themed PDF")
    m.add_argument("light", type=pathlib.Path)
    m.add_argument("dark", type=pathlib.Path)
    m.add_argument("-o", "--output", type=pathlib.Path, required=True)
    papers(m)
    m.add_argument("--only-dark", action="store_true",
                   help="add the dark build's theme only, not the standard themes")
    m.set_defaults(func=cmd_merge)

    a = sub.add_parser("add", help="add the standard themes, a dark one included, to a single PDF")
    a.add_argument("document", type=pathlib.Path)
    a.add_argument("-o", "--output", type=pathlib.Path, required=True)
    papers(a)
    a.set_defaults(func=cmd_add)

    ap = sub.add_parser("apply", help="show a theme the way a reader would, saved as a plain PDF")
    ap.add_argument("themed", type=pathlib.Path)
    ap.add_argument("--theme", default="Dark")
    ap.add_argument("-o", "--output", type=pathlib.Path, required=True)
    ap.add_argument("--no-paper", action="store_true", help="don't paint the theme's paper colour into the pages")
    ap.set_defaults(func=cmd_apply)

    i = sub.add_parser("info", help="list the themes in a themed PDF and what each one swaps")
    i.add_argument("themed", type=pathlib.Path)
    i.add_argument("--colours", action="store_true", help="list every palette colour")
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_info)

    c = sub.add_parser("check", help="check the text contrast of a PDF as it is drawn")
    c.add_argument("document", type=pathlib.Path)
    c.add_argument("--paper", type=hex_colour, default=hex_colour("FFFFFF"), metavar="RRGGBB")
    c.add_argument("--enhanced", action="store_true", help="hold text to 7:1 (WCAG 1.4.6) rather than 4.5:1")
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)
