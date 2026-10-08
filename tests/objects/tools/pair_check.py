"""Check that a light and dark build draw the same objects and differ only in paint.

    python3 tools/pair_check.py out/objects-light.pdf out/objects-dark.pdf

Compares, page by page, the operator sequence of every content stream (pages, forms,
patterns, Type 3 glyphs, appearance streams) and the dictionary keys of every annotation.
Colour-setting operators are left out of the comparison altogether: producers such as
matplotlib skip a colour operator when the colour is already current, so two builds of the
same figure can differ in which colour operators they contain (one writes "1 G 1 g", the
other just "0 g") while painting exactly the same shapes.
"""
import sys

import pikepdf
from pikepdf import Dictionary, Stream

COLOUR_OPS = {"g", "G", "rg", "RG", "k", "K", "sc", "SC", "scn", "SCN", "cs", "CS"}


def streams(page):
    out = []
    seen = set()

    def walk_res(res, tag):
        if res is None:
            return
        for cat in ("XObject", "Pattern", "Font"):
            d = res.get("/" + cat)
            if d is None:
                continue
            for name, obj in sorted(d.items()):
                key = obj.objgen if obj.is_indirect else None
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                if cat == "XObject" and obj.get("/Subtype") == pikepdf.Name.Form:
                    out.append((tag + name, obj))
                    walk_res(obj.get("/Resources"), tag + name + "/")
                elif cat == "Pattern" and isinstance(obj, Stream):
                    out.append((tag + name, obj))
                    walk_res(obj.get("/Resources"), tag + name + "/")
                elif cat == "Font" and obj.get("/Subtype") == pikepdf.Name.Type3:
                    for g, cp in sorted(obj.CharProcs.items()):
                        out.append((tag + name + g, cp))

    contents = page.obj.Contents
    out.append(("page", contents if isinstance(contents, Stream) else None))
    walk_res(page.obj.get("/Resources"), "")
    for i, a in enumerate(page.obj.get("/Annots", [])):
        ap = a.get("/AP")
        if ap is None:
            continue
        for sk, v in sorted(ap.items()):
            for st, s in ([("", v)] if isinstance(v, Stream) else sorted(v.items()) if isinstance(v, Dictionary) else []):
                out.append(("annot%d%s%s" % (i, sk, st), s))
                walk_res(s.get("/Resources"), "annot%d%s%s/" % (i, sk, st))
    return out


def ops(stream):
    if stream is None:
        return []
    res = []
    for item in pikepdf.parse_content_stream(stream):
        if isinstance(item, pikepdf.ContentStreamInlineImage):
            res.append(("INLINE", None))
            continue
        op = str(item.operator)
        if op in COLOUR_OPS:
            continue
        res.append((op, [str(o) for o in item.operands]))
    return res


def main(a, b):
    A, B = pikepdf.open(a), pikepdf.open(b)
    problems = 0
    if len(A.pages) != len(B.pages):
        print("page count differs", len(A.pages), len(B.pages))
        return 1
    total = 0
    for n, (pa, pb) in enumerate(zip(A.pages, B.pages), 1):
        sa, sb = streams(pa), streams(pb)
        if [t for t, _ in sa] != [t for t, _ in sb]:
            print("page %d: different streams" % n)
            problems += 1
            continue
        for (tag, x), (_, y) in zip(sa, sb):
            oa, ob = ops(x), ops(y)
            total += len(oa)
            if oa != ob:
                for i, (u, v) in enumerate(zip(oa, ob)):
                    if u != v:
                        print("page %d %s: op %d differs: %s vs %s" % (n, tag, i, u, v))
                        break
                else:
                    print("page %d %s: length differs %d vs %d" % (n, tag, len(oa), len(ob)))
                problems += 1
        ka = [sorted(str(k) for k in x.keys()) for x in pa.obj.get("/Annots", [])]
        kb = [sorted(str(k) for k in x.keys()) for x in pb.obj.get("/Annots", [])]
        if ka != kb:
            print("page %d: annotation keys differ" % n)
            problems += 1
    print("%d operators compared over %d pages; %d problems" % (total, len(A.pages), problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
