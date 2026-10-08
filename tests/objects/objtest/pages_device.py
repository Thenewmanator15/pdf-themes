"""Printing and device-dependent objects: halftones, transfer functions, black generation,
smoothness, black point compensation, separations, output intents, OPI, MMType1 and the
BX/EX compatibility operators."""
from pikepdf import Array, Dictionary, Name, String
from reportlab.pdfbase import pdfmetrics

from .core import Page, circle_path, n, rect_path, round_rect_path
from .fonts import WINANSI, _winansi_encode
from .palette import fmt


def greys(p, x, y, w, h, gs=None, steps=8, role_fill=None):
    body = []
    for i in range(steps):
        g = i / (steps - 1)
        body.append("%s g %s f" % (fmt([g]), rect_path(x + i * w / steps, y, w / steps, h)))
    s = " ".join(body)
    return "q %s gs %s Q" % (gs, s) if gs else s


def page_device(doc, res):
    p = Page(doc, "Printing and device-dependent objects",
             "Halftones, transfer functions, black generation and the rest act when a page is printed or converted "
             "for a device. A theme changes the colours that go in; these still apply on the way out, so the spec "
             "should say whether a theme applies before or after them. The deprecated objects are here because old "
             "files still carry them.")
    pal = p.pal
    t = p.grid(3, 4)

    def ht1(freq, angle, spot):
        return Dictionary(Type=Name.Halftone, HalftoneType=1, Frequency=freq, Angle=angle, SpotFunction=Name("/" + spot))

    x, y, w, h = p.tile(t[0], "Halftone type 1: spot functions", "T126, T127, T128", "stays", note="Print only")
    for i, spot in enumerate(["Round", "Line", "Ellipse"]):
        gs = p.use("ExtGState", "GSHT1%s" % spot, res.gstate(HT=ht1(40 + 10 * i, 45, spot)))
        p.figure(greys(p, x + 4, y + h - 18 - i * 20, w - 8, 14, gs), "A grey ramp with a %s halftone." % spot)

    x, y, w, h = p.tile(t[1], "Halftone type 5 per colorant", "T132", "stays", note="Different screens for C, M, Y, K")
    ht5 = Dictionary(Type=Name.Halftone, HalftoneType=5, Cyan=ht1(60, 15, "Round"), Magenta=ht1(60, 75, "Round"),
                     Yellow=ht1(60, 0, "Round"), Black=ht1(60, 45, "Round"), Default=ht1(60, 45, "Round"))
    gs = p.use("ExtGState", "GSHT5", res.gstate(HT=ht5))
    p.figure("q %s gs %s Q" % (gs, " ".join("%s k %s f" % (fmt(c), rect_path(x + 4 + i * (w - 8) / 4, y + 6, (w - 8) / 4, h - 12))
                                            for i, c in enumerate([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)]))),
             "Cyan, magenta, yellow and black panels.")

    x, y, w, h = p.tile(t[2], "Threshold halftones: types 6, 10, 16", "T129, T130, T131", "stays")
    th6 = doc.stream(bytes((i * 37) % 256 for i in range(64)), Type=Name.Halftone, HalftoneType=6, Width=8, Height=8)
    th10 = doc.stream(bytes((i * 53) % 256 for i in range(4 * 4 + 2 * 2)), Type=Name.Halftone, HalftoneType=10,
                      Xsquare=4, Ysquare=2)
    th16 = doc.stream(b"".join(((i * 4099) % 65536).to_bytes(2, "big") for i in range(64)), Type=Name.Halftone,
                      HalftoneType=16, Width=8, Height=8)
    for i, ht in enumerate([th6, th10, th16]):
        gs = p.use("ExtGState", "GSTH%d" % i, res.gstate(HT=ht))
        p.figure(greys(p, x + 4, y + h - 18 - i * 20, w - 8, 14, gs), "A grey ramp with a threshold halftone.")

    x, y, w, h = p.tile(t[3], "Transfer functions: TR and TR2", "T57", "viewer",
                        note="Some viewers apply TR, so it changes what the theme draws")
    tr = doc.stream(b"{ 0.6 exp }", FunctionType=4, Domain=Array([0, 1]), Range=Array([0, 1]))
    gs_tr = p.use("ExtGState", "GSTR", res.gstate(TR=tr))
    gs_tr2 = p.use("ExtGState", "GSTR2", res.gstate(TR2=Name.Default))
    p.figure("%s %s q %s gs %s Q" % (greys(p, x + 4, y + h - 20, w - 8, 14), "", gs_tr, greys(p, x + 4, y + h - 40, w - 8, 14)),
             "A grey ramp, then the same ramp through a transfer function.")
    p.figure("q %s gs %s %s f Q" % (gs_tr2, pal.rg("accent"), rect_path(x + 4, y + 6, w - 8, 14)), "A panel with TR2 Default.")

    x, y, w, h = p.tile(t[4], "Black generation and undercolour removal", "T57", "stays",
                        note="BG, BG2, UCR, UCR2: RGB to CMYK at print time")
    bg = doc.stream(b"{ dup 0.5 gt { 0.5 sub 2 mul } { pop 0 } ifelse }", FunctionType=4, Domain=Array([0, 1]), Range=Array([0, 1]))
    ucr = doc.stream(b"{ 0.5 mul }", FunctionType=4, Domain=Array([0, 1]), Range=Array([-1, 1]))
    gs = p.use("ExtGState", "GSBG", res.gstate(BG=bg, UCR=ucr))
    gs2 = p.use("ExtGState", "GSBG2", res.gstate(BG2=Name.Default, UCR2=Name.Default))
    p.figure("q %s gs %s %s f Q q %s gs %s %s f Q" % (gs, pal.rg("purple"), rect_path(x + 4, y + h / 2, w - 8, h / 2 - 6), gs2,
                                                      pal.rg("teal"), rect_path(x + 4, y + 6, w - 8, h / 2 - 10)),
             "Purple and teal panels with black generation set.")

    x, y, w, h = p.tile(t[5], "SM, HTO and UseBlackPtComp", "T57", "stays", note="Smoothness; PDF 2.0 halftone origin and BPC")
    gs = p.use("ExtGState", "GSSM", res.gstate(SM=0.02, HTO=Array([0, 0]), UseBlackPtComp=Name.ON))
    sh = doc.pdf.make_indirect(Dictionary(ShadingType=2, ColorSpace=Name.DeviceRGB, Coords=Array([x, y, x + w, y]),
                                          Function=res.fn_exp("ink", "accent")))
    p.use("Shading", "ShSM", sh)
    p.figure("q %s gs %s W n /ShSM sh Q" % (gs, rect_path(x + 4, y + 6, w - 8, h - 12)), "A gradient drawn with fine smoothness.")

    x, y, w, h = p.tile(t[6], "SeparationInfo", "T400", "stays", note="Says this page is one plate of a separated job")
    p.obj.SeparationInfo = Dictionary(Pages=Array([p.obj]), DeviceColorant=Name.Cyan,
                                      ColorSpace=Array([Name.Separation, Name.Cyan, Name.DeviceCMYK,
                                                        Dictionary(FunctionType=2, Domain=Array([0, 1]),
                                                                   C0=Array([0, 0, 0, 0]), C1=Array([1, 0, 0, 0]), N=1)]))
    p.figure("%s k %s f" % (fmt([1, 0, 0, 0]), round_rect_path(x + 10, y + 10, w - 20, h - 20, 6)), "A cyan plate.")

    x, y, w, h = p.tile(t[7], "Document output intent", "T29, T401", "stays", note="FOGRA39 profile embedded")
    doc.catalog_extra["OutputIntents"] = Array([Dictionary(Type=Name.OutputIntent, S=Name.GTS_PDFX,
                                                           OutputCondition=String("Coated FOGRA39"),
                                                           OutputConditionIdentifier=String("FOGRA39"),
                                                           RegistryName=String("http://www.color.org"),
                                                           Info=String("Coated FOGRA39 (ISO 12647-2:2004)"),
                                                           DestOutputProfile=res.icc_stream("cmyk"))])
    p.para(x + 4, y + h - 6, "Device colours mean FOGRA39 here, so a theme's DeviceCMYK values are read through this profile.",
           w - 8, size=6.8)

    x, y, w, h = p.tile(t[8], "OPI 1.3 and 2.0 on an image (deprecated)", "T405, T406, T407", "stays")
    from .images import photo
    im = photo(80, 54)
    img = doc.stream(im.tobytes(), Type=Name.XObject, Subtype=Name.Image, Width=80, Height=54, ColorSpace=Name.DeviceRGB,
                     BitsPerComponent=8, OPI=Dictionary({
                         "/1.3": Dictionary(Type=Name.OPI, Version=1.3, F=String("high-res/landscape.tif"),
                                            Size=Array([800, 540]), CropRect=Array([0, 0, 800, 540]),
                                            Position=Array([0, 0, 0, 54, 80, 54, 80, 0]), ColorType=Name.Process,
                                            Color=Array([0, 0, 0, 1, String("Black")]), Tint=1.0),
                         "/2.0": Dictionary(Type=Name.OPI, Version=2.0, F=String("high-res/landscape.tif"),
                                            MainImage=String("landscape.tif"), Size=Array([800, 540]),
                                            CropRect=Array([0, 0, 800, 540]))}))
    p.use("XObject", "ImOPI", img)
    s = min(w - 8, (h - 8) * 1.48)
    p.figure("q %s 0 0 %s %s %s cm /ImOPI Do Q" % (n(s), n(s / 1.48), n(x + (w - s) / 2), n(y + 4)),
             "A low-resolution proxy image with an OPI link.")

    x, y, w, h = p.tile(t[9], "MMType1 font (deprecated)", "T108, T109", "swaps", note="Not embedded; the viewer substitutes")
    widths = [int(pdfmetrics.stringWidth(bytes([c]).decode("cp1252", "ignore") or " ", "Helvetica", 1000)) if WINANSI[c] else 0
              for c in range(32, 256)]
    mm = doc.pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.MMType1, BaseFont=Name("/MyriadMM_400_600_"),
                                          FirstChar=32, LastChar=255, Widths=Array(widths), Encoding=Name.WinAnsiEncoding,
                                          FontDescriptor=doc.pdf.make_indirect(Dictionary(
                                              Type=Name.FontDescriptor, FontName=Name("/MyriadMM_400_600_"), Flags=32,
                                              FontBBox=Array([-157, -250, 1126, 952]), ItalicAngle=0, Ascent=718,
                                              Descent=-207, CapHeight=674, StemV=88))))
    p.res["Font"]["MM"] = mm
    p.tagged("P", "BT /MM 11 Tf %s %s %s Td %s Tj ET" % (pal.rg("ink"), n(x + 6), n(y + h / 2), _winansi_encode("Multiple master text")))

    x, y, w, h = p.tile(t[10], "BX/EX and marked points: MP, DP", "T33, T352", "swaps", note="An unknown operator inside BX/EX is skipped")
    p.figure("BX /Unknown 1 2 3 xyzzy EX /Point MP /Point <</Note (a marked point)>> DP %s %s f" % (
        pal.rg("green"), round_rect_path(x + 10, y + 10, w - 20, h - 20, 6)),
             "A green panel drawn after an unknown operator and two marked points.")

    x, y, w, h = p.tile(t[11], "Not tested: removed or invisible", "", "stays")
    p.para(x + 4, y + h - 6, "PostScript XObjects and the PS operator (removed in PDF 2.0), XFA forms (deprecated), "
           "Web Capture and alternate presentations: none of these draw anything a theme can reach.", w - 8, size=6.5,
           role="muted")
    return p
