"""Audit a PDF for the kinds of object it contains, against the full lists in ISO 32000-2.

    python3 tools/audit.py out/objects-light.pdf [--arlington /path/to/arlington-pdf-model]

The required lists for annotation types, actions, shadings, functions, patterns, halftones,
fonts, font files, fields, XObjects and graphics state keys come from the PDF Association's
Arlington PDF Model when it's available, and from the tables below otherwise. Every content
stream (pages, forms, patterns, Type 3 glyphs, appearance streams) is parsed for operators.
"""
import argparse
import csv
import glob
import os
import re
import sys
from collections import Counter, defaultdict

import pikepdf
from pikepdf import Array, Dictionary, Name, Stream

OPERATORS = """b B b* B* BDC BI BMC BT BX c cm CS cs d d0 d1 Do DP EI EMC ET EX f F f* G g gs h i ID j J K k
l m M MP n q Q re RG rg ri s S SC sc SCN scn sh T* Tc Td TD Tf Tj TJ TL Tm Tr Ts Tw Tz v w W W* y ' \"""".split()

COLOUR_SPACES = ["DeviceGray", "DeviceRGB", "DeviceCMYK", "CalGray", "CalRGB", "Lab", "ICCBased", "Indexed",
                 "Pattern", "Separation", "DeviceN"]
FILTERS = ["ASCIIHexDecode", "ASCII85Decode", "LZWDecode", "FlateDecode", "RunLengthDecode", "CCITTFaxDecode",
           "JBIG2Decode", "DCTDecode", "JPXDecode", "Crypt"]
INLINE_ABBREV = {"AHx": "ASCIIHexDecode", "A85": "ASCII85Decode", "LZW": "LZWDecode", "Fl": "FlateDecode",
                 "RL": "RunLengthDecode", "CCF": "CCITTFaxDecode", "DCT": "DCTDecode",
                 "G": "DeviceGray", "RGB": "DeviceRGB", "CMYK": "DeviceCMYK", "I": "Indexed"}
BLEND_MODES = ["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "ColorDodge", "ColorBurn", "HardLight",
               "SoftLight", "Difference", "Exclusion", "Hue", "Saturation", "Color", "Luminosity"]
TEXT_MODES = [str(i) for i in range(8)]
# Removed or deprecated before PDF 2.0 with nothing to draw, or vendor extensions.
OUT_OF_SCOPE = {"XObjectFormPS", "XObjectFormPSpassthrough", "PS", "HTP", "AAPL:AA", "AAPL:ST", "Crypt",
                "NOP", "SetState"}


def arlington_lists(root):
    tsv = os.path.join(root, "tsv", "latest")
    lists = {}

    def subtypes(prefix, key="Subtype"):
        out = {}
        for f in sorted(glob.glob(os.path.join(tsv, prefix + "*.tsv"))):
            for row in csv.reader(open(f), delimiter="\t"):
                if row and row[0] == key and len(row) > 8:
                    vals = re.findall(r"[A-Za-z0-9_.]+", row[8].replace("fn:", ""))
                    vals = [v for v in vals if v not in ("SinceVersion", "Deprecated", "IsPDFVersion", "Extension",
                                                         "ADBE_Extn3", "Eval")]
                    vals = [v for v in vals if not re.match(r"^\d+(\.\d+)?$", v)]
                    if vals:
                        out[os.path.basename(f)[:-4]] = vals[-1]
        return out

    lists["annotations"] = sorted(set(subtypes("Annot").values()) - {"Annot"})
    lists["actions"] = sorted(set(subtypes("Action", "S").values()))
    lists["graphics state keys"] = sorted(r[0] for r in csv.reader(open(os.path.join(tsv, "GraphicsStateParameter.tsv")),
                                                                    delimiter="\t") if r and r[0] not in ("Key", "Type"))
    return lists


FALLBACK = {
    "annotations": ["3D", "Caret", "Circle", "FileAttachment", "FreeText", "Highlight", "Ink", "Line", "Link", "Movie",
                    "Polygon", "PolyLine", "Popup", "PrinterMark", "Projection", "Redact", "RichMedia", "Screen", "Sound",
                    "Square", "Squiggly", "Stamp", "StrikeOut", "Text", "TrapNet", "Underline", "Watermark", "Widget"],
    "actions": ["ECMAScript", "GoTo", "GoTo3DView", "GoToDp", "GoToE", "GoToR", "Hide", "ImportData", "JavaScript", "Launch",
                "Movie", "Named", "NOP", "Rendition", "ResetForm", "RichMediaExecute", "SetOCGState", "SetState", "Sound",
                "SubmitForm", "Thread", "Trans", "URI"],
}


class Audit:
    def __init__(self, pdf):
        self.pdf = pdf
        self.found = defaultdict(Counter)
        self.colour_keys = Counter()
        self.seen_streams = set()

    def add(self, cat, item):
        self.found[cat][str(item)] += 1

    # -- colour spaces --------------------------------------------------------------------
    def colour_space(self, cs):
        if isinstance(cs, Name):
            nm = str(cs)[1:]
            if nm in COLOUR_SPACES:
                self.add("colour spaces", nm)
            return
        if isinstance(cs, Array) and len(cs):
            fam = str(cs[0])[1:]
            self.add("colour spaces", fam)
            if fam == "Indexed":
                self.colour_space(cs[1])
                self.add("Indexed bases", self.cs_name(cs[1]))
            elif fam in ("Separation", "DeviceN"):
                self.colour_space(cs[2])
                self.function(cs[3])
                if fam == "Separation":
                    self.add("Separation colorants", str(cs[1])[1:] if str(cs[1])[1:] in ("All", "None") else "spot")
                if fam == "DeviceN" and len(cs) > 4 and Name.Subtype in cs[4]:
                    self.add("DeviceN subtypes", str(cs[4].Subtype)[1:])
            elif fam == "Pattern" and len(cs) > 1:
                self.colour_space(cs[1])
                self.add("uncoloured pattern bases", self.cs_name(cs[1]))
            elif fam == "ICCBased":
                self.add("ICC components", int(cs[1].N))

    def cs_name(self, cs):
        return str(cs)[1:] if isinstance(cs, Name) else str(cs[0])[1:]

    def function(self, fn):
        if isinstance(fn, Array):
            for f in fn:
                self.function(f)
            return
        if isinstance(fn, (Dictionary, Stream)) and Name.FunctionType in fn:
            self.add("function types", int(fn.FunctionType))
            if int(fn.FunctionType) == 3:
                self.function(fn.Functions)

    # -- walking --------------------------------------------------------------------------
    def dictionary(self, d):
        keys = set(str(k)[1:] for k in d.keys())
        t = str(d.get("/Type", ""))[1:]
        st = str(d.get("/Subtype", ""))[1:]
        if t == "Annot" or (st and "Rect" in keys and ("P" in keys or "AP" in keys or "Contents" in keys)):
            self.add("annotations", st)
            for k in ("C", "IC", "CA", "ca", "BM", "DA", "DS", "RC", "BE", "BS", "OC", "AP", "MK"):
                if k in keys:
                    self.colour_keys["Annot%s.%s" % (st, k)] += 1
            if "AP" in keys:
                for sk in ("N", "R", "D"):
                    if Name("/" + sk) in d.AP:
                        self.add("appearance states", sk)
            else:
                self.add("annotations without AP", st)
            if "FT" in keys or "Parent" in keys and "FT" in d.Parent:
                pass
        if "S" in keys and t in ("Action", "") and str(d.S)[1:] in FALLBACK["actions"] and (
                "Next" in keys or t == "Action" or any(k in keys for k in ("D", "URI", "N", "JS", "T", "F", "State", "R",
                                                                           "AN", "OP", "TA", "CMD", "Sound", "Movie",
                                                                           "Annotation", "Trans", "Dp", "Flags", "Fields"))):
            self.add("actions", str(d.S)[1:])
        if "FT" in keys:
            ft = str(d.FT)[1:]
            ff = int(d.get("/Ff", 0))
            if ft == "Btn":
                kind = "push" if ff & (1 << 16) else "radio" if ff & (1 << 15) else "check"
            elif ft == "Tx":
                kind = ",".join(n for n, b in [("multiline", 12), ("password", 13), ("file", 20), ("comb", 24),
                                               ("rich", 25)] if ff & (1 << b)) or "plain"
            elif ft == "Ch":
                kind = ("combo" if ff & (1 << 17) else "list") + (",edit" if ff & (1 << 18) else "") + (
                    ",multi" if ff & (1 << 21) else "")
            else:
                kind = ""
            self.add("fields", (ft + " " + kind).strip())
        if "MK" in keys:
            for k in ("BG", "BC", "CA", "RC", "AC", "I", "RI", "IX", "IF", "TP"):
                if Name("/" + k) in d.MK:
                    self.colour_keys["MK.%s" % k] += 1
        if "ShadingType" in keys:
            self.add("shading types", int(d.ShadingType))
            if "Background" in keys:
                self.colour_keys["Shading.Background"] += 1
            self.colour_space(d.ColorSpace)
            if "Function" in keys:
                self.function(d.Function)
        if "PatternType" in keys:
            self.add("pattern types", "%d%s" % (int(d.PatternType), "/paint %d" % int(d.PaintType) if "PaintType" in keys else ""))
            if "TilingType" in keys:
                self.add("tiling types", int(d.TilingType))
        if "FunctionType" in keys:
            self.function(d)
        if "HalftoneType" in keys:
            self.add("halftone types", int(d.HalftoneType))
        if t == "Font" or ("BaseFont" in keys and st):
            self.add("font types", st)
            if t == "Font" and "Widths" not in keys and st in ("Type1", "TrueType", "MMType1"):
                self.add("fonts without Widths", str(d.get("/BaseFont", ""))[1:])
            if "Encoding" in keys and isinstance(d.Encoding, Name):
                self.add("font encodings", str(d.Encoding)[1:])
            if "DescendantFonts" in keys:
                for df in d.DescendantFonts:
                    self.add("font types", str(df.Subtype)[1:])
        if t == "FontDescriptor":
            for k in ("FontFile", "FontFile2", "FontFile3"):
                if k in keys:
                    sub = str(d[Name("/" + k)].get("/Subtype", ""))[1:]
                    self.add("font files", k + ("/" + sub if sub else ""))
            if "FontFile" not in keys and "FontFile2" not in keys and "FontFile3" not in keys:
                self.add("font files", "not embedded")
        if t == "ExtGState" or (keys & {"ca", "CA", "BM", "SMask", "TR", "HT", "LW", "TK", "AIS", "OP"} and "Rect" not in keys
                                and "Subtype" not in keys and t in ("", "ExtGState")):
            for k in keys - {"Type"}:
                self.add("graphics state keys", k)
            if "BM" in keys:
                bm = d.BM
                for b in (bm if isinstance(bm, Array) else [bm]):
                    self.add("blend modes", str(b)[1:])
            if "SMask" in keys and isinstance(d.SMask, Dictionary):
                self.add("soft masks", str(d.SMask.S)[1:] + (" +TR" if "/TR" in d.SMask else "") + (" +BC" if "/BC" in d.SMask else ""))
        if t == "Group" or ("S" in keys and str(d.get("/S", ""))[1:] == "Transparency"):
            self.add("groups", "I=%s K=%s CS=%s" % (bool(d.get("/I", False)), bool(d.get("/K", False)),
                                                    self.cs_name(d.CS) if "CS" in keys else "-"))
        if t == "OCG":
            self.add("optional content", "OCG" + (" +Usage" if "Usage" in keys else ""))
            if "Usage" in keys:
                for k in d.Usage.keys():
                    self.add("OC usage", str(k)[1:])
        if t == "OCMD":
            self.add("optional content", "OCMD" + (" +VE" if "VE" in keys else "") + (" P=%s" % str(d.P)[1:] if "P" in keys else ""))
        if t in ("3DView", "3DBG", "3DRenderMode", "3DCrossSection", "3DLightingScheme", "3DMeasure", "ExData", "Rendition",
                 "MediaClip", "MediaScreenParams", "RichMediaContent", "RichMediaConfiguration", "RichMediaInstance",
                 "NavNode", "Thread", "Bead", "Trans", "Viewport", "Measure", "DPart", "DPartRoot", "OutputIntent",
                 "Namespace", "Sound", "Filespec", "EmbeddedFile", "SigFieldLock", "SV", "FWParams", "MediaPermissions",
                 "MediaPlayParams", "MediaCriteria", "RichMediaSettings", "RichMediaActivation", "RichMediaDeactivation",
                 "RichMediaCommand", "NumberFormat", "GEOGCS", "OPI", "Outlines", "Halftone", "Mask", "StructTreeRoot",
                 "StructElem", "OBJR", "MCR", "Pattern", "Encoding"):
            self.add("dictionary types", t)
        for k, label in [("BG", "3DBG.C"), ("RM", "3DRenderMode"), ("LS", "3DLightingScheme"), ("SA", "3DCrossSection"),
                         ("MA", "3DMeasure")]:
            if t == "3DView" and k in keys:
                self.colour_keys["3DView.%s" % k] += 1
        if t == "3DRenderMode":
            for k in ("AC", "FC"):
                if k in keys:
                    self.colour_keys["3DRenderMode.%s" % k] += 1
        if t == "3DCrossSection":
            for k in ("PC", "IC"):
                if k in keys:
                    self.colour_keys["3DCrossSection.%s" % k] += 1
        if t == "3DMeasure" and "C" in keys:
            self.colour_keys["3DMeasure.%s.C" % str(d.Subtype)[1:]] += 1
        if t == "3DBG" and "C" in keys:
            self.colour_keys["3DBG.C"] += 1
        if "Title" in keys and "Parent" in keys and ("Dest" in keys or "A" in keys):
            if "C" in keys:
                self.colour_keys["OutlineItem.C"] += 1
            if "F" in keys:
                self.add("outline flags", int(d.F))
        if "O" in keys and str(d.get("/O", ""))[1:] in ("Layout", "Table", "List", "PrintField", "NSO", "Artifact", "UserProperties"):
            self.add("attribute owners", str(d.O)[1:])
            for k in ("BackgroundColor", "BorderColor", "Color", "TextDecorationColor"):
                if k in keys:
                    self.colour_keys["StructAttr.%s" % k] += 1
        if t == "StructElem" or ("S" in keys and "P" in keys and "K" in keys and t != "Action"):
            self.add("structure types", str(d.S)[1:])
            for k in ("Alt", "ActualText", "E", "Lang", "NS", "C", "ID", "AF", "T"):
                if k in keys:
                    self.add("structure element keys", k)
        if "BoxColorInfo" in keys:
            for box in d.BoxColorInfo.keys():
                self.colour_keys["BoxStyle.%s.C" % str(box)[1:]] += 1
        if t == "MediaScreenParams" or ("B" in keys and ("W" in keys or "O" in keys) and "F" in keys):
            if "B" in keys:
                self.colour_keys["MediaScreenParams.B"] += 1
        if "Colors" in keys and t == "Collection":
            for k in d.Colors.keys():
                self.colour_keys["CollectionColors.%s" % str(k)[1:]] += 1

    def image(self, s, inline=False):
        self.add("image kinds", "inline" if inline else "XObject")
        filt = s.get("/Filter")
        for f in (filt if isinstance(filt, Array) else [filt] if filt is not None else []):
            self.add("filters", str(f)[1:])
        if s.get("/ImageMask", False):
            self.add("image kinds", "stencil mask")
        else:
            if "/ColorSpace" in s:
                self.colour_space(s.ColorSpace)
                self.add("image colour spaces", self.cs_name(s.ColorSpace))
            elif not inline and str(s.get("/Filter", ""))[1:] == "JPXDecode":
                self.add("image colour spaces", "from JPX codestream")
        for k in ("SMask", "Mask", "Decode", "Interpolate", "Alternates", "OPI", "SMaskInData", "Matte"):
            if Name("/" + k) in s:
                v = s[Name("/" + k)]
                self.add("image features", k + (" array" if k == "Mask" and isinstance(v, Array) else
                                                " stream" if k == "Mask" else ""))
        if "/SMask" in s and "/Matte" in s.SMask:
            self.add("image features", "Matte")
        if "/BitsPerComponent" in s:
            self.add("bits per component", int(s.BitsPerComponent))

    def content(self, stream, resources):
        try:
            ops = pikepdf.parse_content_stream(stream)
        except Exception as e:
            self.add("content errors", repr(e)[:80])
            return
        for item in ops:
            if isinstance(item, pikepdf.ContentStreamInlineImage):
                self.add("operators", "BI")
                self.add("operators", "ID")
                self.add("operators", "EI")
                ii = item.iimage
                d = ii.obj
                filt = d.get("/F", d.get("/Filter"))
                for f in (filt if isinstance(filt, Array) else [filt] if filt is not None else []):
                    nm = str(f)[1:]
                    self.add("filters", INLINE_ABBREV.get(nm, nm))
                self.add("image kinds", "inline")
                if d.get("/IM", False):
                    self.add("image kinds", "inline stencil mask")
                cs = d.get("/CS")
                if cs is not None:
                    nm = str(cs)[1:]
                    self.add("inline colour spaces", INLINE_ABBREV.get(nm, nm))
                continue
            op = str(item.operator)
            self.add("operators", op)
            if op == "Tr":
                self.add("text render modes", int(item.operands[0]))
            elif op in ("cs", "CS") and resources is not None:
                nm = item.operands[0]
                if str(nm)[1:] in COLOUR_SPACES:
                    self.add("colour spaces", str(nm)[1:])
                elif "/ColorSpace" in resources and nm in resources.ColorSpace:
                    self.colour_space(resources.ColorSpace[nm])
            elif op in ("g", "G"):
                self.add("colour spaces", "DeviceGray")
            elif op in ("rg", "RG"):
                self.add("colour spaces", "DeviceRGB")
            elif op in ("k", "K"):
                self.add("colour spaces", "DeviceCMYK")
            elif op == "ri":
                self.add("rendering intents", str(item.operands[0])[1:])
            elif op in ("j", "J"):
                self.add("line %s" % ("joins" if op == "j" else "caps"), int(item.operands[0]))
            elif op in ("BDC", "BMC"):
                self.add("marked content tags", str(item.operands[0])[1:])

    def walk_resources(self, res, depth=0):
        if res is None or depth > 12:
            return
        for cat in ("XObject", "Pattern", "Font"):
            if Name("/" + cat) not in res:
                continue
            for _, obj in res[Name("/" + cat)].items():
                key = obj.objgen if obj.is_indirect else id(obj)
                if key in self.seen_streams:
                    continue
                self.seen_streams.add(key)
                if cat == "XObject":
                    sub = str(obj.Subtype)[1:]
                    if sub == "Image":
                        self.image(obj)
                        if "/SMask" in obj:
                            self.add("image kinds", "soft mask")
                    else:
                        self.add("XObject kinds", "Form" + (" +Group" if "/Group" in obj else "") +
                                 (" +Ref" if "/Ref" in obj else "") + (" +OC" if "/OC" in obj else "") +
                                 (" no Resources" if "/Resources" not in obj else ""))
                        self.content(obj, obj.get("/Resources"))
                        self.walk_resources(obj.get("/Resources"), depth + 1)
                elif cat == "Pattern" and isinstance(obj, Stream):
                    self.content(obj, obj.get("/Resources"))
                    self.walk_resources(obj.get("/Resources"), depth + 1)
                elif cat == "Font" and str(obj.get("/Subtype", ""))[1:] == "Type3":
                    for _, cp in obj.CharProcs.items():
                        self.content(cp, obj.get("/Resources"))
                    self.walk_resources(obj.get("/Resources"), depth + 1)

    def visit(self, obj, depth=0):
        """Visit a dictionary and every direct dictionary inside it. Indirect children are
        visited on their own from pdf.objects, so they aren't followed here."""
        if depth > 40:
            return
        if isinstance(obj, (Dictionary, Stream)):
            try:
                self.dictionary(obj)
            except Exception as e:
                self.add("audit errors", repr(e)[:80])
            for k, v in obj.items():
                if k in ("/A", "/Next", "/OpenAction", "/PA", "/NA") and isinstance(v, Dictionary) and "/S" in v:
                    self.add("actions", str(v.S)[1:])
                if k == "/AA" and isinstance(v, Dictionary):
                    for _, act in v.items():
                        if isinstance(act, Dictionary) and "/S" in act:
                            self.add("actions", str(act.S)[1:])
                if k == "/Next" and isinstance(v, Array):
                    for act in v:
                        if isinstance(act, Dictionary) and "/S" in act:
                            self.add("actions", str(act.S)[1:])
                if k in ("/Parent", "/P", "/Prev", "/Next", "/First", "/Last", "/Pg", "/Popup", "/AN", "/TA", "/Obj"):
                    continue
                if isinstance(v, (Dictionary, Array)) and not v.is_indirect:
                    self.visit(v, depth + 1)
        elif isinstance(obj, Array):
            for v in obj:
                if isinstance(v, (Dictionary, Array)) and not v.is_indirect:
                    self.visit(v, depth + 1)

    def run(self):
        pdf = self.pdf
        for obj in pdf.objects:
            if isinstance(obj, (Dictionary, Stream, Array)):
                self.visit(obj)
        for page in pdf.pages:
            self.add("page keys", "page")
            for k in page.obj.keys():
                self.add("page keys", str(k)[1:])
            res = page.obj.get("/Resources")
            for c in [page.obj.Contents] if isinstance(page.obj.Contents, Stream) else list(page.obj.Contents):
                self.content(c, res)
            self.walk_resources(res)
            for a in page.obj.get("/Annots", []):
                ap = a.get("/AP")
                if ap is None:
                    continue
                for sk, v in ap.items():
                    for s in ([v] if isinstance(v, Stream) else list(v.values()) if isinstance(v, Dictionary) else []):
                        if isinstance(s, Stream):
                            self.content(s, s.get("/Resources"))
                            self.walk_resources(s.get("/Resources"))
                for k in ("MK",):
                    if k in a and "/I" in a.MK:
                        self.walk_resources(Dictionary(XObject=Dictionary(I=a.MK.I)))
        for k in pdf.Root.keys():
            self.add("catalog keys", str(k)[1:])
        return self


def report(audit, lists):
    gaps = {}
    lines = []
    for cat, required in lists.items():
        have = set(audit.found[cat])
        required = [r for r in required if str(r) not in OUT_OF_SCOPE]
        missing = [r for r in required if str(r) not in have]
        gaps[cat] = missing
        lines.append("%-22s %3d of %3d%s" % (cat, len(required) - len(missing), len(required),
                                              ("   missing: " + ", ".join(map(str, missing))) if missing else ""))
    return lines, gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--arlington", default=os.environ.get("ARLINGTON", ""))
    ap.add_argument("--all", action="store_true", help="print every category found")
    args = ap.parse_args()
    pdf = pikepdf.open(args.pdf)
    audit = Audit(pdf).run()
    lists = dict(FALLBACK)
    if args.arlington and os.path.isdir(args.arlington):
        lists.update(arlington_lists(args.arlington))
    lists.update({
        "operators": OPERATORS,
        "colour spaces": COLOUR_SPACES,
        "filters": [f for f in FILTERS if f != "Crypt"],
        "shading types": [str(i) for i in range(1, 8)],
        "function types": ["0", "2", "3", "4"],
        "halftone types": ["1", "5", "6", "10", "16"],
        "blend modes": BLEND_MODES,
        "text render modes": TEXT_MODES,
        "font types": ["Type0", "Type1", "MMType1", "TrueType", "Type3", "CIDFontType0", "CIDFontType2"],
        "font files": ["FontFile", "FontFile2", "FontFile3/Type1C", "FontFile3/CIDFontType0C", "FontFile3/OpenType",
                       "not embedded"],
        "fields": ["Btn check", "Btn radio", "Btn push", "Tx plain", "Tx multiline", "Tx password", "Tx file", "Tx comb",
                   "Tx rich", "Ch list", "Ch list,multi", "Ch combo", "Ch combo,edit", "Sig"],
        "line caps": ["0", "1", "2"],
        "line joins": ["0", "1", "2"],
        "rendering intents": ["AbsoluteColorimetric", "RelativeColorimetric", "Saturation", "Perceptual"],
    })
    lines, gaps = report(audit, lists)
    print("Audit of", args.pdf)
    for l in lines:
        print(" ", l)
    print("\nColour-bearing keys found:")
    for k, v in sorted(audit.colour_keys.items()):
        print("  %-40s %d" % (k, v))
    if args.all:
        print()
        for cat in sorted(audit.found):
            if cat not in lists:
                print("  %s: %s" % (cat, ", ".join("%s (%d)" % kv for kv in sorted(audit.found[cat].items()))))
    return 1 if any(gaps.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
