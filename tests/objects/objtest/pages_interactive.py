"""Pages for links, actions and interactive form fields."""
from pikepdf import Array, Dictionary, Name, String
from reportlab.pdfbase.pdfmetrics import stringWidth

from .core import Page, circle_path, n, poly_path, rect_path, round_rect_path
from .pages_annots import DATE, ap_form, markup
from .palette import HUES, fmt


def helv(doc):
    return doc.fonts.standard("Helvetica")


def zadb(doc):
    return doc.fonts.standard("ZapfDingbats")


def fres(doc, *pairs):
    return Dictionary(Font=Dictionary({("/" + k): v for k, v in pairs}))


def link(p, rect, action=None, dest=None, contents="Link", **entries):
    d = Dictionary(Type=Name.Annot, Subtype=Name.Link, Rect=Array([round(v, 3) for v in rect]),
                   Contents=String(contents), F=4)
    if action is not None:
        d.A = action
    if dest is not None:
        d.Dest = dest
    for k, v in entries.items():
        d[Name("/" + k)] = v
    if "Border" not in entries and "BS" not in entries:
        d.Border = Array([0, 0, 0])
    return p.annot(d, tag="Link", alt=contents)


def label(p, x, y, s, size=7.5, role="accent", font="Sans"):
    return p.text(x, y, s, size=size, role=role, font=font, tag="Span")


# -- 17. Links and actions ----------------------------------------------------------------------

def page_links(doc, res):
    p = Page(doc, "Links and actions",
             "Link borders are drawn by the viewer from the C entry, so C must follow the theme. Actions that "
             "show, hide or recolour things on the page are here too; colours set by JavaScript are out of a "
             "theme's reach, which the spec should say.")
    pal = p.pal
    t = p.grid(3, 4)
    sans = p.font("Sans")
    pages = doc.pages

    x, y, w, h = p.tile(t[0], "Link with a border colour: C", "T176, T210", "viewer",
                        note="URI action; the viewer draws the border from C")
    tw = label(p, x + 6, y + h / 2, "example.com")
    link(p, [x + 3, y + h / 2 - 4, x + 9 + tw, y + h / 2 + 10], Dictionary(S=Name.URI, URI=String("https://example.com/")),
         contents="Link to example.com", Border=Array([0, 0, 1]), C=doc.rgb("accent"))

    x, y, w, h = p.tile(t[1], "Highlight modes: H", "T176", "viewer", note="N, I, O and P change how a click looks")
    for i, mode in enumerate(["N", "I", "O", "P"]):
        lx = x + 4 + i * w / 4
        tw = label(p, lx, y + h / 2, "H /" + mode)
        link(p, [lx - 2, y + h / 2 - 4, lx + tw + 2, y + h / 2 + 10], dest=Array([pages[i].obj, Name.Fit]),
             contents="Go to page %d" % (i + 1), H=Name("/" + mode), Border=Array([0, 0, 1]), C=doc.rgb(HUES[i]))

    x, y, w, h = p.tile(t[2], "Link over two lines: QuadPoints", "T176", "viewer")
    label(p, x + 4, y + h / 2 + 8, "This link runs over")
    label(p, x + 4, y + h / 2 - 4, "two lines of text.")
    w1, w2 = sans.width("This link runs over", 7.5), sans.width("two lines of text.", 7.5)
    link(p, [x + 2, y + h / 2 - 8, x + 6 + max(w1, w2), y + h / 2 + 18], dest=Array([pages[0].obj, Name.Fit]),
         contents="Link on two lines", Border=Array([0, 0, 1]), C=doc.rgb("green"),
         QuadPoints=Array([x + 2, y + h / 2 + 17, x + 6 + w1, y + h / 2 + 17, x + 2, y + h / 2 + 5, x + 6 + w1, y + h / 2 + 5,
                           x + 2, y + h / 2 + 5, x + 6 + w2, y + h / 2 + 5, x + 2, y + h / 2 - 7, x + 6 + w2, y + h / 2 - 7]))

    x, y, w, h = p.tile(t[3], "Link with a dashed border style: BS", "T168, T176", "viewer")
    tw = label(p, x + 6, y + h / 2, "Dashed border link")
    link(p, [x + 3, y + h / 2 - 5, x + 9 + tw, y + h / 2 + 11], dest=Array([pages[1].obj, Name.XYZ, 0, 842, 1.5]),
         contents="Dashed link to page 2 at 150%", BS=Dictionary(W=1, S=Name.D, D=Array([3, 2])), C=doc.rgb("purple"))

    x, y, w, h = p.tile(t[4], "Destinations: XYZ, Fit, FitH, FitR, FitB", "T149", "swaps")
    dests = [("XYZ", Array([pages[2].obj, Name.XYZ, 36, 700, 2])), ("Fit", Array([pages[3].obj, Name.Fit])),
             ("FitH", Array([pages[4].obj, Name.FitH, 500])), ("FitR", Array([pages[5].obj, Name.FitR, 36, 400, 300, 700])),
             ("FitB", Array([pages[6].obj, Name.FitB]))]
    for i, (nm, d) in enumerate(dests):
        ly = y + h - 12 - i * (h - 14) / 5
        tw = label(p, x + 6, ly, "%s to page %d" % (nm, 3 + i))
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], dest=d, contents="%s destination" % nm)

    x, y, w, h = p.tile(t[5], "Named, remote and embedded go-to", "T202, T203, T204, T205", "swaps",
                        note="GoToR names a file that is not shipped")
    doc.named_dests["colour-spaces"] = Array([pages[1].obj, Name.Fit])
    target = doc.embedded.get("reference-target.pdf")
    for i, (txt, act) in enumerate([
            ("Named destination", Dictionary(S=Name.GoTo, D=String("colour-spaces"))),
            ("Remote file (GoToR)", Dictionary(S=Name.GoToR, F=String("other.pdf"), D=Array([0, Name.Fit]), NewWindow=True)),
            ("Embedded file (GoToE)", Dictionary(S=Name.GoToE, D=Array([0, Name.Fit]),
                                                 T=Dictionary(R=Name.C, N=String("reference-target.pdf"))))]):
        ly = y + h - 14 - i * 20
        tw = label(p, x + 6, ly, txt)
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], act, contents=txt)

    x, y, w, h = p.tile(t[6], "Named actions", "T215, T216", "swaps")
    for i, nm in enumerate(["FirstPage", "PrevPage", "NextPage", "LastPage"]):
        ly = y + h - 14 - i * (h - 14) / 4
        tw = label(p, x + 6, ly, nm)
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.Named, N=Name("/" + nm)), contents=nm)

    x, y, w, h = p.tile(t[7], "Hide action and the Hidden flag", "T214, T167", "swaps",
                        note="Show and hide a hidden square")
    sq = [x + w * 0.55, y + 10, x + w - 6, y + h - 10]
    rw, rh = sq[2] - sq[0], sq[3] - sq[1]
    hidden = markup(p, "Square", sq, "A square that starts hidden", ap_form(doc, rw, rh, "%s %s f" % (pal.rg("pink"), round_rect_path(0, 0, rw, rh, 6))),
                    F=4 | 2, C=doc.rgb("pink"), IC=doc.rgb("pink"))
    for i, (txt, hide) in enumerate([("Show it", False), ("Hide it", True)]):
        ly = y + h / 2 + 8 - i * 20
        tw = label(p, x + 6, ly, txt)
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.Hide, T=hidden, H=hide), contents=txt)

    x, y, w, h = p.tile(t[8], "JavaScript action and Next", "T221, T196", "viewer",
                        note="Colours in scripts are out of a theme's reach")
    doc.doc_js["themeHelpers"] = ("function paint(name, c) { var f = this.getField(name); if (f) f.fillColor = c; }")
    ly = y + h / 2 + 6
    tw = label(p, x + 6, ly, "Make the name field yellow")
    link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9],
         Dictionary(S=Name.JavaScript, JS=String("paint('name', color.yellow);"),
                    Next=Dictionary(S=Name.JavaScript, JS=String("console.println('chained action ran');"))),
         contents="Run JavaScript that recolours a field")
    ly -= 20
    tw = label(p, x + 6, ly, "Reset its colour")
    link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.JavaScript, JS=String("paint('name', color.transparent);")),
         contents="Run JavaScript that resets the colour")

    x, y, w, h = p.tile(t[9], "Launch, Thread and Transition actions", "T207, T209, T219", "viewer",
                        note="Launch is usually blocked; Thread follows the article")
    for i, (txt, act) in enumerate([
            ("Launch readme.txt", Dictionary(S=Name.Launch, F=String("readme.txt"), NewWindow=True)),
            ("Read the article thread", Dictionary(S=Name.Thread, D=0)),
            ("Dissolve transition", Dictionary(S=Name.Trans, Trans=Dictionary(Type=Name.Trans, S=Name.Dissolve, D=1)))]):
        ly = y + h - 14 - i * 20
        tw = label(p, x + 6, ly, txt)
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], act, contents=txt)

    x, y, w, h = p.tile(t[10], "Flags: NoView, Print off, ToggleNoView", "T167", "viewer",
                        note="Left prints but is not shown; middle shows but does not print")
    q = (w - 12) / 3
    for i, (flags, role, desc) in enumerate([(32 | 4, "red", "NoView, printed"), (0, "green", "Shown, not printed"),
                                              (4 | 256, "blue", "ToggleNoView")]):
        r = [x + 2 + i * (q + 4), y + 10, x + 2 + i * (q + 4) + q, y + h - 10]
        markup(p, "Square", r, desc, ap_form(doc, q, r[3] - r[1], "%s %s f" % (pal.rg(role), round_rect_path(0, 0, q, r[3] - r[1], 5))),
               F=flags, C=doc.rgb(role), IC=doc.rgb(role))

    x, y, w, h = p.tile(t[11], "Page and document additional actions", "T197, T198, T200", "viewer",
                        note="This page logs when opened and closed")
    p.opts["AA"] = Dictionary(O=Dictionary(S=Name.JavaScript, JS=String("console.println('links page opened');")),
                              C=Dictionary(S=Name.JavaScript, JS=String("console.println('links page closed');")))
    doc.catalog_extra["AA"] = Dictionary(WC=Dictionary(S=Name.JavaScript, JS=String("console.println('closing');")),
                                         DP=Dictionary(S=Name.JavaScript, JS=String("console.println('printed');")))
    sq = [x + 6, y + 10, x + w - 6, y + h - 10]
    sw_, sh_ = sq[2] - sq[0], sq[3] - sq[1]
    widget(p, "Btn", "hover", sq, flags=1 << 16, da="%s /Helv 9 Tf" % pal.rg("teal"),
           mk=mk(doc, "tile", "teal", CA=String("Hover or click here")),
           ap=Dictionary(N=ap_form(doc, sw_, sh_, "%s %s f %s 2 w %s S BT /Helv 9 Tf %s 8 %s Td (Hover or click here) Tj ET" % (
               pal.rg("tile"), round_rect_path(0, 0, sw_, sh_, 6), pal.RG("teal"), round_rect_path(1, 1, sw_ - 2, sh_ - 2, 6),
               pal.rg("teal"), n(sh_ / 2 - 3)), [_FontRef("Helv", helv(doc).obj)])),
           extra={"AA": Dictionary(E=Dictionary(S=Name.JavaScript, JS=String("console.println('enter');")),
                                   X=Dictionary(S=Name.JavaScript, JS=String("console.println('exit');")),
                                   D=Dictionary(S=Name.JavaScript, JS=String("console.println('down');")),
                                   U=Dictionary(S=Name.JavaScript, JS=String("console.println('up');")))},
           tu="Button with enter, exit, down and up actions")
    return p


# -- form field helpers --------------------------------------------------------------------------------

def widget(p, ft, name, rect, *, value=None, flags=0, mk=None, da=None, ap=None, q=None, extra=None, parent=None,
           tu=None):
    d = Dictionary(Type=Name.Annot, Subtype=Name.Widget, Rect=Array([round(v, 3) for v in rect]), F=4)
    if parent is None:
        d.FT = Name("/" + ft)
        d.T = String(name)
        d.TU = String(tu or name)
        if flags:
            d.Ff = flags
        if value is not None:
            d.V = value
        if da:
            d.DA = String(da)
    else:
        d.Parent = parent
    if q is not None:
        d.Q = q
    if mk is not None:
        d.MK = mk
    if ap is not None:
        d.AP = ap
    for k, v in (extra or {}).items():
        d[Name("/" + k)] = v
    a = p.annot(d, tag="Form", alt=tu or name)
    if parent is None:
        p.doc.fields.append(a)
    return a


def mk(doc, bg="tile", bc="rule", **more):
    d = Dictionary()
    if bg:
        d.BG = doc.rgb(bg)
    if bc:
        d.BC = doc.rgb(bc)
    for k, v in more.items():
        d[Name("/" + k)] = v
    return d


def frame(pal, w, h, bg="tile", bc="rule", bw=1):
    out = []
    if bg:
        out.append("%s %s f" % (pal.rg(bg), rect_path(0, 0, w, h)))
    if bc:
        out.append("%s %s w %s S" % (pal.RG(bc), n(bw), rect_path(bw / 2, bw / 2, w - bw, h - bw)))
    return " ".join(out)


def esc(s):
    return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def tx_ap(doc, w, h, lines, role="ink", size=9, align=0, bg="tile", bc="rule", comb=None):
    pal = doc.pal
    hv = helv(doc)
    body = [frame(pal, w, h, bg, bc), "/Tx BMC q 1 1 %s %s re W n BT /Helv %s Tf %s" % (n(w - 2), n(h - 2), n(size), pal.rg(role))]
    if comb:
        cell = w / comb
        for i, ch in enumerate(lines[0]):
            cw = stringWidth(ch, "Helvetica", size)
            body.append("1 0 0 1 %s %s Tm %s Tj" % (n(i * cell + (cell - cw) / 2), n((h - size) / 2 + 1.5), esc(ch)))
        body.append("ET Q EMC %s 0.5 w %s S" % (pal.RG("rule"), " ".join(
            "%s 0 m %s %s l" % (n(i * cell), n(i * cell), n(h)) for i in range(1, comb))))
    else:
        top = h - size - 2 if len(lines) > 1 else (h - size) / 2 + 1.5
        for i, line in enumerate(lines):
            lw = stringWidth(line, "Helvetica", size)
            xx = 2 if align == 0 else (w - lw) / 2 if align == 1 else w - lw - 2
            body.append("1 0 0 1 %s %s Tm %s Tj" % (n(xx), n(top - i * size * 1.2), esc(line)))
        body.append("ET Q EMC")
    return ap_form(doc, w, h, " ".join(body), [_FontRef("Helv", hv.obj)])


class _FontRef:
    def __init__(self, key, obj):
        self.key, self.obj = key, obj


# -- 18. Form fields: text and choice --------------------------------------------------------------------

def page_fields_text(doc, res):
    p = Page(doc, "Form fields: text and choice",
             "Text and choice fields. Each widget's appearance is drawn in the theme's colours, and its MK "
             "background and border and its DA text colour say the same, because viewers redraw fields as soon "
             "as someone types.", Tabs=Name.S)
    pal = p.pal
    t = p.grid(3, 5)
    ink = "%s /Helv 9 Tf" % pal.rg("ink")

    def tile_field(i, title, ref, expect, note=None):
        x, y, w, h = p.tile(t[i], title, ref, expect, note=note)
        return x, y, w, h

    x, y, w, h = tile_field(0, "Text field", "T226, T228, T232", "swaps")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Tx", "name", r, value=String("Ada Lovelace"), da=ink, mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["Ada Lovelace"])), tu="Name")

    x, y, w, h = tile_field(1, "Multiline text field", "T231", "swaps")
    r = [x + 4, y + 6, x + w - 4, y + h - 4]
    lines = ["Several lines of text,", "wrapped by the field,", "in the theme's ink."]
    widget(p, "Tx", "notes", r, value=String("\r".join(lines)), flags=1 << 12, da=ink, mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], r[3] - r[1], lines)), tu="Notes")

    x, y, w, h = tile_field(2, "Password field", "T231", "swaps")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Tx", "password", r, flags=1 << 13, da=ink, mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["\x95" * 8])), tu="Password")

    x, y, w, h = tile_field(3, "Comb field: MaxLen 6", "T231, T232", "swaps")
    r = [x + 4, y + h / 2 - 10, x + w - 4, y + h / 2 + 10]
    widget(p, "Tx", "code", r, value=String("AB12CD"), flags=1 << 24, da="%s /Helv 12 Tf" % pal.rg("ink"), mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 20, ["AB12CD"], size=12, comb=6)), extra={"MaxLen": 6}, tu="Code")

    x, y, w, h = tile_field(4, "File-select field", "T231", "swaps")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Tx", "upload", r, value=String("report.pdf"), flags=1 << 20, da=ink, mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["report.pdf"])), tu="File to upload")

    x, y, w, h = tile_field(5, "Rich text field: RV and DS", "T228, T231", "swaps", note="Span colours live in RV")
    r = [x + 4, y + h / 2 - 12, x + w - 4, y + h / 2 + 12]
    rv = ('<?xml version="1.0"?><body xmlns="http://www.w3.org/1999/xhtml" xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/" '
          'xfa:APIVersion="Acrobat:23.0.0" xfa:spec="2.0.2"><p style="color:%s">Plain and <span style="color:%s;'
          'font-weight:bold">coloured</span> text</p></body>' % (pal.hexstr("ink"), pal.hexstr("red")))
    rw = r[2] - r[0]
    apb = (frame(pal, rw, 24) + " /Tx BMC q BT /Helv 9 Tf %s 3 8 Td (Plain and ) Tj %s (coloured) Tj %s ( text) Tj ET Q EMC" %
           (pal.rg("ink"), pal.rg("red"), pal.rg("ink")))
    widget(p, "Tx", "rich", r, value=String("Plain and coloured text"), flags=1 << 25, da=ink, mk=mk(doc),
           ap=Dictionary(N=ap_form(doc, rw, 24, apb, [_FontRef("Helv", helv(doc).obj)])),
           extra={"RV": String(rv), "DS": String("font: Helvetica 9pt; color:%s" % pal.hexstr("ink"))}, tu="Rich text")

    x, y, w, h = tile_field(6, "Alignment: Q 1 and Q 2", "T228", "swaps")
    for i, qv in enumerate([1, 2]):
        r = [x + 4, y + h - 26 - i * 26, x + w - 4, y + h - 8 - i * 26]
        txt = ["Centred", "Right aligned"][i]
        widget(p, "Tx", "align%d" % qv, r, value=String(txt), da=ink, mk=mk(doc), q=qv,
               ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, [txt], align=qv)), tu=txt)

    x, y, w, h = tile_field(7, "Border styles: beveled, inset, underline", "T168, T192", "swaps",
                            note="Bevel shades come from MK BG")
    for i, (style, label) in enumerate([("B", "Beveled"), ("I", "Inset"), ("U", "Underline")]):
        r = [x + 4, y + h - 26 - i * 22, x + w - 4, y + h - 8 - i * 22]
        rw = r[2] - r[0]
        light_, dark_ = ("paper", "muted") if style == "B" else ("muted", "rule")
        if style == "U":
            frame_ = "%s 1 w 0 0.5 m %s 0.5 l S" % (pal.RG("ink"), n(rw))
        else:
            frame_ = ("%s %s f %s 1 w %s S %s 1 1 m 1 17 l %s 17 l S %s %s 17 m %s 1 l 1 1 l S" % (
                pal.rg("tile"), rect_path(0, 0, rw, 18), pal.RG("ink"), rect_path(0.5, 0.5, rw - 1, 17),
                pal.RG(light_ if style == "B" else dark_), n(rw - 1), pal.RG(dark_ if style == "B" else light_),
                n(rw - 1), n(rw - 1)))
        apf = ap_form(doc, rw, 18, frame_ + " /Tx BMC q BT /Helv 9 Tf %s 4 5 Td %s Tj ET Q EMC" % (pal.rg("ink"), esc(label)),
                      [_FontRef("Helv", helv(doc).obj)])
        widget(p, "Tx", "border_" + style, r, value=String(label), da=ink,
               mk=mk(doc, None if style == "U" else "tile", "ink"), ap=Dictionary(N=apf),
               extra={"BS": Dictionary(W=1, S=Name("/" + style))}, tu=label + " border")

    x, y, w, h = tile_field(8, "Required and read-only flags", "T227", "swaps")
    r = [x + 4, y + h - 26, x + w - 4, y + h - 8]
    widget(p, "Tx", "required", r, flags=2, da=ink, mk=mk(doc, "tile", "red"),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["Required"], role="muted", bc="red")), tu="Required field")
    r = [x + 4, y + h - 52, x + w - 4, y + h - 34]
    widget(p, "Tx", "readonly", r, value=String("Read only"), flags=1, da=ink, mk=mk(doc, "rule", None),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["Read only"], bg="rule", bc=None)), tu="Read-only field")

    x, y, w, h = tile_field(9, "Number format script: red negatives", "T199, T221", "viewer",
                            note="AFNumber_Format sets color.red when negative")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    fmt_js = 'AFNumber_Format(2, 0, 1, 0, "\\u00A3", true);'
    widget(p, "Tx", "balance", r, value=String("-42.50"), da=ink, mk=mk(doc), q=2,
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["-\xa342.50"], role="red", align=2)),
           extra={"AA": Dictionary(F=Dictionary(S=Name.JavaScript, JS=String(fmt_js)),
                                   K=Dictionary(S=Name.JavaScript, JS=String('AFNumber_Keystroke(2, 0, 1, 0, "\\u00A3", true);')))},
           tu="Balance")

    x, y, w, h = tile_field(10, "Calculated field: CO", "T199, T224", "viewer", note="Total = a + b, by script")
    names = []
    for i, nm in enumerate(["a", "b"]):
        r = [x + 4 + i * (w - 8) / 3, y + h / 2 - 9, x + (i + 1) * (w - 8) / 3, y + h / 2 + 9]
        names.append(widget(p, "Tx", nm, r, value=String(str(20 + 22 * i)), da=ink, mk=mk(doc),
                            ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, [str(20 + 22 * i)], align=1)), q=1, tu="Value " + nm))
    r = [x + 8 + 2 * (w - 8) / 3, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    total = widget(p, "Tx", "total", r, value=String("62"), da="%s /Helv 9 Tf" % pal.rg("accent"), mk=mk(doc, "tile", "accent"), q=1,
                   ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["62"], role="accent", align=1, bc="accent")),
                   extra={"AA": Dictionary(C=Dictionary(S=Name.JavaScript, JS=String('AFSimple_Calculate("SUM", new Array("a", "b"));')))},
                   tu="Total")
    doc.acroform_extra["CO"] = Array([total])

    def list_ap(w, h, items, selected, combo=False, value=None):
        body = [frame(pal, w, h), "/Tx BMC q 1 1 %s %s re W n" % (n(w - 2), n(h - 2))]
        if combo:
            body.append("BT /Helv 9 Tf %s 3 %s Td %s Tj ET" % (pal.rg("ink"), n((h - 9) / 2 + 1.5), esc(value)))
            body.append("Q EMC %s %s f %s %s f" % (pal.rg("rule"), rect_path(w - 14, 1, 13, h - 2), pal.rg("ink"),
                                                   poly_path([(w - 11, h / 2 + 2), (w - 4, h / 2 + 2), (w - 7.5, h / 2 - 3)], close=True)))
        else:
            for i, it in enumerate(items):
                yy = h - 12 - i * 11
                if i in selected:
                    body.append("%s %s f" % (pal.rg("accent"), rect_path(1, yy - 2.5, w - 2, 11)))
                body.append("BT /Helv 9 Tf %s 3 %s Td %s Tj ET" % (pal.rg("paper" if i in selected else "ink"), n(yy), esc(it)))
            body.append("Q EMC")
        return ap_form(doc, w, h, " ".join(body), [_FontRef("Helv", helv(doc).obj)])

    items = ["Red", "Green", "Blue", "Purple"]
    x, y, w, h = tile_field(11, "List box", "T233, T234", "swaps", note="The selected row is drawn in the accent")
    r = [x + 4, y + 4, x + w - 4, y + h - 4]
    widget(p, "Ch", "colour", r, value=String("Green"), da=ink, mk=mk(doc),
           ap=Dictionary(N=list_ap(r[2] - r[0], r[3] - r[1], items, {1})),
           extra={"Opt": Array([String(i) for i in items]), "I": Array([1])}, tu="Colour")

    x, y, w, h = tile_field(12, "Multi-select list box", "T233, T234", "swaps")
    r = [x + 4, y + 4, x + w - 4, y + h - 4]
    widget(p, "Ch", "colours", r, value=Array([String("Red"), String("Blue")]), flags=1 << 21, da=ink, mk=mk(doc),
           ap=Dictionary(N=list_ap(r[2] - r[0], r[3] - r[1], items, {0, 2})),
           extra={"Opt": Array([Array([String(i.lower()), String(i)]) for i in items]), "I": Array([0, 2])}, tu="Colours")

    x, y, w, h = tile_field(13, "Combo box", "T233", "swaps")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Ch", "size", r, value=String("Medium"), flags=1 << 17, da=ink, mk=mk(doc),
           ap=Dictionary(N=list_ap(r[2] - r[0], 18, None, None, True, "Medium")),
           extra={"Opt": Array([String(s) for s in ("Small", "Medium", "Large")])}, tu="Size")

    x, y, w, h = tile_field(14, "Editable combo box", "T233", "swaps")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Ch", "city", r, value=String("Bristol"), flags=(1 << 17) | (1 << 18), da=ink, mk=mk(doc),
           ap=Dictionary(N=list_ap(r[2] - r[0], 18, None, None, True, "Bristol")),
           extra={"Opt": Array([String(s) for s in ("Bristol", "Manchester", "Stevenage")])}, tu="City")
    return p


# -- 19. Form fields: buttons and signatures -------------------------------------------------------------

def page_fields_buttons(doc, res):
    p = Page(doc, "Form fields: buttons and signatures",
             "Check boxes in all six styles, a radio group, push buttons with captions, rollover and icons, a "
             "signature field, and scripts that change colours on focus. A theme can recolour appearances; it "
             "cannot reach a colour written in a script.", Tabs=Name.S)
    pal = p.pal
    t = p.grid(3, 4)
    zd = zadb(doc)
    hv = helv(doc)

    def check_ap(w, h, char, role, on=True, down=False):
        body = frame(pal, w, h, "rule" if down else "tile", "ink")
        if on:
            cw = stringWidth(char, "ZapfDingbats", h * 0.75)
            body += " q BT /ZaDb %s Tf %s %s %s Td %s Tj ET Q" % (n(h * 0.75), pal.rg(role), n((w - cw) / 2), n(h * 0.2), esc(char))
        return ap_form(doc, w, h, body, [_FontRef("ZaDb", zd.obj)])

    x, y, w, h = p.tile(t[0], "Check boxes: six styles", "T229, T230, T192", "swaps", note="MK CA picks the ZapfDingbats mark")
    styles = [("4", "check"), ("l", "circle"), ("8", "cross"), ("u", "diamond"), ("n", "square"), ("H", "star")]
    for i, (ch, nm) in enumerate(styles):
        bx, by = x + 6 + (i % 3) * (w - 12) / 3, y + h - 30 - (i // 3) * 36
        s = 16
        on = i % 2 == 0
        widget(p, "Btn", "check_" + nm, [bx, by, bx + s, by + s], value=Name.On if on else Name.Off,
               da="%s /ZaDb 0 Tf" % pal.rg(HUES[i]), mk=mk(doc, "tile", "ink", CA=String(ch)),
               ap=Dictionary(N=Dictionary(On=check_ap(s, s, ch, HUES[i]), Off=check_ap(s, s, ch, HUES[i], on=False)),
                             D=Dictionary(On=check_ap(s, s, ch, HUES[i], down=True), Off=check_ap(s, s, ch, HUES[i], on=False, down=True))),
               extra={"AS": Name.On if on else Name.Off}, tu="Check box, %s style" % nm)
        p.text(bx + s + 3, by + 5, nm, size=6, role="muted", tag="Caption")

    x, y, w, h = p.tile(t[1], "Radio group", "T229, T230", "swaps", note="One parent field, three widgets")
    parent = doc.pdf.make_indirect(Dictionary(FT=Name.Btn, T=String("shirt"), TU=String("Shirt size"),
                                              Ff=(1 << 15) | (1 << 14), V=Name("/M"), Kids=Array(),
                                              DA=String("%s /ZaDb 0 Tf" % pal.rg("accent"))))
    doc.fields.append(parent)
    for i, opt in enumerate(["S", "M", "L"]):
        bx, by, s = x + 8 + i * (w - 16) / 3, y + h / 2 - 8, 16
        on_ap = ap_form(doc, s, s, "%s %s f %s 1 w %s S %s %s f" % (pal.rg("tile"), circle_path(8, 8, 7.5), pal.RG("ink"),
                                                                  circle_path(8, 8, 7.5), pal.rg("accent"), circle_path(8, 8, 4)))
        off_ap = ap_form(doc, s, s, "%s %s f %s 1 w %s S" % (pal.rg("tile"), circle_path(8, 8, 7.5), pal.RG("ink"), circle_path(8, 8, 7.5)))
        kid = widget(p, "Btn", None, [bx, by, bx + s, by + s], parent=parent, mk=mk(doc, "tile", "ink", CA=String("l")),
                     ap=Dictionary(N=Dictionary({("/" + opt): on_ap, "/Off": off_ap})),
                     extra={"AS": Name("/" + opt) if opt == "M" else Name.Off})
        parent.Kids.append(kid)
        p.text(bx + s + 3, by + 5, opt, size=7, role="muted", tag="Caption")

    def button_ap(w, h, caption, bg, fg="paper", bc="ink"):
        cw = stringWidth(caption, "Helvetica-Bold", 9)
        return ap_form(doc, w, h, "%s %s f %s 1 w %s S BT /HeBo 9 Tf %s %s %s Td %s Tj ET" % (
            pal.rg(bg), round_rect_path(0, 0, w, h, 4), pal.RG(bc), round_rect_path(0.5, 0.5, w - 1, h - 1, 4), pal.rg(fg),
            n((w - cw) / 2), n((h - 9) / 2 + 2), esc(caption)), [_FontRef("HeBo", doc.fonts.standard("Helvetica-Bold").obj)])

    x, y, w, h = p.tile(t[2], "Push button: N, R and D appearances", "T229, T170, T192, T241", "swaps",
                        note="Captions CA, RC and AC; resets the form")
    r = [x + 10, y + h / 2 - 12, x + w - 10, y + h / 2 + 12]
    bw_, bh_ = r[2] - r[0], r[3] - r[1]
    widget(p, "Btn", "reset", r, flags=1 << 16, da="%s /Helv 9 Tf" % pal.rg("paper"),
           mk=mk(doc, "accent", "ink", CA=String("Reset the form"), RC=String("Click to reset"), AC=String("Resetting")),
           ap=Dictionary(N=button_ap(bw_, bh_, "Reset the form", "accent"), R=button_ap(bw_, bh_, "Click to reset", "teal"),
                         D=button_ap(bw_, bh_, "Resetting", "ink", fg="paper", bc="accent")),
           extra={"A": Dictionary(S=Name.ResetForm)}, tu="Reset the form")

    x, y, w, h = p.tile(t[3], "Icon buttons: MK I, RI, IX, IF and TP", "T192, T250", "swaps",
                        note="Icon only, and caption below; hover and press swap the icon")

    def play_icon(role):
        return doc.form("%s %s f %s %s f" % (pal.rg(role), round_rect_path(0, 0, 32, 32, 6), pal.rg("paper"),
                                              poly_path([(10, 8), (24, 16), (10, 24)], close=True)), [0, 0, 32, 32], Dictionary())

    icon, icon_r, icon_d = play_icon("orange"), play_icon("yellow"), play_icon("red")
    for i, tp in enumerate([1, 2]):
        r = [x + 8 + i * w / 2, y + 10, x + w / 2 - 4 + i * w / 2, y + h - 8]
        bw_, bh_ = r[2] - r[0], r[3] - r[1]
        s = min(bw_, bh_ - (14 if tp == 2 else 0)) - 8

        def face(ic):
            body = "%s %s f q %s 0 0 %s %s %s cm /Ic Do Q" % (pal.rg("tile"), rect_path(0, 0, bw_, bh_), n(s / 32), n(s / 32),
                                                            n((bw_ - s) / 2), n(bh_ - s - 4))
            if tp == 2:
                cw = stringWidth("Play", "Helvetica", 8)
                body += " BT /Helv 8 Tf %s %s 4 Td (Play) Tj ET" % (pal.rg("ink"), n((bw_ - cw) / 2))
            return doc.form(body, [0, 0, bw_, bh_], Dictionary(XObject=Dictionary(Ic=ic), Font=Dictionary(Helv=hv.obj)))

        widget(p, "Btn", "play%d" % tp, r, flags=1 << 16, da="%s /Helv 8 Tf" % pal.rg("ink"),
               mk=mk(doc, "tile", None, I=icon, RI=icon_r, IX=icon_d, TP=tp, CA=String("Play"),
                     IF=Dictionary(SW=Name.A, S=Name.P, A=Array([0.5, 0.5]), FB=False)),
               ap=Dictionary(N=face(icon), R=face(icon_r), D=face(icon_d)),
               extra={"A": Dictionary(S=Name.JavaScript, JS=String("paint('name', color.cyan);"))}, tu="Play button")

    x, y, w, h = p.tile(t[4], "Submit button", "T239, T240", "viewer", note="Submits to an address that does not exist")
    r = [x + 10, y + h / 2 - 12, x + w - 10, y + h / 2 + 12]
    widget(p, "Btn", "submit", r, flags=1 << 16, da="%s /Helv 9 Tf" % pal.rg("paper"), mk=mk(doc, "green", "ink", CA=String("Submit")),
           ap=Dictionary(N=button_ap(r[2] - r[0], r[3] - r[1], "Submit", "green")),
           extra={"A": Dictionary(S=Name.SubmitForm, F=Dictionary(FS=Name.URL, F=String("https://example.invalid/submit")),
                                  Flags=4)}, tu="Submit the form")

    x, y, w, h = p.tile(t[5], "Signature field, unsigned", "T235, T236, T237", "swaps", note="Lock and seed value dictionaries")
    r = [x + 6, y + 10, x + w - 6, y + h - 10]
    sw, sh = r[2] - r[0], r[3] - r[1]
    apb = "%s %s f %s 0.8 w 10 18 m %s 18 l S BT /Helv 8 Tf %s 10 8 Td (Sign here) Tj ET %s 1 w [3 2] 0 d %s S" % (
        pal.rg("tile"), rect_path(0, 0, sw, sh), pal.RG("ink"), n(sw - 10), pal.rg("muted"), pal.RG("accent"),
        rect_path(0.5, 0.5, sw - 1, sh - 1))
    widget(p, "Sig", "signature", r, da="%s /Helv 0 Tf" % pal.rg("ink"), mk=mk(doc, "tile", "accent"),
           ap=Dictionary(N=ap_form(doc, sw, sh, apb, [_FontRef("Helv", hv.obj)])),
           extra={"Lock": doc.pdf.make_indirect(Dictionary(Type=Name.SigFieldLock, Action=Name.All)),
                  "SV": doc.pdf.make_indirect(Dictionary(Type=Name.SV, Reasons=Array([String("I approve this test file")]),
                                                         Ff=0))},
           tu="Signature")

    x, y, w, h = p.tile(t[6], "Focus and blur scripts recolour a field", "T197, T221", "viewer",
                        note="Fo sets a yellow fill; Bl removes it")
    r = [x + 4, y + h / 2 - 9, x + w - 4, y + h / 2 + 9]
    widget(p, "Tx", "focus", r, value=String("Click into me"), da="%s /Helv 9 Tf" % pal.rg("ink"), mk=mk(doc),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["Click into me"])),
           extra={"AA": Dictionary(Fo=Dictionary(S=Name.JavaScript, JS=String("event.target.fillColor = color.yellow;")),
                                   Bl=Dictionary(S=Name.JavaScript, JS=String("event.target.fillColor = color.transparent;")))},
           tu="Field that changes colour on focus")

    x, y, w, h = p.tile(t[7], "Hidden field shown by a button", "T167, T214", "swaps")
    r = [x + 4, y + 8, x + w - 4, y + 26]
    widget(p, "Tx", "secret", r, value=String("Now you see me"), da="%s /Helv 9 Tf" % pal.rg("ink"), mk=mk(doc, "yellow", "ink"),
           ap=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, ["Now you see me"], bg="yellow", bc="ink")), extra={"F": 4 | 2},
           tu="Hidden field")
    r = [x + 10, y + h - 32, x + w - 10, y + h - 10]
    widget(p, "Btn", "reveal", r, flags=1 << 16, da="%s /Helv 9 Tf" % pal.rg("paper"), mk=mk(doc, "purple", "ink", CA=String("Show the field")),
           ap=Dictionary(N=button_ap(r[2] - r[0], r[3] - r[1], "Show the field", "purple")),
           extra={"A": Dictionary(S=Name.Hide, T=String("secret"), H=False)}, tu="Show the hidden field")

    x, y, w, h = p.tile(t[8], "Field hierarchy: a.b names", "T226", "swaps", note="Parent 'address' with two children")
    par = doc.pdf.make_indirect(Dictionary(T=String("address"), FT=Name.Tx, DA=String("%s /Helv 9 Tf" % pal.rg("ink")), Kids=Array()))
    doc.fields.append(par)
    for i, (nm, val) in enumerate([("street", "1 High Street"), ("town", "Bristol")]):
        r = [x + 4, y + h - 26 - i * 24, x + w - 4, y + h - 8 - i * 24]
        kid = p.pdf.make_indirect(Dictionary(Type=Name.Annot, Subtype=Name.Widget, Parent=par, T=String(nm), V=String(val),
                                             Rect=Array(r), F=4, MK=mk(doc), P=p.obj,
                                             AP=Dictionary(N=tx_ap(doc, r[2] - r[0], 18, [val]))))
        p.annots.append(kid)
        from .core import StructElem
        el = StructElem("Form", page=p, alt="address." + nm)
        el.objr = kid
        p.stack[-1].children.append(el)
        par.Kids.append(kid)

    x, y, w, h = p.tile(t[9], "Read-only check box and NoExport", "T227", "swaps")
    s = 18
    widget(p, "Btn", "agree", [x + 8, y + h / 2 - 9, x + 8 + s, y + h / 2 + 9], value=Name.On, flags=1 | 4,
           da="%s /ZaDb 0 Tf" % pal.rg("green"), mk=mk(doc, "tile", "ink", CA=String("4")),
           ap=Dictionary(N=Dictionary(On=check_ap(s, s, "4", "green"), Off=check_ap(s, s, "4", "green", on=False))),
           extra={"AS": Name.On}, tu="Agreed, read only")
    p.text(x + 32, y + h / 2 - 3, "Read only, not exported", size=7, role="muted", tag="Caption")

    x, y, w, h = p.tile(t[10], "Import data action", "T243", "viewer", note="Imports field values from an FDF file")
    r = [x + 10, y + h / 2 - 12, x + w - 10, y + h / 2 + 12]
    widget(p, "Btn", "import", r, flags=1 << 16, da="%s /Helv 9 Tf" % pal.rg("paper"), mk=mk(doc, "teal", "ink", CA=String("Import values")),
           ap=Dictionary(N=button_ap(r[2] - r[0], r[3] - r[1], "Import values", "teal")),
           extra={"A": Dictionary(S=Name.ImportData, F=String("values.fdf"))}, tu="Import values")

    x, y, w, h = p.tile(t[11], "MK colours in grey and CMYK", "T192", "swaps",
                        note="BG and BC can have 1 or 4 components, or none")
    for i, (bg, bc, desc) in enumerate([([pal.gray("tile")], [pal.gray("ink")], "Grey BG and BC"),
                                        (list(pal.cmyk("tile")), list(pal.cmyk("orange")), "CMYK BG and BC"),
                                        ([], list(pal.cmyk("ink")), "No BG (transparent)")]):
        r = [x + 4, y + h - 24 - i * 22, x + w - 4, y + h - 6 - i * 22]
        rw = r[2] - r[0]
        fill = ("%s g %s f" % (fmt(bg), rect_path(0, 0, rw, 18)) if len(bg) == 1 else
                "%s k %s f" % (fmt(bg), rect_path(0, 0, rw, 18)) if len(bg) == 4 else "")
        stroke = ("%s G" % fmt(bc) if len(bc) == 1 else "%s K" % fmt(bc)) + " 1 w %s S" % rect_path(0.5, 0.5, rw - 1, 17)
        txt = "/Tx BMC q BT /Helv 9 Tf %s 3 5 Td %s Tj ET Q EMC" % (pal.rg("ink"), esc(desc))
        apf = ap_form(doc, rw, 18, " ".join(b for b in (fill, stroke, txt) if b), [_FontRef("Helv", hv.obj)])
        widget(p, "Tx", "mk%d" % i, r, value=String(desc), da="%s /Helv 9 Tf" % pal.rg("ink"),
               mk=Dictionary(BG=Array([round(v, 4) for v in bg]), BC=Array([round(v, 4) for v in bc])),
               ap=Dictionary(N=apf), tu=desc)
    return p
