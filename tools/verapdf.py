"""Run veraPDF over a themed PDF: as it is stored, and with each of its themes
shown the way a reader would show it.

A validator only checks what the pages reach, and nothing reaches an
alternate theme's objects until the theme is shown. So each theme is also
validated as a file of its own, with its objects swapped in.

The flavours come from what the file's XMP says it is (its PDF/A part and
conformance, its PDF/UA part), or give them with -f.

Needs veraPDF (https://verapdf.org) and Java. Have `verapdf` on the path, or
set VERAPDF to the command that runs it, for example

    VERAPDF="java -cp greenfield-apps-1.28.2.jar org.verapdf.apps.GreenfieldCliWrapper"

Usage: python tools/verapdf.py themed.pdf [-f 2a -f ua1]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import pikepdf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pdfthemes import apply, themes  # noqa: E402
from pdfthemes.core import SAVE  # noqa: E402


def command():
    """The command that runs veraPDF here, or None."""
    given = os.environ.get("VERAPDF")
    if given:
        return shlex.split(given)
    found = shutil.which("verapdf")
    return [found] if found else None


def claimed(pdf):
    """veraPDF's flavours for what the file's XMP says it conforms to."""
    meta = pdf.Root.get("/Metadata")
    data = meta.read_bytes() if meta is not None else b""

    def value(key):
        m = re.search(rb"<" + key + rb">([^<]+)<|" + key + rb"=\"([^\"]+)\"", data)
        return (m.group(1) or m.group(2)).decode().strip() if m else None

    found = []
    part = value(b"pdfaid:part")
    if part:
        found.append(part + (value(b"pdfaid:conformance") or "").lower())
    if value(b"pdfuaid:part"):
        found.append("ua" + value(b"pdfuaid:part"))
    return found


def shown(data):
    """The file as stored, then with each alternate theme applied."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        names = themes(pdf)
    yield "as stored", data
    for name in names[1:]:
        with pikepdf.open(io.BytesIO(data)) as pdf:
            apply(pdf, name)
            out = io.BytesIO()
            pdf.save(out, **SAVE)
        yield name, out.getvalue()


def validate(data, flavours=None):
    """One row for each flavour and each way of showing the file: the theme,
    the profile, whether it passed and the rules that failed."""
    program = command()
    if program is None:
        raise RuntimeError("veraPDF isn't on the path and VERAPDF isn't set")
    with pikepdf.open(io.BytesIO(data)) as pdf:
        flavours = flavours or claimed(pdf)
    if not flavours:
        raise RuntimeError("the file doesn't say which standard it follows; give a flavour")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        files = {}
        for n, (name, content) in enumerate(shown(data)):
            path = pathlib.Path(tmp) / f"{n}.pdf"
            path.write_bytes(content)
            files[path.name] = name
        for flavour in flavours:
            r = subprocess.run([*program, "--format", "json", "-f", flavour, *(str(pathlib.Path(tmp) / f) for f in files)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            start = r.stdout.find("{")
            if start < 0:
                raise RuntimeError(f"veraPDF gave no report: {(r.stdout + r.stderr).strip()[:400]}")
            for job in json.loads(r.stdout[start:])["report"]["jobs"]:
                name = files[pathlib.Path(job["itemDetails"]["name"]).name]
                results = job.get("validationResult") or []
                if not results:
                    rows.append({"theme": name, "profile": flavour, "passed": False, "rules": 0,
                                 "failed": ["could not be validated"]})
                for v in results:
                    details = v["details"]
                    rows.append({"theme": name, "profile": v["profileName"].split(" validation")[0],
                                 "passed": bool(v["compliant"]), "rules": details["passedRules"],
                                 "failed": sorted({f'{s["clause"]}-{s["testNumber"]}'
                                                   for s in details.get("ruleSummaries", [])
                                                   if s.get("ruleStatus") == "FAILED"})})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("themed", type=pathlib.Path)
    p.add_argument("-f", "--flavour", action="append", help="a veraPDF flavour such as 2b, 2a, 4 or ua1")
    args = p.parse_args(argv)
    try:
        rows = validate(args.themed.read_bytes(), args.flavour)
    except RuntimeError as e:
        print(f"verapdf: {e}", file=sys.stderr)
        return 2
    for row in rows:
        print(f"{row['profile']:<10} {row['theme']:<22} "
              + (f"passes, {row['rules']} rules" if row["passed"] else "FAILS: " + ", ".join(row["failed"])))
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
