"""The way an author can do this today: both builds in one file, each in its
own optional content layer (light on, dark off). Used only to measure size.
Fonts and ICC profiles are shared, so the extra bytes are the second copy of
every page's drawing and text. The dark copy is marked as an artifact, since
the structure tree can only point at one copy of the text."""

from __future__ import annotations

import pikepdf
from pikepdf import Array, Dictionary, Name, Operator, String

from pdfthemes.core import Grafter, canon

DEVICE = {"/Pattern", "/DeviceRGB", "/DeviceGray", "/DeviceCMYK"}


def two_layers(light_path, dark_path) -> pikepdf.Pdf:
    light = pikepdf.open(light_path)
    dark = pikepdf.open(dark_path)
    graft = Grafter(light)
    oc_light = light.make_indirect(Dictionary(Type=Name.OCG, Name=String("Light")))
    oc_dark = light.make_indirect(Dictionary(Type=Name.OCG, Name=String("Dark")))
    for pl, pd in zip(light.pages, dark.pages):
        res_l, res_d = pl.Resources, pd.Resources
        rename = {}
        for kind in ("/Font", "/ColorSpace", "/ExtGState", "/Pattern", "/XObject", "/Shading"):
            for name, obj in res_d.get(kind, {}).items():
                same = next((n for n, o in res_l.get(kind, {}).items() if canon(o) == canon(obj)), None)
                if same is not None:
                    rename[(kind, name)] = same
                    continue
                new = "/D" + name[1:]
                if kind not in res_l:
                    res_l[kind] = Dictionary()
                res_l[kind][new] = graft.copy(obj)
                rename[(kind, name)] = new
        ops = []
        for ins in pikepdf.parse_content_stream(pd):
            op, args = str(ins.operator), list(ins.operands)
            if op == "Tf":
                args[0] = Name(rename[("/Font", str(args[0]))])
            elif op == "gs":
                args[0] = Name(rename[("/ExtGState", str(args[0]))])
            elif op in ("cs", "CS") and str(args[0]) not in DEVICE:
                args[0] = Name(rename[("/ColorSpace", str(args[0]))])
            elif op in ("scn", "SCN") and args and isinstance(args[-1], Name):
                args[-1] = Name(rename[("/Pattern", str(args[-1]))])
            elif op == "BDC":
                op, args = "BMC", [Name.Artifact]
            ops.append((args, Operator(op)))
        content_d = pikepdf.unparse_content_stream(ops)
        content_l = pikepdf.unparse_content_stream(pikepdf.parse_content_stream(pl))
        if "/Properties" not in res_l:
            res_l["/Properties"] = Dictionary()
        res_l.Properties["/OCLight"] = oc_light
        res_l.Properties["/OCDark"] = oc_dark
        pl.obj.Contents = light.make_stream(
            b"/OC /OCLight BDC q\n" + content_l + b"\nQ EMC\n/OC /OCDark BDC q\n" + content_d + b"\nQ EMC\n")
    light.Root.OCProperties = Dictionary(
        OCGs=Array([oc_light, oc_dark]),
        D=Dictionary(ON=Array([oc_light]), OFF=Array([oc_dark]), Order=Array([oc_light, oc_dark]),
                     RBGroups=Array([Array([oc_light, oc_dark])])),
    )
    return light
