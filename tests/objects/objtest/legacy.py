"""The legacy pair: things PDF 2.0 no longer allows but real files still carry, so the viewer
has to draw them from entries in the file. Annotations and fields without appearance
streams, NeedAppearances, standard 14 fonts without metrics, and a form XObject without
Resources. Saved as PDF 1.7.

    python3 -m objtest.legacy out
"""
import math
import os

from pikepdf import Array, Dictionary, Name, String

from .build import save
from .core import Doc, Page, n, poly_path, rect_path
from .pages_annots import markup, popup_for
from .pages_interactive import label, link, mk, widget
from .palette import HUES, build_palettes
from .resources import Res


def page_viewer_annots(doc, res):
    p = Page(doc, "Annotations the viewer draws",
             "None of these annotations has an appearance stream, so every viewer draws them itself from C, IC, BS, "
             "DA, DS and the icon name. For a theme to work, the viewer has to recolour them too.")
    pal = p.pal
    t = p.grid(3, 4)
    sans = p.font("Sans")

    x, y, w, h = p.tile(t[0], "Text: the seven standard icons", "T175", "viewer")
    for i, nm in enumerate(["Comment", "Key", "Note", "Help", "NewParagraph", "Paragraph", "Insert"]):
        cx, cy = x + 4 + (i % 4) * (w - 8) / 4, y + h - 30 - (i // 4) * 34
        markup(p, "Text", [cx, cy, cx + 20, cy + 20], "Note icon " + nm, None, C=doc.rgb(HUES[i]), Name=Name("/" + nm))
        p.text(cx + 10, cy - 7, nm, size=4.8, role="muted", tag="Caption", align="center")

    x, y, w, h = p.tile(t[1], "Square, Circle and Line", "T178, T180", "viewer")
    q = (w - 10) / 3
    markup(p, "Square", [x + 2, y + 8, x + 2 + q, y + h - 8], "Square", None, C=doc.rgb("red"), IC=doc.rgb("yellow"),
           BS=Dictionary(W=2))
    markup(p, "Circle", [x + 6 + q, y + 8, x + 6 + 2 * q, y + h - 8], "Circle", None, C=doc.rgb("blue"),
           IC=doc.rgb("teal"), BS=Dictionary(W=2, S=Name.D, D=Array([3, 2])))
    markup(p, "Line", [x + 10 + 2 * q, y + 8, x + w - 2, y + h - 8], "Line", None,
           L=Array([x + 12 + 2 * q, y + 12, x + w - 6, y + h - 12]), LE=Array([Name.Circle, Name.ClosedArrow]),
           C=doc.rgb("green"), IC=doc.rgb("green"), BS=Dictionary(W=2))

    x, y, w, h = p.tile(t[2], "Polygon, PolyLine and Ink", "T181, T185", "viewer")
    verts = [(x + 8, y + 10), (x + w * 0.35, y + h - 8), (x + w * 0.42, y + 16)]
    markup(p, "Polygon", [x + 2, y + 2, x + w * 0.45, y + h - 2], "Polygon", None,
           Vertices=Array([c for v in verts for c in v]), C=doc.rgb("orange"), IC=doc.rgb("yellow"), BS=Dictionary(W=1.5))
    verts = [(x + w * 0.5, y + 12), (x + w * 0.62, y + h - 12), (x + w * 0.74, y + 18)]
    markup(p, "PolyLine", [x + w * 0.47, y + 2, x + w * 0.78, y + h - 2], "PolyLine", None,
           Vertices=Array([c for v in verts for c in v]), C=doc.rgb("blue"), LE=Array([Name("/None"), Name.OpenArrow]),
           BS=Dictionary(W=1.5))
    pts = [(x + w * 0.8 + 3 * math.sin(i), y + 8 + i * (h - 16) / 12) for i in range(13)]
    markup(p, "Ink", [x + w * 0.78, y + 2, x + w - 2, y + h - 2], "Ink", None,
           InkList=Array([Array([c for pt in pts for c in pt])]), C=doc.rgb("purple"), BS=Dictionary(W=2))

    x, y, w, h = p.tile(t[3], "Text markup from QuadPoints", "T182", "viewer")
    for i, (sub, role) in enumerate([("Highlight", "hl"), ("Underline", "green"), ("Squiggly", "red"),
                                     ("StrikeOut", "purple")]):
        ty = y + h - 14 - i * (h - 16) / 4
        tw = p.text(x + 4, ty, sub + " this text", size=8)
        r = [x + 2, ty - 3, x + 6 + tw, ty + 10]
        markup(p, sub, r, sub, None, C=doc.rgb(role),
               QuadPoints=Array([r[0], r[3], r[2], r[3], r[0], r[1], r[2], r[1]]))

    x, y, w, h = p.tile(t[4], "FreeText from DA, DS and RC", "T177", "viewer")
    rc = ('<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" style="font-size:9pt;color:%s"><p>Free text '
          '<span style="color:%s">in two colours</span></p></body>' % (pal.hexstr("ink"), pal.hexstr("red")))
    markup(p, "FreeText", [x + 4, y + h / 2 - 16, x + w - 4, y + h / 2 + 16], "Free text in two colours", None,
           DA=String("%s /Helv 9 Tf" % pal.rg("ink")), DS=String("font: Helvetica 9pt; color:%s" % pal.hexstr("ink")),
           RC=String(rc), C=doc.rgb("accent"), BS=Dictionary(W=1))

    x, y, w, h = p.tile(t[5], "Stamps by name", "T184", "viewer")
    for i, nm in enumerate(["Approved", "Draft", "Confidential", "Final", "NotApproved", "Expired"]):
        cx, cy = x + 2 + (i % 2) * w / 2, y + h - 22 - (i // 2) * (h - 8) / 3
        markup(p, "Stamp", [cx, cy, cx + w / 2 - 6, cy + 16], "Stamp " + nm, None, Name=Name("/" + nm), C=doc.rgb("red"))

    x, y, w, h = p.tile(t[6], "FileAttachment icons", "T187", "viewer")
    csv = doc.embed_file("legacy.csv", b"a,b\n1,2\n", "text/csv", "A small CSV")
    for i, nm in enumerate(["PushPin", "Paperclip", "Graph", "Tag"]):
        cx = x + 8 + i * (w - 16) / 4
        markup(p, "FileAttachment", [cx, y + h / 2 - 10, cx + 16, y + h / 2 + 10], "Attachment " + nm, None, FS=csv,
               Name=Name("/" + nm), C=doc.rgb(HUES[i]))

    x, y, w, h = p.tile(t[7], "Caret and Popup", "T183, T186", "viewer")
    tw = p.text(x + 4, y + h - 16, "Insert here", size=8)
    markup(p, "Caret", [x + 4 + sans.width("Insert", 8) - 4, y + h - 24, x + 4 + sans.width("Insert", 8) + 4, y + h - 16],
           "Caret", None, C=doc.rgb("blue"), Sy=Name("/None"))
    parent = markup(p, "Text", [x + 4, y + 8, x + 24, y + 28], "Open popup", None, C=doc.rgb("accent"), Open=True,
                    Name=Name.Comment)
    popup_for(p, parent, [x + 30, y + 6, x + w - 4, y + h - 30], open_=True)

    x, y, w, h = p.tile(t[8], "Link borders", "T176", "viewer")
    tw = label(p, x + 6, y + h / 2, "A bordered link")
    link(p, [x + 3, y + h / 2 - 4, x + 9 + tw, y + h / 2 + 10], Dictionary(S=Name.URI, URI=String("https://example.com/")),
         contents="A bordered link", Border=Array([0, 0, 2]), C=doc.rgb("red"))
    return p


def page_viewer_forms(doc, res):
    p = Page(doc, "Fields, fonts and forms the viewer resolves",
             "NeedAppearances is true and no field has an appearance stream, so the viewer builds each one from MK and "
             "DA. The standard 14 fonts have no Widths, and one form XObject has no Resources: all allowed before PDF 2.0.")
    pal = p.pal
    t = p.grid(3, 3)
    doc.acroform_extra["NeedAppearances"] = True
    ink = "%s /Helv 10 Tf" % pal.rg("ink")

    x, y, w, h = p.tile(t[0], "Text field from MK and DA", "T191, T192, T224", "viewer")
    widget(p, "Tx", "legacy_text", [x + 4, y + h / 2 - 10, x + w - 4, y + h / 2 + 10], value=String("Typed text"),
           da=ink, mk=mk(doc, "tile", "accent"))

    x, y, w, h = p.tile(t[1], "Check box and radio from MK CA", "T192, T230", "viewer")
    widget(p, "Btn", "legacy_check", [x + 8, y + h / 2 - 9, x + 26, y + h / 2 + 9], value=Name.Yes,
           da="%s /ZaDb 0 Tf" % pal.rg("green"), mk=mk(doc, "tile", "ink", CA=String("4")), extra={"AS": Name.Yes})
    parent = doc.pdf.make_indirect(Dictionary(FT=Name.Btn, T=String("legacy_radio"), Ff=(1 << 15) | (1 << 14),
                                              V=Name("/B"), Kids=Array(), DA=String("%s /ZaDb 0 Tf" % pal.rg("accent"))))
    doc.fields.append(parent)
    for i, opt in enumerate(["A", "B"]):
        kid = widget(p, "Btn", None, [x + 50 + i * 30, y + h / 2 - 9, x + 68 + i * 30, y + h / 2 + 9], parent=parent,
                     mk=mk(doc, "tile", "ink", CA=String("l")), extra={"AS": Name("/" + opt) if opt == "B" else Name.Off})
        parent.Kids.append(kid)

    x, y, w, h = p.tile(t[2], "Combo and list boxes", "T233, T234", "viewer")
    widget(p, "Ch", "legacy_combo", [x + 4, y + h - 26, x + w - 4, y + h - 8], value=String("Two"), flags=1 << 17, da=ink,
           mk=mk(doc), extra={"Opt": Array([String("One"), String("Two"), String("Three")])})
    widget(p, "Ch", "legacy_list", [x + 4, y + 6, x + w - 4, y + h - 34], value=String("Two"), da=ink, mk=mk(doc),
           extra={"Opt": Array([String("One"), String("Two"), String("Three")]), "I": Array([1])})

    x, y, w, h = p.tile(t[3], "Push button with a caption", "T192, T229", "viewer")
    widget(p, "Btn", "legacy_button", [x + 10, y + h / 2 - 12, x + w - 10, y + h / 2 + 12], flags=1 << 16,
           da="%s /Helv 10 Tf" % pal.rg("paper"), mk=mk(doc, "accent", "ink", CA=String("Press me")))

    x, y, w, h = p.tile(t[4], "Standard 14 fonts without metrics", "T109", "swaps", note="No Widths or FontDescriptor")
    for i, base in enumerate(["Helvetica", "Times-Roman", "Courier", "Helvetica-Bold"]):
        f = p.std_bare(base)
        p.tagged("P", p.text_op(x + 4, y + h - 14 - i * 16, base, 10, f, "ink" if i % 2 == 0 else "accent"))

    x, y, w, h = p.tile(t[5], "Form XObject without Resources", "T93", "swaps", note="Uses the page's font")
    f = p.std_bare("Helvetica-Bold")
    bare = doc.form("BT /%s 14 Tf %s 2 6 Td (Inherited) Tj ET" % (f.key, pal.rg("blue")), [0, 0, 120, 30])
    nm = p.use("XObject", "FmBare", bare)
    p.figure("q 1 0 0 1 %s %s cm %s Do Q" % (n(x + 4), n(y + h / 2 - 10), nm), "The word Inherited.")

    x, y, w, h = p.tile(t[6], "Signature field without appearance", "T235", "viewer")
    widget(p, "Sig", "legacy_signature", [x + 6, y + 10, x + w - 6, y + h - 10], da="%s /Helv 0 Tf" % pal.rg("ink"),
           mk=mk(doc, "tile", "accent"))
    return p


def build_legacy(pal):
    doc = Doc(pal)
    res = Res(doc)
    page_viewer_annots(doc, res)
    page_viewer_forms(doc, res)
    return doc


def main(outdir="out"):
    for pal in build_palettes():
        doc = build_legacy(pal)
        pdf = doc.finish()
        path = os.path.join(outdir, "legacy-%s.pdf" % pal.name)
        save(pdf, path, version="1.7")
        print("wrote", path, os.path.getsize(path))


if __name__ == "__main__":
    import sys
    main(*(sys.argv[1:2] or ["out"]))
